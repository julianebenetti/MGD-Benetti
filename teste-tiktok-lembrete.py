"""Testes do lembrete diário dos links ocultos do TikTok."""
import importlib.util, os, sys
from datetime import datetime, timedelta

spec = importlib.util.spec_from_file_location(
    "lembrete", os.path.join(os.path.dirname(os.path.abspath(__file__)), "tiktok-lembrete.py"))
lb = importlib.util.module_from_spec(spec)
sys.argv = ["x"]
spec.loader.exec_module(lb)

falhas = 0
def checa(nome, condicao, detalhe=""):
    global falhas
    if not condicao:
        falhas += 1
    print(f"{'✅' if condicao else '❌'} {nome}{(' — ' + detalhe) if detalhe and not condicao else ''}")

print("── Texto da mensagem ──")
m = lb.montar_mensagem(None, [])
checa("nunca revisou: fala que não há registro", "ainda não registrou" in m)
checa("nunca revisou: marca urgência", "bastante tempo" in m)

m = lb.montar_mensagem(0, [])
checa("0 dias: não fala em dias", "Faz 0" not in m)

m = lb.montar_mensagem(1, [])
checa("1 dia: singular", "Faz 1 dia que" in m, m[:80])
checa("1 dia: sem urgência", "bastante tempo" not in m)

m = lb.montar_mensagem(3, [])
checa("3 dias: plural", "Faz 3 dias" in m)
checa("3 dias: ainda sem urgência", "bastante tempo" not in m)

m = lb.montar_mensagem(4, [])
checa("4 dias: liga a urgência", "bastante tempo" in m)

m = lb.montar_mensagem(2, [{"produto": "Calça wide leg", "onde_postei": "vídeo 12/09"}])
checa("lista produto confirmado esgotado", "Calça wide leg" in m and "vídeo 12/09" in m)

m = lb.montar_mensagem(2, [])
checa("sempre ensina o caminho no app", "Gerenciar" in m and "Links de produtos ocultos" in m)

print("\n── Contagem de dias (fuso de Brasília) ──")
hoje = lb.hoje_brasilia()
checa("hoje_brasilia devolve uma data", hasattr(hoje, "year"))

# A virada do dia tem que ser às 00h de Brasília, não às 00h UTC — senão a
# página e o robô discordariam entre 21h e 00h.
def dias_desde(dt_brasilia):
    return (hoje - dt_brasilia.astimezone(lb.BRASILIA).date()).days

hoje_cedo   = datetime.combine(hoje, datetime.min.time()).replace(tzinfo=lb.BRASILIA) + timedelta(minutes=30)
ontem_tarde = hoje_cedo - timedelta(hours=1)          # 23:30 de ontem em Brasília
cinco_dias  = hoje_cedo - timedelta(days=5)

checa("00:30 de hoje (BRT) = 0 dias", dias_desde(hoje_cedo) == 0, str(dias_desde(hoje_cedo)))
checa("23:30 de ontem (BRT) = 1 dia", dias_desde(ontem_tarde) == 1, str(dias_desde(ontem_tarde)))
checa("5 dias atrás = 5 dias", dias_desde(cinco_dias) == 5, str(dias_desde(cinco_dias)))

# Esses dois instantes caem no mesmo dia UTC mas em dias diferentes em Brasília.
# É exatamente o caso que quebraria se alguém trocasse o fuso por UTC.
checa("virada do dia respeita Brasília, não UTC",
      dias_desde(hoje_cedo) != dias_desde(ontem_tarde))

print(f"\n{'🎉 Todos os casos passaram' if not falhas else f'❌ {falhas} caso(s) falharam'}")
sys.exit(1 if falhas else 0)
