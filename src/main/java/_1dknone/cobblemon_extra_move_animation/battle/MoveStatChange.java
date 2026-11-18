package _1dknone.cobblemon_extra_move_animation.battle;

import _1dknone.cobblemon_extra_move_animation.molang.PokemonEntityFunctions;
import com.bedrockk.molang.runtime.MoParams;
import com.bedrockk.molang.runtime.value.DoubleValue;
import com.cobblemon.mod.common.battles.dispatch.InterpreterInstruction;
import com.cobblemon.mod.common.battles.interpreter.instructions.AbilityInstruction;
import com.cobblemon.mod.common.battles.interpreter.instructions.BoostInstruction;
import com.cobblemon.mod.common.battles.interpreter.instructions.MoveInstruction;
import com.cobblemon.mod.common.battles.pokemon.BattlePokemon;
import com.cobblemon.mod.common.entity.pokemon.PokemonEntity;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.UUID;

/**
 * Lets an action effect ask whether the move it animates changed a stat, by the battle's own log, so an
 * effect like Muddy Water's murky haze only shows when the accuracy drop really happened.
 *
 * <p>MoLang: {@code q.entity.move_stat_change('accuracy')} (any Pokemon entity struct, so
 * {@code q.target.move_stat_change(...)} works too) returns how many stages the move being animated moved
 * that stat of that Pokemon: negative when it fell, positive when it rose (Contrary), 0 when it didn't
 * change. Stats are Showdown's keys ({@code atk def spa spd spe accuracy evasion}) or their full names.
 *
 * <p>Only the move's own stat changes count: the {@code -boost}/{@code -unboost} lines Showdown prints
 * after the move's line and before the next move, leaving out ones an ability or item made (Showdown tags
 * those {@code [from]}, or puts an {@code -ability} line right before them). The battle has already worked
 * all of this out when the move's action effect starts, so the answer is known from its first keyframe.
 * If the hook isn't there the call returns 0, so a conditional effect simply doesn't play.
 */
public final class MoveStatChange {
    public static final String FUNCTION = "move_stat_change";

    private static final Logger LOGGER = LoggerFactory.getLogger("cobblemon_extra_move_animation");
    /** Start the game with -Dcobblemon_extra_move_animation.debug=true to log every answer. */
    static final boolean DEBUG = Boolean.getBoolean("cobblemon_extra_move_animation.debug");
    private static final Map<String, String> ALIASES = Map.ofEntries(
            Map.entry("attack", "atk"), Map.entry("defense", "def"), Map.entry("defence", "def"),
            Map.entry("special_attack", "spa"), Map.entry("special_defense", "spd"), Map.entry("special_defence", "spd"),
            Map.entry("speed", "spe"), Map.entry("acc", "accuracy"), Map.entry("eva", "evasion"), Map.entry("evasiveness", "evasion"));
    private static boolean warned;

    private MoveStatChange() {
    }

    public static void register() {
        try {
            PokemonEntityFunctions.add(FUNCTION, MoveStatChange::run);
        } catch (Throwable t) {
            LOGGER.warn("Couldn't hook into Cobblemon's MoLang functions; effects that depend on stat changes won't play", t);
        }
    }

    private static Object run(PokemonEntity entity, MoParams params) {
        // Never let an exception escape: a throwing keyframe would cut the rest of the move's timeline short
        try {
            String stat = params.getParams().isEmpty() ? "" : params.getString(0).trim().toLowerCase(Locale.ROOT);
            stat = ALIASES.getOrDefault(stat, stat);
            int stages = stages(entity, stat);
            if (DEBUG) {
                LOGGER.info("[debug] {} on {}: {} stage(s) of {}", FUNCTION, entity.getPokemon().getSpecies().getName(), stages, stat);
            }
            return new DoubleValue(stages);
        } catch (Throwable t) {
            if (!warned) {
                warned = true;
                LOGGER.warn("Reading the battle's stat changes failed; effects that depend on them won't play", t);
            }
            return DoubleValue.ZERO;
        }
    }

    static int stages(PokemonEntity entity, String stat) {
        MoveInstruction move = CurrentMove.of(entity.getBattle());
        if (move == null) {
            return 0;
        }
        List<InterpreterInstruction> instructions = move.getInstructionSet().getInstructions();
        int start = instructions.indexOf(move);
        if (start < 0) {
            return 0;
        }
        int total = 0;
        boolean fromAbility = false;
        for (int i = start + 1; i < instructions.size(); i++) {
            InterpreterInstruction instruction = instructions.get(i);
            if (instruction instanceof MoveInstruction) {
                break;
            }
            if (instruction instanceof AbilityInstruction) {
                // the stat changes printed right after "-ability" are the ability's (Intimidate, Defiant...)
                fromAbility = true;
                continue;
            }
            if (instruction instanceof BoostInstruction boost) {
                if (!fromAbility && !boost.getMessage().hasOptionalArgument("from")
                        && boost.getStatKey().equalsIgnoreCase(stat) && isFor(boost.getPokemon(), entity)) {
                    total += boost.isBoost() ? boost.getStages() : -boost.getStages();
                }
                continue;
            }
            fromAbility = false;
        }
        return total;
    }

    static boolean isFor(BattlePokemon battlePokemon, PokemonEntity entity) {
        if (battlePokemon == null) {
            return false;
        }
        if (battlePokemon.getEntity() == entity) {
            return true;
        }
        UUID id = entity.getPokemon().getUuid();
        return battlePokemon.getUuid().equals(id) || battlePokemon.getEffectedPokemon().getUuid().equals(id);
    }
}
