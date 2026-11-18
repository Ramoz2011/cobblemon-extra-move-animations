"""Generates Bitter Blade's particle effects, generic animation file and action effect.

Outputs (paths relative to the repo root):
  src/main/resources/assets/cobblemon/bedrock/particles/moves/bitterblade/*.particle.json
  src/main/resources/assets/cobblemon/bedrock/generic/animations/moves/bitterblade.animation.json
  src/main/resources/data/cobblemon/action_effects/moves/bitterblade.json

Edit the constants below and re-run `python3 docs/tools/bitterblade_gen.py`; don't hand-edit the outputs.
`python3 docs/tools/bitterblade_gen.py --check-rig` compares the copy of Ceruledge's rig below with the
model and battle idle in every Cobblemon jar in the Gradle cache.
Design notes and the reasoning behind the numbers: docs/bitterblade_assets.md.

How the pieces fit:
- Bitter Blade is Ceruledge's signature move, so Ceruledge plays its own user animation
  (actor_ceruledge): its arms swing its real blades, and everything that sits on the blades (the pink
  glow, the ghost flames licking off them, the ribbon left by the spin) is placed with forward
  kinematics of Ceruledge's model (the RIG below, Cobblemon's own conventions) sampled into curves.
  Any other Pokemon that ends up using it (Metronome, Mirror Move, Copycat, Sketch) plays `actor`:
  the same body motion and flames, with a slash ring sized from its hitbox instead of blades.
- The look is Scarlet/Violet's (user's choice): blue ghost fire with violet and pink wisps wraps the
  user, the blades glow hot pink, it spins in place, a pale cyan slash crosses to the target and cuts
  it diagonally, then a mint-green orb of drained energy flies back and the user heals in a green
  bubble. No dash: in SV Ceruledge never leaves its spot.
- Everything starts in one server tick (one `parallel`) and then runs on the client clock. Particles
  fired by an animation are fired at T0, while root_part is still at rest, so their frame faces the
  target; they are path-locked (one burst, parametric positions, each particle shown only in its own
  time window). The spin itself is carried by the model; what the blades leave behind are particles
  that light up where the blade was, because particles only update 20 times a second.
- The battle heals the user (HP bar and "had its energy drained!") right after the action effect's
  timeline ends, so the timeline ends as the green bubble appears. On a knockout the battle doesn't
  wait and the HP rises early; nothing else changes.
"""
import json, math, os, sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..')
RES = os.path.join(ROOT, 'src/main/resources')
PART_DIR = os.path.join(RES, 'assets/cobblemon/bedrock/particles/moves/bitterblade')
ANIM_OUT = os.path.join(RES, 'assets/cobblemon/bedrock/generic/animations/moves/bitterblade.animation.json')
EFFECT_OUT = os.path.join(RES, 'data/cobblemon/action_effects/moves/bitterblade.json')

# ---------------------------------------------------------------- timing (seconds from the start of the move)
T0 = 0.02            # the user's particles fire here, while root_part is still at rest
# Particles fired by an animation show up PARTICLE_LAG after their keyframe (born the tick after their
# emitter, positions drawn a tick late), so nothing they draw can appear before T0 + PARTICLE_LAG: the
# model starts its crouch at once and the first effects come in right after.
IGNITE = 0.20        # 1. the blades flare pink
WRAP0, WRAP1 = 0.22, 0.72       # blue ghost flames erupt round the user and wrap it
CROUCH = 0.30        # the crouch has settled
WIND0 = 0.58         # 2. wind-up: twists back and raises the blades
SPIN0, SPIN1 = 0.72, 1.02       # the spin slash
SPIN_FROM, SPIN_TO = -28.0, 360.0   # root_part yaw over the wind-up and the spin (degrees)
LUNGE = SPIN1 + 0.20 # the low, wide stance it ends the slash in, held until here
IMPACT = 1.12        # 3. the slash cuts the target (RELEASE, when it leaves the blade, is worked out below)
REC1 = 1.58          # back in its battle stance
ORB0 = 1.28          # 4. an orb of drained energy forms on the target
FLY0, FLY1 = 1.46, 1.88         # ... and flies back to the user
ARRIVE = FLY1        # rings close in round the user
HEAL = 2.06          # 5. the heal bubble; the battle restores the HP right after the timeline ends
HEAL_END = 2.48
ACTOR_LEN = 1.62
HEAL_LEN = 2.52
TAIL = 0.45          # miss or no damage: how long the timeline runs on after the slash lands
PARTICLE_LAG = 0.175 # path-locked particles fired by an animation: their age 0 shows at T0 + this
T_IN = T0 + PARTICLE_LAG
EMIT_LAG = 0.075     # an action-effect emitter's first particles are born about this late
FX_LEAD = 0.075      # the target animation fires its particles this early so they show on the hit frame

# ---------------------------------------------------------------- palette (#AARRGGBB)
WHITE = '#FFFFFFFF'
PINK_HOT = '#FFFF5FD2'      # the blades' glow (Ceruledge's own blade tips are #FF8DEF)
PINK_PALE = '#FFFFE3F6'
MAGENTA = '#FFFF3FC8'
VIOLET = '#FFA86BFF'
COBALT = '#FF4A5CFF'        # the ghost flames (Ceruledge's flame layer runs #4C68C5 .. #9CD9F8)
PERIWINKLE = '#FF8FA6FF'
ICE = '#FFCFF4FF'           # the slash and the cut
CYAN = '#FF7FD8FF'
INDIGO = '#FF2A2C9C'
MINT_WHITE = '#FFF0FFF6'    # the drained energy and the heal (SV's drain look)
MINT = '#FF8EF0C0'
GREEN = '#FF56D896'


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


T_GLOW = tex('moves/bravebird_glow', 32, 32)             # round soft glow (docs/tools/bravebird_textures.py)
T_PUFF = tex('generic/fire/cloudyfire_white', 160, 16)   # 10 frames 16x16: a puff that swells and breaks up
T_WISP = tex('generic/fire/wisp', 99, 13)                # 11 frames 9x13: a blue ghost flame (pre-coloured)
T_SPARK = tex('generic/sparkle/glowingsparkle', 8, 32)   # 4 frames 8x8, big to small, near-white
T_SPARK_PINK = tex('generic/sparkle/glowingsparkle_pink', 8, 32)
T_SPARK_CYAN = tex('generic/sparkle/glowingsparkle_cyan', 8, 32)
T_STAR = tex('generic/sparkle/sparkle', 8, 16)           # 2 frames: a four-point star, big then small
T_TWINKLE = tex('generic/skyding', 275, 25)              # 11 frames 25x25: a four-point star twinkling
T_HIT = tex('generic/hit', 32, 160)                      # 5 frames 32x32, top to bottom: an impact star
T_RING = tex('generic/ring/giantring_white', 448, 64)    # 7 frames 64x64: a ring expanding and breaking up
T_BEAM = tex('generic/smallbeam', 140, 91)

UV_BEAM = {"uv": [70, 42], "uv_size": [70, 7]}    # right half of one smallbeam frame: a soft streak
UV_GLOW = {"uv": [0, 0], "uv_size": [32, 32]}
UV_STAR = {"uv": [0, 0], "uv_size": [7, 7]}


def frame_uv(index, fw, fh, horizontal=True):
    """Static UV of frame `index` (a MoLang expression) of a sheet laid out left-to-right or top-to-bottom."""
    return {"uv": [f"{fw} * ({index})", 0] if horizontal else [0, f"{fh} * ({index})"], "uv_size": [fw, fh]}


def frames(k, count):
    """Frame index for a 0..1 progress over `count` frames."""
    return f"math.floor(math.clamp({k}, 0, 0.999) * {count})"


def puff_frame(k, first=1, last=8):
    """cloudyfire frame for a 0..1 progress: the puff swells (low frames) and breaks up (high frames)."""
    return frame_uv(f"{first} + {frames(k, last - first + 1)}", 16, 16)


def wisp_frame(clock):
    """The ghost flame flickers through its 11 frames (looping) as `clock` (seconds) runs."""
    return frame_uv(f"math.floor(math.mod(math.max({clock}, 0) * 16 + 11 * v.particle_random_4, 11))", 9, 13)


def flipbook(fw, fh, count, horizontal=True):
    return {"flipbook": {"base_UV": [0, 0], "size_UV": [fw, fh], "step_UV": [fw, 0] if horizontal else [0, fh],
                         "frames_per_second": 20, "max_frame": count, "stretch_to_lifetime": True}}


def gradient(inp, stops):
    return {"color": {"interpolant": inp, "gradient": {t(k): v for k, v in stops}}}


def rgb(hexcol):
    v = int(hexcol[1:], 16)
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
    pe = {"description": {"identifier": f"cobblemon:{pid}",
                          "basic_render_parameters": {"material": "particles_blend", "texture": path}}}
    if curves:
        pe["curves"] = curves
    pe["components"] = comps
    return {"format_version": "1.10.0", "particle_effect": pe}


def c3(*parts):
    """Sum per axis of several 3-tuples of expressions."""
    return [" + ".join(f"({p[i]})" for p in parts) for i in range(3)]


SINPHI = "math.sqrt(1 - math.pow(2 * v.particle_random_2 - 1, 2))"
COSPHI = "(2 * v.particle_random_2 - 1)"


def sphere_dir(theta="(360 * v.particle_random_1)"):
    return (f"{SINPHI} * math.cos({theta})", COSPHI, f"{SINPHI} * math.sin({theta})")


K = "(v.particle_age / v.particle_lifetime)"
ENTITY_DEFAULTS = "v.entity_width = 1; v.entity_height = 1;"
SPIN_ICON = {"rotation": "math.floor(v.particle_random_4 * 4) * 90"}


# ================================================================= Ceruledge's rig
# Copied from Cobblemon's bedrock/pokemon/models/0937_ceruledge/ceruledge.geo.json (identical in 1.7.3
# and 1.8.4): bone -> (parent, pivot, rest rotation). The arms are modelled straight out to the sides
# (+x is its left), and each blade is a flat quad 31 units long running along the arm.
RIG = {
    'ceruledge': (None, (0, 0, 0), (0, 0, 0)),
    'body': ('ceruledge', (0, 29.2, -1), (0, 0, 0)),
    'torso': ('body', (0, 27.7, -1), (0, 0, 0)),
    'waist': ('torso', (0, 28.7, -0.9), (2.5, 0, 0)),
    'chest': ('waist', (0, 30.1, 0.6), (-5, 0, 0)),
    'arms': ('chest', (0, 32.9, 0.5), (2.5, 0, 0)),
    'arm_left': ('arms', (3, 33.6, 0.7), (0, 0, 0)),
    'arm_left2': ('arm_left', (8, 32.6, 1.7), (0, 0, 0)),
    'arm_left3': ('arm_left2', (10.5, 32.6, 0.7), (0, 0, 0)),
    'blade_left': ('arm_left3', (12.5, 32.6, 0.8), (0, 0, 0)),
    'arm_right': ('arms', (-3, 33.6, 0.7), (0, 0, 0)),
    'arm_right2': ('arm_right', (-8, 32.6, 1.7), (0, 0, 0)),
    'arm_right3': ('arm_right2', (-10.5, 32.6, 0.7), (0, 0, 0)),
    'blade_right': ('arm_right3', (-12.5, 32.6, 0.8), (0, 0, 0)),
}
# blade quad: x from the hand end to the point (model units), on the plane y = 32.6, centre line z = 0.8
BLADE_X = {'blade_left': (8.5, 39.5), 'blade_right': (-8.5, -39.5)}
# the battle idle (battle_idle, mean over its 1 s loop; its wobble is +-2 degrees): bone -> (position, rotation)
IDLE = {
    'body': ((0, -4.2, 0), (0, 0, 0)),
    'torso': ((0, 0.25, -1.4), (20, 0, 0)),
    'chest': ((0, 0, 0), (7.5, 0, 0)),
    'arm_left': ((0, 0, 0), (5.498, -7.336, 26.044)),
    'arm_left2': ((0, 0, 0), (0, 15, 0)),
    'arm_left3': ((0, 0, 0), (2.429, 7.414, -0.652)),
    'arm_right': ((0, 0, 0), (-4.502, 29.836, -38.544)),
    'arm_right2': ((0, 0, 0), (0, -35, 0)),
    'arm_right3': ((0, 0, 0), (2.429, -7.414, 0.652)),
}


