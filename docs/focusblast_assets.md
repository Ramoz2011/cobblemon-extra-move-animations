# Focus Blast — Asset Notes & Integration Guide

Fighting / Special, 120 BP, 70 % accuracy, priority 0, no contact, single target, 10 % chance to
lower the target's Sp. Def by one stage (Showdown id `focusblast`; flags `protect`, `mirror`,
`metronome`, `bullet`). Checked against the Showdown data bundled in Cobblemon 1.7.3. Nothing here
touches the move's mechanics: only the animation is added. Learned by 225 species in Cobblemon
1.7.3 (172 implemented, 170 of them with models), mostly by TM. Not animated upstream in 1.7.3,
1.8.0, 1.8.1 or `main` (checked 2026-10-04). Aura Sphere isn't either.

## Reference and palette

What the official games and anime show (Bulbapedia stills, viewed 2026-10-04):

- **Sword/Shield:** a gigantic orb held **overhead** (Croagunk), with a pale-yellow white-hot core,
  a white body, a cyan fringe and spiky irregular rays, against a darkened blue scene.
- **Scarlet/Violet:** a white-hot orb with a deep violet-blue halo. The impact is a radial starburst of
  white and cyan streaks inside a spherical shell.
- **X/Y:** a white orb with a violet glow above a raised hand. The impact is a white burst with radial
  white streaks and a dark-blue circular shockwave ring, on a blue background.
- **Sun/Moon:** yellow-white orb with gold speed lines (the odd one out).
- **Anime:** overwhelmingly a **light-blue orb formed between the hands**, often raised above the head
  where it grows as big as the user, then hurled (Scrafty, Lopunny, Beartic, Thundurus, Ursaring...).

So the requested blue / cyan / white palette with subtle violet-blue is also the game-accurate one.
The design takes SwSh's overhead orb and spiky rays, the anime's cyan swirl, and XY's
streak-and-ring impact.

| Role | Colour |
|---|---|
| core | `#FFFFFF` / `#E6FBFF` |
| glow | cyan, alpha ~0.42 (`0.55, 0.92, 1`) |
| halo | violet-blue, alpha ~0.17 (`0.53, 0.58, 1`) |
| motes, rays | `#FFFFFF` → `#C8F6FF` → `#A0D2FF` |
| accents | `#8CEBFF` cyan, `#8C8CFF` violet-blue |

No fire, smoke or dark textures anywhere. The stock `cobblemon:impact_fighting` particle is left out
because its shards are tinted red; the official `impact.fighting` sound is kept.

## Choreography (client clock, seconds)

Times are on the orb's particle clock, which is drawn about 0.1 s behind the model animations (see
"Engine facts"). The target's reaction is keyed at 1.45 on the model clock so that, on screen, it lands
on the same frame as the orb's 1.35 arrival.

| Time | Beat |
|---|---|
| 0.00–0.25 | **Focus.** Crouch, lean in, squash; hands drawn in front of the chest. Radial lines converge on the body (the dash-burst played backwards), then a white twinkle "ding" on the head. Low psychic hum. |
| 0.10–0.60 | **Gather.** Cyan motes spiral in and accelerate into the hold point; streaks rush straight in. Cyan light streaks and motes rise around the body. The body rises and leans back; arms lift toward the orb. A small side-to-side shiver from 0.25 to 0.85 shows the strain. |
| 0.35–0.80 | **Formation.** The orb grows from a point above and in front of the head, with a power-up surge as it reaches full size. Swirling streaks circle it, spikes pump in and out of its surface, star glints pop. Charge swell sound. |
| 0.84–0.92 | **Wind-up.** The orb is pulled back and squeezed; the user rears back further. |
| 0.95 | **Launch.** Forward throw lunge; arms thrust at the target. A shockwave ring is left at the hold point and recoil streaks fly backwards. |
| 0.95–1.35 | **Flight.** Straight line, 0.40 s, starting at a quarter speed (heavy) and ending at 1.75× (fast). Afterimages trail it, motes shed from its surface, and its streaks stretch into motion blur. Nothing is left behind once it lands. |
| 1.35 | **Impact (hit).** The orb bursts outward and fades; on the target: white flash, comic starburst, radial streaks, cyan ring, delayed violet-blue ring, ground ring, sparks, streak shards, `impact.fighting` + a deep burst sound, knockback with a squash and tilt. |
| 1.35 | **Miss.** The orb keeps going past the target, veering 1.6 blocks sideways and 0.75 up, and fades out. |
| ~1.55 | The user is back in its normal stance; the impact particles are gone by ~1.85. |

## How it is wired

- `data/cobblemon/action_effects/moves/focusblast.json`: `add_holds`, then one `parallel` that
  starts the user's animation, every orb emitter and the target's reaction in a single server tick,
  then `pause 1.40` → `remove_holds` (the HP bar drops as the orb lands) → `pause 0.8`.
