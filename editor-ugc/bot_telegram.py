#!/usr/bin/env python3
"""
Robô do Telegram que edita os vídeos UGC: você manda (ou encaminha) o vídeo,
ele corta os trechos em que a modelo fica parada e devolve o vídeo pronto.

Configuração (variáveis de ambiente — no VPS ficam em /etc/editor-ugc.env):
  TELEGRAM_BOT_TOKEN   token que o @BotFather deu
  USUARIOS_PERMITIDOS  IDs do Telegram que podem usar o robô, separados por vírgula.
                       Se ficar vazio, o robô só responde com o seu ID (pra você
                       descobrir e colocar aqui) e não edita nada.

Comandos no chat:
  /start            mostra a ajuda
  /limiar 1.5       ajusta o quanto corta (maior = corta mais; padrão 1.0)
  /minparado 0.4    só corta paradas a partir de X segundos (padrão 0.5)

Só usa a biblioteca padrão do Python + ffmpeg.
"""
import json
import os
import queue
import shutil
import sys
import tempfile
import threading
import time
import traceback
import urllib.error
import urllib.parse
import urllib.request
import uuid
from argparse import Namespace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cortar_parados  # noqa: E402

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
PERMITIDOS = {int(x) for x in os.environ.get("USUARIOS_PERMITIDOS", "").replace(" ", "").split(",") if x}
API = f"https://api.telegram.org/bot{TOKEN}"
ARQ_API = f"https://api.telegram.org/file/bot{TOKEN}"
LIMITE_DOWNLOAD = 20 * 1024 * 1024  # limite da API de bots do Telegram
PASTA_CONFIG = Path(os.environ.get("EDITOR_UGC_DADOS", Path.home() / ".editor-ugc"))
ARQ_CONFIG = PASTA_CONFIG / "config_chats.json"

AJUDA = (
    "🎬 *Editor UGC*\n\n"
    "Me manda ou encaminha os vídeos (pode ser vários de uma vez) que eu corto "
    "as partes em que a modelo fica parada e te devolvo pronto pra postar.\n\n"
    "Ajustes:\n"
    "• /limiar 1.5 — maior corta mais (padrão 1.0). Se sobrar parada, aumente; "
    "se cortar movimento, diminua.\n"
    "• /minparado 0.4 — só corta paradas a partir de X segundos (padrão 0.5).\n"
    "• /config — mostra os ajustes atuais."
)

fila = queue.Queue()
trava_config = threading.Lock()


# ---------------------------------------------------------------- Telegram API
def chamar(metodo, timeout=70, **params):
    dados = urllib.parse.urlencode(
        {k: (json.dumps(v) if isinstance(v, (dict, list)) else v) for k, v in params.items()}
    ).encode()
    with urllib.request.urlopen(f"{API}/{metodo}", data=dados, timeout=timeout) as r:
        resp = json.load(r)
    if not resp.get("ok"):
        raise RuntimeError(f"{metodo}: {resp}")
    return resp["result"]


def enviar_texto(chat_id, texto, responder_a=None, markdown=False):
    params = {"chat_id": chat_id, "text": texto}
    if responder_a:
        params["reply_to_message_id"] = responder_a
        params["allow_sending_without_reply"] = True
    if markdown:
        params["parse_mode"] = "Markdown"
    try:
        return chamar("sendMessage", **params)
    except Exception as e:  # mensagem é só aviso; não derruba o robô
        print("erro sendMessage:", e)


def enviar_video(chat_id, caminho, legenda, responder_a=None):
    """Upload multipart feito à mão (sem bibliotecas extras)."""
    fronteira = uuid.uuid4().hex
    campos = {"chat_id": str(chat_id), "caption": legenda, "supports_streaming": "true"}
    if responder_a:
        campos["reply_to_message_id"] = str(responder_a)
        campos["allow_sending_without_reply"] = "true"
    corpo = bytearray()
    for k, v in campos.items():
        corpo += (f"--{fronteira}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n"
                  f"{v}\r\n").encode()
    corpo += (f"--{fronteira}\r\nContent-Disposition: form-data; name=\"video\"; "
              f"filename=\"{caminho.name}\"\r\nContent-Type: video/mp4\r\n\r\n").encode()
    corpo += caminho.read_bytes()
    corpo += f"\r\n--{fronteira}--\r\n".encode()
    req = urllib.request.Request(
        f"{API}/sendVideo", data=bytes(corpo),
        headers={"Content-Type": f"multipart/form-data; boundary={fronteira}"})
    with urllib.request.urlopen(req, timeout=300) as r:
        resp = json.load(r)
    if not resp.get("ok"):
        raise RuntimeError(f"sendVideo: {resp}")


def baixar(file_id, destino):
    info = chamar("getFile", file_id=file_id)
    url = f"{ARQ_API}/{info['file_path']}"
    with urllib.request.urlopen(url, timeout=300) as r, open(destino, "wb") as f:
        shutil.copyfileobj(r, f)


# ---------------------------------------------------------------- ajustes por chat
def ler_config():
    try:
        return json.loads(ARQ_CONFIG.read_text())
    except Exception:
        return {}


def ajustes(chat_id):
    with trava_config:
        c = ler_config().get(str(chat_id), {})
    return {"limiar": c.get("limiar", 1.0), "min_parado": c.get("min_parado", 0.5)}


def salvar_ajuste(chat_id, chave, valor):
    with trava_config:
        c = ler_config()
        c.setdefault(str(chat_id), {})[chave] = valor
        PASTA_CONFIG.mkdir(parents=True, exist_ok=True)
        ARQ_CONFIG.write_text(json.dumps(c, indent=2))


