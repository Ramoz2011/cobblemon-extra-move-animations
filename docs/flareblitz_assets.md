# Flare Blitz — Asset Notes & Integration Guide

Fire / Physical, 120 BP, 100 %, contact, 33 % recoil, 10 % burn, thaws the user (Showdown
`flareblitz`). Learned by 70 implemented species in Cobblemon 1.7.3, by level-up among others by
the Charizard line, Arcanine, the Blaziken, Infernape, Incineroar and Emboar lines, Talonflame,
Rapidash, Flareon, Volcarona, Darmanitan, Ceruledge and Tauros. Not animated upstream in 1.7.3,
1.8.0, 1.8.1, 1.8.2, `main` or the active dev branches (checked 2026-10-21 via the GitLab API).

Only visuals are added. Damage, accuracy, contact, the burn chance and the recoil amount all stay
Showdown's. The recoil HP drop, its chat line and any burn are still Cobblemon's own; this effect
only times them and adds the recoil flames.

## Reference

Official footage compared per game (2026-10-21, YouTube clips "#394 Flare Blitz - Legends: Arceus VS
Scarlet" and "Evolution of Pokémon Moves - FLARE BLITZ (2006-2018)"):

- **DPPt / BW:** the user is engulfed in fire and rams the target; red-orange burst.
- **XY / ORAS / SM / USUM:** the user becomes a fireball and charges; big yellow-white explosion
  with radial lines and a ring of fire on the target.
- **LGPE:** a fireball with radial streaks.
- **Legends: Arceus:** fire streaks fly in, then a large yellow-orange burst on the target.
- **SV (Tauros):** golden flame streams with sparkles pour into the user from every side while its
  body turns red-hot; it flares **white** with a star glint; it charges as a fireball wrapped in
  spiralling yellow-orange flame rings; white flash on contact; a big orange explosion with black
  smoke and dark debris; flames left burning on the ground round the target.

The design follows SV beat for beat, in Cobblemon's own fire colours.

| Role | Colour |
|---|---|
| fire ramp (Cobblemon's flamecharge/flamewheel) | `#FFFFFFFF` → `#FFFFE872` → `#FFFFCC00` → `#FFFF9400` → `#FFFF4700` → `#FF531C0E` |
| white-hot / gold / amber | `#FFFFF6D2`, `#FFFFEA80`, `#FFFFD040`, `#FFFFA51E` |
| smoke | dark grey-brown, about `#2A2420` |

## Choreography (seconds of animation time, total 1.70)

| Time | Beat |
|---|---|
| 0.00–0.34 | Head-down crouch; 12 golden flame streams set off one after another from all round and curl into the body. |
| 0.12–0.59 | The heat builds: the body trembles harder, flames lick up it, a red-hot glow spreads over it; at 0.22 a ring of flames catches round the feet. |
| 0.60 | **Ignition:** the body flares white, a star glints off the top, burst lines, flames erupt from its surface. |
| 0.62–0.96 | **Charge:** a fireball wraps the user (flames flowing from its front over and off the back as a tail, white-gold light over the body), three crescents of flame spin round it and slide back; fire, dark smoke, embers and little ground flames are left along the path; the ground catches at the launch. |
| 0.96 | **Contact:** white flash, streaks of fire, two shock rings; the fireball bursts into a big explosion over the target, which is knocked back (`impact.fire` + thud + roar). |
| 1.02–1.12 | Hit-stop, then the user rebounds; if it actually took recoil, flames burst off it and sparks crackle, it staggers and smoulders. |
| 1.12–1.98 | Black smoke rolls out of the blast, a scorch mark spreads under the target, flames burn round it and die down. |
| 1.30–1.62 | The user hops home and lands (dust puff). |

**Miss:** the same charge streaks on past the target with a sideways swerve, brakes and gutters out
in a puff of smoke; no explosion, then home. **No recoil taken** (Protect, Rock Head, Magic Guard…):
normal hit, but no recoil flames, stagger or smoulder.

## How it works (Cobblemon 1.7.3)

The machinery is Brave Bird's (see `docs/bravebird_assets.md`), with a ground charge:

- **Real dash.** A `molang` keyframe measures the gap server-side; one of 33 dash animations
  (`dash_0`…`dash_32`, half-block steps up to 16 blocks) plays, or its `dashmiss_*` twin.
- **Path-locked effects.** The dash animation fires the streams, heat, fireball, trails and
  explosion at 0.02 s with `v.du` / `v.miss` in `pre_effect_script`; they evaluate the dash's own
  curves in the root locator's frame, with `PARTICLE_LAG` = 0.175 s.
- **Impact on the client clock.** The target's knock-back and its fire, scorch, ground flames and
  smoke are its own animation, started in the same tick.
- **Recoil timing.** The official `recoil` hold is released at the top of the rebound.
- **Any species.** Rotation, squash/stretch and the tremble on `root_part`; head and arm rotations
  and wing scale where those bones exist. Sizes follow the hitbox: the fireball wraps a ball of
  `max(0.6 × body, 0.45) + 0.1` blocks, flames scale `0.45 + 0.5 × body` (0.7–1.9), the explosion
  `0.6 + 0.45 × body` (0.8–1.7).
- One material (`particles_blend`) for the whole move.

New findings from this move:

- **Nothing placed at the body centre shows over the body.** Particles are drawn after the models
  and depth-tested against them, so a glow quad at the centre is buried inside the model and only
  its rim shows round the silhouette. The white flash, the red-hot glow and the fireball's light
  are therefore many soft glows spread over a ball just *outside* the body: whichever side the
  camera is on, the near ones lie in front of the model.
- **Low-res sheets turn blocky when big.** `largering2` (20×20 frames) as a 4–8-block ring rendered
  as big pale squares; the shock rings use `giantring_white` (64×64 frames). The vanilla 8×8 smoke
  looked like grey checkerboards at a block across; smoke uses Cobblemon's 16×16 fire puff tinted
  dark.
- **Flat planes are one-sided in 1.7.3.** Every Snowstorm particle renders in vanilla
  `PARTICLE_SHEET_TRANSLUCENT` with back-face culling on, so `emitter_transform_xy/xz` quads are
  visible from one side only (1.8's BLEND/ADD materials turn culling off). The only flat quads here
  are the scorch (seen from above); the rings are camera-facing.

## Files

| File | What |
|---|---|
| `data/cobblemon/action_effects/moves/flareblitz.json` | timeline (generated) |
| `assets/cobblemon/bedrock/generic/animations/moves/flareblitz.animation.json` | `actor_recoil`, `actor`, `actor_miss`, `target`, `dash_0..32`, `dashmiss_0..32` (generated) |
| `assets/cobblemon/bedrock/particles/moves/flareblitz/*.particle.json` | 34 effects (generated) |
| `assets/cobblemon/sounds.json` | `move.flareblitz.{gather,ignite,dash,impact,blast,recoil,return,whoosh}` aliases |
| `docs/tools/flareblitz_gen.py` | regenerates particles, animations and the timeline |

No new textures. Reused official assets: `impact_fire` particle and `impact.fire` sound,
`quickattack_dust`, textures `fire/cloudyfire_white`, `fire/flame`, `fire/ember`,
`sparkle/glowingsparkle_yellow`, `moves/explosion_floorscorch`, `ring/giantring_white`, `smallbeam`,
`skyding`, `dashburst`, and this mod's `moves/bravebird_glow`.

Sound aliases (official oggs): gather = `lavaplume_actor` ×1.2, ignite = `ember_actor` ×0.75,
dash = `flamethrower_target` ×0.8, impact = `bodyslam_target` ×0.8, blast = `lavaplume_target`
×0.75, recoil = `ember_target` ×1.35, return = `aerialace_actor_2` ×1.2, whoosh (miss) =
`lavaplume_target` ×1.15.

## Customising

Edit `docs/tools/flareblitz_gen.py` and re-run it; never hand-edit the outputs.

- **Timing:** `GATHER0`, `CROUCH`, `IGNITE`, `DASH0`, `IMPACT`, `HITSTOP`, `REBOUND`, `RETURN0/1`.
  Everything (particles, sounds, target knock-back, server pauses) follows.
- **Speed profile:** `M0`, `M1` (Hermite tangents of the charge). **Reach:** `REACH`.
- **Debug:** `FB_SLOW=4` writes a 4× slow-motion build; `FB_FORCE_MISS=1` makes every use play the
  miss variant. Always regenerate normally before building.
- **Sounds:** aliases of official oggs; to use custom audio drop
  `assets/cobblemon/sounds/move/flareblitz/flareblitz_<part>.ogg` and point the `name` fields there.

## Tools

- `docs/tools/validate_move.py <move>`: textures exist and UV/flipbook rectangles fit the real
  sheets, colours are `#AARRGGBB`, every `v.*` read is declared, every particle/sound/animation
  referenced exists, and every MoLang string parses with Cobblemon's own parser (`MoCheck.java`
  against the jar in the Gradle cache).
- `docs/tools/preview_move.py <move> out.png [--du 64] [--size 1.0] [--miss] [--times …] [--layers …]`:
  replays the generated particle expressions (`molang.py`) and paints side / behind / top
  storyboards with each sprite frame's real coverage, for checking composition before going in-game.

## Testing (dev client, 2026-10-21)

Headless gamescope rig on a floating test platform, recorded through gamescope's PipeWire node:

- Arcanine vs a Lv 100 Blastoise from the side and from behind (four uses, recoil each time).
- Litten (small), Charizard (large), Tauros (the SV reference) vs the same Blastoise.
- A wild Arcanine using it on the player's Charizard (front view).
- Tauros vs Dugtrio with the `FB_FORCE_MISS` debug build (the miss path), and Arcanine knocking out
  a Lv 10 Rattata (faint + recoil).

52–60 fps throughout (vsync 60) with about 630 Flare Blitz particles at the peak; no Flare Blitz
errors in the log. Upstream noise seen while testing, not ours: Arcanine's poser references a
missing `battle_cry` animation.
