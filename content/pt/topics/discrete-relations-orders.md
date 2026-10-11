---
id: discrete-relations-orders
title: "Relações Binárias, Classes de Equivalência e Ordens Parciais"
description: "Deduza partições, ordens parciais, fecho de alcançabilidade e dependências topológicas com contraexemplos executáveis."
category: foundations
difficulty: foundational
updated: 2026-10-11
prerequisites: [logic-proofs-invariants, discrete-counting-probability]
sources:
  - {title: "MIT 6.042J — Lecture 11: Relations, Partial Orders, and Scheduling", url: "https://ocw.mit.edu/courses/6-042j-mathematics-for-computer-science-fall-2010/resources/lecture-11-relations-partial-orders-and-scheduling/", kind: "university lecture"}
  - {title: "MIT 6.042J — Chapter 7: Relations and Partial Orders", url: "https://ocw.mit.edu/courses/6-042j-mathematics-for-computer-science-fall-2010/resources/mit6_042jf10_chap07/", kind: "university open textbook"}
---
As relações são a ligação matemática entre conjuntos e algoritmos que agrupam, restringem ou ordenam objetos. Uma estrutura de conjuntos disjuntos mantém uma **relação de equivalência**; um grafo de dependências representa restrições de ordem; uma junção de banco de dados testa condições sobre tuplas. São contratos diferentes, embora todos possam envolver pares. Este capítulo estabelece as propriedades antes de discutir implementações. O curso MIT 6.042J apresenta relações, classes de equivalência e escalonamento em conjunto [1][2].

Os exemplos usam o universo finito de inteiros `U = {0, ..., n-1}`, com `n >= 0`, e relações explicitadas por pares ordenados. Resultados desse modelo não devem ser estendidos automaticamente a conjuntos infinitos ou a bancos de dados em produção.

## Relações binárias como conjuntos de pares ordenados

Uma relação binária `R` **sobre** `U` é um subconjunto de `U × U`. Escrever `a R b` significa que o par ordenado `(a,b)` pertence a `R`. A direção importa: `(a,b)` não obriga a presença de `(b,a)`. Uma relação de `A` para `B` pertence a `A × B`; é indispensável especificar domínio e contradomínio.

Para `U={0,1,2}`, a relação `R={(0,0),(1,1),(2,2),(0,1)}` possui três pares de identidade e uma aresta dirigida. A relação identidade contém apenas pares de um elemento consigo mesmo. A **relação universal** contém todos os nove pares. A relação vazia num universo não vazio é simétrica e transitiva, mas não reflexiva; no universo vazio, a afirmação universal sobre seus elementos é verdadeira por vacuidade.

Representar arestas dirigidas como relações impede suposições implícitas como "se A depende de B, então B depende de A". Uma aresta pode representar pré-requisito, permissão, conectividade ou comparação, mas as propriedades dependem da semântica escolhida.

## Quatro propriedades e contraexemplos mínimos

`R` é **reflexiva** quando todo `a` satisfaz `a R a`; **simétrica** se `a R b` implica `b R a`; **antissimétrica** se as duas direções implicam `a=b`; e **transitiva** se `a R b` e `b R c` implicam `a R c` [1][2].

Simetria e antissimetria **não são opostos lógicos**. A igualdade apresenta as duas propriedades. Dois elementos distintos relacionados nas duas direções violam a antissimetria, mesmo quando todos os pares reflexivos aparecem. A ausência de um par reverso viola a simetria, mas não necessariamente a antissimetria.

Em `U={0,1,2}`, defina `a R b` quando `|a-b| <= 1`. Essa relação é reflexiva e simétrica. Contudo, `0 R 1` e `1 R 2`, mas `0 R 2` é falso. Portanto não é **transitiva**. O exemplo refuta a ideia de que qualquer critério de "semelhança" forme grupos matematicamente coerentes.

## Equivalência e partições do universo

Uma **relação de equivalência** é reflexiva, simétrica e transitiva. A classe de `a` é `[a] = {b em U : a R b}`. Pela reflexividade, essa classe é não vazia. Pela simetria e pela transitividade, duas classes são disjuntas ou idênticas. Para demonstrar, suponha que `x` esteja em `[a]` e em `[b]`. Como `a R x`, temos `x R a`; combinado com `b R x`, resulta `b R a`. A transitividade permite transportar qualquer elemento de uma classe à outra, e o argumento vale nos dois sentidos.

Assim, as classes distintas formam uma **partição**: blocos não vazios, sem elementos em comum e cuja união é todo o universo. Reciprocamente, uma partição define uma equivalência ao considerar relacionados os elementos pertencentes ao mesmo bloco. Há uma correspondência bijetiva entre partições e equivalências de um universo finito fixado [2].

