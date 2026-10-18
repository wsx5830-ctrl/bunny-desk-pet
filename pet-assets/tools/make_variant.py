"""从主皮肤生成换色演示皮肤（palette swap）：保留肤色和墨线，只换衣服/耳饰色相。

用法：python tools/make_variant.py <源皮肤id> <新皮肤id> "<显示名>" <色相偏移度> <主色>
肤色保护：hue 在 10°~45°（皮肤暖橙区）以及低饱和/深色像素不动。
"""
import json
import os
import shutil
import sys

import numpy as np
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKINS = os.path.join(ROOT, "skins")


def recolor(img, delta_h):
    arr = np.array(img.convert("RGBA"), np.float32) / 255.0
    rgb, a = arr[..., :3], arr[..., 3:]
    mx, mn = rgb.max(-1), rgb.min(-1)
    v = mx
    s = np.where(mx > 0, (mx - mn) / np.maximum(mx, 1e-6), 0)
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    h = np.zeros_like(mx)
    d = mx - mn
    m = d > 1e-6
    rm = m & (mx == r)
    gm = m & (mx == g) & ~rm
    bm = m & (mx == b) & ~rm & ~gm
    h[rm] = (60 * ((g - b) / d) % 360)[rm]
    h[gm] = (60 * ((b - r) / d) + 120)[gm]
    h[bm] = (60 * ((r - g) / d) + 240)[bm]
    h = h % 360

    # 保护：低饱和、近黑、以及肤色暖橙区
    skin = (h >= 10) & (h <= 45)
    keep = (s < 0.13) | (v < 0.30) | skin
    h2 = np.where(keep, h, (h + delta_h) % 360)
    s2 = np.where(keep, s, np.clip(s * 0.95, 0, 1))

    c = v * s2
    hp = h2 / 60.0
    x = c * (1 - np.abs(hp % 2 - 1))
    z = np.zeros_like(c)
    rr = np.select([(hp < 1), (hp < 2), (hp < 3), (hp < 4), (hp < 5), (hp >= 5)], [c, x, z, z, x, c])
    gg = np.select([(hp < 1), (hp < 2), (hp < 3), (hp < 4), (hp < 5), (hp >= 5)], [x, c, c, x, z, z])
    bb = np.select([(hp < 1), (hp < 2), (hp < 3), (hp < 4), (hp < 5), (hp >= 5)], [z, z, x, c, c, x])
    mmm = v - c
    out = np.stack([rr + mmm, gg + mmm, bb + mmm], -1)
    return Image.fromarray((np.concatenate([out, a], -1) * 255).clip(0, 255).astype(np.uint8), "RGBA")


def main(src_id, new_id, name, delta_h, accent):
    src = os.path.join(SKINS, src_id)
    dst = os.path.join(SKINS, new_id)
    if os.path.isdir(dst):
        shutil.rmtree(dst)
    os.makedirs(os.path.join(dst, "layers"))

    meta = json.load(open(os.path.join(src, "skin.json"), encoding="utf-8"))
    meta["id"], meta["name"], meta["accent"] = new_id, name, accent
    for l in meta["layers"]:
        im = Image.open(os.path.join(src, l["src"]))
        recolor(im, delta_h).save(os.path.join(dst, l["src"]))
    t = Image.open(os.path.join(src, "thumb.png"))
    recolor(t, delta_h).save(os.path.join(dst, "thumb.png"))
    with open(os.path.join(dst, "skin.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=1)
    print("variant ready:", new_id, "<-", src_id, "delta", delta_h)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3], float(sys.argv[4]), sys.argv[5])
