"""Generates Brave Bird's particle effects, generic animation file and action effect.

Outputs (paths relative to the repo root):
  src/main/resources/assets/cobblemon/bedrock/particles/moves/bravebird/*.particle.json
  src/main/resources/assets/cobblemon/bedrock/generic/animations/moves/bravebird.animation.json
  src/main/resources/data/cobblemon/action_effects/moves/bravebird.json

Edit the constants below and re-run `python3 docs/tools/bravebird_gen.py`; don't hand-edit the outputs.
The feather and glow sprites come from docs/tools/bravebird_textures.py. Design notes and the reasoning
behind the numbers: docs/bravebird_assets.md.

How it fits together.
- The server measures the gap to the target (v.bb_units, in the user's model units) and starts one
  of 33 dash animations (dash_0 .. dash_32, 8-unit steps) or, on a miss, its dashmiss_* twin. The
  dash animation carries the whole root_part translation: crouch, take-off hop, low dive, the charge
  itself, the hit-stop, the rebound and the flight home.
- The actor animation (actor_recoil / actor / actor_miss) carries rotation, squash and stretch, the
  wing and arm bones, the sounds and the effects of the slow moments (take-off, recoil sparks).
- Everything that has to stay glued to the charging Pokemon (aura, bird silhouette, beak, trails,
  the impact burst) is fired by the dash animation at T0, while root_part is still at rest, with
  `v.du` (the dash length) and `v.miss` in its pre_effect_script. Those emitters work in the frame
  the root locator had at T0 (unscaled, -z towards the target) and evaluate the same curves the
  dash animation is made of, so they ride exactly the path the model takes. A root_part offset of
  u model units is u/16 * q.entity_scale blocks in that frame, and its x comes out mirrored.
- Particle positions are interpolated between client ticks and particles are born a tick after
  their emitter, so the particle clock trails the model clock; PARTICLE_LAG compensates.
"""
import json, math, os

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..')
RES = os.path.join(ROOT, 'src/main/resources')
PART_DIR = os.path.join(RES, 'assets/cobblemon/bedrock/particles/moves/bravebird')
ANIM_OUT = os.path.join(RES, 'assets/cobblemon/bedrock/generic/animations/moves/bravebird.animation.json')
EFFECT_OUT = os.path.join(RES, 'data/cobblemon/action_effects/moves/bravebird.json')

# ---------------------------------------------------------------- timing (seconds of animation time)
T0 = 0.02            # the path-locked emitters fire here, while root_part is still exactly at rest
REST_END = 0.03      # root_part stays at rest until here (rotation, scale and position)
ANTIC = 0.14         # bottom of the crouch / take-off
RISE = 0.30          # top of the take-off hop
DASH0 = 0.36         # forward motion starts
FINAL = 0.66         # final charge: speed burst, sonic boom, the bird fully formed
BOOM2 = 0.78         # second, smaller boom ring
IMPACT = 0.90        # contact
HITSTOP = 0.96       # end of the hit-stop
REBOUND = 1.06       # top of the rebound: recoil sparks, the battle's recoil hold is released
RETURN0, RETURN1 = 1.26, 1.56   # flight home
ACTOR_LEN = 1.62
PARTICLE_LAG = 0.175 # particle clock behind the model clock (see the module docstring)
T_IN = T0 + PARTICLE_LAG        # animation time that a path-locked particle's age 0 stands for
# Debug only: BB_SLOW=4 python3 docs/tools/bravebird_gen.py writes a 4x slow-motion build, so the
# effects' placement can be checked without the timing in the way. Always ship with SLOW = 1.
SLOW = float(os.environ.get('BB_SLOW', '1'))
EMIT_IN = T0 + 0.075            # animation time that an emitter's age 0 stands for (first tick)
FX_LEAD = 0.075      # the target animation fires its particles this early so they show on the hit frame
STEP = 0.025
CURVE_RANGE = 1.80

# ---------------------------------------------------------------- dash
DASH_STEP = 8        # model units between dash variants (half a block at scale 1)
DASH_VARIANTS = 32   # dash_0 .. dash_32 cover 0 .. 256 units
DASH_FALLBACK = 64   # used when there's no target entity (the distance expression yields -1)
REACH = 0.40         # the user stops with its centre this many max(width, height) from the target's edge
P1 = 0.22            # share of the gap covered by FINAL (the slow, accelerating part)
BOOST = 2.6          # gaps per second right after the speed burst at FINAL
REBOUND_UNITS = 18.0 # how far the collision throws the user back (model units)
SWERVE = 22.0        # miss: sideways offset as the user streaks past the target (model units)

SCALE_EXPR = ("v.bb_s = (q.user.species.hitbox_width > 0 && q.user.species.hitbox_fixed == 0)"
              " ? math.clamp(q.user.width / q.user.species.hitbox_width, 0.1, 8)"
              " : math.max(q.user.species.base_scale, 0.1)")
DISTANCE_EXPR = (
    f"{SCALE_EXPR}; v.bb_units = (q.target.width > 0) ? math.clamp((q.user.distance_to_pos(q.target.x, q.target.y, q.target.z)"
    f" - 0.5 * q.target.width - {REACH} * math.max(q.user.width, q.user.height)) * 16 / v.bb_s, 0, {DASH_STEP * DASH_VARIANTS}) : -1"
)

# ---------------------------------------------------------------- palette (#AARRGGBB)
WHITE = '#FFFFFFFF'
ICE = '#FFE6FBFF'
CYAN_L = '#FFB4F0FF'
CYAN = '#FF6EDCFF'
SKY = '#FF46B4FF'
VIOLET = '#FF9196FF'
INDIGO = '#FF7378F0'


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
def F_hit(x):
    """Share of the gap covered at time x: accelerating dash, a speed burst at FINAL, hold, fly home."""
    if x <= DASH0:
        return 0.0
    if x <= FINAL:
        s = (x - DASH0) / (FINAL - DASH0)
        return P1 * s * s
    if x <= IMPACT:
        u, T = x - FINAL, IMPACT - FINAL
        a = (1 - P1 - BOOST * T) / (T * T)
        return P1 + BOOST * u + a * u * u
    if x <= RETURN0:
        return 1.0
    return 1.0 - smooth((x - RETURN0) / (RETURN1 - RETURN0))


V_IMPACT = BOOST + 2 * (1 - P1 - BOOST * (IMPACT - FINAL)) / (IMPACT - FINAL)   # dF/dt arriving at the target


def F_miss(x):
    """Same charge, but it streaks on past the target, brakes, and flies home."""
    if x <= IMPACT:
        return F_hit(x)
    if x <= 1.10:
        p = V_IMPACT * 0.20 / 0.32       # ease-out exponent that keeps the arrival speed
        return 1.0 + 0.32 * ease_out((x - IMPACT) / 0.20, p)
    return 1.32 * (1 - smooth((x - 1.10) / 0.40))


ZC_hit = keyed([(0, 0, 'l'), (REST_END, 0, 'l'), (ANTIC, 2.5, 's'), (DASH0, 0, 's'), (IMPACT, 0, 'l'),
                (0.93, -1.5, 's'), (HITSTOP, -1.5, 'l'), (REBOUND, REBOUND_UNITS, 'o'),
                (RETURN0, REBOUND_UNITS + 2, 's'), (RETURN1, 0, 's')])
ZC_miss = keyed([(0, 0, 'l'), (REST_END, 0, 'l'), (ANTIC, 2.5, 's'), (DASH0, 0, 's')])
Y_hit = keyed([(0, 0, 'l'), (REST_END, 0, 'l'), (ANTIC, -1.8, 's'), (RISE, 7.0, 'o'), (DASH0, 6.6, 's'),
               (FINAL, 2.4, 's'), (IMPACT, 1.6, 's'), (HITSTOP, 1.6, 'l'), (REBOUND, 7.0, 'o'),
               (RETURN0, 5.5, 's'), (1.40, 8.0, 'o'), (RETURN1, 0, 'i')])
Y_miss = keyed([(0, 0, 'l'), (REST_END, 0, 'l'), (ANTIC, -1.8, 's'), (RISE, 7.0, 'o'), (DASH0, 6.6, 's'),
                (FINAL, 2.4, 's'), (IMPACT, 2.0, 's'), (1.08, 10.0, 'o'), (RETURN0, 9.0, 's'), (1.50, 0, 'i')])
