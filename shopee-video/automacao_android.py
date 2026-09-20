#!/usr/bin/env python3
"""
Automacao dos passos dentro do app da Shopee, via ADB.

Roda no computador e conversa com o celular ligado por cabo ou por Wi-Fi.
Faz o que antes era feito na mao: manda o video para a galeria, abre o
produto, favorita, entra na area de video, escolhe o video, cola a legenda,
vincula o produto pelo "Adicionar Produto", toca em "Feito" e salva o
rascunho.

Em vez de coordenadas fixas, cada toque procura o elemento pelo texto que
aparece na tela. Os textos ficam em mapa-telas.json, entao um rotulo novo
do app se resolve editando aquele arquivo.

Quando nao encontra algo, a automacao para, salva um print e o mapa da tela
em evidencias/, e diz quais textos estavam visiveis. E esse dump que serve
para calibrar.

Uso:
  python3 automacao_android.py --post saida/2026-09-20_vestido/info.json
  python3 automacao_android.py --post ... --simular      # so mostra o plano
  python3 automacao_android.py --post ... --confirmar    # pausa a cada passo
  python3 automacao_android.py --post ... --postar       # posta em vez de rascunho
"""
import argparse
import base64
import json
import os
import re
import subprocess
import sys
import time
import unicodedata
import xml.etree.ElementTree as ET

PASTA = os.path.dirname(os.path.abspath(__file__))
MAPA = os.path.join(PASTA, "mapa-telas.json")
PACOTE_SHOPEE = "com.shopee.br"
TECLADO_ADB = "com.android.adbkeyboard/.AdbIME"
DESTINO_VIDEO = "/sdcard/Movies"


def sem_acento(texto):
    base = unicodedata.normalize("NFD", (texto or "").lower())
    return "".join(c for c in base if unicodedata.category(c) != "Mn")


class No:
    """Um elemento da tela, com o retangulo que ele ocupa."""

    def __init__(self, elemento):
        self.texto = elemento.get("text", "")
        self.desc = elemento.get("content-desc", "")
        self.id = elemento.get("resource-id", "")
        self.classe = elemento.get("class", "")
        self.clicavel = elemento.get("clickable") == "true"
        self.editavel = "EditText" in self.classe
        achado = re.findall(r"\d+", elemento.get("bounds", ""))
        self.caixa = [int(v) for v in achado] if len(achado) == 4 else [0, 0, 0, 0]

    @property
    def centro(self):
        x1, y1, x2, y2 = self.caixa
        return (x1 + x2) // 2, (y1 + y2) // 2

    @classmethod
    def simulado(cls, chave):
        """Usado no modo simulacao, onde nao ha tela de verdade para ler."""
        falso = cls.__new__(cls)
        falso.texto = falso.desc = falso.id = ""
        falso.classe = f"simulado:{chave}"
        falso.clicavel = True
        falso.editavel = True
        falso.caixa = [0, 0, 0, 0]
        return falso

    @property
    def rotulo(self):
        return self.texto or self.desc or self.id.split("/")[-1] or self.classe

    def __repr__(self):
        return f"<No {self.rotulo!r} {self.caixa}>"


class Tela:
    """A arvore de elementos da tela atual."""

    def __init__(self, xml):
        self.nos = [No(e) for e in ET.fromstring(xml).iter("node")]

    def achar(self, textos=(), ids=(), somente_clicavel=False, editavel=False):
        """Primeiro elemento cujo texto, descricao ou id bate com a busca."""
        alvos = [sem_acento(t) for t in textos if t]
        pedacos = [i.lower() for i in ids if i]
        candidatos = []
        for no in self.nos:
            if editavel and not no.editavel:
                continue
            if somente_clicavel and not no.clicavel:
                continue
            visivel = sem_acento(f"{no.texto} {no.desc}")
            if alvos and any(alvo and alvo in visivel for alvo in alvos):
                candidatos.append((0 if no.clicavel else 1, no))
                continue
            if pedacos and any(p in no.id.lower() for p in pedacos):
                candidatos.append((2, no))
        if not candidatos:
            return None
        candidatos.sort(key=lambda par: par[0])
        return candidatos[0][1]

    def visiveis(self, limite=40):
        vistos = []
        for no in self.nos:
            rotulo = (no.texto or no.desc).strip()
            if rotulo and rotulo not in vistos:
                vistos.append(rotulo)
        return vistos[:limite]


