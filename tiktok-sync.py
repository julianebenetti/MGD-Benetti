"""
Importador Kalodata -> Supabase (Espião TikTok Shop)

Lê os CSV/XLSX que a Juliane exporta do Kalodata e grava no Supabase, nas tabelas
tiktok_lojas e tiktok_ranking_produtos. Cada import é um snapshot do dia, então dá
pra acompanhar a evolução de GMV semana a semana.

Uso:
    python tiktok-sync.py                          # lê tudo que estiver em dados-kalodata/
    python tiktok-sync.py export.csv               # lê um arquivo específico
    python tiktok-sync.py export.csv --dry-run     # só mostra o mapeamento, não grava
    python tiktok-sync.py export.csv --periodo 30d --data 2026-09-06

Variáveis de ambiente:
    SUPABASE_URL  (default: projeto da AfiliDash)
    SUPABASE_KEY  (obrigatória — anon key ou service role)

Os números do Kalodata são ESTIMATIVA a partir de sinais públicos do TikTok.
Não são dado oficial da plataforma. A coluna fonte guarda isso.
"""
import csv
import io
import json
import os
import re
import sys
import unicodedata
import urllib.error
import urllib.request
from datetime import date, datetime
from pathlib import Path

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://tkxkrbdvcctoajuigvvv.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")
PASTA_PADRAO = "dados-kalodata"
FONTE = "kalodata"

# ── Mapeamento de colunas ────────────────────────────────────────────────
# O Kalodata muda rótulo conforme o idioma e a tela. Em vez de fixar um nome,
# a gente normaliza o cabeçalho e procura por apelido. Cabeçalho não reconhecido
# não quebra o import: entra em colunas_ignoradas pra ajustar aqui depois.

ALIASES_LOJA = {
    "loja":            ["loja", "nome da loja", "vendedor", "seller", "shop", "shop name",
                        "store", "store name", "nome do vendedor"],
    "loja_id":         ["id da loja", "shop id", "seller id", "store id"],
    "categoria":       ["categoria", "category", "categoria principal", "main category"],
    "gmv":             ["gmv", "faturamento", "receita", "revenue", "vendas em reais",
                        "valor de vendas", "sales amount", "gmv total"],
    "unidades":        ["unidades", "unidades vendidas", "itens vendidos", "vendas",
                        "units sold", "sold", "sales", "quantidade vendida"],
    "preco_medio":     ["preco medio", "ticket medio", "average price", "avg price"],
    "produtos_ativos": ["produtos", "produtos ativos", "n de produtos", "products",
                        "product count", "qtd produtos"],
    "criadores":       ["criadores", "influenciadores", "creators", "creator count"],
    "videos":          ["videos", "video count", "n de videos"],
    "crescimento_pct": ["crescimento", "crescimento gmv", "growth", "gmv growth",
                        "variacao", "crescimento %"],
    "link":            ["link", "url", "link da loja", "shop url"],
}

ALIASES_PRODUTO = {
    "produto":             ["produto", "nome do produto", "product", "product name",
                            "titulo", "title", "item"],
    "produto_id":          ["id do produto", "product id", "item id", "sku"],
    "loja":                ["loja", "nome da loja", "vendedor", "seller", "shop",
                            "shop name", "store"],
    "categoria":           ["categoria", "category", "categoria principal"],
    "preco":               ["preco", "price", "preco de venda", "valor"],
    "gmv":                 ["gmv", "faturamento", "receita", "revenue",
                            "valor de vendas", "sales amount"],
    "unidades":            ["unidades", "unidades vendidas", "itens vendidos", "vendas",
                            "units sold", "sold", "sales", "quantidade vendida"],
    "comissao_percentual": ["comissao", "comissao %", "taxa de comissao", "commission",
                            "commission rate", "commission %"],
    "comissao_reais":      ["comissao em reais", "valor da comissao", "commission amount",
                            "comissao r$"],
    "avaliacao":           ["avaliacao", "nota", "rating", "review score", "estrelas"],
    "criadores":           ["criadores", "influenciadores", "creators", "creator count"],
    "videos":              ["videos", "video count", "n de videos"],
    "crescimento_pct":     ["crescimento", "crescimento gmv", "growth", "gmv growth",
                            "variacao"],
    "link":                ["link", "url", "link do produto", "product url"],
}

CAMPOS_NUMERO = {"gmv", "preco", "preco_medio", "comissao_reais"}
CAMPOS_INTEIRO = {"unidades", "produtos_ativos", "criadores", "videos", "ranking"}
CAMPOS_PERCENTUAL = {"crescimento_pct", "comissao_percentual"}
CAMPOS_DECIMAL = {"avaliacao"}


