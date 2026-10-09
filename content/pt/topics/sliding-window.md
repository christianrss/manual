---
id: sliding-window
title: Dois ponteiros e janelas deslizantes
description: Derive algoritmos lineares de janela por condições monotônicas e invariantes, identificando corretamente os casos em que o padrão falha.
category: algorithms
difficulty: intermediate
updated: 2026-10-09
prerequisites:
- complexity-analysis
- hash-tables
sources:
- title: USACO Guide — Two Pointers
  url: https://usaco.guide/silver/two-pointers?lang=cpp
  kind: algorithms tutorial
- title: MIT 6.006 — Introduction to Algorithms
  url: https://ocw.mit.edu/courses/6-006-introduction-to-algorithms-spring-2020/
  kind: university course
---
A técnica da janela deslizante mantém um intervalo contíguo `[esquerda, direita]` e atualiza informações agregadas quando seus limites avançam. Funciona especialmente bem quando ampliar e encolher o intervalo preservam uma condição cuja validade pode ser testada incrementalmente. Não é um substituto universal para busca exaustiva: a propriedade de **monotonicidade** precisa ser demonstrada [1].

## Janelas fixas e variáveis
Uma janela de comprimento fixo `k` pode ser atualizada em tempo constante por posição: retire a contribuição do elemento que saiu e acrescente a do novo elemento. Somar cada janela novamente custaria `O(nk)`, enquanto a atualização incremental produz `O(n)` após a soma inicial. Caso `k>n`, decida explicitamente se não existe janela válida; não acesse posições inexistentes.

Nas janelas variáveis, avançamos o limite direito e, quando a condição fica inválida, avançamos o esquerdo até restaurá-la. Cada ponteiro percorre a entrada no máximo `n` vezes, de modo que o número total de movimentos é `O(n)`, mesmo quando há um `while` dentro de um `for`.

## Exemplo: maior substring sem caracteres repetidos
Mantenha `ultimo[c]`, índice da última ocorrência do caractere `c`, e `inicio`, primeiro índice da janela válida. Ao ver um caractere repetido **dentro** da janela, mova `inicio` para depois de sua ocorrência anterior. Nunca mova `inicio` para trás. A cada passo, a janela contém caracteres diferentes e a resposta considera seu comprimento.

```python
def maior_sem_repetir(texto):
    ultimo = {}
    inicio = 0
    melhor = 0
    for fim, caractere in enumerate(texto):
        if caractere in ultimo:
            inicio = max(inicio, ultimo[caractere] + 1)
        ultimo[caractere] = fim
        melhor = max(melhor, fim - inicio + 1)
    return melhor

assert maior_sem_repetir('abcabcbb') == 3
assert maior_sem_repetir('bbbbb') == 1
assert maior_sem_repetir('') == 0
```

O invariante é que os caracteres da janela atual são distintos e nenhum prefixo descartado poderia produzir resultado válido melhor terminando na posição corrente. O algoritmo toma `O(n)` tempo esperado com dicionário hash e espaço `O(min(n,σ))`, em que `σ` é o número de caracteres distintos no domínio considerado.

## Quando o padrão não funciona
O procedimento clássico para encontrar uma soma alvo expandindo enquanto a soma é pequena e contraindo quando é grande assume elementos **não negativos**. Com valores negativos, remover uma posição pode aumentar ou diminuir a adequação da soma de modo não monotônico. Nesse caso, prefix sums combinados com mapa de frequências, ou outra estrutura, podem ser necessários. Da mesma forma, uma condição que depende de elementos fora da janela não é atualizável apenas pelos limites.

Ao analisar limites de complexidade, mantenha explícito o número total de deslocamentos, de acordo com a abordagem de análise de algoritmos do MIT [2].

## Demonstração por movimento monotônico

Um algoritmo de dois ponteiros é linear apenas quando cada ponteiro se move `O(n)` vezes **e** o custo por movimento é limitado. Para uma janela variável `[left,right]`, conte os movimentos totais: `right` avança no máximo `n` vezes e `left` também, totalizando no máximo `2n`. É um argumento **amortizado**: uma iteração do laço externo pode encurtar a janela várias vezes. A presença de dois índices, por si só, não é prova de linearidade [1].

Quando o estado é um dicionário de frequências, inserir aumenta a contagem e remover diminui; exclua entradas zeradas se a quantidade de chaves distintas representar uma condição. O invariante deve declarar exatamente o significado dessas contagens. Confundir os intervalos `[left,right)` e `[left,right]` provoca erros de comprimento e de remoção.

## Exemplo completo de janela fixa

Para `[3,1,4,1,5]` e janela de tamanho `k=3`, a soma inicial é `3+1+4=8`. Desloque: subtraia 3 e some 1, obtendo 6. Desloque outra vez: subtraia 1 e some 5, obtendo 10. O máximo é 10, sem recalcular três parcelas por janela. Invariante: 'current_sum representa a soma dos elementos da janela atual'. Se `k>n`, decida explicitamente se a operação falha, retorna sentinela ou não encontra resultados.

```python
def maior_soma_fixa(valores, largura):
    if largura <= 0 or largura > len(valores):
        raise ValueError("exige 1 <= largura <= tamanho da entrada")
    atual = sum(valores[:largura])
    melhor = atual
    for direita in range(largura, len(valores)):
        atual += valores[direita] - valores[direita-largura]
        melhor = max(melhor, atual)
    return melhor

assert maior_soma_fixa([3,1,4,1,5],3) == 10
assert maior_soma_fixa([-5,-2,-9],2) == -7
```

## Contraexemplo: números negativos rompem a monotonicidade

Procure o menor subvetor de soma ao menos 3. Com `[2,-3,5]`, ampliar a janela de `[2]` para `[2,-3]` **diminui** a soma de 2 para -1; ampliar para `[2,-3,5]` a eleva para 4. O raciocínio habitual 'expandir até válido, contrair enquanto válido' para números não negativos deixa de ser automaticamente correto. Uma alternativa para valores com sinal usa prefixos `p[j]-p[i]` e deque monotônica, com outro invariante [2].

## Comparação com oráculo simples

Para strings curtas aleatórias, compare `longest_unique` com uma implementação de força bruta que enumere todas as substrings e verifique `len(set(trecho))==len(trecho)`. Inclua repetição, entrada vazia, acentos combinados Unicode e sequências longas do mesmo símbolo. O oráculo pode ser lento, pois opera em entradas pequenas e independentes da otimização. Diferencie 'subsequência' (não necessariamente contígua) de 'substring' ou 'subvetor' (contíguos): janelas deslizantes aplicam-se a estes últimos.

## Exercícios e verificação
1. Para `"abba"`, a maior substring sem repetição tem comprimento `2`; verifique por que `inicio = max(...)` evita retroceder.
2. Para `[2,1,3,2]` e `k=2`, calcule as somas `[3,4,5]` em `O(n)`.
3. Construa um caso com elementos negativos em que o algoritmo ingênuo de soma alvo deixa de ser correto.

A habilidade principal consiste em identificar e provar o invariante de janela antes de implementar.
