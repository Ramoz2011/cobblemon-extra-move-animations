# Bitter Blade — Asset Notes & Integration Guide

Ceruledge's signature move (Showdown id `bitterblade`, Fire / Physical, 90 BP, 100 %, contact, slicing,
`drain: [1, 2]`: the user heals half the damage it deals). Ceruledge learns it at level 48 and is the only
natural learner, but the move has the `metronome` flag, so Metronome, Mirror Move, Copycat or Sketch can
put it in any Pokémon's hands. No Cobblemon version animates it (checked 1.7.3, 1.8.4 and `main`,
2026-11-14), so without this mod it plays the generic move animation.

Damage, the drain and the HP changes stay with the battle. The animation only reads what the battle
reported (`q.hurt`, `q.missed`) and never changes anything.

## Reference and palette

Scarlet/Violet (three clips: "#891 Bitter Blade", "Armarouge and Ceruledge signature moves", "Ceruledge
used Bitter Blade!"):

1. The blades glow hot pink. Blue-indigo ghost fire erupts from the ground and engulfs the body. The fire
   has dark smoky holes and pink and violet wisps on top.
2. Ceruledge spins in place with a pink blade sweeping through the flames. It ends in a wide stance with
   a blade out. It never dashes.
3. A pale cyan streak comes in diagonally to the target. A white starburst and a long white-cyan diagonal
   cut follow, then blue flame fragments scatter along the cut and fade to dark blue.
4. A mint-green orb forms on the target and flies back, leaving white and mint sparkles.
5. Pale rings close round the user, then a translucent green bubble with white radial sparkles appears as
   the HP bar rises.

The spec asked for violet and purple flames, a purple and reddish-orange impact, and purple, magenta and
red absorb particles. The user chose the **game-accurate palette** (2026-11-14). That means blue ghost
fire, hot-pink blades, a cyan-white cut and SV's mint-green drain, with no orange.

| Role | Colour |
|---|---|
| ghost fire | `#4A5CFF` cobalt → `#6F82FF` → `#A86BFF` violet → `#FF7FD8` pink tips, plus Cobblemon's blue `fire/wisp` sprite |
| blade glow | `#FF5FD2` hot pink, `#FFE3F6` white-pink core |
| slash ribbon | `#A86BFF` (hands) → `#FF3FC8` → `#FF5FD2` → `#FFE3F6` (points) |
| slash, cut | `#FFFFFF`, `#CFF4FF` ice, `#7FD8FF` cyan; shards cool `#8FA6FF` → `#4A5CFF` → `#2A2C9C` |
| drain, heal | `#F0FFF6` mint white, `#8EF0C0` mint; model tint (0.42, 1, 0.62) |

## Choreography (animation time, seconds)

| Time | Beat |
|---|---|
| 0.00–0.30 | Crouch and lean. Particles fired by an animation can't show before about 0.2 s (see below), so the first effects start then. |
| 0.20 | **Ignition.** A pink glow and white core run along both blades. Blue ghost flames lick up off the blades. |
| 0.22–0.72 | **Ghost fire.** Flames erupt from a ring at the feet and swirl up the body. There are dark indigo puffs inside, blue wisp tongues, and pink and lilac sparks rising. |
| 0.58–0.72 | **Wind-up.** Twists 28° back. The arms rise toward straight out, so the blades are level. |
| 0.72–1.02 | **Spin slash.** 388° of root yaw, eased. Arms are straight out and trail 16° behind the turn. The blades leave a hot-pink ribbon, with violet near the hands and white-pink at the points. Bright edge streaks run along the cutting edge, and ghost flames are flung off. |
| 0.94 (`RELEASE`, computed) | The right blade crosses the front. A white-cyan flash fires and a diagonal crescent slash leaves the blade. |
| 0.94–1.12 | The crescent (40 glows on a scimitar arc) flies to the target. Streaks and blue flames are shed along the way. |
| 1.02–1.22 | **Lunge.** Low, wide stance leaning forward, then a nod. |
| 1.12 (`IMPACT`) | **The cut.** White flash, cyan halo, impact star and a long diagonal white-cyan line. Blue flame shards, wisps and cyan sparks follow. The target reels. The HP bar drops. |
| 1.28–1.46 | **Drain.** A mint orb forms on the target while pink and violet sparks spiral into it. |
| 1.46–1.88 | The orb flies back on a curve that bows up and to the side, leaving sparkles. |
| 1.88 (`ARRIVE`) | Two mint rings close in. Mint light flares on the body, the model is tinted mint, and the user straightens. |
| 2.06 (`HEAL`) | **Heal.** A green bubble, white radial rays and twinkling stars, then rising motes. The timeline ends here, and the battle restores the HP and prints "had its energy drained" right after. |
| 2.52 | Everything is gone. |

## Engine facts this relies on (Cobblemon 1.7.3 source; same in 1.8.4)

- **The heal comes after the timeline.** `HealInstruction` is a plain `dispatchWaiting` with no effect of its
  own. The target's `DamageInstruction` waits for the move's action effect to finish (`future.isDone`)
  before the next dispatch. So the timeline is kept running until `HEAL + 0.04`. In testing, the HP bar
  started rising within 0.15 s of the bubble. On a knockout the damage dispatch doesn't wait, so the HP
  rises at the hit while the orb is still flying. The faint itself still plays after the heal bubble.
- **Blade positions are forward kinematics of Ceruledge's model.** Its geo has no locators (only the
  defaults root/target/special_attack/middle/top), so nothing can attach to a blade.
  - `bitterblade_gen.py` copies the arm chain (`RIG`), the blade quads and the battle idle's mean pose.
  - It replays Cobblemon's conventions: Bedrock→Java keeps x and z and flips y, rotations are copied
    verbatim, each part is translate·rotZYX·scale, animations add rotations and add positions with y
    negated, and the locator frame undoes the upside-down render (so a model point shows up at (−x, y, z)).
  - It samples the hand end and the point of both blades into linear curves, in model units, times
    `q.entity_scale / 16`.
  - `--check-rig` confirmed the rig is identical in 1.7.3, 1.8.2, 1.8.3 and 1.8.4.
