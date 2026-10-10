---
id: failure-recovery-workshop
title: "Oficina de injeção de falhas: outbox, crashes e entrega duplicada"
description: "Teste falhas antes/depois do commit, outbox pelo menos uma vez, deduplicação no receptor e fronteiras de recuperação."
category: engineering
difficulty: advanced
updated: 2026-10-09
prerequisites: [testing-strategies, asynchronous-messaging, api-reliability]
sources:
  - {title: "SQLite — UPSERT and conflict handling", url: "https://www.sqlite.org/lang_upsert.html", kind: "official database documentation"}
  - {title: "Amazon Builders Library — Making retries safe with idempotent APIs", url: "https://aws.amazon.com/builders-library/making-retries-safe-with-idempotent-APIs/", kind: "original engineering guidance"}
---
Sistemas confiáveis exigem testes que **interrompam trabalho entre etapas duráveis**. Um teste de integração feliz pode passar enquanto eventos somem sempre que um worker cai após commit do banco e antes da publicação no broker. Esta oficina constrói um pequeno protocolo de transactional outbox, injeta falhas em fronteiras explícitas e verifica o estado após retomada. O escopo é uma autoridade SQLite e um receptor simulado; não reivindica envio atômico a broker independente nem efeitos externos exatamente uma vez [1][2].

## Contratos de segurança e recuperação

Uma API hipotética de pedidos recebe chave de operação e grava registro de domínio junto de intenção de evento. O **invariante de segurança** é: cada pedido confirmado possui exatamente uma intenção lógica de outbox, imposta por uma transação local. O **invariante de idempotência** é: repetir a chave não cria outro pedido nem outra intenção. A recuperação exige que uma intenção confirmada e ainda não enviada possa ser descoberta e repetida após reiniciar.

Outra meta—todo evento eventualmente chegar ao destino—é uma **propriedade de progresso**. Ela depende de dispatcher operante, broker acessível, falhas finitas e política de repetição. Armazenar outbox não faz mensagem avançar sozinha. Efeitos ponta a ponta num provedor externo exigem idempotência dele ou conciliação.

## Intenção durável e pontos de interrupção

Crie transação única que insere pedido e respectiva linha outbox. Ambos confirmam ou ambos sofrem rollback. Simule falha **antes do commit** lançando exceção e revertendo: API não deve afirmar aceite. Simule falha **após commit** lançando erro depois da confirmação: cliente pode observar timeout, mas retry da mesma chave recupera pedido existente sem duplicar.

![Fronteiras de falha em transação de pedido, publicação outbox e acknowledgment.](/diagrams/failure-recovery-drill.svg)

O exemplo Python usa SQLite em memória para testes determinísticos locais. Transações, UNIQUE e tratamento de conflitos são documentados pelos autores do SQLite [1]. Para conferir durabilidade real após crash, use banco em arquivo, mate processo independente e reabra os mesmos arquivos; banco em memória não sobrevive ao encerramento do processo.

~~~python
import sqlite3

banco = sqlite3.connect(":memory:", isolation_level=None)
banco.executescript("""
CREATE TABLE orders (
  operation_key TEXT PRIMARY KEY, description TEXT NOT NULL
);
CREATE TABLE outbox (
  event_id TEXT PRIMARY KEY, operation_key TEXT NOT NULL UNIQUE,
  delivered INTEGER NOT NULL DEFAULT 0
);
""")

def aceitar(con, chave, descricao, falhar_em=None):
    if not chave or not descricao:
        raise ValueError("entradas obrigatorias")
    con.execute("BEGIN IMMEDIATE")
    try:
        anterior = con.execute(
            "SELECT description FROM orders WHERE operation_key=?", (chave,)
        ).fetchone()
        if anterior is not None:
            if anterior[0] != descricao:
                raise ValueError("conflito de payload idempotente")
            con.commit()
            return "repetido"
        con.execute("INSERT INTO orders VALUES (?,?)", (chave, descricao))
        con.execute("INSERT INTO outbox(event_id,operation_key) VALUES (?,?)",
                    ("event-" + chave, chave))
        if falhar_em == "before_commit":
            raise RuntimeError("falha injetada antes do commit")
        con.commit()
    except Exception:
        con.rollback()
        raise
    if falhar_em == "after_commit":
        raise RuntimeError("resposta perdida apos commit")
    return "aceito"

try:
    aceitar(banco, "a", "um item", "before_commit")
    assert False
except RuntimeError:
    pass
assert banco.execute("SELECT COUNT(*) FROM orders").fetchone()[0] == 0
assert aceitar(banco, "a", "um item") == "aceito"
try:
    aceitar(banco, "b", "dois itens", "after_commit")
    assert False
except RuntimeError:
    pass
assert aceitar(banco, "b", "dois itens") == "repetido"
assert banco.execute("SELECT COUNT(*) FROM orders").fetchone()[0] == 2
assert banco.execute("SELECT COUNT(*) FROM outbox").fetchone()[0] == 2
~~~

Usar chave de operação como ID do evento é simplificação **didática**. Sistema real precisa escopo por tenant/conta, fingerprint canônico do pedido, controle de acesso e IDs apropriados para replay e auditoria.

## Publique, caia e observe duplicatas inevitáveis

O relay encontra outbox pendente, publica no broker e marca entrega. Se o processo cai depois do envio **antes** de marcar, publicará novamente após restart. Inverter a ordem—marcar antes do envio—cria janela de perda. Sem transação distribuída abrangendo banco e broker, outbox costuma escolher publicação pelo menos uma vez com deduplicação posterior [2].

A simulação guarda aceites do provedor em lista; não é durável. O teste verifica contagens de chamada sob crash escolhido, sem fingir que uma lista representa infraestrutura real.

