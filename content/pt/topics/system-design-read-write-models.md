---
id: system-design-read-write-models
title: "System Design: escrita autoritativa, projeções de leitura e consistência"
description: "Projete caminhos de escrita e projeções de leitura com eventos seguros para replay, limites de atraso e verificação de recuperação."
category: system-design
difficulty: intermediate
updated: 2026-10-12
prerequisites: [system-design-process, database-consistency, asynchronous-messaging]
sources:
  - {title: "Martin Fowler — CQRS", url: "https://martinfowler.com/bliki/CQRS.html", kind: "original architecture article"}
  - {title: "Chris Richardson — Transactional Outbox", url: "https://microservices.io/patterns/data/transactional-outbox.html", kind: "original pattern description"}
  - {title: "PostgreSQL — Transaction Isolation", url: "https://www.postgresql.org/docs/current/transaction-iso.html", kind: "official database documentation"}
---
System Design frequentemente representa “o banco” como uma caixa única. Na prática, **confirmar uma escrita** e **responder a uma consulta** têm requisitos diferentes de correção, latência e falha. Uma arquitetura pode executar ambas no banco transacional; outra pode manter uma projeção de leitura derivada. A segunda só faz sentido se atrasos, replay e recuperação tiverem contratos claros. Command Query Responsibility Segregation (CQRS) separa modelos para atualização e consulta, mas não exige bancos separados, event sourcing ou microsserviços [1].

## Defina os comportamentos observáveis

Considere serviço hipotético de pedidos. Após a confirmação, o registro autoritativo deve sobreviver às falhas previstas no modelo de durabilidade. A página que recupera pedido pelo ID deve proporcionar **read-your-writes** depois da confirmação. Um painel separado agrega pedidos concluídos por loja e aceita atraso de até cinco segundos durante funcionamento normal. Essa meta de atraso é **requisito hipotético**, não promessa universal de sistemas distribuídos.

O caminho de escrita aceita comando, verifica ator e pré-condições, aplica transação e devolve identificador estável. A leitura por ID pode consultar a fonte primária para atender read-your-writes. O painel pode consumir projeção reconstruível a partir de histórico durável de eventos. Separar essas promessas impede alegar que um cache rápido substitui o estado autoritativo.

## Derive primeiro a menor arquitetura

Um único banco relacional transacional pode aceitar escritas e atender leituras indexadas. Comece por ele se o tráfego medido for moderado. Use tabela de pedidos por order_id, identificação de tenant para controle de acesso, preços históricos imutáveis quando necessário e índices que correspondam às consultas reais. Faça EXPLAIN e teste de carga antes de criar outra persistência.

Uma projeção adiciona componentes: publicador, transporte ou log, consumidor, checkpoint, política de ordem, tratamento de erros e reconstrução. Pode reduzir custo de agregações e permitir escala de leitura independente, mas não torna o sistema automaticamente correto. CQRS pode ter dois modelos na mesma aplicação e no mesmo banco; separação física é decisão adicional [1].

## Preserve a autoridade de escrita

Suponha que uma transação altere pedidos e registre evento de outbox com order_id, aggregate_version e novo total confirmado. Os dois registros devem ser confirmados atomicamente. Um relay publica a outbox; se cair depois do envio e antes de marcar a publicação, poderá enviar novamente. A outbox transacional elimina uma janela de inconsistência entre banco e intenção de evento, mas não fornece entrega exatamente uma vez aos consumidores [2].

Defina versão estável, crescente por pedido. Use ID de evento para deduplicar mensagens e trate explicitamente saltos de sequência. Um timestamp global não estabelece sozinho a ordem quando há produtores concorrentes. Agregados diferentes podem ser processados independentemente; transições de um mesmo pedido precisam respeitar a sequência autorizada.

## Modele a projeção e a repetição

O projetor abaixo recebe o **total substituto** de um pedido em cada versão. O pequeno dicionário é estado derivado, não o banco autoritativo. Mensagem repetida com versão e payload idênticos não altera nada; versão repetida com payload diferente causa conflito. Versão futura fora de ordem é rejeitada para retentativa posterior. Cada pedido ocupa uma entrada; portanto, substituição do valor remove implicitamente a contribuição anterior em vez de somá-la duas vezes.

~~~python
from decimal import Decimal

class Projector:
    def __init__(self):
        self.orders = {}
    def apply(self, order_id, version, total):
        if not order_id or type(version) is not int or version < 1:
            raise ValueError("invalid event identity")
        if not isinstance(total, Decimal) or not total.is_finite() or total < 0:
            raise ValueError("invalid amount")
        previous = self.orders.get(order_id)
        if previous is None:
            if version != 1:
                raise ValueError("missing initial version")
        else:
            old_version, old_total = previous
            if version == old_version:
                if total != old_total:
                    raise ValueError("conflicting replay")
                return False
            if version != old_version + 1:
                raise ValueError("out-of-order event")
        self.orders[order_id] = (version, total)
        return True
    def total(self):
        return sum((amount for _, amount in self.orders.values()), Decimal("0"))