X_miss = keyed([(0, 0, 'l'), (0.70, 0, 'l'), (0.92, SWERVE, 's'), (1.10, SWERVE + 4, 's'), (1.50, 0, 's')])
# root_part pitch (+ = nose down) and, for the miss, the bank into the swerve (+ leans towards +x)
TH_hit = keyed([(0, 0, 'l'), (REST_END, 0, 'l'), (ANTIC, -8, 's'), (0.28, 4, 's'), (DASH0, 10, 's'),
                (0.60, 22, 's'), (0.86, 28, 's'), (IMPACT, 30, 's'), (0.93, 12, 's'), (1.02, -22, 's'),
                (1.12, -12, 's'), (RETURN0, -6, 's'), (1.36, -10, 's'), (1.50, -4, 's'), (RETURN1, 0, 's')])
TH_miss = keyed([(0, 0, 'l'), (REST_END, 0, 'l'), (ANTIC, -8, 's'), (0.28, 4, 's'), (DASH0, 10, 's'),
                 (0.60, 22, 's'), (0.86, 28, 's'), (1.00, -14, 's'), (1.15, -8, 's'), (1.30, -6, 's'),
                 (1.50, 0, 's')])
PH_miss = keyed([(0, 0, 'l'), (0.70, 0, 'l'), (0.86, 20, 's'), (1.02, 8, 's'), (1.15, 0, 's')])


def deriv(fn, x, h=0.005):
    return (fn(min(x + h, CURVE_RANGE)) - fn(max(x - h, 0))) / (min(x + h, CURVE_RANGE) - max(x - h, 0))


def speed01(x):
    """Charge speed normalised to 1 at the impact (shared by every variant, it's only used for looks)."""
    return clamp(deriv(F_hit, x) / V_IMPACT, 0, 1) if x <= IMPACT else 0.0


def flow(x):
    """Integral of the over-the-body air-flow speed (loops/s) used by the body streaks."""
    n = int(x / 0.005)
    return sum((1.4 + 4.0 * speed01(i * 0.005)) * 0.005 for i in range(n))


# looks: aura strength, bird formation, bird burst, bird opacity
AURA = keyed([(0, 0, 'l'), (0.16, 0, 'l'), (0.34, 0.55, 'o'), (0.60, 0.65, 's'), (0.86, 0.9, 's'),
              (0.905, 1.15, 's'), (1.00, 0, 's')])
BIRD_FORM = keyed([(0, 0, 'l'), (0.52, 0, 'l'), (0.70, 1, 'o')])
BIRD_BURST = keyed([(0, 0, 'l'), (IMPACT, 0, 'l'), (1.02, 1, 'o')])
BIRD_ALPHA = keyed([(0, 0, 'l'), (0.52, 0, 'l'), (0.64, 1, 's'), (IMPACT, 1, 'l'), (1.02, 0, 's')])


def slowed(expr):
    """Particle/emitter age -> design time (identity unless the BB_SLOW debug factor is set)."""
    return expr if SLOW == 1 else f"({expr}) / {SLOW:g}"


def sample(fn, inp_offset=0.0):
    n = int(round(CURVE_RANGE / STEP)) + 1
    return [r(fn(i * STEP)) for i in range(n)]


def curve(fn, inp):
    return {"type": "linear", "input": inp, "horizontal_range": t(CURVE_RANGE), "nodes": sample(fn)}


TIN = slowed(f"v.particle_age + {r(T_IN)}")
EIN = slowed(f"v.emitter_age + {r(EMIT_IN)}")
PATH_FNS = {
    'variable.bb_f': F_hit, 'variable.bb_fm': F_miss, 'variable.bb_zc': ZC_hit, 'variable.bb_zcm': ZC_miss,
    'variable.bb_y': Y_hit, 'variable.bb_ym': Y_miss, 'variable.bb_xm': X_miss,
    'variable.bb_th': TH_hit, 'variable.bb_thm': TH_miss, 'variable.bb_ph': PH_miss,
}


def path_curves(inp=TIN, extra=None):
    c = {k: curve(f, inp) for k, f in PATH_FNS.items()}
    for k, f in (extra or {}).items():
        c[k] = curve(f, inp)
    return c


# anchor: path point (root) and pitched body centre, recomputed every tick before the motion
ANCHOR = [
    "v.sc = (q.entity_scale > 0 ? q.entity_scale : 1) / 16",
    "v.px = -v.miss * v.bb_xm * v.sc",
    "v.py = (v.bb_y + v.miss * (v.bb_ym - v.bb_y)) * v.sc",
    "v.pz = (v.bb_zc + v.miss * (v.bb_zcm - v.bb_zc) - v.du * (v.bb_f + v.miss * (v.bb_fm - v.bb_f))) * v.sc",
    "v.th = v.bb_th + v.miss * (v.bb_thm - v.bb_th)",
    "v.ph = v.miss * v.bb_ph",
    "v.hc = 0.5 * v.entity_height",
    "v.cx = v.px - v.hc * math.cos(v.th) * math.sin(v.ph)",
    "v.cy = v.py + v.hc * math.cos(v.th) * math.cos(v.ph)",
    "v.cz = v.pz - v.hc * math.sin(v.th)",
    "v.bl = math.clamp(math.max(v.entity_width, v.entity_height), 0.5, 3.0)",   # body size
    "v.bs = math.clamp(0.5 + 0.6 * v.bl, 0.8, 2.2)",    # bird-of-light scale: big on small birds, capped on giants
    "v.ib = math.clamp(0.6 + 0.4 * v.bl, 0.8, 1.5)",    # impact / shockwave scale: grows much slower than the body
    f"v.tt = {slowed(f'v.particle_age + {r(T_IN)}')}",
]
FALLBACK = "v.du = 0; v.miss = 0; v.entity_width = 1; v.entity_height = 1;"


def fixed_anchor(x, nose=0.0):
    """Body centre (or a point `nose` body-lengths in front of it) frozen at animation time x, hit/miss mixed."""
    sc = "(q.entity_scale > 0 ? q.entity_scale : 1) / 16"
    yh, ym = Y_hit(x), Y_miss(x)
    zh, zm = ZC_hit(x), ZC_miss(x)
    fh, fm = F_hit(x), F_miss(x)
    th, tm = math.radians(TH_hit(x)), math.radians(TH_miss(x))
    ph = math.radians(PH_miss(x))
    hx = ["0", f"(-v.miss * {r(X_miss(x))} * {sc} - v.miss * 0.5 * v.entity_height * {r(math.cos(tm) * math.sin(ph))})"]
    cy = (f"(({r(yh)} + v.miss * {r(ym - yh)}) * {sc} + 0.5 * v.entity_height"
          f" * ({r(math.cos(th))} + v.miss * {r(math.cos(tm) * math.cos(ph) - math.cos(th))}))")
    cz = (f"(({r(zh)} + v.miss * {r(zm - zh)} - v.du * ({r(fh)} + v.miss * {r(fm - fh)})) * {sc}"
          f" - 0.5 * v.entity_height * ({r(math.sin(th))} + v.miss * {r(math.sin(tm) - math.sin(th))})"
          f" - {nose} * v.bl)")
    return hx[1], cy, cz


def tex(path, w, h):
    return f"textures/particles/{path}", w, h


T_LFO = tex('generic/orb/largefadeorb', 143, 13)
T_DOTS = tex('generic/orb/glowing_dots_cyan', 8, 32)
T_BEAM = tex('generic/smallbeam', 140, 91)
T_SKY = tex('generic/skyding', 275, 25)
T_RING = tex('generic/ring/largering2', 240, 20)
T_GUST = tex('vanilla/gust', 384, 32)
T_FLASH = tex('balls/ancientfeatherball/battle/ancientfeatherflash', 768, 64)
T_SMOKE = tex('generic/smoke/smoke', 16, 96)
T_FEATHER = tex('moves/bravebird_feather', 16, 16)
T_GLOW = tex('moves/bravebird_glow', 32, 32)   # round soft glow (docs/tools/bravebird_textures.py)

UV_LFO5 = {"uv": [65, 0], "uv_size": [13, 13]}   # biggest, brightest frame
UV_LFO3 = {"uv": [39, 0], "uv_size": [13, 13]}
UV_DOT = {"uv": [0, 0], "uv_size": [8, 8]}
UV_BEAM = {"uv": [70, 42], "uv_size": [70, 7]}    # right half of one smallbeam frame: a soft streak
UV_FEATHER = {"uv": [0, 0], "uv_size": [16, 16]}
UV_GLOW = {"uv": [0, 0], "uv_size": [32, 32]}


