package _1dknone.cobblemon_extra_move_animation.client.beatup;

import _1dknone.cobblemon_extra_move_animation.beatup.BeatUpPayload;
import com.cobblemon.mod.common.api.pokemon.PokemonSpecies;
import com.cobblemon.mod.common.client.net.effect.SpawnSnowstormParticleHandler;
import com.cobblemon.mod.common.client.render.models.blockbench.FloatingState;
import com.cobblemon.mod.common.client.render.models.blockbench.PosableModel;
import com.cobblemon.mod.common.client.render.models.blockbench.repository.RenderContext;
import com.cobblemon.mod.common.client.render.models.blockbench.repository.VaryingModelRepository;
import com.cobblemon.mod.common.entity.PoseType;
import com.cobblemon.mod.common.net.messages.client.effect.SpawnSnowstormParticlePacket;
import com.cobblemon.mod.common.pokemon.FormData;
import com.cobblemon.mod.common.pokemon.Species;
import com.cobblemon.mod.common.pokemon.ai.MoveBehaviour;
import com.mojang.blaze3d.vertex.PoseStack;
import com.mojang.blaze3d.vertex.VertexConsumer;
import com.mojang.math.Axis;
import java.util.HashSet;
import java.util.Set;
import net.minecraft.client.Minecraft;
import net.minecraft.client.multiplayer.ClientLevel;
import net.minecraft.client.renderer.LightTexture;
import net.minecraft.client.renderer.MultiBufferSource;
import net.minecraft.client.renderer.RenderType;
import net.minecraft.client.renderer.texture.OverlayTexture;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.sounds.SoundEvent;
import net.minecraft.sounds.SoundSource;
import net.minecraft.util.Mth;
import net.minecraft.world.entity.EntityDimensions;
import net.minecraft.world.phys.Vec3;

/**
 * One strike of Beat Up: a dark afterimage of the teammate behind it, drawn with that Pokemon's own
 * model. It takes shape beside the user (the user's own strike peels out of its body), rushes in from
 * its own angle, lunges into the target on the strike, and dissolves.
 */
final class Afterimage {
    // Seconds after the afterimage appears. CONTACT is the strike itself.
    static final float MATERIALIZE = 0.06F;
    static final float ARRIVE = 0.24F;
    static final float CONTACT = 0.28F;
    static final float FADE = 0.32F;
    static final float GONE = 0.48F;
    /** When the species' own physical-attack animation starts, so its swing lands near the contact. */
    private static final float SPECIES_ATTACK = 0.17F;

    /** The angle each strike comes in at, in degrees off the line from the user to the target. */
    private static final float[] APPROACH = {0, 38, -38, 16, -58, 58};
    /** Very big or very small Pokemon are scaled into this height range (blocks). */
    private static final float MAX_HEIGHT = 2.2F;
    private static final float MIN_HEIGHT = 0.7F;
    private static final float MAX_GROWTH = 1.8F;
    /** Trail copies: how far behind the afterimage each one is (seconds), and how opaque. */
    private static final float[] ECHO_LAG = {0.02F, 0.04F, 0.06F};
    private static final float[] ECHO_ALPHA = {0.3F, 0.18F, 0.09F};
    // ARGB multipliers over the model's own texture: a dark purple body and a brighter violet trail
    private static final float[] BODY = {0.86F, 0.16F, 0.09F, 0.36F};
    private static final float[] ECHO = {1F, 0.32F, 0.18F, 0.7F};

    private static final ResourceLocation SUMMON = ResourceLocation.fromNamespaceAndPath("cobblemon", "beatup_summon");
    private static final ResourceLocation SUMMON_RING = ResourceLocation.fromNamespaceAndPath("cobblemon", "beatup_summonring");
    private static final ResourceLocation TRAIL = ResourceLocation.fromNamespaceAndPath("cobblemon", "beatup_trail");
    private static final ResourceLocation DISSOLVE = ResourceLocation.fromNamespaceAndPath("cobblemon", "beatup_dissolve");
    private static final ResourceLocation DISSOLVE_SPARKS = ResourceLocation.fromNamespaceAndPath("cobblemon", "beatup_dissolvesparks");
    private static final SoundEvent DASH_SOUND = SoundEvent.createVariableRangeEvent(ResourceLocation.fromNamespaceAndPath("cobblemon", "move.beatup.dash"));
    private static final Set<ResourceLocation> BROKEN_SPECIES = new HashSet<>();

