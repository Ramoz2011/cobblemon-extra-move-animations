package _1dknone.cobblemon_extra_move_animation.client.beatup;

import _1dknone.cobblemon_extra_move_animation.beatup.BeatUpPayload;
import net.minecraft.client.MinecraftClient;
import net.minecraft.client.render.VertexConsumerProvider;
import net.minecraft.client.util.math.MatrixStack;
import net.minecraft.client.world.ClientWorld;
import net.minecraft.entity.Entity;
import net.minecraft.util.math.Vec3d;

import java.util.ArrayList;
import java.util.List;

/**
 * One use of Beat Up: an afterimage per strike, timed from the moment the move started. Time runs on
 * client ticks plus the frame's partial tick, like the actor and target animations it plays alongside,
 * so the strikes stay on the frames where the target flinches.
 */
final class BeatUpSequence {
    private final ClientWorld world;
    private final int userId;
    private final int targetId;
    private final List<Afterimage> afterimages = new ArrayList<>();
    private final TargetFlash flash = new TargetFlash();
    private final boolean landed;
    private final float firstStrike;
    private final float interval;
    private final float end;

    private int ticks;
    private float lastFrame = -1;
    // the last known positions, so an entity that unloads mid-move doesn't snap its afterimages away
    private Vec3d user;
    private Vec3d target;
    private Entity targetEntity;
    private Vec3d facing = new Vec3d(0, 0, 1);
    private float userRadius = 0.4F;
    private float targetRadius = 0.4F;

    BeatUpSequence(ClientWorld world, BeatUpPayload payload) {
        this.world = world;
        this.userId = payload.userId();
        this.targetId = payload.targetId();
        this.landed = payload.hits() > 0;
        this.firstStrike = payload.firstStrike();
        this.interval = payload.interval();
        boolean whiff = !landed;
        List<BeatUpPayload.Teammate> teammates = payload.teammates();
        for (int i = 0; i < teammates.size(); i++) {
            float strike = payload.firstStrike() + payload.interval() * i;
            afterimages.add(new Afterimage(teammates.get(i), i, strike - Afterimage.CONTACT, whiff));
        }
        this.end = afterimages.getLast().appear + Afterimage.GONE + 0.05F;
    }

    /** Runs once per client tick; returns false when the sequence is over. */
    boolean tick(MinecraftClient client) {
        if (client.world != world) {
            return false;
        }
        ticks++;
        float seconds = ticks / 20F;
        if (seconds > end) {
            return false;
        }
        Stage stage = stage(1F, client.gameRenderer.getCamera().getPos());
        if (stage != null) {
            for (Afterimage afterimage : afterimages) {
                afterimage.tick(client, world, stage, seconds);
            }
        }
        return true;
    }

    void render(MatrixStack matrices, VertexConsumerProvider consumers, Vec3d camera, float tickDelta) {
        float now = ticks + tickDelta;
        // FloatingState advances by the time since the last frame it was given
        float frameTicks = lastFrame < 0 ? 0 : Math.max(0, now - lastFrame);
        lastFrame = now;
        Stage stage = stage(tickDelta, camera);
        if (stage == null) {
            return;
        }
        float seconds = now / 20F;
        if (landed && targetEntity != null) {
            flash.render(matrices, consumers, camera, targetEntity, tickDelta, flashStrength(seconds));
        }
        for (Afterimage afterimage : afterimages) {
            afterimage.render(matrices, consumers, camera, stage, seconds, frameTicks);
        }
    }

    /** The target's dark flash: snaps on at each strike and fades over the next few frames. */
    private float flashStrength(float seconds) {
        float strength = 0;
        for (int i = 0; i < afterimages.size(); i++) {
            float since = seconds - (firstStrike + interval * i);
            if (since >= -0.01F && since <= 0.12F) {
                strength = Math.max(strength, since < 0.02F ? (since + 0.01F) / 0.03F : 1 - (since - 0.02F) / 0.1F);
            }
        }
        return strength;
    }

    private Stage stage(float tickDelta, Vec3d camera) {
        Entity userEntity = world.getEntityById(userId);
        if (userEntity != null) {
            user = userEntity.getLerpedPos(tickDelta);
            userRadius = userEntity.getWidth() / 2;
            facing = Vec3d.fromPolar(0, userEntity.getBodyYaw());
        }
        targetEntity = targetId >= 0 ? world.getEntityById(targetId) : null;
        if (targetEntity != null) {
            target = targetEntity.getLerpedPos(tickDelta);
            targetRadius = targetEntity.getWidth() / 2;
        }
        if (user == null) {
            return null;
        }
        Vec3d targetPos = target != null ? target : user.add(facing.multiply(3));
        Vec3d flat = new Vec3d(targetPos.x - user.x, 0, targetPos.z - user.z);
        double distance = flat.length();
        Vec3d forward = distance > 1.0E-3 ? flat.multiply(1 / distance) : new Vec3d(facing.x, 0, facing.z).normalize();
        return new Stage(user, targetPos, forward, new Vec3d(-forward.z, 0, forward.x), distance, userRadius, targetRadius,
                camera);
    }

    /**
     * Where the user and the target stand: feet positions, the horizontal unit vector from the user
     * towards the target and the one square to it, both Pokemon's horizontal radii, and where this
     * client's camera is.
     */
    record Stage(Vec3d user, Vec3d target, Vec3d forward, Vec3d side, double distance, float userRadius, float targetRadius,
                 Vec3d camera) {
    }
}
