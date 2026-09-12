# Knock Off — AI Asset Generation Prompts & Integration Notes

The move works out of the box using official Cobblemon 1.7.3 textures (the
swipe/slash decal texture, the soft dot texture used for the debris burst,
dark-type impact assets) plus one bundled custom texture (a copy of the
official `leftovers` item icon, needed because item textures aren't in the
particle atlas — see §3) and aliased official sounds. No custom animation
file is needed — the timeline reuses Cobblemon's built-in "physical" lunge
(the same fallback official `scratch` and `shadowclaw` use), so the move
works on every species for free.

## Design history (read before changing the hit visual again)

Two earlier drafts of the hit visual were rejected in-game, a third
(volumetric) draft was built but never re-verified in-game, and the design
was then explicitly reverted back to a flat decal — read all of this before
touching the hit visual again, and check which particle file is actually
present (`knockoff_swipe.particle.json` = current) rather than trusting a
single paragraph out of context.

1. **Draft 1** used `generic/scratch` (the claw-rake texture) for a flat
   billboard slash decal. Rejected: "knock off is not claw its a hand."
2. **Draft 2** swapped to `generic/swipe` (a flat hand-strike decal, same
   texture official Close Combat uses) — technically correct shape family,
   still rejected: "I wan't a 3d hand hit the oposing pokemon, not just some
   particles."
3. **Draft 3** built `knockoff_hand3d.particle.json`, a volumetric
   paddle-shaped cluster of ~260 small particles that launched from the
   actor's paw and physically traveled to the target, arcing down like a
   slap, before the impact burst fired — the same "many small points sculpt
   a solid-reading 3D shape" technique used for U-turn's dart and Volt
   Switch's ring. This was never re-confirmed in-game after being built.
