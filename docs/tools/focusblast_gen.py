"""Generates Focus Blast's particle effects, generic animation file and action effect.

Outputs (paths relative to the repo root):
  src/main/resources/assets/cobblemon/bedrock/particles/moves/focusblast/*.particle.json
  src/main/resources/assets/cobblemon/bedrock/generic/animations/moves/focusblast.animation.json
  src/main/resources/data/cobblemon/action_effects/moves/focusblast.json

Edit the constants below and re-run `python3 docs/tools/focusblast_gen.py`; don't hand-edit the outputs.
Design notes and the reasoning behind the numbers: docs/focusblast_assets.md.

How the timing works. Every orb layer is spawned in the same server tick as the user's and the
target's animations, then everything runs on the client clock. The orb particles are all spawned
at t=0 and stay invisible until their phase comes up. They read their flight from curves sampled
in 0.05 s steps (one per client tick), and the target's impact fires at IMPACT on the same clock,
so arrival and impact line up regardless of server lag.

Frame. The orb emitters sit on the user's root locator with the target locator injected, so
target deltas exist. In their parametric frame -z is forward and the target is at
(-dx, +dy, -dz). Emitter SHAPE offsets would flip x, so every orb position uses
particle_motion_parametric only.
"""
import json, math, os

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..')
RES = os.path.join(ROOT, 'src/main/resources')
PART_DIR = os.path.join(RES, 'assets/cobblemon/bedrock/particles/moves/focusblast')
ANIM_OUT = os.path.join(RES, 'assets/cobblemon/bedrock/generic/animations/moves/focusblast.animation.json')
EFFECT_OUT = os.path.join(RES, 'data/cobblemon/action_effects/moves/focusblast.json')

# ---------------------------------------------------------------- timing (seconds, client clock)
FOCUS_END = 0.25        # anticipation: crouch + concentrate
GATHER0, GATHER1 = 0.10, 0.50   # gather motes start between these times
FORM, FULL = 0.35, 0.80          # the orb grows from a point to full size
WIND0, WIND1 = 0.84, 0.92        # wind-up: orb pulled back, body rears back
LAUNCH, IMPACT = 0.95, 1.35      # release and arrival (0.40 s accelerating flight)
# The orb (particle clock) is drawn ~2 ticks behind the model animations: particles are born on the
# client tick after the packet, and a parametric position is rendered one tick after it's computed.
# The target's impact therefore fires this much later so it lands on the frame the orb touches.
PARTICLE_LAG = 0.10
FLIGHT = IMPACT - LAUNCH
DISPERSE = 0.20                  # hit: the orb bursts outward and fades over this long
MISS_U = 1.30                    # miss: the orb keeps going to this much of its flight (u), then is gone
ACTOR_LEN = 1.55
CURVE_RANGE = 1.60               # curves are sampled every 0.05 s over [0, CURVE_RANGE]
STEP = 0.05
TOTAL = 1.95                     # emitter lifetime for the t=0 orb emitters

# ---------------------------------------------------------------- the orb's size and hold point
# v.R = orb radius, (0, v.hy, v.hz) = hold point above / in front of the head, relative to the root.
# Pokemon taller than 3.6 blocks hold it in front of the upper body instead of overhead (so it stays in
# frame); everything shorter holds it above the head, where it's visible even from behind the user.
SIZE_EXPR = ("v.R = math.clamp(0.30 + 0.20 * v.entity_height, 0.42, 0.85);"
             "v.hy = math.min(v.entity_height, 3.6) + 0.9 * v.R;"
             "v.hz = -(0.25 * v.entity_width + 0.45 * v.R + math.clamp(v.entity_height - 3.6, 0, 1) * (0.3 * v.entity_width + v.R));")
FALLBACK = "v.target_deltax = 0; v.target_deltay = 1; v.target_deltaz = 5; v.entity_height = 1; v.entity_width = 1;"
MISS_SIDE, MISS_UP = 1.6, 0.75   # how far a missed orb veers past the target (blocks, emitter frame)
SPIN = 300                        # orb body spin, degrees/s about the vertical axis

# ---------------------------------------------------------------- arms (additive, any rig)
# Fitted with a forward-kinematics census of the battle idle of all 134 learner rigs that have
# arm_left/arm_right in Cobblemon 1.7.3 (docs/focusblast_assets.md). Mirrored for the right arm.
# Bones a model lacks are skipped by Cobblemon, so this is safe on every Pokemon.
ARM_POSES = {           # left-arm delta [x, y, z] degrees
    'rest':   [0, 0, 0],
    'focus':  [-20, 20, 15],     # hands drawn in front of the chest (concentrating)
    'charge': [-55, -8, -50],    # arms raised forward-up toward the orb
    'windup': [-80, -10, -60],   # further up and back
    'throw':  [-55, 0, -5],      # thrust forward at the target
    'relax':  [-18, 0, -2],
}
ARM_KEYS = [(0.0, 'rest'), (0.12, 'focus'), (0.25, 'focus'), (0.5, 'charge', 0.8), (0.8, 'charge'),
            (0.92, 'windup'), (0.99, 'throw'), (1.1, 'throw'), (1.3, 'relax'), (1.5, 'rest'), (ACTOR_LEN, 'rest')]
ARM_BONES = [('arm_left', 'arm_right'), ('left_upper_arm', 'right_upper_arm'), ('left_arm', 'right_arm')]
HEAD_KEYS = [(0.0, 0), (0.12, 6), (0.25, 4), (0.5, -10), (0.85, -12), (0.97, 6), (1.15, 4), (1.45, 0), (ACTOR_LEN, 0)]

# ---------------------------------------------------------------- palette (#AARRGGBB)
WHITE = '#FFFFFFFF'
PALE = '#FFE6FBFF'       # white with a cyan breath
CYAN = '#FF8CEBFF'
DEEP = '#FF5ABDFF'
VIOLET = '#FF8C8CFF'     # violet-blue
INDIGO = '#FF6A6EF0'

# ---------------------------------------------------------------- helpers
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

def ease_out(x, p=2.2):
    x = clamp(x, 0.0, 1.0)
    return 1 - (1 - x) ** p

