---
id: stacks-queues
title: "Pilhas e filas: LIFO, FIFO, deques e invariantes"
description: "Diferencie contratos de pilhas e filas, demonstre seus invariantes e implemente verificação de delimitadores e filas para BFS."
category: algorithms
difficulty: beginner
updated: 2026-10-09
prerequisites: [arrays-and-strings, linked-lists]
sources:
  - {title: "Princeton Algorithms — Bags, Queues, and Stacks", url: "https://algs4.cs.princeton.edu/13stacks/", kind: "university textbook"}
  - {title: "Python Documentation — collections.deque", url: "https://docs.python.org/3/library/collections.html#collections.deque", kind: "official language documentation"}
  - {title: "Python Documentation — Data Structures", url: "https://docs.python.org/3/tutorial/datastructures.html", kind: "official language documentation"}
---
Uma **pilha** e uma **fila** podem guardar os mesmos valores, mas seus contratos de retirada diferem. A pilha devolve primeiro o **último** item inserido (LIFO). A fila devolve primeiro o **primeiro** inserido (FIFO). São tipos abstratos de dados: o contrato determina o comportamento, enquanto arrays, listas ligadas ou buffers circulares são possíveis implementações. Confundir interface e representação provoca erros de custo e lógica [1].

## Contrato da pilha

Uma pilha oferece push(x), pop(), peek() e empty(). Após push(A), push(B), push(C), o pop deve retornar C, e B será o topo seguinte. O invariante é que pop devolve a inserção mais recente ainda não retirada. Usando array dinâmico da lista Python, append e pop na **ponta final** custam tempo constante amortizado, segundo o modelo habitual de redimensionamento [3].

Uma pilha com lista ligada insere e remove na cabeça em O(1), mas alocação e localidade dos nós mudam desempenho prático. Em ambos os casos, consultar topo existente custa O(1). Especifique o tratamento de pilha vazia: sentinela pode confundir dado legítimo; exceção ou resultado opcional costuma ser mais explícito.

![A pilha retira por uma ponta e a fila por outra.](/diagrams/stack-queue-operations.svg)

## Contrato da fila

Uma fila FIFO oferece enqueue(x), dequeue(), front() e empty(). Após enqueue(A), enqueue(B), enqueue(C), dequeue retorna A; B será o primeiro seguinte. Lista simplesmente ligada com cabeça e cauda mantidas permite inserir no fim e remover do início em O(1). Sem ponteiro de cauda, inserir pode percorrer n nós, custando O(n). Um **buffer circular** sobre array usa índice da cabeça e contagem, retornando ao início com aritmética modular.

Usar list.pop(0) em Python não é implementação geral apropriada: remover índice zero desloca todas as referências seguintes, O(n) no pior caso. O collections.deque fornece inserção e remoção eficientes em ambas as pontas, com desempenho aproximado O(1), sendo escolha usual para FIFO em algoritmos Python [2].

## Delimitadores balanceados: invariante da pilha

Para verificar chaves, colchetes e parênteses aninhados, percorra caracteres. Ao encontrar abertura, empilhe o tipo. Ao encontrar fechamento, o **topo deve corresponder ao abridor correto**; se não houver abridor ou tipo divergir, rejeite. No fim, aceite somente pilha vazia. O invariante é que após os primeiros i caracteres a pilha contém as aberturas ainda não casadas, na ordem de aninhamento.

~~~python
def balanceado(texto):
    aberturas = set("([{")
    pares = {")":"(", "]":"[", "}":"{"}
    pilha = []
    for caractere in texto:
        if caractere in aberturas:
            pilha.append(caractere)
        elif caractere in pares:
            if not pilha or pilha.pop() != pares[caractere]:
                return False
    return not pilha

assert balanceado("{a:[b,(c)]}")
assert balanceado("")
assert not balanceado("([)]")
assert not balanceado("(()")
assert not balanceado(")")
~~~

Para n caracteres, tempo O(n). A memória O(d) corresponde ao máximo de aberturas simultâneas, limitado por n. O código ignora caracteres que não são delimitadores; um parser real precisa tratar strings, comentários e escapes, pois pontuação neles pode não ter efeito sintático.

## Fila como base da busca em largura

