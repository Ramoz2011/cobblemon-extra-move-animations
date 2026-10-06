"""Generates darkestlariat_shard.png: 3 jagged dark-energy shards (48x16, three 16x16 variants).

Darkest Lariat's in-game impact (SM / SwSh) throws out jagged black fragments with
red outlines. Tinting can't make that from an official texture (tint multiplies, so a
dark body can't get a bright rim), so the colours are baked into the sprite and the
particle uses a white tint. Pure stdlib, same PNG writer as makeitrain_coin_texture.py.

Usage: python3 darkestlariat_shard_texture.py <out.png>
"""
import zlib, struct, sys

def write_png(path, w, h, px):
    raw = b''
    for y in range(h):
        raw += b'\x00' + bytes(v for x in range(w) for v in px[y][x])
    def chunk(t, d):
        c = t + d
        return struct.pack('>I', len(d)) + c + struct.pack('>I', zlib.crc32(c) & 0xffffffff)
    out = b'\x89PNG\r\n\x1a\n'
    out += chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 6, 0, 0, 0))
    out += chunk(b'IDAT', zlib.compress(raw, 9))
    out += chunk(b'IEND', b'')
    open(path, 'wb').write(out)

def hx(s):
    return (int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16), 255)

# palette: one fixed ramp, every pixel snaps to it (see makeitrain notes: no per-channel mixing)
HOT   = hx('FF8A86')   # lit rim highlight
RIM   = hx('D81B2C')   # crimson outline
CRACK = hx('7A0F1E')   # inner fracture line
BODY1 = hx('22090E')   # body, lit side
BODY2 = hx('14060A')   # body, shadow side
CLEAR = (0, 0, 0, 0)

F = 16
# Irregular shard outlines, vertices in pixel units inside a 16x16 frame.
SHAPES = [
    [(2, 15), (5, 6), (9, 0), (10.5, 6.5), (15, 3), (12, 10), (14.5, 15), (8, 12.5)],   # long splinter
    [(0, 12), (6, 2), (9.5, 7), (16, 3.5), (11.5, 14.5), (5, 12.5)],                    # broken wedge
    [(3, 2), (8, 0.5), (9, 5), (15, 3.5), (12.5, 10), (15, 15), (6, 14.5), (1, 10), (5, 7)],  # notched chunk
]
# One fracture line per shard (start, end), drawn in CRACK inside the body.
CRACKS = [((5, 12), (10, 5)), ((4, 10), (12, 7)), ((5, 5), (10, 12))]

def inside(poly, x, y):
    # even-odd rule at the pixel centre
    px, py = x + 0.5, y + 0.5
    c = False
    n = len(poly)
    for i in range(n):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % n]
        if (y1 > py) != (y2 > py):
            xi = x1 + (py - y1) * (x2 - x1) / (y2 - y1)
            if px < xi:
                c = not c
    return c

def frame(poly, crack):
    mask = [[inside(poly, x, y) for x in range(F)] for y in range(F)]
    buf = [[CLEAR] * F for _ in range(F)]
    for y in range(F):
        for x in range(F):
            if not mask[y][x]:
                continue
            edge_l = x == 0 or not mask[y][x - 1]
            edge_u = y == 0 or not mask[y - 1][x]
            edge_r = x == F - 1 or not mask[y][x + 1]
            edge_d = y == F - 1 or not mask[y + 1][x]
            if edge_l or edge_u:
                buf[y][x] = HOT if (edge_l and edge_u) else RIM     # light comes from upper-left
            elif edge_r or edge_d:
                buf[y][x] = RIM
            else:
                buf[y][x] = BODY1 if (x + y) < 15 else BODY2
    # fracture line (Bresenham), only over body pixels so the rim stays clean
    (x0, y0), (x1, y1) = crack
    dx, dy = abs(x1 - x0), -abs(y1 - y0)
    sx, sy = (1 if x0 < x1 else -1), (1 if y0 < y1 else -1)
    err = dx + dy
    while True:
        if buf[y0][x0] in (BODY1, BODY2):
            buf[y0][x0] = CRACK
        if (x0, y0) == (x1, y1):
            break
        e2 = 2 * err
        if e2 >= dy:
            err += dy; x0 += sx
        if e2 <= dx:
            err += dx; y0 += sy
    return buf

frames = [frame(p, c) for p, c in zip(SHAPES, CRACKS)]
W = F * len(frames)
px = [[CLEAR] * W for _ in range(F)]
for i, fr in enumerate(frames):
    for y in range(F):
        for x in range(F):
            px[y][i * F + x] = fr[y][x]

out = sys.argv[1]
write_png(out, W, F, px)
print(f"wrote {out}  {W}x{F}  ({len(frames)} variants of {F}x{F})")
CH = {HOT: '@', RIM: '#', CRACK: '/', BODY1: '.', BODY2: ':', CLEAR: ' '}
for y in range(F):
    print('|' + '|'.join(''.join(CH[fr[y][x]] for x in range(F)) for fr in frames) + '|')
