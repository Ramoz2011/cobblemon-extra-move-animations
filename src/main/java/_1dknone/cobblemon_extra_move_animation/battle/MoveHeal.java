package _1dknone.cobblemon_extra_move_animation.battle;

import _1dknone.cobblemon_extra_move_animation.molang.PokemonEntityFunctions;
import com.bedrockk.molang.runtime.MoParams;
import com.bedrockk.molang.runtime.value.DoubleValue;
import com.cobblemon.mod.common.api.battles.interpreter.BattleContext;
import com.cobblemon.mod.common.api.battles.interpreter.BattleMessage;
import com.cobblemon.mod.common.api.battles.interpreter.Effect;
import com.cobblemon.mod.common.api.battles.model.PokemonBattle;
import com.cobblemon.mod.common.battles.dispatch.InterpreterInstruction;
import com.cobblemon.mod.common.battles.interpreter.ContextManager;
import com.cobblemon.mod.common.battles.interpreter.instructions.FailInstruction;
import com.cobblemon.mod.common.battles.interpreter.instructions.HealInstruction;
import com.cobblemon.mod.common.battles.interpreter.instructions.MoveInstruction;
import com.cobblemon.mod.common.battles.pokemon.BattlePokemon;
import com.cobblemon.mod.common.entity.pokemon.PokemonEntity;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.util.Collection;
import java.util.List;
import java.util.Locale;

/**
 * Lets an action effect ask how much HP the move it animates restores, by the battle's own log, so a
 * weather-dependent heal (Moonlight, Morning Sun, Synthesis) can look brighter in harsh sunlight and softer
 * in rain, sand, hail or snow. It only reads what the battle already decided; it never changes the heal.
 *
 * <p>MoLang: {@code q.entity.move_heal_share} (any Pokemon entity struct, so {@code q.user.move_heal_share}
 * for a move that heals its user) returns the share of max HP the move's heal was worth to that Pokemon:
 * <ul>
 *   <li>2/3, 1/2 or 1/4 (rounded to whichever of these it is closest to): Showdown prints the HP the Pokemon
 *   ends on, and Cobblemon still holds the HP it had before, so when the heal didn't top it up the share is
 *   exactly what Showdown worked out from the weather (its "effective weather" already counts Cloud Nine,
 *   Air Lock and Utility Umbrella). When the heal did top it up it may have been worth more than it gave;
 *   then the field's weather, as Cobblemon tracks it, picks the share it can still be.</li>
 *   <li>-1 when the move's heal failed because the Pokemon's HP was already full ({@code |-fail|POKEMON|heal}).</li>
 *   <li>0 when the log says nothing about a heal for that Pokemon, or the battle can't be followed. If this hook
 *   is missing altogether the call also returns 0, so an effect that treats 0 as "normal" always plays.</li>
 * </ul>
 * Only the move's own heal counts: the {@code -heal} lines after its {@code |move|} line and before the next
 * move that carry no {@code [from]} (items, abilities, drain), {@code [wisher]}, {@code [zeffect]} or
 * {@code [silent]} tag. The battle has worked all of this out before the move's action effect starts, so the
 * answer is known from its first keyframe.
 */
public final class MoveHeal {
    public static final String FUNCTION = "move_heal_share";

    private static final Logger LOGGER = LoggerFactory.getLogger("cobblemon_extra_move_animation");
    private static final double[] SHARES = {0.25, 0.5, 2.0 / 3.0};
    private static final String[] NOT_THE_MOVE = {"from", "wisher", "zeffect", "silent"};
    private static boolean warned;

    private MoveHeal() {
    }

    public static void register() {
        try {
            PokemonEntityFunctions.add(FUNCTION, MoveHeal::run);
        } catch (Throwable t) {
            LOGGER.warn("Couldn't hook into Cobblemon's MoLang functions; weather-dependent heals will always play their normal version", t);
        }
    }

    private static Object run(PokemonEntity entity, MoParams params) {
        // Never let an exception escape: a throwing keyframe would cut the rest of the move's timeline short
        try {
            double share = share(entity);
            return new DoubleValue(share);
        } catch (Throwable t) {
            if (!warned) {
                warned = true;
                LOGGER.warn("Reading the battle's heal failed; weather-dependent heals play their normal version", t);
            }
            return DoubleValue.ZERO;
        }
    }