A BFS usa FIFO para descobrir vértices em distâncias não decrescentes medidas em **arestas não ponderadas**. Primeiro insira a origem e marque-a descoberta. Remova o primeiro, visite os vizinhos ainda não descobertos e insira-os no fim. Como cada vizinho inserido a partir de vértice de distância k possui distância k+1, e a fila contém níveis k ou k+1 em ordem, a primeira descoberta é um caminho de quantidade mínima de arestas.

~~~python
from collections import deque

def distancias(grafo, origem):
    dist = {origem: 0}
    fila = deque([origem])
    while fila:
        vertice = fila.popleft()
        for vizinho in grafo.get(vertice, ()):
            if vizinho not in dist:
                dist[vizinho] = dist[vertice] + 1
                fila.append(vizinho)
    return dist

grafo = {"s":["a","b"], "a":["t"], "b":["t"], "t":[]}
assert distancias(grafo,"s") == {"s":0,"a":1,"b":1,"t":2}
assert distancias({},"ausente") == {"ausente":0}
~~~

Usar pilha no lugar de FIFO produziria percurso em profundidade, cujo primeiro caminho encontrado pode não ser o menor. BFS em listas de adjacência custa O(V+E) sobre vértices e arestas alcançáveis; a fila armazena até O(V) itens. Com pesos, é necessário algoritmo apropriado como Dijkstra, não BFS FIFO.

## Deques e versões monotônicas

Um **deque** permite adicionar e remover nas duas pontas. Ele implementa pilha ou fila dependendo das operações escolhidas. Um **deque monotônico** mantém valores ou índices em ordem não crescente/não decrescente, removendo entradas dominadas da cauda. Isso suporta máximo de janela deslizante em O(n) operações acumuladas: cada índice entra e sai no máximo uma vez.

Uma **fila de prioridades** é diferente: retira por prioridade, não pela ordem de chegada ou inserção. Heaps binários são implementações comuns e fornecem inserção/remoção O(log n) sob hipóteses de comparação. Não confunda heap com fila FIFO apenas porque ambos devolvem 'próximo' elemento.

## Custos e representação

| Implementação | Inserção | Remoção | Acesso por índice |
| --- | --- | --- | --- |
| List Python como pilha | O(1) amortizado no fim | O(1) no fim | O(1) |
| List Python como fila | O(1) amortizado no fim | O(n) na frente | O(1) |
| Deque FIFO | Aproximadamente O(1) nas pontas | Aproximadamente O(1) | O(n) no meio |
| Lista ligada com cabeça/cauda | O(1) nas pontas | O(1) na cabeça | O(n) |

Custos são assintóticos e dependem da representação. Consultar o meio de um deque pode custar linearmente; ele não substitui array para acesso arbitrário. Um buffer circular de **capacidade fixa** deve definir o que ocorre cheio: rejeitar, bloquear, sobrescrever ou crescer. Sobrescrever sem aviso pode perder trabalho.

## Limitações da abstração

Um deque local em Python **não** equivale a broker distribuído durável. Uma fila com produtores e consumidores concorrentes exige sincronização de threads ou estrutura própria. Uma pilha que processa entrada não confiável deve impor limites de tamanho e profundidade de aninhamento. Vazão ilimitada de produtores sobre fila ilimitada acumula backlog; capacidade e controle de admissão fazem parte do contrato robusto.

## Exercícios e verificação

1. Simule push(1), push(2), pop(), push(3), pop(): respostas 2 e 3. Explique LIFO.
2. Simule enqueue(1), enqueue(2), dequeue(), enqueue(3), dequeue(): respostas 1 e 2. Explique FIFO.
3. Prove o invariante dos delimitadores balanceados por indução sobre o prefixo percorrido.
4. Substitua deque por list.pop(0) na BFS e explique por que o pior custo pode crescer num grafo amplo.
5. Explique por que fila de prioridades e FIFO não são equivalentes, embora ambas recebam o nome 'fila'.

**Leituras relacionadas:** [Arrays](/pt/topics/arrays-and-strings/) explicam crescimento amortizado; [listas ligadas](/pt/topics/linked-lists/) oferecem representação por nós; [percursos de grafos](/pt/topics/graph-traversal/) detalham BFS/DFS.
