import base64, json, os
from pathlib import Path
import anthropic

PROMPT = """Você cria headlines para capas de Reels de uma afiliada brasileira (Shopee), estilo Pinterest.
Veja os frames do vídeo e a legenda (se houver) e escreva 3 headlines em português do Brasil:
- até 7 palavras, tom de curiosidade/desejo, sem clickbait enganoso
- NUNCA mencione suplementos, vitaminas, colágeno ou whey
- sem emojis, sem hashtags
Legenda: {caption}
Responda SOMENTE com um JSON: {{"headlines": ["...", "...", "..."]}}"""


def suggest(frames: list[Path], caption: str = "") -> list[str]:
    content = [{"type": "image", "source": {"type": "base64", "media_type": "image/jpeg",
                "data": base64.b64encode(f.read_bytes()).decode()}} for f in frames]
    content.append({"type": "text", "text": PROMPT.format(caption=caption or "(sem legenda)")})
    msg = anthropic.Anthropic().messages.create(
        model=os.environ.get("HEADLINE_MODEL", "claude-sonnet-5-5"),
        max_tokens=400, messages=[{"role": "user", "content": content}])
    text = msg.content[0].text
    return json.loads(text[text.index("{"): text.rindex("}") + 1])["headlines"][:3]
