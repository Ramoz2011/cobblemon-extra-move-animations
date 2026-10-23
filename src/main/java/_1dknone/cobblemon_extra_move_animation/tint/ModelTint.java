package _1dknone.cobblemon_extra_move_animation.tint;

import _1dknone.cobblemon_extra_move_animation.molang.PokemonEntityFunctions;
import com.bedrockk.molang.runtime.MoParams;
import com.bedrockk.molang.runtime.value.DoubleValue;
import com.cobblemon.mod.common.entity.pokemon.PokemonEntity;
import net.fabricmc.fabric.api.networking.v1.PayloadTypeRegistry;
import net.fabricmc.fabric.api.networking.v1.ServerPlayNetworking;
import net.minecraft.server.network.ServerPlayerEntity;
import net.minecraft.server.world.ServerWorld;
import net.minecraft.util.math.MathHelper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

/**
 * Server half of the model tint: lets an action effect flash a Pokemon's whole model in a colour, the way
 * the games tint a Pokemon that powers up (Counter's red-orange glow).
 *
 * <p>MoLang: {@code q.user.model_tint(r, g, b, strength, flash, delay, rise, hold, fall)} with colour
 * channels and strength in 0..1, flash in -1..1 (see {@link ModelTintPayload}) and times in seconds. It
 * works on any Pokemon entity struct, so {@code q.target.model_tint(...)} tints the target. If this hook is missing the call returns 0 and the
 * move plays without the tint.
 */
public final class ModelTint {
    public static final String FUNCTION = "model_tint";

    private static final Logger LOGGER = LoggerFactory.getLogger("cobblemon_extra_move_animation");
    /** Same reach as Cobblemon's own entity_particles and entity_molang keyframes. */
    private static final double RANGE = 200;
    /** Keeps a typo in an action effect from leaving a Pokemon tinted for minutes. */
    private static final float MAX_SECONDS = 5;
    private static boolean warned;

    private ModelTint() {
    }

    public static void register() {
        PayloadTypeRegistry.playS2C().register(ModelTintPayload.ID, ModelTintPayload.CODEC);
        try {
            PokemonEntityFunctions.add(FUNCTION, ModelTint::run);
        } catch (Throwable t) {
            LOGGER.warn("Couldn't hook into Cobblemon's MoLang functions; moves will play without model tints", t);
        }
    }

    private static Object run(PokemonEntity entity, MoParams params) {
        // Never let an exception escape: a throwing keyframe would cut the rest of the move's timeline short
        try {
            if (!(entity.getWorld() instanceof ServerWorld world) || params.getParams().size() < 9) {
                return DoubleValue.ZERO;
            }
            int color = channel(params, 3) << 24 | channel(params, 0) << 16 | channel(params, 1) << 8 | channel(params, 2);
            ModelTintPayload payload = new ModelTintPayload(entity.getId(), color,
                    MathHelper.clamp((float) params.getDouble(4), -1F, 1F), seconds(params, 5),
                    seconds(params, 6), seconds(params, 7), seconds(params, 8));
            for (ServerPlayerEntity player : world.getPlayers()) {
                if (player.squaredDistanceTo(entity) <= RANGE * RANGE && ServerPlayNetworking.canSend(player, ModelTintPayload.ID)) {
                    ServerPlayNetworking.send(player, payload);
                }
            }
            return DoubleValue.ONE;
        } catch (Throwable t) {
            if (!warned) {
                warned = true;
                LOGGER.warn("A model tint failed; the move plays without it", t);
            }
            return DoubleValue.ZERO;
        }
    }

    private static float unit(MoParams params, int index) {
        return MathHelper.clamp((float) params.getDouble(index), 0F, 1F);
    }

    private static int channel(MoParams params, int index) {
        return Math.round(unit(params, index) * 255);
    }

    private static float seconds(MoParams params, int index) {
        return MathHelper.clamp((float) params.getDouble(index), 0F, MAX_SECONDS);
    }
}
