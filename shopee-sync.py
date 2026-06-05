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
                    "Nome da loja":                         item.get("shopName", ""),
                    "Quantidade":                           str(item.get("qty", 1)),
                    "buyerType":                            buyer_type,
                    "attributionType":                      attribution,
                    "conversionId":                         str(node.get("conversionId", "")),
                    "conversionStatus":                     node.get("conversionStatus", ""),
                    "data":                                 date_str,
                })
    return orders

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

if __name__ == "__main__":
    main()
