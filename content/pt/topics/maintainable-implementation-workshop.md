---
id: maintainable-implementation-workshop
title: "Oficina de código manutenível: token bucket, relógio injetado e testes"
description: "Implemente token bucket revisável com relógio injetado, invariantes explícitos e testes determinísticos; avalie limites distribuídos."
category: engineering
difficulty: intermediate
updated: 2026-10-09
prerequisites: [object-oriented-design, testing-strategies, rate-limiting]
sources:
  - {title: "AWS Architecture Blog — Rate limiting best practices", url: "https://aws.amazon.com/blogs/architecture/throttling-a-tiered-multi-tenant-rest-api-at-scale-using-api-gateway-part-1/", kind: "original engineering guidance"}
  - {title: "Amazon API Gateway — Throttle API requests", url: "https://docs.aws.amazon.com/apigateway/latest/developerguide/api-gateway-request-throttling.html", kind: "official vendor documentation"}
  - {title: "Python — time.monotonic", url: "https://docs.python.org/3/library/time.html#time.monotonic", kind: "official Python documentation"}
---
Uma solução de entrevista que devolve valores corretos ainda pode ser difícil de manter, testar ou implantar. Esta oficina implementa um **limitador de taxa token bucket** como componente de domínio pequeno. A meta não é somente o algoritmo, mas contrato revisável: unidades explícitas, relógio injetado, casos-limite, propriedade do estado, testes determinísticos e indicação de onde uma implementação em memória deixa de ser suficiente. Token buckets são usados para limitar vazão sustentada e permitir rajadas controladas [1].

## Transforme pedido vago em contrato

O requisito “limitar a dez requisições por segundo” é ambíguo: pode enviar dez no mesmo milissegundo? Créditos não usados acumulam? O limite é por usuário ou global? Como tratar ajuste do relógio? Defina uma semântica: cada bucket possui no máximo C tokens, começa cheio, recebe r tokens por segundo com base em **tempo monotônico decorrido**, e operação aceita gasta custo inteiro positivo. Operação rejeitada não consome tokens.

No instante t, se a última observação foi t₀ e o saldo anterior era T₀, o novo saldo é **min(C,T₀+r·(t−t₀))**. Aceite quando saldo é pelo menos o custo. Isso permite rajada máxima C e orçamento sustentado próximo a r por segundo, mas **não** é garantia de exatamente r operações em toda janela deslizante de um segundo.

## Autoridade, estado e fronteira de falha

Bucket em processo impõe limite de um cliente lógico **somente se todas suas chamadas alcançam o mesmo objeto com atualizações sincronizadas**. Com quatro réplicas de API sem estado, cada uma contendo dez tokens, cliente pode gastar até quarenta entre réplicas. Cota global exige armazenamento autoritativo distribuído ou política de roteamento/sharding. Script atômico em Redis ou operação transacional no banco podem impor atualização indivisível, com custos de latência e indisponibilidade específicos [2].

Trate token bucket como **lógica de domínio**, independente de HTTP. Autenticação e identificação do principal pertencem à fronteira da requisição; cliente não pode escolher chave de bucket de outro tenant. HTTP 429 e Retry-After são responsabilidades do adaptador após a decisão. Isso permite testar algoritmo sem inicializar servidor web.

## Injete relógio em vez de usar sleep

Ler relógio real dentro do limitador torna testes lentos e instáveis. Injete função de tempo no construtor; use fonte monotônica na produção e relógio manual nos testes. Tempo monotônico mede intervalos, enquanto relógio civil pode mudar por sincronização e ajustes. A injeção reproduz casos de fronteira temporal diretamente [3].

![Transições token bucket por reposição, consumo e rejeição.](/diagrams/maintainable-token-bucket.svg)

~~~python
from time import monotonic

class BaldeTokens:
    def __init__(self, capacidade, taxa_por_segundo, relogio=monotonic):
        if not isinstance(capacidade, int) or capacidade <= 0:
            raise ValueError("capacidade inteira positiva obrigatoria")
        if taxa_por_segundo <= 0:
            raise ValueError("taxa de reposicao positiva obrigatoria")
        self.capacidade = capacidade
        self.taxa = taxa_por_segundo
        self._relogio = relogio
        self._ultimo = relogio()
        self._tokens = float(capacidade)

    def permitir(self, custo=1):
        if not isinstance(custo, int) or custo <= 0:
            raise ValueError("custo inteiro positivo obrigatorio")
        agora = self._relogio()
        decorrido = agora - self._ultimo
        if decorrido < 0:
            raise ValueError("relogio retrocedeu")
        self._tokens = min(self.capacidade, self._tokens + decorrido * self.taxa)
        self._ultimo = agora
        if custo > self._tokens:
            return False
        self._tokens -= custo
        return True

class RelogioManual:
    def __init__(self):
        self.agora = 0.0
    def __call__(self):
        return self.agora
    def avancar(self, segundos):
        if segundos < 0:
            raise ValueError("avanco negativo")
        self.agora += segundos

