# AfiliDash no VPS — funções que eram da Netlify

**Problema (achado em 18Nov26):** a AfiliDash chama `/.netlify/functions/sync`, `config`, `query`, `shopee` e `/api/comissao`.
Essas funções só existiam na Netlify. Quando a AfiliDash foi para o VPS da Hostinger (fim de Jul26), os endereços passaram
a não existir e nada mais foi gravado no Supabase — `sync_logs`/`sync_control` param em **25Jul26**.

**Solução:** `servidor.js` roda no VPS as mesmas funções do repositório `julianebenetti/afilidash` (pasta `netlify/functions`,
sem alterar nada), nos mesmos endereços, e também o `comissao-scheduled` 4x/dia (8h, 12h, 16h, 20h). O Nginx do site da
AfiliDash ganha só `location /.netlify/functions/` e `location /api/` apontando para ele (cópia do original em
`/root/nginx-afilidash-backup.conf`; se o Nginx recusar, volta sozinho).

## Instalar / atualizar (terminal da Hostinger)
```
curl -fsSL https://raw.githubusercontent.com/julianebenetti/MGD-Benetti/claude/admiring-dirac-ku5zlh/afilidash-vps/instalar.sh | bash
```
Na 1ª vez ele para pedindo a `SUPABASE_KEY` (chave **service_role**: Supabase → Settings → API — a mesma que estava nas
variáveis da Netlify) em `/opt/afilidash-vps/afilidash-vps/.env`. Depois rode de novo.

Logs: `journalctl -u afilidash-funcoes -f`