# ---------------------------------------------------------------- processamento
def pegar_video(msg):
    """Retorna (file_id, tamanho, nome) se a mensagem tiver vídeo."""
    if "video" in msg:
        v = msg["video"]
        return v["file_id"], v.get("file_size", 0), v.get("file_name") or f"video_{msg['message_id']}.mp4"
    doc = msg.get("document")
    if doc and (doc.get("mime_type", "").startswith("video/")
                or Path(doc.get("file_name", "")).suffix.lower() in cortar_parados.EXTENSOES):
        return doc["file_id"], doc.get("file_size", 0), doc.get("file_name") or f"video_{msg['message_id']}.mp4"
    return None


def trabalhador():
    while True:
        chat_id, msg_id, file_id, nome = fila.get()
        pasta = Path(tempfile.mkdtemp(prefix="ugc_"))
        try:
            nome_seguro = "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in nome)
            entrada = pasta / (Path(nome_seguro).stem + (Path(nome_seguro).suffix or ".mp4"))
            baixar(file_id, entrada)
            a = ajustes(chat_id)
            args = Namespace(limiar=a["limiar"], min_parado=a["min_parado"], folga=0.1,
                             min_final=3.0, crf=20, analisar=False)
            r = cortar_parados.processar(entrada, pasta, args)
            if r["status"] == "editado":
                legenda = (f"✂️ {r['cortes']} corte(s) — {r['duracao_original']:.1f}s → "
                           f"{r['duracao_final']:.1f}s")
                enviar_video(chat_id, Path(r["saida"]), legenda, responder_a=msg_id)
            elif r["status"] == "sem paradas":
                enviar_texto(chat_id, "✅ Esse não tem parada — pode postar o original.", msg_id)
            elif r["status"] == "pulado (todo parado)":
                enviar_texto(chat_id, "⚠️ Esse vídeo está parado do começo ao fim. Não editei.", msg_id)
            else:
                enviar_texto(chat_id, f"⚠️ Cortando as paradas sobraria só {r['duracao_final']:.1f}s, "
                                      "então não editei. Se quiser, diminua o /limiar.", msg_id)
        except Exception as e:
            traceback.print_exc()
            enviar_texto(chat_id, f"❌ Deu erro nesse vídeo: {str(e)[:200]}", msg_id)
        finally:
            shutil.rmtree(pasta, ignore_errors=True)
            fila.task_done()


def tratar(msg):
    chat_id = msg["chat"]["id"]
    user_id = msg.get("from", {}).get("id")
    if user_id not in PERMITIDOS:
        enviar_texto(chat_id, f"🔒 Robô privado. Seu ID do Telegram é {user_id} — "
                              "coloque em USUARIOS_PERMITIDOS no servidor pra liberar.")
        return

    texto = (msg.get("text") or "").strip()
    if texto.startswith("/"):
        cmd, *resto = texto.split()
        cmd = cmd.split("@")[0].lower()
        if cmd in ("/start", "/ajuda", "/help"):
            enviar_texto(chat_id, AJUDA, markdown=True)
        elif cmd == "/config":
            a = ajustes(chat_id)
            enviar_texto(chat_id, f"limiar = {a['limiar']}\nminparado = {a['min_parado']}s")
        elif cmd in ("/limiar", "/minparado"):
            chave = "limiar" if cmd == "/limiar" else "min_parado"
            try:
                valor = float(resto[0].replace(",", "."))
                assert 0 < valor <= 20
            except Exception:
                enviar_texto(chat_id, f"Use assim: {cmd} 1.5")
                return
            salvar_ajuste(chat_id, chave, valor)
            enviar_texto(chat_id, f"Feito: {cmd[1:]} = {valor}. Vale para os próximos vídeos.")
        else:
            enviar_texto(chat_id, "Não conheço esse comando. Mande /ajuda.")
        return

    v = pegar_video(msg)
    if not v:
        if texto:
            enviar_texto(chat_id, "Me manda um vídeo 🙂 (/ajuda pra ver os comandos)")
        return
    file_id, tamanho, nome = v
    if tamanho and tamanho > LIMITE_DOWNLOAD:
        enviar_texto(chat_id, f"⚠️ Esse vídeo tem {tamanho / 1048576:.0f} MB e o Telegram só deixa "
                              "robôs baixarem até 20 MB.", msg["message_id"])
        return
    fila.put((chat_id, msg["message_id"], file_id, nome))
    if fila.qsize() > 1:
        enviar_texto(chat_id, f"📥 Recebi — {fila.qsize()} na fila.", msg["message_id"])


def main():
    if not TOKEN:
        sys.exit("Defina TELEGRAM_BOT_TOKEN.")
    if not shutil.which("ffmpeg"):
        sys.exit("ffmpeg não encontrado.")
    eu = chamar("getMe")
    print(f"Robô @{eu['username']} rodando. Permitidos: {sorted(PERMITIDOS) or 'ninguém ainda'}")
    threading.Thread(target=trabalhador, daemon=True).start()
    offset = None
    while True:
        try:
            params = {"timeout": 50, "allowed_updates": ["message"]}
            if offset is not None:
                params["offset"] = offset
            for upd in chamar("getUpdates", timeout=70, **params):
                offset = upd["update_id"] + 1
                if "message" in upd:
                    try:
                        tratar(upd["message"])
                    except Exception:
                        traceback.print_exc()
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            print("rede:", e)
            time.sleep(5)
        except Exception:
            traceback.print_exc()
            time.sleep(5)


if __name__ == "__main__":
    main()