def path_s(u):
    """Flight progress for flight fraction u: starts at a quarter speed (heavy), ends at 1.75x (fast)."""
    return 0.25 * u + 0.75 * u * u

def sample(fn):
    n = int(round(CURVE_RANGE / STEP)) + 1
    return [r(fn(i * STEP)) for i in range(n)]

def curve(fn, inp="v.particle_age"):
    return {"type": "linear", "input": inp, "horizontal_range": CURVE_RANGE, "nodes": sample(fn)}

# ---- the shared curves (functions of time since the move started)
def c_s_hit(a):
    return path_s(clamp((a - LAUNCH) / FLIGHT, 0, 1))

def c_s_miss(a):
    return path_s(clamp((a - LAUNCH) / FLIGHT, 0, MISS_U))

def c_dev_miss(a):
    s = c_s_miss(a)
    return smooth((s - 0.3) / 0.7) + max(0.0, s - 1.0) * 0.8

def c_wind(a):
    if a <= WIND0 or a >= LAUNCH + 0.02:
        return 0.0
    if a <= WIND1:
        return smooth((a - WIND0) / (WIND1 - WIND0))
    return 1 - smooth((a - WIND1) / (LAUNCH + 0.02 - WIND1))

def c_grow(a):
    """Orb size factor before impact: point at FORM, full at FULL with a power-up overshoot,
    squeezed during the wind-up, then slightly compressed in flight."""
    if a < FORM:
        return 0.0
    if a < WIND0:
        base = 0.08 + 0.92 * ease_out((a - FORM) / (FULL - FORM))
        surge = 0.12 * max(0.0, 1 - ((a - 0.77) / 0.08) ** 2)   # power-up surge as it reaches full size
        return base + surge
    if a < LAUNCH:
        return 1.0 - 0.10 * c_wind(a)
    return 1.0 - 0.08 * clamp((a - LAUNCH) / FLIGHT, 0, 1)

def c_rad_hit(a):
    if a <= IMPACT:
        return c_grow(a)
    return c_grow(IMPACT) * (1 + 7.0 * (a - IMPACT))

def c_size_hit(a):
    if a <= IMPACT:
        return c_grow(a)
    k = (a - IMPACT) / DISPERSE
    return c_grow(IMPACT) * max(0.0, (1 + 0.25 * math.sin(math.pi * clamp(k * 3, 0, 1))) * (1 - k))

def c_size_miss(a):
    s = c_s_miss(a)
    return c_grow(a) * (1 - smooth((s - 1.15) / (path_s(MISS_U) - 1.15)))

def c_rays(a):
    if a < 0.55:
        return 0.0
    return smooth((a - 0.55) / 0.2)

PATH_CURVES = {
    'hit': {
        'variable.fb_s': lambda inp="v.particle_age": curve(c_s_hit, inp),
        'variable.fb_w': lambda inp="v.particle_age": curve(c_wind, inp),
        'variable.fb_rad': lambda inp="v.particle_age": curve(c_rad_hit, inp),
        'variable.fb_sz': lambda inp="v.particle_age": curve(c_size_hit, inp),
    },
    'miss': {
        'variable.fb_s': lambda inp="v.particle_age": curve(c_s_miss, inp),
        'variable.fb_w': lambda inp="v.particle_age": curve(c_wind, inp),
        'variable.fb_rad': lambda inp="v.particle_age": curve(c_grow, inp),
        'variable.fb_sz': lambda inp="v.particle_age": curve(c_size_miss, inp),
        'variable.fb_m': lambda inp="v.particle_age": curve(c_dev_miss, inp),
    },
}

def center(variant, s='v.fb_s', w='v.fb_w', m='v.fb_m'):
    """Orb centre in the emitter's parametric frame."""
    cx = f"(-v.target_deltax * {s})"
    cy = f"(v.hy + (v.target_deltay - v.hy) * {s} + 0.12 * {w})"
    cz = f"(v.hz - (v.target_deltaz + v.hz) * {s} + 0.3 * {w})"
    if variant == 'miss':
        cx = f"(-v.target_deltax * {s} + {MISS_SIDE} * {m})"
        cy = f"(v.hy + (v.target_deltay - v.hy) * {s} + 0.12 * {w} + {MISS_UP} * {m})"
    return cx, cy, cz

SINPHI = "math.sqrt(1 - math.pow(2 * v.particle_random_2 - 1, 2))"
COSPHI = "(2 * v.particle_random_2 - 1)"

def sphere_point(radius, theta):
    """Offsets for a point at `radius` on the unit sphere picked by particle_random_1/2, azimuth `theta`."""
    return (f"({radius}) * {SINPHI} * math.cos({theta})",
            f"({radius}) * {COSPHI}",
            f"({radius}) * {SINPHI} * math.sin({theta})")

def add3(a, b):
    return [f"{a[i]} + {b[i]}" for i in range(3)]

def tex(path, w, h):
    return f"textures/particles/generic/{path}", w, h

T_LFO = tex('orb/largefadeorb', 143, 13)
T_DOTS = tex('orb/glowing_dots_cyan', 8, 32)
T_BEAM = tex('smallbeam', 140, 91)
T_SKY = tex('skyding', 275, 25)
T_RING = tex('ring/largering2', 240, 20)
T_DASH = tex('dashburst', 320, 64)
T_HIT = tex('hit', 32, 160)
T_SPARK = tex('sparkle/glowingsparkle_cyan', 8, 32)

UV_LFO5 = {"uv": [65, 0], "uv_size": [13, 13]}   # biggest, brightest frame
UV_LFO4 = {"uv": [52, 0], "uv_size": [13, 13]}
UV_DOT = {"uv": [0, 0], "uv_size": [8, 8]}
UV_BEAM = {"uv": [70, 42], "uv_size": [70, 7]}   # right half of one smallbeam frame = a soft streak
UV_SPARK = {"uv": [0, 0], "uv_size": [8, 8]}

def manual_frames(start, duration, frames, fw, fh, horizontal=True):
    """Static UV whose frame is picked from particle age: plays `frames` frames between start and
    start+duration (Cobblemon evaluates static uv expressions every render)."""
    f = f"math.floor(math.clamp((v.particle_age - {start}) / {duration}, 0, 0.999) * {frames})"
    return {"uv": [f"{fw} * {f}", 0] if horizontal else [0, f"{fh} * {f}"], "uv_size": [fw, fh]}

