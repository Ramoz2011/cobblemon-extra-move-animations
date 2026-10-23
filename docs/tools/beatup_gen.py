"""Generates Beat Up's particle effects, generic animation file and action effect.

Outputs (paths relative to the repo root):
  src/main/resources/assets/cobblemon/bedrock/particles/moves/beatup/*.particle.json
  src/main/resources/assets/cobblemon/bedrock/generic/animations/moves/beatup.animation.json
  src/main/resources/data/cobblemon/action_effects/moves/beatup.json

Edit the constants below and re-run `python3 docs/tools/beatup_gen.py`; don't hand-edit the outputs.
Design notes and the reasoning behind the numbers: docs/beatup_assets.md.

How the pieces fit:
- Beat Up hits once per healthy party member (the user included). The action effect reads the real
  hit count (q.hit_count) and starts, in one tick, the user's animation, the target's animation for
  that many hits, the wave and streaks that run from the user to the target, and the Java hook
  q.user.beat_up_afterimages(...), which sends nearby clients the party member behind each strike.
- The client draws a dark afterimage of each of those Pokemon rushing in and lunging on its strike
  (Java, src/client/.../beatup). Strike k lands at S0 + DT * k; those two numbers go to the Java
  side through the hook, so this file is the one place they're set.
- The target animation carries a flinch on every strike plus the impact effects and sounds, on the
  client clock, so the hits stay on the frames where the afterimages land. Without the Java side the
  strikes still land, the way Sword/Shield and Scarlet/Violet show the move: a brawl of hits on the
  target with nobody in sight.
- Particles are born a client tick after the animation fires them, so the target animation fires
  them FX_LEAD early to put them on the strike frame.
"""
import json, math, os

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..')
RES = os.path.join(ROOT, 'src/main/resources')
PART_DIR = os.path.join(RES, 'assets/cobblemon/bedrock/particles/moves/beatup')
ANIM_OUT = os.path.join(RES, 'assets/cobblemon/bedrock/generic/animations/moves/beatup.animation.json')
EFFECT_OUT = os.path.join(RES, 'data/cobblemon/action_effects/moves/beatup.json')

# ---------------------------------------------------------------- timing (seconds from the start of the move)
S0 = 0.55            # the first strike lands (the user's own)
DT = 0.18            # then one every DT seconds
MAX_HITS = 6         # a party of six
FINAL_GAP = 0.08     # the finishing burst follows the last strike
REAR = 0.12          # the user rears back, gathering the dark energy
THRUST = 0.19        # ... and snaps forward, sending the first afterimage
SETTLE = 0.32        # then holds a forward lean, urging the team on
FX_LEAD = 0.075      # particles fired this early show up on the strike frame
EMIT_LAG = 0.075     # an action-effect emitter's first particles are born about this late
TAIL = 0.45          # after the finish: the last afterimage fades and the burst clears


def strike(k):
    return S0 + DT * k


def finish(n):
    return strike(n - 1) + FINAL_GAP


# ---------------------------------------------------------------- palette (#AARRGGBB)
CORE = '#FFE8AEFF'     # pale violet
VIOLET = '#FFB06BFF'
PURPLE = '#FF6A2CA8'
DEEP = '#FF3A0062'     # deep purple
INDIGO = '#FF2A1B5E'
SHADOW = '#FF1C1030'   # near-black violet
DUST = (0.46, 0.43, 0.5)   # the brawl's dust: a dusky lavender grey


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


T_PUFF = tex('generic/fire/cloudyfire_white', 160, 16)   # 10 frames 16x16: a puff swelling and breaking up
T_GLOW = tex('moves/bravebird_glow', 32, 32)             # round soft glow (docs/tools/bravebird_textures.py)
T_RING = tex('generic/ring/giantring_white', 448, 64)    # 7 frames 64x64: a ring expanding and breaking up
T_STAR = tex('moves/beatup_star', 32, 160)               # 5 frames 32x32, top to bottom (docs/tools/beatup_textures.py)
T_BURST = tex('moves/shadowball_impact', 256, 32)        # 8 frames 32x32: a black orb bursting into purple scrawls
T_SKY = tex('generic/skyding', 275, 25)                  # 11 frames 25x25: a four-point star twinkling
T_BEAM = tex('generic/smallbeam', 140, 91)
T_SHARD = tex('generic/impact/impact_dark', 8, 56)       # 7 frames 8x8: black fragments
T_SPARK = tex('generic/sparkle/glowingsparkle', 8, 32)   # 4 frames 8x8, big to small
T_FIST = tex('generic/bigfist', 270, 30)                 # 9 frames 30x30: a fist, then it dithers away

UV_BEAM = {"uv": [70, 42], "uv_size": [70, 7]}    # right half of one smallbeam frame: a soft streak
UV_GLOW = {"uv": [0, 0], "uv_size": [32, 32]}


def frame_uv(index, fw, fh, horizontal=True):
    """Static UV of frame `index` (a MoLang expression) of a sheet laid out left-to-right or top-to-bottom."""
    return {"uv": [f"{fw} * ({index})", 0] if horizontal else [0, f"{fh} * ({index})"], "uv_size": [fw, fh]}


