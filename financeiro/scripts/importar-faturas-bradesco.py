#!/usr/bin/env python3
"""Importa as faturas do Bradesco (cartoes 0013 Amazon e 3987/3711 Visa Platinum).

Le os PDFs, confere cada fatura contra o total que ela mesma declara pela
identidade  total = saldo anterior + soma dos lancamentos  e so grava se todas
fecharem. Sem --aplicar, apenas simula.

Diferente do Itau, a fatura do Bradesco traz o pagamento da fatura anterior
como lancamento negativo dentro da propria lista. Esse lancamento fica com
natureza 'pagamento' e sai de todo total de gasto — as compras que geraram a
divida ja foram contadas na fatura em que aconteceram.
"""
import json, os, re, sys, subprocess, hashlib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from importlib import import_module
ler = import_module('ler-faturas-bradesco'.replace('-', '_')) if False else None

BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
ARQ  = os.path.join(BASE, 'data', 'financeiro.json')
MES  = ['Jan','Fev','Mar','Abr','Mai','Jun','Jul','Ago','Set','Out','Nov','Dez']

DESCRICAO_CARTAO = {
    '0013': 'Amazon Mastercard Platinum - final 0013',
    '3987': 'Bradesco Visa Platinum Sem Anuidade - final 3987',
    '3711': 'Bradesco Visa Platinum Sem Anuidade - final 3711',
}

# Regras de classificacao deste cartao. A pessoa e quem se beneficia da
# despesa, nao quem passou o cartao — mesmo principio das outras fontes.
REGRAS = [
    (r'PAGAMENTO RECEBIDO|PAGTO\.? POR DEB',      'pagamento',            None,                    None),
    (r'^AMAZON',                                   'despesa',  'compras',              'Juliane'),
    (r'DONA TEREZINHA',                            'despesa',  'alimentacao_fora',     'Juliane'),
    (r'AUTO POSTO|POSTO ',                         'despesa',  'transporte',           'Família'),
    (r'SAVEGNAGO|TENDA ATACADO|ATACAD',            'despesa',  'alimentacao',          'Família'),
    (r'PHARMAC|DROGA|FARMAC',                      'despesa',  'saude',                'Família'),
    (r'CREPES|MC ?DONALD|KFC|RESTAURANT|LANCH',    'despesa',  'alimentacao_fora',     'Família'),
    (r'SEGURO SUPERPROTEGIDO',                     'despesa',  'seguro',               'Juliane'),
    (r'IOF|JUROS|MULTA|ENCARGOS|MORA',             'despesa',  'encargos_financeiros', 'Juliane'),
    (r'SHOPEE|MERCADO ?PAGO|MERCADO ?LIVRE|MP\*',  'despesa',  'compras',              'Juliane'),
]

def classificar(desc):
    for padrao, nat, cat, pessoa in REGRAS:
        if re.search(padrao, desc, re.I):
            return nat, cat, pessoa
    return 'despesa', 'nao_classificado', 'Juliane'

