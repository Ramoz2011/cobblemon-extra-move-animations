package _1dknone.cobblemon_extra_move_animation.client;

import _1dknone.cobblemon_extra_move_animation.beatup.BeatUpPayload;
import _1dknone.cobblemon_extra_move_animation.client.beatup.BeatUpClient;
import _1dknone.cobblemon_extra_move_animation.client.tint.ModelTintClient;
import _1dknone.cobblemon_extra_move_animation.client.toggle.MoveTogglesClient;
import _1dknone.cobblemon_extra_move_animation.client.wave.WaveClient;
import _1dknone.cobblemon_extra_move_animation.tint.ModelTintPayload;
import _1dknone.cobblemon_extra_move_animation.toggle.MoveChoicesPayload;
import _1dknone.cobblemon_extra_move_animation.wave.WavePayload;
import com.mojang.blaze3d.vertex.PoseStack;
import net.minecraft.client.Minecraft;
import net.minecraft.client.gui.screens.Screen;
import net.minecraft.client.renderer.MultiBufferSource;
import net.minecraft.network.protocol.common.custom.CustomPacketPayload;
import net.minecraft.server.packs.resources.ResourceManagerReloadListener;
import net.minecraft.world.phys.Vec3;

/**
 * The client side's own setup, shared by Fabric and NeoForge: each loader passes its client events on to
 * these methods.
 */
public final class ExtraMoveAnimationsClient {

    private ExtraMoveAnimationsClient() {
    }

    /** One of the mod's payloads arrived. Run it on the client thread. */
    public static void receive(Minecraft client, CustomPacketPayload payload) {
        if (payload instanceof BeatUpPayload beatUp) {
            BeatUpClient.start(client, beatUp);
        } else if (payload instanceof ModelTintPayload tint) {
            ModelTintClient.start(client, tint);
        } else if (payload instanceof MoveChoicesPayload choices) {
            MoveTogglesClient.receive(choices);
        } else if (payload instanceof WavePayload wave) {
            WaveClient.start(client, wave);
        }
    }

    /** Run at the end of every client tick. */
    public static void tick(Minecraft client) {
        BeatUpClient.tick(client);
        ModelTintClient.tick(client);
        WaveClient.tick(client);
    }

    /** Run once the world's entities are drawn, in the same frame. */
    public static void renderAfterEntities(PoseStack poseStack, MultiBufferSource consumers, Vec3 camera, float tickDelta) {
        BeatUpClient.render(poseStack, consumers, camera, tickDelta);
        ModelTintClient.render(poseStack, consumers, camera, tickDelta);
        WaveClient.render(poseStack, consumers, camera, tickDelta);
    }

    /** Run when the player leaves a world or server. */
    public static void disconnected() {
        BeatUpClient.clear();
        ModelTintClient.clear();
        MoveTogglesClient.clear();
        WaveClient.clear();
    }

    /** Run after any screen sets itself up. */
    public static void screenInitialized(Minecraft client, Screen screen, int width, MoveTogglesClient.Buttons buttons) {
        MoveTogglesClient.screenInitialized(client, screen, width, buttons);
    }

    /** Loads the client resources the mod reads itself (the wave styles), for the loader to add to resource reloads. */
    public static ResourceManagerReloadListener resourceListener() {
        return WaveClient::loadStyles;
    }
}