def manual_frames(start, duration, frames, fw, fh, first=0, horizontal=True, age="v.tt"):
    """Static UV whose frame is picked from time: plays `frames` frames between start and start+duration."""
    f = f"(math.floor(math.clamp(({age} - {start}) / {duration}, 0, 0.999) * {frames}) + {first})"
    return {"uv": [f"{fw} * {f}", 0] if horizontal else [0, f"{fh} * {f}"], "uv_size": [fw, fh]}


def window(start, end, ramp=0.03, age="v.tt"):
    return f"math.clamp(({age} - {start}) / {ramp}, 0, 1) * math.clamp(({end} - {age}) / {ramp}, 0, 1)"


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


def locked(count, end_time, pos, extra_update=None):
    """A path-locked layer: every particle spawned at once, positioned by the parametric motion."""
    upd = ANCHOR + (extra_update or [])
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


SINPHI = "math.sqrt(1 - math.pow(2 * v.particle_random_2 - 1, 2))"
COSPHI = "(2 * v.particle_random_2 - 1)"


def sphere_dir(theta="(360 * v.particle_random_1)"):
    return (f"{SINPHI} * math.cos({theta})", COSPHI, f"{SINPHI} * math.sin({theta})")


def c3(*parts):
    """Sum per axis of several 3-tuples of expressions."""
    return [" + ".join(f"({p[i]})" for p in parts) for i in range(3)]


CENTRE = ("v.cx", "v.cy", "v.cz")
PATHPT = ("v.px", "v.py", "v.pz")


# ================================================================= energy forming (0.13 - 0.50)
def p_gather():
    """Streaks rushing in from every side and converging on the body: the Flying energy gathering."""
    d0 = "(0.13 + 0.13 * v.particle_random_4)"
    ln = "(0.10 + 0.05 * v.particle_random_3)"
    k = f"math.clamp((v.tt - {d0}) / {ln}, 0, 1)"
    rad = f"(1.0 + 0.6 * v.bl) * math.pow(1 - {k}, 1.5) + 0.25 * v.bl"
    d = sphere_dir()
    pos = c3(CENTRE, tuple(f"({rad}) * {c}" for c in d))
    win = f"math.clamp((v.tt - {d0}) * 30, 0, 1) * math.clamp((1 - {k}) * 8, 0, 1)"
    comps = locked(22, 0.34, pos)
    return particle("bravebird_gather", T_BEAM, comps, path_curves(), UV_BEAM,
                    [f"(0.35 + 0.25 * v.particle_random_3) * v.bl * {win}", f"0.045 * {win}"],
                    camera="lookat_direction", tinting=gradient("v.particle_random_3", [(0.0, WHITE), (0.6, CYAN_L), (1.0, CYAN)]))


def p_swirl():
    """Two rings of wind spiralling up around the body and spinning faster (the SV / BDSP swirl)."""
    ring = "(v.particle_random_2 < 0.5 ? 0 : 1)"
    s0 = f"(0.16 + 0.07 * {ring})"
    k = f"math.clamp((v.tt - {s0}) / 0.30, 0, 1)"
    spin = f"((1 - 2 * {ring}) * (1100 + 300 * {ring}) * (v.tt - {s0}) * (1 + {k}))"
    ang = f"(360 * v.particle_random_1 + {spin})"
    rad = f"(0.55 + 0.15 * math.sin(180 * {k})) * v.bl * (1 - 0.25 * {k})"
    hgt = f"(0.05 + 1.05 * {k}) * v.entity_height"
    pos = c3(PATHPT, (f"({rad}) * math.cos({ang})", hgt, f"({rad}) * math.sin({ang})"))
    vis = f"math.sin(180 * {k}) * math.clamp((v.tt - {s0}) * 40, 0, 1)"
    comps = locked(44, 0.50, pos)
    return particle("bravebird_swirl", T_BEAM, comps, path_curves(), UV_BEAM,
                    [f"0.34 * v.bl * {vis}", f"0.05 * {vis}"], camera="lookat_direction",
                    tinting=gradient("v.particle_random_3", [(0.0, WHITE), (0.5, ICE), (1.0, CYAN_L)]))


def p_aura():
    """The glow the Pokemon is wrapped in. Low alpha, so the model stays readable inside it."""
    extra = {'variable.bb_ak': AURA}
    jit = "0.12 * v.bl"
    pos = c3(CENTRE, (f"{jit} * (v.particle_random_1 - 0.5)", f"{jit} * (v.particle_random_2 - 0.5)",
                      f"{jit} * (v.particle_random_3 - 0.5)"))
    flick = "(1 + 0.08 * math.sin(v.particle_age * (650 + 500 * v.particle_random_4) + 360 * v.particle_random_4))"
    sz = f"(1.5 + 0.4 * v.particle_random_2) * (0.4 + 0.75 * v.bl) * v.bb_ak * {flick}"
    comps = locked(4, 1.02, pos)
    return particle("bravebird_aura", T_GLOW, comps, path_curves(extra=extra), UV_GLOW, [sz, sz],
                    tinting={"color": ["0.55 + 0.15 * v.particle_random_3", "0.92", "1", "0.5 * math.min(v.bb_ak, 1)"]})


def p_motes():
    """Bright motes whirling around the travel axis, faster and faster: the acceleration."""
    extra = {'variable.bb_ak': AURA}
    spin = "(260 * v.tt + 1100 * math.pow(math.max(v.tt - 0.36, 0), 2) * (1.3 + v.particle_random_4))"
    ang = f"(360 * v.particle_random_1 + {spin})"
    rad = "(0.55 + 0.25 * v.particle_random_3) * v.bl"
    pos = c3(CENTRE, (f"({rad}) * math.cos({ang})", f"({rad}) * math.sin({ang})", "(v.particle_random_2 - 0.5) * 0.9 * v.bl"))
    vis = window(0.20, 0.95, 0.05)
    sz = f"(0.07 + 0.05 * v.particle_random_4) * (0.7 + 0.5 * math.min(v.bb_ak, 1)) * {vis}"
    comps = locked(32, 0.95, pos)
    return particle("bravebird_motes", T_DOTS, comps, path_curves(extra=extra), UV_DOT, [sz, sz],
                    tinting=gradient("v.particle_random_3", [(0.0, WHITE), (0.5, CYAN_L), (1.0, VIOLET)]))


def p_streaks():
    """Thin streaks of light flowing backwards over the body, longer and faster with the speed."""
    extra = {'variable.bb_sp': speed01, 'variable.bb_fl': flow}
    ph = "(v.particle_random_3 + v.bb_fl)"
    fr = f"({ph} - math.floor({ph}))"
    ang = "(360 * v.particle_random_1)"
    rad = "(0.45 + 0.35 * v.particle_random_2) * v.bl"
    pos = c3(CENTRE, (f"({rad}) * math.cos({ang})", f"({rad}) * math.sin({ang})", f"v.bl * (0.75 - 1.6 * {fr})"))
    vis = f"{window(0.30, 0.93, 0.04)} * math.sin(180 * {fr})"
    comps = locked(26, 0.93, pos)
    return particle("bravebird_streaks", T_BEAM, comps, path_curves(extra=extra), UV_BEAM,
                    [f"(0.25 + 0.7 * v.bb_sp) * 0.6 * v.bl * {vis}", f"0.035 * math.sqrt(v.bl) * {vis}"],
                    camera="lookat_direction",
                    tinting=gradient("v.particle_random_4", [(0.0, WHITE), (0.6, ICE), (1.0, CYAN_L)]))


# ================================================================= the bird silhouette (0.50 - 1.02)
BIRD_EXTRA = {'variable.bb_fo': BIRD_FORM, 'variable.bb_bs': BIRD_BURST, 'variable.bb_ba': BIRD_ALPHA}
BS = "v.bs"   # bird scale (see ANCHOR): wingspan 3.2 x v.bs, so it reads around the Pokemon, not on it


def bird_place(shape):
    """Bird-shape offset -> final offset: the wings unfold outward from the body as the bird forms,
    then the shape bursts on the hit (forward splash) or blows away backwards on a miss."""
    sx, sy, sz = shape
    grow = "((0.2 + 0.8 * v.bb_fo) * (1 + 1.3 * v.bb_bs))"
    push = f"((v.miss > 0.5) ? 0.9 : -0.9) * {BS} * v.bb_bs"
    return c3(CENTRE,
              (f"({sx}) * {grow}",
               f"({sy}) * {grow} + 0.25 * {BS} * v.bb_bs",
               f"({sz}) * {grow} + 0.35 * {BS} * (1 - v.bb_fo) + {push}"))


