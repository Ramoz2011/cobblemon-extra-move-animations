"""Generates Flare Blitz's particle effects, generic animation file and action effect.

Outputs (paths relative to the repo root):
  src/main/resources/assets/cobblemon/bedrock/particles/moves/flareblitz/*.particle.json
  src/main/resources/assets/cobblemon/bedrock/generic/animations/moves/flareblitz.animation.json
  src/main/resources/data/cobblemon/action_effects/moves/flareblitz.json

Edit the constants below and re-run `python3 docs/tools/flareblitz_gen.py`; don't hand-edit the outputs.
Design notes and the reasoning behind the numbers: docs/flareblitz_assets.md.

The machinery is Brave Bird's (docs/tools/bravebird_gen.py), with a ground charge instead of a dive.
- The server measures the gap to the target (v.fb_units, in the user's model units) and starts one
  of 33 dash animations (dash_0 .. dash_32, 8-unit steps) or, on a miss, its dashmiss_* twin. The dash
  animation carries the whole root_part translation: crouch, launch, charge, hit-stop, rebound and the
  way home.
- The actor animation (actor_recoil / actor / actor_miss) carries rotation, squash and stretch, the
  heat tremble, the head, arm and wing bones, the sounds and the effects of the slow moments (the ring
  of flames at the feet, the launch, the recoil).
- Everything that has to stay glued to the Pokemon (the gathering flame streams, the heat aura, the
  fireball and its spiralling rings, the trails, the explosion) is fired by the dash animation at T0,
  while root_part is still at rest, with `v.du` (the dash length) and `v.miss` in its
  pre_effect_script. Those emitters work in the frame the root locator had at T0 (unscaled, -z
  towards the target) and evaluate the same curves the dash animation is made of. A root_part offset
  of u model units is u/16 * q.entity_scale blocks in that frame, and its x comes out mirrored.
- Particle positions are interpolated between client ticks and particles are born a tick after their
  emitter, so the particle clock trails the model clock; PARTICLE_LAG compensates.
"""
import json, math, os

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..')
RES = os.path.join(ROOT, 'src/main/resources')
PART_DIR = os.path.join(RES, 'assets/cobblemon/bedrock/particles/moves/flareblitz')
ANIM_OUT = os.path.join(RES, 'assets/cobblemon/bedrock/generic/animations/moves/flareblitz.animation.json')
EFFECT_OUT = os.path.join(RES, 'data/cobblemon/action_effects/moves/flareblitz.json')

# ---------------------------------------------------------------- timing (seconds of animation time)
T0 = 0.02            # the path-locked emitters fire here, while root_part is still exactly at rest
REST_END = 0.03      # root_part stays at rest until here
GATHER0 = 0.06       # the first flame stream sets off
CROUCH = 0.34        # the crouch has settled; the heat keeps building
IGNITE = 0.60        # white-hot flash: the Pokemon bursts into flame
DASH0 = 0.62         # launch
IMPACT = 0.96        # contact
HITSTOP = 1.02       # end of the hit-stop
REBOUND = 1.12       # top of the rebound: recoil burst, the battle's recoil hold is released
RETURN0, RETURN1 = 1.30, 1.62   # the way home
ACTOR_LEN = 1.70
PARTICLE_LAG = 0.175 # particle clock behind the model clock (see the module docstring)
T_IN = T0 + PARTICLE_LAG        # animation time that a path-locked particle's age 0 stands for
# Debug only: FB_SLOW=4 python3 docs/tools/flareblitz_gen.py writes a 4x slow-motion build, so the
# effects' placement can be checked without the timing in the way. Always ship with SLOW = 1.
SLOW = float(os.environ.get('FB_SLOW', '1'))
# Debug only: FB_FORCE_MISS=1 makes every use play the miss variant (to check its look without needing
# a real miss). Always ship without it.
FORCE_MISS = os.environ.get('FB_FORCE_MISS') == '1'
EMIT_IN = T0 + 0.075            # animation time that an emitter's age 0 stands for (first tick)
FX_LEAD = 0.075      # the target animation fires its particles this early so they show on the hit frame
STEP = 0.025
CURVE_RANGE = 1.90

# ---------------------------------------------------------------- dash
DASH_STEP = 8        # model units between dash variants (half a block at scale 1)
DASH_VARIANTS = 32   # dash_0 .. dash_32 cover 0 .. 256 units
DASH_FALLBACK = 64   # used when there's no target entity (the distance expression yields -1)
REACH = 0.40         # the user stops with its centre this many max(width, height) from the target's edge
M0, M1 = 0.3, 1.3    # Hermite tangents of the charge (gaps per unit of charge time): quick start, still speeding up at contact
REBOUND_UNITS = 20.0 # how far the collision throws the user back (model units)
SWERVE = 22.0        # miss: sideways offset as the fireball streaks past the target (model units)

SCALE_EXPR = ("v.fb_s = (q.user.species.hitbox_width > 0 && q.user.species.hitbox_fixed == 0)"
              " ? math.clamp(q.user.width / q.user.species.hitbox_width, 0.1, 8)"
              " : math.max(q.user.species.base_scale, 0.1)")
DISTANCE_EXPR = (
    f"{SCALE_EXPR}; v.fb_units = (q.target.width > 0) ? math.clamp((q.user.distance_to_pos(q.target.x, q.target.y, q.target.z)"
    f" - 0.5 * q.target.width - {REACH} * math.max(q.user.width, q.user.height)) * 16 / v.fb_s, 0, {DASH_STEP * DASH_VARIANTS}) : -1"
)

# ---------------------------------------------------------------- palette (#AARRGGBB)
# Cobblemon's own fire ramp (flamecharge / flamewheel): white, pale yellow, yellow, orange, red-orange, ember.
FIRE = [(0.0, '#FFFFFFFF'), (0.2, '#FFFFE872'), (0.4, '#FFFFCC00'), (0.55, '#FFFF9400'), (0.75, '#FFFF4700'),
        (0.9, '#FFFF4700'), (1.0, '#FF531C0E')]
WHITE = '#FFFFFFFF'
HOT = '#FFFFF6D2'     # white-hot
GOLD_L = '#FFFFEA80'
GOLD = '#FFFFD040'
AMBER = '#FFFFA51E'
ORANGE = '#FFFF7A10'
RED = '#FFE8400C'


# ================================================================= helpers
def t(x):
    s = f"{x:.4f}".rstrip('0').rstrip('.')
    return s if '.' in s else s + '.0'


def tk(x):
    """Keyframe key for design time x (scaled by the slow-motion debug factor)."""
    return t(x * SLOW)


def r(x, n=4):
    v = round(x, n)
    return 0 if v == 0 else v


def clamp(v, a, b):
    return max(a, min(b, v))


def smooth(x):
    x = clamp(x, 0.0, 1.0)
    return x * x * (3 - 2 * x)


def ease_out(x, p=2.0):
    x = clamp(x, 0.0, 1.0)
    return 1 - (1 - x) ** p


def ease_in(x, p=2.0):
    x = clamp(x, 0.0, 1.0)
    return x ** p


EASES = {'s': smooth, 'o': ease_out, 'i': ease_in, 'l': lambda x: clamp(x, 0.0, 1.0)}


def keyed(points):
    """points: [(time, value, ease)], ease = how the segment ENDING at this point is shaped."""
    def fn(x):
        if x <= points[0][0]:
            return points[0][1]
        for (a, va, _), (b, vb, e) in zip(points, points[1:]):
            if x <= b:
                return va + (vb - va) * EASES[e]((x - a) / (b - a))
        return points[-1][1]
    return fn


# ================================================================= the path (model units, animation space)
def herm(s):
    """Share of the gap covered over the charge, s in 0..1: cubic Hermite with tangents M0 and M1."""
    return (3 * s * s - 2 * s ** 3) + M0 * (s ** 3 - 2 * s * s + s) + M1 * (s ** 3 - s * s)


def F_hit(x):
    if x <= DASH0:
        return 0.0
    if x <= IMPACT:
        return herm((x - DASH0) / (IMPACT - DASH0))
    if x <= RETURN0:
        return 1.0
    return 1.0 - smooth((x - RETURN0) / (RETURN1 - RETURN0))


V_IMPACT = M1 / (IMPACT - DASH0)   # dF/dt arriving at the target (gaps per second)
OVERSHOOT = 0.35                   # miss: how far past the target the fireball runs (gaps)
BRAKE = 0.22                       # miss: braking time after passing the target


def F_miss(x):
    """Same charge, but it streaks on past the target, brakes, and comes home."""
    if x <= IMPACT:
        return F_hit(x)
    if x <= IMPACT + BRAKE:
        p = V_IMPACT * BRAKE / OVERSHOOT       # ease-out exponent that keeps the arrival speed
        return 1.0 + OVERSHOOT * ease_out((x - IMPACT) / BRAKE, p)
    return (1 + OVERSHOOT) * (1 - smooth((x - IMPACT - BRAKE) / (1.52 - IMPACT - BRAKE)))


ZC_hit = keyed([(0, 0, 'l'), (REST_END, 0, 'l'), (CROUCH, 3.0, 's'), (IGNITE, 3.6, 's'), (DASH0 + 0.06, 0, 's'),
                (IMPACT, 0, 'l'), (0.99, -1.5, 's'), (HITSTOP, -1.5, 'l'), (REBOUND, REBOUND_UNITS, 'o'),
                (RETURN0, REBOUND_UNITS + 2, 's'), (RETURN1, 0, 's')])
ZC_miss = keyed([(0, 0, 'l'), (REST_END, 0, 'l'), (CROUCH, 3.0, 's'), (IGNITE, 3.6, 's'), (DASH0 + 0.06, 0, 's')])
Y_hit = keyed([(0, 0, 'l'), (REST_END, 0, 'l'), (CROUCH, -2.2, 's'), (IGNITE, -2.6, 's'), (DASH0 + 0.06, 1.4, 'o'),
               (IMPACT - 0.08, 0.6, 's'), (IMPACT, 0.3, 's'), (HITSTOP, 0.3, 'l'), (REBOUND, 7.0, 'o'),
               (RETURN0, 4.0, 's'), (1.46, 6.5, 'o'), (RETURN1, 0, 'i')])
Y_miss = keyed([(0, 0, 'l'), (REST_END, 0, 'l'), (CROUCH, -2.2, 's'), (IGNITE, -2.6, 's'), (DASH0 + 0.06, 1.4, 'o'),
                (IMPACT - 0.08, 0.6, 's'), (IMPACT, 0.5, 's'), (IMPACT + 0.16, 3.0, 'o'), (1.32, 6.0, 'o'),
                (1.52, 0, 'i')])
X_miss = keyed([(0, 0, 'l'), (DASH0 + 0.10, 0, 'l'), (IMPACT - 0.04, SWERVE, 's'), (IMPACT + BRAKE, SWERVE + 4, 's'),
                (1.52, 0, 's')])
# root_part pitch (+ = nose down) and, for the miss, the bank into the swerve
TH_hit = keyed([(0, 0, 'l'), (REST_END, 0, 'l'), (CROUCH, 12, 's'), (IGNITE - 0.05, 8, 's'), (IGNITE, -6, 's'),
                (DASH0 + 0.07, 14, 's'), (IMPACT, 18, 's'), (IMPACT + 0.03, 8, 's'), (HITSTOP, 8, 'l'),
                (REBOUND - 0.03, -20, 's'), (REBOUND + 0.08, -12, 's'), (RETURN0, -6, 's'), (1.42, -10, 's'),
                (1.54, -4, 's'), (RETURN1, 0, 's')])