Nos inteiros `0..5`, a congruência módulo 2 produz `{0,2,4}` e `{1,3,5}`. A estrutura [disjoint-set union](/pt/topics/disjoint-set-union/) combina classes eficientemente quando equivalências são adicionadas. Ela não suporta automaticamente a exclusão de uma relação preservando conectividade dinâmica.

## Ordem parcial, incomparabilidade e ordem total

Uma **ordem parcial** é reflexiva, antissimétrica e transitiva. Não há obrigação de comparar todos os pares distintos. A ordem `<=` dos inteiros é total. A relação "divide" nos inteiros **positivos** é parcial, mas não total: tanto 2 quanto 3 dividem 6, porém nenhum divide o outro.

A restrição a positivos é essencial. Entre inteiros com sinal diferentes de zero, 2 divide -2 e -2 divide 2 sem serem o mesmo inteiro. A divisibilidade nesse domínio é uma **pré-ordem** (reflexiva e transitiva), mas não uma ordem antissimétrica. O domínio faz parte do contrato matemático.

Uma **ordem total** acrescenta comparabilidade: para quaisquer `a,b`, vale `a R b` ou `b R a`. Pode-se estender uma ordem parcial escolhendo posições coerentes para elementos incomparáveis. Essa extensão não precisa ser única; cronogramas diferentes podem respeitar exatamente as mesmas dependências [1].

## Dependências, diagramas de Hasse e ordenação topológica

A aresta `a -> b` num grafo de dependências pode indicar que "a precisa ocorrer antes de b". O grafo bruto normalmente omite laços e relações dedutíveis por caminhos maiores. Assim, seu conjunto de arestas não representa diretamente toda a ordem reflexiva e transitiva. O **fecho reflexivo e transitivo** acrescenta `(a,a)` e todos os pares unidos por caminho dirigido de zero ou mais arestas.

Se houver um ciclo dirigido envolvendo vértices distintos, o fecho incluirá `a R b` e `b R a` para `a≠b`; logo a antissimetria falha. Já um grafo dirigido acíclico (DAG) induz uma ordem parcial por alcançabilidade. Uma **ordenação topológica** é uma extensão linear das restrições. Um grafo com ciclo dirigido não admite ordenação topológica.

Um diagrama de Hasse representa compactamente uma ordem parcial finita, omitindo os pares reflexivos e os pares implícitos pela transitividade. Não se confunde com um grafo dirigido qualquer. Na sequência `A -> B -> C`, a relação `A R C` pertence ao fecho mesmo que não apareça a aresta direta `A -> C` [1][2]. Essa distinção fundamenta sistemas de build, planos de estudo e gerenciadores de dependências.

## Modelo finito executável e invariante

A implementação rejeita IDs inválidos, valores booleanos que o Python considera subclasses de inteiros e pares malformados. Verifica propriedades, constrói classes **somente após** confirmar equivalência e calcula o fecho liberando um vértice intermediário por vez.

O invariante do algoritmo de fecho é: após processar o vértice `k`, `reach[i][j]` é verdadeiro exatamente quando existe um caminho de `i` a `j` cujos vértices internos estão entre `0..k`. Um caminho ou evita `k`, ou pode ser dividido em um trecho que chega a `k` e outro que sai de `k`. Isso justifica a atualização. Ao terminar, todos os intermediários possíveis foram considerados.

~~~python
def normalized_relation(n, pairs):
    if type(n) is not int or n < 0:
        raise ValueError("n must be a nonnegative integer")
    relation = set()
    for pair in pairs:
        if (type(pair) is not tuple or len(pair) != 2
                or any(type(x) is not int or not 0 <= x < n for x in pair)):
            raise ValueError("pairs must contain valid (int, int) vertices")
        relation.add(pair)
    return relation

def relation_properties(n, pairs):
    r = normalized_relation(n, pairs)
    reflexive = all((i, i) in r for i in range(n))
    symmetric = all((b, a) in r for a, b in r)
    antisymmetric = all(a == b or (b, a) not in r for a, b in r)
    transitive = all(
        (a, c) in r
        for a in range(n) for b in range(n) for c in range(n)
        if (a, b) in r and (b, c) in r
    )
    return {
        "reflexive": reflexive,
        "symmetric": symmetric,
        "antisymmetric": antisymmetric,
        "transitive": transitive,
        "equivalence": reflexive and symmetric and transitive,
        "partial_order": reflexive and antisymmetric and transitive,
    }

