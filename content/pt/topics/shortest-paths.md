---
id: shortest-paths
title: "Caminhos mínimos: Dijkstra, Bellman–Ford e ciclos negativos"
description: "Demonstre o relaxamento de caminhos mínimos, implemente Dijkstra com heap e analise Bellman–Ford, pesos e ciclos negativos."
category: algorithms
difficulty: advanced
updated: 2026-10-09
prerequisites: [graph-traversal, heaps-priority-queues, complexity-analysis]
sources:
  - {title: "Dijkstra — CP-Algorithms", url: "https://cp-algorithms.com/graph/dijkstra.html", kind: "technical reference"}
  - {title: "Bellman–Ford — CP-Algorithms", url: "https://cp-algorithms.com/graph/bellman_ford.html", kind: "technical reference"}
---
Num grafo sem pesos, a BFS minimiza o número de arestas; num grafo **ponderado**, cada aresta possui um custo numérico. O objetivo passa a ser minimizar a soma dos pesos, e não necessariamente a quantidade de saltos. A escolha do algoritmo depende do sinal dos pesos, da direção das arestas e da existência de ciclos negativos alcançáveis [1][2].

## Problema formal e hipóteses

Para grafo dirigido G=(V,E), um caminho P de origem s a vértice v é uma sequência de vértices adjacentes. Seu custo é a soma dos pesos w(e), e a distância δ(s,v) é o ínfimo de custos de tais caminhos. Para vértice inalcançável, use infinito. Se um **ciclo de peso negativo** é alcançável de s e pode alcançar v, pode ser percorrido repetidamente, reduzindo o custo sem limite: não existe distância mínima finita para v. Em grafo não dirigido, uma aresta negativa percorrível nos dois sentidos já permite um passeio fechado de custo negativo [2].

## Relaxamento: operação comum

Mantenha estimativas d[v], iniciadas com d[s]=0 e d[demais]=infinito. Para aresta u→v de peso w, **relaxe** quando d[u]+w<d[v], atribuindo d[v]=d[u]+w e parent[v]=u. Cada estimativa finita representa um caminho concreto descoberto, portanto nunca é **menor** que o ótimo finito verdadeiro. O relaxamento só reduz estimativas. O desafio é saber quando uma estimativa já é definitiva [1].

![Grafo ponderado: um percurso com mais arestas pode ter custo total menor.](/diagrams/weighted-shortest-path.svg)

## Invariante guloso de Dijkstra

Se todos os pesos alcançáveis são não negativos, retire o vértice ainda não finalizado de menor distância tentativa. Ele não poderá receber caminho menor por outros vértices pendentes: qualquer percurso alternativo teria de atravessar a fronteira dos já finalizados e os pesos restantes não negativos não reduzem o custo. Finalize esse vértice e relaxe suas arestas. Essa é a justificativa gulosa; possuir heap que devolve mínimo, isoladamente, não prova correção [1].

~~~python
from heapq import heappush, heappop

def caminhos_dijkstra(grafo, origem):
    for arestas in grafo.values():
        for _, peso in arestas:
            if peso < 0: raise ValueError("peso negativo")
    distancias = {origem: 0}
    pais = {origem: None}
    heap = [(0, origem)]
    while heap:
        distancia, u = heappop(heap)
        if distancia != distancias[u]:
            continue
        for v, peso in grafo.get(u, []):
            tentativa = distancia + peso
            if tentativa < distancias.get(v, float("inf")):
                distancias[v] = tentativa
                pais[v] = u
                heappush(heap, (tentativa, v))
    return distancias, pais

grafo = {"s":[("a",4),("b",1)], "b":[("a",2),("t",7)], "a":[("t",1)]}
dist, pais = caminhos_dijkstra(grafo,"s")
assert dist["t"] == 4 and pais["t"] == "a"
assert dist["a"] == 3 and "ausente" not in dist
~~~

O dicionário guarda apenas vértices alcançados. Com heap binário e entradas obsoletas descartadas, essa versão custa O((V+E) log(V+E)) e pode armazenar O(V+E) entradas auxiliares. Estruturas especializadas com diminuição de chave têm outros limites; seria errado atribuir memória O(V) a este heap sem ressalva. Objetos de vértices devem ser comparáveis quando distâncias empatam na tupla; use contador inteiro para desempate quando não forem.

## Exemplo calculado passo a passo

Para s→a custo 4, s→b custo 1, b→a custo 2, a→t custo 1 e b→t custo 7: finalize s (distância 0); descubra a:4 e b:1. Finalize b e reduza a de 4 para 3; t passa a 8. Finalize a com 3 e reduza t para 4. Descarte a entrada obsoleta a:4; finalize t com 4. O trajeto s→b→a→t custa 1+2+1=4. A aresta direta s→a usa menos saltos que s→b→a, porém custa mais.

## Bellman–Ford e seus limites de prova

Bellman–Ford relaxa todas as arestas por até |V|-1 rodadas. Um caminho simples mínimo, sem ciclo negativo alcançável, utiliza no máximo |V|-1 arestas: vértices repetidos poderiam ser retirados sem piorar o custo. Após k rodadas, caminhos com até k arestas foram considerados nos limites das distâncias. Logo |V|-1 rodadas bastam; um relaxamento adicional bem-sucedido sinaliza ciclo negativo alcançável capaz de melhorar distância [2].

Com lista de arestas, tempo O(VE) e memória O(V). Encerrar antes caso uma rodada não altere nada é válido, preservadas hipóteses de dados e aritmética. Se existe ciclo negativo alcançável, distâncias dos vértices alcançáveis a partir desse ciclo não são finitas bem definidas. Um ciclo negativo inalcançável de s não prejudica distâncias de outra componente.

## Matriz de escolha e falhas

| Situação | Algoritmo inicial | Restrição |
| --- | --- | --- |
| Arestas unitárias | BFS | Minimiza saltos |
| Arestas com pesos não negativos | Dijkstra | Não aceita pesos negativos |
| Pesos negativos e detecção de ciclos | Bellman–Ford | Custo O(VE) |
| Grafo dirigido acíclico | Relaxamento topológico | Exige DAG |
| Todos os pares | Floyd–Warshall ou execuções repetidas | Custos diferentes |

Não finalize vértice só por tê-lo inserido na fila num grafo ponderado. Um caminho posterior pode reduzir a estimativa. Pesos de ponto flutuante requerem políticas de precisão e infinito. Ciclos negativos destroem o ótimo finito, não apenas um algoritmo. Para reconstruir caminhos, guarde pais e percorra do destino até s, rejeitando destino inalcançável.

**Conexão com pré-requisitos:** [Percurso de grafos](/pt/topics/graph-traversal/) explica camadas da BFS e vértices inalcançáveis. [Heaps binários](/pt/topics/heaps-priority-queues/) explica a extração eficiente da menor estimativa.

## Exercícios e verificação

1. Para s→a peso 8, s→b peso 2 e b→a peso 1, a menor distância até a é 3, não 8. Simule as entradas do heap.
2. Adicione a→t com peso -5: Dijkstra deve rejeitar a entrada, enquanto Bellman–Ford pode tratá-la se não houver ciclo negativo alcançável.
3. Explique por que ciclo negativo **inalcançável de s** não invalida distâncias dos vértices alcançáveis.
4. Compare Dijkstra com Bellman–Ford em grafos pequenos aleatórios com pesos não negativos, sem autolaços.
5. Para cada caminho recuperado, verifique a soma de pesos e existência real das arestas que ligam os predecessores.
