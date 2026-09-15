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
    # O "Resumo da fatura" preenche o espaco com pontos ate o valor
    # ("Saldo anterior......... R$ 259,49"), e a regex antiga so aceitava
    # espaco. Sem achar o saldo, a identidade da fatura nao fechava e o
    # importador recusava um PDF que estava perfeito.
    m = re.search(r'Saldo anterior[\s.]*R\$\s*([\d.]+,\d{2})', txt)
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

# Uma fatura fechada pode cobrar MAIS DE UM CARTAO no mesmo documento: o do
# titular e o adicional, cada um com seu bloco e seu subtotal, somando o total
# da fatura. Ler tudo como se fosse um cartao so joga a compra do adicional na
# conta do titular — e foi o que aconteceu com o 3711 ate 15/09.
#
# O marcador do bloco aparece nos dois formatos: "XXXX.XXXX.XXXX.3987" nos
# extratos em aberto e "4532 XXXX XXXX 3987" na fatura fechada.
BLOCO = re.compile(r'(?:XXXX\.XXXX\.XXXX\.|X{4}\s+X{4}\s+)(\d{4})')
# "Número do Cartão 4532 XXXX XXXX 3987" e o cabecalho da pagina, nao o inicio
# de um bloco — casar nele abriria um bloco vazio antes do primeiro cartao.
CABECALHO = re.compile(r'N[úu]mero do Cart[ãa]o', re.I)
# O subtotal do cartao vem como "Total para <NOME>   887,40", e a linha pode
# trazer texto da coluna da direita depois do numero (foi assim que o 3711
# perdeu o proprio subtotal e herdou o total do documento). "Total para as
# próximas faturas" e outra coisa: o nome do titular comeca com maiuscula.
SUBTOTAL = re.compile(r'Total para\s+[A-ZÁ-Ú][^\d]*?([\d.]+,\d{2})')

def ler(pdf):
    """Devolve UMA fatura por cartao cobrado no documento."""
    txt = texto(pdf)
    venc, tot = vencimento_de(txt), total_de(txt)
    saldo_ant = saldo_anterior_de(txt)
    padrao = cartao_de(txt)

    blocos, atual = [], None
    def novo(cart):
        b = {'cartao': cart, 'itens': [], 'subtotal': None}
        blocos.append(b)
        return b

    for linha in txt.split('\n'):
        c = BLOCO.search(linha)
        if c and not CABECALHO.search(linha):
            atual = novo(c.group(1))
            continue
        st = SUBTOTAL.search(linha.strip())
        if st and atual and atual['subtotal'] is None:
            atual['subtotal'] = brl(st.group(1))
            continue
        m = LINHA.match(linha)
        if not m: continue
        dia, desc, val, neg = m.group(1), m.group(2).strip(), brl(m.group(3)), bool(m.group(4))
        desc = re.sub(r'\s{2,}', ' ', desc).strip()
        if not desc or re.match(r'^R\$', desc): continue
        p = PARCELA.search(desc)
        if atual is None: atual = novo(padrao)
        atual['itens'].append({
            'data': ano_de(dia, venc) if venc else None,
            'descricao': desc,
            'valor': -val if neg else val,
            'parcela_numero': int(p.group(1)) if p else None,
            'parcela_total': int(p.group(2)) if p else None,
        })

    # O pagamento da fatura passada vem impresso ANTES do marcador do primeiro
    # cartao, entao ele abre um bloco implicito do mesmo cartao. Juntar blocos
    # do mesmo numero resolve isso e qualquer outra repeticao de marcador.
    juntos = {}
    for b in blocos:
        if not b['itens'] and b['subtotal'] is None: continue
        alvo = juntos.get(b['cartao'])
        if alvo is None:
            juntos[b['cartao']] = b
        else:
            alvo['itens'].extend(b['itens'])
            if alvo['subtotal'] is None: alvo['subtotal'] = b['subtotal']
    blocos = list(juntos.values())
    if not blocos:
        blocos = [{'cartao': padrao, 'itens': [], 'subtotal': None}]

    vd, vm, va = (map(int, venc.split('/')) if venc else (0,0,0))
    mes = f'{MES[vm-1]}/{str(va)[2:]}' if venc else None

    # O saldo anterior do documento pertence ao cartao que carregava a divida:
    # o bloco que traz o pagamento da fatura passada. Rateá-lo entre os cartoes
    # seria inventar um numero que a fatura nao diz.
    def tem_pagamento(b):
        return any(t['valor'] < 0 and re.search(r'PAGTO|PAGAMENTO', t['descricao'], re.I) for t in b['itens'])
    dono = next((b for b in blocos if tem_pagamento(b)), blocos[0])

    faturas = []
    for b in blocos:
        sa = saldo_ant if b is dono else 0.0
        # Com mais de um cartao, o total do documento e a soma dos blocos; cada
        # fatura vale o proprio subtotal impresso.
        declarado = b['subtotal'] if len(blocos) > 1 and b['subtotal'] is not None else tot
        faturas.append({'arquivo': os.path.basename(pdf), 'cartao': b['cartao'],
                        'saldo_anterior': sa, 'vencimento': venc, 'mes': mes,
                        'total_declarado': declarado, 'itens': b['itens'],
                        'total_do_documento': tot, 'cartoes_no_documento': len(blocos)})
    return faturas

if __name__ == '__main__':
    saida = []
    for pdf in sorted(sys.argv[1:]):
        doDoc = ler(pdf)
        for f in doDoc:
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
        # Segunda conferencia, so quando o documento cobra mais de um cartao:
        # a soma dos subtotais tem de dar o total impresso da fatura. E o que
        # garante que nenhum bloco ficou de fora da leitura.
        if len(doDoc) > 1 and doDoc[0].get('total_do_documento') is not None:
            somaCartoes = round(sum(f['total_declarado'] or 0 for f in doDoc), 2)
            doc = doDoc[0]['total_do_documento']
            ok = abs(somaCartoes - doc) < 0.02
            partes = ' + '.join('%s %.2f' % (f['cartao'], f['total_declarado'] or 0) for f in doDoc)
            print("  %s documento cobra %d cartoes: %s = %.2f contra %.2f declarado"
                  % ('OK ' if ok else '!!!', len(doDoc), partes, somaCartoes, doc))
            if not ok:
                for f in doDoc: f['confere'] = False
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
