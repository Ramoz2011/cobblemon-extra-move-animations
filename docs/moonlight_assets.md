# Moonlight — Asset Notes & Integration Guide

Moonlight is a Fairy-type status move: the user restores its own HP by bathing in moonlight (1/2 of its
max HP, 2/3 in harsh sunlight, 1/4 in rain, sandstorm, hail or snow). This mod animates it: a full moon
rises above the user, a column of moonlight comes down on it, it glows while light spirals round it, and
the games' heal burst plays as the HP bar rises. The look follows Sword/Shield and Scarlet/Violet, and
how bright it is follows the battle's own heal, so it is brighter in harsh sunlight and softer in bad
weather.

Every file below is generated: edit `docs/tools/moonlight_gen.py` (particles, animation, action effect,
sound aliases) or `docs/tools/moonlight_textures.py` (sprites) and re-run them. Don't hand-edit outputs.

## Reference and palette

Not animated by Cobblemon: no `action_effects/moves/moonlight.json` in 1.7.3, 1.8.0-1.8.4, `main` or the
ten most recently active branches (checked 2026-11-16 via the GitLab API; `hydropump.json` as the
control). Showdown (bundled): Fairy, Status, PP 5, target `self`, flags snatch/heal/metronome; at full
HP it fails with `|-fail|POKEMON|heal` ("…'s HP is full!"). 18 implemented learners in 1.7.3, from
Morelull (0.25 blocks tall) to Exeggutor; Clefairy, Clefable, Umbreon, Lunatone, Munna, Musharna,
Oddish line, Shiinotic, Volbeat, Illumise and Noivern learn it by level.

Game look (Magiscars Database "#236 Moonlight - Gen 2-9", bXMsbi4bV9I, frame by frame):

- Gen 2-5: the background darkens, a grey full moon appears near the user with yellow four-point
  sparkles, then the generic heal glow.
- XY / USUM: a cut to a night sky with a big white-blue moon and star sparkles (USUM adds blue halo
  rings), then green heal streaks.
- **SwSh** (Shiinotic): night falls; a grey moon with darker maria fades in; it gets a blue glow and
  sparkly blue dust; concentric cyan rings with violet edges pulse out of it; a translucent blue column
  of light comes down on the user, who stands on a glowing blue-violet circle with cyan arcs swirling
  round it, thin pink and white streaks rising and teal dots floating; then the generic heal (green
  bubble, white and mint sparkle rays).
- **SV** (Cresselia): the moon in the sky, blue rings, light pouring down diagonally; white-lavender
  light rings orbit the body with blue and pink sparkles; then mint sparkles and a green bubble.

The request's palette (silver-white moon, pale blue and lavender light) matches the games. The one
place they differ is the very end: the games finish with their generic **mint/green heal burst**, which
is what this uses (the user has chosen game-accurate colours every time this came up). It is a single
constant (`MINT`) and the four `heal*` layers if a white/blue finish is wanted instead.

| Role | Colour |
|---|---|
| moon (sprite) | grey-blue ramp `#59627D` → `#FAFBFD`, tinted silver `(0.94, 0.97, 1.0)` |
| moon glow (in the sprite) | `#CCDDFF` at the rim → `#6B8FFF` |
| moon rings | white-cyan `#DBF7FF` band, cyan `#6BD1FF`, violet `#9970FF` outer edge |
| column of light | silver-blue `#BDDBFF`, whiter core (texture) |
| ground circle | pale blue-violet pool `#CCD6FF`, cyan swirl `#99E6FF` |
| aura, model tint | white-blue `#BDDEFF`; tint `(0.72, 0.85, 1.0)` with a white wash |
| ribbons, streaks | white heads fading to lavender `#B8ADFF`; some pink streaks `#FFC7F5` |
| heal burst | mint `#9EFFC7`, white rays, mint stars |

## Choreography (animation time, seconds)

The request's 34-tick (1.7 s) plan was stretched to about 2.8 s: the spec allows adjusting the timing,
the games take longer still, and slower reads better in a Minecraft battle (an earlier preference).