~~~python
def relay_uma_vez(con, enviar, falhar_apos_envio=False):
    pendentes = con.execute(
        "SELECT event_id FROM outbox WHERE delivered=0 ORDER BY event_id"
    ).fetchall()
    for (evento,) in pendentes:
        enviar(evento)
        if falhar_apos_envio:
            raise RuntimeError("queda de relay injetada")
        con.execute(
            "UPDATE outbox SET delivered=1 WHERE event_id=?", (evento,)
        )

chamadas = []
try:
    relay_uma_vez(banco, chamadas.append, falhar_apos_envio=True)
    assert False
except RuntimeError:
    pass
assert chamadas == ["event-a"]
relay_uma_vez(banco, chamadas.append)
assert chamadas.count("event-a") == 2
assert chamadas.count("event-b") == 1
assert banco.execute("SELECT COUNT(*) FROM outbox WHERE delivered=0").fetchone()[0] == 0
~~~

O receptor deve registrar event ID único **na mesma transação que seu efeito de negócio**, se disponível. Mesmo assim, um PSP independente pode deixar resultado desconhecido após timeout. Uma linha de deduplicação local não desfaz nem descobre automaticamente efeito externo irreversível.

## Modelo de deduplicação no receptor

Uma pequena tabela inbox impõe unicidade de event ID. Essa garantia é local ao banco da inbox e representa um padrão, sem efeito financeiro real. Em produção, inserir marcador na inbox numa transação e alterar saldo em outra ainda permite efeito duplicado após queda. Mantenha deduplicação e efeito protegido **na mesma transação** ou documente garantia menor.

~~~python
receptor = sqlite3.connect(":memory:", isolation_level=None)
receptor.execute("CREATE TABLE inbox(event_id TEXT PRIMARY KEY)")
receptor.execute("CREATE TABLE processed(event_id TEXT PRIMARY KEY)")

def consumir(con, evento):
    con.execute("BEGIN IMMEDIATE")
    try:
        inserido = con.execute(
            "INSERT INTO inbox(event_id) VALUES (?) ON CONFLICT(event_id) DO NOTHING",
            (evento,)
        ).rowcount
        if inserido:
            con.execute("INSERT INTO processed VALUES (?)", (evento,))
        con.commit()
        return bool(inserido)
    except Exception:
        con.rollback()
        raise

assert [consumir(receptor, evento) for evento in chamadas] == [True, False, True]
assert receptor.execute("SELECT COUNT(*) FROM processed").fetchone()[0] == 2
~~~

O broker pode entregar eventos fora de ordem, e falhas podem ocorrer durante consumidor. Por isso limites transacionais e regras de replay são importantes. Exemplo com uma conexão SQLite não valida consumidores independentes concorrentes num broker gerenciado.

## Matriz de falhas em vez de confiar num único teste

| Momento da queda | Pedido durável | Intenção durável | Comportamento |
| --- | --- | --- | --- |
| Antes de começar transação | Não | Não | Cliente repete |
| Após inserts, antes do commit | Não | Não | Rollback atômico |
| Após commit, antes de HTTP responder | Sim | Sim | Mesma chave recupera resultado |
| Após publicar, antes de ack no outbox | Sim | Sim, pendente | Republicar; receptor deduplica |
| Após ack do outbox | Sim | Sim, concluído | Relay normal não republica |

Injete também **conflito de corpo na mesma chave**, processos competindo para criar chave igual, backpressure do broker e receptor falhando depois de pagamento externo antes do marcador inbox. O último caso não é resolvido apenas pelo outbox local; depende de contrato do provedor e conciliação [2].

## Backlog, timeouts e fronteiras de durabilidade

Com chegadas de 400 eventos/s e capacidade segura do consumidor de 500/s, a margem teórica é 100/s. Pane de dez minutos acumula 240 mil eventos; mantendo chegadas, drenagem exige 2.400 segundos ou 40 minutos. É aproximação contínua com taxas constantes, armazenamento suficiente, zero retries e ausência de quotas externas. Meça idade do backlog e **taxa de tentativas**, não só eventos únicos.

Não implemente retries nem filas ilimitados. Expiração pode caber em notificações, mas é inadequada para dinheiro sem política explícita; defina estado terminal e conciliação humana. Separe retenção de payload e metadados para equilibrar auditoria e privacidade.

## Confira restauração, concorrência e operação

Suíte robusta usa SQLite temporário em arquivo, processo separado, encerramento nos pontos definidos e verificação das linhas após reabrir. Teste de implantação mais forte usa **banco e broker reais**, workers multiprocessos, falhas de rede e garantias duráveis documentadas. Os exemplos atuais validam invariantes locais de schedules escolhidos, não entregas distribuídas gerais.

Telemetria deve revelar evento pendente mais antigo, throughput de relay, falhas de publicação, número de duplicatas, deduplicação no receptor, lag outbox→entrega e falhas terminais. Um runbook distingue consumidor lento de relay travado e identifica quem pode executar replay seguro.

## Exercícios e verificação

1. Identifique a transação que garante pedido e intenção confirmados simultaneamente.
2. Por que enviar antes de marcar pode duplicar, mas marcar antes de enviar pode perder evento?
3. Acrescente fingerprint de payload para transformar chave com corpo diferente em conflito.
4. Teste banco SQLite em arquivo e reabra depois de lançar falha após commit.
5. Recalcule drenagem com 400 entradas/s, pane de 30 minutos e 600 processamentos/s após retorno.

**Capítulos relacionados:** [Mensageria assíncrona](/pt/topics/asynchronous-messaging/), [outbox no projeto de notificações](/pt/topics/system-design-notifications/), [APIs idempotentes](/pt/topics/api-reliability/) e [incidentes](/pt/topics/production-incident-response/) tratam fronteiras relacionadas [1][2].
