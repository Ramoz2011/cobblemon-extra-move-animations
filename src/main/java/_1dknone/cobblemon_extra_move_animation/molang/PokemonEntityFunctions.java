package _1dknone.cobblemon_extra_move_animation.molang;

import com.bedrockk.molang.runtime.MoParams;
import com.cobblemon.mod.common.api.molang.MoLangFunctions;
import com.cobblemon.mod.common.entity.pokemon.PokemonEntity;
import kotlin.jvm.functions.Function1;

import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.function.BiFunction;

/**
 * Adds functions to the MoLang struct of a Pokemon entity, so an action effect can call
 * {@code q.user.<name>(...)} or {@code q.target.<name>(...)}. A function that isn't registered just
 * returns 0 in MoLang, so a move whose hook failed to register still plays its JSON effects.
 */
public final class PokemonEntityFunctions {
    private PokemonEntityFunctions() {
    }

    @SuppressWarnings("unchecked")
    public static void add(String name, BiFunction<PokemonEntity, MoParams, Object> function) throws ReflectiveOperationException {
        Class<?> holder;
        try {
            // Cobblemon 1.8 moved the per-type functions into holder objects with a list for add-ons
            holder = Class.forName("com.cobblemon.mod.common.api.molang.function.PokemonEntityMoLangFunctions");
        } catch (ClassNotFoundException e) {
            holder = null;
        }
        if (holder != null) {
            Object instance = holder.getField("INSTANCE").get(null);
            List<Function1<PokemonEntity, Map<String, Function1<MoParams, Object>>>> custom =
                    (List<Function1<PokemonEntity, Map<String, Function1<MoParams, Object>>>>) holder.getMethod("getCustom").invoke(instance);
            custom.add(entity -> Map.of(name, params -> function.apply(entity, params)));
        } else {
            MoLangFunctions.INSTANCE.getPokemonEntityFunctions().add(entity -> {
                HashMap<String, java.util.function.Function<MoParams, Object>> functions = new HashMap<>();
                functions.put(name, params -> function.apply(entity, params));
                return functions;
            });
        }
    }
}