TH_miss = keyed([(0, 0, 'l'), (REST_END, 0, 'l'), (CROUCH, 12, 's'), (IGNITE - 0.05, 8, 's'), (IGNITE, -6, 's'),
                 (DASH0 + 0.07, 14, 's'), (IMPACT, 16, 's'), (IMPACT + 0.10, -10, 's'), (1.20, -8, 's'),
                 (1.36, -6, 's'), (1.52, 0, 's')])
PH_miss = keyed([(0, 0, 'l'), (DASH0 + 0.10, 0, 'l'), (IMPACT - 0.10, 20, 's'), (IMPACT + 0.06, 8, 's'), (1.22, 0, 's')])


def deriv(fn, x, h=0.005):
    return (fn(min(x + h, CURVE_RANGE)) - fn(max(x - h, 0))) / (min(x + h, CURVE_RANGE) - max(x - h, 0))


def speed01(x):
    """Charge speed normalised to 1 at the impact (shared by every variant, it's only used for looks)."""
    return clamp(deriv(F_hit, x) / V_IMPACT, 0, 1) if DASH0 <= x <= IMPACT else 0.0


def integral(rate):
    def fn(x):
        n = int(x / 0.005)
        return sum(rate(i * 0.005) * 0.005 for i in range(n))
    return fn


# looks
HEAT = keyed([(0, 0, 'l'), (GATHER0 + 0.04, 0, 'l'), (CROUCH, 0.55, 's'), (IGNITE - 0.02, 1.0, 's'),
              (DASH0 + 0.04, 0.6, 's'), (DASH0 + 0.10, 0, 's')])                       # flames licking up the body
GLOWK = keyed([(0, 0, 'l'), (0.12, 0, 'l'), (IGNITE - 0.02, 1.0, 'i'), (IGNITE + 0.04, 0.35, 's'),
               (DASH0 + 0.10, 0, 's')])                                                # red-hot body glow
SHELL = keyed([(0, 0, 'l'), (IGNITE - 0.01, 0, 'l'), (DASH0 + 0.05, 1, 'o'), (IMPACT, 1, 'l'),
               (IMPACT + 0.04, 0, 's')])                                               # the fireball (hit)
SHELL_M = keyed([(0, 0, 'l'), (IGNITE - 0.01, 0, 'l'), (DASH0 + 0.05, 1, 'o'), (IMPACT, 1, 'l'),
                 (IMPACT + 0.20, 0, 's')])                                             # miss: it gutters out
FLOW = integral(lambda x: 2.2 + 4.5 * speed01(x))      # shell phase: puffs flow from the nose to the tail
SPIN = integral(lambda x: 2.4 + 2.6 * speed01(x))      # ring phase: rings slide back along the fireball


def slowed(expr):
    """Particle/emitter age -> design time (identity unless the FB_SLOW debug factor is set)."""
    return expr if SLOW == 1 else f"({expr}) / {SLOW:g}"


def sample(fn):
    n = int(round(CURVE_RANGE / STEP)) + 1
    return [r(fn(i * STEP)) for i in range(n)]


def curve(fn, inp):
    return {"type": "linear", "input": inp, "horizontal_range": t(CURVE_RANGE), "nodes": sample(fn)}


TIN = slowed(f"v.particle_age + {r(T_IN)}")
EIN = slowed(f"v.emitter_age + {r(EMIT_IN)}")
PATH_FNS = {
    'variable.fb_f': F_hit, 'variable.fb_fm': F_miss, 'variable.fb_zc': ZC_hit, 'variable.fb_zcm': ZC_miss,
    'variable.fb_y': Y_hit, 'variable.fb_ym': Y_miss, 'variable.fb_xm': X_miss,
    'variable.fb_th': TH_hit, 'variable.fb_thm': TH_miss, 'variable.fb_ph': PH_miss,
}


def path_curves(extra=None):
    c = {k: curve(f, TIN) for k, f in PATH_FNS.items()}
    for k, f in (extra or {}).items():
        c[k] = curve(f, TIN)
    return c


SIZES = [
    "v.bl = math.clamp(math.max(v.entity_width, v.entity_height), 0.5, 3.0)",   # body size
    "v.rr = math.max(0.6 * v.bl, 0.45) + 0.1",          # a ball just outside the body: what wraps the Pokemon
    "v.fs = math.clamp(0.45 + 0.5 * v.bl, 0.7, 1.9)",    # flame scale: big on small Pokemon, capped on giants
    "v.ib = math.clamp(0.6 + 0.45 * v.bl, 0.8, 1.7)",    # explosion scale: grows much slower than the body
    f"v.tt = {TIN}",
]
# anchor: path point (root) and pitched body centre, recomputed every tick before the motion
ANCHOR = [
    "v.sc = (q.entity_scale > 0 ? q.entity_scale : 1) / 16",
    "v.px = -v.miss * v.fb_xm * v.sc",
    "v.py = (v.fb_y + v.miss * (v.fb_ym - v.fb_y)) * v.sc",
    "v.pz = (v.fb_zc + v.miss * (v.fb_zcm - v.fb_zc) - v.du * (v.fb_f + v.miss * (v.fb_fm - v.fb_f))) * v.sc",
    "v.th = v.fb_th + v.miss * (v.fb_thm - v.fb_th)",
    "v.ph = v.miss * v.fb_ph",
    "v.hc = 0.5 * v.entity_height",
    "v.cx = v.px - v.hc * math.cos(v.th) * math.sin(v.ph)",
    "v.cy = v.py + v.hc * math.cos(v.th) * math.cos(v.ph)",
    "v.cz = v.pz - v.hc * math.sin(v.th)",
] + SIZES
FALLBACK = "v.du = 0; v.miss = 0; v.entity_width = 1; v.entity_height = 1;"
SC = "(q.entity_scale > 0 ? q.entity_scale : 1) / 16"


def fixed_anchor(x, nose=0.0):
    """Body centre (or a point `nose` body-lengths in front of it) frozen at animation time x, hit/miss mixed."""
    yh, ym = Y_hit(x), Y_miss(x)
    zh, zm = ZC_hit(x), ZC_miss(x)
    fh, fm = F_hit(x), F_miss(x)
    th, tm = math.radians(TH_hit(x)), math.radians(TH_miss(x))
    ph = math.radians(PH_miss(x))
    cx = f"(-v.miss * {r(X_miss(x))} * {SC} - v.miss * 0.5 * v.entity_height * {r(math.cos(tm) * math.sin(ph))})"
    cy = (f"(({r(yh)} + v.miss * {r(ym - yh)}) * {SC} + 0.5 * v.entity_height"
          f" * ({r(math.cos(th))} + v.miss * {r(math.cos(tm) * math.cos(ph) - math.cos(th))}))")
    cz = (f"(({r(zh)} + v.miss * {r(zm - zh)} - v.du * ({r(fh)} + v.miss * {r(fm - fh)})) * {SC}"
          f" - 0.5 * v.entity_height * ({r(math.sin(th))} + v.miss * {r(math.sin(tm) - math.sin(th))})"
          f" - {nose} * v.bl)")
    return cx, cy, cz


def tex(path, w, h):
    return f"textures/particles/{path}", w, h


T_PUFF = tex('generic/fire/cloudyfire_white', 160, 16)   # 10 frames 16x16: a white puff that swells and breaks up
T_FLAME = tex('generic/fire/flame', 56, 10)              # 7 frames 8x10: a pixel flame growing (pre-coloured)
T_EMBER = tex('generic/fire/ember', 25, 5)               # 5 frames 5x5: an ember going out
T_SPARK = tex('generic/sparkle/glowingsparkle_yellow', 8, 32)   # 4 frames 8x8, big to small
T_SCORCH = tex('moves/explosion_floorscorch', 48, 48)
T_RING = tex('generic/ring/giantring_white', 448, 64)    # 7 frames 64x64: a white ring expanding and breaking up
T_BEAM = tex('generic/smallbeam', 140, 91)
T_SKY = tex('generic/skyding', 275, 25)                  # 11 frames 25x25: a four-point star twinkling
T_BURST = tex('generic/dashburst', 320, 64)              # 5 frames 64x64: radial burst lines
T_GLOW = tex('moves/bravebird_glow', 32, 32)             # round soft glow (docs/tools/bravebird_textures.py)

UV_BEAM = {"uv": [70, 42], "uv_size": [70, 7]}    # right half of one smallbeam frame: a soft streak
UV_GLOW = {"uv": [0, 0], "uv_size": [32, 32]}
UV_SCORCH = {"uv": [0, 0], "uv_size": [48, 48]}


def frame_uv(index, fw, fh, horizontal=True):
    """Static UV of frame `index` (a MoLang expression) of a sheet laid out left-to-right or top-to-bottom."""
    return {"uv": [f"{fw} * ({index})", 0] if horizontal else [0, f"{fh} * ({index})"], "uv_size": [fw, fh]}


def puff_frame(k, first=1, last=8):
    """cloudyfire frame for a 0..1 progress: the puff swells (low frames) and breaks up (high frames)."""
    return frame_uv(f"{first} + math.floor(math.clamp({k}, 0, 0.999) * {last - first + 1})", 16, 16)


def manual_frames(start, duration, frames, fw, fh, first=0, horizontal=True, age="v.tt"):
    """Static UV whose frame is picked from time: plays `frames` frames between start and start+duration."""
    f = f"(math.floor(math.clamp(({age} - {start}) / {duration}, 0, 0.999) * {frames}) + {first})"
    return {"uv": [f"{fw} * {f}", 0] if horizontal else [0, f"{fh} * {f}"], "uv_size": [fw, fh]}


def gradient(inp, stops):
    return {"color": {"interpolant": inp, "gradient": {t(k): v for k, v in stops}}}


def fire(inp):
    return gradient(inp, FIRE)


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


def locked(count, end_time, pos, extra_update=None, anchor=None):
    """A path-locked layer: every particle spawned at once, positioned by the parametric motion."""
    upd = (ANCHOR if anchor is None else anchor) + (extra_update or [])
    return {
        "minecraft:emitter_initialization": {"creation_expression": FALLBACK},
        "minecraft:emitter_rate_instant": {"num_particles": count},
        "minecraft:emitter_lifetime_once": {"active_time": r(end_time * SLOW - T0)},
        "minecraft:emitter_shape_point": {},
        "minecraft:particle_initialization": {"per_update_expression": ";".join(upd) + ";"},
        "minecraft:particle_lifetime_expression": {"max_lifetime": r(end_time * SLOW - T_IN)},
        "minecraft:particle_initial_speed": 0,
        "minecraft:particle_motion_parametric": {"relative_position": pos},
    }


def frozen(count, end_time, pos, extra_update=None):
    """Like locked(), for layers frozen at one point of the path: no path curves needed."""
    return locked(count, end_time, pos, extra_update, anchor=SIZES)


SINPHI = "math.sqrt(1 - math.pow(2 * v.particle_random_2 - 1, 2))"
COSPHI = "(2 * v.particle_random_2 - 1)"


