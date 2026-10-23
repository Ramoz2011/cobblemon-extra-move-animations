"""Storyboard preview of a generated move: replays its particle expressions and draws side, behind and top views.

  python3 docs/tools/preview_move.py flareblitz OUT.png [--du 64] [--size 1.0] [--miss] [--times 0.2,0.4,...]

It loads docs/tools/<move>_gen.py for the timing constants and the path, evaluates the generated
particle JSON with molang.py in *design time* (as if the particle clock had no lag) and paints every
live particle as a soft disc (streaks as lines, rings as circles) over boxes for the user and the target.
The emitter frame is the one the generators use: -z towards the target, +y up. Only for checking
composition, scale and timing by eye; the real look is checked in-game.
"""
import importlib.util, json, math, os, random, struct, sys, zlib

HERE = os.path.dirname(os.path.abspath(__file__))
sys.dont_write_bytecode = True   # don't leave a __pycache__ in docs/tools
sys.path.insert(0, HERE)
from molang import Env, run, linear_curve   # noqa: E402
import zipfile, glob   # noqa: E402

_JAR = None


def _jar():
    global _JAR
    if _JAR is None:
        hits = [p for p in glob.glob(os.path.expanduser('~/.gradle/caches/modules-2/files-2.1/**/fabric-1.7.3+1.21.1.jar'),
                                     recursive=True) if 'sources' not in p]
        _JAR = zipfile.ZipFile(hits[0])
    return _JAR


