---
id: complexity-analysis
title: Análise assintótica e custo de algoritmos
description: Aprenda a deduzir custos de tempo e memória por contagens, invariantes e recorrências, distinguindo pior caso, custo amortizado e esperança matemática.
category: foundations
difficulty: foundational
updated: 2026-10-10
prerequisites: []
sources:
- title: MIT 6.006 — Introduction to Algorithms
  url: https://ocw.mit.edu/courses/6-006-introduction-to-algorithms-spring-2020/
  kind: university course
- title: MIT 6.046J — Design and Analysis of Algorithms
  url: https://ocw.mit.edu/courses/6-046j-design-and-analysis-of-algorithms-spring-2015/
  kind: university course
---
A análise assintótica descreve como o custo de um algoritmo cresce quando aumenta o tamanho da entrada. Não é um cronômetro: comparamos funções de custo sob um modelo explícito de operações, tamanho `n` e memória adicional. Um algoritmo rápido em um teste pequeno pode crescer mal em produção. Ao escolher uma estrutura de dados, explicite se mede tempo, espaço auxiliar ou comunicação. O material de algoritmos do MIT apresenta essa disciplina como ferramenta de demonstração, não como uma tabela de respostas [1].

## Definições e hipóteses
Se `T(n)` representa o número de operações para uma entrada de tamanho `n`, escrevemos `T(n)=O(g(n))` quando existem constantes positivas `C` e `n0` tais que `T(n) ≤ C·g(n)` para todo `n ≥ n0`. A notação `Ω` fornece limite inferior; `Θ` exige os dois limites. Isso não garante qualquer desempenho específico em milissegundos. Um pior caso limita todas as entradas daquele tamanho; caso médio depende de uma distribuição declarada; custo esperado pode depender de aleatoriedade interna. Em entrevistas, especifique qual deles foi calculado.

## Derivação a partir do código
No exemplo abaixo, o corpo interno executa exatamente `n(n-1)/2` vezes. A soma é `0+1+...+(n-1)` e portanto `Θ(n²)`, enquanto a memória auxiliar é `Θ(1)`.

```python
def pair_count(items):
    total = 0
    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            total += 1
    return total

assert pair_count([1, 2, 3, 4]) == 6
assert pair_count([]) == 0
```

Se uma busca binária elimina aproximadamente metade do intervalo a cada iteração, após `k` iterações resta `n/2^k`; obter um elemento exige `k≈log₂(n)`. Isso vale apenas quando a coleção está ordenada e os índices são atualizados corretamente. Em algoritmos recursivos, uma recorrência como `T(n)=2T(n/2)+Θ(n)` precisa considerar o custo total por nível e a profundidade da árvore; ignorar o trabalho de combinação produz respostas incorretas [1].

## Amortização, expectativa e armadilhas
Uma matriz dinâmica pode ocasionalmente copiar `n` elementos durante crescimento; com duplicação geométrica, o custo acumulado de várias inserções permanece linear no número de inserções, ou constante **amortizado** por inserção. Isso não afirma que cada inserção custa tempo constante. Uma tabela hash costuma oferecer busca **esperada** próxima de constante sob hipóteses sobre dispersão, mas colisões patológicas mudam o limite de pior caso.

Também diferencie uma cópia `items[:]` de uma leitura: a primeira usa memória proporcional a `n`. Uma operação de string dentro de um laço pode custar mais que uma instrução constante. O tamanho da entrada pode envolver vértices `V` e arestas `E`, não apenas `n`; simplificar incorretamente `O(V+E)` para `O(V)` esconde o custo de examinar conexões.

A disciplina de demonstrar limites por recorrências e análise de algoritmos também é aprofundada em MIT 6.046J [2].

## Contar operações sob um modelo explícito

O exemplo anterior prova a soma triangular e seu custo quadrático. Agora considere um segundo algoritmo: dois laços aninhados, mas o interno dobra seu contador. Não há `n²` operações só porque há dois `for/while`; é necessário contar iterações reais [1].

