package _1dknone.cobblemon_extra_move_animation.neoforge;

import _1dknone.cobblemon_extra_move_animation.ExtraMoveAnimations;
import _1dknone.cobblemon_extra_move_animation.neoforge.client.ExtraMoveAnimationsNeoForgeClient;
import net.minecraft.network.protocol.common.custom.CustomPacketPayload;
import net.minecraft.server.level.ServerPlayer;
import net.neoforged.api.distmarker.Dist;
import net.neoforged.bus.api.IEventBus;
import net.neoforged.fml.common.Mod;
import net.neoforged.neoforge.common.NeoForge;
import net.neoforged.neoforge.event.AddReloadListenerEvent;
import net.neoforged.neoforge.event.entity.player.PlayerEvent;
import net.neoforged.neoforge.event.server.ServerAboutToStartEvent;
import net.neoforged.neoforge.event.server.ServerStoppedEvent;
import net.neoforged.neoforge.network.event.RegisterPayloadHandlersEvent;
import net.neoforged.neoforge.network.registration.PayloadRegistrar;

/** NeoForge's entrypoint: wires NeoForge's events to the shared {@link ExtraMoveAnimations}. */
@Mod(ExtraMoveAnimations.MOD_ID)
public final class ExtraMoveAnimationsNeoForge {

    public ExtraMoveAnimationsNeoForge(IEventBus modBus, Dist dist) {
        ExtraMoveAnimations.init(new NeoForgePlatform());
        modBus.addListener(ExtraMoveAnimationsNeoForge::registerPayloads);
        NeoForge.EVENT_BUS.addListener((ServerAboutToStartEvent event) -> ExtraMoveAnimations.serverStarting(event.getServer()));
        NeoForge.EVENT_BUS.addListener((ServerStoppedEvent event) -> ExtraMoveAnimations.serverStopped());
        NeoForge.EVENT_BUS.addListener((PlayerEvent.PlayerLoggedInEvent event) -> {
            if (event.getEntity() instanceof ServerPlayer player) {
                ExtraMoveAnimations.playerJoined(player);
            }
        });
        NeoForge.EVENT_BUS.addListener((AddReloadListenerEvent event) -> event.addListener(ExtraMoveAnimations.serverDataListener()));
        if (dist.isClient()) {
            ExtraMoveAnimationsNeoForgeClient.init(modBus);
        }
    }

    private static void registerPayloads(RegisterPayloadHandlersEvent event) {
        // Optional, as on Fabric: players without this mod can still join, they just don't get these extras
        PayloadRegistrar registrar = event.registrar("1").optional();
        for (ExtraMoveAnimations.Payload<?> payload : ExtraMoveAnimations.CLIENTBOUND_PAYLOADS) {
            register(registrar, payload);
        }
    }

    private static <T extends CustomPacketPayload> void register(PayloadRegistrar registrar, ExtraMoveAnimations.Payload<T> payload) {
        // Only players' games receive these, so the client-only handler never runs on a dedicated server
        registrar.playToClient(payload.type(), payload.codec(), (received, context) -> ExtraMoveAnimationsNeoForgeClient.receive(received));
    }
}
