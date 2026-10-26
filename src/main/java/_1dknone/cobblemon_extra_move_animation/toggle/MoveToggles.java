package _1dknone.cobblemon_extra_move_animation.toggle;

import com.cobblemon.mod.common.api.Priority;
import com.cobblemon.mod.common.api.moves.animations.ActionEffectTimeline;
import com.cobblemon.mod.common.api.moves.animations.ActionEffects;
import net.fabricmc.fabric.api.event.lifecycle.v1.ServerLifecycleEvents;
import net.fabricmc.fabric.api.networking.v1.PayloadTypeRegistry;
import net.fabricmc.fabric.api.networking.v1.ServerPlayConnectionEvents;
import net.fabricmc.fabric.api.networking.v1.ServerPlayNetworking;
import net.fabricmc.fabric.api.resource.IdentifiableResourceReloadListener;
import net.fabricmc.fabric.api.resource.ResourceManagerHelper;
import net.fabricmc.loader.api.FabricLoader;
import net.minecraft.resource.Resource;
import net.minecraft.resource.ResourceManager;
import net.minecraft.resource.ResourceReloader;
import net.minecraft.resource.ResourceType;
import net.minecraft.server.MinecraftServer;
import net.minecraft.server.PlayerManager;
import net.minecraft.server.network.ServerPlayerEntity;
import net.minecraft.util.Identifier;
import net.minecraft.util.Unit;
import net.minecraft.util.profiler.Profiler;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.io.BufferedReader;
import java.io.ByteArrayInputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collections;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.StringJoiner;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.Executor;
import java.util.stream.Stream;

/**
 * Lets each move play either this mod's animation or the one Cobblemon plays without it: Cobblemon's own
 * where it has one (1.8 animates Hydro Pump and Draco Meteor), otherwise its generic move animation.
 *
 * <p>Our action effects stay ordinary data files, so if this hook ever breaks every move keeps this mod's
 * animation. Each time Cobblemon loads its action effects, this works out both versions of every effect we
 * ship, then puts the chosen one into Cobblemon's map, where a battle looks it up when the move runs. That
 * map is the server's, so the server's choice counts for everyone on it.
 */
public final class MoveToggles {
    private static final Logger LOGGER = LoggerFactory.getLogger("cobblemon_extra_move_animation");
    private static final String MOD_ID = "cobblemon_extra_move_animation";
    private static final String DATA = "data/cobblemon/";
    private static final String EFFECTS = "action_effects";
    /** A two-turn move's charge turn (prepare_solarbeam) goes with the move. */
    private static final String CHARGE_PREFIX = "prepare_";

    /** The data the running reload reads; every reload listener gets it before any of them applies. */
    private static volatile ResourceManager resources;
    private static volatile MinecraftServer server;
    private static volatile Map<Identifier, Choice> choices = Map.of();
    private static volatile List<String> cobblemonMoves = List.of();
    private static List<EffectFile> effectFiles;
    private static boolean warned;

    private MoveToggles() {
    }

    public static void register() {
        PayloadTypeRegistry.playS2C().register(MoveChoicesPayload.ID, MoveChoicesPayload.CODEC);
        ServerLifecycleEvents.SERVER_STARTING.register(started -> server = started);
        ServerLifecycleEvents.SERVER_STOPPED.register(stopped -> server = null);
        ServerPlayConnectionEvents.JOIN.register((handler, sender, joined) -> send(handler.player));
        try {
            ResourceManagerHelper.get(ResourceType.SERVER_DATA).registerReloadListener(new ResourceCapture());
            ActionEffects.INSTANCE.getObservable().subscribe(Priority.NORMAL, MoveToggles::onReload);
        } catch (Throwable t) {
            LOGGER.warn("Couldn't hook into Cobblemon's action effects; every move plays this mod's animation", t);
        }
    }

    /** The moves this mod animates, by Showdown id ("hydropump"). */
    public static List<String> moves() {
        return effectFiles().stream().map(EffectFile::move).distinct().sorted().toList();
    }

