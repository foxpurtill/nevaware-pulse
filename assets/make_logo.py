"""
NeveWare Logo Generator v2
Fixed N proportions — proper letter, not three sticks.
"""
from PIL import Image, ImageDraw
import math, os

OUTPUT_DIR = r"C:\Code\nevaware-pulse\assets"

def draw_N(draw, cx, cy, size, color, stroke):
    """
    Draw a proper N:
    - Two strong verticals
    - Diagonal connecting top-left to bottom-right
    - Verticals are heavier than diagonal
    """
    half = size // 2
    # Corners
    tl = (cx - half, cy - half)  # top left
    bl = (cx - half, cy + half)  # bottom left
    tr = (cx + half, cy - half)  # top right
    br = (cx + half, cy + half)  # bottom right

    diag_stroke = max(1, stroke - 2)

    # Left vertical (heavy)
    draw.line([bl, tl], fill=color, width=stroke)
    # Diagonal top-left to bottom-right (lighter)
    draw.line([tl, br], fill=color, width=diag_stroke)
    # Right vertical (heavy)
    draw.line([tr, br], fill=color, width=stroke)

def make_nevaware_logo(size=256):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    cx, cy = size // 2, size // 2
    r = int(size * 0.46)

    # Outer glow
    for i in range(8, 0, -1):
        gr = r + i * 2
        alpha = max(0, 25 - i * 3)
        draw.ellipse([cx-gr, cy-gr, cx+gr, cy+gr],
                     outline=(140, 200, 255, alpha), width=2)

    # Background circle
    draw.ellipse([cx-r, cy-r, cx+r, cy+r], fill=(8, 18, 35, 245))

    # Ring
    rw = max(2, size // 60)
    draw.ellipse([cx-r+rw, cy-r+rw, cx+r-rw, cy+r-rw],
                 outline=(180, 225, 255, 255), width=rw)

    # Dot-dash accent marks (top arc — cheekbone echo)
    ar = r - rw * 3 - int(size * 0.03)
    for i, angle_deg in enumerate(range(-55, 60, 14)):
        angle = math.radians(angle_deg - 90)
        ax = int(cx + ar * math.cos(angle))
        ay = int(cy + ar * math.sin(angle))
        # Alternate small/large dots
        ds = max(2, size // 60) if i % 2 == 0 else max(1, size // 90)
        draw.ellipse([ax-ds, ay-ds, ax+ds, ay+ds],
                     fill=(200, 235, 255, 160))

    # Glow layer for N
    glow = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    n_size = int(size * 0.36)
    stroke = max(3, size // 22)
    draw_N(gd, cx, cy, n_size, (100, 180, 255, 50), stroke + max(3, size // 32))
    img = Image.alpha_composite(img, glow)

    # N itself
    draw2 = ImageDraw.Draw(img)
    draw_N(draw2, cx, cy, n_size, (230, 245, 255, 255), stroke)

    return img


def make_tray_icon(size=64, active=True):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    cx, cy = size // 2, size // 2
    r = int(size * 0.46)

    fill  = (170, 28, 28, 245) if active else (28, 145, 75, 245)
    ring  = (220, 80, 80, 255) if active else (75, 195, 115, 255)

    draw.ellipse([cx-r, cy-r, cx+r, cy+r], fill=fill)
    draw.ellipse([cx-r, cy-r, cx+r, cy+r], outline=ring, width=max(1, size//28))

    stroke = max(2, size // 14)
    n_size = int(size * 0.36)
    draw_N(draw, cx, cy, n_size, (255, 255, 255, 255), stroke)

    return img


if __name__ == "__main__":
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    for size in [256, 128, 64, 32]:
        p = os.path.join(OUTPUT_DIR, f"nevaware_logo_{size}.png")
        make_nevaware_logo(size).save(p)
        print(f"Saved: {p}")

    make_nevaware_logo(256).save(os.path.join(OUTPUT_DIR, "nevaware_logo.png"))
    print("Saved: nevaware_logo.png")

    make_tray_icon(64, active=True).save(os.path.join(OUTPUT_DIR, "tray_active.png"))
    print("Saved: tray_active.png (red)")

    make_tray_icon(64, active=False).save(os.path.join(OUTPUT_DIR, "tray_present.png"))
    print("Saved: tray_present.png (green)")

    print("\nDone.")
