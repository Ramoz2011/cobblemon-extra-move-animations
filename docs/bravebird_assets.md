# Brave Bird — Asset Notes & Integration Guide

Flying / Physical, 120 BP, 100 %, contact, 33 % recoil (Showdown `bravebird`, flags
contact/protect/mirror/distance, target `any`). Learned by 65 species in Cobblemon 1.7.3
(60 implemented). Not animated upstream in 1.7.3, 1.8.0, 1.8.1 or `main` (checked 2026-10-04).

Only visuals are added. Damage, accuracy, priority, contact and the recoil amount all stay
Showdown's. The recoil HP drop, its chat line and the species `recoil` flinch are still
Cobblemon's own; this effect only times them and adds the recoil sparks.

## Reference

Official footage compared per game (2026-10-04):

- **DPPt / BW:** bright cyan streaked sky; the user rushes the target.
- **XY / SM / USUM:** flies up out of view, dives back, then skims LOW over the ground with a dust
  trail. White-gold comet over blue speed lines, concentric rings and a white streak on the hit.
- **SwSh / BDSP:** the user is wrapped in a large flame-bird aura (gold) and rockets in.
- **SV:** swirl rings, then a bird-shaped plume streaks at the target, white flash.
- **Anime (DP–XY):** wings tucked "like a missile", the body becomes a light-blue bird aura,
  explosion on contact, then light-blue sparks crackle over the user (the recoil).
- Bulbapedia: Legends Z-A uses a teal aura.

The spec's cyan / blue-white palette matches the anime and Z-A, so it is used as written.

| Role | Colour |
|---|---|
| core / edges | `#FFFFFFFF`, `#FFE6FBFF` |
| cyan light / cyan / sky | `#FFB4F0FF`, `#FF6EDCFF`, `#FF46B4FF` |
| blue-violet accent | `#FF9196FF`, `#FF7378F0` |

## Choreography (seconds of animation time, total 1.62)

| Time | Beat |
|---|---|
| 0.00–0.14 | Crouch, wings puff open; ground ring + wind puff on take-off. |
| 0.14–0.36 | Hop up; two rings of wind spiral up the body, streaks converge on it, the aura glows. |
| 0.36–0.66 | Accelerating low dive, nose down 10°→22°, body stretches, wings fold (shrink), arms sweep back. Dust kicked from the ground, light trails. |
| 0.66 | Speed burst: sonic-boom ring + vapour cone left in the air (second ring at 0.78). The bird of light unfolds around the user; white-hot point on the beak. |
| 0.66–0.90 | Final charge at full speed, wingtip trails. |
| 0.90 | Contact. 0.06 s hit-stop with squash. Flash, two shockwave rings, radial wind streaks, gusts, sparks, the bird shatters into feathers. Target knocked back (`impact.flying` + thud). A small ring kicks back over the user. |
| 0.96–1.26 | Rebound up and back; at 1.06 recoil sparks crackle over the user (only if it actually took recoil), stagger shake. |
| 1.26–1.56 | Flies home and lands (dust puff). |

**Miss:** the same charge streaks on past the target with a sideways swerve and bank, no impact
effects, then loops home. **No recoil taken** (Protect, Rock Head, Magic Guard…): normal hit
but no sparks and no stagger.

## How it works (Cobblemon 1.7.3)

- **Real dash.** A `molang` keyframe measures the gap server-side
  (`q.user`/`q.target` positions and widths); the render scale comes from
  `width / species.hitbox_width`, so size-variation mods stay right. One of 33 dash animations
  (`dash_0`…`dash_32`, half-block steps up to 16 blocks) plays, or its `dashmiss_*` twin.
- **Path-locked effects.** The dash animation fires the aura, bird, trails and impact at 0.02 s,
  while `root_part` is still at rest, passing `v.du` (dash length) and `v.miss` in
  `pre_effect_script`. Those particles evaluate the same curves as the model's keyframes in the
  root locator's frame (offset u model units = u/16 × `q.entity_scale` blocks, x mirrored).
  Checked numerically against the keyframes: max error 0.0002 blocks.
- **Particle clock lag.** Emitters are created on the client tick the keyframe passes, particles
  are born a tick later and parametric positions render a tick late, so path-locked layers read
  time as `particle_age + 0.195` (`PARTICLE_LAG` = 0.175). 0.11 visibly trailed the model.
