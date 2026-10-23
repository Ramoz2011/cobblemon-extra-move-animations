"""Generates Counter's particle effects, generic animation file and action effect.

Outputs (paths relative to the repo root):
  src/main/resources/assets/cobblemon/bedrock/particles/moves/counter/*.particle.json
  src/main/resources/assets/cobblemon/bedrock/generic/animations/moves/counter.animation.json
  src/main/resources/data/cobblemon/action_effects/moves/counter.json

Edit the constants below and re-run `python3 docs/tools/counter_gen.py`; don't hand-edit the outputs.
Design notes and the reasoning behind the numbers: docs/counter_assets.md.

How the pieces fit:
- Counter has priority -5, so by the time its animation starts the foe's physical hit has already played
  with its own animation. Nothing here replays that hit: the user braces, jolts as the force it took
  'lands', gathers it in (a ring and motes drawn into the body), flashes red-orange with a few puffs of
  white steam (Sword/Shield and Scarlet/Violet), rears back and strikes. A short burst of force streaks
  from its front to the target, which takes one white-hot hit.
- The red-orange flash is the user's own model tinted through the Java hook q.user.model_tint(...)
  (src/main/java/.../tint). Without the hook the call returns 0 and the rest of the move still plays.
- The battle decides everything: the action effect only reads what the battle reported. A hit
  (q.hurt) plays the strike and the impact, a miss (q.missed) the strike with the force streaking
  past, and a failure (no physical hit taken, or a target the move can't touch) only a brace that
  comes to nothing.
- Everything starts in one server tick (one `parallel`) and then runs on the client clock. The user's
  animation and the target's impact are model animations on the same clock; the streaks are spawned
  by the action effect (they need the target's position) and are born EMIT_LAG later, so their
  timings are shifted by that much. Particles fired from an animation show up a tick late, so
  animations fire them FX_LEAD early.
"""
import json, math, os

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..')
RES = os.path.join(ROOT, 'src/main/resources')
PART_DIR = os.path.join(RES, 'assets/cobblemon/bedrock/particles/moves/counter')
ANIM_OUT = os.path.join(RES, 'assets/cobblemon/bedrock/generic/animations/moves/counter.animation.json')
EFFECT_OUT = os.path.join(RES, 'data/cobblemon/action_effects/moves/counter.json')

# ---------------------------------------------------------------- timing (seconds from the start of the move)
BRACE = 0.20         # 1. braced: low, guard up
ABSORB = 0.27        # 2. the jolt of the force it took, a compact flash on its front
GATHER0, GATHER1 = 0.29, 0.45   # ... drawn into the body (ring and motes close in)
POWER = 0.46         # 3. the counterforce: red-orange flash, outward pulse, steam
WIND0, WIND1 = 0.56, 0.66       # rears back
STRIKE = 0.70        # 4. the strike: lunge and punch, the force leaves its front
IMPACT = 0.78        # ... and lands on the target
ACTOR_LEN = 1.30     # 5. back to its battle stance
FAIL_LEN = 0.85      # a failed Counter: braced for a hit that never mattered, then relaxes
FX_LEAD = 0.075      # particles fired this early show up on the frame they're meant for
EMIT_LAG = 0.075     # an action-effect emitter's first particles are born about this late
TAIL = 0.5           # after the battle moves on: the user settles and the impact clears

# the user's tint (Java): fades in from TINT0, full until TINT1, gone by TINT2
TINT0, TINT1, TINT2 = 0.40, 0.78, 1.03
USER_TINT = (1.0, 0.55, 0.25)    # orange, over Minecraft's red hurt overlay (USER_FLASH = -1): red-orange on any colour
USER_TINT_STRENGTH, USER_FLASH = 0.72, -1
TARGET_TINT = (1.0, 0.62, 0.30)  # the target flashes orange on the hit (Sword/Shield)
TARGET_TINT_STRENGTH, TARGET_FLASH = 0.5, 0.7   # flash > 0 washes it towards white

# ---------------------------------------------------------------- palette (#AARRGGBB)
WHITE = '#FFFFFFFF'
CREAM = '#FFFFF6D8'
YELLOW = '#FFFFE27A'     # pale yellow
GOLD = '#FFFFC04A'
ORANGE = '#FFFF8A2E'
REDORANGE = '#FFF2552B'
PALERED = '#FFFF7A6A'
DUST = (0.62, 0.56, 0.48)   # neutral dust kicked up by the lunge


# ================================================================= helpers
def t(x):
    s = f"{x:.4f}".rstrip('0').rstrip('.')
    return s if '.' in s else s + '.0'


def r(x, n=4):
    v = round(x, n)
    return 0 if v == 0 else v


def smooth(x):
    x = max(0.0, min(1.0, x))
    return x * x * (3 - 2 * x)


def tex(path, w, h):
    return f"textures/particles/{path}", w, h


T_GLOW = tex('moves/bravebird_glow', 32, 32)             # round soft glow (docs/tools/bravebird_textures.py)
T_PUFF = tex('generic/fire/cloudyfire_white', 160, 16)   # 10 frames 16x16: a puff swelling and breaking up
T_RING = tex('generic/ring/giantring_white', 448, 64)    # 7 frames 64x64: a ring expanding and breaking up
T_HIT = tex('generic/hit', 32, 160)                      # 5 frames 32x32, top to bottom: an impact star
T_LINES = tex('generic/dashburst', 320, 64)              # 5 frames 64x64: radial burst lines
T_BEAM = tex('generic/smallbeam', 140, 91)
T_SPARK = tex('generic/sparkle/glowingsparkle_yellow', 8, 32)   # 4 frames 8x8, big to small

UV_BEAM = {"uv": [70, 42], "uv_size": [70, 7]}    # right half of one smallbeam frame: a soft streak
UV_GLOW = {"uv": [0, 0], "uv_size": [32, 32]}
UV_SPARK = {"uv": [0, 0], "uv_size": [8, 8]}


def frame_uv(index, fw, fh, horizontal=True):
    """Static UV of frame `index` (a MoLang expression) of a sheet laid out left-to-right or top-to-bottom."""
    return {"uv": [f"{fw} * ({index})", 0] if horizontal else [0, f"{fh} * ({index})"], "uv_size": [fw, fh]}


def frames(k, count):
    """Frame index for a 0..1 progress over `count` frames."""
    return f"math.floor(math.clamp({k}, 0, 0.999) * {count})"


def puff_frame(k, first=1, last=8):
    return frame_uv(f"{first} + math.floor(math.clamp({k}, 0, 0.999) * {last - first + 1})", 16, 16)