def equivalence_classes(n, pairs):
    r = normalized_relation(n, pairs)
    if not relation_properties(n, r)["equivalence"]:
        raise ValueError("relation is not an equivalence")
    unseen = set(range(n))
    classes = []
    while unseen:
        representative = min(unseen)
        group = {j for j in unseen if (representative, j) in r}
        classes.append(tuple(sorted(group)))
        unseen.difference_update(group)
    return tuple(classes)

def reflexive_transitive_closure(n, edges):
    r = normalized_relation(n, edges)
    reach = [[i == j for j in range(n)] for i in range(n)]
    for a, b in r:
        reach[a][b] = True
    for k in range(n):
        for i in range(n):
            if reach[i][k]:
                for j in range(n):
                    if reach[k][j]:
                        reach[i][j] = True
    return {(i, j) for i in range(n) for j in range(n) if reach[i][j]}

parity = {(a, b) for a in range(6) for b in range(6) if a % 2 == b % 2}
assert relation_properties(6, parity)["equivalence"]
assert equivalence_classes(6, parity) == ((0, 2, 4), (1, 3, 5))
divides = {(a, b) for a in range(6) for b in range(6) if (b + 1) % (a + 1) == 0}
assert relation_properties(6, divides)["partial_order"]
assert not relation_properties(6, divides)["symmetric"]
near = {(a, b) for a in range(3) for b in range(3) if abs(a - b) <= 1}
assert relation_properties(3, near)["reflexive"]
assert relation_properties(3, near)["symmetric"]
assert not relation_properties(3, near)["transitive"]
assert reflexive_transitive_closure(3, {(0, 1), (1, 2)}) == {
    (0, 0), (1, 1), (2, 2), (0, 1), (1, 2), (0, 2)
}
assert relation_properties(0, set())["equivalence"]
~~~

Para a relação enumerada, `relation_properties` realiza `O(n³)` consultas de pertinência em tempo esperado e armazena até `O(n²)` pares. A extração de classes realiza até `O(n²)` consultas, além de ordenação. O fecho consome `O(n³)` tempo e `O(n²)` memória adicional. Os limites consideram IDs de inteiros com custo aritmético limitado e pertinência em conjuntos Python com custo esperado constante; não são garantias de custo em bits ou de hashing sob entradas adversariais.

## Limites, falhas e decisões de engenharia

O critério "distância até um" não é uma equivalência. Agrupar por componentes conectados implica acrescentar a **transitividade da conectividade**, o que altera o significado: elementos separados por distância dois podem acabar na mesma classe. Não é adequado fundir cadastros de pessoas a partir de uma semelhança imprecisa.

Um DAG de pré-requisitos permite ordenação topológica, mas não exige uma classificação absoluta única para todas as tarefas. Itens incomparáveis podem ser executados simultaneamente. Da mesma forma, a divisibilidade positiva não estabelece necessidade de executar 2 antes de 3. Impor ordem artificial pode reduzir desnecessariamente o paralelismo.

O modelo programado é finito e didático. Um escalonador normalmente usa ordenação topológica por grau de entrada em `O(V+E)`, em vez de calcular um fecho cúbico, se necessita apenas de uma sequência válida. Uma estrutura DSU atende bem à inserção monotônica de conexões, mas não a remoções arbitrárias. A escolha precisa acompanhar as operações reais do sistema.

## Exercícios e verificação

1. Em `U={0,1,2}`, classifique `{(0,0),(1,1),(2,2),(0,1),(1,0)}`. **Resposta verificável:** reflexiva, simétrica e transitiva, portanto equivalência com classes `{0,1}` e `{2}`; não é antissimétrica.
2. Acrescente `(1,2)` sem acrescentar `(0,2)`. **Resposta:** a transitividade falha em `0 R 1 R 2`; a simetria falha por ausência de `(2,1)`.
3. Determine o fecho de `{(0,1),(1,2)}` em três vértices. **Resposta:** seis pares, incluindo `(0,2)` e os três pares diagonais, conforme as asserções.
4. Na ordem de divisibilidade positiva de `{1,2,3,6}`, apresente duas extensões totais. **Resposta:** `1,2,3,6` e `1,3,2,6`; 2 e 3 permanecem incomparáveis.
5. **Desafio independente:** implemente uma ordenação topológica `O(V+E)`, sem chamar o fecho; detecte ciclos explicitamente. Valide todos os DAGs em quatro vértices, inclusive os desconectados.

Passar nesses testes finitos comprova apenas o comportamento nas entradas verificadas, não a correção universal nem o desempenho em sistemas maiores.
