# Solar Beam — asset notes

## How the two-turn mechanic is wired (no Java!)

Cobblemon's `PrepareInstruction` handles Showdown's `|-prepare|` message for two-turn
moves and looks up the action effect **`cobblemon:prepare_<move>`**. The attack turn
plays the normal **`cobblemon:moves/<move>`** effect via `MoveInstruction`. So:

- `data/cobblemon/action_effects/prepare_solarbeam.json` — charge turn (turn 1)
- `data/cobblemon/action_effects/moves/solarbeam.json` — fire turn (turn 2)

**Harsh Sunlight:** Showdown still emits `-prepare` and then executes the move in the
same turn, so the charge effect (~2.1s) and the beam (~3.2s) play back-to-back
automatically. No weather-detection logic is needed.

The prepare effect only receives a `UsersProvider` (no target exists yet), so all
charge particles anchor on the user's own `special`/`target` locators.

## Choreography

**Charge (2.1s):** god-rays stream down from a disc 3.4 blocks up (`lightbeam.png`
stretched along velocity), green-gold sparkles get inhaled from a 2-block sphere,
a volumetric mini-sun (26 clustered `energyorb` billboards) grows overhead, leaves
spiral upward. Pokémon tilts head up −18° and rises, with a shiver near the end.

**Fire (3.2s):** 0.5s flash-gather → snap forward, recoil −6 with jitter →
official beam recipe: invisible `actorpilot` (creation_event spawns children that
inherit `v.target_delta*` / `v.target_distance`) drives a white-gold add-material
core (0.5 thick) inside a green-gold alpha sheath (0.95), 1.25s sustain →
target: `impact.grass` sound + `cobblemon:impact_grass` + gold explosion burst,
expanding green ring, gravity/bounce sparks, leaf scatter.

## Sounds (aliased, audible immediately)

| Event | Aliases | Pitch |
|---|---|---|
| `move.solarbeam.charge` | `magicalleaf_actor_1` | 0.7 |
| `move.solarbeam.actor` | `icebeam_actor` | 0.85 |
| `move.solarbeam.target` | `magicalleaf_target` | 0.8 |
| (timeline) | official `impact.grass` event | — |

To use custom audio later, drop oggs at
`assets/cobblemon/sounds/move/solarbeam/solarbeam_{charge,actor,target}.ogg` and
change the `name` fields in `assets/cobblemon/sounds.json` to
`cobblemon:move/solarbeam/solarbeam_<part>` — nothing else changes.

## Texture dims used (new to the census)

- `generic/lightbeam.png` 6x128 — single vertical shaft, great god-ray
- `generic/grass/leaf.png` 16x64 — 4 leaf variants 16x16; random variant via
  `base_UV: [0, "math.floor(v.particle_random_3*4)*16"]` with `max_frame: 1`
- `generic/sparkle/mediumsparkle.png` 63x9 — 7 frames 9x9, step [9,0]
- `generic/orb/xsunboost.png` 45x5 — 9 frames 5x5 (unused here, noted for later)
- `generic/ring/largering.png` 160x20 — 8 frames 20x20, step [20,0]
