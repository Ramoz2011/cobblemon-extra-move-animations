package _1dknone.cobblemon_extra_move_animation.beatup;

import _1dknone.cobblemon_extra_move_animation.molang.PokemonEntityFunctions;
import com.bedrockk.molang.runtime.MoParams;
import com.bedrockk.molang.runtime.value.DoubleValue;
import com.bedrockk.molang.runtime.value.MoValue;
import com.cobblemon.mod.common.api.battles.model.PokemonBattle;
import com.cobblemon.mod.common.api.battles.model.actor.BattleActor;
import com.cobblemon.mod.common.api.molang.ObjectValue;
import com.cobblemon.mod.common.battles.ShowdownActionRequest;
import com.cobblemon.mod.common.battles.ShowdownPokemon;
import com.cobblemon.mod.common.battles.ShowdownSide;
import com.cobblemon.mod.common.battles.pokemon.BattlePokemon;
import com.cobblemon.mod.common.entity.pokemon.PokemonEntity;
import net.fabricmc.fabric.api.networking.v1.PayloadTypeRegistry;
import net.fabricmc.fabric.api.networking.v1.ServerPlayNetworking;
import net.minecraft.entity.Entity;
import net.minecraft.server.network.ServerPlayerEntity;
import net.minecraft.server.world.ServerWorld;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.util.ArrayList;
import java.util.List;
import java.util.UUID;

/**
 * Server half of Beat Up's teammate afterimages.
 *
 * <p>Beat Up's action effect calls {@code q.user.beat_up_afterimages(q.hit_count, q.target, first strike,
 * interval)} in the same tick as its animations. This works out which party member each strike belongs
 * to and tells nearby clients, which draw the afterimages. Everything else about the move stays in the
 * JSON, so if this hook is missing the call returns 0 and the move plays without afterimages.
 */
public final class BeatUpAfterimages {
    public static final String FUNCTION = "beat_up_afterimages";

    private static final Logger LOGGER = LoggerFactory.getLogger("cobblemon_extra_move_animation");
    /** Same reach as Cobblemon's own entity_particles and entity_molang keyframes. */
    private static final double RANGE = 200;
    /** A party has six Pokemon, so Beat Up never hits more often. */
    private static final int MAX_STRIKES = 6;
    private static boolean warned;

    private BeatUpAfterimages() {
    }

    public static void register() {
        PayloadTypeRegistry.playS2C().register(BeatUpPayload.ID, BeatUpPayload.CODEC);
        try {
            PokemonEntityFunctions.add(FUNCTION, BeatUpAfterimages::run);
        } catch (Throwable t) {
            LOGGER.warn("Couldn't hook into Cobblemon's MoLang functions; Beat Up will play without teammate afterimages", t);
        }
    }

    private static Object run(PokemonEntity user, MoParams params) {
        // Never let an exception escape: a throwing keyframe would cut the rest of the move's timeline short
        try {
            if (!(user.getWorld() instanceof ServerWorld world)) {
                return DoubleValue.ZERO;
            }
            List<MoValue> args = params.getParams();
            int hits = args.isEmpty() ? 1 : (int) Math.round(params.getDouble(0));
            Entity target = args.size() > 1 && args.get(1) instanceof ObjectValue<?> value && value.getObj() instanceof Entity entity ? entity : null;
            float firstStrike = args.size() > 2 ? (float) params.getDouble(2) : 0.55F;
            float interval = args.size() > 3 ? (float) params.getDouble(3) : 0.18F;

            BeatUpPayload payload = new BeatUpPayload(user.getId(), target == null ? -1 : target.getId(), Math.max(hits, 0),
                    firstStrike, interval, strikers(user, hits));
            for (ServerPlayerEntity player : world.getPlayers()) {
                if (player.squaredDistanceTo(user) <= RANGE * RANGE && ServerPlayNetworking.canSend(player, BeatUpPayload.ID)) {
                    ServerPlayNetworking.send(player, payload);
                }
            }
            return DoubleValue.ONE;
        } catch (Throwable t) {
            if (!warned) {
                warned = true;
                LOGGER.warn("Beat Up's teammate afterimages failed; the move plays without them", t);
            }
            return DoubleValue.ZERO;
        }
    }

    /**
     * The Pokemon behind each strike, in the order the strikes land. Showdown takes Beat Up's
     * participants from the side's party in its own order (active Pokemon first): the user, plus every
     * other member that hasn't fainted and has no status condition. A miss still shows the user's strike.
     */
    static List<BeatUpPayload.Teammate> strikers(PokemonEntity user, int hits) {
        // the user's own strike looks like the user does in battle, so an Illusion keeps its disguise
        BeatUpPayload.Teammate self = new BeatUpPayload.Teammate(user.getExposedSpecies().getResourceIdentifier(),
                List.copyOf(user.getAspects()));
        List<BeatUpPayload.Teammate> order = new ArrayList<>();
        BattlePokemon userBattlePokemon = findBattlePokemon(user);
        if (userBattlePokemon != null) {
            for (BattlePokemon member : partyOrder(userBattlePokemon)) {
                if (member == userBattlePokemon) {
                    order.add(self);
                } else if (member.getHealth() > 0 && member.getEffectedPokemon().getStatus() == null) {
                    order.add(new BeatUpPayload.Teammate(member.getEffectedPokemon().getSpecies().getResourceIdentifier(),
                            List.copyOf(member.getEffectedPokemon().getAspects())));
                }
            }
        }
        if (order.isEmpty()) {
            order.add(self);
        }

        // The battle's hit count is what counts: Showdown stops early when the target faints, and the
        // party can change between the turn's start and this move
        int strikes = Math.clamp(hits, 1, MAX_STRIKES);
        List<BeatUpPayload.Teammate> strikers = new ArrayList<>(strikes);
        for (int i = 0; i < strikes; i++) {
            strikers.add(order.get(i % order.size()));
        }
        return strikers;
    }

    private static BattlePokemon findBattlePokemon(PokemonEntity user) {
        PokemonBattle battle = user.getBattle();
        if (battle == null) {
            return null;
        }
        UUID id = user.getPokemon().getUuid();
        for (BattleActor actor : battle.getActors()) {
            for (BattlePokemon member : actor.getPokemonList()) {
                if (member.getEntity() == user || member.getUuid().equals(id)) {
                    return member;
                }
            }
        }
        return null;
    }

    /** The side's party in Showdown's order if the battle has sent it, otherwise the user first and then the team. */
    private static List<BattlePokemon> partyOrder(BattlePokemon user) {
        List<BattlePokemon> team = user.getActor().getPokemonList();
        try {
            ShowdownActionRequest request = user.getActor().getRequest();
            ShowdownSide side = request == null ? null : request.getSide();
            if (side != null) {
                List<BattlePokemon> ordered = new ArrayList<>(team.size());
                for (ShowdownPokemon showdownPokemon : side.getPokemon()) {
                    UUID id = showdownPokemon.getUuid();
                    team.stream().filter(member -> member.getUuid().equals(id)).findFirst().ifPresent(ordered::add);
                }
                if (ordered.size() == team.size()) {
                    return ordered;
                }
            }
        } catch (RuntimeException e) {
            // a request we can't read just falls back to the team order
        }
        List<BattlePokemon> ordered = new ArrayList<>(team);
        ordered.remove(user);
        ordered.add(0, user);
        return ordered;
    }
}