def flipbook(fw, fh, count, horizontal=True):
    return {"flipbook": {"base_UV": [0, 0], "size_UV": [fw, fh], "step_UV": [fw, 0] if horizontal else [0, fh],
                         "frames_per_second": 20, "max_frame": count, "stretch_to_lifetime": True}}


def gradient(inp, stops):
    return {"color": {"interpolant": inp, "gradient": {t(k): v for k, v in stops}}}


def particle(pid, texture, components, uv, size, camera="rotate_xyz", tinting=None):
    path, tw, th = texture
    bb = {"size": size, "facing_camera_mode": camera, "uv": dict({"texture_width": tw, "texture_height": th}, **uv)}
    comps = dict(components)
    comps["minecraft:particle_appearance_billboard"] = bb
    if tinting is not None:
        comps["minecraft:particle_appearance_tinting"] = tinting
    return {"format_version": "1.10.0", "particle_effect": {
        "description": {"identifier": f"cobblemon:{pid}",
                        "basic_render_parameters": {"material": "particles_blend", "texture": path}},
        "components": comps}}


ENTITY_DEFAULTS = "v.entity_width = 1; v.entity_height = 1;"
BODY = "math.clamp(math.max(v.entity_width, v.entity_height), 0.5, 3.5)"   # body size (blocks)
RR = f"(math.max(0.55 * {BODY}, 0.4) + 0.08)"                               # a ball just outside the body
FX = "math.clamp(0.55 + 0.4 * math.max(v.entity_width, v.entity_height), 0.7, 1.8)"   # effect scale: grows slowly with size
CHEST = "(0.55 * math.min(v.entity_height, 3.2))"                          # chest height above the feet
FRONT = "(0.5 * v.entity_width + 0.12)"                                    # just in front of the body
K = "(v.particle_age / v.particle_lifetime)"
FADE = f"(1 - {K} * {K})"
SPIN = {"rotation": "math.floor(v.particle_random_4 * 4) * 90"}


def burst(count, defaults=ENTITY_DEFAULTS, active=0.2):
    comps = {"minecraft:emitter_initialization": {"creation_expression": defaults}} if defaults else {}
    comps["minecraft:emitter_rate_instant"] = {"num_particles": count}
    comps["minecraft:emitter_lifetime_once"] = {"active_time": active}
    return comps


def still(life):
    return {"minecraft:particle_lifetime_expression": {"max_lifetime": life},
            "minecraft:particle_initial_speed": 0,
            "minecraft:particle_motion_dynamic": {}}


def sphere_dir(theta="(360 * v.particle_random_1)", u="v.particle_random_2"):
    sin_phi = f"math.sqrt(1 - math.pow(2 * {u} - 1, 2))"
    return f"{sin_phi} * math.cos({theta})", f"(2 * {u} - 1)", f"{sin_phi} * math.sin({theta})"


# ================================================================= 1. the brace (actor animation, all on the root locator)
def p_bracemotes():
    """A faint warm shimmer rising off the body as it braces: defensive, not a charge."""
    comps = {
        "minecraft:emitter_initialization": {"creation_expression": ENTITY_DEFAULTS},
        "minecraft:emitter_rate_steady": {"spawn_rate": 26, "max_particles": 10},
        "minecraft:emitter_lifetime_once": {"active_time": 0.3},
        "minecraft:emitter_shape_disc": {"offset": [0, f"v.entity_height * (0.2 + 0.6 * v.particle_random_3)", 0],
                                         "radius": "0.5 * v.entity_width + 0.1", "plane_normal": "y", "surface_only": True},
        "minecraft:particle_lifetime_expression": {"max_lifetime": "0.3 + 0.15 * v.particle_random_1"},
        "minecraft:particle_initial_speed": 0,
        "minecraft:particle_motion_dynamic": {"linear_acceleration": [0, 1.2, 0], "linear_drag_coefficient": 1.5}}
    sz = f"(0.07 + 0.04 * v.particle_random_2) * {FX} * (1 - {K})"
    return particle("counter_bracemotes", T_SPARK, comps, UV_SPARK, [sz, sz],
                    tinting={"color": [1, "0.86 + 0.1 * v.particle_random_4", "0.6", f"0.55 * (1 - {K})"]})


# ================================================================= 2. the force it took, gathered in
def p_absorbflash():
    """A compact white-yellow flash on the user's front: the hit it took, without replaying the hit."""
    comps = dict(burst(1), **{"minecraft:emitter_shape_point": {"offset": [0, CHEST, f"-{FRONT}"]}}, **still(0.11))
    sz = f"0.75 * {FX} * (0.8 + 0.4 * {K})"
    return particle("counter_absorbflash", T_GLOW, comps, UV_GLOW, [sz, sz],
                    tinting={"color": [1, "1 - 0.12 * " + K, f"0.9 - 0.35 * {K}", f"1 - {K} * {K}"]})


def p_absorbstar():
    """... with a small impact star, half the size of the strike's."""
    comps = dict(burst(1), **{"minecraft:emitter_shape_point": {"offset": [0, CHEST, f"-{FRONT}"]}}, **still(0.14))
    sz = f"0.85 * {FX}"
    return particle("counter_absorbstar", T_HIT, comps, flipbook(32, 32, 5, horizontal=False), [sz, sz],
                    tinting={"color": [1, 0.95, 0.75, 0.9]})


def p_absorbstreaks():
    """A few short impact streaks spraying off the contact point."""
    comps = dict(burst(7), **{
        "minecraft:emitter_shape_sphere": {"offset": [0, CHEST, f"-{FRONT}"], "radius": 0.08, "surface_only": True,
                                           "direction": "outwards"},
        "minecraft:particle_lifetime_expression": {"max_lifetime": "0.12 + 0.06 * v.particle_random_1"},
        "minecraft:particle_initial_speed": f"(6 + 3 * v.particle_random_2) * {FX}",
        "minecraft:particle_motion_dynamic": {"linear_drag_coefficient": 6}})
    return particle("counter_absorbstreaks", T_BEAM, comps, UV_BEAM,
                    [f"(0.3 + 0.15 * v.particle_random_3) * {FX} * (1 - {K})", f"0.04 * {FX}"], camera="lookat_direction",
                    tinting=gradient("v.particle_random_3", [(0.0, WHITE), (1.0, YELLOW)]))


