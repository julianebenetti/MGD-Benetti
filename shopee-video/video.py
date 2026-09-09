"""
Tratamento do video antes de subir na Shopee Video.

Substitui o passo manual do CapCut: enquadra em 9:16, corta o cartao final
("Criado com CapCut") e aplica a marca d'agua. Tudo via ffmpeg.
"""
import os
import re
import shutil
import subprocess

LARGURA, ALTURA = 1080, 1920
FONTE_PADRAO = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


def binario():
    """Acha o ffmpeg: variavel de ambiente, PATH ou o que vem no imageio."""
    if os.environ.get("FFMPEG_BIN"):
        return os.environ["FFMPEG_BIN"]
    achado = shutil.which("ffmpeg")
    if achado:
        return achado
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        raise RuntimeError("ffmpeg nao encontrado. Instale com: apt install ffmpeg")


def _rodar(args):
    return subprocess.run(
        [binario(), "-hide_banner", "-y", *args],
        capture_output=True, text=True,
    )


_FILTROS = None


def tem_filtro(nome):
    """Nem todo build de ffmpeg traz drawtext (precisa de libfreetype)."""
    global _FILTROS
    if _FILTROS is None:
        _FILTROS = _rodar(["-filters"]).stdout
    return f" {nome} " in _FILTROS


def inspecionar(caminho):
    """Duracao em segundos e resolucao do arquivo."""
    saida = _rodar(["-i", caminho]).stderr
    duracao = None
    achado = re.search(r"Duration: (\d+):(\d+):(\d+\.\d+)", saida)
    if achado:
        h, m, s = achado.groups()
        duracao = int(h) * 3600 + int(m) * 60 + float(s)
    largura = altura = None
    achado = re.search(r"Video:.*?(\d{2,5})x(\d{2,5})", saida)
    if achado:
        largura, altura = int(achado.group(1)), int(achado.group(2))
    if duracao is None:
        raise RuntimeError(f"Nao consegui ler o video: {caminho}")
    return {"duracao": duracao, "largura": largura, "altura": altura}


def detectar_outro(caminho, duracao, janela=6.0, limiar=0.35):
    """
    Procura o ultimo corte de cena na janela final do video.

    O cartao do CapCut entra como uma troca brusca de imagem nos ultimos
    segundos. O corte de cena mais tardio dentro da janela vira o ponto de
    fim. Devolve None quando nao encontra nada convincente.
    """
    inicio = max(0.0, duracao - janela)
    resultado = _rodar([
        "-ss", f"{inicio:.2f}", "-i", caminho,
        "-vf", f"select='gt(scene,{limiar})',metadata=print",
        "-an", "-f", "null", "-",
    ])
    tempos = [float(t) for t in re.findall(r"pts_time:([\d.]+)", resultado.stderr)]
    candidatos = [inicio + t for t in tempos if 0.15 < t < janela - 0.15]
    if not candidatos:
        return None
    corte = max(candidatos)
    # Um outro de CapCut tem ~2 a 4 s. Fora dessa faixa provavelmente e
    # so um corte do proprio conteudo.
    return corte if 1.0 <= duracao - corte <= 5.0 else None


def _filtro_enquadramento(modo):
    escala_cover = (
        f"scale={LARGURA}:{ALTURA}:force_original_aspect_ratio=increase,"
        f"crop={LARGURA}:{ALTURA}"
    )
    if modo == "cover":
        return escala_cover
    if modo == "pad":
        return (f"scale={LARGURA}:{ALTURA}:force_original_aspect_ratio=decrease,"
                f"pad={LARGURA}:{ALTURA}:(ow-iw)/2:(oh-ih)/2:black")
    # desfoque: mantem o produto inteiro e preenche as bordas
    return (
        f"split[fundo][frente];"
        f"[fundo]{escala_cover},gblur=sigma=28[fundo];"
        f"[frente]scale={LARGURA}:{ALTURA}:force_original_aspect_ratio=decrease[frente];"
        f"[fundo][frente]overlay=(W-w)/2:(H-h)/2"
    )


def _filtro_marca(marca, texto, posicao):
    cantos = {
        "inferior-direito": ("W-w-48", "H-h-220"),
        "inferior-esquerdo": ("48", "H-h-220"),
        "superior-direito": ("W-w-48", "120"),
        "superior-esquerdo": ("48", "120"),
    }
    x, y = cantos.get(posicao, cantos["inferior-direito"])
    if marca and os.path.exists(marca):
        return None, f"[v][marca]overlay={x}:{y}:format=auto"
    if not tem_filtro("drawtext"):
        raise RuntimeError(
            "Este ffmpeg nao tem o filtro drawtext, entao nao da para escrever "
            "a marca d'agua em texto. Passe um PNG em --marca ou instale um "
            "ffmpeg completo (apt install ffmpeg)."
        )
    fonte = os.environ.get("FONTE_MARCA", FONTE_PADRAO)
    escapado = texto.replace(":", "\\:").replace("'", "")
    desenho = (
        f"drawtext=fontfile={fonte}:text='{escapado}':fontcolor=white@0.85:"
        f"fontsize=44:box=1:boxcolor=black@0.28:boxborderw=18:"
        f"x={x.replace('w', 'text_w').replace('W', 'W')}:"
        f"y={y.replace('h', 'text_h').replace('H', 'H')}"
    )
    return desenho, None


def preparar(entrada, saida, marca=None, texto_marca="@julianebenetti",
             posicao="inferior-direito", modo="desfoque",
             cortar_fim=None, auto_outro=True):
    """
    Gera o video pronto para postar.

    cortar_fim: segundos fixos a remover do final. Quando None e auto_outro
    esta ligado, a deteccao de cena decide sozinha; sem deteccao, corta 3 s.
    """
    info = inspecionar(entrada)
    duracao = info["duracao"]

    fim = None
    origem_corte = "nenhum"
    if cortar_fim is not None:
        fim = max(0.5, duracao - float(cortar_fim))
        origem_corte = f"fixo ({cortar_fim}s)"
    elif auto_outro:
        detectado = detectar_outro(entrada, duracao)
        if detectado:
            fim, origem_corte = detectado, "cena detectada"
        else:
            fim, origem_corte = max(0.5, duracao - 3.0), "padrao (3s)"

    enquadra = _filtro_enquadramento(modo)
    desenho, overlay_marca = _filtro_marca(marca, texto_marca, posicao)

    entradas = ["-i", entrada]
    if overlay_marca:
        entradas += ["-i", marca]
        cadeia = f"[0:v]{enquadra}[v];[1:v]scale=260:-1[marca];{overlay_marca}"
    else:
        cadeia = f"[0:v]{enquadra},{desenho}"

    args = [*entradas, "-filter_complex", cadeia]
    if fim:
        args += ["-t", f"{fim:.2f}"]
    args += [
        "-r", "30", "-c:v", "libx264", "-preset", "medium", "-crf", "20",
        "-pix_fmt", "yuv420p", "-profile:v", "high",
        "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", saida,
    ]
    resultado = _rodar(args)
    if resultado.returncode != 0 or not os.path.exists(saida):
        raise RuntimeError(f"ffmpeg falhou:\n{resultado.stderr[-1500:]}")

    return {
        "entrada": entrada,
        "saida": saida,
        "duracao_original": round(duracao, 2),
        "duracao_final": round(inspecionar(saida)["duracao"], 2),
        "corte_final": origem_corte,
        "enquadramento": modo,
        "marca": marca or texto_marca,
    }