class Dispositivo:
    """O celular do outro lado do cabo."""

    def __init__(self, serial=None, adb="adb", simular=False, evidencias="evidencias"):
        self.adb_bin = adb
        self.serial = serial
        self.simular = simular
        self.evidencias = evidencias
        os.makedirs(evidencias, exist_ok=True)
        self.passo_atual = 0

    def _executar(self, args, binario=False, tempo=60):
        comando = [self.adb_bin]
        if self.serial:
            comando += ["-s", self.serial]
        comando += args
        resultado = subprocess.run(comando, capture_output=True, timeout=tempo)
        if resultado.returncode != 0:
            erro = resultado.stderr.decode("utf-8", "ignore").strip()
            raise RuntimeError(f"adb {' '.join(args[:2])} falhou: {erro}")
        return resultado.stdout if binario else resultado.stdout.decode("utf-8", "ignore")

    def conferir(self):
        """Confirma que tem um aparelho conectado e autorizado."""
        saida = self._executar(["devices"])
        linhas = [l for l in saida.splitlines()[1:] if l.strip()]
        conectados = [l.split()[0] for l in linhas if l.endswith("device")]
        se_autorizando = [l for l in linhas if l.endswith("unauthorized")]
        if se_autorizando:
            raise RuntimeError(
                "O celular apareceu mas nao esta autorizado. Desbloqueie a tela e "
                "aceite o aviso de depuracao USB."
            )
        if not conectados:
            raise RuntimeError(
                "Nenhum celular conectado. Ligue o cabo, ative as Opcoes do "
                "desenvolvedor e a Depuracao USB."
            )
        return conectados

    def shell(self, comando):
        return self._executar(["shell", comando])

    def enviar_video(self, caminho):
        """Copia o video para a galeria e avisa o Android para indexar."""
        nome = os.path.basename(caminho)
        destino = f"{DESTINO_VIDEO}/{nome}"
        if self.simular:
            return destino
        self._executar(["push", caminho, destino], tempo=600)
        self.shell(
            "am broadcast -a android.intent.action.MEDIA_SCANNER_SCAN_FILE "
            f"-d file://{destino}"
        )
        return destino

    def abrir_url(self, url):
        if self.simular:
            return
        self.shell(
            "am start -a android.intent.action.VIEW "
            f'-d "{url}" {PACOTE_SHOPEE}'
        )

    def tela(self):
        """Tira o mapa da tela atual com o uiautomator."""
        if self.simular:
            return Tela("<hierarchy></hierarchy>")
        self.shell("uiautomator dump /sdcard/tela.xml")
        return Tela(self._executar(["shell", "cat", "/sdcard/tela.xml"]))

    def tocar(self, x, y):
        if not self.simular:
            self.shell(f"input tap {x} {y}")

    def tocar_no(self, no):
        x, y = no.centro
        self.tocar(x, y)

    def deslizar(self, para="cima"):
        if self.simular:
            return
        if para == "cima":
            self.shell("input swipe 540 1500 540 700 320")
        else:
            self.shell("input swipe 540 700 540 1500 320")

    def voltar(self):
        if not self.simular:
            self.shell("input keyevent 4")

    def tem_teclado_adb(self):
        if self.simular:
            return True
        return "adbkeyboard" in self.shell("pm list packages").lower()

    def digitar(self, texto):
        """
        Escreve no campo em foco.

        Com o ADBKeyBoard instalado o texto vai inteiro, com acento e emoji.
        Sem ele o Android so aceita ASCII, entao acento e emoji caem fora e
        a automacao avisa.
        """
        if self.simular:
            return True
        if self.tem_teclado_adb():
            anterior = self.shell("settings get secure default_input_method").strip()
            self.shell(f"ime set {TECLADO_ADB}")
            time.sleep(0.6)
            codificado = base64.b64encode(texto.encode("utf-8")).decode()
            self.shell(f"am broadcast -a ADB_INPUT_B64 --es msg {codificado}")
            time.sleep(0.8)
            if anterior and "adbkeyboard" not in anterior.lower():
                self.shell(f"ime set {anterior}")
            return True
        limpo = "".join(c for c in sem_acento(texto) if ord(c) < 128)
        for linha in limpo.split("\n"):
            escapado = linha.replace(" ", "%s").replace("'", "")
            self.shell(f"input text '{escapado}'")
            self.shell("input keyevent 66")
        return False

    def print_tela(self, nome):
        if self.simular:
            return None
        self.passo_atual += 1
        destino = os.path.join(self.evidencias, f"{self.passo_atual:02d}_{nome}.png")
        self.shell("screencap -p /sdcard/print.png")
        self._executar(["pull", "/sdcard/print.png", destino])
        return destino


def carregar_mapa(caminho=None):
    with open(caminho or MAPA, encoding="utf-8") as arq:
        return json.load(arq)


def procurar(dispositivo, chave, mapa, tentativas=3, rolando=True, editavel=False):
    """
    Procura um elemento da tela, rolando a pagina se nao achar de cara.

    Devolve o No ou None. Quem chama decide se para ou segue.
    """
    if dispositivo.simular:
        return No.simulado(chave)
    regra = mapa.get(chave, {})
    for tentativa in range(tentativas):
        tela = dispositivo.tela()
        no = tela.achar(regra.get("texto", []), regra.get("id", []),
                        editavel=editavel)
        if no:
            return no
        if rolando and tentativa < tentativas - 1:
            dispositivo.deslizar("cima")
            time.sleep(0.8)
    return None


