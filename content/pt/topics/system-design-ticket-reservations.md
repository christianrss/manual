---
id: system-design-ticket-reservations
title: "System Design: reserva de ingressos, concorrência e expiração"
description: "Projete reserva de assentos com confirmação atômica, idempotência, expiração, isolamento transacional e falhas testadas."
category: system-design
difficulty: advanced
updated: 2026-10-12
prerequisites: [system-design-process, transactional-indexing-isolation, api-reliability, domain-modeling-aggregates-invariants]
sources:
  - {title: "PostgreSQL — Transaction Isolation", url: "https://www.postgresql.org/docs/current/transaction-iso.html", kind: "official database documentation"}
  - {title: "PostgreSQL — Data Consistency Checks at the Application Level", url: "https://www.postgresql.org/docs/current/applevel-consistency.html", kind: "official database documentation"}
  - {title: "AWS Builders Library — Making retries safe with idempotent APIs", url: "https://aws.amazon.com/builders-library/making-retries-safe-with-idempotent-APIs/", kind: "original engineering guidance"}
---
Um serviço de venda de ingressos parece um CRUD comum até vários compradores tentarem reservar **o último assento disponível**. O problema central não é desenhar balanceadores; é estabelecer uma única autoridade capaz de decidir qual reserva pode prosseguir sob concorrência, timeouts e expiração. Este capítulo conecta requisitos, capacidade, transições, isolamento de banco e recuperação. O cenário é hipotético e não representa a infraestrutura de uma empresa real.

## Requisitos e invariantes rígidos

O comprador consulta mapa de assentos, solicita bloqueio temporário, confirma compra e acompanha a reserva. Considere lugares numerados, não lotação geral. O mapa pode estar alguns segundos desatualizado porque oferece informação consultiva; bloquear e vender dependem de decisão autoritativa. O primeiro invariante é **no máximo uma venda confirmada para cada par (evento, assento)**. A autoridade também deve aceitar no máximo um bloqueio não expirado do mesmo assento em determinado instante.

O segundo invariante é temporal: bloqueio tem prazo final e confirmação depois dele deve ser rejeitada. O terceiro trata retentativas: chave de operação repetida com requisição idêntica se refere à mesma reserva lógica; repetir a chave com outro assento, usuário ou prazo gera conflito. Devolva ID e endpoint de estado para distinguir bloqueio aceito, expirado e confirmado. Uma repetição de sucesso antigo não deve prorrogar automaticamente o prazo, pois o cliente poderia monopolizar lugares apenas repetindo mensagens [3].

## Dimensionamento com premissas explícitas

Suponha dois milhões de consultas de mapa e 50 mil tentativas de bloqueio por dia, com pico vinte vezes a média. A taxa média de leitura é aproximadamente 23,15 requisições/s e o pico suposto 463/s. Para bloqueios, temos cerca de 0,579/s em média e 11,57/s no pico. Esses números não determinam quantidade de máquinas. Faça benchmark de contenção no banco sobre **assentos populares**, não apenas da vazão total.

Um único lugar pode atrair centenas de solicitações num lançamento, apesar da baixa média de bloqueios. Cache eficiente do mapa não resolve esse ponto quente: disponibilidade exibida é estimativa, nunca prova de reserva bem-sucedida. Defina SLOs hipotéticos separados para latência de consultas, decisões autoritativas e pagamento, pois p95 baixo no mapa pouco informa sobre espera por lock ou indisponibilidade do provedor.

## Contratos de API e máquina de estados

Uma proposta usa POST /events/{eventId}/holds com ID do assento e chave idempotente, GET /holds/{holdId} e POST /holds/{holdId}/confirm. Assento inválido falha na validação; lugar vendido retorna indisponibilidade explícita; reutilizar chave com payload diferente causa conflito. Imponha duração máxima ao bloqueio e exija relógio controlado pelo serviço. Horário do celular não deve ser autoridade.

Uma máquina de estados finita segue disponível → bloqueado → confirmado. Bloqueado → expirado é permitido ao alcançar prazo. Expirado → bloqueado **não** significa reativar a antiga reserva: uma nova operação cria novo identificador. Confirmação é terminal neste modelo. Cancelamento, estorno, liquidação de pagamento, chargeback e transferência exigem fluxos próprios. Uma resposta de bloqueio aceito não equivale à cobrança concluída.

