---
id: system-design-order-service
title: "Projeto de sistema: pedidos, reserva de estoque e pagamentos"
description: "Projete checkout com reserva atômica de estoque, idempotência durável, outbox transacional e recuperação segura de pagamentos."
category: system-design
difficulty: advanced
updated: 2026-10-09
prerequisites: [system-design-process, storage-selection, asynchronous-messaging, transactional-indexing-isolation]
sources:
  - {title: "PostgreSQL — Transaction Isolation", url: "https://www.postgresql.org/docs/current/transaction-iso.html", kind: "official database documentation"}
  - {title: "AWS Builders Library — Making retries safe with idempotent APIs", url: "https://aws.amazon.com/builders-library/making-retries-safe-with-idempotent-APIs/", kind: "original engineering guidance"}
---
Um serviço de pedidos é um **estudo completo de System Design** porque checkout aparentemente simples atravessa três autoridades: catálogo, estoque e provedor externo de pagamento. Uma resposta HTTP de sucesso precisa ter significado exato. Aceitar solicitação não equivale a reservar estoque, autorizar pagamento, capturar dinheiro ou expedir produto. Arquitetura confiável nomeia essas fronteiras e determina o comportamento quando o processo cai entre duas operações [1][2].

## Requisitos, invariantes e cenário

Considere loja virtual hipotética de itens físicos. Clientes enviam cesta, recebem ID de pedido, consultam situação e cancelam quando permitido. O sistema nunca deve reservar mais unidades de SKU do que estão disponíveis na autoridade de estoque. Repetir checkout com a mesma chave de operação do cliente deve devolver o **mesmo pedido lógico**, sem nova reserva. Pagamento pode ficar indisponível; reserva confirmada deve terminar em conclusão ou liberação conforme política.

Ficam fora de escopo tributos por jurisdição, câmbio multimoedas, vários vendedores e remessas parciais. São regras de produto relevantes, não detalhes a inventar silenciosamente. Defina arredondamento, moeda e promessa de frete antes de implementar. Máquina de estados integra o contrato: criado → reservado → pagamento_pendente → confirmado ou cancelado; envio possui transições próprias. Cada mudança exige guardas e histórico auditável.

## Capacidade e hipóteses não funcionais

Suponha **864 mil tentativas de checkout/dia** e pico trinta vezes a média. Isso gera média de 10 tentativas/s e pico hipotético de **300 tentativas/s**. Com três linhas por pedido aceito, pode haver aproximadamente 900 verificações de estoque de linha/s no pico, além de escritas de pedido, idempotência e outbox. Os números não incluem retries abandonados, callbacks de pagamento e eventos logísticos. Com 2 KiB de registros lógicos por pedido e 864 mil pedidos bem-sucedidos/dia, seriam cerca de 1,65 GiB/dia e 602 GiB/ano antes de índices, WAL, réplicas e backups.

SLOs hipotéticos: 99,9% das solicitações de checkout elegíveis alcançam **resultado durável reservado ou rejeitado** em até 750 ms no servidor; 99% das autorizações com provedor saudável terminam em dois minutos. Defina explicitamente como panes dos provedores são contabilizadas. Acompanhe taxa de compra concluída e incidentes de cobrança duplicada separadamente da latência HTTP.

## Arquitetura e limites de autoridade

Comece com cliente → Checkout API autenticada → **autoridade transacional de pedidos e estoque**. Essa autoridade controla disponibilidade, reservas, identidade de pedido e outbox. O publisher envia comandos de pagamento a fila durável. Workers consultam PSP usando chave idempotente estável do provedor. Consumidor de resultados avança pedido e publica evento de fulfillment. Catálogo e busca podem estar desatualizados, mas reserva exige conferência atual na autoridade de estoque.

![Transação de checkout controla pedido e estoque; pagamento e expedição seguem etapas duráveis separadas.](/diagrams/order-service-saga.svg)

Catálogo não deve baixar estoque porque a vitrine mostrou “disponível”: esse dado pode ser cache. Nunca trate preço enviado pelo navegador como autoridade; recalcule e registre preços válidos e identificadores de produto na transação, vinculando reserva a SKU durável.

