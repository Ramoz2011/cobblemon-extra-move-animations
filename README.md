# Cobblemon: Extra Move Animations

A [Fabric](https://fabricmc.net/) mod that adds custom battle animations, particle
effects, and sound design to [Cobblemon](https://cobblemon.com/) for fourteen moves
the base mod doesn't animate yet.

![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)
![Minecraft 1.21.1](https://img.shields.io/badge/minecraft-1.21.1-brightgreen.svg)
![Fabric](https://img.shields.io/badge/modloader-Fabric-dbb69d.svg)

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

## How it works

Cobblemon's move animations are entirely data-driven, so this mod ships **no
custom gameplay Java** — every effect is defined declaratively:

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

Because everything is JSON, the mod loads its effects straight into
Cobblemon's existing systems with no mixins into gameplay logic — the Java
side only exists for the standard Fabric mod entrypoints.

## Requirements

- Minecraft 1.21.1
- [Fabric Loader](https://fabricmc.net/) ≥ 0.19.3
- [Fabric API](https://modrinth.com/mod/fabric-api)
- [Fabric Language Kotlin](https://modrinth.com/mod/fabric-language-kotlin)
- [Cobblemon](https://modrinth.com/mod/cobblemon) ≥ 1.7.3

## Installation

1. Install [Fabric Loader](https://fabricmc.net/use/) for Minecraft 1.21.1.
2. Download and place in your `mods` folder: Fabric API, Fabric Language
   Kotlin, Cobblemon, and this mod's jar.
3. Launch the game.

**Playing on a server?** Install the mod on the server as well as on every
player's client. Cobblemon runs move animations on the server, so if the mod
is only on your client, nothing will show up.

## Building from source

```sh
./gradlew build
```

The built jar is output to `build/libs/`.

## License

[MIT](LICENSE.txt)

## Disclaimer

This is unofficial fan-made content for Cobblemon and is not affiliated with
or endorsed by the Cobblemon team, Game Freak, Nintendo, Creatures Inc., or
The Pokémon Company.