def _mul(a, b):
    return [[sum(a[i][k] * b[k][j] for k in range(4)) for j in range(4)] for i in range(4)]


def _part_matrix(offset, rot_deg, scale=(1, 1, 1)):
    """A ModelPart's transform: translate, then rotationZYX (z, y, x), then scale (Minecraft's order)."""
    x, y, z = (math.radians(c) for c in rot_deg)
    cx, sx, cy, sy, cz, sz = math.cos(x), math.sin(x), math.cos(y), math.sin(y), math.cos(z), math.sin(z)
    rz = [[cz, -sz, 0], [sz, cz, 0], [0, 0, 1]]
    ry = [[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]]
    rx = [[1, 0, 0], [0, cx, -sx], [0, sx, cx]]
    m3 = [[sum(rz[i][k] * sum(ry[k][l] * rx[l][j] for l in range(3)) for k in range(3)) for j in range(3)] for i in range(3)]
    return [[m3[i][0] * scale[0], m3[i][1] * scale[1], m3[i][2] * scale[2], offset[i]] for i in range(3)] + [[0, 0, 0, 1]]


def _chain(bone):
    out = []
    while bone:
        out.append(bone)
        bone = RIG[bone][0]
    return out[::-1]


def rig_point(bone, local, deltas, root):
    """Where a point of `bone` (Java model units in the bone's space) is in the frame of the 'root' locator
    as the emitters fired at T0 see it (model units; +y up, -z towards the target, -x the Pokemon's left).

    deltas: bone -> (position, rotation) added on top of the battle idle, in animation-file units;
    root: (position, rotation) of root_part. Cobblemon (TexturedModel) keeps Bedrock's x and z and flips y,
    copies rotations as they are and builds each part as translate * rotZYX; animations add rotations and
    add positions with y negated; the locators undo the entity's upside-down render with a z half-turn.
    """
    m = _part_matrix((root[0][0], -root[0][1], root[0][2]), root[1])
    for name in _chain(bone):
        parent, pivot, rest = RIG[name]
        if parent is None:
            off = [0.0, 0.0, 0.0]
        else:
            pp = RIG[parent][1]
            off = [pivot[0] - pp[0], -(pivot[1] - pp[1]), pivot[2] - pp[2]]
        rot = list(rest)
        for pos_rot in (IDLE.get(name), deltas.get(name)):
            if pos_rot:
                off = [off[0] + pos_rot[0][0], off[1] - pos_rot[0][1], off[2] + pos_rot[0][2]]
                rot = [rot[i] + pos_rot[1][i] for i in range(3)]
        m = _mul(m, _part_matrix(off, rot))
    p = [sum(m[i][k] * (local[k] if k < 3 else 1) for k in range(4)) for i in range(3)]
    return [-p[0], -p[1], p[2]]


def blade_local(blade, u):
    """Point u of a blade's centre line (0 = hand end, 1 = point), in the blade bone's space."""
    pivot = RIG[blade][1]
    x0, x1 = BLADE_X[blade]
    return [x0 + (x1 - x0) * u - pivot[0], 0.0, 0.0]


# ================================================================= the user's motion
# root_part: position in model units (+z = back, -y = down), rotation in degrees (+x = lean forward,
# +y = the turn that brings its left side to the front). Shared by every species.
ROOT_POS = keyed([(0, (0, 0, 0)), (T0 + 0.01, (0, 0, 0)), (CROUCH, (0, -1.0, 0.4)), (WIND0, (0, -1.3, 0.6)),
                  (SPIN0, (0, -1.8, 0.9)), (SPIN1 - 0.06, (0, -0.8, -0.6)), (SPIN1 + 0.05, (0, -2.6, -3.0), 'o'),
                  (LUNGE, (0, -2.4, -3.2)), (REC1, (0, 0, 0))])
ROOT_PITCH = keyed([(0, 0), (T0 + 0.01, 0), (CROUCH, 4), (WIND0, 5), (SPIN0, 3), (SPIN1 + 0.05, 11, 'o'), (LUNGE, 10),
                    (REC1, 0)])
ROOT_YAW = keyed([(0, 0), (WIND0, 0), (SPIN0, SPIN_FROM), (SPIN1, SPIN_TO), (ACTOR_LEN, SPIN_TO)])
# Ceruledge's arms: share of the way from the battle idle to arms straight out (blades level), and how
# far both arms trail behind the turn while it spins (degrees about the body's axis)
ARMS_OUT = keyed([(0, 0), (CROUCH, 0.12), (WIND0, 0.2), (SPIN0, 0.92), (SPIN1, 1.0), (SPIN1 + 0.08, 0.7), (LUNGE, 0.55),
                  (REC1, 0)])
ARM_LAG = keyed([(0, 0), (SPIN0, 0), (SPIN0 + 0.08, -16), (SPIN1 - 0.06, -16), (SPIN1 + 0.04, 0)])
STANCE = keyed([(0, 0), (SPIN1 - 0.05, 0), (SPIN1 + 0.05, 1, 'o'), (LUNGE, 0.9), (REC1, 0)])   # feet wide for the lunge
NOD = keyed([(0, 0), (SPIN1 - 0.02, 0), (SPIN1 + 0.06, 8), (LUNGE, 6), (REC1, 0)])
# arms straight out = the battle idle's arm rotations undone
ARMS_STRAIGHT = {b: tuple(-c for c in IDLE[b][1]) for b in ('arm_left', 'arm_left2', 'arm_left3',
                                                            'arm_right', 'arm_right2', 'arm_right3')}


def root_at(x):
    p = ROOT_POS(x)
    return (p, (ROOT_PITCH(x)[0], ROOT_YAW(x)[0], 0.0))


def ceruledge_deltas(x):
    k = ARMS_OUT(x)[0]
    lag = ARM_LAG(x)[0]
    d = {}
    for b, rot in ARMS_STRAIGHT.items():
        extra = lag if b in ('arm_left', 'arm_right') else 0.0
        d[b] = ((0, 0, 0), (rot[0] * k, rot[1] * k + extra, rot[2] * k))
    st = STANCE(x)[0]
    d['leg_left'] = ((0, 0, 0), (0, 0, -12 * st))
    d['leg_right'] = ((0, 0, 0), (0, 0, 12 * st))
    d['head'] = ((0, 0, 0), (NOD(x)[0], 0, 0))
    return d


def blade_at(x, blade, u):
    return rig_point(blade, blade_local(blade, u), ceruledge_deltas(x), root_at(x))


def find_release():
    """When the right blade's point crosses the front (x = 0, z < 0) during the spin: the slash leaves it."""
    prev = None
    x = SPIN0
    while x <= SPIN1:
        p = blade_at(x, 'blade_right', 1.0)
        if prev is not None and p[2] < 0 and prev[0] * p[0] <= 0 and prev[0] != p[0]:
            return r(x - 0.002 + 0.002 * prev[0] / (prev[0] - p[0]), 3)
        prev, x = p, x + 0.002
    raise SystemExit('the right blade never crosses the front during the spin')


RELEASE = find_release()


def spin_sense_ok():
    """Sanity check: the tangent the spin layers use, (-z, 0, x), points the way the blade really moves."""
    for x in (SPIN0 + 0.08, (SPIN0 + SPIN1) / 2, SPIN1 - 0.05):
        p0, p1 = blade_at(x, 'blade_left', 1.0), blade_at(x + 0.004, 'blade_left', 1.0)
        mv = (p1[0] - p0[0], p1[2] - p0[2])
        tan = (-p0[2], p0[0])
        if mv[0] * tan[0] + mv[1] * tan[1] <= 0:
            raise SystemExit(f'spin tangent points the wrong way at {x:.3f}')


spin_sense_ok()


# ================================================================= curves: blade paths
def blade_curves(inp, lo, hi, step):
    """12 linear curves (hand end and point of both blades, frame model units) over [lo, hi] of `inp`."""
    n = int(round((hi - lo) / step)) + 1
    xs = [lo + i * (hi - lo) / (n - 1) for i in range(n)]
    pts = {(b, u): [blade_at(x, b, u) for x in xs] for b in ('blade_left', 'blade_right') for u in (0.0, 1.0)}
    out = {}
    for side, blade in (('l', 'blade_left'), ('r', 'blade_right')):
        for end, u in (('h', 0.0), ('t', 1.0)):
            for i, axis in enumerate('xyz'):
                out[f"variable.bb_{side}{end}{axis}"] = {
                    "type": "linear", "input": f"({inp}) - {r(lo)}", "horizontal_range": r(hi - lo, 4),
                    "nodes": [r(p[i], 2) for p in pts[(blade, u)]]}
    return out


SC = "((q.entity_scale > 0 ? q.entity_scale : 1) / 16)"
SIZES = [
    "v.bl = math.clamp(math.max(v.entity_width, v.entity_height), 0.5, 3.0)",   # body size (blocks)
    "v.fs = math.clamp(0.45 + 0.5 * v.bl, 0.7, 1.9)",    # effect scale: grows slowly with the body
    "v.rw = 0.42 * v.entity_width + 0.22",               # radius of the flame wrap
    f"v.sc = {SC}",                                      # model units -> blocks
    "v.bs = math.clamp(q.entity_scale / 0.7, 0.4, 2.5)", # Ceruledge's blade effects vs a normal-sized one
    f"v.tt = v.particle_age + {r(T_IN)}",                # animation time this particle is showing
]


def blade_point(u):
    """Per-update lines putting v.px/v.py/v.pz (blocks) at point `u` of the particle's blade (v.sd = left)."""
    lines = []
    for i, axis in enumerate('xyz'):
        lines.append(f"v.p{axis} = (v.sd ? (v.bb_lh{axis} + {u} * (v.bb_lt{axis} - v.bb_lh{axis}))"
                     f" : (v.bb_rh{axis} + {u} * (v.bb_rt{axis} - v.bb_rh{axis}))) * v.sc")
    return lines


