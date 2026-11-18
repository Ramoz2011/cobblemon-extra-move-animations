# Muddy Water — Asset Notes & Integration Guide

Muddy Water (Water, Special, 90 power, 85% accuracy, hits all adjacent foes, 30% chance to lower each
foe's accuracy by one stage). No Cobblemon version animates it (checked 1.7.3 to 1.8.4 and upstream
`main`, 2026-11-15), so nothing is replaced.

Everything is generated: `python3 docs/tools/muddywater_gen.py` writes the particles, the generic
animations, the action effect, the wave style and the `move.muddywater.*` sound entries;
`python3 docs/tools/muddywater_textures.py` writes the wave texture. Edit the constants at the top of the
generator rather than the outputs.

## Reference and palette

Scarlet/Violet's sequence (the "#330 Muddy Water Animation Comparison: Gen 3 to Gen 9" video):
1. The user rears up.
2. Muddy water bursts up round its feet as a crown.
3. The crown spreads into a wide wave that floods across the field over the foes.

Sword/Shield and Ultra Sun/Ultra Moon show the same flood as dark brown water with tan highlights and a
foam crest. The spec's colours (dark muddy brown, tan splashes) match the games, so no palette question
was needed.

| Use | Colour |
| --- | --- |
| Wave mesh: deep / body / light / foam | `#5C3F20` / `#8E6538` / `#C49A62` / `#F2E6CC` (lighter than the particles, because the mesh is shaded and its texture is grey) |
| Particles: deep / body / light | `#3E2914` / `#6B4A28` / `#A47C4A` |
| Particles: tan / foam / cream | `#C9A878` / `#E3D2AE` / `#F2E8D2` |
| Sediment specks | `#2E1E10` |
| Murky haze | `#6A5038` to `#9C8466` |

## Choreography (move time, seconds; one server tick starts it all, then it runs on the client clock)

| Time | User | Water (mesh) | Particles |
| --- | --- | --- | --- |
| 0.10–0.56 | rears back and strains | pool spreads under it from 0.18; crown rises to full height by 0.52, swirling | droplets swirl in, mud clots, bubbles, sediment |
| 0.60 | bows forward, drives the wave out | crown bursts outwards (0.16 s); wave forms in front, narrow | burst of spray, foam boiling at its feet |
| 0.60–1.05 | holds the push | wave rolls to the foes, fanning out to the full width of their line; the lip curls | spray, foam and mud clods ride the crest (one lane per foe) |
| 1.05 | settles by 1.45 | lip slams down on the foes, wave flattens into a flood that surges past them | per foe: splash crown, billows, droplets, bouncing clods, ripples, churning water |
| 1.35–1.95 | | flood drains, the user's end first | |
| 1.27–2.7 | | | haze, mud drips and motes round each foe whose accuracy fell |

Foe reactions:
- **Hit:** knocked back and shakes the mud off.
- **Missed:** hops aside.
- **Immune** (Water Absorb, Storm Drain) **or protected:** only the splash.

The battle drops the HP bars as the wave crashes (`remove_holds` at 1.0). Cobblemon's own stat-drop
arrows and the "accuracy fell" message come after the timeline, on top of the haze.

## How the pieces fit

- **Action effect** `data/cobblemon/action_effects/moves/muddywater.json`: one `parallel` keyframe
  starts every animation, the crest particles and both Java hooks in the same tick.
- **Wave mesh** (Java, client): `q.user.wave_effect('muddywater', q.target, q.targets)` sends the user and
  foes to nearby clients.
  - `client/wave/WaveSequence` rebuilds three sheets every frame from where the Pokémon stand: the pool,
    the crown and the wave/flood.
  - It uses only their positions and hitboxes, never bones, so it fits any model.
  - A short downward raycast puts the water on the ground (or water surface) under hovering Pokémon.
  - It is drawn with `RenderLayer.getEntityTranslucent` after entities. Minecraft sorts translucent
    quads, so the curl blends correctly over itself.
  - Its texture scrolls, and its colours swirl with value noise.
- **Wave style** `assets/cobblemon_extra_move_animation/wave_effects/muddywater.json` holds all the mesh's
  numbers. The generator writes it from the same timing constants as the action effect.
- **Accuracy haze only when it really happened:** `q.entity.move_stat_change('accuracy') < 0` per foe.
  - `battle/MoveStatChange` reads the battle's own log: the `-unboost` lines after this move's `|move|`
    line.
  - It skips stat changes an ability or item made.
  - `battle/CurrentMove` knows which move is being animated: it wraps Cobblemon's `move` log parser
    (calling the original, so battles are unchanged) and uses `ShowdownInterpreter.lastCauser`.
- **Foes a spread move missed:** Showdown lists only the foes it hit after `[spread]`, and Cobblemon gives
  the action effect only those.
  - `q.user.play_on_missed_spread_targets('muddywater', 'splash', 'dodge')` (`battle/MissedTargets`)
    plays the splash and dodge on the missed ones with Cobblemon's own `RunPosableMoLangPacket`.
  - The wave also spans them.
  - Misses Cobblemon does pass in (a single battle) stay in the JSON.
- If any Java hook is missing, its MoLang call returns 0: the move keeps its particles and animations,
  and the haze never shows by mistake.

## Files

- `docs/tools/muddywater_gen.py`, `docs/tools/muddywater_textures.py`
- `src/main/resources/assets/cobblemon/bedrock/particles/moves/muddywater/` (18 particles):
  - gather: `gather`, `gathermud`, `bubbles`, `sediment`, `burst`, `burstfoam`;
  - crest: `crestspray`, `crestfoam`, `crestclods`;
  - crash: `splash`, `splashmass`, `droplets`, `clods`, `ripple`, `churn`;
  - haze: `murk`, `drips`, `motes`.