## Contratos HTTP e significado de checkout

Uma proposta `POST /v1/orders` recebe cesta, referência de entrega e `Idempotency-Key` no escopo da conta autenticada. Verifica quantidade, moeda, preços e permissões, depois reserva estoque e persiste pedido com outbox atomicamente. Responda **202 Accepted** com ID e URL de status se pagamento ocorrer depois; significa aceitação do fluxo assíncrono, não dinheiro recebido. Rejeição de reserva devolve conflito de estoque documentado; chave usada com outro payload deve ser rejeitada.

`GET /v1/orders/{id}` valida proprietário e devolve `payment_pending`, `confirmed`, `cancelled` ou `payment_failed`. Depois de timeout, cliente não deve repetir checkout com chave diferente: a reserva pode ter sido confirmada. Se repetir chave original, recupera resultado durável. Índice UNIQUE e transação aplicam a regra até com múltiplas instâncias [1].

## Modelo executável de uma transação local

O exemplo **didático com SQLite** demonstra o invariante para um único SKU: estoque diminui apenas com saldo suficiente, pedido e outbox são gravados na mesma transação, e chave repetida não altera estoque novamente. Não é checkout distribuído nem integração de pagamento.

~~~python
import sqlite3

banco = sqlite3.connect(":memory:", isolation_level=None)
banco.executescript("""
CREATE TABLE stock(sku TEXT PRIMARY KEY,
    available INTEGER NOT NULL CHECK(available>=0));
CREATE TABLE orders(order_id TEXT PRIMARY KEY,
    operation_key TEXT UNIQUE, sku TEXT, quantity INTEGER, state TEXT);
CREATE TABLE outbox(order_id TEXT UNIQUE, event_type TEXT);
INSERT INTO stock VALUES ('sku-A', 4);
""")

def reservar(con, chave, sku, quantidade):
    if not chave or quantidade <= 0:
        raise ValueError("comando invalido")
    con.execute("BEGIN IMMEDIATE")
    try:
        anterior = con.execute(
            "SELECT order_id,sku,quantity FROM orders WHERE operation_key=?",
            (chave,)).fetchone()
        if anterior:
            if anterior[1:] != (sku, quantidade):
                raise ValueError("payload diferente na mesma chave")
            con.commit()
            return anterior[0], "repetido"
        linhas = con.execute(
            "UPDATE stock SET available=available-? "
            "WHERE sku=? AND available>=?",
            (quantidade, sku, quantidade)).rowcount
        if linhas != 1:
            con.rollback()
            return None, "sem_estoque"
        con.execute("INSERT INTO orders VALUES (?,?,?,?,?)",
                    (chave, chave, sku, quantidade, "payment_pending"))
        con.execute("INSERT INTO outbox VALUES (?,?)",
                    (chave, "authorize_payment"))
        con.commit()
        return chave, "aceito"
    except Exception:
        con.rollback()
        raise

assert reservar(banco, "pedido-1", "sku-A", 3) == ("pedido-1", "aceito")
assert reservar(banco, "pedido-1", "sku-A", 3) == ("pedido-1", "repetido")
assert reservar(banco, "pedido-2", "sku-A", 2) == (None, "sem_estoque")
assert banco.execute("SELECT available FROM stock").fetchone() == (1,)
assert banco.execute("SELECT COUNT(*) FROM outbox").fetchone() == (1,)
try:
    reservar(banco, "pedido-1", "sku-A", 1)
    assert False
except ValueError:
    pass
~~~

BEGIN IMMEDIATE serializa escritores SQLite no ambiente desse arquivo/conexão; o UPDATE condicional impede saldo negativo. Um sistema real em PostgreSQL ou distribuído precisa de testes com **conexões concorrentes distintas**, isolamento de transações real, escopo de chaves por cliente e política de IDs. Aqui o ID do pedido é a própria chave apenas para simplificar. TTL de reserva e liberação não são implementados nesse pequeno exemplo.

## Pagamento e fronteira da saga

