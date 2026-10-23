package _1dknone.cobblemon_extra_move_animation.client.beatup;

import _1dknone.cobblemon_extra_move_animation.beatup.BeatUpPayload;
import net.fabricmc.fabric.api.client.event.lifecycle.v1.ClientTickEvents;
import net.fabricmc.fabric.api.client.networking.v1.ClientPlayConnectionEvents;
import net.fabricmc.fabric.api.client.networking.v1.ClientPlayNetworking;
import net.fabricmc.fabric.api.client.rendering.v1.WorldRenderContext;
import net.fabricmc.fabric.api.client.rendering.v1.WorldRenderEvents;
import net.minecraft.client.MinecraftClient;
import net.minecraft.client.render.VertexConsumerProvider;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.util.ArrayList;
import java.util.List;

/**
 * Client half of Beat Up's teammate afterimages: keeps the moves in progress, ticks their particles and
 * sounds, and draws the afterimages after the world's entities.
 *
 * <p>The afterimages lean on Cobblemon's model classes, which aren't a stable API. If anything about
 * them goes wrong, the afterimages switch off for the session and Beat Up keeps its JSON-driven effects.
 */
public final class BeatUpClient {
    static final Logger LOGGER = LoggerFactory.getLogger("cobblemon_extra_move_animation");

    private static final List<BeatUpSequence> SEQUENCES = new ArrayList<>();
    private static boolean disabled;

    private BeatUpClient() {
    }

    public static void register() {
        ClientPlayNetworking.registerGlobalReceiver(BeatUpPayload.ID, (payload, context) -> start(context.client(), payload));
        ClientTickEvents.END_CLIENT_TICK.register(BeatUpClient::tick);
        WorldRenderEvents.AFTER_ENTITIES.register(BeatUpClient::render);
        ClientPlayConnectionEvents.DISCONNECT.register((handler, client) -> SEQUENCES.clear());
    }

    private static void start(MinecraftClient client, BeatUpPayload payload) {
        if (disabled || client.world == null || payload.teammates().isEmpty()) {
            return;
        }
        try {
            SEQUENCES.add(new BeatUpSequence(client.world, payload));
        } catch (Throwable t) {
            fail(t);
        }
    }

    private static void tick(MinecraftClient client) {
        if (SEQUENCES.isEmpty() || client.isPaused()) {
            return;
        }
        try {
            // a sequence ends once its last afterimage has faded, or when the player changes world
            SEQUENCES.removeIf(sequence -> !sequence.tick(client));
        } catch (Throwable t) {
            fail(t);
        }
    }

    private static void render(WorldRenderContext context) {
        VertexConsumerProvider consumers = context.consumers();
        if (SEQUENCES.isEmpty() || consumers == null) {
            return;
        }
        try {
            float tickDelta = context.tickCounter().getTickDelta(false);
            for (BeatUpSequence sequence : SEQUENCES) {
                sequence.render(context.matrixStack(), consumers, context.camera().getPos(), tickDelta);
            }
        } catch (Throwable t) {
            fail(t);
        }
    }

    private static void fail(Throwable t) {
        disabled = true;
        SEQUENCES.clear();
        LOGGER.warn("Beat Up's teammate afterimages ran into an error and are off for this session", t);
    }
}
