"""
Identidade visual usada na capa e na marca d'agua.

Os valores ficam em identidade.json, na mesma pasta. O arquivo e opcional:
sem ele valem os padroes daqui, que seguem o roxo ja usado na AfiliDash e
no app de Videos IA.
"""
import json
import os

PASTA = os.path.dirname(os.path.abspath(__file__))
ARQUIVO = os.path.join(PASTA, "identidade.json")

# Inclui os caminhos do Android e do Termux, para o caso de tudo rodar no
# proprio tablet. Roboto existe em qualquer Android.
FONTES_CANDIDATAS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    os.path.join(os.environ.get("PREFIX", "/nao-existe"),
                 "share/fonts/TTF/DejaVuSans-Bold.ttf"),
    "/data/data/com.termux/files/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
    "/system/fonts/Roboto-Bold.ttf",
    "/system/fonts/RobotoStatic-Bold.ttf",
    "/system/fonts/DroidSans-Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
]

PADRAO = {
    "handle": "@julianebenetti",
    "cor_principal": "#a855f7",
    "cor_secundaria": "#7c3aed",
    "cor_texto": "#ffffff",
    "fonte": None,          # None = procura uma fonte do sistema
    "logo": None,           # PNG opcional, entra na capa e na marca d'agua
    "marca": {
        "posicao": "inferior-direito",
        "tamanho": 44,      # altura do texto em px, no video de 1080x1920
        "opacidade": 0.85,
        "fundo": True,      # caixinha escura atras do texto
        "largura_logo": 200,
    },
    "capa": {
        "modelo": "faixa",  # faixa | minimo | cartao
        "titulo_max": 42,   # caracteres antes de quebrar linha
        "mostrar_preco": True,
        "mostrar_nota": True,
        "selo": "ACHADINHO",
        "escurecer": 0.55,  # forca do degrade sobre a foto
    },
    "video": {
        "realce": True,     # leve ajuste de contraste, saturacao e volume
        "contraste": 1.06,
        "saturacao": 1.12,
        "brilho": 0.01,
        "normalizar_audio": True,
    },
    "specs": {              # o que e conferido no arquivo final
        "largura": 1080,
        "altura": 1920,
        "duracao_min": 10,
        "duracao_max": 60,
        "tamanho_max_mb": 100,
    },
}


def _fundir(base, novo):
    saida = dict(base)
    for chave, valor in (novo or {}).items():
        if isinstance(valor, dict) and isinstance(saida.get(chave), dict):
            saida[chave] = _fundir(saida[chave], valor)
        else:
            saida[chave] = valor
    return saida


def achar_fonte(caminho=None):
    for candidata in [caminho, os.environ.get("FONTE_MARCA"), *FONTES_CANDIDATAS]:
        if candidata and os.path.exists(candidata):
            return candidata
    raise RuntimeError(
        "Nenhuma fonte encontrada. Aponte uma em identidade.json > fonte "
        "(ex: um .ttf da sua marca) ou instale fonts-dejavu."
    )


def carregar(caminho=None):
    """Devolve a identidade completa, com os padroes preenchidos."""
    alvo = caminho or ARQUIVO
    dados = {}
    if os.path.exists(alvo):
        with open(alvo, encoding="utf-8") as arq:
            dados = json.load(arq)
    ident = _fundir(PADRAO, dados)
    ident["fonte"] = achar_fonte(ident.get("fonte"))
    if ident.get("logo") and not os.path.isabs(ident["logo"]):
        ident["logo"] = os.path.join(PASTA, ident["logo"])
    return ident


def rgb(cor, alfa=None):
    """#a855f7 -> (168, 85, 247) ou (168, 85, 247, 217) com alfa 0..1."""
    limpo = cor.lstrip("#")
    valores = tuple(int(limpo[i:i + 2], 16) for i in (0, 2, 4))
    return valores if alfa is None else valores + (int(255 * alfa),)
