#!/usr/bin/env python3
"""
Prepara os posts da Shopee Video.

Pega o video (do grupo do Telegram ou de um arquivo local), enquadra em
9:16, corta o final do CapCut, aplica a marca d'agua, monta a legenda com
5 hashtags e 10 palavras de SEO sem repetir palavra e gera o link de
afiliado. Entrega uma pasta por video, pronta para subir.

Exemplos:
  python3 pipeline.py --telegram --marca marca.png
  python3 pipeline.py --video flow.mp4 --link https://shopee.com.br/...-i.1.2
"""
import argparse
import json
import os
import re
import shutil
import sys
import unicodedata
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import capa as capa_mod  # noqa: E402
import identidade as identidade_mod  # noqa: E402
import legenda  # noqa: E402
import roteiro as roteiro_mod  # noqa: E402
import shopee_api  # noqa: E402
import video as video_mod  # noqa: E402

PASTA_PADRAO = "saida"
ESTADO = ".telegram-estado.json"


def apelido(texto, limite=40):
    base = unicodedata.normalize("NFD", texto.lower())
    base = "".join(c for c in base if unicodedata.category(c) != "Mn")
    base = re.sub(r"[^a-z0-9]+", "-", base).strip("-")
    return base[:limite] or "produto"


def ajustar_identidade(ident, opcoes):
    """Aplica na identidade o que veio pela linha de comando."""
    if opcoes.texto_marca:
        ident["handle"] = opcoes.texto_marca
    if opcoes.posicao:
        ident["marca"]["posicao"] = opcoes.posicao
    if opcoes.modelo_capa:
        ident["capa"]["modelo"] = opcoes.modelo_capa
    if opcoes.selo is not None:
        ident["capa"]["selo"] = opcoes.selo
    if opcoes.logo:
        ident["logo"] = opcoes.logo
    if opcoes.sem_realce:
        ident["video"]["realce"] = False
    return ident


def fazer_capa(caminho_video, origem, destino, produto, ident, opcoes,
               limite_duracao=None):
    """
    Escolhe o quadro, monta a capa e embute como poster do mp4.

    O quadro sai do video de origem, nao do tratado, para a marca d'agua
    nao aparecer duas vezes na arte.
    """
    pasta_quadros = os.path.join(destino, "_quadros")
    os.makedirs(pasta_quadros, exist_ok=True)

    if opcoes.capa_em is not None:
        quadro = os.path.join(pasta_quadros, "escolhido.png")
        video_mod._rodar(["-ss", f"{opcoes.capa_em:.2f}", "-i", origem,
                          "-frames:v", "1", "-q:v", "2", quadro])
        if not os.path.exists(quadro):
            raise RuntimeError(f"Nao ha quadro em {opcoes.capa_em}s.")
        escolhido = {"arquivo": quadro, "momento": opcoes.capa_em, "nota": None}
    else:
        escolhido = capa_mod.escolher_quadro(origem, pasta_quadros,
                                            limite_duracao=limite_duracao)

    caminho_capa = capa_mod.montar_capa(
        escolhido["arquivo"], os.path.join(destino, "capa.jpg"), produto, ident
    )

    embutida = True
    try:
        temporario = os.path.join(destino, "_com_capa.mp4")
        capa_mod.embutir_capa(caminho_video, caminho_capa, temporario)
        os.replace(temporario, caminho_video)
    except Exception:
        embutida = False

    shutil.rmtree(pasta_quadros, ignore_errors=True)
    return {
        "arquivo": caminho_capa,
        "momento": round(escolhido["momento"], 2),
        "escolha": "manual" if opcoes.capa_em is not None else "automatica",
        "modelo": ident["capa"]["modelo"],
        "embutida_no_mp4": embutida,
    }


