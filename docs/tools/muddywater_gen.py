"""Generates Muddy Water's particle effects, generic animation file, action effect, wave style and sounds.

Outputs (paths relative to the repo root):
  src/main/resources/assets/cobblemon/bedrock/particles/moves/muddywater/*.particle.json
  src/main/resources/assets/cobblemon/bedrock/generic/animations/moves/muddywater.animation.json
  src/main/resources/data/cobblemon/action_effects/moves/muddywater.json
  src/main/resources/assets/cobblemon_extra_move_animation/wave_effects/muddywater.json  (the wave mesh, drawn by Java)
  src/main/resources/assets/cobblemon/sounds.json  (only its move.muddywater.* entries)

Edit the constants below and re-run `python3 docs/tools/muddywater_gen.py`; don't hand-edit the outputs.
The wave's texture comes from docs/tools/muddywater_textures.py. Design notes: docs/muddywater_assets.md.

How the pieces fit (Scarlet/Violet's look: muddy water gathers round the user as a crown, which bursts
into a wide wave that floods across the field over the foes):
- One `parallel` keyframe starts everything in the same server tick; from then on the user's animation,
  the targets' animations and the wave all run on the client's clock, so they stay in step.
- The wave itself is a mesh drawn by Java (client/wave/WaveSequence): a crown of water round the user,
  a curling wave as wide as the foes' line that rolls over to them, the crash and the flood draining
  away. The action effect starts it with `q.user.wave_effect('muddywater', q.target, q.targets)`;
  WAVE_* below are its numbers, written to the wave style file, and the spray riding the crest uses the
  same formulas so it stays on the crest.
- The user's animation fires the gathering particles (muddy droplets swirling in, mud bubbles, sediment)
  and the burst at the release. Every target plays `splash` (the wave crashing round it, hit or miss),
  plus `target` if it was hurt or `dodge` if it was missed.
- `murk` (the accuracy drop) plays ONLY on a target whose accuracy the battle really lowered: the Java
  hook `q.entity.move_stat_change('accuracy')` reads the battle's own log, and each target is checked on
  its own. Without the hook it reads 0, so the haze never shows by mistake.
- Damage and the accuracy drop are the battle's; nothing here changes them.
"""
import json, math, os, sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..')
RES = os.path.join(ROOT, 'src/main/resources')
PART_DIR = os.path.join(RES, 'assets/cobblemon/bedrock/particles/moves/muddywater')
ANIM_OUT = os.path.join(RES, 'assets/cobblemon/bedrock/generic/animations/moves/muddywater.animation.json')
EFFECT_OUT = os.path.join(RES, 'data/cobblemon/action_effects/moves/muddywater.json')
STYLE_OUT = os.path.join(RES, 'assets/cobblemon_extra_move_animation/wave_effects/muddywater.json')
SOUNDS = os.path.join(RES, 'assets/cobblemon/sounds.json')

# ---------------------------------------------------------------- timing (seconds from the start of the move)
T0 = 0.02            # the user's particles fire here
PARTICLE_LAG = 0.175 # path-locked particles fired by an animation: their age 0 shows at T0 + this
T_IN = T0 + PARTICLE_LAG
EMIT_LAG = 0.075     # an action-effect emitter's first particles are born about this late
FX_LEAD = 0.075      # the targets' animations fire their burst particles this early so they show on time
# 1. gathering
GATHER0 = 0.2        # muddy droplets start swirling in (nothing animation-fired shows before ~0.2 s)
CROWN_RISE = 0.18    # the crown of water starts rising round the user (mesh)
CROWN_PEAK = 0.52    # ... at full height
# 2. release
RELEASE = 0.60       # the user thrusts forward, the crown bursts into the wave
IMPACT = 1.05        # 3. the wave crashes onto the targets
TRAVEL = IMPACT - RELEASE
CRASH_END = 1.35     # the crash has flattened into a flood
DRAIN_END = 1.95     # 5. the flood has drained away
MURK0 = IMPACT + 0.22     # 4. the murky haze (accuracy fell) starts gathering round the target
MURK_LEN = 1.45           # ... and has cleared after this long
ACTOR_LEN = 1.5
TARGET_LEN = IMPACT + 0.85
TAIL = 0.9           # the timeline runs on this long after the hit (the haze and the flood show)

# ---------------------------------------------------------------- the wave mesh (written to the wave style)
TEXTURE = 'cobblemon_extra_move_animation:textures/effect/muddy_water.png'
TEXTURE_BLOCKS = 2.0         # one repeat of the texture covers this many blocks (16 px per block)
FLOW_SPEED = 0.9             # texture repeats per second the water runs over the crest and down the face
CROWN_HEIGHT = {'scale': 1.1, 'add': 0.35, 'min': 1.0, 'max': 3.2}   # x the user's height, plus add, clamped
CROWN_GAP = 0.3              # between the user's body and the crown
CROWN_FLARE = 0.35           # the crown opens out like a bowl, this much per block of height
CROWN_SWIRL = 200            # degrees per second
CROWN_JAG = 0.22             # how ragged its rim is
CROWN_COLLAPSE = 0.16        # seconds it takes to burst once the wave is released
POOL_RADIUS = 1.1            # how far the muddy pool spreads past the user's body
WAVE_HEIGHT = {'scale': 0.75, 'add': 0.8, 'min': 1.5, 'max': 3.0}
START_GAP = 0.35             # where the wave forms, in front of the user's body
SIDE_PADDING = 1.3           # past the outermost target, on each side
MIN_HALF_WIDTH = 2.2
LIP = 0.5                    # how far the curling lip reaches forward (x the wave's height)
BOW = 0.2                    # how far the wave's ends trail its middle (x height)
END_TAPER = 6.0              # higher = the wave keeps its full height further out to its ends
LIGHTING_UP_BIAS = 0.6       # tips the mesh's normals up so steep water isn't shaded too dark
OVERSHOOT = 0.9              # how far the water surges past the targets after the crash (x height)
CREST_NOISE = 0.08
FOAM_BACK = 0.6             # foam starts this far up the wave's back (0 foot .. 1 crest)
FOAM_FACE = 0.45            # ... and reaches this far down its face (the lip's outside is the first ~45%)
MOTTLE = 0.35               # lighter/darker swirls drifting through the water

# ---------------------------------------------------------------- palette (#AARRGGBB; the mesh uses #RRGGBB)
DEEP = '#FF3E2914'       # thick muddy water
BODY = '#FF6B4A28'
LIGHT = '#FFA47C4A'      # thin water, light swirls
TAN = '#FFC9A878'        # splashes and spray
FOAM = '#FFE3D2AE'       # foam on the crest and the crown's rim
CREAM = '#FFF2E8D2'
SPECK = '#FF2E1E10'      # sediment
MURK = '#FF6A5038'       # the murky haze
MURK_PALE = '#FF9C8466'
MESH_COLOR = {'deep': '#5C3F20', 'body': '#8E6538', 'light': '#C49A62', 'foam': '#F2E6CC'}   # the wave mesh (#RRGGBB)


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