def window(start, end, ramp=0.03):
    """1 between start and end (seconds of particle age), 0 outside, with short linear ramps."""
    return (f"math.clamp((v.particle_age - {start}) / {ramp}, 0, 1)"
            f" * math.clamp(({end} - v.particle_age) / {ramp}, 0, 1)")

def tint4(rgba):
    return {"color": rgba}

def gradient(inp, stops):
    return {"color": {"interpolant": inp, "gradient": {t(k): v for k, v in stops}}}

def particle(pid, texture, components, curves=None, uv=None, size=None, camera="rotate_xyz", tinting=None):
    path, tw, th = texture
    bb = {"size": size, "facing_camera_mode": camera, "uv": dict({"texture_width": tw, "texture_height": th}, **uv)}
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

def orb_emitter(count, lifetime, motion, per_update=SIZE_EXPR):
    return {
        "minecraft:emitter_initialization": {"creation_expression": FALLBACK, "per_update_expression": per_update},
        "minecraft:emitter_rate_instant": {"num_particles": count},
        "minecraft:emitter_lifetime_once": {"active_time": TOTAL},
        "minecraft:emitter_shape_point": {},
        "minecraft:particle_lifetime_expression": {"max_lifetime": lifetime},
        "minecraft:particle_initial_speed": 0,
        "minecraft:particle_motion_parametric": {"relative_position": motion},
    }

def life(variant, extra=0.0):
    if variant == 'hit':
        return r(IMPACT + DISPERSE + extra)
    return r(LAUNCH + FLIGHT * MISS_U + 0.05 + extra)

# ================================================================= the orb (t=0 emitters, hit + miss)
def p_orb(variant):
    """White-hot core: a few big shaded orb sprites jittered around the centre and flickering out of
    step, so it reads as one bright, slightly lumpy mass rather than a clean disc."""
    curves = {k: f() for k, f in PATH_CURVES[variant].items()}
    jit = "v.R * 0.16 * math.pow(v.particle_random_3, 0.5)"
    theta = f"(360 * v.particle_random_1 + {SPIN} * v.particle_age)"
    pos = add3(center(variant), sphere_point(jit, theta))
    flick = "(1 + 0.09 * math.sin(v.particle_age * (700 + 900 * v.particle_random_4) + 360 * v.particle_random_4))"
    sz = f"v.R * v.fb_sz * (0.95 + 0.2 * v.particle_random_2) * {flick}"
    return particle(f"focusblast_orb{'' if variant == 'hit' else '_miss'}", T_LFO,
                    orb_emitter(8, life(variant), pos), curves, UV_LFO5, [sz, sz],
                    tinting=gradient("v.particle_random_3", [(0.0, WHITE), (1.0, PALE)]))

def p_orbaura(variant):
    """The glow: big translucent cyan sprites around the core, plus (about a third of them) a wider,
    fainter violet-blue halo. Each breathes at its own rate, so the edge is irregular and unstable."""
    curves = {k: f() for k, f in PATH_CURVES[variant].items()}
    jit = "v.R * 0.12 * v.particle_random_4"
    theta = f"(360 * v.particle_random_1 - 170 * v.particle_age)"
    pos = add3(center(variant), sphere_point(jit, theta))
    halo = "math.clamp((v.particle_random_3 - 0.66) * 50, 0, 1)"   # 0 = cyan glow, 1 = violet halo
    wob = "(1 + 0.12 * math.sin(v.particle_age * (380 + 520 * v.particle_random_4) + 360 * v.particle_random_2))"
    sz = f"v.R * v.fb_sz * (1.35 + 0.2 * v.particle_random_2 + 0.5 * {halo}) * {wob}"
    return particle(f"focusblast_orbaura{'' if variant == 'hit' else '_miss'}", T_LFO,
                    orb_emitter(9, life(variant), pos), curves, UV_LFO5, [sz, sz],
                    tinting={"color": [f"0.55 - 0.02 * {halo}", f"0.92 - 0.34 * {halo}", "1", f"0.42 - 0.25 * {halo}"]})

def p_orbmotes(variant):
    """Bright energy motes racing over the surface: the churning energy inside the sphere."""
    curves = {k: f() for k, f in PATH_CURVES[variant].items()}
    rad = "v.R * v.fb_rad * (0.86 + 0.2 * v.particle_random_3)"
    theta = "(360 * v.particle_random_1 + (330 + 330 * v.particle_random_4) * v.particle_age)"
    pos = add3(center(variant), sphere_point(rad, theta))
    tw = "(0.75 + 0.25 * math.sin(v.particle_age * (1100 + 900 * v.particle_random_3) + 360 * v.particle_random_1))"
    sz = f"(0.07 + 0.11 * v.R) * v.fb_sz * (0.8 + 0.5 * v.particle_random_2) * {tw}"
    return particle(f"focusblast_orbmotes{'' if variant == 'hit' else '_miss'}", T_DOTS,
                    orb_emitter(36, life(variant), pos), curves, UV_DOT, [sz, sz],
                    tinting=gradient("v.particle_random_3", [(0.0, WHITE), (0.55, '#FFC8F6FF'), (1.0, '#FFA0D2FF')]))

def p_swirl(variant):
    """Streaks circling the sphere fast: the swirling energy around the orb. In flight their motion
    is dominated by the orb's own, so they stretch into motion-blur streaks along the path."""
    curves = {k: f() for k, f in PATH_CURVES[variant].items()}
    theta = "(360 * v.particle_random_1 + (560 + 240 * v.particle_random_4) * v.particle_age)"
    lat = "(1.4 * v.particle_random_2 - 0.7)"   # keep to the middle latitudes so they read as bands
    rad = "v.R * v.fb_rad * (1.1 + 0.08 * v.particle_random_3)"
    off = (f"({rad}) * math.sqrt(1 - {lat} * {lat}) * math.cos({theta})", f"({rad}) * {lat}",
           f"({rad}) * math.sqrt(1 - {lat} * {lat}) * math.sin({theta})")
    pos = add3(center(variant), off)
    comps = orb_emitter(26, life(variant), pos)
    return particle(f"focusblast_orbswirl{'' if variant == 'hit' else '_miss'}", T_BEAM, comps, curves, UV_BEAM,
                    ["v.R * v.fb_sz * (0.5 + 0.2 * v.particle_random_3)", "0.07 * v.fb_sz"], camera="lookat_direction",
                    tinting=gradient("v.particle_random_3", [(0.0, WHITE), (0.6, PALE), (1.0, CYAN)]))