def locked(count, end_time, pos, update=(), start=T_IN):
    """Path-locked layer fired by an animation at T0: every particle spawned at once, positioned by the
    parametric motion and shown only in its own time window (sizes go to 0 outside it)."""
    return {
        "minecraft:emitter_initialization": {"creation_expression": ENTITY_DEFAULTS},
        "minecraft:emitter_rate_instant": {"num_particles": count},
        "minecraft:emitter_lifetime_once": {"active_time": 0.1},
        "minecraft:emitter_shape_point": {},
        "minecraft:particle_initialization": {"per_update_expression": ";".join(list(SIZES) + list(update)) + ";"},
        "minecraft:particle_lifetime_expression": {"max_lifetime": r(end_time - start)},
        "minecraft:particle_initial_speed": 0,
        "minecraft:particle_motion_parametric": {"relative_position": pos},
    }


def window(since, life, fade_in=0.03):
    """1 while 0 <= since < life (soft edges), else 0."""
    return f"math.clamp(({since}) / {fade_in}, 0, 1) * math.clamp(({life} - ({since})) * 40, 0, 1)"


# ================================================================= 1. ignition: the blades flare, ghost flames wrap the user
def p_wrap():
    """Blue ghost fire erupting from the ground round the user and climbing it: puffs born on a ring at the
    feet that swirl up the body, swelling, then breaking up violet and pink above the head (SV)."""
    tb = f"({WRAP0} + {WRAP1 - WRAP0} * math.pow(v.particle_random_1, 1.3))"
    life = "(0.36 + 0.14 * v.particle_random_4)"
    since = f"(v.tt - {tb})"
    k = f"math.clamp({since} / {life}, 0, 1)"
    ang = f"(360 * v.particle_random_2 + 110 * {k})"
    rad = f"v.rw * (1.05 - 0.4 * {k}) * (0.75 + 0.5 * v.particle_random_3)"
    pos = [f"{rad} * math.cos({ang})", f"v.entity_height * (0.02 + 1.08 * math.pow({k}, 0.8))", f"{rad} * math.sin({ang})"]
    vis = window(since, life, 0.04)
    sz = f"(0.22 + 0.12 * v.particle_random_4) * v.fs * (0.55 + 0.75 * math.sin(180 * math.min({k} * 1.3, 1))) * {vis}"
    comps = locked(70, WRAP1 + 0.52, pos)
    comps["minecraft:particle_initial_spin"] = SPIN_ICON
    return particle("bitterblade_wrap", T_PUFF, comps, puff_frame(k, 1, 9), [sz, sz],
                    tinting=ramp(k, [(0.0, COBALT), (0.45, '#FF6F82FF'), (0.75, VIOLET), (1.0, '#FFFF7FD8')],
                                 f"0.6 * (1 - {k} * {k})"))


def p_wrapsmoke():
    """The dark holes in SV's ghost fire: a few deep indigo puffs rising inside the flames."""
    tb = f"({WRAP0 + 0.03} + {WRAP1 - WRAP0 - 0.05} * v.particle_random_1)"
    life = "(0.4 + 0.12 * v.particle_random_4)"
    since = f"(v.tt - {tb})"
    k = f"math.clamp({since} / {life}, 0, 1)"
    ang = f"(360 * v.particle_random_2 + 90 * {k})"
    rad = f"v.rw * (0.85 - 0.3 * {k}) * (0.7 + 0.5 * v.particle_random_3)"
    pos = [f"{rad} * math.cos({ang})", f"v.entity_height * (0.1 + 0.95 * {k})", f"{rad} * math.sin({ang})"]
    vis = window(since, life, 0.05)
    sz = f"(0.36 + 0.14 * v.particle_random_4) * v.fs * (0.6 + 0.6 * {k}) * {vis}"
    comps = locked(26, WRAP1 + 0.55, pos)
    comps["minecraft:particle_initial_spin"] = SPIN_ICON
    return particle("bitterblade_wrapsmoke", T_PUFF, comps, puff_frame(k, 2, 9), [sz, sz],
                    tinting={"color": [0.11, 0.09, 0.3, f"0.55 * math.sin(180 * {k})"]})


def p_wrapwisps():
    """Ghost flames (Cobblemon's blue wisp sprite) licking up the body inside the fire."""
    tb = f"({WRAP0} + {WRAP1 - WRAP0 + 0.04} * v.particle_random_1)"
    life = "(0.3 + 0.12 * v.particle_random_3)"
    since = f"(v.tt - {tb})"
    k = f"math.clamp({since} / {life}, 0, 1)"
    ang = "(360 * v.particle_random_2)"
    rad = f"v.rw * (0.55 + 0.5 * v.particle_random_3)"
    pos = [f"{rad} * math.cos({ang})", f"v.entity_height * (0.05 + 0.6 * v.particle_random_1 + 0.5 * {k})",
           f"{rad} * math.sin({ang})"]
    vis = window(since, life)
    grow = f"math.sin(180 * math.min({k} * 1.25, 1))"
    w = f"(0.2 + 0.1 * v.particle_random_4) * v.fs * {grow} * {vis}"
    comps = locked(66, WRAP1 + 0.5, pos)
    return particle("bitterblade_wrapwisps", T_WISP, comps, wisp_frame(since), [w, f"{w} * 1.44"],
                    tinting={"color": [1, "v.particle_random_2 < 0.3 ? 0.72 : 1", 1, f"0.9 * (1 - {k} * {k})"]})


def p_embers():
    """Pink and lilac sparks rising round the user while the fire builds and through the spin."""
    tb = f"({WRAP0} + {SPIN1 - WRAP0} * v.particle_random_1)"
    life = "(0.45 + 0.15 * v.particle_random_3)"
    since = f"(v.tt - {tb})"
    k = f"math.clamp({since} / {life}, 0, 1)"
    ang = f"(360 * v.particle_random_2 + 120 * {k})"
    rad = f"v.rw * (0.7 + 0.7 * v.particle_random_3) * (1 + 0.3 * {k})"
    pos = [f"{rad} * math.cos({ang})", f"v.entity_height * (0.15 + 0.7 * v.particle_random_4) + 1.3 * v.fs * {since}",
           f"{rad} * math.sin({ang})"]
    vis = window(since, life)
    sz = f"(0.08 + 0.04 * v.particle_random_4) * v.fs * {vis}"
    comps = locked(40, SPIN1 + 0.62, pos)
    return particle("bitterblade_embers", T_SPARK_PINK, comps, frame_uv(frames(k, 4), 8, 8, horizontal=False), [sz, sz],
                    tinting={"color": ["v.particle_random_2 < 0.35 ? 0.78 : 1", "v.particle_random_2 < 0.35 ? 0.6 : 0.55",
                                       "v.particle_random_2 < 0.35 ? 1 : 0.86", f"1 - {k} * {k}"]})


# ---------------------------------------------------------------- Ceruledge's blades
FOLLOW_END = REC1 + 0.4                      # the blades' path curves run to here (back at rest after REC1)


def follow_curves():
    return blade_curves(f"v.particle_age + {r(T_IN)}", 0.0, FOLLOW_END, 0.02)


def glow_vis():
    """The pink glow: up from IGNITE, hidden while the blades whirl (the ribbon takes over), back for the
    lunge, fading once it is back in its stance."""
    on = f"math.clamp((v.tt - {IGNITE}) / 0.08, 0, 1)"
    spin_out = f"math.clamp(({SPIN0 + 0.05} - v.tt) * 25, 0, 1)"
    spin_back = f"math.clamp((v.tt - {SPIN1 - 0.03}) * 25, 0, 1)"
    fade = f"math.clamp(({REC1 + 0.2} - v.tt) / 0.35, 0, 1)"
    return f"{on} * math.max({spin_out}, {spin_back}) * {fade}"


def p_bladeglow():
    """A hot-pink sheath of light along both blades (SV: the blades blaze pink for the whole move)."""
    u = "(0.3 + 0.7 * v.particle_random_2)"
    update = ["v.sd = v.particle_random_1 < 0.5"] + blade_point(u)
    flick = "(1 + 0.18 * math.sin(v.tt * (700 + 500 * v.particle_random_3) + 360 * v.particle_random_4))"
    jit = "(0.035 * v.bs)"
    pos = [f"v.px + {jit} * (v.particle_random_3 - 0.5)", f"v.py + {jit} * (v.particle_random_4 - 0.5)", "v.pz"]
    vis = glow_vis()
    sz = f"(0.24 + 0.12 * v.particle_random_3) * v.bs * {flick} * {vis}"
    comps = locked(24, FOLLOW_END, pos, update)
    return particle("bitterblade_bladeglow", T_GLOW, comps, UV_GLOW, [sz, sz], curves=follow_curves(),
                    tinting={"color": [1, "0.36 + 0.16 * v.particle_random_2", "0.82 + 0.1 * v.particle_random_2",
                                       f"0.4 * {flick}"]})


def p_bladecore():
    """The white-hot core of the blades' glow."""
    u = "(0.34 + 0.62 * v.particle_random_2)"
    update = ["v.sd = v.particle_random_1 < 0.5"] + blade_point(u)
    vis = glow_vis()
    sz = f"(0.1 + 0.04 * v.particle_random_3) * v.bs * {vis}"
    comps = locked(14, FOLLOW_END, ["v.px", "v.py", "v.pz"], update)
    return particle("bitterblade_bladecore", T_GLOW, comps, UV_GLOW, [sz, sz], curves=follow_curves(),
                    tinting={"color": [1, 0.9, 0.97, 0.85]})


FLAME0, FLAME1 = IGNITE + 0.03, SPIN0 + 0.04


def p_bladeflames():
    """Blue ghost flames licking up off both blades while the fire builds: each is born on the blade where
    it was at that moment (curves of the birth time) and rises from there."""
    tb = f"({FLAME0} + {r(FLAME1 - FLAME0)} * v.particle_random_1)"
    u = "(0.3 + 0.7 * v.particle_random_3)"
    update = ["v.sd = v.particle_random_2 < 0.5"] + blade_point(u)
    life = "(0.26 + 0.1 * v.particle_random_4)"
    since = f"(v.tt - {tb})"
    k = f"math.clamp({since} / {life}, 0, 1)"
    rise = f"(0.75 * {since} + 1.6 * {since} * {since}) * v.bs"
    sway = f"0.05 * v.bs * math.sin(900 * {since} + 360 * v.particle_random_4)"
    pos = [f"v.px + {sway}", f"v.py + 0.03 * v.bs + {rise}", "v.pz"]
    vis = window(since, life)
    w = f"(0.17 + 0.07 * v.particle_random_4) * v.bs * math.sin(180 * math.min({k} * 1.3, 1)) * {vis}"
    comps = locked(80, FLAME1 + 0.4, pos, update)
    return particle("bitterblade_bladeflames", T_WISP, comps, wisp_frame(since), [w, f"{w} * 1.44"],
                    curves=blade_curves(tb, FLAME0, FLAME1, 0.02),
                    tinting={"color": [1, "v.particle_random_3 > 0.75 ? 0.62 : 1", 1, f"0.95 * (1 - {k} * {k})"]})