```python
def visitas_potencias(n):
    if n < 0:
        raise ValueError("n negativo")
    total = 0
    for _ in range(n):
        passo = 1
        while passo <= n:
            total += 1
            passo *= 2
    return total

assert visitas_potencias(0) == 0
assert visitas_potencias(8) == 32
for n in range(1, 65):
    assert visitas_potencias(n) == n * n.bit_length()
```

Para `n >= 1`, o laço interno executa `floor(log₂ n)+1` vezes por iteração externa, portanto `T(n)=n(floor(log₂ n)+1)=Theta(n log(n+1))` no modelo RAM de aritmética de custo constante. O espaço extra é `Theta(1)`. No Python real, inteiros têm precisão arbitrária; para magnitudes enormes, o custo em bits deve ser considerado. Uma busca indexada numa lista ligada, uma consulta SQL e um acesso a RAM também possuem modelos de custo diferentes. Declare os custos das primitivas e se a pilha recursiva integra a memória auxiliar antes de atribuir uma notação.
## Recorrências: expansão, substituição e hipóteses

Considere `T(n)=2T(n/2)+cn` para potências de dois, com `T(1)=d`. A árvore de recursão tem `log₂n` níveis internos, cada qual realizando `cn` operações, e `n` folhas de custo `d`. Logo `T(n)=cn log₂n + dn = Θ(n log n)`. Isso deriva o resultado dessa recorrência; não constitui uma regra para qualquer divisão e conquista [2].

O teorema Mestre trata formas `T(n)=aT(n/b)+f(n)`, com `a≥1, b>1` e condições técnicas adicionais. Compara-se `f(n)` a `n^(log_b a)`; não se aplica acriticamente a subproblemas desiguais nem a funções que violem as hipóteses. Pelo método da substituição, proponha `T(n)≤C n log n`, insira a hipótese na relação e escolha constantes que sustentem a indução. Casos-base e arredondamentos também devem ser tratados.

## Prova amortizada com contagem de cópias

Num vetor que dobra a capacidade quando fica cheio, a inclusão de `n` elementos a partir do vazio provoca, no máximo, cópias somadas `1+2+4+...+2^k < 2n`, além das `n` gravações dos próprios elementos. O custo total é `O(n)` e cada inclusão tem custo **amortizado** `O(1)`; individualmente, uma realocação ainda custa `Θ(n)`. Não há aleatoriedade nessa garantia. No método do potencial, define-se uma função não negativa que representa trabalho antecipadamente pago; custo amortizado = custo real + variação do potencial. A soma telescopa. Um potencial arbitrário ou negativo sem ajuste não prova a afirmação [2].

## Verificação além do benchmark

Antes de implementar, declare domínio da entrada, representação de inteiros, significado de `n`, custo de comparações e acesso por índice e inclusão da pilha recursiva na memória auxiliar. Conte comparações e compare `T(2n)/T(n)`: valores próximos de dois sugerem crescimento linear e de quatro, quadrático, mas caches e constantes podem distorcer. A demonstração fornece o limite assintótico; medições investigam o desempenho real.

**Verificação:** por que uma busca binária numa lista ligada pode não ser `O(log n)`? Porque encontrar cada ponto médio exige percorrer ligações: o acesso aleatório estava implícito. Por que uma busca hash não é `O(1)` incondicional? Porque colisões, distribuição das chaves e detalhes da implementação determinam os limites.

## Exercícios e verificação
1. Conte as iterações de dois laços aninhados, um de `0` até `n-1` e outro de `0` até `i-1`: a soma resulta `n(n-1)/2`, portanto `Θ(n²)`.
2. Uma cópia completa de uma lista de `n` elementos precisa de `Θ(n)` espaço adicional, mesmo sem laços visíveis no código-fonte.
3. Uma busca binária em array não ordenado não preserva a condição que justifica descartar metade dos elementos; o limite logarítmico não torna o resultado correto.

Sempre relacione a notação ao procedimento real, aos invariantes e ao modelo de custo adotado.
