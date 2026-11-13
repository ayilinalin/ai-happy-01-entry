#!/usr/bin/env python3
"""ai-happy-01 v2 -- "Teacup kitten, golden hour".

A tiny ginger kitten sits in a floral teacup at golden hour: warm backlight,
sunflower bokeh, soft steam curls, one paw draped over the rim. Drawn
procedurally with the Python standard library only (no PIL, no numpy, no
network). Deterministic: one fixed seed drives every random stroke, so two
runs write byte-identical output.

Writes /output/entry.png (or $MAKEFUN_OUTPUT_DIR/entry.png), 768x768.
"""

import math
import os
import random
import struct
import zlib

W = H = 768
SEED = 20261114

rng = random.Random(SEED)
buf = bytearray(W * H * 3)


def _i(x, y):
    return (y * W + x) * 3


def put(x, y, r, g, b):
    if 0 <= x < W and 0 <= y < H:
        i = _i(x, y)
        buf[i] = r
        buf[i + 1] = g
        buf[i + 2] = b


def blend(x, y, r, g, b, a):
    if 0 <= x < W and 0 <= y < H and a > 0.0:
        if a >= 1.0:
            put(x, y, r, g, b)
            return
        i = _i(x, y)
        ia = 1.0 - a
        buf[i] = int(buf[i] * ia + r * a)
        buf[i + 1] = int(buf[i + 1] * ia + g * a)
        buf[i + 2] = int(buf[i + 2] * ia + b * a)


def hspan(y, x0, x1, r, g, b):
    if y < 0 or y >= H:
        return
    x0 = max(0, int(math.floor(x0)))
    x1 = min(W, int(math.ceil(x1)))
    if x1 <= x0:
        return
    s = y * W * 3 + x0 * 3
    buf[s:s + (x1 - x0) * 3] = bytes((r, g, b)) * (x1 - x0)


def ellipse(cx, cy, rx, ry, r, g, b):
    y0 = max(0, int(cy - ry))
    y1 = min(H - 1, int(cy + ry) + 1)
    for y in range(y0, y1 + 1):
        t = (y - cy) / ry
        d = rx * math.sqrt(max(0.0, 1.0 - t * t))
        hspan(y, cx - d, cx + d, r, g, b)


def rot_ellipse(cx, cy, rx, ry, ang, r, g, b, a=1.0):
    ca, sa = math.cos(ang), math.sin(ang)
    ext = int(rx + ry) + 2
    x0 = max(0, int(cx - ext))
    x1 = min(W - 1, int(cx + ext))
    y0 = max(0, int(cy - ext))
    y1 = min(H - 1, int(cy + ext))
    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1):
            dx, dy = x - cx, y - cy
            u = dx * ca + dy * sa
            v = -dx * sa + dy * ca
            if (u / rx) ** 2 + (v / ry) ** 2 <= 1.0:
                if a >= 1.0:
                    put(x, y, r, g, b)
                else:
                    blend(x, y, r, g, b, a)


def soft_ellipse(cx, cy, rx, ry, ang, r, g, b, a0, feather=0.55):
    """Soft-edged ellipse: full alpha a0 inside (1-feather), fading to 0."""
    ca, sa = math.cos(ang), math.sin(ang)
    ext = int(rx + ry) + 2
    x0 = max(0, int(cx - ext))
    x1 = min(W - 1, int(cx + ext))
    y0 = max(0, int(cy - ext))
    y1 = min(H - 1, int(cy + ext))
    inner = 1.0 - feather
    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1):
            dx, dy = x - cx, y - cy
            u = dx * ca + dy * sa
            v = -dx * sa + dy * ca
            q = (u / rx) ** 2 + (v / ry) ** 2
            if q >= 1.0:
                continue
            d = math.sqrt(q)
            if d <= inner:
                al = a0
            else:
                al = a0 * (1.0 - (d - inner) / feather)
            if al > 0.003:
                blend(x, y, r, g, b, al)


