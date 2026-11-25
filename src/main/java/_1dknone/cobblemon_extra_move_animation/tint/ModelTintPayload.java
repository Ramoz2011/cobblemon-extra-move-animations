package _1dknone.cobblemon_extra_move_animation.tint;

import net.minecraft.network.RegistryFriendlyByteBuf;
import net.minecraft.network.codec.StreamCodec;
import net.minecraft.network.protocol.common.custom.CustomPacketPayload;
import net.minecraft.resources.ResourceLocation;

/**
 * Sent to nearby clients to tint a Pokemon's model for a moment: the colour fades in, holds and fades
 * out, timed from when the packet arrives.
 *
 * @param entityId entity id of the Pokemon to tint
 * @param color    ARGB tint; the alpha is the tint's full strength
 * @param flash    Minecraft's own hurt/flash overlay, mixed in after the colour: 0 = none, 0..1 = washed
 *                 that far towards white (a white-hot flash), below 0 = the red hurt overlay (30% red, so
 *                 any Pokemon, blue or black, reads red-hot under a warm colour)
 * @param delay    seconds before the tint starts fading in
 * @param rise     seconds to fade in
 * @param hold     seconds at full strength
 * @param fall     seconds to fade out
 */
public record ModelTintPayload(int entityId, int color, float flash, float delay, float rise, float hold,
                               float fall) implements CustomPacketPayload {

    public static final Type<ModelTintPayload> ID = new Type<>(ResourceLocation.fromNamespaceAndPath("cobblemon_extra_move_animation", "model_tint"));

    // seven fields, one more than PacketCodec.tuple takes
    public static final StreamCodec<RegistryFriendlyByteBuf, ModelTintPayload> CODEC = StreamCodec.ofMember(
            (payload, buf) -> {
                buf.writeVarInt(payload.entityId);
                buf.writeInt(payload.color);
                buf.writeFloat(payload.flash);
                buf.writeFloat(payload.delay);
                buf.writeFloat(payload.rise);
                buf.writeFloat(payload.hold);
                buf.writeFloat(payload.fall);
            },
            buf -> new ModelTintPayload(buf.readVarInt(), buf.readInt(), buf.readFloat(), buf.readFloat(), buf.readFloat(),
                    buf.readFloat(), buf.readFloat())
    );

    @Override
    public Type<ModelTintPayload> type() {
        return ID;
    }

    /** Seconds from the start until the tint is gone. */
    public float end() {
        return delay + rise + hold + fall;
    }
}
