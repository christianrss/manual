---
id: algorithm-interview-workshop
title: "Oficina de algoritmos: salas para intervalos e janelas com negativos"
description: "Resolva dois exercícios originais com heap e deque monotônica, provas, contraexemplos e testes exaustivos independentes."
category: algorithms
difficulty: intermediate
updated: 2026-10-09
prerequisites: [heaps-priority-queues, two-pointers-prefix-sums, monotonic-stacks]
sources:
  - {title: "Amazon SDE II Interview Preparation", url: "https://amazon.jobs/content/en/how-we-hire/sde-ii-interview-prep", kind: "official preparation overview"}
  - {title: "Python — heapq", url: "https://docs.python.org/3/library/heapq.html", kind: "official language documentation"}
  - {title: "Python — collections.deque", url: "https://docs.python.org/3/library/collections.html#collections.deque", kind: "official language documentation"}
---
Prática de programação vale quando o candidato consegue **especificar contrato, derivar invariante, justificar complexidade e refutar alternativas tentadoras** sem depender de uma IDE. Este capítulo contém dois exercícios originais: determinar a quantidade mínima de salas para intervalos e encontrar o menor subarray cuja soma alcança uma meta mesmo com números negativos. Eles exigem ideias distintas—heap ordenado e deque monotônico—e não são questões vazadas nem garantidas de entrevistas. Preparação técnica de qualidade privilegia correção, manutenção e código testado, não memorização de receitas [1].

## Protocolo de oficina: defina antes de codificar

Em cada exercício, informe o que a função recebe, o que retorna, quais são as regras de fronteira e quais entradas inválidas serão rejeitadas. Comece por exemplos pequenos e argumento explícito de limite inferior. Depois escreva código com nomes claros, execute casos-limite e justifique complexidade no pior caso. Um contraexemplo bem escolhido a solução incorreta é mais convincente que muitos asserts triviais.

Ao resolver sem IDE, mantenha lista mental: coleção vazia, elemento único, duplicatas, extremos que se tocam, entrada grande, negativos quando cabíveis e possibilidade de alterar a entrada. Indique qual variável é n; chamar algoritmo de O(n) sem contabilizar ordenação ou custo do heap não explica seu trabalho real.

## Exercício A: mínimo de salas para intervalos

**Contrato:** dados n intervalos semiabertos [início,fim), com início estritamente menor que fim, devolva a menor quantidade de salas idênticas para acomodar todos sem alterar horários. [1,3) e [3,5) podem usar mesma sala. A saída é inteiro e os dados do chamador não devem ser modificados.

A resposta é o **máximo de trabalhos simultaneamente ativos** em qualquer instante: tarefas que se sobrepõem precisam de salas diferentes, enquanto sala liberada ao término pode ser reaproveitada. Ordene por início e guarde num min-heap os términos das tarefas ativas. Antes de começar nova tarefa, remova términos menores ou iguais ao início atual; insira o novo término e registre tamanho máximo do heap [2].

![A varredura de intervalos usa heap de términos ativos; uma deque monotônica resolve somas com negativos.](/diagrams/algorithm-interview-workshop.svg)

~~~python
from heapq import heappush, heappop

def minimo_salas(intervalos):
    for inicio, fim in intervalos:
        if inicio >= fim:
            raise ValueError("duracao precisa ser positiva")
    finais_ativos = []
    maximo = 0
    for inicio, fim in sorted(intervalos):
        while finais_ativos and finais_ativos[0] <= inicio:
            heappop(finais_ativos)
        heappush(finais_ativos, fim)
        maximo = max(maximo, len(finais_ativos))
    return maximo

assert minimo_salas([]) == 0
assert minimo_salas([(1,3), (3,5)]) == 1
assert minimo_salas([(0,5), (1,4), (2,3)]) == 3
assert minimo_salas([(0,4), (2,6), (4,8)]) == 2
try:
    minimo_salas([(2,2)])
    assert False
except ValueError:
    pass
~~~

