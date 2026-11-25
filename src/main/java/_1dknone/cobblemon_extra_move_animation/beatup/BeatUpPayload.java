package _1dknone.cobblemon_extra_move_animation.beatup;

import java.util.List;
import net.minecraft.network.RegistryFriendlyByteBuf;
import net.minecraft.network.codec.ByteBufCodecs;
import net.minecraft.network.codec.StreamCodec;
import net.minecraft.network.protocol.common.custom.CustomPacketPayload;
import net.minecraft.resources.ResourceLocation;

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
                            List<Teammate> teammates) implements CustomPacketPayload {

    public static final Type<BeatUpPayload> ID = new Type<>(ResourceLocation.fromNamespaceAndPath("cobblemon_extra_move_animation", "beat_up"));

    public static final StreamCodec<RegistryFriendlyByteBuf, BeatUpPayload> CODEC = StreamCodec.composite(
            ByteBufCodecs.VAR_INT, BeatUpPayload::userId,
            ByteBufCodecs.VAR_INT, BeatUpPayload::targetId,
            ByteBufCodecs.VAR_INT, BeatUpPayload::hits,
            ByteBufCodecs.FLOAT, BeatUpPayload::firstStrike,
            ByteBufCodecs.FLOAT, BeatUpPayload::interval,
            Teammate.CODEC.apply(ByteBufCodecs.list(6)), BeatUpPayload::teammates,
            BeatUpPayload::new
    );

    @Override
    public Type<BeatUpPayload> type() {
        return ID;
    }

    /** A party member taking part in the attack: its species and aspects pick the model and its variant. */
    public record Teammate(ResourceLocation species, List<String> aspects) {
        static final StreamCodec<RegistryFriendlyByteBuf, Teammate> CODEC = StreamCodec.composite(
                ResourceLocation.STREAM_CODEC, Teammate::species,
                ByteBufCodecs.STRING_UTF8.apply(ByteBufCodecs.list()), Teammate::aspects,
                Teammate::new
        );
    }
}
