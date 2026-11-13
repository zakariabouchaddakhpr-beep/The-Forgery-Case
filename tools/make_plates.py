"""Synthesise the simulated technical plates for the three cases.

Run:  python make_plates.py <plates_dir>
Reads base_starry.jpg / base_widows.jpg / base_horses.jpg, writes
<case>_{photo,xray,uv,macro,raking_light}.png. Every plate is simulated and stamped as such.
Each case gets physical clues that match its sealed story (see README).
"""
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

W = 800
RNG = np.random.default_rng(7)  # fixed seed: plates are reproducible


def load(path):
    im = Image.open(path).convert("RGB")
    return im.resize((W, round(im.height * W / im.width)), Image.LANCZOS)


def gray(im):
    return np.asarray(ImageOps.grayscale(im), dtype=np.float32) / 255


def to_img(a):
    return Image.fromarray((np.clip(a, 0, 1) * 255).astype(np.uint8))


def noise(shape, sigma=0.04, blur=1.0):
    n = to_img(0.5 + RNG.normal(0, sigma, shape)).filter(ImageFilter.GaussianBlur(blur))
    return np.asarray(n, dtype=np.float32) / 255 - 0.5


def cracks(shape, cell, irregular, width):
    """Voronoi-edge crack mask in [0,1]. irregular=True gives natural, uneven networks."""
    h, w = shape
    n = (h // cell) * (w // cell)
    pts = RNG.uniform([0, 0], [h, w], (n, 2))
    if not irregular:  # baked craquelure: near-regular grid of cells
        gy, gx = np.mgrid[cell / 2:h:cell, cell / 2:w:cell]
        pts = np.stack([gy.ravel(), gx.ravel()], 1) + RNG.normal(0, cell * 0.12, (gy.size, 2))
    yy, xx = np.mgrid[0:h, 0:w]
    d1 = np.full(shape, np.inf, np.float32)
    d2 = np.full(shape, np.inf, np.float32)
    for py, px in pts:
        d = np.hypot(yy - py, xx - px).astype(np.float32)
        d2 = np.where(d < d1, d1, np.minimum(d2, d))
        d1 = np.minimum(d1, d)
    edge = (d2 - d1) < width
    if irregular:  # break the network up so it looks organic
        edge &= noise(shape, 0.25, 6) > -0.08
    return to_img(edge.astype(np.float32)).filter(ImageFilter.GaussianBlur(0.6))


def stamp(im, label):
    im = im.convert("RGB")
    d = ImageDraw.Draw(im)
    try:
        f = ImageFont.truetype("arial.ttf", 16)
    except OSError:
        f = ImageFont.load_default()
    text = f"SIMULATED PLATE - {label}"
    box = d.textbbox((0, 0), text, font=f)
    d.rectangle([8, 8, box[2] + 20, box[3] + 16], fill=(0, 0, 0))
    d.text((14, 11), text, fill=(255, 255, 255), font=f)
    return im


def xray(im, hidden=None):
    g = gray(im)
    # lead-rich lights absorb X-rays -> bright; texture of brushwork kept via edges
    edges = np.asarray(im.convert("L").filter(ImageFilter.FIND_EDGES), np.float32) / 255
    a = 0.25 + 0.55 * g ** 1.4 + 0.35 * edges + noise(g.shape, 0.05, 1.2)
    if hidden is not None:  # an earlier composition under the visible paint
        a = 0.6 * a + 0.4 * hidden
    a = np.asarray(to_img(a).filter(ImageFilter.GaussianBlur(1.2)), np.float32) / 255
    return ImageOps.autocontrast(to_img(a), cutoff=1)


def uv(im, varnish, absorb_mask=None, glow_mask=None, retouch=0):
    g = gray(im)
    base = np.array(varnish, np.float32)  # varnish fluorescence colour
    out = (0.25 + 0.65 * g)[..., None] * base + noise(g.shape, 0.03, 2)[..., None]
    if absorb_mask is not None:  # UV-absorbing white: reads dark, almost black-violet
        out = np.where(absorb_mask[..., None], [0.10, 0.06, 0.16], out)
    if glow_mask is not None:  # strongly fluorescing white: yellow-green glow
        out = np.where(glow_mask[..., None], [0.75, 0.9, 0.45], out)
    img = to_img(out.clip(0, 1)) if out.ndim == 2 else Image.fromarray((out.clip(0, 1) * 255).astype(np.uint8))
    d = ImageDraw.Draw(img)
    for _ in range(retouch):  # small later retouchings: dark, sharp-edged patches
        x, y = RNG.integers(60, img.width - 60), RNG.integers(60, img.height - 60)
        r = RNG.integers(6, 16)
        d.ellipse([x - r, y - r * 0.7, x + r, y + r * 0.7], fill=(25, 15, 35))
    return img.filter(ImageFilter.GaussianBlur(0.8))


def macro(im, crack_mask, crack_colour, crack_strength, sharpen=True):
    # 4x close-up of the central area
    cw, ch = im.width // 4, im.height // 4
    crop = im.crop((im.width // 2 - cw // 2, im.height // 2 - ch // 2,
                    im.width // 2 + cw // 2, im.height // 2 + ch // 2)).resize((W, round(W * ch / cw)), Image.BICUBIC)
    if sharpen:
        crop = crop.filter(ImageFilter.UnsharpMask(3, 120, 2))
    m = np.asarray(crack_mask.resize(crop.size), np.float32)[..., None] / 255 * crack_strength
    arr = np.asarray(crop, np.float32) / 255
    arr = arr * (1 - m) + np.array(crack_colour, np.float32) * m
    return Image.fromarray((arr.clip(0, 1) * 255).astype(np.uint8))


def raking(im, relief):
    g = im.convert("L").filter(ImageFilter.GaussianBlur(1))
    emb = np.asarray(g.filter(ImageFilter.EMBOSS), np.float32) / 255 - 0.5
    a = 0.45 + emb * relief + gray(im) * 0.15
    return ImageOps.autocontrast(to_img(a), cutoff=0.5)


def main(d):
    d = Path(d)
    cases = {
        "case_starry_night": load(d / "base_starry.jpg"),
        "case_widows_supper": load(d / "base_widows.jpg"),
        "case_blue_horses_dusk": load(d / "base_horses.jpg"),
    }
    for case, im in cases.items():
        shape = (im.height, im.width)
        im.save(d / f"{case}_photo.jpg", quality=88)
        if case == "case_starry_night":
            plates = {
                "xray": xray(im),
                "uv": uv(im, [0.45, 0.6, 0.35], retouch=4),  # aged varnish: even greenish glow
                "macro": macro(im, cracks(shape, 22, True, 1.6), [0.15, 0.12, 0.08], 0.7),
                "raking_light": raking(im, 2.6),  # heavy impasto
            }
        elif case == "case_widows_supper":
            # earlier composition: a landscape horizon and a large oval form, rotated 90 degrees
            hid = Image.new("L", (im.height, im.width), 70)
            hd = ImageDraw.Draw(hid)
            hd.rectangle([0, im.width * 0.55, im.height, im.width], fill=150)
            hd.ellipse([im.height * 0.2, im.width * 0.1, im.height * 0.7, im.width * 0.5], fill=200)
            hd.polygon([(0, im.width * 0.55), (im.height * 0.4, im.width * 0.35), (im.height, im.width * 0.6)], fill=120)
            hidden = np.asarray(hid.rotate(90, expand=True).resize(im.size).filter(ImageFilter.GaussianBlur(4)), np.float32) / 255
            plates = {
                "xray": xray(im, hidden),
                "uv": uv(im, [0.22, 0.18, 0.40]),  # dull, uniform, no aged-varnish glow
                "macro": macro(im, cracks(shape, 18, False, 2.2), [0.02, 0.02, 0.02], 0.95),  # regular, ink-filled
                "raking_light": raking(im, 0.6),  # flat, glassy surface
            }
        else:
            hsv = np.asarray(im.convert("HSV"), np.float32) / 255
            white = (hsv[..., 2] > 0.72) & (hsv[..., 1] < 0.22)
            col = np.arange(im.width)[None, :].repeat(im.height, 0)
            trunks = white & ((col < im.width * 0.15) | ((col > im.width * 0.55) & (col < im.width * 0.82)))
            plates = {
                "xray": xray(im),
                "uv": uv(im, [0.30, 0.28, 0.42], absorb_mask=trunks, glow_mask=white & ~trunks),
                "macro": macro(im, cracks(shape, 40, True, 0.8), [0.2, 0.2, 0.2], 0.25),  # fresh, barely cracked
                "raking_light": raking(im, 1.4),
            }
        for kind, p in plates.items():
            stamp(p, kind.upper().replace("_", " ")).save(d / f"{case}_{kind}.png", optimize=True)
            print("wrote", case, kind)

    # self-check: every plate exists and is a readable PNG
    for case in cases:
        for kind in ("xray", "uv", "macro", "raking_light"):
            assert Image.open(d / f"{case}_{kind}.png").size[0] == W


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else ".")
