# Darkest Lariat — Asset Notes & Integration Guide

Incineroar's signature Dark move (Showdown id `darkestlariat`, Dark / Physical,
85 BP, 100 %, contact, `ignoreDefensive` + `ignoreEvasion`). Learned in Cobblemon
1.7.3 by 20 species; 15 of them have models (Incineroar at level 1, plus Bewear,
Dusknoir, Electivire, Golurk, Grimmsnarl, Krookodile, Machamp, Mew, Poliwrath,
Regigigas, Rillaboom, Snorlax, Swampert, Zarude by TM). Not animated upstream in
1.7.3, 1.8.0, 1.8.1 or `main` (checked 2026-10-03).

The stat-ignoring effect is damage logic only. Nothing here touches the target's
stats or shows a stat-change visual.

## Reference and palette

The official animation (Bulbapedia's Gen VII / VIII stills, viewed 2026-10-03):

- **Sun/Moon:** the scene goes dark red, the user holds a T-pose with both arms
  straight out and spins, with crimson circles under each fist and radial red
  speed lines. The hit is a red-orange burst with jagged dark shards.
- **Sword/Shield:** black background, the user is a spinning blur with a glowing
  **crimson orb ringed in gold** at each fist and X-shaped flares; the hit is a
  red burst with red-outlined dark fragments.
- Anime (Grimmsnarl): hands covered in energy, spins rapidly with arms held out,
  slams into the opponent. Rumble Rush classes it as a 3-hit *dash*.

The original spec asked for dark purple / violet. The games use **black and
crimson** with gold accents and no purple anywhere, so the user picked the
game-accurate palette (2026-10-03). The spec's "no fire, no smoke" still holds:
only crisp rings, streaks, orbs and shards, never flame or smoke textures.

| Role | Colour |
|---|---|
| aura body | `#1A0A0E` near-black wine |
| aura rim / deep trail | `#7A0F1E` |
| crimson | `#E01E2E` |
| hot core | `#FFD9D0` / `#FFF1EC` |
| gold ring rims, sparks | `#FFC23A` / `#FFF2C2` |
| impact crimson | `#D81B2C` |

## Choreography (animation time, seconds)

| Time | Beat |
|---|---|
| 0.00–0.20 | **Anticipation.** Crouch, brace forward 7°, wind up the torso 40° the wrong way. Dark motes rush inward (`gather`). Arms start to cock. Low ominous heave (`charge`). |
| 0.20–0.34 | **Aura.** Release the wind-up and rise; both arms fling out past horizontal. Black aura wisps (`aura`) and crimson streaks (`auraglint`) spiral up around the body. |
| 0.34–0.50 | **Lariat stance.** T-pose held facing the target (spin angle locked at 0). At 0.37 each fist ignites: a volumetric crimson orb (`fistorb`), a spinning gold hoop (`fisthoop`) and an X flare (`fiststar`), plus a crimson circle on the floor (`stancering`). This is the SM/SwSh still. |
| 0.50–0.80 | **Spinning lariat.** 1.75 turns at a constant 2100°/s while dashing straight into the target. Crimson motion arcs and a black umbra trail the fists (`swoosh`, `swooshdark`); dark speed lines stream back (`dashlines`); two whooshes. |
| 0.80–0.90 | **Impact + hit-stop.** The spin freezes with one arm pointing straight at the target. Both fists flare bigger (same beat effects, `v.flare = 1`). On the target, all on the same frame: white-hot flash, crimson shockwave ring, ground ring, black radial lines, gold-crimson sparks, black-and-red shards, official `impact_dark` + `impact.dark`, a heavy thud and a knockback shove. The battle hold is released here so the HP bar drops with the hit. |
| 0.90–1.26 | **Follow-through.** The spin carries on and decelerates to exactly 3 turns. Softer arcs. |
| 1.00–1.32 | **Recovery.** Hop back to the starting spot (light whoosh, official `quickattack_dust` on landing), arms relax, the aura fades. |
| 1.45 | Animation ends. Total timeline 1.70 s. |

## Engine facts this relies on (verified in Cobblemon 1.7.3 source)

- **Arms on any model.** `BedrockAnimation.run` looks bones up by name and skips
  ones a model doesn't have, and adds rotations on top of the current pose. The
  generic animation drives `arm_left`/`arm_right` (13 learners),
  `arm_left1`/`arm_right1` (Incineroar, Poliwrath), `arm_*2` (forearms) and
  `shoulder_*1` (Incineroar only; no other Cobblemon model has that name).
- **The deltas are fitted, not guessed.** Cobblemon models are authored in a
  T-pose and the battle idle lowers the arms. A forward-kinematics solver
  reproducing Cobblemon's conventions (Bedrock→Java flips Y only; rotation
  angles copied verbatim; ModelPart order ZYX; animations add Euler angles) fitted
  one mirrored delta set over the battle idle of all 15 rigs, then a separate
  fit for Incineroar's asymmetric shoulders. Result at mid-idle: arms 0.7–1.0
  "outward", within about ±25° of horizontal, for nearly every learner.
- **Why not a primary animation for a perfect T-pose.** A primary fades out the
  idle, which would make hidden bones appear: Snorlax's `coolhat`, nine of
  Dusknoir's light overlays, Golurk's hand and waist fires. So everything here is
  a stateful (additive) animation, like every official generic move.
- **Locators inherit the spin.** `updateLocators` runs after all animations, so
  emitters on `root` turn with the body. The arcs use that, and the fist beats
  are fired from the animation while the spin angle is frozen (0.34–0.50 hold,
  0.80–0.90 hit-stop), so their captured frame has the arms on its local x axis.