- **Path-locked layers.** Every user particle is fired at `T0 = 0.02`, while root_part is at rest, so its frame
  faces the target. Each particle is shown only in its own time window. The spin is carried by the model.
  The ribbon is made of particles that light up where the blade was, because particles update only 20 times
  a second and the blade turns about 90° per tick at full speed.
- **Particle clock.** Animation-fired path-locked particles show about 0.175 s after their keyframe
  (`PARTICLE_LAG`, from Brave Bird). Action-effect particles are born about 0.075 s late (`EMIT_LAG`). The
  target animation fires its effects 0.075 s early (`FX_LEAD`).
- **One keyframe costs one server tick**, so everything starts in one `parallel`. The impact lives in the
  target's animation, on the client clock.
- **Species branch.** `q.entity.species.identifier == 'cobblemon:ceruledge'` picks `actor_ceruledge` or `actor`.
  This string compare was tested in Cobblemon's MoLang engine. A missing struct reads 0, so it never throws.
  Species-variant files such as `bitterblade_ceruledge.json` were avoided on purpose: the move toggle screen
  lists every action-effect file as its own move.
- **Streak orientation.** A `lookat_direction` streak points along its per-tick motion, and Cobblemon's
  `FromMotion` ignores speeds below 0.01 blocks/s. The cut line is spawned 0.003 blocks back along itself,
  so it is already oriented on its first frame. Without that it was invisible for a tick and was lost
  under the shards.
- **Close targets.** The slash starts at most 0.45 of the way to the target, with the release flash at the
  same point. A wild battle can leave the Pokémon under a block apart.

## Files

| File | What |
|---|---|
| `data/cobblemon/action_effects/moves/bitterblade.json` | timeline (generated) |
| `assets/cobblemon/bedrock/generic/animations/moves/bitterblade.animation.json` | `actor_ceruledge`, `actor` (any other species), `heal`, `target` (generated) |
| `assets/cobblemon/bedrock/particles/moves/bitterblade/*.particle.json` | 39 particle effects (generated) |
| `assets/cobblemon/sounds.json` | 11 `move.bitterblade.*` aliases of official oggs |
| `docs/tools/bitterblade_gen.py` | regenerates all of the above except sounds; `--check-rig` |

No new textures and no Java. It reuses Cobblemon's `fire/wisp`, `fire/cloudyfire_white`, `hit`,
`ring/giantring_white`, `skyding`, `smallbeam` and the `sparkle` sheets, plus this mod's `moves/bravebird_glow`.
The mint glow on the model is the existing `q.user.model_tint` hook (Counter). If that hook is missing, the
call returns 0 and everything else plays.

