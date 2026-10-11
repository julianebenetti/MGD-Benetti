"""Texto da capa: Claude lê as imagens e propõe faixa (produto) + gancho + complemento."""
import base64, json, os
from pathlib import Path
import anthropic

PROMPT = """Você monta o texto de capas de Reels de uma afiliada brasileira da Shopee ("Achei na Shopee").
A capa tem 3 textos (a linha "ACHEI NA SHOPEE" é fixa, não escreva):
- "badge": nome/apelido CURTO do produto (vai numa faixa branca)
- "linha3": o gancho principal / benefício, concreto (a maior linha da capa)
- "linha4": complemento do gancho
Exemplos do padrão: badge "AQUECEDOR PORTÁTIL" / linha3 "ESQUENTA A ÁGUA" / linha4 "EM 3 SEGUNDOS";
"ORGANIZA TUDO" / "SEM FURAR A PAREDE"; "CARREGA RÁPIDO" / "E AINDA VIRA APOIO".
Regras: gancho forte e concreto, nunca genérico; português do Brasil; sem emojis; tudo em MAIÚSCULAS;
linha3 até ~20 caracteres e linha4 até ~26. NUNCA para suplementos, vitaminas, colágeno ou whey.

As imagens vêm nesta ordem: as primeiras são do VÍDEO/fundo da capa; as demais (se houver) são prints
da Shopee só de contexto. Se as imagens de contexto mostrarem um produto DIFERENTE do fundo,
marque "inconsistente": true e explique em "aviso" — não assuma qual está certo.
{extra}
Responda SOMENTE com JSON:
{{"produto": "...", "inconsistente": false, "aviso": "",
  "opcoes": [{{"badge": "...", "linha3": "...", "linha4": "..."}}, ... 3 opções diferentes ...]}}"""


def _img(p: Path):
    return {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg",
            "data": base64.b64encode(p.read_bytes()).decode()}}


def suggest(images: list[Path], caption: str = "", correcao: str = "") -> dict:
    extra = ""
    if caption:
        extra += f"\nLegenda enviada: {caption}"
    if correcao:
        extra += f"\nCORREÇÃO da usuária sobre o produto/função (siga isto): {correcao}"
    msg = anthropic.Anthropic().messages.create(
        model=os.environ.get("HEADLINE_MODEL", "claude-sonnet-5-5"), max_tokens=700,
        messages=[{"role": "user", "content": [*map(_img, images), {"type": "text", "text": PROMPT.format(extra=extra)}]}])
    t = msg.content[0].text
    data = json.loads(t[t.index("{"): t.rindex("}") + 1])
    data["opcoes"] = data["opcoes"][:3]
    return data