def p_rays(variant):
    """Short spikes pumping in and out of the surface (SwSh's spiky aura). Their radial motion
    orients the streaks outward while the orb is held."""
    curves = {k: f() for k, f in PATH_CURVES[variant].items()}
    curves['variable.fb_ray'] = curve(c_rays)
    pump = "math.abs(math.sin(v.particle_age * (520 + 480 * v.particle_random_4) + 360 * v.particle_random_3))"
    theta = f"(360 * v.particle_random_1 + {SPIN} * v.particle_age)"
    pos = add3(center(variant), sphere_point(f"v.R * v.fb_rad * (1.05 + 0.42 * {pump})", theta))
    comps = orb_emitter(16, life(variant), pos)
    ln = f"v.R * v.fb_sz * v.fb_ray * (0.35 + 0.55 * {pump})"
    return particle(f"focusblast_orbrays{'' if variant == 'hit' else '_miss'}", T_BEAM, comps, curves, UV_BEAM,
                    [ln, "0.06 * v.fb_ray * v.fb_sz"], camera="lookat_direction",
                    tinting=gradient("v.particle_random_3", [(0.0, WHITE), (0.55, PALE), (1.0, '#FFAFB4FF')]))

def p_glints(variant):
    """A few star glints popping on the surface while the orb is at full power."""
    curves = {k: f() for k, f in PATH_CURVES[variant].items()}
    t0 = "(0.52 + 0.5 * v.particle_random_4)"
    theta = f"(360 * v.particle_random_1 + {SPIN} * v.particle_age)"
    pos = add3(center(variant), sphere_point("v.R * v.fb_rad * 0.98", theta))
    comps = orb_emitter(8, life(variant), pos)
    f = f"math.floor(math.clamp((v.particle_age - {t0}) / 0.3, 0, 0.999) * 11)"
    uv = {"uv": [f"25 * {f}", 0], "uv_size": [25, 25]}
    win = (f"math.clamp((v.particle_age - {t0}) * 40, 0, 1) * math.clamp(({t0} + 0.3 - v.particle_age) * 40, 0, 1)")
    sz = f"v.R * v.fb_sz * 0.95 * {win}"
    return particle(f"focusblast_orbglints{'' if variant == 'hit' else '_miss'}", T_SKY, comps, curves, uv, [sz, sz],
                    tinting=tint4([1, 1, 1, 1]))

def p_trail(variant):
    """Afterimages of the orb following the same path a little behind it: a short, tapered comet
    tail whose length grows with speed. Gone at the impact, so no streak is left on the field."""
    lag = "(0.015 + 0.11 * v.particle_random_1)"
    inp = f"v.particle_age - {lag}"
    curves = {k: f(inp) for k, f in PATH_CURVES[variant].items()}
    pos = list(center(variant))
    moving = "math.clamp(v.fb_s * 30, 0, 1)"
    end = IMPACT if variant == 'hit' else LAUNCH + FLIGHT * MISS_U
    alive = f"math.clamp(({end} - v.particle_age) * 30, 0, 1)"
    sz = f"v.R * v.fb_sz * (1.25 - 0.75 * v.particle_random_1) * {moving} * {alive}"
    comps = orb_emitter(22, life(variant), pos)
    return particle(f"focusblast_trail{'' if variant == 'hit' else '_miss'}", T_LFO, comps, curves, UV_LFO4, [sz, sz],
                    tinting={"color": ["0.62 + 0.25 * (1 - v.particle_random_1)", "0.86 + 0.1 * (1 - v.particle_random_1)",
                                       "1", "0.55 * (1 - 0.8 * v.particle_random_1)"]})

def p_motes(variant):
    """Small motes shed from the orb's surface during the flight; each drifts off and fades."""
    rel = f"({LAUNCH} + {r(FLIGHT * 0.95)} * v.particle_random_4)"
    curves = {k: f(rel) for k, f in PATH_CURVES[variant].items() if k != 'variable.fb_sz'}
    since = f"math.max(v.particle_age - {rel}, 0)"
    theta = "(360 * v.particle_random_1)"
    surf = sphere_point("v.R * v.fb_rad * 0.95", theta)
    drift = sphere_point(f"0.9 * {since}", theta)
    c = center(variant)
    pos = [f"{c[i]} + {surf[i]} + {drift[i]}" for i in range(3)]
    pos[1] += f" - 0.6 * {since} * {since}"
    win = f"math.clamp((v.particle_age - {rel}) * 40, 0, 1) * math.clamp(1 - {since} / 0.28, 0, 1)"
    sz = f"(0.1 + 0.07 * v.particle_random_3) * {win}"
    comps = orb_emitter(30, life(variant, 0.3), pos)
    return particle(f"focusblast_motes{'' if variant == 'hit' else '_miss'}", T_DOTS, comps, curves, UV_DOT, [sz, sz],
                    tinting=gradient("v.particle_random_3", [(0.0, WHITE), (0.5, CYAN), (1.0, VIOLET)]))

# ================================================================= shared t=0 emitters (both variants)
def hold(extra_y=""):
    return ["0", f"v.hy{extra_y}", "v.hz"]

def p_gather():
    """Motes spiralling in from a wide sphere and accelerating into the hold point."""
    d0 = f"({GATHER0} + {r(GATHER1 - GATHER0)} * v.particle_random_4)"
    L = "(0.24 + 0.1 * v.particle_random_3)"
    k = f"math.clamp((v.particle_age - {d0}) / {L}, 0, 1)"
    G = "math.clamp(1.2 + 0.7 * v.entity_radius, 1.3, 2.6)"
    rad = f"{G} * math.pow(1 - {k}, 1.4)"
    theta = f"(360 * v.particle_random_1 + 220 * {k})"
    pos = add3(hold(), sphere_point(rad, theta))
    win = f"math.clamp((v.particle_age - {d0}) * 25, 0, 1) * math.clamp((1 - {k}) * 10, 0, 1)"
    sz = f"(0.11 + 0.08 * v.particle_random_2) * (0.6 + 0.4 * {k}) * {win}"
    comps = orb_emitter(44, f"{d0} + {L} + 0.02", pos)
    return particle("focusblast_gather", T_DOTS, comps, None, UV_DOT, [sz, sz],
                    tinting=gradient("v.particle_random_3", [(0.0, WHITE), (0.45, CYAN), (1.0, VIOLET)]))

