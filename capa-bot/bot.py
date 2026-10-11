"""Bot do Telegram: vídeo (ou fotos) -> sugere texto -> devolve a capa no padrão 'Achei na Shopee'.

Entrada:
  - vídeo: o fundo é um frame do vídeo (botão "Outro frame" troca)
  - fotos (várias na mesma mensagem): a PRIMEIRA é o fundo; as demais são prints da Shopee (contexto)
Para escrever o texto você mesma: mande 3 linhas (faixa / gancho / complemento).
Qualquer outra mensagem de texto vira correção sobre o produto e gera novas sugestões.
"""
import logging, os, tempfile, time
from pathlib import Path
import requests
from PIL import Image
import cover, headlines

TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
API = f"https://api.telegram.org/bot{TOKEN}"
ALLOWED = {int(x) for x in os.environ.get("ALLOWED_CHAT_IDS", "").split(",") if x.strip()}
log = logging.getLogger("capa-bot")
sessions: dict[int, dict] = {}   # chat -> {bg, frames, context, options, caption, work}
pending: dict[int, dict] = {}    # chat -> álbum de fotos sendo recebido


def call(method, **kw):
    r = requests.post(f"{API}/{method}", timeout=70, **kw)
    r.raise_for_status()
    return r.json()["result"]


def say(chat, text, **kw):
    return call("sendMessage", json={"chat_id": chat, "text": text, **kw})


def download(file_id: str, dest: Path):
    info = call("getFile", json={"file_id": file_id})
    dest.write_bytes(requests.get(f"https://api.telegram.org/file/bot{TOKEN}/{info['file_path']}", timeout=300).content)


def keyboard(s, with_frame):
    kb = [[{"text": f"{o['badge']} · {o['linha3']} · {o['linha4']}"[:60], "callback_data": f"h{i}"}]
          for i, o in enumerate(s["options"])]
    row = [{"text": "🔄 Outras opções", "callback_data": "more"}]
    if with_frame:
        row.append({"text": "🖼 Outro frame", "callback_data": "frame"})
    return {"inline_keyboard": kb + [row]}


def offer(chat, with_frame, correcao=""):
    s = sessions[chat]
    data = headlines.suggest(s["images_for_ai"], s.get("caption", ""), correcao)
    s["options"] = data["opcoes"]
    if data.get("inconsistente"):
        say(chat, f"⚠️ As imagens não parecem ser do mesmo produto: {data.get('aviso', '')}\n"
                  "Se quiser, me diga qual é o produto certo que eu ajusto.")
    lines = "\n".join(f"{i + 1}. {o['badge']} → {o['linha3']} / {o['linha4']}" for i, o in enumerate(s["options"]))
    say(chat, f"Produto: {data.get('produto', '?')}\n\n{lines}\n\nEscolha uma opção, ou mande 3 linhas "
              "(faixa / gancho / complemento) com o seu texto.", reply_markup=keyboard(s, with_frame))


def on_video(msg):
    chat = msg["chat"]["id"]
    v = msg.get("video") or msg.get("document")
    if v.get("file_size", 0) > 20 * 1024 * 1024:
        return say(chat, "Esse vídeo passa de 20 MB (limite do Telegram para bots). Mande uma versão menor.")
    say(chat, "Recebi! Lendo o vídeo... ⏳")
    work = Path(tempfile.mkdtemp(prefix="capa_"))
    video = work / "video.mp4"
    download(v["file_id"], video)
    frames = cover.extract_frames(video)
    sessions[chat] = {"work": work, "frames": frames, "frame_i": 1, "bg": frames[1],
                      "images_for_ai": frames[:3], "caption": msg.get("caption", "")}
    offer(chat, with_frame=True)


def flush_album(chat):
    a = pending.pop(chat)
    work = Path(tempfile.mkdtemp(prefix="capa_"))
    paths = []
    for i, fid in enumerate(a["file_ids"]):
        p = work / f"img{i}.jpg"
        download(fid, p)
        paths.append(p)
    sessions[chat] = {"work": work, "bg": paths[0], "images_for_ai": paths, "caption": a["caption"]}
    say(chat, f"Recebi {len(paths)} imagem(ns): a primeira é o fundo. Montando o texto... ⏳")
    offer(chat, with_frame=False)


