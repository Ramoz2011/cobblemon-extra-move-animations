package _1dknone.cobblemon_extra_move_animation.battle;

import _1dknone.cobblemon_extra_move_animation.molang.PokemonEntityFunctions;
import com.bedrockk.molang.runtime.MoParams;
import com.bedrockk.molang.runtime.value.DoubleValue;
import com.cobblemon.mod.common.api.battles.model.PokemonBattle;
import com.cobblemon.mod.common.battles.interpreter.instructions.MoveInstruction;
import com.cobblemon.mod.common.battles.pokemon.BattlePokemon;
import com.cobblemon.mod.common.entity.pokemon.PokemonEntity;
import com.cobblemon.mod.common.net.messages.client.effect.RunPosableMoLangPacket;
import net.minecraft.server.network.ServerPlayerEntity;
import net.minecraft.server.world.ServerWorld;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.util.ArrayList;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Set;
import java.util.regex.Pattern;

/**
 * Lets a spread move's action effect animate the foes it missed, which Cobblemon leaves out of it.
 *
 * <p>Cobblemon hands a spread move's action effect only the Pokemon Showdown lists as hit, so when Muddy
 * Water misses one of two foes, that foe isn't among the action effect's entities and its {@code q.missed}
 * keyframes never reach it. {@code q.user.play_on_missed_spread_targets('muddywater', 'splash', 'dodge')}
 * plays those generic animations (group first, then animation names) on exactly those foes, the same way
 * an {@code entity_molang} keyframe would. Misses Cobblemon does pass in (a single battle's) are left to
 * the JSON. Returns how many Pokemon it animated; 0 when the hook is missing, so nothing plays twice.
 */
public final class MissedTargets {
    public static final String FUNCTION = "play_on_missed_spread_targets";

    private static final Logger LOGGER = LoggerFactory.getLogger("cobblemon_extra_move_animation");
    /** Same reach as Cobblemon's own entity_molang keyframes. */
    private static final double RANGE = 200;
    /** Names go into a MoLang expression, so only plain identifiers are accepted. */
    private static final Pattern NAME = Pattern.compile("[a-z0-9_]+");
    private static boolean warned;

    private MissedTargets() {
    }

    public static void register() {
        try {
            PokemonEntityFunctions.add(FUNCTION, MissedTargets::run);
        } catch (Throwable t) {
            LOGGER.warn("Couldn't hook into Cobblemon's MoLang functions; foes a spread move misses won't be animated", t);
        }
    }

    private static Object run(PokemonEntity user, MoParams params) {
        // Never let an exception escape: a throwing keyframe would cut the rest of the move's timeline short
        try {
            if (!(user.getWorld() instanceof ServerWorld world) || params.getParams().size() < 2) {
                return DoubleValue.ZERO;
            }
            String group = params.getString(0).trim();
            Set<String> expressions = new LinkedHashSet<>();
            for (int i = 1; i < params.getParams().size(); i++) {
                String animation = params.getString(i).trim();
                if (NAME.matcher(group).matches() && NAME.matcher(animation).matches()) {
                    expressions.add("q.play_animation(q.bedrock_stateful('" + group + "', '" + animation + "', 'endures_primary_animations'))");
                }
            }
            PokemonBattle battle = user.getBattle();
            MoveInstruction move = CurrentMove.of(battle);
            if (expressions.isEmpty() || move == null) {
                return DoubleValue.ZERO;
            }
            int animated = 0;
            for (BattlePokemon missed : CurrentMove.missedTargets(move)) {
                PokemonEntity entity = missed.getEntity();
                if (entity == null || entity == user || CurrentMove.isListedTarget(move, missed, battle)) {
                    continue;
                }
                List<ServerPlayerEntity> players = new ArrayList<>();
                for (ServerPlayerEntity player : world.getPlayers()) {
                    if (player.squaredDistanceTo(entity) <= RANGE * RANGE) {
                        players.add(player);
                    }
                }
                new RunPosableMoLangPacket(entity.getId(), expressions).sendToPlayers(players);
                animated++;
                if (MoveStatChange.DEBUG) {
                    LOGGER.info("[debug] {}: {} on {}, which the move missed", FUNCTION, expressions, entity.getPokemon().getSpecies().getName());
                }
            }
            return new DoubleValue(animated);
        } catch (Throwable t) {
            if (!warned) {
                warned = true;
                LOGGER.warn("Animating the foes a move missed failed; they play no reaction", t);
            }
            return DoubleValue.ZERO;
        }
    }
}