projection = Projector()
assert projection.apply("A", 1, Decimal("10.00"))
assert not projection.apply("A", 1, Decimal("10.00"))
assert projection.apply("B", 1, Decimal("4.50"))
assert projection.apply("A", 2, Decimal("8.00"))
assert projection.total() == Decimal("12.50")
before = dict(projection.orders)
for event in (("A", 2, Decimal("100")), ("A", 4, Decimal("9")),
              ("C", 2, Decimal("5"))):
    try:
        projection.apply(*event)
    except ValueError:
        pass
    else:
        raise AssertionError("invalid replay accepted")
assert projection.orders == before
~~~

Para n pedidos projetados, apply tem tempo esperado O(1) por evento sob as hipóteses convencionais de hashing de dicionários e mantém O(n) estado; somar valores exige O(n) tempo. Atualizar agregado acumulado permitiria consultas O(1), porém seria necessário atualizá-lo atomicamente com o registro por pedido e testá-lo diante de replay conflitante. O exemplo **não** persiste checkpoints, autentica eventos, coordena escritores paralelos ou resolve crescimento da memória.

## Dimensione atraso e backpressure

Suponha 600 eventos/s de entrada e capacidade sustentada de 500 eventos/s durante 120 segundos, com taxas constantes e sem duplicatas. O backlog cresce (600−500)×120 = 12.000 eventos. Se a entrada cair para 300/s e o processamento continuar em 500/s, a drenagem leva 12.000/(500−300) = 60 segundos, mesmo antes de contabilizar retries e overhead da fila.

~~~python
def backlog(arrivals_per_s, capacity_per_s, seconds, initial=0):
    if min(arrivals_per_s, capacity_per_s, seconds, initial) < 0:
        raise ValueError("negative input")
    return max(0, initial + (arrivals_per_s-capacity_per_s)*seconds)

assert backlog(600, 500, 120) == 12000
assert backlog(300, 500, 60, 12000) == 0
assert backlog(500, 500, 60, 12000) == 12000
~~~

Este modelo fluido aproxima volumes, **não** limita atraso individual. O SLO de cinco segundos precisa de instrumentação do intervalo criação→visibilidade, idade da fila, erros e p95/p99 com rajadas representativas. Um painel pode exibir “atualizado em” e degradar explicitamente, em vez de apresentar total antigo como informação autoritativa.

## Recuperação, ordem e consistência

Persista estado do projetor e offset confirmado na mesma fronteira consistente, ou reconstrua tudo a partir de log autoritativo reexecutável. Checkpoint à frente do estado perde atualização; checkpoint atrás pode repetir eventos. Deduplicação durável protege o segundo caso somente quando atualização e checkpoint seguem um contrato transacional coerente. Com vários workers, particione ou serialize por agregado; verificação de versão em memória não impede corrida entre processos.

A página que exige read-your-writes pode consultar o primário, direcionar sessão para réplica atualizada ou esperar versão confirmada. O painel separado pode oferecer dados eventuais porque o contrato permite atraso. Níveis de isolamento, atualizações simultâneas e anomalias dependem da semântica do banco real e devem ser testados na tecnologia escolhida [3].

## Contraexemplos e revisão arquitetural

Não adicione broker simplesmente porque um enunciado menciona CQRS. Uma consulta SQL indexada pode ser mais econômica, simples e correta. Contagem em cache pode servir ao painel analítico e ser inaceitável para cobrança. Eventos com **deltas incrementais** exigem lógica de replay diferente do total substituto demonstrado: aplicar o mesmo +10 duas vezes corrompe a soma. Se um stream tem lacunas irrecuperáveis, a expressão “consistência eventual” não promete convergência.

Confira também segurança: projeções de leitura podem expor dados entre tenants se suas chaves omitirem a identidade do tenant ou a consulta confiar em identificador fornecido pelo cliente. Eventos podem conter dados pessoais sujeitos a retenção e exclusão. Correção de dados inclui autorização, não apenas ordem das mensagens.

## Exercícios e verificação

1. Refaça o projetor para eventos de delta. Prove quais IDs e dados de deduplicação evitam somar duas vezes e teste replay após reinício.
2. Calcule backlog com 600/s de entrada, 400/s de processamento por três minutos e recuperação para 700/s quando a entrada cai para 300/s.
3. Projete SLO e alerta de atraso. Diferencie profundidade da fila da idade dos eventos e descreva medições.
4. Mostre o ponto de crash entre commit do pedido e relay da outbox. Explique por que a mensagem pode repetir, mas nunca descrever pedido que sofreu rollback.
5. Decida se a consulta imediata de pedido pode usar a réplica assíncrona do painel. Identifique o requisito de consistência que determina a resposta.

Relacionados: [consistência](/pt/topics/database-consistency/), [mensageria](/pt/topics/asynchronous-messaging/), [APIs confiáveis](/pt/topics/api-reliability/) e [revisão arquitetural](/pt/topics/system-design-architecture-review/).