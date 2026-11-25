package _1dknone.cobblemon_extra_move_animation.client.beatup;

import _1dknone.cobblemon_extra_move_animation.beatup.BeatUpPayload;
import com.mojang.blaze3d.vertex.PoseStack;
import java.util.ArrayList;
import java.util.List;
import net.minecraft.client.Minecraft;
import net.minecraft.client.multiplayer.ClientLevel;
import net.minecraft.client.renderer.MultiBufferSource;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.phys.Vec3;

/**
 * One use of Beat Up: an afterimage per strike, timed from the moment the move started. Time runs on
 * client ticks plus the frame's partial tick, like the actor and target animations it plays alongside,
 * so the strikes stay on the frames where the target flinches.
 */
final class BeatUpSequence {
    private final ClientLevel world;
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
    private Vec3 user;
    private Vec3 target;
    private Entity targetEntity;
    private Vec3 facing = new Vec3(0, 0, 1);
    private float userRadius = 0.4F;
    private float targetRadius = 0.4F;

    BeatUpSequence(ClientLevel world, BeatUpPayload payload) {
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
    boolean tick(Minecraft client) {
        if (client.level != world) {
            return false;
        }
        ticks++;
        float seconds = ticks / 20F;
        if (seconds > end) {
            return false;
        }
        Stage stage = stage(1F, client.gameRenderer.getMainCamera().getPosition());
        if (stage != null) {
            for (Afterimage afterimage : afterimages) {
                afterimage.tick(client, world, stage, seconds);
            }
        }
        return true;
    }

    void render(PoseStack matrices, MultiBufferSource consumers, Vec3 camera, float tickDelta) {
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

    private Stage stage(float tickDelta, Vec3 camera) {
        Entity userEntity = world.getEntity(userId);
        if (userEntity != null) {
            user = userEntity.getPosition(tickDelta);
            userRadius = userEntity.getBbWidth() / 2;
            facing = Vec3.directionFromRotation(0, userEntity.getVisualRotationYInDegrees());
        }
        targetEntity = targetId >= 0 ? world.getEntity(targetId) : null;
        if (targetEntity != null) {
            target = targetEntity.getPosition(tickDelta);
            targetRadius = targetEntity.getBbWidth() / 2;
        }
        if (user == null) {
            return null;
        }
        Vec3 targetPos = target != null ? target : user.add(facing.scale(3));
        Vec3 flat = new Vec3(targetPos.x - user.x, 0, targetPos.z - user.z);
        double distance = flat.length();
        Vec3 forward = distance > 1.0E-3 ? flat.scale(1 / distance) : new Vec3(facing.x, 0, facing.z).normalize();
        return new Stage(user, targetPos, forward, new Vec3(-forward.z, 0, forward.x), distance, userRadius, targetRadius,
                camera);
    }

    /**
     * Where the user and the target stand: feet positions, the horizontal unit vector from the user
     * towards the target and the one square to it, both Pokemon's horizontal radii, and where this
     * client's camera is.
     */
    record Stage(Vec3 user, Vec3 target, Vec3 forward, Vec3 side, double distance, float userRadius, float targetRadius,
                 Vec3 camera) {
    }
}
