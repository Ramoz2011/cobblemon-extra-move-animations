"""Generates Brave Bird's two custom sprites (pure stdlib, no Pillow).

Outputs (src/main/resources/assets/cobblemon/textures/particle/moves/):
  bravebird_feather.png  16x16 white feather on the diagonal (quill bottom-left, tip top-right): bright
                         rachis, soft vane fading toward the edge, two notches in the vane.
  bravebird_glow.png     32x32 white round glow. Minecraft's particle shader discards fragments with
                         alpha < 0.1, so the falloff reaches that level well inside the square and the
                         glow stays round. Vanilla's flash.png keeps ~0.05-0.1 alpha right up to its
                         edges and renders as a rounded square; Cobblemon's orb sprites have hard
                         pixel edges.
Both are white: the particles tint them. Run `python3 docs/tools/bravebird_textures.py`.
"""
import math, os, struct, zlib

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..')
OUT_DIR = os.path.join(ROOT, 'src/main/resources/assets/cobblemon/textures/particle/moves')

FEATHER_BASE = (2.6, 13.4)     # quill end
FEATHER_TIP = (13.2, 2.4)      # feather tip
NOTCHES = [(0.46, 1, 0.09), (0.68, -1, 0.08)]   # (position along the axis, side, half-width) cut into the vane
GLOW_R = 15.0                  # glow radius in pixels (texture is 32x32)


def write_png(path, w, h, px):
    raw = b''.join(b'\x00' + bytes(c for p in row for c in p) for row in px)

    def chunk(t, b):
        return struct.pack('>I', len(b)) + t + b + struct.pack('>I', zlib.crc32(t + b) & 0xffffffff)
    with open(path, 'wb') as f:
        f.write(b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 6, 0, 0, 0))
                + chunk(b'IDAT', zlib.compress(raw, 9)) + chunk(b'IEND', b''))


def feather(size=16):
    ax, ay = FEATHER_TIP[0] - FEATHER_BASE[0], FEATHER_TIP[1] - FEATHER_BASE[1]
    length = math.hypot(ax, ay)
    ux, uy = ax / length, ay / length          # along the rachis
    nx, ny = -uy, ux                           # across it
    px = []
    for y in range(size):
        row = []
        for x in range(size):
            cx, cy = x + 0.5 - FEATHER_BASE[0], y + 0.5 - FEATHER_BASE[1]
            s = (cx * ux + cy * uy) / length   # 0 at the quill, 1 at the tip
            d = cx * nx + cy * ny              # signed distance from the rachis (pixels)
            a = 0.0
            if 0.0 <= s <= 1.0:
                # vane half-width: none on the bare quill, widest past the middle, pointed tip
                vane = 0.0 if s < 0.16 else 3.3 * math.sin(math.pi * ((s - 0.16) / 0.84) ** 0.75)
                side = 1 if d >= 0 else -1
                for pos, nside, half in NOTCHES:
                    if side == nside and abs(s - pos) < half:
                        vane *= 0.15 + 0.85 * abs(s - pos) / half
                if abs(d) <= 0.55:
                    a = 1.0                                  # rachis
                elif abs(d) <= vane:
                    a = 0.72 - 0.42 * (abs(d) / vane) ** 1.3   # vane, softer toward the edge
                elif abs(d) <= vane + 0.6:
                    a = 0.18 * (1 - (abs(d) - vane) / 0.6)    # anti-aliased rim
            a = max(0.0, min(1.0, a))
            v = 255 if a > 0.9 else int(235 + 20 * a)      # near-white everywhere; the tint does the colour
            row.append((v, v, v, int(round(255 * a))))
        px.append(row)
    return px


def glow(size=32):
    """(1 - (r/R)^2)^2.4: a bright core easing out smoothly; alpha 0.1 is crossed at ~0.78 R."""
    c = size / 2
    px = []
    for y in range(size):
        row = []
        for x in range(size):
            r = math.hypot(x + 0.5 - c, y + 0.5 - c) / GLOW_R
            a = (1 - r * r) ** 2.4 if r < 1 else 0.0
            row.append((255, 255, 255, int(round(255 * a))))
        px.append(row)
    return px


if __name__ == '__main__':
    for name, w, h, px in (('bravebird_feather', 16, 16, feather()), ('bravebird_glow', 32, 32, glow())):
        path = os.path.join(OUT_DIR, name + '.png')
        write_png(path, w, h, px)
        print('wrote', os.path.relpath(path, ROOT))
