package _1dknone.cobblemon_extra_move_animation.wave;

import _1dknone.cobblemon_extra_move_animation.battle.CurrentMove;
import _1dknone.cobblemon_extra_move_animation.molang.PokemonEntityFunctions;
import _1dknone.cobblemon_extra_move_animation.platform.Platform;
import com.bedrockk.molang.runtime.MoParams;
import com.bedrockk.molang.runtime.struct.VariableStruct;
import com.bedrockk.molang.runtime.value.DoubleValue;
import com.bedrockk.molang.runtime.value.MoValue;
import com.cobblemon.mod.common.api.battles.model.PokemonBattle;
import com.cobblemon.mod.common.api.molang.ObjectValue;
import com.cobblemon.mod.common.battles.ActiveBattlePokemon;
import com.cobblemon.mod.common.battles.interpreter.instructions.MoveInstruction;
import com.cobblemon.mod.common.battles.pokemon.BattlePokemon;
import com.cobblemon.mod.common.entity.pokemon.PokemonEntity;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.entity.Entity;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.util.ArrayList;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Set;

/**
 * Server half of the wave effects: a move's action effect calls
 * {@code q.user.wave_effect('muddywater', q.target, q.targets)} in the same tick as its animations, and
 * every nearby client draws that wave style (see {@code WaveClient}) from the user over the targets.
 *
 * <p>The first argument names the style ({@code cobblemon_extra_move_animation:<name>} when it has no
 * namespace); after it come the Pokemon to aim at, as single entities or lists. A spread move like Muddy
 * Water gets {@code q.targets} and a single-target one {@code q.target}; the one a move doesn't have
 * reads as 0 and is skipped. With no targets at all it aims at the Pokemon the battle says the move hit.
 * Foes the battle says it missed are always added: Cobblemon leaves them out of a spread move's targets,
 * but the wave floods their side all the same.
 * If this hook is missing the call returns 0 and the move plays its JSON effects without the wave.
 */
public final class WaveEffect {
    public static final String FUNCTION = "wave_effect";

    private static final Logger LOGGER = LoggerFactory.getLogger("cobblemon_extra_move_animation");
    /** Same reach as Cobblemon's own entity_particles and entity_molang keyframes. */
    private static final double RANGE = 200;
    private static boolean warned;

    private WaveEffect() {
    }

    public static void register() {
        try {
            PokemonEntityFunctions.add(FUNCTION, WaveEffect::run);
        } catch (Throwable t) {
            LOGGER.warn("Couldn't hook into Cobblemon's MoLang functions; moves will play without their waves", t);
        }
    }

    private static Object run(PokemonEntity user, MoParams params) {
        // Never let an exception escape: a throwing keyframe would cut the rest of the move's timeline short
        try {
            if (!(user.level() instanceof ServerLevel world) || params.getParams().isEmpty()) {
                return DoubleValue.ZERO;
            }
            String name = params.getString(0).trim();
            ResourceLocation style = name.contains(":") ? ResourceLocation.tryParse(name) : ResourceLocation.tryBuild("cobblemon_extra_move_animation", name);
            if (style == null) {
                return DoubleValue.ZERO;
            }
            Set<Integer> targets = new LinkedHashSet<>();
            List<MoValue> args = params.getParams();
            for (int i = 1; i < args.size(); i++) {
                collect(args.get(i), user, targets, 0);
            }
            if (targets.isEmpty()) {
                fromBattle(user, targets);
            }
            // A spread move's action effect only lists the foes it hit; the wave covers the ones it missed too
            MoveInstruction move = CurrentMove.of(user.getBattle());
            if (move != null) {
                for (BattlePokemon missed : CurrentMove.missedTargets(move)) {
                    add(missed, user, targets);
                }
            }
            List<Integer> ids = new ArrayList<>(targets);
            if (ids.size() > WavePayload.MAX_TARGETS) {
                ids = ids.subList(0, WavePayload.MAX_TARGETS);
            }
            WavePayload payload = new WavePayload(style, user.getId(), List.copyOf(ids));
            for (ServerPlayer player : world.players()) {
                if (player.distanceToSqr(user) <= RANGE * RANGE && Platform.get().canSend(player, WavePayload.ID)) {
                    Platform.get().send(player, payload);
                }
            }
            return DoubleValue.ONE;
        } catch (Throwable t) {
            if (!warned) {
                warned = true;
                LOGGER.warn("A wave effect failed; the move plays without it", t);
            }
            return DoubleValue.ZERO;
        }
    }

    /** Entities in a MoLang value: an entity struct, or a list (q.targets) of them. */
    private static void collect(MoValue value, Entity user, Set<Integer> ids, int depth) {
        if (value instanceof ObjectValue<?> object) {
            if (object.getObj() instanceof Entity entity && entity != user) {
                ids.add(entity.getId());
            }
        } else if (value instanceof VariableStruct list && depth < 2) {
            for (MoValue element : list.getMap().values()) {
                collect(element, user, ids, depth + 1);
            }
        }
    }

    /** The Pokemon the battle says the move being animated was aimed at. */
    private static void fromBattle(PokemonEntity user, Set<Integer> ids) {
        PokemonBattle battle = user.getBattle();
        MoveInstruction move = CurrentMove.of(battle);
        if (move == null) {
            return;
        }
        add(move.getTargetPokemon(), user, ids);
        for (String pnx : move.getSpreadTargets()) {
            for (ActiveBattlePokemon active : battle.getActivePokemon()) {
                if (pnx.equals(active.getPNX())) {
                    add(active.getBattlePokemon(), user, ids);
                }
            }
        }
    }

    private static void add(BattlePokemon pokemon, Entity user, Set<Integer> ids) {
        Entity entity = pokemon == null ? null : pokemon.getEntity();
        if (entity != null && entity != user) {
            ids.add(entity.getId());
        }
    }
}
