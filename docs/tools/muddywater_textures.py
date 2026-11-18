"""Generates the texture of Muddy Water's wave (pure stdlib, no Pillow).

Output (src/main/resources/assets/cobblemon_extra_move_animation/textures/effect/):
  muddy_water.png  32x32 greyscale, tiles seamlessly in both directions. A network of pale streaks over
                   darker water, like the caustic lines on Sword/Shield's muddy flood, stretched along v
                   (the way the water flows over the wave), plus a few bright pixels for a wet glint.
                   Greyscale on purpose: the wave's vertex colours tint it (deep brown body, tan foam),
                   so the same texture would serve another wave in another colour.

Drawn by Java (client/wave/WaveSequence), not as a particle, so it lives in this mod's namespace. The
texture repeats (Minecraft wraps standalone textures), which lets the wave scroll it along its surface.
Run `python3 docs/tools/muddywater_textures.py`.
"""
import math, os, random, struct, zlib

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..')
OUT_DIR = os.path.join(ROOT, 'src/main/resources/assets/cobblemon_extra_move_animation/textures/effect')

SIZE = 32
SEED = 330                 # Muddy Water's move number: the same texture every run
CELLS = 7                  # cells in the streak network
STRETCH = 0.62             # < 1 stretches the cells along v (the flow)
LEVELS = [0.6, 0.67, 0.74, 0.82, 0.91, 1.0]   # pixel-art palette steps (grey); bright, the vertex colours darken it
ALPHA = 248


def write_png(path, w, h, px):
    raw = b''.join(b'\x00' + bytes(c for p in row for c in p) for row in px)

    def chunk(t, b):
        return struct.pack('>I', len(b)) + t + b + struct.pack('>I', zlib.crc32(t + b) & 0xffffffff)
    with open(path, 'wb') as f:
        f.write(b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 6, 0, 0, 0))
                + chunk(b'IDAT', zlib.compress(raw, 9)) + chunk(b'IEND', b''))
    print('wrote', os.path.relpath(path, ROOT))


def wrapped(d):
    """Shortest distance on the torus (the texture tiles)."""
    d = abs(d) % SIZE
    return min(d, SIZE - d)


def soft(x, y):
    """Tileable low-frequency variation in -1..1 (sums of whole sine periods across the tile)."""
    a = 2 * math.pi / SIZE
    return (0.5 * math.sin(a * x + 1.3) * math.cos(a * y * 2 - 0.4)
            + 0.3 * math.sin(a * (x + y) * 2 + 2.1) + 0.2 * math.cos(a * (x * 3 - y) + 0.7))


def muddy_water():
    rnd = random.Random(SEED)
    points = [(rnd.uniform(0, SIZE), rnd.uniform(0, SIZE)) for _ in range(CELLS)]
    px = []
    for y in range(SIZE):
        row = []
        for x in range(SIZE):
            ds = sorted(math.hypot(wrapped(x + 0.5 - cx), wrapped(y + 0.5 - cy) * STRETCH) for cx, cy in points)
            edge = ds[1] - ds[0]               # small along the borders between cells
            v = 0.6 + 0.09 * soft(x, y) - 0.08 * min(ds[0] / 7, 1)
            if edge < 0.6:
                v = 1.0
            elif edge < 1.25:
                v = 0.82
            elif edge < 2.0:
                v = max(v, 0.7)
            row.append(v)
        px.append(row)
    # a few wet glints in the darker water
    for _ in range(7):
        x, y = rnd.randrange(SIZE), rnd.randrange(SIZE)
        if px[y][x] < 0.7:
            px[y][x] = 1.0
    out = []
    for row in px:
        line = []
        for v in row:
            q = min(LEVELS, key=lambda lv: abs(lv - v))
            c = round(255 * q)
            line.append((c, c, c, ALPHA))
        out.append(line)
    return out


if __name__ == '__main__':
    os.makedirs(OUT_DIR, exist_ok=True)
    write_png(os.path.join(OUT_DIR, 'muddy_water.png'), SIZE, SIZE, muddy_water())