def processar(caminho_video, link, opcoes):
    """Roda um video de ponta a ponta e devolve o resumo do que foi gerado."""
    produto, curto, avisos = None, link, []
    ident = ajustar_identidade(identidade_mod.carregar(opcoes.identidade), opcoes)

    try:
        produto = shopee_api.buscar_produto(link)
    except Exception as erro:
        avisos.append(f"Nao consegui ler os dados do produto: {erro}")

    if produto is None and opcoes.nome:
        produto = {"nome": opcoes.nome}
    if produto is None:
        raise RuntimeError(
            "Sem dados do produto. Passe --nome \"Nome do produto\" ou confira "
            "as credenciais SHOPEE_APP_ID / SHOPEE_SECRET."
        )

    if produto.get("comissao_reais") is not None and produto["comissao_reais"] < 9:
        avisos.append(
            f"Comissao de R$ {produto['comissao_reais']:.2f} — abaixo do piso "
            "de R$ 9,00 que voce usa no garimpo."
        )

    try:
        curto = shopee_api.link_afiliado(link, [opcoes.sub_id])
    except Exception as erro:
        avisos.append(f"Nao consegui encurtar o link de afiliado: {erro}")

    # duas versoes: a do Shopee Video, onde o produto entra pela etiqueta,
    # e a com link colado, que serve para TikTok e Instagram.
    texto = legenda.montar(produto, curto, com_link=False)
    texto_com_link = legenda.montar(produto, curto, com_link=True)

    destino = os.path.join(
        opcoes.saida,
        f"{datetime.now():%Y-%m-%d}_{apelido(produto.get('nome', 'produto'))}",
    )
    os.makedirs(destino, exist_ok=True)

    # marca d'agua: PNG da Juliane ou um gerado agora a partir da identidade
    if opcoes.marca:
        marca_png, largura_marca = opcoes.marca, opcoes.largura_marca or 300
    else:
        marca_png = capa_mod.marca_dagua(ident, os.path.join(destino, "marca.png"))
        largura_marca = opcoes.largura_marca

    caminho_final = os.path.join(destino, "video.mp4")
    relatorio_video = video_mod.preparar(
        caminho_video,
        caminho_final,
        marca=marca_png,
        texto_marca=ident["handle"],
        posicao=ident["marca"]["posicao"],
        modo=opcoes.modo,
        cortar_fim=opcoes.cortar_fim,
        auto_outro=not opcoes.sem_auto_outro,
        realce=ident["video"],
        largura_marca=largura_marca,
    )

    relatorio_capa = None
    if not opcoes.sem_capa:
        try:
            relatorio_capa = fazer_capa(
                caminho_final, caminho_video, destino, produto, ident, opcoes,
                limite_duracao=relatorio_video["duracao_final"],
            )
        except Exception as erro:
            avisos.append(f"Nao consegui montar a capa: {erro}")

    conferencia = video_mod.conferir(caminho_final, ident["specs"])
    avisos.extend(f"Conferencia do video: {p}" for p in conferencia["problemas"])

    with open(os.path.join(destino, "legenda-shopee-video.txt"), "w") as arq:
        arq.write(texto["texto"] + "\n")
    with open(os.path.join(destino, "legenda.txt"), "w") as arq:
        arq.write(texto_com_link["texto"] + "\n")

    resumo = {
        "pasta": destino,
        "produto": produto,
        "link_original": link,
        "link_afiliado": curto,
        "legenda": texto,
        "legenda_com_link": texto_com_link,
        "video": relatorio_video,
        "capa": relatorio_capa,
        "conferencia_video": conferencia,
        "identidade": {
            "handle": ident["handle"],
            "cor_principal": ident["cor_principal"],
            "modelo_capa": ident["capa"]["modelo"],
        },
        "avisos": avisos,
    }
    if opcoes.entregar_telegram:
        try:
            import telegram_grupo

            telegram_grupo.enviar_video(caminho_final, texto["texto"])
            resumo["entregue_no_telegram"] = True
        except Exception as erro:
            avisos.append(f"Nao consegui devolver o video no Telegram: {erro}")

    guia = roteiro_mod.montar(resumo)
    resumo["roteiro"] = guia["passos"]
    resumo["termo_busca"] = guia["termo_busca"]
    with open(os.path.join(destino, "roteiro.txt"), "w") as arq:
        arq.write(guia["texto"])

    with open(os.path.join(destino, "info.json"), "w") as arq:
        json.dump(resumo, arq, indent=2, ensure_ascii=False)
    indexar(resumo, opcoes.saida)
    return resumo


