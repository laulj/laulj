#!/usr/bin/env python3
"""Render the profile banner and the social preview image.

Two crops come out of one design:

    assets/banner.png   1920x480   (4:1)    sits at the top of README.md
    assets/og.png       1200x630   (1.91:1) og:image for laulj.github.io

Both are drawn from the site's own design tokens, so the banner cannot drift away
from the page it points at: the palette below is the `@theme` block from
laulj.github.io/src/index.css, and the monogram is the geometry from its
favicon.svg. The only text a human maintains is NAME, EYEBROW and CLAIM, which
are the site's title and positioning.

JetBrains Mono only, on purpose. It is the site's --font-mono and the face the
BootIntro terminal is set in, so the banner reads as the same identity. The
site's other two faces (Manrope, Instrument Serif) ship there only as .woff2,
which Pillow cannot read, and no woff2 decompressor is installed here; reaching
for a lookalike system serif would be a lie about the brand, so none is used.

    python3 tools/make-banner.py            # writes both PNGs into assets/
    python3 tools/make-banner.py --font-dir /path/to/JetBrainsMono-otf

Requires Pillow and a local JetBrains Mono install (the TeX Live copy is found
automatically).
"""

import argparse
import glob
import math
import os
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

# ── Text ─────────────────────────────────────────────────────────────────────
# The site's <title>, split into the three tiers the hero already uses.
NAME = "Lau Lok Jing"
EYEBROW = "FULL-STACK ENGINEER · SMART CONTRACT AUDITOR"
CLAIM = "Every metric carries its source and its date."
URL = "laulj.github.io"

# ── Tokens (laulj.github.io/src/index.css, @theme) ───────────────────────────
INK_950 = (5, 7, 13)
INK_900 = (11, 15, 25)
ACCENT_300 = (110, 231, 183)
ACCENT_400 = (52, 211, 153)
ACCENT_500 = (16, 185, 129)
WARN_500 = (245, 158, 11)
TEXT_100 = (248, 250, 252)
TEXT_400 = (148, 163, 184)
# The site's text-slate-500 is #64748b, which measures 4.03:1 against this
# background -- below the 4.5:1 AA floor for normal text. The URL line is small,
# so it is lifted two steps to 5.07:1 rather than shipped failing.
URL_GREY = (115, 133, 156)


def background(w, h):
    """Vertical gradient, ink-950 -> ink-900, as an untextured base."""
    img = Image.new("RGB", (w, h))
    draw = ImageDraw.Draw(img)
    for y in range(h):
        t = y / max(1, h - 1)
        row = tuple(round(a + (b - a) * t) for a, b in zip(INK_950, INK_900))
        draw.line([(0, y), (w, y)], fill=row)
    return img


def radial_mask(w, h, cx, cy, rx, ry, solid, fade, downscale=8):
    """Normalised elliptical falloff, matching the CSS radial-gradient masks.

    Built small and scaled up: a smooth gradient does not need full resolution,
    and the 1/8 pass keeps this O(20k) instead of O(900k) pixel writes.
    """
    mw, mh = max(1, w // downscale), max(1, h // downscale)
    mask = Image.new("L", (mw, mh), 0)
    px = mask.load()
    for y in range(mh):
        ny = (y + 0.5) / mh
        for x in range(mw):
            nx = (x + 0.5) / mw
            d = math.hypot((nx - cx) / rx, (ny - cy) / ry)
            if d <= solid:
                v = 1.0
            elif d >= fade:
                v = 0.0
            else:
                v = (fade - d) / (fade - solid)
            px[x, y] = round(255 * v)
    return mask.resize((w, h), Image.BICUBIC)


def add_grid(img, step=72, alpha=8):
    """The 72px ambient grid, faded out from the top like .ambient-grid."""
    w, h = img.size
    grid = Image.new("L", (w, h), 0)
    draw = ImageDraw.Draw(grid)
    for x in range(0, w + step, step):
        draw.line([(x, 0), (x, h)], fill=alpha, width=1)
    for y in range(0, h + step, step):
        draw.line([(0, y), (w, y)], fill=alpha, width=1)
    faded = ImageChops.multiply(grid, radial_mask(w, h, 0.5, 0.0, 1.3, 0.85, 0.25, 0.80))
    img.paste(Image.new("RGB", (w, h), (255, 255, 255)), (0, 0), faded)


def add_glow(img, cx, cy, radius, colour=ACCENT_500, strength=0.16, blur=90):
    """A blurred orb, standing in for .ambient-orb-a's 90px blur."""
    w, h = img.size
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).ellipse(
        [cx - radius, cy - radius, cx + radius, cy + radius], fill=round(255 * strength)
    )
    img.paste(Image.new("RGB", (w, h), colour), (0, 0), mask.filter(ImageFilter.GaussianBlur(blur)))


