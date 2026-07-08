"""
Shopee Affiliate API Sync
Roda via GitHub Actions todo dia
Salva shopee-data.json no repositorio
"""
import hashlib, time, json, os, urllib.request, urllib.error
from datetime import datetime, timezone

URL    = "https://open-api.affiliate.shopee.com.br/graphql"
APP_ID = os.environ["SHOPEE_APP_ID"]
SECRET = os.environ["SHOPEE_SECRET"]
DAYS   = 90

# ── Monitor de Comissão ──────────────────────────────────────────
MONITOR_FILE       = "comissoes-monitor.json"
DIAS_ATIVIDADE     = 7      # produto com pedido nos últimos N dias = considerado "rodando"
QUEDA_MINIMA_ALERTA = 2.0   # pontos percentuais de queda pra disparar alerta

EMAILJS_PUBLIC_KEY  = "GLe9wQzP7zB0viJIo"
EMAILJS_SERVICE_ID  = "service_ptgsjyg"
EMAILJS_TEMPLATE_ID = "template_j9q926c"
EMAILJS_PRIVATE_KEY = os.environ.get("EMAILJS_PRIVATE_KEY", "")

def call(query):
    payload = json.dumps({"query": query}, separators=(',', ':'))
    ts  = str(int(time.time()))
    sig = hashlib.sha256((APP_ID + ts + payload + SECRET).encode()).hexdigest()
    auth = f"SHA256 Credential={APP_ID}, Timestamp={ts}, Signature={sig}"
    req = urllib.request.Request(URL, data=payload.encode(),
        headers={"Content-Type": "application/json", "Authorization": auth},
        method="POST")
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())

def fetch_all():
    now   = int(time.time())
    start = now - (DAYS * 86400)
    all_nodes  = []
    scroll_id  = None
    page       = 0
    while True:
        page += 1
        print(f"  Buscando pagina {page}... (ja coletados: {len(all_nodes)})")
        scroll_arg = f', scrollId: "{scroll_id}"' if scroll_id else ""
        query = """{
          conversionReport(
            purchaseTimeStart: %d
            purchaseTimeEnd: %d
            limit: 100%s
          ) {
            nodes {
              purchaseTime conversionId conversionStatus
              utmContent buyerType netCommission totalCommission
              sellerCommission shopeeCommissionCapped grossCommission
              orders {
                orderId orderStatus
                items {
                  itemId itemName itemPrice actualAmount refundAmount qty
                  displayItemStatus attributionType shopId shopName
                  itemSellerCommissionRate itemShopeeCommissionRate
                  itemSellerCommission itemShopeeCommissionCapped
                  itemCommission categoryLv1Name categoryLv2Name
                }
              }
            }
            pageInfo { hasNextPage scrollId }
          }
        }""" % (start, now, scroll_arg)
        result = call(query)
        if "errors" in result:
            print(f"  ERRO: {result['errors'][0]['message']}")
            break
        data  = result.get("data", {}).get("conversionReport", {})
        nodes = data.get("nodes", [])
        pi    = data.get("pageInfo", {})
        all_nodes.extend(nodes)
        print(f"  Pagina {page}: {len(nodes)} conversoes")
        if not pi.get("hasNextPage"):
            break
        scroll_id = pi.get("scrollId")
        if not scroll_id:
            break
        time.sleep(5)
    return all_nodes