def normalizar(texto):
    """Cabeçalho vira minúsculo, sem acento e sem pontuação, pra casar com os apelidos."""
    t = unicodedata.normalize("NFD", str(texto or ""))
    t = "".join(c for c in t if unicodedata.category(c) != "Mn").lower()
    t = t.replace("r$", " ").replace("%", " % ")
    t = re.sub(r"[^a-z0-9%]+", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def montar_mapa(cabecalhos, aliases):
    """Casa cada cabeçalho do arquivo com um campo da tabela."""
    mapa, ignoradas = {}, []
    reverso = {}
    for campo, apelidos in aliases.items():
        for apelido in apelidos:
            reverso.setdefault(normalizar(apelido), campo)
    for bruto in cabecalhos:
        chave = normalizar(bruto)
        if not chave:
            continue
        campo = reverso.get(chave)
        if campo is None:
            # tolera sufixo do Kalodata: "GMV (7 dias)", "Unidades vendidas 7d"
            for apelido, alvo in reverso.items():
                if chave.startswith(apelido + " ") or chave == apelido:
                    campo = alvo
                    break
        if campo and campo not in mapa.values():
            mapa[bruto] = campo
        elif campo is None:
            ignoradas.append(bruto)
    return mapa, ignoradas


MULTIPLICADORES = {
    "k": 1_000, "mil": 1_000,
    "m": 1_000_000, "mi": 1_000_000, "mm": 1_000_000, "milhao": 1_000_000,
    "milhoes": 1_000_000, "b": 1_000_000_000, "bi": 1_000_000_000,
}


def para_numero(valor):
    """Entende 'R$ 1.234,56', '1,2 mil', '3.4K', '12,5%', '1.234'."""
    if valor is None:
        return None
    if isinstance(valor, (int, float)):
        return float(valor)
    bruto = str(valor).strip()
    if not bruto or bruto in {"-", "--", "N/A", "n/a", "—"}:
        return None
    limpo = bruto.replace("R$", "").replace("r$", "").replace("%", "").strip()
    negativo = limpo.startswith("-")
    limpo = limpo.lstrip("+-").strip()

    sufixo = ""
    achado = re.search(r"([a-zA-Zãõç]+)\s*$", limpo)
    if achado:
        candidato = normalizar(achado.group(1)).replace(" ", "")
        if candidato in MULTIPLICADORES:
            sufixo = candidato
            limpo = limpo[: achado.start()].strip()

    somente = re.sub(r"[^\d.,]", "", limpo)
    if not somente:
        return None
    # Decide quem é separador decimal: o último que aparecer manda.
    if "," in somente and "." in somente:
        if somente.rfind(",") > somente.rfind("."):
            somente = somente.replace(".", "").replace(",", ".")
        else:
            somente = somente.replace(",", "")
    elif "," in somente:
        inteiro, _, resto = somente.rpartition(",")
        somente = f"{inteiro.replace(',', '')}.{resto}" if len(resto) in (1, 2) \
            else somente.replace(",", "")
    elif somente.count(".") > 1:
        somente = somente.replace(".", "")
    elif "." in somente:
        _, _, resto = somente.rpartition(".")
        if len(resto) == 3:  # 1.234 é mil, não 1,234
            somente = somente.replace(".", "")

    try:
        numero = float(somente)
    except ValueError:
        return None
    if sufixo:
        numero *= MULTIPLICADORES[sufixo]
    return -numero if negativo else numero


def converter(campo, valor):
    numero = para_numero(valor)
    if campo in CAMPOS_INTEIRO:
        return int(round(numero)) if numero is not None else None
    if campo in CAMPOS_NUMERO or campo in CAMPOS_PERCENTUAL or campo in CAMPOS_DECIMAL:
        return round(numero, 4) if numero is not None else None
    texto = str(valor).strip() if valor is not None else ""
    return texto or None


def ler_linhas(caminho):
    """Lê CSV (detectando o separador) ou XLSX, se openpyxl estiver disponível."""
    p = Path(caminho)
    if p.suffix.lower() in {".xlsx", ".xlsm"}:
        try:
            from openpyxl import load_workbook
        except ImportError:
            raise SystemExit(
                f"{p.name} é Excel e o openpyxl não está instalado.\n"
                "Rode: pip install openpyxl — ou exporte como CSV no Kalodata."
            )
        aba = load_workbook(p, read_only=True, data_only=True).active
        linhas = list(aba.iter_rows(values_only=True))
        if not linhas:
            return [], []
        cabecalho = [str(c) if c is not None else "" for c in linhas[0]]
        return cabecalho, [dict(zip(cabecalho, linha)) for linha in linhas[1:]]

    bruto = p.read_text(encoding="utf-8-sig", errors="replace")
    amostra = bruto[:4096]
    try:
        dialeto = csv.Sniffer().sniff(amostra, delimiters=",;\t")
        separador = dialeto.delimiter
    except csv.Error:
        separador = ";" if amostra.count(";") > amostra.count(",") else ","
    leitor = csv.DictReader(io.StringIO(bruto), delimiter=separador)
    return list(leitor.fieldnames or []), list(leitor)


def detectar_tipo(cabecalhos):
    chaves = {normalizar(c) for c in cabecalhos}
    tem_produto = any(k in chaves for k in
                      [normalizar(a) for a in ALIASES_PRODUTO["produto"]])
    if tem_produto:
        return "produtos"
    tem_loja = any(k in chaves for k in [normalizar(a) for a in ALIASES_LOJA["loja"]])
    if tem_loja:
        return "lojas"
    return None


def http(metodo, caminho, corpo=None, headers=None):
    if not SUPABASE_KEY:
        raise SystemExit("Falta a variável de ambiente SUPABASE_KEY.")
    cabecalhos = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
    }
    cabecalhos.update(headers or {})
    dados = json.dumps(corpo).encode() if corpo is not None else None
    req = urllib.request.Request(f"{SUPABASE_URL}/rest/v1/{caminho}",
                                 data=dados, headers=cabecalhos, method=metodo)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            texto = r.read().decode()
            return json.loads(texto) if texto.strip() else []
    except urllib.error.HTTPError as e:
        raise SystemExit(f"Supabase respondeu {e.code}: {e.read().decode()[:500]}")


