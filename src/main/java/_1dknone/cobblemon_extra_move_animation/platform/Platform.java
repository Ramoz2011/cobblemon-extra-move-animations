package _1dknone.cobblemon_extra_move_animation.platform;

import net.minecraft.network.protocol.common.custom.CustomPacketPayload;
import net.minecraft.server.level.ServerPlayer;

import java.nio.file.Path;
import java.util.Optional;

/**
 * The few things this mod needs from the mod loader. Fabric and NeoForge each set one up before anything
 * else runs, so the rest of the mod is the same code on both.
 */
public interface Platform {

    /** The game's config folder. */
    Path configDir();

    /**
     * A file or folder inside an installed mod, e.g. {@code ("cobblemon", "data/cobblemon/action_effects")}.
     * Empty when the mod isn't installed or doesn't have it.
     */
    Optional<Path> findInMod(String modId, String path);

    /** Whether the player's game can take this payload, i.e. whether it has this mod. */
    boolean canSend(ServerPlayer player, CustomPacketPayload.Type<?> type);

    void send(ServerPlayer player, CustomPacketPayload payload);

    static Platform get() {
        return PlatformHolder.platform;
    }

    static void set(Platform platform) {
        PlatformHolder.platform = platform;
    }
}

final class PlatformHolder {
    static volatile Platform platform;

    private PlatformHolder() {
    }
}
