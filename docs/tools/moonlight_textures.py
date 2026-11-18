"""Generates Moonlight's three custom sprites (pure stdlib, no Pillow).

Outputs (src/main/resources/assets/cobblemon/textures/particle/moves/):
  moonlight_moon.png    128x128 the full moon with its glow: a 61-pixel disc of pale grey highlands and
                               blue-grey maria laid out like the real near side (Sword/Shield and
                               Scarlet/Violet show a realistic grey moon), a few bright craters (Tycho with
                               its rays, Copernicus, Aristarchus) and a faintly brighter limb, snapped to
                               one 10-rung grey-blue ramp so it stays crisp pixel art; round it, a pale blue
                               glow fading to deep blue. The glow is part of the sprite on purpose: a
                               separate glow quad at the same spot is coplanar with the moon (both face the
                               camera through the same point), and coplanar particles z-fight, which made
                               the moon blink out in-game.
  moonlight_column.png  64x32  the column of moonlight, drawn with lookat_direction, so the long (U) axis
                               runs along the beam: soft fade at both ends, soft sides with a brighter core
                               and faint vertical streaks (one quad; a second core quad would z-fight).
                               White; the tint colours it. Symmetric along U, so it doesn't matter
                               which end of the quad the renderer puts at the top.
  moonlight_swirl.png   512x64 8 frames (64x64, left to right) of the glowing circle under the user: three
                               comet-like arcs spiralling round inside a thin rim (Sword/Shield's ground
                               swirl). Each frame turns 15 degrees; the arcs repeat every 120, so the
                               flipbook loops seamlessly. Particles in an xz plane can't spin (Cobblemon's
                               EmitterXZPlane ignores the particle angle), hence a flipbook.
  moonlight_ring.png    64x64  a ring of light pulsing out of the moon (Sword/Shield): a soft bright cyan band
                               edged violet outside, pale inside. Coloured in the texture; the particle
                               tint only fades it.
Minecraft's particle shader discards fragments with alpha < 0.1 (after the tint), so soft edges end in
a faint step where texture alpha x tint alpha crosses 0.1.
Run `python3 docs/tools/moonlight_textures.py`.
"""
import math, os, struct, zlib

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..')
OUT_DIR = os.path.join(ROOT, 'src/main/resources/assets/cobblemon/textures/particle/moves')

# ---------------------------------------------------------------- the moon
MOON = 128
MOON_R = 30.5                      # disc radius in pixels
GLOW_IN = (0.80, 0.87, 1.0)        # glow colour at the moon's edge ...
GLOW_OUT = (0.42, 0.56, 1.0)       # ... and where it fades out
# grey-blue ramp, darkest mare to brightest highland (every moon pixel is snapped to one of these)
RAMP = ['#59627D', '#69728C', '#7A839C', '#8C94AB', '#9FA7BB', '#B3BACB', '#C7CCDA', '#D9DDE7', '#EAEDF3', '#FAFBFD']
# maria as soft ellipses in disc units (x right, y up, radius 1): (cx, cy, rx, ry, rotation deg, depth)
MARIA = [
    (-0.55, 0.02, 0.30, 0.55, 12, 0.62),    # Oceanus Procellarum
    (-0.40, -0.22, 0.20, 0.20, 0, 0.5),     # ... its southern reach towards Nubium
    (-0.27, 0.42, 0.29, 0.25, 0, 0.9),      # Mare Imbrium
    (0.17, 0.42, 0.16, 0.15, 0, 0.95),      # Mare Serenitatis
    (0.33, 0.13, 0.21, 0.16, -20, 0.9),     # Mare Tranquillitatis
    (0.26, 0.29, 0.10, 0.10, 0, 0.75),      # the neck between Serenitatis and Tranquillitatis
    (0.70, 0.30, 0.11, 0.09, 0, 1.0),       # Mare Crisium
    (0.60, -0.12, 0.11, 0.18, 10, 0.75),    # Mare Fecunditatis
    (0.40, -0.29, 0.09, 0.09, 0, 0.8),      # Mare Nectaris
    (-0.17, -0.33, 0.18, 0.13, -10, 0.68),  # Mare Nubium
    (-0.47, -0.39, 0.10, 0.09, 0, 0.78),    # Mare Humorum
    (-0.05, 0.73, 0.40, 0.065, -4, 0.6),    # Mare Frigoris
    (0.04, 0.21, 0.09, 0.07, 0, 0.6),       # Mare Vaporum / Sinus Medii
]
# craters: (cx, cy, radius, brightness): bright ray craters and small pits
CRATERS = [(-0.16, -0.70, 0.05, 0.5), (-0.31, 0.16, 0.04, 0.35), (-0.71, 0.36, 0.03, 0.45), (0.52, -0.55, 0.035, 0.2),
           (-0.45, -0.62, 0.03, 0.15), (0.20, -0.62, 0.03, 0.18), (0.75, -0.42, 0.025, 0.15), (-0.83, -0.05, 0.03, 0.2)]