def sphere_dir(theta="(360 * v.particle_random_1)"):
    return (f"{SINPHI} * math.cos({theta})", COSPHI, f"{SINPHI} * math.sin({theta})")


def c3(*parts):
    """Sum per axis of several 3-tuples of expressions."""
    return [" + ".join(f"({p[i]})" for p in parts) for i in range(3)]


CENTRE = ("v.cx", "v.cy", "v.cz")


# ================================================================= gathering (0.06 - 0.60)
# Golden flame streams rush in from all around and pour into the body (SV). Each particle belongs to
# one of N_STREAMS streams (picked by its first random); a stream's start time, direction and curl
# come from its index, so all of a stream's particles ride the same curving path.
N_STREAMS = 12
STREAM = [
    f"v.k = math.floor(v.particle_random_1 * {N_STREAMS})",
    f"v.s0 = {GATHER0} + 0.40 * math.mod(v.k * 0.618034 + 0.1, 1)",       # set-off time
    "v.sd = 0.15 + 0.05 * math.mod(v.k * 0.754878 + 0.3, 1)",              # travel time
    "v.az = v.k * 137.508 + 25",                                          # where it comes from
    "v.ey = -0.15 + 0.95 * math.mod(v.k * 0.381966 + 0.55, 1)",            # height of its origin (-0.15 .. 0.8)
    "v.eh = math.sqrt(1 - v.ey * v.ey)",
    "v.r0 = 1.8 + 1.1 * v.bl",                                            # starting distance (blocks)
]


def stream_pos(lag):
    """Point of the particle's stream that the head passed `lag` seconds ago."""
    u = f"math.clamp((v.tt - {lag} - v.s0) / v.sd, 0, 1)"
    w = f"math.pow({u}, 1.7)"                   # share of the way covered: the streams accelerate in
    rad = f"(v.r0 * (1 - {w}) + 0.15 * v.bl * {w})"
    ang = f"(v.az + 75 * (1 - {w}))"            # and curl as they come
    return c3(CENTRE, (f"{rad} * v.eh * math.cos({ang})", f"{rad} * v.ey", f"{rad} * v.eh * math.sin({ang})")), u


def stream_vis(lag, u):
    return f"math.clamp((v.tt - {lag} - v.s0) * 60, 0, 1) * math.clamp((1 - {u}) * 20, 0, 1)"


def p_gather():
    """The streams themselves: chains of fire puffs, white-gold at the head, orange further back."""
    lag = "(0.075 * math.pow(v.particle_random_2, 1.4))"
    pos, u = stream_pos(lag)
    vis = stream_vis(lag, u)
    age = "math.pow(v.particle_random_2, 1.4)"           # 0 at the head, 1 at the end of the chain
    sz = f"(0.34 - 0.16 * {age}) * (0.7 + 0.3 * v.bl) * (0.8 + 0.4 * v.particle_random_3) * {vis}"
    comps = locked(168, IGNITE, pos, STREAM)
    comps["minecraft:particle_initial_spin"] = {"rotation": "math.floor(v.particle_random_4 * 4) * 90"}
    return particle("flareblitz_gather", T_PUFF, comps, path_curves(), puff_frame(f"0.15 + 0.7 * {age}"),
                    [sz, sz], tinting=gradient(f"0.12 + 0.5 * {age}", FIRE))


def p_gatherstreak():
    """A bright core line along the front of each stream."""
    lag = "(0.012 * v.particle_random_2)"
    pos, u = stream_pos(lag)
    vis = stream_vis(lag, u)
    comps = locked(36, IGNITE, pos, STREAM)
    return particle("flareblitz_gatherstreak", T_BEAM, comps, path_curves(), UV_BEAM,
                    [f"(0.5 + 0.2 * v.particle_random_3) * (0.7 + 0.3 * v.bl) * {vis}", f"0.07 * {vis}"],
                    camera="lookat_direction", tinting=gradient("v.particle_random_3", [(0.0, WHITE), (1.0, GOLD_L)]))


def p_gathersparks():
    """Glitter thrown off the streams (SV's streams sparkle)."""
    lag = "(0.02 + 0.09 * v.particle_random_2)"
    pos, u = stream_pos(lag)
    jit = "0.22 * v.bl"
    pos = c3(pos, (f"{jit} * (v.particle_random_3 - 0.5)", f"{jit} * (v.particle_random_4 - 0.5)",
                   f"{jit} * (math.mod(v.particle_random_3 * 7.31, 1) - 0.5)"))
    vis = stream_vis(lag, u)
    comps = locked(60, IGNITE, pos, STREAM)
    sz = f"(0.09 + 0.06 * v.particle_random_4) * {vis}"
    return particle("flareblitz_gathersparks", T_SPARK, comps, path_curves(),
                    frame_uv("math.floor(v.particle_random_4 * 3.99)", 8, 8, horizontal=False), [sz, sz],
                    tinting=gradient("v.particle_random_3", [(0.0, WHITE), (0.5, GOLD_L), (1.0, AMBER)]))


def p_heat():
    """Flames licking up the body as the heat builds: puffs climb from the feet to above the head,
    swelling and cooling as they go, faster and denser as the flash nears."""
    extra = {'variable.fb_heat': HEAT}
    ph = "(v.particle_random_3 + 2.4 * v.tt)"
    p = f"({ph} - math.floor({ph}))"            # 0 at the feet, 1 above the head
    ang = f"(360 * v.particle_random_1 + 50 * {p} * (v.particle_random_2 - 0.5))"
    rad = f"(0.42 + 0.18 * math.sin(180 * {p})) * v.bl * (1 - 0.45 * {p})"
    pos = c3(CENTRE, (f"{rad} * math.cos({ang})", f"v.entity_height * (1.15 * {p} - 0.55)", f"{rad} * math.sin({ang})"))
    sz = f"(0.3 + 0.18 * v.particle_random_4) * (0.65 + 0.4 * v.bl) * math.sin(180 * {p}) * v.fb_heat"
    comps = locked(48, DASH0 + 0.12, pos)
    comps["minecraft:particle_initial_spin"] = {"rotation": "math.floor(v.particle_random_4 * 4) * 90"}
    return particle("flareblitz_heat", T_PUFF, comps, path_curves(extra), puff_frame(p, 1, 9), [sz, sz],
                    tinting=fire(f"0.1 + 0.85 * {p}"))


def surface_glows(count, end_time, rgb, alpha, size, extra=None, radius=1.0):
    """Soft glows spread over a ball just outside the body (v.rr). Whatever side the camera is on, the
    near ones sit in front of the model and tint it; a glow at the body centre would be hidden inside
    the model, because particles are drawn after it and test against its depth."""
    d = sphere_dir()
    pos = c3(CENTRE, tuple(f"{radius} * v.rr * {c}" for c in d))
    flick = "(1 + 0.12 * math.sin(v.tt * (900 + 700 * v.particle_random_3) + 360 * v.particle_random_4))"
    sz = f"({size}) * (0.85 + 0.3 * v.particle_random_3) * {flick}"
    comps = locked(count, end_time, pos)
    return comps, [sz, sz], {"color": [str(c) for c in rgb] + [f"({alpha}) * {flick}"]}


def p_heatglow():
    """The red-hot body: faint orange-red glows over the Pokemon while the heat builds (SV turns it red)."""
    comps, size, tint = surface_glows(16, DASH0 + 0.12, (1, 0.42, 0.12), "0.3 * v.fb_gk", "0.95 * v.fs * v.fb_gk")
    return particle("flareblitz_heatglow", T_GLOW, comps, path_curves({'variable.fb_gk': GLOWK}), UV_GLOW, size,
                    tinting=tint)


# ================================================================= ignition (0.59 - 0.86)
IX, IY, IZ = fixed_anchor(IGNITE)


def p_flash():
    """The white-hot flash: the Pokemon flares white for a moment (glows over the whole body)."""
    k = f"math.clamp((v.tt - {IGNITE - 0.01}) / 0.16, 0, 1)"
    on = f"math.clamp((v.tt - {IGNITE - 0.01}) * 70, 0, 1)"
    comps, size, tint = surface_glows(18, IGNITE + 0.16, (1, 0.98, 0.9), f"0.9 * (1 - {k} * {k}) * {on}",
                                      f"1.25 * v.fs * (1 + 0.4 * {k}) * {on}", radius=0.85)
    return particle("flareblitz_flash", T_GLOW, comps, path_curves(), UV_GLOW, size, tinting=tint)


def p_flashstar():
    """A four-point star glinting off the top of the body as it ignites."""
    k = f"math.clamp((v.tt - {IGNITE}) / 0.28, 0, 1)"
    on = f"math.clamp((v.tt - {IGNITE}) * 60, 0, 1)"
    uv = manual_frames(IGNITE, 0.28, 11, 25, 25)
    sz = f"(0.7 + 0.6 * math.sin(180 * {k})) * (0.6 + 0.3 * v.bl) * {on}"    # pixel art: kept small so it stays crisp
    comps = locked(1, IGNITE + 0.28, c3(CENTRE, ("0", "0.6 * v.entity_height", "-0.25 * v.rr")))
    return particle("flareblitz_flashstar", T_SKY, comps, path_curves(), uv, [sz, sz], tinting={"color": [1, 1, 0.92, 1]})


def p_flashlines():
    """Radial burst lines around the ignition."""
    uv = manual_frames(IGNITE, 0.22, 5, 64, 64)
    on = f"math.clamp((v.tt - {IGNITE}) * 60, 0, 1)"
    sz = f"2.3 * (0.5 + 0.55 * v.bl) * {on}"
    comps = frozen(1, IGNITE + 0.22, [IX, IY, IZ])
    return particle("flareblitz_flashlines", T_BURST, comps, None, uv, [sz, sz], tinting={"color": [1, 0.93, 0.6, 1]})


def p_ignite():
    """The flames erupt as it ignites: fire puffs bursting out from the surface of the body."""
    ts = f"(v.tt - {IGNITE})"
    k = f"math.clamp({ts} / 0.32, 0, 1)"
    d = sphere_dir()
    dist = f"(v.rr + 1.0 * v.fs * (1 - math.pow(1 - {k}, 2.4)))"
    pos = [f"{IX} + {dist} * {d[0]}", f"{IY} + {dist} * {d[1]} * 0.7 + 0.35 * v.fs * {k}", f"{IZ} + {dist} * {d[2]}"]
    on = f"math.clamp({ts} * 60, 0, 1)"
    sz = f"(0.45 + 0.2 * v.particle_random_3) * v.fs * (1 + 0.5 * {k}) * (1 - {k} * {k} * {k}) * {on}"
    comps = frozen(30, IGNITE + 0.32, pos)
    comps["minecraft:particle_initial_spin"] = {"rotation": "math.floor(v.particle_random_4 * 4) * 90"}
    return particle("flareblitz_ignite", T_PUFF, comps, None, puff_frame(k, 2, 9), [sz, sz],
                    tinting=fire(f"0.05 + 0.9 * {k}"))


# ================================================================= the fireball (0.60 - 0.96, path-locked)
SHELL_EXTRA = {'variable.fb_sh': SHELL, 'variable.fb_shm': SHELL_M, 'variable.fb_fl': FLOW}
SHV = "(v.fb_sh + v.miss * (v.fb_shm - v.fb_sh))"