def wing_le(u, side):
    """Leading edge of one wing: a quadratic Bezier from the shoulder to a tip swept back and raised
    about 33 degrees, so the wings make a V from behind and a rising swept shape from the side (a flat
    wing seen from the side is just a line)."""
    return (f"{side} * {BS} * (0.30 + 1.30 * {u})",
            f"{BS} * (0.15 + 0.80 * {u} + 0.10 * {u} * {u})",
            f"{BS} * (-0.20 + 0.70 * {u} + 0.35 * {u} * {u})")


def p_birdedge():
    """The bright outline: both wings' leading edges and the head/beak line."""
    side = "(v.particle_random_2 < 0.41 ? -1 : 1)"
    u = "v.particle_random_1"
    le = wing_le(u, side)
    head = ("0", f"{BS} * (0.12 - 0.06 * {u})", f"-{BS} * (0.30 + 0.70 * {u})")
    is_wing = "(v.particle_random_2 < 0.82)"
    shape = tuple(f"({is_wing} ? ({le[i]}) : ({head[i]}))" for i in range(3))
    pos = bird_place(shape)
    fl = "(0.85 + 0.15 * math.sin(v.particle_age * (900 + 700 * v.particle_random_3) + 360 * v.particle_random_3))"
    sz = f"(0.30 - 0.12 * {u}) * {BS} * v.bb_ba * {fl}"
    comps = locked(56, 1.04, pos)
    return particle("bravebird_birdedge", T_GLOW, comps, path_curves(extra=BIRD_EXTRA), UV_GLOW, [sz, sz],
                    tinting={"color": ["0.62 + 0.3 * (1 - v.particle_random_1)", "0.94", "1", "0.95"]})


def p_birdfeathers():
    """Feather streaks behind the leading edges (the wing surface) and a fanned tail plume."""
    side = "(v.particle_random_2 < 0.40 ? -1 : 1)"
    u = "v.particle_random_1"
    w = "v.particle_random_3"
    le = wing_le(u, side)
    feather = (f"{le[0]} + {side} * {BS} * 0.05 * {w}", f"{le[1]} - {BS} * 0.14 * {w}",
               f"{le[2]} + {BS} * (0.62 - 0.30 * {u}) * {w}")
    tail = (f"{BS} * 0.40 * {u} * (2 * {w} - 1)", f"{BS} * (0.05 + 0.06 * {u})", f"{BS} * (0.45 + 1.15 * {u})")
    is_wing = "(v.particle_random_2 < 0.80)"
    shape = tuple(f"({is_wing} ? ({feather[i]}) : ({tail[i]}))" for i in range(3))
    pos = bird_place(shape)
    ln = f"({is_wing} ? (0.55 - 0.25 * {u}) : (0.75 - 0.3 * {u}))"
    comps = locked(76, 1.04, pos)
    return particle("bravebird_birdfeathers", T_BEAM, comps, path_curves(extra=BIRD_EXTRA), UV_BEAM,
                    [f"{ln} * {BS} * v.bb_ba", f"0.075 * math.sqrt({BS}) * v.bb_ba"], camera="lookat_direction",
                    tinting={"color": {"interpolant": f"math.clamp(0.6 * {u} + 0.5 * {w}, 0, 1)",
                                       "gradient": {"0.0": ICE, "0.45": CYAN, "1.0": VIOLET}}})


def p_birdglow():
    """A few big soft glows along the wings and body: the energy body of the bird."""
    side = "(v.particle_random_2 < 0.5 ? -1 : 1)"
    u = "(0.15 + 0.8 * v.particle_random_1)"
    le = wing_le(u, side)
    shape = (le[0], le[1], f"{le[2]} + 0.25 * {BS}")
    pos = bird_place(shape)
    sz = f"(1.2 - 0.4 * v.particle_random_1) * {BS} * v.bb_ba"
    comps = locked(8, 1.04, pos)
    return particle("bravebird_birdglow", T_GLOW, comps, path_curves(extra=BIRD_EXTRA), UV_GLOW, [sz, sz],
                    tinting={"color": ["0.42", "0.84", "1", "0.5 * v.bb_ba"]})


def p_beak():
    """Front emphasis: streaks racing forward and converging into a white-hot point ahead of the head."""
    tip = ("0", f"0.08 * {BS}", f"-1.05 * {BS}")
    ang = "(360 * v.particle_random_1)"
    rad = f"(0.25 + 0.3 * v.particle_random_2) * {BS}"
    ph = "(v.particle_random_3 + 3.2 * v.tt)"
    k = f"({ph} - math.floor({ph}))"   # 0 at the back of the cone, 1 at the tip
    off = (f"({rad}) * (1 - {k}) * math.cos({ang})", f"{tip[1]} + ({rad}) * (1 - {k}) * math.sin({ang})",
           f"-0.15 * {BS} + ({tip[2]} + 0.15 * {BS}) * {k}")
    pos = c3(CENTRE, off)
    vis = f"{window(0.60, 0.93, 0.03)} * math.sin(180 * {k})"
    comps = locked(10, 0.93, pos)
    return particle("bravebird_beak", T_BEAM, comps, path_curves(), UV_BEAM,
                    [f"0.38 * {BS} * {vis}", f"0.05 * {vis}"], camera="lookat_direction",
                    tinting=gradient("v.particle_random_3", [(0.0, WHITE), (1.0, ICE)]))


BEAK_TIP = ("0", f"0.08 * {BS}", f"-1.05 * {BS}")


def p_beakglint():
    """A star twinkling on the point of the beak as the charge peaks."""
    pos = c3(CENTRE, BEAK_TIP)
    vis = window(0.62, 0.92, 0.04)
    uv = manual_frames(0.62, 0.30, 11, 25, 25)
    comps = locked(1, 0.93, pos)
    sz = f"0.8 * {BS} * (1 + 0.2 * math.sin(v.tt * 1500)) * {vis}"
    return particle("bravebird_beakglint", T_SKY, comps, path_curves(), uv, [sz, sz], tinting={"color": [1, 1, 1, 1]})


def p_beakcore():
    """The white-hot point itself, pulsing."""
    pos = c3(CENTRE, BEAK_TIP)
    vis = window(0.60, 0.92, 0.04)
    comps = locked(2, 0.93, pos)
    sz = f"(0.27 + 0.1 * v.particle_random_1) * {BS} * (1 + 0.25 * math.sin(v.tt * 1700 + 90 * v.particle_random_1)) * {vis}"
    return particle("bravebird_beakcore", T_LFO, comps, path_curves(), UV_LFO5, [sz, sz],
                    tinting={"color": ["0.9 + 0.1 * v.particle_random_1", "1", "1", "1"]})


# ================================================================= the charge left behind
def p_boom():
    """Sonic-boom rings punched into the air as the speed bursts (FINAL) and again a beat later. They
    stay where they were made while the Pokemon shoots on. Plane perpendicular to the charge."""
    ax, ay, az = fixed_anchor(FINAL)
    bx, by, bz = fixed_anchor(BOOM2)
    second = "(v.particle_random_1 < 0.5 ? 0 : 1)"
    tb = f"({FINAL} + {r(BOOM2 - FINAL)} * {second})"
    k = f"math.clamp((v.tt - {tb}) / 0.32, 0, 1)"
    pos = [f"{second} > 0.5 ? ({bx}) : ({ax})", f"{second} > 0.5 ? ({by}) : ({ay})",
           f"({second} > 0.5 ? ({bz}) : ({az})) + 0.5 * v.ib * {k}"]
    vis = f"math.clamp((v.tt - {tb}) * 60, 0, 1) * (1 - {k})"
    sz = f"(1 - 0.35 * {second}) * v.ib * (1.0 + 1.6 * {k}) * math.clamp((v.tt - {tb}) * 60, 0, 1)"
    uv = manual_frames(tb, 0.32, 6, 64, 64, first=4)   # frames 4-9: the white part of the wind burst
    comps = locked(2, BOOM2 + 0.34, pos)
    return particle("bravebird_boom", T_FLASH, comps, path_curves(), uv, [sz, sz], camera="emitter_transform_xy",
                    tinting={"color": ["1", "1", "1", f"0.95 * {vis}"]})


