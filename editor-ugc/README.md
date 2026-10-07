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