- **Particles only update at 20 Hz.** `SnowstormParticle.originPos` and local
  rotation are sampled per tick, so nothing can glue itself to a fist spinning at
  ~105° per tick. The spin is carried by the model; the arcs are *left-behind*
  world-space particles that fill the angle swept since the previous tick.
- **Every keyframe costs a server tick.** In 1.7.3 the keyframes' `delayedFuture(seconds)`
  always schedules through `afterOnServer`, even for a zero delay, so each `entity_*` /
  `animation` / `molang` keyframe takes one tick; only skipped (false-condition) ones are
  free. All start keyframes therefore fire inside one `parallel` (a single tick).
- **The impact runs on the client clock.** Server pauses are counted in server ticks, and on
  a loaded integrated server those burst and stall: in testing, a server-timed impact landed
  0.17 s late with a plain keyframe list and 0.3 s *early* with `parallel` + `pause`, while the
  client animation kept real time. So the whole impact lives in `animation.darkestlariat.target`
  instead: that animation is started in the same tick as the actor's, holds still until 0.80,
  then fires every impact particle, both impact sounds and the knockback. Both animations
  run on the same client clock, so the impact is locked to the dash arrival. The server
  timeline only keeps gameplay pacing: `pause 0.75` → `remove_holds` (HP bar), and the
  species `recoil` keyframe was dropped as the generic knockback covers every species.
  Verified in-game on 2026-10-03: the white-hot flash appears on the same frames as the hit-stop.
- **Reaching the target.** `move_to_target` is real pathfinding at walking speed
  (4 s timeout), so it's useless here. Instead a `molang` keyframe computes the
  gap server-side (`q.user`/`q.target` are entity structs with `x/y/z`, `width`,
  `height`, `species.base_scale` and `distance_to_pos`) and 16 conditional
  `entity_molang` keyframes pick one of 15 dash lengths (16-unit steps up to 240)
  or a fallback. Tested in the real bundled MoLang engine: with no target entity
  `q.target.width` reads 0 (no exception), the expression yields −1 and the
  fallback dash plays.

## Files

| File | What |
|---|---|
| `data/cobblemon/action_effects/moves/darkestlariat.json` | timeline (generated) |
| `assets/cobblemon/bedrock/generic/animations/moves/darkestlariat.animation.json` | `actor`, `target` (carries the whole impact), `dash_1`…`dash_15` (generated) |
| `assets/cobblemon/bedrock/particles/moves/darkestlariat/*.particle.json` | 16 particle effects (hand-written) |
| `assets/cobblemon/textures/particle/moves/darkestlariat_shard.png` | 48×16, 3 jagged black shards with crimson rims (generated) |
| `assets/cobblemon/sounds.json` | `move.darkestlariat.{charge,spin,spin2,return,target}` aliases |
| `docs/tools/darkestlariat_gen.py` | regenerates the animation file and action effect |
| `docs/tools/darkestlariat_shard_texture.py` | regenerates the shard texture |

Reused official assets: `impact_dark` particle, `quickattack_dust` particle,
`impact.dark` sound, textures `aura_white`, `orb/largefadeorb`,
`orb/smallfadeorb`, `sparkle/bigsparkle`, `ring/largering2`,
`ring/giantring_white`, `dashburst`, `quickattack_dashlines`.

## Customising

Edit `docs/tools/darkestlariat_gen.py` and re-run it; don't hand-edit the two
generated files.

- **Timing:** `SPIN_START`, `IMPACT`, `HITSTOP_END`, `RETURN_*`. `IMPACT` also moves the
  target animation's impact beat automatically. If you move `IMPACT`, also move the swoosh windows (`emitter_age` 0.5–0.81 and 0.9–1.14 in
  `swoosh`/`swooshdark`), and keep the 0.37 and `IMPACT` fist beats inside a
  frozen-spin window.
- **Spin:** `SPIN_IMPACT` must stay at 90° mod 180° (an arm points at the target
  on the hit) and `SPIN_END` at a multiple of 360°. The arcs' per-tick fill
  angle (118°, 88°) is ω/20 plus ~10 %, so recompute it if the spin speed changes.
- **Arms:** `ARM_DELTAS` / `ARM_CURVE`. Re-fit if Cobblemon reworks a learner's
  idle.
- **Reach:** `REACH_FACTOR` (0.53) is where the user stops, in multiples of
  `max(width, height)`. Fist reach in the particles is `1.4 * v.entity_radius`
  at height `0.62 * v.entity_height`.
- **Colours:** the tint gradients in the particle files (palette above).
- **Sounds:** the five `move.darkestlariat.*` events alias official oggs. To use
  custom audio, drop `assets/cobblemon/sounds/move/darkestlariat/darkestlariat_<part>.ogg`
  and point the `name` fields at `cobblemon:move/darkestlariat/darkestlariat_<part>`.

## Testing

Tested in the dev client on 2026-10-03 against a Lv 100 Snorlax at two distances
(6.4 and 8.1 blocks, picking `dash_5` and `dash_7`). The first run exposed a white blowout
on the fist-ignite beat, an over-large impact flash and the timing drift above; all three
were fixed and re-checked in-game. Headless test rig, for repeat runs without touching the
desktop: `gamescope --backend headless -W 960 -H 540 -w 960 -h 540 -- bash -c 'unset
WAYLAND_DISPLAY; ./gradlew runClient --offline --args="--username Player106"'`, then drive it
with `xdotool` on gamescope's Xwayland display and record with `ffmpeg -f x11grab -window_id`.
Cobblemon's battle menu needs real mouse clicks (no keyboard support).
