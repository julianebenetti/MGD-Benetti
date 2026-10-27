#!/usr/bin/env python3
"""
Lista os campos que a API de afiliados devolve para cada produto (productOfferV2), para descobrir se
existe algum campo de estoque/disponibilidade, e os das conversões (o "Canal": vídeo, live, redes sociais). Rode no VPS:  .venv/bin/python campos_api.py
Só mostra nomes de campos (nenhuma chave aparece).
"""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / '.env')

from shopee_affiliate import ShopeeAffiliateClient  # noqa: E402

PISTAS = ('stock', 'estoque', 'avail', 'sold', 'status', 'quantity', 'qty', 'inventory', 'active')


def main():
    client = ShopeeAffiliateClient(os.environ['SHOPEE_AFFILIATE_APP_ID'], os.environ['SHOPEE_AFFILIATE_SECRET'])
    try:
        data = client._graphql('{__schema{types{name fields{name}}}}')
    except Exception as e:
        print(f"A API não deixou listar os campos ({e}).")
        return
    for t in data['__schema']['types']:
        if t['name'].startswith('ProductOffer') and t.get('fields'):
            names = [f['name'] for f in t['fields']]
            print(f"\n{t['name']}:\n  " + ', '.join(names))
            suspeitos = [n for n in names if any(p in n.lower() for p in PISTAS)]
            if suspeitos:
                print(f"  ➜ possíveis campos de estoque/disponibilidade: {', '.join(suspeitos)}")
        if 'conversion' in t['name'].lower() and t.get('fields'):
            names = [f['name'] for f in t['fields']]
            print(f"\n{t['name']}:\n  " + ', '.join(names))
            canal = [n for n in names if 'channel' in n.lower()]
            if canal:
                print(f"  ➜ campo de canal (vídeo/live/redes) usado no /vendas: {', '.join(canal)}")


if __name__ == '__main__':
    main()
