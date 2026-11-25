package _1dknone.cobblemon_extra_move_animation.wave;

import java.util.List;
import net.minecraft.network.RegistryFriendlyByteBuf;
import net.minecraft.network.codec.ByteBufCodecs;
import net.minecraft.network.codec.StreamCodec;
import net.minecraft.network.protocol.common.custom.CustomPacketPayload;
import net.minecraft.resources.ResourceLocation;

/**
 * Sent to nearby clients when a move's action effect starts a wave: which wave style to draw, who makes
 * it and whom it rolls over. The client times the wave from the moment this arrives, the same moment the
 * move's animations start.
 *
 * @param style     the wave style, a client resource at {@code assets/<namespace>/wave_effects/<path>.json}
 * @param userId    entity id of the Pokemon making the wave
 * @param targetIds entity ids of the Pokemon it is aimed at (any number, possibly none)
 */
public record WavePayload(ResourceLocation style, int userId, List<Integer> targetIds) implements CustomPacketPayload {

    /** Showdown has at most three Pokemon on a side. */
    public static final int MAX_TARGETS = 6;

    public static final Type<WavePayload> ID = new Type<>(ResourceLocation.fromNamespaceAndPath("cobblemon_extra_move_animation", "wave"));

    public static final StreamCodec<RegistryFriendlyByteBuf, WavePayload> CODEC = StreamCodec.composite(
            ResourceLocation.STREAM_CODEC, WavePayload::style,
            ByteBufCodecs.VAR_INT, WavePayload::userId,
            ByteBufCodecs.VAR_INT.apply(ByteBufCodecs.list(MAX_TARGETS)), WavePayload::targetIds,
            WavePayload::new
    );

    @Override
    public Type<WavePayload> type() {
        return ID;
    }
}
