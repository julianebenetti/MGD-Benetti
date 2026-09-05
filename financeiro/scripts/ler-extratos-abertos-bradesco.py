#!/usr/bin/env python3
"""Le os extratos "EM ABERTO" do app Bradesco Cartoes.

Formato diferente da fatura mensal fechada: um PDF pode trazer mais de um
cartao, cada um com seu bloco e seu subtotal, e a coluna de valor vem por
ultimo (depois da moeda de origem e da cotacao). A linha "SALDO ANTERIOR" e
marcador de saldo, nao lancamento — entra so para conferir o subtotal.
"""
import re, sys, json, subprocess

MES = ['Jan','Fev','Mar','Abr','Mai','Jun','Jul','Ago','Set','Out','Nov','Dez']
CAB   = re.compile(r'XXXX\.XXXX\.XXXX\.(\d{4})')
# No extrato do app a descricao as vezes nao cabe na linha da data e se quebra
# nas linhas de cima e de baixo, deixando so o codigo "000" no meio. Por isso a
# descricao e remontada a partir das linhas vizinhas quando a da data vem vazia.
LINHA = re.compile(r'^\s*(\d{2}/\d{2})\s+(.*?)\s{2,}[\d.,]+\s+[\d.,]+\s+R\$\s*[\d.,]+\s+(-?[\d.]+,\d{2})\s*$')
LINHA_SIMPLES = re.compile(r'^\s*(\d{2}/\d{2})\s+(\S.*?)\s{2,}[\d.,]+\s+R\$\s*[\d.,]+\s+(-?[\d.]+,\d{2})\s*$')
SO_DATA = re.compile(r'^\s*\d{2}/\d{2}\s')
LIXO = re.compile(r'^[\s.\d,R$]*$')
SUB   = re.compile(r'Total para .*?R\$\s*([\d.]+,\d{2})')
brl   = lambda s: float(s.replace('.','').replace(',','.'))

def ler(pdf, mes_alvo, venc_iso):
    txt = subprocess.run(['pdftotext','-layout',pdf,'-'],capture_output=True,text=True).stdout
    blocos, atual = [], None
    linhas = txt.split('\n')
    for i, linha in enumerate(linhas):
        c = CAB.search(linha)
        if c:
            atual = {'cartao': c.group(1), 'itens': [], 'subtotal': None,
                     'mes': mes_alvo, 'vencimento': venc_iso}
            blocos.append(atual); continue
        if atual is None: continue
        s = SUB.search(linha)
        if s and atual['subtotal'] is None:
            atual['subtotal'] = brl(s.group(1)); continue
        m = LINHA.match(linha) or LINHA_SIMPLES.match(linha)
        if not m: continue
        dia, desc, val = m.group(1), re.sub(r'\s{2,}',' ',m.group(2)).strip(), brl(m.group(3))
        if LIXO.match(desc):
            antes = linhas[i-1].strip() if i > 0 else ''
            depois = linhas[i+1].strip() if i + 1 < len(linhas) else ''
            partes = [x for x in (antes, depois)
                      if x and not SO_DATA.match(x) and not LIXO.match(x) and 'Total' not in x]
            desc = re.sub(r'\s{2,}', ' ', ' '.join(partes)).strip()
        if 'SALDO ANTERIOR' in desc.upper():
            atual['saldo_anterior'] = val; continue
        d, mm = map(int, dia.split('/'))
        # Sobra da coluna "moeda de origem" que o layout cola no fim da descricao.
        desc = re.sub(r'\s*\b000\b[\s\d.,]*$', '', desc).strip()
        pn = pt = None
        mp = re.search(r'(\d{1,2})\s*/\s*(\d{1,2})\s*$', desc)
        if mp:
            pn, pt = int(mp.group(1)), int(mp.group(2))
            desc = desc[:mp.start()].strip()
        atual['itens'].append({'data': f'2026-{mm:02d}-{d:02d}', 'descricao': desc,
                               'valor': val, 'parcela_numero': pn, 'parcela_total': pt})
    # Nem todo bloco imprime a linha "SALDO ANTERIOR". Quando falta, o saldo e
    # deduzido do total da ultima fatura fechada do mesmo cartao, e so e aceito
    # se com ele o subtotal do bloco fechar — se nao fechar, o bloco continua
    # marcado como divergente em vez de entrar com numero inventado.
    try:
        fechadas = json.load(open('/tmp/bradesco.json', encoding='utf-8'))
    except Exception:
        fechadas = []
    ultimo = {}
    for f in fechadas:
        if f.get('total_declarado') is None: continue
        ant = ultimo.get(f['cartao'])
        if ant is None or f['vencimento'][6:] + f['vencimento'][3:5] > ant['vencimento'][6:] + ant['vencimento'][3:5]:
            ultimo[f['cartao']] = f

    for b in blocos:
        if 'saldo_anterior' not in b and b['subtotal'] is not None:
            soma = round(sum(i['valor'] for i in b['itens']), 2)
            deduzido = (ultimo.get(b['cartao']) or {}).get('total_declarado')
            if deduzido and abs(deduzido + soma - b['subtotal']) < 0.02:
                b['saldo_anterior'] = deduzido
                b['saldo_anterior_deduzido'] = True
                print(f"  ! {b['cartao']}: saldo anterior nao vem no extrato, deduzido da "
                      f"ultima fatura fechada ({deduzido:.2f}) — com ele o bloco fecha")
    for b in blocos:
        b.setdefault('saldo_anterior', 0.0)
        soma = round(sum(i['valor'] for i in b['itens']), 2)
        b['soma_itens'] = soma
        b['total_declarado'] = b['subtotal']
        esperado = round(b['saldo_anterior'] + soma, 2)
        b['confere'] = b['subtotal'] is not None and abs(esperado - b['subtotal']) < 0.02
        b['soma_compras'] = round(sum(i['valor'] for i in b['itens'] if i['valor'] > 0), 2)
    return blocos

if __name__ == '__main__':
    todos = []
    for pdf in [a for a in sys.argv[1:] if a.endswith('.pdf')]:
        for b in ler(pdf, 'Set/26', '2026-09-15'):
            todos.append(b)
            print(f"{b['cartao']} {b['mes']} n={len(b['itens']):3d} saldo_ant={b['saldo_anterior']:8.2f} "
                  f"soma={b['soma_itens']:9.2f} subtotal={b['subtotal']} "
                  f"{'CONFERE' if b['confere'] else '<<< NAO FECHA'}")
    json.dump(todos, open('/tmp/bradesco-abertos.json','w'), ensure_ascii=False, indent=1)