def frames(k, count):
    """Frame index for a 0..1 progress over `count` frames."""
    return f"math.floor(math.clamp({k}, 0, 0.999) * {count})"


def puff_frame(k, first=1, last=8):
    return frame_uv(f"{first} + math.floor(math.clamp({k}, 0, 0.999) * {last - first + 1})", 16, 16)


def gradient(inp, stops):
    return {"color": {"interpolant": inp, "gradient": {t(k): v for k, v in stops}}}


def particle(pid, texture, components, uv, size, camera="rotate_xyz", tinting=None, curves=None):
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


ENTITY_DEFAULTS = "v.entity_width = 1; v.entity_height = 1;"
BODY = "math.clamp(math.max(v.entity_width, v.entity_height), 0.5, 3.5)"   # body size (blocks)
RR = f"(math.max(0.55 * {BODY}, 0.4) + 0.08)"                               # a ball just outside the body
FX = "math.clamp(0.55 + 0.4 * math.max(v.entity_width, v.entity_height), 0.7, 1.8)"   # effect scale: grows slowly with size
K = "(v.particle_age / v.particle_lifetime)"
SPIN = {"rotation": "math.floor(v.particle_random_4 * 4) * 90"}


def burst(count, defaults=ENTITY_DEFAULTS, active=0.2):
    comps = {"minecraft:emitter_initialization": {"creation_expression": defaults}} if defaults else {}
    comps["minecraft:emitter_rate_instant"] = {"num_particles": count}
    comps["minecraft:emitter_lifetime_once"] = {"active_time": active}
    return comps


def sphere_dir(theta="(360 * v.particle_random_1)", u="v.particle_random_2"):
    sin_phi = f"math.sqrt(1 - math.pow(2 * {u} - 1, 2))"
    return f"{sin_phi} * math.cos({theta})", f"(2 * {u} - 1)", f"{sin_phi} * math.sin({theta})"


# ================================================================= the user: gather, burst, ripple (actor animation)
def p_gather():
    """Dark wisps drawn in from all round, gathering on the body as the user rears back."""
    k = "math.clamp(v.particle_age / 0.2, 0, 1)"
    d = sphere_dir()
    dist = f"{RR} * (1 + 1.7 * math.pow(1 - {k}, 1.4))"
    comps = dict(burst(22), **{
        "minecraft:emitter_shape_point": {},
        "minecraft:particle_lifetime_expression": {"max_lifetime": 0.22},
        "minecraft:particle_initial_speed": 0,
        "minecraft:particle_motion_parametric": {"relative_position": [f"{dist} * {d[0]}", f"{dist} * {d[1]}", f"{dist} * {d[2]}"]},
        "minecraft:particle_initial_spin": SPIN})
    vis = f"math.clamp(v.particle_age * 30, 0, 1) * math.clamp((0.22 - v.particle_age) / 0.05, 0, 1)"
    sz = f"(0.26 + 0.12 * v.particle_random_3) * {FX} * (0.6 + 0.4 * {k})"
    return particle("beatup_gather", T_PUFF, comps, puff_frame(k, 3, 8), [sz, sz],
                    tinting={"color": ["0.2", "0.1", "0.32", f"0.85 * {vis}"]})


def p_aura():
    """A dark flicker over the user while it calls its team: soft glows just outside the body."""
    flick = "(1 + 0.18 * math.sin(v.particle_age * (1100 + 600 * v.particle_random_3) + 360 * v.particle_random_4))"
    env = "math.clamp(v.particle_age * 12, 0, 1) * math.clamp((v.particle_lifetime - v.particle_age) / 0.15, 0, 1)"
    comps = dict(burst(14), **{
        "minecraft:emitter_shape_sphere": {"radius": RR, "surface_only": True},
        "minecraft:particle_lifetime_expression": {"max_lifetime": 0.5},
        "minecraft:particle_initial_speed": 0,
        "minecraft:particle_motion_dynamic": {}})
    sz = f"(0.9 + 0.3 * v.particle_random_3) * {FX} * {flick}"
    return particle("beatup_aura", T_GLOW, comps, UV_GLOW, [sz, sz],
                    tinting={"color": ["0.32", "0.12", "0.55", f"0.32 * {env} * {flick}"]})


def p_burst():
    """The snap forward throws dark puffs off the body."""
    comps = dict(burst(12), **{
        "minecraft:emitter_shape_sphere": {"radius": f"0.45 * {BODY}", "surface_only": True, "direction": "outwards"},
        "minecraft:particle_lifetime_expression": {"max_lifetime": "0.26 + 0.1 * v.particle_random_1"},
        "minecraft:particle_initial_speed": f"(3.5 + 2 * v.particle_random_2) * {FX}",
        "minecraft:particle_motion_dynamic": {"linear_drag_coefficient": 7},
        "minecraft:particle_initial_spin": SPIN})
    sz = f"(0.32 + 0.12 * v.particle_random_3) * {FX} * (1 - {K} * {K})"
    return particle("beatup_burst", T_PUFF, comps, puff_frame(K, 2, 9), [sz, sz],
                    tinting=gradient(K, [(0.0, INDIGO), (0.6, SHADOW), (1.0, '#001C1030')]))