def monogram(size, supersample=4):
    """favicon.svg's geometry, redrawn at its own 32x32 design units.

    Supersampled 4x then downscaled, because Pillow has no anti-aliased stroke
    joins; the round caps are explicit circles since `line` only does flat ends.
    """
    scale = size * supersample
    k = scale / 32.0
    stroke = 2.6 * k
    img = Image.new("RGBA", (scale, scale), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle([0, 0, scale - 1, scale - 1], radius=7 * k, fill=INK_900 + (255,))

    emerald = ACCENT_500 + (255,)
    amber = WARN_500 + (255,)

    def cap(x, y, colour):
        draw.ellipse([x - stroke / 2, y - stroke / 2, x + stroke / 2, y + stroke / 2], fill=colour)

    draw.line(
        [(9 * k, 8.5 * k), (9 * k, 19.7 * k), (16.4 * k, 19.7 * k)],
        fill=emerald,
        width=round(stroke),
        joint="curve",
    )
    for x, y in ((9, 8.5), (16.4, 19.7)):
        cap(x * k, y * k, emerald)

    draw.line([(20.5 * k, 8.5 * k), (20.5 * k, 17.5 * k)], fill=amber, width=round(stroke))
    cap(20.5 * k, 8.5 * k, amber)
    draw.ellipse(
        [(20.5 - 1.6) * k, (22.4 - 1.6) * k, (20.5 + 1.6) * k, (22.4 + 1.6) * k], fill=amber
    )

    img = img.resize((size, size), Image.LANCZOS)
    # Border after the downscale, so it stays a crisp hairline rather than a smear.
    ImageDraw.Draw(img).rounded_rectangle(
        [0, 0, size - 1, size - 1], radius=7 * size / 32, outline=ACCENT_500 + (70,), width=1
    )
    return img


WEIGHTS = {
    "regular": "JetBrainsMono-Regular.otf",
    "medium": "JetBrainsMono-Medium.otf",
    "bold": "JetBrainsMono-Bold.otf",
}


def find_fonts(explicit_dir=None):
    """Locate the three weights, or fail loudly.

    No silent fallback to another family: a banner set in DejaVu is a banner that
    quietly stops matching the site.
    """
    candidates = []
    if explicit_dir:
        candidates.append(explicit_dir)
    candidates += sorted(
        glob.glob("/usr/local/texlive/*/texmf-dist/fonts/opentype/SIL/jetbrainsmono-otf"), reverse=True
    )
    candidates += [
        "/usr/share/fonts/truetype/jetbrains-mono",
        "/usr/local/share/fonts/JetBrainsMono",
        os.path.expanduser("~/.local/share/fonts/JetBrainsMono"),
        os.path.expanduser("~/.fonts/JetBrainsMono"),
    ]
    for directory in candidates:
        if directory and all(os.path.exists(os.path.join(directory, f)) for f in WEIGHTS.values()):
            return {w: os.path.join(directory, f) for w, f in WEIGHTS.items()}
    raise SystemExit(
        "JetBrains Mono (Regular/Medium/Bold) not found. Searched:\n  "
        + "\n  ".join(c for c in candidates if c)
        + "\nPass --font-dir at a directory holding those three .otf files."
    )


def tracked_width(font, text, tracking):
    return sum(font.getlength(c) for c in text) + tracking * max(0, len(text) - 1)


def draw_tracked(draw, xy, text, font, fill, tracking=0.0, centre=False):
    """Letter-spaced text; Pillow has no tracking, so this walks the string.

    Every glyph is anchored "lm" so uneven glyph heights cannot drift the baseline.
    """
    width = tracked_width(font, text, tracking)
    x, y = xy
    if centre:
        x -= width / 2
    for ch in text:
        draw.text((x, y), ch, font=font, fill=fill, anchor="lm")
        x += font.getlength(ch) + tracking
    return width


def draw_name(draw, x, centre_y, font, size, centre=False):
    """The name, followed by the BootIntro caret -- the site's stop-motion cursor."""
    name_w = tracked_width(font, NAME, 0.0)
    caret_w, gap = 11, 16
    if centre:
        x -= (name_w + gap + caret_w) / 2
    draw.text((x, centre_y), NAME, font=font, fill=TEXT_100, anchor="lm")
    left = x + name_w + gap
    height = size * 0.9
    draw.rectangle([left, centre_y - height / 2, left + caret_w, centre_y + height / 2], fill=ACCENT_400)


def render(spec, fonts):
    w, h = spec["w"], spec["h"]
    sizes = spec["sizes"]
    margin = spec["margin"]
    img = background(w, h)
    add_grid(img)
    for orb in spec["orbs"]:
        add_glow(img, *orb)
    draw = ImageDraw.Draw(img)

    eyebrow = ImageFont.truetype(fonts["medium"], sizes["eyebrow"])
    name = ImageFont.truetype(fonts["bold"], sizes["name"])
    claim = ImageFont.truetype(fonts["regular"], sizes["claim"])
    url = ImageFont.truetype(fonts["regular"], sizes["url"])

    if spec["layout"] == "row":
        # Wide lockup: monogram left, text column beside it.
        size = spec["monogram"]
        mark = monogram(size)
        img.paste(mark, (margin, (h - size) // 2), mark)
        x = margin + size + spec["gap"]

        draw_tracked(draw, (x, 166), EYEBROW, eyebrow, ACCENT_300, tracking=sizes["eyebrow"] * 0.2)
        draw_name(draw, x, 236, name, sizes["name"])
        draw.text((x, 306), CLAIM, font=claim, fill=TEXT_400, anchor="lm")
        draw_tracked(
            draw,
            (w - margin - tracked_width(url, URL, 1.0), h - 44),
            URL,
            url,
            URL_GREY,
            tracking=1.0,
        )

    elif spec["layout"] == "stack":
        # Tall lockup for og:image (1.91:1): centred, monogram above the text.
        size = spec["monogram"]
        mark = monogram(size)
        img.paste(mark, ((w - size) // 2, margin), mark)

        draw_tracked(
            draw, (w / 2, 288), EYEBROW, eyebrow, ACCENT_300, tracking=sizes["eyebrow"] * 0.2, centre=True
        )
        draw_name(draw, w / 2, 368, name, sizes["name"], centre=True)
        draw.text((w / 2, 440), CLAIM, font=claim, fill=TEXT_400, anchor="mm")
        draw_tracked(draw, (w / 2, 524), URL, url, URL_GREY, tracking=1.0, centre=True)

    else:
        raise SystemExit(f"unknown layout: {spec['layout']}")

    return img


SPECS = [
    {
        "file": "banner.png",
        "layout": "row",
        "w": 1920,
        "h": 480,
        "monogram": 132,
        "margin": 96,
        "gap": 56,
        "sizes": {"eyebrow": 22, "name": 76, "claim": 24, "url": 20},
        # Mirrors .ambient-orb-a / .ambient-orb-b: sizes and alphas lifted from the
        # stylesheet, transposed from rem onto this canvas.
        "orbs": [
            (310, 48, 272, ACCENT_500, 0.16, 90),
            (1750, 285, 208, (13, 148, 136), 0.13, 90),
        ],
    },
    {
        "file": "og.png",
        "layout": "stack",
        "w": 1200,
        "h": 630,
        "monogram": 128,
        "margin": 96,
        "gap": 0,
        "sizes": {"eyebrow": 24, "name": 68, "claim": 24, "url": 20},
        "orbs": [
            (600, 30, 360, ACCENT_500, 0.16, 110),
            (1080, 300, 240, (13, 148, 136), 0.13, 110),
        ],
    },
]


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--font-dir", help="directory holding the three JetBrains Mono .otf files")
    parser.add_argument("--out-dir", help="defaults to <repo>/assets")
    args = parser.parse_args()

    fonts = find_fonts(args.font_dir)
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    out_dir = args.out_dir or os.path.join(root, "assets")
    os.makedirs(out_dir, exist_ok=True)

    print(f"fonts: {os.path.dirname(fonts['regular'])}")
    for spec in SPECS:
        image = render(spec, fonts)
        path = os.path.join(out_dir, spec["file"])
        image.save(path, optimize=True)
        print(f"  {spec['file']:12} {image.size[0]}x{image.size[1]}  {os.path.getsize(path) / 1024:.0f} KB")


if __name__ == "__main__":
    main()