def gravar(tabela, registros, conflito):
    if not registros:
        return 0
    salvos = 0
    for i in range(0, len(registros), 200):
        lote = registros[i:i + 200]
        http("POST", f"{tabela}?on_conflict={conflito}", lote,
             {"Prefer": "resolution=merge-duplicates,return=minimal"})
        salvos += len(lote)
    return salvos


def importar(caminho, periodo, data_ref, dry_run):
    cabecalhos, linhas = ler_linhas(caminho)
    if not linhas:
        print(f"  {Path(caminho).name}: arquivo vazio, pulei.")
        return

    tipo = detectar_tipo(cabecalhos)
    if tipo is None:
        print(f"  {Path(caminho).name}: não achei coluna de produto nem de loja.")
        print(f"     Cabeçalhos lidos: {cabecalhos}")
        return

    aliases = ALIASES_PRODUTO if tipo == "produtos" else ALIASES_LOJA
    tabela = "tiktok_ranking_produtos" if tipo == "produtos" else "tiktok_lojas"
    conflito = ("produto,loja,periodo,data_ref" if tipo == "produtos"
                else "loja,periodo,data_ref")
    obrigatorio = "produto" if tipo == "produtos" else "loja"

    mapa, ignoradas = montar_mapa(cabecalhos, aliases)
    print(f"  {Path(caminho).name} → {tabela} ({len(linhas)} linha(s))")
    for bruto, campo in mapa.items():
        print(f"     {bruto!r} → {campo}")
    if ignoradas:
        print(f"     não mapeadas: {ignoradas}")

    registros = []
    for i, linha in enumerate(linhas, start=1):
        reg = {"periodo": periodo, "data_ref": data_ref, "fonte": FONTE, "ranking": i}
        for bruto, campo in mapa.items():
            reg[campo] = converter(campo, linha.get(bruto))
        if not reg.get(obrigatorio):
            continue
        if tipo == "lojas":
            reg.setdefault("loja_id", None)
        registros.append(reg)

    print(f"     {len(registros)} linha(s) válida(s) de {len(linhas)}")
    if registros:
        print(f"     exemplo: {json.dumps(registros[0], ensure_ascii=False)[:300]}")

    if dry_run:
        print("     (dry-run: nada foi gravado)")
        return

    salvos = gravar(tabela, registros, conflito)
    http("POST", "tiktok_importacoes", [{
        "arquivo": Path(caminho).name, "tipo": tipo, "periodo": periodo,
        "data_ref": data_ref, "linhas_lidas": len(linhas), "linhas_salvas": salvos,
        "colunas_ignoradas": ignoradas,
    }], {"Prefer": "return=minimal"})
    print(f"     {salvos} linha(s) gravada(s) no Supabase.")


def main():
    args = sys.argv[1:]
    dry_run = "--dry-run" in args
    args = [a for a in args if a != "--dry-run"]

    periodo, data_ref = "7d", date.today().isoformat()
    restantes = []
    i = 0
    while i < len(args):
        if args[i] == "--periodo" and i + 1 < len(args):
            periodo = args[i + 1]; i += 2
        elif args[i] == "--data" and i + 1 < len(args):
            data_ref = datetime.strptime(args[i + 1], "%Y-%m-%d").date().isoformat()
            i += 2
        else:
            restantes.append(args[i]); i += 1

    if periodo not in {"1d", "7d", "30d", "90d"}:
        raise SystemExit("--periodo aceita 1d, 7d, 30d ou 90d.")

    arquivos = restantes or sorted(
        str(p) for p in Path(PASTA_PADRAO).glob("*")
        if p.suffix.lower() in {".csv", ".xlsx", ".xlsm"}
    )
    if not arquivos:
        raise SystemExit(
            f"Nenhum arquivo pra importar. Coloque o export do Kalodata em {PASTA_PADRAO}/ "
            "ou passe o caminho: python tiktok-sync.py export.csv"
        )

    print(f"Importando período {periodo}, data de referência {data_ref}")
    for arquivo in arquivos:
        importar(arquivo, periodo, data_ref, dry_run)
    print("Pronto.")


if __name__ == "__main__":
    main()
