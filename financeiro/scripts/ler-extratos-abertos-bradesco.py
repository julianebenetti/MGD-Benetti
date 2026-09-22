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
# Total do documento inteiro. Num extrato de um cartao so ele tem de ser igual
# ao "Total para <nome>"; num de varios, a soma dos subtotais.
TOTDOC = re.compile(r'Total da Fatura em Real.*?R\$\s*([\d.]+,\d{2})')
DATA_EXTRATO = re.compile(r'Data:\s*(\d{2})/(\d{2})/(\d{4})')
brl   = lambda s: float(s.replace('.','').replace(',','.'))

def ciclo_em_aberto(txt, dia_venc=15):
    """De que fatura este extrato em aberto e a previa.

    O ciclo aberto e o que vence no proximo dia `dia_venc` DEPOIS da data em que
    o extrato foi tirado: puxado em 22/09, a fatura de 15/09 ja fechou e o que
    esta enchendo vence em 15/10. Antes isso vinha fixo no codigo ('Set/26'), o
    que estava certo para os arquivos de 30/08 e passou a mentir em silencio no
    primeiro extrato tirado depois de um vencimento — gravando uma foto de ciclo
    aberto por cima da fatura fechada do mes anterior.
    """
    m = DATA_EXTRATO.search(txt)
    if not m:
        return None, None
    d, mm, aa = int(m.group(1)), int(m.group(2)), int(m.group(3))
    if d >= dia_venc:
        mm += 1
        if mm > 12:
            mm, aa = 1, aa + 1
    return f'{MES[mm-1]}/{str(aa)[2:]}', f'{aa}-{mm:02d}-{dia_venc:02d}'


def ler(pdf, mes_alvo=None, venc_iso=None, dia_venc=15):
    txt = subprocess.run(['pdftotext','-layout',pdf,'-'],capture_output=True,text=True).stdout
    if mes_alvo is None or venc_iso is None:
        mes_alvo, venc_iso = ciclo_em_aberto(txt, dia_venc)
        if mes_alvo is None:
            print(f'  ! {pdf}: sem a data do extrato, nao da para dizer de que ciclo e')
            return []
        print(f"  {pdf.split('/')[-1]}: extrato em aberto do ciclo que vence "
              f"{venc_iso[8:]}/{venc_iso[5:7]}/{venc_iso[:4]} -> {mes_alvo}")
    total_documento = None
    td = TOTDOC.search(txt)
    if td:
        total_documento = brl(td.group(1))
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
    # **O total do documento manda quando ele e de um cartao so.**
    #
    # No extrato de 22/09 o "Total para JULIANE BENETTI" diz R$ 261,48 e o
    # "Total da Fatura em Real" diz R$ 193,08 — e sao os R$ 193,08 que a
    # itemizacao reproduz ao centavo (261,48 = 2x compras - pagamento, que nao e
    # conta de nada; parece defeito do proprio app). Nos extratos de 30/08 os
    # dois batiam, entao a divergencia e do documento, nao da leitura.
    #
    # Escolher o numero que fecha nao pode ser silencioso: a troca e anunciada,
    # e so acontece com UM bloco no documento — com varios, o subtotal por
    # cartao e a unica forma de saber quanto e de quem.
    if total_documento is not None and len(blocos) == 1:
        b = blocos[0]
        if b['subtotal'] is not None and abs(b['subtotal'] - total_documento) > 0.02:
            print(f"  ! {b['cartao']}: 'Total para <nome>' diz {b['subtotal']:.2f} e "
                  f"'Total da Fatura em Real' diz {total_documento:.2f}; fico com o "
                  f"total do documento, que e o que a itemizacao reproduz")
            b['subtotal'] = total_documento
            b['subtotal_trocado_pelo_total_do_documento'] = True
    if total_documento is not None and len(blocos) > 1:
        soma_sub = round(sum(b['subtotal'] or 0 for b in blocos), 2)
        if abs(soma_sub - total_documento) > 0.02:
            print(f"  ! a soma dos subtotais ({soma_sub:.2f}) nao da o total do "
                  f"documento ({total_documento:.2f}) — algum bloco ficou de fora")

    # Nem todo bloco imprime a linha "SALDO ANTERIOR". Quando falta, o saldo e
    # deduzido do total da ultima fatura fechada do mesmo cartao, e so e aceito
    # se com ele o subtotal do bloco fechar — se nao fechar, o bloco continua
    # marcado como divergente em vez de entrar com numero inventado.
    try:
        fechadas = json.load(open('/tmp/bradesco.json', encoding='utf-8'))
    except Exception:
        fechadas = []
    # O /tmp so tem o que a ultima leitura de fatura produziu. A lista completa
    # do que ja esta gravado esta no proprio financeiro.json — sem ela, um
    # extrato em aberto de um cartao cuja fatura nao foi relida agora fica sem
    # saldo anterior e e marcado como divergente sem motivo.
    try:
        import os
        base = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                           '..', 'data', 'financeiro.json'), encoding='utf-8'))
        for f in base.get('faturas_cartao', []):
            if f.get('total_fatura') is None or not f.get('vencimento'):
                continue
            v = f['vencimento']  # ja vem em AAAA-MM-DD
            fechadas.append({'cartao': f['cartao'], 'total_declarado': f['total_fatura'],
                             'vencimento': f"{v[8:10]}/{v[5:7]}/{v[:4]}"})
    except Exception:
        pass
    # A fatura que carrega o saldo anterior e a ultima que venceu ANTES deste
    # ciclo — nao a mais recente que existir na base. Com o financeiro.json
    # inteiro em maos, a fatura do proprio ciclo (ou uma posterior) ja pode estar
    # gravada, e usa-la faria o bloco nunca fechar.
    def chave(venc_br):
        return venc_br[6:] + venc_br[3:5] + venc_br[:2]

    def ultima_antes(cartao, venc_iso_bloco):
        limite = venc_iso_bloco[:4] + venc_iso_bloco[5:7] + venc_iso_bloco[8:10]
        melhor = None
        for f in fechadas:
            if f['cartao'] != cartao or f.get('total_declarado') is None: continue
            k = chave(f['vencimento'])
            if k >= limite: continue
            if melhor is None or k > chave(melhor['vencimento']):
                melhor = f
        return melhor

    for b in blocos:
        if 'saldo_anterior' not in b and b['subtotal'] is not None:
            soma = round(sum(i['valor'] for i in b['itens']), 2)
            deduzido = (ultima_antes(b['cartao'], b['vencimento']) or {}).get('total_declarado')
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
        for b in ler(pdf):
            todos.append(b)
            print(f"{b['cartao']} {b['mes']} n={len(b['itens']):3d} saldo_ant={b['saldo_anterior']:8.2f} "
                  f"soma={b['soma_itens']:9.2f} subtotal={b['subtotal']} "
                  f"{'CONFERE' if b['confere'] else '<<< NAO FECHA'}")
    json.dump(todos, open('/tmp/bradesco-abertos.json','w'), ensure_ascii=False, indent=1)