def p_shell():
    """The fireball. Puffs flow over a ball just outside the body from its front pole to the back,
    white-hot in front and cooling to orange behind; a third of them stream off the back as a tail.
    From behind the user (the usual view) it is a ring of fire round the Pokemon with the tail
    towards the camera; from the side and the front, flames over the body."""
    ph = "(v.particle_random_3 + v.fb_fl)"
    p = f"({ph} - math.floor({ph}))"            # 0 at the front pole, 1 at the back (or the end of the tail)
    tail = "(v.particle_random_2 < 0.32)"
    th = "(360 * v.particle_random_1 + 25 * math.sin(720 * v.tt + 360 * v.particle_random_4))"
    lat = f"(180 * {p})"
    rad = "(v.rr * (0.92 + 0.16 * v.particle_random_4))"
    ball = (f"{rad} * math.sin({lat}) * math.cos({th})", f"{rad} * math.sin({lat}) * math.sin({th})",
            f"-{rad} * math.cos({lat}) - 0.1 * v.rr")
    trad = f"(v.rr * 0.8 * (1 - 0.7 * {p}))"
    tl = (f"{trad} * math.cos({th})", f"{trad} * math.sin({th})", f"v.rr * (0.75 + 1.4 * {p})")
    pos = c3(CENTRE, tuple(f"({tail} ? ({tl[i]}) : ({ball[i]}))" for i in range(3)))
    sz = f"(0.38 + 0.14 * v.particle_random_4) * v.fs * ({tail} ? (1 - 0.55 * {p}) : (0.75 + 0.35 * math.sin({lat}))) * {SHV}"
    heat = f"({tail} ? (0.42 + 0.55 * {p}) : (0.04 + 0.5 * {p}))"
    comps = locked(124, IMPACT + 0.22, pos)
    comps["minecraft:particle_initial_spin"] = {"rotation": "math.floor(v.particle_random_4 * 4) * 90"}
    return particle("flareblitz_shell", T_PUFF, comps, path_curves(SHELL_EXTRA), puff_frame(f"0.1 + 0.85 * {heat}", 2, 8),
                    [sz, sz], tinting=fire(f"math.clamp({heat} + 0.08 * v.particle_random_2, 0, 1)"))


def p_rings():
    """SV's spiralling rings: three crescents of flame wound around the fireball, spinning and sliding
    back along it while they widen, so the charge reads as a fire vortex."""
    ring = "math.floor(v.particle_random_1 * 3)"
    ph = f"({ring} / 3 + v.fb_sp)"
    rp = f"({ph} - math.floor({ph}))"           # 0 just ahead of the body, 1 well behind it
    spin = f"(1080 * v.tt * (1 + 0.5 * {rp}) + 120 * {ring})"
    a = f"({spin} + 230 * v.particle_random_2)"    # each ring is a 230 degree crescent
    rad = f"v.rr * (1.12 + 0.55 * {rp}) + 0.06 * v.fs * (v.particle_random_3 - 0.5)"
    zc = f"v.rr * (1.9 * {rp} - 0.55) + 0.26 * ({rad}) * math.sin({a})"
    pos = c3(CENTRE, (f"({rad}) * math.cos({a})", f"({rad}) * math.sin({a})", zc))
    tip = "v.particle_random_2"                  # 1 = the leading tip of the crescent
    vis = f"{SHV} * math.sin(180 * math.min({rp} * 1.4, 1))"
    sz = f"(0.26 + 0.18 * {tip}) * v.fs * {vis}"
    comps = locked(108, IMPACT + 0.22, pos)
    return particle("flareblitz_rings", T_GLOW, comps, path_curves(dict(SHELL_EXTRA, **{'variable.fb_sp': SPIN})), UV_GLOW,
                    [sz, sz], tinting=gradient(f"math.clamp(1 - {tip} + 0.4 * {rp}, 0, 1)",
                                               [(0.0, HOT), (0.3, GOLD_L), (0.6, GOLD), (0.85, AMBER), (1.0, ORANGE)]))


def p_core():
    """The fireball's light: white-gold glows over the body (over the model whichever side it is seen
    from) and one big faint halo round it."""
    halo = "(v.particle_random_1 < 0.06)"
    d = sphere_dir("(360 * v.particle_random_3)")
    pos = c3(CENTRE, tuple(f"({halo} ? 0 : 0.8 * v.rr * {c})" for c in d))
    flick = "(1 + 0.12 * math.sin(v.tt * (1300 + 600 * v.particle_random_4) + 360 * v.particle_random_4))"
    sz = f"({halo} ? 3.2 * v.rr : 1.1 * v.fs * (0.85 + 0.3 * v.particle_random_4)) * {SHV} * {flick}"
    comps = locked(20, IMPACT + 0.22, pos)
    return particle("flareblitz_core", T_GLOW, comps, path_curves(SHELL_EXTRA), UV_GLOW, [sz, sz],
                    tinting={"color": ["1", f"{halo} ? 0.8 : 0.95", f"{halo} ? 0.35 : 0.72",
                                       f"({halo} ? 0.3 : 0.42) * {SHV} * {flick}"]})


def trail_like(count_rate, max_particles, active, offset, lifetime, speed=0.0, direction=(0, 0, 1)):
    """Emitter for world-space layers fired by the dash animation. The emitter follows the root locator
    every tick (frame rotation frozen at T0); these particles are left behind along the path."""
    return {
        "minecraft:emitter_initialization": {"creation_expression": FALLBACK},
        "minecraft:emitter_rate_steady": {"spawn_rate": count_rate, "max_particles": max_particles},
        "minecraft:emitter_lifetime_once": {"active_time": active},
        "minecraft:emitter_shape_point": {"offset": offset, "direction": list(direction)},
        "minecraft:particle_lifetime_expression": {"max_lifetime": lifetime},
        "minecraft:particle_initial_speed": speed,
        "minecraft:particle_motion_dynamic": {"linear_drag_coefficient": 3},
    }


TRAIL_EXTRA = {'variable.fb_v': lambda x: deriv(F_hit, x), 'variable.fb_vm': lambda x: deriv(F_miss, x),
               'variable.fb_sp': speed01}
GAP = f"v.du * (v.fb_v + v.miss * (v.fb_vm - v.fb_v)) * {SC} * {0.05 / SLOW:g}"
BLE = "math.clamp(math.max(v.entity_width, v.entity_height), 0.5, 3.0)"
FSE = f"math.clamp(0.45 + 0.5 * {BLE}, 0.7, 1.9)"
ON_CHARGE = f"(({EIN} >= {DASH0} && {EIN} < {IMPACT} + 0.2 * v.miss) ? 1 : 0)"


def trail_curves():
    return {k: curve(f, EIN) for k, f in TRAIL_EXTRA.items()}


def p_trail():
    """Flames shed along the path: puffs left behind at the body that billow up and cool to embers."""
    rate = f"{ON_CHARGE} * (70 + 150 * v.fb_sp) * (1 + v.du / 128)"
    ang = "(360 * v.particle_random_1)"
    rad = f"0.45 * {FSE} * v.particle_random_2"
    offset = [f"{rad} * math.cos({ang})", f"0.5 * v.entity_height + {rad} * math.sin({ang})",
              f"v.particle_random_4 * {GAP} + 0.6 * {FSE}"]
    comps = trail_like(rate, 220, IMPACT + 0.25, offset, "0.32 + 0.22 * v.particle_random_3", speed="0.6 + 0.8 * v.particle_random_2",
                       direction=("(v.particle_random_1 - 0.5)", "0.6", "0.8"))
    comps["minecraft:particle_motion_dynamic"] = {"linear_drag_coefficient": 3, "linear_acceleration": [0, 2.6, 0]}
    comps["minecraft:particle_initial_spin"] = {"rotation": "math.floor(v.particle_random_4 * 4) * 90"}
    k = "(v.particle_age / v.particle_lifetime)"
    sz = f"(0.32 + 0.16 * v.particle_random_3) * {FSE} * (0.8 + 0.6 * {k}) * (1 - {k} * {k} * {k})"
    uv = {"flipbook": {"base_UV": [16, 0], "size_UV": [16, 16], "step_UV": [16, 0], "frames_per_second": 20,
                       "max_frame": 9, "stretch_to_lifetime": True}}
    return particle("flareblitz_trail", T_PUFF, comps, trail_curves(), uv, [sz, sz], tinting=fire(f"0.25 + 0.75 * {k}"))


SMOKE_RGB = ("0.16 + 0.08 * v.particle_random_1", "0.14 + 0.06 * v.particle_random_1", "0.13")


def p_trailsmoke():
    """Dark smoke rolling off the back of the fireball (SV leaves black smoke behind)."""
    rate = f"{ON_CHARGE} * (22 + 40 * v.fb_sp) * (1 + v.du / 160)"
    offset = [f"0.4 * {FSE} * (v.particle_random_1 - 0.5)", f"0.55 * v.entity_height + 0.3 * {FSE} * (v.particle_random_2 - 0.5)",
              f"v.particle_random_4 * {GAP} + 0.9 * {FSE}"]
    comps = trail_like(rate, 90, IMPACT + 0.25, offset, "0.6 + 0.35 * v.particle_random_3", speed="0.4 + 0.5 * v.particle_random_2",
                       direction=("(v.particle_random_1 - 0.5)", "1", "0.5"))
    comps["minecraft:particle_motion_dynamic"] = {"linear_drag_coefficient": 2.5, "linear_acceleration": [0, 1.4, 0]}
    comps["minecraft:particle_initial_spin"] = {"rotation": "math.floor(v.particle_random_4 * 4) * 90"}
    k = "(v.particle_age / v.particle_lifetime)"
    sz = f"(0.4 + 0.18 * v.particle_random_3) * {FSE} * (0.7 + 0.6 * {k})"
    return particle("flareblitz_trailsmoke", T_PUFF, comps, trail_curves(), puff_frame(k, 3, 9), [sz, sz],
                    tinting={"color": list(SMOKE_RGB) + [f"0.75 * (1 - {k} * {k})"]})


def p_trailembers():
    """Embers flung off the fireball."""
    rate = f"{ON_CHARGE} * (30 + 60 * v.fb_sp)"
    offset = [f"0.6 * {FSE} * (v.particle_random_1 - 0.5)", f"0.5 * v.entity_height + 0.5 * {FSE} * (v.particle_random_2 - 0.5)",
              f"v.particle_random_4 * {GAP} + 0.4 * {FSE}"]
    comps = trail_like(rate, 80, IMPACT + 0.25, offset, "0.35 + 0.3 * v.particle_random_3", speed="2.5 + 2.5 * v.particle_random_2",
                       direction=("(v.particle_random_1 - 0.5) * 2", "0.8 + v.particle_random_3", "0.6"))
    comps["minecraft:particle_motion_dynamic"] = {"linear_drag_coefficient": 1.5, "linear_acceleration": [0, -7, 0]}
    k = "(v.particle_age / v.particle_lifetime)"
    uv = {"flipbook": {"base_UV": [0, 0], "size_UV": [5, 5], "step_UV": [5, 0], "frames_per_second": 20,
                       "max_frame": 5, "stretch_to_lifetime": True}}
    sz = "0.11 + 0.05 * v.particle_random_3"
    return particle("flareblitz_trailembers", T_EMBER, comps, trail_curves(), uv, [sz, sz],
                    tinting=gradient(k, [(0.0, HOT), (0.4, GOLD), (1.0, RED)]))


