# Draco Meteor — AI Asset Generation Prompts & Integration Notes

The move works out of the box using official Cobblemon 1.7.3 textures and aliased
official sounds. The prompts below are for the optional custom-asset upgrade pass.

## 1. Texture sheet prompt (Midjourney / DALL-E)

> Sprite sheet for a video game particle effect, pixel-art style, 2D game VFX
> texture atlas on a fully transparent background (alpha channel PNG). Subject:
> dragon-energy meteor and trail. Layout: a single horizontal strip of 8 frames,
> each frame 32x32 pixels (final sheet 256x32). Frames 1-4: a glowing comet orb
> with a white-hot core, orange molten mantle, and violet-magenta plasma aura,
> progressively elongating with a wispy trailing tail. Frames 5-8: the trail
> dissolving into curling indigo-purple smoke wisps and small violet sparkles.
> Colors: #FFFFFF core, #FF9A3C fire, #C77DFF and #7038F8 dragon energy, deep
> #4C1D95 smoke. Crisp edges, no background, no glow bleed outside each frame,
> centered per frame, game-ready billboard particle texture, orthographic,
> flat lighting.

Post-process before use: quantize to a small palette, verify true transparency
(no white matte), and confirm final size 256x32.

Wire-up: save as
`assets/cobblemon/textures/particle/moves/dracometeor_meteor.png`, then in
`dracometeor_rain.particle.json` set `"texture":
"textures/particles/moves/dracometeor_meteor"` and change the billboard `uv`
block to `texture_width: 256, texture_height: 32`, flipbook `size_UV: [32,32]`,
`step_UV: [32,0]`, `max_frame: 8`, `stretch_to_lifetime: true`, and drop the
tint gradient to `#FFFFFFFF` (the sheet is pre-colored).

## 2. Sound prompt (ElevenLabs SFX)

Generate three clips (they map to the three sound events):

1. **dracometeor_charge.ogg (~1.4 s):** "A deep, guttural dragon roar charging
   up: low sub-bass rumble swelling in intensity, layered with a rising
   crystalline energy shimmer, building tension, ends abruptly at the peak.
   Cinematic fantasy creature SFX, no music."
2. **dracometeor_actor.ogg (~1.0 s):** "A ferocious dragon roar bursting into a
   powerful skyward projectile launch: a heavy whoosh sweeping upward with a
   doppler rise, trailing crackling energy sparkles. Cinematic game SFX, no
   music."
3. **dracometeor_target.ogg (~1.6 s):** "Multiple heavy explosive meteor
   impacts in quick succession: deep concussive booms with ground-shaking
   sub-bass shockwaves, debris scatter, and a fading rumble tail. Cinematic
   fantasy battle SFX, no music."

Convert to mono Ogg Vorbis (e.g. `ffmpeg -i in.wav -ac 1 -c:a libvorbis -q:a 4 out.ogg`),
place at `assets/cobblemon/sounds/move/dracometeor/dracometeor_{charge,actor,target}.ogg`,
then in `assets/cobblemon/sounds.json` swap the three `move.dracometeor.*`
alias `name` fields to `cobblemon:move/dracometeor/dracometeor_{charge,actor,target}`
and remove the pitch overrides. No other file changes needed.

## 3. File layout

```
src/main/resources/
├── assets/cobblemon/
│   ├── bedrock/
│   │   ├── generic/animations/moves/dracometeor.animation.json
│   │   └── particles/moves/dracometeor/
│   │       ├── dracometeor_charge.particle.json
│   │       ├── dracometeor_chargeorb.particle.json
│   │       ├── dracometeor_orb.particle.json
│   │       ├── dracometeor_orbtrail.particle.json
│   │       ├── dracometeor_skyburst.particle.json
│   │       ├── dracometeor_rain.particle.json
│   │       ├── dracometeor_rainsmoke.particle.json
│   │       ├── dracometeor_impactburst.particle.json
│   │       ├── dracometeor_targetring.particle.json
│   │       └── dracometeor_targetsparks.particle.json
│   ├── sounds.json                          (merged; adds move.dracometeor.*)
│   ├── sounds/move/dracometeor/*.ogg        (optional custom audio, see §2)
│   └── textures/particle/moves/dracometeor_meteor.png  (optional, see §1)
└── data/cobblemon/action_effects/moves/dracometeor.json
```

## 4. Timeline cheat sheet (absolute battle time ≈ anim time + 0.1 s)

| Time (anim) | Event |
|---|---|
| 0.00–1.15 | Charge: rear-back tilt to −26°, shiver, inward violet sparkles + pulsing orb |
| 1.20 | Launch: snap to −40°, body thrusts up; orb + live trail rise ~8.6 blocks in 0.36 s (accel 55/s²) |
| 1.54 | Sky burst 9 blocks up (meteor split) |
| 1.75 | Meteor rain + smoke spawn over target (box emitter, 8.5 blocks up, expire on ground contact) |
| 2.20 | Impact 1: impact.dragon + burst + shockring + sparks |
| 2.38 | Impact 2: small (impact_dragon + sparks) |
| 2.56 | Impact 3: impact.dragon + burst + sparks |
| 2.74 | Impact 4 (final): move.dracometeor.target + burst + shockring + sparks |
