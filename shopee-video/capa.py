"""
Capa (thumbnail) do post e marca d'agua, montadas com a sua identidade.

A capa sai do proprio video: o modulo testa varios quadros, escolhe o mais
nitido e colorido e monta em cima dele o selo, o titulo, o preco e a nota.
A marca d'agua e gerada como PNG transparente, entao nao depende do filtro
drawtext estar compilado no ffmpeg.
"""
import math
import os

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageStat

import identidade as ident_mod
import legenda
import video as video_mod

LARGURA, ALTURA = 1080, 1920


# ── escolha do quadro ────────────────────────────────────────────
def _pontuar(caminho):
    """Nitidez, cor e exposicao do quadro. Maior e melhor."""
    with Image.open(caminho) as imagem:
        pequena = imagem.convert("RGB").resize((320, 568))
    cinza = pequena.convert("L")
    nitidez = ImageStat.Stat(cinza.filter(ImageFilter.FIND_EDGES)).var[0]
    cor = sum(ImageStat.Stat(pequena).stddev) / 3
    media = ImageStat.Stat(cinza).mean[0]
    # quadro estourado ou quase preto perde pontos
    exposicao = 1 - abs(media - 128) / 128
    return {"nitidez": nitidez, "cor": cor, "exposicao": max(exposicao, 0)}


def escolher_quadro(caminho_video, pasta, candidatos=10, limite_duracao=None):
    """
    Extrai quadros espalhados pelo video e devolve o melhor deles.

    limite_duracao evita cair no cartao final do CapCut quando a busca roda
    no arquivo original, antes do corte.
    """
    info = video_mod.inspecionar(caminho_video)
    duracao = min(info["duracao"], limite_duracao or info["duracao"])
    inicio, fim = duracao * 0.15, duracao * 0.85
    if fim <= inicio:
        inicio, fim = 0.0, max(duracao - 0.1, 0.1)
    passo = (fim - inicio) / max(candidatos - 1, 1)

    quadros = []
    for indice in range(candidatos):
        momento = inicio + passo * indice
        destino = os.path.join(pasta, f"quadro_{indice:02d}.png")
        resultado = video_mod._rodar([
            "-ss", f"{momento:.2f}", "-i", caminho_video,
            "-frames:v", "1", "-q:v", "2", destino,
        ])
        if resultado.returncode == 0 and os.path.exists(destino):
            quadros.append({"arquivo": destino, "momento": momento,
                            **_pontuar(destino)})
    if not quadros:
        raise RuntimeError("Nao consegui extrair nenhum quadro do video.")

    def normalizar(chave):
        valores = [q[chave] for q in quadros]
        menor, maior = min(valores), max(valores)
        faixa = (maior - menor) or 1
        for quadro in quadros:
            quadro[f"n_{chave}"] = (quadro[chave] - menor) / faixa

    for chave in ("nitidez", "cor", "exposicao"):
        normalizar(chave)
    for quadro in quadros:
        quadro["nota"] = (0.6 * quadro["n_nitidez"] + 0.25 * quadro["n_cor"]
                          + 0.15 * quadro["n_exposicao"])
    return max(quadros, key=lambda q: q["nota"])


# ── desenho ──────────────────────────────────────────────────────
def _fonte(ident, tamanho):
    return ImageFont.truetype(ident["fonte"], tamanho)


def _largura(desenho, texto, fonte):
    caixa = desenho.textbbox((0, 0), texto, font=fonte)
    return caixa[2] - caixa[0]


def quebrar(desenho, texto, fonte, largura_max, max_linhas=3):
    linhas, atual = [], ""
    for palavra in texto.split():
        teste = f"{atual} {palavra}".strip()
        if _largura(desenho, teste, fonte) <= largura_max or not atual:
            atual = teste
        else:
            linhas.append(atual)
            atual = palavra
            if len(linhas) == max_linhas:
                break
    if atual and len(linhas) < max_linhas:
        linhas.append(atual)
    if len(linhas) == max_linhas and _largura(desenho, linhas[-1], fonte) > largura_max * 0.98:
        linhas[-1] = linhas[-1][:-3] + "..."
    return linhas


def titulo_curto(nome, max_palavras=6):
    """Corta o titulo quilometrico da Shopee no que cabe numa capa."""
    escolhidas = []
    for palavra in nome.split():
        limpa = legenda.normalizar(palavra)
        if not limpa or limpa in legenda.LIXO_NOME:
            continue
        escolhidas.append(palavra)
        if len(escolhidas) == max_palavras:
            break
    return " ".join(escolhidas) or nome