def p_groundtrail():
    """Little flames left burning on the ground along the path."""
    rate = f"{ON_CHARGE} * (14 + 30 * v.fb_sp) * (1 + v.du / 160)"
    hop = f"(v.fb_y + v.miss * (v.fb_ym - v.fb_y)) * {SC}"
    side = "(v.particle_random_2 < 0.5 ? -1 : 1)"
    offset = [f"{side} * (0.1 + 0.4 * v.particle_random_3) * math.max(v.entity_width, 0.6)", f"0.02 - {hop}",
              f"v.particle_random_4 * {GAP}"]
    comps = trail_like(rate, 70, IMPACT + 0.25, offset, "0.4 + 0.25 * v.particle_random_1")
    comps["minecraft:particle_motion_dynamic"] = {}
    k = "(v.particle_age / v.particle_lifetime)"
    grow = f"math.min({k} * 6, 1)"
    sz = f"(0.2 + 0.1 * v.particle_random_3) * math.clamp(0.7 + 0.3 * {BLE}, 0.8, 1.4) * {grow} * (1 - math.pow({k}, 3))"
    curves = dict(trail_curves(), **{'variable.fb_y': curve(Y_hit, EIN), 'variable.fb_ym': curve(Y_miss, EIN)})
    return particle("flareblitz_groundtrail", T_FLAME, comps, curves, flame_uv(f"({k} * 6)"),
                    [sz, f"1.25 * ({sz})"], camera="rotate_y", tinting={"color": [1, 1, 1, 1]})


# ================================================================= the explosion (path-locked, frozen at the contact point)
EX, EY, EZ = fixed_anchor(IMPACT, nose=0.45)
TS = f"(v.tt - {IMPACT})"


def impact_vis(dur, ramp=60):
    return f"math.clamp({TS} * {ramp}, 0, 1) * math.clamp(1 - {TS} / {dur}, 0, 1)"


def p_impactflash():
    """SV whites the screen on contact: a big white flash with a gold rim."""
    k = f"math.clamp({TS} / 0.15, 0, 1)"
    core = "(v.particle_random_1 < 0.34)"
    on = f"math.clamp({TS} * 80, 0, 1)"
    sz = f"({core} ? (2.0 + 1.3 * {k}) : (3.0 + 1.8 * {k})) * v.ib * {on}"
    comps = frozen(3, IMPACT + 0.16, [EX, EY, EZ])
    return particle("flareblitz_impactflash", T_GLOW, comps, None, UV_GLOW, [sz, sz],
                    tinting={"color": ["1", f"{core} ? 1 : 0.86", f"{core} ? 0.94 : 0.45",
                                       f"({core} ? 1 : 0.6) * (1 - {k} * {k}) * {on}"]})


def p_impactfire():
    """The fireball bursts: puffs thrown out around the target, rolling up and cooling to embers."""
    k = f"math.clamp({TS} / 0.48, 0, 1)"
    d = sphere_dir()
    dist = f"v.ib * (0.25 + 1.8 * (1 - math.pow(1 - {k}, 2.4)))"
    pos = [f"{EX} + ({dist}) * {d[0]}",
           f"{EY} + ({dist}) * {d[1]} * 0.75 + 0.6 * v.ib * math.pow({k}, 1.5)",
           f"{EZ} + ({dist}) * ({d[2]} - 0.35)"]
    on = f"math.clamp({TS} * 60, 0, 1)"
    sz = f"(0.48 + 0.3 * v.particle_random_3) * v.ib * (0.8 + 0.7 * {k}) * (1 - math.pow({k}, 3)) * {on}"
    comps = frozen(48, IMPACT + 0.48, pos)
    comps["minecraft:particle_initial_spin"] = {"rotation": "math.floor(v.particle_random_4 * 4) * 90"}
    return particle("flareblitz_impactfire", T_PUFF, comps, None, puff_frame(k, 1, 9), [sz, sz],
                    tinting=fire(f"math.clamp(0.04 + 0.95 * {k} + 0.08 * v.particle_random_4, 0, 1)"))


def p_impactcore():
    """The body of the explosion: big puffs crowding the contact point, white-hot to orange."""
    k = f"math.clamp({TS} / 0.34, 0, 1)"
    d = sphere_dir()
    dist = f"v.ib * (0.15 + 0.6 * v.particle_random_3) * (0.6 + 0.6 * {k})"
    pos = [f"{EX} + ({dist}) * {d[0]}", f"{EY} + ({dist}) * {d[1]} + 0.3 * v.ib * {k}", f"{EZ} + ({dist}) * {d[2]}"]
    on = f"math.clamp({TS} * 60, 0, 1)"
    sz = f"(0.75 + 0.3 * v.particle_random_4) * v.ib * (1 + 0.4 * {k}) * (1 - math.pow({k}, 4)) * {on}"
    comps = frozen(16, IMPACT + 0.34, pos)
    comps["minecraft:particle_initial_spin"] = {"rotation": "math.floor(v.particle_random_4 * 4) * 90"}
    return particle("flareblitz_impactcore", T_PUFF, comps, None, puff_frame(k, 3, 8), [sz, sz],
                    tinting=fire(f"0.75 * {k}"))


def p_impactlines():
    """Streaks of fire bursting outward."""
    k = f"math.clamp({TS} / 0.3, 0, 1)"
    ang = "(360 * v.particle_random_1)"
    dist = f"v.ib * (0.3 + 2.5 * (1 - math.pow(1 - {k}, 2)))"
    fwd = "(0.1 + 0.6 * v.particle_random_2)"
    pos = [f"{EX} + ({dist}) * math.cos({ang})", f"{EY} + ({dist}) * math.sin({ang})", f"{EZ} - ({dist}) * {fwd}"]
    vis = impact_vis(0.3)
    comps = frozen(20, IMPACT + 0.3, pos)
    return particle("flareblitz_impactlines", T_BEAM, comps, None, UV_BEAM,
                    [f"(1.15 - 0.65 * {k}) * v.ib * {vis}", f"0.075 * math.sqrt(v.ib) * {vis}"], camera="lookat_direction",
                    tinting=gradient("v.particle_random_3", [(0.0, HOT), (0.5, GOLD), (1.0, ORANGE)]))


def p_impactring():
    """Two shock rings around the blast. Camera-facing, so they read from every side; the 64-texel ring
    sheet stays crisp at this size (the 20-texel largering2 turns into big pale squares)."""
    second = "(v.particle_random_1 < 0.5 ? 0 : 1)"
    dl = f"(0.05 * {second})"
    dur = f"(0.3 + 0.1 * {second})"
    k = f"math.clamp(({TS} - {dl}) / {dur}, 0, 1)"
    uv = {"uv": [f"64 * math.floor({k} * 6.99)", 0], "uv_size": [64, 64]}
    on = f"math.clamp(({TS} - {dl}) * 80, 0, 1)"
    sz = f"({second} > 0.5 ? 3.3 : 2.5) * v.ib * {on}"
    comps = frozen(2, IMPACT + 0.42, [EX, EY, EZ])
    return particle("flareblitz_impactring", T_RING, comps, None, uv, [sz, sz],
                    tinting={"color": ["1", f"{second} > 0.5 ? 0.62 : 0.86", f"{second} > 0.5 ? 0.2 : 0.45",
                                       f"({second} > 0.5 ? 0.7 : 0.95) * {on} * (1 - 0.6 * {k})"]})


def p_impactsmoke():
    """Black smoke rolling out of the blast once the fire has flashed (SV)."""
    dl = "(0.06 + 0.1 * v.particle_random_4)"
    k = f"math.clamp(({TS} - {dl}) / 0.85, 0, 1)"
    d = sphere_dir()
    dist = f"v.ib * (0.45 + 1.3 * (1 - math.pow(1 - {k}, 2)))"
    pos = [f"{EX} + ({dist}) * {d[0]}", f"{EY} + ({dist}) * math.abs({d[1]}) * 0.5 + 1.1 * v.ib * {k}",
           f"{EZ} + ({dist}) * ({d[2]} - 0.25)"]
    on = f"math.clamp(({TS} - {dl}) * 30, 0, 1)"
    sz = f"(0.7 + 0.3 * v.particle_random_3) * v.ib * (0.75 + 0.7 * {k}) * {on}"
    comps = frozen(16, IMPACT + 1.02, pos)
    comps["minecraft:particle_initial_spin"] = {"rotation": "math.floor(v.particle_random_4 * 4) * 90"}
    return particle("flareblitz_impactsmoke", T_PUFF, comps, None, puff_frame(k, 3, 9), [sz, sz],
                    tinting={"color": list(SMOKE_RGB) + [f"0.82 * (1 - {k} * {k}) * {on}"]})


def p_impactembers():
    """Embers and sparks sprayed by the blast, falling back."""
    k = f"math.clamp({TS} / 0.6, 0, 1)"
    d = sphere_dir()
    dist = f"v.ib * 2.6 * (1 - math.pow(1 - {k}, 2.2))"
    pos = [f"{EX} + ({dist}) * {d[0]}", f"{EY} + ({dist}) * (math.abs({d[1]}) + 0.2) - 2.2 * {k} * {k} * v.ib",
           f"{EZ} + ({dist}) * ({d[2]} - 0.4)"]
    vis = impact_vis(0.6)
    comps = frozen(26, IMPACT + 0.6, pos)
    sz = f"(0.13 + 0.07 * v.particle_random_3) * {vis}"
    uv = frame_uv(f"math.floor(math.clamp({k} * 5, 0, 4.99))", 5, 5)
    return particle("flareblitz_impactembers", T_EMBER, comps, None, uv, [sz, sz],
                    tinting=gradient(k, [(0.0, HOT), (0.35, GOLD), (0.8, ORANGE), (1.0, RED)]))


def p_missfizzle():
    """Miss: the fireball runs past, brakes and gutters out in a puff of smoke."""
    mx, my, mz = fixed_anchor(IMPACT + BRAKE)
    ts = f"(v.tt - {IMPACT + 0.12})"
    k = f"math.clamp({ts} / 0.6, 0, 1)"
    d = sphere_dir()
    dist = f"v.fs * (0.2 + 0.7 * (1 - math.pow(1 - {k}, 2)))"
    pos = [f"{mx} + ({dist}) * {d[0]}", f"{my} + ({dist}) * {d[1]} * 0.6 + 0.7 * v.fs * {k}", f"{mz} + ({dist}) * {d[2]}"]
    on = f"math.clamp({ts} * 30, 0, 1)"
    sz = f"(0.5 + 0.3 * v.particle_random_3) * v.fs * (0.7 + 0.6 * {k}) * {on}"
    comps = frozen(12, IMPACT + 0.72, pos)
    comps["minecraft:particle_initial_spin"] = {"rotation": "math.floor(v.particle_random_4 * 4) * 90"}
    return particle("flareblitz_missfizzle", T_PUFF, comps, None, puff_frame(k, 3, 9), [sz, sz],
                    tinting={"color": ["0.3", "0.27", "0.25", f"0.75 * (1 - {k} * {k}) * {on}"]})


# ================================================================= slow moments (fired by the actor / target animations)
def burst(count, active=0.2):
    return {
        "minecraft:emitter_initialization": {"creation_expression": "v.entity_width = 1; v.entity_height = 1;"},
        "minecraft:emitter_rate_instant": {"num_particles": count},
        "minecraft:emitter_lifetime_once": {"active_time": active},
    }


