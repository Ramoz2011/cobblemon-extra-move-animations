package _1dknone.cobblemon_extra_move_animation.toggle;

import net.minecraft.network.RegistryByteBuf;
import net.minecraft.network.codec.PacketCodec;
import net.minecraft.network.codec.PacketCodecs;
import net.minecraft.network.packet.CustomPayload;
import net.minecraft.util.Identifier;

import java.util.List;

/**
 * Sent to players when they join and whenever the server's choices change, so the move animation screen
 * can show what the server plays (players on a server can't change it themselves).
 *
 * @param cobblemonMoves the moves that play Cobblemon's animation instead of this mod's
 */
public record MoveChoicesPayload(List<String> cobblemonMoves) implements CustomPayload {

    public static final Id<MoveChoicesPayload> ID = new Id<>(Identifier.of("cobblemon_extra_move_animation", "move_choices"));

    public static final PacketCodec<RegistryByteBuf, MoveChoicesPayload> CODEC = PacketCodec.tuple(
            PacketCodecs.STRING.collect(PacketCodecs.toList()), MoveChoicesPayload::cobblemonMoves,
            MoveChoicesPayload::new
    );

    @Override
    public Id<MoveChoicesPayload> getId() {
        return ID;
    }
}
