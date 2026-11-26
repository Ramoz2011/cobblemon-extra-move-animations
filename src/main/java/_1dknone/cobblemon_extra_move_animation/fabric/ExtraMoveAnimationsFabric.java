package _1dknone.cobblemon_extra_move_animation.fabric;

import _1dknone.cobblemon_extra_move_animation.ExtraMoveAnimations;
import net.fabricmc.api.ModInitializer;
import net.fabricmc.fabric.api.event.lifecycle.v1.ServerLifecycleEvents;
import net.fabricmc.fabric.api.networking.v1.PayloadTypeRegistry;
import net.fabricmc.fabric.api.networking.v1.ServerPlayConnectionEvents;
import net.fabricmc.fabric.api.resource.ResourceManagerHelper;
import net.minecraft.network.protocol.common.custom.CustomPacketPayload;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.server.packs.PackType;

/** Fabric's entrypoint: wires Fabric's events to the shared {@link ExtraMoveAnimations}. */
public final class ExtraMoveAnimationsFabric implements ModInitializer {
    private static final ResourceLocation MOVE_TOGGLES = ResourceLocation.fromNamespaceAndPath(ExtraMoveAnimations.MOD_ID, "move_toggles");

    @Override
    public void onInitialize() {
        for (ExtraMoveAnimations.Payload<?> payload : ExtraMoveAnimations.CLIENTBOUND_PAYLOADS) {
            register(payload);
        }
        ExtraMoveAnimations.init(new FabricPlatform());
        ServerLifecycleEvents.SERVER_STARTING.register(ExtraMoveAnimations::serverStarting);
        ServerLifecycleEvents.SERVER_STOPPED.register(server -> ExtraMoveAnimations.serverStopped());
        ServerPlayConnectionEvents.JOIN.register((handler, sender, server) -> ExtraMoveAnimations.playerJoined(handler.player));
        ResourceManagerHelper.get(PackType.SERVER_DATA)
                .registerReloadListener(new FabricReloadListener(MOVE_TOGGLES, ExtraMoveAnimations.serverDataListener()));
    }

    private static <T extends CustomPacketPayload> void register(ExtraMoveAnimations.Payload<T> payload) {
        PayloadTypeRegistry.playS2C().register(payload.type(), payload.codec());
    }
}