def p_boomcone():
    """Vapour-cone streaks flung outward and back from the first boom."""
    ax, ay, az = fixed_anchor(FINAL)
    ts = f"math.max(v.tt - {FINAL}, 0)"
    k = f"math.clamp({ts} / 0.26, 0, 1)"
    ang = "(360 * v.particle_random_1)"
    rad = f"v.ib * (0.45 + 1.5 * (1 - math.pow(1 - {k}, 2)))"
    pos = [f"({ax}) + ({rad}) * math.cos({ang})", f"({ay}) + ({rad}) * math.sin({ang})", f"({az}) + 1.2 * v.ib * {k}"]
    vis = f"math.clamp((v.tt - {FINAL}) * 60, 0, 1) * (1 - {k})"
    comps = locked(14, FINAL + 0.28, pos)
    return particle("bravebird_boomcone", T_BEAM, comps, path_curves(), UV_BEAM,
                    [f"(0.55 - 0.3 * {k}) * v.ib * {vis}", f"0.05 * {vis}"], camera="lookat_direction",
                    tinting=gradient("v.particle_random_2", [(0.0, WHITE), (1.0, CYAN_L)]))


def trail_like(count_rate, max_particles, active, offset, lifetime, speed=0.0, direction=(0, 0, 1)):
    """Emitter for world-space layers fired by the dash animation. The emitter follows the root locator
    every tick (frame rotation frozen at T0); these particles are left behind along the path."""
    comps = {
        "minecraft:emitter_initialization": {"creation_expression": FALLBACK},
        "minecraft:emitter_rate_steady": {"spawn_rate": count_rate, "max_particles": max_particles},
        "minecraft:emitter_lifetime_once": {"active_time": active},
        "minecraft:emitter_shape_point": {"offset": offset, "direction": list(direction)},
        "minecraft:particle_lifetime_expression": {"max_lifetime": lifetime},
        "minecraft:particle_initial_speed": speed,
        "minecraft:particle_motion_dynamic": {"linear_drag_coefficient": 8},
    }
    return comps


GAP = f"v.du * (v.bb_v + v.miss * (v.bb_vm - v.bb_v)) * (q.entity_scale > 0 ? q.entity_scale : 1) / 16 * {0.05 / SLOW:g}"


def p_trail():
    """Long light trails left along the path: one from the body and, once the bird has formed, one from
    each wingtip. Each tick's spawns are spread over the distance covered since the previous tick, so the
    trails stay continuous at any speed; their length grows with the speed."""
    extra = {'variable.bb_v': lambda x: deriv(F_hit, x), 'variable.bb_vm': lambda x: deriv(F_miss, x),
             'variable.bb_ba': BIRD_ALPHA, 'variable.bb_sp': speed01}
    curves = {k: curve(f, EIN) for k, f in extra.items()}
    strand = "(v.particle_random_1 < 0.34 ? 0 : (v.particle_random_1 < 0.67 ? -1 : 1))"
    span = "1.6 * math.clamp(0.5 + 0.6 * math.clamp(math.max(v.entity_width, v.entity_height), 0.5, 3.0), 0.8, 2.2)"
    on = f"({EIN} >= 0.40 && {EIN} < 0.93) ? 1 : 0"
    rate = f"({on}) * (60 + 140 * v.bb_sp) * (1 + v.du / 128)"
    offset = [f"{strand} * {span}", f"0.5 * v.entity_height + math.abs({strand}) * 1.05 * {span} / 1.6",
              f"v.particle_random_4 * {GAP} + math.abs({strand}) * 0.85 * {span} / 1.6"]
    comps = trail_like(rate, 240, 0.95, offset, "0.22 + 0.1 * v.particle_random_2", speed=0.4)
    fade = "math.pow(1 - v.particle_age / v.particle_lifetime, 1.4)"
    wing = "(v.particle_random_1 >= 0.34)"
    vis = f"{fade} * ({wing} ? v.bb_ba : 1)"
    ln = f"(0.25 + 0.35 * v.bb_sp) * (1 + v.du / 160) * math.clamp(math.max(v.entity_width, v.entity_height), 0.5, 3.5)"
    th = f"({wing} ? 0.05 : 0.12) * math.sqrt(math.clamp(math.max(v.entity_width, v.entity_height), 0.5, 3.5))"
    return particle("bravebird_trail", T_BEAM, comps, curves, UV_BEAM, [f"{ln} * {vis}", f"{th} * {vis}"],
                    camera="lookat_direction",
                    tinting={"color": {"interpolant": f"{wing} ? (0.55 + 0.45 * v.particle_age / v.particle_lifetime) : (0.5 * v.particle_age / v.particle_lifetime)",
                                       "gradient": {"0.0": WHITE, "0.35": CYAN_L, "0.7": CYAN, "1.0": VIOLET}}})


def p_dust():
    """XY/SM's low-altitude giveaway: dust kicked up from the ground under the skimming Pokemon."""
    extra = {'variable.bb_v': lambda x: deriv(F_hit, x), 'variable.bb_vm': lambda x: deriv(F_miss, x),
             'variable.bb_y': Y_hit, 'variable.bb_ym': Y_miss, 'variable.bb_sp': speed01}
    curves = {k: curve(f, EIN) for k, f in extra.items()}
    on = f"({EIN} >= 0.48 && {EIN} < 0.92) ? 1 : 0"
    rate = f"({on}) * (24 + 46 * v.bb_sp) * (1 + v.du / 160)"
    hop = "(v.bb_y + v.miss * (v.bb_ym - v.bb_y)) * (q.entity_scale > 0 ? q.entity_scale : 1) / 16"
    side = "(v.particle_random_2 < 0.5 ? -1 : 1)"
    offset = [f"{side} * (0.15 + 0.45 * v.particle_random_3) * math.max(v.entity_width, 0.6)", f"0.06 - {hop}",
              f"v.particle_random_4 * {GAP}"]
    comps = trail_like(rate, 160, 0.95, offset, "0.45 + 0.2 * v.particle_random_1", speed="0.9 + 0.8 * v.particle_random_3",
                       direction=(f"{side} * 0.8", 1, 0.6))
    comps["minecraft:particle_motion_dynamic"] = {"linear_drag_coefficient": 3.2, "linear_acceleration": [0, 0.5, 0]}
    k = "(v.particle_age / v.particle_lifetime)"
    sz = f"(0.3 + 0.5 * {k}) * math.clamp(math.max(v.entity_width, 0.6), 0.6, 2.4) * (0.7 + 0.4 * v.particle_random_1)"
    uv = {"flipbook": {"base_UV": [0, 0], "size_UV": [16, 16], "step_UV": [0, 16], "frames_per_second": 12,
                       "max_frame": 6, "stretch_to_lifetime": True}}
    return particle("bravebird_dust", T_SMOKE, comps, curves, uv, [sz, sz],
                    tinting={"color": ["0.86", "0.88", "0.86", f"0.5 * (1 - {k})"]})


# ================================================================= the impact (path-locked, frozen at the contact point)
EX, EY, EZ = fixed_anchor(IMPACT, nose=0.45)
TS = f"(v.tt - {IMPACT})"


def impact_vis(dur, ramp=60):
    return f"math.clamp({TS} * {ramp}, 0, 1) * math.clamp(1 - {TS} / {dur}, 0, 1)"


def p_impactflash():
    k = f"math.clamp({TS} / 0.14, 0, 1)"
    core = "(v.particle_random_1 < 0.34)"
    pos = [EX, EY, EZ]
    comps = locked(3, IMPACT + 0.16, pos)
    sz = f"({core} ? (1.7 + 1.2 * {k}) : (2.4 + 1.6 * {k})) * v.ib * math.clamp({TS} * 80, 0, 1)"
    return particle("bravebird_impactflash", T_GLOW, comps, path_curves(), UV_GLOW, [sz, sz],
                    tinting={"color": [f"{core} ? 1 : 0.6", f"{core} ? 1 : 0.92", "1",
                                       f"({core} ? 1 : 0.55) * (1 - {k} * {k}) * math.clamp({TS} * 80, 0, 1)"]})


def p_impactring():
    """XY's concentric rings around the hit, in the plane perpendicular to the charge."""
    second = "(v.particle_random_1 < 0.5 ? 0 : 1)"
    d = f"(0.06 * {second})"
    dur = f"(0.32 + 0.08 * {second})"
    k = f"math.clamp(({TS} - {d}) / {dur}, 0, 1)"
    pos = [EX, EY, EZ]
    uv = {"uv": [f"20 * math.floor({k} * 11.99)", 0], "uv_size": [20, 20]}
    on = f"math.clamp(({TS} - {d}) * 80, 0, 1)"
    sz = f"({second} > 0.5 ? 4.0 : 3.1) * v.ib * {on}"
    comps = locked(2, IMPACT + 0.42, pos)
    return particle("bravebird_impactring", T_RING, comps, path_curves(), uv, [sz, sz], camera="emitter_transform_xy",
                    tinting={"color": [f"{second} > 0.5 ? 0.62 : 0.85", f"{second} > 0.5 ? 0.66 : 0.98", "1",
                                       f"({second} > 0.5 ? 0.75 : 1) * {on} * (1 - 0.6 * {k})"]})


