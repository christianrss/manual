---
id: hash-tables
title: Tabelas hash, colisões e invariantes
description: Entenda funções hash, tratamento de colisões, fator de carga e entradas adversariais por meio de um algoritmo verificável e suas limitações.
category: foundations
difficulty: foundational
updated: 2026-10-09
prerequisites:
- complexity-analysis
sources:
- title: MIT 6.006 — Introduction to Algorithms
  url: https://ocw.mit.edu/courses/6-006-introduction-to-algorithms-spring-2020/
  kind: university course
- title: 'Python documentation — Mapping Types: dict'
  url: https://docs.python.org/3/library/stdtypes.html#mapping-types-dict
  kind: language documentation
---
Uma tabela hash associa chaves a valores por meio de uma função de dispersão e um conjunto finito de posições. A vantagem é obter busca, inserção e remoção normalmente rápidas sem manter as chaves ordenadas. A propriedade fundamental não é a ausência de colisões, mas a capacidade de localizar novamente uma chave após inserções, exclusões e redimensionamentos [1].

## Modelo, dispersão e colisões
Com capacidade `m`, uma estratégia simples escolhe a posição `h(chave) mod m`. Como existem mais chaves possíveis do que posições, chaves diferentes podem disputar um mesmo índice. No **encadeamento separado**, cada posição mantém uma coleção de entradas. No **endereçamento aberto**, uma sequência de sondagem procura outras posições; excluir uma entrada não pode interromper a pesquisa por chaves inseridas depois.

O fator de carga `α=n/m` relaciona o número de entradas à capacidade. Uma tabela muito ocupada tende a ter sondagens mais longas. Redimensionar pode exigir reconstruir as posições, pois `m` aparece no cálculo do índice. Sem hipóteses favoráveis de distribuição, o pior caso de uma busca pode percorrer `Θ(n)` entradas [1].

## Igualdade e o invariante de localização
Se duas chaves são consideradas iguais, a semântica de hash precisa ser compatível com a igualdade. Mutar campos que participam do hash depois de inserir a chave pode torná-la inalcançável. Em Python, chaves de dicionário precisam ser hashable; inteiros e strings são exemplos comuns, enquanto listas mutáveis não são aceitas como chaves [2].

## Exemplo correto: primeira repetição
Percorremos a sequência e guardamos em `seen` todos os valores vistos antes do índice atual. Se o valor já existe, a repetição foi encontrada. A prova depende do invariante: imediatamente antes de examinar `items[i]`, o conjunto representa precisamente os valores do prefixo `items[:i]`.

```python
def primeira_repeticao(items):
    vistos = set()
    for valor in items:
        if valor in vistos:
            return valor
        vistos.add(valor)
    return None

assert primeira_repeticao([7, 2, 7, 2]) == 7
assert primeira_repeticao([1, 2, 3]) is None
assert primeira_repeticao([]) is None
```

Para `n` elementos hashable, o tempo esperado é `O(n)` e o espaço auxiliar `O(u)`, onde `u` é o número de valores diferentes. Isso **não** garante tempo `O(n)` no pior caso de colisões. Uma árvore balanceada preserva ordenação e oferece operações logarítmicas no pior caso, sendo mais apropriada para consultas por intervalo.

## Contraprovas e limitações
Uma solução que converte objetos arbitrários para texto pode confundir valores diferentes com representações idênticas. Em dados mutáveis, construa chaves estáveis e explicitamente comparáveis. Também não espere que hash tables forneçam naturalmente a próxima chave ordenada: dispersão e ordenação são objetivos diferentes.

## Exercícios e verificação
1. Se todas as chaves caem no mesmo bucket e usam uma lista simples, uma busca malsucedida pode custar `Θ(n)`.
2. Explique por que uma exclusão ingênua em endereçamento aberto pode quebrar a pesquisa de chaves que vieram depois na mesma sequência de sondagem.
3. Para `[4,4,5,6]`, um conjunto contém três valores distintos. Teste também negativos, lista vazia e todos iguais.

O objetivo é reconhecer os invariantes de localização e de igualdade, não decorar que um dicionário é rápido.
