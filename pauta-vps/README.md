# 📅 Minha Agenda no VPS (com senha)

Publica `minha-pauta.html` em `https://posts.descontoirresistivel.com.br/pauta/` protegida por usuário e senha, no mesmo
endereço do histórico do robô do Facebook (`/facebook/postados.json`). É isso que faz a aba **📜 Postados** funcionar
(a agenda publicada no Claude não consegue buscar dados de fora).

## Instalar (uma vez) e atualizar
```
curl -fsSL https://raw.githubusercontent.com/julianebenetti/MGD-Benetti/claude/eager-wozniak-yxsgfc/pauta-vps/instalar.sh | sudo bash
```
Ele baixa a agenda, cria a senha (usuário `Benetti`; só na primeira vez) e gera `/etc/nginx/snippets/pauta.conf`.
Depois é preciso **uma vez** acrescentar `include /etc/nginx/snippets/pauta.conf;` dentro do `server { }` HTTPS do site e rodar
`sudo nginx -t && sudo systemctl reload nginx`. Para atualizar a agenda depois, é só rodar o mesmo comando de novo.

## Trocar os dados do Claude para o VPS
Os dados da agenda (o que você marcou) ficam no navegador de cada endereço. Na agenda antiga: **Atividades → Copiar backup**.
Na do VPS: **Atividades → Restaurar backup** e colar.

## Segurança
- A senha fica só como hash em `/etc/nginx/.htpasswd-pauta`. Use HTTPS (o site já usa).
- O arquivo `postados.json` não tem tokens nem caminhos de arquivo; ele traz produto, sub-ID, link e link do post.
