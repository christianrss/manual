---
id: cpu-pipeline-hazards-branch-prediction
title: "Pipeline de CPU: dependências, forwarding e previsão de desvios"
description: "Derive latência, vazão, stalls, dependências de carga e previsão de desvios de dois bits com modelos e testes independentes."
category: computer-architecture
difficulty: intermediate
updated: 2026-10-10
prerequisites: [machine-representation-isa-cache]
sources:
  - {title: "MIT 6.004 — Pipelining the Beta (annotated slides)", url: "https://ocw.mit.edu/courses/6-004-computation-structures-spring-2017/pages/c15/c15s1/", kind: "university teaching material"}
  - {title: "MIT 6.5900 — Computer System Architecture lecture notes", url: "https://csg.csail.mit.edu/6.5900/lecnotes.html", kind: "university course materials"}
  - {title: "Intel — 64 and IA-32 Optimization Manual", url: "https://www.intel.com/content/www/us/en/developer/articles/technical/intel64-and-ia32-architectures-optimization.html", kind: "official vendor optimization manuals"}
---
Pipelining sobrepõe fases diferentes de várias instruções. Sua finalidade principal é elevar a **vazão** (*throughput*), não necessariamente reduzir a **latência** de uma instrução individual. A arquitetura do conjunto de instruções (ISA) especifica resultados arquiteturais observáveis; pipeline, forwarding, stalls, previsão de desvios e especulação são técnicas de implementação que devem conservar esses resultados. Um cronograma rápido que lê registrador incorreto continua errado, ainda que apresente ótimo CPI [1].

Este capítulo prossegue a [representação binária, ISA e mapeamento de cache](/pt/topics/machine-representation-isa-cache/). Vamos deduzir um modelo didático deliberadamente restrito, de cinco estágios e emissão única, confrontar seus cronogramas com restrições temporais verificadas independentemente e analisar um preditor de desvios de dois bits. **Não** é uma simulação de CPU moderna Intel/AMD, RISC-V real, cache coerente, espera por memória, exceções precisas ou execução fora de ordem. Esses aspectos exigem contratos e experimentos adicionais [1][2].

## Cinco estágios: latência não é vazão

No pipeline didático, **IF** busca a instrução; **ID** a decodifica e lê registradores; **EX** executa a operação ou calcula endereços; **MEM** representa o acesso a dados; **WB** grava o resultado arquitetural. Assumiremos exatamente um ciclo por estágio, na ordem IF→ID→EX→MEM→WB. Uma instrução emitida no ciclo `s` ocupa essas fases nos ciclos `s, s+1, s+2, s+3, s+4`.

| Emissão | Ciclo 0 | Ciclo 1 | Ciclo 2 | Ciclo 3 | Ciclo 4 | Ciclo 5 | Ciclo 6 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Instrução A | IF | ID | EX | MEM | WB | | |
| Instrução B | | IF | ID | EX | MEM | WB | |
| Instrução C | | | IF | ID | EX | MEM | WB |

Cada instrução isolada demora **cinco ciclos modelados**. Sem hazards e com emissão de uma instrução por ciclo, `n` instruções terminam em `n+4` ciclos. Logo `CPI=(n+4)/n`, aproximando-se de **uma instrução por ciclo** no regime estável, embora cada instrução atravesse cinco estágios [1]. O termo `+4` contabiliza preenchimento e esvaziamento **deste modelo**, não é penalidade fixa de hardware.

Reduzir a quantidade de lógica combinacional em cada estágio pode encurtar o período do clock, mas registradores entre estágios e desequilíbrio de trabalho limitam o ganho. Não é possível comparar CPUs com clocks diferentes usando apenas CPI. Emissão superscalar, etapas com durações diferentes e execução fora de ordem mudam o modelo [2][3].

## Hazards: conflitos estruturais, de dados e de controle

