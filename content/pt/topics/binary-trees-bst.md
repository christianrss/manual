---
id: binary-trees-bst
title: "Árvores binárias e BSTs: percursos, ordenação e altura"
description: "Explique estrutura de árvores binárias, DFS/BFS, ordenação BST e complexidade dependente da altura com implementação iterativa."
category: algorithms
difficulty: intermediate
updated: 2026-10-09
prerequisites: [arrays-and-strings, stacks-queues, complexity-analysis]
sources:
  - {title: "Princeton Algorithms — Binary Search Trees", url: "https://algs4.cs.princeton.edu/32bst/", kind: "university textbook"}
  - {title: "Princeton Algorithms — Balanced Search Trees", url: "https://algs4.cs.princeton.edu/33balanced/", kind: "university textbook"}
---
Uma **árvore** é um grafo conexo sem ciclos quando observado de modo não dirigido. Uma **árvore enraizada** acrescenta raiz escolhida e orientação pai-filho. A **árvore binária** limita cada nó a dois filhos, chamados esquerda e direita, sem exigir valores ordenados. A **árvore binária de busca (BST)** acrescenta invariante: toda chave da subárvore esquerda é menor que a do nó, e toda chave da direita é maior, sob comparação definida [1].

## Forma, profundidade e altura

Uma folha não possui filhos. Profundidade de um nó é a distância em arestas desde a raiz; raiz tem profundidade zero. Altura de árvore não vazia é a maior quantidade de arestas entre raiz e folha. Alguns livros adotam altura −1 para árvore vazia, outros zero; declare a convenção antes de usar recorrências. Uma árvore binária bem balanceada com n nós tem altura Θ(log n). Uma cadeia de n nós também é árvore binária, mas possui altura n−1. Ser **binária** não significa ser **balanceada**.

No nível d há no máximo 2^d nós. Somando níveis 0 até h, existem no máximo 2^(h+1)−1 nós. Portanto uma árvore com n nós possui altura pelo menos logarítmica quando os níveis estão quase completos, mas a desigualdade não impede altura maior em BST desbalanceada.

## Percursos DFS e seus invariantes

Um percurso precisa definir **ordem de visita**. Pré-ordem visita nó, esquerda, direita. Em-ordem visita esquerda, nó, direita. Pós-ordem visita esquerda, direita, nó. Numa BST válida de chaves distintas, em-ordem produz ordem estritamente crescente. Busca em largura visita os níveis em ordem FIFO. Cada percurso custa O(n), pois visita cada nó uma vez. DFS usa O(h) espaço em pilha, e BFS usa O(w) fila, onde h é altura e w é largura máxima de um nível.

![BST e seu percurso em-ordem crescente.](/diagrams/bst-inorder.svg)

Por exemplo, raiz 8 com filho esquerdo 3 e direito 10 tem em-ordem 3,8,10; pré-ordem 8,3,10; pós-ordem 3,10,8. Ter resultado crescente é consequência do invariante BST, não propriedade de **qualquer** árvore binária.

## Inserção e percurso iterativo de BST

O exemplo ignora chaves duplicadas e supõe chaves comparáveis por < e >. É **BST simples desbalanceada**, não AVL nem rubro-negra. O percurso iterativo evita limite de recursão Python numa cadeia profunda.

~~~python
class No:
    def __init__(self, chave):
        self.chave = chave
        self.esquerda = None
        self.direita = None

def inserir(raiz, chave):
    if raiz is None:
        return No(chave)
    atual = raiz
    while True:
        if chave == atual.chave:
            return raiz
        if chave < atual.chave:
            if atual.esquerda is None:
                atual.esquerda = No(chave)
                return raiz
            atual = atual.esquerda
        else:
            if atual.direita is None:
                atual.direita = No(chave)
                return raiz
            atual = atual.direita

def em_ordem(raiz):
    saida, pilha = [], []
    atual = raiz
    while atual is not None or pilha:
        while atual is not None:
            pilha.append(atual)
            atual = atual.esquerda
        atual = pilha.pop()
        saida.append(atual.chave)
        atual = atual.direita
    return saida

raiz = None
for chave in [8,3,10,1,6,14,4,7,13]:
    raiz = inserir(raiz,chave)