APP = "app-postagens.html"


def publicar_app(pasta_saida):
    """Deixa o app de postagens ao lado do posts.json, para abrir no celular."""
    origem = os.path.join(os.path.dirname(os.path.abspath(__file__)), APP)
    if os.path.exists(origem):
        shutil.copy2(origem, os.path.join(pasta_saida, APP))


def indexar(resumo, pasta_saida):
    """Mantem posts.json, que e o que o app de postagens le."""
    publicar_app(pasta_saida)
    caminho = os.path.join(pasta_saida, "posts.json")
    posts = []
    if os.path.exists(caminho):
        try:
            with open(caminho, encoding="utf-8") as arq:
                posts = json.load(arq)
        except (ValueError, OSError):
            posts = []

    pasta = os.path.basename(resumo["pasta"])
    produto = resumo.get("produto") or {}
    registro = {
        "id": pasta,
        "criado_em": datetime.now().isoformat(timespec="seconds"),
        "pasta": pasta,
        "produto": {
            "nome": produto.get("nome"),
            "loja": produto.get("loja"),
            "preco": produto.get("preco"),
            "nota": produto.get("nota"),
            "comissao_reais": produto.get("comissao_reais"),
        },
        "termo_busca": resumo.get("termo_busca"),
        "link_original": resumo.get("link_original"),
        "link_afiliado": resumo.get("link_afiliado"),
        "video": f"{pasta}/video.mp4",
        "capa": f"{pasta}/capa.jpg" if resumo.get("capa") else None,
        "legenda": resumo["legenda"]["texto"],
        "legenda_com_link": resumo["legenda_com_link"]["texto"],
        "roteiro": resumo.get("roteiro", []),
        "avisos": resumo.get("avisos", []),
    }
    posts = [p for p in posts if p.get("id") != registro["id"]]
    posts.insert(0, registro)
    with open(caminho, "w", encoding="utf-8") as arq:
        json.dump(posts, arq, indent=2, ensure_ascii=False)
    return caminho


def do_telegram(opcoes):
    import telegram_grupo

    estado_arq = os.path.join(opcoes.saida, ESTADO)
    os.makedirs(opcoes.saida, exist_ok=True)
    estado = telegram_grupo.ler_estado(estado_arq)
    pares = telegram_grupo.coletar(estado)

    pendentes = [p for p in pares if p["message_id"] not in estado["processados"]]
    if opcoes.limite:
        pendentes = pendentes[: opcoes.limite]

    resumos = []
    brutos = os.path.join(opcoes.saida, "_brutos")
    os.makedirs(brutos, exist_ok=True)
    for par in pendentes:
        if not par["link"]:
            print(f"⚠️  Video {par['nome']} veio sem link da Shopee — pulei.")
            continue
        try:
            bruto = telegram_grupo.baixar(par, os.path.join(brutos, par["nome"]))
            resumos.append(processar(bruto, par["link"], opcoes))
            estado["processados"].append(par["message_id"])
        except Exception as erro:
            print(f"⚠️  {par['nome']}: {erro}")
    telegram_grupo.salvar_estado(estado_arq, estado)
    return resumos