def p_impactlines():
    """Wind streaks bursting outward around the hit, splashing forward past the target."""
    k = f"math.clamp({TS} / 0.28, 0, 1)"
    ang = "(360 * v.particle_random_1)"
    dist = f"v.ib * (0.25 + 2.2 * (1 - math.pow(1 - {k}, 2)))"
    fwd = "(0.15 + 0.6 * v.particle_random_2)"
    pos = [f"{EX} + ({dist}) * math.cos({ang})", f"{EY} + ({dist}) * math.sin({ang})", f"{EZ} - ({dist}) * {fwd}"]
    vis = impact_vis(0.28)
    comps = locked(22, IMPACT + 0.3, pos)
    return particle("bravebird_impactlines", T_BEAM, comps, path_curves(), UV_BEAM,
                    [f"(0.95 - 0.6 * {k}) * v.ib * {vis}", f"0.055 * math.sqrt(v.ib) * {vis}"], camera="lookat_direction",
                    tinting=gradient("v.particle_random_3", [(0.0, WHITE), (0.6, ICE), (1.0, CYAN_L)]))


def p_impactgust():
    """Swirling gusts of displaced air around the hit (vanilla wind-burst sprite, frames 4-11)."""
    k = f"math.clamp({TS} / 0.4, 0, 1)"
    ang = "(360 * v.particle_random_1)"
    dist = f"v.ib * (0.45 + 0.5 * {k})"
    pos = [f"{EX} + ({dist}) * math.cos({ang})", f"{EY} + ({dist}) * math.sin({ang})", f"{EZ} - 0.3 * v.ib * {k}"]
    uv = {"uv": [f"32 * (4 + math.floor({k} * 7.99))", 0], "uv_size": [32, 32]}
    on = f"math.clamp({TS} * 60, 0, 1)"
    sz = f"(0.75 + 0.3 * v.particle_random_2) * v.ib * {on}"
    comps = locked(6, IMPACT + 0.42, pos)
    return particle("bravebird_impactgust", T_GUST, comps, path_curves(), uv, [sz, sz],
                    tinting={"color": ["0.86", "0.97", "1", f"0.7 * {on} * (1 - {k} * {k})"]})


def p_impactfeathers():
    """The bird of light shatters into feathers that burst out, then flutter down."""
    k = f"math.clamp({TS} / 0.35, 0, 1)"
    ang = "(360 * v.particle_random_1)"
    dist = f"1.5 * v.ib * (1 - math.pow(1 - {k}, 2))"
    fall = f"0.9 * math.pow(math.max({TS} - 0.2, 0), 2) * 3"
    flut = f"0.12 * v.ib * math.sin(540 * {TS} + 360 * v.particle_random_4)"
    pos = [f"{EX} + ({dist}) * math.cos({ang}) + {flut}", f"{EY} + ({dist}) * math.sin({ang}) * 0.8 + 0.3 * v.ib * {k} - {fall}",
           f"{EZ} - ({dist}) * (0.2 + 0.5 * v.particle_random_2)"]
    vis = impact_vis(0.9, 40)
    comps = locked(12, IMPACT + 0.92, pos)
    comps["minecraft:particle_initial_spin"] = {"rotation": "360 * v.particle_random_3",
                                                "rotation_rate": "(v.particle_random_4 - 0.5) * 720"}
    sz = f"(0.2 + 0.08 * v.particle_random_2) * v.ib * {vis}"
    return particle("bravebird_impactfeathers", T_FEATHER, comps, path_curves(), UV_FEATHER, [sz, sz],
                    tinting={"color": {"interpolant": "v.particle_random_3",
                                       "gradient": {"0.0": WHITE, "0.5": CYAN_L, "1.0": VIOLET}}})


def p_impactsparks():
    k = f"math.clamp({TS} / 0.4, 0, 1)"
    d = sphere_dir()
    dist = f"v.ib * 2.4 * (1 - math.pow(1 - {k}, 2.2))"
    pos = [f"{EX} + ({dist}) * {d[0]}", f"{EY} + ({dist}) * {d[1]} * 0.8 - 0.4 * {k} * {k}",
           f"{EZ} + ({dist}) * ({d[2]} - 0.6)"]
    vis = impact_vis(0.4)
    comps = locked(24, IMPACT + 0.42, pos)
    sz = f"(0.08 + 0.05 * v.particle_random_3) * (0.5 + 0.5 * v.ib) * {vis}"
    return particle("bravebird_impactsparks", T_DOTS, comps, path_curves(), UV_DOT, [sz, sz],
                    tinting=gradient("v.particle_random_3", [(0.0, WHITE), (0.5, CYAN), (1.0, VIOLET)]))


def p_recoilburst():
    """The collision's force kicking back into the user: a small shock ring travelling back over it."""
    d = 0.04
    k = f"math.clamp(({TS} - {d}) / 0.28, 0, 1)"
    pos = [EX, EY, f"{EZ} + v.ib * (0.35 + 0.7 * {k})"]
    uv = {"uv": [f"20 * math.floor({k} * 11.99)", 0], "uv_size": [20, 20]}
    on = f"math.clamp(({TS} - {d}) * 80, 0, 1)"
    comps = locked(1, IMPACT + 0.34, pos)
    sz = f"(1.0 + 0.8 * {k}) * v.ib * {on}"
    return particle("bravebird_recoilburst", T_RING, comps, path_curves(), uv, [sz, sz], camera="emitter_transform_xy",
                    tinting={"color": ["0.9", "0.98", "1", f"0.9 * {on} * (1 - {k})"]})


# ================================================================= slow moments (fired by the actor / target animations)
def burst(count, active=0.2):
    return {
        "minecraft:emitter_initialization": {"creation_expression": "v.entity_width = 1; v.entity_height = 1;"},
        "minecraft:emitter_rate_instant": {"num_particles": count},
        "minecraft:emitter_lifetime_once": {"active_time": active},
    }


BODY = "math.clamp(math.max(v.entity_width, v.entity_height), 0.5, 3.5)"
GROUND = "math.clamp(0.6 + 0.4 * math.max(v.entity_width, v.entity_height), 0.8, 1.8)"   # ground rings grow slowly with size


def p_takeoff():
    """Ground ring as the Pokemon springs into the air."""
    comps = dict(burst(1), **{
        "minecraft:emitter_shape_point": {"offset": [0, 0.05, 0]},
        "minecraft:particle_lifetime_expression": {"max_lifetime": 0.36},
        "minecraft:particle_initial_speed": 0,
        "minecraft:particle_motion_dynamic": {}})
    k = "(v.particle_age / v.particle_lifetime)"
    uv = {"uv": ["20 * math.floor(" + k + " * 11.99)", 0], "uv_size": [20, 20]}
    return particle("bravebird_takeoff", T_RING, comps, None, uv, [f"2.0 * {GROUND}", f"2.0 * {GROUND}"],
                    camera="emitter_transform_xz", tinting={"color": ["0.8", "0.95", "1", f"0.75 * (1 - {k})"]})


def p_takeoffgust():
    """Wind blown out from under the wings by the take-off."""
    comps = dict(burst(5), **{
        "minecraft:emitter_shape_disc": {"offset": [0, 0.15, 0], "radius": f"0.35 * {BODY}", "plane_normal": "y",
                                         "surface_only": True, "direction": "outwards"},
        "minecraft:particle_lifetime_expression": {"max_lifetime": 0.4},
        "minecraft:particle_initial_speed": "2.5 + 1.5 * v.particle_random_1",
        "minecraft:particle_motion_dynamic": {"linear_drag_coefficient": 4, "linear_acceleration": [0, 0.6, 0]}})
    k = "(v.particle_age / v.particle_lifetime)"
    uv = {"uv": [f"32 * (4 + math.floor({k} * 7.99))", 0], "uv_size": [32, 32]}
    sz = f"(0.55 + 0.25 * v.particle_random_2) * {BODY}"
    return particle("bravebird_takeoffgust", T_GUST, comps, None, uv, [sz, sz],
                    tinting={"color": ["0.85", "0.96", "1", f"0.8 * (1 - {k} * {k})"]})


