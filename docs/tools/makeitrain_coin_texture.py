import zlib, struct, math, sys

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
    return (int(s[0:2],16), int(s[2:4],16), int(s[4:6],16), 255)

# gold ramp, brightest -> darkest
GLINT = hx('FFFBE0')
L1    = hx('FFF0A8')
L2    = hx('FFE067')
M1    = hx('FFCB33')
M2    = hx('EFAF22')
S1    = hx('D08F16')
S2    = hx('A96F10')
RIM   = hx('7A4E08')
CLEAR = (0,0,0,0)

FACE = [L1, L2, M1, M2, S1]           # face shading ramp
EDGE = [L1, L2, M1, M2, S1, S2]       # edge-on shading ramp

F = 16          # frame size
HALF = 7.0      # coin radius in px (vertical, constant)
# half-widths across one full revolution (8 frames)
WIDTHS = [7.0, 5.4, 3.4, 1.55, 0.85, 1.55, 3.4, 5.4]

def frame(hw):
    buf = [[CLEAR]*F for _ in range(F)]
    cx = cy = (F-1)/2.0
    edge_on = hw < 2.4
    for y in range(F):
        for x in range(F):
            dx = x - cx
            dy = y - cy
            u = dx / hw
            v = dy / HALF
            d = u*u + v*v
            if d > 1.0:
                continue
            r = math.sqrt(d)
            if edge_on:
                # read as the milled rim of the coin catching light
                t = abs(u)                       # 0 at centre column, 1 at silhouette
                k = 0 if t < 0.34 else (2 if t < 0.62 else (3 if t < 0.85 else 4))
                if abs(v) > 0.80:                # darken the rounded top/bottom caps
                    k = min(len(EDGE)-1, k + 2)
                elif abs(v) > 0.58:
                    k = min(len(EDGE)-1, k + 1)
                buf[y][x] = EDGE[k]
                if t < 0.34 and -0.30 < v < 0.10:   # specular flash along the milled rim
                    buf[y][x] = GLINT
            else:
                if r > 0.80:                     # beveled outer rim
                    lit = (-u*0.55 - v*0.84)     # upper-left lit
                    buf[y][x] = S1 if lit > 0.35 else (S2 if lit > -0.35 else RIM)
                else:
                    lit = (-u*0.55 - v*0.84)     # -1.0 .. 1.0
                    k = int(round((1.0 - lit) * 2.0))
                    k = max(0, min(4, k))
                    if 0.50 < r < 0.66:          # raised inner ring on the face
                        k = min(4, k + 1)
                    buf[y][x] = FACE[k]
                    # specular glint, upper-left
                    if hw > 4.0 and (u + 0.40)**2 + (v + 0.44)**2 < 0.052:
                        buf[y][x] = GLINT
    return buf

frames = []
for i, hw in enumerate(WIDTHS):
    f = frame(hw)
    if i >= 4:                       # back half of the revolution: reverse face, light flips
        f = [list(reversed(row)) for row in f]
    frames.append(f)
H = F * len(frames)
px = [[CLEAR]*F for _ in range(H)]
for i, fr in enumerate(frames):
    for y in range(F):
        px[i*F + y] = fr[y]

out = sys.argv[1]
write_png(out, F, H, px)
print(f"wrote {out}  {F}x{H}  ({len(frames)} frames of {F}x{F})")

CH = {GLINT:'@', L1:'%', L2:'8', M1:'o', M2:'*', S1:'+', S2:'-', RIM:'.', CLEAR:' '}
for i, fr in enumerate(frames):
    print(f"--- frame {i} (hw={WIDTHS[i]}) ---")
    for y in range(F):
        print('|' + ''.join(CH.get(fr[y][x], '?') for x in range(F)) + '|')
