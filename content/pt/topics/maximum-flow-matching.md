---
id: maximum-flow-matching
title: "Fluxo máximo, corte mínimo e emparelhamento bipartido"
description: "Deduza conservação de fluxo, rede residual, caminhos aumentantes, teorema fluxo-corte e redução de emparelhamento com código testado."
category: algorithms
difficulty: advanced
updated: 2026-10-09
prerequisites: [graph-traversal, disjoint-set-union, complexity-analysis]
sources:
  - {title: "Maximum flow — Edmonds–Karp", url: "https://cp-algorithms.com/graph/edmonds_karp.html", kind: "algorithmic reference"}
  - {title: "Kuhn's algorithm — Maximum bipartite matching", url: "https://cp-algorithms.com/graph/kuhn_maximum_bipartite_matching.html", kind: "algorithmic reference"}
---
Uma rede com arestas dirigidas e capacidades não negativas modela quantas unidades de material, informação ou trabalho podem ser transportadas da origem ao destino. **Fluxo máximo** procura a maior vazão viável. Seu invariante é conservação: vértices intermediários não criam nem destroem unidades. Diferentemente de caminhos mínimos, escolher um percurso favorável não basta; rotas disputam gargalos e escolhas antigas podem precisar ser desfeitas [1].

## Defina viabilidade antes da otimização

Para grafo dirigido G=(V,E), origem s distinta do destino t, capacidade c(u,v)≥0 e fluxo f(u,v), imponha 0≤f(u,v)≤c(u,v) em cada aresta original. Em todo vértice distinto de s e t, a soma dos fluxos que entram é igual à dos que saem. O **valor do fluxo** é a saída líquida de s, ou entrada líquida em t. Numa implementação, uma aresta residual inversa representa a capacidade de cancelar alocação anterior, sem inventar fluxo físico negativo sobre a aresta original.

Capacidades devem ter **unidade** coerente: requisições/s, veículos/hora ou unidades inteiras abstratas. Ligações distintas com limites próprios não asseguram que todas atinjam sua capacidade ao mesmo tempo caso compartilhem gargalo real. O grafo é um modelo e suas hipóteses precisam ser declaradas.

## Rede residual e aumento de fluxo

Numa aresta com capacidade c e fluxo f, a **capacidade residual direta** é c−f: quanto ainda pode passar. A **capacidade residual inversa** é f: quanto pode ser cancelado para redistribuir em outro caminho. Isso explica por que algoritmo guloso que só acrescenta fluxo direto pode parar antes do ótimo. Um **caminho aumentante** liga s a t usando apenas arestas com capacidade residual positiva. Seu gargalo é o menor residual do percurso; aumentar esse valor preserva conservação e capacidades [1].

![Capacidade residual, caminhos aumentantes e fluxo entre origem e destino.](/diagrams/maxflow-residual.svg)

Repetir buscas aumentantes constitui o método Ford–Fulkerson. Para capacidades inteiras, cada aumento positivo eleva fluxo integral e o procedimento termina, mas a quantidade de passos pode depender numericamente do fluxo máximo. Capacidades reais arbitrárias exigem cuidado adicional com término conforme escolha dos percursos. **Edmonds–Karp** seleciona via BFS o caminho aumentante mais curto **em quantidade de arestas residuais**, obtendo limite de tempo polinomial [1].

## Implementação executável de Edmonds–Karp

A versão aceita vértices de 0 até n−1 e triplas (u,v,capacidade), inclusive arestas paralelas. Representa em cada par ordenado uma capacidade residual agregada. Se há arestas originais em ambos os sentidos, suas contribuições convivem corretamente nessa representação.

~~~python
from collections import deque

def fluxo_maximo(n, arestas, origem, destino):
    if n < 2 or not 0 <= origem < n or not 0 <= destino < n or origem == destino:
        raise ValueError("grafo ou extremos invalidos")
    vizinhos = [set() for _ in range(n)]
    residual = {}
    for u, v, capacidade in arestas:
        if not 0 <= u < n or not 0 <= v < n or capacidade < 0:
            raise ValueError("aresta invalida")
        if u == v:
            continue
        vizinhos[u].add(v)
        vizinhos[v].add(u)
        residual[(u,v)] = residual.get((u,v), 0) + capacidade
        residual.setdefault((v,u), 0)

    total = 0
    while True:
        pai = {origem: None}
        fila = deque([origem])
        while fila and destino not in pai:
            u = fila.popleft()
            for v in vizinhos[u]:
                if v not in pai and residual.get((u,v), 0) > 0:
                    pai[v] = u
                    fila.append(v)
        if destino not in pai:
            return total
        gargalo = float("inf")
        v = destino
        while v != origem:
            u = pai[v]
            gargalo = min(gargalo, residual[(u,v)])
            v = u
        v = destino
        while v != origem:
            u = pai[v]
            residual[(u,v)] -= gargalo
            residual[(v,u)] = residual.get((v,u), 0) + gargalo
            v = u
        total += gargalo

