from PIL import Image, ImageFilter
from collections import deque

SRC = r"C:\Users\XIAOMI\Documents\xwechat_files\wxid_v8qmhmncwrf612_c52e\msg\file\2026-10\584218dce29ae5a7674a9d4dde032d57.PNG"
OUT = r"C:\Users\XIAOMI\WorkBuddy\2026-10-18-14-45-54\pet-assets\character\idle_01.png"

TOL = 235  # near-white threshold

im = Image.open(SRC).convert("RGB")
w, h = im.size
px = im.load()

def is_bg(x, y):
    r, g, b = px[x, y]
    return r >= TOL and g >= TOL and b >= TOL

mask = [[0] * w for _ in range(h)]  # 1 = background
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
    for nx, ny in ((x+1,y),(x-1,y),(x,y+1),(x,y-1)):
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

# erode 1px to kill white halo, then feather the edge
alpha = alpha.filter(ImageFilter.MinFilter(3)).filter(ImageFilter.GaussianBlur(1))

rgba = im.convert("RGBA")
rgba.putalpha(alpha)

bbox = alpha.getbbox()
rgba = rgba.crop(bbox)
print("content bbox:", bbox, "size:", rgba.size)

# paste onto 512x512 canvas, feet anchored at bottom-center
canvas = Image.new("RGBA", (512, 512), (0, 0, 0, 0))
scale = min((500 - 20) / rgba.height, (512 - 40) / rgba.width, 1.0)
nw, nh = int(rgba.width * scale), int(rgba.height * scale)
rgba = rgba.resize((nw, nh), Image.LANCZOS)
canvas.paste(rgba, ((512 - nw) // 2, 505 - nh), rgba)
canvas.save(OUT)
print("saved:", OUT, "final:", canvas.size, "char:", (nw, nh))