| Time | Beat |
|---|---|
| 0.00–0.42 | The user looks up: leans back 7°, head up 14°, rises a little. Nothing an animation fires can show before about 0.2 s, so the first effects start then. |
| 0.22–0.82 | **The moon** fades in above and slightly behind the user, drifting down a touch. Stars twinkle round it and blue glitter drifts off it. |
| 0.80, 0.98, 1.16 | Three **rings** pulse out of the moon; it swells slightly with each. |
| 0.98–1.30 | **The column of moonlight** grows down from the moon to the ground. |
| 1.20–1.42 | **The circle of light** lights up under the user: a pale pool with three cyan arcs turning inside a thin rim. Motes start drifting down the column. |
| 1.28–2.13 | Thin white and pink streaks rise round the user inside the column. |
| 1.38–1.68 | **The glow**: the user's model is tinted white-blue (Java hook) and a soft aura gathers over it. It breathes and sways in the light and floats up. |
| 1.42–2.24 | Three **light ribbons** spiral up round the body (a third of a turn apart, tilted apart), with four-point stars circling slowly. |
| 1.58, 1.80, 2.02 | **Rings of light** spread out from the body (low, middle, high). |
| 2.06 (`HEAL`) | **Heal.** The column flares once, the user stretches, the mint heal bubble, rays and stars burst. The action effect releases its hold here, so the battle restores the HP and prints "…restored its HP." now. |
| 2.16–2.56 | The column (narrowing as it fades), the circle and the aura fade. |
| 2.24–2.76 | The moon fades last. The user drops back into its stance with a small bounce (settled by 2.70). |
| 2.86 | The action effect ends; nothing is left behind. |

## Weather versions (visual only)

The battle decides the heal; the animation only reads what it decided. The action effect calls
`q.user.move_heal_share` (Java hook `battle/MoveHeal.java`): the share of max HP this heal was worth.

- **Not topped up:** Showdown prints the HP the Pokémon ends on and Cobblemon still holds the HP it had,
  so the share is exact (healed / max: 0.667, 0.5 or 0.25). That is the weather as Showdown applied it,
  Cloud Nine, Air Lock and Utility Umbrella included.
- **Topped up** (HP reached max): the heal may have been worth more than it gave, so the field's
  weather as Cobblemon tracks it picks the share it can still be.
- **Failed** (HP already full): -1. **Unknown** (or the hook missing): 0, which plays the normal version.

| Share | Version | Look |
|---|---|---|
| > 0.58 (harsh sunlight) | `actor_bright` | brightness ×1.3, every sparkle, stronger model tint |
| 0.38–0.58, or 0 | `actor` | normal: brightness ×1, 80 % of the optional sparkles |
| 0 < share < 0.38 (rain, sand, hail, snow) | `actor_soft` | brightness ×0.68, 55 % of the sparkles, softer tint |
| < 0 (HP full) | `actor_fail` | the moon peeks out faintly and fades (0.95 s); no column, no heal |

The versions are the same animation with different `pre_effect_script` values (`v.lum`, `v.dens`) on
each effect. Nothing here changes how much HP is restored.

## Engine facts this relies on (Cobblemon 1.7.3 source; same in 1.8.4)

- `MoveInstruction` waits on `UntilDispatch { "effects" !in holds }`; the `-heal` line's
  `HealInstruction` is a plain `dispatchWaiting`, so the HP bar rises exactly when the timeline removes
  the hold. Measured: mint burst at 6.3 s, "restored its HP." and the bar rising at 6.4 s.
- Moonlight's log line names its user as its own target, so the action effect gets the user twice (users
  and targets providers). `entity_particles` tests `isUser` as "is in the users list", so every effect
  would be sent twice; `entity_molang` passes `isUser` per provider, so `q.entity.is_user == true` reaches
  the user once. Hence everything is fired by the user's animation, started by one `entity_molang`.
- No MoLang query exposes weather or heals (checked both jars), hence the hook. Cobblemon's
  `ContextManager` (battle weather) is deprecated in both versions; the hook only asks it for topped-up
  heals, inside its own try/catch.
- Particles keep the emitter frame of the tick they were born in; everything is born at T0 with the
  body at rest, so sky and ground layers stay put while the body floats; body layers add the root_part
  float (curves `fy`/`fz`).
- Billboards accept `"direction": {"mode": "custom", "custom_direction": [...]}`; with
  `lookat_direction` the quad's x axis (size[0], texture U) runs along that direction, so the column is
  one vertical quad that turns to face the camera. `emitter_transform_xz` quads ignore the particle
  angle, so the turning ground swirl is an 8-frame flipbook. Billboard full width = 2 × size / 1.5.
- Depth: translucent particles write depth wherever they pass the 0.1 alpha cut, and spawn order is
  draw order. Quads that face the camera through the same point are coplanar and z-fight (in-game the moon
  blinked out behind a separate halo quad, and a seam ran across it), so the glow is part of the moon
  sprite, there is one column quad, and the rings sit 0.04 below the moon's centre (battle cameras look
  up at it). Big soft glows drawn before the column punched dark holes in it at night, so the aura and
  heal burst are drawn after it.

## Files

