import base64, io, os, subprocess, tempfile
from pathlib import Path
import requests
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import style


def extract_frames(video: Path, n: int = 3) -> list[Path]:
    """n frames igualmente espaçados do vídeo (JPEG)."""
    dur = float(subprocess.check_output(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nw=1:nk=1", str(video)]).decode().strip() or 1)
    out = []
    for i in range(n):
        t = dur * (i + 1) / (n + 1)
        p = video.with_name(f"frame{i}.jpg")
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{t:.2f}", "-i", str(video),
                        "-frames:v", "1", "-q:v", "3", str(p)], check=True)
        out.append(p)
    return out


def generate_background(reference: Path) -> Image.Image:
    """Fundo gerado por IA (gpt-image-1, usando um frame como referência)."""
    r = requests.post(
        "https://api.openai.com/v1/images/edits",
        headers={"Authorization": f"Bearer {os.environ['OPENAI_API_KEY']}"},
        files={"image": ("ref.jpg", reference.read_bytes(), "image/jpeg")},
        data={"model": "gpt-image-1", "prompt": style.IMAGE_PROMPT, "size": "1024x1536"},
        timeout=300)
    r.raise_for_status()
    img = Image.open(io.BytesIO(base64.b64decode(r.json()["data"][0]["b64_json"]))).convert("RGB")
    return fit_cover(img, style.W, style.H)


def fit_cover(img: Image.Image, w: int, h: int) -> Image.Image:
    s = max(w / img.width, h / img.height)
    img = img.resize((round(img.width * s), round(img.height * s)), Image.LANCZOS)
    x, y = (img.width - w) // 2, (img.height - h) // 2
    return img.crop((x, y, x + w, y + h))


def _font(size: int):
    try:
        return ImageFont.truetype(str(style.FONT_PATH), size)
    except OSError:
        for f in ("DejaVuSans-Bold.ttf", "Arial Bold.ttf"):
            try:
                return ImageFont.truetype(f, size)
            except OSError:
                pass
        return ImageFont.load_default()


def _wrap(draw, text, font, max_w):
    lines, cur = [], ""
    for word in text.split():
        t = f"{cur} {word}".strip()
        if draw.textlength(t, font=font) <= max_w:
            cur = t
        else:
            lines.append(cur)
            cur = word
    return lines + [cur] if cur else lines


def compose(bg: Image.Image, headline: str) -> Image.Image:
    """Escurece levemente o topo e aplica a headline (texto 100% por código)."""
    bg = bg.convert("RGBA")
    grad = Image.new("RGBA", bg.size, (0, 0, 0, 0))
    gd = ImageDraw.Draw(grad)
    for y in range(int(style.H * 0.6)):
        gd.line([(0, y), (style.W, y)], fill=(0, 0, 0, int(120 * (1 - y / (style.H * 0.6)))))
    bg = Image.alpha_composite(bg, grad)

    draw = ImageDraw.Draw(bg)
    size = 120
    while size > 50:
        font = _font(size)
        lines = _wrap(draw, headline.upper(), font, style.MAX_TEXT_WIDTH)
        if len(lines) <= 4 and all(draw.textlength(l, font=font) <= style.MAX_TEXT_WIDTH for l in lines):
            break
        size -= 6
    lh = int(size * 1.15)
    y = style.TEXT_Y_CENTER - lh * len(lines) // 2

    shadow = Image.new("RGBA", bg.size, (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    for i, l in enumerate(lines):
        x = (style.W - sd.textlength(l, font=font)) / 2
        sd.text((x + 4, y + i * lh + 6), l, font=font, fill=style.SHADOW_COLOR)
    bg = Image.alpha_composite(bg, shadow.filter(ImageFilter.GaussianBlur(6)))

    draw = ImageDraw.Draw(bg)
    for i, l in enumerate(lines):
        x = (style.W - draw.textlength(l, font=font)) / 2
        color = style.ACCENT_COLOR if i == len(lines) - 1 and len(lines) > 1 else style.TEXT_COLOR
        draw.text((x, y + i * lh), l, font=font, fill=color)
    return bg.convert("RGB")
