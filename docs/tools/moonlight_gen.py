"""Generates Moonlight's particle effects, generic animation file and action effect.

Outputs (paths relative to the repo root):
  src/main/resources/assets/cobblemon/bedrock/particles/moves/moonlight/*.particle.json
  src/main/resources/assets/cobblemon/bedrock/generic/animations/moves/moonlight.animation.json
  src/main/resources/data/cobblemon/action_effects/moves/moonlight.json
  src/main/resources/assets/cobblemon/sounds.json  (only its move.moonlight.* entries)

Edit the constants below and re-run `python3 docs/tools/moonlight_gen.py`; don't hand-edit the outputs.
The three custom sprites come from docs/tools/moonlight_textures.py. Design notes, the game reference and
the reasoning behind the numbers: docs/moonlight_assets.md.

How the pieces fit:
- The look follows Sword/Shield and Scarlet/Violet: a grey full moon with darker maria fades in above and
  slightly behind the user, a blue halo and expanding blue rings pulse round it, a soft column of moonlight
  comes down on the user, who stands in a swirling blue-violet circle of light while streaks rise and motes
  fall, then glows as light ribbons spiral round it and rings of light spread out; the games' mint heal
  burst plays as the HP bar rises, the light flares once and everything fades.
- Everything is fired by the user's own animation at T0 (while root_part is still at rest, so every
  emitter's frame is level and faces the foe) and runs on the client clock. Each layer is path-locked: one
  burst, parametric positions, each particle shown only in its own time window. Moonlight targets its
  user, so Cobblemon hands the user to the action effect twice (as user and as target); entity_particles
  keyframes would send every effect twice, the animation (started by entity_molang on q.entity.is_user,
  which tells the two apart) plays once.
- Every layer is born at T0 and keeps that tick's frame, so the sky and ground layers (moon, column,
  circle, motes) stay put while the body floats up and settles; the body's own layers (aura, ribbons,
  rings, heal burst) add the root_part float (curves fy/fz) so they ride it.
- Draw order is spawn order and translucent particles write depth (see DRAW_ORDER). Quads
  that face the camera through the same point are coplanar and z-fight (in-game the moon blinked out
  behind a separate halo glow), so the moon's glow is part of the moon sprite, and the rings round it sit
  0.04 below its centre: battle cameras look up at the moon, so that puts them a hair in front of it.
- Weather changes how much HP Moonlight restores (2/3 in harsh sunlight, 1/4 in rain, sand, hail or snow,
  1/2 otherwise). The action effect asks the battle how much this heal was worth (Java hook
  q.user.move_heal_share, docs in battle/MoveHeal.java) and plays one of four versions of the same
  animation: actor_bright (sun), actor (normal, also used whenever the hook can't tell), actor_soft
  (rain and the like) or actor_fail (HP already full: the moon peeks out and fades, nothing heals). The
  versions only differ in v.lum / v.dens, set per effect by pre_effect_script.
- The battle restores the HP when the action effect releases its "effects" hold, so the timeline
  releases it at HEAL, when the mint heal burst plays.
"""
import json, math, os, sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..')
RES = os.path.join(ROOT, 'src/main/resources')
PART_DIR = os.path.join(RES, 'assets/cobblemon/bedrock/particles/moves/moonlight')
ANIM_OUT = os.path.join(RES, 'assets/cobblemon/bedrock/generic/animations/moves/moonlight.animation.json')
EFFECT_OUT = os.path.join(RES, 'data/cobblemon/action_effects/moves/moonlight.json')
SOUNDS = os.path.join(RES, 'assets/cobblemon/sounds.json')

# ---------------------------------------------------------------- timing (seconds from the start of the move)
T0 = 0.02            # the user's particles fire here, while root_part is still at rest
PARTICLE_LAG = 0.175 # path-locked particles fired by an animation: their age 0 shows at T0 + this
T_IN = T0 + PARTICLE_LAG
LOOK = 0.42          # the user has turned its face up to the sky
# 1. the moon
MOON0, MOON1 = 0.22, 0.82          # it fades in (and drifts down a touch)
STARS0, STARS1 = 0.40, 2.20        # stars twinkle round it
RING_T = (0.80, 0.98, 1.16)        # blue rings pulse out of it
# 2. the moonlight comes down
BEAM0, BEAM1 = 0.98, 1.30          # the column grows from the moon to the ground
GROUND0 = 1.20                     # the circle of light lights up under the user
MOTES0, MOTES1 = 1.05, 1.95        # motes drift down the column (start times)
# 3. healing
GLOW0, GLOW_FULL = 1.38, 1.68      # the user's glow and aura rise
ORBIT0, ORBIT1 = 1.42, 2.24        # light ribbons spiral up round the body
ORBIT_OUT = 2.02                   # ... and fade from here
HEAL_RINGS = (1.58, 1.80, 2.02)    # rings of light spread out from the body
# 4. completion
HEAL = 2.06          # the battle restores the HP here; the mint heal burst and the light's last flare
FADE0, FADE1 = 2.16, 2.56          # the column, the circle and the aura fade
MOON_OUT0, MOON_OUT1 = 2.24, 2.76  # the moon fades last
SETTLE = 2.70        # the body is back at rest
ACTOR_LEN = 2.80
END = 2.86           # the action effect ends (the next move waits for this)
# HP already full: the short version
FAIL_IN, FAIL_HOLD, FAIL_OUT = 0.22, 0.44, 0.84
FAIL_LEN = 0.95
CURVE_END = 2.90     # envelope curves cover anim time 0 .. this

# ---------------------------------------------------------------- weather versions (set per effect by pre_effect_script)
VARIANTS = {
    'actor_bright': (1.3, 1.0),   # harsh sunlight: brighter light, every sparkle
    'actor': (1.0, 0.8),          # no weather (or the hook couldn't tell)
    'actor_soft': (0.68, 0.55),   # rain, sandstorm, hail, snow: softer light, fewer sparkles
}

# ---------------------------------------------------------------- palette (r, g, b in 0..1)
MOON_TINT = (0.94, 0.97, 1.0)       # silver; the texture is grey-blue
BEAM = (0.74, 0.86, 1.0)            # the column: silver-blue, whiter in its core (texture)
GROUND = (0.8, 0.84, 1.0)           # pale blue-violet pool of light (light enough to brighten the grass)
SWIRL = (0.6, 0.9, 1.0)             # cyan swirl
AURA = (0.74, 0.87, 1.0)            # white-blue aura
LAVENDER = (0.72, 0.68, 1.0)
PINK_STREAK = (1.0, 0.78, 0.96)     # SwSh's rising streaks are partly pink
MINT = (0.62, 1.0, 0.78)            # the games' heal burst
TINT = (0.72, 0.85, 1.0)            # the user's glow (Java model tint)


# ================================================================= helpers
def t(x):
    s = f"{x:.4f}".rstrip('0').rstrip('.')
    return s if '.' in s else s + '.0'


def r(x, n=4):
    v = round(x, n)
    return 0 if v == 0 else v


