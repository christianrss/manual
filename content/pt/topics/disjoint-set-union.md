---
id: disjoint-set-union
title: "Union-Find: conectividade, compressão e Kruskal"
description: "Dedução dos invariantes de union-find, compressão de caminhos, união por tamanho, custo amortizado e aplicação em árvores geradoras."
category: algorithms
difficulty: intermediate
updated: 2026-10-09
prerequisites: [complexity-analysis, graph-traversal]
sources:
  - {title: "Disjoint Set Union — CP-Algorithms", url: "https://cp-algorithms.com/data_structures/disjoint_set_union.html", kind: "technical reference"}
  - {title: "Minimum Spanning Tree — Kruskal — CP-Algorithms", url: "https://cp-algorithms.com/graph/mst_kruskal_with_dsu.html", kind: "technical reference"}
---
Uma estrutura de conjuntos disjuntos (DSU, ou union-find) mantém uma **partição** de um universo fixo em conjuntos sem interseção. Permite verificar se dois elementos pertencem ao mesmo componente e unir componentes. É adequada quando relacionamentos apenas **adicionam** conectividade, como arestas de um grafo não dirigido inseridas ao longo do tempo; não guarda toda a topologia do grafo [1].

## Modelo matemático e contrato

Considere elementos inteiros de 0 a n-1. Inicialmente cada elemento constitui um conjunto. A relação 'pertencer ao mesmo componente' é reflexiva, simétrica e transitiva. A operação find(x) devolve um **representante** do conjunto de x; union(a,b) mescla componentes e informa se houve união efetiva. O representante é detalhe interno: o consumidor não deve pressupor qual vértice continuará como líder. Índices negativos ou superiores ao universo são entradas inválidas.

![Uma coleção de componentes disjuntos é representada por ponteiros para pais.](/diagrams/dsu-forest.svg)

## Invariante da floresta e união por tamanho

Represente cada conjunto como árvore enraizada. parent[x] aponta em direção à raiz, e uma raiz satisfaz parent[root]=root. O invariante exige que seguir os pais termine em exatamente uma raiz, sem ciclos dirigidos de comprimento maior que um. Portanto, union deve ligar **raízes**, e não nós arbitrários. Do contrário, a estrutura pode perder conectividade ou produzir uma representação inválida.

Sem política para escolher o pai, uniões sucessivas produzem cadeias de até n-1 ligações, tornando find linear. Em **union by size**, a raiz da árvore menor é anexada à maior. Sempre que a profundidade de um elemento cresce, o tamanho do componente ao qual ele pertence ao menos dobra. Assim, a profundidade aumenta no máximo floor(log₂ n) vezes antes de alcançar n elementos. O argumento demonstra altura logarítmica mesmo sem compressão [1].

## Compressão de caminhos e implementação

A busca de representante percorre pais até a raiz. A **compressão de caminhos** aproxima da raiz os nós visitados, preservando a partição, pois só muda conexões internas ao mesmo componente. Com união por tamanho, o custo **amortizado** por operação é O(α(n)), sendo α a inversa da função de Ackermann. É um limite sobre sequências, não uma garantia de tempo constante em cada chamada; o argumento simples de duplicação não prova sozinho esse limite mais forte [1].

~~~python
class Conjuntos:
    def __init__(self, n):
        if n < 0: raise ValueError("n deve ser nao negativo")
        self.pai = list(range(n))
        self.tamanho = [1] * n
        self.componentes = n

    def buscar(self, x):
        if not 0 <= x < len(self.pai): raise IndexError(x)
        while self.pai[x] != x:
            self.pai[x] = self.pai[self.pai[x]]
            x = self.pai[x]
        return x

    def unir(self, a, b):
        a, b = self.buscar(a), self.buscar(b)
        if a == b: return False
        if self.tamanho[a] < self.tamanho[b]: a, b = b, a
        self.pai[b] = a
        self.tamanho[a] += self.tamanho[b]
        self.componentes -= 1
        return True

d = Conjuntos(5)
assert d.componentes == 5
assert d.unir(0, 1) and d.unir(1, 2)
assert d.buscar(0) == d.buscar(2)
assert not d.unir(0, 2)
assert d.componentes == 3
~~~

A implementação usa **compressão por metades de caminho** de forma iterativa, evitando profundidade recursiva. Memória e construção custam O(n). Os tamanhos são autoritativos somente nas raízes. Após anexar uma raiz a outra, o tamanho armazenado no antigo líder pode ficar desatualizado, mas não deve ser consultado diretamente.

## Exemplo: ciclo em grafo não dirigido

Processe arestas (0,1), (1,2), (3,4), (2,0). As duas primeiras formam {0,1,2}; a terceira cria {3,4}. Na aresta (2,0), buscar devolve o mesmo representante: inseri-la cria ciclo porque já existe caminho entre seus extremos. A justificativa vale para **grafo não dirigido**; esse teste não detecta corretamente ciclos dirigidos.

Se m arestas são inseridas, o custo total após inicialização é O(m α(n)) amortizado. DSU não informa o caminho concreto que conecta dois vértices. Também não remove arbitrariamente arestas existentes sem técnicas offline específicas ou outra estrutura de conectividade dinâmica.

## Kruskal e floresta geradora mínima

Kruskal ordena arestas não dirigidas pelo peso crescente e seleciona uma aresta apenas se seus extremos pertencerem a componentes diferentes. A **propriedade do corte** justifica a segurança de escolher uma aresta de peso mínimo atravessando um corte apropriado. Ordenar custa O(E log E); as operações DSU custam O(E α(V)). Em grafo desconexo, o resultado é uma **floresta geradora mínima**, não árvore única [2].

| Pergunta | DSU resolve? | Motivo |
| --- | --- | --- |
| u e v estão conectados após inclusões? | Sim | Compara representantes |
| Nova aresta não dirigida gera ciclo? | Sim | Extremos já conectados |
| Qual menor caminho ponderado? | Não | Pesos e predecessores não estão na DSU |
| O que ocorre ao remover aresta? | Não diretamente | DSU usual apenas une |

## Contraexemplos, correção e alternativas

Após unir(0,1), unir(1,2) e excluir a aresta (1,2), a estrutura usual continua respondendo que 0 e 2 estão conectados, mesmo sem caminho alternativo: **remoção** viola o modelo. Também é errado executar pai[a]=b em extremos arbitrários sem localizar raízes. Em várias threads, alterar pai e tamanho sem sincronização causa corridas; segurança concorrente exige projeto e primitivas adequadas.

## Exercícios e verificação

1. Faça quatro uniões em seis elementos e acompanhe o número de componentes. Ele só diminui se os representantes forem distintos.
2. Demonstre o limite logarítmico usando o número de vezes que o tamanho do componente de um elemento pode dobrar.
3. Implemente tamanho do componente por tamanho[buscar(x)]; teste elementos cujo campo local de tamanho ficou desatualizado.
4. Com arestas de pesos (0,1,2), (1,2,5), (0,2,1), Kruskal escolhe pesos 1 e 2, total 3; explique por que 5 criaria ciclo.
5. Compare o resultado da DSU com alcançabilidade por DFS num grafo pequeno **não dirigido e somente com inclusões**, usando a segunda técnica como oráculo independente.