Um **hazard estrutural** aparece quando duas operações disputam um recurso não duplicado no mesmo ciclo, por exemplo uma porta única usada simultaneamente para buscar instrução e ler dados. Nosso modelo presume recursos separados; portanto, **não modela hazard estrutural**. Isso não significa que portas reais sejam ilimitadas.

Um **hazard de dados** surge quando uma instrução precisa de valor ainda não produzido por instrução anterior. O principal caso do pipeline em ordem é **RAW (read after write)**. Já WAR e WAW são conflitos de ordenação especialmente relevantes quando instruções executam ou terminam fora da ordem. Como o exemplo confirma resultados na ordem do programa, não os agenda separadamente. Um **hazard de controle** resulta de desvios ou exceções que alteram a próxima instrução. Trabalho especulativo do caminho incorreto deve ter seus efeitos arquiteturais descartados [1].

Um stall segura fases dependentes; forwarding (ou *bypassing*) envia um resultado diretamente de determinado estágio sem esperar sua gravação no banco de registradores. As técnicas preservam o resultado exigido, mas mudam cronograma e complexidade de circuito. Dependência **load-use** ainda pode exigir stall: o dado chega **ao fim de MEM**, tarde demais para a instrução seguinte consumi-lo no início de EX [1].

## Defina o instante do acesso antes de contar bubbles

Assumiremos que o consumidor lê o banco de registradores no **início de ID** e consome o valor encaminhado no **início de EX**. Resultado de ALU surge **ao final de EX**; dado carregado surge **ao final de MEM**; gravação habitual do registrador ocorre **ao final de WB**. Um valor gerado num ciclo somente poderá ser lido **no começo de ciclo posterior**.

Se `p` é o ciclo de emissão do produtor e `c` o do consumidor:

| Produtor e modo | Emissão mínima do consumidor | Consequência |
| --- | --- | --- |
| Sem forwarding, ALU ou carga | `c >= p+4` | 3 posições vazias |
| ALU com forwarding | `c >= p+1` | Nenhuma bolha |
| Carga com forwarding | `c >= p+2` | 1 posição vazia |

Deduza a primeira linha: produtor grava ao final de WB, em `p+4`. Consumidor começa ID em `c+1`. Para enxergar o novo valor, `c+1 > p+4`; logo `c >= p+4`. Para ALU encaminhada, consumidor EX começa em `c+2 > p+2`; para carga, precisa de `c+2 > p+3`. Alguns materiais permitem gravar em WB e ler em ID **no mesmo ciclo**, em instantes distintos; então o número da primeira linha muda. **Não misture convenções** [1].

## Agendador executável de instruções com dependências RAW

Cada instrução artificial tem a forma `(tipo, destino, fontes)`: `ALU` produz resultado depois de EX e `LOAD` depois de MEM. Esses itens são **metadados de agendamento**, não opcodes reais nem uma implementação da codificação RISC-V. Assumimos uma única saída por instrução, com fontes disponíveis no início ou produzidas por instruções anteriores. Não modelamos stores, aliasing, especulação, exceções nem cache.

O agendador guarda o **último produtor anterior** de cada registrador de entrada. Como emissão e conclusão seguem a ordem do programa, esse é o produtor relevante. Para cada instrução, escolhe o primeiro ciclo de emissão que atende todas as restrições. A função valida o programa antes do cálculo, não modifica estado externo e retorna uma tupla imutável.

