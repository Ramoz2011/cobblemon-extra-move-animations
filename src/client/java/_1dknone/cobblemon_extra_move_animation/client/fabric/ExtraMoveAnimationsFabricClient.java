package _1dknone.cobblemon_extra_move_animation.client.fabric;

import _1dknone.cobblemon_extra_move_animation.ExtraMoveAnimations;
import _1dknone.cobblemon_extra_move_animation.client.ExtraMoveAnimationsClient;
import _1dknone.cobblemon_extra_move_animation.client.toggle.MoveTogglesClient;
import _1dknone.cobblemon_extra_move_animation.fabric.FabricReloadListener;
import net.fabricmc.api.ClientModInitializer;
import net.fabricmc.fabric.api.client.event.lifecycle.v1.ClientTickEvents;
import net.fabricmc.fabric.api.client.networking.v1.ClientPlayConnectionEvents;
import net.fabricmc.fabric.api.client.networking.v1.ClientPlayNetworking;
import net.fabricmc.fabric.api.client.rendering.v1.WorldRenderEvents;
import net.fabricmc.fabric.api.client.screen.v1.ScreenEvents;
import net.fabricmc.fabric.api.client.screen.v1.Screens;
import net.fabricmc.fabric.api.resource.ResourceManagerHelper;
import net.minecraft.client.gui.components.AbstractWidget;
import net.minecraft.network.protocol.common.custom.CustomPacketPayload;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.server.packs.PackType;

import java.util.List;

/** Fabric's client entrypoint: wires Fabric's client events to the shared {@link ExtraMoveAnimationsClient}. */
public final class ExtraMoveAnimationsFabricClient implements ClientModInitializer {
    private static final ResourceLocation WAVE_STYLES = ResourceLocation.fromNamespaceAndPath(ExtraMoveAnimations.MOD_ID, "wave_effects");

    @Override
    public void onInitializeClient() {
        for (ExtraMoveAnimations.Payload<?> payload : ExtraMoveAnimations.CLIENTBOUND_PAYLOADS) {
            receive(payload);
        }
        ClientTickEvents.END_CLIENT_TICK.register(ExtraMoveAnimationsClient::tick);
        WorldRenderEvents.AFTER_ENTITIES.register(context -> ExtraMoveAnimationsClient.renderAfterEntities(context.matrixStack(),
                context.consumers(), context.camera().getPosition(), context.tickCounter().getGameTimeDeltaPartialTick(false)));
        ClientPlayConnectionEvents.DISCONNECT.register((handler, client) -> ExtraMoveAnimationsClient.disconnected());
        ScreenEvents.AFTER_INIT.register((client, screen, width, height) ->
                ExtraMoveAnimationsClient.screenInitialized(client, screen, width, new MoveTogglesClient.Buttons() {
                    @Override
                    public List<AbstractWidget> list() {
                        return Screens.getButtons(screen);
                    }

                    @Override
                    public void add(AbstractWidget button) {
                        Screens.getButtons(screen).add(button);
                    }
                }));
        ResourceManagerHelper.get(PackType.CLIENT_RESOURCES)
                .registerReloadListener(new FabricReloadListener(WAVE_STYLES, ExtraMoveAnimationsClient.resourceListener()));
    }

    private static <T extends CustomPacketPayload> void receive(ExtraMoveAnimations.Payload<T> payload) {
        ClientPlayNetworking.registerGlobalReceiver(payload.type(),
                (received, context) -> ExtraMoveAnimationsClient.receive(context.client(), received));
    }
}
