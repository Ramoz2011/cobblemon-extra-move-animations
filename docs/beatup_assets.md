# Beat Up — Asset Notes & Integration Guide

Dark / Physical, non-contact, 100 % (Showdown `beatup`). It hits once for the user and once for
every other party member that hasn't fainted and has no status condition, so up to six times; each
hit's power is 5 + the striker's base Attack / 10. Learned by 62 implemented species in Cobblemon
1.7.3, by level-up by Sneasel / Weavile, Houndour / Houndoom, Shiftry, Scraggy / Scrafty, Durant,
Wishiwashi, Nickit / Thievul and Tandemaus / Maushold. Not animated upstream in 1.7.3, 1.8.0, 1.8.1,
1.8.2, `main` or the 14 most recently active branches (checked 2026-10-21 via the GitLab API).

Only visuals are added. Damage, accuracy, the hit count and who takes part all stay Showdown's; the
animation only reads the hit count the battle reports.

This is the first move in the mod with Java behind it: the teammates are drawn with their own
Cobblemon models, which the JSON animation system can't do. Everything else is data, like the other
moves, and keeps working if the Java part ever can't run (see *Failure behaviour*).

## Reference

Official footage compared per game (2026-10-21, YouTube "#251 Beat Up - Gen 2-9 Pokémon Move"):

- **Gen 2–4:** "*X*'s attack!" for each party member, each with a fist hit on the target (a purple
  fist in Platinum).
- **Gen 5 (BW2):** a translucent dark-purple fist, then the target flashes as a black silhouette,
  once per hit.
- **Gen 6 (XY):** a white flash and a ring with black and yellow dots.
- **Gen 7 (USUM):** a red fist inside a violet spiky burst with blue-violet radial streaks, then a
  purple fist outline.
- **Gen 8 (SwSh):** a grey-white cartoon brawl cloud on the target with black spiky impact stars
  popping out of it.
- **Gen 9 (SV):** a cream-white brawl cloud with black spiky stars (white-gold cores, crimson rims)
  and little yellow sparkle stars popping in succession, then the puffs disperse.

No game shows the party Pokémon. The request asked for them, and the user chose (2026-10-21) to
draw the real teammates as dark afterimages, while the hits keep the official grammar: an impact
star per hit (SwSh / SV), the target darkening per hit (BW2), a dark fist on the finish (Gen 5 / 7).

| Role | Colour |
|---|---|
| pale violet / violet / purple | `#FFE8AEFF`, `#FFB06BFF`, `#FF6A2CA8` |
| deep purple / indigo / near-black | `#FF3A0062`, `#FF2A1B5E`, `#FF1C1030` |
| afterimage body (multiplies the model's texture) | ARGB 0.86, 0.16, 0.09, 0.36 |
| afterimage trail copies | ARGB 0.7, 0.32, 0.18 (alpha 0.3 / 0.18 / 0.09) |
| target flash | ARGB 0.78, 0.08, 0.03, 0.14 |
| brawl dust | dusky lavender grey (0.46, 0.43, 0.5) |

## Choreography (seconds from the start of the move)

Strike *k* (0-based) lands at `S0 + DT × k` = 0.55 + 0.18 *k*; the finish follows the last strike
by 0.08. Six hits finish at 1.53, one hit at 0.63; everything has cleared about 0.45 s later.

| Time | Beat |
|---|---|
| 0.00–0.12 | The user rears back; dark wisps are drawn in from all round, a dark flicker plays over its body. |
| 0.12–0.19 | It snaps forward: dark puffs and violet sparks burst off it, a shadowy ring spreads over the ground at its feet, three flat rings run along the ground towards the target and a few dark streaks shoot at it. |
| 0.21 | The user's own afterimage peels out of its body (Beat Up's first hit is the user's). |
| per strike, from 0.28 s before it | A teammate's afterimage takes shape beside the user in dark mist (a violet ring under it), then rushes in from its own angle (0°, +38°, −38°, +16°, −58°, +58° off the line to the target) with a dark wake and a short trail of copies, running, flying or swimming according to the species. |
| each strike | It lunges into the target leaning forward, while its species' own `physical` animation plays if the model has one; the target darkens for an instant and flinches a little (rolling away from alternate sides); an impact star pops on the face towards the attacker with black shards, violet streaks, dust puffs and two pale twinkles. `impact.dark` plus a punch. |
| 0.04–0.20 after each strike | The afterimage holds the hit, drifts back and dissolves into dark wisps and violet motes. |
| finish (last strike + 0.08) | A dark fist, a bigger star, a black burst tearing into purple scrawls (Shadow Ball's impact sheet), a violet ring, black shards and fast streaks; the target flinches a bit harder. The battle carries on here (HP bar, "Hit *N* times!"). |

**Miss / Protect / no effect** (no hit count): only the user's afterimage rushes in and carries on
past the target's flank, then dissolves; no impact, no flinch. On a real miss the target sidesteps.

## How it works

### Data (like the other moves)

- `data/cobblemon/action_effects/moves/beatup.json` adds the `effects` hold and starts everything in
  one `parallel` (one server tick): the user's animation `actor1`…`actor6` and the target's
  `target1`…`target6`, both picked by `q.hit_count` (a missed move reports none, read as 0), the
  wave and streaks that need the target's position (`entity_particles` with `targetLocators`), and
  the hook `q.user.beat_up_afterimages(q.hit_count, q.target, S0, DT)`. A `pause` whose length is a
  MoLang expression of the hit count then releases the hold at the finish.
- The target's flinches, impacts and sounds live in its own animation, on the client clock in step
  with the afterimages; the animation fires its particles `FX_LEAD` (0.075 s) early so they're on
  the strike frame (particles are born a client tick late).

### Java

- **Server** (`beatup/BeatUpAfterimages.java`): registers the MoLang function on Pokémon entities —
  on Cobblemon 1.8 through `PokemonEntityMoLangFunctions.custom` (reflection), on 1.7 through
  `MoLangFunctions.pokemonEntityFunctions`. When the action effect calls it, it finds the user's
  battle side, takes the party in Showdown's own order from the battle request (active Pokémon
  first), keeps the user plus every member with HP left and no status, trims or repeats that list
  to exactly the reported hit count, and sends `BeatUpPayload` (user, target, hit count, timing,
  species + aspects per strike) to players within 200 blocks who have the mod. The user's own entry
  uses its displayed species, so an Illusion keeps its disguise.
- **Client** (`client/beatup/`): `BeatUpClient` keeps the moves in progress, ticks them and draws
  them after the world's entities; `BeatUpSequence` is one use (timed on client ticks plus partial
  ticks, like the animations it plays beside); `Afterimage` draws one teammate with Cobblemon's own
  model classes — the poser and texture for its species and aspects, a `FloatingState` for its pose
  and animations, the transforms `LivingEntityRenderer` gives a Pokémon, a translucent render layer
  tinted dark purple, full-bright; `TargetFlash` draws the target's current pose again a hair
  larger in near-black for the per-hit flash. Trail, summon and dissolve effects are this mod's own
  Snowstorm particles, spawned at world positions through Cobblemon's `SpawnSnowstormParticleHandler`.
