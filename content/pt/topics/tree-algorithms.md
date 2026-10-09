---
id: tree-algorithms
title: "Algoritmos em árvores: níveis, LCA, diâmetro e validação BST"
description: "Deduza percursos por níveis, ancestral comum mais baixo, diâmetro e limites de BST com implementações iterativas."
category: algorithms
difficulty: intermediate
updated: 2026-10-09
prerequisites: [binary-trees-bst, stacks-queues, recursion-call-stack]
sources:
  - {title: "Princeton Algorithms — Binary Search Trees", url: "https://algs4.cs.princeton.edu/32bst/", kind: "university textbook"}
---
Árvores binárias aparecem em problemas de algoritmos porque a mesma estrutura permite várias perguntas: visitar por níveis, comparar subárvores, encontrar o ancestral comum mais baixo, calcular o caminho mais longo ou verificar ordenação. Cada tarefa exige **invariantes diferentes**. Uma árvore binária não é automaticamente uma BST, e uma BST não é necessariamente balanceada [1].

## Modelo preciso de nós e entradas

Adote árvore binária enraizada com n **objetos de nó distintos**, cada um contendo valor e até dois filhos. Não há ciclos, nem filho acessível por dois caminhos de pais diferentes. A árvore vazia tem zero nós. A identidade do nó é diferente do valor armazenado: dois objetos distintos podem guardar 7 e ainda serem vértices diferentes.

A maior quantidade de arestas da raiz até uma folha é a altura. Uma árvore balanceada apresenta altura O(log n); uma cadeia com n nós tem altura n−1. Isso afeta a profundidade de pilhas recursivas, mas o percurso completo visita cada nó mesmo em árvore balanceada, custando Θ(n) sob processamento local constante.

## Percurso por níveis usando fila FIFO

A busca em largura mantém uma fila de nós cujos pais já foram processados. Em cada rodada, registre o tamanho atual da fila: essas entradas representam exatamente um nível de profundidade. Remova todos esses nós e acrescente os filhos no final, garantindo que o nível seguinte só seja visitado após completar o atual.

![Níveis por largura, relações de ancestralidade e caminho máximo numa árvore de exemplo.](/diagrams/tree-levels-lca.svg)

~~~python
from collections import deque

class No:
    def __init__(self, valor, esquerda=None, direita=None):
        self.valor = valor
        self.esquerda = esquerda
        self.direita = direita

def niveis(raiz):
    if raiz is None:
        return []
    fila = deque([raiz])
    resposta = []
    while fila:
        nivel = []
        for _ in range(len(fila)):
            no = fila.popleft()
            nivel.append(no.valor)
            if no.esquerda is not None:
                fila.append(no.esquerda)
            if no.direita is not None:
                fila.append(no.direita)
        resposta.append(nivel)
    return resposta

n4, n5, n3 = No(4), No(5), No(3)
n2 = No(2, n4, n5)
raiz = No(1, n2, n3)
assert niveis(raiz) == [[1], [2, 3], [4, 5]]
assert niveis(None) == []
~~~

Cada nó entra e sai da fila uma vez: Θ(n) tempo. A fila mantém até O(w) nós por vez, onde w considera a largura dos níveis em processamento e construção; seu limite assintótico geral é O(n). A saída armazena os n valores. Diferentemente de DFS, a memória de BFS depende da largura em vez da altura.

## Ancestral comum mais baixo e identidade

O **lowest common ancestor (LCA)** dos nós a e b é o ancestral compartilhado mais profundo, admitindo que um nó seja seu próprio ancestral. Para os nós 4 e 5, a resposta é o objeto 2. Para 4 e 3, a resposta é a raiz 1. Comparar somente valores dá resultado errado quando existem duplicatas; LCA normalmente consulta identidades, salvo contrato de chaves únicas.

Para árvore geral sem ponteiros aos pais, construa mapa de pais percorrendo nós até encontrar ambos os alvos. Insira todos os ancestrais de a num conjunto e suba a partir de b até o primeiro ancestral presente no conjunto. Isso custa O(n) tempo e O(n) memória no pior caso. Numa BST com valores presentes, a ordenação pode permitir descida O(h), mas esse atalho não serve para árvores binárias comuns.

~~~python
def ancestral_comum(raiz, a, b):
    if raiz is None or a is None or b is None:
        return None
    pais = {raiz: None}
    pilha = [raiz]
    while pilha and (a not in pais or b not in pais):
        no = pilha.pop()
        for filho in (no.esquerda, no.direita):
            if filho is not None and filho not in pais:
                pais[filho] = no
                pilha.append(filho)
    if a not in pais or b not in pais:
        return None
    ancestrais = set()
    while a is not None:
        ancestrais.add(a)
        a = pais[a]
    while b not in ancestrais:
        b = pais[b]
    return b

assert ancestral_comum(raiz, n4, n5) is n2
assert ancestral_comum(raiz, n4, n3) is raiz
assert ancestral_comum(raiz, n2, n2) is n2
assert ancestral_comum(raiz, n4, No(4)) is None
~~~

A última verificação trata ausência de nó: outro objeto com valor 4 **não** é o mesmo alvo. A implementação supõe objetos Python com hash por identidade, sem alteração concorrente da árvore e sem ciclos. Para nós não hashable, use identificadores estáveis explícitos.

## Diâmetro por programação dinâmica em pós-ordem