Nothing needs registering. Cobblemon finds the action effect by the move id, and the move switch in
Cobblemon's settings lists every action effect in the jar on its own (it picked up `bitterblade` with no
change).

## Customising

Edit `docs/tools/bitterblade_gen.py` and re-run it. Don't hand-edit the generated files. Then run
`python3 docs/tools/validate_move.py bitterblade`.

- **Timing:** the constants at the top. `IGNITE`, `WRAP0/WRAP1`, `WIND0`, `SPIN0/SPIN1`, `IMPACT`, `ORB0`,
  `FLY0/FLY1`, `HEAL` and `HEAL_END` drive the animations, particles and pauses together.
  - `RELEASE` is worked out from the rig (when the right blade's point crosses the front), so moving the
    spin moves it.
  - Keep `IGNITE` at 0.2 s or later.
  - The server pauses follow `IMPACT` (HP bar) and `HEAL` (end of the timeline), so the heal stays in sync.
- **Spin:** `SPIN_FROM`/`SPIN_TO` (yaw), `ARMS_OUT` (how level the blades are), `ARM_LAG` (trail behind the
  turn). Keep `SPIN_TO` a multiple of 360.
- **Particle intensity:** the first number passed to `locked(...)`, `wave_emitter(...)`, `heal_locked(...)` or
  `burst(...)` in each `p_*` function is that layer's particle count. The `0.6 * (1 - k * k)`-style alpha
  terms in the tints set how strong each layer is. The busiest layers are `p_wrap` (70), `p_wrapwisps` (66)
  and `p_spinarc` (170).
- **Slash size:**
  - the crescent radius is `0.62 * v.fxw` in `p_wave` (its arc span is `150` degrees);
  - the ribbon reaches the blade points on Ceruledge, and for other species its reach is `0.9 * v.fs` in `ring_point`;
  - the cut's length is `1.5 + 0.8 * size` in `p_cutline`, with widths `0.1`/`0.3`;
  - the glow sizes are the `(a + b * u)` terms in `p_spinarc`/`p_ringarc`.
- **Colours:** the palette constants and the `ramp(...)` stops in each particle.
- **Sounds:** the eleven `move.bitterblade.*` events alias official oggs (Will-O-Wisp, Lava Plume, Aerial
  Ace, Flamethrower, Confusion, Magical Leaf, the medicine sound, Protect). To use custom audio, drop
  `assets/cobblemon/sounds/move/bitterblade/<name>.ogg` and point the event's `name` at it.
- **Debug:** `BB_FORCE_MISS=1 python3 docs/tools/bitterblade_gen.py` builds an action effect where every use
  plays the miss version. Never ship it.

## Testing (2026-11-14, Cobblemon 1.7.3 dev client, headless rig)

- **Lv100 Ceruledge vs a wild Lv100 Magikarp:** Magikarp only has Normal-type moves, which can't touch a
  Ghost. Three hits were run:
  - one from a 3/4 camera behind Ceruledge;
  - one from the side that knocked it out;
  - one from the side with the HUD kept on. Ceruledge was poisoned down to 28/280, and the HP bar rose to 84
    as the bubble and rays played.
- **Incineroar taught the move** with `q.pokemon.teach_move('bitterblade', true)`. The generic `actor` played
  (flames up the body, a slash ring) against a Magikarp 0.85 blocks away. This exposed the close-target start
  point, which is now clamped.
- **Forced miss** (debug build) with Incineroar and with Ceruledge: the crescent veers past and keeps going,
  with no cut, flinch, orb or heal, and the turn ends early.
- No errors from the mod in the log. `validate_move.py`: 272 expressions parse, 0 problems.
- **Static checks against 1.8.4:**
  - the Ceruledge model and battle idle are identical;
  - every texture used is byte-identical;
  - every aliased ogg exists;
  - no particle id, sound event or file clashes;
  - `species.identifier` exists on the entity struct.

  It was not run in-game on 1.8.x.

Known limits:

- Particles depth-test against the model, so a thick flame column partly hides Ceruledge between 0.3 and 0.7 s, which is meant.
- On a knockout the HP rises at the hit rather than with the bubble, because the battle doesn't wait.
- The release flash for species other than Ceruledge sits at a fixed share of their size, not on a limb.