def p_gatherlines():
    """Streaks rushing straight in: the concentration lines of the gather."""
    d0 = f"({GATHER0 + 0.05} + {r(GATHER1 - GATHER0)} * v.particle_random_4)"
    L = "0.2"
    k = f"math.clamp((v.particle_age - {d0}) / {L}, 0, 1)"
    G = "math.clamp(1.3 + 0.7 * v.entity_radius, 1.4, 2.8)"
    rad = f"{G} * math.pow(1 - {k}, 1.6) + 0.15"
    theta = f"(360 * v.particle_random_1 + 40 * {k})"
    pos = add3(hold(), sphere_point(rad, theta))
    win = f"math.clamp((v.particle_age - {d0}) * 25, 0, 1) * math.clamp((1 - {k}) * 8, 0, 1)"
    comps = orb_emitter(18, f"{d0} + {L} + 0.02", pos)
    return particle("focusblast_gatherlines", T_BEAM, comps, None, UV_BEAM,
                    [f"(0.4 + 0.25 * v.particle_random_3) * {win}", f"0.05 * {win}"], camera="lookat_direction",
                    tinting=gradient("v.particle_random_3", [(0.0, WHITE), (1.0, CYAN)]))

def p_launchring():
    """Shockwave ring left at the hold point as the orb is thrown."""
    uv = manual_frames(LAUNCH, 0.3, 12, 20, 20)
    sz = f"v.R * 3.0 * {window(LAUNCH, LAUNCH + 0.3, 0.02)}"
    comps = orb_emitter(1, LAUNCH + 0.32, hold())
    return particle("focusblast_launchring", T_RING, comps, None, uv, [sz, sz],
                    tinting={"color": [0.75, 0.95, 1, f"0.95 - 0.5 * math.clamp((v.particle_age - {LAUNCH}) / 0.3, 0, 1)"]})

def p_launchburst():
    """Streaks flung backwards out of the hold point on release (the recoil of the throw)."""
    k = f"math.clamp((v.particle_age - {LAUNCH}) / 0.22, 0, 1)"
    rad = f"v.R * (0.6 + 2.6 * (1 - math.pow(1 - {k}, 2)))"
    theta = "(360 * v.particle_random_1)"
    off = sphere_point(rad, theta)
    pos = ["0 + " + off[0], "v.hy + " + off[1], f"v.hz + 0.35 * {rad} + " + off[2]]
    win = window(LAUNCH, LAUNCH + 0.22, 0.02)
    comps = orb_emitter(14, LAUNCH + 0.25, pos)
    return particle("focusblast_launchburst", T_BEAM, comps, None, UV_BEAM,
                    [f"v.R * 0.9 * (1 - 0.6 * {k}) * {win}", f"0.06 * {win}"], camera="lookat_direction",
                    tinting=gradient("v.particle_random_3", [(0.0, WHITE), (1.0, CYAN)]))

# ================================================================= fired from the user's animation
def p_focus():
    """Anticipation: radial lines converging on the user (the dash-burst played backwards)."""
    dur = 0.28
    f = f"math.floor(math.clamp(v.particle_age / {dur}, 0, 0.999) * 5)"
    uv = {"uv": [f"64 * (4 - {f})", 0], "uv_size": [64, 64]}
    sz = "math.clamp(1.3 * v.entity_height + 0.6, 1.4, 4.5)"
    comps = {
        "minecraft:emitter_initialization": {"creation_expression": "v.entity_height = 1;"},
        "minecraft:emitter_rate_instant": {"num_particles": 1},
        "minecraft:emitter_lifetime_once": {"active_time": 0.3},
        "minecraft:emitter_shape_point": {},
        "minecraft:particle_lifetime_expression": {"max_lifetime": dur},
        "minecraft:particle_initial_speed": 0,
        "minecraft:particle_motion_dynamic": {},
    }
    return particle("focusblast_focus", T_DASH, comps, None, uv, [sz, sz],
                    tinting={"color": [0.82, 0.96, 1, f"0.9 * math.clamp(v.particle_age / 0.06, 0, 1)"]})

def p_focusglint():
    """A single 'ding' twinkle on top of the head as the concentration peaks."""
    comps = {
        "minecraft:emitter_rate_instant": {"num_particles": 1},
        "minecraft:emitter_lifetime_once": {"active_time": 0.3},
        "minecraft:emitter_shape_point": {"offset": [0, 0.15, 0]},
        "minecraft:particle_lifetime_expression": {"max_lifetime": 0.3},
        "minecraft:particle_initial_speed": 0,
        "minecraft:particle_motion_dynamic": {},
    }
    uv = {"texture_width": 275, "texture_height": 25, "flipbook": {"base_UV": [0, 0], "size_UV": [25, 25], "step_UV": [25, 0],
          "frames_per_second": 36, "max_frame": 11, "stretch_to_lifetime": True}}
    pth, tw, th = T_SKY
    return {"format_version": "1.10.0", "particle_effect": {
        "description": {"identifier": "cobblemon:focusblast_focusglint",
                        "basic_render_parameters": {"material": "particles_blend", "texture": pth}},
        "components": dict(comps, **{
            "minecraft:particle_appearance_billboard": {"size": [0.75, 0.75], "facing_camera_mode": "rotate_xyz", "uv": uv},
            "minecraft:particle_appearance_tinting": {"color": [1, 1, 1, 1]}})}}