O banco de pedidos **não** executa commit atômico com PSP independente apenas porque ambos oferecem APIs transacionais. Uma saga coordena transições locais e compensações. Um fluxo é: reservar estoque → solicitar autorização de pagamento → confirmar pedido no sucesso; liberar reserva em falha definitiva; se a resposta for incerta, **reconciliar** com PSP antes de liberar ou cobrar novamente [2].

Chamada ao PSP deve usar chave idempotente reconhecida por ele, se suportada; resposta pode sumir depois da autorização real. Repetir com chave nova pode gerar autorizações/cobranças duplicadas. Compensação não é voltar no tempo: estorno pode demorar, ter custo ou falhar e exigir conciliação humana. Guarde referências duráveis do PSP, histórico de tentativas e estados monetários. Evite registrar dados crus de cartão sem modelo completo de conformidade.

## Evite sobrevenda com concorrência

Imagine dois clientes vendo três unidades disponíveis e comprando dois cada. Leitura prévia de `SELECT available` seguida de decremento incondicional pode conceder quatro unidades. O invariante é **available ≥ 0 após toda reserva confirmada**. Aplique-o numa escrita condicional (como acima) ou com locks/isolation adequados dentro da autoridade de estoque.

Um SKU extremamente popular é **chave quente**. Sharding por usuário não distribui automaticamente atualizações atômicas do mesmo SKU; evitar sobrevenda pode continuar exigindo serialização. Considere alocação por depósito, quotas pré-distribuídas com limites, controle de admissão ou regra explícita de backorder, sem fingir que mais nós eliminam o hotspot.

## Expiração, cancelamento e liberação idempotente

Reservas não podem permanecer para sempre quando pagamentos expiram. Um processo de expiração identifica reservas vencidas e libera estoque **uma única vez na autoridade local** através de transição condicional, como `reserved → released`. Resultado de pagamento atrasado pode competir com vencimento; defina qual estado prevalece e como compensar pedido pago mas cancelado. Evento outbox de liberação pode chegar repetido; consumidores precisam deduplicar por identidade durável.

Reservar, confirmar, liberar e cancelar devem ser idempotentes sob chaves estáveis. Booleano local não sobrevive a failover. Transições exigem versionamento otimista ou locks e trilha de auditoria. Qualquer mudança que movimente dinheiro demanda reconciliação e análise específica de falhas.

## Falhas, métricas e testes operacionais

| Falha | Resposta segura | Teste |
| --- | --- | --- |
| Dois checkouts para um SKU | UPDATE condicional/lock | Duas conexões concorrentes |
| Timeout HTTP após commit | Mesma chave idempotente | Replay de payload igual/diferente |
| Outbox publicado duas vezes | Deduplicar comando de pagamento | Mensagens duplicadas |
| PSP aceita e resposta some | Mesma chave no PSP e conciliação | Timeout após efeito externo |
| Reserva vence no sucesso do PSP | Transição com fencing e compensação | Teste de corrida |
| Banco autoritativo cai | Falhar fechado, sem prometer estoque | Injeção de falhas |

Instrumente rejeições de checkout, contenção de estoque, idade de reservas, atraso do outbox, chaves repetidas, timeout de PSP, valor liquidado versus autorizado, cancelamentos e backlog de compensação. Checkout pode responder 202 rápido e deixar pagamentos travados; meça **conclusão do negócio** separadamente.

## Exercícios e verificação

1. Deduza pico de 300 tentativas/s e discuta efeito de 30% dos clientes repetirem por timeout.
2. Mostre intercalação de sobrevenda com dois pedidos de duas unidades quando só existem três.
3. Prove por que transação única sobre pedidos, stock e outbox impede pedido confirmado sem intenção de pagamento persistida.
4. Explique o que um timeout do PSP **não** informa ao comerciante e quando é necessária conciliação.
5. Desenhe teste de corrida entre sucesso do pagamento e expiração da reserva.

**Capítulos relacionados:** [Método de System Design](/pt/topics/system-design-process/), [escolha de armazenamento](/pt/topics/storage-selection/), [isolamento transacional](/pt/topics/transactional-indexing-isolation/), [mensageria assíncrona](/pt/topics/asynchronous-messaging/) e [idempotência HTTP](/pt/topics/api-reliability/) fundamentam o projeto.