def tex(path, w, h):
    return f"textures/particles/{path}", w, h


T_ORB = tex('generic/orb/mediumfadeorb', 99, 9)          # 11 frames 9x9; frame 5 is a solid round orb (white)
T_PUFF = tex('generic/fire/cloudyfire_white', 160, 16)   # 10 frames 16x16: a puff that swells and breaks up
T_HAZE = tex('generic/smoke/obscuringsmoke', 16, 80)     # 5 frames 16x16, top to bottom: wispy streaks
T_RIPPLE = tex('generic/water/ripple_white', 16, 144)    # 9 frames 16x16, top to bottom: a ring spreading out
T_MUD = tex('generic/mud/mudbubble', 80, 8)              # 10 frames 8x8: a mud blob swelling then shrinking (brown)
T_SPLAT = tex('generic/mud/mudsplash', 8, 56)            # 7 frames 8x8, top to bottom: a mud chunk bursting (brown)
T_CLOD = tex('generic/impact/impact_ground', 8, 56)      # 7 frames 8x8, top to bottom: dirt clods (brown)

UV_DROP = {"uv": [45, 0], "uv_size": [9, 9]}


def frame_uv(index, fw, fh, horizontal=True):
    """Static UV of frame `index` (a MoLang expression) of a sheet laid out left-to-right or top-to-bottom."""
    return {"uv": [f"{fw} * ({index})", 0] if horizontal else [0, f"{fh} * ({index})"], "uv_size": [fw, fh]}


def frames(k, count):
    """Frame index for a 0..1 progress over `count` frames."""
    return f"math.floor(math.clamp({k}, 0, 0.999) * {count})"


def puff_frame(k, first=1, last=8):
    """cloudyfire frame for a 0..1 progress: the puff swells (low frames) and breaks up (high frames)."""
    return frame_uv(f"{first} + {frames(k, last - first + 1)}", 16, 16)


def flipbook(fw, fh, count, horizontal=True):
    return {"flipbook": {"base_UV": [0, 0], "size_UV": [fw, fh], "step_UV": [fw, 0] if horizontal else [0, fh],
                         "frames_per_second": 20, "max_frame": count, "stretch_to_lifetime": True}}


def rgb(hexcol):
    v = int(hexcol[-6:], 16)
    return ((v >> 16 & 255) / 255, (v >> 8 & 255) / 255, (v & 255) / 255)


def ramp(k, stops, alpha):
    """Tint array [r, g, b, a] blending through `stops` [(0..1, '#AARRGGBB')] by the MoLang progress k."""
    chans = []
    for ch in range(3):
        expr = f"{r(rgb(stops[0][1])[ch], 3)}"
        for (a, ca), (b, cb) in zip(stops, stops[1:]):
            d = rgb(cb)[ch] - rgb(ca)[ch]
            if abs(d) > 1e-4:
                expr += f" + {r(d, 3)} * math.clamp(({k} - {r(a, 3)}) / {r(b - a, 3)}, 0, 1)"
        chans.append(expr)
    return {"color": chans + [alpha]}


def particle(pid, texture, components, uv, size, camera="rotate_xyz", tinting=None, curves=None):
    path, tw, th = texture
    bb = {"size": size, "facing_camera_mode": camera, "uv": dict({"texture_width": tw, "texture_height": th}, **uv)}
    comps = dict(components)
    comps["minecraft:particle_appearance_billboard"] = bb
    if tinting is not None:
        comps["minecraft:particle_appearance_tinting"] = tinting
    # one material for the whole move: Cobblemon draws all particles with the last one's blending
    pe = {"description": {"identifier": f"cobblemon:{pid}",
                          "basic_render_parameters": {"material": "particles_blend", "texture": path}}}
    if curves:
        pe["curves"] = curves
    pe["components"] = comps
    return {"format_version": "1.10.0", "particle_effect": pe}


def window(since, life, fade_in=0.03):
    """1 while 0 <= since < life (soft edges), else 0."""
    return f"math.clamp(({since}) / {fade_in}, 0, 1) * math.clamp(({life} - ({since})) * 30, 0, 1)"


K = "(v.particle_age / v.particle_lifetime)"
ENTITY_DEFAULTS = "v.entity_width = 1; v.entity_height = 1;"
SPIN_ICON = {"rotation": "math.floor(v.particle_random_4 * 4) * 90"}


# ================================================================= 1. gathering (user animation, root locator)
# Fired at T0 while root_part is still at rest: the frame's -z faces the targets. Path-locked: every
# particle is spawned at once and shown only in its own time window (sizes go to 0 outside it).
USER_SIZES = [
    "v.bl = math.clamp(math.max(v.entity_width, v.entity_height), 0.5, 3.0)",   # body size (blocks)
    "v.fs = math.clamp(0.45 + 0.5 * v.bl, 0.7, 1.9)",    # effect scale: grows slowly with the body
    f"v.rw = 0.5 * v.entity_width + {CROWN_GAP}",        # the crown's inner radius (the mesh's too)
    f"v.ch = math.clamp({CROWN_HEIGHT['scale']} * v.entity_height + {CROWN_HEIGHT['add']}, {CROWN_HEIGHT['min']}, {CROWN_HEIGHT['max']})",
    f"v.tt = v.particle_age + {r(T_IN)}",                # move time this particle is showing
]


def locked(count, end_time, pos, update=()):
    return {
        "minecraft:emitter_initialization": {"creation_expression": ENTITY_DEFAULTS},
        "minecraft:emitter_rate_instant": {"num_particles": count},
        "minecraft:emitter_lifetime_once": {"active_time": 0.1},
        "minecraft:emitter_shape_point": {},
        "minecraft:particle_initialization": {"per_update_expression": ";".join(USER_SIZES + list(update)) + ";"},
        "minecraft:particle_lifetime_expression": {"max_lifetime": r(end_time - T_IN)},
        "minecraft:particle_initial_speed": 0,
        "minecraft:particle_motion_parametric": {"relative_position": pos},
    }


def p_gather():
    """Droplets of brown water swirling in from all round and climbing the crown as it rises."""
    update = [f"v.tb = {GATHER0} + {r(CROWN_PEAK - GATHER0 - 0.04)} * v.particle_random_1",
              "v.lf = 0.3 + 0.12 * v.particle_random_4",
              "v.k = math.clamp((v.tt - v.tb) / v.lf, 0, 1)",
              "v.an = 360 * v.particle_random_2 + 170 * v.k",
              "v.rd = v.rw + 0.05 + (1.25 + 0.55 * v.particle_random_3) * math.pow(1 - v.k, 1.3)",
              "v.hy = v.ch * (0.06 + (0.3 + 0.55 * v.particle_random_3) * math.pow(v.k, 1.4))"]
    pos = ["v.rd * math.cos(v.an)", "v.hy", "v.rd * math.sin(v.an)"]
    vis = window("v.tt - v.tb", "v.lf")
    sz = f"(0.055 + 0.05 * v.particle_random_4) * v.fs * {vis}"
    comps = locked(60, CROWN_PEAK + 0.1, pos, update)
    return particle("muddywater_gather", T_ORB, comps, UV_DROP, [sz, sz],
                    tinting=ramp("v.k", [(0.0, TAN), (0.6, LIGHT), (1.0, BODY)], "0.95"))