    static double share(PokemonEntity entity) {
        PokemonBattle battle = entity.getBattle();
        MoveInstruction move = CurrentMove.of(battle);
        if (move == null) {
            return debug(entity, 0, "no move to follow");
        }
        List<InterpreterInstruction> instructions = move.getInstructionSet().getInstructions();
        int start = instructions.indexOf(move);
        if (start < 0) {
            return debug(entity, 0, "move not in its instruction set");
        }
        for (int i = start + 1; i < instructions.size(); i++) {
            InterpreterInstruction instruction = instructions.get(i);
            if (instruction instanceof MoveInstruction) {
                break;
            }
            if (instruction instanceof HealInstruction heal) {
                BattleMessage message = heal.getPrivateMessage();
                if (isTagged(message)) {
                    continue;
                }
                BattlePokemon pokemon = message.battlePokemon(0, battle);
                if (!MoveStatChange.isFor(pokemon, entity)) {
                    continue;
                }
                double[] hp = parseHp(message.argumentAt(1));
                if (hp == null) {
                    continue;
                }
                double before = pokemon.getHealth();
                double max = hp[1] > 0 ? hp[1] : pokemon.getMaxHealth();
                if (max <= 0 || hp[0] <= before) {
                    continue;
                }
                double healed = (hp[0] - before) / max;
                if (hp[0] < max) {
                    return debug(entity, nearest(healed), String.format(Locale.ROOT, "healed %.0f of %.0f (%.3f)",
                            hp[0] - before, max, healed));
                }
                // topped up: the heal was worth at least `healed`; take the weather's share if it can be that
                String weather = weather(battle);
                double fromWeather = weatherShare(weather);
                double share = fromWeather >= healed - 0.01 ? fromWeather : smallestAtLeast(healed);
                return debug(entity, share, String.format(Locale.ROOT, "topped up, healed %.0f of %.0f (%.3f), weather %s",
                        hp[0] - before, max, healed, weather));
            }
            if (instruction instanceof FailInstruction fail) {
                BattleMessage message = fail.getMessage();
                Effect what = message.effectAt(1);
                if (what != null && "heal".equals(what.getId()) && MoveStatChange.isFor(message.battlePokemon(0, battle), entity)) {
                    return debug(entity, -1, "heal failed (HP full)");
                }
            }
        }
        return debug(entity, 0, "no heal in the log");
    }

    private static boolean isTagged(BattleMessage message) {
        for (String tag : NOT_THE_MOVE) {
            if (message.hasOptionalArgument(tag)) {
                return true;
            }
        }
        return false;
    }

    /** "300/394" or "300/394 par" -> {300, 394}; null if it isn't HP. */
    private static double[] parseHp(String raw) {
        if (raw == null) {
            return null;
        }
        String[] parts = raw.trim().split(" ")[0].split("/");
        if (parts.length != 2) {
            return null;
        }
        try {
            return new double[]{Double.parseDouble(parts[0]), Double.parseDouble(parts[1])};
        } catch (NumberFormatException e) {
            return null;
        }
    }

    private static double nearest(double healed) {
        double best = SHARES[0];
        for (double s : SHARES) {
            if (Math.abs(s - healed) < Math.abs(best - healed)) {
                best = s;
            }
        }
        return best;
    }

    private static double smallestAtLeast(double healed) {
        for (double s : SHARES) {
            if (s >= healed - 0.01) {
                return s;
            }
        }
        return healed;
    }

    /**
     * The field's weather as Cobblemon tracks it, as a Showdown id ("sunnyday", "raindance"...), or "none".
     * Cobblemon marks its ContextManager deprecated (to be replaced; side conditions aren't reliable outside
     * singles, the field's weather is), so this is only asked when a heal topped the HP up, and any failure
     * reads as no weather: the normal look.
     */
    @SuppressWarnings("deprecation")
    static String weather(PokemonBattle battle) {
        try {
            if (battle == null) {
                return "none";
            }
            ContextManager contexts = battle.getContextManager();
            Collection<BattleContext> weather = contexts.get(BattleContext.Type.WEATHER);
            if (weather == null || weather.isEmpty()) {
                return "none";
            }
            return weather.iterator().next().getId().toLowerCase(Locale.ROOT).replaceAll("[^a-z0-9]", "");
        } catch (Throwable t) {
            return "none";
        }
    }

    /** Moonlight, Morning Sun and Synthesis: 2/3 in harsh sunlight, 1/4 in rain, sandstorm, hail or snow, else 1/2. */
    private static double weatherShare(String weather) {
        return switch (weather) {
            case "sunnyday", "desolateland" -> 2.0 / 3.0;
            case "raindance", "primordialsea", "sandstorm", "hail", "snow", "snowscape" -> 0.25;
            default -> 0.5;
        };
    }

    private static double debug(PokemonEntity entity, double share, String why) {
        if (MoveStatChange.DEBUG) {
            LOGGER.info("[debug] {} on {}: {} ({})", FUNCTION, entity.getPokemon().getSpecies().getName(),
                    String.format(Locale.ROOT, "%.3f", share), why);
        }
        return share;
    }
}
