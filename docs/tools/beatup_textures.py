"""Generates Beat Up's custom sprite (pure stdlib, no Pillow).

Output (src/main/resources/assets/cobblemon/textures/particle/moves/):
  beatup_star.png  32x160, five 32x32 frames top to bottom: the comic impact star Scarlet/Violet and
                   Sword/Shield pop on the target for every Beat Up hit. A black spiky star with a violet
                   rim and a pale core: (0) a tight burst, (1) the full star, (2) spikes stretching as the
                   core cools, (3) the middle breaking open, (4) only the spike tips left.
Tinting can't give a black body a bright rim (a tint multiplies), so the colours are baked in and the
particle uses a white tint. Run `python3 docs/tools/beatup_textures.py`.
"""
import math, os, struct, zlib

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..')
OUT_DIR = os.path.join(ROOT, 'src/main/resources/assets/cobblemon/textures/particle/moves')

F = 32          # frame size
SS = 4          # supersampling per axis


def hx(s):
    return int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16)


# one fixed ramp: every pixel snaps to it (per-channel blending turns muddy, see makeitrain_void_texture.py)
CORE_HOT = hx('FFF4FF')
CORE = hx('E8AEFF')
RIM = hx('B06BFF')
RIM_DEEP = hx('6A2CA8')
BODY = hx('1C1030')
BODY_DEEP = hx('0C0716')

# nine spikes, irregular like a hand-drawn hit mark: (angle in degrees, length 0..1, half-width in degrees)
SPIKES = [(4, 1.0, 15), (44, 0.78, 13), (83, 0.95, 16), (121, 0.72, 12), (160, 0.98, 15),
          (199, 0.8, 14), (238, 0.93, 16), (279, 0.7, 12), (318, 0.9, 15)]

# per frame: outer radius, inner radius, core radius, hole radius, spike stretch, tips-only threshold
FRAMES = [
    dict(outer=7.5, inner=4.6, core=3.2, hole=0.0, stretch=0.8, tips=0.0),
    dict(outer=13.5, inner=6.6, core=4.2, hole=0.0, stretch=1.0, tips=0.0),
    dict(outer=15.2, inner=6.8, core=2.8, hole=0.0, stretch=1.12, tips=0.0),
    dict(outer=15.6, inner=7.0, core=0.0, hole=4.4, stretch=1.2, tips=0.0),
    dict(outer=15.8, inner=7.0, core=0.0, hole=0.0, stretch=1.25, tips=0.7),
]


def star_radius(theta, f):
    """Boundary radius at angle theta (degrees): the inner disc plus triangular spikes."""
    r = f['inner']
    for ang, length, half in SPIKES:
        d = abs((theta - ang + 180) % 360 - 180)
        width = half / f['stretch'] ** 0.5          # stretched spikes get thinner
        if d < width:
            tip = f['inner'] + (f['outer'] * length - f['inner']) * f['stretch']
            r = max(r, f['inner'] + (min(tip, 15.8) - f['inner']) * (1 - d / width) ** 1.15)
    return r


def frame(f):
    c = F / 2
    px = []
    for y in range(F):
        row = []
        for x in range(F):
            # supersample the coverage, measure the distance to the edge at the pixel centre
            inside = 0
            for sy in range(SS):
                for sx in range(SS):
                    dx, dy = x + (sx + 0.5) / SS - c, y + (sy + 0.5) / SS - c
                    dist = math.hypot(dx, dy)
                    theta = math.degrees(math.atan2(-dy, dx)) % 360
                    if f['hole'] <= dist <= star_radius(theta, f) and (f['tips'] == 0 or dist >= f['tips'] * f['outer']):
                        inside += 1
            if inside < SS * SS * 0.45:
                row.append((0, 0, 0, 0))
                continue
            dx, dy = x + 0.5 - c, y + 0.5 - c
            dist = math.hypot(dx, dy)
            theta = math.degrees(math.atan2(-dy, dx)) % 360
            edge = min(star_radius(theta, f) - dist, dist - f['hole'] if f['hole'] > 0 else 99)
            if f['core'] > 0 and dist < f['core']:
                col = CORE_HOT if dist < f['core'] * 0.55 else CORE
            elif f['tips'] > 0:
                col = RIM if edge < 1.0 else RIM_DEEP
            elif edge < 1.1:
                col = RIM
            elif edge < 2.1:
                col = RIM_DEEP
            else:
                # a little shading: the upper-left of the body catches a touch more light
                col = BODY if dx + dy < 0 else BODY_DEEP
            row.append(col + (255,))
        px.append(row)
    return px


def write_png(path, w, h, px):
    raw = b''.join(b'\x00' + bytes(c for p in row for c in p) for row in px)

    def chunk(t, b):
        return struct.pack('>I', len(b)) + t + b + struct.pack('>I', zlib.crc32(t + b) & 0xffffffff)
    with open(path, 'wb') as f:
        f.write(b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 6, 0, 0, 0))
                + chunk(b'IDAT', zlib.compress(raw, 9)) + chunk(b'IEND', b''))


if __name__ == '__main__':
    sheet = [row for f in FRAMES for row in frame(f)]
    path = os.path.join(OUT_DIR, 'beatup_star.png')
    write_png(path, F, F * len(FRAMES), sheet)
    print('wrote', os.path.relpath(path, ROOT))