def p_burstsparks():
    """... and a spray of violet sparks."""
    comps = dict(burst(10), **{
        "minecraft:emitter_shape_sphere": {"radius": f"0.4 * {BODY}", "surface_only": True, "direction": "outwards"},
        "minecraft:particle_lifetime_expression": {"max_lifetime": "0.22 + 0.1 * v.particle_random_1"},
        "minecraft:particle_initial_speed": f"(5 + 3 * v.particle_random_2) * {FX}",
        "minecraft:particle_motion_dynamic": {"linear_drag_coefficient": 5}})
    uv = frame_uv(frames(K, 4), 8, 8, horizontal=False)
    sz = f"(0.13 + 0.05 * v.particle_random_3)"
    return particle("beatup_burstsparks", T_SPARK, comps, uv, [sz, sz],
                    tinting=gradient(K, [(0.0, CORE), (0.5, VIOLET), (1.0, PURPLE)]))


def p_ripple():
    """A shadowy ring spreading over the ground from the user's feet."""
    comps = dict(burst(1), **{
        "minecraft:emitter_shape_point": {"offset": [0, 0.04, 0]},
        "minecraft:particle_lifetime_expression": {"max_lifetime": 0.34},
        "minecraft:particle_initial_speed": 0,
        "minecraft:particle_motion_dynamic": {}})
    uv = frame_uv(frames(K, 7), 64, 64)
    sz = f"(0.8 + 2.6 * (1 - math.pow(1 - {K}, 2))) * {FX}"
    return particle("beatup_ripple", T_RING, comps, uv, [sz, sz], camera="emitter_transform_xz",
                    tinting={"color": ["0.42", "0.18", "0.75", f"0.85 * (1 - {K} * {K})"]})


# ================================================================= user to target (action effect, fired at the start)
# Fired by the action effect with targetLocators: the target sits at (-dx, dy, -dz) in the emitter's frame.
TX, TY, TZ = "(-v.target_deltax)", "v.target_deltay", "(-v.target_deltaz)"
TARGET_DEFAULTS = "v.target_deltax = 0; v.target_deltay = 0; v.target_deltaz = 5;"


def one_per_tick(count):
    """Spawns one particle per client tick, so a particle's spawn age tells which one it is (v.emitter_age
    is copied into the particle at spawn)."""
    return {
        "minecraft:emitter_initialization": {"creation_expression": TARGET_DEFAULTS},
        "minecraft:emitter_rate_steady": {"spawn_rate": 20, "max_particles": count},
        "minecraft:emitter_lifetime_once": {"active_time": r(count / 20 - 0.01)},
    }


def p_wave():
    """A quick shadowy ripple running along the ground towards the target: three flat rings in a row."""
    i = "math.round(v.emitter_age * 20)"
    start = f"({THRUST + 0.02 - EMIT_LAG} + 0.05 * {i} - v.emitter_age)"   # its own delay, from its spawn
    life = 0.26
    k = f"math.clamp((v.particle_age - {start}) / {life}, 0, 1)"
    f = f"(0.22 + 0.25 * {i})"                                             # share of the way to the target
    comps = dict(one_per_tick(3), **{
        "minecraft:emitter_shape_point": {},
        "minecraft:particle_lifetime_expression": {"max_lifetime": f"{start} + {life}"},
        "minecraft:particle_initial_speed": 0,
        "minecraft:particle_motion_parametric": {"relative_position": [f"{f} * {TX}", f"{f} * {TY} + 0.05", f"{f} * {TZ}"]}})
    on = f"(v.particle_age >= {start} ? 1 : 0)"
    uv = frame_uv(frames(k, 7), 64, 64)
    sz = f"(0.7 + 1.5 * (1 - math.pow(1 - {k}, 2))) * {on}"
    return particle("beatup_wave", T_RING, comps, uv, [sz, sz], camera="emitter_transform_xz",
                    tinting={"color": ["0.3", "0.1", "0.5", f"0.8 * (1 - {k} * {k}) * {on}"]})


def p_streaks():
    """A few dark energy streaks shooting from the user towards the target as the attack begins."""
    i = "math.round(v.emitter_age * 20)"
    start = f"({THRUST - 0.02 - EMIT_LAG} + 0.03 * {i} - v.emitter_age)"
    fly = 0.24
    s = f"math.clamp((v.particle_age - {start}) / {fly}, 0, 1)"
    e = f"(1 - math.pow(1 - {s}, 1.6))"
    # a sideways bow so the streaks fan out a little: along the horizontal normal of the line to the target
    ln = f"math.max(math.sqrt({TX} * {TX} + {TZ} * {TZ}), 0.01)"
    bow = f"(v.particle_random_1 - 0.5) * 1.6 * math.sin(180 * {s})"
    lift = f"(v.particle_random_2 - 0.4) * 0.8 * math.sin(180 * {s})"
    pos = [f"{e} * {TX} + {bow} * {TZ} / {ln}", f"{e} * {TY} + {lift}", f"{e} * {TZ} - {bow} * {TX} / {ln}"]
    comps = dict(one_per_tick(4), **{
        "minecraft:emitter_shape_point": {},
        "minecraft:particle_lifetime_expression": {"max_lifetime": f"{start} + {fly}"},
        "minecraft:particle_initial_speed": 0,
        "minecraft:particle_motion_parametric": {"relative_position": pos}})
    vis = f"(v.particle_age >= {start} ? 1 : 0) * math.clamp((0.8 - {s}) / 0.25, 0, 1)"
    return particle("beatup_streaks", T_BEAM, comps, UV_BEAM, [f"1.1 * {vis}", f"0.07 * {vis}"],
                    camera="lookat_direction",
                    tinting=gradient("v.particle_random_3", [(0.0, VIOLET), (0.5, PURPLE), (1.0, DEEP)]))


