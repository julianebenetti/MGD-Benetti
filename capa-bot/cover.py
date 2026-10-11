"""Capa de Reels — padrão "Achei na Shopee" (1080x1920), conforme o documento de padrão."""
import math, subprocess
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

W, H = 1080, 1920
CX = W // 2
FONTS = Path(__file__).parent / "fonts"
F_TITLE = FONTS / "Boogaloo-Regular.ttf"
F_BADGE = FONTS / "Montserrat-ExtraBold.ttf"
WHITE, BLACK, GOLD = (255, 255, 255), (0, 0, 0), (255, 205, 40)

LINE1 = "ACHEI NA SHOPEE"
SIZE1, SIZE3, SIZE4, SIZE_BADGE = 78, 122, 70, 46
STROKE1, STROKE3, STROKE4 = 7, 9, 6
GAP_1_BADGE, GAP_BADGE_3, GAP_3_4 = 48, 66, 96
PAD_X, PAD_Y = 34, 18
BADGE_MIN, BADGE_MAX_W = 26, W - 260
STAR, STAR_GAP = 26, 36
BLOCK_OFFSET_UP = 140


def extract_frames(video: Path, n: int = 4) -> list[Path]:
    """n frames igualmente espaçados do vídeo (JPEG), para fundo e para o Claude olhar."""
    dur = float(subprocess.check_output(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nw=1:nk=1", str(video)]).decode().strip() or 1)
    out = []
    for i in range(n):
        p = video.with_name(f"frame{i}.jpg")
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{dur * (i + 1) / (n + 1):.2f}",
                        "-i", str(video), "-frames:v", "1", "-q:v", "2", str(p)], check=True)
        out.append(p)
    return out


def cover_fit(img: Image.Image) -> Image.Image:
    img = img.convert("RGB")
    s = max(W / img.width, H / img.height)
    img = img.resize((round(img.width * s), round(img.height * s)), Image.LANCZOS)
    x, y = (img.width - W) // 2, (img.height - H) // 2
    return img.crop((x, y, x + W, y + H))


def _font(path, size):
    return ImageFont.truetype(str(path), size)


def _sparkle(draw, cx, cy, size, fill, outline=None, outline_w=0):
    """Estrela de 4 pontas."""
    pts = []
    for i in range(8):
        r = size if i % 2 == 0 else size * 0.28
        a = math.pi / 2 * (i / 2) - math.pi / 2
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    if outline:
        draw.polygon(pts, fill=outline)
        draw.line(pts + [pts[0]], fill=outline, width=outline_w * 2, joint="curve")
    draw.polygon(pts, fill=fill)


def _stars(draw, cx, cy, size, side):
    """Principal dourada com contorno branco + companheira branca na diagonal superior."""
    _sparkle(draw, cx, cy, size, GOLD, WHITE, 4)
    _sparkle(draw, cx + side * 1.5 * size, cy - 0.85 * size, size * 0.38, WHITE)


def _text_h(draw, text, font, stroke):
    b = draw.textbbox((0, 0), text, font=font, anchor="mm", stroke_width=stroke)
    return b[3] - b[1]


def _fit(draw, text, path, size, stroke, max_w=W - 80):
    """Reduz a fonte só se a linha estourar o canvas (proteção para textos longos)."""
    while size > 30 and draw.textlength(text, font=_font(path, size)) + 2 * stroke > max_w:
        size -= 2
    return _font(path, size)


def compose(background: Image.Image, badge: str, linha3: str, linha4: str) -> Image.Image:
    img = cover_fit(background).convert("RGBA")
    d = ImageDraw.Draw(img)
    badge, linha3, linha4 = badge.upper(), linha3.upper(), linha4.upper()

    f1 = _fit(d, LINE1, F_TITLE, SIZE1, STROKE1)
    f3 = _fit(d, linha3, F_TITLE, SIZE3, STROKE3)
    f4 = _fit(d, linha4, F_TITLE, SIZE4, STROKE4)

    bsize = SIZE_BADGE                       # faixa: reduz de 2 em 2 até caber (mín. 26)
    while bsize > BADGE_MIN and d.textlength(badge, font=_font(F_BADGE, bsize)) + 2 * PAD_X > BADGE_MAX_W:
        bsize -= 2
    fb = _font(F_BADGE, bsize)
    bw = d.textlength(badge, font=fb) + 2 * PAD_X
    bh = _text_h(d, badge, fb, 0) + 2 * PAD_Y

    h1, h3, h4 = _text_h(d, LINE1, f1, STROKE1), _text_h(d, linha3, f3, STROKE3), _text_h(d, linha4, f4, STROKE4)
    total = h1 + GAP_1_BADGE + bh + GAP_BADGE_3 + h3 + GAP_3_4 + h4
    top = H / 2 - total / 2 - BLOCK_OFFSET_UP

    y1 = top + h1 / 2
    yb = top + h1 + GAP_1_BADGE + bh / 2
    y3 = top + h1 + GAP_1_BADGE + bh + GAP_BADGE_3 + h3 / 2
    y4 = top + h1 + GAP_1_BADGE + bh + GAP_BADGE_3 + h3 + GAP_3_4 + h4 / 2

    d.text((CX, y1), LINE1, font=f1, fill=WHITE, anchor="mm", stroke_width=STROKE1, stroke_fill=BLACK)
    d.rounded_rectangle((CX - bw / 2, yb - bh / 2, CX + bw / 2, yb + bh / 2), radius=bh // 2, fill=WHITE)
    d.text((CX, yb), badge, font=fb, fill=BLACK, anchor="mm")
    _stars(d, CX - bw / 2 - STAR_GAP, yb, STAR, -1)
    _stars(d, CX + bw / 2 + STAR_GAP, yb, STAR, +1)
    d.text((CX, y3), linha3, font=f3, fill=WHITE, anchor="mm", stroke_width=STROKE3, stroke_fill=BLACK)
    d.text((CX, y4), linha4, font=f4, fill=WHITE, anchor="mm", stroke_width=STROKE4, stroke_fill=BLACK)

    ov = Image.new("RGBA", img.size, (0, 0, 0, 0))   # ícone de play (canto superior direito)
    od = ImageDraw.Draw(ov)
    px, py, r = W - 70, 70, 34
    od.ellipse((px - r, py - r, px + r, py + r), fill=(0, 0, 0, 130))
    od.polygon([(px - 10, py - 16), (px - 10, py + 16), (px + 17, py)], fill=WHITE)
    return Image.alpha_composite(img, ov).convert("RGB")
