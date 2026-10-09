---
id: recursion-call-stack
title: "Recursão, pilha de chamadas e divisão e conquista"
description: "Entenda contratos recursivos, casos-base, quadros da pilha, provas de término e recorrências de divisão e conquista com testes."
category: foundations
difficulty: beginner
updated: 2026-10-09
prerequisites: [complexity-analysis, arrays-and-strings, stacks-queues]
sources:
  - {title: "MIT OpenCourseWare — Introduction to Algorithms", url: "https://ocw.mit.edu/courses/6-006-introduction-to-algorithms-spring-2020/", kind: "university course"}
  - {title: "Python Documentation — sys.getrecursionlimit", url: "https://docs.python.org/3/library/sys.html#sys.getrecursionlimit", kind: "official language documentation"}
---
**Recursão** resolve um problema chamando o mesmo cálculo em instâncias menores. Um programa não é correto apenas porque chama a si mesmo: ele precisa de contrato preciso, cada redução deve caminhar para uma condição de parada e as respostas dos subproblemas devem ser combinadas corretamente. O custo depende tanto da quantidade de chamadas quanto do número de chamadas simultaneamente ativas. As distinções importam em exercícios de programação, algoritmos de árvores e sistemas reais [1].

## Do contrato ao caso-base

Considere calcular fatorial para inteiro n≥0. O contrato matemático é 0!=1 e n!=n×(n−1)! para n>0. O **caso-base** lida com n=0 sem outra chamada. O **caso recursivo** invoca fatorial(n−1) com entrada menor e multiplica por n. O programa também precisa rejeitar n<0: subtrair um de inteiro negativo nunca conduz ao zero.

Término e correção são provas separadas. A medida n é inteiro não negativo que diminui estritamente a cada chamada, portanto não existe sequência infinita antes de chegar ao zero. Para correção, use indução: o caso-base entrega o valor definido; suponha que a chamada menor devolve (n−1)!, então multiplicar por n produz n!, demonstrando o passo.

~~~python
def fatorial(n):
    if not isinstance(n, int) or isinstance(n, bool) or n < 0:
        raise ValueError("esperado inteiro nao negativo")
    if n == 0:
        return 1
    return n * fatorial(n - 1)

assert fatorial(0) == 1
assert fatorial(5) == 120
assert fatorial(1) == 1
try:
    fatorial(-1)
    assert False
except ValueError:
    pass
~~~

A implementação é didática, **não** indicada para qualquer valor arbitrariamente grande de n em Python. Python limita a profundidade de chamadas recursivas para proteger a pilha do interpretador, com valor específico dependendo do ambiente [2]. Um laço iterativo evita um frame por elemento e é preferível para n muito grande.

## Acompanhe a pilha de chamadas, não apenas resultados

Uma invocação cria conceitualmente um **quadro de pilha** com variáveis locais, endereço de retorno e estado da execução. Para fatorial(3), as chamadas entram em fatorial(3) → fatorial(2) → fatorial(1) → fatorial(0). A chamada profunda retorna 1, depois fatorial(1) retorna 1, fatorial(2) retorna 2 e fatorial(3) retorna 6. Quatro quadros ficam simultaneamente ativos, mesmo que o código possua apenas uma chamada recursiva.

![Chamadas recursivas descem ao caso-base e os resultados retornam pelos quadros da pilha.](/diagrams/recursion-call-stack.svg)

A pilha é LIFO: a última função chamada termina primeiro. Um algoritmo recursivo profundo pode esgotar memória ou alcançar limite do interpretador mesmo quando o tempo assintótico é aceitável. Python não oferece garantia geral de eliminação de chamada de cauda com pilha constante. Se a profundidade cresce com entrada não confiável, prefira versão iterativa ou pilha explícita alocada fora da pilha de chamadas.

## Conte chamadas e separe tempo de espaço na pilha

Para fatorial de n≥0 existem n+1 invocações. Ignorando custo de multiplicações de inteiros grandes, o tempo no **modelo de palavras fixas** é Θ(n), enquanto memória adicional da pilha é Θ(n). O inteiro retornado pode ter muitos bits, e operar inteiros grandes não é trabalho constante. Declare o modelo de computação em vez de chamar Θ(n) de limite irrestrito da máquina.