def p_absorbsparks():
    comps = dict(burst(8), **{
        "minecraft:emitter_shape_sphere": {"offset": [0, CHEST, f"-{FRONT}"], "radius": 0.1, "surface_only": True,
                                           "direction": "outwards"},
        "minecraft:particle_lifetime_expression": {"max_lifetime": "0.18 + 0.1 * v.particle_random_1"},
        "minecraft:particle_initial_speed": f"(3 + 2.5 * v.particle_random_2) * {FX}",
        "minecraft:particle_motion_dynamic": {"linear_acceleration": [0, -4, 0], "linear_drag_coefficient": 4}})
    sz = f"(0.08 + 0.05 * v.particle_random_3) * {FX} * (1 - 0.6 * {K})"
    return particle("counter_absorbsparks", T_SPARK, comps, frame_uv(frames(K, 4), 8, 8, horizontal=False), [sz, sz],
                    tinting={"color": [1, 1, "0.8 - 0.2 * v.particle_random_4", 1]})


def p_absorbring():
    """A tight ring closing in round the body: the ring texture played backwards, shrinking onto it."""
    life = r(GATHER1 - GATHER0)
    comps = dict(burst(1), **{"minecraft:emitter_shape_point": {"offset": [0, CHEST, 0]}}, **still(life))
    k = K
    uv = frame_uv(f"6 - {frames(k, 7)}", 64, 64)
    sz = f"{RR} * (3.2 - 1.6 * {k} * {k})"
    return particle("counter_absorbring", T_RING, comps, uv, [sz, sz],
                    tinting={"color": [1, 0.93, 0.62, f"0.85 * math.clamp({k} * 6, 0, 1) * math.clamp((1 - {k}) * 6, 0, 1)"]})


def p_absorbmotes():
    """White-yellow motes drawn into the body from all round, accelerating as they arrive."""
    life = r(GATHER1 - GATHER0)
    d0 = "(0.05 * v.particle_random_4)"
    k = f"math.clamp((v.particle_age - {d0}) / ({life} - 0.05), 0, 1)"
    d = sphere_dir()
    dist = f"{RR} * (1 + 1.5 * math.pow(1 - {k}, 1.6))"
    comps = dict(burst(16), **{
        "minecraft:emitter_shape_point": {},
        "minecraft:particle_lifetime_expression": {"max_lifetime": life},
        "minecraft:particle_initial_speed": 0,
        "minecraft:particle_motion_parametric": {"relative_position": [f"{dist} * {d[0]}", f"{CHEST} + {dist} * {d[1]}",
                                                                       f"{dist} * {d[2]}"]}})
    vis = f"math.clamp((v.particle_age - {d0}) * 30, 0, 1) * math.clamp((1 - {k}) * 8, 0, 1)"
    sz = f"(0.09 + 0.05 * v.particle_random_3) * {FX} * {vis}"
    return particle("counter_absorbmotes", T_SPARK, comps, UV_SPARK, [sz, sz],
                    tinting=gradient("v.particle_random_3", [(0.0, WHITE), (0.6, YELLOW), (1.0, GOLD)]))


# ================================================================= 3. the counterforce (red-orange flash, pulse, steam, streaks)
def p_powerglow():
    """Soft red-orange glows just outside the body while the model itself is tinted (the Java tint): a
    halo round the silhouette, and the whole glow if the tint isn't available."""
    life = r(TINT1 - POWER + 0.12)
    flick = "(1 + 0.15 * math.sin(v.particle_age * (900 + 600 * v.particle_random_3) + 360 * v.particle_random_4))"
    env = f"math.clamp(v.particle_age * 14, 0, 1) * math.clamp((v.particle_lifetime - v.particle_age) / 0.15, 0, 1)"
    comps = dict(burst(12), **{
        "minecraft:emitter_shape_sphere": {"offset": [0, "0.5 * v.entity_height", 0], "radius": RR, "surface_only": True}},
        **still(life))
    sz = f"(0.5 + 0.2 * v.particle_random_3) * {FX} * {flick}"
    return particle("counter_powerglow", T_GLOW, comps, UV_GLOW, [sz, sz],
                    tinting={"color": [1, "0.45 + 0.12 * v.particle_random_2", 0.2, f"0.16 * {env}"]})


def p_powerring():
    """An orange-white pulse leaving the body: the force turned round."""
    comps = dict(burst(1), **{"minecraft:emitter_shape_point": {"offset": [0, CHEST, 0]}}, **still(0.24))
    sz = f"{RR} * (1.6 + 2.2 * (1 - math.pow(1 - {K}, 2)))"
    return particle("counter_powerring", T_RING, comps, frame_uv(frames(K, 7), 64, 64), [sz, sz],
                    tinting=gradient(K, [(0.0, CREAM), (0.4, GOLD), (1.0, '#00FF8A2E')]))


def p_steam():
    """A few puffs of white steam rising off the head and shoulders (both Sword/Shield and Scarlet/Violet)."""
    comps = {
        "minecraft:emitter_initialization": {"creation_expression": ENTITY_DEFAULTS},
        "minecraft:emitter_rate_steady": {"spawn_rate": 11, "max_particles": 5},
        "minecraft:emitter_lifetime_once": {"active_time": 0.36},
        "minecraft:emitter_shape_disc": {"offset": [0, "0.92 * v.entity_height", 0], "radius": "0.3 * v.entity_width + 0.05",
                                         "plane_normal": "y"},
        "minecraft:particle_lifetime_expression": {"max_lifetime": "0.42 + 0.12 * v.particle_random_1"},
        "minecraft:particle_initial_speed": 0,
        "minecraft:particle_motion_dynamic": {"linear_acceleration": [0, f"2.6 * {FX}", 0], "linear_drag_coefficient": 2.2},
        "minecraft:particle_initial_spin": SPIN}
    sz = f"(0.34 + 0.12 * v.particle_random_3) * {FX} * (0.75 + 0.5 * {K})"
    return particle("counter_steam", T_PUFF, comps, puff_frame(K, 1, 8), [sz, sz],
                    tinting={"color": [1, 1, 1, f"0.85 * (1 - {K} * {K})"]})


def p_powerstreaks():
    """Fast streaks sweeping forward past the body as it turns from defence to attack. Parametric, because
    in that frame -z is forward for certain (a shape's `direction` vector sent them backwards in-game)."""
    k = f"(1 - math.pow(1 - {K}, 2))"
    theta = "(360 * v.particle_random_1)"
    rad = "(0.55 * v.entity_width + 0.2)"
    pos = [f"{rad} * math.cos({theta})",
           f"v.entity_height * (0.2 + 0.65 * v.particle_random_3) + 0.25 * {rad} * math.sin({theta})",
           f"0.4 * {FRONT} - ({FRONT} + 1.4 * {FX}) * {k}"]
    comps = dict(burst(8, active=0.1), **{
        "minecraft:emitter_shape_point": {},
        "minecraft:particle_lifetime_expression": {"max_lifetime": "0.14 + 0.05 * v.particle_random_1"},
        "minecraft:particle_initial_speed": 0,
        "minecraft:particle_motion_parametric": {"relative_position": pos}})
    return particle("counter_powerstreaks", T_BEAM, comps, UV_BEAM,
                    [f"(0.55 + 0.25 * v.particle_random_3) * {FX} * (1 - {K})", f"0.05 * {FX}"], camera="lookat_direction",
                    tinting=gradient("v.particle_random_3", [(0.0, WHITE), (0.5, YELLOW), (1.0, ORANGE)]))