def main():
    aplicar = '--aplicar' in sys.argv
    pdfs = [a for a in sys.argv[1:] if a.endswith('.pdf')]
    faturas = json.load(open('/tmp/bradesco.json', encoding='utf-8'))
    fechadas = [f for f in faturas if f['total_declarado'] is not None]
    # Extratos "EM ABERTO" do app: a fatura do mes em curso, ainda enchendo.
    try:
        abertos = json.load(open('/tmp/bradesco-abertos.json', encoding='utf-8'))
    except Exception:
        abertos = []
    for b in abertos:
        b['aberta'] = True
    fechadas = fechadas + abertos

    ruins = [f for f in fechadas if not f['confere']]
    if ruins:
        print('Faturas que nao fecham — nada foi gravado:')
        for f in ruins:
            print(f"  {f['cartao']} {f['mes']}: declarado {f['total_declarado']} "
                  f"x saldo_ant {f['saldo_anterior']} + soma {f['soma_itens']}")
        return 1

    dados = json.load(open(ARQ, encoding='utf-8'))
    tx = dados['fluxo_mensal']['transacoes']
    existentes = {t.get('id') for t in tx}

    novos, cabecalhos = [], {}
    for f in fechadas:
        cart, mes, venc = f['cartao'], f['mes'], f['vencimento']
        # A fatura fechada traz o vencimento como dd/mm/aaaa; o extrato em
        # aberto ja vem em ISO. Normaliza os dois para ISO.
        if '/' in venc:
            vd, vm, va = map(int, venc.split('/'))
            venc_iso = f'{va:04d}-{vm:02d}-{vd:02d}'
        else:
            venc_iso = venc
        chave = f'{cart}|{mes}'
        compras = estornos = pagos = 0.0
        n = 0
        for i, item in enumerate(f['itens']):
            desc = item['descricao']
            nat, cat, pessoa = classificar(desc)
            valor = item['valor']
            if nat == 'pagamento':
                valor = -abs(valor); pagos += abs(valor)
            else:
                if valor > 0:
                    compras += valor
                else:
                    # Valor negativo que nao e pagamento e devolucao de compra
                    # (a fatura marca com "EST" ou traz o valor com sinal). Tem
                    # de ficar como estorno, nao como despesa negativa, senao
                    # some das checagens de estorno e polui o total de gasto.
                    estornos += valor
                    nat = 'estorno'
            n += 1
            base = f"{chave}|{i}|{item['data']}|{desc}|{valor}"
            tid = 'brad_' + hashlib.md5(base.encode()).hexdigest()[:12]
            if tid in existentes: continue
            t = {
                'id': tid,
                'data': item['data'],
                'tipo': 'saida' if valor > 0 else 'entrada',
                'natureza': nat,
                'descricao': re.sub(r'\s*\(\d{2}/\d{2}\)\s*$', '', desc).strip(),
                'valor': round(valor, 2),
                'pessoa': pessoa or 'Juliane',
                'categoria': cat or 'pagamento_fatura',
                'classificado_por': 'regra_bradesco',
                'conta_origem': DESCRICAO_CARTAO.get(cart, cart),
                'cartao_final': cart,
                'final_cartao': cart,
                'conta_destino': 'Comerciante',
                'status': 'confirmado',
                'origem': 'cartao_credito_bradesco',
                'mes_vencimento': mes,
                'data_vencimento_fatura': venc_iso,
                'mes_referencia': mes,
                'fatura_origem': chave,
                'titularidade': 'Titular',
                'portador': 'Juliane Ferreira Benetti',
                'tipo_cartao': 'Físico',
                'carga_id': 'faturas_bradesco_2026',
                'ambito': 'pessoal',
                'eh_parcelada': bool(item['parcela_numero']),
            }
            if item['parcela_numero']:
                t.update({
                    'parcela_numero': item['parcela_numero'],
                    'parcela_total': item['parcela_total'],
                    'descricao_parcela': f"{item['parcela_numero']}/{item['parcela_total']}",
                    'parcela_fonte': 'coluna',
                    'id_compra': 'compra_' + tid,
                    'data_compra_original': item['data'],
                })
            novos.append(t)
        cabecalhos[chave] = {
            'aberta': bool(f.get('aberta')),
            'cartao': cart, 'cartao_descricao': DESCRICAO_CARTAO.get(cart, cart),
            'mes': mes, 'vencimento': venc_iso,
            'lancamentos': n, 'compras': round(compras, 2), 'estornos': round(estornos, 2),
            'pagamentos': round(pagos, 2), 'divida_parcelada': 0,
            'cobrado': round(compras + estornos, 2),
            'saldo_anterior': round(f['saldo_anterior'], 2),
            'total_fatura': round(f['total_declarado'], 2),
        }

    # Uma fatura esta paga quando a fatura seguinte do mesmo cartao traz o
    # pagamento dela; a ultima de cada cartao se resolve pelo extrato.
    porCartao = {}
    for c in cabecalhos.values():
        porCartao.setdefault(c['cartao'], []).append(c)
    for cart, lista in porCartao.items():
        lista.sort(key=lambda c: c['vencimento'])
        for idx, c in enumerate(lista):
            seguinte = lista[idx + 1] if idx + 1 < len(lista) else None
            if seguinte and abs(seguinte['pagamentos'] - c['total_fatura']) < 0.02:
                c['pago'] = c['total_fatura']; c['em_aberto'] = 0.0; c['situacao'] = 'paga'
            elif seguinte:
                c['pago'] = seguinte['pagamentos']
                c['em_aberto'] = round(c['total_fatura'] - seguinte['pagamentos'], 2)
                c['situacao'] = 'paga_parcial' if seguinte['pagamentos'] > 0 else 'fechada'
            elif c.get('aberta'):
                c['pago'] = 0.0; c['em_aberto'] = c['total_fatura']; c['situacao'] = 'aberta'
            else:
                pago_extrato = sum(
                    t['valor'] for t in tx
                    if t.get('origem') == 'extrato_itau' and t.get('data', '') >= c['vencimento']
                    and abs(t.get('valor', 0) - c['total_fatura']) < 0.02
                    and re.search(r'bradescard|cart[ãa]o amazon', (t.get('descricao') or '') + ' ' + (t.get('descricao_original') or ''), re.I))
                c['pago'] = round(pago_extrato, 2)
                c['em_aberto'] = round(c['total_fatura'] - pago_extrato, 2)
                c['situacao'] = 'paga' if c['em_aberto'] < 0.02 else 'fechada'

    print(f'{len(novos)} lancamentos novos · {len(cabecalhos)} faturas\n')
    for chave in sorted(cabecalhos, key=lambda k: (k.split('|')[0], cabecalhos[k]['vencimento'])):
        c = cabecalhos[chave]
        print(f"  {c['cartao']} {c['mes']:7s} venc={c['vencimento']} lanc={c['lancamentos']:3d} "
              f"compras={c['compras']:8.2f} saldo_ant={c['saldo_anterior']:8.2f} "
              f"total={c['total_fatura']:8.2f} pago={c['pago']:8.2f} aberto={c['em_aberto']:8.2f} {c['situacao']}")

    if not aplicar:
        print('\n(simulacao — use --aplicar para gravar)')
        return 0

    outras = [f for f in dados['faturas_cartao'] if f"{f['cartao']}|{f['mes']}" not in cabecalhos]
    for c in cabecalhos.values():
        c.pop('aberta', None)
    # Ordena por cartao + vencimento: a aba Cartoes e as checagens de sequencia
    # leem a lista na ordem em que ela esta gravada.
    dados['faturas_cartao'] = sorted(outras + list(cabecalhos.values()),
                                     key=lambda f: (f.get('cartao', ''), f.get('vencimento', '')))
    dados['fluxo_mensal']['transacoes'] = tx + novos
    json.dump(dados, open(ARQ, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
    print(f'\nGRAVADO em {ARQ}')
    return 0

if __name__ == '__main__':
    sys.exit(main())