def soft_disc(cx, cy, rad, r, g, b, a0, feather=0.55):
    soft_ellipse(cx, cy, rad, rad, 0.0, r, g, b, a0, feather)


def triangle(x0, y0, x1, y1, x2, y2, r, g, b):
    pts = sorted(((x0, y0), (x1, y1), (x2, y2)), key=lambda p: p[1])
    (ax, ay), (bx, by), (cx, cy) = pts
    for y in range(max(0, int(ay)), min(H, int(cy) + 1)):
        if y < by:
            t1 = (y - ay) / max(1.0, by - ay)
            xa = ax + (bx - ax) * t1
        else:
            xa = bx
        t2 = (y - ay) / max(1.0, cy - ay)
        xb = ax + (cx - ax) * t2
        hspan(y, min(xa, xb), max(xa, xb), r, g, b)


def line(x0, y0, x1, y1, r, g, b, a=1.0):
    steps = int(max(abs(x1 - x0), abs(y1 - y0))) + 1
    for i in range(steps + 1):
        t = i / steps
        blend(int(round(x0 + (x1 - x0) * t)),
              int(round(y0 + (y1 - y0) * t)), r, g, b, a)


def vgrad(y0, y1, stops):
    """Vertical gradient between (frac, color) stops, frac in 0..1."""
    for y in range(max(0, y0), min(H, y1 + 1)):
        f = (y - y0) / max(1.0, y1 - y0)
        for k in range(len(stops) - 1):
            f0, c0 = stops[k]
            f1, c1 = stops[k + 1]
            if f0 <= f <= f1:
                t = (f - f0) / max(1e-9, f1 - f0)
                hspan(y, 0, W,
                      int(c0[0] + (c1[0] - c0[0]) * t),
                      int(c0[1] + (c1[1] - c0[1]) * t),
                      int(c0[2] + (c1[2] - c0[2]) * t))
                break


# ---------------------------------------------------------------- background
def draw_background():
    vgrad(0, 560, [
        (0.00, (255, 203, 118)),
        (0.35, (247, 182, 100)),
        (0.65, (214, 168, 96)),
        (1.00, (150, 138, 82)),
    ])
    # sun glow, top right
    soft_ellipse(645, 85, 280, 210, 0.0, 255, 228, 150, 0.55, 0.7)
    # sunflower bokeh: yellow discs with soft dark centres
    for (cx, cy, rad, cr) in [(150, 130, 72, 26), (625, 215, 56, 19),
                              (88, 305, 50, 17), (705, 335, 62, 21),
                              (560, 118, 42, 14), (330, 95, 46, 15)]:
        soft_disc(cx, cy, rad, 242, 193, 78, 0.6, 0.75)
        soft_disc(cx, cy, cr, 122, 74, 28, 0.5, 0.65)
    # leafy green bokeh
    for (cx, cy, rad, a) in [(420, 88, 82, 0.38), (250, 205, 62, 0.34),
                             (680, 92, 72, 0.38), (58, 185, 56, 0.38),
                             (480, 185, 46, 0.3), (150, 430, 60, 0.3),
                             (700, 480, 66, 0.3)]:
        soft_disc(cx, cy, rad, 125, 138, 74, a, 0.75)
    # sparkles
    for (cx, cy, rad) in [(210, 70, 7), (520, 60, 6), (90, 250, 6),
                          (660, 280, 7), (400, 140, 5)]:
        soft_disc(cx, cy, rad, 255, 240, 190, 0.6, 0.5)


def draw_table():
    vgrad(560, H, [
        (0.00, (169, 116, 63)),
        (0.50, (140, 92, 47)),
        (1.00, (110, 69, 37)),
    ])
    for y in (612, 668, 724):
        hspan(y, 0, W, 132, 84, 42)
    soft_ellipse(500, 705, 270, 62, 0.0, 255, 198, 118, 0.16, 0.7)
    soft_ellipse(150, 720, 200, 55, 0.0, 255, 205, 130, 0.12, 0.7)