def imprimir(resumo):
    print("\n" + "=" * 58)
    print(f"📁 {resumo['pasta']}")
    print(f"🛍️  {resumo['produto'].get('nome', '?')}")
    comissao = resumo["produto"].get("comissao_reais")
    if comissao is not None:
        print(f"💰 comissao R$ {comissao:.2f} ({resumo['produto'].get('comissao_pct')}%)")
    print(f"🎬 {resumo['video']['duracao_original']}s → "
          f"{resumo['video']['duracao_final']}s (corte: {resumo['video']['corte_final']})")
    conferencia = resumo["conferencia_video"]["info"]
    print(f"📐 {conferencia['largura']}x{conferencia['altura']} · "
          f"{conferencia['tamanho_mb']} MB · "
          f"marca d'agua {resumo['video']['marca']}")
    if resumo.get("capa"):
        print(f"🖼️  capa {resumo['capa']['modelo']} do segundo "
              f"{resumo['capa']['momento']} ({resumo['capa']['escolha']})")
    print(f"🔗 {resumo['link_afiliado']}")
    print("-" * 58)
    print(resumo["legenda"]["texto"])
    print("-" * 58)
    repetidas = resumo["legenda"]["conferencia"]
    print("✅ nenhuma palavra repetida" if not repetidas
          else f"❌ repetidas: {repetidas}")
    for aviso in resumo["avisos"]:
        print(f"⚠️  {aviso}")
    print("👉 no app: " + " → ".join(
        p["titulo"] for p in resumo.get("roteiro", []) if p["etapa"] == "app"
    ))
    print(f"   roteiro completo em {resumo['pasta']}/roteiro.txt")


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--telegram", action="store_true",
                   help="busca os videos novos no grupo do Telegram")
    p.add_argument("--video", help="arquivo de video local")
    p.add_argument("--link", help="link do produto na Shopee")
    p.add_argument("--nome", help="nome do produto, quando a API nao responde")
    p.add_argument("--identidade", help="outro identidade.json")
    p.add_argument("--marca", help="PNG da marca d'agua, no lugar do gerado")
    p.add_argument("--largura-marca", type=int,
                   help="largura da marca d'agua em px")
    p.add_argument("--logo", help="PNG do logo usado na capa e na marca")
    p.add_argument("--sem-capa", action="store_true", help="nao gerar capa")
    p.add_argument("--modelo-capa", choices=["faixa", "minimo", "cartao"],
                   help="layout da capa")
    p.add_argument("--selo", help='texto do selo da capa, "" tira o selo')
    p.add_argument("--capa-em", type=float,
                   help="segundo do video a usar como capa, em vez da escolha automatica")
    p.add_argument("--sem-realce", action="store_true",
                   help="nao ajustar contraste, saturacao e volume")
    p.add_argument("--texto-marca", help="sobrescreve o @ da identidade")
    p.add_argument("--posicao",
                   choices=["inferior-direito", "inferior-esquerdo",
                            "superior-direito", "superior-esquerdo"])
    p.add_argument("--modo", default="desfoque", choices=["desfoque", "cover", "pad"],
                   help="como encaixar em 9:16")
    p.add_argument("--cortar-fim", type=float,
                   help="segundos fixos a cortar do final")
    p.add_argument("--sem-auto-outro", action="store_true",
                   help="nao tentar detectar o cartao final do CapCut")
    p.add_argument("--entregar-telegram", action="store_true",
                   help="devolve o video tratado e a legenda no chat do Telegram")
    p.add_argument("--sub-id", default="shopee_video",
                   help="sub_id de rastreio do link")
    p.add_argument("--limite", type=int, help="maximo de videos por rodada")
    p.add_argument("--saida", default=PASTA_PADRAO)
    opcoes = p.parse_args()

    if opcoes.telegram:
        resumos = do_telegram(opcoes)
    elif opcoes.video and opcoes.link:
        resumos = [processar(opcoes.video, opcoes.link, opcoes)]
    else:
        p.error("use --telegram ou --video junto com --link")

    for resumo in resumos:
        imprimir(resumo)
    if not resumos:
        print("Nada novo para processar.")


if __name__ == "__main__":
    main()
