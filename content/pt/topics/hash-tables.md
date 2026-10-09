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

## Da função hash ao índice de armazenamento

Uma tabela hash transforma uma chave `k`, por meio de `h(k)`, em um dentre `m` buckets, geralmente reduzindo o resultado por `h(k) mod m`. **Colisões** são inevitáveis quando o universo de chaves é maior que o conjunto finito de posições. Uma função que sempre retorna o mesmo bucket pode continuar correta se as colisões forem tratadas, mas seu desempenho se deteriora. Boa distribuição empírica não comprova resistência a entradas adversariais [1].

Sejam `n` registros e `α=n/m` o **fator de carga**. Sob hipótese de dispersão uniforme, buscas sem sucesso com encadeamento separado custam em média `Θ(1+α)`, pois cada bucket recebe aproximadamente `α` entradas. Com colisões extremas, o custo é `Θ(n)`. A expectativa depende de um modelo explícito: usar um dicionário não fornece garantia universal de tempo constante [2].

## Encadeamento separado versus endereçamento aberto

O **encadeamento separado** guarda múltiplos registros num mesmo bucket, em listas ou outras estruturas. A exclusão remove o registro sem alterar outros buckets. No **endereçamento aberto**, os registros ocupam posições da própria tabela e a busca percorre uma sequência de sondagem. Sondagem linear aproveita localidade de cache, mas forma agrupamentos; sondagens quadráticas ou hashing duplo alteram a sequência e exigem configuração correta para alcançar as posições necessárias. A exclusão geralmente usa uma marca de remoção (*tombstone*): converter uma posição ocupada em 'nunca usada' pode encerrar uma busca antes de uma chave inserida posteriormente.

| Propriedade | Encadeamento | Endereçamento aberto |
| --- | --- | --- |
| Armazenamento | Referências mais registros | Slots pré-alocados |
| Fator de carga | Pode superar um | Precisa ficar abaixo de um para novas inserções |
| Exclusão | Remoção localizada | Tombstones ou reparo da sondagem |
| Pior caso de busca | Linear | Linear |

## Redimensionamento e invariantes de igualdade

Ao superar um limite de carga, uma tabela pode alocar mais posições e **rehash** dos registros. Isso mantém operações esperadas próximas de constantes ao longo de uma sequência, mas a operação individual de expansão é linear: a garantia é amortizada. Há ainda um invariante decisivo: **chaves consideradas iguais precisam ter o mesmo hash enquanto armazenadas**. Alterar campos que participam do hash após inserir a chave pode torná-la inalcançável. Hash, igualdade, normalização Unicode e sensibilidade a maiúsculas devem ser coerentes.

## Segurança, alternativas e verificação

Um atacante pode construir chaves colidentes quando a função é previsível, consumindo CPU. Endurecimento de hashing em runtimes reduz alguns riscos, mas não substitui limites de tamanho e de quantidade de chaves por requisição. Tabelas hash são adequadas para consultas exatas, não para intervalos ordenados; árvores balanceadas podem oferecer busca por predecessores e limite determinístico logarítmico.

**Exemplo:** para `n=24` chaves e `m=8` buckets, `α=3`. Sob hipótese uniforme, a busca malsucedida por encadeamento percorre em média cerca de três registros, além do acesso ao bucket. Se todas as 24 chaves colidirem, poderá percorrer 24. Para testar, use deliberadamente uma função hash constante, insira chaves distintas e verifique leitura, atualização e exclusão. A correção deve persistir, mesmo com pior desempenho.

## Exercícios e verificação
1. Se todas as chaves caem no mesmo bucket e usam uma lista simples, uma busca malsucedida pode custar `Θ(n)`.
2. Explique por que uma exclusão ingênua em endereçamento aberto pode quebrar a pesquisa de chaves que vieram depois na mesma sequência de sondagem.
3. Para `[4,4,5,6]`, um conjunto contém três valores distintos. Teste também negativos, lista vazia e todos iguais.

O objetivo é reconhecer os invariantes de localização e de igualdade, não decorar que um dicionário é rápido.
