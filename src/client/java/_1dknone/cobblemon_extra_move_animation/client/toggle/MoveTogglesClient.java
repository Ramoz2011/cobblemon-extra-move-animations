package _1dknone.cobblemon_extra_move_animation.client.toggle;

import _1dknone.cobblemon_extra_move_animation.toggle.MoveChoicesPayload;
import net.minecraft.client.Minecraft;
import net.minecraft.client.gui.components.AbstractWidget;
import net.minecraft.client.gui.components.Button;
import net.minecraft.client.gui.screens.Screen;
import net.minecraft.network.chat.CommonComponents;
import net.minecraft.network.chat.Component;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.util.List;

/**
 * Client half of the per-move animation choice: a button in Cobblemon's own settings screen that opens
 * {@link MoveAnimationsScreen}, and the server's choices, which that screen shows when playing on a server.
 *
 * <p>Cobblemon's settings screen has no hook for add-ons, so the button is added after the screen sets
 * itself up. The screen is recognised by name: if a future Cobblemon renames or rebuilds it, the button
 * just doesn't appear.
 */
public final class MoveTogglesClient {
    private static final Logger LOGGER = LoggerFactory.getLogger("cobblemon_extra_move_animation");
    private static final String COBBLEMON_SETTINGS = "com.cobblemon.mod.common.client.gui.config.CobblemonConfigScreen";
    private static final Component BUTTON = Component.translatable("cobblemon_extra_move_animation.options.button");

    private static volatile List<String> serverCobblemonMoves = List.of();
    private static boolean warned;

    private MoveTogglesClient() {
    }

    /** The server sent its choices. */
    public static void receive(MoveChoicesPayload payload) {
        serverCobblemonMoves = List.copyOf(payload.cobblemonMoves());
    }

    /** Forgets the server's choices when the player leaves it. */
    public static void clear() {
        serverCobblemonMoves = List.of();
    }

    /** Run after any screen sets itself up; adds our button when it is Cobblemon's settings. */
    public static void screenInitialized(Minecraft client, Screen screen, int width, Buttons buttons) {
        if (screen.getClass().getName().equals(COBBLEMON_SETTINGS)) {
            addButton(client, screen, width, buttons);
        }
    }

    /** The moves the server plays Cobblemon's animation for, as it last said. */
    static List<String> serverCobblemonMoves() {
        return serverCobblemonMoves;
    }

    /** Puts our button beside Done in the screen's footer, the way vanilla pairs two footer buttons. */
    private static void addButton(Minecraft client, Screen screen, int width, Buttons buttons) {
        try {
            AbstractWidget done = buttons.list().stream()
                    .filter(button -> button instanceof Button && CommonComponents.GUI_DONE.equals(button.getMessage()))
                    .findFirst().orElse(null);
            if (done == null) {
                return;
            }
            done.setWidth(150);
            done.setX(width / 2 + 4);
            buttons.add(Button.builder(BUTTON, button -> client.setScreen(new MoveAnimationsScreen(screen)))
                    .bounds(width / 2 - 154, done.getY(), 150, done.getHeight())
                    .build());
        } catch (Throwable t) {
            if (!warned) {
                warned = true;
                LOGGER.warn("Couldn't add the move animation button to Cobblemon's settings", t);
            }
        }
    }

    /** A screen's buttons, as the mod loader hands them out. */
    public interface Buttons {
        List<AbstractWidget> list();

        void add(AbstractWidget button);
    }
}