- Every orb emitter is spawned at t=0 on the user's `root` locator with `targetLocators: ["target"]`
  (that's the only way to get target deltas). Their particles exist from t=0 but have zero size
  until their phase. The flight reads from curves sampled every 0.05 s (one per client tick).
  The impact lives in `animation.focusblast.target` at 1.45 (`IMPACT + PARTICLE_LAG`). So the whole
  move runs on the client clock and the impact is frame-locked to the arrival, even when the server
  lags.
- **Hit or miss is the real battle outcome.** Each orb layer has a `_miss` twin; the timeline spawns
  one set with `entityCondition` `q.missed == false` or `q.missed == true` (official precedent:
  `firespin.json`). The target reaction needs `q.missed(uuid) == false && q.hurt(uuid) == true`, so
  Protect or a Ghost-type immunity gets only the orb bursting harmlessly, with no knockback.
- **Sp. Def drop.** The animation never implies it. When Showdown actually rolls it (10 %), it emits
  `-unboost`, and Cobblemon's `BoostInstruction` plays its own `misc/unboost.json` stat-down effect.
- **Orb size and position** come from the user's own hitbox, so one file fits every learner:
  `R = clamp(0.30 + 0.20·h, 0.42, 0.85)`; held at height `min(h, 3.6) + 0.9·R` and
  `0.25·w + 0.45·R` forward. Anything taller than 3.6 blocks holds it in front of its upper body
  instead, so it stays in frame. Above the head, it's visible even from behind the user, which is
  where the player usually stands.

## Engine facts this relies on (Cobblemon 1.7.3 source)

- **One material per move.** Every Snowstorm particle renders in vanilla's
  `PARTICLE_SHEET_TRANSLUCENT` (the material mapping is commented out), and `render()` calls
  `RenderSystem.blendFunc` per particle, so the whole particle batch draws with the *last* visible
  particle's blend mode. Mixing `particles_add` in can flip a frame to additive. Every Focus Blast
  particle uses `particles_blend`.
- **Draw order is spawn order**, and translucent particles still write depth (only alpha < 0.1 is
  discarded). The core is spawned before the glow, the glow before the motes, so outer layers blend
  over the core instead of hiding it.
- **Emitter shape offsets flip x** (`getCenter` multiplies by `(-1, 1, 1)`); parametric
  `relative_position` doesn't. In the parametric frame the target is at `(-dx, +dy, -dz)`. All orb
  positions are parametric for that reason. (Official Shadow Ball uses `-dx` in shape offsets, which
  mirrors it whenever `dx ≠ 0`.)
- **Particles clone the emitter's variables at spawn.** `v.emitter_age` inside a particle expression is
  frozen at its spawn value; use `v.particle_age`. Non-local particles also freeze the emitter matrix
  at spawn, so the orb doesn't follow the user's lean or lunge.
- `creation_expression` runs before the entity variables exist; the size maths is in
  `per_update_expression`, which runs before the first particles spawn.
- Every model has `root`, `target` (approximate unless defined), `special_attack`, `middle` and `top`
  locators.
- Static `uv` expressions are evaluated every render, which is how the dash-burst plays backwards and
  the rings and glints pick frames from particle age.
- **The particle clock trails the model clock by about 0.1 s.** Particles are spawned on the client
  tick after their emitter is created, become visible on the tick after that, and a parametric
  position is rendered one tick after it's computed (render interpolates between the last two ticks).
  The first in-game recording showed the target's knockback and flash firing while the orb was still
  most of a body-width short. Keying the target animation `PARTICLE_LAG` (0.10 s) later fixed it: at
  30 fps the orb touches the target, the knockback starts one frame later and the burst one frame
  after that. Any move whose impact (a model animation) has to meet a particle projectile needs this.
- `max_frame` is a frame count. There is no camera-shake API in 1.7.3, so there's no camera shake.

## Arms on any model

Only 17 learners define a species `special` animation (Lucario doesn't), so the arm motion is an
additive generic animation. It drives `arm_left`/`arm_right` (134 of the 170 learner rigs),
`left_upper_arm`/`right_upper_arm` and `left_arm`/`right_arm`. Bones a model lacks are skipped.
The deltas were fitted with a forward-kinematics census of every learner's battle idle (same
conventions as Darkest Lariat: Bedrock→Java flips Y only, Euler angles added, `rotationZYX`):

| Beat | Left-arm delta (right mirrored) | Result over all rigs |
|---|---|---|
| focus | `[-20, 20, 15]` | hands drawn in front of the chest |
| charge | `[-55, -8, -50]` | hands up and forward: median elevation −36° → +23°, 82 % of arms clearly raised |
| wind-up | `[-80, -10, -60]` | higher and slightly back |
| throw | `[-55, 0, -5]` | thrust forward, roughly horizontal |

On the `left_upper_arm` / `left_arm` rigs the same deltas mostly raise the arms too (Nidoking-style
bipeds, Rhydon, Beartic, Trevenant, Hypno); Golem's stubby arms swing slightly backward instead,
which is barely visible on a boulder. `arm_*1` bones (Incineroar, Falinks, Poliwrath, Druddigon,
Nidoking) are deliberately left out: on Incineroar and Falinks the same deltas sent the arms
backwards or across the body. The head pitches up toward the orb during the charge and forward
on the throw.

## Files

| File | What |
|---|---|
| `data/cobblemon/action_effects/moves/focusblast.json` | timeline (generated) |
| `assets/cobblemon/bedrock/generic/animations/moves/focusblast.animation.json` | `actor`, `target` (generated) |
| `assets/cobblemon/bedrock/particles/moves/focusblast/*.particle.json` | 32 effects (generated) |
| `assets/cobblemon/sounds.json` | `move.focusblast.{focus,charge,launch,target}` |
| `docs/tools/focusblast_gen.py` | regenerates all of the above except `sounds.json` |

Particle layers, in draw order: `orb` (8 white core sprites), `orbaura` (9 cyan glow / violet halo),
`orbmotes` (36 surface motes), `orbswirl` (26 streaks), `orbrays` (16 pumping spikes), `orbglints`
(8 star glints), `trail` (22 afterimages), `motes` (30 shed motes), each with a `_miss` twin; then
`launchring`, `launchburst`, `gather`, `gatherlines`. Fired from the user's animation: `focus`,
`aura`, `auramotes`, `focusglint`. Fired from the target's animation: `impactflash`, `impactstar`,
`impactlines`, `impactring`, `impactring2`, `impactsparks`, `impactshards`, `impactground`.
About 160 orb particles at peak, plus 60 for the impact.

Reused official assets only (no new textures): `orb/largefadeorb`, `orb/glowing_dots_cyan`,
`smallbeam`, `skyding`, `ring/largering2`, `dashburst`, `hit`; sounds `impact.fighting`,
`confusion_actor`, `protect_actor`, `seismictoss_actor`, `shadowball_target`.

## Customising

Edit `docs/tools/focusblast_gen.py` and re-run it; don't hand-edit the generated files.

- **Timing:** `FORM`, `FULL`, `WIND0`/`WIND1`, `LAUNCH`, `IMPACT`, `PARTICLE_LAG`. The curves, the target's impact
  beat and the server pause all follow. Keep times on 0.05 s steps.
- **Speed feel:** `path_s` (quarter speed at release, 1.75× at arrival).
- **Orb size and position:** `SIZE_EXPR`.
- **Miss path:** `MISS_SIDE`, `MISS_UP`, `MISS_U`.
- **Arms:** `ARM_POSES` / `ARM_KEYS` / `ARM_BONES`.
- **Colours:** the tint gradients and the palette constants.
- **Sounds:** the four `move.focusblast.*` events alias official oggs. For custom audio, drop
  `assets/cobblemon/sounds/move/focusblast/focusblast_<part>.ogg` and point the `name` fields at
  `cobblemon:move/focusblast/focusblast_<part>`.

## Testing

Tested in the dev client on 2026-10-04 in the headless gamescope rig (see the Darkest Lariat doc),
10 uses across five learners, against a pinned Lv 100 Gardevoir, Shuckle and Gengar:

| User | Height | Seen from | Result |
|---|---|---|---|
| Snorlax | 3.35 | side ×2, directly behind | hit ×3 |
| Lucario | 1.2 | behind, side, front | miss ×2, hit ×1 |
| Machamp | 1.6 | front | miss |
| Riolu | 0.7 | side | hit |
| Charizard | 1.7 | side | hit; then vs Gengar: "But Gengar is immune!" |

- **Hit:** the impact lands on the arrival frame every time, with knockback; the HP bar drops with it.
- **Miss** (3 of 10 uses, as the 70 % accuracy predicts): the orb sails past the target and fades;
  no impact, no knockback.
- **Immunity:** against Gengar the orb bursts harmlessly at the target with no knockback.
- **Arms:** Lucario draws its hands in, raises them to the orb and thrusts them forward on the throw.
  Machamp raises its upper pair to the orb while its lower pair spreads.
- **Other moves:** Machamp's Seismic Toss (official animation) still played normally, and the log
  showed no errors from this mod.
- **From directly behind a bulky user at eye level** (Snorlax, 5 blocks back), the orb's lower half
  hides behind the head during the charge. Its glowing crown and rays still show above the head, and
  it's fully visible from the throw onward. From that spot the target and impact are hidden behind
  Snorlax as well, which happens with any move from that angle.

Two fixes came out of testing:
- The first orb (84 small shaded balls) read as a dull lavender cluster of bubbles. It was rebuilt
  as 8 big white core sprites, 9 cyan glow / violet halo sprites and 36 bright surface motes.
- The hold point was raised and its cut-off went from 2.4 to 3.6 blocks, so tall Pokémon hold the
  orb overhead instead of in front of their chest, and small Pokémon aren't washed out by its glow.

**Showcase GIF** (2026-10-04, for the CurseForge gallery): `~/Videos/Screencasts/focus_blast.gif`,
720x405, 24 fps, 200 colours, 2.37 s, 1.31 MB (62 % of the 2 MB cap). A wild Lv 50 Lucario that
only knows Focus Blast fires it at the player's Lv 100 Machamp, which only knows Splash, so every
take is the move and nothing else. Side view, HUD hidden with F1, trimmed from idle to idle, so it
loops cleanly. It was recorded after the impact-timing fix.