rede = [(0,1,3),(0,2,2),(1,2,1),(1,3,2),(2,3,3)]
assert fluxo_maximo(4, rede, 0, 3) == 5
assert fluxo_maximo(3, [(0,1,2),(0,1,4),(1,2,6)], 0, 2) == 6
assert fluxo_maximo(3, [(0,1,2)], 0, 2) == 0
~~~

Aresta inexistente tem capacidade residual zero. Os testes usam inteiros finitos; a função também aceita capacidades decimais não negativas, mas erros de ponto flutuante podem dificultar o teste de positividade. Para grafos enormes, prefira registros indexados compactos em lugar de dicionários de tuplas e conjuntos.

## Demonstração do limite polinomial

Cada BFS percorre rede residual com O(E) arestas em lista de adjacência, onde E conta arestas originais (incluir inversas apenas multiplica por constante). As distâncias da origem aos vértices, medidas no menor caminho residual, não diminuem durante o algoritmo. Sempre que uma aresta é saturada e volta a ser útil mais tarde, distâncias relevantes precisam aumentar. Cada aresta sofre essa situação no máximo O(V) vezes, resultando em O(VE) aumentos. Cada busca custa O(E), de modo que o tempo total é **O(VE²)** no pior caso [1]. Isso não significa que o próprio valor numérico do fluxo é O(VE).

A memória é O(V+E) para adjacências e registros residuais, desconsiderando sobrecarga de objetos Python. Uma BFS constrói uma árvore de predecessores por aumento. Quando nenhuma BFS encontra destino, a origem não alcança t por arestas residuais positivas.

## Cortes mínimos como certificado ótimo

Um corte particiona vértices em S e T, com s∈S e t∈T. Sua capacidade soma capacidades **originais diretas** das arestas S→T; não se subtrai diretamente capacidade das arestas inversas. Qualquer fluxo viável é limitado por cada corte: a conservação torna o fluxo líquido através da fronteira igual ao valor transportado, enquanto fluxo contrário não aumenta esse limite. Sem caminho aumentante, escolha S como o conjunto alcançável da origem na rede residual. Todas as arestas originais S→T estão saturadas e não existe fluxo líquido de retorno que destrua a igualdade. Logo, valor do fluxo = capacidade do corte. Esse é o **teorema fluxo máximo–corte mínimo** [1].

No exemplo, a origem possui arestas saindo com capacidades 3 e 2. O corte {0} vale 5. O algoritmo constrói fluxo viável de valor 5: ele atinge o limite superior e portanto é ótimo, qualquer que seja a ordem de visitas da BFS entre caminhos empatados.

## Emparelhamento bipartido por redução

Um grafo bipartido possui lados L e R, com arestas apenas entre eles. Um emparelhamento escolhe arestas sem compartilhar extremidades. Construa rede: uma superorigem conecta-se a cada vértice de L com capacidade 1; cada opção L→R tem capacidade 1; e cada vértice de R liga-se a um superdestino com capacidade 1. Fluxo máximo integral corresponde a emparelhamento de maior cardinalidade: cada unidade representa par único e nenhuma extremidade pode repetir [2].

| Pergunta | Técnica | Hipótese |
| --- | --- | --- |
| Vazão total | Fluxo máximo | Arestas dirigidas com capacidade |
| Gargalo entre duas regiões | Corte mínimo | Mesmo modelo de capacidade |
| Alocação um a um | Emparelhamento bipartido | Lados separados e capacidade unitária |
| Alocação de custo mínimo | Fluxo de custo mínimo ou atribuição | Custos exigem outro objetivo |
| Rota mais curta | BFS/Dijkstra | Distância, não vazão |

Um emparelhamento **maximal** (sem aresta imediata adicional) não é necessariamente **máximo**. Caminhos alternantes podem mudar parceiros para liberar capacidade, analogamente a usar arestas residuais inversas [2].

## Contraexemplos e exercícios

Não trate aresta dirigida como conexão não dirigida única: capacidade u→v independe de v→u. Uma escolha gulosa que atribui ao trabalhador capaz de executar A e B a tarefa A pode produzir um único par, enquanto realocá-lo para B e dar A ao outro trabalhador permite dois. DSU comum não representa capacidades dirigidas. Autolaços não contribuem para fluxo origem-destino, por isso o exemplo os ignora.

1. Para a rede de exemplo, indique um corte de capacidade cinco e explique por que nenhum fluxo excede cinco.
2. Depois de transmitir duas unidades em aresta de capacidade cinco, mostre residual direto três e inverso dois.
3. Construa redução bipartida para dois trabalhadores e duas tarefas, em que um trabalhador executa ambas e outro apenas a primeira.
4. Por que um caminho aumentante eleva o valor total, em vez de apenas redistribuí-lo?
5. Compare resposta num grafo pequeno com força bruta sobre atribuições inteiras de fluxo, verificando conservação e capacidade com oráculo independente.

**Leituras relacionadas:** [Percurso de grafos](/pt/topics/graph-traversal/) explica BFS; [Union-Find](/pt/topics/disjoint-set-union/) resolve conectividade não dirigida; [caminhos mínimos](/pt/topics/shortest-paths/) otimiza custo de rota e não vazão total.
