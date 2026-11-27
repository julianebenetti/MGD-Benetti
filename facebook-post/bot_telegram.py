#!/usr/bin/env python3
"""
Bot do Telegram para o robô do Facebook: uma ABA (tópico) por Página.

Você manda uma FOTO com o nome do produto e o link na legenda numa aba; o robô enfileira, posta na Página certa
(foto + link na legenda + link no 1º comentário), respeitando limite por dia, intervalo e horário, e avisa na aba.

Segurança: por padrão o robô NÃO posta de verdade (modo teste). Só posta com BOT_ENVIAR=sim no .env.
Comandos (em qualquer aba): /aqui bbc · /fila · /pausar · /retomar · /limpar sim · /status · /ajuda
"""
import json, os, re, sys, time, urllib.error, urllib.request
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import facebook_post as fp
import shopee_link

AQUI = fp.AQUI
BR = ZoneInfo("America/Sao_Paulo")
URL_RE = re.compile(r"https?://\S+")
ERRO_DE_LIMITE = re.compile(r"too many actions|spam|restrict|request limit|rate limit|2207042|2207051|\(#4\)|\(#17\)|\(#32\)|\(#368\)", re.I)


def agora():
    return datetime.now(BR)


def carregar_config():
    fp.carregar_env()
    e = os.environ.get
    ini, _, fim = e("BOT_JANELA", "8-22").partition("-")
    return {
        "tg_token": e("TG_BOT_TOKEN", ""),
        "tg_chat": int(e("TG_CHAT_ID", "0") or 0),
        "tg_base": e("TG_BASE", "https://api.telegram.org"),
        "usuarios": {int(x) for x in e("TG_USUARIOS", "").split(",") if x.strip().lstrip("-").isdigit()},
        "enviar": e("BOT_ENVIAR", "nao").strip().lower() in ("sim", "1", "true", "yes"),
        "janela": (int(ini or 8), int(fim or 22)),
        "limite_dia": int(e("BOT_LIMITE_DIA", "3")),
        "limite_max": int(e("BOT_LIMITE_MAX", e("BOT_LIMITE_DIA", "3"))),
        "aumento_dia": int(e("BOT_AUMENTO_DIA", "0")),
        "converter": e("BOT_CONVERTER_SHOPEE", "sim").strip().lower() in ("sim", "1", "true", "yes"),
        "intervalo_min": int(e("BOT_INTERVALO_MIN", "120")),
        "max_fila": int(e("BOT_MAX_FILA", "30")),
        "max_tentativas": int(e("BOT_MAX_TENTATIVAS", "3")),
        "pausa_horas": float(e("BOT_PAUSA_HORAS", "6")),
        "dados": Path(e("BOT_DADOS", str(AQUI / "dados.json"))),
        "paginas": Path(e("BOT_PAGINAS", str(AQUI / "paginas.json"))),
        "config": Path(e("BOT_CONFIG", str(AQUI / "config-bot.json"))),
    }