| File | What |
|---|---|
| `data/cobblemon/action_effects/moves/moonlight.json` | timeline: picks the version, model tint, releases the hold at `HEAL` (generated) |
| `assets/cobblemon/bedrock/generic/animations/moves/moonlight.animation.json` | `actor_bright`, `actor`, `actor_soft`, `actor_fail` (generated) |
| `assets/cobblemon/bedrock/particles/moves/moonlight/*.particle.json` | 26 particle effects (generated) |
| `assets/cobblemon/textures/particle/moves/moonlight_{moon,column,ring,swirl}.png` | sprites (generated by `moonlight_textures.py`) |
| `assets/cobblemon/sounds.json` | 6 `move.moonlight.*` aliases of Cobblemon's own sounds (generated) |
| `src/main/java/.../battle/MoveHeal.java` | `move_heal_share` MoLang hook (registered in `Cobblemon_extra_move_animation.java`) |
| `docs/tools/moonlight_gen.py`, `docs/tools/moonlight_textures.py` | generators |

Reused: `moves/bravebird_glow` (soft round glow), `generic/sparkle/glowingsparkle`, `generic/skyding`,
`generic/smallbeam`. Sounds: moon = `psychic_actor` (pitch 0.7), twinkle/glow = `evolution_notification`
(pitch 1.6 / 1.2), beam = `protect_actor` (0.75), heal = `medicine_liquid_use` (1.1) +
`impact_generic_fairy_3` (1.3). The shiny chime was avoided on purpose (players read it as "a shiny").
The move is listed in the mod's "This mod / Cobblemon" settings screen automatically.

## Customising

All in `docs/tools/moonlight_gen.py`; re-run it, then `./gradlew build` (or, in a running dev client,
copy `src/main/resources` to `build/resources/main` and press F3+T, then `/reload`).

- **Moon size and height:** `GEOM` — `v.mr` (radius, `0.5 + 0.24 × body size`, clamped 0.62–1.2 blocks),
  `v.my` (centre height above the feet), `v.mz` (how far behind). The glow around it is part of
  `moonlight_moon.png` (`GLOW_IN`/`GLOW_OUT` and the falloff in `moonlight_textures.py`).
- **Beam width and intensity:** `v.cr` in `GEOM` (column radius) and `p_beam()` (`0.7 × v.benv × v.lu`,
  capped at 0.92); `beam_env()` shapes its rise, the flare at `HEAL` (+50 %) and the fade. Colour `BEAM`.
  The soft profile is `column()` in `moonlight_textures.py`.
- **Weather difference:** `VARIANTS` (brightness and sparkle share per version) and `TINT_LEVELS`
  (model tint strength and white wash); thresholds `SUN`/`WEAK`/`FAIL`.
- **Particle amounts:** the count passed to `locked(...)` in each `p_*` function; `v.dens` hides a share of
  the optional sparkles in the softer versions.
- **Timing:** the constants at the top (`MOON0`, `BEAM0`, `HEAL`, `FADE0`, …). Keep `END` just after the
  last fade; `HEAL` is also when the HP bar rises. Body motion: `ROOT_BASE`, `ROOT_ROT_BASE`, `HEAD`.
- **Debug builds:** `ML_FORCE=sun|weak|fail python3 docs/tools/moonlight_gen.py` makes every Moonlight
  play that version (never ship); `-Dcobblemon_extra_move_animation.debug=true` logs each hook answer.

## Testing (2026-11-16, Cobblemon 1.7.3 dev client, headless rig)

- `validate_move.py moonlight`: 0 problems (26 particles, 4 animations, every MoLang string parses with
  Cobblemon's parser). `./gradlew build` OK. MoveHeal's 21 Cobblemon/MoLang references resolve with the
  same signatures in 1.7.3 and 1.8.4; 1.8.4's particle reader has every feature used.
- Clefable vs a wild Lv100 Magikarp (Splash only), poisoned to lower its HP:
  - no weather, 58/162 HP: healed 81 = share 0.500 exact → normal version;
  - no weather, topped up (healed 43): share 0.5 from the weather fallback → normal;
  - Rain Dance then Moonlight, topped up (healed 40): 0.25 → soft version;
  - Sunny Day then Moonlight, topped up: 0.667 → bright version, visibly stronger column and glow;
  - full HP: -1 → the moon peeks and fades, then "Clefable's HP is full!".
- Clefairy (small), Exeggutor (tall; its palm leaves top its hitbox, hence `1.1 × v.bh` in `v.my`),
  Noivern (big, dark model glows pale) and a wild Clefable seen from the player's side at night.
- HP restoration unchanged (Showdown's own numbers above); the user returns to its stance; nothing is
  left after 2.86 s; no warnings from the mod. The settings screen config gained `"moonlight": "this_mod"`.
- Not tested in-game: Cobblemon 1.8.x runtime (static checks only), a double battle.
