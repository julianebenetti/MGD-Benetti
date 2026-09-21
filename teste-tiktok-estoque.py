"""Testes offline do analisador do validador de estoque do TikTok Shop."""
import importlib.util, os, sys, json

spec = importlib.util.spec_from_file_location("tts", os.path.join(os.path.dirname(os.path.abspath(__file__)), "tiktok-estoque-sync.py"))
tts = importlib.util.module_from_spec(spec)
sys.argv = ["x"]
spec.loader.exec_module(tts)

PID = "1729419574822508544"
CANON = f"https://shop.tiktok.com/view/product/{PID}"

def pagina(corpo, script=""):
    return f"""<!DOCTYPE html><html><head><title>Produto</title>
<script>{script}</script></head><body><div id="root">{corpo}</div>
<p>Frete gratis acima de R$79. Entrega em ate 7 dias uteis. Avaliacoes dos clientes: 4.7 de 5 estrelas
com base em 312 avaliacoes verificadas da loja. Politica de devolucao em ate 30 dias corridos apos o
recebimento do pedido, sem custo adicional para o comprador. Vendido e entregue por loja parceira
verificada da plataforma, com nota fiscal emitida em nome do consumidor final. Duvidas sobre tamanho,
medidas, composicao do tecido e instrucoes de lavagem estao descritas na aba de detalhes do produto.</p>
</body></html>"""

# Bundle de tradução que o TikTok carrega em TODA página — a armadilha.
I18N = '{"pdp_sold_out":"Sold out","pdp_add_cart":"Adicionar ao carrinho","pdp_esgotado":"Esgotado"}'

casos = [
    # (nome, http, url_final, html, status esperado)
    ("JSON-LD InStock", 200, CANON,
     pagina('<h1>Calça wide leg</h1><button>Adicionar ao carrinho</button>',
            '') .replace("</head>", '<script type="application/ld+json">'
            + json.dumps({"@type":"Product","name":"Calca","offers":{"@type":"Offer","availability":"https://schema.org/InStock","price":"89.90"}})
            + '</script></head>'),
     "disponivel"),

    ("JSON-LD OutOfStock", 200, CANON,
     pagina('<h1>Calça wide leg</h1>')
        .replace("</head>", '<script type="application/ld+json">'
        + json.dumps({"@type":"Product","offers":{"availability":"https://schema.org/OutOfStock"}})
        + '</script></head>'),
     "esgotado"),

    ("404 — link morreu", 404, CANON, "<html><body>Not found</body></html>", "removido"),

    ("Muro de captcha", 200, CANON,
     "<html><body><div>Security check. Please verify to continue.</div></body></html>",
     "indefinido"),

    ("ARMADILHA: 'Sold out' só no JS de tradução + botão de compra visível",
     200, CANON, pagina('<h1>Vestido longo</h1><button>Adicionar ao carrinho</button><span>R$129,90</span>', I18N),
     "disponivel"),

    ("sold_out:true no estado embutido", 200, CANON,
     pagina('<h1>Vestido</h1>', 'window.__DATA__={"product_id":"%s","sold_out":true,"stock":0};' % PID),
     "esgotado"),

    ("Conflito: sold_out true e availability InStock", 200, CANON,
     pagina('<h1>X</h1>', '{"sold_out":true,"availability":"InStock"}'),
     "indefinido"),

    ("Só estoque=0 (sinal fraco)", 200, CANON,
     pagina('<h1>Bolsa tote</h1>', '{"product_id":"1","stock":0}'),
     "esgotado"),

    ("Texto 'Esgotado' visível, sem botão de compra", 200, CANON,
     pagina('<h1>Tênis flatform</h1><div class="cta">Esgotado</div>'),
     "esgotado"),

    ("Conflito no texto: Esgotado + Adicionar ao carrinho", 200, CANON,
     pagina('<h1>Blusa</h1><button>Adicionar ao carrinho</button><aside>Você também pode gostar: Saia midi — Esgotado</aside>'),
     "indefinido"),

    ("Página vazia (200 mas sem conteúdo)", 200, CANON, "<html><body></body></html>", "indefinido"),

    ("Redirecionou pra home", 200, "https://www.tiktok.com/",
     pagina('<h1>TikTok</h1><p>Descubra videos em alta no seu feed hoje mesmo agora</p>'),
     "removido"),
]

print("── Analisador ──")
falhas = 0
for nome, code, final, html, esperado in casos:
    r = tts.analisar(code, final, html, PID)
    ok = r["status"] == esperado
    falhas += 0 if ok else 1
    print(f"{'✅' if ok else '❌'} {nome}\n     -> {r['status']} (esperado {esperado}) | {r['metodo']} | {r['detalhe']}")

print("\n── Regra de confirmação e alerta (sequência de rodadas) ──")
linha = {"id": 1, "produto": "Vestido", "status": "disponivel", "confirmacoes": 0,
         "esgotado_desde": None, "alerta_enviado_em": None, "link": CANON}
sequencia = ["esgotado", "esgotado", "indefinido", "indefinido", "esgotado", "disponivel"]
esperado_alerta = [False, True, False, False, False, False]
esperado_volta  = [False, False, False, False, False, True]

for i, bruto in enumerate(sequencia):
    res = {"status": bruto, "metodo": "teste", "detalhe": "sintético", "http": 200}
    res = tts.aplicar_regra(linha, res)
    a, v = res["avisar_esgotou"], res.get("avisar_volta")
    ok = (a == esperado_alerta[i]) and (v == esperado_volta[i])
    falhas += 0 if ok else 1
    print(f"{'✅' if ok else '❌'} rodada {i+1}: leu '{bruto}' -> status={res['status']} "
          f"conf={res['confirmacoes']} alerta={a} voltou={v}")
    # simula o que fica gravado no banco pra próxima rodada
    linha["status"] = res["status"]
    linha["confirmacoes"] = res["confirmacoes"]
    linha["esgotado_desde"] = res["esgotado_desde"]
    if a:
        linha["alerta_enviado_em"] = tts.agora_iso()

print(f"\n{'🎉 Todos os casos passaram' if not falhas else f'❌ {falhas} caso(s) falharam'}")
sys.exit(1 if falhas else 0)
