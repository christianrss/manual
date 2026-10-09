---
id: strongly-connected-components
title: "Componentes fortemente conexos e grafos condensados"
description: "Deduza componentes fortemente conexos, prove por que a condensação é acíclica e implemente Kosaraju iterativo com testes."
category: algorithms
difficulty: advanced
updated: 2026-10-09
prerequisites: [graph-traversal, complexity-analysis]
sources:
  - {title: "Strongly Connected Components and Condensation Graph — CP-Algorithms", url: "https://cp-algorithms.com/graph/strongly-connected-components.html", kind: "technical reference"}
  - {title: "Princeton Algorithms — Directed Graphs", url: "https://algs4.cs.princeton.edu/42digraph/", kind: "university course"}
---
Um grafo dirigido pode conter conjuntos de vértices em que todo membro alcança todos os outros. Esses conjuntos máximos são **componentes fortemente conexos** (CFCs). Não equivalem simplesmente aos componentes do grafo sem orientação: a direção determina se há caminho de volta. Descobrir CFCs simplifica ciclos de dependências, agrupa estados mutuamente alcançáveis e revela a estrutura acíclica entre grupos [1].

## Definição, maximalidade e partição

Considere G=(V,E) dirigido. Os vértices u e v são mutuamente alcançáveis quando existe um caminho dirigido de u até v e outro de v até u. Essa relação é de equivalência: reflexiva pelo caminho de comprimento zero, simétrica pela definição e transitiva pela concatenação dos caminhos. Portanto V é particionado em classes sem interseção. Cada classe é máxima, pois adicionar vértice externo violaria a alcançabilidade mútua. Um vértice isolado constitui CFC mesmo sem autolaço; autolaço não é requisito.

Não confunda CFC com componente do grafo não dirigido. Nas arestas A→B e B→C, ignorar direção gera um único componente, mas existem três CFCs unitárias. Por outro lado, A→B→C→A forma uma única CFC.

## Condensação e demonstração de ausência de ciclos

Substitua cada CFC por um vértice. Crie aresta X→Y entre componentes diferentes se alguma aresta original conecta um membro de X a um membro de Y. O resultado é o **grafo condensado**. Ele não pode ter ciclo dirigido entre dois ou mais componentes: caso existisse, todos os componentes do ciclo alcançariam uns aos outros, formando uma CFC maior. Isso contradiz a maximalidade. Assim, a condensação é um grafo dirigido acíclico (DAG) [1].

![Três componentes fortemente conexos são reduzidos a um grafo dirigido acíclico.](/diagrams/scc-condensation.svg)

A demonstração é relevante para dependências. Um escalonador não consegue ordenar topologicamente pacotes que formam ciclo, mas pode ordenar os **grupos** de pacotes mutuamente dependentes. Resolver o ciclo dentro de cada grupo continua sendo problema distinto; condensar não elimina automaticamente a dependência semântica.

## Por que duas buscas em profundidade funcionam

Kosaraju–Sharir executa DFS no grafo original para registrar tempos de término dos vértices. Depois executa DFS no **grafo transposto**, que possui todas as arestas invertidas, considerando vértices em ordem decrescente de conclusão. A segunda etapa encontra uma CFC por busca. A propriedade central é a ordenação dos tempos de saída entre componentes: inverter as arestas impede que a segunda busca escape da componente de origem adequada entre as ainda não processadas [1][2].

A primeira etapa deve alcançar **todos os vértices**, não somente os alcançáveis de uma origem. Registre o vértice ao terminar de explorar descendentes, não quando ele é descoberto. A segunda DFS deve seguir a **ordem inversa de término**. Inverter essas decisões pode unir componentes incorretamente. Transpor muda orientação das arestas, mas preserva as classes de alcançabilidade mútua.

## Implementação iterativa sem risco de pilha recursiva