def p_gathermud():
    """Clots of mud dragged along the ground into the swirl."""
    update = [f"v.tb = {GATHER0} + 0.3 * v.particle_random_1",
              "v.lf = 0.34 + 0.1 * v.particle_random_4",
              "v.k = math.clamp((v.tt - v.tb) / v.lf, 0, 1)",
              "v.an = 360 * v.particle_random_2 + 130 * v.k",
              "v.rd = v.rw + 0.1 + (1.1 + 0.5 * v.particle_random_3) * (1 - v.k)",
              "v.hy = 0.05 + 0.25 * v.ch * v.k * v.k"]
    pos = ["v.rd * math.cos(v.an)", "v.hy", "v.rd * math.sin(v.an)"]
    vis = window("v.tt - v.tb", "v.lf")
    sz = f"(0.1 + 0.06 * v.particle_random_3) * v.fs * {vis}"
    comps = locked(18, CROWN_PEAK + 0.1, pos, update)
    comps["minecraft:particle_initial_spin"] = SPIN_ICON
    return particle("muddywater_gathermud", T_MUD, comps, frame_uv("3 + math.floor(v.particle_random_3 * 4)", 8, 8),
                    [sz, sz], tinting={"color": [1, 1, 1, 1]})


def p_bubbles():
    """Mud bubbles swelling and popping in the pool round the user's feet."""
    update = ["v.tb = 0.24 + 0.34 * v.particle_random_3",
              "v.lf = 0.26 + 0.08 * v.particle_random_4",
              "v.k = math.clamp((v.tt - v.tb) / v.lf, 0, 1)",
              "v.rd = (v.rw + 0.8) * math.sqrt(0.15 + 0.85 * v.particle_random_1)"]
    pos = ["v.rd * math.cos(360 * v.particle_random_2)", "0.05 + 0.06 * v.k", "v.rd * math.sin(360 * v.particle_random_2)"]
    vis = window("v.tt - v.tb", "v.lf")
    sz = f"(0.12 + 0.08 * v.particle_random_4) * v.fs * {vis}"
    comps = locked(16, RELEASE + 0.05, pos, update)
    # swells through the blob's growing frames, then pops (its last frame is a small splat)
    return particle("muddywater_bubbles", T_MUD, comps, frame_uv(f"math.min({frames('v.k', 6)}, 5)", 8, 8), [sz, sz],
                    tinting={"color": [1, 1, 1, 1]})


def p_sediment():
    """Specks of dirt whirling round inside the crown."""
    update = ["v.rise = math.clamp((v.tt - 0.24) / 0.3, 0, 1)",
              f"v.on = math.clamp((v.tt - 0.24) * 20, 0, 1) * math.clamp(({RELEASE + 0.1} - v.tt) * 20, 0, 1)",
              "v.an = 360 * v.particle_random_3 + 280 * v.tt",
              "v.rd = v.rw + 0.08 + 0.3 * v.particle_random_1"]
    pos = ["v.rd * math.cos(v.an)", "v.ch * v.rise * (0.08 + 0.8 * v.particle_random_2)", "v.rd * math.sin(v.an)"]
    sz = "(0.035 + 0.03 * v.particle_random_4) * v.fs * v.on"
    comps = locked(36, RELEASE + 0.12, pos, update)
    return particle("muddywater_sediment", T_ORB, comps, UV_DROP, [sz, sz],
                    tinting=ramp("v.particle_random_4", [(0.0, SPECK), (0.7, DEEP), (1.0, LIGHT)], "1"))


def p_burst():
    """The crown bursting forwards as the wave is released: brown water flung out and up."""
    update = [f"v.sn = v.tt - {RELEASE} - 0.04 * v.particle_random_4",
              "v.lf = 0.42 + 0.15 * v.particle_random_4",
              "v.s = math.max(v.sn, 0)",
              "v.an = -90 + (v.particle_random_1 - 0.5) * 230",
              "v.out = 2.0 + 2.2 * v.particle_random_3",
              "v.y0 = v.ch * (0.25 + 0.65 * v.particle_random_2)"]
    pos = ["(v.rw + 0.15 + v.out * v.s) * math.cos(v.an)",
           "v.y0 + (1.4 + 2.2 * v.particle_random_3) * v.s - 6 * v.s * v.s",
           "(v.rw + 0.15 + v.out * v.s) * math.sin(v.an) - (2.4 + 1.6 * v.particle_random_4) * v.s"]
    vis = f"{window('v.sn', 'v.lf', 0.02)} * math.clamp((v.y0 + (1.4 + 2.2 * v.particle_random_3) * v.s - 6 * v.s * v.s) * 8, 0, 1)"
    sz = f"(0.045 + 0.045 * v.particle_random_3) * v.fs * {vis}"
    comps = locked(56, RELEASE + 0.65, pos, update)
    return particle("muddywater_burst", T_ORB, comps, UV_DROP, [sz, sz],
                    tinting=ramp("v.particle_random_2", [(0.0, BODY), (0.5, LIGHT), (1.0, TAN)], "0.95"))


def p_burstfoam():
    """Foam boiling up round the user's feet as the crown bursts, hiding the hand-over to the wave."""
    update = [f"v.sn = v.tt - {RELEASE - 0.02} - 0.06 * v.particle_random_4",
              "v.lf = 0.42 + 0.12 * v.particle_random_4",
              "v.k = math.clamp(v.sn / v.lf, 0, 1)",
              "v.an = -90 + (v.particle_random_1 - 0.5) * 300",
              "v.rd = v.rw + 0.2 + 0.7 * v.k"]
    pos = ["v.rd * math.cos(v.an)", "v.ch * (0.1 + 0.35 * v.particle_random_2) + 0.3 * v.k", "v.rd * math.sin(v.an)"]
    vis = window("v.sn", "v.lf")
    sz = f"(0.3 + 0.15 * v.particle_random_3) * v.fs * (0.55 + 0.6 * math.sin(180 * math.min(v.k * 1.4, 1))) * {vis}"
    comps = locked(14, RELEASE + 0.65, pos, update)
    comps["minecraft:particle_initial_spin"] = SPIN_ICON
    return particle("muddywater_burstfoam", T_PUFF, comps, puff_frame("v.k", 2, 9), [sz, sz],
                    tinting=ramp("v.k", [(0.0, CREAM), (0.5, FOAM), (1.0, TAN)], "0.85 * (1 - v.k * v.k)"))


