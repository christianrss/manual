---
id: binary-search
title: "Busca binária: limites, invariantes e predicados monótonos"
description: "Deduza a busca binária com invariante de partição, implemente limites, analise complexidade e identifique condições de invalidade."
category: algorithms
difficulty: intermediate
updated: 2026-10-09
prerequisites: [complexity-analysis]
sources:
  - {title: "CP-Algorithms — Binary Search", url: "https://cp-algorithms.com/num_methods/binary_search.html", kind: "technical reference"}
  - {title: "Python Documentation — bisect", url: "https://docs.python.org/3/library/bisect.html", kind: "official language documentation"}
---
A busca binária encontra uma **transição de um predicado monótono** descartando metade das possibilidades a cada passo. Buscar em vetor ordenado é apenas uma aplicação. A correção depende da prova de monotonicidade, não simplesmente de calcular um índice central [1].

## Defina o contrato

Seja a um vetor com n elementos comparáveis em ordem não decrescente. O **limite inferior** de x é a primeira posição i em que a[i] é maior ou igual a x, ou n se ela não existir. O **limite superior** é a primeira posição com valor estritamente maior que x. São posições de inserção, não necessariamente ocorrências. Em [1, 2, 2, 2, 5], o limite inferior de 2 é 1 e o superior é 4; existem 4 menos 1 ocorrências [2].

Defina P(i) como verdadeiro quando a[i] é maior ou igual a x. A ordenação produz falsos seguidos de verdadeiros. Mantenha um intervalo [lo, hi] de **respostas possíveis**, inicialmente [0,n], em que n representa ausência. Em cada passo, examine mid em [lo,hi). Se a[mid] é menor que x, os elementos anteriores também são pequenos demais: faça lo=mid+1. Caso contrário, a primeira posição válida não pode estar depois de mid: faça hi=mid. Assim a resposta permanece em [lo,hi] após cada iteração [1].

## Implementação e verificação

~~~python
def limite_inferior(a, x):
    lo, hi = 0, len(a)
    while lo < hi:
        mid = lo + (hi - lo) // 2
        if a[mid] < x:
            lo = mid + 1
        else:
            hi = mid
    return lo

def limite_superior(a, x):
    lo, hi = 0, len(a)
    while lo < hi:
        mid = lo + (hi - lo) // 2
        if a[mid] <= x:
            lo = mid + 1
        else:
            hi = mid
    return lo

a = [1, 2, 2, 2, 5]
assert (limite_inferior(a, 2), limite_superior(a, 2)) == (1, 4)
assert limite_inferior(a, 3) == 4
assert limite_inferior([], 7) == 0
assert limite_inferior(a, 9) == len(a)
~~~

**Prova:** inicialmente a resposta pertence a [0,n]. A decisão no ponto médio descarta somente posições impossíveis pela hipótese de ordenação. Enquanto lo < hi, o comprimento diminui estritamente, garantindo término. Ao final lo=hi é a menor posição que satisfaz o predicado ou n. É uma prova para todas as entradas válidas, não apenas para os exemplos.

## Complexidade e alternativas

Após k passos restam aproximadamente n/2^k possibilidades. O tempo é O(log(n+1)), com espaço auxiliar O(1), desde que indexação e comparação custem tempo constante. Numa lista ligada, chegar ao ponto médio pode ser caro. A expressão lo+(hi-lo)//2 evita somar dois índices positivos potencialmente grandes em linguagens de inteiros de largura fixa; inteiros comuns de Python não estouram desse modo [1].

| Vetor | Limite inferior de 2 | Limite superior de 2 |
| --- | ---: | ---: |
| Vazio | 0 | 0 |
| [2] | 0 | 1 |
| [1,2,2,5] | 1 | 3 |
| [3,4] | 0 | 0 |

