---
id: graph-traversal
title: Busca em grafos com BFS e DFS
description: Deduza BFS e DFS, caminhos mínimos em grafos sem pesos, invariantes de visitação e limites de custo em função de vértices e arestas.
category: algorithms
difficulty: intermediate
updated: 2026-10-09
prerequisites:
- complexity-analysis
- hash-tables
sources:
- title: CP-Algorithms — Breadth First Search
  url: https://cp-algorithms.com/graph/breadth-first-search.html
  kind: technical reference
- title: MIT 6.006 — Introduction to Algorithms
  url: https://ocw.mit.edu/courses/6-006-introduction-to-algorithms-spring-2020/
  kind: university course
---
Um grafo `G=(V,E)` reúne vértices e relações entre eles. Pode ser dirigido ou não dirigido; a estrutura de dados escolhida determina quais operações são baratas. Para percorrer vizinhos de cada vértice, listas de adjacência ocupam `O(V+E)` espaço e permitem uma travessia completa com custo `O(V+E)`, desde que os vértices sejam marcados para não repetir trabalho indefinidamente [1].

## Representação e hipóteses
Em uma lista de adjacência, `adj[u]` contém os vizinhos de `u`. Um vértice sem arestas pode ter lista vazia. Em grafo não dirigido, cada aresta normalmente aparece duas vezes, uma em cada extremidade; essa duplicação constante não altera `O(V+E)`. Diferencie um grafo sem pesos de um grafo ponderado: as garantias de caminho mínimo da BFS comum só valem quando cada aresta tem o mesmo custo unitário.

## BFS e o invariante da fila
A **busca em largura** explora vértices por camadas crescentes de distância. Inicialize uma fila com a origem e um conjunto `visitados` contendo a origem. Ao remover `u`, examine vizinhos ainda não vistos, marque-os no momento da inserção e registre `dist[v]=dist[u]+1`. O invariante garante que os elementos saem da fila em ordem não decrescente de distância. Portanto, a primeira descoberta de um vértice fornece seu menor número de arestas a partir da origem [1].

```python
from collections import deque

def distancias(adj, origem):
    fila = deque([origem])
    dist = {origem: 0}
    while fila:
        u = fila.popleft()
        for v in adj.get(u, []):
            if v not in dist:
                dist[v] = dist[u] + 1
                fila.append(v)
    return dist

assert distancias({'a':['b','c'],'b':['d'],'c':['d']}, 'a')['d'] == 2
```

O diagrama a seguir representa o princípio de visitar uma camada antes de passar à seguinte:

![Camadas de um grafo visitado em busca em largura](/diagrams/bfs-graph.svg)

## DFS e diferenças fundamentais
A **busca em profundidade** acompanha um caminho até esgotar vizinhos e então retrocede. Pode usar recursão ou uma pilha explícita. É útil para componentes conexos, ordenação topológica quando aplicável e detecção de ciclos mediante estados de visita. Ao contrário da BFS, a ordem de descoberta da DFS não garante caminho mínimo em grafos sem pesos.

Ambas podem percorrer o grafo em `O(V+E)` tempo com listas de adjacência e `O(V)` memória de marcação e estrutura de busca, além do armazenamento do grafo. Em profundidade recursiva extrema, o limite da pilha é um risco prático.

## Falhas e contraprovas
Marcar o nó somente quando sai da fila pode enfileirar o mesmo vértice inúmeras vezes. Ignorar a possibilidade de ciclos permite repetição infinita. Em grafo dirigido, visitar `u→v` não autoriza inferir a aresta `v→u`. Para pesos positivos arbitrários, utilize algoritmo adequado como Dijkstra com heap, após verificar hipóteses de pesos e representação.

As aulas de algoritmos do MIT apresentam provas formais das propriedades de busca e dos custos de travessia [2].

## Exercícios e verificação
1. Em um grafo `a→b, a→c, b→d, c→d`, a distância BFS de `a` a `d` é `2`.
2. Em grafo com ciclo, indique quando um nó entra em `visitados` para evitar duplicações na fila.
3. Mostre um grafo em que DFS encontra primeiro um caminho mais longo que a distância mínima; isso não viola sua correção como travessia.
