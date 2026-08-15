#!/usr/bin/env python3
"""
Build assets/GD/glowdaze-sheet.png from Laayba's drawings.

    python tools/build-glowdaze-sprite.py [ART_DIR]

ART_DIR must contain OG.png (running pose) and daed.png (crash pose).
Defaults to ../GD-updated/GD-updated relative to the repo.

Everything the game animates is derived from those two files. Nothing is
repainted: frames are built by removing or repeating whole rows and sliding
limbs in whole-pixel steps, so her pixel grid and 20-colour palette survive
exactly. The only invented pixels are outline (#302030) put back around edges
a move exposed -- roughly 50 per frame.

If she supplies hand-drawn frames later, drop them in as extra cells in
build_sheet() and delete the matching generator call. Requires Pillow.
"""
import json
import os
import sys

from PIL import Image

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(REPO, "assets", "GD")
DEFAULT_ART = os.path.join(os.path.dirname(REPO), "GD-updated", "GD-updated")

OUTLINE = (48, 32, 48, 255)          # #302030, her outline colour

# Landmarks measured from OG.png. If she redraws her substantially these are
# the numbers to re-check -- run with --debug to print a region map.
SPLIT_TOP = 83                       # below here the hind legs are separate runs
HOCK = 87                            # where the lower leg is cut so it can fold
DROP_ROWS = [64, 69, 74]             # torso rows removed to compress her
FRONT_TOP, FRONT_BOT, FRONT_XMIN = 62, 77, 70     # foreleg: shoulder to paw
EAR_ROWS = list(range(2, 19))
NECK_ROWS = list(range(47, 60))

# One bound. Frame 1 is her drawing untouched: airborne at full stretch.
SWING = [0, 3, 6, 8, 6, 3]           # how far forward each hind foot has swung
LIFT = [0, 3, 4, 2, 0, 0]            # how far it is off the ground while swinging
LEG_OFFSET = 3                       # half a cycle, so the legs alternate
#        squash  fore  bob  pitch  reach
BODY = [(0,   0,  11,  +2,    0),    # flight: highest, nose up, front paw tucked
        (1,  -3,   8,  +1,    5),    # reaching down
        (2,  -5,   4,   0,   10),
        (3,  -7,   0,  -2,   14),    # touchdown: lowest, paw planted
        (2,  -5,   4,  -1,    9),    # drive off
        (1,  -2,   8,  +1,    4)]    # rising, tucking again

DUCK_EARS, DUCK_NECK, DUCK_LEGS = 15, 10, 3
DUCK_TILT = 3                        # nose-down lean; also shortens her


def load_art(art_dir):
    src = os.path.join(art_dir, "OG.png")
    if not os.path.exists(src):
        sys.exit("could not find OG.png in " + art_dir)
    im = Image.open(src).convert("RGBA")
    return im.crop(im.getbbox())


def palette_of(art):
    return {tuple(p) for row in range(art.size[1])
            for p in [art.getpixel((x, row)) for x in range(art.size[0])] if p[3] > 0}


def reink(im, fill):
    """Give her outline back to any fill pixel now touching open air."""
    w, h = im.size
    px = im.load()
    add = []
    for y in range(h):
        for x in range(w):
            if px[x, y][3] != 0:
                continue
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nx, ny = x + dx, y + dy
                if 0 <= nx < w and 0 <= ny < h and px[nx, ny] in fill:
                    add.append((x, y))
                    break
    for x, y in add:
        px[x, y] = OUTLINE
    return len(add)


def label_legs(art):
    """Below SPLIT_TOP each row has two runs of pixels: the two hind legs."""
    W, H = art.size
    px = art.load()
    out = {}
    for y in range(SPLIT_TOP, H):
        runs, x = [], 0
        while x < W:
            if px[x, y][3] > 128:
                s = x
                while x < W and px[x, y][3] > 128:
                    x += 1
                runs.append((s, x - 1))
            else:
                x += 1
        for i, (a, b) in enumerate(runs):
            for x2 in range(a, b + 1):
                out[(x2, y)] = "A" if i == 0 else "B"
    return out


def in_front(x, y):
    return FRONT_TOP <= y <= FRONT_BOT and x >= FRONT_XMIN


