---
id: heaps-priority-queues
title: "Heaps binários e filas de prioridade"
description: "Explique os invariantes de forma e ordem, derive atualizações logarítmicas, heapify linear e resolva top-k com exemplos executáveis."
category: algorithms
difficulty: intermediate
updated: 2026-10-09
prerequisites: [complexity-analysis]
sources:
  - {title: "Python Documentation — heapq", url: "https://docs.python.org/3/library/heapq.html", kind: "official language documentation"}
  - {title: "Python Documentation — queue", url: "https://docs.python.org/3/library/queue.html", kind: "official language documentation"}
---
Uma **fila de prioridade** seleciona elementos conforme prioridade, não ordem de chegada. Um heap binário é uma implementação que mantém acesso rápido a uma chave extrema sem ordenar todos os itens. Um **min-heap** remove primeiro a menor chave, convenção usada por heapq em Python [1].

## Dois invariantes distintos

O **invariante de forma** exige árvore binária completa preenchida por níveis da esquerda para a direita. O **invariante de ordem** exige que a chave do pai seja menor ou igual à dos filhos. Irmãos não precisam estar ordenados. Num vetor indexado a partir de zero, os filhos de i estão em 2i+1 e 2i+2; para i>0, o pai está em (i-1)//2 [1].

O vetor [1,4,3,9,8,7] é um min-heap válido mesmo com 4 maior que 3. Cada pai é menor ou igual aos próprios filhos e a transitividade nos caminhos garante que a raiz é o mínimo global. Já [1,7,3,2] não é heap: 7 é pai de 2, mas é maior.

## Inserção, remoção e construção

Para inserir, acrescente o novo item ao fim do vetor, preservando a forma completa, e troque para cima enquanto for menor que o pai. Para remover o mínimo, guarde a raiz, coloque o último item no índice zero e troque para baixo com o menor filho até restaurar a ordem. Apenas um caminho pode estar fora de ordem. Com n elementos, a altura é floor(log2 n), portanto inserção e remoção custam O(log n), enquanto inspecionar a raiz custa O(1) [1].

Construir um heap por inserções sucessivas custa O(n log n). O **heapify de baixo para cima** custa O(n): metade dos nós é folha, aproximadamente um quarto tem altura pelo menos um, e a soma ponderada das alturas internas cresce linearmente. Isso é importante quando todos os dados já estão disponíveis.

## Exemplo: os k maiores valores

Mantenha min-heap com os k maiores valores já observados. A raiz é o menor dos retidos; uma chegada maior que ela a substitui.

~~~python
from heapq import heappush, heapreplace

def maiores_k(valores, k):
    if k < 0:
        raise ValueError('k negativo')
    heap = []
    for valor in valores:
        if len(heap) < k:
            heappush(heap, valor)
        elif k and valor > heap[0]:
            heapreplace(heap, valor)
    return sorted(heap, reverse=True)

assert maiores_k([5, 1, 8, 2, 8, 3], 3) == [8, 8, 5]
assert maiores_k([7, 2], 5) == [7, 2]
assert maiores_k([7, 2], 0) == []
~~~

**Invariante:** após cada prefixo, o heap conserva os maiores min(k, tamanho do prefixo) valores. Cada candidato só substitui o menor retido se for superior. Para n valores e k pelo menos um, o tempo, incluindo ordenação final, é O(n log k + k log k), com O(k) de memória adicional. Esta implementação ainda percorre os n itens quando k é zero.

## Comparação e aplicabilidade

| Operação | Vetor desordenado | Vetor ordenado | Heap binário |
| --- | ---: | ---: | ---: |
| Ler mínimo | O(n) | O(1) no início | O(1) |
| Inserir | O(1) amortizado ao fim | O(n) para deslocar | O(log n) |
| Remover mínimo | O(n) para achar | O(n) para deslocar | O(log n) |
| Buscar chave arbitrária | O(n) | O(log n) | O(n) |

Heap **não** é índice geral de chave. Alterar eficientemente a prioridade de item conhecido exige mapa de posições ou invalidação preguiçosa. Prioridades iguais precisam de critério estável de desempate, como um contador crescente, quando os objetos não admitem comparação. Filas sem limite consomem memória e prioridade estrita pode causar fome das tarefas menos urgentes. heapq por si só não sincroniza threads; queue.PriorityQueue oferece bloqueios apropriados [2].

## Exercícios e verificação

1. Confira pares pai-filho em [1,4,3,9,8,7] e explique a validade do heap apesar de o vetor não estar ordenado.
2. Para fluxo [5,1,8,2] com k=2, os valores retidos evoluem como {5}, {1,5}, {5,8}, {5,8}.
3. Explique por que itens empatados precisam de contador de sequência quando o payload não suporta comparação.
4. Compare saídas sucessivas de heapq.heappop após heapify com a ordenação normal, incluindo duplicatas.
