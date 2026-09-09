"""
Leitura do grupo do Telegram onde os videos sao postados.

Cada rodada busca as mensagens novas, junta cada video ao link da Shopee
que veio junto (na legenda ou numa mensagem vizinha) e baixa o arquivo.

Precisa de:
  TELEGRAM_BOT_TOKEN  - token do bot criado no @BotFather
  TELEGRAM_GRUPO_ID   - id do grupo (negativo, ex: -1001234567890)

O bot precisa estar no grupo com "privacy mode" desligado, senao o
Telegram nao entrega as mensagens dos outros participantes para ele.
"""
import json
import os
import re
import urllib.parse
import urllib.request

API = "https://api.telegram.org/bot{token}/{metodo}"
ARQUIVO = "https://api.telegram.org/file/bot{token}/{caminho}"
LINK_SHOPEE = re.compile(r"https?://(?:\S*\.)?shopee\.com\.br/\S+|https?://s\.shopee\.com\.br/\S+")
LIMITE_BOT_API = 20 * 1024 * 1024  # o getFile do Bot API para em 20 MB


def _token():
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("Defina TELEGRAM_BOT_TOKEN com o token do @BotFather.")
    return token


def chamar(metodo, **parametros):
    url = API.format(token=_token(), metodo=metodo)
    if parametros:
        url += "?" + urllib.parse.urlencode(parametros)
    with urllib.request.urlopen(url, timeout=60) as resposta:
        dados = json.loads(resposta.read())
    if not dados.get("ok"):
        raise RuntimeError(f"Telegram recusou {metodo}: {dados}")
    return dados["result"]


def ler_estado(caminho):
    if os.path.exists(caminho):
        with open(caminho) as arq:
            return json.load(arq)
    return {"offset": 0, "processados": []}


def salvar_estado(caminho, estado):
    with open(caminho, "w") as arq:
        json.dump(estado, arq, indent=2)


def _video_da_mensagem(msg):
    if msg.get("video"):
        return msg["video"]
    doc = msg.get("document") or {}
    if str(doc.get("mime_type", "")).startswith("video/"):
        return doc
    return None


def _link_da_mensagem(msg):
    texto = f"{msg.get('caption', '')} {msg.get('text', '')}"
    achado = LINK_SHOPEE.search(texto)
    return achado.group(0).rstrip(").,") if achado else None


def coletar(estado, grupo_id=None):
    """
    Devolve a lista de {video, link, message_id} das mensagens novas.

    O link pode vir na legenda do video ou numa mensagem proxima (ate 3
    mensagens antes ou depois), que e como o grupo costuma ser usado.
    """
    grupo = grupo_id or os.environ.get("TELEGRAM_GRUPO_ID")
    atualizacoes = chamar("getUpdates", offset=estado["offset"], timeout=0,
                          allowed_updates=json.dumps(["message", "channel_post"]))
    mensagens = []
    for item in atualizacoes:
        estado["offset"] = max(estado["offset"], item["update_id"] + 1)
        msg = item.get("message") or item.get("channel_post")
        if not msg:
            continue
        if grupo and str(msg.get("chat", {}).get("id")) != str(grupo):
            continue
        mensagens.append(msg)

    pares = []
    for indice, msg in enumerate(mensagens):
        arquivo = _video_da_mensagem(msg)
        if not arquivo:
            continue
        link = _link_da_mensagem(msg)
        if not link:
            vizinhos = mensagens[max(0, indice - 3):indice + 4]
            for vizinho in vizinhos:
                link = link or _link_da_mensagem(vizinho)
        pares.append({
            "message_id": msg["message_id"],
            "file_id": arquivo["file_id"],
            "tamanho": arquivo.get("file_size"),
            "nome": arquivo.get("file_name") or f"video_{msg['message_id']}.mp4",
            "link": link,
        })
    return pares


def baixar(par, destino):
    """Baixa o video do Telegram para `destino`."""
    if par.get("tamanho") and par["tamanho"] > LIMITE_BOT_API:
        raise RuntimeError(
            f"{par['nome']} tem {par['tamanho'] / 1e6:.1f} MB. O Bot API so "
            "baixa ate 20 MB — mande o video comprimido ou use um Bot API local."
        )
    info = chamar("getFile", file_id=par["file_id"])
    url = ARQUIVO.format(token=_token(), caminho=info["file_path"])
    with urllib.request.urlopen(url, timeout=300) as resposta, open(destino, "wb") as saida:
        while True:
            pedaco = resposta.read(1 << 20)
            if not pedaco:
                break
            saida.write(pedaco)
    return destino