# ================================================================= each strike (target animation)
TOWARD = "-(0.35 * v.entity_width + 0.12)"     # the face of the target that looks at its attacker (-z)


def p_star():
    """The comic impact star of the Sword/Shield and Scarlet/Violet animation, popping on the hit."""
    comps = dict(burst(1), **{
        "minecraft:emitter_shape_point": {"offset": [f"0.3 * (v.particle_random_1 - 0.5) * {BODY}",
                                                     f"0.3 * (v.particle_random_2 - 0.5) * {BODY}", TOWARD]},
        "minecraft:particle_lifetime_expression": {"max_lifetime": 0.26},
        "minecraft:particle_initial_speed": 0,
        "minecraft:particle_motion_dynamic": {},
        "minecraft:particle_initial_spin": {"rotation": "v.particle_random_3 * 360"}})
    uv = frame_uv(frames(f"math.pow({K}, 0.8)", 5), 32, 32, horizontal=False)
    sz = f"(0.85 + 0.25 * v.particle_random_4) * {FX}"
    return particle("beatup_star", T_STAR, comps, uv, [sz, sz], tinting={"color": [1, 1, 1, 1]})


def p_hitlines():
    """A few sharp streaks flying off the hit."""
    comps = dict(burst(4), **{
        "minecraft:emitter_shape_point": {"offset": [0, 0, TOWARD]},
        "minecraft:particle_lifetime_expression": {"max_lifetime": 0.15},
        "minecraft:particle_initial_speed": 0})
    d = sphere_dir()
    dist = f"(0.25 + 1.2 * (1 - math.pow(1 - {K}, 2))) * {FX}"
    comps["minecraft:particle_motion_parametric"] = {
        "relative_position": [f"{dist} * {d[0]}", f"{dist} * {d[1]}", f"{dist} * ({d[2]} * 0.5 - 0.5)"]}
    vis = f"(1 - {K})"
    return particle("beatup_hitlines", T_BEAM, comps, UV_BEAM, [f"0.75 * {FX} * {vis}", f"0.06 * {vis}"],
                    camera="lookat_direction", tinting=gradient("v.particle_random_3", [(0.0, CORE), (1.0, VIOLET)]))


def p_brawl():
    """The scuffle's dust: puffs kicked up round the target's feet on every hit, the dust cloud of the
    Sword/Shield and Scarlet/Violet animation, kept thin so the target stays in view."""
    comps = dict(burst(4), **{
        "minecraft:emitter_shape_disc": {"offset": [0, f"0.1 + 0.2 * v.particle_random_2 * v.entity_height", 0],
                                         "radius": "0.5 * v.entity_width + 0.15", "plane_normal": "y",
                                         "surface_only": True, "direction": "outwards"},
        "minecraft:particle_lifetime_expression": {"max_lifetime": "0.32 + 0.12 * v.particle_random_1"},
        "minecraft:particle_initial_speed": f"(1.6 + 1.2 * v.particle_random_3) * {FX}",
        "minecraft:particle_motion_dynamic": {"linear_drag_coefficient": 5, "linear_acceleration": [0, 0.5, 0]},
        "minecraft:particle_initial_spin": SPIN})
    sz = f"(0.3 + 0.12 * v.particle_random_4) * {FX} * (0.7 + 0.6 * {K})"
    return particle("beatup_brawl", T_PUFF, comps, puff_frame(K, 3, 9), [sz, sz],
                    tinting={"color": [str(c) for c in DUST] + [f"0.55 * (1 - {K} * {K})"]})


def p_twinkle():
    """Little four-point stars flying out of the brawl (Scarlet/Violet), in pale violet."""
    comps = dict(burst(2), **{
        "minecraft:emitter_shape_sphere": {"radius": f"0.45 * {BODY}", "surface_only": True, "direction": "outwards"},
        "minecraft:particle_lifetime_expression": {"max_lifetime": 0.3},
        "minecraft:particle_initial_speed": "3 + 1.5 * v.particle_random_3",
        "minecraft:particle_motion_dynamic": {"linear_drag_coefficient": 4, "linear_acceleration": [0, -4, 0]}})
    uv = frame_uv(frames(K, 11), 25, 25)
    sz = "0.3 + 0.08 * v.particle_random_4"     # pixel art: kept small so it stays crisp
    return particle("beatup_twinkle", T_SKY, comps, uv, [sz, sz], tinting={"color": [0.94, 0.8, 1, 1]})


