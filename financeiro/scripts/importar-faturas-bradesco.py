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
    (r'SAVEGNAGO|TENDA ATACADO|ATACAD|SUPERMERC|MINIMERCAD|MERCEARIA|HORTIFRUT',
                                                   'despesa',  'alimentacao',          'Família'),
    (r'PHARMAC|DROGA|FARMAC',                      'despesa',  'saude',                'Família'),
    (r'CREPES|MC ?DONALD|KFC|RESTAURANT|LANCH|PARMEGGIO|PIZZA|BURGER',
                                                   'despesa',  'alimentacao_fora',     'Família'),
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

    # O extrato "EM ABERTO" e uma foto do ciclo enquanto ele ainda enche. Quando
    # a fatura fechada do MESMO ciclo chega, ela manda: traz as compras do fim do
    # periodo que a foto nao tinha e o total definitivo. Sem esta regra, a foto
    # de 30/08 continuaria valendo sobre a fatura de 15/09 e o mes ficaria
    # R$ 188,66 mais barato do que e.
    jaFechadas = {(f['cartao'], f['mes']) for f in fechadas}
    superados = [b for b in abertos if (b['cartao'], b['mes']) in jaFechadas]
    for b in superados:
        print(f"  {b['cartao']} {b['mes']}: extrato em aberto descartado — "
              f"a fatura fechada do mesmo ciclo chegou (R$ {b['total_declarado']:.2f} → "
              f"{[f['total_declarado'] for f in fechadas if (f['cartao'], f['mes']) == (b['cartao'], b['mes'])][0]})")
    fechadas = fechadas + [b for b in abertos if (b['cartao'], b['mes']) not in jaFechadas]

    ruins = [f for f in fechadas if not f['confere']]
    if ruins:
        print('Faturas que nao fecham — nada foi gravado:')
        for f in ruins:
            print(f"  {f['cartao']} {f['mes']}: declarado {f['total_declarado']} "
                  f"x saldo_ant {f['saldo_anterior']} + soma {f['soma_itens']}")
        return 1

    dados = json.load(open(ARQ, encoding='utf-8'))
    tx = dados['fluxo_mensal']['transacoes']

    # O cabecalho da fatura ja era substituido; os lancamentos dela nao eram.
    # Reimportar uma fatura ja gravada somava as duas leituras: quando a fatura
    # fechada de 15/09 chegou por cima da foto em aberto de 30/08, o 3711 passou
    # a somar R$ 698,47 numa fatura de R$ 383,57.
    #
    # Mesmo principio do importador do extrato: o que e relido e substituido,
    # nao acrescentado. So as faturas desta rodada — as outras ficam intactas.
    #
    # A purga vem ANTES de montar `existentes`, e a ordem e o proprio bug: com
    # os antigos ainda na lista, todo id repetido era tratado como "ja existe",
    # o lancamento novo nao chegava a ser gerado, e a purga apagava o antigo sem
    # repor. Ficaram 9 faturas com zero lancamento.
    relidas = {f"{f['cartao']}|{f['mes']}" for f in fechadas}
    antes = len(tx)
    tx = [t for t in tx if t.get('fatura_origem') not in relidas]
    if antes != len(tx):
        print(f'{antes - len(tx)} lancamento(s) da leitura anterior destas faturas serao substituidos')

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
    todas = tx + novos

    # Liga as parcelas da MESMA compra.
    #
    # Ate aqui cada lancamento parcelado ganhava um id_compra proprio ('compra_'
    # + id), entao a parcela 2/4 e a 3/4 do mesmo aparelho compradas em 19/11
    # viravam duas compras diferentes: a numeracao de cada grupo fica sequencial
    # sozinha, e por isso os testes de sequencia nunca acusaram — mas a tela
    # mostra duas compras onde ha uma, e a previsao de quitacao sai errada.
    #
    # Mesma regra dos outros importadores: mesmo cartao, mesma data de compra,
    # mesmo numero de parcelas, e um texto que e comeco do outro (a fatura as
    # vezes corta a descricao). O teste de prefixo impede fundir duas compras
    # de verdade que so coincidam em data e prazo.
    grupos = {}
    for t in todas:
        if t.get('origem') != 'cartao_credito_bradesco' or not t.get('eh_parcelada'):
            continue
        grupos.setdefault((t.get('cartao_final'), t.get('data'), t.get('parcela_total')), []).append(t)

    religadas = 0
    for parcelas in grupos.values():
        familias = []
        for t in parcelas:
            d = (t.get('descricao') or '').lower()
            for f in familias:
                base = (f[0].get('descricao') or '').lower()
                if d.startswith(base) or base.startswith(d):
                    f.append(t)
                    break
            else:
                familias.append([t])
        for f in familias:
            if len(f) < 2:
                continue
            f.sort(key=lambda x: x.get('parcela_numero') or 0)
            id_compra = f[0].get('id_compra') or ('compra_' + str(f[0].get('id')))
            completa = len(f) == f[0].get('parcela_total')
            total = (round(sum(x['valor'] for x in f), 2) if completa
                     else round(f[0]['valor'] * f[0]['parcela_total'], 2))
            for x in f:
                if x.get('id_compra') != id_compra:
                    religadas += 1
                x['id_compra'] = id_compra
                x['valor_total_compra'] = total
                x['valor_total_exato'] = completa
                x['parcelas_no_periodo'] = len(f)

    if religadas:
        print(f'{religadas} parcela(s) religadas a compra a que pertencem.')

    dados['fluxo_mensal']['transacoes'] = todas
    json.dump(dados, open(ARQ, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
    print(f'\nGRAVADO em {ARQ}')
    return 0

if __name__ == '__main__':
    sys.exit(main())