def on_photo(msg):
    chat = msg["chat"]["id"]
    a = pending.setdefault(chat, {"file_ids": [], "caption": "", "ts": 0})
    a["file_ids"].append(msg["photo"][-1]["file_id"])   # maior resolução
    a["caption"] = a["caption"] or msg.get("caption", "")
    a["ts"] = time.time()


def make_cover(chat, o):
    s = sessions.get(chat)
    if not s:
        return say(chat, "Me mande um vídeo ou as fotos do produto primeiro 🙂")
    img = cover.compose(Image.open(s["bg"]), o["badge"], o["linha3"], o["linha4"])
    out = s["work"] / "capa.png"
    img.save(out)
    with open(out, "rb") as f:
        call("sendDocument", data={"chat_id": chat, "caption": f"{o['badge']} · {o['linha3']} · {o['linha4']}"},
             files={"document": f})


def on_callback(cb):
    chat = cb["message"]["chat"]["id"]
    call("answerCallbackQuery", json={"callback_query_id": cb["id"]})
    s = sessions.get(chat)
    if not s:
        return say(chat, "Me mande um vídeo ou as fotos do produto primeiro 🙂")
    d = cb["data"]
    if d == "more":
        return offer(chat, with_frame="frames" in s)
    if d == "frame":
        s["frame_i"] = (s["frame_i"] + 1) % len(s["frames"])
        s["bg"] = s["frames"][s["frame_i"]]
        return say(chat, f"Fundo trocado para o frame {s['frame_i'] + 1}/{len(s['frames'])}. "
                         "Escolha o texto de novo para gerar.", reply_markup=keyboard(s, True))
    make_cover(chat, s["options"][int(d[1:])])


def on_text(msg):
    chat, text = msg["chat"]["id"], msg["text"].strip()
    if text.startswith("/start"):
        return say(chat, "Oi! Me mande o vídeo do Reels (ou as fotos do produto: a 1ª é o fundo, as outras são "
                         f"prints da Shopee) que eu monto a capa. (seu chat id: {chat})")
    if chat not in sessions:
        return say(chat, "Me mande um vídeo ou as fotos do produto primeiro 🙂")
    parts = [p.strip() for p in text.splitlines() if p.strip()]
    if len(parts) == 3:                                   # texto próprio: faixa / gancho / complemento
        return make_cover(chat, {"badge": parts[0], "linha3": parts[1], "linha4": parts[2]})
    say(chat, "Entendi, ajustando as sugestões... ⏳")      # correção sobre o produto
    offer(chat, with_frame="frames" in sessions[chat], correcao=text)


def handle(u):
    m = u.get("message") or (u.get("callback_query") or {}).get("message")
    chat = m["chat"]["id"]
    if ALLOWED and chat not in ALLOWED:
        return log.warning("chat não autorizado: %s", chat)
    if "callback_query" in u:
        return on_callback(u["callback_query"])
    msg = u["message"]
    if msg.get("video") or (msg.get("document") or {}).get("mime_type", "").startswith("video/"):
        on_video(msg)
    elif msg.get("photo"):
        on_photo(msg)
    elif msg.get("text"):
        on_text(msg)


def main():
    logging.basicConfig(level=logging.INFO)
    offset = None
    while True:
        try:
            for u in call("getUpdates", json={"offset": offset, "timeout": 3}):
                offset = u["update_id"] + 1
                try:
                    handle(u)
                except Exception:
                    log.exception("erro processando update")
                    c = (u.get("message") or u["callback_query"]["message"])["chat"]["id"]
                    say(c, "Deu erro ao processar 😕 Tente de novo.")
            for chat in [c for c, a in pending.items() if time.time() - a["ts"] > 2]:  # álbum completo
                try:
                    flush_album(chat)
                except Exception:
                    log.exception("erro no álbum")
                    pending.pop(chat, None)
                    say(chat, "Deu erro ao processar as fotos 😕 Tente de novo.")
        except requests.RequestException:
            time.sleep(5)


if __name__ == "__main__":
    main()