def clamp(v, a, b):
    return max(a, min(b, v))


def smooth(x):
    x = clamp(x, 0.0, 1.0)
    return x * x * (3 - 2 * x)


def ease_out(x, p=2.0):
    return 1 - (1 - clamp(x, 0.0, 1.0)) ** p


def ease_in(x, p=2.0):
    return clamp(x, 0.0, 1.0) ** p


EASES = {'s': smooth, 'o': ease_out, 'i': ease_in, 'l': lambda x: clamp(x, 0.0, 1.0)}


def keyed(points):
    """[(time, value or tuple, ease)] -> fn(time) -> list; `ease` shapes the segment ending at that point."""
    pts = [(p[0], list(p[1]) if isinstance(p[1], (tuple, list)) else [p[1]], p[2] if len(p) > 2 else 's') for p in points]

    def fn(x):
        if x <= pts[0][0]:
            return list(pts[0][1])
        for (a, va, _), (b, vb, e) in zip(pts, pts[1:]):
            if x <= b:
                k = EASES[e]((x - a) / (b - a))
                return [va[i] + (vb[i] - va[i]) * k for i in range(len(va))]
        return list(pts[-1][1])
    return fn


def band(x, a, rise, b, fall):
    """0 before a, eases to 1 over `rise`, holds, eases back to 0 over `fall` ending at b."""
    return smooth((x - a) / rise) * (1 - smooth((x - (b - fall)) / fall))


def bump(x, at, rise, fall):
    """A pulse: 0 -> 1 over `rise` up to `at`, back to 0 over `fall`."""
    if x <= at:
        return smooth((x - (at - rise)) / rise)
    return 1 - smooth((x - at) / fall)


def tex(path, w, h):
    return f"textures/particles/{path}", w, h


T_MOON = tex('moves/moonlight_moon', 128, 128)        # the moon (61 px disc) with its glow baked in
T_COLUMN = tex('moves/moonlight_column', 64, 32)
T_SWIRL = tex('moves/moonlight_swirl', 512, 64)          # 8 frames 64x64, left to right
T_GLOW = tex('moves/bravebird_glow', 32, 32)             # round soft glow (docs/tools/bravebird_textures.py)
T_SPARK = tex('generic/sparkle/glowingsparkle', 8, 32)   # 4 frames 8x8 top to bottom: big star .. dot
T_TWINKLE = tex('generic/skyding', 275, 25)              # 11 frames 25x25: a four-point star twinkling
T_RING = tex('moves/moonlight_ring', 64, 64)             # a soft cyan band edged violet, radius 0.78
T_BEAM = tex('generic/smallbeam', 140, 91)

UV_FULL_MOON = {"uv": [0, 0], "uv_size": [128, 128]}
MOON_SPRITE = 64 / 30.5                            # half the sprite / the disc radius (moonlight_textures.py)
UV_COLUMN = {"uv": [0, 0], "uv_size": [64, 32]}
UV_GLOW = {"uv": [0, 0], "uv_size": [32, 32]}
UV_BEAM = {"uv": [70, 42], "uv_size": [70, 7]}    # right half of one smallbeam frame: a soft streak
UV_RING = {"uv": [0, 0], "uv_size": [64, 64]}
RING_FRAC = 0.78                                   # moonlight_ring: band radius / half the sprite
SWIRL_RIM = 0.955                                  # moonlight_swirl: rim radius / half the frame
UP = ["0", "1", "0"]                               # custom view direction: a vertical lookat_direction quad


def W(blocks):
    """Billboard `size` for a quad `blocks` wide: Cobblemon draws size / 1.5 either side of the centre."""
    return r(0.75 * blocks, 4)


def frame_uv(index, fw, fh, horizontal=True):
    """Static UV of frame `index` (a MoLang expression) of a sheet laid out left-to-right or top-to-bottom."""
    return {"uv": [f"{fw} * ({index})", 0] if horizontal else [0, f"{fh} * ({index})"], "uv_size": [fw, fh]}


def frames(k, count):
    """Frame index for a 0..1 progress over `count` frames."""
    return f"math.floor(math.clamp({k}, 0, 0.999) * {count})"


def particle(pid, texture, components, uv, size, camera="rotate_xyz", tinting=None, curves=None, direction=None):
    path, tw, th = texture
    bb = {"size": size, "facing_camera_mode": camera, "uv": dict({"texture_width": tw, "texture_height": th}, **uv)}
    if direction is not None:
        bb["direction"] = {"mode": "custom", "custom_direction": direction}
    comps = dict(components)
    comps["minecraft:particle_appearance_billboard"] = bb
    if tinting is not None:
        comps["minecraft:particle_appearance_tinting"] = tinting
    pe = {"description": {"identifier": f"cobblemon:{pid}",
                          "basic_render_parameters": {"material": "particles_blend", "texture": path}}}
    if curves:
        pe["curves"] = curves
    pe["components"] = comps
    return {"format_version": "1.10.0", "particle_effect": pe}


SINPHI = "math.sqrt(1 - math.pow(2 * v.particle_random_2 - 1, 2))"
COSPHI = "(2 * v.particle_random_2 - 1)"


def sphere_dir(theta="(360 * v.particle_random_1)"):
    return (f"{SINPHI} * math.cos({theta})", COSPHI, f"{SINPHI} * math.sin({theta})")


ENTITY_DEFAULTS = "v.entity_width = 1; v.entity_height = 1;"
SC = "((q.entity_scale > 0 ? q.entity_scale : 1) / 16)"
GEOM = [
    "v.bw = math.clamp(v.entity_width, 0.3, 3.0)",                 # body width (blocks)
    "v.bh = math.clamp(v.entity_height, 0.3, 4.2)",                # body height
    "v.bl = math.clamp(math.max(v.bw, v.bh), 0.5, 3.0)",           # body size
    "v.fs = math.clamp(0.45 + 0.5 * v.bl, 0.7, 1.9)",              # effect scale: grows slowly with the body
    "v.lu = v.lum > 0 ? v.lum : 1",                                # brightness of this version
    "v.dn = v.dens > 0 ? v.dens : 0.8",                            # share of the optional sparkles shown
    "v.mr = math.clamp(0.5 + 0.24 * v.bl, 0.62, 1.2)",             # moon radius
    "v.my = 1.1 * v.bh + 0.6 + v.mr + 0.12 * v.bl",                # moon centre height (models often top their hitbox)
    "v.mz = 0.15 + 0.1 * v.bl",                                    # ... slightly behind the user (+z)
    "v.cr = math.clamp(0.72 * v.bw + 0.4, 0.75, 2.0)",             # radius of the column of light
    "v.ct = v.my - 0.25 * v.mr",                                   # its top, inside the moon's lower half
    "v.or = 0.5 * v.bw + 0.3",                                     # radius the light ribbons orbit at
    "v.rr = math.max(0.55 * v.bl, 0.4) + 0.08",                    # a ball just outside the body
    "v.cy = 0.5 * v.bh",                                           # body centre height
    f"v.sc = {SC}",                                                # model units -> blocks
    f"v.tt = v.particle_age + {r(T_IN)}",                          # animation time this particle is showing
]
K = "(v.particle_age / v.particle_lifetime)"


