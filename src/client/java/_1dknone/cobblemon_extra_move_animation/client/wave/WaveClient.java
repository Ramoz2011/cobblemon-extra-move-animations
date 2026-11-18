package _1dknone.cobblemon_extra_move_animation.client.wave;

import _1dknone.cobblemon_extra_move_animation.wave.WavePayload;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import net.fabricmc.fabric.api.client.event.lifecycle.v1.ClientTickEvents;
import net.fabricmc.fabric.api.client.networking.v1.ClientPlayConnectionEvents;
import net.fabricmc.fabric.api.client.networking.v1.ClientPlayNetworking;
import net.fabricmc.fabric.api.client.rendering.v1.WorldRenderContext;
import net.fabricmc.fabric.api.client.rendering.v1.WorldRenderEvents;
import net.fabricmc.fabric.api.resource.ResourceManagerHelper;
import net.fabricmc.fabric.api.resource.SimpleSynchronousResourceReloadListener;
import net.minecraft.client.MinecraftClient;
import net.minecraft.client.render.VertexConsumerProvider;
import net.minecraft.resource.Resource;
import net.minecraft.resource.ResourceManager;
import net.minecraft.resource.ResourceType;
import net.minecraft.util.Identifier;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.io.Reader;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;

/**
 * Client half of the wave effects (Muddy Water): loads the wave styles, starts a wave when the server
 * says a move made one, and draws the waves in progress after the world's entities.
 *
 * <p>A wave is an extra on top of the move's JSON effects (particles, animations, sounds), so if
 * anything here goes wrong the waves switch off for the session and the moves play on without them.
 */
public final class WaveClient {
    static final Logger LOGGER = LoggerFactory.getLogger("cobblemon_extra_move_animation");
    private static final String FOLDER = "wave_effects";

    private static final List<WaveSequence> SEQUENCES = new ArrayList<>();
    private static final Map<Identifier, WaveStyle> STYLES = new HashMap<>();
    private static final Set<Identifier> MISSING = new HashSet<>();
    private static boolean disabled;

    private WaveClient() {
    }

    public static void register() {
        ClientPlayNetworking.registerGlobalReceiver(WavePayload.ID, (payload, context) -> start(context.client(), payload));
        ClientTickEvents.END_CLIENT_TICK.register(WaveClient::tick);
        WorldRenderEvents.AFTER_ENTITIES.register(WaveClient::render);
        ClientPlayConnectionEvents.DISCONNECT.register((handler, client) -> SEQUENCES.clear());
        ResourceManagerHelper.get(ResourceType.CLIENT_RESOURCES).registerReloadListener(new SimpleSynchronousResourceReloadListener() {
            @Override
            public Identifier getFabricId() {
                return Identifier.of("cobblemon_extra_move_animation", FOLDER);
            }

            @Override
            public void reload(ResourceManager manager) {
                loadStyles(manager);
            }
        });
    }

    /** Reads every {@code assets/<namespace>/wave_effects/<name>.json} as the style {@code <namespace>:<name>}. */
    private static void loadStyles(ResourceManager manager) {
        STYLES.clear();
        MISSING.clear();
        for (Map.Entry<Identifier, Resource> entry : manager.findResources(FOLDER, id -> id.getPath().endsWith(".json")).entrySet()) {
            Identifier file = entry.getKey();
            String path = file.getPath();
            Identifier id = Identifier.of(file.getNamespace(), path.substring(FOLDER.length() + 1, path.length() - ".json".length()));
            try (Reader reader = entry.getValue().getReader()) {
                JsonObject json = JsonParser.parseReader(reader).getAsJsonObject();
                STYLES.put(id, WaveStyle.parse(json));
            } catch (Exception e) {
                LOGGER.warn("Couldn't read the wave style {}; moves using it play without their wave", file, e);
            }
        }
    }

    private static void start(MinecraftClient client, WavePayload payload) {
        if (disabled || client.world == null) {
            return;
        }
        WaveStyle style = STYLES.get(payload.style());
        if (style == null) {
            if (MISSING.add(payload.style())) {
                LOGGER.warn("No wave style {}; the move plays without its wave", payload.style());
            }
            return;
        }
        try {
            SEQUENCES.add(new WaveSequence(client.world, style, payload));
        } catch (Throwable t) {
            fail(t);
        }
    }

    private static void tick(MinecraftClient client) {
        if (SEQUENCES.isEmpty() || client.isPaused()) {
            return;
        }
        try {
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
            for (WaveSequence sequence : SEQUENCES) {
                sequence.render(context.matrixStack(), consumers, context.camera().getPos(), tickDelta);
            }
        } catch (Throwable t) {
            fail(t);
        }
    }

    private static void fail(Throwable t) {
        disabled = true;
        SEQUENCES.clear();
        LOGGER.warn("The wave effects ran into an error and are off for this session", t);
    }
}