# ================================================================= 4. the strike (user side)
def p_strikeflash():
    """The force leaving the user's front with the punch."""
    comps = dict(burst(1), **{"minecraft:emitter_shape_point": {"offset": [0, CHEST, f"-{FRONT} - 0.15"]}}, **still(0.1))
    sz = f"0.8 * {FX} * (0.7 + 0.6 * {K})"
    return particle("counter_strikeflash", T_GLOW, comps, UV_GLOW, [sz, sz],
                    tinting={"color": [1, f"0.95 - 0.3 * {K}", f"0.8 - 0.5 * {K}", f"1 - {K}"]})


def p_strikedust():
    """Neutral dust kicked back from the feet by the lunge."""
    comps = dict(burst(6), **{
        "minecraft:emitter_shape_disc": {"offset": [0, 0.05, 0], "radius": "0.4 * v.entity_width + 0.1", "plane_normal": "y",
                                         "surface_only": True, "direction": "outwards"},
        "minecraft:particle_lifetime_expression": {"max_lifetime": "0.35 + 0.15 * v.particle_random_1"},
        "minecraft:particle_initial_speed": f"(1.6 + 1.2 * v.particle_random_2) * {FX}",
        "minecraft:particle_motion_dynamic": {"linear_acceleration": [0, 0.6, 0], "linear_drag_coefficient": 3.5},
        "minecraft:particle_initial_spin": SPIN})
    sz = f"(0.3 + 0.12 * v.particle_random_3) * {FX} * (0.6 + 0.6 * {K})"
    return particle("counter_strikedust", T_PUFF, comps, puff_frame(K, 2, 9), [sz, sz],
                    tinting={"color": [DUST[0], DUST[1], DUST[2], f"0.55 * (1 - {K})"]})


# ================================================================= 4. the force crossing to the target (action effect, t=0)
# Spawned with the battle's target locator, so the emitter knows where the target is: in its parametric
# frame -z is forward and the target is at (-dx, dy, -dz). A particle of age a stands for move time
# a + EMIT_LAG.
WAVE_A0 = r(STRIKE - EMIT_LAG)            # particle age the force leaves the user's front
WAVE_A1 = r(IMPACT - EMIT_LAG)            # ... and reaches the target's
WAVE_FL = r(WAVE_A1 - WAVE_A0)
WAVE_DEFAULTS = (ENTITY_DEFAULTS + " v.target_deltax = 0; v.target_deltay = 1; v.target_deltaz = 4;")
DIST = "math.max(math.sqrt(v.target_deltax * v.target_deltax + v.target_deltaz * v.target_deltaz), 0.01)"
# stop short of the target's centre by about half a body, but never past halfway
STOP = f"(1 - math.clamp(0.55 / {DIST}, 0, 0.5))"
START = ["0", CHEST, f"-{FRONT}"]


def wave_point(s, miss):
    """Point at path fraction s (a MoLang expression) from the user's front to the target's front.
    A missed force veers off sideways and keeps going past the target."""
    end = [f"(-v.target_deltax * {STOP})", "v.target_deltay", f"(-v.target_deltaz * {STOP})"]
    if miss:
        side = [f"(v.target_deltaz / {DIST})", "0", f"(-v.target_deltax / {DIST})"]
        end = [f"(-v.target_deltax * 1.35 + 1.1 * {side[0]})", "(v.target_deltay + 0.35)",
               f"(-v.target_deltaz * 1.35 + 1.1 * {side[2]})"]
    return [f"({START[i]} + ({end[i]} - {START[i]}) * {s})" for i in range(3)]


def wave_dir(miss):
    """Unit-ish direction of travel (for the drift that points the streaks along the path)."""
    a = wave_point("0", miss)
    b = wave_point("1", miss)
    d = [f"({b[i]} - {a[i]})" for i in range(3)]
    n = f"math.max(math.sqrt({d[0]} * {d[0]} + {d[1]} * {d[1]} + {d[2]} * {d[2]}), 0.01)"
    return [f"{d[i]} / {n}" for i in range(3)]


def wave_emitter(count, life, pos):
    return {
        "minecraft:emitter_initialization": {"creation_expression": WAVE_DEFAULTS},
        "minecraft:emitter_rate_instant": {"num_particles": count},
        "minecraft:emitter_lifetime_once": {"active_time": 0.1},
        "minecraft:emitter_shape_point": {},
        "minecraft:particle_lifetime_expression": {"max_lifetime": life},
        "minecraft:particle_initial_speed": 0,
        "minecraft:particle_motion_parametric": {"relative_position": pos}}


def p_wave(miss):
    """Speed streaks drawn along the path, each lighting up as the force passes it: a fast slash of
    force that reads at 20 particle ticks a second even though it crosses in under a tenth of one."""
    span = 1.25 if miss else 1.0
    s = f"(v.particle_random_1 * {span})"
    born = f"({WAVE_A0} + {WAVE_FL} * {s})"
    since = f"math.max(v.particle_age - {born}, 0)"
    p = wave_point(s, miss)
    d = wave_dir(miss)
    jit = ["(0.3 * v.particle_random_2 - 0.15)", "(0.3 * v.particle_random_3 - 0.15)", "0"]
    pos = [f"{p[i]} + {jit[i]} + {d[i]} * 2.5 * ({since} + 0.01 * v.particle_age)" for i in range(3)]
    vis = f"math.clamp((v.particle_age - {born}) * 60, 0, 1) * math.clamp(1 - {since} / 0.13, 0, 1)"
    if miss:
        vis += f" * math.clamp((1.25 - {s}) * 3, 0, 1)"
    life = r(WAVE_A1 + 0.15 + (0.05 if miss else 0))
    comps = wave_emitter(16, life, pos)
    return particle(f"counter_wave{'_miss' if miss else ''}", T_BEAM, comps, UV_BEAM,
                    [f"(0.55 + 0.35 * v.particle_random_4) * {FX} * {vis}", f"0.06 * {FX} * {vis}"], camera="lookat_direction",
                    tinting=gradient("v.particle_random_4", [(0.0, WHITE), (0.45, YELLOW), (1.0, ORANGE)]))