O **diâmetro** é a maior quantidade de arestas num caminho simples entre quaisquer dois nós; ele **não precisa atravessar a raiz**. Em cada nó, o maior caminho que passa por ele combina alturas de suas subárvores. Definindo altura de filho vazio como −1, o caminho tem esquerda_altura + direita_altura + 2 arestas.

Percurso em pós-ordem calcula alturas de filhos antes dos pais, guardando um resultado por nó. O máximo entre todos os caminhos que passam por cada nó é o diâmetro. Isso é programação dinâmica em árvore: a altura de cada subárvore é calculada uma vez e utilizada quando necessária.

~~~python
def diametro_arestas(raiz):
    if raiz is None:
        return 0
    pilha = [(raiz, False)]
    alturas = {}
    resposta = 0
    while pilha:
        no, processado = pilha.pop()
        if not processado:
            pilha.append((no, True))
            if no.direita is not None:
                pilha.append((no.direita, False))
            if no.esquerda is not None:
                pilha.append((no.esquerda, False))
        else:
            esquerda = alturas.get(no.esquerda, -1)
            direita = alturas.get(no.direita, -1)
            resposta = max(resposta, esquerda + direita + 2)
            alturas[no] = max(esquerda, direita) + 1
    return resposta

assert diametro_arestas(raiz) == 3
assert diametro_arestas(No(9)) == 0
assert diametro_arestas(None) == 0
~~~

No exemplo, o maior caminho é 4→2→1→3, com três arestas. Um erro comum é calcular apenas altura_esquerda(raiz)+altura_direita(raiz)+2: o caminho mais longo pode estar inteiro numa subárvore muito profunda e nunca atravessar a raiz. Examinar o candidato em **cada nó** evita o erro.

A implementação iterativa evita limite de recursão Python. Usa Θ(n) tempo e O(n) memória para alturas e pilha. Uma versão recursiva pode usar O(h) quadros e acompanhar diâmetro global, mas corre risco de esgotar a pilha numa cadeia profunda.

## Validar BST com limites herdados

Uma **árvore binária de busca** exige regra mais forte: todos os valores na esquerda de um nó são estritamente menores e todos na direita estritamente maiores, supondo duplicatas proibidas. Comparar apenas filhos imediatos não basta. Raiz 10, filho direito 15 e filho esquerdo de 15 contendo 8 parecem ordenados localmente em 15, mas o valor 8 viola o limite inferior herdado da raiz 10.

Mantenha intervalo aberto permitido (inferior,superior) para cada nó. Descendo à esquerda, o limite superior vira valor do pai; à direita, o limite inferior vira valor do pai. Valor fora do intervalo herdado, inclusive na borda, invalida a árvore. Isso confere restrições de todos os ancestrais em Θ(n), usando O(h) espaço típico de DFS, com h chegando a Θ(n) em árvore desbalanceada.

~~~python
def bst_valida(raiz):
    pendentes = [(raiz, None, None)]
    while pendentes:
        no, inferior, superior = pendentes.pop()
        if no is None:
            continue
        if (inferior is not None and no.valor <= inferior) or (
            superior is not None and no.valor >= superior
        ):
            return False
        pendentes.append((no.esquerda, inferior, no.valor))
        pendentes.append((no.direita, no.valor, superior))
    return True

assert bst_valida(No(10, No(5), No(15, No(12), No(20))))
assert not bst_valida(No(10, No(5), No(15, No(8))))
assert not bst_valida(No(2, No(2), No(3)))
assert bst_valida(None)
~~~

O código assume valores numéricos comparáveis e usa None para limite inexistente; adapte se None for chave permitida. Árvores imensas ou persistentes acrescentam problemas de armazenamento externo, compartilhamento estrutural e mutação concorrente não modelados aqui.

## Técnica conforme a pergunta

| Problema | Invariante | Custo típico |
| --- | --- | --- |
| Percorrer por nível | Fronteira FIFO | Θ(n) tempo, até O(n) espaço |
| LCA em árvore comum | Mapa de pais ou recursão | O(n) tempo |
| Diâmetro | Alturas e pós-ordem | Θ(n) tempo |
| Validar BST | Limites herdados | Θ(n) tempo |
| Buscar BST balanceada | Descida ordenada | O(log n) tempo |
| Buscar BST desbalanceada | Descida ordenada | O(h), pior Θ(n) |

Não aplique regras de BST a árvore binária qualquer. Não confunda valores iguais com nós idênticos sem contrato de unicidade. Não confunda *altura* (raiz até folha) com *diâmetro* (quaisquer dois vértices). São fontes recorrentes de erros aparentemente plausíveis.

## Exercícios e verificação

1. Trace a fila FIFO para cada nível da árvore de cinco nós e reproduza a saída.
2. Prove por que o algoritmo de mapa de pais retorna o ancestral **mais baixo**, não qualquer ancestral compartilhado.
3. Deduza a fórmula do diâmetro com altura −1 para filho vazio e valide o caminho de três arestas.
4. Construa árvore cujo diâmetro esteja integralmente na subárvore esquerda, sem atravessar a raiz.
5. Explique por que comparação só com filhos não encontra o erro do valor 8 sob a raiz 10 e trace seus limites herdados.

**Capítulos relacionados:** [Árvores binárias e BST](/pt/topics/binary-trees-bst/) definem estruturas; [filas](/pt/topics/stacks-queues/) suportam BFS; [recursão](/pt/topics/recursion-call-stack/) ajuda a decompor subárvores [1].