# ------------------------------------------------------------------- teacup
CREAM = (247, 239, 221)
CREAM_D = (232, 217, 189)
GOLD = (217, 164, 65)
GOLD_L = (242, 205, 122)


def rose(cx, cy, s):
    petal = (232, 160, 168)
    petal_d = (214, 128, 140)
    for k in range(5):
        ang = k * 2.0 * math.pi / 5.0 - math.pi / 2.0
        px = cx + math.cos(ang) * s * 0.52
        py = cy + math.sin(ang) * s * 0.52
        rot_ellipse(px, py, s * 0.44, s * 0.30, ang, petal[0], petal[1], petal[2])
    ellipse(cx, cy, s * 0.30, s * 0.30, petal_d[0], petal_d[1], petal_d[2])
    ellipse(cx, cy, s * 0.14, s * 0.14, 244, 214, 120)
    rot_ellipse(cx - s * 1.05, cy + s * 0.75, s * 0.52, s * 0.22, -0.6,
                125, 155, 90)
    rot_ellipse(cx + s * 1.05, cy + s * 0.70, s * 0.52, s * 0.22, 0.6,
                125, 155, 90)


def draw_cup():
    # shadow under saucer
    soft_ellipse(384, 702, 335, 46, 0.0, 60, 35, 15, 0.28, 0.6)
    # saucer with gold edge
    ellipse(384, 692, 305, 52, GOLD[0], GOLD[1], GOLD[2])
    ellipse(384, 692, 294, 46, 238, 226, 198)
    ellipse(384, 692, 250, 36, 232, 218, 186)
    # handle: thick arc of discs on the right, bigger and bolder
    for k in range(41):
        t = -1.05 + 2.1 * k / 40.0
        hx = 618 + 74 * math.cos(t)
        hy = 560 + 102 * math.sin(t)
        soft_disc(int(hx), int(hy), 21, CREAM[0], CREAM[1], CREAM[2], 1.0, 0.25)
    for k in range(41):
        t = -1.05 + 2.1 * k / 40.0
        hx = 618 + 88 * math.cos(t)
        hy = 560 + 116 * math.sin(t)
        soft_disc(int(hx), int(hy), 5, GOLD_L[0], GOLD_L[1], GOLD_L[2], 0.9, 0.4)
    # body: rows narrowing toward the foot
    for y in range(468, 691):
        f = (y - 468) / 222.0
        hw = 282 - (282 - 150) * (f ** 1.25)
        hspan(y, 384 - hw, 384 + hw, CREAM[0], CREAM[1], CREAM[2])
    # body shading: warm light right, soft shadow left and bottom
    for y in range(468, 691):
        f = (y - 468) / 222.0
        hw = 282 - (282 - 150) * (f ** 1.25)
        for x in range(int(384 - hw), int(384 + hw) + 1):
            g = (x - 384) / hw  # -1 left .. +1 right
            al = 0.0
            cr = cg = cb = 0
            if g < -0.35:
                al = 0.20 * (-g - 0.35) / 0.65
                cr, cg, cb = 190, 160, 110
            elif g > 0.45:
                al = 0.16 * (g - 0.45) / 0.55
                cr, cg, cb = 255, 248, 225
            if f > 0.8:
                al = max(al, 0.12 * (f - 0.8) / 0.2)
                cr, cg, cb = 180, 145, 95
            if al > 0.003:
                blend(x, y, cr, cg, cb, al)
    # foot
    ellipse(384, 690, 122, 18, CREAM_D[0], CREAM_D[1], CREAM_D[2])
    ellipse(384, 688, 112, 13, CREAM[0], CREAM[1], CREAM[2])
    # floral pattern on the front
    rose(300, 585, 26)
    rose(430, 615, 30)
    rose(520, 565, 22)
    rose(215, 600, 18)
    # small sprigs
    for (sx, sy, ang) in [(360, 640, 0.5), (470, 660, -0.4), (255, 640, 0.3)]:
        rot_ellipse(sx, sy, 16, 5, ang, 125, 155, 90)
        ellipse(sx, sy - 6, 4, 4, 232, 160, 168)
    # gold rim + tea surface, with a soft inner shadow so the tea reads deep
    ellipse(384, 468, 282, 66, GOLD[0], GOLD[1], GOLD[2])
    ellipse(384, 468, 270, 59, 233, 211, 168)
    soft_ellipse(384, 468, 262, 52, 0.0, 190, 150, 95, 0.18, 0.7)
    soft_ellipse(300, 445, 90, 26, 0.0, 255, 240, 200, 0.25, 0.7)
    # rim highlight, front-left arc
    for k in range(31):
        t = math.pi * (0.08 + 0.34 * k / 30.0)
        hx = 384 + 276 * math.cos(t)
        hy = 468 + 62 * math.sin(t)
        soft_disc(int(hx), int(hy), 4, GOLD_L[0], GOLD_L[1], GOLD_L[2], 0.9, 0.4)


