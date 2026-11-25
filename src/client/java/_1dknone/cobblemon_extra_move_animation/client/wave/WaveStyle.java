package _1dknone.cobblemon_extra_move_animation.client.wave;

import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.util.Mth;

/**
 * The numbers behind one wave: when each part happens, how big it gets, its colours. Read from
 * {@code assets/<namespace>/wave_effects/<name>.json} (Muddy Water's is written by
 * {@code docs/tools/muddywater_gen.py} from the same timing constants as its action effect and
 * animations). Missing values fall back to Muddy Water's. Press F3+T in game to reload after an edit.
 *
 * <p>All times are seconds from the start of the move, sizes are blocks.
 */
final class WaveStyle {
    /** Greyscale, tileable: the vertex colours below tint it. */
    final ResourceLocation texture;
    /** World size of one repeat of the texture. */
    final float textureBlocks;
    /** Texture repeats per second the water flows along the wave (over the crest and down its face). */
    final float flowSpeed;
    /**
     * How far every normal is tipped towards the sky (0 = true shape). Minecraft lights entities from
     * above, so without this the steep crown and wave face come out much darker than flat water.
     */
    final float lightingUpBias;

    // ---- timing
    /** The crown of water starts rising round the user. */
    final float crownRise;
    /** ... and reaches its full height. */
    final float crownPeak;
    /** The crown collapses forward into the wave, which starts rolling towards the targets. */
    final float release;
    /** The wave crashes onto the targets (their hit animation and splash are keyed to this). */
    final float impact;
    /** The crash has flattened into a flood. */
    final float crashEnd;
    /** The flood has drained away: nothing is drawn after this. */
    final float drainEnd;

    // ---- the crown round the user
    final Size crownHeight;
    /** Gap between the user's body and the inside of the crown. */
    final float crownGap;
    /** How far the crown opens outwards per block of height (a bowl, as in Scarlet/Violet). */
    final float crownFlare;
    /** Degrees per second the crown and the pool under it swirl. */
    final float crownSwirl;
    /** How ragged the crown's top edge is (share of its height). */
    final float crownJag;
    /** Seconds the crown takes to collapse once the wave is released. */
    final float crownCollapse;
    /** How far the muddy pool spreads past the user's body. */
    final float poolRadius;

    // ---- the wave
    final Size waveHeight;
    /** Where the wave forms, in front of the user's body. */
    final float startGap;
    /** Room the wave leaves at its sides past the outermost target. */
    final float sidePadding;
    /** Narrowest the wave gets (half its width). */
    final float minHalfWidth;
    /** How far the curling lip reaches forward (share of the wave's height). */
    final float lip;
    /** How far the wave's ends trail behind its middle (share of its height). */
    final float bow;
    /** How far past the targets the water surges after the crash (share of the wave's height). */
    final float overshoot;
    /** How uneven the crest is (share of the height). */
    final float crestNoise;
    /**
     * How square the wave's ends are: its height across the width is (1 - |u|^endTaper)^0.5 with u = -1..1.
     * Higher keeps it full height further out (a long crest); low values round it into a hill.
     */
    final float endTaper;
    /** Where the foam starts up the wave's back (0 = its foot, 1 = the crest): what you see from behind. */
    final float foamBack;
    /** How far down the face the foam reaches from the crest (0..1 of the face). */
    final float foamFace;
    /** Strength of the lighter and darker swirls drifting through the water (0 = flat colour). */
    final float mottle;

    // ---- colours (r, g, b in 0..1) and opacity
    /** Thick water: the bottom of the crown and the body of the wave. */
    final float[] deep;
    final float[] body;
    /** Thin water and the lighter swirls in it. */
    final float[] light;
    /** Foam on the crest, the lip and the crown's rim. */
    final float[] foam;
    final float alphaBody;
    final float alphaSheet;
    final float alphaFoam;
    final float alphaCrown;
    final float alphaPool;

    /** A size that follows the user's height: {@code scale * height + add}, kept within min..max. */
    record Size(float scale, float add, float min, float max) {
        float of(float height) {
            return Mth.clamp(scale * height + add, min, max);
        }
    }

