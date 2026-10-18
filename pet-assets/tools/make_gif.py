"""把 _gif_frames/*.jpg 合成为演示 GIF
用法: python tools/make_gif.py
输出: docs/images/demo.gif
"""
import glob, os, sys
from PIL import Image

ROOT = r"C:/Users/XIAOMI/WorkBuddy/2026-10-18-14-45-54"
SRC = os.path.join(ROOT, "_gif_frames")
OUT = os.path.join(ROOT, "docs", "images", "demo.gif")

CROP = (40, 170, 620, 700)   # 裁掉大片空白，保留角色+气泡+状态栏
OUT_W = 480                  # 输出宽度
DURATION = 167               # ms/帧（60 帧 ≈ 10s 实录节奏）

files = sorted(glob.glob(os.path.join(SRC, "*.jpg")))
assert files, "no frames"
imgs = []
for f in files:
    im = Image.open(f).convert("RGB").crop(CROP)
    h = round(im.height * OUT_W / im.width)
    imgs.append(im.resize((OUT_W, h), Image.LANCZOS))

# 每帧独立 256 色调色板（跨皮肤颜色差异大，共用调色板会失真）
pal_frames = [im.quantize(colors=256, method=Image.MEDIANCUT) for im in imgs]
os.makedirs(os.path.dirname(OUT), exist_ok=True)
pal_frames[0].save(OUT, save_all=True, append_images=pal_frames[1:],
                   duration=DURATION, loop=0, optimize=True)
mb = os.path.getsize(OUT) / 1048576
print(f"frames={len(pal_frames)}  size={mb:.2f}MB  -> {OUT}")
if mb > 4:
    print("[warn] 超过 4MB，建议降低 OUT_W 或抽帧")
