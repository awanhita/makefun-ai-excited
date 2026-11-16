#!/usr/bin/env python3
"""The Second Before Everything Changes — ai-excited-01 entry.

A lone figure on a cliff edge watches a colossal ring of dawn-light open
in the sky like a portal, a river of light pouring out of it into their
raised hand.

Pure Python 3.13 standard library: the picture is drawn pixel by pixel
from a fixed seed, so two runs write byte-identical PNGs. No network, no
clock, no files read, no downloaded image, no font file.
"""

import math
import os
import random
import struct
import zlib

W = 1024
H = 1024
SEED = 20261116


# ---------------------------------------------------------------- canvas
class Canvas:
    def __init__(self, w, h):
        self.w = w
        self.h = h
        self.px = bytearray(w * h * 3)

    def _idx(self, x, y):
        return (y * self.w + x) * 3

    def set(self, x, y, color):
        if 0 <= x < self.w and 0 <= y < self.h:
            i = self._idx(x, y)
            self.px[i] = color[0]
            self.px[i + 1] = color[1]
            self.px[i + 2] = color[2]

    def add(self, x, y, color, amount=1.0):
        """Additive blend: colour * amount added, clamped at 255."""
        if 0 <= x < self.w and 0 <= y < self.h and amount > 0.0:
            i = self._idx(x, y)
            r = self.px[i] + color[0] * amount
            g = self.px[i + 1] + color[1] * amount
            b = self.px[i + 2] + color[2] * amount
            self.px[i] = 255 if r > 255 else int(r)
            self.px[i + 1] = 255 if g > 255 else int(g)
            self.px[i + 2] = 255 if b > 255 else int(b)

    def fill_row(self, y, color):
        i = y * self.w * 3
        self.px[i:i + self.w * 3] = bytes(color) * self.w

    def disc(self, cx, cy, r, color, additive=False):
        """Filled circle, opaque or additive."""
        r = int(r)
        if r <= 0:
            return
        x0 = max(0, cx - r)
        x1 = min(self.w - 1, cx + r)
        y0 = max(0, cy - r)
        y1 = min(self.h - 1, cy + r)
        r2 = r * r
        for y in range(y0, y1 + 1):
            dy = y - cy
            dy2 = dy * dy
            for x in range(x0, x1 + 1):
                dx = x - cx
                if dx * dx + dy2 <= r2:
                    if additive:
                        self.add(x, y, color, 1.0)
                    else:
                        self.set(x, y, color)

    def glow(self, cx, cy, r, color, strength=1.0):
        """Soft radial glow: intensity falls off as (1 - d^2/r^2)^2."""
        r = int(r)
        if r <= 0:
            return
        x0 = max(0, cx - r)
        x1 = min(self.w - 1, cx + r)
        y0 = max(0, cy - r)
        y1 = min(self.h - 1, cy + r)
        r2 = float(r * r)
        for y in range(y0, y1 + 1):
            dy = y - cy
            dy2 = dy * dy
            for x in range(x0, x1 + 1):
                dx = x - cx
                d2 = dx * dx + dy2
                if d2 < r2:
                    t = 1.0 - d2 / r2
                    self.add(x, y, color, t * t * strength)

    def thick_line(self, x0, y0, x1, y1, width, color, additive=False):
        """A line drawn as a chain of discs."""
        length = math.hypot(x1 - x0, y1 - y0)
        steps = max(1, int(length / max(1.0, width * 0.5)))
        radius = width / 2.0
        for s in range(steps + 1):
            t = s / steps
            x = int(round(x0 + (x1 - x0) * t))
            y = int(round(y0 + (y1 - y0) * t))
            self.disc(x, y, radius, color, additive=additive)

    def poly(self, points, color):
        """Filled polygon (scanline fill)."""
        if len(points) < 3:
            return
        ymin = max(0, min(p[1] for p in points))
        ymax = min(self.h - 1, max(p[1] for p in points))
        n = len(points)
        for y in range(ymin, ymax + 1):
            xs = []
            for i in range(n):
                x0, y0 = points[i]
                x1, y1 = points[(i + 1) % n]
                if y0 == y1:
                    continue
                if (y0 <= y < y1) or (y1 <= y < y0):
                    t = (y - y0) / (y1 - y0)
                    xs.append(x0 + t * (x1 - x0))
            xs.sort()
            for k in range(0, len(xs) - 1, 2):
                xa = max(0, int(math.ceil(xs[k])))
                xb = min(self.w - 1, int(math.floor(xs[k + 1])))
                for x in range(xa, xb + 1):
                    self.set(x, y, color)


def lerp(a, b, t):
    return a + (b - a) * t


def lerp_color(c0, c1, t):
    return (
        int(round(lerp(c0[0], c1[0], t))),
        int(round(lerp(c0[1], c1[1], t))),
        int(round(lerp(c0[2], c1[2], t))),
    )