relogio = RelogioManual()
balde = BaldeTokens(2, 1, relogio)
assert balde.permitir() and balde.permitir()
assert not balde.permitir()
relogio.avancar(0.5)
assert not balde.permitir()
relogio.avancar(0.5)
assert balde.permitir()
assert not balde.permitir()
~~~

Usa tokens em ponto flutuante para demonstração. Em quotas financeiras ou longas execuções, defina políticas de precisão e overflow; validação pode rejeitar NaN, infinito e tipos numéricos arbitrários. O código assume taxa finita confiável e relógio confiável. **Não é thread-safe** sem lock externo, nem durável após reinício.

## Casos de fronteira e invariante de rejeição

O **invariante da rejeição** estabelece que chamada negada não debita saldo. O tempo avança e a reposição observada na tentativa negada ainda integra o estado. Verifique saldo zero, reposição fracionária, saturação depois de longa pausa e custo inválido. Um bug comum subtrai antes de conferir saldo, criando número negativo de tokens.

~~~python
relogio2 = RelogioManual()
limitador = BaldeTokens(3, 2, relogio2)
assert limitador.permitir(3)
assert not limitador.permitir(1)
relogio2.avancar(0.25)
assert not limitador.permitir(1)
relogio2.avancar(0.25)
assert limitador.permitir(1)
relogio2.avancar(100)
assert limitador.permitir(3)
assert not limitador.permitir(1)
for invalido in (0, -1, 1.5):
    try:
        limitador.permitir(invalido)
        assert False
    except ValueError:
        pass
~~~

Os testes verificam **decisões observáveis**, não acessam sempre o campo privado `_tokens`. Teste interno de invariante pode consultar estado durante verificação especializada, mas depender de detalhes privados em todas as verificações acopla a suíte à implementação.

## Demonstração de invariante e custos

Sob entradas finitas confiáveis, vale **0 ≤ tokens ≤ C** após cada chamada `permitir`. Na inicialização tokens=C. Durante reposição, decorrido≥0 e taxa>0 impedem queda do saldo; min(C,...) limita ao teto. Só subtraímos quando saldo≥custo e custo>0, portanto não há saldo negativo. Rejeição preserva o saldo após reposição. Indução no número de chamadas demonstra o invariante.

Cada decisão efetua O(1) operações aritméticas e usa O(1) memória de instância **sob aritmética de precisão fixa**. Isso é complexidade local, não latência HTTP de banco remoto. Sob chamadas concorrentes sem lock, leituras e atualizações podem violar o invariante; atomicidade é problema distinto de correção aritmética.

## Contraexemplos: janelas fixas e réplicas

Uma contagem por janela fixa permite quase 2C chamadas ao redor do limite entre janelas: envie C pouco antes do término de uma e C logo após começar outra. Token bucket limita créditos acumulados e reposição, mas também permite rajadas por contrato. Limitador de **janela deslizante** pode ser melhor quando produto exige máximo exato em toda janela, ao custo de mais rastreamento.

Outro contraexemplo é o mesmo cliente ser atendido por processos diferentes com buckets independentes. Cada processo concede a própria cota, violando limite global. Sticky sessions só ajudam enquanto roteamento e falhas preservam associação, sem substituir autoridade única quando cliente pode chegar a múltiplas instâncias.

## Revisão de design e evolução

| Decisão | Benefício | Limitação |
| --- | --- | --- |
| Injetar `relogio` | Testes rápidos e determinísticos | Fonte monotônica confiável |
| Separar HTTP do núcleo | Lógica reutilizável | Adaptador traduz 429 e headers |
| Rejeitar custo inválido | Contrato claro | Política de custos necessária |
| Iniciar cheio | Permite rajadas | Difere de cota estrita por segundo |
| Estado em memória | Protótipo rápido | Sem durabilidade entre processos |
| Lock por bucket | Protege threads com objeto comum | Não coordena réplicas diferentes |

A classe se justifica porque o bucket **controla estado mutável** com invariante coerente. Não crie fábricas de estratégia, bancos ou brokers sem requisitos reais. Code review deve discutir tipos, justiça, descarte de buckets inativos, cardinalidade sem limite, autenticação, métricas e o que acontece quando a autoridade do limitador falha.

## Exercícios e verificação

1. Calcule decisões para C=3, r=2 tokens/s com chamadas em 0, 0, 0, 0,25 e 0,5, custo um.
2. Por que bucket iniciado cheio difere de máximo exato por janela deslizante?
3. Acrescente wrapper sincronizado com `threading.Lock` e teste duas threads sobre estado compartilhado.
4. Desenhe esquema distribuído de buckets por tenant com atualização atômica condicional.
5. Escolha métricas para rejeições, explosão de buckets, divergência entre réplicas e indisponibilidade do armazenamento.

**Capítulos relacionados:** [Arquitetura de limites](/pt/topics/rate-limiting/), [contratos OO](/pt/topics/object-oriented-design/), [testes](/pt/topics/testing-strategies/) e [oficina de concorrência](/pt/topics/concurrency-interview-workshop/) explicam os trade-offs [1][2].