# ================================================================= the finish (target animation)
def p_finalburst():
    """The last strike lands harder: a black burst tearing into purple scrawls (Shadow Ball's impact sheet)."""
    comps = dict(burst(1), **{
        "minecraft:emitter_shape_point": {"offset": [0, 0, TOWARD]},
        "minecraft:particle_lifetime_expression": {"max_lifetime": 0.4},
        "minecraft:particle_initial_speed": 0,
        "minecraft:particle_motion_dynamic": {}})
    uv = frame_uv(frames(K, 8), 32, 32)
    sz = f"(1.1 + 0.25 * {BODY})"
    return particle("beatup_finalburst", T_BURST, comps, uv, [sz, sz], tinting=gradient(K, [(0.0, CORE), (1.0, DEEP)]))


def p_finalring():
    """A violet shock ring around the finishing hit."""
    comps = dict(burst(1), **{
        "minecraft:emitter_shape_point": {"offset": [0, 0, TOWARD]},
        "minecraft:particle_lifetime_expression": {"max_lifetime": 0.3},
        "minecraft:particle_initial_speed": 0,
        "minecraft:particle_motion_dynamic": {}})
    uv = frame_uv(frames(K, 7), 64, 64)
    sz = f"(0.9 + 1.2 * (1 - math.pow(1 - {K}, 2))) * {FX}"
    return particle("beatup_finalring", T_RING, comps, uv, [sz, sz],
                    tinting={"color": ["0.69", "0.42", "1", f"0.9 * (1 - {K} * {K})"]})


def p_finalstar():
    """A bigger impact star for the finish."""
    p = p_star()
    pe = p["particle_effect"]
    pe["description"]["identifier"] = "cobblemon:beatup_finalstar"
    pe["components"]["minecraft:particle_lifetime_expression"] = {"max_lifetime": 0.32}
    bb = pe["components"]["minecraft:particle_appearance_billboard"]
    sz = f"(1.35 + 0.3 * v.particle_random_4) * {FX}"
    bb["size"] = [sz, sz]
    return p


def p_finalshards():
    """A small radial burst of black fragments."""
    comps = dict(burst(18), **{
        "minecraft:emitter_shape_point": {"offset": [0, 0, TOWARD]},
        "minecraft:particle_lifetime_expression": {"max_lifetime": "0.22 + 0.2 * v.particle_random_1"},
        "minecraft:particle_initial_speed": f"(9 + 5 * v.particle_random_2) * {FX}",
        "minecraft:particle_motion_dynamic": {"linear_drag_coefficient": 6},
        "minecraft:particle_initial_spin": {"rotation": "v.particle_random_3 * 360"}})
    uv = frame_uv(frames(K, 7), 8, 8, horizontal=False)
    sz = f"0.36 * (1 - {K})"
    return particle("beatup_finalshards", T_SHARD, comps, uv, [sz, sz],
                    tinting=gradient(K, [(0.0, '#FF523363'), (1.0, SHADOW)]))


def p_finallines():
    """Fast streaks off the finish."""
    p = p_hitlines()
    pe = p["particle_effect"]
    pe["description"]["identifier"] = "cobblemon:beatup_finallines"
    comps = pe["components"]
    comps["minecraft:emitter_rate_instant"] = {"num_particles": 7}
    comps["minecraft:particle_lifetime_expression"] = {"max_lifetime": 0.2}
    d = sphere_dir()
    dist = f"(0.35 + 2.0 * (1 - math.pow(1 - {K}, 2))) * {FX}"
    comps["minecraft:particle_motion_parametric"] = {
        "relative_position": [f"{dist} * {d[0]}", f"{dist} * {d[1]}", f"{dist} * ({d[2]} * 0.5 - 0.5)"]}
    vis = f"(1 - {K})"
    comps["minecraft:particle_appearance_billboard"]["size"] = [f"1.2 * {FX} * {vis}", f"0.08 * {vis}"]
    return p


def p_finalfist():
    """A dark fist flashing on the finishing blow (Black/White and Ultra Sun/Moon draw Beat Up as fists)."""
    comps = dict(burst(1), **{
        "minecraft:emitter_shape_point": {"offset": [0, 0, f"{TOWARD} - 0.05"]},
        "minecraft:particle_lifetime_expression": {"max_lifetime": 0.34},
        "minecraft:particle_initial_speed": 0,
        "minecraft:particle_motion_dynamic": {}})
    uv = frame_uv(frames(K, 9), 30, 30)
    sz = f"(1.0 + 0.2 * {BODY}) * (0.85 + 0.15 * math.min({K} * 8, 1))"
    return particle("beatup_finalfist", T_FIST, comps, uv, [sz, sz],
                    tinting={"color": ["0.85", "0.55", "1", "0.95"]})


# ================================================================= the afterimages (spawned by the Java side at a point in the world)
WORLD_DEFAULTS = ""    # no entity: these are spawned at a bare position