# ------------------------------------------------------------------- font
# 5x7 bitmap glyphs, written from the standard 5x7 pattern.
FONT = {
    "A": (".###.", "#...#", "#...#", "#####", "#...#", "#...#", "#...#"),
    "B": ("####.", "#...#", "#...#", "####.", "#...#", "#...#", "####."),
    "C": (".####", "#....", "#....", "#....", "#....", "#....", ".####"),
    "D": ("###..", "#..#.", "#...#", "#...#", "#...#", "#..#.", "###.."),
    "E": ("#####", "#....", "#....", "####.", "#....", "#....", "#####"),
    "F": ("#####", "#....", "#....", "####.", "#....", "#....", "#...."),
    "G": (".####", "#....", "#....", "#.###", "#...#", "#...#", ".###."),
    "H": ("#...#", "#...#", "#...#", "#####", "#...#", "#...#", "#...#"),
    "I": ("#####", "..#..", "..#..", "..#..", "..#..", "..#..", "#####"),
    "N": ("#...#", "##..#", "##..#", "#.#.#", "#..##", "#..##", "#...#"),
    "O": (".###.", "#...#", "#...#", "#...#", "#...#", "#...#", ".###."),
    "R": ("####.", "#...#", "#...#", "####.", "#.#..", "#..#.", "#...#"),
    "S": (".####", "#....", "#....", ".###.", "....#", "....#", "####."),
    "T": ("#####", "..#..", "..#..", "..#..", "..#..", "..#..", "..#.."),
    "V": ("#...#", "#...#", "#...#", "#...#", "#...#", ".#.#.", "..#.."),
    "Y": ("#...#", "#...#", ".#.#.", "..#..", "..#..", "..#..", "..#.."),
    " ": (".....", ".....", ".....", ".....", ".....", ".....", "....."),
}

TEXT = "THE SECOND BEFORE EVERYTHING CHANGES"


def draw_text(canvas, text, x0, y0, scale, color):
    """Draw text with the 5x7 font; returns the total width in pixels."""
    x = x0
    for ch in text:
        glyph = FONT[ch]
        for row in range(7):
            bits = glyph[row]
            for col in range(5):
                if bits[col] == "#":
                    for dy in range(scale):
                        for dx in range(scale):
                            canvas.set(x + col * scale + dx,
                                       y0 + row * scale + dy, color)
        x += 5 * scale + scale
    return x - scale - x0


# -------------------------------------------------------------------- png
def png_bytes(canvas):
    def chunk(kind, data):
        out = struct.pack(">I", len(data)) + kind + data
        out += struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
        return out

    ihdr = struct.pack(">IIBBBBB", canvas.w, canvas.h, 8, 2, 0, 0, 0)
    raw = bytearray()
    row_bytes = canvas.w * 3
    for y in range(canvas.h):
        raw.append(0)
        raw += canvas.px[y * row_bytes:(y + 1) * row_bytes]
    idat = zlib.compress(bytes(raw), 9)
    sig = b"\x89PNG\r\n\x1a\n"
    return sig + chunk(b"IHDR", ihdr) + chunk(b"IDAT", idat) + chunk(b"IEND", b"")


