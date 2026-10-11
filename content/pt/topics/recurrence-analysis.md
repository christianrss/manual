---
id: recurrence-analysis
title: "Resolução de Recorrências: Árvores, Substituição e Teorema Mestre"
description: "Deduza e verifique recorrências de divisão e conquista, contagens exatas, casos do Teorema Mestre, contraexemplos e uso da pilha."
category: foundations
difficulty: intermediate
updated: 2026-10-11
prerequisites: [complexity-analysis, recursion-call-stack]
sources:
  - {title: "MIT 6.006 — Introduction to Algorithms, Lecture Notes", url: "https://ocw.mit.edu/courses/6-006-introduction-to-algorithms-spring-2020/resources/lecture-notes/", kind: "university course notes"}
  - {title: "MIT 6.046J — Recitation Notes, Divide and Conquer", url: "https://ocw.mit.edu/courses/6-046j-design-and-analysis-of-algorithms-spring-2015/pages/recitation-notes/", kind: "university recitation notes"}
  - {title: "MIT 6.046J — Introduction to Algorithms, Lecture 2", url: "https://ocw.mit.edu/courses/6-046j-introduction-to-algorithms-sma-5503-fall-2005/resources/lecture-videos/", kind: "university lecture"}
---
Uma recorrência expressa o custo de um cálculo por meio dos custos de cálculos menores. Ela não representa o *resultado* da função recursiva: um programa pode produzir a mesma resposta com custo linear ou exponencial. O capítulo de [análise de complexidade](/pt/topics/complexity-analysis/) introduz as notações assintóticas; [recursão e pilha de chamadas](/pt/topics/recursion-call-stack/) trata de terminação e frames. Aqui, o objetivo é resolver recorrências de **custo**, sem repetir aquelas introduções. Esses métodos fazem parte das disciplinas de algoritmos do MIT [1][2][3].

Os modelos contam **operações abstratas de custo unitário**, não nanossegundos. Salvo indicação contrária, `n` é uma potência positiva de dois, `T(1)=1` operação abstrata, e as chamadas recursivas são avaliadas sequencialmente. Essas restrições permitem identidades exatas; arredondamentos e custos de instruções reais precisam de tratamento adicional.

## Deduzir a recorrência a partir das chamadas

Considere uma função que divide uma entrada de tamanho `n` em duas metades, processa ambas recursivamente e realiza exatamente `n` unidades de trabalho de combinação quando `n>1`. O contrato de custo é

`T(1)=1` e `T(n)=2T(n/2)+n` para `n=2,4,8,...`.

O fator 2 representa **duas chamadas recursivas**, enquanto o termo `n` representa o trabalho **fora** das chamadas. Um erro frequente é concluir que a complexidade é logarítmica apenas porque cada argumento é reduzido à metade. Isso ignora que as duas metades são executadas. Em busca binária, normalmente apenas uma metade prossegue: um modelo idealizado correspondente é `T(n)=T(n/2)+1` [1].

Uma recorrência precisa especificar domínio, caso-base, quantidade de ramificações e trabalho não recursivo. Se o programa cria fatias de arrays, copiar essas fatias pode alterar o custo. Se subproblemas se sobrepõem, as chamadas devem ser contadas; a introdução de memoização muda o número efetivo de chamadas e pode invalidar a relação de custo original.

## Árvores de recursão: somar o custo por nível

Expanda `T(n)=2T(n/2)+n`. No nível zero há um problema de tamanho `n`, com custo local `n`. No nível um há dois problemas de tamanho `n/2`, cada um custando `n/2`: o total continua `n`. No nível `i`, existem `2^i` problemas de tamanho `n/2^i`, totalizando `n`.

Defina `k=log₂n`, inteiro na hipótese adotada. Os níveis internos `i=0,...,k-1` contribuem `kn`. No nível final há `2^k=n` folhas com custo-base 1. Portanto,

`T(n)=n log₂n+n=n(1+log₂n)=Θ(n log n)`.

Esta é uma **identidade exata do modelo**, não uma contagem exata de comparações em qualquer implementação de merge sort. Laços de intercalação e casos-base podem ter custos diferentes. Se o custo em cada nó for `cn` e cada folha custar `d`, o mesmo raciocínio produz `cn log₂n+dn` [1][3].

## Substituição: provar uma expressão fechada

