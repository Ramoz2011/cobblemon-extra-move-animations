package _1dknone.cobblemon_extra_move_animation.client.toggle;

import _1dknone.cobblemon_extra_move_animation.toggle.MoveConfig;
import _1dknone.cobblemon_extra_move_animation.toggle.MoveToggles;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import net.minecraft.ChatFormatting;
import net.minecraft.client.Minecraft;
import net.minecraft.client.gui.components.CycleButton;
import net.minecraft.client.gui.components.StringWidget;
import net.minecraft.client.gui.components.Tooltip;
import net.minecraft.client.gui.layouts.LinearLayout;
import net.minecraft.client.gui.screens.Screen;
import net.minecraft.client.gui.screens.options.OptionsSubScreen;
import net.minecraft.client.resources.language.I18n;
import net.minecraft.client.server.IntegratedServer;
import net.minecraft.network.chat.Component;

/**
 * One switch per move this mod animates: this mod's animation, or Cobblemon's (its own where it has one,
 * otherwise its generic move animation). Moves are named by Cobblemon's own translations.
 *
 * <p>The server picks which animation plays. In singleplayer, or when hosting a LAN world, the switches
 * work and take effect when the screen closes. On someone else's server they only show the server's
 * choices; its owner sets them in the server's config file.
 */
public class MoveAnimationsScreen extends OptionsSubScreen {
    private static final String KEY = "cobblemon_extra_move_animation.options.";
    private static final Component THIS_MOD = Component.translatable(KEY + "this_mod");
    private static final Component COBBLEMON = Component.translatable(KEY + "cobblemon");
    private static final Tooltip THIS_MOD_TOOLTIP = Tooltip.create(Component.translatable(KEY + "this_mod.tooltip"));
    private static final Tooltip OWN_TOOLTIP = Tooltip.create(Component.translatable(KEY + "cobblemon.tooltip.own"));
    private static final Tooltip GENERIC_TOOLTIP = Tooltip.create(Component.translatable(KEY + "cobblemon.tooltip.generic"));
    private static final Component SERVER_NOTE = Component.translatable(KEY + "server").withStyle(ChatFormatting.GRAY);

    /** False on someone else's server, which decides for itself. */
    private final boolean editable;
    /** Move id to whether it plays this mod's animation. */
    private final Map<String, Boolean> choices = new HashMap<>();
    private boolean changed;

    public MoveAnimationsScreen(Screen parent) {
        super(parent, Minecraft.getInstance().options, Component.translatable(KEY + "title"));
        Minecraft client = Minecraft.getInstance();
        editable = client.level == null || client.getSingleplayerServer() != null;
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
    protected void addTitle() {
        if (editable) {
            super.addTitle();
            return;
        }
        LinearLayout header = layout.addToHeader(LinearLayout.vertical().spacing(4));
        header.defaultCellSetting().alignHorizontallyCenter();
        header.addChild(new StringWidget(title, font));
        header.addChild(new StringWidget(SERVER_NOTE, font));
    }

    @Override
    protected void addOptions() {
        List<String> moves = new ArrayList<>(choices.keySet());
        moves.sort(Comparator.comparing(move -> I18n.get("cobblemon.move." + move)));
        for (String move : moves) {
            Tooltip cobblemonTooltip = MoveToggles.cobblemonAnimates(move) ? OWN_TOOLTIP : GENERIC_TOOLTIP;
            CycleButton<Boolean> button = CycleButton.booleanBuilder(THIS_MOD, COBBLEMON)
                    .withInitialValue(choices.get(move))
                    .withTooltip(thisMod -> thisMod ? THIS_MOD_TOOLTIP : cobblemonTooltip)
                    .create(0, 0, 310, 20, Component.translatable("cobblemon.move." + move), (widget, thisMod) -> {
                        choices.put(move, thisMod);
                        changed = true;
                    });
            button.active = editable;
            list.addSmall(button, null);
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
        IntegratedServer server = minecraft.getSingleplayerServer();
        if (server != null) {
            server.execute(MoveToggles::apply);
        }
    }
}