BODY = "math.clamp(math.max(v.entity_width, v.entity_height), 0.5, 3.5)"
GROUND = "math.clamp(0.6 + 0.4 * math.max(v.entity_width, v.entity_height), 0.8, 1.8)"   # ground effects grow slowly with size
FOOT_R = "(0.35 + 0.55 * math.clamp(0.5 * v.entity_width, 0.25, 1.6))"   # just outside the feet

FLICKER = "math.mod(math.floor(v.particle_age * 14 + 4 * v.particle_random_1), 4)"


def flame_uv(k_grow):
    """Pixel flame: the 7-frame sheet grows over frames 0-3, then flickers on frames 3-6."""
    return frame_uv(f"({k_grow} < 1) ? math.floor(math.clamp({k_grow}, 0, 0.999) * 4) : (3 + {FLICKER})", 8, 10)


def p_footflames():
    """A ring of flames catching around the feet one after another as the heat builds."""
    life = (DASH0 + 0.14) - 0.22
    comps = dict(burst(12), **{
        "minecraft:emitter_shape_disc": {"offset": [0, 0.02, 0], "radius": f"{FOOT_R} * {GROUND}", "plane_normal": "y",
                                         "surface_only": True},
        "minecraft:particle_lifetime_expression": {"max_lifetime": r(life)},
        "minecraft:particle_initial_speed": 0,
        "minecraft:particle_motion_dynamic": {}})
    d0 = "(0.25 * v.particle_random_1)"       # each flame catches at its own moment
    grow = f"math.clamp((v.particle_age - {d0}) / 0.1, 0, 1.0001)"
    on = f"(v.particle_age >= {d0} ? 1 : 0)"
    die = f"math.clamp(({r(life)} - v.particle_age) / 0.1, 0, 1)"
    sz = f"(0.22 + 0.1 * v.particle_random_2) * {GROUND} * math.min({grow}, 1) * {die} * {on}"
    return particle("flareblitz_footflames", T_FLAME, comps, None, flame_uv(f"(({grow}) * 1.0)"),
                    [sz, f"1.25 * ({sz})"], camera="rotate_y", tinting={"color": [1, 1, 1, 1]})


def p_launchring():
    """The ground catches as it launches: fire puffs racing outward along the ground from the feet."""
    comps = dict(burst(18), **{
        "minecraft:emitter_shape_disc": {"offset": [0, 0.12, 0], "radius": f"0.25 * {BODY}", "plane_normal": "y",
                                         "surface_only": True, "direction": "outwards"},
        "minecraft:particle_lifetime_expression": {"max_lifetime": "0.3 + 0.12 * v.particle_random_2"},
        "minecraft:particle_initial_speed": f"(5 + 2 * v.particle_random_3) * {GROUND}",
        "minecraft:particle_motion_dynamic": {"linear_drag_coefficient": 7, "linear_acceleration": [0, 1.5, 0]}})
    comps["minecraft:particle_initial_spin"] = {"rotation": "math.floor(v.particle_random_4 * 4) * 90"}
    k = "(v.particle_age / v.particle_lifetime)"
    sz = f"(0.36 + 0.14 * v.particle_random_4) * {GROUND} * (1 - {k} * {k})"
    return particle("flareblitz_launchring", T_PUFF, comps, None, puff_frame(k, 2, 9), [sz, sz],
                    tinting=fire(f"0.15 + 0.85 * {k}"))


def p_launchdust():
    """Smoke and dust kicked back from the feet by the launch."""
    comps = dict(burst(10), **{
        "minecraft:emitter_shape_disc": {"offset": [0, 0.12, 0], "radius": f"0.3 * {BODY}", "plane_normal": "y",
                                         "surface_only": True, "direction": ["(v.particle_random_1 - 0.5) * 2", 0.5, 1.6]},
        "minecraft:particle_lifetime_expression": {"max_lifetime": "0.45 + 0.25 * v.particle_random_2"},
        "minecraft:particle_initial_speed": "2.0 + 2.0 * v.particle_random_3",
        "minecraft:particle_motion_dynamic": {"linear_drag_coefficient": 4, "linear_acceleration": [0, 0.8, 0]}})
    comps["minecraft:particle_initial_spin"] = {"rotation": "math.floor(v.particle_random_4 * 4) * 90"}
    k = "(v.particle_age / v.particle_lifetime)"
    sz = f"(0.35 + 0.2 * v.particle_random_4) * {BODY} * (0.6 + 0.7 * {k})"
    return particle("flareblitz_launchdust", T_PUFF, comps, None, puff_frame(k, 3, 9), [sz, sz],
                    tinting={"color": ["0.45", "0.41", "0.37", f"0.65 * (1 - {k} * {k})"]})


def recoil_emitter(count, life, active=0.32):
    """Local space, so the effect stays on the body through the stagger."""
    base = {k: v for k, v in burst(count).items() if k != "minecraft:emitter_rate_instant"}
    return dict(base, **{
        "minecraft:emitter_rate_steady": {"spawn_rate": round(count / (active - 0.02), 1), "max_particles": count},
        "minecraft:emitter_lifetime_once": {"active_time": active},
        "minecraft:emitter_local_space": {"position": True, "rotation": False},
        "minecraft:emitter_shape_sphere": {"radius": f"0.45 * {BODY}", "surface_only": True, "direction": "outwards"},
        "minecraft:particle_lifetime_expression": {"max_lifetime": life},
        "minecraft:particle_initial_speed": "0.6 + 0.8 * v.particle_random_2",
        "minecraft:particle_motion_dynamic": {"linear_drag_coefficient": 5}})


def p_recoilfire():
    """Recoil: the blast slams back into the user and flames burst off its body."""
    comps = recoil_emitter(16, "0.25 + 0.15 * v.particle_random_1")
    comps["minecraft:particle_motion_dynamic"] = {"linear_drag_coefficient": 5, "linear_acceleration": [0, 2.5, 0]}
    comps["minecraft:particle_initial_spin"] = {"rotation": "math.floor(v.particle_random_4 * 4) * 90"}
    k = "(v.particle_age / v.particle_lifetime)"
    sz = f"(0.28 + 0.12 * v.particle_random_3) * (0.6 + 0.35 * {BODY}) * (1 - {k} * {k})"
    return particle("flareblitz_recoilfire", T_PUFF, comps, None, puff_frame(k, 2, 9), [sz, sz],
                    tinting=fire(f"0.3 + 0.7 * {k}"))


def p_recoilember():
    """Sparks crackling off the user as it takes the recoil."""
    comps = recoil_emitter(14, "0.2 + 0.15 * v.particle_random_1")
    comps["minecraft:particle_initial_speed"] = "2.5 + 2.5 * v.particle_random_2"
    comps["minecraft:particle_motion_dynamic"] = {"linear_drag_coefficient": 3, "linear_acceleration": [0, -6, 0]}
    k = "(v.particle_age / v.particle_lifetime)"
    uv = frame_uv(f"math.floor(math.clamp({k} * 4, 0, 3.99))", 8, 8, horizontal=False)
    sz = f"(0.16 + 0.08 * v.particle_random_3) * (1 - 0.4 * {k})"
    return particle("flareblitz_recoilember", T_SPARK, comps, None, uv, [sz, sz],
                    tinting=gradient(k, [(0.0, WHITE), (0.5, GOLD), (1.0, ORANGE)]))


def p_smolder():
    """The singed user smoulders on its way home."""
    comps = recoil_emitter(14, "0.6 + 0.3 * v.particle_random_1", active=0.55)
    comps["minecraft:emitter_shape_sphere"] = {"radius": f"0.3 * {BODY}", "surface_only": False,
                                               "direction": ["(v.particle_random_1 - 0.5) * 0.4", 1, "(v.particle_random_3 - 0.5) * 0.4"]}
    comps["minecraft:emitter_local_space"] = {"position": False, "rotation": False}
    comps["minecraft:particle_initial_speed"] = "0.3 + 0.3 * v.particle_random_2"
    comps["minecraft:particle_motion_dynamic"] = {"linear_drag_coefficient": 1.5, "linear_acceleration": [0, 1.2, 0]}
    comps["minecraft:particle_initial_spin"] = {"rotation": "math.floor(v.particle_random_4 * 4) * 90"}
    k = "(v.particle_age / v.particle_lifetime)"
    sz = f"(0.24 + 0.1 * v.particle_random_3) * (0.6 + 0.35 * {BODY}) * (0.6 + 0.8 * {k})"
    return particle("flareblitz_smolder", T_PUFF, comps, None, puff_frame(k, 3, 9), [sz, sz],
                    tinting={"color": ["0.26", "0.23", "0.21", f"0.7 * (1 - {k} * {k})"]})


def p_targetfire():
    """The target is wrapped in flame for a moment."""
    comps = dict(burst(18, 0.1), **{
        "minecraft:emitter_shape_sphere": {"radius": f"0.45 * {BODY}", "surface_only": True, "direction": "outwards"},
        "minecraft:particle_lifetime_expression": {"max_lifetime": "0.4 + 0.3 * v.particle_random_1"},
        "minecraft:particle_initial_speed": "0.8 + 1.2 * v.particle_random_2",
        "minecraft:particle_motion_dynamic": {"linear_drag_coefficient": 3, "linear_acceleration": [0, 3.2, 0]}})
    comps["minecraft:particle_initial_spin"] = {"rotation": "math.floor(v.particle_random_4 * 4) * 90"}
    k = "(v.particle_age / v.particle_lifetime)"
    sz = f"(0.36 + 0.16 * v.particle_random_3) * (0.6 + 0.35 * {BODY}) * (1 - {k} * {k} * {k})"
    return particle("flareblitz_targetfire", T_PUFF, comps, None, puff_frame(k, 1, 9), [sz, sz],
                    tinting=fire(f"0.15 + 0.85 * {k}"))


def p_groundfire():
    """Flames left burning on the ground around the target after the blast (SV), dying down."""
    life = 1.15
    comps = dict(burst(14), **{
        "minecraft:emitter_shape_disc": {"offset": [0, 0.02, 0], "radius": f"(0.55 + 0.45 * v.particle_random_1) * {FOOT_R} * 1.6 * {GROUND}",
                                         "plane_normal": "y", "surface_only": True},
        "minecraft:particle_lifetime_expression": {"max_lifetime": f"{life - 0.3} + 0.3 * v.particle_random_2"},
        "minecraft:particle_initial_speed": 0,
        "minecraft:particle_motion_dynamic": {}})
    d0 = "(0.12 * v.particle_random_3)"
    grow = f"math.clamp((v.particle_age - {d0}) / 0.08, 0, 1.0001)"
    on = f"(v.particle_age >= {d0} ? 1 : 0)"
    die = "math.clamp((v.particle_lifetime - v.particle_age) / 0.35, 0, 1)"
    sz = f"(0.26 + 0.14 * v.particle_random_4) * {GROUND} * math.min({grow}, 1) * {die} * {on}"
    return particle("flareblitz_groundfire", T_FLAME, comps, None, flame_uv(grow), [sz, f"1.25 * ({sz})"],
                    camera="rotate_y", tinting={"color": [1, 1, 1, 1]})


