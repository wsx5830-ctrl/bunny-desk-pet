"""一键接入新皮肤：图片 -> skins/<id>/ 皮肤包（抠底 + 拆层 + 画布归一化）。

用法：
  python tools/ingest_skin.py <图片路径> <皮肤id> "<显示名>" [主色]

归一化的意义：十套皮肤如果各自裁图，画布尺寸和角色比例都不一样，
换皮时角色会突然变大变小、脚底离地。这里把每套皮肤统一缩放到
“身高 = 560px、脚底贴在 y=616、身体中线在 x=320”的 640×640 画布上，
换皮只换像素，位置和支点完全一致。
"""
import io
import json
import os
import shutil
import sys
import tempfile
from collections import deque

import numpy as np
from PIL import Image, ImageFilter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import petsplit  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKINS = os.path.join(ROOT, "skins")

CANVAS = 640
BASELINE = 616      # 脚底落点
BODY_H = 560        # 角色（含耳朵/发顶）统一高度
CENTER_X = 320

ORDER = ["tail", "shorts", "body", "hand_L", "hand_R", "face", "mouth",
         "eye_L", "eye_R", "hair", "ear_L", "ear_R", "hat"]

ROLE_CN = {
    "shorts": "下装", "body": "身体", "hand_L": "左手", "hand_R": "右手",
    "face": "脸", "mouth": "嘴", "eye_L": "左眼", "eye_R": "右眼",
    "hair": "头发", "ear_L": "左耳/左耳饰", "ear_R": "右耳/右耳饰",
    "tail": "尾巴", "hat": "帽子/头饰",
}


def cut_bg(path, tol=235):
    """白底转透明：只从画布边缘 flood fill，内部白色（衣服/高光）不动。"""
    im = Image.open(path).convert("RGBA")
    arr = np.array(im)
    if (arr[..., 3] < 20).mean() > 0.02:      # 已经带透明通道，直接用
        alpha = Image.fromarray(arr[..., 3])
        rgb = im.convert("RGB")
        rgba = rgb.convert("RGBA")
        rgba.putalpha(alpha)
        return rgba.crop(alpha.getbbox())

    im = im.convert("RGB")
    w, h = im.size
    px = im.load()

    def is_bg(x, y):
        r, g, b = px[x, y]
        return r >= tol and g >= tol and b >= tol

    mask = [[0] * w for _ in range(h)]
    q = deque()
    for x in range(w):
        for y in (0, h - 1):
            if is_bg(x, y) and not mask[y][x]:
                mask[y][x] = 1
                q.append((x, y))
    for y in range(h):
        for x in (0, w - 1):
            if is_bg(x, y) and not mask[y][x]:
                mask[y][x] = 1
                q.append((x, y))
    while q:
        x, y = q.popleft()
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if 0 <= nx < w and 0 <= ny < h and not mask[ny][nx] and is_bg(nx, ny):
                mask[ny][nx] = 1
                q.append((nx, ny))

    alpha = Image.new("L", (w, h), 255)
    ap = alpha.load()
    for y in range(h):
        row = mask[y]
        for x in range(w):
            if row[x]:
                ap[x, y] = 0
    alpha = alpha.filter(ImageFilter.MinFilter(3)).filter(ImageFilter.GaussianBlur(1))

    rgba = im.convert("RGBA")
    rgba.putalpha(alpha)
    return rgba.crop(alpha.getbbox())


def ingest(src, skin_id, name, accent="#C23B3B", quotes=None, static_ears=False, no_tail=False):
    work = tempfile.mkdtemp(prefix="skin_")
    try:
        master = os.path.join(work, "master.png")
        cut_bg(src).save(master)
        raw = os.path.join(work, "raw")
        info = petsplit.split(master, raw, debug=False)

        boxes = {l["name"]: l["box"] for l in info["layers"]}
        x0 = min(b[0] for b in boxes.values())
        y0 = min(b[1] for b in boxes.values())
        x1 = max(b[2] for b in boxes.values())
        y1 = max(b[3] for b in boxes.values())

        scale = BODY_H / max(y1 - y0, 1)
        body_box = boxes.get("body")
        cx_src = (body_box[0] + body_box[2]) / 2 if body_box else (x0 + x1) / 2
        ox = CENTER_X - cx_src * scale
        oy = BASELINE - y1 * scale

        outdir = os.path.join(SKINS, skin_id)
        layerdir = os.path.join(outdir, "layers")
        os.makedirs(layerdir, exist_ok=True)

        order = [r for r in ORDER if r in boxes] + [r for r in boxes if r not in ORDER]
        layers = []
        for role in order:
            im = Image.open(os.path.join(raw, role + ".png")).convert("RGBA")
            nw, nh = max(1, round(im.width * scale)), max(1, round(im.height * scale))
            im = im.resize((nw, nh), Image.LANCZOS)
            canvas = Image.new("RGBA", (CANVAS, CANVAS), (0, 0, 0, 0))
            canvas.alpha_composite(im, (round(ox), round(oy)))
            canvas.save(os.path.join(layerdir, role + ".png"))
            layers.append(role)

        pivots = {}
        for role in layers:
            p = info["pivots"].get(role)
            if p:
                pivots[role] = [round(p[0] * scale + ox), round(p[1] * scale + oy)]
        if "body" in layers:
            pivots["body"] = [CENTER_X, BASELINE]

        # 缩略图（菜单里用）
        comp = Image.new("RGBA", (CANVAS, CANVAS), (0, 0, 0, 0))
        for role in layers:
            comp.alpha_composite(Image.open(os.path.join(layerdir, role + ".png")))
        thumb = comp.crop((0, BASELINE - BODY_H - 20, CANVAS, BASELINE + 8))
        thumb.thumbnail((160, 160), Image.LANCZOS)
        thumb.save(os.path.join(outdir, "thumb.png"))

        meta = {
            "id": skin_id,
            "name": name,
            "canvas": [CANVAS, CANVAS],
            "baseline": BASELINE,
            "accent": accent,
            "layers": [{"role": r, "src": "layers/%s.png" % r, "label": ROLE_CN.get(r, r)}
                       for r in layers],
            "pivots": pivots,
            "quotes": quotes or {},
            # 动画能力表：耳朵若是造型的一部分（兽耳/发箍/帽子上的假耳），设为 False，
            # 则不独立摆动/扇动，但仍归入头部组随点头一起转；眨眼、呼吸、拖拽、落地、睡眠不受影响。
            "anim": {
                "breathe": True,
                "blink": ("eye_L" in layers and "eye_R" in layers),  # 单眼层时不眨眼，防穿帮
                "nod": True,
                "hairSway": True,
                "earSway": not static_ears,
                "tailSway": (not no_tail) and ("tail" in layers),
            },
        }
        with open(os.path.join(outdir, "skin.json"), "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=1)
        print("skin ready:", skin_id, "layers:", layers, "scale:", round(scale, 3))
        return meta
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="接入一套桌宠皮肤")
    ap.add_argument("src", help="角色图片路径")
    ap.add_argument("skin_id", help="皮肤 id（英文/拼音，用作目录名）")
    ap.add_argument("name", help="显示名")
    ap.add_argument("--accent", default="#C23B3B", help="皮肤主色，换装时 UI 点缀色")
    ap.add_argument("--static-ears", action="store_true",
                    help="耳朵属于造型本身，不独立摆动（眨眼等其他动画保留）")
    ap.add_argument("--no-tail", action="store_true", help="尾巴不摆动")
    args = ap.parse_args()
    ingest(args.src, args.skin_id, args.name, args.accent,
           static_ears=args.static_ears, no_tail=args.no_tail)
