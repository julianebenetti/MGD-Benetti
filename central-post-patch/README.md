# Limites de publicação do Instagram (Central Post)

**Problema:** o agendador do Instagram (`server.js`, `runInstagramScheduler`, roda a cada 1 min) publicava a fila inteira
assim que passava das 20h (sem ritmo nenhum) e repetia as falhas para sempre, sem contar tentativas. Com muitos vídeos
na aba Pack, o Instagram respondeu `User is performing too many actions`.

**Solução:** `limite-instagram.js` prepara uma versão nova do `server.js` com limites; `fila-instagram.js` para e libera a fila.

## Passo a passo no VPS (nesta ordem)
```
mkdir -p /home/benetti/central-post-patch && cd /home/benetti/central-post-patch
for f in limite-instagram.js fila-instagram.js; do curl -fsSLO https://raw.githubusercontent.com/julianebenetti/MGD-Benetti/claude/eager-wozniak-yxsgfc/central-post-patch/$f; done
```
1. **Preparar** (não instala; só gera e confere a sintaxe): `node limite-instagram.js`
2. **Ver a fila**: `node fila-instagram.js status`
3. **Parar o serviço, segurar a fila, instalar e ligar** (o serviço fica parado ~1 minuto; a Central de Respostas pausa junto):
   ```
   sudo systemctl stop central-post
   node fila-instagram.js segurar --aplicar
   B=/opt/central-post/backup-antes-limite-ig-$(date +%Y%m%d-%H%M%S) && sudo mkdir -p $B && sudo cp /opt/central-post/server.js $B/server.js
   sudo cp /home/benetti/staged-limite-ig/server.js /opt/central-post/server.js
   sudo systemctl start central-post
   ```
4. **Conferir**: `journalctl -u central-post --since "5 min ago" --no-pager | tail`
5. **Depois de 24–48 h** (e o Status da conta do Instagram sem restrição), solte uns poucos por dia:
   `sudo systemctl stop central-post && node fila-instagram.js liberar 5 --aplicar && sudo systemctl start central-post`

**Desfazer:** `sudo cp $B/server.js /opt/central-post/server.js && sudo systemctl restart central-post`

## Regras novas (ajustáveis por variável de ambiente no serviço)
| Variável | Padrão | O que faz |
|---|---|---|
| `IG_MAX_POR_DIA` | 6 | máximo de posts automáticos por conta por dia |
| `IG_INTERVALO_MIN` | 60 | espaço mínimo entre posts da mesma conta (e no máx. 1 por rodada) |
| `IG_MAX_TENTATIVAS` | 3 | depois de N falhas o item para (fica na fila, com o erro anotado) |
| `IG_PAUSA_HORAS` | 6 | pausa da conta ao receber "too many actions", spam ou limite |

A pausa fica na memória do serviço: se ele reiniciar, a pausa some (as falhas por item continuam contadas no `tasks.json`).
Posts agendados por data/hora também respeitam o teto diário e o espaçamento.