~~~python
def componentes_fortes(grafo):
    vertices = set(grafo)
    for vizinhos in grafo.values():
        vertices.update(vizinhos)
    vistos, saida = set(), []
    for inicio in vertices:
        if inicio in vistos:
            continue
        vistos.add(inicio)
        pilha = [(inicio, iter(grafo.get(inicio, ())))]
        while pilha:
            vertice, arestas = pilha[-1]
            proximo = next(arestas, None)
            if proximo is None:
                saida.append(vertice)
                pilha.pop()
            elif proximo not in vistos:
                vistos.add(proximo)
                pilha.append((proximo, iter(grafo.get(proximo, ()))))
    reverso = {v: [] for v in vertices}
    for u, vizinhos in grafo.items():
        for v in vizinhos:
            reverso[v].append(u)
    vistos.clear()
    grupos = []
    for inicio in reversed(saida):
        if inicio in vistos:
            continue
        grupo, pendentes = set(), [inicio]
        vistos.add(inicio)
        while pendentes:
            u = pendentes.pop()
            grupo.add(u)
            for v in reverso[u]:
                if v not in vistos:
                    vistos.add(v)
                    pendentes.append(v)
        grupos.append(grupo)
    return grupos

grafo = {0:[1], 1:[0,2], 2:[3], 3:[2,4], 4:[]}
grupos = componentes_fortes(grafo)
assert {frozenset(c) for c in grupos} == {
    frozenset({0,1}), frozenset({2,3}), frozenset({4})
}
assert componentes_fortes({}) == []
assert {frozenset(c) for c in componentes_fortes({7:[7]})} == {frozenset({7})}
~~~

O código usa None como sentinela de esgotamento do iterador; portanto pressupõe rótulos de vértices **diferentes de None**. Rótulos precisam ser hashable, e o exemplo usa inteiros. Uma biblioteca genérica deveria usar um objeto sentinela exclusivo e validar o domínio. A ordem dos conjuntos devolvidos pode variar, pois a coleção inicial é um set; a propriedade assegurada é a composição dos grupos, não sua apresentação.

## Simulação com dois ciclos

Considere 0→1, 1→0, 1→2, 2→3, 3→2 e 3→4. A alcançabilidade mútua gera A={0,1}, B={2,3}, C={4}. A alcança B, mas B não alcança A; B alcança C, mas C não tem caminho de volta. A condensação é A→B→C. Uma ordem topológica possível é A,B,C; a numeração interna dos representantes não determina uma ordem natural.

Para construir o condensado, associe a cada vértice o identificador de sua CFC, percorra arestas originais u→v e crie componente(u)→componente(v) quando forem diferentes. Um conjunto de pares remove arestas duplicadas. A construção visita O(V+E) entradas. Em seguida, aplique ordenação topológica no novo DAG sem encontrar ciclos entre CFCs.

## Modelo de custos e limites práticos

Com listas de adjacência, primeira DFS, transposição e segunda DFS inspecionam O(V+E) elementos cada. O tempo total é **O(V+E)** e listas, adjacência invertida e pilhas usam **O(V+E)** de memória. DFS iterativa evita o limite de recursão Python em grafos profundos, mas os objetos de iterador e pilha continuam consumindo memória. Se arestas chegam em streaming e não podem ser revisitadas, obter o transposto exige reter informações ou usar técnica de memória externa.

Num grafo com milhões de arestas, organização de memória e localidade podem pesar mais que micro-otimizações Python. O algoritmo de Tarjan encontra CFCs em uma travessia, usando índices de descoberta e valores low-link, mas sua correção depende de outro invariante; menos passagens não garantem automaticamente maior velocidade real [1].

## Métodos inadequados e contraexemplos

Union-Find não pode substituir diretamente algoritmos de CFC: DSU acompanha conectividade não dirigida sob uniões, enquanto uma CFC exige caminhos dirigidos **nos dois sentidos**. Uma BFS desde origem única também falha ao ignorar vértices inalcançáveis. Aresta A→B não prova que A e B pertencem à mesma CFC. Reutilizar o conjunto de visitados da primeira etapa sem limpá-lo antes da segunda também é erro frequente.

## Exercícios e verificação

1. Determine CFCs da cadeia 0→1→2 sem arestas inversas. Resposta: três componentes unitárias.
2. Adicione 2→0. Demonstre que os três vértices pertencem a uma única CFC, construindo caminhos de ida e volta.
3. No exemplo do artigo, confirme que o condensado é um DAG e apresente uma ordenação topológica.
4. Implemente arestas de condensação e valide que nenhuma delas conecta a CFC a si mesma.
5. Compare o algoritmo em pequenos grafos aleatórios com oráculo lento: para cada par de vértices, calcule alcançabilidade nos dois sentidos. Esse teste é independente da ordenação por término de Kosaraju.