def p_summon():
    """Dark mist curling up where a teammate's afterimage takes shape."""
    comps = dict(burst(9, WORLD_DEFAULTS), **{
        "minecraft:emitter_shape_disc": {"offset": [0, 0.1, 0], "radius": 0.45, "plane_normal": "y", "surface_only": True,
                                         "direction": ["(v.particle_random_1 - 0.5) * 0.6", 1, "(v.particle_random_2 - 0.5) * 0.6"]},
        "minecraft:particle_lifetime_expression": {"max_lifetime": "0.35 + 0.15 * v.particle_random_3"},
        "minecraft:particle_initial_speed": "1.4 + 0.8 * v.particle_random_4",
        "minecraft:particle_motion_dynamic": {"linear_drag_coefficient": 3},
        "minecraft:particle_initial_spin": SPIN})
    sz = f"(0.24 + 0.1 * v.particle_random_3) * (0.7 + 0.5 * {K})"
    return particle("beatup_summon", T_PUFF, comps, puff_frame(K, 3, 9), [sz, sz],
                    tinting=gradient(K, [(0.0, '#996A2CA8'), (0.4, '#7A2A1B5E'), (1.0, '#001C1030')]))


def p_summonring():
    """... and a small violet ring on the ground under it."""
    comps = dict(burst(1, WORLD_DEFAULTS), **{
        "minecraft:emitter_shape_point": {"offset": [0, 0.05, 0]},
        "minecraft:particle_lifetime_expression": {"max_lifetime": 0.25},
        "minecraft:particle_initial_speed": 0,
        "minecraft:particle_motion_dynamic": {}})
    uv = frame_uv(frames(K, 7), 64, 64)
    sz = f"0.5 + 1.1 * (1 - math.pow(1 - {K}, 2))"
    return particle("beatup_summonring", T_RING, comps, uv, [sz, sz], camera="emitter_transform_xz",
                    tinting={"color": ["0.69", "0.42", "1", f"0.85 * (1 - {K} * {K})"]})


def p_trail():
    """The dark wake an afterimage leaves as it rushes in (one emitter per tick, at its body)."""
    comps = dict(burst(2, WORLD_DEFAULTS, active=0.05), **{
        "minecraft:emitter_shape_sphere": {"radius": 0.25, "surface_only": False},
        "minecraft:particle_lifetime_expression": {"max_lifetime": "0.24 + 0.08 * v.particle_random_1"},
        "minecraft:particle_initial_speed": "0.3 * v.particle_random_2",
        "minecraft:particle_motion_dynamic": {"linear_drag_coefficient": 2},
        "minecraft:particle_initial_spin": SPIN})
    sz = f"(0.3 + 0.08 * v.particle_random_3) * (1 - 0.6 * {K})"
    return particle("beatup_trail", T_PUFF, comps, puff_frame(K, 4, 9), [sz, sz],
                    tinting=gradient(K, [(0.0, '#8C3A1A6A'), (0.5, '#5A24123F'), (1.0, '#001C1030')]))


def p_dissolve():
    """The afterimage dissolves into dark wisps after its strike: many small ones, so it reads as smoke
    coming off the body rather than a handful of balls."""
    comps = dict(burst(12, WORLD_DEFAULTS), **{
        "minecraft:emitter_shape_sphere": {"radius": 0.5, "surface_only": False, "direction": "outwards"},
        "minecraft:particle_lifetime_expression": {"max_lifetime": "0.24 + 0.12 * v.particle_random_1"},
        "minecraft:particle_initial_speed": "0.7 + 0.6 * v.particle_random_2",
        "minecraft:particle_motion_dynamic": {"linear_drag_coefficient": 3, "linear_acceleration": [0, 0.9, 0]},
        "minecraft:particle_initial_spin": SPIN})
    sz = f"(0.2 + 0.1 * v.particle_random_3) * (0.8 + 0.4 * {K})"
    return particle("beatup_dissolve", T_PUFF, comps, puff_frame(K, 4, 9), [sz, sz],
                    tinting=gradient(K, [(0.0, '#8C4A1E8C'), (0.5, '#662A1B5E'), (1.0, '#001C1030')]))


def p_dissolvesparks():
    """... with a few violet motes drifting up."""
    comps = dict(burst(6, WORLD_DEFAULTS), **{
        "minecraft:emitter_shape_sphere": {"radius": 0.4, "surface_only": False, "direction": "outwards"},
        "minecraft:particle_lifetime_expression": {"max_lifetime": "0.3 + 0.15 * v.particle_random_1"},
        "minecraft:particle_initial_speed": "1.2 + 1.0 * v.particle_random_2",
        "minecraft:particle_motion_dynamic": {"linear_drag_coefficient": 3, "linear_acceleration": [0, 2.2, 0]}})
    uv = frame_uv(frames(K, 4), 8, 8, horizontal=False)
    return particle("beatup_dissolvesparks", T_SPARK, comps, uv, ["0.12", "0.12"],
                    tinting=gradient(K, [(0.0, CORE), (0.6, VIOLET), (1.0, '#006A2CA8')]))


# ================================================================= animations
ARMS = ['arm_left', 'arm_right', 'left_upper_arm', 'right_upper_arm', 'left_arm', 'right_arm']
HEAD = ['head']


