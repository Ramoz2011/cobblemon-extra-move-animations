package _1dknone.cobblemon_extra_move_animation.neoforge;

import _1dknone.cobblemon_extra_move_animation.platform.Platform;
import net.minecraft.network.protocol.common.custom.CustomPacketPayload;
import net.minecraft.server.level.ServerPlayer;
import net.neoforged.fml.ModList;
import net.neoforged.fml.loading.FMLPaths;
import net.neoforged.neoforge.network.PacketDistributor;
import net.neoforged.neoforgespi.language.IModFileInfo;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Optional;

final class NeoForgePlatform implements Platform {

    @Override
    public Path configDir() {
        return FMLPaths.CONFIGDIR.get();
    }

    @Override
    public Optional<Path> findInMod(String modId, String path) {
        IModFileInfo mod = ModList.get().getModFileById(modId);
        if (mod == null) {
            return Optional.empty();
        }
        Path found = mod.getFile().findResource(path.split("/"));
        return Files.exists(found) ? Optional.of(found) : Optional.empty();
    }

    @Override
    public boolean canSend(ServerPlayer player, CustomPacketPayload.Type<?> type) {
        return player.connection.hasChannel(type);
    }

    @Override
    public void send(ServerPlayer player, CustomPacketPayload payload) {
        PacketDistributor.sendToPlayer(player, payload);
    }
}