- **Any species:** the afterimage's size is its form's hitbox times its base scale, fitted into
  0.7–2.2 blocks (tiny Pokémon grow at most ×1.8). It stops just touching the target
  (`target radius + 0.9 × its radius + 0.05`) and lunges `0.15 + 0.2 × radius` into it. Anything that
  can walk runs in (a flying pose spreads the wings far too wide), flyers that can't walk fly,
  Pokémon that can't walk or fly swim through the air.
- **Camera:** a player usually watches from just behind their own Pokémon, so a teammate's summoning
  spot slides along the line to the target until it is `2.6 + 1.4 × max(height, width)` blocks from
  this client's camera (at most 45 % of the way). This is per viewer and purely visual.

### Cleanup and failure behaviour

- Every afterimage has a fixed life (0.48 s); a use ends 0.05 s after its last afterimage and is
  dropped on disconnect or a world change. Nothing is spawned in the world, no entity is touched:
  the user and target keep rendering normally the whole time.
- The MoLang hook never throws (an exception there would cut the rest of the timeline short); if it
  isn't registered, Cobblemon reads the call as 0 and the move plays without afterimages.
- On the client, a species whose model fails to draw is skipped from then on; any other error
  (for example a Cobblemon update changing these classes) switches the afterimages off for the
  session with one warning in the log. Either way the JSON part of the move still plays.

## Version notes (1.7.3 vs 1.8.2)

Run on both (2026-10-22): the jar built against 1.7.3 was run with Cobblemon 1.8.2 in the dev client.
That run caught one difference the source check had missed: 1.8 dropped
`PokemonClientDelegate.entityScaleModifier` (its renderer now multiplies `effectiveScale` and
`activeSendoutScale`), so the target flash takes its scale from the entity's height over its form's
hitbox height instead, which holds on both.

Unchanged and used as-is: `PosableModel.render / applyAnimations / setDefault / resetLayerContext`,
`VaryingModelRepository.getPoser / getTexture`, `FloatingState`, `RenderContext`, `PoseType`,
`SpawnSnowstormParticleHandler` and its packet, `PokemonSpecies.getByIdentifier`, `Species.getForm`,
`FormData.baseScale / hitbox / behaviour`, `Pokemon.status / aspects`, `BattleActor.pokemonList /
request`, `ShowdownPokemon.condition / uuid`, `PokemonEntity.battle / exposedSpecies`. Changed:
1.8 moved the per-type MoLang function lists into `AbstractMoLangFunctionHolder` objects (handled
above), and `PokemonGuiUtils.drawProfilePokemon`'s signature (not used).

## Files