```python
def issue_cycles(program, forwarding=True):
    if type(forwarding) is not bool:
        raise ValueError("forwarding must be boolean")
    validated = []
    for operation in program:
        if (not isinstance(operation, tuple) or len(operation) != 3):
            raise ValueError("expected (kind, destination, sources)")
        kind, destination, sources = operation
        if (kind not in ("ALU", "LOAD")
                or not isinstance(destination, str) or not destination
                or not isinstance(sources, tuple)
                or any(not isinstance(src, str) or not src for src in sources)):
            raise ValueError("invalid teaching instruction")
        validated.append((kind, destination, sources))

    writers = {}
    issued = []
    for kind, destination, sources in validated:
        earliest = (issued[-1] + 1) if issued else 0
        for source in sources:
            if source in writers:
                producer_issue, producer_kind = writers[source]
                separation = (4 if not forwarding
                              else 2 if producer_kind == "LOAD" else 1)
                earliest = max(earliest, producer_issue + separation)
        issued.append(earliest)
        writers[destination] = (earliest, kind)
    return tuple(issued)

dependent = [
    ("LOAD", "r1", ()),
    ("ALU", "r2", ("r1",)),
    ("ALU", "r3", ("r2",)),
]
assert issue_cycles(dependent, forwarding=True) == (0, 2, 3)
assert issue_cycles(dependent, forwarding=False) == (0, 4, 8)
assert issue_cycles([("ALU", "a", ()), ("ALU", "b", ())]) == (0, 1)

def modeled_cycles(issue_times):
    return 0 if not issue_times else issue_times[-1] + 5

assert modeled_cycles(issue_cycles(dependent, True)) == 8
assert modeled_cycles(issue_cycles(dependent, False)) == 13
```

No exemplo de três instruções, forwarding produz `(0,2,3)`: a instrução que consome o `LOAD` aguarda uma posição, mas a seguinte consome ALU sem stall adicional. Sem forwarding, temos `(0,4,8)`, com seis posições de emissão vazias. Os tempos totais modelados são respectivamente 8 e 13 ciclos, incluindo quatro estágios após a última emissão. Esses valores são **resultados do modelo**, não medidas de CPU física.

O **invariante de correção** é: depois de agendar `k` instruções, os ciclos de emissão são estritamente crescentes e o último produtor anterior de cada operando concluiu a fase que disponibiliza seu resultado antes da leitura pelo consumidor. Para a instrução seguinte, escolher o menor ciclo que satisfaz todas as desigualdades preserva o invariante. O algoritmo termina para programa finito e validado. Tempo esperado é proporcional ao número de instruções e operandos, presumindo nomes de registradores limitados e busca média constante em dicionários; memória proporcional ao programa e aos destinos distintos.

## Previsão de desvios: contador saturante de dois bits

Um desvio condicional cria dependência de controle: o endereço da próxima busca pode depender de resultado ainda não conhecido. A previsão permite prosseguir antes do resultado; quando está incorreta, instruções especulativas do caminho errado precisam ser descartadas, com penalidade específica da implementação. O processador **não pode confirmar** resultados arquiteturais incorretos por causa da previsão [1][3].

Um **contador saturante de dois bits** possui quatro estados: 0=fortemente não tomado, 1=fracamente não tomado, 2=fracamente tomado e 3=fortemente tomado. Prevê **tomado** nos estados 2/3 e **não tomado** nos estados 0/1. Cada resultado tomado incrementa até o limite 3; um resultado não tomado decrementa até 0. Essa histerese evita inverter forte preferência após uma única observação contrária. É **um único contador didático**, não um preditor moderno de histórico, BTB ou algoritmo de uma CPU real [1].

```python
class TwoBitPredictor:
    def __init__(self, state=1):
        if type(state) is not int or state not in (0, 1, 2, 3):
            raise ValueError("state must be a two-bit integer")
        self.state = state

    def predict(self):
        return self.state >= 2

    def observe(self, taken):
        if type(taken) is not bool:
            raise ValueError("branch outcome must be boolean")
        predicted = self.predict()
        self.state = min(3, self.state + 1) if taken else max(0, self.state - 1)
        return predicted

counter = TwoBitPredictor(1)
outcomes = (True, True, False, False, False)
predictions = tuple(counter.observe(outcome) for outcome in outcomes)
assert predictions == (False, True, True, True, False)
assert sum(a != b for a, b in zip(predictions, outcomes)) == 3
assert counter.state == 0
```