    /** Seconds after the move started at which this afterimage appears. */
    final float appear;
    private final ResourceLocation species;
    private final Set<String> aspects;
    private final int index;
    private final boolean whiff;
    private final float baseScale;
    private final float scale;
    private final float height;
    private final float radius;
    private final PoseType movingPose;
    private final FloatingState state = new FloatingState();
    private final RenderContext context = new RenderContext();

    private boolean summoned;
    private boolean moving;
    private boolean attacked;
    private boolean dissolved;

    Afterimage(BeatUpPayload.Teammate teammate, int index, float appear, boolean whiff) {
        this.species = teammate.species();
        this.aspects = Set.copyOf(teammate.aspects());
        this.index = index;
        this.appear = appear;
        this.whiff = whiff;

        Species speciesData = PokemonSpecies.getByIdentifier(species);
        FormData form = speciesData == null ? null : speciesData.getForm(aspects);
        float base = form == null ? 1F : form.getBaseScale();
        EntityDimensions hitbox = form == null ? null : form.getHitbox();
        // A Pokemon entity's size is its form's hitbox times its base scale
        float fullHeight = Math.max(hitbox == null ? 1F : hitbox.height() * base, 0.05F);
        float fullWidth = hitbox == null ? 0.8F : hitbox.width() * base;
        float fit = fullHeight > MAX_HEIGHT ? MAX_HEIGHT / fullHeight
                : fullHeight < MIN_HEIGHT ? Math.min(MIN_HEIGHT / fullHeight, MAX_GROWTH) : 1F;
        this.baseScale = base;
        this.scale = base * fit;
        this.height = fullHeight * fit;
        this.radius = fullWidth * fit / 2;
        this.movingPose = movingPose(form);
        state.setCurrentAspects(aspects);
    }

    /** Anything that can walk runs in (a flying pose spreads the wings far too wide), flyers that can't
     * walk come in on the wing, and the rest swim through the air. */
    private static PoseType movingPose(FormData form) {
        if (form == null) {
            return PoseType.WALK;
        }
        MoveBehaviour moving = form.getBehaviour().getMoving();
        if (moving.getWalk().getCanWalk()) {
            return PoseType.WALK;
        }
        return moving.getFly().getCanFly() ? PoseType.FLY : PoseType.SWIM;
    }

    /** Once per client tick: the summoning mist, the trail and the dissolve, plus the rush sound. */
    void tick(Minecraft client, ClientLevel world, BeatUpSequence.Stage stage, float seconds) {
        float u = seconds - appear;
        if (u < 0 || u > GONE) {
            return;
        }
        Placement here = place(stage, u);
        if (!summoned) {
            summoned = true;
            Vec3 feet = new Vec3(here.x, here.y, here.z);
            spawn(client, SUMMON, feet);
            spawn(client, SUMMON_RING, feet);
            world.playLocalSound(here.x, here.y, here.z, DASH_SOUND, SoundSource.NEUTRAL, 0.8F, 0.95F + 0.07F * index, false);
        }
        if (u >= MATERIALIZE && u <= CONTACT) {
            spawn(client, TRAIL, new Vec3(here.x, here.y + height * 0.45, here.z));
            if (height > 1.6F) {
                spawn(client, TRAIL, new Vec3(here.x, here.y + height * 0.8, here.z));
            }
        }
        if (!dissolved && u >= FADE) {
            dissolved = true;
            Vec3 middle = new Vec3(here.x, here.y + height * 0.5, here.z);
            spawn(client, DISSOLVE, middle);
            spawn(client, DISSOLVE_SPARKS, middle);
            if (height > 1.6F) {
                spawn(client, DISSOLVE, new Vec3(here.x, here.y + height * 0.85, here.z));
            }
        }
    }

