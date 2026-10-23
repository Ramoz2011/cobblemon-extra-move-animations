package _1dknone.cobblemon_extra_move_animation.client.beatup;

import _1dknone.cobblemon_extra_move_animation.client.render.ModelOverlay;
import net.minecraft.client.render.OverlayTexture;
import net.minecraft.client.render.VertexConsumerProvider;
import net.minecraft.client.util.math.MatrixStack;
import net.minecraft.entity.Entity;
import net.minecraft.util.math.Vec3d;

/**
 * The target darkening for an instant on every hit, as Black/White 2 shows Beat Up: its own model, in
 * its current pose, drawn again a hair larger in near-black violet over the real one.
 */
final class TargetFlash {
    // ARGB multipliers at full strength
    private static final float[] SHADE = {0.78F, 0.08F, 0.03F, 0.14F};

    /** Off for the session after any error: the flash is an extra, the afterimages carry on without it. */
    private static boolean broken;

    private final ModelOverlay overlay = new ModelOverlay();

    void render(MatrixStack matrices, VertexConsumerProvider consumers, Vec3d camera, Entity entity, float tickDelta,
                float strength) {
        if (broken || strength <= 0) {
            return;
        }
        try {
            int color = ModelOverlay.argb(SHADE[0] * Math.min(strength, 1F), SHADE[1], SHADE[2], SHADE[3]);
            overlay.render(matrices, consumers, camera, entity, tickDelta, color, OverlayTexture.DEFAULT_UV);
        } catch (RuntimeException | LinkageError e) {
            broken = true;
            BeatUpClient.LOGGER.warn("Couldn't draw Beat Up's hit flash; it's off for this session", e);
        }
    }
}