# ---------------------------------------------------------------- the spin (Ceruledge): what the blades leave behind
SPIN_TB = f"({SPIN0} + {r(SPIN1 - SPIN0)} * v.particle_random_2)"   # when the blade passed this spot


def spin_point(u):
    return ["v.sd = v.particle_random_1 < 0.5"] + blade_point(u) + [
        "v.pr = math.max(math.sqrt(v.px * v.px + v.pz * v.pz), 0.01)",
        "v.ox = v.px / v.pr", "v.oz = v.pz / v.pr",          # outward
        "v.wx = -v.oz", "v.wz = v.ox"]                        # the way the blade moves


def p_spinarc():
    """The slash: a ribbon of hot pink light along the swept blades, lit where each blade passed and
    fading behind it; violet near the hands, white-pink at the points."""
    u = "(0.26 + 0.74 * math.sqrt(v.particle_random_3))"
    life = f"(0.08 + 0.1 * {u})"
    since = f"(v.tt - {SPIN_TB})"
    k = f"math.clamp({since} / {life}, 0, 1)"
    drift = f"0.6 * v.bs * {since}"
    pos = [f"v.px + v.ox * {drift}", f"v.py - 0.2 * v.bs * {since}", f"v.pz + v.oz * {drift}"]
    vis = window(since, life, 0.02)
    sz = f"(0.17 + 0.17 * {u}) * v.bs * (1 - 0.45 * {k}) * {vis}"
    comps = locked(170, SPIN1 + 0.25, pos, spin_point(u))
    return particle("bitterblade_spinarc", T_GLOW, comps, UV_GLOW, [sz, sz],
                    curves=blade_curves(SPIN_TB, SPIN0, SPIN1, 0.004),
                    tinting=ramp(u, [(0.26, VIOLET), (0.6, MAGENTA), (0.88, PINK_HOT), (1.0, PINK_PALE)],
                                 f"0.78 * (1 - {k} * {k})"))


def p_spinedge():
    """Bright streaks on the cutting edge near the points, drawn along the way the blade moves."""
    u = "(0.82 + 0.18 * v.particle_random_3)"
    life = "0.1"
    since = f"(v.tt - {SPIN_TB})"
    k = f"math.clamp({since} / {life}, 0, 1)"
    move = f"0.3 * v.bs * ({since} + 0.01 * v.particle_age)"   # a small drift along the motion orients the streak
    pos = [f"v.px + v.wx * {move}", "v.py", f"v.pz + v.wz * {move}"]
    vis = window(since, life, 0.02)
    comps = locked(56, SPIN1 + 0.2, pos, spin_point(u))
    return particle("bitterblade_spinedge", T_BEAM, comps, UV_BEAM,
                    [f"0.55 * v.bs * (1 - 0.5 * {k}) * {vis}", f"0.05 * v.bs * {vis}"], camera="lookat_direction",
                    curves=blade_curves(SPIN_TB, SPIN0, SPIN1, 0.004),
                    tinting={"color": [1, f"0.85 - 0.35 * {k}", f"0.96 - 0.1 * {k}", f"0.95 * (1 - {k})"]})


def p_spinflames():
    """Ghost fire flung off the whirling blades: blue puffs thrown along and out from the blade."""
    u = "(0.5 + 0.5 * v.particle_random_3)"
    life = "(0.26 + 0.1 * v.particle_random_4)"
    since = f"(v.tt - {SPIN_TB})"
    k = f"math.clamp({since} / {life}, 0, 1)"
    fly = f"v.bs * (1.6 * {since} - 2.2 * {since} * {since})"
    pos = [f"v.px + (0.9 * v.wx + 0.7 * v.ox) * {fly}", f"v.py + 0.5 * v.bs * {since}",
           f"v.pz + (0.9 * v.wz + 0.7 * v.oz) * {fly}"]
    vis = window(since, life, 0.03)
    w = f"(0.17 + 0.08 * v.particle_random_4) * v.bs * (1 - 0.35 * {k}) * {vis}"
    comps = locked(44, SPIN1 + 0.4, pos, spin_point(u))
    return particle("bitterblade_spinflames", T_WISP, comps, wisp_frame(since), [w, f"{w} * 1.44"],
                    curves=blade_curves(SPIN_TB, SPIN0, SPIN1, 0.004),
                    tinting={"color": [1, "v.particle_random_2 < 0.25 ? 0.65 : 1", 1, f"0.95 * (1 - {k} * {k})"]})


# ---------------------------------------------------------------- the spin (any other species): a slash ring
def yaw_curve(inp, lo, hi, step):
    n = int(round((hi - lo) / step)) + 1
    return {"variable.bb_yaw": {"type": "linear", "input": f"({inp}) - {r(lo)}", "horizontal_range": r(hi - lo, 4),
                                "nodes": [r(ROOT_YAW(lo + i * (hi - lo) / (n - 1))[0], 2) for i in range(n)]}}


def ring_point(u):
    """A point of the slash ring of a Pokemon without blades: from just outside its body out to a blade's
    reach, at chest height, turning with the body (the left side comes to the front as the yaw grows)."""
    return ["v.sd = v.particle_random_1 < 0.5",
            f"v.rin = 0.5 * v.entity_width + 0.12",
            f"v.rad = v.rin + {u} * 0.9 * v.fs",
            "v.ox = (v.sd ? -1 : 1) * math.cos(v.bb_yaw)", "v.oz = (v.sd ? -1 : 1) * math.sin(v.bb_yaw)",
            "v.px = v.rad * v.ox", "v.py = 0.55 * math.min(v.entity_height, 3.2)", "v.pz = v.rad * v.oz",
            "v.wx = -v.oz", "v.wz = v.ox"]


def p_ringarc():
    u = "math.sqrt(v.particle_random_3)"
    life = f"(0.08 + 0.1 * {u})"
    since = f"(v.tt - {SPIN_TB})"
    k = f"math.clamp({since} / {life}, 0, 1)"
    drift = f"0.6 * v.fs * {since}"
    pos = [f"v.px + v.ox * {drift}", f"v.py - 0.2 * v.fs * {since}", f"v.pz + v.oz * {drift}"]
    vis = window(since, life, 0.02)
    sz = f"(0.17 + 0.17 * {u}) * v.fs * 0.75 * (1 - 0.45 * {k}) * {vis}"
    comps = locked(150, SPIN1 + 0.25, pos, ring_point(u))
    return particle("bitterblade_ringarc", T_GLOW, comps, UV_GLOW, [sz, sz],
                    curves=yaw_curve(SPIN_TB, SPIN0, SPIN1, 0.004),
                    tinting=ramp(u, [(0.0, VIOLET), (0.45, MAGENTA), (0.85, PINK_HOT), (1.0, PINK_PALE)],
                                 f"0.78 * (1 - {k} * {k})"))


def p_ringflames():
    u = "(0.4 + 0.6 * v.particle_random_3)"
    life = "(0.26 + 0.1 * v.particle_random_4)"
    since = f"(v.tt - {SPIN_TB})"
    k = f"math.clamp({since} / {life}, 0, 1)"
    fly = f"v.fs * (1.4 * {since} - 2 * {since} * {since})"
    pos = [f"v.px + (0.9 * v.wx + 0.7 * v.ox) * {fly}", f"v.py + 0.5 * v.fs * {since}",
           f"v.pz + (0.9 * v.wz + 0.7 * v.oz) * {fly}"]
    vis = window(since, life, 0.03)
    w = f"(0.16 + 0.08 * v.particle_random_4) * v.fs * (1 - 0.35 * {k}) * {vis}"
    comps = locked(36, SPIN1 + 0.4, pos, ring_point(u))
    return particle("bitterblade_ringflames", T_WISP, comps, wisp_frame(since), [w, f"{w} * 1.44"],
                    curves=yaw_curve(SPIN_TB, SPIN0, SPIN1, 0.004),
                    tinting={"color": [1, "v.particle_random_2 < 0.25 ? 0.65 : 1", 1, f"0.95 * (1 - {k} * {k})"]})


def p_auraflames():
    """Any other species: ghost flames lick up its body instead of off blades."""
    tb = f"({FLAME0} + {r(FLAME1 - FLAME0)} * v.particle_random_1)"
    life = "(0.28 + 0.1 * v.particle_random_4)"
    since = f"(v.tt - {tb})"
    k = f"math.clamp({since} / {life}, 0, 1)"
    ang = "(360 * v.particle_random_2)"
    rad = "(0.5 * v.entity_width + 0.08)"
    pos = [f"{rad} * math.cos({ang})", f"v.entity_height * (0.3 + 0.6 * v.particle_random_3) + 0.9 * v.fs * {since}",
           f"{rad} * math.sin({ang})"]
    vis = window(since, life)
    w = f"(0.2 + 0.08 * v.particle_random_4) * v.fs * math.sin(180 * math.min({k} * 1.3, 1)) * {vis}"
    comps = locked(50, FLAME1 + 0.42, pos)
    return particle("bitterblade_auraflames", T_WISP, comps, wisp_frame(since), [w, f"{w} * 1.44"],
                    tinting={"color": [1, "v.particle_random_3 > 0.75 ? 0.62 : 1", 1, f"0.95 * (1 - {k} * {k})"]})


# ---------------------------------------------------------------- the slash leaves the blade (both)
# Where the right blade's point crosses the front at RELEASE, as a share of the body: the generic version
# puts it at the same share of any Pokemon's size (checked against Ceruledge's own rig in main()).
REL_H, REL_F = 0.48, 0.75


def p_releaseflash():
    """A white-cyan flash where the slash leaves the blade (spawned with the slash by the action effect, so
    it sits where the slash really starts)."""
    since = f"(v.te - {RELEASE})"
    k = f"math.clamp({since} / 0.12, 0, 1)"
    vis = window(since, 0.12, 0.02)
    sz = f"0.85 * v.fs * (0.8 + 0.5 * {k}) * {vis}"
    comps = wave_emitter(1, RELEASE + 0.15 - EMIT_LAG, ["v.sx", "v.sy", "v.sz"], wave_frame(False))
    return particle("bitterblade_releaseflash", T_GLOW, comps, UV_GLOW, [sz, sz],
                    tinting={"color": [f"1 - 0.3 * {k}", f"1 - 0.1 * {k}", 1, f"0.9 * (1 - {k} * {k})"]})


# ================================================================= 2. the slash crossing to the target (action effect)
# Spawned by the action effect with the battle's target locator: in its parametric frame -z is forward
# and the target's 'target' locator is at (-dx, dy, -dz). A particle of age a stands for move time
# a + EMIT_LAG.
WAVE_DEFAULTS = ENTITY_DEFAULTS + " v.target_deltax = 0; v.target_deltay = 1; v.target_deltaz = 4;"
WAVE_FL = r(IMPACT - RELEASE)