    private WaveStyle(JsonObject json) {
        texture = ResourceLocation.parse(string(json, "texture", "cobblemon_extra_move_animation:textures/effect/muddy_water.png"));
        textureBlocks = Math.max(0.1F, number(json, "texture_blocks", 2F));
        flowSpeed = number(json, "flow_speed", 0.9F);
        lightingUpBias = Math.max(0F, number(json, "lighting_up_bias", 0.6F));

        JsonObject time = object(json, "time");
        crownRise = number(time, "crown_rise", 0.18F);
        crownPeak = Math.max(crownRise + 0.01F, number(time, "crown_peak", 0.52F));
        release = Math.max(crownRise, number(time, "release", 0.6F));
        impact = Math.max(release + 0.05F, number(time, "impact", 1.05F));
        crashEnd = Math.max(impact + 0.05F, number(time, "crash_end", 1.35F));
        drainEnd = Math.max(crashEnd + 0.05F, number(time, "drain_end", 1.95F));

        JsonObject crown = object(json, "crown");
        crownHeight = size(object(crown, "height"), new Size(1.1F, 0.35F, 1F, 3.2F));
        crownGap = number(crown, "gap", 0.3F);
        crownFlare = number(crown, "flare", 0.35F);
        crownSwirl = number(crown, "swirl", 200F);
        crownJag = number(crown, "jag", 0.22F);
        crownCollapse = Math.max(0.02F, number(crown, "collapse", 0.16F));
        poolRadius = number(crown, "pool_radius", 1.1F);

        JsonObject wave = object(json, "wave");
        waveHeight = size(object(wave, "height"), new Size(0.75F, 0.8F, 1.5F, 3.0F));
        startGap = number(wave, "start_gap", 0.35F);
        sidePadding = number(wave, "side_padding", 1.3F);
        minHalfWidth = Math.max(0.3F, number(wave, "min_half_width", 2.2F));
        lip = number(wave, "lip", 0.5F);
        bow = number(wave, "bow", 0.2F);
        overshoot = number(wave, "overshoot", 0.9F);
        crestNoise = number(wave, "crest_noise", 0.08F);
        endTaper = Math.max(1F, number(wave, "end_taper", 6F));
        foamBack = Mth.clamp(number(wave, "foam_back", 0.6F), 0F, 0.99F);
        foamFace = Mth.clamp(number(wave, "foam_face", 0.45F), 0.01F, 1F);
        mottle = Math.max(0F, number(wave, "mottle", 0.35F));

        JsonObject color = object(json, "color");
        deep = color(color, "deep", "#5C3F20");
        body = color(color, "body", "#8E6538");
        light = color(color, "light", "#C49A62");
        foam = color(color, "foam", "#F2E6CC");

        JsonObject alpha = object(json, "alpha");
        alphaBody = number(alpha, "body", 0.92F);
        alphaSheet = number(alpha, "sheet", 0.7F);
        alphaFoam = number(alpha, "foam", 0.97F);
        alphaCrown = number(alpha, "crown", 0.9F);
        alphaPool = number(alpha, "pool", 0.8F);
    }

    static WaveStyle parse(JsonObject json) {
        return new WaveStyle(json);
    }

    private static JsonObject object(JsonObject json, String key) {
        JsonElement element = json == null ? null : json.get(key);
        return element != null && element.isJsonObject() ? element.getAsJsonObject() : new JsonObject();
    }

    private static float number(JsonObject json, String key, float fallback) {
        JsonElement element = json.get(key);
        return element != null && element.isJsonPrimitive() && element.getAsJsonPrimitive().isNumber() ? element.getAsFloat() : fallback;
    }

    private static String string(JsonObject json, String key, String fallback) {
        JsonElement element = json.get(key);
        return element != null && element.isJsonPrimitive() ? element.getAsString() : fallback;
    }

    private static Size size(JsonObject json, Size fallback) {
        return new Size(number(json, "scale", fallback.scale()), number(json, "add", fallback.add()),
                number(json, "min", fallback.min()), number(json, "max", fallback.max()));
    }

    /** "#RRGGBB" -> {r, g, b} in 0..1. */
    private static float[] color(JsonObject json, String key, String fallback) {
        String hex = string(json, key, fallback);
        int rgb;
        try {
            rgb = Integer.parseUnsignedInt(hex.startsWith("#") ? hex.substring(1) : hex, 16);
        } catch (NumberFormatException e) {
            rgb = Integer.parseUnsignedInt(fallback.substring(1), 16);
        }
        return new float[]{(rgb >> 16 & 255) / 255F, (rgb >> 8 & 255) / 255F, (rgb & 255) / 255F};
    }
}