def gate():
    """1 for the share v.dn of a layer's particles, 0 for the rest (fewer sparkles in a softer version)."""
    return "(math.mod(v.particle_random_1 * 17.31 + v.particle_random_3 * 5.77, 1) < v.dn ? 1 : 0)"


def window(since, life, fade_in=0.03):
    """1 while 0 <= since < life (soft edges), else 0."""
    return f"math.clamp(({since}) / {fade_in}, 0, 1) * math.clamp(({life} - ({since})) * 40, 0, 1)"


def locked(count, end_time, pos, update=(), start=T_IN):
    """Path-locked layer fired by an animation at T0: every particle spawned at once, positioned by the
    parametric motion and shown only in its own time window (sizes go to 0 outside it)."""
    return {
        "minecraft:emitter_initialization": {"creation_expression": ENTITY_DEFAULTS},
        "minecraft:emitter_rate_instant": {"num_particles": count},
        "minecraft:emitter_lifetime_once": {"active_time": 0.1},
        "minecraft:emitter_shape_point": {},
        "minecraft:particle_initialization": {"per_update_expression": ";".join(GEOM + list(update)) + ";"},
        "minecraft:particle_lifetime_expression": {"max_lifetime": r(end_time - start)},
        "minecraft:particle_initial_speed": 0,
        "minecraft:particle_motion_parametric": {"relative_position": pos},
    }


# ================================================================= the user's motion
# root_part position in model units (+y up, +z back), rotation in degrees (-x = lean back), scale.
# It looks up to the moon and rises a little, breathes and sways in the light, floats up as it heals,
# stretches as the HP comes back, then drops back into its stance with a small bounce.
ROOT_BASE = keyed([(0, (0, 0, 0)), (0.06, (0, 0, 0)), (LOOK, (0, 1.4, 0.35), 'o'), (1.30, (0, 1.9, 0.35)),
                   (1.95, (0, 3.0, 0.2)), (HEAL, (0, 3.2, 0.2)), (2.30, (0, 2.0, 0.1)), (2.52, (0, -0.35, 0), 'i'),
                   (2.66, (0, 0.2, 0)), (SETTLE, (0, 0, 0)), (ACTOR_LEN, (0, 0, 0))])


def root_pos(x):
    p = ROOT_BASE(x)
    p[1] += 0.35 * math.sin(2 * math.pi * 1.1 * (x - LOOK)) * band(x, LOOK, 0.25, HEAL - 0.06, 0.25)
    return p


ROOT_ROT_BASE = keyed([(0, (0, 0, 0)), (0.06, (0, 0, 0)), (LOOK, (-7, 0, 0), 'o'), (1.30, (-6, 0, 0)), (1.95, (-4, 0, 0)),
                       (HEAL, (-3, 0, 0)), (2.36, (0, 0, 0)), (ACTOR_LEN, (0, 0, 0))])


def root_rot(x):
    p = ROOT_ROT_BASE(x)
    p[2] += 1.6 * math.sin(2 * math.pi * 0.6 * (x - LOOK)) * band(x, LOOK, 0.3, HEAL + 0.1, 0.35)
    return p


ROOT_SCALE = keyed([(0, (1, 1, 1)), (HEAL - 0.08, (1, 1, 1)), (HEAL + 0.04, (0.97, 1.05, 0.97), 'o'),
                    (HEAL + 0.18, (1.01, 0.99, 1.01)), (HEAL + 0.32, (1, 1, 1)), (ACTOR_LEN, (1, 1, 1))])
HEAD = keyed([(0, (0, 0, 0)), (0.08, (0, 0, 0)), (LOOK, (-14, 0, 0), 'o'), (1.30, (-12, 0, 0)), (1.95, (-9, 0, 0)),
              (HEAL, (-6, 0, 0)), (2.36, (0, 0, 0)), (ACTOR_LEN, (0, 0, 0))])
FAIL_ROOT = keyed([(0, (0, 0, 0)), (0.06, (0, 0, 0)), (0.32, (0, 0.8, 0.2), 'o'), (0.56, (0, 0.8, 0.2)), (0.86, (0, 0, 0)),
                   (FAIL_LEN, (0, 0, 0))])
FAIL_ROT = keyed([(0, (0, 0, 0)), (0.06, (0, 0, 0)), (0.32, (-4, 0, 0), 'o'), (0.56, (-4, 0, 0)), (0.86, (0, 0, 0)),
                  (FAIL_LEN, (0, 0, 0))])
FAIL_HEAD = keyed([(0, (0, 0, 0)), (0.08, (0, 0, 0)), (0.32, (-12, 0, 0), 'o'), (0.58, (-12, 0, 0)), (0.88, (0, 0, 0)),
                   (FAIL_LEN, (0, 0, 0))])


# ================================================================= envelope curves (anim time -> value)
CURVE_STEP = 0.05


def time_curve(fn, end=CURVE_END, step=CURVE_STEP):
    n = int(round(end / step)) + 1
    return {"type": "linear", "input": f"v.particle_age + {r(T_IN)}", "horizontal_range": r(end),
            "nodes": [r(fn(i * end / (n - 1)), 4) for i in range(n)]}


def moon_grow(x):
    return smooth((x - MOON0) / (MOON1 - MOON0))


def moon_env(x):
    return moon_grow(x) * (1 - smooth((x - MOON_OUT0) / (MOON_OUT1 - MOON_OUT0)))


def halo_pulse(x):
    return sum(bump(x, at + 0.06, 0.08, 0.3) for at in RING_T)


def ground_env(x):
    return smooth((x - GROUND0) / 0.22) * (1 - smooth((x - FADE0) / (FADE1 - FADE0)))


def beam_grow(x):
    return ease_out((x - BEAM0) / (BEAM1 - BEAM0), 2.2)


def beam_env(x):
    """The column's brightness: up as it comes down, a last flare as the HP comes back, then gone."""
    return smooth((x - BEAM0) / 0.25) * (1 + 0.5 * bump(x, HEAL, 0.12, 0.2)) * (1 - smooth((x - FADE0) / (FADE1 - FADE0)))


def aura_env(x):
    return smooth((x - GLOW0) / (GLOW_FULL - GLOW0)) * (1 + 0.5 * bump(x, HEAL, 0.08, 0.2)) \
        * (1 - smooth((x - FADE0) / (FADE1 - FADE0 + 0.05)))


def orbit_env(x):
    return smooth((x - ORBIT0) / 0.15) * (1 - smooth((x - ORBIT_OUT) / (ORBIT1 - ORBIT_OUT)))


def fail_env(x):
    return smooth((x - FAIL_IN) / (FAIL_HOLD - FAIL_IN)) * (1 - smooth((x - FAIL_HOLD - 0.08) / (FAIL_OUT - FAIL_HOLD - 0.08)))