def _estrela(desenho, centro, raio, cor):
    pontos = []
    for passo in range(10):
        angulo = math.radians(-90 + passo * 36)
        distancia = raio if passo % 2 == 0 else raio * 0.45
        pontos.append((centro[0] + distancia * math.cos(angulo),
                       centro[1] + distancia * math.sin(angulo)))
    desenho.polygon(pontos, fill=cor)


def _degrade_inferior(imagem, forca):
    """Escurece a parte de baixo para o texto ficar legivel."""
    altura = imagem.height
    mascara = Image.new("L", (1, altura))
    for linha in range(altura):
        posicao = linha / altura
        valor = 0 if posicao < 0.45 else (posicao - 0.45) / 0.55
        mascara.putpixel((0, linha), int(255 * forca * (valor ** 1.4)))
    mascara = mascara.resize(imagem.size)
    preto = Image.new("RGB", imagem.size, (0, 0, 0))
    return Image.composite(preto, imagem, mascara)


def _colar_logo(imagem, ident, largura, posicao):
    caminho = ident.get("logo")
    if not caminho or not os.path.exists(caminho):
        return None
    with Image.open(caminho) as bruta:
        logo = bruta.convert("RGBA")
    altura = max(1, int(logo.height * largura / logo.width))
    logo = logo.resize((largura, altura), Image.LANCZOS)
    imagem.paste(logo, posicao, logo)
    return logo.size


def montar_capa(quadro, destino, produto, ident):
    """Compoe a capa 1080x1920 a partir do quadro escolhido."""
    conf = ident["capa"]
    with Image.open(quadro) as bruta:
        base = bruta.convert("RGB")

    escala = max(LARGURA / base.width, ALTURA / base.height)
    base = base.resize((max(LARGURA, int(base.width * escala)),
                        max(ALTURA, int(base.height * escala))), Image.LANCZOS)
    esquerda = (base.width - LARGURA) // 2
    topo = (base.height - ALTURA) // 2
    base = base.crop((esquerda, topo, esquerda + LARGURA, topo + ALTURA))

    modelo = conf.get("modelo", "faixa")
    if modelo != "minimo":
        base = _degrade_inferior(base, float(conf.get("escurecer", 0.55)))

    capa = base.convert("RGBA")
    camada = Image.new("RGBA", capa.size, (0, 0, 0, 0))
    desenho = ImageDraw.Draw(camada)

    principal = ident_mod.rgb(ident["cor_principal"])
    secundaria = ident_mod.rgb(ident["cor_secundaria"])
    texto_cor = ident_mod.rgb(ident["cor_texto"])

    margem = 72

    # o layout e montado de baixo para cima para nada se sobrepor
    y_handle = ALTURA - 92
    y_selos_base = y_handle - 78
    tem_selos = modelo != "minimo" and (
        (conf.get("mostrar_preco", True) and produto.get("preco"))
        or (conf.get("mostrar_nota", True) and produto.get("nota"))
    )
    y_selos_topo = y_selos_base - 96 if tem_selos else y_selos_base
    y_titulo_base = y_selos_topo - (56 if tem_selos else 20)

    titulo = titulo_curto((produto.get("nome") or "").strip(),
                          conf.get("titulo_palavras", 6))
    fonte_titulo = _fonte(ident, 76)
    altura_linha = 90
    linhas = quebrar(desenho, titulo, fonte_titulo, LARGURA - 2 * margem,
                     max_linhas=conf.get("titulo_linhas", 2)) if titulo else []
    y_titulo_topo = y_titulo_base - altura_linha * len(linhas)

    if modelo == "cartao":
        desenho.rounded_rectangle(
            [margem - 28, y_titulo_topo - 40, LARGURA - margem + 28, ALTURA - 44],
            radius=44, fill=(0, 0, 0, 165),
        )

    # selo do topo
    selo = (conf.get("selo") or "").strip()
    if selo and modelo != "minimo":
        fonte_selo = _fonte(ident, 40)
        largura_selo = _largura(desenho, selo, fonte_selo)
        desenho.rounded_rectangle(
            [margem, 140, margem + largura_selo + 64, 216],
            radius=38, fill=principal + (235,),
        )
        desenho.text((margem + 32, 178), selo, font=fonte_selo,
                     fill=texto_cor + (255,), anchor="lm")

    # titulo
    y = y_titulo_topo
    for linha in linhas:
        desenho.text((margem + 3, y + 3), linha, font=fonte_titulo,
                     fill=(0, 0, 0, 150))
        desenho.text((margem, y), linha, font=fonte_titulo,
                     fill=texto_cor + (255,))
        y += altura_linha

    # preco e nota, lado a lado
    if tem_selos:
        cursor = margem
        preco = produto.get("preco")
        if conf.get("mostrar_preco", True) and preco:
            fonte_preco = _fonte(ident, 60)
            texto_preco = f"R$ {preco}"
            largura_preco = _largura(desenho, texto_preco, fonte_preco)
            desenho.rounded_rectangle(
                [cursor, y_selos_topo, cursor + largura_preco + 60, y_selos_topo + 96],
                radius=26, fill=secundaria + (240,),
            )
            desenho.text((cursor + 30, y_selos_topo + 48), texto_preco,
                         font=fonte_preco, fill=texto_cor + (255,), anchor="lm")
            cursor += largura_preco + 84

        nota = produto.get("nota")
        if conf.get("mostrar_nota", True) and nota:
            fonte_nota = _fonte(ident, 54)
            texto_nota = f"{nota}".replace(".", ",")
            largura_nota = _largura(desenho, texto_nota, fonte_nota)
            desenho.rounded_rectangle(
                [cursor, y_selos_topo, cursor + largura_nota + 108, y_selos_topo + 96],
                radius=26, fill=(255, 255, 255, 235),
            )
            _estrela(desenho, (cursor + 42, y_selos_topo + 48), 26,
                     principal + (255,))
            desenho.text((cursor + 74, y_selos_topo + 48), texto_nota,
                         font=fonte_nota, fill=(20, 20, 26, 255), anchor="lm")

    # assinatura
    desenho.text((margem, y_handle), ident["handle"], font=_fonte(ident, 42),
                 fill=texto_cor + (225,), anchor="lm")

    capa = Image.alpha_composite(capa, camada)
    _colar_logo(capa, ident, ident["marca"].get("largura_logo", 200),
                (LARGURA - margem - ident["marca"].get("largura_logo", 200), 132))

    capa.convert("RGB").save(destino, "JPEG", quality=92, optimize=True)
    return destino


