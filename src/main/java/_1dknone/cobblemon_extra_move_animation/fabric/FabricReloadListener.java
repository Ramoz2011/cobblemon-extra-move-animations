package _1dknone.cobblemon_extra_move_animation.fabric;

import net.fabricmc.fabric.api.resource.IdentifiableResourceReloadListener;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.server.packs.resources.PreparableReloadListener;
import net.minecraft.server.packs.resources.ResourceManager;
import net.minecraft.util.profiling.ProfilerFiller;

import java.util.concurrent.CompletableFuture;
import java.util.concurrent.Executor;

/** Gives one of the mod's shared reload listeners the id Fabric's resource API asks for. */
public record FabricReloadListener(ResourceLocation id, PreparableReloadListener listener) implements IdentifiableResourceReloadListener {

    @Override
    public ResourceLocation getFabricId() {
        return id;
    }

    @Override
    public CompletableFuture<Void> reload(PreparationBarrier barrier, ResourceManager manager, ProfilerFiller prepareProfiler,
                                          ProfilerFiller applyProfiler, Executor prepareExecutor, Executor applyExecutor) {
        return listener.reload(barrier, manager, prepareProfiler, applyProfiler, prepareExecutor, applyExecutor);
    }

    @Override
    public String getName() {
        return id.toString();
    }
}