# ================================================================= 2. the crest (action effect, user root -> each target)
# Spawned by the action effect with targetLocators ['root']: one emitter per target, so with two foes
# each gets its own lane of spray. In the parametric frame the target's feet are at (-dx, dy, -dz).
# A particle of age a stands for move time a + EMIT_LAG. The crest follows the same path as the mesh.
WAVE_DEFAULTS = ENTITY_DEFAULTS + " v.target_deltax = 0; v.target_deltay = 0; v.target_deltaz = 4;"
LANE = [
    f"v.te = v.particle_age + {EMIT_LAG}",
    "v.hd = math.max(math.sqrt(v.target_deltax * v.target_deltax + v.target_deltaz * v.target_deltaz), 0.01)",
    "v.fx = -v.target_deltax / v.hd",
    "v.fz = -v.target_deltaz / v.hd",
    f"v.big = math.clamp({WAVE_HEIGHT['scale']} * v.entity_height + {WAVE_HEIGHT['add']}, {WAVE_HEIGHT['min']}, {WAVE_HEIGHT['max']})",
    f"v.x0 = 0.5 * v.entity_width + {START_GAP}",
    f"v.x1 = math.max(v.x0 + 0.3, math.max(v.hd, 1.5) - {LIP} * v.big)",
    "v.ln = 1.1 + 0.25 * v.entity_width",     # half width of this target's lane
]


def crest(prefix, tvar):
    """Per-update lines: the crest's distance v.<prefix>x and height v.<prefix>h at time tvar (mesh formulas)."""
    p = f"v.{prefix}p"
    s = f"v.{prefix}s"
    return [f"{p} = math.clamp(({tvar} - {RELEASE}) / {r(TRAVEL)}, 0, 1)",
            f"v.{prefix}x = v.x0 + (v.x1 - v.x0) * (0.65 * {p} + 0.35 * {p} * {p} * (3 - 2 * {p}))",
            f"{s} = math.min({p} / 0.55, 1)",
            f"v.{prefix}h = v.big * (0.55 + 0.45 * {s} * {s} * (3 - 2 * {s}))"]


def lane_pos(along, lateral, up):
    """A point `along` the line to the target, `lateral` across it, `up` above the ground under it."""
    ground = f"v.target_deltay * math.clamp(({along}) / v.hd, 0, 1)"
    return [f"v.fx * ({along}) - v.fz * ({lateral})", f"{ground} + {up}", f"v.fz * ({along}) + v.fx * ({lateral})"]


def lane_emitter(count, end_time, pos, update):
    return {
        "minecraft:emitter_initialization": {"creation_expression": WAVE_DEFAULTS},
        "minecraft:emitter_rate_instant": {"num_particles": count},
        "minecraft:emitter_lifetime_once": {"active_time": 0.1},
        "minecraft:emitter_shape_point": {},
        "minecraft:particle_initialization": {"per_update_expression": ";".join(LANE + list(update)) + ";"},
        "minecraft:particle_lifetime_expression": {"max_lifetime": r(end_time - EMIT_LAG)},
        "minecraft:particle_initial_speed": 0,
        "minecraft:particle_motion_parametric": {"relative_position": pos},
    }


def p_crestspray():
    """Spray thrown up and ahead off the crest all the way across, falling back under gravity."""
    update = [f"v.tb = {RELEASE} + {r(TRAVEL)} * (0.06 + 0.94 * v.particle_random_1)"] + crest('b', 'v.tb') + [
        "v.sn = v.te - v.tb", "v.s = math.max(v.sn, 0)", "v.lf = 0.24 + 0.16 * v.particle_random_4",
        "v.al = v.bx + 0.25 * v.bh + (2.0 + 1.8 * v.particle_random_4) * v.s",
        "v.lt = (v.particle_random_2 - 0.5) * 2 * v.ln * (1 + 0.4 * v.s)",
        "v.up = v.bh * (0.8 + 0.2 * v.particle_random_3) + (0.8 + 1.6 * v.particle_random_3) * v.s - 7 * v.s * v.s"]
    pos = lane_pos("v.al", "v.lt", "v.up")
    vis = f"{window('v.sn', 'v.lf', 0.02)} * math.clamp(v.up * 6, 0, 1)"
    sz = f"(0.045 + 0.045 * v.particle_random_3) * {vis}"
    comps = lane_emitter(84, IMPACT + 0.5, pos, update)
    return particle("muddywater_crestspray", T_ORB, comps, UV_DROP, [sz, sz],
                    tinting=ramp("v.particle_random_3", [(0.0, LIGHT), (0.6, TAN), (1.0, FOAM)], "0.95"))


def p_crestfoam():
    """Foam churning on the crest, riding along with it."""
    update = [f"v.tb = {RELEASE} + {r(TRAVEL)} * (0.03 + 0.97 * v.particle_random_1)"] + crest('c', 'v.te') + [
        "v.sn = v.te - v.tb", "v.lf = 0.18 + 0.1 * v.particle_random_4", "v.k = math.clamp(v.sn / v.lf, 0, 1)",
        "v.lt = (v.particle_random_2 - 0.5) * 2 * v.ln"]
    pos = lane_pos("v.cx + (0.15 + 0.15 * v.particle_random_3) * v.ch", "v.lt",
                   "v.ch * (0.9 + 0.12 * v.particle_random_3) + 0.3 * v.k")
    vis = f"{window('v.sn', 'v.lf')} * math.clamp(({IMPACT + 0.06} - v.te) * 20, 0, 1)"
    sz = f"(0.22 + 0.12 * v.particle_random_4) * (0.6 + 0.2 * v.ch) * (0.6 + 0.5 * math.sin(180 * math.min(v.k * 1.3, 1))) * {vis}"
    comps = lane_emitter(34, IMPACT + 0.2, pos, update)
    comps["minecraft:particle_initial_spin"] = SPIN_ICON
    return particle("muddywater_crestfoam", T_PUFF, comps, puff_frame("v.k", 2, 9), [sz, sz],
                    tinting=ramp("v.k", [(0.0, CREAM), (0.6, FOAM), (1.0, TAN)], "0.9 * (1 - v.k * v.k)"))


def p_crestclods():
    """Clods of mud tumbling along inside the wave's face."""
    update = [f"v.tb = {RELEASE} + {r(TRAVEL)} * (0.05 + 0.7 * v.particle_random_1)"] + crest('c', 'v.te') + [
        "v.sn = v.te - v.tb", "v.lt = (v.particle_random_4 - 0.5) * 2 * v.ln"]
    pos = lane_pos("v.cx + (0.12 + 0.25 * v.particle_random_3) * v.ch", "v.lt",
                   "v.ch * (0.2 + 0.55 * v.particle_random_2) + 0.12 * math.sin(720 * v.sn + 360 * v.particle_random_4)")
    vis = f"{window('v.sn', '0.42')} * math.clamp(({IMPACT} - v.te) * 20, 0, 1)"
    sz = f"(0.1 + 0.06 * v.particle_random_3) * {vis}"
    comps = lane_emitter(16, IMPACT + 0.1, pos, update)
    comps["minecraft:particle_initial_spin"] = {"rotation": "360 * v.particle_random_2", "rotation_rate": 540}
    return particle("muddywater_crestclods", T_CLOD, comps, frame_uv("1 + math.floor(v.particle_random_3 * 4)", 8, 8, horizontal=False),
                    [sz, sz], tinting={"color": [0.85, 0.8, 0.75, 1]})