def wave_frame(miss):
    """Per-update lines: start/end of the flight, unit forward v.f*, the crescent's diagonal axis v.a*, and
    the head's centre v.c* at flight share v.s (0 at the blade, 1 at the target)."""
    lines = SIZES[:2] + [
        f"v.te = v.particle_age + {EMIT_LAG}",
        "v.hd = math.sqrt(v.target_deltax * v.target_deltax + v.target_deltaz * v.target_deltaz)",
        "v.sx = 0", f"v.sy = {REL_H} * v.entity_height",
        f"v.sz = -math.min(0.5 * v.entity_width + {REL_F} * v.bl, 0.45 * v.hd)",
        "v.ex = -v.target_deltax", "v.ey = v.target_deltay", "v.ez = -v.target_deltaz",
        "v.fx = v.ex - v.sx", "v.fy = v.ey - v.sy", "v.fz = v.ez - v.sz",
        "v.fl = math.max(math.sqrt(v.fx * v.fx + v.fy * v.fy + v.fz * v.fz), 0.01)",
        "v.fx = v.fx / v.fl", "v.fy = v.fy / v.fl", "v.fz = v.fz / v.fl",
        "v.fh = math.max(math.sqrt(v.fx * v.fx + v.fz * v.fz), 0.01)",
        "v.ax = -0.82 * v.fz / v.fh", "v.ay = 0.57", "v.az = 0.82 * v.fx / v.fh",
        "v.fxw = math.clamp(0.6 + 0.35 * v.bl, 0.8, 1.5)",
    ]
    if miss:
        # veers off to the side and keeps going past the target
        lines += ["v.ex = v.ex + 1.4 * v.fx - 1.1 * v.fz / v.fh", "v.ey = v.ey + 0.35",
                  "v.ez = v.ez + 1.4 * v.fz + 1.1 * v.fx / v.fh"]
    return lines


def wave_centre(s):
    return [f"(v.sx + (v.ex - v.sx) * {s})", f"(v.sy + (v.ey - v.sy) * {s})", f"(v.sz + (v.ez - v.sz) * {s})"]


def wave_emitter(count, life, pos, update):
    return {
        "minecraft:emitter_initialization": {"creation_expression": WAVE_DEFAULTS},
        "minecraft:emitter_rate_instant": {"num_particles": count},
        "minecraft:emitter_lifetime_once": {"active_time": 0.1},
        "minecraft:emitter_shape_point": {},
        "minecraft:particle_initialization": {"per_update_expression": ";".join(update) + ";"},
        "minecraft:particle_lifetime_expression": {"max_lifetime": r(life)},
        "minecraft:particle_initial_speed": 0,
        "minecraft:particle_motion_parametric": {"relative_position": pos},
    }


def p_wave(miss):
    """The slash itself: a scimitar-shaped crescent of pale cyan light, diagonal, flying blade-first."""
    span = 1.3 if miss else 1.0
    s = f"math.clamp((v.te - {RELEASE}) / {WAVE_FL}, 0, {span})"
    al = "((v.particle_random_1 - 0.5) * 150)"
    rad = "(0.62 * v.fxw)"
    c = wave_centre(s)
    jit = "0.04 * (v.particle_random_3 - 0.5)"
    pos = [f"{c[0]} + {rad} * math.sin({al}) * v.ax + {rad} * (math.cos({al}) - 1) * 0.55 * v.fx + {jit}",
           f"{c[1]} + {rad} * math.sin({al}) * v.ay + {rad} * (math.cos({al}) - 1) * 0.55 * v.fy",
           f"{c[2]} + {rad} * math.sin({al}) * v.az + {rad} * (math.cos({al}) - 1) * 0.55 * v.fz + {jit}"]
    if miss:
        vis = f"math.clamp((v.te - {RELEASE}) * 60, 0, 1) * math.clamp(({RELEASE + WAVE_FL * span} - v.te) * 12, 0, 1)"
        life = RELEASE + WAVE_FL * span + 0.05 - EMIT_LAG
    else:
        vis = f"math.clamp((v.te - {RELEASE}) * 60, 0, 1) * math.clamp(({IMPACT} - v.te) * 60, 0, 1)"
        life = IMPACT + 0.03 - EMIT_LAG
    mid = "(1 - math.abs(v.particle_random_1 - 0.5) * 2)"     # 1 in the middle of the crescent, 0 at its tips
    sz = f"(0.16 + 0.14 * {mid}) * v.fxw * {vis}"
    comps = wave_emitter(40, life, pos, wave_frame(miss))
    return particle(f"bitterblade_wave{'_miss' if miss else ''}", T_GLOW, comps, UV_GLOW, [sz, sz],
                    tinting=ramp(mid, [(0.0, CYAN), (0.5, ICE), (1.0, WHITE)], "0.95"))


def p_wavetrail(miss):
    """Streaks left along the flight, each lit as the slash passes it."""
    span = 1.3 if miss else 1.0
    s = f"(v.particle_random_1 * {span})"
    born = f"({RELEASE} + {WAVE_FL} * {s})"
    since = f"math.max(v.te - {born}, 0)"
    c = wave_centre(s)
    off = "(0.62 * v.fxw * (v.particle_random_2 - 0.5) * 1.4)"
    move = f"2.5 * ({since} + 0.01 * v.particle_age)"
    pos = [f"{c[0]} + {off} * v.ax + v.fx * {move}", f"{c[1]} + {off} * v.ay + v.fy * {move}",
           f"{c[2]} + {off} * v.az + v.fz * {move}"]
    vis = f"math.clamp((v.te - {born}) * 60, 0, 1) * math.clamp(1 - {since} / 0.14, 0, 1)"
    if miss:
        vis += f" * math.clamp(({span} - {s}) * 4, 0, 1)"
    life = RELEASE + WAVE_FL * span + 0.18 - EMIT_LAG
    comps = wave_emitter(26, life, pos, wave_frame(miss))
    return particle(f"bitterblade_wavetrail{'_miss' if miss else ''}", T_BEAM, comps, UV_BEAM,
                    [f"(0.5 + 0.3 * v.particle_random_4) * v.fxw * {vis}", f"0.06 * v.fxw * {vis}"],
                    camera="lookat_direction", tinting=gradient("v.particle_random_4", [(0.0, WHITE), (0.5, ICE), (1.0, CYAN)]))


def p_waveflames(miss):
    """Blue ghost fire shed along the flight, hanging a moment and rising away."""
    span = 1.3 if miss else 1.0
    s = f"(v.particle_random_1 * {span})"
    born = f"({RELEASE} + {WAVE_FL} * {s})"
    since = f"(v.te - {born})"
    life = "(0.3 + 0.1 * v.particle_random_4)"
    k = f"math.clamp({since} / {life}, 0, 1)"
    c = wave_centre(s)
    off = "(0.62 * v.fxw * (v.particle_random_2 - 0.5) * 1.6)"
    pos = [f"{c[0]} + {off} * v.ax", f"{c[1]} + {off} * v.ay + 0.7 * math.max({since}, 0)", f"{c[2]} + {off} * v.az"]
    vis = window(since, life)
    if miss:
        vis += f" * math.clamp(({span} - {s}) * 4, 0, 1)"
    w = f"(0.2 + 0.08 * v.particle_random_3) * v.fxw * math.sin(180 * math.min({k} * 1.3, 1)) * {vis}"
    life_all = RELEASE + WAVE_FL * span + 0.45 - EMIT_LAG
    comps = wave_emitter(22, life_all, pos, wave_frame(miss))
    return particle(f"bitterblade_waveflames{'_miss' if miss else ''}", T_WISP, comps, wisp_frame(since), [w, f"{w} * 1.44"],
                    tinting={"color": [1, 1, 1, f"0.9 * (1 - {k} * {k})"]})


# ================================================================= 3. the cut (target animation, 'target' locator)
TFRONT = "(0.25 * v.entity_width)"      # on the target's face that took the hit (-z faces the attacker)
FXT = "math.clamp(0.55 + 0.4 * math.max(v.entity_width, v.entity_height), 0.7, 1.8)"
CUT_DIR = (0.62, 0.7, -0.35)             # the diagonal of the cut, in the target's frame
_n = math.sqrt(sum(c * c for c in CUT_DIR))
CUT_DIR = tuple(r(c / _n, 3) for c in CUT_DIR)
AT = (0, 0, f"-{TFRONT}")


def burst(count, active=0.1):
    return {"minecraft:emitter_initialization": {"creation_expression": ENTITY_DEFAULTS},
            "minecraft:emitter_rate_instant": {"num_particles": count},
            "minecraft:emitter_lifetime_once": {"active_time": active}}


def still(life):
    return {"minecraft:particle_lifetime_expression": {"max_lifetime": life},
            "minecraft:particle_initial_speed": 0,
            "minecraft:particle_motion_dynamic": {}}


def p_cutline(core):
    """The long diagonal cut across the target (SV): a thin white line in a wider cyan glow, thinning out."""
    life = 0.22 if core else 0.28
    length = f"(1.5 + 0.8 * math.max(v.entity_width, v.entity_height))"
    # A streak points the way it moves. It is spawned a hair back along the line (shape offsets have x
    # mirrored) so it already moves along it on its first tick, then drifts on.
    drift = "(0.02 * v.particle_age)"
    eps = 0.003
    comps = dict(burst(1), **{
        "minecraft:emitter_shape_point": {"offset": [r(eps * CUT_DIR[0]), r(-eps * CUT_DIR[1]),
                                                     f"-{TFRONT} - {r(eps * CUT_DIR[2])}"]},
        "minecraft:particle_lifetime_expression": {"max_lifetime": life},
        "minecraft:particle_initial_speed": 0,
        "minecraft:particle_motion_parametric": {"relative_position": [
            f"{CUT_DIR[0]} * {drift}", f"{CUT_DIR[1]} * {drift}", f"-{TFRONT} + {CUT_DIR[2]} * {drift}"]}})
    grow = f"math.min({K} * 8, 1)"
    if core:
        size = [f"{length} * 0.95 * (0.6 + 0.4 * {grow})", f"0.1 * {FXT} * (1 - {K})"]
        tint = {"color": [1, 1, 1, f"1 - {K} * {K}"]}
    else:
        size = [f"{length} * (0.6 + 0.4 * {grow})", f"0.3 * {FXT} * (1 - 0.6 * {K})"]
        tint = gradient(K, [(0.0, '#B0BFF4FF'), (0.6, '#807FD8FF'), (1.0, '#004A5CFF')])
    return particle(f"bitterblade_cut{'core' if core else 'glow'}", T_BEAM, comps, UV_BEAM, size,
                    camera="lookat_direction", tinting=tint)


def p_cutflash():
    comps = dict(burst(1), **{"minecraft:emitter_shape_point": {"offset": AT}}, **still(0.14))
    sz = f"1.0 * {FXT} * (0.85 + 0.5 * (1 - math.pow(1 - {K}, 3)))"
    return particle("bitterblade_cutflash", T_GLOW, comps, UV_GLOW, [sz, sz],
                    tinting={"color": [f"1 - 0.15 * {K}", 1, 1, f"1 - {K} * {K}"]})


def p_cuthalo():
    comps = dict(burst(1), **{"minecraft:emitter_shape_point": {"offset": AT}}, **still(0.24))
    sz = f"2.2 * {FXT} * (0.8 + 0.35 * {K})"
    return particle("bitterblade_cuthalo", T_GLOW, comps, UV_GLOW, [sz, sz],
                    tinting=gradient(K, [(0.0, '#C0CFF4FF'), (0.5, '#907FD8FF'), (1.0, '#004A5CFF')]))