def curves(*names):
    table = {
        'fy': lambda: time_curve(lambda x: root_pos(x)[1], ACTOR_LEN),
        'fz': lambda: time_curve(lambda x: root_pos(x)[2], ACTOR_LEN),
        'mgro': lambda: time_curve(moon_grow),
        'menv': lambda: time_curve(moon_env),
        'hpul': lambda: time_curve(halo_pulse),
        'genv': lambda: time_curve(ground_env),
        'bgro': lambda: time_curve(beam_grow),
        'benv': lambda: time_curve(beam_env),
        'aenv': lambda: time_curve(aura_env),
        'oenv': lambda: time_curve(orbit_env),
        'fenv': lambda: time_curve(fail_env, 1.0, 0.025),
    }
    return {f"variable.{n}": table[n]() for n in names}


# Particles that aren't in emitter-local space keep the emitter's frame from the tick they were born in,
# and every layer is born at T0 with the body at rest, so the sky and ground layers stay put by themselves.
# The body's own layers add the root_part float (curves fy/fz, model units) so they rise with it.
def anchored(x, y, z):
    return [x, y, z]


def on_body(x, y, z):
    return [x, f"{y} + v.fy * v.sc", f"{z} + v.fz * v.sc"]


def tint4(rgb, alpha):
    return {"color": [r(rgb[0], 3), r(rgb[1], 3), r(rgb[2], 3), alpha]}


def mix(a, b, k):
    """Per-channel blend of two colours by the MoLang progress k."""
    return [f"{r(a[i], 3)} + {r(b[i] - a[i], 3)} * ({k})" if abs(b[i] - a[i]) > 1e-4 else r(a[i], 3) for i in range(3)]


# ================================================================= 1. the moon
MOON_POS = anchored("0", "v.my + 0.14 * (1 - v.mgro)", "v.mz")


def p_moonring(j):
    """Rings of light pulsing out of the moon (SwSh): a cyan band edged violet, fading as it spreads."""
    tb = RING_T[j]
    since = f"(v.tt - {tb})"
    k = f"math.clamp({since} / 0.5, 0, 1)"
    radius = f"v.mr * (1.02 + 0.85 * (1 - math.pow(1 - {k}, 2)))"
    vis = window(since, 0.5, 0.02)
    sz = f"{W(2 / RING_FRAC)} * {radius} * {vis}"
    comps = locked(1, tb + 0.52, anchored("0", "v.my + 0.14 * (1 - v.mgro) - 0.04", "v.mz"))
    return particle(f"moonlight_moonring_{j}", T_RING, comps, UV_RING, [sz, sz],
                    tinting={"color": [1, 1, 1, f"0.9 * math.pow(1 - {k}, 1.2) * math.min(v.lu, 1.15)"]},
                    curves=curves('mgro'))


def p_moon():
    """The full moon and its glow (one sprite): fades in over half a second while drifting down a touch,
    swells a little with each ring it sends out, fades out last."""
    comps = locked(1, MOON_OUT1, MOON_POS)
    size = f"{W(2 * MOON_SPRITE)} * v.mr * (0.9 + 0.1 * v.mgro) * (1 + 0.035 * v.hpul)"
    return particle("moonlight_moon", T_MOON, comps, UV_FULL_MOON, [size, size],
                    tinting=tint4(MOON_TINT, "0.98 * v.menv * math.min(0.9 + 0.1 * v.lu, 1.0)"),
                    curves=curves('mgro', 'menv', 'hpul'))


def p_moonstars():
    """Four-point stars twinkling round the moon."""
    tb = f"({STARS0} + {STARS1 - STARS0} * v.particle_random_1)"
    life = "(0.5 + 0.35 * v.particle_random_3)"
    since = f"(v.tt - {tb})"
    k = f"math.clamp({since} / {life}, 0, 1)"
    d = sphere_dir("(360 * v.particle_random_4)")
    dist = "(v.mr * (1.3 + 0.9 * v.particle_random_4))"
    pos = anchored(f"1.1 * {d[0]} * {dist}", f"v.my + (0.75 * {d[1]} + 0.2) * {dist}", f"v.mz + 0.8 * {d[2]} * {dist}")
    tw = "(0.55 + 0.45 * math.sin(v.tt * (700 + 500 * v.particle_random_2) + 360 * v.particle_random_3))"
    vis = window(since, life)
    sz = f"(0.12 + 0.08 * v.particle_random_4) * math.sin(180 * {k}) * {tw} * {vis} * {gate()} * v.menv"
    comps = locked(18, STARS1 + 0.86, pos)
    return particle("moonlight_moonstars", T_SPARK, comps, frame_uv("math.floor(v.particle_random_3 * 2)", 8, 8, False),
                    [sz, sz], tinting=tint4((0.9, 0.95, 1.0), 1), curves=curves('menv'))


def p_moondust():
    """Blue glitter drifting out from round the moon as it brightens (SwSh)."""
    tb = "(0.42 + 0.95 * v.particle_random_1)"
    life = "(0.55 + 0.2 * v.particle_random_3)"
    since = f"(v.tt - {tb})"
    k = f"math.clamp({since} / {life}, 0, 1)"
    d = sphere_dir("(360 * v.particle_random_4)")
    dist = f"(v.mr * (1.0 + 0.7 * v.particle_random_4) + 0.35 * math.max({since}, 0))"
    pos = anchored(f"{d[0]} * {dist}", f"v.my + {d[1]} * {dist}", f"v.mz + {d[2]} * {dist}")
    vis = window(since, life)
    sz = f"0.06 * math.sin(180 * {k}) * {vis} * {gate()}"
    comps = locked(30, 0.42 + 0.95 + 0.76, pos)
    return particle("moonlight_moondust", T_SPARK, comps, frame_uv("2", 8, 8, False), [sz, sz],
                    tinting=tint4((0.55, 0.82, 1.0), 1))


# ================================================================= 2. the circle of light on the ground
def p_groundglow():
    """A blue-violet pool of light on the ground round the user (flat on the ground)."""
    comps = locked(1, FADE1, anchored("0", "0.035", "0"))
    size = f"{W(2 * 1.5)} * v.cr * (0.8 + 0.2 * v.genv)"
    return particle("moonlight_groundglow", T_GLOW, comps, UV_GLOW, [size, size], camera="emitter_transform_xz",
                    tinting=tint4(GROUND, "math.min(0.52 * v.genv * v.lu, 0.68)"), curves=curves('genv'))


def p_groundswirl():
    """SwSh's swirl: three comet arcs turning inside a thin rim (flipbook, 8 frames of 15 degrees)."""
    comps = locked(1, FADE1, anchored("0", "0.05", "0"))
    size = f"{W(2 * 1.25 / SWIRL_RIM)} * v.cr * (0.85 + 0.15 * v.genv)"
    uv = frame_uv("math.floor(math.mod(v.tt * 14, 8))", 64, 64)
    return particle("moonlight_groundswirl", T_SWIRL, comps, uv, [size, size], camera="emitter_transform_xz",
                    tinting=tint4(SWIRL, "math.min(0.95 * v.genv * (0.85 + 0.15 * v.lu), 1)"),
                    curves=curves('genv'))