assert em_ordem(raiz) == [1,3,4,6,7,8,10,13,14]
assert em_ordem(inserir(raiz,6)) == [1,3,4,6,7,8,10,13,14]
assert em_ordem(None) == []
~~~

Após cada inserção, toda chave na esquerda permanece menor que seus ancestrais pertinentes e na direita permanece maior. O laço percorre um caminho até encontrar filho ausente; ligar o novo nó nesse ponto preserva ordenação. A correção do percurso decorre de indução: esquerda ordenada, chave da raiz, direita ordenada formam sequência crescente.

## Busca depende da altura, não só de n

Buscar numa BST compara a chave desejada com a atual e avança à esquerda ou direita. Cada passo desce um nível, então o custo é O(h+1), onde h representa altura. Árvores balanceadas garantem h=O(log n), mas BST simples construída com chaves já ordenadas pode virar cadeia e exigir Θ(n) comparações [1][2].

Ao inserir sete chaves em ordem crescente, a raiz possui cadeia somente à direita com sete nós. O pior acesso faz sete comparações. Se construir árvore balanceada usando mediana como raiz, as mesmas sete chaves podem ter altura dois, com no máximo três comparações. Os valores são iguais; **ordem de inserção e política de balanceamento** explicam a diferença.

## Argumento de preservação do invariante

Na inserção, se a chave já existe, nada muda. Se chave é menor que o nó atual, qualquer posição válida deve estar na subárvore esquerda; colocá-la na direita violaria a ordenação desse nó. Simetricamente, valores maiores precisam descer à direita. No primeiro ponteiro ausente, insira. Cada ancestral no percurso já restringiu o intervalo permitido, logo a chave respeita as restrições acumuladas. Por indução, a árvore inteira permanece uma BST.

Um validador deve conferir **faixas herdadas de todos os ancestrais**, não apenas comparar cada nó com seus filhos diretos. Raiz 10 com filho direito 15 que possui filho esquerdo 8 é inválida mesmo que 8<15 localmente: nó 8 está na subárvore direita da raiz 10 e deveria ser maior que 10.

## Árvores binárias, heaps e tries

Um **heap** binário possui propriedade de prioridade pai-filho e formato de árvore completa, frequentemente em array. Ele não fornece percurso em-ordem ordenado nem busca rápida por chave arbitrária. Uma **trie** ramifica por símbolos de prefixo e nem sempre é binária. Uma BST decide ramificação comparando a chave inteira. BSTs balanceadas fornecem ordenação, predecessores e sucessores; tabelas hash oferecem busca exata eficiente esperada, mas não ordem implícita.

| Operação | BST simples | BST balanceada |
| --- | --- | --- |
| Buscar | O(h), pior Θ(n) | O(log n) |
| Inserir | O(h), pior Θ(n) | O(log n) |
| Percorrer ordenado | O(n) | O(n) |
| Dados por nó | Dois filhos | Frequentemente metadados de balanceamento |

## Limites e exercícios

Não espere O(log n) no pior caso de BST comum sem balanceamento. Percurso recursivo em cadeia profunda pode ultrapassar a pilha da linguagem; o iterativo evita isso. Exclusão é mais difícil: nó com dois filhos costuma ser substituído por predecessor ou sucessor, mantendo ordem e descendentes. Modificação concorrente requer sincronização; classe No comum não é índice concorrente.

1. Insira [5,2,8,1,3] e escreva percursos em-ordem, pré-ordem e pós-ordem.
2. Monte contraexemplo em que filhos locais parecem corretos, mas intervalo definido por ancestral é violado.
3. Compare números de comparações entre inserção crescente e inserção pela mediana de sete chaves.
4. Demonstre por indução que em-ordem de BST válida com chaves distintas é crescente.
5. Explique por que a raiz de min-heap é mínimo, mas sua subárvore esquerda não precisa conter todos os valores menores que a direita.

**Leituras relacionadas:** [Pilhas e filas](/pt/topics/stacks-queues/) fornecem estruturas de percurso; [heaps](/pt/topics/heaps-priority-queues/) usam invariantes distintos; [grafos](/pt/topics/graph-traversal/) estendem o percurso a estruturas com ciclos.
