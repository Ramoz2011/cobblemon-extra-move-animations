package _1dknone.cobblemon_extra_move_animation;

import _1dknone.cobblemon_extra_move_animation.battle.CurrentMove;
import _1dknone.cobblemon_extra_move_animation.battle.MissedTargets;
import _1dknone.cobblemon_extra_move_animation.battle.MoveHeal;
import _1dknone.cobblemon_extra_move_animation.battle.MoveStatChange;
import _1dknone.cobblemon_extra_move_animation.beatup.BeatUpAfterimages;
import _1dknone.cobblemon_extra_move_animation.beatup.BeatUpPayload;
import _1dknone.cobblemon_extra_move_animation.platform.Platform;
import _1dknone.cobblemon_extra_move_animation.tint.ModelTint;
import _1dknone.cobblemon_extra_move_animation.tint.ModelTintPayload;
import _1dknone.cobblemon_extra_move_animation.toggle.MoveChoicesPayload;
import _1dknone.cobblemon_extra_move_animation.toggle.MoveToggles;
import _1dknone.cobblemon_extra_move_animation.wave.WaveEffect;
import _1dknone.cobblemon_extra_move_animation.wave.WavePayload;
import net.minecraft.network.RegistryFriendlyByteBuf;
import net.minecraft.network.codec.StreamCodec;
import net.minecraft.network.protocol.common.custom.CustomPacketPayload;
import net.minecraft.server.MinecraftServer;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.server.packs.resources.PreparableReloadListener;

import java.util.List;

/**
 * The mod's own setup, shared by Fabric and NeoForge. Each loader's entrypoint calls {@link #init} first,
 * registers {@link #CLIENTBOUND_PAYLOADS}, and passes on the events below.
 */
public final class ExtraMoveAnimations {
    public static final String MOD_ID = "cobblemon_extra_move_animation";

    /** Everything the server sends to players' games. */
    public static final List<Payload<?>> CLIENTBOUND_PAYLOADS = List.of(
            new Payload<>(BeatUpPayload.ID, BeatUpPayload.CODEC),
            new Payload<>(ModelTintPayload.ID, ModelTintPayload.CODEC),
            new Payload<>(MoveChoicesPayload.ID, MoveChoicesPayload.CODEC),
            new Payload<>(WavePayload.ID, WavePayload.CODEC)
    );

    private ExtraMoveAnimations() {
    }

    public static void init(Platform platform) {
        Platform.set(platform);
        BeatUpAfterimages.register();
        ModelTint.register();
        MoveToggles.register();
        MoveStatChange.register();
        MoveHeal.register();
        MissedTargets.register();
        WaveEffect.register();
    }

    /** For the loader to add to every server data reload. */
    public static PreparableReloadListener serverDataListener() {
        return MoveToggles.RESOURCE_CAPTURE;
    }

    /** Run as a server starts, before it loads its worlds. */
    public static void serverStarting(MinecraftServer server) {
        MoveToggles.serverStarting(server);
        CurrentMove.serverStarting();
    }

    public static void serverStopped() {
        MoveToggles.serverStopped();
    }

    public static void playerJoined(ServerPlayer player) {
        MoveToggles.playerJoined(player);
    }

    /** A payload the loader registers: its type and how it's written to the network. */
    public record Payload<T extends CustomPacketPayload>(CustomPacketPayload.Type<T> type,
                                                         StreamCodec<RegistryFriendlyByteBuf, T> codec) {
    }
}