# ================================================================= 3. healing: aura, ribbons, rings, streaks
def p_aura():
    """A soft white-blue aura over the body: glows on a ball just outside it, so the near ones overlay the
    model whichever side it is seen from (a glow at the body's centre would be hidden inside the model)."""
    d = sphere_dir()
    pos = on_body(f"0.95 * v.rr * {d[0]}", f"v.cy + 0.95 * v.rr * {d[1]}", f"0.95 * v.rr * {d[2]}")
    flick = "(1 + 0.12 * math.sin(v.tt * (900 + 700 * v.particle_random_3) + 360 * v.particle_random_4))"
    sz = f"0.62 * v.fs * v.aenv * (0.85 + 0.3 * v.particle_random_3) * {flick}"
    comps = locked(22, FADE1 + 0.05, pos)
    return particle("moonlight_aura", T_GLOW, comps, UV_GLOW, [sz, sz],
                    tinting=tint4(AURA, f"math.min(0.2 * v.aenv * v.lu, 0.3) * {flick}"), curves=curves('aenv', 'fy', 'fz'))


ORBIT_TILT = (-16, 9, 3)
ORBIT_TRAIL = 0.18   # seconds of path each ribbon trails behind its head
ORBIT_SPEED = 330    # degrees per second


def p_orbit(j):
    """A ribbon of light spiralling up round the body: a bright head with a trail fading to lavender
    (Scarlet/Violet's light rings round the user). Three of them, a third of a turn apart, tilted apart."""
    s = "v.particle_random_1"                               # 0 at the head, 1 at the end of the trail
    tau = f"(v.tt - {ORBIT_TRAIL} * {s})"
    rise = f"math.clamp(({tau} - {ORBIT0}) / {ORBIT1 - ORBIT0}, 0, 1)"
    theta = f"({120 * j} + {ORBIT_SPEED} * ({tau} - {ORBIT0}))"
    a = math.radians(ORBIT_TILT[j])
    rad = f"(v.or * {r(1 + 0.1 * j, 3)})"
    y = f"v.bh * ({r(0.14 + 0.05 * j, 3)} + 0.72 * {rise})"
    pos = on_body(f"{rad} * math.cos({theta})", f"{y} + {rad} * math.sin({theta}) * {r(math.sin(a), 4)}",
                  f"{rad} * math.sin({theta}) * {r(math.cos(a), 4)}")
    started = f"math.clamp(({tau} - {ORBIT0}) * 30, 0, 1)"
    sz = f"0.17 * v.fs * (1 - 0.7 * {s}) * v.oenv * {started}"
    comps = locked(36, ORBIT1 + 0.05, pos)
    return particle(f"moonlight_orbit_{j}", T_GLOW, comps, UV_GLOW, [sz, sz],
                    tinting={"color": mix((1.0, 1.0, 1.0), LAVENDER, s) + [f"math.pow(1 - {s}, 1.3) * v.oenv"]},
                    curves=curves('oenv', 'fy', 'fz'))


def p_orbitstars():
    """A few four-point stars circling the body slowly while it heals."""
    theta = f"(360 * v.particle_random_2 + 115 * (v.tt - {ORBIT0}))"
    rad = "(1.3 * v.or)"
    pos = on_body(f"{rad} * math.cos({theta})", "v.bh * (0.3 + 0.55 * v.particle_random_4)", f"{rad} * math.sin({theta})")
    tw = "(0.55 + 0.45 * math.sin(v.tt * (650 + 400 * v.particle_random_4) + 360 * v.particle_random_3))"
    sz = f"(0.12 + 0.05 * v.particle_random_4) * v.fs * {tw} * v.oenv * {gate()}"
    comps = locked(8, ORBIT1 + 0.05, pos)
    return particle("moonlight_orbitstars", T_SPARK, comps, frame_uv("math.floor(v.particle_random_3 * 2)", 8, 8, False),
                    [sz, sz], tinting=tint4((0.95, 0.97, 1.0), 1), curves=curves('oenv', 'fy', 'fz'))


def p_healring(j):
    """A ring of light spreading out round the body (one of three, low, middle and high), beading up as
    it fades."""
    tb = HEAL_RINGS[j]
    since = f"(v.tt - {tb})"
    k = f"math.clamp({since} / 0.5, 0, 1)"
    rho = f"(v.or * (0.9 + 1.45 * (1 - math.pow(1 - {k}, 2))))"
    theta = "(360 * v.particle_random_1)"
    y = f"v.bh * {r(0.3 + 0.17 * j, 3)} + 0.12 * {k}"
    pos = on_body(f"{rho} * math.cos({theta})", y, f"{rho} * math.sin({theta})")
    vis = window(since, 0.5, 0.02)
    sz = f"0.1 * v.fs * (1 - 0.45 * {k}) * {vis}"
    comps = locked(48, tb + 0.52, pos)
    return particle(f"moonlight_healring_{j}", T_GLOW, comps, UV_GLOW, [sz, sz],
                    tinting={"color": mix((0.9, 0.96, 1.0), (0.7, 0.92, 1.0), k)
                             + [f"0.9 * math.pow(1 - {k}, 1.2) * math.min(v.lu, 1.2)"]}, curves=curves('fy', 'fz'))


def p_risestreaks():
    """Thin streaks of light rising round the user inside the column (SwSh), white and pink."""
    tb = "(1.28 + 0.85 * v.particle_random_1)"
    life = "(0.32 + 0.15 * v.particle_random_3)"
    since = f"(v.tt - {tb})"
    k = f"math.clamp({since} / {life}, 0, 1)"
    ang = "(360 * v.particle_random_2)"
    rad = "(v.or * (0.85 + 0.45 * v.particle_random_4))"
    pos = on_body(f"{rad} * math.cos({ang})", f"v.bh * (0.05 + 0.35 * v.particle_random_3) + 1.6 * math.max({since}, 0)",
                  f"{rad} * math.sin({ang})")
    vis = window(since, life)
    g = gate()
    comps = locked(24, 1.28 + 0.85 + 0.48, pos)
    pink = "(v.particle_random_2 < 0.4)"
    col = [f"{pink} ? {PINK_STREAK[i]} : {(0.88, 0.94, 1.0)[i]}" for i in range(3)]
    return particle("moonlight_risestreaks", T_BEAM, comps, UV_BEAM,
                    [f"{W(0.42)} * (1 + 0.45 * v.particle_random_4) * v.fs * {vis} * {g}", f"{W(0.045)} * v.fs * {vis} * {g}"],
                    camera="lookat_direction", direction=UP,
                    tinting={"color": col + [f"0.9 * (1 - {k} * {k})"]}, curves=curves('fy', 'fz'))