def marca_dagua(ident, destino):
    """Gera o PNG transparente da marca d'agua a partir da identidade."""
    conf = ident["marca"]
    tamanho = int(conf.get("tamanho", 44))
    texto = ident["handle"]
    fonte = _fonte(ident, tamanho)

    medida = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
    largura_texto = _largura(medida, texto, fonte)
    respiro_x, respiro_y = int(tamanho * 0.55), int(tamanho * 0.42)

    logo_largura = 0
    if ident.get("logo") and os.path.exists(ident["logo"]):
        logo_largura = int(conf.get("largura_logo", 200) * 0.45) + respiro_x

    largura = largura_texto + logo_largura + respiro_x * 2
    altura = int(tamanho * 1.9)
    imagem = Image.new("RGBA", (largura, altura), (0, 0, 0, 0))
    desenho = ImageDraw.Draw(imagem)

    if conf.get("fundo", True):
        desenho.rounded_rectangle([0, 0, largura - 1, altura - 1],
                                  radius=altura // 2, fill=(0, 0, 0, 90))

    cursor = respiro_x
    if logo_largura:
        tamanho_logo = _colar_logo(imagem, ident, logo_largura - respiro_x,
                                   (cursor, respiro_y // 2))
        if tamanho_logo:
            cursor += tamanho_logo[0] + respiro_x

    alfa = int(255 * float(conf.get("opacidade", 0.85)))
    desenho.text((cursor, altura // 2), texto, font=fonte,
                 fill=ident_mod.rgb(ident["cor_texto"]) + (alfa,), anchor="lm")
    imagem.save(destino, "PNG")
    return destino


def embutir_capa(caminho_video, caminho_capa, destino):
    """Coloca a capa como poster do mp4, para o app ja mostrar a arte certa."""
    resultado = video_mod._rodar([
        "-i", caminho_video, "-i", caminho_capa,
        "-map", "0", "-map", "1", "-c", "copy", "-c:v:1", "mjpeg",
        "-disposition:v:1", "attached_pic", destino,
    ])
    if resultado.returncode != 0 or not os.path.exists(destino):
        raise RuntimeError(f"Nao consegui embutir a capa:\n{resultado.stderr[-800:]}")
    return destino