def p_wavehead(miss):
    """The bright head of the force, carried from the user's front to the target's."""
    span = 1.25 if miss else 1.0
    s = f"(math.clamp((v.particle_age - {WAVE_A0}) / {WAVE_FL}, 0, {span}))"
    p = wave_point(s, miss)
    jit = sphere_dir()
    pos = [f"{p[i]} + 0.12 * v.particle_random_3 * {jit[i]}" for i in range(3)]
    vis = f"math.clamp((v.particle_age - {WAVE_A0}) * 40, 0, 1)"
    if miss:
        vis += f" * math.clamp(({span} * {WAVE_FL} + {WAVE_A0} + 0.04 - v.particle_age) * 20, 0, 1)"
        life = r(WAVE_A0 + WAVE_FL * span + 0.06)
    else:
        life = r(WAVE_A1 + 0.02)
    comps = wave_emitter(3, life, pos)
    sz = f"(0.55 + 0.15 * v.particle_random_2) * {FX} * {vis}"
    return particle(f"counter_wavehead{'_miss' if miss else ''}", T_GLOW, comps, UV_GLOW, [sz, sz],
                    tinting=gradient("v.particle_random_2", [(0.0, WHITE), (1.0, GOLD)]))


# ================================================================= 4. the impact (target animation, 'target' locator)
TFRONT = "(0.3 * v.entity_width)"      # towards the attacker, on the target's face that took the hit
AT = [0, 0, f"-{TFRONT}"]


def p_impactcore():
    comps = dict(burst(1), **{"minecraft:emitter_shape_point": {"offset": AT}}, **still(0.13))
    sz = f"1.45 * {FX} * (0.85 + 0.5 * (1 - math.pow(1 - {K}, 3)))"
    return particle("counter_impactcore", T_GLOW, comps, UV_GLOW, [sz, sz],
                    tinting={"color": [1, 1, f"1 - 0.25 * {K}", f"1 - {K} * {K}"]})


def p_impactglow():
    """The orange-yellow glow round the white core, a little longer-lived."""
    comps = dict(burst(1), **{"minecraft:emitter_shape_point": {"offset": AT}}, **still(0.24))
    sz = f"2.5 * {FX} * (0.8 + 0.35 * {K})"
    return particle("counter_impactglow", T_GLOW, comps, UV_GLOW, [sz, sz],
                    tinting=gradient(K, [(0.0, '#D8FFD070'), (0.5, '#A0FF9A3A'), (1.0, '#00F2552B')]))


def p_impactstar():
    comps = dict(burst(1), **{"minecraft:emitter_shape_point": {"offset": AT}}, **still(0.2))
    sz = f"2.0 * {FX}"
    return particle("counter_impactstar", T_HIT, comps, flipbook(32, 32, 5, horizontal=False), [sz, sz],
                    tinting=gradient(K, [(0.0, WHITE), (0.6, CREAM), (1.0, YELLOW)]))


def p_impactlines():
    """Radial lines bursting out of the hit."""
    comps = dict(burst(1), **{"minecraft:emitter_shape_point": {"offset": AT}}, **still(0.24))
    sz = f"3.1 * {FX}"
    return particle("counter_impactlines", T_LINES, comps, flipbook(64, 64, 5), [sz, sz],
                    tinting=gradient(K, [(0.0, WHITE), (0.35, YELLOW), (0.7, ORANGE), (1.0, PALERED)]))


def p_impactring():
    """A small, fast shockwave."""
    comps = dict(burst(1), **{"minecraft:emitter_shape_point": {"offset": AT}}, **still(0.26))
    sz = f"{FX} * (0.9 + 2.6 * (1 - math.pow(1 - {K}, 2)))"
    return particle("counter_impactring", T_RING, comps, frame_uv(frames(K, 7), 64, 64), [sz, sz],
                    tinting=gradient(K, [(0.0, CREAM), (0.5, GOLD), (1.0, '#00FF8A2E')]))


def p_impactstreaks():
    """Angular impact streaks thrown out of the hit: white, then yellow, then a pale red."""
    comps = dict(burst(12), **{
        "minecraft:emitter_shape_sphere": {"offset": AT, "radius": f"0.15 * {FX}", "surface_only": True, "direction": "outwards"},
        "minecraft:particle_lifetime_expression": {"max_lifetime": "0.16 + 0.08 * v.particle_random_1"},
        "minecraft:particle_initial_speed": f"(11 + 5 * v.particle_random_2) * {FX}",
        "minecraft:particle_motion_dynamic": {"linear_drag_coefficient": 6}})
    return particle("counter_impactstreaks", T_BEAM, comps, UV_BEAM,
                    [f"(0.7 + 0.4 * v.particle_random_3) * {FX} * (1 - {K})", f"0.075 * {FX} * (1 - 0.5 * {K})"],
                    camera="lookat_direction",
                    tinting=gradient(K, [(0.0, WHITE), (0.4, YELLOW), (0.75, ORANGE), (1.0, PALERED)]))


def p_impactsparks():
    comps = dict(burst(18), **{
        "minecraft:emitter_shape_sphere": {"offset": AT, "radius": f"0.2 * {FX}", "surface_only": True, "direction": "outwards"},
        "minecraft:particle_lifetime_expression": {"max_lifetime": "0.3 + 0.2 * v.particle_random_1"},
        "minecraft:particle_initial_speed": f"(5 + 4 * v.particle_random_2) * {FX}",
        "minecraft:particle_motion_dynamic": {"linear_acceleration": [0, -5, 0], "linear_drag_coefficient": 3.2}})
    sz = f"(0.1 + 0.06 * v.particle_random_3) * {FX} * (0.4 + 0.6 * (1 - {K}))"
    return particle("counter_impactsparks", T_SPARK, comps, frame_uv(frames(K, 4), 8, 8, horizontal=False), [sz, sz],
                    tinting={"color": [1, "0.78 + 0.22 * v.particle_random_4", "0.45 + 0.4 * v.particle_random_4", 1]})