def p_motes():
    """Motes of moonlight drifting down the column, twinkling, gone before they touch the ground."""
    tb = f"({MOTES0} + {MOTES1 - MOTES0} * v.particle_random_1)"
    life = "0.9"
    since = f"(v.tt - {tb})"
    k = f"math.clamp({since} / {life}, 0, 1)"
    ang = "(360 * v.particle_random_2)"
    rad = "(v.cr * 0.82 * math.sqrt(v.particle_random_3))"
    y = f"(v.ct - 0.3 - (1.0 + 0.6 * v.particle_random_4) * math.max({since}, 0))"
    sway = f"0.06 * math.sin({since} * 400 + 360 * v.particle_random_4)"
    pos = anchored(f"{rad} * math.cos({ang}) + {sway}", y, f"{rad} * math.sin({ang})")
    tw = "(0.6 + 0.4 * math.sin(v.tt * 820 + 360 * v.particle_random_3))"
    vis = f"{window(since, life)} * math.clamp(({y} - 0.08) * 8, 0, 1)"
    sz = f"(0.06 + 0.03 * v.particle_random_4) * v.fs * {tw} * {vis} * {gate()}"
    comps = locked(42, MOTES1 + 0.92, pos)
    return particle("moonlight_motes", T_SPARK, comps, frame_uv("1 + math.floor(v.particle_random_3 * 2)", 8, 8, False),
                    [sz, sz], tinting=tint4((0.86, 0.95, 1.0), f"1 - {k} * {k} * {k}"))


def p_beamstreaks():
    """Faint vertical streaks shimmering inside the column as the light pours down."""
    tb = "(1.05 + 1.1 * v.particle_random_1)"
    life = "(0.32 + 0.12 * v.particle_random_3)"
    since = f"(v.tt - {tb})"
    k = f"math.clamp({since} / {life}, 0, 1)"
    ang = "(360 * v.particle_random_2)"
    rad = "(v.cr * 0.75 * math.sqrt(v.particle_random_4))"
    y = f"0.4 + (v.ct - 1.0) * v.particle_random_3 - 0.8 * math.max({since}, 0)"
    pos = anchored(f"{rad} * math.cos({ang})", y, f"{rad} * math.sin({ang})")
    vis = window(since, life)
    g = gate()
    comps = locked(26, 1.05 + 1.1 + 0.45, pos)
    return particle("moonlight_beamstreaks", T_BEAM, comps, UV_BEAM,
                    [f"{W(0.6)} * (1 + 0.8 * v.particle_random_4) * {vis} * {g}", f"{W(0.035)} * v.fs * {vis} * {g}"],
                    camera="lookat_direction", direction=UP,
                    tinting=tint4((0.92, 0.96, 1.0), f"0.55 * math.sin(180 * {k}) * math.min(v.lu, 1.2)"),
                    curves=None)


# ================================================================= 4. the heal burst (the games' generic heal: mint)
def surface(count, end_time, size, alpha, col, radius=1.0):
    d = sphere_dir()
    pos = on_body(f"{radius} * v.rr * {d[0]}", f"v.cy + {radius} * v.rr * {d[1]}", f"{radius} * v.rr * {d[2]}")
    flick = "(1 + 0.12 * math.sin(v.tt * (900 + 700 * v.particle_random_3) + 360 * v.particle_random_4))"
    sz = f"({size}) * (0.85 + 0.3 * v.particle_random_3) * {flick}"
    return locked(count, end_time, pos), [sz, sz], tint4(col, f"({alpha}) * {flick}")


def p_healbubble():
    """The heal bubble: a translucent mint sphere of light round the user as the HP comes back."""
    since = f"(v.tt - {HEAL})"
    env = f"math.clamp({since} / 0.08, 0, 1) * math.clamp(1 - ({since} - 0.22) / 0.2, 0, 1)"
    comps, size, tint = surface(28, HEAL + 0.45, f"0.95 * v.fs * {env}", f"0.22 * {env} * math.min(v.lu, 1.25)", MINT, 1.08)
    return particle("moonlight_healbubble", T_GLOW, comps, UV_GLOW, size, tinting=tint, curves=curves('fy', 'fz'))


def p_healrays():
    """White sparkle streaks shooting out of the bubble, mostly upwards."""
    tb = f"({HEAL + 0.02} + 0.1 * v.particle_random_4)"
    since = f"(v.tt - {tb})"
    k = f"math.clamp({since} / 0.24, 0, 1)"
    ang = "(360 * v.particle_random_1)"
    up = "(0.15 + 0.85 * v.particle_random_2)"
    hor = f"math.sqrt(1 - {up} * {up})"
    dist = f"v.rr * (0.7 + 1.1 * (1 - math.pow(1 - {k}, 2)) + 0.01 * v.particle_age)"
    pos = on_body(f"{hor} * math.cos({ang}) * {dist}", f"v.cy + {up} * {dist}", f"{hor} * math.sin({ang}) * {dist}")
    vis = window(since, 0.24, 0.02)
    comps = locked(16, HEAL + 0.4, pos)
    return particle("moonlight_healrays", T_BEAM, comps, UV_BEAM,
                    [f"0.42 * v.fs * (1 - 0.6 * {k}) * {vis} * {gate()}", f"0.045 * v.fs * {vis}"], camera="lookat_direction",
                    tinting={"color": [f"1 - 0.25 * {k}", 1, f"1 - 0.15 * {k}", f"1 - {k} * {k}"]}, curves=curves('fy', 'fz'))


def p_healstars():
    """Four-point stars twinkling round the bubble (pixel art: kept small so it stays crisp)."""
    tb = f"({HEAL} + 0.24 * v.particle_random_4)"
    since = f"(v.tt - {tb})"
    k = f"math.clamp({since} / 0.3, 0, 1)"
    d = sphere_dir()
    pos = on_body(f"1.15 * v.rr * {d[0]}", f"v.cy + 1.15 * v.rr * {d[1]} + 0.3 * math.max({since}, 0)", f"1.15 * v.rr * {d[2]}")
    vis = window(since, 0.3, 0.02)
    sz = f"(0.32 + 0.12 * v.particle_random_3) * math.sin(180 * {k}) * {vis}"
    comps = locked(10, HEAL + 0.6, pos)
    return particle("moonlight_healstars", T_TWINKLE, comps, frame_uv(frames(k, 11), 25, 25), [sz, sz],
                    tinting=tint4((0.86, 1.0, 0.92), 1), curves=curves('fy', 'fz'))


def p_healmotes():
    """Small mint sparkles rising off the user as the bubble fades."""
    tb = f"({HEAL + 0.04} + 0.3 * v.particle_random_1)"
    since = f"(v.tt - {tb})"
    life = "(0.4 + 0.12 * v.particle_random_4)"
    k = f"math.clamp({since} / {life}, 0, 1)"
    ang = "(360 * v.particle_random_2)"
    rad = "(v.rr * (0.6 + 0.5 * v.particle_random_3))"
    pos = on_body(f"{rad} * math.cos({ang})", f"v.bh * (0.2 + 0.6 * v.particle_random_3) + 0.9 * math.max({since}, 0)",
                  f"{rad} * math.sin({ang})")
    vis = window(since, life)
    sz = f"(0.07 + 0.04 * v.particle_random_4) * v.fs * {vis}"
    comps = locked(18, HEAL + 0.85, pos)
    return particle("moonlight_healmotes", T_SPARK, comps, frame_uv(frames(k, 4), 8, 8, horizontal=False), [sz, sz],
                    tinting=tint4((0.66, 1.0, 0.8), f"1 - {k} * {k}"), curves=curves('fy', 'fz'))