def decode_png(data):
    """Minimal PNG decoder (8-bit RGBA / RGB / grey+alpha / palette, non-interlaced) -> (w, h, rows of RGBA)."""
    pos, idat, plte, trns = 8, b'', None, None
    w = h = ctype = 0
    while pos < len(data):
        ln = struct.unpack('>I', data[pos:pos + 4])[0]
        typ, body = data[pos + 4:pos + 8], data[pos + 8:pos + 8 + ln]
        if typ == b'IHDR':
            w, h, depth, ctype = struct.unpack('>IIBB', body[:10])
        elif typ == b'PLTE':
            plte = body
        elif typ == b'tRNS':
            trns = body
        elif typ == b'IDAT':
            idat += body
        pos += 12 + ln
    raw = zlib.decompress(idat)
    bpp = {6: 4, 2: 3, 4: 2, 0: 1, 3: 1}[ctype]
    stride = w * bpp
    rows, prev, i = [], bytearray(stride), 0
    for _ in range(h):
        f, line = raw[i], bytearray(raw[i + 1:i + 1 + stride])
        i += 1 + stride
        for x in range(stride):
            a = line[x - bpp] if x >= bpp else 0
            b = prev[x]
            c = prev[x - bpp] if x >= bpp else 0
            if f == 1:
                line[x] = (line[x] + a) & 255
            elif f == 2:
                line[x] = (line[x] + b) & 255
            elif f == 3:
                line[x] = (line[x] + (a + b) // 2) & 255
            elif f == 4:
                pa, pb, pc = abs(b - c), abs(a - c), abs(a + b - 2 * c)
                line[x] = (line[x] + (a if pa <= pb and pa <= pc else (b if pb <= pc else c))) & 255
        prev = line
        px = []
        for x in range(w):
            q = line[x * bpp:(x + 1) * bpp]
            if ctype == 6:
                px.append(tuple(q))
            elif ctype == 2:
                px.append((q[0], q[1], q[2], 255))
            elif ctype == 4:
                px.append((q[0], q[0], q[0], q[1]))
            elif ctype == 0:
                px.append((q[0], q[0], q[0], 255))
            else:
                k = q[0]
                a = trns[k] if trns and k < len(trns) else 255
                px.append((plte[3 * k], plte[3 * k + 1], plte[3 * k + 2], a))
        rows.append(px)
    return w, h, rows


_TEX = {}


def texture(path):
    """'textures/particles/...' -> decoded image from our resources or the Cobblemon jar."""
    if path not in _TEX:
        rel = 'assets/cobblemon/' + path.replace('textures/particles/', 'textures/particle/', 1) + '.png'
        ours = os.path.join(RES, rel)
        data = open(ours, 'rb').read() if os.path.exists(ours) else _jar().read(rel)
        _TEX[path] = decode_png(data)
    return _TEX[path]


_COV = {}


def coverage(path, u, v, uw, vh):
    """(equivalent radius as a share of the quad half-size, mean colour, mean opacity) of one UV rectangle.
    Pixels the particle shader discards (alpha < 0.1) count as empty."""
    key = (path, int(u), int(v), int(uw), int(vh))
    if key not in _COV:
        w, h, rows = texture(path)
        n, rgb, alpha = 0, [0, 0, 0], 0.0
        for y in range(int(v), min(int(v + vh), h)):
            for x in range(int(u), min(int(u + uw), w)):
                r_, g_, b_, a_ = rows[y][x]
                if a_ >= 26:
                    n += 1
                    alpha += a_ / 255
                    for i, c in enumerate((r_, g_, b_)):
                        rgb[i] += c / 255
        area = max(1, int(uw) * int(vh))
        _COV[key] = (math.sqrt(n / area * 4 / math.pi) if n else 0.0,
                     tuple(c / n for c in rgb) if n else (1, 1, 1), alpha / n if n else 0.0)
    return _COV[key]

RES = os.path.join(HERE, '..', '..', 'src/main/resources')


def load_gen(move):
    spec = importlib.util.spec_from_file_location(f'{move}_gen', os.path.join(HERE, f'{move}_gen.py'))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def load_particles(move):
    d = os.path.join(RES, f'assets/cobblemon/bedrock/particles/moves/{move}')
    out = {}
    for f in sorted(os.listdir(d)):
        p = json.load(open(os.path.join(d, f)))['particle_effect']
        out[p['description']['identifier']] = p
    return out


# ------------------------------------------------------------------ evaluation
def apply_curves(pe, env):
    for name, spec in pe.get('curves', {}).items():
        key = 'v.' + name.split('.', 1)[1].lower()
        env.vars[key] = linear_curve(spec, env)


def tint_of(pe, env):
    c = pe['components'].get('minecraft:particle_appearance_tinting', {}).get('color')
    if c is None:
        return (1, 1, 1, 1)
    if isinstance(c, list):
        return tuple(run(x, env) for x in c)
    k = run(c['interpolant'], env)
    stops = sorted((float(a), b) for a, b in c['gradient'].items())

    def rgba(h):
        v = int(h[1:], 16)
        return ((v >> 16 & 255) / 255, (v >> 8 & 255) / 255, (v & 255) / 255, (v >> 24 & 255) / 255)
    if k <= stops[0][0]:
        return rgba(stops[0][1])
    for (a, ca), (b, cb) in zip(stops, stops[1:]):
        if k <= b:
            f = (k - a) / (b - a) if b > a else 0
            return tuple(x + (y - x) * f for x, y in zip(rgba(ca), rgba(cb)))
    return rgba(stops[-1][1])


def base_env(pe, ent, extra=None):
    env = Env({'v.entity_width': ent['w'], 'v.entity_height': ent['h'], 'v.du': ent.get('du', 0),
               'v.miss': ent.get('miss', 0)}, {'q.entity_scale': ent['scale']})
    env.vars.update(extra or {})
    return env


def eval_particle(pe, env):
    """Size, tint and drawing style of a particle whose env already holds its age, randoms and variables."""
    comps = pe['components']
    upd = comps.get('minecraft:particle_initialization', {}).get('per_update_expression')
    apply_curves(pe, env)
    if upd:
        run(upd, env)
    bb = comps['minecraft:particle_appearance_billboard']
    sx, sy = (run(s, env) for s in bb['size'])
    path = pe['description']['basic_render_parameters']['texture']
    tex = path.rsplit('/', 1)[1]
    col = tint_of(pe, env)
    uv = bb['uv']
    if 'flipbook' in uv:
        fb = uv['flipbook']
        n = int(run(fb.get('max_frame', 1), env))
        age, life = env.get('v.particle_age'), env.get('v.particle_lifetime') or 1
        if fb.get('stretch_to_lifetime'):
            frame = min(int(age / life * n), n - 1)
        else:
            frame = int(age * run(fb.get('frames_per_second', 8), env))
            frame = frame % n if fb.get('loop') else min(frame, n - 1)
        bu, bv = (run(c, env) for c in fb['base_UV'])
        su, sv_ = (run(c, env) for c in fb['size_UV'])
        stu, stv = (run(c, env) for c in fb['step_UV'])
        rect = (bu + stu * frame, bv + stv * frame, su, sv_)
    else:
        rect = tuple(run(c, env) for c in uv['uv']) + tuple(run(c, env) for c in uv['uv_size'])
    rad, texel, opac = coverage(path, *rect)
    style = 'ring' if 'ring' in tex else ('streak' if bb['facing_camera_mode'] == 'lookat_direction' else
                                         ('flat' if bb['facing_camera_mode'].startswith('emitter_transform_xz') else 'disc'))
    if style in ('ring', 'streak'):
        rad = 1.0
    return {'sx': 2 * abs(sx) / 1.5, 'sy': 2 * abs(sy) / 1.5, 'cov': rad,
            'rgb': tuple(b * c for b, c in zip(texel, col[:3])), 'a': max(0.0, min(1.0, col[3] * opac)), 'style': style}


def randoms(seed):
    rnd = random.Random(seed)
    return {f'v.particle_random_{i}': rnd.random() for i in range(1, 5)}


def locked_layer(pe, ent, x, t_in):
    """Path-locked layer (instant spawn, parametric motion) at design time x."""
    comps = pe['components']
    n = int(run(comps['minecraft:emitter_rate_instant']['num_particles'], Env()))
    out = []
    pos_expr = comps['minecraft:particle_motion_parametric']['relative_position']
    for i in range(n):
        rv = randoms(hash((pe['description']['identifier'], i)) & 0xffffffff)
        env = base_env(pe, ent, rv)
        life = run(comps['minecraft:particle_lifetime_expression']['max_lifetime'], env)
        age = x - t_in
        if age < 0 or age > life:
            continue
        env.vars['v.particle_age'] = age
        env.vars['v.particle_lifetime'] = life
        d = eval_particle(pe, env)
        p = tuple(run(e, env) for e in pos_expr)
        if d['style'] == 'streak':        # direction from the motion over the last few hundredths of a second
            env2 = base_env(pe, ent, rv)
            env2.vars['v.particle_age'] = max(age - 0.02, 0)
            env2.vars['v.particle_lifetime'] = life
            apply_curves(pe, env2)
            run(comps['minecraft:particle_initialization']['per_update_expression'], env2)
            p0 = tuple(run(e, env2) for e in pos_expr)
            d['dir'] = tuple(a - b for a, b in zip(p, p0))
        d['p'] = p
        out.append(d)
    return out


def shape_point(comps, env, rnd):
    """Spawn offset and direction of an emitter shape (frame of the emitter, before translation)."""
    if 'minecraft:emitter_shape_point' in comps:
        sh = comps['minecraft:emitter_shape_point']
        off = [run(e, env) for e in sh.get('offset', [0, 0, 0])]
        dr = sh.get('direction', [0, 0, 0])
        dr = [run(e, env) for e in dr] if isinstance(dr, list) else [0, 1, 0]
        return off, dr
    for key in ('minecraft:emitter_shape_sphere', 'minecraft:emitter_shape_disc'):
        if key in comps:
            sh = comps[key]
            off = [run(e, env) for e in sh.get('offset', [0, 0, 0])]
            rad = run(sh.get('radius', 1), env)
            if key.endswith('sphere'):
                z, a = rnd.uniform(-1, 1), rnd.uniform(0, 2 * math.pi)
                u = (math.sqrt(1 - z * z) * math.cos(a), z, math.sqrt(1 - z * z) * math.sin(a))
            else:
                a = rnd.uniform(0, 2 * math.pi)
                u = (math.cos(a), 0, math.sin(a))
            rr = rad if sh.get('surface_only') else rad * math.sqrt(rnd.random())
            p = [o + rr * c for o, c in zip(off, u)]
            dr = sh.get('direction', 'outwards')
            if dr == 'outwards':
                dvec = list(u)
            elif dr == 'inwards':
                dvec = [-c for c in u]
            else:
                dvec = [run(e, env) for e in dr]
            return p, dvec
    return [0, 0, 0], [0, 1, 0]


def emitter_layer(pe, ent, x, fire_time, where, ein_offset=0.0):
    """A steady/instant emitter fired at animation time `fire_time`, simulated tick by tick up to x.
    `where(t)` gives the emitter position (frame coordinates) at animation time t."""
    comps = pe['components']
    if x < fire_time:
        return []
    env = base_env(pe, ent)
    init = comps.get('minecraft:emitter_initialization', {}).get('creation_expression')
    if init:
        run(init, env)
        env.vars['v.entity_width'], env.vars['v.entity_height'] = ent['w'], ent['h']
        env.vars['v.du'], env.vars['v.miss'] = ent.get('du', 0), ent.get('miss', 0)
    life_em = run(comps['minecraft:emitter_lifetime_once']['active_time'], env)
    rnd = random.Random(hash(pe['description']['identifier']) & 0xffffffff)
    parts, acc, n_ticks = [], 0.0, int((x - fire_time) / 0.05 + 1e-6)
    dyn = comps.get('minecraft:particle_motion_dynamic', {})
    for tick in range(n_ticks + 1):
        em_age = tick * 0.05
        env.vars['v.emitter_age'] = em_age + ein_offset
        env.vars['v.emitter_age'] = em_age
        apply_curves(pe, env)
        spawn = 0
        if em_age <= life_em:
            if 'minecraft:emitter_rate_instant' in comps:
                spawn = int(run(comps['minecraft:emitter_rate_instant']['num_particles'], env)) if tick == 0 else 0
            else:
                rate = comps['minecraft:emitter_rate_steady']
                acc += run(rate['spawn_rate'], env) / 20
                spawn = int(acc)
                acc -= spawn
                spawn = min(spawn, int(run(rate['max_particles'], env)))
        origin = where(fire_time + em_age)
        for _ in range(spawn):
            rv = {f'v.particle_random_{i}': rnd.random() for i in range(1, 5)}
            env.vars.update(rv)
            off, dr = shape_point(comps, env, rnd)
            speed = run(comps.get('minecraft:particle_initial_speed', 0), env)
            norm = math.sqrt(sum(c * c for c in dr)) or 1
            life = run(comps['minecraft:particle_lifetime_expression']['max_lifetime'], env)
            parts.append({'p': [o + c for o, c in zip(origin, off)], 'v': [speed * c / norm for c in dr],
                          'born': em_age, 'life': life, 'rv': rv})
        for q in parts:      # integrate the motion of everything alive this tick
            if em_age > q['born']:
                envp = base_env(pe, ent, q['rv'])
                envp.vars['v.particle_age'] = em_age - q['born']
                acc_v = [run(e, envp) for e in dyn.get('linear_acceleration', [0, 0, 0])]
                drag = run(dyn.get('linear_drag_coefficient', 0), envp)
                q['v'] = [vv + (aa - drag * vv) * 0.05 for vv, aa in zip(q['v'], acc_v)]
                q['p'] = [pp + vv * 0.05 for pp, vv in zip(q['p'], q['v'])]
    out = []
    em_age = n_ticks * 0.05
    for q in parts:
        age = em_age - q['born']
        if age > q['life']:
            continue
        env2 = base_env(pe, ent, q['rv'])
        env2.vars['v.particle_age'] = age
        env2.vars['v.particle_lifetime'] = q['life']
        env2.vars['v.emitter_age'] = em_age
        d = eval_particle(pe, env2)
        d['p'] = tuple(q['p'])
        d['dir'] = tuple(q['v'])
        out.append(d)
    return out


# ------------------------------------------------------------------ drawing
class Canvas:
    def __init__(self, w, h, bg):
        self.w, self.h = w, h
        self.px = [list(bg) for _ in range(w * h)]

    def blend(self, x, y, rgb, a):
        if 0 <= x < self.w and 0 <= y < self.h and a > 0.003:
            c = self.px[y * self.w + x]
            for i in range(3):
                c[i] += (rgb[i] - c[i]) * a

    def disc(self, cx, cy, rad, rgb, a, soft=True):
        rad = max(rad, 0.6)
        for y in range(int(cy - rad), int(cy + rad) + 2):
            for x in range(int(cx - rad), int(cx + rad) + 2):
                d = math.hypot(x + 0.5 - cx, y + 0.5 - cy) / rad
                if d < 1:
                    self.blend(x, y, rgb, a * ((1 - d * d) ** 1.2 if soft else 1))

    def line(self, x0, y0, x1, y1, rgb, a, width=1.0):
        n = int(max(abs(x1 - x0), abs(y1 - y0)) * 1.5) + 1
        for i in range(n + 1):
            k = i / n
            self.disc(x0 + (x1 - x0) * k, y0 + (y1 - y0) * k, width / 2 + 0.5, rgb, a, soft=False)

    def ring(self, cx, cy, rad, rgb, a):
        n = int(rad * 6) + 8
        for i in range(n):
            ang = 2 * math.pi * i / n
            self.blend(int(cx + rad * math.cos(ang)), int(cy + rad * math.sin(ang)), rgb, a)

    def box(self, x0, y0, x1, y1, rgb, a):
        for x in range(int(min(x0, x1)), int(max(x0, x1)) + 1):
            self.blend(x, int(y0), rgb, a)
            self.blend(x, int(y1), rgb, a)
        for y in range(int(min(y0, y1)), int(max(y0, y1)) + 1):
            self.blend(int(x0), y, rgb, a)
            self.blend(int(x1), y, rgb, a)


FONT = {  # 3x5 digits for the time labels
    '0': '111101101101111', '1': '010110010010111', '2': '111001111100111', '3': '111001111001111',
    '4': '101101111001001', '5': '111100111001111', '6': '111100111101111', '7': '111001001001001',
    '8': '111101111101111', '9': '111101111001111', '.': '000000000000010', 's': '000011010001110',
}


def label(cv, x, y, text, rgb=(1, 1, 0.3)):
    for ch in text:
        bits = FONT.get(ch, '0' * 15)
        for i, b in enumerate(bits):
            if b == '1':
                for dy in range(2):
                    for dx in range(2):
                        cv.blend(x + (i % 3) * 2 + dx, y + (i // 3) * 2 + dy, rgb, 1)
        x += 8


VIEWS = {   # world (x, y, z) -> screen (u, v, depth); camera looks at the scene from...
    'side': lambda p: (-p[2], p[1], p[0]),       # ...the right of the charge: target on the right
    'behind': lambda p: (p[0], p[1], -p[2]),     # ...behind the user, looking at the target
    'top': lambda p: (-p[2], -p[0], p[1]),       # ...above
}


def render(view, items, bodies, x_range, y_range, w, h, t_label):
    cv = Canvas(w, h, (0.16, 0.19, 0.24))
    sx = w / (x_range[1] - x_range[0])
    sy = h / (y_range[1] - y_range[0])
    s = min(sx, sy)

    def to_px(u, v):
        return (u - x_range[0]) * s, h - (v - y_range[0]) * s
    proj = VIEWS[view]
    if view != 'top':                                       # ground line
        gx0, gy = to_px(x_range[0], 0)
        cv.line(0, gy, w, gy, (0.4, 0.45, 0.35), 0.8)
    for (bx0, by0, bz0), (bx1, by1, bz1), rgb in bodies:   # bodies as outlines
        corners = [proj((xx, yy, zz)) for xx in (bx0, bx1) for yy in (by0, by1) for zz in (bz0, bz1)]
        us = [c[0] for c in corners]
        vs = [c[1] for c in corners]
        a0, b0 = to_px(min(us), min(vs))
        a1, b1 = to_px(max(us), max(vs))
        cv.box(a0, b0, a1, b1, rgb, 0.9)
    for it in sorted(items, key=lambda it: proj(it['p'])[2]):
        u, v, _ = proj(it['p'])
        px, py = to_px(u, v)
        if it['a'] <= 0 or it['sx'] <= 0:
            continue
        if it['style'] == 'streak' and 'dir' in it:
            du, dv, _ = proj(it['dir'])
            ln = math.hypot(du, dv) or 1
            half = it['sx'] * s / 2
            cv.line(px - du / ln * half, py + dv / ln * half, px + du / ln * half, py - dv / ln * half, it['rgb'], it['a'],
                    max(1.0, it['sy'] * s))
        elif it['style'] == 'ring':
            cv.ring(px, py, it['sx'] * s * 0.42, it['rgb'], it['a'])
        elif it['style'] == 'flat':
            if view == 'top':
                cv.disc(px, py, it['sx'] * s / 2 * it['cov'], it['rgb'], it['a'] * 0.8)
            else:
                cv.line(px - it['sx'] * s / 2, py, px + it['sx'] * s / 2, py, it['rgb'], it['a'], 2)
        else:
            cv.disc(px, py, it['sx'] * s / 2 * it['cov'], it['rgb'], it['a'])
    label(cv, 3, 3, t_label)
    return cv


def write_png(path, w, h, rows):
    raw = b''.join(b'\x00' + bytes(max(0, min(255, int(c * 255))) for px in row for c in px) for row in rows)

    def chunk(t, b):
        return struct.pack('>I', len(b)) + t + b + struct.pack('>I', zlib.crc32(t + b) & 0xffffffff)
    with open(path, 'wb') as f:
        f.write(b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 2, 0, 0, 0))
                + chunk(b'IDAT', zlib.compress(raw, 6)) + chunk(b'IEND', b''))


def main():
    args = sys.argv[1:]
    move, out = args[0], args[1]
    opt = {'--du': '64', '--size': '1.0', '--times': None, '--views': 'side,behind,top', '--layers': None}
    miss = '--miss' in args
    for k in opt:
        if k in args:
            opt[k] = args[args.index(k) + 1]
    gen = load_gen(move)
    parts = load_particles(move)
    du, size = float(opt['--du']), float(opt['--size'])
    ent = {'w': size * 0.9, 'h': size, 'scale': size, 'du': du, 'miss': 1 if miss else 0}
    sc = ent['scale'] / 16
    reach = gen.REACH * max(ent['w'], ent['h'])
    dist = du * sc + 0.5 * ent['w'] + reach               # root-to-root distance to the target
    times = [float(t) for t in opt['--times'].split(',')] if opt['--times'] else \
        [0.12, 0.24, 0.36, 0.48, 0.58, 0.62, 0.70, 0.80, 0.90, 0.98, 1.06, 1.20, 1.40, 1.70]
    F = gen.F_miss if miss else gen.F_hit
    Y = gen.Y_miss if miss else gen.Y_hit
    ZC = gen.ZC_miss if miss else gen.ZC_hit

    def root_at(t):
        x = -gen.X_miss(t) * sc if miss else 0.0
        return (x, Y(t) * sc, (ZC(t) - du * F(t)) * sc)

    locked_ids = [f'cobblemon:{move}_{l}' for l in gen.LOCKED_COMMON + (gen.LOCKED_MISS if miss else gen.LOCKED_IMPACT)
                  + gen.LOCKED_LAST]
    only = set(f'cobblemon:{move}_{l}' for l in opt['--layers'].split(',')) if opt['--layers'] else None
    if only:
        locked_ids = [i for i in locked_ids if i in only]
    anim = json.load(open(os.path.join(RES, f'assets/cobblemon/bedrock/generic/animations/moves/{move}.animation.json')))
    actor = anim['animations'][f'animation.{move}.actor_miss' if miss else f'animation.{move}.actor_recoil']
    target = anim['animations'][f'animation.{move}.target']
    fired = []    # (time, effect id, locator, owner)
    for tkey, effs in actor.get('particle_effects', {}).items():
        for e in (effs if isinstance(effs, list) else [effs]):
            fired.append((float(tkey), e['effect'], e['locator'], 'user'))
    if not miss:
        for tkey, effs in target.get('particle_effects', {}).items():
            for e in (effs if isinstance(effs, list) else [effs]):
                fired.append((float(tkey), e['effect'], e['locator'], 'target'))
    views = opt['--views'].split(',')
    W, H = 300, 170
    rows = []
    for x in times:
        items = []
        for pid in locked_ids:
            pe = parts.get(pid)
            if pe is None:
                continue
            if 'minecraft:emitter_rate_instant' in pe['components'] and \
                    'minecraft:particle_motion_parametric' in pe['components']:
                items += locked_layer(pe, ent, x, gen.T_IN)
            else:          # world-space layer that follows the root locator
                items += emitter_layer(pe, ent, x, gen.EMIT_IN, root_at)
        for ft, pid, loc, owner in fired:
            pe = parts.get(pid)
            if pe is None or (only and pid not in only):
                continue
            if owner == 'user':
                lift = 0.5 * ent['h'] if loc == 'middle' else 0.0
                fixed = root_at(ft)
                where = (lambda t, f=fixed, l=lift: (f[0], f[1] + l, f[2]))
            else:
                lift = 0.5 * ent['h'] if loc in ('middle', 'target') else 0.0
                where = (lambda t, l=lift: (0.0, l, -dist))
            items += emitter_layer(pe, ent, x, ft, where)
        rp = root_at(x)
        bodies = [((rp[0] - ent['w'] / 2, rp[1], rp[2] - ent['w'] / 2), (rp[0] + ent['w'] / 2, rp[1] + ent['h'], rp[2] + ent['w'] / 2),
                   (0.5, 0.9, 1.0)),
                  ((-ent['w'] / 2, 0, -dist - ent['w'] / 2), (ent['w'] / 2, ent['h'], -dist + ent['w'] / 2), (1.0, 0.6, 0.6))]
        row_canvases = []
        for view in views:
            if view == 'behind':
                xr, yr = (-3.5, 3.5), (-0.5, 3.5)
            elif view == 'top':
                xr, yr = (-2.5, dist + 3.0), (-2.5, 2.5)
            else:
                xr, yr = (-2.5, dist + 3.0), (-0.5, 3.5)
            row_canvases.append(render(view, items, bodies, xr, yr, W, H, f'{x:.2f}s'))
        rows.append(row_canvases)
    gap = 4
    total_w = len(views) * W + (len(views) - 1) * gap
    out_rows = []
    for row in rows:
        for y in range(H):
            line = []
            for i, cv in enumerate(row):
                line += cv.px[y * W:(y + 1) * W]
                if i < len(row) - 1:
                    line += [(0, 0, 0)] * gap
            out_rows.append(line)
        out_rows += [[(0, 0, 0)] * total_w] * gap
    write_png(out, total_w, len(out_rows), out_rows)
    print('wrote', out, total_w, 'x', len(out_rows))


if __name__ == '__main__':
    main()