TYCHO = (-0.16, -0.70)
# small pits scattered over the (mostly southern) highlands, placed by a fixed pseudo-random walk
PITS = []
_seed = 7
while len(PITS) < 26:
    _seed = (_seed * 1103515245 + 12345) & 0x7fffffff
    _u = (_seed % 1000) / 500.0 - 1
    _seed = (_seed * 1103515245 + 12345) & 0x7fffffff
    _v = (_seed % 1000) / 500.0 - 1.15
    if _u * _u + _v * _v < 0.8:
        PITS.append((_u, _v, 0.022 + 0.012 * ((_seed >> 5) % 3), 0.12))

# ---------------------------------------------------------------- the column
COL_U, COL_V = 64, 32
STREAKS = [(0.30, 0.22), (0.44, 0.30), (0.53, 0.18), (0.62, 0.26), (0.71, 0.20), (0.37, 0.12)]   # (position across, strength)

# ---------------------------------------------------------------- the ring
RING = 64
RING_R = 0.78                      # band radius / half the sprite
RING_CORE = (0.86, 0.97, 1.0)      # white-cyan at the band's centre
RING_MID = (0.42, 0.82, 1.0)       # cyan
RING_RIM = (0.6, 0.44, 1.0)        # violet outer edge

# ---------------------------------------------------------------- the swirl
SW = 64
SW_FRAMES = 8
SW_STEP = 120.0 / SW_FRAMES        # degrees turned per frame


def write_png(path, w, h, px):
    raw = b''.join(b'\x00' + bytes(c for p in row for c in p) for row in px)

    def chunk(t, b):
        return struct.pack('>I', len(b)) + t + b + struct.pack('>I', zlib.crc32(t + b) & 0xffffffff)
    with open(path, 'wb') as f:
        f.write(b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 6, 0, 0, 0))
                + chunk(b'IDAT', zlib.compress(raw, 9)) + chunk(b'IEND', b''))


def hexrgb(h):
    v = int(h[1:], 16)
    return (v >> 16 & 255, v >> 8 & 255, v & 255)


def smoothstep(a, b, x):
    t = max(0.0, min(1.0, (x - a) / (b - a)))
    return t * t * (3 - 2 * t)


def _hash(ix, iy, seed):
    n = (ix * 374761393 + iy * 668265263 + seed * 2147483647) & 0xffffffff
    n = ((n ^ (n >> 13)) * 1274126177) & 0xffffffff
    return ((n ^ (n >> 16)) & 0xffff) / 65535.0


def value_noise(x, y, seed):
    ix, iy = math.floor(x), math.floor(y)
    fx, fy = x - ix, y - iy
    sx, sy = fx * fx * (3 - 2 * fx), fy * fy * (3 - 2 * fy)
    a, b = _hash(ix, iy, seed), _hash(ix + 1, iy, seed)
    c, d = _hash(ix, iy + 1, seed), _hash(ix + 1, iy + 1, seed)
    return (a + (b - a) * sx) + ((c + (d - c) * sx) - (a + (b - a) * sx)) * sy


def fbm(x, y, seed, octaves=3):
    total, amp, norm = 0.0, 1.0, 0.0
    for o in range(octaves):
        total += amp * value_noise(x * (2 ** o), y * (2 ** o), seed + 17 * o)
        norm += amp
        amp *= 0.5
    return total / norm