    void render(PoseStack matrices, MultiBufferSource consumers, Vec3 camera, BeatUpSequence.Stage stage,
                float seconds, float frameTicks) {
        float u = seconds - appear;
        if (u < 0 || u > GONE || BROKEN_SPECIES.contains(species)) {
            return;
        }
        try {
            VaryingModelRepository repository = VaryingModelRepository.INSTANCE;
            PosableModel model = repository.getPoser(species, state);
            ResourceLocation texture = repository.getTexture(species, state);
            context.put(RenderContext.Companion.getRENDER_STATE(), RenderContext.RenderState.WORLD);
            context.put(RenderContext.Companion.getSPECIES(), species);
            context.put(RenderContext.Companion.getASPECTS(), aspects);
            context.put(RenderContext.Companion.getTEXTURE(), texture);
            context.put(RenderContext.Companion.getSCALE(), baseScale);
            context.put(RenderContext.Companion.getPOSABLE_STATE(), state);
            context.put(RenderContext.Companion.getDO_QUIRKS(), false);
            model.setContext(context);
            state.setCurrentModel(model);
            pose(u);
            state.updatePartialTicks(frameTicks);
            model.applyAnimations(null, state, 0F, 0F, state.getAnimationSeconds() * 20F, 0F, 0F);
            model.resetLayerContext();

            VertexConsumer buffer = consumers.getBuffer(RenderType.entityTranslucent(texture));
            float trail = u < MATERIALIZE ? 0F : u <= CONTACT ? 1F : 1F - Mth.clamp((u - CONTACT) / 0.05F, 0F, 1F);
            if (trail > 0) {
                for (int i = ECHO_LAG.length - 1; i >= 0; i--) {
                    float lagged = Math.max(u - ECHO_LAG[i], 0F);
                    draw(model, matrices, buffer, camera, place(stage, lagged), ECHO, ECHO_ALPHA[i] * trail);
                }
            }
            draw(model, matrices, buffer, camera, place(stage, u), BODY, 1F);
            model.setDefault();
        } catch (RuntimeException e) {
            // one species misbehaving only hides that species' afterimages; API mismatches (linkage
            // errors) go up to BeatUpClient, which switches the afterimages off
            BROKEN_SPECIES.add(species);
            BeatUpClient.LOGGER.warn("Couldn't draw a Beat Up afterimage of {}", species, e);
        }
    }

    /** Standing while it takes shape, moving for the rush, then the species' own physical attack. */
    private void pose(float u) {
        if (state.getCurrentPose() == null) {
            state.setPoseToFirstSuitable(PoseType.STAND);
        }
        if (!moving && u >= MATERIALIZE) {
            moving = true;
            state.setPoseToFirstSuitable(movingPose);
        }
        if (!attacked && u >= SPECIES_ATTACK) {
            attacked = true;
            state.addFirstAnimation(Set.of("physical"));
        }
    }

    private void draw(PosableModel model, PoseStack matrices, VertexConsumer buffer, Vec3 camera, Placement placement,
                      float[] tint, float opacity) {
        float alpha = tint[0] * placement.alpha * opacity;
        if (alpha <= 0.01F) {
            return;
        }
        int color = (int) (alpha * 255) << 24 | (int) (tint[1] * 255) << 16 | (int) (tint[2] * 255) << 8 | (int) (tint[3] * 255);
        float s = scale * placement.size;
        matrices.pushPose();
        matrices.translate(placement.x - camera.x, placement.y - camera.y, placement.z - camera.z);
        matrices.mulPose(Axis.YP.rotationDegrees(180F - placement.yaw));
        // lean into the strike around the middle of the body
        matrices.translate(0F, height * placement.size * 0.5F, 0F);
        matrices.mulPose(Axis.XP.rotationDegrees(-placement.lean));
        matrices.translate(0F, -height * placement.size * 0.5F, 0F);
        // what LivingEntityRenderer and PosableEntityModel do around a Pokemon's model
        matrices.scale(-1F, -1F, 1F);
        matrices.scale(s, s, s);
        matrices.translate(0F, -1.501F + 1.5F, 0F);
        model.render(context, matrices, buffer, LightTexture.FULL_BRIGHT, OverlayTexture.NO_OVERLAY, color);
        matrices.popPose();
    }

