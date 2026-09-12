import zlib, struct, math, sys

def write_png(path, w, h, px):
    raw = b''
    for y in range(h):
        raw += b'\x00' + bytes(v for x in range(w) for v in px[y][x])
    def chunk(t, d):
        c = t + d
        return struct.pack('>I', len(d)) + c + struct.pack('>I', zlib.crc32(c) & 0xffffffff)
    open(path, 'wb').write(
        b'\x89PNG\r\n\x1a\n'
        + chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 6, 0, 0, 0))
        + chunk(b'IDAT', zlib.compress(raw, 9))
        + chunk(b'IEND', b''))

def hx(s):
    return (int(s[0:2],16), int(s[2:4],16), int(s[4:6],16), 255)

# one fixed gold ramp, dark pit -> white-hot rim; every pixel snaps to a rung
RAMP = [hx(c) for c in
        ('070501','140D02','241806','3E2909','6B460C','A56C11','D99A1C','FFCB3C','FFE88F','FFF8D8')]
CLEAR = (0, 0, 0, 0)

F, NF, ARMS = 32, 8, 3
R_OUT, R_RIM = 15.0, 11.6

def snap(b):
    return RAMP[max(0, min(len(RAMP) - 1, int(round(b))))]

def frame(fi):
    phase = (fi / NF) * (2 * math.pi / ARMS)
    buf = [[CLEAR] * F for _ in range(F)]
    c = (F - 1) / 2.0
    for y in range(F):
        for x in range(F):
            dx, dy = x - c, y - c
            r = math.hypot(dx, dy)
            if r > R_OUT:
                continue
            th = math.atan2(dy, dx)
            if r >= R_RIM:
                t = (r - R_RIM) / (R_OUT - R_RIM)              # 0 inner .. 1 outer
                arm = 0.5 + 0.5 * math.sin(ARMS * th + phase * ARMS)
                lit = (1.0 - abs(t - 0.40) * 1.8) * (0.62 + 0.38 * arm)
                if t >= 0.88:
                    continue                                   # crisp outer silhouette
                buf[y][x] = snap(4.2 + 5.6 * max(0.0, min(1.0, lit)))
            else:
                t = r / R_RIM                                  # 0 centre .. 1 rim
                spiral = math.sin(ARMS * th + 2.6 * math.log(max(r, 1.2)) + phase * ARMS)
                s = max(0.0, spiral) ** 2.0 * (t ** 1.6)       # arms fade into the pit
                buf[y][x] = snap(0.2 + 2.0 * t ** 1.4 + 6.2 * s)
    return buf

out = sys.argv[1]
px = [row for i in range(NF) for row in frame(i)]
write_png(out, F, F * NF, px)
print(f"wrote {out}  {F}x{F*NF}  ({NF} frames of {F}x{F})")