# ================================================================= the column of moonlight (drawn last)
def p_beam():
    """The column of moonlight from the moon to the ground: grows down from the moon, flares as the HP
    comes back, then fades (narrowing, as its soft sides drop under the shader's alpha cut-off). Drawn as
    one quad that turns about the vertical to face the camera, so it reads as a round column from any
    side; it runs a little below the ground so it reaches the ground at full strength."""
    bottom = "(v.ct - 1.15 * v.ct * v.bgro)"
    length = f"(v.ct - {bottom})"
    width = f"(2 * v.cr * (0.92 + 0.08 * v.lu) * (0.7 + 0.3 * v.bgro))"
    comps = locked(1, FADE1, anchored("0", f"(v.ct + {bottom}) / 2", "0"))
    return particle("moonlight_beam", T_COLUMN, comps, UV_COLUMN,
                    [f"0.75 * {length}", f"0.75 * {width}"], camera="lookat_direction", direction=UP,
                    tinting=tint4(BEAM, "math.min(0.7 * v.benv * v.lu, 0.92)"), curves=curves('bgro', 'benv'))


# ================================================================= HP already full: the moon peeks out and fades
def p_failmoon():
    comps = locked(1, FAIL_LEN, ["0", "v.my - 0.1 * v.mr", "v.mz"])
    size = f"{W(2 * 0.75 * MOON_SPRITE)} * v.mr * (0.9 + 0.1 * v.fenv)"
    return particle("moonlight_failmoon", T_MOON, comps, UV_FULL_MOON, [size, size],
                    tinting=tint4(MOON_TINT, "0.55 * v.fenv"), curves=curves('fenv'))


def p_failstars():
    tb = "(0.3 + 0.3 * v.particle_random_1)"
    life = "(0.3 + 0.15 * v.particle_random_3)"
    since = f"(v.tt - {tb})"
    k = f"math.clamp({since} / {life}, 0, 1)"
    d = sphere_dir("(360 * v.particle_random_4)")
    dist = "(v.mr * (0.9 + 0.5 * v.particle_random_4))"
    pos = [f"{d[0]} * {dist}", f"v.my - 0.1 * v.mr + (0.7 * {d[1]} + 0.15) * {dist}", f"v.mz + 0.8 * {d[2]} * {dist}"]
    vis = window(since, life)
    sz = f"(0.1 + 0.05 * v.particle_random_4) * math.sin(180 * {k}) * {vis}"
    comps = locked(5, FAIL_LEN, pos)
    return particle("moonlight_failstars", T_SPARK, comps, frame_uv("math.floor(v.particle_random_3 * 2)", 8, 8, False),
                    [sz, sz], tinting=tint4((0.9, 0.95, 1.0), 1))


# ================================================================= animations
STEP = 0.025


def vec(v):
    return [r(c, 3) for c in v]


def dense_keys(fn, end, tol=0.02, extra=(), step=STEP, start=0.0):
    """Sample fn every `step` (plus `extra` times) from `start` to `end`; drop points that linear
    interpolation reproduces within `tol`."""
    n = int((end - start) / step + 1e-9)
    xs = sorted(set([r(start + i * step) for i in range(n + 1)] + [end] + [x for x in extra if start <= x <= end]))
    xs = [x for x in xs if x <= end]
    pts = [(x, [float(c) for c in fn(x)]) for x in xs]
    keep = [pts[0]]
    for i in range(1, len(pts) - 1):
        a, b = keep[-1], pts[i + 1]
        guess = [a[1][j] + (b[1][j] - a[1][j]) * (pts[i][0] - a[0]) / (b[0] - a[0]) for j in range(len(a[1]))]
        if max(abs(g - v) for g, v in zip(guess, pts[i][1])) > tol:
            keep.append(pts[i])
    keep.append(pts[-1])
    return {t(x): vec(v) for x, v in keep}


KEY_TIMES = (0.06, LOOK, 1.30, 1.95, HEAL, HEAL + 0.04, 2.30, 2.52, 2.66, SETTLE)

# spawn (= draw) order. Translucent particles write depth wherever they pass the 0.1 alpha cut, so a big
# soft glow drawn before the column punches a hole in it (it showed as a dark disc at night). The column
# goes after the sky, the ground and the small bright particles, and the big soft glows (aura, heal
# bubble) and the rest of the heal burst go after the column, blending over it.
DRAW_ORDER = (['moon'] + [f'moonring_{j}' for j in range(3)] + ['moonstars', 'moondust', 'groundglow', 'groundswirl']
              + [f'orbit_{j}' for j in range(3)] + ['orbitstars'] + [f'healring_{j}' for j in range(3)]
              + ['risestreaks', 'motes', 'beamstreaks', 'beam', 'aura', 'healbubble', 'healrays', 'healstars', 'healmotes'])


def fx(names, pre):
    return [{'effect': f'cobblemon:moonlight_{n}', 'locator': 'root', 'pre_effect_script': pre} for n in names]


def actor(lum, dens):
    pre = f"v.lum = {lum}\nv.dens = {dens}"
    return {
        'animation_length': ACTOR_LEN,
        'bones': {
            'root_part': {
                'position': dense_keys(root_pos, ACTOR_LEN, 0.02, KEY_TIMES),
                'rotation': dense_keys(root_rot, ACTOR_LEN, 0.1, KEY_TIMES),
                'scale': dense_keys(ROOT_SCALE, ACTOR_LEN, 0.002, KEY_TIMES)},
            'head': {'rotation': dense_keys(HEAD, ACTOR_LEN, 0.2, KEY_TIMES)}},
        'particle_effects': {t(T0): fx(DRAW_ORDER, pre)},
        'sound_effects': {
            t(MOON0): [{'effect': 'move.moonlight.moon'}],
            t(STARS0 + 0.12): [{'effect': 'move.moonlight.twinkle'}],
            t(BEAM0): [{'effect': 'move.moonlight.beam'}],
            t(GLOW0 + 0.04): [{'effect': 'move.moonlight.glow'}],
            t(HEAL - 0.02): [{'effect': 'move.moonlight.heal'}, {'effect': 'move.moonlight.sparkle'}],
        },
    }


def actor_fail():
    keys = (0.06, 0.32, 0.56, 0.86)
    return {
        'animation_length': FAIL_LEN,
        'bones': {
            'root_part': {'position': dense_keys(FAIL_ROOT, FAIL_LEN, 0.02, keys),
                          'rotation': dense_keys(FAIL_ROT, FAIL_LEN, 0.1, keys)},
            'head': {'rotation': dense_keys(FAIL_HEAD, FAIL_LEN, 0.2, keys)}},
        'particle_effects': {t(T0): [{'effect': 'cobblemon:moonlight_failmoon', 'locator': 'root'},
                                     {'effect': 'cobblemon:moonlight_failstars', 'locator': 'root'}]},
        'sound_effects': {t(FAIL_IN): [{'effect': 'move.moonlight.twinkle'}]},
    }