def transform(nodes):
    orders = []
    for node in nodes:
        purchase_ts = node.get("purchaseTime", 0)
        purchase_dt = datetime.fromtimestamp(purchase_ts, tz=timezone.utc)
        date_str    = purchase_dt.strftime("%Y-%m-%d")
        time_str    = purchase_dt.strftime("%Y-%m-%d %H:%M:%S")
        sub_id      = node.get("utmContent", "").rstrip("-").rstrip()
        buyer_type  = node.get("buyerType", "")
        for order in node.get("orders", []):
            order_id     = order.get("orderId", "")
            order_status = order.get("orderStatus", "")
            for item in order.get("items", []):
                attribution  = item.get("attributionType", "")
                is_same_shop = attribution == "ORDERED_IN_SAME_SHOP"
                orders.append({
                    "ID do pedido":                         order_id,
                    "Status do Pedido":                     order_status,
                    "Horario do pedido":                    time_str,
                    "Sub_id1":                              sub_id,
                    "Valor de Compra(R$)":                  item.get("actualAmount", "0"),
                    "Comissao liquida do afiliado(R$)":     node.get("netCommission", "0"),
                    "Taxa de comissao Shopee do item":      item.get("itemShopeeCommissionRate", "0%"),
                    "Taxa de comissao do vendedor do item": item.get("itemSellerCommissionRate", "0%"),
                    "Comissao Shopee(R$)":                  item.get("itemShopeeCommissionCapped", "0"),
                    "Comissao do vendedor(R$)":             item.get("itemSellerCommission", "0"),
                    "Comissao total do pedido(R$)":         node.get("totalCommission", "0"),
                    "Tipo de atribuicao":                   "Pedido na mesma loja" if is_same_shop else "Pedido em loja diferente",
                    "Nome do Item":                         item.get("itemName", ""),
                    "Status do item do afiliado":           item.get("displayItemStatus", ""),
                    "ID do item":                           str(item.get("itemId", "")),
                    "ID da loja":                           str(item.get("shopId", "")),
                    "Nome da loja":                         item.get("shopName", ""),
                    "Quantidade":                           str(item.get("qty", 1)),
                    "buyerType":                            buyer_type,
                    "attributionType":                      attribution,
                    "conversionId":                         str(node.get("conversionId", "")),
                    "conversionStatus":                     node.get("conversionStatus", ""),
                    "data":                                 date_str,
                })
    return orders

def get_commission(item_id):
    """Consulta a comissão atual de um produto via productOfferV2."""
    query = """{
      productOfferV2(itemId: %s, limit: 1) {
        nodes { itemId productName commissionRate sellerCommissionRate shopeeCommissionRate shopName priceMin }
      }
    }""" % item_id
    result = call(query)
    if "errors" in result:
        return None
    nodes = result.get("data", {}).get("productOfferV2", {}).get("nodes", [])
    return nodes[0] if nodes else None

