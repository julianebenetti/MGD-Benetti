# Copiador de grupo Telegram → Telegram

1. Em https://my.telegram.org > *API development tools*, crie um app e anote `api_id` e `api_hash`.
2. `pip install -r requirements.txt`
3. `cp .env.example .env` e preencha `TG_API_ID` e `TG_API_HASH`.
4. `python telegram_copiador.py --listar` (entra com telefone + código) e copie os IDs
   do grupo de origem e de destino para `TG_ORIGEM` / `TG_DESTINO` no `.env`.
5. `python telegram_copiador.py` — a partir daí cada mensagem nova da origem é copiada ao destino.

## Rodar 24h no VPS
Crie `/etc/systemd/system/tg-copiador.service`:

    [Service]
    WorkingDirectory=/caminho/telegram-copiador
    ExecStart=/usr/bin/python3 telegram_copiador.py
    Restart=always

    [Install]
    WantedBy=multi-user.target

Depois: `systemctl enable --now tg-copiador`.

**Atenção:** o arquivo `*.session` dá acesso total à sua conta — nunca commitar nem compartilhar.
Grupos com "restringir salvamento de conteúdo" podem bloquear a cópia de mídia.