- `src/main/resources/assets/cobblemon/bedrock/generic/animations/moves/muddywater.animation.json`:
  `actor`, `splash`, `target`, `dodge`, `murk`.
- `src/main/resources/data/cobblemon/action_effects/moves/muddywater.json`
- `src/main/resources/assets/cobblemon_extra_move_animation/wave_effects/muddywater.json`
- `src/main/resources/assets/cobblemon_extra_move_animation/textures/effect/muddy_water.png` (32x32 greyscale, tileable)
- `src/main/resources/assets/cobblemon/sounds.json`: `move.muddywater.*` entries, all aliases of
  Cobblemon's own sound files:
  - `gather` = Mud Sport;
  - `surge` = big fishing splash;
  - `rush` = Water Gun;
  - `crash` = Mud Bomb hit;
  - `splash` = big fishing splash;
  - `murk` = Sand Attack hit.
- Java, under `src/main/java/_1dknone/cobblemon_extra_move_animation/`:
  - `battle/CurrentMove.java`, `battle/MoveStatChange.java`, `battle/MissedTargets.java`;
  - `wave/WavePayload.java`, `wave/WaveEffect.java`;
  - all registered in `Cobblemon_extra_move_animation.java`.
- Java, client, under `src/client/java/_1dknone/cobblemon_extra_move_animation/client/wave/`:
  - `WaveClient.java`, `WaveStyle.java`, `WaveSequence.java`, `WaveGrid.java`;
  - registered in `Cobblemon_extra_move_animationClient.java`.

The move appears in the "This mod / Cobblemon" settings screen by itself.

## Customising

All of these are constants at the top of `muddywater_gen.py`. Re-run it. In the dev client, copy into
`build/resources/main` (`rsync -a --exclude fabric.mod.json src/main/resources/ build/resources/main/`),
then press F3+T (mesh, particles, sounds) and run `/reload` (action effect).

- **Wave size:**
  - `WAVE_HEIGHT` (`scale` × the user's height + `add`, clamped to `min`..`max`);
  - `MIN_HALF_WIDTH` and `SIDE_PADDING` (how far it reaches past the outermost foe);
  - `LIP` (how far the curl reaches);
  - `OVERSHOOT` (how far the flood surges past);
  - `CROWN_HEIGHT`, `POOL_RADIUS`.
- **Timing:**
  - `CROWN_RISE`, `CROWN_PEAK`, `RELEASE`, `IMPACT`, `CRASH_END`, `DRAIN_END`, `MURK0`, `MURK_LEN`, `TAIL`;
  - the mesh, the crest spray and the foes' reactions all follow them.
- **Water movement and look:**
  - `FLOW_SPEED` (how fast the surface runs over the crest);
  - `CROWN_SWIRL` (degrees per second);
  - `CREST_NOISE`, `BOW`, `END_TAPER`, `MOTTLE`;
  - `FOAM_BACK` and `FOAM_FACE` (where the foam is);
  - `MESH_COLOR` and the style's `alpha` block;
  - `LIGHTING_UP_BIAS` (how much the shading is softened).
- **Particle intensity:**
  - each particle function's count (the number passed to `locked(...)`, `lane_emitter(...)`, `burst(...)`
    or `murk_emitter(...)`);
  - its size expression.

Debugging:
- `MW_FORCE_MURK=1 python3 docs/tools/muddywater_gen.py` builds a test version where every foe that
  wasn't missed gets the haze. It prints a warning; never ship it.
- Start the game with `-Dcobblemon_extra_move_animation.debug=true` to log every `move_stat_change`
  answer and every missed-foe animation.

## Testing (2026-11-15, Cobblemon 1.7.3 dev client, headless rig)

**Singles:**
- Swampert vs Magikarp: back view and side view.
- A wild Quagsire (Muddy Water only) vs Swampert: front view, wave rolling at the camera.

**Doubles** against a test NPC's two Magikarp (`q.npc.start_battle('Player106', 'doubles')`):
- Swampert, Incineroar (taught it) and Pelipper as casters.
- The wave spans both foes, fans out from the caster without sweeping through its partner, and crashes
  on both.

**Accuracy:**

| Battle log | `move_stat_change` | Haze |
| --- | --- | --- |
| "Magikarp's accuracy fell" | -1 | on that foe only |
| "Swampert's Accuracy fell" | -1 | on Swampert |
| no drop (several uses) | 0 | none |
| doubles, one foe's accuracy fell | -1 for that foe, 0 for the other | on that foe only |

**Misses:**
- A single-battle miss plays the dodge (from the JSON).
- A doubles partial miss ("But it missed." on one foe) plays the splash and dodge on the missed foe
  through `play_on_missed_spread_targets`, and the wave spans it.

**Other cases:**
- Immune (Quagsire's Water Absorb): splash only, no knockback.
- Critical hits and knockouts: no change to the animation.
- No warnings or errors from the mod in any session log. The mesh and particles are gone by about 2.7 s;
  nothing is left in the world.

**Not tested:**
- In-game on 1.8.x. Static checks only: every Cobblemon class, method and packet used has the same
  signature in 1.7.3 and 1.8.4, and 1.8.4 has no `muddywater` action effect.
- Shader packs.
- A real hovering caster (Pelipper stood on the ground in this battle).
- Sounds: the test rig records no audio.