4. **Current design**: on a later pass, explicitly reverted back to a flat
   decal — `knockoff_swipe.particle.json`, using the same `generic/swipe`
   texture as draft 2, but built on the proven single-instant-particle decal
   technique from `uturn_targetcut.particle.json` (an approved, in-game
   tested effect) rather than draft 2's from-scratch attempt. `draft 3's
   knockoff_hand3d.particle.json` file was deleted. If a future request asks
   for "a 3D hand" again, re-read point 2 and 3 above first — that exact
   ask has been made and answered before.

**Hard engine constraint, confirmed by scanning all 970 official particle
files and all 125 official action effects in the 1.7.3 jar:** every single
particle in the game uses `minecraft:particle_appearance_billboard` — there
is no mesh/geometry particle type, and no action-effect keyframe type for
attaching a temporary 3D prop model to a bone. A literal hand *mesh* is not
achievable in this data-driven system; a volumetric particle cluster (many
small billboards sculpted into a solid-reading shape, as draft 3 did) is the
closest true equivalent. The current flat-decal design is a deliberate
choice, not a rediscovery of this constraint — swap back to a volumetric
cluster (see draft 3's technique above) if a literal "make it read as 3D"
request comes in again.

## 1. Texture sheet prompt (Midjourney / DALL-E) — optional upgrade

The current swipe reuses the official `generic/swipe` flipbook texture (a
32×192px sheet, 6 frames at 32×32 each) — the same sheet official Close
Combat and this mod's own U-turn (`uturn_targetcut.particle.json`) use. Only
bother with a custom texture here if you want the mark itself to look
different (e.g. a torn/ripped shape instead of a clean swipe streak); the
dark/purple *coloring* is already achieved via tinting (see
`knockoff_swipe.particle.json`'s `particle_appearance_tinting` gradient), not
by the texture, so a color-only change never needs a new texture.

## 2. Sound prompt (ElevenLabs SFX)

Generate two clips (they map to the two sound events):

1. **knockoff_actor.ogg (~0.4 s):** "A single fast, sharp swipe/whoosh through
   the air, quick and decisive, with a faint dark shadowy undertone. Cinematic
   game SFX, no music."
2. **knockoff_target.ogg (~0.6 s):** "A sharp physical hand-slap impact with a
   dark, slightly hollow thud, followed immediately by a light metallic
   clatter as a small object is knocked loose and skitters away. Cinematic
   game SFX, no music."

Convert to mono Ogg Vorbis (e.g. `ffmpeg -i in.wav -ac 1 -c:a libvorbis -q:a 4 out.ogg`),
place at `assets/cobblemon/sounds/move/knockoff/knockoff_{actor,target}.ogg`,
then in `assets/cobblemon/sounds.json` swap the two `move.knockoff.*` alias
`name` fields to `cobblemon:move/knockoff/knockoff_{actor,target}` and remove
the pitch overrides. No other file changes needed.

## 3. File layout

```
src/main/resources/
├── assets/cobblemon/
│   ├── bedrock/particles/moves/knockoff/
│   │   ├── knockoff_hand.particle.json        (small dark crackle on the paw during windup)
│   │   ├── knockoff_swipe.particle.json       (the dark/purple swipe decal — appears across the target on contact)
│   │   ├── knockoff_targetsparks.particle.json (debris chip burst on contact)
│   │   └── knockoff_targetitem.particle.json  (the target's held item pops loose, tumbles, and vanishes)
│   ├── textures/particle/moves/
│   │   └── knockoff_item.png                  (copy of the official `leftovers` item icon — see note below)
│   ├── sounds.json                            (merged; adds move.knockoff.actor/target)
│   └── sounds/move/knockoff/*.ogg             (optional custom audio, see §2)
└── data/cobblemon/action_effects/moves/knockoff.json
```

**Why `knockoff_item.png` is bundled instead of referencing the official item
icon in place:** the first attempt pointed `knockoff_targetitem`'s texture
straight at `textures/item/held_items/leftovers`. In-game this rendered as
the missing-texture glitch (purple/black checker) — Cobblemon's bedrock
particle renderer only resolves textures that live under the
`textures/particle/...` tree (referenced in JSON as `textures/particles/...`,
plural — every official particle and this mod's own custom textures use that
prefix; nothing reaches into `textures/item/`). The fix was to copy the icon
into `textures/particle/moves/knockoff_item.png` and reference it as
`textures/particles/moves/knockoff_item`, matching the convention. Any future
"render this item/GUI icon as a particle" trick needs the same copy-in step.

**Why no vanilla `minecraft:crit` / `minecraft:damage_indicator` particle
IDs:** Cobblemon's move-animation pipeline (the `entity_particles` keyframe
type) only spawns particle effects registered under the Bedrock/Snowstorm
JSON format used here (`cobblemon:<name>`, resolved from
`bedrock/particles/moves/...`) — there is no keyframe type that spawns a raw
vanilla `ParticleType` directly, and none of the 125 official action effects
scanned do so either. "Customized particle parameters" (this mod's own
`.particle.json` files) is the actual mechanism; `minecraft:crit`-style IDs
aren't reachable from this system.

No `generic/animations/moves/knockoff.animation.json` — the timeline's
`"animation": ["knockoff", "scratch", "physical"]` line is a fallback chain:
Cobblemon looks for a per-species pose literally named `knockoff`, then
`scratch`, and finally falls back to `physical` — the generic attack-lunge
pose every Cobblemon-animated species already defines in its own poser
files. No custom poser JSON needs to ship with this mod; that's exactly what
the official `scratch` and `shadowclaw` action effects do too.

## 4. The swipe decal recipe (`knockoff_swipe.particle.json`)

Directly adapted from `uturn_targetcut.particle.json` (an approved,
in-game-tested effect) — the general-purpose "flat decal" recipe, as
distinct from the volumetric-cluster recipe used elsewhere in this mod (see
[[uturn-design-patterns]] for both).

- **Emitter:** `minecraft:emitter_rate_instant` with `num_particles: 1` — a
  single particle, not a spray; the "density" of the mark comes from its
  size and flipbook animation, not particle count.
- **Position:** `offset` uses `q.entity_radius` (the target's own hitbox
  radius) instead of a fixed number, so the mark lands in a sensible spot on
  the target's body regardless of whether it's a tiny or huge Pokémon.
- **Motion:** near-zero `particle_initial_speed` (0.1) with a high
  `linear_drag_coefficient` (25) — the mark is meant to hold still and just
  play its 6-frame flipbook, not fly anywhere.
- **Facing:** `facing_camera_mode: lookat_direction` orients the billboard
  plane using the `direction` vector in `emitter_shape_point`, rather than
  always facing the camera — this is what makes a decal read as "lying
  across" the target instead of a flat sticker facing the player.
- **Color:** the tint gradient (`#FFB49BD6` → `#FF4A2A6E` → transparent
  `#00140A1C`) reuses the same lavender→deep-violet→near-black palette as
  `knockoff_hand.particle.json` and `knockoff_targetsparks.particle.json`,
  so all three of the move's particles read as one coherent dark/purple
  effect rather than three different colors.

Fires directly inside the impact `sequence` in `knockoff.json` alongside
`impact_dark` and the sparks burst — no separate travel time is needed since
(unlike draft 3) nothing has to fly from the actor to the target first.

## 5. Timeline cheat sheet (absolute battle time ≈ anim time + 0.1 s)

| Time (anim) | Event |
|---|---|
| 0.10 | Built-in "physical" lunge animation starts; actor swipe sound; dark crackle begins building on the striking paw |
| 1.10 | Impact: `impact.dark` sound + dark/purple swipe decal + debris sparks + `impact_dark` flash, all at once |
| 1.20 | Held item pops loose and tumbles away, spinning, then vanishes; `move.knockoff.target` sound |
| ~2.6 | Timeline ends |

## 6. Customization guide

- **Timing:** the two `pause` values before each `sequence` block in
  `knockoff.json` control when impact and the item-pop land relative to the
  0.1s-delayed animation start. The first `pause: 1.0` is calibrated to land
  on the built-in "physical" lunge's contact frame — shortening it will make
  the swipe appear before the attacking Pokémon visually reaches the target.
- **Colors:** each particle's `minecraft:particle_appearance_tinting.color.gradient`
  maps a time fraction (0.0–1.0 of that particle's own lifetime) to an ARGB
  hex color. Edit the hex stops in `knockoff_swipe.particle.json` (and the
  other two tinted files, to keep them matching) to shift the palette —
  e.g. toward blue-black for a colder look, or brighter magenta for a more
  saturated one.
- **Particle density:** `knockoff_targetsparks.particle.json`'s
  `minecraft:emitter_rate_instant.num_particles` (currently 7) controls the
  debris count directly. `knockoff_swipe.particle.json` is deliberately a
  single particle (it's one decal mark, not a spray) — raise its
  `num_particles` above 1 only if you want multiple overlapping swipe marks
  (e.g. a "double slash" look), and vary each copy's `offset`/`rotation` via
  `math.random(...)` (see `knockoff_targetsparks.particle.json`'s direction
  vector for the pattern) so they don't stack exactly on top of each other.
- **Size/shape:** `knockoff_swipe.particle.json`'s
  `minecraft:particle_appearance_billboard.size` (`[1.3, 0.65]`, in blocks)
  controls the decal's on-screen width/height directly.
