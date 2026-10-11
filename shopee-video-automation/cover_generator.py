"""
Cover Generator
Gera a capa do vídeo: melhor quadro do vídeo + título em faixas brancas arredondadas.
"""

import logging
import subprocess
import tempfile
from pathlib import Path
from typing import List, Optional, Tuple

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageStat

logger = logging.getLogger(__name__)

ASSETS = Path(__file__).parent / 'assets'
TEXT_FONT = ASSETS / 'fonts' / 'Oswald.ttf'
EMOJI_FONT = Path('/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf')
EMOJI_NATIVE_SIZE = 109  # Noto Color Emoji só renderiza nesse tamanho

# Proporções medidas nas capas de referência do perfil
FONT_SIZE_RATIO = 0.062
MAX_TEXT_WIDTH_RATIO = 0.70
TEXT_CENTER_Y_RATIO = 0.47
PILL_PAD_X_RATIO = 0.35
PILL_PAD_Y_RATIO = 0.10
LINE_OVERLAP_RATIO = 0.18
TEXT_COLOR = (34, 34, 34, 255)
PILL_COLOR = (255, 255, 255, 240)


def _is_emoji(ch: str) -> bool:
    cp = ord(ch)
    return (cp >= 0x1F000 or 0x2600 <= cp <= 0x27BF or 0x2B00 <= cp <= 0x2BFF
            or cp in (0x200D, 0xFE0F, 0x2122, 0x2139) or 0x2190 <= cp <= 0x21FF)


def _runs(text: str) -> List[Tuple[bool, str]]:
    runs: List[Tuple[bool, str]] = []
    for ch in text:
        e = _is_emoji(ch)
        if runs and runs[-1][0] == e:
            runs[-1] = (e, runs[-1][1] + ch)
        else:
            runs.append((e, ch))
    return runs


class CoverGenerator:
    def __init__(self, width: int = 1080, height: int = 1920):
        self.width = width
        self.height = height
        self.font_size = int(width * FONT_SIZE_RATIO)
        self.font = ImageFont.truetype(str(TEXT_FONT), self.font_size)
        self.font.set_variation_by_name('Regular')
        self.emoji_font = ImageFont.truetype(str(EMOJI_FONT), EMOJI_NATIVE_SIZE)
        self.emoji_size = int(self.font_size * 0.95)

    def pick_frame(self, video_path: str, samples: int = 10) -> Image.Image:
        """Escolhe o quadro mais nítido entre amostras (ignora início e fim)."""
        duration = float(subprocess.run(
            ['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
             '-of', 'csv=p=0', video_path],
            capture_output=True, text=True, check=True).stdout.strip())

        best, best_score = None, -1.0
        with tempfile.TemporaryDirectory() as tmp:
            for i in range(samples):
                t = duration * (0.1 + 0.8 * i / max(samples - 1, 1))
                out = Path(tmp) / f'f{i}.png'
                subprocess.run(['ffmpeg', '-loglevel', 'error', '-ss', f'{t:.2f}', '-i', video_path,
                                '-frames:v', '1', '-y', str(out)], check=True)
                if not out.exists():
                    continue
                img = Image.open(out).convert('RGB')
                score = ImageStat.Stat(img.convert('L').filter(ImageFilter.FIND_EDGES)).var[0]
                if score > best_score:
                    best, best_score = img.copy(), score
        if best is None:
            raise RuntimeError(f'Nenhum quadro extraído de {video_path}')
        return best.resize((self.width, self.height))

    def _emoji_img(self, ch: str) -> Image.Image:
        size = EMOJI_NATIVE_SIZE
        canvas = Image.new('RGBA', (size * 2, size * 2), (0, 0, 0, 0))
        ImageDraw.Draw(canvas).text((0, 0), ch, font=self.emoji_font, embedded_color=True)
        bbox = canvas.getbbox() or (0, 0, 1, 1)
        return canvas.crop(bbox).resize((self.emoji_size, self.emoji_size), Image.LANCZOS)

    def _emoji_clusters(self, s: str) -> List[str]:
        clusters: List[str] = []
        for ch in s:
            if clusters and (ch in '‍️' or clusters[-1].endswith('‍')):
                clusters[-1] += ch
            else:
                clusters.append(ch)
        return clusters

    def _measure(self, text: str) -> int:
        w = 0
        for is_emoji, run in _runs(text):
            if is_emoji:
                w += len(self._emoji_clusters(run)) * (self.emoji_size + 4)
            else:
                w += int(self.font.getlength(run))
        return w

    def _wrap(self, text: str) -> List[str]:
        max_w = self.width * MAX_TEXT_WIDTH_RATIO
        lines, cur = [], ''
        for word in text.split():
            cand = f'{cur} {word}'.strip()
            if cur and self._measure(cand) > max_w:
                lines.append(cur)
                cur = word
            else:
                cur = cand
        if cur:
            lines.append(cur)
        return lines

    def _draw_line(self, base: Image.Image, text: str, cx: int, top: int) -> int:
        text_w = self._measure(text)
        ascent, descent = self.font.getmetrics()
        line_h = ascent + descent
        pad_x = int(self.font_size * PILL_PAD_X_RATIO)
        pad_y = int(self.font_size * PILL_PAD_Y_RATIO)
        pill_w, pill_h = text_w + 2 * pad_x, line_h + 2 * pad_y
        left = cx - pill_w // 2

        overlay = Image.new('RGBA', base.size, (0, 0, 0, 0))
        d = ImageDraw.Draw(overlay)
        d.rounded_rectangle((left, top, left + pill_w, top + pill_h), radius=pill_h // 2, fill=PILL_COLOR)
        base.alpha_composite(overlay)

        d = ImageDraw.Draw(base)
        x = left + pad_x
        for is_emoji, run in _runs(text):
            if is_emoji:
                for cl in self._emoji_clusters(run):
                    em = self._emoji_img(cl)
                    base.alpha_composite(em, (x + 2, top + pad_y + (line_h - self.emoji_size) // 2))
                    x += self.emoji_size + 4
            else:
                d.text((x, top + pad_y), run, font=self.font, fill=TEXT_COLOR)
                x += int(self.font.getlength(run))
        return pill_h

    def generate(self, video_path: str, title: str, output_path: str) -> Optional[str]:
        try:
            frame = self.pick_frame(video_path).convert('RGBA')
            lines = self._wrap(title)
            ascent, descent = self.font.getmetrics()
            pill_h = ascent + descent + 2 * int(self.font_size * PILL_PAD_Y_RATIO)
            step = int(pill_h * (1 - LINE_OVERLAP_RATIO))
            total_h = step * (len(lines) - 1) + pill_h
            top = int(self.height * TEXT_CENTER_Y_RATIO - total_h / 2)
            for i, line in enumerate(lines):
                self._draw_line(frame, line, self.width // 2, top + i * step)
            frame.convert('RGB').save(output_path, quality=92)
            logger.info(f'✅ Capa gerada: {output_path}')
            return output_path
        except Exception as e:
            logger.error(f'Erro ao gerar capa: {e}')
            return None