def p_cutstar():
    comps = dict(burst(1), **{"minecraft:emitter_shape_point": {"offset": AT}}, **still(0.2))
    sz = f"1.6 * {FXT}"
    return particle("bitterblade_cutstar", T_HIT, comps, flipbook(32, 32, 5, horizontal=False), [sz, sz],
                    tinting=gradient(K, [(0.0, WHITE), (0.5, ICE), (1.0, CYAN)]))


def cut_spot():
    """A point along the cut line (v.particle_random_1) and a direction away from the line (v.n*)."""
    along = f"(v.particle_random_1 - 0.5) * (1.3 + 0.7 * math.max(v.entity_width, v.entity_height))"
    d = sphere_dir("(360 * v.particle_random_3)")
    dot = f"({d[0]} * {CUT_DIR[0]} + {d[1]} * {CUT_DIR[1]} + {d[2]} * {CUT_DIR[2]})"
    n = [f"({d[i]} - {dot} * {CUT_DIR[i]})" for i in range(3)]
    base = [f"{along} * {CUT_DIR[0]}", f"{along} * {CUT_DIR[1]}", f"-{TFRONT} + {along} * {CUT_DIR[2]}"]
    return base, n


def p_cutshards():
    """Blue flame shards scattering off the length of the cut, cooling to deep indigo."""
    base, n = cut_spot()
    dist = f"{FXT} * 0.9 * (1 - math.pow(1 - {K}, 2.2)) * (0.5 + 0.6 * v.particle_random_4)"
    pos = [f"{base[i]} + {n[i]} * {dist}" + (f" + 0.25 * {K}" if i == 1 else "") for i in range(3)]
    comps = dict(burst(18), **{
        "minecraft:emitter_shape_point": {},
        "minecraft:particle_lifetime_expression": {"max_lifetime": "0.4 + 0.16 * v.particle_random_2"},
        "minecraft:particle_initial_speed": 0,
        "minecraft:particle_motion_parametric": {"relative_position": pos},
        "minecraft:particle_initial_spin": SPIN_ICON})
    appear = "math.clamp((v.particle_age - 0.05) * 30, 0, 1)"     # just after the cut and the flash
    sz = f"(0.17 + 0.1 * v.particle_random_4) * {FXT} * (1 - 0.5 * {K}) * {appear}"
    return particle("bitterblade_cutshards", T_PUFF, comps, puff_frame(K, 3, 9), [sz, sz],
                    tinting=ramp(K, [(0.0, ICE), (0.25, PERIWINKLE), (0.6, COBALT), (1.0, INDIGO)],
                                 f"0.75 * (1 - {K} * {K})"))


def p_cutwisps():
    """Ghost flames flaring out of the cut and rising away."""
    base, n = cut_spot()
    dist = f"{FXT} * 0.45 * (1 - math.pow(1 - {K}, 2))"
    pos = [f"{base[i]} + {n[i]} * {dist}" + (f" + 0.55 * {FXT} * {K}" if i == 1 else "") for i in range(3)]
    comps = dict(burst(14), **{
        "minecraft:emitter_shape_point": {},
        "minecraft:particle_lifetime_expression": {"max_lifetime": "0.4 + 0.15 * v.particle_random_2"},
        "minecraft:particle_initial_speed": 0,
        "minecraft:particle_motion_parametric": {"relative_position": pos}})
    w = f"(0.2 + 0.08 * v.particle_random_4) * {FXT} * math.sin(180 * math.min({K} * 1.3, 1)) * math.clamp((v.particle_age - 0.04) * 30, 0, 1)"
    return particle("bitterblade_cutwisps", T_WISP, comps, wisp_frame("v.particle_age"), [w, f"{w} * 1.44"],
                    tinting={"color": [1, 1, 1, f"0.95 * (1 - {K} * {K})"]})


def p_cutsparks():
    comps = dict(burst(18), **{
        "minecraft:emitter_shape_sphere": {"offset": AT, "radius": f"0.15 * {FXT}", "surface_only": True,
                                           "direction": "outwards"},
        "minecraft:particle_lifetime_expression": {"max_lifetime": "0.3 + 0.2 * v.particle_random_1"},
        "minecraft:particle_initial_speed": f"(4.5 + 3.5 * v.particle_random_2) * {FXT}",
        "minecraft:particle_motion_dynamic": {"linear_acceleration": [0, -4.5, 0], "linear_drag_coefficient": 3.2}})
    sz = f"(0.1 + 0.05 * v.particle_random_3) * {FXT} * (0.4 + 0.6 * (1 - {K}))"
    return particle("bitterblade_cutsparks", T_SPARK_CYAN, comps, frame_uv(frames(K, 4), 8, 8, horizontal=False), [sz, sz],
                    tinting={"color": [1, 1, 1, 1]})


def p_cutembers():
    """Dark blue embers drifting up where the cut was, after the flash."""
    base, n = cut_spot()
    pos = [f"{base[i]} + {n[i]} * 0.25 * {FXT} * {K}" + (f" + 0.6 * {FXT} * {K}" if i == 1 else "") for i in range(3)]
    comps = dict(burst(14), **{
        "minecraft:emitter_shape_point": {},
        "minecraft:particle_lifetime_expression": {"max_lifetime": "0.55 + 0.25 * v.particle_random_2"},
        "minecraft:particle_initial_speed": 0,
        "minecraft:particle_motion_parametric": {"relative_position": pos}})
    w = f"(0.12 + 0.05 * v.particle_random_4) * {FXT} * (1 - {K})"
    return particle("bitterblade_cutembers", T_WISP, comps, wisp_frame("v.particle_age"), [w, f"{w} * 1.44"],
                    tinting=ramp(K, [(0.0, WHITE), (1.0, '#FF5050C0')], f"0.85 * (1 - {K} * {K})"))


# ================================================================= 4. the drain (action effect, user root + target locator)
DRAIN_DEFAULTS = WAVE_DEFAULTS


def orb_frame():
    """Per-update lines: the orb's flight from the target (v.o*) to the user's chest (v.u*) along a curve
    that bows up and to the side, and its position v.c* now."""
    return SIZES[:2] + [
        f"v.te = v.particle_age + {EMIT_LAG}",
        "v.ox = -v.target_deltax", "v.oy = v.target_deltay + 0.05", "v.oz = -v.target_deltaz",
        "v.ux = 0", "v.uy = 0.55 * math.min(v.entity_height, 3.2)", "v.uz = -0.2 * v.entity_width",
        "v.dl = math.max(math.sqrt(math.pow(v.ox - v.ux, 2) + math.pow(v.oz - v.uz, 2)), 0.01)",
        "v.qx = (v.ox + v.ux) / 2 + 0.2 * v.dl * (v.oz - v.uz) / v.dl",
        "v.qy = (v.oy + v.uy) / 2 + 0.18 * v.dl + 0.3",
        "v.qz = (v.oz + v.uz) / 2 - 0.2 * v.dl * (v.ox - v.ux) / v.dl",
        f"v.fk = math.clamp((v.te - {FLY0}) / {r(FLY1 - FLY0)}, 0, 1)",
        "v.s = v.fk * v.fk * (3 - 2 * v.fk)",
        "v.cx = (1 - v.s) * (1 - v.s) * v.ox + 2 * (1 - v.s) * v.s * v.qx + v.s * v.s * v.ux",
        "v.cy = (1 - v.s) * (1 - v.s) * v.oy + 2 * (1 - v.s) * v.s * v.qy + v.s * v.s * v.uy"
        " + 0.04 * math.sin(v.te * 720) * (1 - v.fk)",
        "v.cz = (1 - v.s) * (1 - v.s) * v.oz + 2 * (1 - v.s) * v.s * v.qz + v.s * v.s * v.uz",
    ]


ORB_VIS = (f"math.clamp((v.te - {ORB0}) / 0.12, 0, 1) * (v.te < {ARRIVE} ? 1 : math.clamp(1 - (v.te - {ARRIVE}) / 0.06, 0, 1))")


def p_orb(core):
    """The drained energy: a glowing mint orb (a white-mint core in a soft mint halo, SV's drain colour)."""
    n = 5 if core else 1
    jit = "0.05 * (v.particle_random_{} - 0.5)"
    pos = [f"v.cx + {jit.format(1)}", f"v.cy + {jit.format(2)}", f"v.cz + {jit.format(3)}"] if core else ["v.cx", "v.cy", "v.cz"]
    pulse = "(1 + 0.12 * math.sin(v.te * 1100))"
    grow = f"(0.5 + 0.5 * math.clamp((v.te - {ORB0}) / 0.16, 0, 1))"
    if core:
        sz = f"0.3 * {grow} * {pulse} * {ORB_VIS}"
        tint = {"color": [0.94, 1, 0.96, 0.9]}
    else:
        sz = f"0.95 * {grow} * {pulse} * {ORB_VIS}"
        tint = {"color": [0.56, 0.94, 0.75, f"0.55 * {ORB_VIS}"]}
    comps = wave_emitter(n, ARRIVE + 0.1 - EMIT_LAG, pos, orb_frame())
    return particle(f"bitterblade_orb{'core' if core else 'halo'}", T_GLOW, comps, UV_GLOW, [sz, sz], tinting=tint)


def p_orbsparks():
    """Energy torn out of the target: pink and violet sparks spiralling into the orb as it forms, turning
    mint as they arrive."""
    t0 = f"({ORB0 - 0.08} + 0.1 * v.particle_random_4)"
    k = f"math.clamp((v.te - {t0}) / 0.2, 0, 1)"
    d = sphere_dir(f"(360 * v.particle_random_1 + 220 * {k})")
    rad = f"(0.55 + 0.4 * v.particle_random_3) * (1 - {k})"
    pos = [f"v.ox + {rad} * {d[0]}", f"v.oy + {rad} * {d[1]}", f"v.oz + {rad} * {d[2]}"]
    vis = f"math.clamp((v.te - {t0}) * 30, 0, 1) * math.clamp((1 - {k}) * 10, 0, 1)"
    sz = f"(0.09 + 0.04 * v.particle_random_3) * {vis}"
    comps = wave_emitter(16, ORB0 + 0.3 - EMIT_LAG, pos, orb_frame())
    return particle("bitterblade_orbsparks", T_STAR, comps, UV_STAR, [sz, sz],
                    tinting=ramp(k, [(0.0, '#FFFF7FD8'), (0.5, VIOLET), (1.0, MINT)], "1"))