def primeiro_da_galeria(tela, altura_minima=200):
    """
    O video recem-enviado e o mais recente, entao fica na primeira posicao.

    A galeria mostra miniaturas sem texto, entao a escolha e pela posicao:
    o item mais acima e mais a esquerda da grade. O print do passo seguinte
    serve para voce conferir que pegou o certo.
    """
    candidatos = []
    for no in tela.nos:
        x1, y1, x2, y2 = no.caixa
        largura, altura = x2 - x1, y2 - y1
        if largura < altura_minima or altura < altura_minima:
            continue
        if not (no.clicavel or "Image" in no.classe):
            continue
        if y1 < 150:  # barra de cima
            continue
        candidatos.append(((y1 // 50, x1), no))
    if not candidatos:
        return None
    candidatos.sort(key=lambda par: par[0])
    return candidatos[0][1]


class Parou(Exception):
    """A automacao nao achou o que precisava e guardou as evidencias."""


def exigir(dispositivo, chave, mapa, descricao, **extras):
    no = procurar(dispositivo, chave, mapa, **extras)
    if no:
        return no
    print_feito = dispositivo.print_tela(f"nao_achei_{chave}")
    tela = dispositivo.tela()
    raise Parou(
        f"Nao achei '{descricao}' na tela.\n"
        f"  print: {print_feito}\n"
        f"  textos visiveis: {', '.join(tela.visiveis(20)) or '(nenhum)'}\n"
        f"  conserto: acrescente o rotulo certo em mapa-telas.json > {chave}"
    )


def publicar(post, dispositivo, mapa, opcoes):
    """Executa os passos do app e devolve o que aconteceu em cada um."""
    feitos = []

    def registrar(titulo, detalhe=""):
        feitos.append({"passo": titulo, "detalhe": detalhe})
        print(f"  ✔ {titulo}" + (f" — {detalhe}" if detalhe else ""))
        if opcoes.confirmar and not opcoes.simular:
            input("    [enter] para o proximo passo, ctrl+c para parar ")

    def esperar(segundos=1.6):
        if not opcoes.simular:
            time.sleep(segundos)

    registrar("Salvar o video na galeria",
              dispositivo.enviar_video(post["video"]))

    dispositivo.abrir_url(post["link_original"])
    esperar(4)
    registrar("Abrir o produto no app da Shopee", post["link_original"])
    dispositivo.print_tela("produto")

    favorito = procurar(dispositivo, "favoritar", mapa, tentativas=2, rolando=False)
    if favorito:
        dispositivo.tocar_no(favorito)
        esperar()
        registrar("Favoritar o produto")
    else:
        registrar("Favoritar o produto", "botao nao encontrado, favorite na mao")

    dispositivo.tocar_no(exigir(dispositivo, "area_video", mapa, "a area de video"))
    esperar(2.5)
    registrar("Entrar na area de video")

    galeria = procurar(dispositivo, "galeria", mapa, tentativas=2)
    if galeria:
        dispositivo.tocar_no(galeria)
        esperar(2)
    registrar("Abrir a galeria")
    dispositivo.print_tela("galeria")

    if not opcoes.simular:
        item = primeiro_da_galeria(dispositivo.tela())
        if not item:
            dispositivo.print_tela("galeria_sem_itens")
            raise Parou(
                "Abri a galeria mas nao reconheci as miniaturas.\n"
                "  Toque no video que acabou de chegar e rode de novo com\n"
                "  --continuar, que eu sigo da legenda em diante."
            )
        dispositivo.tocar_no(item)
        esperar(2)
        dispositivo.print_tela("video_escolhido")
    registrar("Escolher o video",
              "peguei o mais recente da galeria, confira o print")

    return feitos + continuar(post, dispositivo, mapa, opcoes)


def continuar(post, dispositivo, mapa, opcoes):
    """Segue do editor em diante, com o video ja escolhido na tela."""
    feitos = []

    def registrar(titulo, detalhe=""):
        feitos.append({"passo": titulo, "detalhe": detalhe})
        print(f"  ✔ {titulo}" + (f" — {detalhe}" if detalhe else ""))
        if opcoes.confirmar and not opcoes.simular:
            input("    [enter] para o proximo passo, ctrl+c para parar ")

    def esperar(segundos=1.6):
        if not opcoes.simular:
            time.sleep(segundos)

    avancar = procurar(dispositivo, "proximo", mapa, tentativas=1, rolando=False)
    if avancar:
        dispositivo.tocar_no(avancar)
        esperar(2)
        registrar("Avancar para a tela de edicao")

    campo = exigir(dispositivo, "legenda", mapa, "o campo de legenda", editavel=True)
    dispositivo.tocar_no(campo)
    esperar(1)
    completo = dispositivo.digitar(post["legenda"])
    dispositivo.voltar()
    esperar()
    registrar("Adicionar legenda",
              "texto completo" if completo else
              "sem acento e sem emoji, instale o ADBKeyBoard para o texto inteiro")

    dispositivo.tocar_no(
        exigir(dispositivo, "adicionar_produto", mapa, "o botao Adicionar Produto"))
    esperar(2)
    registrar("Tocar em Adicionar Produto")

    busca = procurar(dispositivo, "busca_produto", mapa, tentativas=2)
    if busca and post.get("termo_busca"):
        dispositivo.tocar_no(busca)
        esperar(1)
        dispositivo.digitar(post["termo_busca"])
        esperar(2.5)
        registrar("Localizar o produto na lista", post["termo_busca"])
    else:
        registrar("Localizar o produto na lista", "sem campo de busca, role a lista")

    dispositivo.print_tela("lista_produtos")
    dispositivo.tocar_no(
        exigir(dispositivo, "botao_adicionar", mapa, "o botao Adicionar do produto"))
    esperar(2)
    registrar("Tocar em Adicionar")

    dispositivo.print_tela("produto_vinculado")
    registrar("Conferir as informacoes do produto", "print salvo para voce olhar")

    dispositivo.tocar_no(exigir(dispositivo, "feito", mapa, "o botao Feito"))
    esperar(2)
    registrar("Tocar em Feito")

    chave = "postar" if opcoes.postar else "rascunho"
    rotulo = "Postar" if opcoes.postar else "Salvar rascunho"
    botao = procurar(dispositivo, chave, mapa, tentativas=3)
    if not botao:
        dispositivo.print_tela("fim")
        raise Parou(
            f"Cheguei com tudo pronto mas nao achei o botao '{rotulo}'.\n"
            "  O post esta montado na tela, e so tocar voce mesma."
        )
    dispositivo.tocar_no(botao)
    esperar(3)
    dispositivo.print_tela("publicado")
    registrar(rotulo)
    return feitos


def carregar_post(caminho):
    """Aceita o info.json de um post ou uma entrada do posts.json."""
    with open(caminho, encoding="utf-8") as arq:
        dados = json.load(arq)
    if isinstance(dados, list):
        dados = dados[0]
    pasta = os.path.dirname(os.path.abspath(caminho))
    video = dados.get("video")
    if isinstance(video, dict):
        video = video.get("saida")
    elif video:
        video = os.path.join(os.path.dirname(pasta), video)
    legenda_texto = dados.get("legenda")
    if isinstance(legenda_texto, dict):
        legenda_texto = legenda_texto.get("texto")
    return {
        "video": video,
        "legenda": legenda_texto,
        "link_original": dados.get("link_original"),
        "termo_busca": dados.get("termo_busca"),
        "produto": (dados.get("produto") or {}).get("nome"),
    }


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--post", required=True, help="info.json do post")
    p.add_argument("--continuar", action="store_true",
                   help="segue do editor, com o video ja escolhido na tela")
    p.add_argument("--simular", action="store_true",
                   help="mostra o plano sem tocar no celular")
    p.add_argument("--confirmar", action="store_true",
                   help="pausa antes de cada passo")
    p.add_argument("--postar", action="store_true",
                   help="posta de verdade; sem isso salva rascunho")
    p.add_argument("--serial", help="serial do aparelho, se houver mais de um")
    p.add_argument("--adb", default="adb", help="caminho do adb")
    p.add_argument("--mapa", help="outro mapa-telas.json")
    p.add_argument("--evidencias", default="evidencias",
                   help="pasta dos prints de cada passo")
    opcoes = p.parse_args()

    post = carregar_post(opcoes.post)
    mapa = carregar_mapa(opcoes.mapa)
    dispositivo = Dispositivo(opcoes.serial, opcoes.adb, opcoes.simular,
                              opcoes.evidencias)

    print(f"📱 {post['produto'] or post['link_original']}")
    if opcoes.simular:
        print("   modo simulacao: nada e tocado no celular")
    else:
        print(f"   aparelhos: {', '.join(dispositivo.conferir())}")
        if not dispositivo.tem_teclado_adb():
            print("   ⚠️  sem ADBKeyBoard: a legenda vai sem acento e sem emoji")

    try:
        if opcoes.continuar:
            continuar(post, dispositivo, mapa, opcoes)
        else:
            publicar(post, dispositivo, mapa, opcoes)
    except Parou as parada:
        print(f"\n⏸️  {parada}")
        return 2
    print("\n✅ fim")
    return 0


if __name__ == "__main__":
    sys.exit(main())