def p_scorch():
    """A scorch mark under the target, fading."""
    comps = dict(burst(1), **{
        "minecraft:emitter_shape_point": {"offset": [0, 0.015, 0]},
        "minecraft:particle_lifetime_expression": {"max_lifetime": 1.5},
        "minecraft:particle_initial_spin": {"rotation": "math.floor(v.particle_random_1 * 4) * 90"},
        "minecraft:particle_initial_speed": 0,
        "minecraft:particle_motion_dynamic": {}})
    k = "(v.particle_age / v.particle_lifetime)"
    sz = f"2.2 * {GROUND} * math.min({k} * 12, 1)"
    return particle("flareblitz_scorch", T_SCORCH, comps, None, UV_SCORCH, [sz, sz], camera="emitter_transform_xz",
                    tinting={"color": [1, 1, 1, f"0.85 * (1 - math.pow({k}, 2.5))"]})


def p_targetsmoke():
    """Smoke rising off the target after the blast."""
    comps = {
        "minecraft:emitter_initialization": {"creation_expression": "v.entity_width = 1; v.entity_height = 1;"},
        "minecraft:emitter_rate_steady": {"spawn_rate": 20, "max_particles": 24},
        "minecraft:emitter_lifetime_once": {"active_time": 0.6},
        "minecraft:emitter_shape_sphere": {"radius": f"0.35 * {BODY}", "surface_only": False,
                                           "direction": ["(v.particle_random_1 - 0.5) * 0.5", 1, "(v.particle_random_3 - 0.5) * 0.5"]},
        "minecraft:particle_lifetime_expression": {"max_lifetime": "0.7 + 0.4 * v.particle_random_2"},
        "minecraft:particle_initial_speed": "0.4 + 0.4 * v.particle_random_4",
        "minecraft:particle_motion_dynamic": {"linear_drag_coefficient": 1.2, "linear_acceleration": [0, 1.3, 0]},
        "minecraft:particle_initial_spin": {"rotation": "math.floor(v.particle_random_4 * 4) * 90"},
    }
    k = "(v.particle_age / v.particle_lifetime)"
    sz = f"(0.36 + 0.15 * v.particle_random_3) * (0.6 + 0.35 * {BODY}) * (0.6 + 0.9 * {k})"
    return particle("flareblitz_targetsmoke", T_PUFF, comps, None, puff_frame(k, 3, 9), [sz, sz],
                    tinting={"color": ["0.22", "0.2", "0.19", f"0.72 * (1 - {k} * {k})"]})


# ================================================================= animations
WING_OPEN = ['wing_open_left', 'wing_open_right', 'wing_left_open', 'wing_right_open', 'wing_open_left1',
             'wing_open_right1', 'wing_open_left_main', 'wing_open_right_main', 'wing_top_left', 'wing_top_right',
             'wing_bottom_left', 'wing_bottom_right']
WING_ANY = ['wing_left', 'wing_right', 'left_wing', 'right_wing', 'wing_upper_left', 'wing_upper_right']
ARMS = ['arm_left', 'arm_right', 'left_upper_arm', 'right_upper_arm', 'left_arm', 'right_arm']
HEAD = ['head']

# scale multipliers (a bone the idle has hidden stays hidden: scale multiplies): wings tuck for the charge
WING_OPEN_S = [(0, 1), (REST_END, 1), (CROUCH, 1.08), (IGNITE, 1.14), (DASH0 + 0.06, 0.66), (IMPACT, 0.64),
               (HITSTOP, 1.15), (REBOUND + 0.06, 1.05), (RETURN0, 1)]
WING_ANY_S = [(0, 1), (REST_END, 1), (CROUCH, 1.05), (IGNITE, 1.10), (DASH0 + 0.06, 0.82), (IMPACT, 0.80),
              (HITSTOP, 1.12), (REBOUND + 0.06, 1.04), (RETURN0, 1)]
WING_MISS_TAIL = [(IMPACT + 0.06, 0.75), (IMPACT + 0.2, 1.05), (RETURN0, 1)]
# arms (+x = swept backwards): braced in the crouch, flung back for the charge, thrown forward by the hit
ARMS_R = [(0, 0), (REST_END, 0), (CROUCH, -12), (IGNITE - 0.04, -18), (IGNITE, 10), (DASH0 + 0.08, 42),
          (IMPACT, 46), (IMPACT + 0.05, -24), (REBOUND, -12), (RETURN0 + 0.05, 0)]
ARMS_R_MISS = [(0, 0), (REST_END, 0), (CROUCH, -12), (IGNITE - 0.04, -18), (IGNITE, 10), (DASH0 + 0.08, 42),
               (IMPACT + 0.05, 46), (IMPACT + 0.25, 10), (1.45, 0)]
# head (+x = down): lowered like a charging bull
HEAD_R = [(0, 0), (REST_END, 0), (CROUCH, 10), (IGNITE - 0.04, 8), (IGNITE, -12), (DASH0 + 0.08, 14), (IMPACT, 16),
          (IMPACT + 0.05, -6), (REBOUND, -14), (RETURN0 + 0.08, 0)]
HEAD_R_MISS = [(0, 0), (REST_END, 0), (CROUCH, 10), (IGNITE - 0.04, 8), (IGNITE, -12), (DASH0 + 0.08, 14),
               (IMPACT + 0.05, 14), (IMPACT + 0.25, -4), (1.45, 0)]

ROOT_SCALE = [(0, (1, 1, 1)), (REST_END, (1, 1, 1)), (CROUCH, (1.08, 0.9, 1.08)), (IGNITE - 0.03, (1.1, 0.88, 1.1)),
              (IGNITE + 0.01, (0.94, 1.1, 0.94)), (DASH0 + 0.08, (0.92, 0.94, 1.16)), (IMPACT - 0.02, (0.9, 0.92, 1.2)),
              (IMPACT + 0.02, (1.16, 0.92, 0.8)), (HITSTOP + 0.02, (0.95, 1.05, 1.06)), (REBOUND, (1, 1, 1)),
              (RETURN1 - 0.08, (1, 1, 1)), (RETURN1 - 0.04, (1.06, 0.92, 1.06)), (ACTOR_LEN, (1, 1, 1))]
ROOT_SCALE_MISS = [(0, (1, 1, 1)), (REST_END, (1, 1, 1)), (CROUCH, (1.08, 0.9, 1.08)), (IGNITE - 0.03, (1.1, 0.88, 1.1)),
                   (IGNITE + 0.01, (0.94, 1.1, 0.94)), (DASH0 + 0.08, (0.92, 0.94, 1.16)), (IMPACT + 0.04, (0.9, 0.92, 1.18)),
                   (IMPACT + 0.2, (1, 1, 1)), (1.46, (1, 1, 1)), (1.50, (1.06, 0.92, 1.06)), (1.56, (1, 1, 1)),
                   (ACTOR_LEN, (1, 1, 1))]
TREMBLE0, TREMBLE1 = 0.12, IGNITE - 0.01   # the heat makes the body tremble, harder as the flash nears


def vec(v):
    return [r(c, 3) for c in v]


def lerpv(a, b, k):
    return [a[i] + (b[i] - a[i]) * k for i in range(len(a))]


def dense_keys(fn, end, tol=0.02):
    """Sample fn (-> list) every STEP up to `end`, drop points that linear interpolation reproduces."""
    n = int(end / STEP + 1e-9)
    xs = [round(i * STEP, 4) for i in range(n + 1)]
    if end - xs[-1] > 1e-6:
        xs.append(end)
    pts = [(x, [float(c) for c in fn(x)]) for x in xs]
    keep = [pts[0]]
    for i in range(1, len(pts) - 1):
        a, b = keep[-1], pts[i + 1]
        k = (pts[i][0] - a[0]) / (b[0] - a[0])
        guess = lerpv(a[1], b[1], k)
        if max(abs(g - v) for g, v in zip(guess, pts[i][1])) > tol:
            keep.append(pts[i])
    keep.append(pts[-1])
    return {t(x * SLOW): vec(v) for x, v in keep}


def fine_keys(fn, start, end, step=0.0125):
    """Keys every `step` between start and end (for the tremble, which dense_keys' STEP would alias)."""
    n = int(round((end - start) / step))
    return {t((start + i * step) * SLOW): vec(fn(start + i * step)) for i in range(n + 1)}


def smooth_keys(points):
    """[(time, value or tuple)] -> smoothstep-blended function returning a list."""
    pts = [(p[0], list(p[1]) if isinstance(p[1], (tuple, list)) else [p[1]]) for p in points]

    def fn(x):
        if x <= pts[0][0]:
            return pts[0][1]
        for (a, va), (b, vb) in zip(pts, pts[1:]):
            if x <= b:
                return lerpv(va, vb, smooth((x - a) / (b - a)))
        return pts[-1][1]
    return fn


def tremble(x):
    """Small, fast, growing shake while the heat builds (model units / degrees)."""
    if not TREMBLE0 <= x <= TREMBLE1:
        return 0.0
    k = (x - TREMBLE0) / (TREMBLE1 - TREMBLE0)
    return k ** 1.5 * math.sin(2 * math.pi * 16 * (x - TREMBLE0))


def actor_animation(variant):
    """variant: 'recoil' (hit, the user takes recoil), 'hit' (hit, no recoil: Protect, Rock Head...), 'miss'."""
    miss = variant == 'miss'
    th = TH_miss if miss else TH_hit
    ph = PH_miss if miss else (lambda x: 0.0)
    jitter = variant == 'recoil'

    def rot(x):
        roll = ph(x) + 2.2 * tremble(x)
        if jitter and REBOUND - 0.06 <= x <= RETURN0:
            k = (x - (REBOUND - 0.06)) / (RETURN0 - REBOUND + 0.06)
            roll += 8 * (1 - k) * math.sin(2 * math.pi * 5.5 * k)
        return [th(x), 0, roll]

    def pos(x):
        p = [0.45 * tremble(x), 0, 0]
        if jitter and REBOUND - 0.04 <= x <= RETURN0:
            k = (x - (REBOUND - 0.04)) / (RETURN0 - REBOUND + 0.04)
            p[0] += 0.9 * (1 - k) * math.sin(2 * math.pi * 6 * k)
        return p

    rot_keys = dense_keys(rot, ACTOR_LEN, 0.15)
    rot_keys.update(fine_keys(rot, TREMBLE0, TREMBLE1))
    pos_keys = dense_keys(pos, ACTOR_LEN, 0.02)
    pos_keys.update(fine_keys(pos, TREMBLE0, TREMBLE1))
    bones = {'root_part': {'rotation': dict(sorted(rot_keys.items(), key=lambda kv: float(kv[0]))),
                           'position': dict(sorted(pos_keys.items(), key=lambda kv: float(kv[0]))),
                           'scale': dense_keys(smooth_keys(ROOT_SCALE_MISS if miss else ROOT_SCALE), ACTOR_LEN, 0.004)}}

    def wing_scale(table):
        pts = table if not miss else [p for p in table if p[0] < IMPACT] + WING_MISS_TAIL
        f = smooth_keys(pts)
        return dense_keys(lambda x: [f(x)[0]] * 3, ACTOR_LEN, 0.004)
    for names, table in ((WING_OPEN, WING_OPEN_S), (WING_ANY, WING_ANY_S)):
        sc = wing_scale(table)
        for b in names:
            bones[b] = {'scale': sc}
    arm = smooth_keys(ARMS_R_MISS if miss else ARMS_R)
    arm_keys = dense_keys(lambda x: [arm(x)[0], 0, 0], ACTOR_LEN, 0.15)
    for b in ARMS:
        bones[b] = {'rotation': arm_keys}
    head = smooth_keys(HEAD_R_MISS if miss else HEAD_R)
    head_keys = dense_keys(lambda x: [head(x)[0], 0, 0], ACTOR_LEN, 0.15)
    for b in HEAD:
        bones[b] = {'rotation': head_keys}

    particles = {tk(0.22): {'effect': 'cobblemon:flareblitz_footflames', 'locator': 'root'},
                 tk(DASH0): [{'effect': 'cobblemon:flareblitz_launchring', 'locator': 'root'},
                             {'effect': 'cobblemon:flareblitz_launchdust', 'locator': 'root'}],
                 tk(RETURN1 if not miss else 1.52): {'effect': 'cobblemon:quickattack_dust', 'locator': 'root'}}
    if variant == 'recoil':
        particles[tk(REBOUND)] = [{'effect': 'cobblemon:flareblitz_recoilfire', 'locator': 'middle'},
                                 {'effect': 'cobblemon:flareblitz_recoilember', 'locator': 'middle'},
                                 {'effect': 'cobblemon:flareblitz_smolder', 'locator': 'middle'}]
    sounds = {tk(GATHER0): {'effect': 'move.flareblitz.gather'},
              tk(IGNITE - 0.02): {'effect': 'move.flareblitz.ignite'},
              tk(DASH0): {'effect': 'move.flareblitz.dash'}}
    if variant == 'recoil':
        sounds[tk(REBOUND)] = {'effect': 'move.flareblitz.recoil'}
    if miss:
        sounds[tk(IMPACT)] = {'effect': 'move.flareblitz.whoosh'}
        sounds[tk(1.22)] = {'effect': 'move.flareblitz.return'}
    else:
        sounds[tk(RETURN0 + 0.01)] = {'effect': 'move.flareblitz.return'}
    return {'animation_length': r(ACTOR_LEN * SLOW), 'bones': bones, 'particle_effects': particles, 'sound_effects': sounds}