- **Impact on the client clock.** The target's knock-back is its own animation started in the
  same tick; the impact particles ride the dash animation. Both run on the client clock.
- **Recoil timing.** The timeline adds Cobblemon's official `recoil` hold (DamageInstruction waits
  for it). It's released at the top of the rebound, which only changes anything when the target
  faints; otherwise Cobblemon applies recoil after the timeline anyway.
- **Any species.** Rotation and squash/stretch on `root_part`, scale on wing bones (scale
  multiplies, so bones an idle hides stay hidden; authored dive tucks disagree in sign between
  rigs, so no wing rotation is guessed), rotation on arm bones. Missing bones are skipped.
  Effect sizes are clamped: the bird scales `0.5 + 0.6 × body` (max 2.2), impacts
  `0.6 + 0.4 × body` (max 1.5), so small birds get a big silhouette and giants don't fill the screen.
- **Per-species hook.** The timeline also requests an animation named `bravebird`; a resource pack
  can add one to a species poser and it plays on top. No official poser has one.
- One material (`particles_blend`) for the whole move; soft glows draw last.

## Files

| File | What |
|---|---|
| `data/cobblemon/action_effects/moves/bravebird.json` | timeline (generated) |
| `assets/cobblemon/bedrock/generic/animations/moves/bravebird.animation.json` | `actor_recoil`, `actor`, `actor_miss`, `target`, `dash_0..32`, `dashmiss_0..32` (generated) |
| `assets/cobblemon/bedrock/particles/moves/bravebird/*.particle.json` | 27 effects (generated) |
| `assets/cobblemon/textures/particle/moves/bravebird_feather.png` | 16×16 white feather |
| `assets/cobblemon/textures/particle/moves/bravebird_glow.png` | 32×32 round soft glow (Minecraft discards alpha < 0.1, so vanilla `flash.png` renders square) |
| `assets/cobblemon/sounds.json` | `move.bravebird.{flap,charge,dash,boom,impact,recoil,return,whoosh}` aliases |
| `docs/tools/bravebird_gen.py` | regenerates particles, animations and the timeline |
| `docs/tools/bravebird_textures.py` | regenerates both textures |

Reused official assets: `impact_flying` particle and `impact.flying` sound, `quickattack_dust`,
textures `orb/largefadeorb`, `orb/glowing_dots_cyan`, `smallbeam`, `skyding`, `ring/largering2`,
`smoke/smoke`, `vanilla/gust`, `balls/ancientfeatherball/battle/ancientfeatherflash` (frames 4–9 =
a white wind ring).

## Customising

Edit `docs/tools/bravebird_gen.py` and re-run it; never hand-edit the outputs.

- **Timing:** `ANTIC`, `RISE`, `DASH0`, `FINAL`, `IMPACT`, `HITSTOP`, `REBOUND`, `RETURN0/1`.
  Everything (particles, sounds, target knock-back, server pauses) follows.
- **Speed profile:** `P1` (share of the gap before the burst), `BOOST`.
- **Reach:** `REACH` (where the user stops, in body sizes from the target's edge).
- **Debug:** `BB_SLOW=4 python3 docs/tools/bravebird_gen.py` writes a 4× slow-motion build for
  checking placement. Always regenerate normally before building.
- **Sounds:** aliases of official oggs; to use custom audio drop
  `assets/cobblemon/sounds/move/bravebird/bravebird_<part>.ogg` and point the `name` fields there.

## Testing (dev client, 2026-10-04/05)

Staraptor vs Snorlax (two hits, the second a KO: target faints, recoil applied after), Talonflame,
Corviknight, Blaziken (no wings) and Mew vs a Lv 100 Bastiodon, and a real miss (Brave Bird into
Dugtrio's Dig, "But it missed.", swerve-past variant). Checked at normal speed and 4× slow motion
from the side and from behind. Recoil HP and messages are Showdown's/Cobblemon's in every case.
No Brave Bird errors in the log.

Known upstream issue, not ours: Corviknight's official poser references a `recoil` animation that
doesn't exist, so Cobblemon logs an error whenever Corviknight takes damage.
