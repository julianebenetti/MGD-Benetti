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
import sys
import unicodedata
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import legenda  # noqa: E402
import shopee_api  # noqa: E402
import video as video_mod  # noqa: E402

PASTA_PADRAO = "saida"
ESTADO = ".telegram-estado.json"


def apelido(texto, limite=40):
    base = unicodedata.normalize("NFD", texto.lower())
    base = "".join(c for c in base if unicodedata.category(c) != "Mn")
    base = re.sub(r"[^a-z0-9]+", "-", base).strip("-")
    return base[:limite] or "produto"


def processar(caminho_video, link, opcoes):
    """Roda um video de ponta a ponta e devolve o resumo do que foi gerado."""
    produto, curto, avisos = None, link, []

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

    texto = legenda.montar(produto, curto)

    destino = os.path.join(
        opcoes.saida,
        f"{datetime.now():%Y-%m-%d}_{apelido(produto.get('nome', 'produto'))}",
    )
    os.makedirs(destino, exist_ok=True)

    relatorio_video = video_mod.preparar(
        caminho_video,
        os.path.join(destino, "video.mp4"),
        marca=opcoes.marca,
        texto_marca=opcoes.texto_marca,
        posicao=opcoes.posicao,
        modo=opcoes.modo,
        cortar_fim=opcoes.cortar_fim,
        auto_outro=not opcoes.sem_auto_outro,
    )

    with open(os.path.join(destino, "legenda.txt"), "w") as arq:
        arq.write(texto["texto"] + "\n")

    resumo = {
        "pasta": destino,
        "produto": produto,
        "link_original": link,
        "link_afiliado": curto,
        "legenda": texto,
        "video": relatorio_video,
        "avisos": avisos,
        "falta_fazer_na_mao": [
            f"Favoritar o produto na Shopee: {link}",
            "Subir o video no Shopee Video e salvar como rascunho",
            "Colar a legenda de legenda.txt e anexar o link do produto",
        ],
    }
    with open(os.path.join(destino, "info.json"), "w") as arq:
        json.dump(resumo, arq, indent=2, ensure_ascii=False)
    return resumo


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
    print(f"🔗 {resumo['link_afiliado']}")
    print("-" * 58)
    print(resumo["legenda"]["texto"])
    print("-" * 58)
    repetidas = resumo["legenda"]["conferencia"]
    print("✅ nenhuma palavra repetida" if not repetidas
          else f"❌ repetidas: {repetidas}")
    for aviso in resumo["avisos"]:
        print(f"⚠️  {aviso}")
    print("👉 falta na mao: " + " | ".join(resumo["falta_fazer_na_mao"]))


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--telegram", action="store_true",
                   help="busca os videos novos no grupo do Telegram")
    p.add_argument("--video", help="arquivo de video local")
    p.add_argument("--link", help="link do produto na Shopee")
    p.add_argument("--nome", help="nome do produto, quando a API nao responde")
    p.add_argument("--marca", help="PNG da marca d'agua")
    p.add_argument("--texto-marca", default="@julianebenetti",
                   help="marca d'agua em texto, quando nao ha PNG")
    p.add_argument("--posicao", default="inferior-direito",
                   choices=["inferior-direito", "inferior-esquerdo",
                            "superior-direito", "superior-esquerdo"])
    p.add_argument("--modo", default="desfoque", choices=["desfoque", "cover", "pad"],
                   help="como encaixar em 9:16")
    p.add_argument("--cortar-fim", type=float,
                   help="segundos fixos a cortar do final")
    p.add_argument("--sem-auto-outro", action="store_true",
                   help="nao tentar detectar o cartao final do CapCut")
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