def recoil_emitter(count, life):
    """Local space, so the sparks stay on the body through the stagger (it moves slowly by then). They
    keep popping for a third of a second, like the anime's crackle."""
    base = {k: v for k, v in burst(count).items() if k != "minecraft:emitter_rate_instant"}
    return dict(base, **{
        "minecraft:emitter_rate_steady": {"spawn_rate": round(count / 0.3, 1), "max_particles": count},
        "minecraft:emitter_lifetime_once": {"active_time": 0.32},
        "minecraft:emitter_local_space": {"position": True, "rotation": False},
        "minecraft:emitter_shape_sphere": {"radius": f"0.5 * {BODY}", "surface_only": True, "direction": "outwards"},
        "minecraft:particle_lifetime_expression": {"max_lifetime": life},
        "minecraft:particle_initial_speed": "0.6 + 0.8 * v.particle_random_2",
        "minecraft:particle_motion_dynamic": {"linear_drag_coefficient": 6}})


def p_recoilspark():
    """Recoil: light-blue sparks of pain popping over the user, as in the anime. Star twinkles rather
    than lightning, so it doesn't read as an Electric move."""
    comps = recoil_emitter(16, "0.2 + 0.16 * v.particle_random_1")
    k = "(v.particle_age / v.particle_lifetime)"
    uv = {"uv": [f"25 * math.floor({k} * 10.99)", 0], "uv_size": [25, 25]}
    sz = f"(0.5 + 0.2 * v.particle_random_3) * {BODY} * (1 - 0.3 * {k})"
    return particle("bravebird_recoilspark", T_SKY, comps, None, uv, [sz, sz],
                    tinting={"color": ["0.75 + 0.25 * v.particle_random_4", "0.95", "1", f"1 - {k} * {k}"]})


def p_recoilflick():
    """Short flicks of light jumping off the body with the sparks."""
    comps = recoil_emitter(12, "0.10 + 0.08 * v.particle_random_1")
    comps["minecraft:particle_initial_speed"] = "2.5 + 2.0 * v.particle_random_2"
    k = "(v.particle_age / v.particle_lifetime)"
    return particle("bravebird_recoilflick", T_BEAM, comps, None, UV_BEAM,
                    [f"0.32 * {BODY} * (1 - {k})", f"0.035 * math.sqrt({BODY})"], camera="lookat_direction",
                    tinting={"color": ["0.8", "0.96", "1", f"1 - {k}"]})


def p_targetground():
    """Ground ring and dust under the target as it is driven back."""
    comps = dict(burst(1), **{
        "minecraft:emitter_shape_point": {"offset": [0, 0.05, 0]},
        "minecraft:particle_lifetime_expression": {"max_lifetime": 0.42},
        "minecraft:particle_initial_speed": 0,
        "minecraft:particle_motion_dynamic": {}})
    k = "(v.particle_age / v.particle_lifetime)"
    uv = {"uv": ["20 * math.floor(" + k + " * 11.99)", 0], "uv_size": [20, 20]}
    return particle("bravebird_targetground", T_RING, comps, None, uv, [f"2.6 * {GROUND}", f"2.6 * {GROUND}"],
                    camera="emitter_transform_xz", tinting={"color": ["0.78", "0.92", "1", f"0.7 * (1 - {k})"]})


# ================================================================= animations
WING_OPEN = ['wing_open_left', 'wing_open_right', 'wing_left_open', 'wing_right_open', 'wing_open_left1',
             'wing_open_right1', 'wing_open_left_main', 'wing_open_right_main', 'wing_top_left', 'wing_top_right',
             'wing_bottom_left', 'wing_bottom_right']
WING_ANY = ['wing_left', 'wing_right', 'left_wing', 'right_wing', 'wing_upper_left', 'wing_upper_right']
WING_CLOSED = ['wing_closed_left', 'wing_closed_right', 'wing_left_closed', 'wing_right_closed',
               'wing_closed_left1', 'wing_closed_right1', 'wing_folded_left', 'wing_folded_right']
ARMS = ['arm_left', 'arm_right', 'left_upper_arm', 'right_upper_arm', 'left_arm', 'right_arm']

# scale multipliers (a bone the idle has hidden stays hidden: scale multiplies)
WING_OPEN_S = [(0, 1), (REST_END, 1), (0.12, 1.16), (0.30, 1.12), (0.44, 0.62), (0.88, 0.60), (0.95, 1.2), (1.10, 1.05), (1.30, 1)]
WING_ANY_S = [(0, 1), (REST_END, 1), (0.12, 1.12), (0.30, 1.08), (0.44, 0.80), (0.88, 0.80), (0.95, 1.15), (1.10, 1.04), (1.30, 1)]
WING_CLOSED_S = [(0, 1), (REST_END, 1), (0.12, 1.08), (0.30, 1.0), (0.44, 0.93), (0.88, 0.93), (0.95, 1.06), (1.15, 1)]
WING_MISS_TAIL = [(0.95, 0.75), (1.10, 1.05), (1.30, 1)]
# arms swept back for the charge (+x = backwards), flung forward by the hit
ARMS_R = [(0, 0), (REST_END, 0), (0.13, -14), (0.30, 10), (0.50, 40), (0.88, 44), (0.95, -24), (1.10, -10), (1.35, 0)]
ARMS_R_MISS = [(0, 0), (REST_END, 0), (0.13, -14), (0.30, 10), (0.50, 40), (0.95, 44), (1.15, 10), (1.35, 0)]

ROOT_SCALE = [(0, (1, 1, 1)), (REST_END, (1, 1, 1)), (0.13, (1.08, 0.88, 1.08)), (0.22, (0.94, 1.10, 0.94)),
              (0.34, (1, 1, 1)), (0.60, (0.94, 0.95, 1.10)), (0.86, (0.88, 0.90, 1.22)), (0.915, (1.16, 0.92, 0.78)),
              (0.98, (0.95, 1.05, 1.08)), (1.08, (1, 1, 1)), (1.54, (1, 1, 1)), (1.58, (1.06, 0.92, 1.06)), (ACTOR_LEN, (1, 1, 1))]
ROOT_SCALE_MISS = [(0, (1, 1, 1)), (REST_END, (1, 1, 1)), (0.13, (1.08, 0.88, 1.08)), (0.22, (0.94, 1.10, 0.94)),
                   (0.34, (1, 1, 1)), (0.60, (0.94, 0.95, 1.10)), (0.86, (0.88, 0.90, 1.22)), (0.95, (0.92, 0.94, 1.14)),
                   (1.10, (1, 1, 1)), (1.48, (1, 1, 1)), (1.52, (1.06, 0.92, 1.06)), (1.56, (1, 1, 1)), (ACTOR_LEN, (1, 1, 1))]


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