def vec(v):
    return [r(c, 3) for c in v]


def keys(points):
    return {t(x): vec(v) for x, v in sorted(points, key=lambda p: p[0])}


def actor_animation(n):
    """The user rears back, gathering dark energy, snaps forward to send the first strike (its own), and
    holds a forward lean, pumping its arms as each teammate strikes."""
    fin = finish(n)
    rest = fin + 0.34
    pitch = [(0, 0), (REAR, -9), (THRUST, 13), (SETTLE, 6)]     # + leans forward
    arms = [(0, 0), (REAR, 25), (THRUST, -45), (SETTLE, -30)]   # + sweeps them back
    for k in range(1, n):
        s = strike(k)
        pitch += [(s - 0.06, 6), (s, 8.5), (s + 0.08, 6)]
        arms += [(s - 0.06, -30), (s, -40), (s + 0.08, -30)]
    pitch += [(fin + 0.06, 5), (rest, 0)]
    arms += [(fin + 0.06, -26), (rest, 0)]
    bones = {
        'root_part': {
            'rotation': keys([(x, (p, 0, 0)) for x, p in pitch]),
            'position': keys([(0, (0, 0, 0)), (REAR, (0, -0.8, 1.2)), (THRUST, (0, 0.5, -2.4)), (SETTLE, (0, 0, -1.2)),
                              (fin + 0.06, (0, 0, -1.0)), (rest, (0, 0, 0))]),
            'scale': keys([(0, (1, 1, 1)), (REAR, (1.05, 0.94, 1.05)), (THRUST, (0.96, 1.06, 0.96)), (SETTLE, (1, 1, 1)),
                           (rest, (1, 1, 1))]),
        },
    }
    arm_keys = keys([(x, (a, 0, 0)) for x, a in arms])
    for b in ARMS:
        bones[b] = {'rotation': arm_keys}
    head_keys = keys([(0, (0, 0, 0)), (REAR, (10, 0, 0)), (THRUST, (-8, 0, 0)), (SETTLE, (-4, 0, 0)), (rest, (0, 0, 0))])
    for b in HEAD:
        bones[b] = {'rotation': head_keys}
    return {
        'animation_length': r(rest + 0.04),
        'bones': bones,
        'particle_effects': {
            t(0.0): [{'effect': 'cobblemon:beatup_gather', 'locator': 'middle'},
                     {'effect': 'cobblemon:beatup_aura', 'locator': 'middle'}],
            t(THRUST - 0.03): [{'effect': 'cobblemon:beatup_burst', 'locator': 'middle'},
                               {'effect': 'cobblemon:beatup_burstsparks', 'locator': 'middle'},
                               {'effect': 'cobblemon:beatup_ripple', 'locator': 'root'}],
        },
        'sound_effects': {t(0.0): {'effect': 'move.beatup.summon'}},
    }


# the strikes come in from alternating sides (see Afterimage.APPROACH); the target rolls away from each
ROLL = [0, 3, -3, 2, -4, 4]
STRIKE_FX = ['beatup_star', 'impact_dark', 'beatup_hitlines', 'beatup_brawl', 'beatup_twinkle']
FINAL_FX = ['beatup_finalfist', 'beatup_finalburst', 'beatup_finalring', 'beatup_finalstar', 'beatup_finalshards',
            'beatup_finallines', 'beatup_brawl']
HIT_SOUNDS = ['move.beatup.hit', 'move.beatup.hit_high']


def target_animation(n):
    """A small flinch on every strike and a slightly bigger one on the finish, each recovering before the
    next, with the hit effects and sounds; so it can't drift from the strikes, it all runs on the client."""
    fin = finish(n)
    pos, rot, scl = [(0, (0, 0, 0))], [(0, (0, 0, 0))], [(0, (1, 1, 1))]
    fx, sounds = {}, {}
    for k in range(n):
        s = strike(k)
        pos += [(s, (0, 0, 0)), (s + 0.03, (0.5 * math.copysign(1, ROLL[k]) if ROLL[k] else 0, -0.3, 1.6))]
        rot += [(s, (0, 0, 0)), (s + 0.03, (-7, 0, ROLL[k]))]
        scl += [(s, (1, 1, 1)), (s + 0.03, (1.05, 0.94, 1.05))]
        if k < n - 1:
            # back to rest before the next strike; the last one runs straight into the finish
            pos.append((s + 0.13, (0, 0, 0.3)))
            rot.append((s + 0.13, (-1, 0, 0)))
            scl.append((s + 0.11, (1, 1, 1)))
        fx[t(s - FX_LEAD)] = [{'effect': f'cobblemon:{e}', 'locator': 'root' if e == 'beatup_brawl' else
                               'middle' if e == 'beatup_twinkle' else 'target'} for e in STRIKE_FX]
        sounds[t(s)] = [{'effect': 'impact.dark'}, {'effect': HIT_SOUNDS[k % 2]}]
    pos += [(fin, (0, -0.15, 1.0)), (fin + 0.04, (0, -0.4, 2.6)), (fin + 0.2, (0, 0, 1.2)), (fin + 0.4, (0, 0, 0))]
    rot += [(fin, (-4, 0, 0)), (fin + 0.04, (-10, 0, 0)), (fin + 0.2, (-4, 0, 0)), (fin + 0.4, (0, 0, 0))]
    scl += [(fin, (1.02, 0.97, 1.02)), (fin + 0.04, (1.07, 0.92, 1.07)), (fin + 0.16, (1, 1, 1))]
    fx[t(fin - FX_LEAD)] = [{'effect': f'cobblemon:{e}', 'locator': 'root' if e == 'beatup_brawl' else 'target'}
                            for e in FINAL_FX]
    sounds[t(fin)] = [{'effect': 'move.beatup.final'}, {'effect': 'impact.dark'}]
    return {
        'animation_length': r(fin + 0.45),
        'bones': {'root_part': {'position': keys(pos), 'rotation': keys(rot), 'scale': keys(scl)}},
        'particle_effects': fx,
        'sound_effects': sounds,
    }


