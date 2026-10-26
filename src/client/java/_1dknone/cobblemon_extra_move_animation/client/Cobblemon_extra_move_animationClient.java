package _1dknone.cobblemon_extra_move_animation.client;

import _1dknone.cobblemon_extra_move_animation.client.beatup.BeatUpClient;
import _1dknone.cobblemon_extra_move_animation.client.tint.ModelTintClient;
import _1dknone.cobblemon_extra_move_animation.client.toggle.MoveTogglesClient;
import net.fabricmc.api.ClientModInitializer;

public class Cobblemon_extra_move_animationClient implements ClientModInitializer {

    @Override
    public void onInitializeClient() {
        BeatUpClient.register();
        ModelTintClient.register();
        MoveTogglesClient.register();
    }
}