def p_bodyaura():
    """Rising streaks of light around the body while the user charges (energy, not flame)."""
    comps = {
        "minecraft:emitter_initialization": {"creation_expression": "v.entity_height = 1; v.entity_width = 1;"},
        "minecraft:emitter_rate_steady": {"spawn_rate": 34, "max_particles": 60},
        "minecraft:emitter_lifetime_once": {"active_time": 0.75},
        "minecraft:emitter_shape_disc": {"offset": [0, "v.entity_height * 0.5 * v.particle_random_3", 0],
                                         "radius": "0.5 * v.entity_width + 0.2", "plane_normal": "y", "surface_only": True,
                                         "direction": [0, 1, 0]},
        "minecraft:particle_lifetime_expression": {"max_lifetime": "0.32 + 0.2 * v.particle_random_1"},
        "minecraft:particle_initial_speed": "2.0 + 1.4 * v.particle_random_2",
        "minecraft:particle_motion_dynamic": {"linear_drag_coefficient": 1.2},
    }
    fade = "(1 - math.pow(v.particle_age / v.particle_lifetime, 2))"
    return particle("focusblast_aura", T_BEAM, comps, None, UV_BEAM,
                    [f"(0.32 + 0.2 * v.particle_random_4) * {fade}", "0.045"], camera="lookat_direction",
                    tinting={"color": ["0.55 + 0.4 * v.particle_random_4", "0.85 + 0.15 * v.particle_random_4", "1", f"0.85 * {fade}"]})

def p_auramotes():
    comps = {
        "minecraft:emitter_initialization": {"creation_expression": "v.entity_height = 1; v.entity_width = 1;"},
        "minecraft:emitter_rate_steady": {"spawn_rate": 22, "max_particles": 40},
        "minecraft:emitter_lifetime_once": {"active_time": 0.8},
        "minecraft:emitter_shape_disc": {"offset": [0, "v.entity_height * 0.8 * v.particle_random_3", 0],
                                         "radius": "0.45 * v.entity_width + 0.25", "plane_normal": "y",
                                         "direction": [0, 1, 0]},
        "minecraft:particle_lifetime_expression": {"max_lifetime": "0.4 + 0.25 * v.particle_random_1"},
        "minecraft:particle_initial_speed": "0.8 + 0.8 * v.particle_random_2",
        "minecraft:particle_motion_dynamic": {"linear_drag_coefficient": 0.6},
    }
    fade = "(1 - v.particle_age / v.particle_lifetime)"
    sz = f"(0.09 + 0.06 * v.particle_random_4) * {fade}"
    return particle("focusblast_auramotes", T_DOTS, comps, None, UV_DOT, [sz, sz],
                    tinting=gradient("v.particle_random_4", [(0.0, WHITE), (0.6, CYAN), (1.0, VIOLET)]))

# ================================================================= the impact (fired from the target's animation)
TSCALE = "math.clamp(0.55 + 0.45 * v.entity_radius, 0.7, 1.8)"   # the target's own size

def burst(count, active=0.2):
    return {
        "minecraft:emitter_initialization": {"creation_expression": "v.entity_radius = 0.6;"},
        "minecraft:emitter_rate_instant": {"num_particles": count},
        "minecraft:emitter_lifetime_once": {"active_time": active},
    }

def p_impactflash():
    k = "(v.particle_age / v.particle_lifetime)"
    comps = dict(burst(1), **{
        "minecraft:emitter_shape_point": {},
        "minecraft:particle_lifetime_expression": {"max_lifetime": 0.15},
        "minecraft:particle_initial_speed": 0,
        "minecraft:particle_motion_dynamic": {}})
    sz = f"{TSCALE} * (0.9 + 0.8 * (1 - math.pow(1 - {k}, 3)))"
    return particle("focusblast_impactflash", T_LFO, comps, None, UV_LFO5, [sz, sz],
                    tinting={"color": [f"1 - 0.25 * {k}", "1", "1", f"1 - {k} * {k}"]})

def p_impactstar():
    comps = dict(burst(1), **{
        "minecraft:emitter_shape_point": {},
        "minecraft:particle_lifetime_expression": {"max_lifetime": 0.22},
        "minecraft:particle_initial_speed": 0,
        "minecraft:particle_motion_dynamic": {}})
    uv = {"flipbook": {"base_UV": [0, 0], "size_UV": [32, 32], "step_UV": [0, 32], "frames_per_second": 24,
                       "max_frame": 5, "stretch_to_lifetime": True}}
    sz = f"2.1 * {TSCALE}"
    return particle("focusblast_impactstar", T_HIT, comps, None, uv, [sz, sz], tinting={"color": [0.85, 0.97, 1, 1]})

def p_impactlines():
    comps = dict(burst(1), **{
        "minecraft:emitter_shape_point": {},
        "minecraft:particle_lifetime_expression": {"max_lifetime": 0.26},
        "minecraft:particle_initial_speed": 0,
        "minecraft:particle_motion_dynamic": {}})
    uv = {"flipbook": {"base_UV": [0, 0], "size_UV": [64, 64], "step_UV": [64, 0], "frames_per_second": 20,
                       "max_frame": 5, "stretch_to_lifetime": True}}
    sz = f"3.3 * {TSCALE}"
    return particle("focusblast_impactlines", T_DASH, comps, None, uv, [sz, sz],
                    tinting=gradient("v.particle_age / v.particle_lifetime", [(0.0, WHITE), (0.5, '#FFC8F2FF'), (1.0, '#B48CDCFF')]))

def p_impactring(second=False):
    delay = 0.07 if second else 0.0
    dur = 0.38 if second else 0.32
    uv = manual_frames(delay, dur, 12, 20, 20)
    comps = dict(burst(1), **{
        "minecraft:emitter_shape_point": {},
        "minecraft:particle_lifetime_expression": {"max_lifetime": r(delay + dur)},
        "minecraft:particle_initial_speed": 0,
        "minecraft:particle_motion_dynamic": {}})
    sz = f"{4.0 if second else 3.2} * {TSCALE} * math.clamp((v.particle_age - {delay}) * 100, 0, 1)"
    col = [0.62, 0.62, 1, 0.8] if second else [0.78, 0.97, 1, 1]
    return particle("focusblast_impactring2" if second else "focusblast_impactring", T_RING, comps, None, uv, [sz, sz],
                    tinting={"color": col})

