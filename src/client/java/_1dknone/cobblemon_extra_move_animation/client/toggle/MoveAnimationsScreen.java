package _1dknone.cobblemon_extra_move_animation.client.toggle;

import _1dknone.cobblemon_extra_move_animation.toggle.MoveConfig;
import _1dknone.cobblemon_extra_move_animation.toggle.MoveToggles;
import net.minecraft.client.MinecraftClient;
import net.minecraft.client.gui.screen.Screen;
import net.minecraft.client.gui.screen.option.GameOptionsScreen;
import net.minecraft.client.gui.tooltip.Tooltip;
import net.minecraft.client.gui.widget.CyclingButtonWidget;
import net.minecraft.client.gui.widget.DirectionalLayoutWidget;
import net.minecraft.client.gui.widget.TextWidget;
import net.minecraft.client.resource.language.I18n;
import net.minecraft.server.integrated.IntegratedServer;
import net.minecraft.text.Text;
import net.minecraft.util.Formatting;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * One switch per move this mod animates: this mod's animation, or Cobblemon's (its own where it has one,
 * otherwise its generic move animation). Moves are named by Cobblemon's own translations.
 *
 * <p>The server picks which animation plays. In singleplayer, or when hosting a LAN world, the switches
 * work and take effect when the screen closes. On someone else's server they only show the server's
 * choices; its owner sets them in the server's config file.
 */
public class MoveAnimationsScreen extends GameOptionsScreen {
    private static final String KEY = "cobblemon_extra_move_animation.options.";
    private static final Text THIS_MOD = Text.translatable(KEY + "this_mod");
    private static final Text COBBLEMON = Text.translatable(KEY + "cobblemon");
    private static final Tooltip THIS_MOD_TOOLTIP = Tooltip.of(Text.translatable(KEY + "this_mod.tooltip"));
    private static final Tooltip OWN_TOOLTIP = Tooltip.of(Text.translatable(KEY + "cobblemon.tooltip.own"));
    private static final Tooltip GENERIC_TOOLTIP = Tooltip.of(Text.translatable(KEY + "cobblemon.tooltip.generic"));
    private static final Text SERVER_NOTE = Text.translatable(KEY + "server").formatted(Formatting.GRAY);

    /** False on someone else's server, which decides for itself. */
    private final boolean editable;
    /** Move id to whether it plays this mod's animation. */
    private final Map<String, Boolean> choices = new HashMap<>();
    private boolean changed;

    public MoveAnimationsScreen(Screen parent) {
        super(parent, MinecraftClient.getInstance().options, Text.translatable(KEY + "title"));
        MinecraftClient client = MinecraftClient.getInstance();
        editable = client.world == null || client.getServer() != null;
        List<String> moves = MoveToggles.moves();
        if (editable) {
            MoveConfig.load(moves);
        }
        List<String> serverCobblemonMoves = MoveTogglesClient.serverCobblemonMoves();
        for (String move : moves) {
            choices.put(move, editable ? MoveConfig.usesThisMod(move) : !serverCobblemonMoves.contains(move));
        }
    }

    @Override
    protected void initHeader() {
        if (editable) {
            super.initHeader();
            return;
        }
        DirectionalLayoutWidget header = layout.addHeader(DirectionalLayoutWidget.vertical().spacing(4));
        header.getMainPositioner().alignHorizontalCenter();
        header.add(new TextWidget(title, textRenderer));
        header.add(new TextWidget(SERVER_NOTE, textRenderer));
    }

    @Override
    protected void addOptions() {
        List<String> moves = new ArrayList<>(choices.keySet());
        moves.sort(Comparator.comparing(move -> I18n.translate("cobblemon.move." + move)));
        for (String move : moves) {
            Tooltip cobblemonTooltip = MoveToggles.cobblemonAnimates(move) ? OWN_TOOLTIP : GENERIC_TOOLTIP;
            CyclingButtonWidget<Boolean> button = CyclingButtonWidget.onOffBuilder(THIS_MOD, COBBLEMON)
                    .initially(choices.get(move))
                    .tooltip(thisMod -> thisMod ? THIS_MOD_TOOLTIP : cobblemonTooltip)
                    .build(0, 0, 310, 20, Text.translatable("cobblemon.move." + move), (widget, thisMod) -> {
                        choices.put(move, thisMod);
                        changed = true;
                    });
            button.active = editable;
            body.addWidgetEntry(button, null);
        }
    }

    @Override
    public void removed() {
        super.removed();
        if (!editable) {
            return;
        }
        if (changed) {
            MoveConfig.save(choices);
        }
        // the switches also pick up edits made to the file by hand
        IntegratedServer server = client.getServer();
        if (server != null) {
            server.execute(MoveToggles::apply);
        }
    }
}