Para achar a menor capacidade viável, defina P(capacidade) como a existência de solução. Se a viabilidade mudar exatamente uma vez de falso para verdadeiro num conjunto finito de inteiros, a busca binária serve. Com R respostas candidatas e custo C por teste, o tempo é O(C log R). Se a viabilidade oscilar, a técnica é incorreta mesmo que cada avaliação seja confiável. Encontrar a posição custa tempo logarítmico, mas inserir em lista Python ainda desloca elementos com custo O(n) [2].

## Falhas e aplicabilidade

Dados desordenados, predicado não monótono, mudança concorrente da sequência, comparador inconsistente e tratamento indefinido de duplicatas quebram o raciocínio. Tabelas hash podem ser melhores para diversas consultas independentes por chave; em vetor minúsculo desordenado, varredura pode custar menos que ordenar. A própria documentação de bisect alerta contra alterações simultâneas durante a busca [2].

## Invariante completo do laço

Interprete a resposta como fronteira numa sequência booleana `P(0),...,P(n-1)`, com todos os valores falsos antes dos verdadeiros. Mantenha `[lo,hi)` com `0≤lo≤hi≤n`, de modo que todo índice abaixo de `lo` já seja conhecido como falso e todo índice a partir de `hi` seja conhecido como verdadeiro (`n` é uma sentinela verdadeira virtual). Inicialmente `lo=0,hi=n`, sem índices excluídos. Para `mid`, se `P(mid)` é falso, monotonicidade elimina `0..mid`, então `lo=mid+1`. Caso contrário, `mid..n-1` é verdadeiro e `hi=mid`. Ao terminar, a fronteira só pode estar em `lo=hi` [1]. Essa é a prova de correção parcial; a redução estrita de `hi-lo` demonstra término.

## Busca em predicados sem decorar modelos

Para 'menor capacidade viável', procure num domínio inteiro **finito e ordenado** cuja viabilidade seja monotônica. Seja `P(C)` a afirmação de que todo o trabalho cabe em no máximo D dias com capacidade C. Se C é viável, qualquer capacidade superior também o é; capacidades menores talvez não sejam. É necessário ter limites corretos, uma fronteira inviável/viável e um verificador de viabilidade correto. Se a viabilidade custa `O(n)` e existem `R` capacidades possíveis, o custo é `O(n log R)`. Um erro dentro de `P` não é consertado pela busca externa.

## Aritmética e restrições reais

Se outra thread altera a coleção durante a busca, até invariantes de índices impecáveis podem falhar: a hipótese de monotonicidade desaparece durante a execução. Em linguagens com inteiros de largura fixa, use `mid=lo+(hi-lo)//2` para evitar overflow de `lo+hi`. Python evita esse overflow nos índices, mas não torna as operações gratuitas. Encontrar a posição em `O(log n)` num vetor não implica inserir em tempo logarítmico: o deslocamento custa `O(n)` [2].

## Testes adicionais de borda

```python
from bisect import bisect_left, bisect_right
for xs in ([], [2], [2,2,2], [1,3,4,8]):
    for key in (-1,0,1,2,3,5,9):
        assert limite_inferior(xs,key) == bisect_left(xs,key)
        assert limite_superior(xs,key) == bisect_right(xs,key)
```

Esses testes **complementam as funções definidas anteriormente no capítulo**: execute os dois blocos na mesma sessão Python. Cubra duplicatas, valores ausentes, entrada vazia e limites externos. Se o vetor não está ordenado, não atribua a resposta incorreta ao código: o contrato da entrada foi violado.

## Exercícios e verificação

1. Rastreie limite inferior de 4 em [1,2,2,5]: avalie índice 2 (valor 2) e depois índice 3 (valor 5); resposta 3.
2. Explique por que P(i) = (a[i] igual a x) não é monótono mesmo com dados ordenados: pode ser falso, verdadeiro e falso novamente.
3. Compare a implementação com bisect_left e bisect_right em casos vazios, duplicados e extremos.
4. Elabore um teste de capacidade, prove a monotonicidade e conte o máximo de avaliações para R=1.024.