def p_impactsparks():
    comps = dict(burst(30), **{
        "minecraft:emitter_shape_sphere": {"radius": f"0.25 * {TSCALE}", "surface_only": True, "direction": "outwards"},
        "minecraft:particle_lifetime_expression": {"max_lifetime": "0.35 + 0.3 * v.particle_random_1"},
        "minecraft:particle_initial_speed": "7 + 5 * v.particle_random_2",
        "minecraft:particle_motion_dynamic": {"linear_acceleration": [0, -3, 0], "linear_drag_coefficient": 3.6}})
    fade = "(1 - v.particle_age / v.particle_lifetime)"
    sz = f"(0.12 + 0.08 * v.particle_random_3) * (0.4 + 0.6 * {fade})"
    return particle("focusblast_impactsparks", T_DOTS, comps, None, UV_DOT, [sz, sz],
                    tinting=gradient("v.particle_random_3", [(0.0, WHITE), (0.5, CYAN), (1.0, VIOLET)]))

def p_impactshards():
    comps = dict(burst(16), **{
        "minecraft:emitter_shape_sphere": {"radius": f"0.3 * {TSCALE}", "surface_only": True, "direction": "outwards"},
        "minecraft:particle_lifetime_expression": {"max_lifetime": "0.2 + 0.12 * v.particle_random_1"},
        "minecraft:particle_initial_speed": "11 + 6 * v.particle_random_2",
        "minecraft:particle_motion_dynamic": {"linear_drag_coefficient": 5}})
    fade = "(1 - v.particle_age / v.particle_lifetime)"
    return particle("focusblast_impactshards", T_BEAM, comps, None, UV_BEAM,
                    [f"(0.7 + 0.5 * v.particle_random_3) * {fade}", f"0.08 * {fade}"], camera="lookat_direction",
                    tinting=gradient("v.particle_random_3", [(0.0, WHITE), (1.0, PALE)]))

def p_impactground():
    uv = manual_frames(0.0, 0.42, 12, 20, 20)
    comps = dict(burst(1), **{
        "minecraft:emitter_shape_point": {"offset": [0, 0.05, 0]},
        "minecraft:particle_lifetime_expression": {"max_lifetime": 0.42},
        "minecraft:particle_initial_speed": 0,
        "minecraft:particle_motion_dynamic": {}})
    sz = f"3.6 * {TSCALE}"
    return particle("focusblast_impactground", T_RING, comps, None, uv, [sz, sz], camera="emitter_transform_xz",
                    tinting={"color": [0.66, 0.9, 1, "0.85 - 0.6 * v.particle_age / v.particle_lifetime"]})

# ================================================================= animations
PATH_LAYERS = ['orb', 'orbaura', 'orbmotes', 'orbswirl', 'orbrays', 'orbglints', 'trail', 'motes']   # draw order matters: orb first
SHARED_T0 = ['launchring', 'launchburst', 'gather', 'gatherlines']

def vec(v):
    return [r(c, 3) for c in v]

def lerp(a, b, k):
    return [a[i] + (b[i] - a[i]) * k for i in range(len(a))]

def keyframes(points):
    """points: list of (time, value) -> dense keyframes every 0.05 s, linearly blended."""
    pts = sorted(points)
    out = {}
    tt = 0.0
    times = sorted(set([p[0] for p in pts] + [round(i * STEP, 4) for i in range(int(pts[-1][0] / STEP) + 1)]))
    for x in times:
        for (t0, v0), (t1, v1) in zip(pts, pts[1:]):
            if t0 <= x <= t1:
                k = 0 if t1 == t0 else (x - t0) / (t1 - t0)
                out[t(x)] = vec(lerp(v0, v1, smooth(k)))
                break
    return out

def actor_animation():
    rot = [(0.0, [0, 0, 0]), (0.1, [7, 0, 0]), (0.22, [8, 0, 0]), (0.4, [-6, 0, 0]), (0.65, [-9, 0, 0]),
           (0.8, [-10, 0, 0]), (0.92, [-16, 0, 0]), (0.98, [15, 0, 0]), (1.06, [17, 0, 0]), (1.2, [7, 0, 0]),
           (1.36, [2, 0, 0]), (1.5, [0, 0, 0]), (ACTOR_LEN, [0, 0, 0])]
    pos = [(0.0, [0, 0, 0]), (0.1, [0, -1.2, 0]), (0.22, [0, -1.6, 0.4]), (0.4, [0, 0.4, 0.2]), (0.65, [0, 0.8, 0.4]),
           (0.8, [0, 1.0, 0.5]), (0.92, [0, 1.4, 1.4]), (0.98, [0, -0.6, -2.2]), (1.06, [0, -1.0, -2.6]),
           (1.2, [0, -0.4, -1.5]), (1.36, [0, 0, -0.4]), (1.5, [0, 0, 0]), (ACTOR_LEN, [0, 0, 0])]
    scale = [(0.0, [1, 1, 1]), (0.12, [1.04, 0.95, 1.04]), (0.22, [1.05, 0.94, 1.05]), (0.4, [0.98, 1.04, 0.98]),
             (0.8, [0.98, 1.05, 0.98]), (0.92, [0.97, 1.06, 0.97]), (0.98, [1.05, 0.95, 1.05]), (1.1, [1.0, 1.0, 1.0]),
             (ACTOR_LEN, [1, 1, 1])]
    rk, pk, sk = keyframes(rot), keyframes(pos), keyframes(scale)
    # concentration tremble while the orb charges (0.25-0.85): a small side-to-side shiver
    for key in list(pk):
        x = float(key)
        if 0.25 <= x <= 0.85:
            amp = 0.22 + 0.18 * smooth((x - 0.25) / 0.6)
            pk[key][0] = r(amp * (1 if round(x / STEP) % 2 == 0 else -1), 3)
    bones = {'root_part': {'rotation': rk, 'position': pk, 'scale': sk}}
    arm_pts = [(k[0], [c * (k[2] if len(k) > 2 else 1) for c in ARM_POSES[k[1]]]) for k in ARM_KEYS]
    left = keyframes(arm_pts)
    right = {k: vec([v[0], -v[1], -v[2]]) for k, v in left.items()}
    for lb, rb in ARM_BONES:
        bones[lb] = {'rotation': left}
        bones[rb] = {'rotation': right}
    bones['head'] = {'rotation': keyframes([(k, [v, 0, 0]) for k, v in HEAD_KEYS])}
    return {
        'animation_length': ACTOR_LEN,
        'bones': bones,
        'particle_effects': {
            t(0.02): {'effect': 'cobblemon:focusblast_focus', 'locator': 'middle'},
            t(0.14): [{'effect': 'cobblemon:focusblast_aura', 'locator': 'root'},
                      {'effect': 'cobblemon:focusblast_auramotes', 'locator': 'root'}],
            t(0.2): {'effect': 'cobblemon:focusblast_focusglint', 'locator': 'top'},
        },
        'sound_effects': {
            t(0.02): {'effect': 'move.focusblast.focus'},
            t(0.35): {'effect': 'move.focusblast.charge'},
            t(0.88): {'effect': 'move.focusblast.launch'},
        },
    }

