package _1dknone.cobblemon_extra_move_animation.client.toggle;

import _1dknone.cobblemon_extra_move_animation.toggle.MoveChoicesPayload;
import net.fabricmc.fabric.api.client.networking.v1.ClientPlayConnectionEvents;
import net.fabricmc.fabric.api.client.networking.v1.ClientPlayNetworking;
import net.fabricmc.fabric.api.client.screen.v1.ScreenEvents;
import net.fabricmc.fabric.api.client.screen.v1.Screens;
import net.minecraft.client.MinecraftClient;
import net.minecraft.client.gui.screen.Screen;
import net.minecraft.client.gui.widget.ButtonWidget;
import net.minecraft.client.gui.widget.ClickableWidget;
import net.minecraft.screen.ScreenTexts;
import net.minecraft.text.Text;
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
    private static final Text BUTTON = Text.translatable("cobblemon_extra_move_animation.options.button");

    private static volatile List<String> serverCobblemonMoves = List.of();
    private static boolean warned;

    private MoveTogglesClient() {
    }

    public static void register() {
        ClientPlayNetworking.registerGlobalReceiver(MoveChoicesPayload.ID, (payload, context) -> serverCobblemonMoves = List.copyOf(payload.cobblemonMoves()));
        ClientPlayConnectionEvents.DISCONNECT.register((handler, client) -> serverCobblemonMoves = List.of());
        ScreenEvents.AFTER_INIT.register((client, screen, width, height) -> {
            if (screen.getClass().getName().equals(COBBLEMON_SETTINGS)) {
                addButton(client, screen, width);
            }
        });
    }

    /** The moves the server plays Cobblemon's animation for, as it last said. */
    static List<String> serverCobblemonMoves() {
        return serverCobblemonMoves;
    }

    /** Puts our button beside Done in the screen's footer, the way vanilla pairs two footer buttons. */
    private static void addButton(MinecraftClient client, Screen screen, int width) {
        try {
            List<ClickableWidget> buttons = Screens.getButtons(screen);
            ClickableWidget done = buttons.stream()
                    .filter(button -> button instanceof ButtonWidget && ScreenTexts.DONE.equals(button.getMessage()))
                    .findFirst().orElse(null);
            if (done == null) {
                return;
            }
            done.setWidth(150);
            done.setX(width / 2 + 4);
            buttons.add(ButtonWidget.builder(BUTTON, button -> client.setScreen(new MoveAnimationsScreen(screen)))
                    .dimensions(width / 2 - 154, done.getY(), 150, done.getHeight())
                    .build());
        } catch (Throwable t) {
            if (!warned) {
                warned = true;
                LOGGER.warn("Couldn't add the move animation button to Cobblemon's settings", t);
            }
        }
    }
}