def send_email_alert(info):
    """Dispara alerta por e-mail via EmailJS (API REST, fora do navegador)."""
    delta = info["atual_pct"] - info["baseline_pct"]
    params = {
        "product_name":     info["nome"],
        "shop_name":        info["shop_name"],
        "old_commission":   f"{info['baseline_pct']:.1f}",
        "new_commission":   f"{info['atual_pct']:.1f}",
        "delta":            f"{delta:+.1f}",
        "price":            f"{info['preco']:.2f}",
        "commission_value": f"{info['preco'] * info['atual_pct'] / 100:.2f}",
        "seller_pct":       "—",
        "shopee_pct":       "—",
        "baseline_date":    info["baseline_data"],
        "product_link":     info["link"],
    }
    payload_dict = {
        "service_id":  EMAILJS_SERVICE_ID,
        "template_id": EMAILJS_TEMPLATE_ID,
        "user_id":     EMAILJS_PUBLIC_KEY,
        "template_params": params,
    }
    if EMAILJS_PRIVATE_KEY:
        payload_dict["accessToken"] = EMAILJS_PRIVATE_KEY
    payload = json.dumps(payload_dict).encode()
    req = urllib.request.Request(
        "https://api.emailjs.com/api/v1.0/email/send",
        data=payload, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            print(f"  Alerta enviado por e-mail: {info['nome'][:40]} (HTTP {r.status})")
    except urllib.error.HTTPError as e:
        print(f"  ERRO ao enviar e-mail: {e.code} {e.read().decode()}")
    except Exception as e:
        print(f"  ERRO ao enviar e-mail: {e}")

def check_commissions(orders):
    """Verifica comissão dos produtos ativos (com pedido recente) e atualiza o baseline."""
    print("Verificando comissoes dos produtos ativos...")
    hoje = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    corte = (datetime.now(timezone.utc).timestamp() - DIAS_ATIVIDADE * 86400)
    corte_str = datetime.fromtimestamp(corte, tz=timezone.utc).strftime("%Y-%m-%d")

    # Produtos com pedido nos últimos DIAS_ATIVIDADE dias
    ativos = {}
    for o in orders:
        iid = o.get("ID do item", "")
        if not iid or o.get("data", "") < corte_str:
            continue
        ativos[iid] = {
            "nome":    o.get("Nome do Item", ""),
            "shopId":  o.get("ID da loja", ""),
        }
    print(f"  {len(ativos)} produtos com pedido nos ultimos {DIAS_ATIVIDADE} dias")

    # Carrega monitor existente
    monitor = {}
    if os.path.exists(MONITOR_FILE):
        try:
            with open(MONITOR_FILE, "r", encoding="utf-8") as f:
                monitor = json.load(f).get("produtos", {})
        except Exception:
            monitor = {}

    for item_id, meta in ativos.items():
        node = get_commission(item_id)
        time.sleep(1)  # não martelar a API
        if not node:
            continue
        atual_pct = round(float(node.get("commissionRate", 0)) * 100, 2)
        preco     = float(node.get("priceMin", 0) or 0)
        shop_name = node.get("shopName", "") or ""
        link      = f"https://shopee.com.br/product/{meta['shopId']}/{item_id}"

        existente = monitor.get(item_id)
        if not existente:
            # Primeira vez visto — trava o baseline
            monitor[item_id] = {
                "nome": meta["nome"], "shop_name": shop_name, "preco": preco,
                "baseline_pct": atual_pct, "baseline_data": hoje,
                "atual_pct": atual_pct, "atual_data": hoje,
                "alertado_para": None,
            }
            print(f"  [NOVO] {meta['nome'][:40]} — baseline travado em {atual_pct}%")
        else:
            existente["nome"]       = meta["nome"] or existente.get("nome", "")
            existente["shop_name"]  = shop_name or existente.get("shop_name", "")
            existente["preco"]      = preco or existente.get("preco", 0)
            existente["atual_pct"]  = atual_pct
            existente["atual_data"] = hoje
            delta = atual_pct - existente["baseline_pct"]
            print(f"  {meta['nome'][:40]} — baseline {existente['baseline_pct']}% -> atual {atual_pct}% ({delta:+.1f}pp)")
            if delta <= -QUEDA_MINIMA_ALERTA and existente.get("alertado_para") != atual_pct:
                send_email_alert({
                    "nome": existente["nome"], "shop_name": existente["shop_name"],
                    "preco": existente["preco"], "baseline_pct": existente["baseline_pct"],
                    "baseline_data": existente["baseline_data"], "atual_pct": atual_pct,
                    "link": link,
                })
                existente["alertado_para"] = atual_pct

    with open(MONITOR_FILE, "w", encoding="utf-8") as f:
        json.dump({
            "updated_at_br": datetime.now().strftime("%d/%m/%Y %H:%M"),
            "produtos": monitor,
        }, f, ensure_ascii=False, indent=2)
    print(f"Monitor de comissao salvo: {len(monitor)} produtos rastreados")

def main():
    print(f"Shopee Affiliate Sync - {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    print(f"Buscando {DAYS} dias de dados...")
    nodes  = fetch_all()
    orders = transform(nodes)
    output = {
        "updated_at":        int(time.time()),
        "updated_at_br":     datetime.now().strftime("%d/%m/%Y %H:%M"),
        "period_days":       DAYS,
        "total_orders":      len(orders),
        "total_conversions": len(nodes),
        "orders":            orders
    }
    with open("shopee-data.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"Concluido! Conversoes: {len(nodes)} | Itens: {len(orders)}")

    try:
        check_commissions(orders)
    except Exception as e:
        print(f"ERRO no monitor de comissao (nao interrompe o sync principal): {e}")

if __name__ == "__main__":
    main()