| File | What |
|---|---|
| `data/cobblemon/action_effects/moves/beatup.json` | timeline (generated) |
| `assets/cobblemon/bedrock/generic/animations/moves/beatup.animation.json` | `actor1..6`, `target1..6`, `target_miss` (generated) |
| `assets/cobblemon/bedrock/particles/moves/beatup/*.particle.json` | 22 effects (generated) |
| `assets/cobblemon/textures/particle/moves/beatup_star.png` | the impact star, 5 frames (generated) |
| `assets/cobblemon/sounds.json` | `move.beatup.{summon,dash,hit,hit_high,final}` aliases |
| `src/main/java/.../beatup/BeatUpPayload.java`, `BeatUpAfterimages.java` | the packet and the server hook |
| `src/client/java/.../client/beatup/*.java` | `BeatUpClient`, `BeatUpSequence`, `Afterimage`, `TargetFlash` |
| `docs/tools/beatup_gen.py` | regenerates particles, animations and the timeline |
| `docs/tools/beatup_textures.py` | regenerates the impact star |

Reused official assets: `impact_dark` particle, `impact.dark` sound, textures `fire/cloudyfire_white`,
`ring/giantring_white`, `moves/shadowball_impact`, `skyding`, `smallbeam`, `impact/impact_dark`,
`sparkle/glowingsparkle`, `bigfist`, and this mod's `moves/bravebird_glow`.

Sound aliases (official oggs): summon = `shadowball_actor` ×1.3, dash = `quickattack_actor` ×1.25
(played per afterimage by the client, rising a little with each teammate), hit / hit_high =
`pursuit_target` ×1.1 / ×1.3 (alternating), final = `crunch_target` ×0.85.

## Customising

- **Timing:** `S0`, `DT`, `FINAL_GAP`, `REAR`, `THRUST`, `SETTLE` in `docs/tools/beatup_gen.py`
  (re-run it; never hand-edit the outputs). `S0` and `DT` reach the Java side through the hook, so
  the afterimages follow. Within a strike: `MATERIALIZE`, `ARRIVE`, `CONTACT`, `FADE`, `GONE` in
  `Afterimage.java`.
- **Look of the afterimages:** `BODY`, `ECHO`, `ECHO_LAG`, `ECHO_ALPHA`, `APPROACH`, `MAX_HEIGHT`,
  `MIN_HEIGHT` in `Afterimage.java`; the flash in `TargetFlash.java`.
- **Sounds:** aliases of official oggs; to use custom audio drop
  `assets/cobblemon/sounds/move/beatup/beatup_<part>.ogg` and point the `name` fields there.

## Testing

### Steps

1. `./gradlew build` (or `runClient`), open a world with cheats.
2. `/givepokemon weavile level=60 moves=beatup`, plus up to five more party members of different
   shapes (e.g. `pikachu`, `snorlax`, `pidgeot`, `magikarp`).
3. `/spawnpokemonat ~ ~ ~5 shuckle level=100` (it barely takes damage), send out Weavile at it with
   R and use Beat Up: the log says "Hit 6 times!" and six afterimages land one after another, the
   user's own first, then the rest in party order.
4. Give three teammates a status (`/pokemonedit <slot> status=poison`, `paralysis`, `burn`): "Hit 3
   times!" and three afterimages; the statused ones sit out. `/healpokemon` clears them.
5. A wild user: `/spawnpokemonat ~ ~ ~5 weavile level=30 moves=beatup`, battle it with a sturdy
   Pokémon using a status move until it picks Beat Up: one hit, its own afterimage.
6. Protect: `/spawnpokemonat ~ ~ ~5 shuckle level=100 moves=protect`; when it protects, one
   afterimage rushes past and nothing hits.
7. Check the log: there should be no "Beat Up" warnings.

### Results (dev client, Cobblemon 1.7.3, 2026-10-21/22)

Headless gamescope rig on a floating platform, recorded through gamescope's PipeWire node, from
behind the user (the normal battle camera) and from the side:

- Weavile + Incineroar, Pikachu, Snorlax, Pidgeot, Magikarp vs a Lv 100 Blastoise and a Lv 100
  Shuckle: "Hit 6 times!", six afterimages in Showdown's order, impacts and flinch per hit, the
  finish, everything gone afterwards.
- The same party with three statused members: "Hit 3 times!", three afterimages.
- A wild Weavile using it on the player's Snorlax: "Hit 1 time!", its own afterimage, the flash
  visible on Snorlax.
- Into Shuckle's Protect: one afterimage whiffs past, no hit effects.
- Our Hydro Pump played normally in the same battles; no warnings from the mod in the log.

- Cobblemon 1.8.2 (the 1.7.3-built mod, dev world backed up first): the 1.8 MoLang hook registers,
  "Hit 6 times!" with all six afterimages and the hit effects, no warnings after the flash fix above.

Not tested in-game: an NPC trainer using Beat Up (same code path as a player's side).