def build_animation_file():
    anims = {f'animation.moonlight.{name}': actor(lum, dens) for name, (lum, dens) in VARIANTS.items()}
    anims['animation.moonlight.actor_fail'] = actor_fail()
    return {'format_version': '1.8.0', 'animations': anims}


# ================================================================= the action effect
def play(anim):
    return f"q.play_animation(q.bedrock_stateful('moonlight', '{anim}', 'endures_primary_animations'))"


# What the battle reported decides which version plays; the hook returns the share of max HP the heal was
# worth (2/3, 1/2, 1/4), -1 if the heal failed (HP already full) and 0 if it can't tell (or isn't there).
SHARE = "q.user.move_heal_share"
FAIL = f"{SHARE} < 0"
SUN = f"{SHARE} > 0.58"
WEAK = f"{SHARE} > 0 && {SHARE} < 0.38"
NORMAL = f"!({FAIL}) && !({SUN}) && !({WEAK})"
USER = "q.entity.is_user == true"
FORCE = os.environ.get('ML_FORCE')   # debug builds for checking each version in-game: sun / weak / fail. Never ship.
if FORCE in ('sun', 'weak', 'fail'):
    picked = {'sun': 'SUN', 'weak': 'WEAK', 'fail': 'FAIL'}[FORCE]
    SUN, WEAK, FAIL = (("true" if n == picked else "false") for n in ('SUN', 'WEAK', 'FAIL'))
    NORMAL = "false"
# the user's glow while it heals (Java hook; returns 0 and does nothing if it isn't there)
TINT_LEVELS = {'SUN': (0.55, 0.5), 'NORMAL': (0.42, 0.38), 'WEAK': (0.28, 0.25)}   # (strength, white wash)


def tint_call(level):
    strength, flash = TINT_LEVELS[level]
    args = [*TINT, strength, flash, GLOW0 - 0.03, 0.3, FADE0 - GLOW0 - 0.25, 0.4]
    return f"q.user.model_tint({', '.join(str(r(a)) for a in args)})"


def build_effect_file():
    # Every keyframe costs a server tick in 1.7.3, so the whole start is one `parallel` (one tick).
    start = [
        {'type': 'entity_molang', 'condition': NORMAL, 'entityCondition': USER, 'expressions': [play('actor')]},
        {'type': 'entity_molang', 'condition': SUN, 'entityCondition': USER, 'expressions': [play('actor_bright')]},
        {'type': 'entity_molang', 'condition': WEAK, 'entityCondition': USER, 'expressions': [play('actor_soft')]},
        {'type': 'entity_molang', 'condition': FAIL, 'entityCondition': USER, 'expressions': [play('actor_fail')]},
        {'type': 'molang', 'expressions': f"({FAIL}) ? 0 : (({SUN}) ? {tint_call('SUN')} : "
                                          f"(({WEAK}) ? {tint_call('WEAK')} : {tint_call('NORMAL')}))"},
    ]
    # the parallel above already took a tick; the battle restores the HP when the hold is released
    return {'timeline': [
        {'type': 'add_holds', 'holds': ['effects']},
        {'type': 'parallel', 'keyframes': start},
        {'type': 'pause', 'pause': f"({FAIL}) ? {r(FAIL_HOLD)} : {r(HEAL - 0.05)}"},
        {'type': 'remove_holds', 'holds': ['effects']},
        {'type': 'pause', 'pause': f"({FAIL}) ? {r(FAIL_LEN - FAIL_HOLD - 0.05)} : {r(END - HEAL)}"},
    ]}


def all_particles():
    out = [p_moon()] + [p_moonring(j) for j in range(3)] + [p_moonstars(), p_moondust()]
    out += [p_groundglow(), p_groundswirl(), p_aura()] + [p_orbit(j) for j in range(3)] + [p_orbitstars()]
    out += [p_healring(j) for j in range(3)] + [p_risestreaks(), p_motes(), p_beamstreaks()]
    out += [p_healbubble(), p_healrays(), p_healstars(), p_healmotes(), p_beam()]
    out += [p_failmoon(), p_failstars()]
    return out


# Sound events (aliases of Cobblemon's own sounds; see docs/moonlight_assets.md): name -> (file, volume, pitch)
SOUND_EVENTS = {
    'move.moonlight.moon': ('cobblemon:move/psychic/psychic_actor', 0.5, 0.7),           # a deep, calm swell
    'move.moonlight.twinkle': ('cobblemon:evolution/evolution_notification', 0.9, 1.6),  # a soft high chime
    'move.moonlight.beam': ('cobblemon:move/protect/protect_actor', 0.55, 0.75),         # shimmering light
    'move.moonlight.glow': ('cobblemon:evolution/evolution_notification', 0.9, 1.2),
    'move.moonlight.heal': ('cobblemon:item/medicine/medicine_liquid_use', 0.8, 1.1),
    'move.moonlight.sparkle': ('cobblemon:move/impact_generic/impact_generic_fairy_3', 0.4, 1.3),
}


def update_sounds():
    with open(SOUNDS) as f:
        sounds = json.load(f)
    for key, (name, volume, pitch) in SOUND_EVENTS.items():
        sounds[key] = {'sounds': [{'name': name, 'volume': volume, 'pitch': pitch}]}
    for stale in [k for k in sounds if k.startswith('move.moonlight.') and k not in SOUND_EVENTS]:
        del sounds[stale]
    with open(SOUNDS, 'w') as f:
        f.write(json.dumps(sounds, indent=2) + '\n')
    print('updated', os.path.relpath(SOUNDS, ROOT), f'({len(SOUND_EVENTS)} move.moonlight.* events)')


def write(path, data):
    with open(path, 'w') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write('\n')
    print('wrote', os.path.relpath(path, ROOT))


if __name__ == '__main__':
    if FORCE:
        print(f'*** DEBUG BUILD: every Moonlight plays the {FORCE} version. Rebuild without ML_FORCE before shipping. ***')
    os.makedirs(PART_DIR, exist_ok=True)
    wanted = set()
    for p in all_particles():
        pid = p['particle_effect']['description']['identifier'].split(':')[1]
        wanted.add(pid + '.particle.json')
        write(os.path.join(PART_DIR, pid + '.particle.json'), p)
    for stale in set(os.listdir(PART_DIR)) - wanted:
        os.remove(os.path.join(PART_DIR, stale))
        print('removed stale', stale)
    order = [f'moonlight_{n}.particle.json' for n in DRAW_ORDER]
    missing = [n for n in order if n not in wanted]
    if missing:
        raise SystemExit(f'DRAW_ORDER names effects that are not generated: {missing}')
    write(ANIM_OUT, build_animation_file())
    write(EFFECT_OUT, build_effect_file())
    update_sounds()