A árvore sugere `T(n)=n(1+log₂n)`. Demonstre por indução em `k=log₂n`. Para `n=1`, a fórmula fornece 1. Suponha que a fórmula valha para `n/2`. Então,

`T(n)=2(n/2)(1+log₂(n/2))+n`

`=n(1+log₂n-1)+n=n(1+log₂n)`.

A base e o passo indutivo estão demonstrados para todos os `n` permitidos. Encontrar a mesma sequência numérica em algumas execuções não substitui essa prova. Para limites superiores com termos de ordem inferior, pode ser preciso reforçar a **hipótese de indução**, por exemplo acrescentando uma correção linear negativa que viabilize as constantes [2][3].

Outro exemplo mostra por que o formato da árvore não determina sozinho a resposta. Seja `T(n)=2T(n/2)+n²`, com o mesmo custo-base. Substituindo a hipótese `2n²-n`:

`2[2(n/2)²-(n/2)]+n²=2n²-n`.

No caso-base, a expressão também vale 1. Portanto o custo exato desse modelo é quadrático, e não `n log n`, embora a árvore tenha **exatamente a mesma estrutura de ramificação**. É indispensável medir o trabalho local de cada nó.

## Teorema Mestre e condições de aplicação

Para `T(n)=aT(n/b)+f(n)`, com constantes `a>=1`, `b>1`, função `f(n)` assintoticamente não negativa e arredondamentos ausentes ou controlados, defina `p=log_b(a)`. A árvore possui aproximadamente `n^p` folhas. Compare o custo local `f(n)` ao termo `n^p` [2][3].

| Caso | Condição suficiente | Limite justo |
| --- | --- | --- |
| Domínio das folhas | `f(n)=O(n^(p-epsilon))` para algum `epsilon>0` | `Θ(n^p)` |
| Trabalho equilibrado | `f(n)=Θ(n^p log^q n)`, com `q>=0` fixo | `Θ(n^p log^(q+1)n)` |
| Domínio da raiz | `f(n)=Ω(n^(p+epsilon))` e `a f(n/b)<=c f(n)` para algum `c<1`, eventualmente | `Θ(f(n))` |

A **condição de regularidade** da terceira linha é indispensável. A segunda linha inclui uma extensão logarítmica comum da forma elementar, para `q` fixo e não negativo. Não aplique essa tabela indiscriminadamente a funções oscilantes, trabalho negativo, ramificações variáveis ou divisões desiguais.

Para `T(n)=2T(n/2)+1`, `p=1` e o trabalho constante é polinomialmente menor que `n`: `Θ(n)`. Para `T(n)=2T(n/2)+n`, há equilíbrio: `Θ(n log n)`. Para `T(n)=2T(n/2)+n²`, a raiz domina, e a regularidade vale pois `2(n/2)²=n²/2`: `Θ(n²)`. São três recorrências com a mesma ramificação e diferentes taxas de crescimento.

## Casos que exigem outros métodos

A recorrência `T(n)=T(n-1)+n` não reduz o tamanho por fator constante; o Teorema Mestre não se aplica. A expansão fornece `T(n)=1+2+...+n=n(n+1)/2=Θ(n²)`. A profundidade da recursão é `n`, não `log n`, apesar de existir uma única ramificação.

Os casos elementares acima também não classificam diretamente `T(n)=2T(n/2)+n/log₂n`, para potências de dois `n>=2` e `T(1)=1`. Com `k=log₂n`, o trabalho local somado no nível `i` é `n/(k-i)`. Logo o total é `n+n(1+1/2+...+1/k)=n(1+H_k)`, onde `H_k=Θ(log k)` é o número harmônico. O resultado é `Θ(n log log n)` para `n` crescente, intermediário entre linear e `n log n`. Decorar três casos não resolve esse exemplo; a soma por níveis resolve [2].

Uma rotina que divide em `floor(n/2)` e `ceil(n/2)` também não obedece literalmente à recorrência de duas metades iguais. O limite assintótico pode coincidir, mas fórmulas exatas exigem tratar arredondamentos e condições-base.

## Modelos executáveis e reprodução independente

O código a seguir contabiliza níveis de seis **famílias distintas** de recorrências, de maneira iterativa. O resultado é trabalho abstrato total, e não medição de tempo. Rejeita entradas não inteiras, booleanas, não positivas ou que não sejam potências de dois; `kind` deve identificar uma família declarada.