# ================================================================= 3. the crash (splash animation, every target's root)
# Fired by the targets' `splash` animation FX_LEAD before IMPACT. In the target's frame -z faces the
# user, so the water comes from -z and throws everything towards +z.
TARGET_SIZES = [
    "v.bl = math.clamp(math.max(v.entity_width, v.entity_height), 0.5, 3.0)",
    "v.fx = math.clamp(0.55 + 0.4 * v.bl, 0.7, 1.8)",       # impact scale
    "v.rw = 0.5 * v.entity_width + 0.15",
]


def burst(count, update=(), active=0.1):
    return {"minecraft:emitter_initialization": {"creation_expression": ENTITY_DEFAULTS},
            "minecraft:emitter_rate_instant": {"num_particles": count},
            "minecraft:emitter_lifetime_once": {"active_time": active},
            "minecraft:emitter_shape_point": {},
            "minecraft:particle_initialization": {"per_update_expression": ";".join(TARGET_SIZES + list(update)) + ";"}}


def p_splash():
    """The explosive splash: a crown of muddy water thrown high round the target, falling back."""
    update = ["v.an = 360 * v.particle_random_1", "v.rd = v.rw * (0.4 + 0.6 * v.particle_random_2)",
              "v.vo = 1.0 + 1.8 * v.particle_random_3", "v.vu = (4.2 + 2.8 * v.particle_random_4) * math.sqrt(v.fx)",
              "v.a = v.particle_age",
              "v.y = 0.1 + v.vu * v.a - 7.5 * v.a * v.a"]
    pos = ["(v.rd + v.vo * v.a) * math.cos(v.an)", "v.y", "(v.rd + v.vo * v.a) * math.sin(v.an) + 1.3 * v.a"]
    comps = dict(burst(96, update), **{
        "minecraft:particle_lifetime_expression": {"max_lifetime": "0.6 + 0.22 * v.particle_random_2"},
        "minecraft:particle_initial_speed": 0,
        "minecraft:particle_motion_parametric": {"relative_position": pos}})
    sz = f"(0.055 + 0.055 * v.particle_random_3) * v.fx * (1 - 0.35 * {K}) * math.clamp(v.y * 6, 0, 1)"
    return particle("muddywater_splash", T_ORB, comps, UV_DROP, [sz, sz],
                    tinting=ramp(K, [(0.0, TAN), (0.5, LIGHT), (1.0, BODY)], "0.95"))


def p_splashmass():
    """Billows of spray bursting up and out of the crash, the body of the splash."""
    update = ["v.an = 360 * v.particle_random_1", "v.k = " + K,
              "v.out = (0.9 + 1.0 * v.particle_random_3) * (1 - math.pow(1 - v.k, 2.2))"]
    pos = ["(v.rw * 0.8 + v.out) * math.cos(v.an)",
           "v.entity_height * (0.1 + 0.6 * v.particle_random_2) + (1.2 + 1.2 * v.particle_random_4) * v.k",
           "(v.rw * 0.8 + v.out) * math.sin(v.an) + 0.6 * v.k"]
    comps = dict(burst(30, update), **{
        "minecraft:particle_lifetime_expression": {"max_lifetime": "0.46 + 0.16 * v.particle_random_2"},
        "minecraft:particle_initial_speed": 0,
        "minecraft:particle_motion_parametric": {"relative_position": pos},
        "minecraft:particle_initial_spin": SPIN_ICON})
    sz = "math.min((0.34 + 0.18 * v.particle_random_4) * v.fx, 0.62) * (0.6 + 0.6 * math.sin(180 * math.min(v.k * 1.3, 1)))"
    return particle("muddywater_splashmass", T_PUFF, comps, puff_frame("v.k", 2, 9), [sz, sz],
                    tinting=ramp("v.k", [(0.0, FOAM), (0.4, TAN), (1.0, LIGHT)], "0.8 * (1 - v.k * v.k)"))


def p_droplets():
    """Fine muddy droplets scattering far in every direction."""
    comps = {
        "minecraft:emitter_initialization": {"creation_expression": ENTITY_DEFAULTS},
        "minecraft:emitter_rate_instant": {"num_particles": 40},
        "minecraft:emitter_lifetime_once": {"active_time": 0.1},
        "minecraft:emitter_shape_sphere": {"offset": [0, "0.45 * v.entity_height", 0],
                                           "radius": "0.3 * v.entity_width", "surface_only": True, "direction": "outwards"},
        "minecraft:particle_initialization": {"per_update_expression": ";".join(TARGET_SIZES) + ";"},
        "minecraft:particle_lifetime_expression": {"max_lifetime": "0.6 + 0.3 * v.particle_random_1"},
        "minecraft:particle_initial_speed": "(4.0 + 5.0 * v.particle_random_2) * math.sqrt(v.fx)",
        "minecraft:particle_motion_dynamic": {"linear_acceleration": [0, -16, 0], "linear_drag_coefficient": 1.2},
        "minecraft:particle_motion_collision": {"collision_radius": 0.04, "expire_on_contact": True},
    }
    sz = f"(0.045 + 0.04 * v.particle_random_3) * v.fx * (1 - 0.4 * {K})"
    return particle("muddywater_droplets", T_ORB, comps, UV_DROP, [sz, sz],
                    tinting=ramp("v.particle_random_4", [(0.0, BODY), (0.6, LIGHT), (1.0, TAN)], "0.95"))


def p_clods():
    """Chunks of mud flying out of the crash and bouncing on the ground."""
    comps = {
        "minecraft:emitter_initialization": {"creation_expression": ENTITY_DEFAULTS},
        "minecraft:emitter_rate_instant": {"num_particles": 12},
        "minecraft:emitter_lifetime_once": {"active_time": 0.1},
        "minecraft:emitter_shape_sphere": {"offset": [0, "0.3 * v.entity_height", "0.2 * v.entity_width"],
                                           "radius": "0.35 * v.entity_width", "surface_only": True, "direction": "outwards"},
        "minecraft:particle_initialization": {"per_update_expression": ";".join(TARGET_SIZES) + ";"},
        "minecraft:particle_lifetime_expression": {"max_lifetime": "0.75 + 0.3 * v.particle_random_1"},
        "minecraft:particle_initial_speed": "(3.0 + 3.0 * v.particle_random_2) * math.sqrt(v.fx)",
        "minecraft:particle_motion_dynamic": {"linear_acceleration": [0, -24, 0], "linear_drag_coefficient": 0.6},
        "minecraft:particle_motion_collision": {"collision_radius": 0.06, "coefficient_of_restitution": 0.45,
                                                "collision_drag": 4},
        "minecraft:particle_initial_spin": {"rotation": "360 * v.particle_random_3", "rotation_rate": 400},
    }
    sz = f"(0.07 + 0.05 * v.particle_random_3) * v.fx * (1 - 0.3 * {K})"
    return particle("muddywater_clods", T_SPLAT, comps, frame_uv("math.floor(v.particle_random_4 * 3)", 8, 8, horizontal=False),
                    [sz, sz], tinting={"color": [1, 1, 1, f"1 - math.pow({K}, 4)"]})


