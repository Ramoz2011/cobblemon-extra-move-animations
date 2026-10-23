package _1dknone.cobblemon_extra_move_animation.beatup;

import net.minecraft.network.RegistryByteBuf;
import net.minecraft.network.codec.PacketCodec;
import net.minecraft.network.codec.PacketCodecs;
import net.minecraft.network.packet.CustomPayload;
import net.minecraft.util.Identifier;

import java.util.List;

/**
 * Sent to nearby clients when Beat Up's action effect starts: who attacks whom, and which Pokemon
 * each strike belongs to, so the client can draw an afterimage of the real teammate for every hit.
 *
 * @param userId      entity id of the Pokemon using Beat Up
 * @param targetId    entity id of its target, or -1 when there is none
 * @param hits        the hit count the battle reported (0 when the move missed or was blocked)
 * @param firstStrike seconds from the start of the move to the first strike
 * @param interval    seconds between strikes
 * @param teammates   one entry per strike, in the order the strikes land
 */
public record BeatUpPayload(int userId, int targetId, int hits, float firstStrike, float interval,
                            List<Teammate> teammates) implements CustomPayload {

    public static final Id<BeatUpPayload> ID = new Id<>(Identifier.of("cobblemon_extra_move_animation", "beat_up"));

    public static final PacketCodec<RegistryByteBuf, BeatUpPayload> CODEC = PacketCodec.tuple(
            PacketCodecs.VAR_INT, BeatUpPayload::userId,
            PacketCodecs.VAR_INT, BeatUpPayload::targetId,
            PacketCodecs.VAR_INT, BeatUpPayload::hits,
            PacketCodecs.FLOAT, BeatUpPayload::firstStrike,
            PacketCodecs.FLOAT, BeatUpPayload::interval,
            Teammate.CODEC.collect(PacketCodecs.toList(6)), BeatUpPayload::teammates,
            BeatUpPayload::new
    );

    @Override
    public Id<BeatUpPayload> getId() {
        return ID;
    }

    /** A party member taking part in the attack: its species and aspects pick the model and its variant. */
    public record Teammate(Identifier species, List<String> aspects) {
        static final PacketCodec<RegistryByteBuf, Teammate> CODEC = PacketCodec.tuple(
                Identifier.PACKET_CODEC, Teammate::species,
                PacketCodecs.STRING.collect(PacketCodecs.toList()), Teammate::aspects,
                Teammate::new
        );
    }
}