    /** Where the afterimage is u seconds after appearing. */
    private Placement place(BeatUpSequence.Stage stage, float u) {
        double angle = Math.toRadians(APPROACH[index % APPROACH.length]);
        double side = angle > 0 ? 1 : angle < 0 ? -1 : (index % 2 == 0 ? 1 : -1);
        // the direction it comes in along, and the spot it strikes from, just touching the target
        Vec3 in = rotate(stage.forward(), angle);
        double reach = stage.targetRadius() + radius * 0.9 + 0.05;
        Vec3 spot = stage.target().subtract(in.scale(reach));
        if (whiff) {
            // a miss carries it past the target's flank instead
            spot = stage.target().add(stage.side().scale(side * (stage.targetRadius() + radius + 0.35)));
        }
        Vec3 start = index == 0 ? stage.user() : summonSpot(stage, side);

        double rush = smooth((u - MATERIALIZE) / (ARRIVE - MATERIALIZE));
        double arc = Math.sin(Math.PI * rush);
        Vec3 pos = start.lerp(spot, rush);
        if (index != 0) {
            pos = pos.add(stage.side().scale(side * (0.15 + 0.04 * stage.distance()) * arc));
        }
        double hop = (index == 3 ? 0.55 : 0.2) + 0.12 * Math.min(height, 2.5);
        double rise = -0.15 * height * (1 - smooth(u / MATERIALIZE));

        // lunge on the strike, hold the hit for a moment, then drift back as it fades
        double lunge = 0.15 + 0.2 * radius;
        double push;
        float lean;
        float alpha = (float) smooth(u / MATERIALIZE);
        float size = 0.8F + 0.2F * (float) smooth(u / MATERIALIZE);
        double lift = 0;
        if (u < ARRIVE) {
            push = 0;
            lean = 8F * (float) rush;
        } else if (u < CONTACT) {
            double k = easeOut((u - ARRIVE) / (CONTACT - ARRIVE));
            push = lunge * k;
            lean = 8F + 14F * (float) k;
        } else if (u < FADE) {
            double k = smooth((u - CONTACT) / (FADE - CONTACT));
            push = lunge - 0.06 * k;
            lean = 22F - 12F * (float) k;
        } else {
            double k = smooth((u - FADE) / (GONE - FADE));
            push = lunge - 0.06 - 0.3 * k;
            lean = 10F * (1F - (float) k);
            lift = 0.2 * k;
            alpha *= 1F - (float) k;
            size *= 1F - 0.1F * (float) k;
        }
        if (whiff) {
            // no target to stop it: it keeps going and the lean straightens out
            push = u < ARRIVE ? 0 : 0.9 * easeOut((u - ARRIVE) / (GONE - ARRIVE));
            lean = 8F * (float) rush;
        }
        Vec3 travel = whiff ? spot.subtract(start).multiply(1, 0, 1).normalize() : in;
        pos = pos.add(travel.scale(push)).add(0, hop * arc + rise + lift, 0);

        Vec3 look = whiff ? travel : stage.target().subtract(pos);
        float yaw = (float) Math.toDegrees(Math.atan2(-look.x, look.z));
        return new Placement(pos.x, pos.y, pos.z, yaw, lean, alpha, size);
    }

    /**
     * Teammates take shape beside the user and a little ahead of it. A player usually watches from just
     * behind their own Pokemon, so the spot slides further towards the target until it's clear of this
     * client's camera; otherwise a big teammate would fill the screen.
     */
    private Vec3 summonSpot(BeatUpSequence.Stage stage, double side) {
        Vec3 spot = stage.user().add(stage.side().scale(side * (stage.userRadius() + 0.7 * radius + 0.35)))
                .add(stage.forward().scale(0.15 + 0.2 * radius));
        // models reach well past their hitbox (wings, tails), so go by the bigger of height and width
        double clearance = 2.6 + 1.4 * Math.max(height, 2 * radius);
        Vec3 fromCamera = new Vec3(spot.x - stage.camera().x, 0, spot.z - stage.camera().z);
        double b = stage.forward().dot(fromCamera);
        double c = fromCamera.lengthSqr() - clearance * clearance;
        if (c < 0) {
            // how far along the line to the target the spot has to move to be `clearance` from the camera
            double slide = -b + Math.sqrt(b * b - c);
            spot = spot.add(stage.forward().scale(Math.min(slide, 0.45 * stage.distance())));
        }
        return spot;
    }

    private static Vec3 rotate(Vec3 v, double angle) {
        double cos = Math.cos(angle);
        double sin = Math.sin(angle);
        return new Vec3(v.x * cos - v.z * sin, 0, v.x * sin + v.z * cos);
    }

    private static double smooth(double x) {
        x = Mth.clamp(x, 0, 1);
        return x * x * (3 - 2 * x);
    }

    private static double easeOut(double x) {
        x = Mth.clamp(x, 0, 1);
        return 1 - (1 - x) * (1 - x);
    }

    private static void spawn(Minecraft client, ResourceLocation effect, Vec3 pos) {
        SpawnSnowstormParticleHandler.INSTANCE.handle(new SpawnSnowstormParticlePacket(effect, pos), client);
    }

    private record Placement(double x, double y, double z, float yaw, float lean, float alpha, float size) {
    }
}