def p_ripple():
    """Rings of muddy water spreading over the ground from the target's feet."""
    comps = {
        "minecraft:emitter_initialization": {"creation_expression": ENTITY_DEFAULTS},
        "minecraft:emitter_rate_steady": {"spawn_rate": 7, "max_particles": 3},
        "minecraft:emitter_lifetime_once": {"active_time": 0.42},
        "minecraft:emitter_shape_point": {"offset": [0, 0.06, 0]},
        "minecraft:particle_initialization": {"per_update_expression": ";".join(TARGET_SIZES) + ";"},
        "minecraft:particle_lifetime_expression": {"max_lifetime": 0.6},
        "minecraft:particle_initial_speed": 0,
        "minecraft:particle_motion_dynamic": {},
    }
    sz = f"(1.0 + 1.6 * {K}) * v.fx"
    return particle("muddywater_ripple", T_RIPPLE, comps, flipbook(16, 16, 9, horizontal=False), [sz, sz],
                    camera="emitter_transform_xz", tinting=ramp(K, [(0.0, FOAM), (1.0, LIGHT)], f"0.9 * (1 - {K} * {K})"))


def p_churn():
    """Turbulent brown water swirling round the target's feet after the crash."""
    update = ["v.k = " + K, "v.an = 360 * v.particle_random_1 + 300 * v.particle_age",
              "v.rd = v.rw + 0.15 + 0.25 * v.particle_random_2 + 0.3 * v.k"]
    pos = ["v.rd * math.cos(v.an)", "0.08 + 0.4 * v.entity_height * v.particle_random_3 * (1 - v.k)", "v.rd * math.sin(v.an)"]
    comps = dict(burst(18, update), **{
        "minecraft:particle_lifetime_expression": {"max_lifetime": "0.55 + 0.2 * v.particle_random_4"},
        "minecraft:particle_initial_speed": 0,
        "minecraft:particle_motion_parametric": {"relative_position": pos},
        "minecraft:particle_initial_spin": SPIN_ICON})
    sz = "math.min((0.28 + 0.14 * v.particle_random_4) * v.fx, 0.55) * (0.7 + 0.4 * math.sin(180 * math.min(v.k * 1.4, 1)))"
    return particle("muddywater_churn", T_PUFF, comps, puff_frame("v.k", 3, 9), [sz, sz],
                    tinting=ramp("v.k", [(0.0, LIGHT), (0.5, BODY), (1.0, DEEP)], "0.75 * (1 - v.k * v.k)"))


# ================================================================= 4. the murky haze (murk animation, only if accuracy fell)
MURK_SIZES = TARGET_SIZES + [f"v.mt = v.particle_age"]


def murk_emitter(count, life, pos, update):
    return {
        "minecraft:emitter_initialization": {"creation_expression": ENTITY_DEFAULTS},
        "minecraft:emitter_rate_instant": {"num_particles": count},
        "minecraft:emitter_lifetime_once": {"active_time": 0.1},
        "minecraft:emitter_shape_point": {},
        "minecraft:particle_initialization": {"per_update_expression": ";".join(MURK_SIZES + list(update)) + ";"},
        "minecraft:particle_lifetime_expression": {"max_lifetime": life},
        "minecraft:particle_initial_speed": 0,
        "minecraft:particle_motion_parametric": {"relative_position": pos},
    }


def p_murk():
    """A murky brown haze settling round the target's head and upper body, drifting, then clearing."""
    update = ["v.tb = 0.3 * v.particle_random_4", "v.sn = math.max(v.mt - v.tb, 0)",
              f"v.k = math.clamp(v.sn / {MURK_LEN - 0.35}, 0, 1)",
              "v.an = 360 * v.particle_random_1 + 35 * v.sn",
              "v.rd = (v.rw + 0.1) * (0.75 + 0.5 * v.particle_random_2)"]
    pos = ["v.rd * math.cos(v.an)", "v.entity_height * (0.55 + 0.45 * v.particle_random_3) + 0.12 * v.sn",
           "v.rd * math.sin(v.an)"]
    vis = "math.clamp((v.mt - v.tb) / 0.25, 0, 1)"
    sz = f"(0.55 + 0.3 * v.particle_random_4) * v.fx * (0.75 + 0.35 * v.k) * {vis}"
    comps = murk_emitter(22, MURK_LEN, pos, update)
    comps["minecraft:particle_initial_spin"] = {"rotation": "360 * v.particle_random_2", "rotation_rate": 20}
    return particle("muddywater_murk", T_HAZE, comps, frame_uv("math.floor(v.particle_random_3 * 4)", 16, 16, horizontal=False),
                    [sz, sz], tinting=ramp("v.particle_random_2", [(0.0, MURK), (1.0, MURK_PALE)],
                                           "0.78 * math.clamp((1 - v.k) * 2.2, 0, 1)"))


def p_drips():
    """Mud dripping off the target's upper body."""
    update = ["v.tb = 0.05 + 0.85 * v.particle_random_1", "v.sn = v.mt - v.tb", "v.s = math.max(v.sn, 0)",
              "v.an = 360 * v.particle_random_2", "v.rd = v.rw * (0.6 + 0.3 * v.particle_random_3)",
              "v.y0 = v.entity_height * (0.5 + 0.45 * v.particle_random_3)",
              "v.y = v.y0 - 0.4 * v.s - 3.5 * math.pow(math.max(v.s - 0.12, 0), 2)"]
    pos = ["v.rd * math.cos(v.an)", "v.y", "v.rd * math.sin(v.an)"]
    vis = f"{window('v.sn', '0.65', 0.08)} * math.clamp(v.y * 8, 0, 1)"
    sz = f"(0.09 + 0.04 * v.particle_random_4) * v.fx * {vis}"
    comps = murk_emitter(16, MURK_LEN - 0.2, pos, update)
    return particle("muddywater_drips", T_MUD, comps, frame_uv("2 + math.floor(v.particle_random_4 * 2)", 8, 8), [sz, f"{sz} * 1.3"],
                    tinting={"color": [1, 1, 1, 1]})


def p_motes():
    """Specks of mud drifting slowly round the target's eyes."""
    update = ["v.an = 360 * v.particle_random_1 + (70 + 40 * v.particle_random_4) * v.mt",
              "v.rd = v.rw * 0.9 + 0.2 + 0.2 * v.particle_random_2",
              f"v.k = math.clamp(v.mt / {MURK_LEN}, 0, 1)"]
    pos = ["v.rd * math.cos(v.an)",
           "v.entity_height * (0.75 + 0.3 * v.particle_random_3) + 0.08 * math.sin(240 * v.mt + 360 * v.particle_random_2)",
           "v.rd * math.sin(v.an)"]
    vis = "math.clamp((v.mt - 0.15 * v.particle_random_3) / 0.2, 0, 1)"
    sz = f"(0.05 + 0.03 * v.particle_random_4) * v.fx * {vis}"
    comps = murk_emitter(12, MURK_LEN, pos, update)
    return particle("muddywater_motes", T_ORB, comps, UV_DROP, [sz, sz],
                    tinting=ramp("v.particle_random_4", [(0.0, SPECK), (1.0, DEEP)], "0.95 * (1 - math.pow(v.k, 3))"))


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


