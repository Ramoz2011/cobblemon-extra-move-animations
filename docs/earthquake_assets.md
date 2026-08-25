# Earthquake — AI Asset Generation Prompts & Integration Notes

The move works out of the box using official Cobblemon 1.7.3 textures
(`ring/groundquake`, `impact/impact_ground`, `generic/earth`, `smoke/smoke`)
and aliased official sounds. The prompts below are for the optional
custom-asset upgrade pass.

## 1. Sound aliases currently in use

| Event | Aliased official ogg | Pitch |
|---|---|---|
| `move.earthquake.actor` | `move/bulldoze/bulldoze_actor` | 0.7 |
| `move.earthquake.rumble` | `move/eruption/eruption_actor` | 0.55 |
| `move.earthquake.target` | `move/bulldoze/bulldoze_target` | 0.75 |
| timeline impacts | official `cobblemon:impact.ground` event (8 variants) | — |

To swap in custom audio later, drop oggs at
`assets/cobblemon/sounds/move/earthquake/earthquake_{actor,rumble,target}.ogg`
and change only the `"name"` fields in `sounds.json` to
`cobblemon:move/earthquake/earthquake_*` — nothing else changes.

Custom audio brief: actor = single deep ground slam with sub-bass thump
(~0.8 s); rumble = low rolling earth tremor with rock grinding, slow fade
(~2 s); target = rock crunch + debris scatter (~1 s).

## 2. Texture sheet prompt (optional custom crack ring)

> Sprite sheet for a video game particle effect, pixel-art style, 2D game VFX
> texture atlas on a fully transparent background (alpha channel PNG). Subject:
> top-down expanding ground-crack shockwave ring. Layout: a single horizontal
> strip of 10 frames, each frame 64x64 pixels (final sheet 640x64). Frames 1-10:
> a jagged circular crack ring seen from directly above, expanding outward from
> the center, with radial fissure lines, small dirt chunks flying off the ring
> edge, and the ring fading and crumbling in the last 3 frames. Colors: earthy
> #9E8B72 and #6B5A44 cracks, #CBB79A dust highlights, no glow. Crisp edges,
> no background, centered per frame, orthographic, flat lighting.

Wire-up: save as
`assets/cobblemon/textures/particle/moves/earthquake_ring.png`, then in
`earthquake_slamring.particle.json` and `earthquake_targetring.particle.json`
set `"texture": "textures/particles/moves/earthquake_ring"` (uv block already
matches 640x64, 10 frames of 64x64).

## 3. Design recap (for future reference)

- Actor anim 3.0 s: crouch (0–0.42) → leap to y=12 model units (0.58) → slam
  with squash 1.13/0.85 (0.667) → decaying sin-shiver on x/y/rot-z until 2.08.
- Slam frame fires slamring + slamburst + dust + actorshake from the anim;
  slamring repeats at 1.04 and 1.46 (aftershock rings).
- Timeline: fissure (live-trail point emitter racing actor→target over 0.38 s)
  at slam+~0.05, then target sequence 0.4 s later: target shake anim
  (`animation.earthquake.target`, 1.4 s sin shake) + targetfloor (official
  bulldoze field-rumble recipe, radius clamp 5–8, event-spawns rumbleclod) +
  targetring pulses (3 rings via rate_steady 2.6, max 3) + dust; two follow-up
  impacts (rocks + `cobblemon:impact_ground` stock + `impact.ground` sound) at
  +0.35 and +0.75.
- Boulders use `impact/impact_rock` (7-frame rock chunks, brown-tinted) — NOT
  `generic/earth.png`, which is literally a tiny planet-Earth sprite.
- `earthquake_dust` is shared between actor slam and target impacts (disc
  radius `0.9+v.entity_radius`).