def p_impactsmoke():
    """A little orange smoke hanging where the hit landed, gone in half a second (Scarlet/Violet)."""
    comps = dict(burst(5), **{
        "minecraft:emitter_shape_sphere": {"offset": AT, "radius": f"0.25 * {FX}", "direction": "outwards"},
        "minecraft:particle_lifetime_expression": {"max_lifetime": "0.4 + 0.15 * v.particle_random_1"},
        "minecraft:particle_initial_speed": f"(1.2 + 0.8 * v.particle_random_2) * {FX}",
        "minecraft:particle_motion_dynamic": {"linear_acceleration": [0, 0.8, 0], "linear_drag_coefficient": 3},
        "minecraft:particle_initial_spin": SPIN})
    sz = f"(0.45 + 0.15 * v.particle_random_3) * {FX} * (0.7 + 0.5 * {K})"
    return particle("counter_impactsmoke", T_PUFF, comps, puff_frame(K, 2, 9), [sz, sz],
                    tinting=gradient(K, [(0.0, '#B0FFB060'), (0.5, '#80E07A40'), (1.0, '#00A0603A')]))


# ================================================================= animations
STEP = 0.05


def vec(v):
    return [r(c, 3) for c in v]


def lerpv(a, b, k):
    return [a[i] + (b[i] - a[i]) * k for i in range(len(a))]


def smooth_fn(points):
    """[(time, value or list)] -> function returning a list, smoothstep-blended between the points."""
    pts = [(p[0], list(p[1]) if isinstance(p[1], (tuple, list)) else [p[1]]) for p in points]

    def fn(x):
        if x <= pts[0][0]:
            return pts[0][1]
        for (a, va), (b, vb) in zip(pts, pts[1:]):
            if x <= b:
                return lerpv(va, vb, smooth((x - a) / (b - a)))
        return pts[-1][1]
    return fn


def dense_keys(fn, end, tol=0.02, extra=()):
    """Sample fn every STEP (plus the `extra` times) up to `end`; drop points linear interpolation reproduces."""
    xs = sorted(set([round(i * STEP, 4) for i in range(int(end / STEP + 1e-9) + 1)] + [end] + [x for x in extra if x <= end]))
    pts = [(x, [float(c) for c in fn(x)]) for x in xs]
    keep = [pts[0]]
    for i in range(1, len(pts) - 1):
        a, b = keep[-1], pts[i + 1]
        guess = lerpv(a[1], b[1], (pts[i][0] - a[0]) / (b[0] - a[0]))
        if max(abs(g - v) for g, v in zip(guess, pts[i][1])) > tol:
            keep.append(pts[i])
    keep.append(pts[-1])
    return {t(x): vec(v) for x, v in keep}


KEY_TIMES = (BRACE, ABSORB, ABSORB + 0.04, GATHER1, POWER, WIND0, WIND1, STRIKE, STRIKE + 0.04, IMPACT)

# root_part: position in model units (+z = backwards, -y = down), rotation in degrees (+x = lean forward)
ROOT_POS = [(0, (0, 0, 0)), (BRACE, (0, -1.4, 1.0)), (ABSORB, (0, -1.1, 2.8)), (ABSORB + 0.06, (0, -1.5, 1.8)),
            (GATHER1, (0, -1.4, 1.6)), (WIND0, (0, -1.1, 2.0)), (WIND1, (0, -1.3, 3.0)), (STRIKE, (0, -0.7, 0)),
            (IMPACT, (0, -0.6, 0)), (IMPACT + 0.12, (0, -0.4, 0)), (1.08, (0, -0.1, 0)), (1.22, (0, 0, 0)),
            (ACTOR_LEN, (0, 0, 0))]
ROOT_ROT = [(0, (0, 0, 0)), (BRACE, (5, 0, 0)), (ABSORB, (-9, 0, 4)), (ABSORB + 0.04, (-6, 0, -3)), (ABSORB + 0.09, (2, 0, 1)),
            (GATHER1, (4, 0, 0)), (POWER + 0.04, (2, 0, 0)), (WIND1, (-9, 0, 0)), (STRIKE, (13, 0, 0)), (IMPACT + 0.06, (15, 0, 0)),
            (1.0, (6, 0, 0)), (1.2, (0, 0, 0)), (ACTOR_LEN, (0, 0, 0))]
ROOT_SCALE = [(0, (1, 1, 1)), (BRACE, (1.04, 0.95, 1.04)), (ABSORB, (0.97, 1.03, 0.97)), (ABSORB + 0.07, (1.04, 0.95, 1.04)),
              (GATHER1, (1.03, 0.96, 1.03)), (POWER + 0.03, (1.07, 0.97, 1.07)), (WIND1, (0.97, 1.04, 0.97)),
              (STRIKE, (1.03, 0.96, 1.08)), (IMPACT + 0.06, (1.02, 0.98, 1.04)), (1.05, (1, 1, 1)), (ACTOR_LEN, (1, 1, 1))]
HEAD_ROT = [(0, 0), (BRACE, 6), (ABSORB, -8), (ABSORB + 0.08, 4), (GATHER1, 5), (WIND1, -4), (STRIKE, 10), (IMPACT + 0.06, 9),
            (1.1, 2), (ACTOR_LEN, 0)]
# arms (additive; a bone the model lacks is skipped): left = guard, right = the punching arm.
# Deltas [x, y, z] for the LEFT arm; the right arm's are mirrored (y and z negated). From Focus Blast's
# forward-kinematics census of learner rigs: [-20, 20, 15] puts the hands in front of the chest.
GUARD = (-32, 22, 22)
LEFT_ARM = [(0, (0, 0, 0)), (BRACE, GUARD), (ABSORB, (-14, 26, 28)), (ABSORB + 0.08, GUARD), (WIND1, (-36, 20, 18)),
            (STRIKE, (8, 6, 4)), (IMPACT + 0.1, (6, 4, 2)), (1.12, (0, 0, 0)), (ACTOR_LEN, (0, 0, 0))]
RIGHT_ARM = [(0, (0, 0, 0)), (BRACE, GUARD), (ABSORB, (-14, 26, 28)), (ABSORB + 0.08, GUARD), (WIND0, (-10, 10, 10)),
             (WIND1, (28, -8, 6)), (STRIKE, (-80, 4, -6)), (IMPACT + 0.1, (-76, 4, -4)), (1.12, (-12, 0, 0)),
             (ACTOR_LEN, (0, 0, 0))]
ARM_BONES = [('arm_left', 'arm_right'), ('left_upper_arm', 'right_upper_arm'), ('left_arm', 'right_arm')]


def shiver(x):
    """The power surging through the body: a small, fast shake while the tint comes on."""
    a, b = POWER - 0.02, WIND0 + 0.02
    if not a <= x <= b:
        return 0.0
    k = (x - a) / (b - a)
    return math.sin(math.pi * k) * math.sin(2 * math.pi * 18 * (x - a))


