---
id: dynamic-programming
title: 'Programação dinâmica: estados e recorrências'
description: Aprenda a definir estados, derivar recorrências, demonstrar transições e escolher memoização ou tabulação com limites de custo explícitos.
category: algorithms
difficulty: intermediate
updated: 2026-10-09
prerequisites:
- complexity-analysis
sources:
- title: CP-Algorithms — Introduction to Dynamic Programming
  url: https://cp-algorithms.com/dynamic_programming/intro-to-dp.html
  kind: technical reference
- title: MIT 6.006 — Introduction to Algorithms
  url: https://ocw.mit.edu/courses/6-006-introduction-to-algorithms-spring-2020/
  kind: university course
---
Programação dinâmica resolve problemas combinando subproblemas menores cujas soluções são reutilizadas. O ponto central é definir um **estado suficiente**: um resumo da informação necessária para tomar a próxima decisão, sem carregar o histórico inteiro. Um código que apenas usa uma tabela não é necessariamente uma solução correta; é preciso provar que a recorrência cobre todas as possibilidades relevantes [1].


![Tabela de dependências da programação dinâmica para a maior subsequência comum das strings AB e BA.](/diagrams/dynamic-programming-invariant.svg)

## Do problema ao estado
Antes de codificar, responda: o que representa `dp[i]`? Qual é o caso base? Como se relacionam estados menores? Em qual ordem eles precisam ser avaliados? Se dois históricos diferentes produzem o mesmo estado, eles devem admitir as mesmas decisões futuras e o mesmo custo ótimo restante. Caso contrário, faltam variáveis no estado.

Considere o problema de obter uma soma `A` com o menor número de moedas de valores inteiros positivos, com suprimento ilimitado. Defina `dp[x]` como o número mínimo de moedas para formar `x`, ou infinito quando impossível. A base é `dp[0]=0`. Para `x>0`, qualquer solução termina com alguma moeda `c ≤ x`; removê-la deixa uma solução para `x-c`. Logo: `dp[x]=1+min(dp[x-c])` sobre moedas válidas. Essa derivação exige que as moedas tenham valor positivo e que exista uma solução finita para o subproblema [1].

## Implementação e prova
```python
def min_moedas(moedas, alvo):
    if alvo < 0 or any(c <= 0 for c in moedas):
        raise ValueError('entrada inválida')
    infinito = alvo + 1
    dp = [infinito] * (alvo + 1)
    dp[0] = 0
    for x in range(1, alvo + 1):
        for c in moedas:
            if c <= x:
                dp[x] = min(dp[x], dp[x-c] + 1)
    return -1 if dp[alvo] == infinito else dp[alvo]

assert min_moedas([1, 3, 4], 6) == 2
assert min_moedas([4, 6], 5) == -1
```

**Invariante:** antes de calcular `dp[x]`, todos os estados de valores menores estão corretos. Como cada moeda é positiva, `x-c<x`; a hipótese de indução justifica cada transição. Toda solução para `x` termina com alguma moeda permitida, então tomar o mínimo entre essas possibilidades não elimina a solução ótima.

## Custos e escolhas
Para alvo `A` e `k` tipos de moedas, a tabulação usa `O(Ak)` tempo e `O(A)` espaço. A memoização calcula estados sob demanda com custo semelhante na pior hipótese, mas usa pilha de recursão e pode estourar o limite. Uma estratégia gulosa que escolhe sempre a maior moeda não é correta para todos os sistemas: com `[1,3,4]` e alvo `6`, escolhe `4+1+1`, enquanto o ótimo é `3+3`.

Quando o estado inclui índice e capacidade, a tabela pode ser bidimensional. Reduzir memória exige verificar se uma atualização sobrescreve estados ainda necessários na mesma iteração.

As notas do MIT discutem o raciocínio por subproblemas e a ordem de avaliação, que complementam a derivação exposta [2].

## Correção formal do estado por indução

O estado da programação dinâmica precisa resumir toda a informação relevante para decisões futuras. No problema das moedas positivas, `dp[x]` guarda o ótimo para a quantia exata `x`, e a recorrência examina cada **última moeda** possível. Prove por indução forte em `x`: `dp[0]=0` é ótimo; para `x>0`, cada candidato contém uma moeda `c` e uma solução ótima para a quantia menor `x-c`, ótima pela hipótese indutiva. Tomar o mínimo cobre todas as soluções válidas. Essa prova falha se denominações nulas ou negativas criarem dependências que não diminuem [1].

## Segundo modelo: maior subsequência comum

Para strings `A` e `B`, defina `dp[i][j]` como o comprimento da maior subsequência comum (LCS) dos prefixos `A[:i]` e `B[:j]`. Casos-base: `dp[0][j]=dp[i][0]=0`. Se os últimos caracteres coincidem, é possível incluí-los numa solução ótima: `dp[i][j]=dp[i-1][j-1]+1`. Se diferem, ao menos um deles é excluído, então `dp[i][j]=max(dp[i-1][j],dp[i][j-1])`. Para comprimentos `m,n`, a tabela demanda `O(mn)` tempo e espaço; manter linhas adjacentes reduz o espaço do **cálculo do comprimento** para `O(min(m,n))`, mas reconstruir a sequência exige preservar decisões adicionais [2].

```python
def comprimento_lcs(a,b):
    anterior = [0]*(len(b)+1)
    for x in a:
        atual = [0]*(len(b)+1)
        for j,y in enumerate(b,1):
            atual[j] = anterior[j-1]+1 if x == y else max(anterior[j],atual[j-1])
        anterior = atual
    return anterior[-1]

assert comprimento_lcs("ABCBDAB","BDCABA") == 4
assert comprimento_lcs("","x") == 0
assert comprimento_lcs("abc","def") == 0
```

## Memoization ou tabulation: escolha prática

A memoização de cima para baixo memoriza só estados visitados, mas requer pilha de recursão suficiente e chaves de cache inequívocas. A tabulação de baixo para cima exige ordem que respeite dependências, facilitando previsão de memória e custo. Em ambos os casos, número de estados distintos multiplicado pelo trabalho por estado é o ponto de partida; hash de chaves grandes e cópia de sequências para o cache também custam. Reduzir memória só é válido depois de demonstrar que estados descartados não serão utilizados novamente.

## Tempo pseudopolinomial e atalhos gulosos inválidos

O algoritmo de moedas custa `O(A·C)` para quantia numérica `A` e quantidade de denominações `C`. Como representar `A` em binário exige `Θ(log A)` bits, o algoritmo é **pseudopolinomial**, não polinomial no tamanho codificado da entrada. A estratégia 'pegar sempre a maior moeda' falha para `1,3,4` e quantia 6: `4+1+1` perde para `3+3`. Estratégias gulosas precisam de argumento de troca ou demonstração específica para o sistema de moedas.

**Verificações:** explique por que denominações negativas não cabem no estado atual sem revisão; derive a LCS de `"ab"` e `"ba"` (resposta 1); mostre por que DP com `2^n` estados não é necessariamente eficiente mesmo que cada transição tenha custo constante.

## Exercícios e verificação
1. Explique por que `dp[0]=0` e por que a recorrência precisa tratar alvo inalcançável.
2. Para moedas `[2,5]` e alvo `7`, a resposta é `2`; para alvo `1`, é `-1`.
3. Mostre um contraexemplo à abordagem gulosa para moedas `[1,3,4]` e alvo `6`.

O método útil é derivar estado, transição e prova; decorar padrões de tabelas não substitui esse raciocínio.