## Modelo local verificável

O código usa tempo lógico inteiro informado pelo teste para exercitar limites sem sleeps. Implementação produtiva requer relógio confiável no servidor e transação atômica em banco. As chamadas do modelo são seriais: ele demonstra **contrato observável**, não isolamento entre threads ou processos. O histórico fica em memória e não oferece deduplicação durável.

~~~python
class ReservationModel:
    def __init__(self, seats):
        if not seats or len(set(seats)) != len(seats):
            raise ValueError("invalid seat inventory")
        self.seats = frozenset(seats)
        self.active = {}       # seat -> reservation key
        self.sold = {}         # seat -> confirmed key
        self.records = {}      # durable in a real implementation

    def hold(self, seat, owner, key, now, ttl):
        if (seat not in self.seats or not isinstance(owner, str) or not owner
                or not isinstance(key, str) or not key
                or type(now) is not int or now < 0
                or type(ttl) is not int or not 1 <= ttl <= 900):
            raise ValueError("invalid request")
        fingerprint = (seat, owner, ttl)
        if key in self.records:
            if self.records[key]["request"] != fingerprint:
                raise ValueError("idempotency conflict")
            return key
        if seat in self.sold:
            raise ValueError("seat already sold")
        prior = self.active.get(seat)
        if prior is not None:
            previous = self.records[prior]
            if now < previous["until"]:
                raise ValueError("seat is held")
            previous["state"] = "expired"
            del self.active[seat]
        self.records[key] = {"request": fingerprint, "seat": seat,
                             "until": now + ttl, "state": "held"}
        self.active[seat] = key
        return key

    def confirm(self, key, now):
        if key not in self.records or type(now) is not int or now < 0:
            raise ValueError("unknown key or time")
        record = self.records[key]
        if record["state"] == "confirmed":
            return "confirmed"
        if record["state"] != "held":
            raise ValueError("not an active hold")
        seat = record["seat"]
        if now >= record["until"]:
            record["state"] = "expired"
            if self.active.get(seat) == key:
                del self.active[seat]
            raise ValueError("hold expired")
        if self.active.get(seat) != key or seat in self.sold:
            raise ValueError("conflicting hold")
        del self.active[seat]
        self.sold[seat] = key
        record["state"] = "confirmed"
        return "confirmed"

    def status(self, key, now):
        if key not in self.records or type(now) is not int or now < 0:
            raise ValueError("unknown key or time")
        record = self.records[key]
        if record["state"] == "held" and now >= record["until"]:
            return "expired"
        return record["state"]

model = ReservationModel(["A1", "A2"])
assert model.hold("A1", "alice", "op-1", 100, 30) == "op-1"
assert model.hold("A1", "alice", "op-1", 120, 30) == "op-1"
try:
    model.hold("A1", "bob", "op-2", 120, 30)
except ValueError:
    pass
else:
    raise AssertionError("double hold accepted")
assert model.confirm("op-1", 129) == "confirmed"
assert model.confirm("op-1", 200) == "confirmed"
assert model.status("op-1", 500) == "confirmed"
try:
    model.hold("A1", "bob", "op-3", 500, 30)
except ValueError:
    pass
else:
    raise AssertionError("confirmed seat resold")
assert model.hold("A2", "bob", "op-4", 100, 30) == "op-4"
assert model.status("op-4", 130) == "expired"
assert model.hold("A2", "cara", "op-5", 130, 30) == "op-5"
assert model.status("op-4", 130) == "expired"
assert model.confirm("op-5", 131) == "confirmed"
~~~

Os testes cobrem conflito de bloqueios, replay estável, repetição de confirmação, expiração no instante exato, reutilização após prazo e impossibilidade de revender lugar confirmado. Replay devolve a chave original mesmo que o bloqueio tenha expirado. O cliente deve consultar o estado, não interpretar a chave como nova disponibilidade. Guardar operações indefinidamente é inviável em escala; serviços reais precisam de retenção e contrato para tentativas após a expiração do histórico.

## Transações autoritativas e concorrência

