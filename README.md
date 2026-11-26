# Cobblemon: Extra Move Animations

A mod for [Fabric](https://fabricmc.net/) and [NeoForge](https://neoforged.net/)
that adds custom battle animations, particle effects, and sound design to
[Cobblemon](https://cobblemon.com/) for twenty moves the base mod doesn't
animate yet.

![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)
![Minecraft 1.21.1](https://img.shields.io/badge/minecraft-1.21.1-brightgreen.svg)
![Fabric](https://img.shields.io/badge/modloader-Fabric-dbb69d.svg)
![NeoForge](https://img.shields.io/badge/modloader-NeoForge-e68c37.svg)

## This mod's animation or Cobblemon's

Each move can play either this mod's animation or Cobblemon's. Cobblemon 1.8
and later animate Hydro Pump and Draco Meteor themselves; for the other moves,
"Cobblemon" means its generic move animation. Every move starts on this mod's
animation.

To switch, open Cobblemon's settings (type `/cobblemonconfig`, or on Fabric
use **Mods → Cobblemon → Configure** with [Mod Menu](https://modrinth.com/mod/modmenu))
and click **Extra Move Animations...** next to Done. Click a move to flip it
between **This mod** and **Cobblemon**; the change applies when you close the
screen.

On a multiplayer server the server decides for everyone, so the screen only
shows its choices. Server owners set them in the server's
`config/cobblemon_extra_move_animation.json` and then run `/reload`:

```json
{
  "dracometeor": "this_mod",
  "hydropump": "cobblemon"
}
```

## Moves

| Move | Type | Description |
|---|---|---|
| **U-turn** | Bug | The user darts to the target and cuts back before switching out. |
| **Moonblast** | Fairy | A charged lunar orb collapses into a beam of moonlight. |
| **Hyper Beam** | Normal | A charged orb fires a sustained high-energy beam. |
| **Hydro Pump** | Water | A charged jet blasts a volley of pressurized water. |
| **Volt Switch** | Electric | A spinning ring of electricity volleys into the target before the user switches out. |
| **Draco Meteor** | Dragon | A skyward orb calls down a rain of draconic meteors. |
| **Earthquake** | Ground | A ground-slam sends a shattering ring of rock across the field. |
| **Solar Beam** | Grass | A two-turn charge gathers sunlight before releasing a beam of solar energy. |
| **Knock Off** | Dark | A dark, purple-tinged strike knocks the target's held item loose. |
| **Make It Rain** | Steel | A hoard of gold is hurled skyward, then pours back down through a golden void as a torrent of coins. |
| **Triple Axel** | Ice | An axel spin into three rapid slashes, each releasing a crescent of ice that carves a glowing X and a vertical gash. |
| **Darkest Lariat** | Dark | Crimson orbs ignite at each fist as the user spins into the target, scattering black-and-red shards on impact. |
| **Focus Blast** | Fighting | Focused energy forms a white-hot orb with a cyan halo, which the user hurls at the target. |
| **Brave Bird** | Flying | The user dives low in a bird of cyan light and crashes into the target, then recoil sparks crackle over it. |
| **Flare Blitz** | Fire | Flame streams pour into the user until it flares white-hot, then it charges as a fireball wrapped in spiralling rings of fire and explodes on the target in flame and black smoke. |
| **Beat Up** | Dark | Dark afterimages of the user and its real teammates, drawn with their own models, strike one after another: one per hit, so fainted or statused teammates sit it out. |
| **Counter** | Fighting | The user braces to absorb the blow, its body flushes red-orange, and it strikes back with a white-hot burst of orange sparks. |
| **Bitter Blade** | Fire | Blue ghost flames engulf the user as its blades glow hot pink, it spins into a slash that cuts the target in white light, and a mint-green orb of drained energy flies back to heal it. |
| **Muddy Water** | Water | A crown of muddy water rises around the user and rolls out as a wave that crashes over every foe; a murky haze clings to a foe only when its accuracy really falls. |
| **Moonlight** | Fairy | A full moon rises above the user and pours a column of moonlight onto it, shining brighter in harsh sunlight and softer in bad weather, before a mint heal burst restores its HP. |

## How it works

Cobblemon's move animations are data-driven, so almost every effect in this
mod is defined declaratively:

- `data/cobblemon/action_effects/moves/<move>.json` — a keyframe timeline
  (animations, particle spawns, sounds, pauses) driven by Cobblemon's own
  action-effect system.
- `assets/cobblemon/bedrock/particles/moves/<move>/*.particle.json` —
  Bedrock/Snowstorm-format particle effects (volumetric shapes, emitter-age
  trails, target-relative motion, parametric curves).
- `assets/cobblemon/bedrock/generic/animations/moves/<move>.animation.json` —
  stateful actor animations (e.g. charge poses) referenced from the timeline.
- `assets/cobblemon/sounds.json` — sound events, largely aliased from
  existing official Cobblemon move audio rather than new recordings.
- `assets/cobblemon/textures/particle/moves/*.png` — the handful of custom
  sprite sheets the official atlas doesn't cover; the generators for these
  live in `docs/tools/`.

Some moves need something the JSON system can't do, so they add a small
amount of client-side rendering in Java:

- **Beat Up** draws the user's real teammates, with their own Cobblemon
  models, as dark afterimages, and darkens the target's model on each hit.
- **Counter** tints the user's model red-orange as it turns the blow around,
  and flashes the target's model orange on impact. **Bitter Blade** tints the
  user mint as the drained energy reaches it, and **Moonlight** bathes it in
  white-blue light.
- **Muddy Water** draws its wave as a 3D sheet of water that rises around
  the user and rolls out over every foe.

The move's normal action-effect timeline calls a MoLang function, and the
server then tells nearby clients what to draw with a small custom packet.

Two moves also read what the battle has already decided, so the animation
can follow it. Muddy Water's murky haze only shows on a foe whose accuracy
really fell, and in a double battle a foe it misses hops aside. Moonlight
shines brighter in harsh sunlight and softer in rain, sand, hail or snow,
matching how much HP it restores. They only read the battle and never
change it.

A little more Java lets players choose between this mod's animation and
Cobblemon's for each move (see above). Once Cobblemon has loaded its action
effects, it puts the chosen version of each move in place, and it adds the
button that opens the choice to Cobblemon's settings screen.

There are still no mixins and no changes to battle logic: damage, accuracy
and hit counts all stay Cobblemon's. If a future Cobblemon update breaks the
Java side, only those extras and the choice switch off, and every move keeps
this mod's particle animation.

The Fabric and NeoForge versions are built from the same code and the same
animation files. Only a thin layer that hooks into each loader's events
differs: the `fabric` packages in `src/`, and the `neoforge/` folder.

## Requirements

- Minecraft 1.21.1
- [Cobblemon](https://modrinth.com/mod/cobblemon) 1.7.3 or newer (tested up to 1.8.4)
- On Fabric: [Fabric Loader](https://fabricmc.net/) ≥ 0.19.3,
  [Fabric API](https://modrinth.com/mod/fabric-api) and
  [Fabric Language Kotlin](https://modrinth.com/mod/fabric-language-kotlin)
- On NeoForge: [NeoForge](https://neoforged.net/) 21.1 and
  [Kotlin for Forge](https://modrinth.com/mod/kotlin-for-forge), which
  Cobblemon needs anyway

## Installation

1. Install [Fabric Loader](https://fabricmc.net/use/) or
   [NeoForge](https://neoforged.net/) for Minecraft 1.21.1.
2. Download and place in your `mods` folder: Cobblemon and what it needs on
   your loader, and this mod's jar for your loader (the `fabric` or the
   `neoforge` one).
3. Launch the game.

**Playing on a server?** Install the mod on the server as well as on every
player's client. Cobblemon runs move animations on the server, so if the mod
is only on your client, nothing will show up.

## Building from source

```sh
./gradlew build                  # Fabric jar, in build/libs/
cd neoforge && ./gradlew build   # NeoForge jar, in neoforge/build/libs/
```

## License

[MIT](LICENSE.txt)

## Disclaimer

This is unofficial fan-made content for Cobblemon and is not affiliated with
or endorsed by the Cobblemon team, Game Freak, Nintendo, Creatures Inc., or
The Pokémon Company.
