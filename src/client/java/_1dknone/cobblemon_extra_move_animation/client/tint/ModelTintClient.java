package _1dknone.cobblemon_extra_move_animation.client.tint;

import _1dknone.cobblemon_extra_move_animation.client.render.ModelOverlay;
import _1dknone.cobblemon_extra_move_animation.tint.ModelTintPayload;
import net.fabricmc.fabric.api.client.event.lifecycle.v1.ClientTickEvents;
import net.fabricmc.fabric.api.client.networking.v1.ClientPlayConnectionEvents;
import net.fabricmc.fabric.api.client.networking.v1.ClientPlayNetworking;
import net.fabricmc.fabric.api.client.rendering.v1.WorldRenderContext;
import net.fabricmc.fabric.api.client.rendering.v1.WorldRenderEvents;
import net.minecraft.client.MinecraftClient;
import net.minecraft.client.render.OverlayTexture;
import net.minecraft.client.render.VertexConsumerProvider;
import net.minecraft.client.world.ClientWorld;
import net.minecraft.entity.Entity;
import net.minecraft.util.math.MathHelper;
import net.minecraft.util.math.Vec3d;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.util.ArrayList;
import java.util.List;

/**
 * Client half of the model tint: keeps the tints in progress and draws each one as a coloured shell of
 * the Pokemon's own model after the world's entities. Time runs on client ticks plus the frame's partial
 * tick, like the move animations the tint plays alongside.
 *
 * <p>If drawing ever fails (Cobblemon's model classes aren't a stable API), tints switch off for the
 * session and moves keep their particles and animations.
 */
public final class ModelTintClient {
    private static final Logger LOGGER = LoggerFactory.getLogger("cobblemon_extra_move_animation");
    // rows of the vanilla overlay texture: below 8 the red hurt flash, from 8 the white wash
    private static final int RED_ROW = 3;
    private static final int WHITE_ROW = 10;

    private static final List<Tint> TINTS = new ArrayList<>();
    private static final ModelOverlay OVERLAY = new ModelOverlay();
    private static boolean disabled;

    private ModelTintClient() {
    }

    public static void register() {
        ClientPlayNetworking.registerGlobalReceiver(ModelTintPayload.ID, (payload, context) -> start(context.client(), payload));
        ClientTickEvents.END_CLIENT_TICK.register(ModelTintClient::tick);
        WorldRenderEvents.AFTER_ENTITIES.register(ModelTintClient::render);
        ClientPlayConnectionEvents.DISCONNECT.register((handler, client) -> TINTS.clear());
    }

    private static void start(MinecraftClient client, ModelTintPayload payload) {
        if (!disabled && client.world != null) {
            TINTS.add(new Tint(client.world, payload));
        }
    }

    private static void tick(MinecraftClient client) {
        if (TINTS.isEmpty() || client.isPaused()) {
            return;
        }
        TINTS.removeIf(tint -> client.world != tint.world || ++tint.ticks / 20F > tint.payload.end());
    }

    private static void render(WorldRenderContext context) {
        VertexConsumerProvider consumers = context.consumers();
        if (TINTS.isEmpty() || consumers == null) {
            return;
        }
        try {
            float tickDelta = context.tickCounter().getTickDelta(false);
            Vec3d camera = context.camera().getPos();
            for (Tint tint : TINTS) {
                float strength = tint.strength((tint.ticks + tickDelta) / 20F);
                Entity entity = tint.world.getEntityById(tint.payload.entityId());
                if (strength <= 0 || entity == null || entity.isInvisible()) {
                    continue;
                }
                int color = tint.payload.color();
                float alpha = (color >>> 24) / 255F * strength;
                float flash = tint.payload.flash();
                int overlay = flash < 0 ? OverlayTexture.packUv(0, RED_ROW) : OverlayTexture.packUv(Math.round(flash * 15), WHITE_ROW);
                OVERLAY.render(context.matrixStack(), consumers, camera, entity, tickDelta,
                        (int) (alpha * 255) << 24 | color & 0xFFFFFF, overlay);
            }
        } catch (Throwable t) {
            disabled = true;
            TINTS.clear();
            LOGGER.warn("Couldn't draw a model tint; tints are off for this session", t);
        }
    }

    private static final class Tint {
        final ClientWorld world;
        final ModelTintPayload payload;
        int ticks;

        Tint(ClientWorld world, ModelTintPayload payload) {
            this.world = world;
            this.payload = payload;
        }

        /** 0..1: eases in over `rise`, holds, then eases out over `fall`. */
        float strength(float seconds) {
            float since = seconds - payload.delay();
            if (since < 0) {
                return 0;
            }
            if (since < payload.rise()) {
                return smooth(since / payload.rise());
            }
            since -= payload.rise();
            if (since < payload.hold()) {
                return 1;
            }
            since -= payload.hold();
            return payload.fall() <= 0 ? 0 : 1 - smooth(since / payload.fall());
        }

        private static float smooth(float x) {
            x = MathHelper.clamp(x, 0F, 1F);
            return x * x * (3 - 2 * x);
        }
    }
}