def target_animation():
    # Started in the same tick as the user's animation; holds still until the orb arrives, so the whole
    # impact (particles, sounds, knock-back) is on the client clock with the orb's flight.
    I = IMPACT + PARTICLE_LAG
    pos = [(0.0, [0, 0, 0]), (I, [0, 0, 0]), (I + 0.04, [0, 1.2, 6.0]), (I + 0.12, [0, 0.8, 8.0]), (I + 0.24, [0, 0.2, 5.0]),
           (I + 0.38, [0, 0, 2.0]), (I + 0.55, [0, 0, 0.5]), (I + 0.7, [0, 0, 0])]
    rot = [(0.0, [0, 0, 0]), (I, [0, 0, 0]), (I + 0.04, [-13, 0, 0]), (I + 0.12, [-11, 0, 4]), (I + 0.24, [-6, 0, -3]),
           (I + 0.38, [-2, 0, 1]), (I + 0.55, [0, 0, 0]), (I + 0.7, [0, 0, 0])]
    sc = [(0.0, [1, 1, 1]), (I, [1, 1, 1]), (I + 0.04, [1.07, 0.92, 1.07]), (I + 0.14, [0.97, 1.03, 0.97]), (I + 0.3, [1, 1, 1]),
          (I + 0.7, [1, 1, 1])]
    def sparse(points):   # exact keyframes (no densifying needed for a hit reaction)
        return {t(k): vec(v) for k, v in points}
    impact = [{'effect': f'cobblemon:focusblast_{e}', 'locator': loc} for e, loc in (
        ('impactflash', 'target'), ('impactstar', 'target'), ('impactlines', 'target'), ('impactring', 'target'),
        ('impactring2', 'target'), ('impactsparks', 'target'), ('impactshards', 'target'), ('impactground', 'root'))]
    return {
        'animation_length': r(I + 0.7),
        'bones': {'root_part': {'position': sparse(pos), 'rotation': sparse(rot), 'scale': sparse(sc)}},
        'particle_effects': {t(I): impact},
        'sound_effects': {t(I): [{'effect': 'impact.fighting'}, {'effect': 'move.focusblast.target'}]},
    }

def build_animation_file():
    return {'format_version': '1.8.0', 'animations': {
        'animation.focusblast.actor': actor_animation(),
        'animation.focusblast.target': target_animation()}}

def play(anim):
    return f"q.play_animation(q.bedrock_stateful('focusblast', '{anim}', 'endures_primary_animations'))"

USER_HIT = "q.entity.is_user == true && q.missed == false"
USER_MISS = "q.entity.is_user == true && q.missed == true"
TARGET_HIT = "q.entity.is_user == false && q.missed(q.entity.uuid) == false && q.hurt(q.entity.uuid) == true"

def build_effect_file():
    # Every keyframe costs a server tick in 1.7.3, so the whole start is one `parallel` (one tick).
    start = [{'type': 'entity_molang', 'expressions': [play('actor')]}]
    for layer in PATH_LAYERS:
        start.append({'type': 'entity_particles', 'entityCondition': USER_HIT, 'effect': f'cobblemon:focusblast_{layer}',
                      'locators': ['root'], 'targetLocators': ['target']})
        start.append({'type': 'entity_particles', 'entityCondition': USER_MISS, 'effect': f'cobblemon:focusblast_{layer}_miss',
                      'locators': ['root'], 'targetLocators': ['target']})
    for layer in SHARED_T0:
        start.append({'type': 'entity_particles', 'effect': f'cobblemon:focusblast_{layer}', 'locators': ['root']})
    start.append({'type': 'entity_molang', 'entityCondition': TARGET_HIT, 'expressions': [play('target')]})
    return {'timeline': [
        {'type': 'add_holds', 'holds': ['effects']},
        {'type': 'parallel', 'keyframes': start},
        # the parallel above already used one tick; release the battle as the orb lands so the HP bar
        # (and, 10% of the time, Cobblemon's own Sp. Def drop effect) follows the impact
        {'type': 'pause', 'pause': r(IMPACT + PARTICLE_LAG - 0.05)},
        {'type': 'remove_holds', 'holds': ['effects']},
        {'type': 'pause', 'pause': 0.8},
    ]}

def all_particles():
    out = []
    for variant in ('hit', 'miss'):
        out += [p_orb(variant), p_orbaura(variant), p_orbmotes(variant), p_swirl(variant), p_rays(variant), p_glints(variant),
                p_trail(variant), p_motes(variant)]
    out += [p_gather(), p_gatherlines(), p_launchring(), p_launchburst(), p_focus(), p_focusglint(), p_bodyaura(),
            p_auramotes(), p_impactflash(), p_impactstar(), p_impactlines(), p_impactring(), p_impactring(True),
            p_impactsparks(), p_impactshards(), p_impactground()]
    return out

def write(path, data):
    with open(path, 'w') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write('\n')
    print('wrote', os.path.relpath(path, ROOT))

if __name__ == '__main__':
    os.makedirs(PART_DIR, exist_ok=True)
    wanted = set()
    for p in all_particles():
        pid = p['particle_effect']['description']['identifier'].split(':')[1]
        wanted.add(pid + '.particle.json')
        write(os.path.join(PART_DIR, pid + '.particle.json'), p)
    for stale in set(os.listdir(PART_DIR)) - wanted:
        os.remove(os.path.join(PART_DIR, stale))
        print('removed stale', stale)
    write(ANIM_OUT, build_animation_file())
    write(EFFECT_OUT, build_effect_file())
