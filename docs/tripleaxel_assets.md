# Triple Axel — Asset Notes & Integration Guide

Weavile's and Cinccino's three-hit Ice move (Showdown id `tripleaxel`, Ice,
20/40/60 BP across three hits). Built entirely from **official Cobblemon 1.7.3
textures and aliased official sounds** — no custom sprite sheets, because the
atlas already ships two unused sheets that are exactly right for it.

> **Naming note.** This animation was specified as *"Triple Axe"*, which is not
> a move — Cobblemon's bundled Showdown data has `tripleaxel`, `stoneaxe`,
> `axekick`, `triplearrows`, `tripledive` and `triplekick`, and an action effect
> filed under a non-existent id would never fire. `tripleaxel` was chosen: the
> closest name, and a genuine three-hit move, so the spec's three consecutive
> slashes map onto three real damage hits. The spec's green/metallic palette was
> retyped to the move's real Ice colours at the same time; the "metallic" note
> survives as the frost-steel `#FFDCE8F2` used on the blade glints.

## Design

The spec's beat sheet, kept to the frame, with a figure-skating **axel jump**
folded into it for game accuracy (Triple Axel is named after the axel jump —
that's why an Ice move is a three-hit contact attack):

1. **Anticipation (0.00 – 0.30 s).** The user dips and rears back, winding
   away from the target. Ice motes rush inward from a sphere around it, a
   frost swirl spirals up around its body, an icy aura blooms over it, and
   frost-steel glints flare off its striking limbs at the coil peak.
2. **Execution (0.30 – 1.00 s).** It explodes upward into a full 360° axel
   spin, squaring up again at 0.46 s — then throws three slashes in rapid
   succession: **left horizontal (0.50)**, **right horizontal (0.625)**,
   **overhead downward chop (0.75)**, the body counter-rotating between the
   first two and pitching 38° forward into the chop. Each swing leaves a
   crescent arc at the user and releases a crescent projectile that flies
   at the target. Frost is flung off the spin as a horizontal ring.
3. **Impact (1.00 – 1.30 s).** The crescents land on the beat — 1.00, 1.15,
   1.30. Hit 1 carves a diagonal, hit 2 carves the crossing diagonal
   (**the X**), hit 3 lands the vertical gash *and re-flashes both diagonals*,
   so the finished mark is a glowing X with a vertical cut through it. Each
   hit throws an ice-spark burst, a shockwave ring and the official
   `impact.ice` set; the third adds a heavy shard explosion, a bright flash
   and lingering frost mist. The target flinches once per hit.
4. **Recovery (1.30 – 1.50 s).** The user touches down with a landing squash
   and a powder-snow puff, rebounds, and settles back to idle as the trails
   fade.

## One slash per hit that actually landed

Triple Axel is `multihit: 3` with a **per-hit accuracy check**, so it lands one,
two or three hits — or misses outright. The animation follows the real outcome
rather than always playing three swings.

Cobblemon's `MoveInstruction` scans the battle instruction set for the
`HitCountInstruction` and registers **`q.hit_count`** on the action-effect
MoLang runtime *before* `ActionEffectTimeline.run` is called, so the whole
timeline can branch on it via the `condition` field that every keyframe type
inherits from `ConditionalActionEffectKeyframe`:

| Outcome | Actor | Crescents | Marks on the target |
|---|---|---|---|
| missed | `actor1` — one swing | 1 flies past | none (gated by `q.missed`) |
| 1 hit | `actor1` — one swing | 1 | `/` |
| 2 hits | `actor2` — two swings | 2 | `/` + `\` = **X** |
| 3 hits | `actor3` — three swings | 3 | X + vertical gash |

Three details make this safe:

- **A missed move emits no `-hitcount`**, so `q.hit_count` is never registered.
  MoLang's `QueryStruct.get` returns `DoubleValue.ZERO` for an unknown query
  rather than throwing, so it reads as `0` — which is why the first branch is
  `q.hit_count <= 1` and not `== 1`. A miss therefore plays the one-swing
  variant and the crescent flies past, matching how `aerialace` and `uturn`
  handle their own misses.
- **Every `pause` stays outside the conditional blocks.** A failed condition
  calls `skip()`, which completes instantly — a pause nested inside one would
  drag every later beat forward and desync the impacts from the crescents.
  The timeline is 3.00 s for all four outcomes.
- **The variants share one shape.** Anticipation and the axel spin are
  identical; the landing/recovery tail hangs off the last slash (`TL`) at fixed
  offsets (`TL+0.125` descent, `+0.2083` land, `+0.2917` rebound, `+0.40`
  settle, `+0.75` idle), so a one-hit Triple Axel reads as the same move cut
  short rather than a different animation.

## The crescents are volumetric, not decals

Each of the three projectiles is a **cluster of chunky ice chips sculpted onto
an arc**, not a flat billboard — per the project's standing rule that anything
reading as a solid object flying at the target must have real depth. The arc
lives in the plane perpendicular to travel, so it presents its broad face to
the battle camera:

```
theta = (random_1 - 0.5) * span          # position along the arc
taper = 4u(1-u)                          # 1 at the centre, 0 at both tips
r     = r0 + (random_3 - 0.5) * thickness * taper
(a,b) = (r cos theta, r sin theta)
```

`(a,b)` is then rolled into place by a **baked** rotation — `phi = +90` gives a
horizontal arc bulging up (slash 1), `-90` a horizontal arc bulging down
(slash 2), `0` a vertical arc (the chop). Baking the rotation into the
expressions rather than using `particle_initial_spin` means the three arcs are
oriented deterministically, with no dependence on which way the engine rolls a
sprite. Chip size is scaled by `taper` too, so the tips thin out into points.

A second, softer cluster of glow orbs (`glow1/2/3`) rides the *same* arc math at
a slightly tighter radius, so the shape reads as a lit energy blade rather than
loose debris, and a shared sparkle wake (`trail`) spawns along the flight path.

Flight uses `minecraft:particle_motion_parametric`, interpolating from a launch
offset to `v.target_delta*` so arrival timing is exact:

```
pos = launch * (1 - t) + target_delta * t + arc_shape
```

The three flight times are **0.500 / 0.525 / 0.550 s**, staggered against the
launch times (0.50 / 0.625 / 0.75) so the impacts land on exactly 1.00 / 1.15 /
1.30 despite the different launch offsets. Chip counts and radii ramp 100/120/160
and 0.72/0.82/1.02 blocks with the move's own 20/40/60 power ramp.

## Official textures reused

| Texture | Size | Used for |
|---|---|---|
| `generic/slash` | 32×160, 5f | the swing arcs at the user, and the vertical gash on the target — a ready-made pale-ice crescent sheet with **zero official uses** |
| `generic/cut` | 32×224, 7f | the two diagonal cut strokes that form the X |
| `generic/ice/iceshard` | 42×14, 3f | every crescent chip, the spin frost, and both impact bursts — chunky, blocky, tints ice-blue |
| `generic/smallexplosion` | 16×144, 9f | the per-hit shockwave ring (**zero official uses**) |
| `generic/ice/icy_snow` | 16×4, 4f | the wind/frost swirl motes — literally 4 single-pixel voxel specks (**zero official uses**) |
| `generic/ice/powdered_snow` | 64×16, 4f | the landing puff (horizontal strip, `step_UV [16,0]`) |
| `generic/sparkle/glowingsparkle_cyan` | 8×32, 4f | the inward energy gather and the projectile wake |
| `generic/sparkle/bigsparkle` | 16×96, 6f | the frost-steel blade glints |
| `generic/aura_white` | 8×56, 7f | the icy body aura |
| `generic/orb/scaling` | 8×32, 4f | crescent glow orbs (static frame 0) and the third-hit flash |
| `generic/smoke/glowingsmoke_cyan` | 8×48, 6f | lingering frost mist |
| `generic/impact/impact_ice` | 8×56, 7f | via the stock `cobblemon:impact_ice` effect |

## Sounds

All aliased from official Cobblemon audio in `assets/cobblemon/sounds.json`;
every referenced `.ogg` was verified to exist in the 1.7.3 jar.

| Event | Source | Vol / Pitch |
|---|---|---|
| `move.tripleaxel.charge` | `move/icebeam/icebeam_actor` | 0.80 / 1.10 |
| `move.tripleaxel.swing1` | `move/aerialace/aerialace_actor_1` | 0.95 / 1.15 |
| `move.tripleaxel.swing2` | `move/aerialace/aerialace_actor_1` | 0.95 / 1.28 |
| `move.tripleaxel.swing3` | `move/aerialace/aerialace_actor_2` | 1.00 / 0.95 |
| `move.tripleaxel.land` | `move/quickattack/quickattack_actor` | 0.65 / 0.85 |
| `move.tripleaxel.target` | `move/icebeam/icebeam_target_1` | 1.00 / 0.90 |

Hits 1 and 2 use the stock 8-variant `impact.ice` set; hit 3 layers
`move.tripleaxel.target` over it.

## Palette

| Role | Hex |
|---|---|
| core white | `#FFFFFFFF` |
| glacier | `#FFEAFBFF` |
| pale ice | `#FFC8F2FF` |
| ice blue | `#FF9EE4FF` |
| bright cyan | `#FF6FD0FF` |
| deep ice | `#FF3FA8F5` |
| shadow | `#FF2A6FD0` |
| frost-steel (the spec's "metallic") | `#FFDCE8F2` |

## Files

```
data/cobblemon/action_effects/moves/tripleaxel.json          timeline, 3.00 s
assets/cobblemon/bedrock/generic/animations/moves/tripleaxel.animation.json
    animation.tripleaxel.actor1   1.75 s  |  actor2  1.90 s  |  actor3  2.00 s
    animation.tripleaxel.target1  0.90 s  |  target2 1.05 s  |  target3 1.20 s
    (one swing / one recoil per landed hit; picked by q.hit_count)
assets/cobblemon/bedrock/particles/moves/tripleaxel/         24 particles
```

Action-effect time runs **0.1 s ahead of animation time** (the animation is
triggered after the opening pause), so animation 0.50 = action 0.60, and so on.

| Particle | Fired at | Role |
|---|---|---|
| `gather`, `frostswirl`, `aura` | anim 0.0417 | energy gathers, wind swirl, icy aura |
| `glint` | anim 0.25 | frost-steel blade flares at the coil peak |
| `spinfrost` | anim 0.2917 | frost flung off the axel spin |
| `swing1` / `swing2` / `swing3` | anim 0.50 / 0.625 / 0.75 | the blade arcs at the user |
| `crescent1-3` + `glow1-3` + `trail` | action 0.60 / 0.725 / 0.85 | the flying crescents (2 and 3 gated on `q.hit_count`) |
| `cut1` / `cut2` / `cut3` | action 1.10 / 1.25 / 1.40 | "/" then "\" (the X) then the vertical gash |
| `sparks`, `ring` | each landed hit | spark burst + shockwave |
| `shards`, `burst`, `frostmist` | hit 3 only | heavy explosion, flash, lingering mist |
| `land` | anim 0.9583 | powder-snow landing puff |

## Customising

- **Always play all three swings** (ignore the real hit count): drop the
  `condition` fields from the action effect and point every branch at
  `actor3` / `target3`.
- **Slower, more readable flight:** raise `max_lifetime` on `crescent{n}` and
  `glow{n}` together (they must match), then add the same delta to the
  corresponding `pause` before that hit's `sequence` in the action effect.
- **Bigger crescents:** the `r0` constant inside each `crescent{n}` /
  `glow{n}` expression (0.72 / 0.82 / 1.02) is the arc radius in blocks; the
  `*1.0` / `*1.08` / `*1.2` factor in the `size` expression scales the chips.
- **Different arc shape:** the `*190` / `*200` inside `math.cos`/`math.sin` is
  the arc's angular span in degrees. Below ~140 it reads as a shallow scythe;
  above ~240 it closes into a ring.
- **Re-tint:** every colour is an `#AARRGGBB` string in
  `particle_appearance_tinting`. Note `particles_alpha` is a **cutout**
  material in Cobblemon — anything on it must fade by shrinking its size
  curve, never by ramping tint alpha, or it pops. `particles_blend` fades
  properly; `particles_add` is additive glow.
- **Flipbook frames:** Cobblemon reads `max_frame` as the frame **count**, not
  the last index — 743 of the 971 official particles set it to exactly
  `sheet height / frame height`. Setting it to `count - 1` silently drops the
  sheet's last frame (usually the one that fades out), so a flipbook edited
  that way pops instead of fading.