Quando uma tarefa começa, remover as concluídas deixa no heap exatamente as tarefas anteriores que se sobrepõem à nova. O tamanho após inserir é a quantidade simultaneamente ativa naquele instante. Todo pico de sobreposição ocorre logo após algum início; o máximo registrado é limite inferior das salas necessárias. Reaproveitar salas liberadas atinge esse limite, demonstrando ótimo.

Ordenar custa O(n log n), e cada término entra e sai do heap no máximo uma vez, custando O(n log n) adicionais e O(n) memória auxiliar. A saída é contagem, não atribuição de sala. Para devolver salas concretas, mantenha heap de pares (fim,id_sala) e lista de IDs livres; a solução de contagem não preserva identidade de salas.

## Resposta errada A: olhar somente a primeira tarefa

Solução incorreta comum conta os intervalos que se sobrepõem à primeira tarefa e usa esse valor como resposta. O pico pode ocorrer muito depois. Em [(0,1), (2,6), (3,5), (4,7)], a primeira não conflita com nenhuma, enquanto três posteriores se sobrepõem. Outro erro é remover término apenas quando `fim < início`: conta falsamente [1,3) e [3,4) como duas salas na convenção semiaberta.

Um oráculo lento pode avaliar simultaneidade em todos os instantes de início. Para cada início t, conte trabalhos com início ≤ t < fim; o máximo é a resposta. Esse oráculo O(n²) é deliberadamente mais lento, mas é independente do heap e fácil de auditar.

~~~python
def oraculo_salas(intervalos):
    return max((sum(a <= t < b for a, b in intervalos)
                for t, _ in intervalos), default=0)

from itertools import combinations
opcoes = [(a,b) for a in range(4) for b in range(a+1,5)]
for tamanho in range(5):
    for teste in combinations(opcoes, tamanho):
        assert minimo_salas(teste) == oraculo_salas(teste)
~~~

O teste exaustivo cobre domínio finito de tempos inteiros, não qualquer timestamp real. O invariante dos intervalos justifica o caso geral; o oráculo evita erros de implementação.

## Exercício B: menor subarray não vazio com soma pelo menos K

**Contrato:** dado array de n inteiros, possivelmente negativos, e meta inteira **positiva** K, devolva o comprimento mínimo de um subarray **contíguo e não vazio** cuja soma seja pelo menos K. Se não existir, retorne -1. Rejeite K não positivo. Diferentemente da janela com números positivos, ampliar a direita pode **reduzir** a soma; retirar o primeiro número pode aumentá-la quando ele é negativo.

Para [2,-1,2] e K=3 a resposta é 3; com K=2 é 1. Janela deslizante que encolhe somente após alcançar K pode perder solução ótima quando negativos anulam monotonicidade. A solução linear usa **somas prefixadas e deque monotônica** [3].

## Derivação do invariante com prefixos

Defina P[0]=0 e P[j]=soma dos primeiros j números. A soma da faixa [i,j) é P[j]-P[i]. Para cada fim j, procuramos i anterior com P[j]-P[i] ≥ K e desejamos minimizar j-i. Mantenha candidatos numa deque com índices crescentes e valores prefixados **estritamente crescentes**.

Quando P[j] satisfaz o limite contra a frente, ela produz subarray válido; registre comprimento e retire a frente. Para aquele começo, j já é o primeiro término válido, então nenhum término futuro produzirá resultado menor. Antes de inserir j, elimine índices no fim da deque com prefixos ≥ P[j]: o índice mais recente j produz intervalos menores ou iguais e sua soma futura será maior ou igual. Essa dominância explica a correção.

~~~python
from collections import deque

def menor_soma_minima(valores, alvo):
    if alvo <= 0:
        raise ValueError("alvo deve ser positivo")
    prefixo = [0]
    for numero in valores:
        prefixo.append(prefixo[-1] + numero)
    candidatos = deque()
    melhor = len(valores) + 1
    for direita, atual in enumerate(prefixo):
        while candidatos and atual - prefixo[candidatos[0]] >= alvo:
            melhor = min(melhor, direita - candidatos.popleft())
        while candidatos and prefixo[candidatos[-1]] >= atual:
            candidatos.pop()
        candidatos.append(direita)
    return melhor if melhor <= len(valores) else -1

