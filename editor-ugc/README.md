# Editor UGC — corta trechos com a modelo parada

Corta automaticamente as partes dos vídeos de IA em que a modelo fica estática,
pra o vídeo parecer gravado por uma pessoa real (estilo UGC no TikTok).
Processa uma pasta inteira de uma vez.

## Instalar (uma vez só)
Precisa só de **Python 3** e **ffmpeg**:
- **Windows:** `winget install Python.Python.3.12` e `winget install Gyan.FFmpeg`
- **Mac:** `brew install python ffmpeg`
- **VPS (Ubuntu):** `sudo apt install python3 ffmpeg`

## Usar
```bash
# 1) Ver o que ele cortaria (não gera vídeo, só mostra o gráfico de movimento)
python3 cortar_parados.py "C:/Videos/tiktok" --analisar

# 2) Editar a pasta toda
python3 cortar_parados.py "C:/Videos/tiktok"
```
Os vídeos prontos vão pra `editados/` dentro da pasta, com o nome `<original>_editado.mp4`,
e um `relatorio.csv` dizendo quanto foi cortado em cada um.

## Ajustes
| Opção | Padrão | O que faz |
|---|---|---|
| `--limiar` | 1.0 | Quanto de movimento conta como "parada". **Maior = corta mais.** Se ele não cortar paradas onde a modelo só pisca/respira, suba pra 1.5–2. Se cortar demais, desça pra 0.6. |
| `--min-parado` | 0.5 | Só corta paradas com pelo menos X segundos. |
| `--folga` | 0.1 | Segundos de parada mantidos em volta do corte (deixa o corte menos seco). |
| `--min-final` | 3 | Não salva se o vídeo final ficar menor que X segundos. |
| `--crf` | 18 | Qualidade (menor = melhor/arquivo maior). |

O áudio é cortado junto com o vídeo (com um fade de 30 ms pra não estalar).
Se a narração estiver por cima da parte parada, ela também sai — nesse caso é melhor
editar sem áudio e colocar a narração/música depois.

---

# Robô do Telegram (jeito mais fácil)

Você manda ou encaminha os vídeos pro seu robô no Telegram e ele devolve cada um
já editado. Ele roda 24h no VPS da Hostinger.

## Instalação (uma vez só)
1. **Criar o robô:** no Telegram, abra o **@BotFather** → `/newbot` → escolha um nome
   e um usuário terminado em `bot`. Guarde o **token** que ele te der.
2. **Descobrir seu ID:** mande `/start` pro **@userinfobot** e anote o número `Id`.
3. **Instalar no VPS:** no hPanel → VPS → **Terminal** (ou via SSH como root), cole:
   ```bash
   curl -fsSL https://raw.githubusercontent.com/julianebenetti/MGD-Benetti/claude/ugc-tiktok-video-editing-7d11hx/editor-ugc/instalar-bot.sh | bash
   ```
   Ele vai pedir o token e o seu ID. No fim deve aparecer **✅ Robô rodando!**
4. Abra o seu robô no Telegram e mande `/start`.

## Uso
- Mande ou **encaminhe** os vídeos (vários de uma vez também funciona; ele faz um por vez).
- Ele responde cada vídeo com a versão editada e a legenda `✂️ N corte(s) — 12.0s → 9.4s`.
- `/limiar 1.5` → corta mais (se ainda sobrar parada). `/limiar 0.7` → corta menos.
- `/minparado 0.3` → corta também paradas mais curtas.
- `/config` → mostra os ajustes atuais.

Limite: o Telegram só deixa robôs baixarem vídeos de até **20 MB**.

## Manutenção (no terminal do VPS)
- Ver se está rodando / erros: `journalctl -u editor-ugc -n 50`
- Reiniciar: `systemctl restart editor-ugc`
- Atualizar o código: rodar o mesmo comando `curl ... | bash` de novo
- Trocar token ou liberar outra pessoa: `nano /etc/editor-ugc.env` e depois `systemctl restart editor-ugc`