def fx(time):
    return t(max(0.0, time - FX_LEAD))


# ---- the user: rears up while the water gathers, then bows forward and drives the wave out
POS = keyed([(0, (0, 0, 0)), (0.1, (0, 0, 0)), (0.46, (0, 1.4, 2.6)), (0.56, (0, 1.7, 2.9)),
             (0.64, (0, -0.5, -3.4), 'o'), (0.8, (0, -0.25, -3.0)), (1.05, (0, 0, -2.4)), (1.45, (0, 0, 0))])
PITCH = keyed([(0, 0), (0.1, 0), (0.46, -13), (0.56, -15), (0.64, 15, 'o'), (0.8, 11), (1.05, 8), (1.45, 0)])
KEY_TIMES = (0.1, 0.46, 0.56, 0.64, 0.8, 1.05, 1.45)


def shiver(x):
    """Strains as the water gathers (0.28-0.56), pushes the wave out with a slight sway (0.66-1.05)."""
    a = 1.8 * smooth((x - 0.28) / 0.16) * (1 - smooth((x - 0.54) / 0.04))
    b = 1.2 * smooth((x - 0.66) / 0.1) * (1 - smooth((x - 0.95) / 0.12))
    return a * math.sin(2 * math.pi * 13 * x) + b * math.sin(2 * math.pi * 3.2 * x)


def actor_animation():
    return {
        'animation_length': ACTOR_LEN,
        'bones': {'root_part': {
            'position': dense_keys(POS, ACTOR_LEN, 0.02, KEY_TIMES),
            'rotation': dense_keys(lambda x: [PITCH(x)[0], 0.0, shiver(x)], ACTOR_LEN, 0.15, KEY_TIMES, step=0.0125)}},
        'particle_effects': {t(T0): [{'effect': f'cobblemon:muddywater_{n}', 'locator': 'root'} for n in
                                     ('gather', 'gathermud', 'bubbles', 'sediment', 'burst', 'burstfoam')]},
        'sound_effects': {
            t(GATHER0 - 0.06): [{'effect': 'move.muddywater.gather'}],
            t(RELEASE - 0.03): [{'effect': 'move.muddywater.surge'}],
            t(RELEASE + 0.02): [{'effect': 'move.muddywater.rush'}],
        },
    }


def splash_animation():
    """Every target, hit or missed: the wave crashing down round it."""
    return {
        'animation_length': r(IMPACT + 0.2),
        'bones': {},
        'particle_effects': {fx(IMPACT): [{'effect': f'cobblemon:muddywater_{n}', 'locator': 'root'} for n in
                                          ('splashmass', 'splash', 'droplets', 'clods', 'ripple', 'churn')]},
        'sound_effects': {t(IMPACT - 0.02): [{'effect': 'move.muddywater.crash'}, {'effect': 'move.muddywater.splash'}]},
    }


def exact(points):
    return {t(k): vec(v) for k, v in points}


def target_animation():
    """A target the wave hurt: bowled back by the water, then shaking it off."""
    I = IMPACT
    pos = [(0.0, [0, 0, 0]), (I, [0, 0, 0]), (I + 0.05, [0, 0.6, 3.6]), (I + 0.15, [0, 0.3, 4.4]), (I + 0.3, [0, 0.1, 3.0]),
           (I + 0.5, [0, 0, 1.2]), (I + 0.7, [0, 0, 0.3]), (I + 0.85, [0, 0, 0])]
    rot = [(0.0, [0, 0, 0]), (I, [0, 0, 0]), (I + 0.05, [-9, 0, 0]), (I + 0.15, [-7, 0, 3]), (I + 0.24, [-5, 0, -5]),
           (I + 0.32, [-3, 0, 4]), (I + 0.4, [-2, 0, -3]), (I + 0.48, [-1, 0, 2]), (I + 0.56, [0, 0, -1]), (I + 0.85, [0, 0, 0])]
    sc = [(0.0, [1, 1, 1]), (I, [1, 1, 1]), (I + 0.05, [1.07, 0.92, 1.07]), (I + 0.16, [0.97, 1.04, 0.97]), (I + 0.3, [1, 1, 1]),
          (I + 0.85, [1, 1, 1])]
    return {
        'animation_length': r(TARGET_LEN),
        'bones': {'root_part': {'position': exact(pos), 'rotation': exact(rot), 'scale': exact(sc)}},
        'particle_effects': {fx(I): [{'effect': 'cobblemon:impact_water', 'locator': 'target'}]},
        'sound_effects': {t(I): [{'effect': 'impact.water'}]},
    }


def dodge_animation():
    """A target the move missed: hops aside as the wave breaks round it."""
    D = IMPACT - 0.14
    pos = [(0.0, [0, 0, 0]), (D, [0, 0, 0]), (D + 0.1, [3.0, 4.5, 1.0]), (D + 0.24, [4.0, 3.0, 1.4]), (D + 0.36, [4.2, 0, 1.2]),
           (D + 0.5, [2.0, 0, 0.6]), (D + 0.7, [0, 0, 0])]
    rot = [(0.0, [0, 0, 0]), (D, [0, 0, 0]), (D + 0.1, [-6, 0, -10]), (D + 0.24, [-3, 0, -6]), (D + 0.36, [0, 0, 2]),
           (D + 0.7, [0, 0, 0])]
    return {
        'animation_length': r(D + 0.7),
        'bones': {'root_part': {'position': exact(pos), 'rotation': exact(rot)}},
    }


def murk_animation():
    """A target whose accuracy fell: mud and a murky haze cling round its eyes; it shakes its head."""
    M = MURK0
    rot = [(0.0, [0, 0, 0]), (M, [0, 0, 0]), (M + 0.15, [0, 8, 0]), (M + 0.35, [0, -7, 0]), (M + 0.55, [0, 5, 0]),
           (M + 0.75, [0, -3, 0]), (M + 0.95, [0, 0, 0])]
    pos = [(0.0, [0, 0, 0]), (M, [0, 0, 0]), (M + 0.3, [0, -0.6, 0]), (M + 1.0, [0, 0, 0])]
    return {
        'animation_length': r(M + MURK_LEN),
        'bones': {'root_part': {'position': exact(pos), 'rotation': exact(rot)}},
        'particle_effects': {t(M): [{'effect': f'cobblemon:muddywater_{n}', 'locator': 'root'} for n in ('murk', 'drips', 'motes')]},
        'sound_effects': {t(M): [{'effect': 'move.muddywater.murk'}]},
    }