LOCKED_COMMON = ['gatherstreak', 'gather', 'gathersparks', 'heat', 'flashstar', 'flashlines', 'ignite', 'shell', 'rings',
                 'trail', 'trailsmoke', 'trailembers', 'groundtrail']
LOCKED_IMPACT = ['impactlines', 'impactembers', 'impactcore', 'impactfire', 'impactring', 'impactsmoke']
LOCKED_MISS = ['missfizzle']
LOCKED_LAST = ['flash', 'impactflash', 'core', 'heatglow']   # big soft glows go last: particles write depth


def dash_animation(units, miss):
    u = float(units)
    if miss:
        fn = lambda x: [X_miss(x), Y_miss(x), ZC_miss(x) - u * F_miss(x)]
    else:
        fn = lambda x: [0.0, Y_hit(x), ZC_hit(x) - u * F_hit(x)]
    script = f"v.du = {units}\nv.miss = {1 if miss else 0}"
    layers = LOCKED_COMMON + (LOCKED_MISS if miss else LOCKED_IMPACT) + [l for l in LOCKED_LAST if not (miss and l == 'impactflash')]
    effects = [{'effect': f'cobblemon:flareblitz_{l}', 'locator': 'root', 'pre_effect_script': script} for l in layers]
    return {
        'animation_length': r(ACTOR_LEN * SLOW),
        'bones': {'root_part': {'position': dense_keys(fn, ACTOR_LEN, 0.02)}},
        'particle_effects': {t(T0): effects},
    }


def target_animation():
    """Started in the same tick as the user's animations; holds still until the contact frame, so the
    knock-back is on the client clock with the dash."""
    I = IMPACT
    pos = [(0.0, [0, 0, 0]), (I, [0, 0, 0]), (I + 0.05, [0, 1.8, 9.0]), (I + 0.15, [0, 1.2, 12.0]),
           (I + 0.3, [0, 0.3, 7.5]), (I + 0.46, [0, 0, 3.0]), (I + 0.62, [0, 0, 0.8]), (I + 0.8, [0, 0, 0])]
    rot = [(0.0, [0, 0, 0]), (I, [0, 0, 0]), (I + 0.05, [-19, 0, 0]), (I + 0.15, [-15, 0, 5]), (I + 0.3, [-8, 0, -4]),
           (I + 0.46, [-2, 0, 2]), (I + 0.62, [0, 0, 0]), (I + 0.8, [0, 0, 0])]
    sc = [(0.0, [1, 1, 1]), (I, [1, 1, 1]), (I + 0.04, [1.1, 0.88, 1.1]), (I + 0.15, [0.97, 1.04, 0.97]),
          (I + 0.3, [1, 1, 1]), (I + 0.8, [1, 1, 1])]

    def exact(points):
        return {tk(k): vec(v) for k, v in points}
    fx = I * SLOW - FX_LEAD
    return {
        'animation_length': r((I + 1.3) * SLOW),
        'bones': {'root_part': {'position': exact(pos), 'rotation': exact(rot), 'scale': exact(sc)}},
        'particle_effects': {t(fx): [{'effect': 'cobblemon:impact_fire', 'locator': 'target'},
                                     {'effect': 'cobblemon:flareblitz_targetfire', 'locator': 'middle'},
                                     {'effect': 'cobblemon:flareblitz_scorch', 'locator': 'root'},
                                     {'effect': 'cobblemon:flareblitz_groundfire', 'locator': 'root'},
                                     {'effect': 'cobblemon:flareblitz_targetsmoke', 'locator': 'middle'}]},
        'sound_effects': {tk(I): [{'effect': 'impact.fire'}, {'effect': 'move.flareblitz.impact'},
                                  {'effect': 'move.flareblitz.blast'}]},
    }


def build_animation_file():
    anims = {'animation.flareblitz.actor_recoil': actor_animation('recoil'),
             'animation.flareblitz.actor': actor_animation('hit'),
             'animation.flareblitz.actor_miss': actor_animation('miss'),
             'animation.flareblitz.target': target_animation()}
    for k in range(DASH_VARIANTS + 1):
        anims[f'animation.flareblitz.dash_{k}'] = dash_animation(k * DASH_STEP, False)
    for k in range(DASH_VARIANTS + 1):
        anims[f'animation.flareblitz.dashmiss_{k}'] = dash_animation(k * DASH_STEP, True)
    return {'format_version': '1.8.0', 'animations': anims}


# ================================================================= action effect
def play(anim):
    return f"q.play_animation(q.bedrock_stateful('flareblitz', '{anim}', 'endures_primary_animations'))"


USER_RECOIL = "q.entity.is_user == true && q.missed == false && q.hurt(q.entity.uuid) == true"
USER_HIT = "q.entity.is_user == true && q.missed == false && q.hurt(q.entity.uuid) == false"
USER_MISS = "q.entity.is_user == true && q.missed == true"
TARGET_HIT = "q.entity.is_user == false && q.missed(q.entity.uuid) == false && q.hurt(q.entity.uuid) == true"
MISSED, HIT = ("true", "false") if FORCE_MISS else ("q.missed == true", "q.missed == false")
if FORCE_MISS:
    USER_RECOIL = USER_HIT = TARGET_HIT = "false"
    USER_MISS = "q.entity.is_user == true"


def build_effect_file():
    # Every entity_* / animation / molang keyframe costs one server tick in 1.7.3, so the whole start
    # is one `parallel` (a single tick). Only the keyframes whose condition holds send anything.
    start = [
        # Cobblemon's per-species hook: a poser that defines a "flareblitz" animation gets it on top.
        # No official poser does, and an unknown name plays nothing.
        {'type': 'animation', 'animation': ['flareblitz']},
        {'type': 'entity_molang', 'entityCondition': USER_RECOIL, 'expressions': [play('actor_recoil')]},
        {'type': 'entity_molang', 'entityCondition': USER_HIT, 'expressions': [play('actor')]},
        {'type': 'entity_molang', 'entityCondition': USER_MISS, 'expressions': [play('actor_miss')]},
    ]
    half = DASH_STEP / 2
    for miss in (False, True):
        name = 'dashmiss' if miss else 'dash'
        mc = MISSED if miss else HIT
        for k in range(DASH_VARIANTS + 1):
            lo, hi = k * DASH_STEP - half, k * DASH_STEP + half
            if k == 0:
                rng = f"v.fb_units >= 0 && v.fb_units < {hi:g}"
            elif k == DASH_VARIANTS:
                rng = f"v.fb_units >= {lo:g}"
            else:
                rng = f"v.fb_units >= {lo:g} && v.fb_units < {hi:g}"
            start.append({'type': 'entity_molang', 'condition': f"{rng} && {mc}", 'expressions': [play(f'{name}_{k}')]})
        start.append({'type': 'entity_molang', 'condition': f"!(v.fb_units >= 0) && {mc}",
                      'expressions': [play(f'{name}_{DASH_FALLBACK // DASH_STEP}')]})
    start.append({'type': 'entity_molang', 'entityCondition': TARGET_HIT, 'expressions': [play('target')]})
    return {'timeline': [
        # "recoil" is the hold Cobblemon's DamageInstruction waits on before it applies recoil damage
        {'type': 'add_holds', 'holds': ['effects', 'recoil']},
        {'type': 'molang', 'expressions': DISTANCE_EXPR},
        {'type': 'parallel', 'keyframes': start},
        # the parallel already used one tick; release the battle on the hit so the target's HP bar drops with it
        {'type': 'pause', 'pause': r(IMPACT * SLOW - 0.05)},
        {'type': 'remove_holds', 'holds': ['effects']},
        # then let the recoil through at the top of the rebound (only matters when the target faints,
        # otherwise Cobblemon applies recoil once this timeline has finished)
        {'type': 'pause', 'pause': r((REBOUND - IMPACT) * SLOW)},
        {'type': 'remove_holds', 'holds': ['recoil']},
        {'type': 'pause', 'pause': r((ACTOR_LEN - REBOUND) * SLOW + 0.05)},
    ]}


def all_particles():
    return [p_gather(), p_gatherstreak(), p_gathersparks(), p_heat(), p_heatglow(), p_flash(), p_flashstar(),
            p_flashlines(), p_ignite(), p_shell(), p_rings(), p_core(), p_trail(), p_trailsmoke(), p_trailembers(),
            p_groundtrail(), p_impactflash(), p_impactfire(), p_impactcore(), p_impactlines(), p_impactring(),
            p_impactsmoke(), p_impactembers(), p_missfizzle(), p_footflames(), p_launchring(), p_launchdust(),
            p_recoilfire(), p_recoilember(), p_smolder(), p_targetfire(), p_groundfire(), p_scorch(), p_targetsmoke()]


def dumps(data):
    """indent=2, but arrays of plain numbers/strings stay on one line (keyframe vectors, curve nodes)."""
    import re
    text = json.dumps(data, indent=2, ensure_ascii=False)
    return re.sub(r'\[\s+((?:-?[\d.e+-]+|"[^"\n]*")(?:,\s+(?:-?[\d.e+-]+|"[^"\n]*"))*)\s+\]',
                  lambda m: '[' + re.sub(r',\s+', ', ', m.group(1)) + ']', text)


def write(path, data):
    with open(path, 'w') as f:
        f.write(dumps(data))
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