def p_orbtrail():
    """White and mint sparkles left along the orb's flight, sinking a little as they fade."""
    tb = f"({FLY0} + {r(FLY1 - FLY0)} * v.particle_random_1)"
    since = f"(v.te - {tb})"
    life = "(0.3 + 0.1 * v.particle_random_4)"
    k = f"math.clamp({since} / {life}, 0, 1)"
    fk = f"math.clamp(({tb} - {FLY0}) / {r(FLY1 - FLY0)}, 0, 1)"
    s = f"({fk} * {fk} * (3 - 2 * {fk}))"
    pt = [f"(1 - {s}) * (1 - {s}) * v.o{a} + 2 * (1 - {s}) * {s} * v.q{a} + {s} * {s} * v.u{a}" for a in 'xyz']
    jit = "0.09 * (v.particle_random_{} - 0.5)"
    pos = [f"{pt[0]} + {jit.format(2)}", f"{pt[1]} + {jit.format(3)} - 0.25 * math.max({since}, 0)", f"{pt[2]} + {jit.format(2)}"]
    vis = window(since, life, 0.02)
    sz = f"(0.07 + 0.05 * v.particle_random_3) * (1 - 0.5 * {k}) * {vis}"
    comps = wave_emitter(40, FLY1 + 0.45 - EMIT_LAG, pos, orb_frame())
    return particle("bitterblade_orbtrail", T_SPARK, comps, frame_uv(frames(k, 4), 8, 8, horizontal=False), [sz, sz],
                    tinting={"color": ["v.particle_random_2 < 0.5 ? 1 : 0.7", 1, "v.particle_random_2 < 0.5 ? 1 : 0.85",
                                       f"1 - {k} * {k}"]})


# ================================================================= 5. the heal (heal animation, user root locator)
HEAL_SIZES = SIZES + [
    "v.rr = math.max(0.55 * v.bl, 0.4) + 0.08",      # a ball just outside the body
    "v.cy = 0.5 * v.entity_height",
]


def heal_locked(count, end_time, pos, update=()):
    comps = locked(count, end_time, pos, update)
    comps["minecraft:particle_initialization"] = {"per_update_expression": ";".join(HEAL_SIZES + list(update)) + ";"}
    return comps


def p_absorbring():
    """Two pale mint rings closing in round the user as the energy reaches it (SV)."""
    tb = f"({ARRIVE - 0.02} + (v.particle_random_1 < 0.5 ? 0 : 0.09))"
    since = f"(v.tt - {tb})"
    k = f"math.clamp({since} / 0.2, 0, 1)"
    uv = frame_uv(f"6 - {frames(k, 7)}", 64, 64)
    vis = window(since, 0.2, 0.02)
    sz = f"v.rr * (2.4 - 1.3 * {k} * {k}) * {vis}"
    comps = heal_locked(2, ARRIVE + 0.35, ["0", "0.55 * math.min(v.entity_height, 3.2)", "0"])
    return particle("bitterblade_absorbring", T_RING, comps, uv, [sz, sz],
                    tinting={"color": [0.8, 1, 0.88, f"0.9 * math.clamp({k} * 6, 0, 1) * math.clamp((1 - {k}) * 6, 0, 1)"]})


def surface(count, end_time, size, alpha, col, radius=1.0, update=()):
    d = sphere_dir()
    pos = [f"{radius} * v.rr * {d[0]}", f"v.cy + {radius} * v.rr * {d[1]}", f"{radius} * v.rr * {d[2]}"]
    flick = "(1 + 0.12 * math.sin(v.tt * (900 + 700 * v.particle_random_3) + 360 * v.particle_random_4))"
    sz = f"({size}) * (0.85 + 0.3 * v.particle_random_3) * {flick}"
    return heal_locked(count, end_time, pos, update), [sz, sz], {"color": [col[0], col[1], col[2], f"({alpha}) * {flick}"]}


def p_absorbglow():
    """Mint light flaring over the user's body as it takes the energy in (over the model, whichever side
    it is seen from: a glow at the body's centre would be hidden inside the model)."""
    since = f"(v.tt - {ARRIVE})"
    env = f"math.clamp({since} / 0.05, 0, 1) * math.clamp(1 - ({since} - 0.05) / 0.22, 0, 1)"
    comps, size, tint = surface(14, ARRIVE + 0.3, f"0.75 * v.fs * {env}", f"0.32 * {env}", (0.6, 1, 0.78), 0.85)
    return particle("bitterblade_absorbglow", T_GLOW, comps, UV_GLOW, size, tinting=tint)


def p_healbubble():
    """SV's green heal bubble: a translucent mint sphere of light round the user."""
    since = f"(v.tt - {HEAL})"
    env = f"math.clamp({since} / 0.08, 0, 1) * math.clamp(1 - ({since} - 0.22) / 0.2, 0, 1)"
    comps, size, tint = surface(28, HEAL + 0.45, f"0.95 * v.fs * {env}", f"0.22 * {env}", (0.62, 1, 0.78), 1.08)
    return particle("bitterblade_healbubble", T_GLOW, comps, UV_GLOW, size, tinting=tint)


def p_healrays():
    """White sparkle streaks shooting out of the bubble, mostly upwards."""
    tb = f"({HEAL + 0.02} + 0.1 * v.particle_random_4)"
    since = f"(v.tt - {tb})"
    k = f"math.clamp({since} / 0.24, 0, 1)"
    ang = "(360 * v.particle_random_1)"
    up = "(0.15 + 0.85 * v.particle_random_2)"
    hor = f"math.sqrt(1 - {up} * {up})"
    dist = f"v.rr * (0.7 + 1.1 * (1 - math.pow(1 - {k}, 2)) + 0.01 * v.particle_age)"
    pos = [f"{hor} * math.cos({ang}) * {dist}", f"v.cy + {up} * {dist}", f"{hor} * math.sin({ang}) * {dist}"]
    vis = window(since, 0.24, 0.02)
    comps = heal_locked(14, HEAL + 0.4, pos)
    return particle("bitterblade_healrays", T_BEAM, comps, UV_BEAM,
                    [f"0.42 * v.fs * (1 - 0.6 * {k}) * {vis}", f"0.045 * v.fs * {vis}"], camera="lookat_direction",
                    tinting={"color": [f"1 - 0.25 * {k}", 1, f"1 - 0.15 * {k}", f"1 - {k} * {k}"]})


def p_healstars():
    """Four-point stars twinkling round the bubble (pixel art: kept small so it stays crisp)."""
    tb = f"({HEAL} + 0.24 * v.particle_random_4)"
    since = f"(v.tt - {tb})"
    k = f"math.clamp({since} / 0.3, 0, 1)"
    d = sphere_dir()
    pos = [f"1.15 * v.rr * {d[0]}", f"v.cy + 1.15 * v.rr * {d[1]} + 0.3 * math.max({since}, 0)", f"1.15 * v.rr * {d[2]}"]
    vis = window(since, 0.3, 0.02)
    sz = f"(0.32 + 0.12 * v.particle_random_3) * math.sin(180 * {k}) * {vis}"
    comps = heal_locked(10, HEAL + 0.6, pos)
    uv = frame_uv(frames(k, 11), 25, 25)
    return particle("bitterblade_healstars", T_TWINKLE, comps, uv, [sz, sz],
                    tinting={"color": [0.86, 1, 0.92, 1]})


def p_healmotes():
    """Small mint sparkles rising off the user as the bubble fades."""
    tb = f"({HEAL + 0.04} + 0.3 * v.particle_random_1)"
    since = f"(v.tt - {tb})"
    life = "(0.4 + 0.12 * v.particle_random_4)"
    k = f"math.clamp({since} / {life}, 0, 1)"
    ang = "(360 * v.particle_random_2)"
    rad = "(v.rr * (0.6 + 0.5 * v.particle_random_3))"
    pos = [f"{rad} * math.cos({ang})", f"v.entity_height * (0.2 + 0.6 * v.particle_random_3) + 0.9 * math.max({since}, 0)",
           f"{rad} * math.sin({ang})"]
    vis = window(since, life)
    sz = f"(0.07 + 0.04 * v.particle_random_4) * v.fs * {vis}"
    comps = heal_locked(18, HEAL + 0.85, pos)
    return particle("bitterblade_healmotes", T_SPARK, comps, frame_uv(frames(k, 4), 8, 8, horizontal=False), [sz, sz],
                    tinting={"color": [0.66, 1, 0.8, f"1 - {k} * {k}"]})


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


KEY_TIMES = (T0, CROUCH, WIND0, SPIN0, RELEASE, SPIN1, SPIN1 + 0.05, LUNGE, REC1)


def root_bone(length):
    return {'root_part': {
        'position': dense_keys(lambda x: ROOT_POS(x), length, 0.02, KEY_TIMES),
        'rotation': dense_keys(lambda x: [ROOT_PITCH(x)[0], ROOT_YAW(x)[0], 0.0], length, 0.15, KEY_TIMES, step=0.0125)}}


def fx(time):
    return t(max(0.0, time - FX_LEAD))


def user_sounds():
    return {
        t(IGNITE): [{'effect': 'move.bitterblade.ignite'}],
        t(WRAP0 + 0.04): [{'effect': 'move.bitterblade.flames'}],
        t(SPIN0 - 0.04): [{'effect': 'move.bitterblade.spin'}],
        t(RELEASE - 0.03): [{'effect': 'move.bitterblade.slash'}, {'effect': 'move.bitterblade.slashfire'}],
    }


def at_root(*names):
    return [{'effect': f'cobblemon:bitterblade_{n}', 'locator': 'root'} for n in names]


def actor_ceruledge():
    bones = root_bone(ACTOR_LEN)
    names = ['arm_left', 'arm_left2', 'arm_left3', 'arm_right', 'arm_right2', 'arm_right3', 'leg_left', 'leg_right', 'head']
    for b in names:
        bones[b] = {'rotation': dense_keys(lambda x, b=b: ceruledge_deltas(x)[b][1], ACTOR_LEN, 0.4, KEY_TIMES, step=0.0125)}
    return {
        'animation_length': ACTOR_LEN,
        'bones': bones,
        'particle_effects': {t(T0): at_root('wrap', 'wrapsmoke', 'wrapwisps', 'embers', 'bladecore', 'bladeglow',
                                            'bladeflames', 'spinarc', 'spinedge', 'spinflames')},
        'sound_effects': user_sounds(),
    }


def actor_generic():
    return {
        'animation_length': ACTOR_LEN,
        'bones': root_bone(ACTOR_LEN),
        'particle_effects': {t(T0): at_root('wrap', 'wrapsmoke', 'wrapwisps', 'embers', 'auraflames', 'ringarc',
                                            'ringflames')},
        'sound_effects': user_sounds(),
    }


HEAL_POS = keyed([(0, (0, 0, 0)), (ARRIVE - 0.04, (0, 0, 0)), (ARRIVE + 0.06, (0, -0.8, 0.3)), (HEAL, (0, 0.7, 0), 'o'),
                  (HEAL + 0.22, (0, 0.5, 0)), (HEAL_LEN, (0, 0, 0))])
HEAL_ROT = keyed([(0, (0, 0, 0)), (ARRIVE - 0.04, (0, 0, 0)), (ARRIVE + 0.06, (4, 0, 0)), (HEAL, (-5, 0, 0), 'o'),
                  (HEAL + 0.22, (-3, 0, 0)), (HEAL_LEN, (0, 0, 0))])
HEAL_HEAD = keyed([(0, (0, 0, 0)), (ARRIVE, (0, 0, 0)), (HEAL, (-8, 0, 0)), (HEAL + 0.25, (-6, 0, 0)), (HEAL_LEN, (0, 0, 0))])