class Bot:
    def __init__(self, cfg):
        self.c = cfg
        self.paginas = fp.ler_json(cfg["paginas"], {})      # chave -> {page_id, nome, token}
        self.extra = fp.ler_json(cfg["config"], {})         # chave -> {nicho, limite_dia, intervalo_min, legenda, comentario}
        self.d = fp.ler_json(cfg["dados"], {"offset": 0, "paginas": {}, "fila": [], "postados": []})

    # ---------- infraestrutura ----------
    def salvar(self):
        tmp = Path(str(self.c["dados"]) + ".tmp")
        tmp.write_text(json.dumps(self.d, ensure_ascii=False, indent=1), encoding="utf-8")
        os.replace(tmp, self.c["dados"])

    def tg(self, metodo, dados=None, espera=60):
        req = urllib.request.Request(
            f"{self.c['tg_base']}/bot{self.c['tg_token']}/{metodo}",
            data=json.dumps(dados or {}).encode(), headers={"Content-Type": "application/json"}, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=espera) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            raise RuntimeError(f"Telegram respondeu {e.code}: {e.read().decode(errors='replace')[:200]}")

    def dizer(self, thread, texto, reply_to=None):
        d = {"chat_id": self.c["tg_chat"], "text": texto, "disable_web_page_preview": True}
        if thread:
            d["message_thread_id"] = thread
        if reply_to:
            d["reply_to_message_id"] = reply_to
            d["allow_sending_without_reply"] = True
        try:
            self.tg("sendMessage", d)
        except Exception as e:
            print("não consegui avisar no Telegram:", e, file=sys.stderr)

    def reagir(self, message_id, emoji):
        """👀 na fila · 👍 postado · 👎 falhou. Sem emoji = tira a reação. Se o Telegram recusar, ignora."""
        if not message_id:
            return
        try:
            self.tg("setMessageReaction", {"chat_id": self.c["tg_chat"], "message_id": message_id,
                                           "reaction": [{"type": "emoji", "emoji": emoji}] if emoji else []})
        except Exception as e:
            print("reação não aplicada:", e, file=sys.stderr)

    def baixar(self, file_id, nome):
        info = self.tg("getFile", {"file_id": file_id})["result"]
        url = f"{self.c['tg_base']}/file/bot{self.c['tg_token']}/{info['file_path']}"
        pasta = AQUI / "imagens"
        pasta.mkdir(exist_ok=True)
        destino = pasta / f"{nome}{Path(info['file_path']).suffix or '.jpg'}"
        with urllib.request.urlopen(url, timeout=180) as r:
            destino.write_bytes(r.read())
        return str(destino)

    # ---------- regras por Página ----------
    def nome(self, chave):
        return self.paginas.get(chave, {}).get("nome", chave)

    def limite(self, chave):
        """Posts por dia. Com BOT_AUMENTO_DIA > 0 o limite sobe devagar (aquecimento) até BOT_LIMITE_MAX."""
        ex = self.extra.get(chave, {})
        base = int(ex.get("limite_dia", self.c["limite_dia"]))
        maximo = int(ex.get("limite_max", self.c["limite_max"]))
        aumento = int(ex.get("aumento_dia", self.c["aumento_dia"]))
        if aumento <= 0 or maximo <= base:
            return base
        inicio = self.d["paginas"].get(chave, {}).get("inicio")
        dias = (agora().date() - date.fromisoformat(inicio)).days if inicio else 0
        return min(maximo, base + aumento * max(0, dias))

    def intervalo(self, chave):
        return int(self.extra.get(chave, {}).get("intervalo_min", self.c["intervalo_min"]))

    def chave_da_aba(self, thread):
        for k, v in self.d["paginas"].items():
            if v.get("topic") == thread and thread:
                return k
        return None

    def pendentes(self, chave):
        return [i for i in self.d["fila"] if i["pagina"] == chave and i["status"] == "pendente"]

    def postados_hoje(self, chave):
        hoje = agora().date()
        return sum(1 for p in self.d["postados"] if p["pagina"] == chave and datetime.fromisoformat(p["quando"]).astimezone(BR).date() == hoje)

    def ultimo_post(self, chave):
        qs = [datetime.fromisoformat(p["quando"]) for p in self.d["postados"] if p["pagina"] == chave]
        return max(qs) if qs else None

    def estimar(self, chave):
        n = agora()
        ult = self.ultimo_post(chave)
        base = max(n, ult.astimezone(BR) + timedelta(minutes=self.intervalo(chave))) if ult else n
        ini, fim = self.c["janela"]
        if self.postados_hoje(chave) >= self.limite(chave) and base.date() == n.date():
            base = (n + timedelta(days=1)).replace(hour=ini, minute=5)
        if base.hour < ini:
            base = base.replace(hour=ini, minute=5)
        elif base.hour >= fim:
            base = (base + timedelta(days=1)).replace(hour=ini, minute=5)
        return ("hoje " if base.date() == n.date() else base.strftime("%d/%m ")) + base.strftime("%H:%M")

    # ---------- mensagens ----------
    def lote(self):
        r = self.tg("getUpdates", {"offset": self.d["offset"], "timeout": 25, "allowed_updates": ["message"]}, espera=40)
        for u in r.get("result", []):
            self.d["offset"] = u["update_id"] + 1
            try:
                self.mensagem(u.get("message"))
            except Exception as e:
                print("erro ao tratar mensagem:", e, file=sys.stderr)
        self.salvar()

    def mensagem(self, m):
        if not m or m.get("chat", {}).get("id") != self.c["tg_chat"]:
            return
        if self.c["usuarios"] and m.get("from", {}).get("id") not in self.c["usuarios"]:
            return
        thread = m.get("message_thread_id")
        texto = (m.get("text") or m.get("caption") or "").strip()
        if texto.startswith("/"):
            return self.comando(thread, texto)
        if m.get("photo"):
            return self.novo_item(thread, m, texto, "foto")
        doc = m.get("document") or {}
        if m.get("video") or str(doc.get("mime_type", "")).startswith("video/"):
            return self.novo_item(thread, m, texto, "video")
        if self.chave_da_aba(thread) and URL_RE.search(texto):
            self.dizer(thread, "📷 Mande a FOTO do produto com o link na legenda.")

    def comando(self, thread, texto):
        cmd, _, arg = texto.partition(" ")
        cmd, arg = cmd.split("@")[0].lower(), arg.strip().lower()
        chave = self.chave_da_aba(thread)
        if cmd == "/aqui":
            if not thread:
                return self.dizer(thread, "Use /aqui dentro de uma ABA (tópico), não no Geral.")
            if arg not in self.paginas:
                return self.dizer(thread, "Qual Página? Use /aqui " + " | ".join(self.paginas) + ".")
            for v in self.d["paginas"].values():
                if v.get("topic") == thread:
                    v["topic"] = None
            self.d["paginas"].setdefault(arg, {})["topic"] = thread
            self.dizer(thread, f"✅ Esta aba agora é da Página {self.nome(arg)}. Mande uma foto com o link na legenda.")
        elif cmd == "/status":
            self.dizer(thread, self.resumo())
        elif cmd == "/postados":
            n = int(arg) if arg.isdigit() else 10
            linhas = self.historico(chave, max(1, min(n, 30)))
            titulo = f"📜 Últimos postados — {self.nome(chave)}" if chave else "📜 Últimos postados — todas as Páginas"
            self.dizer(thread, titulo + "\n" + ("\n".join(linhas) if linhas else "Nada postado ainda."))
        elif cmd in ("/ajuda", "/start", "/help"):
            self.dizer(thread, self.ajuda())
        elif not chave:
            self.dizer(thread, "Esta aba ainda não está ligada a uma Página. Use /aqui " + " | ".join(self.paginas) + ".")
        elif cmd == "/fila":
            pend = self.pendentes(chave)
            linhas = [f"📋 {self.nome(chave)}: {len(pend)} na fila · hoje {self.postados_hoje(chave)}/{self.limite(chave)} · próximo ~{self.estimar(chave)}"]
            linhas += [f"{n}. {i['produto'].splitlines()[0][:60]}" for n, i in enumerate(pend[:10], 1)]
            if self.d["paginas"][chave].get("pausado"):
                linhas.append("⏸️ Página PAUSADA (use /retomar)")
            self.dizer(thread, "\n".join(linhas))
        elif cmd == "/pausar":
            self.d["paginas"][chave]["pausado"] = True
            self.dizer(thread, f"⏸️ {self.nome(chave)} pausada. Nada será postado até /retomar.")
        elif cmd == "/retomar":
            self.d["paginas"][chave]["pausado"] = False
            self.d["paginas"][chave]["pausa_ate"] = 0
            self.d["paginas"][chave]["pausas_seguidas"] = 0
            self.dizer(thread, f"▶️ {self.nome(chave)} retomada.")
        elif cmd == "/limpar":
            if arg != "sim":
                return self.dizer(thread, f"Isso cancela {len(self.pendentes(chave))} item(ns) da fila. Para confirmar: /limpar sim")
            n = 0
            for i in self.pendentes(chave):
                i["status"] = "cancelado"
                self.reagir(i.get("msg_id"), None)
                n += 1
            self.dizer(thread, f"🧹 {n} item(ns) cancelado(s).")
        else:
            self.dizer(thread, self.ajuda())

    def historico(self, chave, n):
        por_id = {i["id"]: i for i in self.d["fila"]}
        regs = sorted((p for p in self.d["postados"] if chave is None or p["pagina"] == chave), key=lambda p: p["quando"], reverse=True)[:n]
        linhas = []
        for p in regs:
            it = por_id.get(p["id"], {})
            quando = datetime.fromisoformat(p["quando"]).astimezone(BR).strftime("%d/%m %H:%M")
            nome = (it.get("produto") or "?").splitlines()[0][:40]
            base = f"{quando} {'🎬' if it.get('tipo') == 'video' else '🖼️'} {nome}" + (f" [{self.nome(p['pagina'])}]" if chave is None else "")
            if p.get("simulado"):
                linhas.append(f"🧪 {base} (teste, não foi ao Facebook)")
                continue
            url = p.get("url") or (f"https://www.facebook.com/{p['post_id']}" if p.get("post_id") else "")
            linhas.append(f"✅ {base}" + (f" · sub-ID {it['subid']}" if it.get("subid") else "") + (f"\n   {url}" if url else "") +
                          ("" if p.get("comentario_ok", True) else "\n   ⚠️ sem o comentário"))
        return linhas

    def ajuda(self):
        return ("🤖 Robô do Facebook\n"
                "• Mande uma FOTO com o nome do produto e o link na legenda.\n"
                "• /fila — o que está esperando nesta aba\n"
                "• /postados — o que já foi pro Facebook (ex.: /postados 20)\n"
                "• 👀 na foto = na fila · 👍 = postado · 👎 = falhou\n"
                "• /pausar e /retomar — controla esta Página\n"
                "• /limpar sim — esvazia a fila desta aba\n"
                "• /status — resumo de todas as Páginas\n"
                "• /aqui " + " | ".join(self.paginas) + " — liga esta aba a uma Página\n"
                + ("" if self.c["enviar"] else "\n🧪 MODO TESTE: nada é postado de verdade."))

    def resumo(self):
        linhas = ["📊 Páginas" + ("" if self.c["enviar"] else " (MODO TESTE)")]
        for k in self.paginas:
            reg = self.d["paginas"].get(k, {})
            estado = "sem aba" if not reg.get("topic") else ("⏸️ pausada" if reg.get("pausado") or reg.get("pausa_ate", 0) > time.time() else "ativa")
            linhas.append(f"• {self.nome(k)}: {estado} · fila {len(self.pendentes(k))} · hoje {self.postados_hoje(k)}/{self.limite(k)}")
        return "\n".join(linhas)

    def novo_item(self, thread, m, texto, tipo="foto"):
        chave = self.chave_da_aba(thread)
        if not chave:
            return self.dizer(thread, "Esta aba ainda não está ligada a uma Página. Use /aqui " + " | ".join(self.paginas) + ".")
        links = URL_RE.findall(texto)
        if not links:
            return self.dizer(thread, "🔗 Falta o link do produto na legenda.")
        original = links[0].rstrip(".,);")
        nome_dado = re.sub(r"\n{3,}", "\n\n", URL_RE.sub("", texto)).strip()
        if any(i["pagina"] == chave and i["status"] in ("pendente", "postado") and i.get("link_original") == original for i in self.d["fila"]):
            return self.dizer(thread, "⚠️ Esse link já foi enviado para esta Página. Não repeti.")
        if len(self.pendentes(chave)) >= self.c["max_fila"]:
            return self.dizer(thread, f"✋ A fila desta Página já tem {self.c['max_fila']} itens. Espere sair alguns ou use /limpar sim.")
        # arquivo do Telegram (foto ou vídeo)
        if tipo == "video":
            arq = m.get("video") or m.get("document") or {}
            if int(arq.get("file_size") or 0) > 20 * 1024 * 1024:
                return self.dizer(thread, "🎬 Esse vídeo passa de 20 MB, o limite do Telegram para bots baixarem. Mande uma versão menor (ou comprimida).")
            file_id = arq.get("file_id")
        else:
            file_id = m["photo"][-1]["file_id"]
        # conversão do link (Shopee) com sub-ID rastreável + nome do produto
        link, produto, avisos, subid, item_id = original, nome_dado, [], "", None
        if self.c["converter"] and shopee_link.eh_shopee(original):
            if not shopee_link.disponivel():
                avisos.append("⚠️ Sem as chaves da Shopee: o link vai do jeito que veio, SEM rastreio.")
            else:
                try:
                    conv = shopee_link.converter(original, chave, nome_dado)
                    link, subid, item_id = conv["link"], conv["subid"], conv["item_id"]
                    if not nome_dado:
                        produto = conv["nome"][:120]
                except Exception as e:
                    avisos.append(f"⚠️ Não consegui converter o link ({e}). Ele vai como veio, SEM rastreio.")
            if item_id and any(i["pagina"] == chave and i["status"] in ("pendente", "postado") and i.get("item_id") == item_id for i in self.d["fila"]):
                return self.dizer(thread, "⚠️ Esse produto já foi enviado para esta Página. Não repeti.")
        if not produto:
            produto = "Achadinho"
            avisos.append("💡 Sem o nome do produto, a legenda sai só como \"Achadinho\". Escreva o nome antes do link.")
        iid = f"{int(time.time())}-{m['message_id']}"
        try:
            caminho = self.baixar(file_id, iid)
        except Exception as e:
            return self.dizer(thread, f"❌ Não consegui baixar o arquivo: {e}")
        self.d["fila"].append({"id": iid, "pagina": chave, "tipo": tipo, "produto": produto, "link": link, "link_original": original,
                               "subid": subid, "item_id": item_id, "imagem": caminho, "status": "pendente", "falhas": 0,
                               "msg_id": m["message_id"], "criado": agora().isoformat(timespec="seconds")})
        self.salvar()
        linhas = [f"📥 Na fila — {self.nome(chave)} ({'vídeo' if tipo == 'video' else 'foto'}): posição {len(self.pendentes(chave))}.",
                  f"Hoje {self.postados_hoje(chave)}/{self.limite(chave)} · próximo post ~{self.estimar(chave)}"]
        if subid:
            linhas.append(f"🔗 Link convertido · sub-ID: {subid}")
        self.dizer(thread, "\n".join(linhas + avisos), reply_to=m["message_id"])
        self.reagir(m["message_id"], "👀")

    # ---------- postagem ----------
    def tick(self):
        n = agora()
        ini, fim = self.c["janela"]
        if not (ini <= n.hour < fim):
            return
        for chave in self.paginas:
            reg = self.d["paginas"].get(chave) or {}
            if not reg.get("topic") or reg.get("pausado") or reg.get("pausa_ate", 0) > time.time():
                continue
            if self.postados_hoje(chave) >= self.limite(chave):
                continue
            ult = self.ultimo_post(chave)
            if ult and n - ult.astimezone(BR) < timedelta(minutes=self.intervalo(chave)):
                continue
            item = next((i for i in self.pendentes(chave) if i.get("proxima", 0) <= time.time()), None)
            if item:
                self.postar(chave, reg, item)

    def postar(self, chave, reg, item):
        topic, pg = reg["topic"], self.paginas[chave]
        reg.setdefault("inicio", agora().date().isoformat())
        resumo = item["produto"].splitlines()[0][:60]
        video = item.get("tipo") == "video"
        if not self.c["enviar"]:
            item["status"] = "postado"
            self.d["postados"].append({"pagina": chave, "id": item["id"], "quando": agora().isoformat(timespec="seconds"), "simulado": True})
            self.salvar()
            return self.dizer(topic, f"🧪 (modo teste) Eu postaria {'o vídeo' if video else 'agora'} na {pg.get('nome', chave)}: {resumo}")
        if not pg.get("token") or pg["token"] == "PENDENTE":
            reg["pausado"] = True
            return self.dizer(topic, f"🔑 Falta o token da Página {pg.get('nome', chave)}; não postei e pausei esta Página. Rode `node obter-tokens-paginas.js` e depois /retomar.")
        c = dict(fp.cfg())
        c.update(page_id=pg["page_id"], token=pg["token"])
        ex = self.extra.get(chave, {})
        if ex.get("legenda"):
            c["legenda"] = ex["legenda"].replace("\\n", "\n")
        if ex.get("comentario"):
            c["comentario"] = ex["comentario"].replace("\\n", "\n")
        legenda, comentario = fp.textos(c, item)
        try:
            if video:
                r = fp.api(c, "POST", f"{pg['page_id']}/videos", {"description": legenda, "published": "true"}, arquivo=item["imagem"])
                post_id = r.get("id")
                url_post = f"https://www.facebook.com/watch/?v={post_id}"
            else:
                r = fp.api(c, "POST", f"{pg['page_id']}/photos", {"caption": legenda, "published": "true"}, arquivo=item["imagem"])
                post_id = r.get("post_id") or r.get("id")
                url_post = f"https://www.facebook.com/{post_id}"
            comentou = False
            for tentativa in range(2 if video else 1):  # vídeo pode demorar a processar: tenta o comentário 2 vezes
                try:
                    time.sleep(int(os.environ.get("FB_ESPERA_VIDEO_SEG", "30")) if video else c["espera_comentario"])
                    fp.api(c, "POST", f"{post_id}/comments", {"message": comentario})
                    comentou = True
                    break
                except Exception as e:
                    print("comentário falhou:", e, file=sys.stderr)
            item["status"] = "postado"
            reg["pausas_seguidas"] = 0
            self.d["postados"].append({"pagina": chave, "id": item["id"], "quando": agora().isoformat(timespec="seconds"),
                                       "post_id": post_id, "url": url_post, "comentario_ok": comentou})
            self.salvar()
            self.dizer(topic, f"✅ {'Vídeo postado' if video else 'Postado'} na {pg.get('nome', chave)}: {resumo}\n{url_post}" +
                              ("" if comentou else "\n⚠️ O post saiu, mas o comentário com o link falhou. Coloque o link à mão."),
                       reply_to=item.get("msg_id"))
            self.reagir(item.get("msg_id"), "👍")
        except Exception as e:
            msg = str(e)
            item["falhas"] = item.get("falhas", 0) + 1
            item["erro"] = msg[:300]
            if ERRO_DE_LIMITE.search(msg):
                reg["pausa_ate"] = time.time() + self.c["pausa_horas"] * 3600
                reg["pausas_seguidas"] = reg.get("pausas_seguidas", 0) + 1
                if reg["pausas_seguidas"] >= 3:
                    reg["pausado"] = True
                    self.dizer(topic, f"🛑 A Meta pediu calma 3 vezes seguidas ({msg[:100]}). Pausei esta Página até você usar /retomar. Confira o status da Página no Facebook antes.")
                else:
                    self.dizer(topic, f"⏸️ A Meta pediu calma ({msg[:120]}). Pausei esta Página por {self.c['pausa_horas']:g} h.")
            elif item["falhas"] >= self.c["max_tentativas"]:
                item["status"] = "falhou"
                self.dizer(topic, f"❌ Desisti de: {resumo}\nMotivo: {msg[:200]}", reply_to=item.get("msg_id"))
                self.reagir(item.get("msg_id"), "👎")
            else:
                item["proxima"] = time.time() + 1800
                self.dizer(topic, f"⚠️ Não consegui postar ({msg[:150]}). Tento de novo em 30 min.")
            self.salvar()


