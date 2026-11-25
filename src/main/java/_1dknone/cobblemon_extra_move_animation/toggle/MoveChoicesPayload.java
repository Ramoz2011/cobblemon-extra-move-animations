package _1dknone.cobblemon_extra_move_animation.toggle;

import java.util.List;
import net.minecraft.network.RegistryFriendlyByteBuf;
import net.minecraft.network.codec.ByteBufCodecs;
import net.minecraft.network.codec.StreamCodec;
import net.minecraft.network.protocol.common.custom.CustomPacketPayload;
import net.minecraft.resources.ResourceLocation;

/**
 * Sent to players when they join and whenever the server's choices change, so the move animation screen
 * can show what the server plays (players on a server can't change it themselves).
 *
 * @param cobblemonMoves the moves that play Cobblemon's animation instead of this mod's
 */
public record MoveChoicesPayload(List<String> cobblemonMoves) implements CustomPacketPayload {

    public static final Type<MoveChoicesPayload> ID = new Type<>(ResourceLocation.fromNamespaceAndPath("cobblemon_extra_move_animation", "move_choices"));

    public static final StreamCodec<RegistryFriendlyByteBuf, MoveChoicesPayload> CODEC = StreamCodec.composite(
            ByteBufCodecs.STRING_UTF8.apply(ByteBufCodecs.list()), MoveChoicesPayload::cobblemonMoves,
            MoveChoicesPayload::new
    );

    @Override
    public Type<MoveChoicesPayload> type() {
        return ID;
    }
}
