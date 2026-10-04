# Migração R39 -> Nexvory Cloud R2

## O que foi preservado

O cálculo do `FlowMotor` do R39 foi copiado sem alteração para `app/strategies/flow_r39_core.py`.
Ele continua responsável por candle M1, padrão de impulso/correção, confirmação de rompimento,
veto M5 quando disponível e emissão de `SINAL`/`RECUSADO`.

## O que saiu da estratégia

- `FlowFeedIndependente`: passa a pertencer à camada Market Data/BrokerAdapter.
- `nexvory_flow_exec_demo.py`: sua responsabilidade passa ao `ExecutionCoordinator`.
- Android/Chaquopy/ForegroundService: não fazem parte do servidor.
- Credenciais/tokens: não entram na estratégia.

## Segurança da R2

A R2 não envia ordem pela Deriv. O `DerivAdapter.execute()` continua bloqueado.
O `DemoBrokerAdapter` permite validar estratégia, estados, idempotência e isolamento sem risco financeiro.

## Próxima etapa

R3: persistência PostgreSQL, cofre de credenciais, Market Data compartilhado por broker,
reconciliação de ordens e integração Deriv DEMO ponta a ponta no servidor.
