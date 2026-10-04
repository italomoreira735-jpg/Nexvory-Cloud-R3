# Nexvory Cloud R3 — FLOW R39 + Deriv DEMO

R3 tira o Android do caminho crítico. O Android será cliente/painel; o worker Cloud mantém mercado, estratégia, gerenciamento e execução.

## Segurança R3
- REAL hard-blocked no `DerivAdapter`.
- DEMO nasce desligada: `NEXVORY_ALLOW_DEMO_EXECUTION=false`.
- Nenhum token é incluído neste pacote.
- OTP e URL autenticada são obtidos no servidor e nunca devem ser logados.
- Uma compra de resposta incerta não é reenviada automaticamente.
- Idempotência é reservada antes do `buy`.

## Fluxo
`ws/public -> ticks -> FlowR39Adapter -> ExecutionCoordinator -> proposal -> buy DEMO -> proposal_open_contract -> RiskService`

O FLOW R39 permanece no snapshot `app/strategies/flow_r39_core.py` e não conhece Android nem Deriv.

## Persistência
`SqliteRepository` prova persistência/restart local sem dependências extras. O Docker Compose traz PostgreSQL + Redis para a implantação Cloud; a interface de repositório continua separada da estratégia.

## Validar no Termux/PRoot
```bash
cd /root/Nexvory-Cloud-R3
source .venv/bin/activate
python -m pip install pytest==8.4.1
bash scripts/validar_r3.sh
```

## Implantar no servidor Linux
Use Python 3.12/Docker. Não use Python 3.14 do Android como servidor de produção.
```bash
cp .env.example .env
# preencher segredos SOMENTE no servidor
# manter NEXVORY_ALLOW_DEMO_EXECUTION=false no primeiro boot
docker compose up -d --build
```

## API Deriv nova usada na R3
- REST health: `GET https://api.derivws.com/v1/health`
- Public WS: `wss://api.derivws.com/trading/v1/options/ws/public`
- OTP: `POST /trading/v1/options/accounts/{accountId}/otp`
- Proposta: `proposal` com `underlying_symbol`
- Compra: `buy` por proposal id
- Resultado: `proposal_open_contract` com subscribe e limpeza da subscription

## Ainda não é produção comercial
Faltam Secret Manager/Vault multi-tenant, `PostgresRepository` efetivo, Redis lease ligado ao runtime, login/licença, observabilidade e deploy remoto. As fronteiras já estão definidas.