    /** Whether the installed Cobblemon animates the move itself, rather than with its generic animation. */
    public static boolean cobblemonAnimates(String move) {
        return FabricLoader.getInstance().getModContainer("cobblemon")
                .flatMap(container -> container.findPath(DATA + EFFECTS + "/moves/" + move + ".json"))
                .isPresent();
    }

    /** Puts the current choices into Cobblemon's map, e.g. after the screen changed them. Run it on the server thread. */
    public static void apply() {
        try {
            apply(ActionEffects.INSTANCE.getActionEffects());
        } catch (Throwable t) {
            warnOnce(t);
        }
    }

    private static void onReload(ActionEffects effects) {
        // Never let an exception escape: it would abort the rest of Cobblemon's data reload
        try {
            MoveConfig.load(moves());
            Map<Identifier, ActionEffectTimeline> map = effects.getActionEffects();
            ResourceManager manager = resources;
            Map<Identifier, Choice> found = new LinkedHashMap<>();
            for (EffectFile file : effectFiles()) {
                try {
                    Choice choice = choose(file, map.get(file.key()), manager);
                    if (choice != null) {
                        found.put(file.key(), choice);
                    }
                } catch (Exception e) {
                    LOGGER.warn("Couldn't load both animations for {}; it plays whichever loaded", file.key(), e);
                }
            }
            choices = Collections.unmodifiableMap(found);
            apply(map);
        } catch (Throwable t) {
            warnOnce(t);
        }
    }

    /** This mod's version of one effect, and whatever plays without it (null for Cobblemon's generic animation). */
    private static Choice choose(EffectFile file, ActionEffectTimeline loaded, ResourceManager manager) throws IOException {
        byte[] ours = read(MOD_ID, file);
        if (ours == null) {
            return null;
        }
        byte[] own = read("cobblemon", file);
        // every copy of the file, lowest priority first: the top one is what Cobblemon just loaded
        List<byte[]> copies = manager == null ? List.of() : copies(manager, file);
        byte[] top = copies.isEmpty() ? null : copies.getLast();
        if (top == null || Arrays.equals(top, ours)) {
            // without ours, the next copy down would have loaded; when the packs only show their top copy,
            // that's Cobblemon's own
            byte[] below = own;
            for (int i = copies.size() - 2; i >= 0; i--) {
                if (!Arrays.equals(copies.get(i), ours)) {
                    below = copies.get(i);
                    break;
                }
            }
            return new Choice(file.move(), loaded != null ? loaded : parse(ours, file), below == null ? null : parse(below, file));
        }
        // Something loaded over ours. Cobblemon's own copy still gives way to ours, since mod packs have no
        // guaranteed order; a data pack or another add-on keeps winning, as it always has.
        ActionEffectTimeline thisMod = Arrays.equals(top, own) ? parse(ours, file) : loaded;
        return new Choice(file.move(), thisMod, loaded);
    }

    private static void apply(Map<Identifier, ActionEffectTimeline> map) {
        List<String> cobblemon = new ArrayList<>();
        for (Map.Entry<Identifier, Choice> entry : choices.entrySet()) {
            Choice choice = entry.getValue();
            boolean thisMod = MoveConfig.usesThisMod(choice.move());
            ActionEffectTimeline timeline = thisMod ? choice.thisMod() : choice.cobblemon();
            if (timeline == null) {
                map.remove(entry.getKey());
            } else {
                map.put(entry.getKey(), timeline);
            }
            if (!thisMod && !cobblemon.contains(choice.move())) {
                cobblemon.add(choice.move());
            }
        }
        cobblemonMoves = List.copyOf(cobblemon);
        if (!cobblemon.isEmpty()) {
            LOGGER.info("Moves playing Cobblemon's animation instead of this mod's: {}", String.join(", ",
                    cobblemon.stream().map(move -> move + (cobblemonAnimates(move) ? " (its own)" : " (its generic one)")).toList()));
        }
        MinecraftServer running = server;
        PlayerManager players = running == null ? null : running.getPlayerManager();
        if (players != null) {
            players.getPlayerList().forEach(MoveToggles::send);
        }
    }