def descobrir_chat(cfg):
    """Mostra os grupos/abas que o bot viu (para achar o TG_CHAT_ID). Não imprime o token."""
    bot = Bot.__new__(Bot)
    bot.c = cfg
    r = bot.tg("getUpdates", {"timeout": 0, "allowed_updates": ["message"]})
    vistos = {}
    for u in r.get("result", []):
        m = u.get("message") or {}
        ch = m.get("chat", {})
        vistos[(ch.get("id"), m.get("message_thread_id"))] = ch.get("title") or ch.get("username") or "(privado)"
    if not vistos:
        print("O bot ainda não viu nenhuma mensagem. Escreva algo no grupo (numa aba) e rode de novo.")
    for (cid, th), nome in vistos.items():
        print(f"Grupo: {nome} · TG_CHAT_ID={cid}" + (f" · aba (tópico) id {th}" if th else ""))


def main():
    cfg = carregar_config()
    if "--descobrir-chat" in sys.argv:
        if not cfg["tg_token"]:
            sys.exit("Falta TG_BOT_TOKEN no arquivo .env.")
        return descobrir_chat(cfg)
    if not cfg["tg_token"] or not cfg["tg_chat"]:
        sys.exit("Faltam TG_BOT_TOKEN e TG_CHAT_ID no arquivo .env (veja o README).")
    if not cfg["paginas"].exists():
        sys.exit("Falta o paginas.json. Rode antes: node obter-tokens-paginas.js")
    bot = Bot(cfg)
    if cfg["enviar"] and any((v.get("token") in (None, "", "PENDENTE")) for v in bot.paginas.values()):
        sys.exit("BOT_ENVIAR=sim, mas há Páginas sem token de verdade no paginas.json. Rode: node obter-tokens-paginas.js")
    print("Bot do Facebook no ar · " + ("ENVIANDO DE VERDADE" if cfg["enviar"] else "MODO TESTE (nada é postado)") + " · Páginas: " + ", ".join(bot.paginas), flush=True)
    while True:
        try:
            bot.lote()
        except Exception as e:
            print("erro ao ler o Telegram:", e, file=sys.stderr, flush=True)
            time.sleep(10)
        try:
            bot.tick()
        except Exception as e:
            print("erro ao postar:", e, file=sys.stderr, flush=True)


if __name__ == "__main__":
    main()
