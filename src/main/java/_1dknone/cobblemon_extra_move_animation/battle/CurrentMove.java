package _1dknone.cobblemon_extra_move_animation.battle;

import com.cobblemon.mod.common.api.battles.interpreter.BattleMessage;
import com.cobblemon.mod.common.api.battles.model.PokemonBattle;
import com.cobblemon.mod.common.battles.ActiveBattlePokemon;
import com.cobblemon.mod.common.battles.ShowdownInterpreter;
import com.cobblemon.mod.common.battles.dispatch.InstructionSet;
import com.cobblemon.mod.common.battles.dispatch.InterpreterInstruction;
import com.cobblemon.mod.common.battles.interpreter.instructions.MissInstruction;
import com.cobblemon.mod.common.battles.interpreter.instructions.MoveInstruction;
import com.cobblemon.mod.common.battles.pokemon.BattlePokemon;
import kotlin.jvm.functions.Function4;
import net.fabricmc.fabric.api.event.lifecycle.v1.ServerLifecycleEvents;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.lang.ref.WeakReference;
import java.lang.reflect.Field;
import java.util.ArrayList;
import java.util.Collections;
import java.util.Iterator;
import java.util.List;
import java.util.Map;
import java.util.WeakHashMap;

/**
 * Tells a MoLang hook which move a battle is animating at the moment, so it can read what the battle
 * reported about that move (which stats it changed, which Pokemon it hit).
 *
 * <p>Cobblemon reads a whole update of the battle log into instructions before it plays any of them, and
 * while a move's action effect runs, {@code ShowdownInterpreter.lastCauser} holds that move's log line.
 * This wraps Cobblemon's parser for {@code |move|} lines to remember which {@link MoveInstruction} each
 * line became. The wrapper calls Cobblemon's own parser and hands back what it made, so the battle runs
 * exactly as before. If the parser can't be wrapped, {@link #of} returns null and the hooks built on it
 * report nothing, which leaves every move playing as if they weren't there.
 */
public final class CurrentMove {
    private static final Logger LOGGER = LoggerFactory.getLogger("cobblemon_extra_move_animation");
    /** Log line -> the instruction it became. Weak both ways: a finished turn's instructions can be freed. */
    private static final Map<BattleMessage, WeakReference<MoveInstruction>> MOVES =
            Collections.synchronizedMap(new WeakHashMap<>());
    /** The parser map outlives a singleplayer world, so it is wrapped once per game, not per server. */
    private static boolean wrapped;

    private CurrentMove() {
    }

    public static void register() {
        // Battles only run on a server, and by the time one starts every mod has set itself up
        ServerLifecycleEvents.SERVER_STARTING.register(server -> wrapParser());
    }

    @SuppressWarnings("unchecked")
    private static synchronized void wrapParser() {
        if (wrapped) {
            return;
        }
        wrapped = true;
        try {
            Field field = ShowdownInterpreter.class.getDeclaredField("updateInstructionParser");
            field.setAccessible(true);
            Map<String, Function4<PokemonBattle, InstructionSet, BattleMessage, Iterator<BattleMessage>, InterpreterInstruction>> parsers =
                    (Map<String, Function4<PokemonBattle, InstructionSet, BattleMessage, Iterator<BattleMessage>, InterpreterInstruction>>) field.get(null);
            Function4<PokemonBattle, InstructionSet, BattleMessage, Iterator<BattleMessage>, InterpreterInstruction> original = parsers.get("move");
            if (original == null) {
                LOGGER.warn("Cobblemon has no parser for move lines; effects that depend on the battle's stat changes are off");
                return;
            }
            ShowdownInterpreter.registerUpdateInstructionParser("move", (battle, instructions, message, rest) -> {
                InterpreterInstruction instruction = original.invoke(battle, instructions, message, rest);
                if (instruction instanceof MoveInstruction move) {
                    MOVES.put(message, new WeakReference<>(move));
                }
                return instruction;
            });
        } catch (Throwable t) {
            LOGGER.warn("Couldn't follow Cobblemon's battle log; effects that depend on the battle's stat changes are off", t);
        }
    }

    /**
     * The Pokemon the battle log says this move missed: the {@code -miss} lines after its {@code |move|}
     * line and before the next move's.
     */
    public static List<BattlePokemon> missedTargets(MoveInstruction move) {
        List<BattlePokemon> missed = new ArrayList<>();
        List<InterpreterInstruction> instructions = move.getInstructionSet().getInstructions();
        int start = instructions.indexOf(move);
        if (start < 0) {
            return missed;
        }
        for (int i = start + 1; i < instructions.size(); i++) {
            InterpreterInstruction instruction = instructions.get(i);
            if (instruction instanceof MoveInstruction) {
                break;
            }
            if (instruction instanceof MissInstruction miss && miss.getTarget() != null && !missed.contains(miss.getTarget())) {
                missed.add(miss.getTarget());
            }
        }
        return missed;
    }

    /**
     * Whether Cobblemon hands this Pokemon to the move's action effect as a target. A spread move's
     * action effect only gets the Pokemon Showdown lists after {@code [spread]}, the ones it hit, so a foe
     * it missed in a double battle is left out; otherwise the move's own target is the one.
     */
    public static boolean isListedTarget(MoveInstruction move, BattlePokemon pokemon, PokemonBattle battle) {
        List<String> spread = move.getSpreadTargets();
        if (spread.isEmpty()) {
            return pokemon == move.getTargetPokemon();
        }
        for (String pnx : spread) {
            for (ActiveBattlePokemon active : battle.getActivePokemon()) {
                if (pnx.equals(active.getPNX()) && active.getBattlePokemon() == pokemon) {
                    return true;
                }
            }
        }
        return false;
    }

    /** The move whose action effect the battle is playing now, or null if that can't be told. */
    public static MoveInstruction of(PokemonBattle battle) {
        if (battle == null) {
            return null;
        }
        BattleMessage cause = ShowdownInterpreter.INSTANCE.getLastCauser().get(battle.getBattleId());
        if (cause == null) {
            return null;
        }
        WeakReference<MoveInstruction> move = MOVES.get(cause);
        return move == null ? null : move.get();
    }
}
