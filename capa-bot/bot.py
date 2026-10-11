"""Bot do Telegram: recebe vídeo -> sugere headlines -> gera capa estilo Pinterest."""
import logging, os, tempfile, time
from pathlib import Path
import requests
import cover, headlines

TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
API = f"https://api.telegram.org/bot{TOKEN}"
ALLOWED = {int(x) for x in os.environ.get("ALLOWED_CHAT_IDS", "").split(",") if x.strip()}
log = logging.getLogger("capa-bot")
sessions: dict[int, dict] = {}   # chat_id -> {frames, options}


def call(method, **kw):
    r = requests.post(f"{API}/{method}", timeout=70, **kw)
    r.raise_for_status()
    return r.json()["result"]


def say(chat, text, **kw):
    return call("sendMessage", json={"chat_id": chat, "text": text, **kw})


def download(file_id: str, dest: Path) -> bool:
    info = call("getFile", json={"file_id": file_id})
    r = requests.get(f"https://api.telegram.org/file/bot{TOKEN}/{info['file_path']}", timeout=300)
    dest.write_bytes(r.content)
    return True


def on_video(msg):
    chat = msg["chat"]["id"]
    v = msg.get("video") or msg.get("document")
    if v.get("file_size", 0) > 20 * 1024 * 1024:
        return say(chat, "Esse vídeo passa de 20 MB (limite do Telegram para bots). "
                         "Mande uma versão menor/comprimida.")
    say(chat, "Recebi! Lendo o vídeo e criando as headlines... ⏳")
    work = Path(tempfile.mkdtemp(prefix="capa_"))
    video = work / "video.mp4"
    download(v["file_id"], video)
    frames = cover.extract_frames(video)
    opts = headlines.suggest(frames, msg.get("caption", ""))
    sessions[chat] = {"frames": frames, "options": opts}
    kb = [[{"text": o, "callback_data": f"h{i}"}] for i, o in enumerate(opts)]
    kb.append([{"text": "🔄 Outras opções", "callback_data": "more"}])
    say(chat, "Escolha a headline da capa (ou responda com seu próprio texto):",
        reply_markup={"inline_keyboard": kb})


def make_cover(chat, headline):
    s = sessions.get(chat)
    if not s:
        return say(chat, "Me mande um vídeo primeiro 🙂")
    say(chat, f"Gerando a capa com: “{headline}” ⏳ (~1 min)")
    img = cover.compose(cover.generate_background(s["frames"][1]), headline)
    out = s["frames"][0].with_name("capa.png")
    img.save(out)
    with open(out, "rb") as f:
        call("sendDocument", data={"chat_id": chat, "caption": headline}, files={"document": f})


def on_callback(cb):
    chat = cb["message"]["chat"]["id"]
    call("answerCallbackQuery", json={"callback_query_id": cb["id"]})
    s = sessions.get(chat)
    if not s:
        return say(chat, "Me mande um vídeo primeiro 🙂")
    if cb["data"] == "more":
        s["options"] = headlines.suggest(s["frames"])
        kb = [[{"text": o, "callback_data": f"h{i}"}] for i, o in enumerate(s["options"])]
        kb.append([{"text": "🔄 Outras opções", "callback_data": "more"}])
        return say(chat, "Novas opções:", reply_markup={"inline_keyboard": kb})
    make_cover(chat, s["options"][int(cb["data"][1:])])


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
    elif msg.get("text", "").startswith("/start"):
        say(chat, f"Oi! Me mande o vídeo do Reels que eu monto a capa. (seu chat id: {chat})")
    elif msg.get("text"):
        make_cover(chat, msg["text"].strip())   # texto livre = headline própria


def main():
    logging.basicConfig(level=logging.INFO)
    offset = None
    while True:
        try:
            for u in call("getUpdates", json={"offset": offset, "timeout": 50}):
                offset = u["update_id"] + 1
                try:
                    handle(u)
                except Exception:
                    log.exception("erro processando update")
                    c = (u.get("message") or u["callback_query"]["message"])["chat"]["id"]
                    say(c, "Deu erro ao processar 😕 Tente de novo.")
        except requests.RequestException:
            time.sleep(5)


if __name__ == "__main__":
    main()
