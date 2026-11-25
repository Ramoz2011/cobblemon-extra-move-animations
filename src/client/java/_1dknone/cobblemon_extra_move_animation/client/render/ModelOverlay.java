package _1dknone.cobblemon_extra_move_animation.client.render;

import com.cobblemon.mod.common.client.entity.PokemonClientDelegate;
import com.cobblemon.mod.common.client.render.models.blockbench.PosableModel;
import com.cobblemon.mod.common.client.render.models.blockbench.repository.RenderContext;
import com.cobblemon.mod.common.client.render.models.blockbench.repository.VaryingModelRepository;
import com.cobblemon.mod.common.entity.pokemon.PokemonEntity;
import com.cobblemon.mod.common.pokemon.Pokemon;
import com.mojang.blaze3d.vertex.PoseStack;
import com.mojang.math.Axis;
import net.minecraft.client.renderer.LightTexture;
import net.minecraft.client.renderer.MultiBufferSource;
import net.minecraft.client.renderer.RenderType;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.util.Mth;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.entity.EntityDimensions;
import net.minecraft.world.phys.Vec3;

/**
 * Draws a Pokemon's own model again, in its current pose, a hair larger than the real one and in a
 * colour, as a translucent shell over it: Beat Up's dark hit flash and the model tint both use it.
 *
 * <p>Leans on Cobblemon's model classes, which aren't a stable API, so it throws on anything it can't
 * handle and leaves it to the caller to switch its effect off.
 */
public final class ModelOverlay {
    /** Just outside the real model, so only the shell facing the camera passes the depth test. */
    private static final float INFLATE = 1.015F;

    private final RenderContext context = new RenderContext();

    /**
     * @param color   ARGB multiplier over the model's texture (after the overlay)
     * @param overlay packed overlay UV, e.g. {@code OverlayTexture.packUv(u, 10)} washes the texture towards
     *                white by u/15*75% before the colour is applied
     * @return false if the entity isn't a rendered Pokemon
     */
    public boolean render(PoseStack matrices, MultiBufferSource consumers, Vec3 camera, Entity entity,
                          float tickDelta, int color, int overlay) {
        if (!(entity instanceof PokemonEntity pokemonEntity) || !(pokemonEntity.getDelegate() instanceof PokemonClientDelegate state)) {
            return false;
        }
        Pokemon pokemon = pokemonEntity.getPokemon();
        ResourceLocation species = pokemon.getSpecies().getResourceIdentifier();
        VaryingModelRepository repository = VaryingModelRepository.INSTANCE;
        PosableModel model = repository.getPoser(species, state);
        ResourceLocation texture = repository.getTexture(species, state);
        context.put(RenderContext.Companion.getRENDER_STATE(), RenderContext.RenderState.WORLD);
        context.put(RenderContext.Companion.getENTITY(), pokemonEntity);
        context.put(RenderContext.Companion.getSPECIES(), species);
        context.put(RenderContext.Companion.getASPECTS(), pokemon.getAspects());
        context.put(RenderContext.Companion.getTEXTURE(), texture);
        context.put(RenderContext.Companion.getSCALE(), pokemon.getForm().getBaseScale());
        context.put(RenderContext.Companion.getPOSABLE_STATE(), state);
        model.setContext(context);

        // the same pose LivingEntityRenderer gave it this frame (applying it again changes nothing)
        float bodyYaw = Mth.rotLerp(tickDelta, pokemonEntity.yBodyRotO, pokemonEntity.yBodyRot);
        float headYaw = Mth.rotLerp(tickDelta, pokemonEntity.yHeadRotO, pokemonEntity.yHeadRot) - bodyYaw;
        model.applyAnimations(pokemonEntity, state, pokemonEntity.walkAnimation.position(tickDelta),
                pokemonEntity.walkAnimation.speed(tickDelta), pokemonEntity.tickCount + tickDelta, headYaw, pokemonEntity.getViewXRot(tickDelta));
        model.resetLayerContext();

        // The renderer's own scale factors moved between Cobblemon versions, but the entity's height is
        // always its form's hitbox times that scale
        EntityDimensions hitbox = pokemon.getForm().getHitbox();
        float scale = (hitbox.fixed() || hitbox.height() <= 0 ? pokemon.getForm().getBaseScale()
                : pokemonEntity.getBbHeight() / hitbox.height()) * INFLATE;
        Vec3 pos = pokemonEntity.getPosition(tickDelta);
        matrices.pushPose();
        matrices.translate(pos.x - camera.x, pos.y - camera.y, pos.z - camera.z);
        matrices.mulPose(Axis.YP.rotationDegrees(180F - bodyYaw));
        matrices.scale(-1F, -1F, 1F);
        matrices.scale(scale, scale, scale);
        matrices.translate(0F, -1.501F + 1.5F, 0F);
        model.render(context, matrices, consumers.getBuffer(RenderType.entityTranslucent(texture)),
                LightTexture.FULL_BRIGHT, overlay, color);
        matrices.popPose();
        model.setDefault();
        return true;
    }

    /** Packs alpha and red/green/blue (all 0..1) into an ARGB int. */
    public static int argb(float alpha, float red, float green, float blue) {
        return channel(alpha) << 24 | channel(red) << 16 | channel(green) << 8 | channel(blue);
    }

    private static int channel(float value) {
        return (int) (Mth.clamp(value, 0F, 1F) * 255);
    }
}
