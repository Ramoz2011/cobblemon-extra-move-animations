package _1dknone.cobblemon_extra_move_animation;

import _1dknone.cobblemon_extra_move_animation.beatup.BeatUpAfterimages;
import _1dknone.cobblemon_extra_move_animation.tint.ModelTint;
import _1dknone.cobblemon_extra_move_animation.toggle.MoveToggles;
import net.fabricmc.api.ModInitializer;

public class Cobblemon_extra_move_animation implements ModInitializer {

    @Override
    public void onInitialize() {
        BeatUpAfterimages.register();
        ModelTint.register();
        MoveToggles.register();
    }
}