def heal_animation():
    """Played with the user's animation when the hit drained something: takes the energy in, then heals."""
    keys = (ARRIVE - 0.04, ARRIVE + 0.06, HEAL, HEAL + 0.22)
    return {
        'animation_length': HEAL_LEN,
        'bones': {'root_part': {'position': dense_keys(HEAL_POS, HEAL_LEN, 0.02, keys),
                                'rotation': dense_keys(HEAL_ROT, HEAL_LEN, 0.15, keys)},
                  'head': {'rotation': dense_keys(HEAL_HEAD, HEAL_LEN, 0.15, keys)}},
        'particle_effects': {t(T0): at_root('absorbring', 'absorbglow', 'healbubble', 'healrays', 'healstars', 'healmotes')},
        'sound_effects': {
            t(ORB0 - 0.02): [{'effect': 'move.bitterblade.drain'}],
            t(ARRIVE - 0.02): [{'effect': 'move.bitterblade.absorb'}],
            t(HEAL - 0.02): [{'effect': 'move.bitterblade.heal'}, {'effect': 'move.bitterblade.shimmer'}],
        },
    }


def target_animation():
    """Started in the same tick as the user's; holds still until the slash lands, then reels from the cut."""
    I = IMPACT
    pos = [(0.0, [0, 0, 0]), (I, [0, 0, 0]), (I + 0.04, [0, 0.8, 4.0]), (I + 0.12, [0, 0.5, 5.0]), (I + 0.24, [0, 0.2, 3.0]),
           (I + 0.4, [0, 0, 1.0]), (I + 0.56, [0, 0, 0.2]), (I + 0.7, [0, 0, 0])]
    rot = [(0.0, [0, 0, 0]), (I, [0, 0, 0]), (I + 0.04, [-10, 6, -7]), (I + 0.12, [-8, 4, -5]), (I + 0.24, [-4, 2, 3]),
           (I + 0.4, [-1, 0, -1]), (I + 0.56, [0, 0, 0]), (I + 0.7, [0, 0, 0])]
    sc = [(0.0, [1, 1, 1]), (I, [1, 1, 1]), (I + 0.04, [1.06, 0.93, 1.06]), (I + 0.14, [0.97, 1.03, 0.97]), (I + 0.3, [1, 1, 1]),
          (I + 0.7, [1, 1, 1])]

    def exact(points):
        return {t(k): vec(v) for k, v in points}
    impact = [{'effect': f'cobblemon:bitterblade_{n}', 'locator': 'target'} for n in (
        'cutflash', 'cutstar', 'cuthalo', 'cutglow', 'cutcore', 'cutshards', 'cutwisps', 'cutsparks', 'cutembers')]
    return {
        'animation_length': r(I + 0.7),
        'bones': {'root_part': {'position': exact(pos), 'rotation': exact(rot), 'scale': exact(sc)}},
        'particle_effects': {fx(I): impact},
        'sound_effects': {t(I): [{'effect': 'impact.fire'}, {'effect': 'move.bitterblade.cut'},
                                 {'effect': 'move.bitterblade.burst'}]},
    }


def build_animation_file():
    return {'format_version': '1.8.0', 'animations': {
        'animation.bitterblade.actor_ceruledge': actor_ceruledge(),
        'animation.bitterblade.actor': actor_generic(),
        'animation.bitterblade.heal': heal_animation(),
        'animation.bitterblade.target': target_animation()}}


# ================================================================= the action effect
def play(anim):
    return f"q.play_animation(q.bedrock_stateful('bitterblade', '{anim}', 'endures_primary_animations'))"


# What the battle reported decides which version plays; nothing here works anything out for itself.
HIT = "q.hurt == true"                    # it drained something: the orb flies back and the user heals
MISSED = "q.missed == true"
USER = "q.entity.is_user == true"
CERULEDGE = "q.entity.species.identifier == 'cobblemon:ceruledge'"
TARGET_HIT = "q.entity.is_user == false && q.hurt(q.entity.uuid) == true"
if os.environ.get('BB_FORCE_MISS') == '1':
    # debug build for checking the miss version in-game (a real miss needs an evasion boost): every
    # Bitter Blade plays as a miss. Never ship this.
    HIT = "q.hurt == 2"
    MISSED = "q.hurt == true || q.missed == true"
    TARGET_HIT = "q.entity.is_user == 2"
# the user's mint glow as the energy reaches it (Java hook; returns 0 and does nothing if it isn't there)
TINT = (0.42, 1.0, 0.62)
TINT_STRENGTH, TINT_FLASH = 0.55, 0.45


def tint_call():
    args = [*TINT, TINT_STRENGTH, TINT_FLASH, ARRIVE - 0.03, 0.06, HEAL + 0.12 - ARRIVE, 0.3]
    return f"q.user.model_tint({', '.join(str(r(a)) for a in args)})"


def build_effect_file():
    # Every keyframe costs a server tick in 1.7.3, so the whole start is one `parallel` (one tick).
    start = [
        {'type': 'entity_molang', 'entityCondition': f"{USER} && {CERULEDGE}", 'expressions': [play('actor_ceruledge')]},
        {'type': 'entity_molang', 'entityCondition': f"{USER} && !({CERULEDGE})", 'expressions': [play('actor')]},
        {'type': 'entity_molang', 'condition': HIT, 'entityCondition': USER, 'expressions': [play('heal')]},
        {'type': 'entity_molang', 'entityCondition': TARGET_HIT, 'expressions': [play('target')]},
    ]
    start.append({'type': 'entity_particles', 'effect': 'cobblemon:bitterblade_releaseflash', 'locators': ['root'],
                  'targetLocators': ['target']})
    for layer in ('wave', 'wavetrail', 'waveflames'):
        start.append({'type': 'entity_particles', 'condition': f"!({MISSED})", 'effect': f'cobblemon:bitterblade_{layer}',
                      'locators': ['root'], 'targetLocators': ['target']})
        start.append({'type': 'entity_particles', 'condition': MISSED, 'effect': f'cobblemon:bitterblade_{layer}_miss',
                      'locators': ['root'], 'targetLocators': ['target']})
    for layer in ('orbsparks', 'orbhalo', 'orbcore', 'orbtrail'):
        start.append({'type': 'entity_particles', 'condition': HIT, 'effect': f'cobblemon:bitterblade_{layer}',
                      'locators': ['root'], 'targetLocators': ['target']})
    start.append({'type': 'molang', 'expressions': f"{HIT} ? {tint_call()} : 0"})
    # the parallel above already took a tick; the HP bar drops as the slash lands, and the timeline ends
    # as the heal bubble appears (the battle heals the user then)
    return {'timeline': [
        {'type': 'add_holds', 'holds': ['effects']},
        {'type': 'parallel', 'keyframes': start},
        {'type': 'pause', 'pause': r(IMPACT - 0.05)},
        {'type': 'remove_holds', 'holds': ['effects']},
        {'type': 'pause', 'pause': f"{HIT} ? {r(HEAL + 0.04 - IMPACT)} : {TAIL}"},
    ]}


def all_particles():
    out = [p_wrap(), p_wrapsmoke(), p_wrapwisps(), p_embers(), p_bladeglow(), p_bladecore(), p_bladeflames(),
           p_spinarc(), p_spinedge(), p_spinflames(), p_ringarc(), p_ringflames(), p_auraflames(), p_releaseflash()]
    for miss in (False, True):
        out += [p_wave(miss), p_wavetrail(miss), p_waveflames(miss)]
    out += [p_cutflash(), p_cuthalo(), p_cutstar(), p_cutline(False), p_cutline(True), p_cutshards(), p_cutwisps(),
            p_cutsparks(), p_cutembers()]
    out += [p_orb(True), p_orb(False), p_orbsparks(), p_orbtrail()]
    out += [p_absorbring(), p_absorbglow(), p_healbubble(), p_healrays(), p_healstars(), p_healmotes()]
    return out


# ================================================================= rig check
def check_rig():
    """Compares RIG / BLADE_X / IDLE with the Ceruledge model and battle idle in each Cobblemon jar."""
    import glob, zipfile
    jars = sorted(p for p in glob.glob(os.path.expanduser('~/.gradle/caches/modules-2/files-2.1/com.cobblemon/fabric/*/*/fabric-*.jar'))
                  if 'sources' not in p)
    if not jars:
        raise SystemExit('no Cobblemon jar in the Gradle cache')
    ok = True
    for jar in jars:
        z = zipfile.ZipFile(jar)
        geo = json.loads(z.read('assets/cobblemon/bedrock/pokemon/models/0937_ceruledge/ceruledge.geo.json'))
        bones = {b['name']: b for b in geo['minecraft:geometry'][0]['bones']}
        problems = []
        for name, (parent, pivot, rest) in RIG.items():
            b = bones.get(name)
            if b is None:
                problems.append(f'{name} missing')
                continue
            if b.get('parent') != parent or [float(c) for c in b['pivot']] != [float(c) for c in pivot] \
                    or [float(c) for c in (b.get('rotation') or [0, 0, 0])] != [float(c) for c in rest]:
                problems.append(f'{name} differs: {b.get("parent")} {b["pivot"]} {b.get("rotation")}')
        for blade, (x0, x1) in BLADE_X.items():
            c = bones[blade]['cubes'][0]
            xs = sorted([c['origin'][0], c['origin'][0] + c['size'][0]], key=abs)
            if [float(v) for v in xs] != [float(x0), float(x1)] or abs(c['origin'][1] - 32.6) > 1e-6 \
                    or abs(c['origin'][2] + c['size'][2] / 2 - 0.8) > 1e-6:
                problems.append(f'{blade} quad differs: {c}')
        anim = json.loads(z.read('assets/cobblemon/bedrock/pokemon/animations/0937_ceruledge/ceruledge.animation.json'))
        idle = anim['animations']['animation.ceruledge.battle_idle']['bones']
        for name, (pos, rot) in IDLE.items():
            got = idle.get(name, {})
            for ch, want in (('position', pos), ('rotation', rot)):
                val = got.get(ch)
                if val is None:
                    if any(want):
                        problems.append(f'idle {name}.{ch} missing')
                    continue
                if isinstance(val, dict):    # keyframed: compare the first key's constant parts loosely
                    val = list(val.values())[0]
                for i, v in enumerate(val):
                    base = float(v) if not isinstance(v, str) else float(v.split('+')[0].split('Math')[0] or 0)
                    if abs(base - want[i]) > 0.01:
                        problems.append(f'idle {name}.{ch}[{i}] = {v} (expected about {want[i]})')
        print(os.path.basename(jar), 'OK' if not problems else 'DIFFERS')
        for p in problems:
            print('   ', p)
        ok = ok and not problems
    if not ok:
        raise SystemExit(1)


def write(path, data):
    with open(path, 'w') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write('\n')
    print('wrote', os.path.relpath(path, ROOT))


if __name__ == '__main__':
    if '--check-rig' in sys.argv:
        check_rig()
        sys.exit(0)
    rel = blade_at(RELEASE, 'blade_right', 1.0)
    w, h = 1.1 * 0.7, 2.7 * 0.7
    generic = (0.0, REL_H * h, -(0.5 * w + REL_F * max(w, h)))
    print(f'release at {RELEASE:.3f} s: right blade point {[round(c * 0.7 / 16, 2) for c in rel]} blocks,'
          f' generic release point {[round(c, 2) for c in generic]}')
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