def fine_keys(fn, start, end, step=0.0125):
    n = int(round((end - start) / step))
    return {t(start + i * step): vec(fn(start + i * step)) for i in range(n + 1)}


def merged(*dicts):
    out = {}
    for d in dicts:
        out.update(d)
    return dict(sorted(out.items(), key=lambda kv: float(kv[0])))


def fx(time):
    return t(max(0.0, time - FX_LEAD))


def actor_animation():
    rot = smooth_fn(ROOT_ROT)
    pos = smooth_fn(ROOT_POS)

    def pos_shivered(x):
        p = pos(x)
        return [p[0] + 0.35 * shiver(x), p[1], p[2]]
    bones = {'root_part': {
        'rotation': dense_keys(rot, ACTOR_LEN, 0.15, KEY_TIMES),
        'position': merged(dense_keys(pos_shivered, ACTOR_LEN, 0.02, KEY_TIMES), fine_keys(pos_shivered, POWER - 0.02, WIND0 + 0.02)),
        'scale': dense_keys(smooth_fn(ROOT_SCALE), ACTOR_LEN, 0.004, KEY_TIMES)}}
    left = dense_keys(smooth_fn(LEFT_ARM), ACTOR_LEN, 0.15, KEY_TIMES)
    right_fn = smooth_fn(RIGHT_ARM)
    right = dense_keys(lambda x: (lambda v: [v[0], -v[1], -v[2]])(right_fn(x)), ACTOR_LEN, 0.15, KEY_TIMES)
    for lb, rb in ARM_BONES:
        bones[lb] = {'rotation': left}
        bones[rb] = {'rotation': right}
    head = smooth_fn(HEAD_ROT)
    bones['head'] = {'rotation': dense_keys(lambda x: [head(x)[0], 0, 0], ACTOR_LEN, 0.15, KEY_TIMES)}

    def at(time, *names):
        return {fx(time): [{'effect': f'cobblemon:counter_{n}', 'locator': 'root'} for n in names]}
    particles = merged(
        at(0.02, 'bracemotes'),
        at(ABSORB, 'absorbflash', 'absorbstar', 'absorbstreaks', 'absorbsparks'),
        at(GATHER0, 'absorbring', 'absorbmotes'),
        at(POWER, 'powerring', 'powerglow'),
        at(GATHER1 - 0.04, 'steam'),
        at(WIND1 - 0.02, 'powerstreaks'),
        at(STRIKE, 'strikeflash', 'strikedust'))
    return {
        'animation_length': ACTOR_LEN,
        'bones': bones,
        'particle_effects': particles,
        'sound_effects': {
            t(ABSORB): {'effect': 'move.counter.absorb'},
            t(POWER - 0.02): {'effect': 'move.counter.power'},
            t(STRIKE - 0.06): {'effect': 'move.counter.strike'},
        },
    }


# ---------------------------------------------------------------- the lunge
# The server measures the real gap between the two Pokemon (v.cn_units, in the user's model units) and
# picks the lunge that stops just short of the target, so a Pokemon standing close doesn't drive into it.
LUNGE_MAX = 7           # model units at most (under half a block at scale 1)
LUNGE_FALLBACK = 5      # no target entity
LUNGE = [(0, 0), (WIND1, 0), (STRIKE, 0.85), (IMPACT, 1.0), (IMPACT + 0.12, 0.8), (1.08, 0.18), (1.22, 0), (ACTOR_LEN, 0)]
DISTANCE_EXPR = (
    "v.cn_units = (q.target.width > 0) ? math.clamp((q.user.distance_to_pos(q.target.x, q.target.y, q.target.z)"
    " - 0.5 * q.target.width - 0.5 * q.user.width - 0.4) * 16 / math.max(q.user.species.base_scale, 0.1), 0, "
    f"{LUNGE_MAX}) : {LUNGE_FALLBACK}")


def lunge_animation(units):
    f = smooth_fn(LUNGE)
    return {'animation_length': ACTOR_LEN,
            'bones': {'root_part': {'position': dense_keys(lambda x: [0, 0, -units * f(x)[0]], ACTOR_LEN, 0.02, KEY_TIMES)}}}


def fail_animation():
    """Braced for a hit that never connected (or doesn't count): the guard goes up, holds, and drops."""
    pos = smooth_fn([(0, (0, 0, 0)), (BRACE, (0, -1.4, 1.0)), (0.5, (0, -1.2, 0.8)), (0.72, (0, 0, 0)), (FAIL_LEN, (0, 0, 0))])
    rot = smooth_fn([(0, (0, 0, 0)), (BRACE, (5, 0, 0)), (0.42, (4, 0, 2)), (0.55, (2, 0, -2)), (0.75, (0, 0, 0)), (FAIL_LEN, (0, 0, 0))])
    sc = smooth_fn([(0, (1, 1, 1)), (BRACE, (1.04, 0.95, 1.04)), (0.5, (1.03, 0.96, 1.03)), (0.72, (1, 1, 1)), (FAIL_LEN, (1, 1, 1))])
    arm = smooth_fn([(0, (0, 0, 0)), (BRACE, GUARD), (0.5, GUARD), (0.75, (0, 0, 0)), (FAIL_LEN, (0, 0, 0))])
    head = smooth_fn([(0, (0, 0, 0)), (BRACE, (6, 0, 0)), (0.4, (3, 8, 0)), (0.55, (3, -8, 0)), (0.75, (0, 0, 0)), (FAIL_LEN, (0, 0, 0))])
    bones = {'root_part': {'position': dense_keys(pos, FAIL_LEN, 0.02), 'rotation': dense_keys(rot, FAIL_LEN, 0.15),
                           'scale': dense_keys(sc, FAIL_LEN, 0.004)},
             'head': {'rotation': dense_keys(head, FAIL_LEN, 0.15)}}
    left = dense_keys(arm, FAIL_LEN, 0.15)
    right = {k: vec([v[0], -v[1], -v[2]]) for k, v in left.items()}
    for lb, rb in ARM_BONES:
        bones[lb] = {'rotation': left}
        bones[rb] = {'rotation': right}
    return {'animation_length': FAIL_LEN, 'bones': bones,
            'particle_effects': {fx(0.02): {'effect': 'cobblemon:counter_bracemotes', 'locator': 'root'}}}


