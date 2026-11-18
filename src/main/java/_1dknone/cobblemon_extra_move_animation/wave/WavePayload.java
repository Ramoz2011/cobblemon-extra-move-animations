package _1dknone.cobblemon_extra_move_animation.wave;

import net.minecraft.network.RegistryByteBuf;
import net.minecraft.network.codec.PacketCodec;
import net.minecraft.network.codec.PacketCodecs;
import net.minecraft.network.packet.CustomPayload;
import net.minecraft.util.Identifier;

import java.util.List;

/**
 * Sent to nearby clients when a move's action effect starts a wave: which wave style to draw, who makes
 * it and whom it rolls over. The client times the wave from the moment this arrives, the same moment the
 * move's animations start.
 *
 * @param style     the wave style, a client resource at {@code assets/<namespace>/wave_effects/<path>.json}
 * @param userId    entity id of the Pokemon making the wave
 * @param targetIds entity ids of the Pokemon it is aimed at (any number, possibly none)
 */
public record WavePayload(Identifier style, int userId, List<Integer> targetIds) implements CustomPayload {

    /** Showdown has at most three Pokemon on a side. */
    public static final int MAX_TARGETS = 6;

    public static final Id<WavePayload> ID = new Id<>(Identifier.of("cobblemon_extra_move_animation", "wave"));

    public static final PacketCodec<RegistryByteBuf, WavePayload> CODEC = PacketCodec.tuple(
            Identifier.PACKET_CODEC, WavePayload::style,
            PacketCodecs.VAR_INT, WavePayload::userId,
            PacketCodecs.VAR_INT.collect(PacketCodecs.toList(MAX_TARGETS)), WavePayload::targetIds,
            WavePayload::new
    );

    @Override
    public Id<WavePayload> getId() {
        return ID;
    }
}