    private static void send(ServerPlayerEntity player) {
        if (ServerPlayNetworking.canSend(player, MoveChoicesPayload.ID)) {
            ServerPlayNetworking.send(player, new MoveChoicesPayload(cobblemonMoves));
        }
    }

    /** Our action effects, found in our own jar so a new move needs no list kept up to date. */
    private static synchronized List<EffectFile> effectFiles() {
        if (effectFiles == null) {
            List<EffectFile> files = new ArrayList<>();
            Optional<Path> root = FabricLoader.getInstance().getModContainer(MOD_ID).flatMap(container -> container.findPath(DATA + EFFECTS));
            if (root.isPresent()) {
                try (Stream<Path> paths = Files.walk(root.get())) {
                    paths.filter(path -> path.getFileName().toString().endsWith(".json")).forEach(path -> {
                        StringJoiner relative = new StringJoiner("/", EFFECTS + "/", "");
                        root.get().relativize(path).forEach(part -> relative.add(part.toString()));
                        // Cobblemon keys an action effect by its file name alone
                        String name = path.getFileName().toString().replaceFirst("\\.json$", "");
                        String move = name.startsWith(CHARGE_PREFIX) ? name.substring(CHARGE_PREFIX.length()) : name;
                        files.add(new EffectFile(relative.toString(), Identifier.of("cobblemon", name), move));
                    });
                } catch (IOException e) {
                    LOGGER.warn("Couldn't list this mod's action effects", e);
                }
            }
            files.sort(Comparator.comparing(EffectFile::path));
            effectFiles = List.copyOf(files);
        }
        return effectFiles;
    }

    private static byte[] read(String modId, EffectFile file) throws IOException {
        Optional<Path> path = FabricLoader.getInstance().getModContainer(modId).flatMap(container -> container.findPath(DATA + file.path()));
        return path.isPresent() ? Files.readAllBytes(path.get()) : null;
    }

    private static List<byte[]> copies(ResourceManager manager, EffectFile file) throws IOException {
        List<byte[]> copies = new ArrayList<>();
        for (Resource resource : manager.getAllResources(Identifier.of("cobblemon", file.path()))) {
            try (InputStream in = resource.getInputStream()) {
                copies.add(in.readAllBytes());
            }
        }
        return copies;
    }

    private static ActionEffectTimeline parse(byte[] json, EffectFile file) {
        return ActionEffects.INSTANCE.parse(new BufferedReader(new InputStreamReader(new ByteArrayInputStream(json), StandardCharsets.UTF_8)), file.key());
    }

    private static void warnOnce(Throwable t) {
        if (!warned) {
            warned = true;
            LOGGER.warn("Couldn't switch move animations; moves play whichever animation loaded", t);
        }
    }

    /**
     * @param path path under data/cobblemon/, e.g. action_effects/moves/hydropump.json
     * @param key  the action effect's id in Cobblemon's map
     * @param move the move it belongs to
     */
    private record EffectFile(String path, Identifier key, String move) {
    }

    /** One effect's two versions; {@code cobblemon} is null when Cobblemon plays its generic animation. */
    private record Choice(String move, ActionEffectTimeline thisMod, ActionEffectTimeline cobblemon) {
    }

    /** Hands this class the data a reload reads, before Cobblemon's action effects are applied from it. */
    private static final class ResourceCapture implements IdentifiableResourceReloadListener {
        private static final Identifier ID = Identifier.of(MOD_ID, "move_toggles");

        @Override
        public Identifier getFabricId() {
            return ID;
        }

        @Override
        public CompletableFuture<Void> reload(ResourceReloader.Synchronizer synchronizer, ResourceManager manager, Profiler prepareProfiler,
                                              Profiler applyProfiler, Executor prepareExecutor, Executor applyExecutor) {
            resources = manager;
            return synchronizer.whenPrepared(Unit.INSTANCE).thenRun(() -> {
            });
        }
    }
}
