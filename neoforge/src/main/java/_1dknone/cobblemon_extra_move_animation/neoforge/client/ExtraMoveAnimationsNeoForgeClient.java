package _1dknone.cobblemon_extra_move_animation.neoforge.client;

import _1dknone.cobblemon_extra_move_animation.client.ExtraMoveAnimationsClient;
import _1dknone.cobblemon_extra_move_animation.client.toggle.MoveTogglesClient;
import net.minecraft.client.Minecraft;
import net.minecraft.client.gui.components.AbstractWidget;
import net.minecraft.client.gui.screens.Screen;
import net.minecraft.network.protocol.common.custom.CustomPacketPayload;
import net.neoforged.bus.api.IEventBus;
import net.neoforged.neoforge.client.event.ClientPlayerNetworkEvent;
import net.neoforged.neoforge.client.event.ClientTickEvent;
import net.neoforged.neoforge.client.event.RegisterClientReloadListenersEvent;
import net.neoforged.neoforge.client.event.RenderLevelStageEvent;
import net.neoforged.neoforge.client.event.ScreenEvent;
import net.neoforged.neoforge.common.NeoForge;

import java.util.List;

/**
 * NeoForge's client side: wires NeoForge's client events to the shared {@link ExtraMoveAnimationsClient}.
 * Only ever loaded on a player's game.
 */
public final class ExtraMoveAnimationsNeoForgeClient {

    private ExtraMoveAnimationsNeoForgeClient() {
    }

    public static void init(IEventBus modBus) {
        modBus.addListener((RegisterClientReloadListenersEvent event) -> event.registerReloadListener(ExtraMoveAnimationsClient.resourceListener()));
        NeoForge.EVENT_BUS.addListener((ClientTickEvent.Post event) -> ExtraMoveAnimationsClient.tick(Minecraft.getInstance()));
        NeoForge.EVENT_BUS.addListener(ExtraMoveAnimationsNeoForgeClient::renderStage);
        NeoForge.EVENT_BUS.addListener((ClientPlayerNetworkEvent.LoggingOut event) -> ExtraMoveAnimationsClient.disconnected());
        NeoForge.EVENT_BUS.addListener(ExtraMoveAnimationsNeoForgeClient::screenInitialized);
    }

    /** One of the mod's payloads arrived; NeoForge runs payload handlers on the client thread. */
    public static void receive(CustomPacketPayload payload) {
        ExtraMoveAnimationsClient.receive(Minecraft.getInstance(), payload);
    }

    private static void renderStage(RenderLevelStageEvent event) {
        if (event.getStage() != RenderLevelStageEvent.Stage.AFTER_ENTITIES) {
            return;
        }
        // The same buffers the world's entities were drawn into; the rest of the frame draws what we add
        ExtraMoveAnimationsClient.renderAfterEntities(event.getPoseStack(), Minecraft.getInstance().renderBuffers().bufferSource(),
                event.getCamera().getPosition(), event.getPartialTick().getGameTimeDeltaPartialTick(false));
    }

    private static void screenInitialized(ScreenEvent.Init.Post event) {
        Screen screen = event.getScreen();
        ExtraMoveAnimationsClient.screenInitialized(Minecraft.getInstance(), screen, screen.width, new MoveTogglesClient.Buttons() {
            @Override
            public List<AbstractWidget> list() {
                return event.getListenersList().stream()
                        .filter(AbstractWidget.class::isInstance)
                        .map(AbstractWidget.class::cast)
                        .toList();
            }

            @Override
            public void add(AbstractWidget button) {
                event.addListener(button);
            }
        });
    }
}
