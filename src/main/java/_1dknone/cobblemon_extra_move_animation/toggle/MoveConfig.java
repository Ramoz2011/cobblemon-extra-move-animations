package _1dknone.cobblemon_extra_move_animation.toggle;

import com.google.gson.Gson;
import com.google.gson.GsonBuilder;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import com.google.gson.JsonParseException;
import com.google.gson.JsonParser;
import com.google.gson.JsonPrimitive;
import net.fabricmc.loader.api.FabricLoader;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.io.IOException;
import java.io.Reader;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Collection;
import java.util.Locale;
import java.util.Map;
import java.util.TreeMap;

/**
 * The file behind the per-move choice, {@code config/cobblemon_extra_move_animation.json}: one entry per
 * move, {@code "this_mod"} or {@code "cobblemon"} ({@code true}/{@code false} work too). Players change it
 * from the screen inside Cobblemon's settings; on a dedicated server the owner edits it and runs
 * {@code /reload}.
 *
 * <p>A file that can't be read is never overwritten by a reload, so a typo stays there to be fixed. Until
 * then every move plays this mod's animation.
 */
public final class MoveConfig {
    public static final String FILE_NAME = "cobblemon_extra_move_animation.json";
    static final String THIS_MOD = "this_mod";
    static final String COBBLEMON = "cobblemon";

    private static final Logger LOGGER = LoggerFactory.getLogger("cobblemon_extra_move_animation");
    private static final Gson GSON = new GsonBuilder().setPrettyPrinting().create();
    /** Move id to whether it plays this mod's animation. Swapped whole: the screen and the server read it from different threads. */
    private static volatile Map<String, Boolean> choices = Map.of();

    private MoveConfig() {
    }

    /** Whether the move plays this mod's animation. Moves the file doesn't mention do. */
    public static boolean usesThisMod(String move) {
        return choices.getOrDefault(move, true);
    }

    /**
     * Re-reads the file. Moves it doesn't mention yet (a new file, or moves added by an update) are written
     * in as {@code "this_mod"}, keeping everything else in it.
     */
    public static void load(Collection<String> moves) {
        JsonObject json = read();
        if (json == null) {
            choices = Map.of();
            return;
        }
        Map<String, Boolean> loaded = new TreeMap<>();
        boolean added = false;
        for (String move : moves) {
            JsonElement value = json.get(move);
            if (value == null) {
                json.addProperty(move, THIS_MOD);
                added = true;
            }
            Boolean thisMod = value == null ? Boolean.TRUE : parse(value);
            if (thisMod == null) {
                LOGGER.warn("config/{}: \"{}\" should be \"{}\" or \"{}\"; it plays this mod's animation", FILE_NAME, move, THIS_MOD, COBBLEMON);
                thisMod = true;
            }
            loaded.put(move, thisMod);
        }
        for (String key : json.keySet()) {
            if (!moves.contains(key)) {
                LOGGER.warn("config/{}: \"{}\" isn't a move this mod animates", FILE_NAME, key);
            }
        }
        choices = Map.copyOf(loaded);
        if (added) {
            write(json);
        }
    }

    /** Stores new choices and writes them to the file; anything else in it stays. */
    public static void save(Map<String, Boolean> newChoices) {
        JsonObject existing = read();
        // the player chose these on the screen, so they replace a file that couldn't be read
        JsonObject json = existing != null ? existing : new JsonObject();
        Map<String, Boolean> merged = new TreeMap<>(choices);
        newChoices.forEach((move, thisMod) -> {
            json.addProperty(move, thisMod ? THIS_MOD : COBBLEMON);
            merged.put(move, thisMod);
        });
        choices = Map.copyOf(merged);
        write(json);
    }

    private static Path path() {
        return FabricLoader.getInstance().getConfigDir().resolve(FILE_NAME);
    }

    /** The file's contents: empty when there's no file yet, null when it can't be read. */
    private static JsonObject read() {
        Path path = path();
        if (!Files.exists(path)) {
            return new JsonObject();
        }
        try (Reader reader = Files.newBufferedReader(path)) {
            JsonElement json = JsonParser.parseReader(reader);
            if (!json.isJsonObject()) {
                throw new JsonParseException("expected { \"move\": \"" + THIS_MOD + "\", ... }");
            }
            return json.getAsJsonObject();
        } catch (IOException | RuntimeException e) {
            LOGGER.warn("Couldn't read config/{}, so every move plays this mod's animation until it's fixed: {}", FILE_NAME, e.getMessage());
            return null;
        }
    }

    private static void write(JsonObject json) {
        JsonObject sorted = new JsonObject();
        new TreeMap<>(json.asMap()).forEach(sorted::add);
        try {
            Files.createDirectories(path().getParent());
            Files.writeString(path(), GSON.toJson(sorted) + System.lineSeparator());
        } catch (IOException e) {
            LOGGER.warn("Couldn't write config/{}", FILE_NAME, e);
        }
    }

    private static Boolean parse(JsonElement value) {
        if (!value.isJsonPrimitive()) {
            return null;
        }
        JsonPrimitive primitive = value.getAsJsonPrimitive();
        if (primitive.isBoolean()) {
            return primitive.getAsBoolean();
        }
        return switch (primitive.getAsString().trim().toLowerCase(Locale.ROOT)) {
            case THIS_MOD -> Boolean.TRUE;
            case COBBLEMON -> Boolean.FALSE;
            default -> null;
        };
    }
}
