"""
Reels -> Stories (Instagram Graph API oficial)

Roda via GitHub Actions. Para cada Reel novo da conta:
  1. Publica o mesmo video como Story
  2. Extrai o link da Shopee da legenda (ou de stories-links.json)
  3. Registra em stories-state.json e no resumo do Action o que falta fazer
     manualmente no celular (a API NAO suporta link sticker nem Destaques):
       - colar o sticker de link
       - tocar em "Destaques"

Variaveis de ambiente:
  IG_ACCESS_TOKEN  token longo da Graph API (obrigatorio)
  IG_USER_ID       ID da conta Instagram Business/Creator (obrigatorio)
  MAX_AGE_HOURS    so posta Reels dos ultimos N horas (padrao 48)
  DRY_RUN          "1" = nao publica, so mostra o que faria
"""
import json, os, re, sys, time, urllib.parse, urllib.request, urllib.error
from datetime import datetime, timezone, timedelta

GRAPH     = "https://graph.facebook.com/v21.0"
TOKEN     = os.environ["IG_ACCESS_TOKEN"]
USER_ID   = os.environ["IG_USER_ID"]
MAX_AGE_H = int(os.environ.get("MAX_AGE_HOURS", "48"))
DRY_RUN   = os.environ.get("DRY_RUN") == "1"

STATE_FILE = "stories-state.json"   # {"baseline_done": bool, "reels": {media_id: {...}}}
LINKS_FILE = "stories-links.json"   # opcional: {media_id: "https://s.shopee.com.br/..."}
LINK_RE    = re.compile(r"https?://(?:s\.shopee\.com\.br|shope\.ee|shopee\.com\.br)/\S+")


def api(method, path, params=None):
    params = dict(params or {}, access_token=TOKEN)
    url = f"{GRAPH}/{path}"
    data = None
    if method == "GET":
        url += "?" + urllib.parse.urlencode(params)
    else:
        data = urllib.parse.urlencode(params).encode()
    req = urllib.request.Request(url, data=data, method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"{e.code} {e.read().decode()[:400]}")


def load(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return default


def save(path, obj):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def fetch_reels():
    res = api("GET", f"{USER_ID}/media", {
        "fields": "id,caption,media_type,media_product_type,media_url,permalink,timestamp",
        "limit": 25,
    })
    return [m for m in res.get("data", []) if m.get("media_product_type") == "REELS"]


def find_link(reel, manual_links):
    if reel["id"] in manual_links:
        return manual_links[reel["id"]]
    m = LINK_RE.search(reel.get("caption") or "")
    return m.group(0).rstrip(".,)") if m else None


def publish_story(video_url):
    container = api("POST", f"{USER_ID}/media", {"media_type": "STORIES", "video_url": video_url})["id"]
    for _ in range(40):  # ate ~6 min
        status = api("GET", container, {"fields": "status_code,status"})
        code = status.get("status_code")
        if code == "FINISHED":
            break
        if code in ("ERROR", "EXPIRED"):
            raise RuntimeError(f"container {code}: {status.get('status')}")
        time.sleep(10)
    else:
        raise RuntimeError("timeout processando o video")
    return api("POST", f"{USER_ID}/media_publish", {"creation_id": container})["id"]


def main():
    state  = load(STATE_FILE, {"baseline_done": False, "reels": {}})
    manual = load(LINKS_FILE, {})
    reels  = fetch_reels()
    now    = datetime.now(timezone.utc)

    # Primeira execucao: marca os Reels existentes como ja vistos (sem postar backlog)
    if not state["baseline_done"]:
        for r in reels:
            state["reels"][r["id"]] = {"status": "baseline", "permalink": r.get("permalink")}
        state["baseline_done"] = True
        save(STATE_FILE, state)
        print(f"Baseline: {len(reels)} reels existentes ignorados. Proximos reels serao postados.")
        return

    summary = []
    for r in sorted(reels, key=lambda x: x["timestamp"]):
        if r["id"] in state["reels"]:
            continue
        ts = datetime.strptime(r["timestamp"], "%Y-%m-%dT%H:%M:%S%z")
        if now - ts > timedelta(hours=MAX_AGE_H):
            state["reels"][r["id"]] = {"status": "ignorado_antigo", "permalink": r.get("permalink")}
            continue
        if not r.get("media_url"):
            print(f"{r['id']}: sem media_url, tentando na proxima rodada")
            continue

        link = find_link(r, manual)
        entry = {"permalink": r.get("permalink"), "link_produto": link, "postado_em": now.isoformat()}
        print(f"Reel {r['id']} ({r.get('permalink')}) link={link}")
        if DRY_RUN:
            continue
        try:
            entry["story_id"] = publish_story(r["media_url"])
            entry["status"] = "story_postado"
            entry["pendente_manual"] = ["link sticker", "destaques"]
            summary.append(f"- {r.get('permalink')} -> link: {link or 'NAO ENCONTRADO na legenda'}")
        except Exception as e:
            entry["status"] = "erro"
            entry["erro"] = str(e)
            print(f"  ERRO: {e}", file=sys.stderr)
        state["reels"][r["id"]] = entry
        save(STATE_FILE, state)

    save(STATE_FILE, state)
    if summary:
        text = "## Stories postados — falta no celular: link sticker + Destaques\n" + "\n".join(summary) + "\n"
        print(text)
        path = os.environ.get("GITHUB_STEP_SUMMARY")
        if path:
            with open(path, "a", encoding="utf-8") as f:
                f.write(text)


if __name__ == "__main__":
    main()
