"""Estilo da capa. Ajuste aqui para ficar igual às capas que você já usa."""
from pathlib import Path

W, H = 1080, 1920                       # 9:16 (Reels)
FONT_PATH = Path(__file__).parent / "fonts" / "headline.ttf"  # coloque sua fonte aqui
TEXT_COLOR = (255, 255, 255)
ACCENT_COLOR = (255, 214, 102)          # destaque (última linha da headline)
SHADOW_COLOR = (0, 0, 0, 150)
MAX_TEXT_WIDTH = int(W * 0.84)
TEXT_Y_CENTER = int(H * 0.30)           # headline no terço superior (área segura do Reels)

IMAGE_PROMPT = (
    "Capa vertical de Reels estilo Pinterest: fotografia lifestyle estética, luz natural "
    "suave, tons quentes e neutros, composição limpa com espaço livre no terço superior "
    "para texto. Use a imagem de referência como inspiração do produto/cena. "
    "NÃO inclua nenhum texto, letras, logos ou marcas d'água na imagem."
)