def mare_weight(u, v):
    """0 on highland, up to ~1 on the darkest mare; boundaries roughened with noise."""
    wobble = 0.24 * (fbm(u * 4.5 + 7.1, v * 4.5 + 2.3, 11) - 0.5)
    best = 0.0
    for cx, cy, rx, ry, rot, depth in MARIA:
        a = math.radians(rot)
        dx, dy = u - cx, v - cy
        lx = (dx * math.cos(a) + dy * math.sin(a)) / rx
        ly = (-dx * math.sin(a) + dy * math.cos(a)) / ry
        d = math.sqrt(lx * lx + ly * ly) + wobble * 2.2
        best = max(best, depth * (1 - smoothstep(0.75, 1.15, d)))
    return best


def moon():
    px = []
    c = MOON / 2
    ramp = [hexrgb(h) for h in RAMP]
    for y in range(MOON):
        row = []
        for x in range(MOON):
            # coverage of the disc by 4x4 sub-samples (anti-aliased rim)
            cov = 0
            for sy in range(4):
                for sx in range(4):
                    if math.hypot(x + (sx + 0.5) / 4 - c, y + (sy + 0.5) / 4 - c) <= MOON_R:
                        cov += 1
            cov /= 16.0
            if cov < 0.3:
                # the glow round the disc: a bright rim fading into a wide faint blue haze
                dist = (math.hypot(x + 0.5 - c, y + 0.5 - c) - MOON_R) / MOON_R
                ga = 0.62 * math.exp(-max(dist, 0) / 0.11) + 0.36 * max(0.0, 1 - dist / 0.8) ** 1.5
                k = min(1.0, max(dist, 0) / 0.6)
                col = tuple(int(round(255 * (GLOW_IN[i] + (GLOW_OUT[i] - GLOW_IN[i]) * k))) for i in range(3))
                row.append(col + (int(round(255 * min(1.0, ga))) if ga >= 0.04 else 0,))
                continue
            u, v = (x + 0.5 - c) / MOON_R, (c - (y + 0.5)) / MOON_R
            r = min(1.0, math.hypot(u, v))
            b = 0.90                                                  # highlands
            m = mare_weight(u, v)
            b -= 0.5 * m                                             # maria
            b += 0.08 * (fbm(u * 9 + 3.3, v * 9 + 8.8, 5) - 0.5)     # fine mottling
            for cx, cy, cr, br in CRATERS + PITS:
                d = math.hypot(u - cx, v - cy) / cr
                if d < 1.0:
                    b += br * (1 - d * d) * 0.35 - (0.06 if d < 0.45 else 0.0)
                elif d < 1.6:
                    b += 0.05 * br * (1.6 - d)
            # Tycho's rays: faint bright streaks fanning out over the southern highlands
            tu, tv = u - TYCHO[0], v - TYCHO[1]
            td = math.hypot(tu, tv)
            if 0.06 < td < 0.75:
                ang = math.degrees(math.atan2(tv, tu))
                ray = max(0.0, math.cos(math.radians(((ang + 13) % 29) - 14.5) * 6)) ** 8
                b += 0.035 * ray * (1 - td / 0.75) * (1 - m)
            b += 0.06 * smoothstep(0.8, 1.0, r)                      # slightly brighter limb
            b = max(0.0, min(1.0, b))
            col = ramp[min(len(ramp) - 1, int(round(b * (len(ramp) - 1))))]
            a = 255 if cov >= 0.85 else int(round(255 * (0.55 + 0.45 * cov)))
            row.append((col[0], col[1], col[2], a))
        px.append(row)
    return px


def column():
    px = []
    for yv in range(COL_V):
        across = abs((yv + 0.5) / COL_V * 2 - 1)                    # 0 on the axis, 1 at the sides
        side = 0.62 * (1 - across ** 2.2) ** 1.6 + 0.38 * max(0.0, 1 - (across / 0.42) ** 2) ** 2
        streak = 1.0
        for pos, k in STREAKS:
            streak += k * math.exp(-(((yv + 0.5) / COL_V - pos) / 0.035) ** 2)
        row = []
        for xu in range(COL_U):
            along = (xu + 0.5) / COL_U
            ends = smoothstep(0.0, 0.2, along) * smoothstep(1.0, 0.82, along)
            a = max(0.0, min(1.0, side * ends * streak))
            row.append((255, 255, 255, int(round(255 * a))))
        px.append(row)
    return px