def build_animation_file():
    return {'format_version': '1.8.0', 'animations': {
        'animation.muddywater.actor': actor_animation(),
        'animation.muddywater.splash': splash_animation(),
        'animation.muddywater.target': target_animation(),
        'animation.muddywater.dodge': dodge_animation(),
        'animation.muddywater.murk': murk_animation()}}


# ================================================================= the action effect
def play(anim):
    return f"q.play_animation(q.bedrock_stateful('muddywater', '{anim}', 'endures_primary_animations'))"


# What the battle reported decides what plays; nothing here works anything out for itself.
USER = "q.entity.is_user == true"
FOE = "q.entity.is_user == false"
FOE_HIT = f"{FOE} && q.hurt(q.entity.uuid) == true"
FOE_MISSED = f"{FOE} && q.missed(q.entity.uuid) == true"
# the battle lowered this target's accuracy (Java hook; reads 0 if it isn't there, so nothing shows)
FOE_MURKED = f"{FOE} && q.entity.move_stat_change('accuracy') < 0"
if os.environ.get('MW_FORCE_MURK') == '1':
    # debug build for checking the haze in-game without waiting for the 30% roll: every target that
    # wasn't missed gets it. Never ship this.
    FOE_MURKED = f"{FOE} && q.missed(q.entity.uuid) == false"


def build_effect_file():
    # Every keyframe costs a server tick in 1.7.3, so the whole start is one `parallel` (one tick).
    start = [
        {'type': 'entity_molang', 'entityCondition': USER, 'expressions': [play('actor')]},
        {'type': 'entity_molang', 'entityCondition': FOE, 'expressions': [play('splash')]},
        {'type': 'entity_molang', 'entityCondition': FOE_HIT, 'expressions': [play('target')]},
        {'type': 'entity_molang', 'entityCondition': FOE_MISSED, 'expressions': [play('dodge')]},
        {'type': 'entity_molang', 'entityCondition': FOE_MURKED, 'expressions': [play('murk')]},
    ]
    for layer in ('crestspray', 'crestfoam', 'crestclods'):
        start.append({'type': 'entity_particles', 'effect': f'cobblemon:muddywater_{layer}', 'locators': ['root'],
                      'targetLocators': ['root']})
    # the wave mesh (Java hook; returns 0 and draws nothing if it isn't there)
    start.append({'type': 'molang', 'expressions': "q.user.wave_effect('muddywater', q.target, q.targets)"})
    # Cobblemon leaves a foe a spread move missed out of the action effect (a double battle), so the
    # keyframes above can't reach it: this Java hook plays its splash and dodge (0 and nothing if absent)
    start.append({'type': 'molang', 'expressions': "q.user.play_on_missed_spread_targets('muddywater', 'splash', 'dodge')"})
    # the parallel above already took a tick; the HP bars drop as the wave crashes, and the timeline runs
    # on while the flood drains and any haze settles
    return {'timeline': [
        {'type': 'add_holds', 'holds': ['effects']},
        {'type': 'parallel', 'keyframes': start},
        {'type': 'pause', 'pause': r(IMPACT - 0.05)},
        {'type': 'remove_holds', 'holds': ['effects']},
        {'type': 'pause', 'pause': TAIL},
    ]}


# ================================================================= the wave style (client resource, read by Java)
def hex6(c):
    return '#' + c[-6:]


def build_style_file():
    return {
        'texture': TEXTURE, 'texture_blocks': TEXTURE_BLOCKS, 'flow_speed': FLOW_SPEED, 'lighting_up_bias': LIGHTING_UP_BIAS,
        'time': {'crown_rise': CROWN_RISE, 'crown_peak': CROWN_PEAK, 'release': RELEASE, 'impact': IMPACT,
                 'crash_end': CRASH_END, 'drain_end': DRAIN_END},
        'crown': {'height': CROWN_HEIGHT, 'gap': CROWN_GAP, 'flare': CROWN_FLARE, 'swirl': CROWN_SWIRL, 'jag': CROWN_JAG,
                  'collapse': CROWN_COLLAPSE, 'pool_radius': POOL_RADIUS},
        'wave': {'height': WAVE_HEIGHT, 'start_gap': START_GAP, 'side_padding': SIDE_PADDING,
                 'min_half_width': MIN_HALF_WIDTH, 'lip': LIP, 'bow': BOW, 'overshoot': OVERSHOOT,
                 'crest_noise': CREST_NOISE, 'end_taper': END_TAPER, 'foam_back': FOAM_BACK, 'foam_face': FOAM_FACE,
                 'mottle': MOTTLE},
        # the mesh is shaded and its texture is grey, so it gets lighter versions of the particle colours
        'color': MESH_COLOR,
        'alpha': {'body': 0.92, 'sheet': 0.7, 'foam': 0.97, 'crown': 0.9, 'pool': 0.8},
    }


# ================================================================= sounds (aliases of Cobblemon's own files)
SOUND_EVENTS = {
    'move.muddywater.gather': ('cobblemon:move/mudsport/mudsport_actor', 0.75, 1.0),     # mud churning round the user
    'move.muddywater.surge': ('cobblemon:fishing/fishing_splash_big_1', 1.0, 0.75),      # the crown bursting
    'move.muddywater.rush': ('cobblemon:move/watergun/watergun_actor', 0.8, 0.6),        # the wave rushing across
    'move.muddywater.crash': ('cobblemon:move/mudbomb/mudbomb_target', 1.0, 0.8),        # mud slamming into the target
    'move.muddywater.splash': ('cobblemon:fishing/fishing_splash_big_2', 0.9, 0.85),     # the water crashing round it
    'move.muddywater.murk': ('cobblemon:move/sandattack/sandattack_target', 0.8, 0.75),  # accuracy fell
}


def update_sounds():
    with open(SOUNDS) as f:
        sounds = json.load(f)
    for key, (name, volume, pitch) in SOUND_EVENTS.items():
        sounds[key] = {'sounds': [{'name': name, 'volume': volume, 'pitch': pitch}]}
    for stale in [k for k in sounds if k.startswith('move.muddywater.') and k not in SOUND_EVENTS]:
        del sounds[stale]
    with open(SOUNDS, 'w') as f:
        f.write(json.dumps(sounds, indent=2) + '\n')
    print('updated', os.path.relpath(SOUNDS, ROOT), f'({len(SOUND_EVENTS)} move.muddywater.* events)')


# ================================================================= output
def all_particles():
    return [p_gather(), p_gathermud(), p_bubbles(), p_sediment(), p_burst(), p_burstfoam(),
            p_crestspray(), p_crestfoam(), p_crestclods(),
            p_splash(), p_splashmass(), p_droplets(), p_clods(), p_ripple(), p_churn(),
            p_murk(), p_drips(), p_motes()]


def write(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
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
    write(STYLE_OUT, build_style_file())
    update_sounds()
    if os.environ.get('MW_FORCE_MURK') == '1':
        print('WARNING: MW_FORCE_MURK debug build: every target gets the haze. Re-run without it before shipping.')