assert menor_soma_minima([2,-1,2],3) == 3
assert menor_soma_minima([2,-1,2],2) == 1
assert menor_soma_minima([-5,2,3],5) == 2
assert menor_soma_minima([],1) == -1
assert menor_soma_minima([1,-1,5],5) == 1
try:
    menor_soma_minima([1,2],0)
    assert False
except ValueError:
    pass
~~~

Cada índice entra uma vez e sai por uma extremidade no máximo uma vez; portanto são O(n) operações de deque. Construir P também custa O(n) tempo e espaço. Em Python, inteiros aumentam de precisão para guardar soma exata; em linguagem com inteiros limitados, use tipo suficientemente largo e discuta overflow.

## Oráculo independente e limites

Considere todos os subarrays [i,j) por soma acumulada desde cada i. Custa O(n²) tempo para n elementos e O(1) armazenamento extra. É fácil conferir independentemente e serve como teste de regressão do algoritmo amortizado. Teste exaustivamente sequências curtas no domínio {-2,-1,0,1,2} e metas positivas, cobrindo prefixos duplicados e números negativos.

~~~python
from itertools import product

def oraculo_menor(valores, alvo):
    melhor = len(valores) + 1
    for i in range(len(valores)):
        soma = 0
        for j in range(i, len(valores)):
            soma += valores[j]
            if soma >= alvo:
                melhor = min(melhor, j - i + 1)
    return melhor if melhor <= len(valores) else -1

for n in range(6):
    for arr in product((-2,-1,0,1,2), repeat=n):
        for meta in (1,2,3,4):
            assert menor_soma_minima(arr, meta) == oraculo_menor(arr, meta)
~~~

Deque monotônica resolve esse problema **estático unidimensional** de somas prefixadas. Não é estrutura genérica para atualizações arbitrárias em faixas e não substitui escalonamento de intervalos. Se valores mudam entre consultas, outras estruturas e garantias podem ser necessárias.

## Rubrica de revisão e variações

| Critério | Salas | Subarray mínimo |
| --- | --- | --- |
| Contrato | Intervalos semiabertos com duração positiva | Inteiros, K positivo, resposta não vazia |
| Invariante | Heap de términos ativos | Prefixos candidatos crescentes |
| Ótimo | Limite inferior por sobreposição | Prefixos antigos dominados são eliminados |
| Complexidade | O(n log n), O(n) espaço | O(n) tempo, O(n) espaço |
| Contraexemplo | Limites tocados / pico posterior | Negativos invalidam janela positiva |
| Oráculo | Contar ativos nos inícios | Enumerar todos os subarrays |

Numa revisão cronometrada, explique provas sem olhar código e reescreva ambas as funções com testes. Depois altere uma regra—intervalos fechados no exercício A ou números somente positivos no B—e indique precisamente qual comparação ou algoritmo poderia ser simplificado.

## Exercícios e verificação

1. Para [(0,1),(2,6),(3,5),(4,7)], percorra o heap e obtenha pico de salas.
2. Por que usar `<` em vez de `<=` ao liberar uma sala viola os extremos semiabertos?
3. Prove que prefixo antigo com valor pelo menos tão alto quanto prefixo novo pode sair da deque.
4. Dê sequência com números negativos na qual o argumento convencional de janela positiva não vale.
5. Amplie os oráculos independentes com outro domínio curto, preservando qualquer contraexemplo antes de modificar a solução otimizada.

**Capítulos relacionados:** [Heaps](/pt/topics/heaps-priority-queues/), [intervalos](/pt/topics/greedy-intervals/), [prefixos](/pt/topics/two-pointers-prefix-sums/) e [pilhas monotônicas](/pt/topics/monotonic-stacks/) fornecem os fundamentos.