A recorrência T(n)=T(n−1)+Θ(1) se expande para T(n)=Θ(n). O Fibonacci recursivo ingênuo, por outro lado, possui subproblemas sobrepostos: fib(n) chama fib(n−1) e fib(n−2), recalculando valores repetidamente. Sua árvore de chamadas cresce exponencialmente, embora a profundidade máxima continue O(n). **Quantidade de trabalho e profundidade máxima são grandezas distintas**.

~~~python
def fibonacci_memo(n):
    if not isinstance(n, int) or n < 0:
        raise ValueError("n deve ser nao negativo")
    memoria = {0: 0, 1: 1}
    def calcular(k):
        if k not in memoria:
            memoria[k] = calcular(k - 1) + calcular(k - 2)
        return memoria[k]
    return calcular(n)

assert fibonacci_memo(0) == 0
assert fibonacci_memo(1) == 1
assert fibonacci_memo(10) == 55
assert fibonacci_memo(20) == 6765
~~~

Memoização guarda cada subproblema distinto uma única vez. Supondo custo constante de soma e operações de hash, o exemplo gasta O(n) tempo e armazena O(n) valores; a profundidade recursiva continua O(n). Para n grande, Fibonacci iterativo ou método fast doubling pode ser melhor.

## Divisão e conquista versus sobreposição

Divisão e conquista particiona uma entrada, resolve instâncias menores e combina resultados. Mergesort divide a sequência ao meio, ordena ambas as metades e mescla sequências ordenadas; combinar custa Θ(n). Em entradas balanceadas, a recorrência é T(n)=2T(n/2)+Θ(n). Cada nível da árvore recursiva realiza Θ(n) trabalho, e existem Θ(log n) níveis, resultando em Θ(n log n) [1].

Isso difere de Fibonacci ingênuo. As metades do mergesort têm posições disjuntas, enquanto os ramos de Fibonacci perguntam repetidamente por fib(k) igual. **Memoização** ajuda quando há sobreposição, mas não substitui o trabalho de mesclagem da ordenação. A regra de divisão, número de subproblemas e custo de combiná-los determinam a recorrência.

## Demonstre término com uma medida decrescente

Para dividir n elementos, confirme que todo subproblema recursivo possui tamanho estritamente menor quando n ultrapassa o caso-base. Se um algoritmo divide intervalo [inicio,fim) e por engano chama a si mesmo com o intervalo original, um cálculo de meio aparentemente plausível pode criar recursão infinita. Uma **medida bem-fundada**, como fim−inicio, explicita a prova: cada chamada diminui uma quantidade não negativa até o caso-base.

Rotinas mais complexas podem precisar de medida lexicográfica (vértices restantes, alternativas restantes) ou de conjunto de visitados em grafos para impedir ciclos. Fazer recursão em grafo cíclico sem controle de visitados pode não terminar mesmo com número finito de nós.

## Armadilhas de implementação

| Erro | Consequência | Correção |
| --- | --- | --- |
| Esquecer caso-base | Chamadas não terminam | Definir condição terminal primeiro |
| Entrada não diminui | Término não demonstrado | Provar medida decrescente |
| Acumulador mutável padrão compartilhado | Estado vaza entre chamadas | Inicializar por execução |
| Subproblemas exponenciais sobrepostos | Retrabalho | Memoização ou DP |
| Grafo sem visitados | Ciclos repetem chamadas | Marcar vértices |
| Supor otimização de cauda | Estouro da pilha Python | Iterar ou usar pilha explícita |

Criar slices de listas Python também tem custo escondido. Implementar mergesort com slicing cria sublistas; seu consumo de memória difere de uma versão que reutiliza buffers de mesclagem. Calcule complexidade das operações efetivas, não apenas do pseudocódigo.

## Exercícios e verificação

1. Trace fatorial(4) com cinco quadros, apresentando cada retorno. Explique por que a maior profundidade simultânea é cinco.
2. Prove que fatorial termina para n≥0 e identifique por que a prova falha se n negativo for aceito.
3. Desenhe a árvore de fib(5), marque cálculos repetidos de fib(2) e compare com memoização.
4. Use árvore de recursão para deduzir Θ(n log n) de T(n)=2T(n/2)+Θ(n) quando n é potência de dois.
5. Substitua fatorial por loop e explique por que a memória auxiliar da pilha cai para O(1) sob hipóteses iguais de aritmética.

**Leituras relacionadas:** [Pilhas e filas](/pt/topics/stacks-queues/) introduzem LIFO; [análise de complexidade](/pt/topics/complexity-analysis/) trabalha recorrências; [ordenação](/pt/topics/sorting-algorithms/) aplica divisão e conquista.
