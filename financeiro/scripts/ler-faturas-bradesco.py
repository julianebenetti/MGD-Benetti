#!/usr/bin/env python3
"""Le as faturas do Bradesco (PDF -> texto via pdftotext -layout) e devolve os
lancamentos de cada uma, ja conferidos contra o total que a propria fatura
declara. So imprime; nao grava nada."""
import re, sys, os, json, subprocess

MES = ['Jan','Fev','Mar','Abr','Mai','Jun','Jul','Ago','Set','Out','Nov','Dez']

# Valor da transacao nunca vem com "R$" — esse prefixo so aparece nas colunas de
# limite e resumo que o layout do PDF derrama na mesma linha. E o que separa
# um do outro.
LINHA = re.compile(r'^\s*(\d{2}/\d{2})\s+(\S.*?)\s{2,}(\d{1,3}(?:\.\d{3})*,\d{2})(\s*-)?(?:\s|$)')
PARCELA = re.compile(r'\((\d{2})/(\d{2})\)\s*$')

def texto(pdf):
    return subprocess.run(['pdftotext','-layout',pdf,'-'],
                          capture_output=True, text=True).stdout

def cartao_de(txt):
    m = re.search(r'XXXX\.XXXX\.XXXX\.(\d{4})', txt)
    if m: return m.group(1)
    if re.search(r'AMAZON MASTERCARD PLATINUM', txt, re.I): return '0013'
    if re.search(r'PLATINUM (PRIME|)\s*SEM ANUIDADE', txt, re.I): return '3987'
    return None

def vencimento_de(txt):
    m = re.search(r'Vencimento.*?(\d{2}/\d{2}/\d{4})', txt, re.S)
    if not m: m = re.search(r'(\d{2}/\d{2}/\d{4})', txt)
    return m.group(1) if m else None

def saldo_anterior_de(txt):
    m = re.search(r'Saldo anterior\s+R\$\s*([\d.]+,\d{2})', txt)
    return brl(m.group(1)) if m else 0.0

def total_de(txt):
    m = re.search(r'Total da fatura.*?R\$\s*([\d.]+,\d{2})', txt, re.S)
    return brl(m.group(1)) if m else None

def brl(s): return float(s.replace('.','').replace(',','.'))

def ano_de(dia_mes, venc):
    """A fatura traz so dia/mes da compra. O ano sai do vencimento: compra em
    mes maior que o do vencimento e do ano anterior (compra de nov/dez numa
    fatura de jan)."""
    d, m = map(int, dia_mes.split('/'))
    vd, vm, va = map(int, venc.split('/'))
    ano = va if m <= vm else va - 1
    return f'{ano:04d}-{m:02d}-{d:02d}'

def ler(pdf):
    txt = texto(pdf)
    cart, venc, tot = cartao_de(txt), vencimento_de(txt), total_de(txt)
    saldo_ant = saldo_anterior_de(txt)
    itens = []
    for linha in txt.split('\n'):
        m = LINHA.match(linha)
        if not m: continue
        dia, desc, val, neg = m.group(1), m.group(2).strip(), brl(m.group(3)), bool(m.group(4))
        desc = re.sub(r'\s{2,}', ' ', desc).strip()
        if not desc or re.match(r'^R\$', desc): continue
        p = PARCELA.search(desc)
        itens.append({
            'data': ano_de(dia, venc) if venc else None,
            'descricao': desc,
            'valor': -val if neg else val,
            'parcela_numero': int(p.group(1)) if p else None,
            'parcela_total': int(p.group(2)) if p else None,
        })
    vd, vm, va = (map(int, venc.split('/')) if venc else (0,0,0))
    return {'arquivo': os.path.basename(pdf), 'cartao': cart, 'saldo_anterior': saldo_ant, 'vencimento': venc,
            'mes': f'{MES[vm-1]}/{str(va)[2:]}' if venc else None,
            'total_declarado': tot, 'itens': itens}

if __name__ == '__main__':
    saida = []
    for pdf in sorted(sys.argv[1:]):
        f = ler(pdf)
        soma = round(sum(i['valor'] for i in f['itens']), 2)
        pos  = round(sum(i['valor'] for i in f['itens'] if i['valor'] > 0), 2)
        f['soma_itens'] = soma; f['soma_compras'] = pos
        # A fatura fecha por: total = saldo anterior + soma dos lancamentos
        # (o pagamento da fatura passada entra como lancamento negativo).
        esperado = f['saldo_anterior'] + soma
        bate = f['total_declarado'] is not None and abs(esperado - f['total_declarado']) < 0.02
        f['confere'] = bate
        saida.append(f)
        print(f"{f['cartao'] or '????'} {f['mes'] or '?':7s} venc={f['vencimento']} "
              f"total={str(f['total_declarado']):>8s} saldo_ant={f['saldo_anterior']:8.2f} soma={soma:9.2f} compras={pos:8.2f} "
              f"n={len(f['itens']):3d} {'CONFERE' if bate else '<<< NAO FECHA'}")
    # O PDF do 3987 nao imprime a linha "Saldo anterior", mas traz o pagamento
    # da fatura passada como lancamento negativo — sem o saldo, a identidade
    # nao fecha. Nesses casos o saldo e deduzido do total da fatura anterior do
    # mesmo cartao, e so e aceito se isso fizer a conta fechar: se nao fechar,
    # o valor deduzido e descartado e a fatura continua marcada como divergente.
    porCartao = {}
    for f in saida:
        if f['total_declarado'] is not None:
            porCartao.setdefault(f['cartao'], []).append(f)
    for lista in porCartao.values():
        lista.sort(key=lambda f: (f['vencimento'][6:], f['vencimento'][3:5]))
        for i, f in enumerate(lista):
            if f['confere'] or f['saldo_anterior'] or i == 0:
                continue
            deduzido = lista[i-1]['total_declarado']
            if abs(deduzido + f['soma_itens'] - f['total_declarado']) < 0.02:
                f['saldo_anterior'] = deduzido
                f['saldo_anterior_deduzido'] = True
                f['confere'] = True
                print(f"  ! {f['cartao']} {f['mes']}: saldo anterior nao vem no PDF, "
                      f"deduzido da fatura anterior ({deduzido:.2f}) — com ele a fatura fecha")

    json.dump(saida, open('/tmp/bradesco.json','w'), ensure_ascii=False, indent=1)
    naoFecham = [f for f in saida if f['total_declarado'] is not None and not f['confere']]
    print(f"\n{len(saida)} PDFs · {len([f for f in saida if f['total_declarado'] is not None])} faturas fechadas · "
          f"{len(naoFecham)} sem conferir")
    print('-> /tmp/bradesco.json')
