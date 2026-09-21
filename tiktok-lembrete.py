"""
Lembrete diário — Links de produtos ocultos do TikTok
=====================================================

O TikTok já detecta sozinho quando um produto vinculado a um vídeo esgota ou é
removido; ele só não avisa. Esse lembrete cutuca a Juliane todo dia pra ela
abrir o painel e trocar os produtos dos vídeos afetados.

Caminho no app:
  TikTok → Vídeos → Gerenciar → filtro "Links de produtos ocultos" → Vincular

Não é um lembrete burro: ele lê a tabela `tiktok_revisoes` e fica calado se a
revisão de hoje já foi feita. Assim a mensagem não vira paisagem.

Uso:
  python3 tiktok-lembrete.py            # manda se ainda não revisou hoje
  python3 tiktok-lembrete.py --forcar   # manda de qualquer jeito
  python3 tiktok-lembrete.py --teste    # só mostra o texto, não envia
"""

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://tkxkrbdvcctoajuigvvv.supabase.co")
SUPABASE_KEY = os.environ.get(
    "SUPABASE_KEY",
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InRreGtyYmR2Y2N0b2FqdWlndnZ2Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODM4NzY2NzUsImV4cCI6MjA5OTQ1MjY3NX0.-szTE2wYYr9DNTLiff6zmLpbP6UOL1l9SFpvc-29Njs",
)
TELEGRAM_TOKEN   = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
# URL da página no VPS, pra ela marcar a revisão com um toque. Opcional.
PAGINA_URL       = os.environ.get("PAGINA_VALIDADOR_URL", "")

BRASILIA = timezone(timedelta(hours=-3))


def hoje_brasilia():
    return datetime.now(BRASILIA).date()


def sb_get(path):
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/{path}",
        headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        txt = r.read().decode()
        return json.loads(txt) if txt.strip() else []


def telegram(texto):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("⚠ TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID não configurados — nada enviado.")
        return False
    body = urllib.parse.urlencode({
        "chat_id": TELEGRAM_CHAT_ID,
        "text": texto,
        "parse_mode": "HTML",
        "disable_web_page_preview": "true",
    }).encode()
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        with urllib.request.urlopen(urllib.request.Request(url, data=body), timeout=20) as r:
            return json.loads(r.read()).get("ok", False)
    except Exception as e:
        print(f"❌ Falha ao enviar no Telegram: {e}")
        return False


def ultima_revisao():
    linhas = sb_get("tiktok_revisoes?select=revisado_em,videos_corrigidos"
                    "&order=revisado_em.desc&limit=1")
    if not linhas:
        return None
    return datetime.fromisoformat(linhas[0]["revisado_em"].replace("Z", "+00:00"))


def produtos_com_problema():
    """Reforço: produtos que o robô da página pública já confirmou como esgotados.
    Se o robô estiver desligado a lista simplesmente vem vazia."""
    try:
        return sb_get("tiktok_estoque_monitor?select=produto,status,onde_postei"
                      "&ativo=eq.true&confirmacoes=gte.2"
                      "&status=in.(esgotado,removido)&limit=10")
    except Exception:
        return []


def montar_mensagem(dias, extras):
    if dias is None:
        abertura = "Você ainda não registrou nenhuma revisão dos links do TikTok."
    elif dias == 0:
        # Só acontece com --forcar; sem isso o script nem envia.
        abertura = "Você já revisou os links hoje — esse é um lembrete extra."
    elif dias == 1:
        abertura = "Faz 1 dia que você não confere os links ocultos."
    else:
        abertura = f"Faz {dias} dias que você não confere os links ocultos."

    urgencia = "\n⚠️ <b>Já faz bastante tempo</b> — provavelmente tem vídeo no ar com link morto.\n" \
               if (dias is None or dias >= 4) else ""

    msg = (f"🔗 <b>Links do TikTok</b>\n\n{abertura}\n{urgencia}\n"
           "📲 <b>Caminho:</b>\n"
           "TikTok → <b>Vídeos</b> (ícone da estrelinha) → <b>Gerenciar</b>\n"
           "→ filtro <b>“Links de produtos ocultos”</b>\n"
           "→ nos vídeos com aviso vermelho, toque em <b>Vincular</b> e troque o produto.\n\n"
           "Leva uns 2 minutos e evita vídeo no ar mandando gente pra link que não vende.")

    if extras:
        nomes = "\n".join(
            f"• {e['produto']}" + (f" — {e['onde_postei']}" if e.get("onde_postei") else "")
            for e in extras
        )
        msg += f"\n\n🔴 <b>O validador também já confirmou esgotado:</b>\n{nomes}"

    if PAGINA_URL:
        msg += f"\n\n✅ Depois de revisar, marque aqui: {PAGINA_URL}"
    else:
        msg += "\n\n✅ Depois de revisar, marque a revisão na página do validador."
    return msg


def main():
    ap = argparse.ArgumentParser(description="Lembrete diário dos links ocultos do TikTok")
    ap.add_argument("--forcar", action="store_true", help="envia mesmo se já revisou hoje")
    ap.add_argument("--teste", action="store_true", help="mostra o texto e não envia")
    args = ap.parse_args()

    try:
        ultima = ultima_revisao()
    except Exception as e:
        print(f"❌ Não consegui ler o Supabase: {e}")
        return 1

    hoje = hoje_brasilia()
    if ultima:
        dias = (hoje - ultima.astimezone(BRASILIA).date()).days
        print(f"Última revisão: {ultima.astimezone(BRASILIA):%d/%m/%Y %H:%M} ({dias} dia(s) atrás)")
    else:
        dias = None
        print("Nenhuma revisão registrada ainda.")

    if dias == 0 and not args.forcar:
        print("✅ Já revisou hoje — não vou incomodar.")
        return 0

    msg = montar_mensagem(dias, produtos_com_problema())
    if args.teste:
        print("\n── Mensagem que seria enviada ──\n")
        print(msg)
        return 0

    print("📲 Enviado." if telegram(msg) else "❌ Não consegui enviar.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