def actor_animation(variant):
    """variant: 'recoil' (hit, the user takes recoil), 'hit' (hit, no recoil: Protect, Rock Head...), 'miss'."""
    miss = variant == 'miss'
    th = TH_miss if miss else TH_hit
    ph = PH_miss if miss else (lambda x: 0.0)
    jitter = variant == 'recoil'

    def rot(x):
        roll = ph(x)
        if jitter and REBOUND - 0.06 <= x <= RETURN0:
            k = (x - (REBOUND - 0.06)) / (RETURN0 - REBOUND + 0.06)
            roll += 8 * (1 - k) * math.sin(2 * math.pi * 5.5 * k)
        return [th(x), 0, roll]

    bones = {'root_part': {'rotation': dense_keys(rot, ACTOR_LEN, 0.15),
                           'scale': dense_keys(smooth_keys(ROOT_SCALE_MISS if miss else ROOT_SCALE), ACTOR_LEN, 0.004)}}
    if jitter:
        def shake(x):
            if REBOUND - 0.04 <= x <= RETURN0:
                k = (x - (REBOUND - 0.04)) / (RETURN0 - REBOUND + 0.04)
                return [0.9 * (1 - k) * math.sin(2 * math.pi * 6 * k), 0, 0]
            return [0, 0, 0]
        bones['root_part']['position'] = dense_keys(shake, ACTOR_LEN, 0.02)

    def wing_scale(table):
        pts = table if not miss else [p for p in table if p[0] < 0.9] + WING_MISS_TAIL
        f = smooth_keys(pts)
        return dense_keys(lambda x: [f(x)[0]] * 3, ACTOR_LEN, 0.004)
    for names, table in ((WING_OPEN, WING_OPEN_S), (WING_ANY, WING_ANY_S), (WING_CLOSED, WING_CLOSED_S)):
        sc = wing_scale(table)
        for b in names:
            bones[b] = {'scale': sc}
    arm = smooth_keys(ARMS_R_MISS if miss else ARMS_R)
    arm_keys = dense_keys(lambda x: [arm(x)[0], 0, 0], ACTOR_LEN, 0.15)
    for b in ARMS:
        bones[b] = {'rotation': arm_keys}

    particles = {tk(ANTIC): [{'effect': 'cobblemon:bravebird_takeoff', 'locator': 'root'},
                            {'effect': 'cobblemon:bravebird_takeoffgust', 'locator': 'root'}],
                 tk(RETURN1): {'effect': 'cobblemon:quickattack_dust', 'locator': 'root'}}
    if variant == 'recoil':
        particles[tk(REBOUND)] = [{'effect': 'cobblemon:bravebird_recoilspark', 'locator': 'middle'},
                                 {'effect': 'cobblemon:bravebird_recoilflick', 'locator': 'middle'}]
    sounds = {tk(REST_END): {'effect': 'move.bravebird.flap'},
              tk(0.15): {'effect': 'move.bravebird.charge'},
              tk(DASH0): {'effect': 'move.bravebird.dash'},
              tk(FINAL - 0.02): {'effect': 'move.bravebird.boom'}}
    if variant == 'recoil':
        sounds[tk(REBOUND)] = {'effect': 'move.bravebird.recoil'}
    if miss:
        sounds[tk(IMPACT)] = {'effect': 'move.bravebird.whoosh'}
        sounds[tk(1.12)] = {'effect': 'move.bravebird.return'}
    else:
        sounds[tk(RETURN0 + 0.01)] = {'effect': 'move.bravebird.return'}
    return {'animation_length': r(ACTOR_LEN * SLOW), 'bones': bones, 'particle_effects': particles, 'sound_effects': sounds}


LOCKED_COMMON = ['beakglint', 'beakcore', 'birdedge', 'beak', 'birdfeathers', 'motes', 'streaks', 'gather', 'swirl',
                 'boom', 'boomcone', 'trail', 'dust']
LOCKED_IMPACT = ['impactflash', 'impactsparks', 'impactlines', 'impactfeathers', 'impactgust', 'impactring',
                 'recoilburst']
LOCKED_LAST = ['birdglow', 'aura']   # big soft glows go last: particles write depth, so draw them after the rest


def dash_animation(units, miss):
    u = float(units)
    if miss:
        fn = lambda x: [X_miss(x), Y_miss(x), ZC_miss(x) - u * F_miss(x)]
    else:
        fn = lambda x: [0.0, Y_hit(x), ZC_hit(x) - u * F_hit(x)]
    script = f"v.du = {units}\nv.miss = {1 if miss else 0}"
    layers = LOCKED_COMMON + ([] if miss else LOCKED_IMPACT) + LOCKED_LAST
    effects = [{'effect': f'cobblemon:bravebird_{l}', 'locator': 'root', 'pre_effect_script': script} for l in layers]
    return {
        'animation_length': r(ACTOR_LEN * SLOW),
        'bones': {'root_part': {'position': dense_keys(fn, ACTOR_LEN, 0.02)}},
        'particle_effects': {t(T0): effects},
    }


def target_animation():
    """Started in the same tick as the user's animations; holds still until the contact frame, so the
    knock-back is on the client clock with the dash."""
    I = IMPACT
    pos = [(0.0, [0, 0, 0]), (I, [0, 0, 0]), (I + 0.05, [0, 1.4, 8.0]), (I + 0.14, [0, 1.0, 10.5]),
           (I + 0.28, [0, 0.3, 6.5]), (I + 0.44, [0, 0, 2.5]), (I + 0.6, [0, 0, 0.6]), (I + 0.75, [0, 0, 0])]
    rot = [(0.0, [0, 0, 0]), (I, [0, 0, 0]), (I + 0.05, [-17, 0, 0]), (I + 0.14, [-14, 0, 5]), (I + 0.28, [-7, 0, -4]),
           (I + 0.44, [-2, 0, 2]), (I + 0.6, [0, 0, 0]), (I + 0.75, [0, 0, 0])]
    sc = [(0.0, [1, 1, 1]), (I, [1, 1, 1]), (I + 0.04, [1.08, 0.9, 1.08]), (I + 0.14, [0.97, 1.04, 0.97]),
          (I + 0.3, [1, 1, 1]), (I + 0.75, [1, 1, 1])]

    def exact(points):
        return {tk(k): vec(v) for k, v in points}
    fx = I * SLOW - FX_LEAD
    return {
        'animation_length': r((I + 0.75) * SLOW),
        'bones': {'root_part': {'position': exact(pos), 'rotation': exact(rot), 'scale': exact(sc)}},
        'particle_effects': {t(fx): [{'effect': 'cobblemon:impact_flying', 'locator': 'target'},
                                     {'effect': 'cobblemon:bravebird_targetground', 'locator': 'root'}]},
        'sound_effects': {tk(I): [{'effect': 'impact.flying'}, {'effect': 'move.bravebird.impact'}]},
    }


def build_animation_file():
    anims = {'animation.bravebird.actor_recoil': actor_animation('recoil'),
             'animation.bravebird.actor': actor_animation('hit'),
             'animation.bravebird.actor_miss': actor_animation('miss'),
             'animation.bravebird.target': target_animation()}
    for k in range(DASH_VARIANTS + 1):
        anims[f'animation.bravebird.dash_{k}'] = dash_animation(k * DASH_STEP, False)
    for k in range(DASH_VARIANTS + 1):
        anims[f'animation.bravebird.dashmiss_{k}'] = dash_animation(k * DASH_STEP, True)
    return {'format_version': '1.8.0', 'animations': anims}


# ================================================================= action effect
def play(anim):
    return f"q.play_animation(q.bedrock_stateful('bravebird', '{anim}', 'endures_primary_animations'))"


USER_RECOIL = "q.entity.is_user == true && q.missed == false && q.hurt(q.entity.uuid) == true"
USER_HIT = "q.entity.is_user == true && q.missed == false && q.hurt(q.entity.uuid) == false"
USER_MISS = "q.entity.is_user == true && q.missed == true"
TARGET_HIT = "q.entity.is_user == false && q.missed(q.entity.uuid) == false && q.hurt(q.entity.uuid) == true"


def build_effect_file():
    # Every entity_* / animation / molang keyframe costs one server tick in 1.7.3, so the whole start
    # is one `parallel` (a single tick). Only the keyframes whose condition holds send anything.
    start = [
        # Cobblemon's per-species hook: a poser that defines a "bravebird" animation gets it on top.
        # No official poser does, and an unknown name plays nothing.
        {'type': 'animation', 'animation': ['bravebird']},
        {'type': 'entity_molang', 'entityCondition': USER_RECOIL, 'expressions': [play('actor_recoil')]},
        {'type': 'entity_molang', 'entityCondition': USER_HIT, 'expressions': [play('actor')]},
        {'type': 'entity_molang', 'entityCondition': USER_MISS, 'expressions': [play('actor_miss')]},
    ]
    half = DASH_STEP / 2
    for miss in (False, True):
        name = 'dashmiss' if miss else 'dash'
        mc = "q.missed == true" if miss else "q.missed == false"
        for k in range(DASH_VARIANTS + 1):
            lo, hi = k * DASH_STEP - half, k * DASH_STEP + half
            if k == 0:
                rng = f"v.bb_units >= 0 && v.bb_units < {hi:g}"
            elif k == DASH_VARIANTS:
                rng = f"v.bb_units >= {lo:g}"
            else:
                rng = f"v.bb_units >= {lo:g} && v.bb_units < {hi:g}"
            start.append({'type': 'entity_molang', 'condition': f"{rng} && {mc}", 'expressions': [play(f'{name}_{k}')]})
        start.append({'type': 'entity_molang', 'condition': f"!(v.bb_units >= 0) && {mc}",
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
    return [p_gather(), p_swirl(), p_aura(), p_motes(), p_streaks(), p_birdedge(), p_birdfeathers(), p_birdglow(),
            p_beak(), p_beakglint(), p_beakcore(), p_boom(), p_boomcone(), p_trail(), p_dust(), p_impactflash(), p_impactring(),
            p_impactlines(), p_impactgust(), p_impactfeathers(), p_impactsparks(), p_recoilburst(), p_takeoff(),
            p_takeoffgust(), p_recoilspark(), p_recoilflick(), p_targetground()]


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
