#!/usr/bin/env python3
"""
Robô de postagem na Página do Facebook (Graph API oficial).

Para cada produto da fila:
  1. publica a FOTO na Página, com o link do produto na legenda;
  2. escreve o link do produto no 1º COMENTÁRIO do post.

Segurança: por padrão NADA é enviado (modo teste, mostra o que faria).
Só posta de verdade com --enviar. O token fica no .env, nunca no código.

Uso:
  python3 facebook_post.py --testar-token          # confere o acesso à Página (não posta)
  python3 facebook_post.py                         # mostra o que postaria (não envia)
  python3 facebook_post.py --enviar                # posta o próximo produto da fila
  python3 facebook_post.py --enviar --quantos 2    # posta os 2 próximos
"""
import argparse, json, mimetypes, os, random, sys, time, urllib.error, urllib.parse, urllib.request, uuid
from datetime import datetime
from pathlib import Path

AQUI = Path(__file__).resolve().parent


def carregar_env():
    f = AQUI / ".env"
    if not f.exists():
        return
    for linha in f.read_text(encoding="utf-8").splitlines():
        linha = linha.strip()
        if linha and not linha.startswith("#") and "=" in linha:
            k, v = linha.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def cfg():
    return {
        "page_id": os.environ.get("FB_PAGE_ID", ""),
        "token": os.environ.get("FB_PAGE_TOKEN", ""),
        "versao": os.environ.get("FB_GRAPH_VERSION", "v24.0"),
        "base": os.environ.get("FB_GRAPH_BASE", "https://graph.facebook.com"),
        "limite_dia": int(os.environ.get("FB_LIMITE_DIA", "3")),
        "espera_comentario": int(os.environ.get("FB_ESPERA_COMENTARIO_SEG", "20")),
        "legenda": os.environ.get("FB_MODELO_LEGENDA",
                                  "{produto}\\n\\n🛒 Compre aqui: {link}\\n\\n⚠️ Link de afiliado. Preço e estoque podem mudar.").replace("\\n", "\n"),
        "comentario": os.environ.get("FB_MODELO_COMENTARIO", "🛒 Compre aqui: {link}").replace("\\n", "\n"),
    }


def api(c, metodo, caminho, campos=None, arquivo=None):
    """Chama a Graph API. O token vai no corpo/parâmetros, nunca é impresso."""
    campos = dict(campos or {}, access_token=c["token"])
    url = f"{c['base']}/{c['versao']}/{caminho}"
    if metodo == "GET":
        req = urllib.request.Request(url + "?" + urllib.parse.urlencode(campos))
    elif arquivo:
        limite = "----fb" + uuid.uuid4().hex
        partes = []
        for k, v in campos.items():
            partes.append(f'--{limite}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode())
        nome = Path(arquivo).name
        tipo = mimetypes.guess_type(nome)[0] or "application/octet-stream"
        partes.append(f'--{limite}\r\nContent-Disposition: form-data; name="source"; filename="{nome}"\r\n'
                      f'Content-Type: {tipo}\r\n\r\n'.encode() + Path(arquivo).read_bytes() + b"\r\n")
        partes.append(f"--{limite}--\r\n".encode())
        req = urllib.request.Request(url, data=b"".join(partes), method="POST",
                                     headers={"Content-Type": f"multipart/form-data; boundary={limite}"})
    else:
        req = urllib.request.Request(url, data=urllib.parse.urlencode(campos).encode(), method="POST")
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"Meta respondeu {e.code}: {e.read().decode(errors='replace')[:500]}")


def ler_json(caminho, padrao):
    try:
        return json.loads(Path(caminho).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return padrao


def salvar_json(caminho, obj):
    Path(caminho).write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def textos(c, item):
    legenda = item.get("legenda") or c["legenda"].format(produto=item["produto"], link=item["link"])
    if item["link"] not in legenda:
        legenda += f"\n\n🛒 {item['link']}"
    comentario = item.get("comentario") or c["comentario"].format(produto=item["produto"], link=item["link"])
    return legenda, comentario


def postar(c, item, enviar):
    legenda, comentario = textos(c, item)
    img = item["imagem"]
    print(f"\n— {item['produto']}")
    print(f"  imagem: {img}\n  legenda:\n    " + legenda.replace("\n", "\n    "))
    print("  1º comentário: " + comentario)
    if not enviar:
        print("  (modo teste: nada foi enviado)")
        return None
    campos = {"caption": legenda, "published": "true"}
    if img.startswith("http"):
        campos["url"] = img
        r = api(c, "POST", f"{c['page_id']}/photos", campos)
    else:
        if not Path(img).is_absolute():
            img = str(AQUI / img)
        r = api(c, "POST", f"{c['page_id']}/photos", campos, arquivo=img)
    post_id = r.get("post_id") or r.get("id")
    comentou = False
    try:
        time.sleep(c["espera_comentario"])
        api(c, "POST", f"{post_id}/comments", {"message": comentario})
        comentou = True
    except RuntimeError as e:
        print(f"  ⚠️ postou, mas o comentário falhou: {e}")
    print(f"  ✅ postado (id {post_id}){'' if comentou else ' SEM o comentário'}")
    return {"post_id": post_id, "comentario_ok": comentou}


def main():
    carregar_env()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--enviar", action="store_true", help="posta de verdade (sem isso é só teste)")
    ap.add_argument("--testar-token", action="store_true", help="confere o acesso à Página e sai")
    ap.add_argument("--quantos", type=int, default=1, help="quantos produtos da fila postar nesta execução")
    ap.add_argument("--fila", default=str(AQUI / "fila.json"))
    ap.add_argument("--estado", default=str(AQUI / "estado.json"))
    a = ap.parse_args()
    c = cfg()

    if a.testar_token or a.enviar:
        if not c["page_id"] or not c["token"]:
            sys.exit("Faltam FB_PAGE_ID e FB_PAGE_TOKEN no arquivo .env (veja o README).")
    if a.testar_token:
        r = api(c, "GET", c["page_id"], {"fields": "id,name"})
        print(f"✅ Acesso OK à Página: {r.get('name')} ({r.get('id')})")
        return

    fila = ler_json(a.fila, [])
    estado = ler_json(a.estado, {"postados": []})
    feitos = {p["id"] for p in estado["postados"]}
    hoje = datetime.now().strftime("%Y-%m-%d")
    hoje_n = sum(1 for p in estado["postados"] if p["quando"].startswith(hoje))
    pend = [i for i in fila if i["id"] not in feitos]
    vagas = max(0, c["limite_dia"] - hoje_n)
    print(f"Fila: {len(pend)} pendente(s) · hoje já postou {hoje_n} de {c['limite_dia']} permitidos")
    if a.enviar and vagas == 0:
        sys.exit("Limite diário atingido. Volte amanhã (ou aumente FB_LIMITE_DIA com cuidado).")

    n = min(a.quantos, vagas) if a.enviar else a.quantos
    for k, item in enumerate(pend[:n]):
        if k:
            time.sleep(random.randint(30, 90))
        r = postar(c, item, a.enviar)
        if r:
            estado["postados"].append({"id": item["id"], "produto": item["produto"],
                                       "quando": datetime.now().isoformat(timespec="seconds"), **r})
            salvar_json(a.estado, estado)


if __name__ == "__main__":
    main()