def target_animation():
    """Started in the same tick as the user's; holds still until the force lands, then one hit reaction."""
    I = IMPACT
    pos = [(0.0, [0, 0, 0]), (I, [0, 0, 0]), (I + 0.04, [0, 1.0, 5.5]), (I + 0.12, [0, 0.6, 7.0]), (I + 0.24, [0, 0.2, 4.0]),
           (I + 0.4, [0, 0, 1.5]), (I + 0.56, [0, 0, 0.3]), (I + 0.7, [0, 0, 0])]
    rot = [(0.0, [0, 0, 0]), (I, [0, 0, 0]), (I + 0.04, [-13, 0, 0]), (I + 0.12, [-10, 0, 4]), (I + 0.24, [-5, 0, -3]),
           (I + 0.4, [-2, 0, 1]), (I + 0.56, [0, 0, 0]), (I + 0.7, [0, 0, 0])]
    sc = [(0.0, [1, 1, 1]), (I, [1, 1, 1]), (I + 0.04, [1.07, 0.92, 1.07]), (I + 0.14, [0.97, 1.03, 0.97]), (I + 0.3, [1, 1, 1]),
          (I + 0.7, [1, 1, 1])]

    def exact(points):
        return {t(k): vec(v) for k, v in points}
    impact = [{'effect': f'cobblemon:counter_{n}', 'locator': 'target'} for n in (
        'impactcore', 'impactstar', 'impactglow', 'impactlines', 'impactring', 'impactstreaks', 'impactsparks', 'impactsmoke')]
    return {
        'animation_length': r(I + 0.7),
        'bones': {'root_part': {'position': exact(pos), 'rotation': exact(rot), 'scale': exact(sc)}},
        'particle_effects': {fx(I): impact},
        'sound_effects': {t(I): [{'effect': 'impact.fighting'}, {'effect': 'move.counter.impact'}]},
    }


def build_animation_file():
    return {'format_version': '1.8.0', 'animations': {
        'animation.counter.actor': actor_animation(),
        'animation.counter.actor_fail': fail_animation(),
        **{f'animation.counter.lunge_{k}': lunge_animation(k) for k in range(1, LUNGE_MAX + 1)},
        'animation.counter.target': target_animation()}}


# ================================================================= the action effect
def play(anim):
    return f"q.play_animation(q.bedrock_stateful('counter', '{anim}', 'endures_primary_animations'))"


# What the battle reported decides which version plays; nothing here works anything out for itself.
HIT = "q.hurt == true"
MISS = "q.hurt == false && q.missed == true"
CONNECTS = f"({HIT} || q.missed == true)"          # the strike is thrown (it lands or it misses)
FAILED = "q.hurt == false && q.missed == false"     # no physical hit to return, or a target it can't touch
USER = "q.entity.is_user == true"
TARGET_HIT = "q.entity.is_user == false && q.hurt(q.entity.uuid) == true"
if os.environ.get('COUNTER_FORCE_MISS') == '1':
    # debug build for checking the miss version in-game (a real miss needs an evasion boost): every
    # landed Counter plays as a miss. Never ship this.
    HIT = "q.hurt == 2"
    MISS = "q.hurt == true || q.missed == true"
    TARGET_HIT = "q.entity.is_user == 2"


def tint_call(who, rgb, strength, flash, delay, rise, hold, fall):
    args = [*rgb, strength, flash, delay, rise, hold, fall]
    return f"q.{who}.model_tint({', '.join(str(r(a)) for a in args)})"


def build_effect_file():
    user_tint = tint_call('user', USER_TINT, USER_TINT_STRENGTH, USER_FLASH, TINT0, POWER + 0.04 - TINT0,
                          TINT1 - POWER - 0.04, TINT2 - TINT1)
    target_tint = tint_call('target', TARGET_TINT, TARGET_TINT_STRENGTH, TARGET_FLASH, IMPACT - 0.02, 0.03, 0.05, 0.16)
    # Every keyframe costs a server tick in 1.7.3, so the whole start is one `parallel` (one tick).
    start = [
        {'type': 'entity_molang', 'entityCondition': f"{USER} && {CONNECTS}", 'expressions': [play('actor')]},
        {'type': 'entity_molang', 'entityCondition': f"{USER} && {FAILED}", 'expressions': [play('actor_fail')]},
        {'type': 'entity_molang', 'entityCondition': TARGET_HIT, 'expressions': [play('target')]},
    ]
    # the lunge nearest the real gap (lunge_0 = no lunge: already touching)
    for k in range(1, LUNGE_MAX + 1):
        cond = f"v.cn_units >= {k - 0.5:g}" if k == LUNGE_MAX else f"v.cn_units >= {k - 0.5:g} && v.cn_units < {k + 0.5:g}"
        start.append({'type': 'entity_molang', 'condition': cond, 'entityCondition': f"{USER} && {CONNECTS}",
                      'expressions': [play(f'lunge_{k}')]})
    for layer in ('wave', 'wavehead'):
        start.append({'type': 'entity_particles', 'entityCondition': f"{USER} && {HIT}", 'effect': f'cobblemon:counter_{layer}',
                      'locators': ['root'], 'targetLocators': ['target']})
        start.append({'type': 'entity_particles', 'entityCondition': f"{USER} && {MISS}", 'effect': f'cobblemon:counter_{layer}_miss',
                      'locators': ['root'], 'targetLocators': ['target']})
    # the Java side: the red-orange flash on the user's model, and the target's orange flash on the hit
    # (each returns 0 and does nothing if the hook isn't there)
    start.append({'type': 'molang', 'expressions': f"{CONNECTS} ? {user_tint} : 0"})
    start.append({'type': 'molang', 'expressions': f"{HIT} ? {target_tint} : 0"})
    # the parallel above already took a tick; let the battle go on (HP bar) as the hit lands
    pause = f"{CONNECTS} ? {r(IMPACT - 0.05)} : {r(FAIL_LEN - 0.35)}"
    return {'timeline': [
        {'type': 'add_holds', 'holds': ['effects']},
        # server side: how far the user can lunge (see DISTANCE_EXPR)
        {'type': 'molang', 'expressions': DISTANCE_EXPR},
        {'type': 'parallel', 'keyframes': start},
        {'type': 'pause', 'pause': pause},
        {'type': 'remove_holds', 'holds': ['effects']},
        {'type': 'pause', 'pause': TAIL},
    ]}


def all_particles():
    out = [p_bracemotes(), p_absorbflash(), p_absorbstar(), p_absorbstreaks(), p_absorbsparks(), p_absorbring(), p_absorbmotes(),
           p_powerglow(), p_powerring(), p_steam(), p_powerstreaks(), p_strikeflash(), p_strikedust()]
    for miss in (False, True):
        out += [p_wave(miss), p_wavehead(miss)]
    out += [p_impactcore(), p_impactglow(), p_impactstar(), p_impactlines(), p_impactring(), p_impactstreaks(),
            p_impactsparks(), p_impactsmoke()]
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