A sequência produz três previsões erradas, incluindo dois erros sucessivos na transição descendente de estados. O invariante é `0 <= state <= 3`; cada observação mantém valor inteiro válido. Entradas precisam ser `bool` explícito; aceitar números arbitrários mascararia um contrato incorreto. O preditor retorna a previsão calculada **antes de atualizar** o estado: verificar apenas o estado final não detectaria um preditor que consulta a resposta e só então afirma que a previu.

## CPI, custo dos desvios e limites da fórmula

Para um modelo simples, com penalidades independentes e não sobrepostas, podemos escrever

`ciclos ≈ instruções + 4 + slots_de_stall + erros_de_previsão × penalidade`.

Essa é uma **aproximação analítica aditiva**, não um simulador de especulação. Pressupõe emissão única, custo fixo de recuperação e ausência de sobreposição entre desvios errados, stalls, faltas de cache e trabalho independente. Numa sequência com 3 erros e penalidade **suposta** de 2 ciclos, acrescentamos 6 ciclos modelados: **não** se demonstra que uma CPU real perde dois ciclos por erro.

Para medir equipamento real são necessários contadores de desempenho e microbenchmarks, controlando processador, compilador, aquecimento, entrada e mistura de instruções. Os manuais Intel discutem otimização e previsão de desvios, mas não justificam transportar o mesmo custo para todas as microarquiteturas [3]. Faltas de cache e previsões erradas são fenômenos distintos; o capítulo [de cache anterior](/pt/topics/machine-representation-isa-cache/) apresenta outra fonte de atraso.

## Paralelismo entre instruções, ordenação e estado preciso

Instruções independentes podem se sobrepor; uma cadeia de dependências define um caminho crítico. Compiladores podem reorganizar cálculos independentes para esconder bolhas de carga, desde que **preservem o comportamento observável**. Hardware também pode encaminhar valores, especular, renomear registradores e executar fora de ordem. Porém renomeação não remove uma dependência RAW verdadeira; o consumidor precisa do resultado lógico produzido antes [2].

Exceções tornam a questão mais delicada: o estado que o software observa deve corresponder a ponto arquiteturalmente bem definido. CPUs modernas podem executar especulativamente e confirmar efeitos numa ordem consistente com o contrato da ISA. Nosso agendador **não contém reorder buffer, exceções, endereços de desvios, dependência de memória ou estado especulativo**; seria incorreto descrevê-lo como traço fiel de CPU [1][2].

## Exercícios e verificação

1. Desenhe os cinco estágios de 3 instruções independentes e explique por que a latência individual é cinco ciclos, apesar de a vazão ideal ser uma por ciclo.
2. Refaça as desigualdades RAW de ALU e carga. Se WB puder gravar antes de ID ler **no mesmo ciclo**, explique como muda a quantidade de bolhas.
3. Agende manualmente `LOAD r1; ALU r2←r1; ALU r3←r2` com e sem forwarding. Compare os ciclos obtidos com o código.
4. Insira uma ALU independente entre LOAD e uso. Determine em que situação a instrução independente ocupa a bolha sem modificar a semântica.
5. Construa instrução com dois operandos produzidos por **escritas anteriores diferentes**. Verifique que prevalece a maior restrição temporal.
6. Desenhe a tabela completa dos quatro estados do preditor e dois resultados possíveis; confirme que a previsão usa o **estado anterior** à atualização.
7. Distinga afirmações de **correção arquitetural**, propriedades de **microarquitetura** e **hipóteses analíticas** presentes na explicação.
8. Imagine uma escrita em memória no caminho errado de um desvio. Mostre por que um preditor de dois bits corretamente implementado não basta para preservar o estado arquitetural.

**Próximos:** [memória virtual e syscalls](/pt/topics/processes-virtual-memory/) tratam outra camada de tradução e proteção; [concorrência](/pt/topics/concurrency-synchronization/) trata interleavings entre threads. Coerência de cache multicore, ordenação real de memória, temporização RISC-V e experimentos com contadores de desempenho exigem capítulos separados [1][2][3].