Identifique assento por (event_id, seat_id). Uma linha primária pode guardar reserva confirmada, bloqueio corrente e expiração. A aquisição deve realizar mutação condicional que só tenha êxito se não existir venda nem bloqueio não expirado. A condição e a escrita precisam compor **uma única transação atômica**. Fazer SELECT, verificar disponibilidade na aplicação e depois UPDATE incondicional é inseguro: dois workers podem observar o mesmo estado antigo.

Na confirmação, verifique atomicamente ID do bloqueio, prazo e ausência de venda; então marque como confirmado. O isolamento do PostgreSQL define quais anomalias são impedidas e quando é necessário repetir transação após falha de serialização [1]. Bloqueios explícitos ajudam a proteger linhas, mas não substituem atualização autoritativa e verificação de predicados [2]. Acrescente restrição de unicidade que proteja uma venda por assento. Teste comportamento concorrente no banco real em vez de confiar apenas no Python.

## Expiração e pagamentos são autoridades diferentes

Prazo do bloqueio não garante que o provedor de pagamento termine dentro dele. Se o provedor capturou o valor, mas a resposta se perdeu, tentar nova cobrança com identidade diferente pode duplicar o débito. Persista intenção de pagamento e chave estável, reconcilie respostas incertas e defina compensação ou estorno. O ingresso não fica confirmado simplesmente porque uma tela mostrou pagamento efetuado.

Um worker de expiração pode limpar registros para eficiência, mas a correção não pode depender de ele executar exatamente no prazo. A própria condição autoritativa verifica o tempo. Se tarefa antiga chegar depois de outro usuário adquirir assento, ela precisa identificar **o bloqueio antigo** e jamais liberar o sucessor. TTL, mensagens duplicadas e filas atrasadas exigem verificação de identidade, não confiança na ordem do agendamento.

## Partições, pontos quentes e disponibilidade

Divida dados por evento ou faixas de assentos quando medições justificarem. Leituras podem ter cache por evento; escritas do mesmo assento precisam convergir sobre decisão autoritativa única. Uma réplica atrasada pode mostrar lugar livre depois da venda. Isso é tolerável no mapa consultivo se o checkout sempre revalidar no primário. Aceitar escritas concorrentes em primários independentes sem protocolo de conflito pode vender duas vezes durante partições.

O projeto geralmente deve privilegiar consistência para um assento: se a autoridade de banco está indisponível, rejeite ou adie bloqueios em vez de prometer duas vendas aparentemente confirmadas. Documente impacto na disponibilidade e nos objetivos de serviço. Reserva ativa-ativa multirregional exige regras adicionais de quórum ou propriedade de partição, não apenas replicar servidores HTTP.

## Complexidade, testes e contraexemplos

Com s assentos e h reservas mantidas no histórico, o modelo usa O(s + h) estado. Buscas e atualizações de dicionário têm custo esperado O(1) sob hipóteses usuais de hashing, **não** garantia de pior caso nem limite para latência SQL. Custos reais incluem locks, índices, logs, replicação, retentativas e integração de pagamentos.

Simule 100 tentativas simultâneas ao último lugar com conexões reais e chaves distintas. Exatamente um bloqueio deve ser aceito enquanto permanecer válido. Teste timeout após commit, repetição após perda de resposta, confirmação no prazo exato, duas confirmações, tarefa de expiração atrasada, failover e reconstrução por dados persistidos. Métodos locais chamados sequencialmente não estabelecem isolamento entre processos nem confiabilidade operacional.

## Exercícios e verificação

1. Derive taxas médias e máximas usando os volumes propostos. Explique por que vazão agregada oculta disputa por assento específico.
2. Expire bloqueio X, crie Y no mesmo lugar e repita X. Explique por que X não pode ganhar novo prazo nem cancelar Y.
3. Esboce UPDATE SQL atômico para adquirir e confirmar bloqueio, com lock, constraint de unicidade e verificação de linhas afetadas.
4. Descreva crash após commit do pagamento no provedor e antes da resposta ao serviço. Diferencie estorno, reconciliação e duplicação de cobrança.
5. Projete testes com banco real e conexões concorrentes. Identifique as evidências que faltam ao modelo em memória.

Relacionados: [isolamento de transações](/pt/topics/transactional-indexing-isolation/), [API confiável](/pt/topics/api-reliability/), [invariantes de domínio](/pt/topics/domain-modeling-aggregates-invariants/) e [método de System Design](/pt/topics/system-design-process/).