~~~python
def recurrence_work(n, kind):
    if type(n) is not int or n <= 0 or (n & (n - 1)) != 0:
        raise ValueError("n must be a positive power of two")
    branching = {
        "split-unit": 2,
        "split-linear": 2,
        "split-quadratic": 2,
        "split-log": 2,
        "halve-unit": 1,
        "halve-linear": 1,
    }
    if kind not in branching:
        raise ValueError("unknown recurrence family")
    branches = branching[kind]
    nodes, size, total = 1, n, 0
    while size > 1:
        if kind.endswith("unit"):
            local = 1
        elif kind.endswith("quadratic"):
            local = size * size
        elif kind == "split-log":
            local = size * (size.bit_length() - 1)
        else:
            local = size
        total += nodes * local
        nodes *= branches
        size //= 2
    return total + nodes  # each leaf has T(1) = 1

def descending_work(n):
    if type(n) is not int or n < 1:
        raise ValueError("n must be a positive integer")
    total = 1
    for size in range(2, n + 1):
        total += size
    return total

for k in range(9):
    n = 1 << k
    assert recurrence_work(n, "split-unit") == 2 * n - 1
    assert recurrence_work(n, "split-linear") == n * (k + 1)
    assert recurrence_work(n, "split-quadratic") == 2 * n * n - n
    assert recurrence_work(n, "split-log") == n * (1 + k * (k + 1) // 2)
    assert recurrence_work(n, "halve-unit") == k + 1
    assert recurrence_work(n, "halve-linear") == 2 * n - 1
assert descending_work(5) == 15
~~~

Para as famílias de divisão pela metade, o modelo percorre `Θ(log n)` **níveis da árvore** e usa uma quantidade fixa de variáveis inteiras, sob um modelo de operações aritméticas unitárias. O valor retornado pode crescer como `n²`, de modo que o custo em bits dos inteiros Python não permanece constante. O instrumento **não implementa** um algoritmo de ordenação; apenas calcula a contagem idealizada do trabalho associado à recorrência.

## Memória de pilha versus trabalho total

A *largura* da árvore matemática conta ramos da expansão, mas não o número de frames ativos num programa sequencial. Duas chamadas recursivas balanceadas podem gerar `Θ(n)` folhas e manter apenas `Θ(log n)` frames ativos ao longo de um caminho. Buffers de intercalação são memória adicional, possivelmente `Θ(n)`, dependendo da implementação. Uma única chamada com argumento `n-1` resulta em profundidade `Θ(n)`. Portanto a recorrência `T(n)` **não determina sozinha** o uso de memória auxiliar [1].

Substituir a recursão pelo contador iterativo diminui a profundidade *do contador*, não da função real cujo custo ele modela. Em Python, a profundidade de chamadas é limitada; um algoritmo que sempre termina matematicamente ainda pode lançar uma exceção de execução. Em toda análise, separe operações executadas, profundidade máxima, arrays temporários e espaço de saída.

## Exercícios e verificação

1. Resolva `T(n)=T(n/2)+n`, com `T(1)=1`. **Verificação:** os custos por nível são `n,n/2,...,2`, seguidos da folha de custo 1. Portanto `T(n)=2n-1=Θ(n)`.
2. Resolva `T(n)=2T(n/2)+n log₂n` para potências de dois. **Verificação:** o trabalho por nível é `nk,n(k-1),...,n`, com `k=log₂n`, mais `n` folhas. Logo `T(n)=n[1+k(k+1)/2]=Θ(n log²n)`.
3. Explique por que `T(n)=2T(n/2)+n²` é `Θ(n²)`. **Verificação:** os níveis custam `n²,n²/2,n²/4,...`; a soma geométrica não supera `2n²` e o modelo exato vale `2n²-n`.
4. **Exercício inédito:** implemente um avaliador não recursivo com `O(log n)` de espaço para `T(n)=3T(n/3)+n` em potências de três. Prove a fórmula de custo exata independentemente do código anterior e confronte os resultados.
5. Por que a razão medida `T(2n)/T(n)` isoladamente não comprova o limite assintótico? **Verificação:** amostras finitas não provam uma afirmação universal; comportamento de hardware também pode divergir das hipóteses de custo unitário.

As asserções incluídas verificam entradas representativas. Testes separados devem usar outro mecanismo para avaliar a recorrência e conferir entradas inválidas. Mesmo assim, testes ou gráficos de crescimento não substituem demonstrações indutivas.
