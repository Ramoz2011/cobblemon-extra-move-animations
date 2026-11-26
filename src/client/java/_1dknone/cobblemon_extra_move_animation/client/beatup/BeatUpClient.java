package _1dknone.cobblemon_extra_move_animation.client.beatup;

import _1dknone.cobblemon_extra_move_animation.beatup.BeatUpPayload;
import com.mojang.blaze3d.vertex.PoseStack;
import net.minecraft.client.Minecraft;
import net.minecraft.client.renderer.MultiBufferSource;
import net.minecraft.world.phys.Vec3;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.util.ArrayList;
import java.util.List;

/**
 * Client half of Beat Up's teammate afterimages: keeps the moves in progress, ticks their particles and
 * sounds, and draws the afterimages after the world's entities.
 *
 * <p>The afterimages lean on Cobblemon's model classes, which aren't a stable API. If anything about
 * them goes wrong, the afterimages switch off for the session and Beat Up keeps its JSON-driven effects.
 */
public final class BeatUpClient {
    static final Logger LOGGER = LoggerFactory.getLogger("cobblemon_extra_move_animation");

    private static final List<BeatUpSequence> SEQUENCES = new ArrayList<>();
    private static boolean disabled;

    private BeatUpClient() {
    }

    /** Forgets the moves in progress, e.g. when the player leaves the world. */
    public static void clear() {
        SEQUENCES.clear();
    }

    public static void start(Minecraft client, BeatUpPayload payload) {
        if (disabled || client.level == null || payload.teammates().isEmpty()) {
            return;
        }
        try {
            SEQUENCES.add(new BeatUpSequence(client.level, payload));
        } catch (Throwable t) {
            fail(t);
        }
    }

    public static void tick(Minecraft client) {
        if (SEQUENCES.isEmpty() || client.isPaused()) {
            return;
        }
        try {
            // a sequence ends once its last afterimage has faded, or when the player changes world
            SEQUENCES.removeIf(sequence -> !sequence.tick(client));
        } catch (Throwable t) {
            fail(t);
        }
    }

    public static void render(PoseStack poseStack, MultiBufferSource consumers, Vec3 camera, float tickDelta) {
        if (SEQUENCES.isEmpty() || consumers == null) {
            return;
        }
        try {
            for (BeatUpSequence sequence : SEQUENCES) {
                sequence.render(poseStack, consumers, camera, tickDelta);
            }
        } catch (Throwable t) {
            fail(t);
        }
    }

    private static void fail(Throwable t) {
        disabled = true;
        SEQUENCES.clear();
        LOGGER.warn("Beat Up's teammate afterimages ran into an error and are off for this session", t);
    }
}