# ------------------------------------------------------------------ scene
def draw_scene():
    rng = random.Random(SEED)
    c = Canvas(W, H)

    # --- sky: vertical gradient, deep indigo -> violet -> near-black
    stops = [(0.0, (7, 10, 30)), (0.55, (20, 16, 54)), (1.0, (5, 6, 15))]
    for y in range(H):
        t = y / (H - 1)
        if t < 0.55:
            col = lerp_color(stops[0][1], stops[1][1], t / 0.55)
        else:
            col = lerp_color(stops[1][1], stops[2][1], (t - 0.55) / 0.45)
        c.fill_row(y, col)

    # --- stars across the sky
    star_cols = [(255, 255, 255), (170, 200, 255), (255, 220, 170)]
    for _ in range(260):
        x = rng.randrange(0, W)
        y = rng.randrange(0, 900)
        col = star_cols[rng.randrange(3)]
        b = rng.uniform(0.45, 1.0)
        bright = (int(col[0] * b), int(col[1] * b), int(col[2] * b))
        c.add(x, y, bright, 1.0)
        if rng.random() < 0.12:
            c.add(x + 1, y, bright, 0.8)
            c.add(x, y + 1, bright, 0.8)

    # --- three shooting-star streaks
    for _ in range(3):
        sx = rng.randrange(80, 900)
        sy = rng.randrange(60, 300)
        ang = rng.uniform(0.5, 1.0)  # down-right, shallow
        length = rng.uniform(55, 90)
        dx = math.cos(ang) * length
        dy = math.sin(ang) * length
        steps = int(length)
        for s in range(steps):
            t = s / steps
            x = int(sx + dx * t)
            y = int(sy + dy * t)
            c.add(x, y, (255, 240, 200), (1.0 - t) * 0.9)

    # --- the portal at (648, 372)
    px, py = 648, 372
    c.glow(px, py, 400, (255, 120, 40), 0.55)   # warm halo
    c.glow(px, py, 290, (255, 60, 160), 0.45)   # magenta halo
    c.disc(px, py, 235, (255, 138, 0))          # outer orange ring
    c.disc(px, py, 200, (255, 46, 136))         # mid magenta ring
    c.disc(px, py, 172, (255, 214, 96))         # thin gold rim
    c.disc(px, py, 162, (10, 8, 30))            # dark interior: the opening
    # tiny stars inside the dark opening
    for _ in range(14):
        ang = rng.uniform(0, 2 * math.pi)
        rr = rng.uniform(0, 140)
        x = int(px + math.cos(ang) * rr)
        y = int(py + math.sin(ang) * rr)
        c.add(x, y, (255, 255, 255), rng.uniform(0.5, 1.0))
    # the bright heart: something is coming through
    c.glow(px, py, 60, (255, 244, 214), 0.9)
    c.disc(px, py, 22, (255, 244, 214))

    # --- rays bursting from the ring's outer edge (skip the river's wedge)
    ray_cols = [(255, 214, 96), (140, 230, 255), (255, 255, 255)]
    made = 0
    tries = 0
    while made < 14 and tries < 200:
        tries += 1
        ang = rng.uniform(0, 2 * math.pi)
        deg = math.degrees(ang) % 360
        if 95 <= deg <= 135:  # keep the river's exit clean
            continue
        length = rng.uniform(300, 560)
        width = rng.uniform(3, 5)
        col = ray_cols[made % 3]
        x0 = px + math.cos(ang) * 238
        y0 = py + math.sin(ang) * 238
        x1 = px + math.cos(ang) * (238 + length)
        y1 = py + math.sin(ang) * (238 + length)
        steps = int(length / 3)
        for s in range(steps + 1):
            t = s / steps
            x = int(round(x0 + (x1 - x0) * t))
            y = int(round(y0 + (y1 - y0) * t))
            c.disc(x, y, max(0.8, width * 0.5 * (1 - t * 0.6)), col,
                   additive=True)
        made += 1

    # --- river of light: quadratic Bezier to the raised hand
    bx0, by0 = 545, 600
    bx1, by1 = 470, 695
    bx2, by2 = 336, 772
    gold = (255, 208, 110)
    ice = (185, 240, 255)
    steps = 140
    pts = []
    for s in range(steps + 1):
        t = s / steps
        mt = 1 - t
        x = mt * mt * bx0 + 2 * mt * t * bx1 + t * t * bx2
        y = mt * mt * by0 + 2 * mt * t * by1 + t * t * by2
        pts.append((x, y, t))
    for (x, y, t) in pts:  # soft cyan glow underneath
        c.disc(int(x), int(y), lerp(52, 22, t) / 2, (120, 220, 255),
               additive=True)
    for (x, y, t) in pts:  # opaque body, gold near the ring, ice at hand
        c.disc(int(x), int(y), lerp(34, 10, t) / 2,
               lerp_color(gold, ice, t))
    for (x, y, t) in pts:  # thin white thread on top
        c.disc(int(x), int(y), 1, (255, 255, 255))

    # --- ridges: a distant violet ridge, then the near-black cliff
    ridge = []
    for x in range(0, W + 1, 16):
        y = 838 + 14 * math.sin(x / 170.0 + 1.2) + 8 * math.sin(x / 61.0)
        ridge.append((x, int(y)))
    c.poly(ridge + [(W, H), (0, H)], (30, 22, 60))
    cliff = []
    for x in range(0, W + 1, 16):
        y = 878 + (x - 300) * -0.05 + 5 * math.sin(x / 90.0 + 0.4)
        cliff.append((x, int(y)))
    c.poly(cliff + [(W, H), (0, H)], (4, 4, 12))

    # --- the figure: a black silhouette, ~128 px tall, feet at (300, 878)
    black = (2, 3, 10)
    c.poly([(280, 782), (320, 782), (312, 878), (288, 878)], black)
    c.disc(300, 764, 12, black)                       # head
    c.thick_line(284, 788, 274, 848, 9, black)        # left arm, hanging
    c.thick_line(314, 788, 336, 772, 10, black)       # right arm, raised
    c.thick_line(318, 782, 338, 770, 2, (255, 214, 96))  # gold rim
    c.glow(336, 772, 26, (255, 214, 96), 0.8)         # light in the hand

    # --- the one line of text, gold on a dark shadow
    scale = 4
    width = len(TEXT) * (5 * scale + scale) - scale
    tx = (W - width) // 2
    ty = 962
    draw_text(c, TEXT, tx + 2, ty + 2, scale, (8, 6, 18))
    draw_text(c, TEXT, tx, ty, scale, (255, 215, 106))

    return c


def main():
    outdir = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")
    canvas = draw_scene()
    data = png_bytes(canvas)
    os.makedirs(outdir, exist_ok=True)
    path = os.path.join(outdir, "entry.png")
    with open(path, "wb") as f:
        f.write(data)
    print(f"wrote {path}: {len(data)} bytes, {W}x{H}")


if __name__ == "__main__":
    main()