def ring():
    c = RING / 2
    out = []
    for y in range(RING):
        row = []
        for x in range(RING):
            acc = [0.0, 0.0, 0.0, 0.0]
            for sy in range(3):
                for sx in range(3):
                    r = math.hypot(x + (sx + 0.5) / 3 - c, y + (sy + 0.5) / 3 - c) / c
                    d = r - RING_R                                 # + outside the band's centre
                    a = math.exp(-(d / (0.075 if d < 0 else 0.1)) ** 2)
                    if d < 0:
                        k = min(1.0, -d / 0.12)
                        col = [RING_CORE[i] + (RING_MID[i] - RING_CORE[i]) * k * 0.5 for i in range(3)]
                    else:
                        k = min(1.0, d / 0.14)
                        col = [RING_CORE[i] + (RING_MID[i] - RING_CORE[i]) * min(1.0, 2 * k) for i in range(3)]
                        if k > 0.5:
                            col = [RING_MID[i] + (RING_RIM[i] - RING_MID[i]) * (2 * k - 1) for i in range(3)]
                    for i in range(3):
                        acc[i] += col[i] * a
                    acc[3] += a
            a = acc[3] / 9.0
            if a < 0.05:
                row.append((0, 0, 0, 0))
                continue
            col = [acc[i] / acc[3] for i in range(3)]
            row.append((int(round(255 * col[0])), int(round(255 * col[1])), int(round(255 * col[2])), int(round(255 * min(1.0, a)))))
        out.append(row)
    return out


def swirl_frame(f):
    """Three comet arcs (bright head, tapering tail) spiralling inside a thin rim, turned f * SW_STEP."""
    c = SW / 2
    R = SW / 2 - 0.6
    out = []
    for y in range(SW):
        row = []
        for x in range(SW):
            acc = 0.0
            for sy in range(3):
                for sx in range(3):
                    px_, py_ = x + (sx + 0.5) / 3 - c, c - (y + (sy + 0.5) / 3)
                    r = math.hypot(px_, py_) / R
                    th = math.degrees(math.atan2(py_, px_))
                    a = 0.0
                    # rim
                    a = max(a, 0.6 * math.exp(-((r - 0.955) / 0.022) ** 2))
                    # faint inner rim
                    a = max(a, 0.22 * math.exp(-((r - 0.52) / 0.02) ** 2))
                    for k in range(3):
                        head = f * SW_STEP + k * 120.0
                        back = (head - th) % 360.0                    # how far behind the head (degrees)
                        if back > 110.0:
                            continue
                        s = back / 110.0                              # 0 at the head, 1 at the tail end
                        rad = 0.84 - 0.12 * s                         # spirals inward along the tail
                        half = 0.075 * (1 - s) ** 0.7 + 0.016
                        inten = (1 - s) ** 1.15
                        a = max(a, inten * math.exp(-((r - rad) / half) ** 2))
                    acc += min(1.0, a)
            a = acc / 9.0
            row.append((255, 255, 255, int(round(255 * a)) if a >= 0.04 else 0))
        out.append(row)
    return out


def swirl():
    frames = [swirl_frame(f) for f in range(SW_FRAMES)]
    return [sum((frames[f][y] for f in range(SW_FRAMES)), []) for y in range(SW)]


if __name__ == '__main__':
    os.makedirs(OUT_DIR, exist_ok=True)
    for name, w, h, px in (('moonlight_moon', MOON, MOON, moon()), ('moonlight_column', COL_U, COL_V, column()),
                           ('moonlight_ring', RING, RING, ring()), ('moonlight_swirl', SW * SW_FRAMES, SW, swirl())):
        path = os.path.join(OUT_DIR, name + '.png')
        write_png(path, w, h, px)
        print('wrote', os.path.relpath(path, ROOT))