def build_run_frame(art, legs, fill, squash, fold_a, fold_b, fold_front,
                    bob, pitch, reach, lift_a, lift_b, pad=26):
    W, H = art.size
    px = art.load()
    out = Image.new("RGBA", (W + pad * 2, H + pad * 2), (0, 0, 0, 0))
    drop = set(DROP_ROWS[:squash])

    def rise(x):
        # bob lifts everything equally, pitch tilts it about her middle.
        # Both touch every pixel, so neither can open a seam.
        return -bob + int(round(pitch * ((x - W / 2) / (W / 2))))

    for y in range(H):
        if y in drop:
            continue
        shift = sum(1 for d in drop if d < y)
        for x in range(W):
            p = px[x, y]
            if p[3] == 0 or in_front(x, y):
                continue
            dx = up = 0
            k = legs.get((x, y))
            if k is not None:
                swing = fold_a if k == "A" else fold_b
                hoof = lift_a if k == "A" else lift_b
                if y >= HOCK:
                    dx, up = swing, hoof
                else:
                    t = (y - SPLIT_TOP) / max(1, HOCK - SPLIT_TOP)
                    dx, up = int(round(swing * t * 0.55)), int(round(hoof * t))
            out.putpixel((x + pad + dx, y + pad - shift - up + rise(x)), p)

    # Foreleg, stretched downward so the paw reaches for the ground. Her drawing
    # tucks it 15 px above her hind feet -- right for a leap, wrong for a stride.
    # Output rows sample input rows, so the leg gets LONGER by repeating rows
    # instead of moving and leaving a hole at the shoulder.
    span = FRONT_BOT - FRONT_TOP
    for yo in range(FRONT_TOP, FRONT_BOT + reach + 1):
        yi = FRONT_TOP + int(round((yo - FRONT_TOP) * span / max(1, span + reach)))
        if not 0 <= yi < H:
            continue
        shift = sum(1 for d in drop if d < yi)
        dx = int(round(fold_front * (yo - FRONT_TOP) / max(1, span + reach)))
        for x in range(FRONT_XMIN, W):
            if not in_front(x, yi):
                continue
            p = px[x, yi]
            if p[3] > 0:
                out.putpixel((x + pad + dx, yo + pad - shift + rise(x)), p)

    reink(out, fill)
    return out