# ------------------------------------------------------------------- kitten
GINGER = (229, 154, 82)
GINGER_L = (246, 193, 132)
GINGER_D = (201, 122, 51)
MUZZLE = (251, 227, 194)


def draw_kitten():
    # ears (behind head)
    rot_ellipse(272, 222, 52, 78, -0.45, GINGER[0], GINGER[1], GINGER[2])
    rot_ellipse(496, 222, 52, 78, 0.45, GINGER[0], GINGER[1], GINGER[2])
    rot_ellipse(278, 232, 28, 48, -0.45, 232, 154, 144)
    rot_ellipse(490, 232, 28, 48, 0.45, 232, 154, 144)
    # head
    ellipse(384, 335, 150, 135, GINGER[0], GINGER[1], GINGER[2])
    # per-pixel face shading: edge darkening + cream muzzle
    cx, cy, rx, ry = 384, 335, 150, 135
    for y in range(cy - ry, cy + ry + 1):
        for x in range(cx - rx, cx + rx + 1):
            q = ((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2
            if q > 1.0:
                continue
            if q > 0.55:
                al = 0.10 * (q - 0.55) / 0.45
                blend(x, y, 190, 110, 45, al)
            m = ((x - 384) / 80.0) ** 2 + ((y - 410) / 54.0) ** 2
            if m < 1.0:
                blend(x, y, MUZZLE[0], MUZZLE[1], MUZZLE[2], (1.0 - m) * 0.8)
    # forehead stripes
    for (sx, sy, ln, ang) in [(352, 238, 34, 0.15), (384, 228, 38, 0.0),
                              (416, 238, 34, -0.15), (330, 262, 26, 0.35),
                              (438, 262, 26, -0.35)]:
        dx = math.sin(ang) * ln / 2
        dy = math.cos(ang) * ln / 2
        line(int(sx - dx), int(sy - dy), int(sx + dx), int(sy + dy),
             GINGER_D[0], GINGER_D[1], GINGER_D[2], 0.65)
    # cheek stripes
    for (sx, sy, ln, ang) in [(252, 355, 22, 0.5), (516, 355, 22, -0.5),
                              (258, 385, 20, 0.7), (510, 385, 20, -0.7)]:
        dx = math.sin(ang) * ln / 2
        dy = math.cos(ang) * ln / 2
        line(int(sx - dx), int(sy - dy), int(sx + dx), int(sy + dy),
             GINGER_D[0], GINGER_D[1], GINGER_D[2], 0.5)
    # fluffy edge strokes around the head, short and soft
    for k in range(64):
        ang = k * 2.0 * math.pi / 64.0
        ex = 384 + 150 * math.cos(ang)
        ey = 335 + 135 * math.sin(ang)
        ox = 384 + 157 * math.cos(ang)
        oy = 335 + 142 * math.sin(ang)
        col = GINGER_L if k % 2 else GINGER
        line(int(ex), int(ey), int(ox), int(oy), col[0], col[1], col[2], 0.55)
    # fur strokes on the face
    for _ in range(700):
        a = rng.uniform(0, 2 * math.pi)
        rr = math.sqrt(rng.uniform(0, 1))
        x = 384 + 138 * rr * math.cos(a)
        y = 335 + 123 * rr * math.sin(a)
        ln = rng.uniform(4, 11)
        ang = rng.uniform(-0.35, 0.35) + math.pi / 2
        col = GINGER_D if rng.random() < 0.45 else GINGER_L
        line(int(x), int(y), int(x + math.cos(ang) * ln),
             int(y + math.sin(ang) * ln), col[0], col[1], col[2], 0.35)
    # eyes
    for ecx in (318, 450):
        draw_eye(ecx, 330)
    # nose + mouth
    triangle(372, 392, 396, 392, 384, 407, 224, 120, 120)
    ellipse(378, 398, 3, 2, 170, 80, 80)
    ellipse(390, 398, 3, 2, 170, 80, 80)
    line(384, 407, 384, 417, 190, 120, 100, 0.8)
    line(384, 417, 371, 425, 190, 120, 100, 0.8)
    line(384, 417, 397, 425, 190, 120, 100, 0.8)
    # whiskers: short, drooping, staying on the muzzle
    for (x0, y0, x1, y1) in [(334, 402, 282, 392), (336, 414, 286, 414),
                             (338, 426, 292, 434), (434, 402, 486, 392),
                             (432, 414, 482, 414), (430, 426, 476, 434)]:
        line(x0, y0, x1, y1, 255, 244, 222, 0.8)


def draw_eye(cx, cy):
    # dark outline ring
    ellipse(cx, cy, 41, 43, 122, 74, 40)
    # iris, per-pixel radial profile with striations
    for y in range(cy - 36, cy + 37):
        for x in range(cx - 36, cx + 37):
            dx, dy = x - cx, y - cy
            d = math.hypot(dx, dy)
            if d > 36:
                continue
            if d <= 14:
                put(x, y, 16, 36, 42)
                continue
            t = d / 36.0
            ang = math.atan2(dy, dx)
            wob = 0.5 + 0.5 * math.sin(ang * 14.0 + d * 0.6)
            if t > 0.86:
                r, g, b = 20, 80, 92
            elif t > 0.55:
                f = (t - 0.55) / 0.31
                r = int(47 + (20 - 47) * f)
                g = int(143 + (80 - 143) * f)
                b = int(158 + (92 - 158) * f)
            else:
                f = (0.55 - t) / 0.55
                r = int(47 + (127 - 47) * f * 0.7)
                g = int(143 + (196 - 143) * f * 0.7)
                b = int(158 + (201 - 158) * f * 0.7)
            r = int(r * (0.92 + 0.16 * wob))
            g = int(g * (0.92 + 0.16 * wob))
            b = int(b * (0.92 + 0.16 * wob))
            put(x, y, max(0, min(255, r)), max(0, min(255, g)),
                max(0, min(255, b)))
    # highlights: big catchlight + small one
    soft_disc(cx - 11, cy - 13, 10, 255, 255, 255, 0.95, 0.35)
    soft_disc(cx + 13, cy + 12, 5, 255, 255, 255, 0.8, 0.35)
    # upper lid shadow
    soft_ellipse(cx, cy - 30, 38, 14, 0.0, 201, 122, 51, 0.35, 0.6)


def draw_paw():
    # soft shadow on the rim, then the paw draped over the FRONT rim edge
    soft_ellipse(470, 528, 66, 18, 0.0, 120, 80, 30, 0.20, 0.6)
    rot_ellipse(470, 512, 60, 36, -0.12, GINGER[0], GINGER[1], GINGER[2])
    rot_ellipse(470, 504, 52, 26, -0.12, 244, 200, 142)
    for tx in (444, 470, 496):
        line(tx, 530, tx + 3, 512, GINGER_D[0], GINGER_D[1], GINGER_D[2], 0.6)


# ------------------------------------------------------------------- atmosphere
def steam_wisp(x0, y0, height, phase, alpha):
    for k in range(80):
        t = k / 79.0
        x = x0 + 34 * math.sin(t * 6.5 + phase) + 22 * t
        y = y0 - height * t
        rad = 22 * (1.0 - 0.45 * t) + 6
        soft_disc(int(x), int(y), int(rad), 255, 250, 240,
                  alpha * (1.0 - 0.55 * t), 0.65)


def draw_steam():
    steam_wisp(215, 440, 300, 0.0, 0.22)
    steam_wisp(290, 448, 250, 2.1, 0.16)
    steam_wisp(540, 442, 210, 4.0, 0.13)


def draw_atmosphere():
    # one diagonal sunbeam from the top right
    soft_ellipse(560, 130, 320, 55, -0.5, 255, 232, 170, 0.10, 0.7)
    # drifting petal + tiny butterfly, the small story
    rot_ellipse(228, 252, 13, 6, 0.7, 242, 170, 175)
    rot_ellipse(148, 180, 20, 12, -0.5, 242, 165, 65)
    rot_ellipse(170, 180, 20, 12, 0.5, 242, 165, 65)
    rot_ellipse(148, 180, 12, 7, -0.5, 214, 120, 40)
    rot_ellipse(170, 180, 12, 7, 0.5, 214, 120, 40)
    line(159, 176, 159, 196, 90, 60, 30, 0.9)
    line(156, 174, 148, 164, 90, 60, 30, 0.8)
    line(162, 174, 170, 164, 90, 60, 30, 0.8)


def finish():
    # gentle vignette + a whisper of grain so gradients do not band
    cx, cy = W / 2.0, H / 2.0
    maxd2 = cx * cx + cy * cy
    for y in range(H):
        dy = y - cy
        for x in range(W):
            dx = x - cx
            d2 = (dx * dx + dy * dy) / maxd2
            v = 1.0 - 0.12 * max(0.0, d2 - 0.30) / 0.70
            n = rng.randint(-2, 2)
            i = _i(x, y)
            buf[i] = max(0, min(255, int(buf[i] * v) + n))
            buf[i + 1] = max(0, min(255, int(buf[i + 1] * v) + n))
            buf[i + 2] = max(0, min(255, int(buf[i + 2] * v) + n))


# ------------------------------------------------------------------- png out
def write_png(path):
    raw = bytearray()
    stride = W * 3
    for y in range(H):
        raw.append(0)
        raw += buf[y * stride:(y + 1) * stride]
    comp = zlib.compress(bytes(raw), 6)

    def chunk(tag, data):
        c = struct.pack(">I", len(data)) + tag + data
        return c + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    ihdr = struct.pack(">IIBBBBB", W, H, 8, 2, 0, 0, 0)
    png = (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
           + chunk(b"IDAT", comp) + chunk(b"IEND", b""))
    with open(path, "wb") as f:
        f.write(png)
    return len(png)


def main():
    outdir = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")
    os.makedirs(outdir, exist_ok=True)
    draw_background()
    draw_table()
    draw_cup()
    draw_steam()  # behind the kitten: steam must never veil the eyes
    draw_kitten()
    draw_paw()
    draw_atmosphere()
    finish()
    size = write_png(os.path.join(outdir, "entry.png"))
    print(f"wrote {size} bytes, {W}x{H}")


if __name__ == "__main__":
    main()