def miss_target_animation():
    """A miss: the target sidesteps the user's strike."""
    s = strike(0)
    return {
        'animation_length': r(s + 0.4),
        'bones': {'root_part': {'position': keys([(0, (0, 0, 0)), (s - 0.1, (0, 0, 0)), (s, (-4, 0, 0.5)),
                                                  (s + 0.3, (0, 0, 0))]),
                                'rotation': keys([(0, (0, 0, 0)), (s - 0.1, (0, 0, 0)), (s, (0, 0, -6)), (s + 0.3, (0, 0, 0))])}},
    }


def build_animation_file():
    anims = {}
    for n in range(1, MAX_HITS + 1):
        anims[f'animation.beatup.actor{n}'] = actor_animation(n)
    for n in range(1, MAX_HITS + 1):
        anims[f'animation.beatup.target{n}'] = target_animation(n)
    anims['animation.beatup.target_miss'] = miss_target_animation()
    return {'format_version': '1.8.0', 'animations': anims}


# ================================================================= action effect
def play(anim):
    return f"q.play_animation(q.bedrock_stateful('beatup', '{anim}', 'endures_primary_animations'))"


def hits(n):
    """MoLang condition for exactly n hits; the last variant also takes anything above it."""
    if n == 1:
        return "q.hit_count <= 1"
    return f"q.hit_count >= {n}" if n == MAX_HITS else f"q.hit_count == {n}"


HIT = "q.hit_count >= 1"
USER = "q.entity.is_user == true"
TARGET = "q.entity.is_user == false"


def build_effect_file():
    # Every entity_* / animation / molang keyframe costs one server tick in 1.7.3, so the whole start is one
    # `parallel` (a single tick): the animations, the afterimage hook and the user-to-target effects all
    # reach the client together and run on its clock from there.
    start = [
        # Cobblemon's per-species hook: a poser that defines a "beatup" animation gets it on top. No
        # official poser does, and an unknown name plays nothing.
        {'type': 'animation', 'animation': ['beatup']},
    ]
    for n in range(1, MAX_HITS + 1):
        start.append({'type': 'entity_molang', 'condition': hits(n), 'entityCondition': USER, 'expressions': [play(f'actor{n}')]})
    for n in range(1, MAX_HITS + 1):
        start.append({'type': 'entity_molang', 'condition': f"{hits(n)} && {HIT}", 'entityCondition': TARGET,
                      'expressions': [play(f'target{n}')]})
    start += [
        {'type': 'entity_molang', 'condition': "q.hit_count < 1", 'entityCondition': f"{TARGET} && q.missed(q.entity.uuid) == true",
         'expressions': [play('target_miss')]},
        {'type': 'entity_particles', 'effect': 'cobblemon:beatup_wave', 'locators': ['root'], 'targetLocators': ['root']},
        {'type': 'entity_particles', 'effect': 'cobblemon:beatup_streaks', 'locators': ['middle'], 'targetLocators': ['target']},
        # the Java side: an afterimage of the party member behind each strike (returns 0 and does nothing
        # if the hook isn't there)
        {'type': 'molang', 'expressions': f"q.user.beat_up_afterimages(q.hit_count, q.target, {S0}, {DT})"},
    ]
    strikes = f"math.clamp(q.hit_count, 1, {MAX_HITS})"
    return {'timeline': [
        {'type': 'add_holds', 'holds': ['effects']},
        {'type': 'parallel', 'keyframes': start},
        # the parallel already took a tick; let the battle go on (HP bar, "Hit N times!") at the finish
        {'type': 'pause', 'pause': f"{S0 + FINAL_GAP - 0.05} + {DT} * ({strikes} - 1)"},
        {'type': 'remove_holds', 'holds': ['effects']},
        {'type': 'pause', 'pause': TAIL},
    ]}


def all_particles():
    return [p_gather(), p_aura(), p_burst(), p_burstsparks(), p_ripple(), p_wave(), p_streaks(), p_star(),
            p_hitlines(), p_brawl(), p_twinkle(), p_finalburst(), p_finalring(), p_finalstar(), p_finalshards(),
            p_finallines(), p_finalfist(), p_summon(), p_summonring(), p_trail(), p_dissolve(), p_dissolvesparks()]


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