def build_duck_frame(art, fill, ear_drop, neck_drop, leg_up, pad=24):
    """Rows come out of the ears and neck, never out of her face, so the eye
    and muzzle stay exactly as drawn."""
    W, H = art.size
    px = art.load()
    drop = set(EAR_ROWS[::max(1, len(EAR_ROWS) // ear_drop)][:ear_drop])
    drop |= set(NECK_ROWS[::max(1, len(NECK_ROWS) // neck_drop)][:neck_drop])
    out = Image.new("RGBA", (W + pad * 2, H + pad * 2), (0, 0, 0, 0))
    for y in range(H):
        if y in drop:
            continue
        shift = sum(1 for d in drop if d < y)
        for x in range(W):
            p = px[x, y]
            if p[3] > 0:
                out.putpixel((x + pad, y + pad - shift - (leg_up if y >= 83 else 0)), p)
    reink(out, fill)
    return out.crop(out.getbbox())


def tilt(im, amount, fill):
    """Vertical shear. A true rotation would resample and break 1 px linework;
    stepping whole columns never interpolates."""
    w, h = im.size
    px = im.load()
    pad = abs(amount) + 4
    out = Image.new("RGBA", (w, h + pad * 2), (0, 0, 0, 0))
    for x in range(w):
        dy = int(round(amount * (x - w / 2) / max(1, w / 2)))
        for y in range(h):
            p = px[x, y]
            if p[3] > 0:
                out.putpixel((x, y + pad + dy), p)
    reink(out, fill)
    return out.crop(out.getbbox())


def collision_bands(cell, cw, ch, scale, cols=4):
    """Boxes traced from the artwork. The dino's were shaped like a dinosaur:
    a tall head over a narrow body. Hers is a long leap with a trailing tail."""
    im = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
    im.alpha_composite(cell, ((cw - cell.size[0]) // 2, ch - cell.size[1]))
    px = im.load()
    boxes, step = [], cw / cols
    for i in range(cols):
        x0, x1 = int(i * step), int((i + 1) * step)
        pts = [(x, y) for y in range(ch) for x in range(x0, x1) if px[x, y][3] > 128]
        if not pts:
            continue
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        bx, by = min(xs), min(ys)
        boxes.append([round(bx * scale), round(by * scale),
                      round((max(xs) - bx + 1) * scale), round((max(ys) - by + 1) * scale)])
    return boxes


def main(art_dir):
    art = load_art(art_dir)
    fill = {c for c in palette_of(art) if c != OUTLINE}
    legs = label_legs(art)
    print(f"OG.png {art.size}, {len(fill) + 1} colours")

    leg_a, leg_b = SWING, [SWING[(i + LEG_OFFSET) % 6] for i in range(6)]
    lift_a, lift_b = LIFT, [LIFT[(i + LEG_OFFSET) % 6] for i in range(6)]
    raw = [build_run_frame(art, legs, fill, s, leg_a[i], leg_b[i], f,
                           bo, p, r, lift_a[i], lift_b[i])
           for i, (s, f, bo, p, r) in enumerate(BODY)]

    # One shared crop box across the run frames -- that box is what carries the
    # bob. Trimming each frame to its own bounds would re-seat them all on the
    # floor and delete the bounce.
    bx = [f.getbbox() for f in raw]
    box = (min(b[0] for b in bx), min(b[1] for b in bx),
           max(b[2] for b in bx), max(b[3] for b in bx))
    run = [f.crop(box) for f in raw]

    ducks = [tilt(build_duck_frame(art, fill, DUCK_EARS, DUCK_NECK, DUCK_LEGS),
                  DUCK_TILT, fill),
             tilt(build_duck_frame(art, fill, DUCK_EARS, DUCK_NECK, 1),
                  DUCK_TILT, fill)]

    dead = Image.open(os.path.join(art_dir, "daed.png")).convert("RGBA")
    cells = run + ducks + [dead.crop(dead.getbbox())]
    names = [f"run{i+1}" for i in range(6)] + ["duck1", "duck2", "crash"]

    # Even cell size so the sheet halves exactly. The cell grows upward with the
    # bob, which is harmless: the engine draws it from yPos to yPos + HEIGHT and
    # groundYPos is 150 - HEIGHT - 10, so its bottom edge always lands on y=140.
    even = lambda n: n + (n % 2)
    CW, CH = even(max(c.size[0] for c in cells)), even(max(c.size[1] for c in cells))

    sheet2x = Image.new("RGBA", (CW * len(cells), CH), (0, 0, 0, 0))
    for i, c in enumerate(cells):
        sheet2x.alpha_composite(c, (i * CW + (CW - c.size[0]) // 2, CH - c.size[1]))
    sheet1x = sheet2x.resize((sheet2x.size[0] // 2, CH // 2), Image.NEAREST)

    os.makedirs(OUT_DIR, exist_ok=True)
    sheet2x.save(os.path.join(OUT_DIR, "glowdaze-sheet-2x.png"))
    sheet1x.save(os.path.join(OUT_DIR, "glowdaze-sheet.png"))

    meta = {
        "cell": [CW // 2, CH // 2], "cell2x": [CW, CH],
        "frames": {n: i for i, n in enumerate(names)},
        "run": list(range(6)), "duck": [6, 7], "crash": 8, "tilt": DUCK_TILT,
        "collision": {
            "RUNNING": collision_bands(run[0], CW, CH, 0.5, cols=4),
            "DUCKING": collision_bands(ducks[0], CW, CH, 0.5, cols=3),
        },
    }
    with open(os.path.join(OUT_DIR, "glowdaze-sheet.json"), "w") as fh:
        json.dump(meta, fh, indent=2)

    print(f"wrote {len(cells)} cells at {CW}x{CH} (2x), {CW//2}x{CH//2} drawn")
    print("If cell size changed, update CELL_W/CELL_H/CELL2X_W/CELL2X_H and")
    print("COLLISION in gd-sprite.js to match assets/GD/glowdaze-sheet.json.")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else DEFAULT_ART)
