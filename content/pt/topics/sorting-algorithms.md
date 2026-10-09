---
id: sorting-algorithms
title: "Algoritmos de ordenação: estabilidade, mergesort, quicksort e heapsort"
description: "Deduza insertion, merge, quick e heap sort, compare custos e estabilidade e verifique duas implementações completas."
category: algorithms
difficulty: intermediate
updated: 2026-10-09
prerequisites: [arrays-and-strings, complexity-analysis, recursion-call-stack]
sources:
  - {title: "Princeton Algorithms — Mergesort", url: "https://algs4.cs.princeton.edu/22mergesort/", kind: "university textbook"}
  - {title: "Princeton Algorithms — Quicksort", url: "https://algs4.cs.princeton.edu/23quicksort/", kind: "university textbook"}
  - {title: "Python Sorting HOWTO", url: "https://docs.python.org/3/howto/sorting.html", kind: "official language documentation"}
---
Ordenar significa rearranjar valores segundo uma relação definida por comparador ou chave. O problema parece simples, mas os algoritmos diferem em garantia de ordem, estabilidade, tempo, memória auxiliar e alteração dos dados originais. A escolha precisa seguir o **contrato**, não apenas a frase O(n log n) é bom. A ordenação padrão de Python é estável e otimizada; implementar métodos manualmente serve especialmente para raciocínio algorítmico e análise de restrições [3].

## Ordenação, estabilidade e contrato do comparador

Para valores a[0..n−1], uma ordenação não decrescente satisfaz a[i]≤a[i+1] para cada par de vizinhos válido. Uma ordenação **estável** preserva ainda a ordem relativa original dos registros que possuem a mesma chave. Se duas mensagens têm prioridade 4 e entraram A depois B? Para estabilidade, suponha A e depois B: o resultado mantém A antes de B. A estabilidade não diz nada sobre preservar posições de valores com chaves distintas.

Comparações precisam definir relação adequada, normalmente transitiva e consistente. Um comparador que alterna respostas ou depende de estado global mutável pode invalidar provas. NaN comporta-se de modo especial em comparações de ponto flutuante, então defina política se precisar de ordem total. Teste duplicatas, vazio, valores já ordenados e ordem inversa.

## Insertion sort: invariante e custo quadrático

Insertion sort percorre da esquerda para direita mantendo prefixo [0,i) ordenado. Para cada novo elemento, desloca os maiores do prefixo à direita e insere o valor na posição adequada. O invariante é: antes de processar i, os i elementos anteriores estão ordenados e são permutação dos i elementos originais. Inserir preserva ordem e multiconjunto de valores. Por indução, ao terminar, todo o array está ordenado.

O melhor caso usa Θ(n) comparações em entrada já ordenada com parada antecipada. O pior custa Θ(n²), por exemplo ordem inversa: deslocamentos somam 1+2+...+(n−1). A implementação in-place convencional usa O(1) de memória auxiliar e é estável quando elementos **iguais não atravessam uns aos outros**. É adequada para entradas pequenas ou quase ordenadas, não para grandes coleções arbitrárias.

## Mergesort: metades e intercalação estável

Mergesort divide um intervalo em metades, ordena cada metade recursivamente e as intercala. No merge, dois índices de leitura apontam para menores valores ainda disponíveis; escolha o menor e avance seu índice. O invariante é que a saída permanece ordenada e contém precisamente os menores elementos já consumidos das duas metades. No empate, escolher primeiro o item da **esquerda** preserva a ordem relativa entre registros com mesma chave [1].

![Mergesort divide um array e combina metades ordenadas.](/diagrams/mergesort-tree.svg)

O exemplo recebe registros e uma função que extrai a chave. Cria listas novas e preserva a entrada. A função de chave deve ser determinística e gerar valores comparáveis.

~~~python
def mergesort_estavel(itens, chave=lambda x: x):
    if len(itens) <= 1:
        return list(itens)
    meio = len(itens) // 2
    esquerda = mergesort_estavel(itens[:meio], chave)
    direita = mergesort_estavel(itens[meio:], chave)
    saida = []
    i = j = 0
    while i < len(esquerda) and j < len(direita):
        if chave(esquerda[i]) <= chave(direita[j]):
            saida.append(esquerda[i])
            i += 1
        else:
            saida.append(direita[j])
            j += 1
    saida.extend(esquerda[i:])
    saida.extend(direita[j:])
    return saida

registros = [(2, "A"), (1, "B"), (2, "C"), (1, "D")]
assert mergesort_estavel(registros, chave=lambda r: r[0]) == [
    (1, "B"), (1, "D"), (2, "A"), (2, "C")
]
assert registros[0] == (2, "A")
assert mergesort_estavel([]) == []
assert mergesort_estavel([9]) == [9]
assert mergesort_estavel([5, -1, 5, 0]) == [-1, 0, 5, 5]
~~~

Intercalar k elementos custa Θ(k): cada item entra uma vez na saída. A recorrência T(n)=2T(n/2)+Θ(n) produz Θ(n log n), assumindo comparações de custo constante. A profundidade recursiva é O(log n). Como cria slices e listas, essa **implementação Python** pode gerar alocações temporárias adicionais, mas o pico de armazenamento simultâneo dos elementos é O(n), além de O(log n) quadros de pilha. Não é in-place.

## Quicksort: partição e pior caso

Quicksort escolhe um **pivô**, particiona valores menores e maiores ou iguais segundo uma estratégia consistente e ordena as partições. Um esquema in-place comum, Lomuto, mantém intervalo [inicio,k) com elementos conhecidos ≤pivô, e as posições já examinadas restantes guardam os maiores. Ao colocar o pivô em sua posição final, os dois subintervalos são menores [2].

Partições equilibradas produzem T(n)=2T(n/2)+Θ(n), isto é Θ(n log n). Escolher o último elemento como pivô em entrada já ordenada pode gerar repetidamente lados com n−1 e zero elementos, então T(n)=T(n−1)+Θ(n)=Θ(n²). Pivot aleatório fornece expectativa Θ(n log n) de comparações segundo hipóteses de randomização, **não garantia determinística de pior caso**. Quicksort in-place comum não é estável e pode consumir Θ(n) quadros sob particionamento ruim.

Com muitas chaves duplicadas, vale empregar partição em três conjuntos: menores, iguais e maiores que o pivô. Assim evita redistribuir repetidamente grandes blocos de valores idênticos. Ideia semelhante aparece em quickselect, que busca estatística de ordem em vez de ordenar tudo.

## Heapsort: invariante do heap sem buffer de merge

Um **max-heap** mantém cada pai maior ou igual aos filhos. Em array, uma árvore binária completa usa filhos 2i+1 e 2i+2. Monte max-heap em O(n) usando sift-down de nós internos, dos níveis inferiores à raiz. Em seguida, troque o máximo de índice zero com o final do prefixo ativo e recupere a propriedade no prefixo encurtado. O invariante é: prefixo ativo é max-heap e sufixo guarda os maiores elementos nas posições finais ordenadas.

~~~python
def heapsort(itens):
    a = list(itens)
    n = len(a)
    def descer(raiz, fim):
        while True:
            filho = 2 * raiz + 1
            if filho >= fim:
                return
            if filho + 1 < fim and a[filho] < a[filho + 1]:
                filho += 1
            if a[raiz] >= a[filho]:
                return
            a[raiz], a[filho] = a[filho], a[raiz]
            raiz = filho
    for i in range(n // 2 - 1, -1, -1):
        descer(i, n)
    for fim in range(n - 1, 0, -1):
        a[0], a[fim] = a[fim], a[0]
        descer(0, fim)
    return a

casos = [[], [1], [3,1,2], [2,2,2], [9,-1,4,0,9], list(range(10)), list(range(9,-1,-1))]
for caso in casos:
    assert heapsort(caso) == sorted(caso)
~~~

Construir o heap custa Θ(n), pois a maioria dos nós está perto das folhas e exige poucas trocas. Cada uma das até n extrações máximas executa O(log n), totalizando O(n log n) no pior caso. A função copia a entrada e usa O(n) memória para devolver nova lista; as operações internas sobre lista existente exigem O(1) memória auxiliar. Heapsort normal não é estável [1].

## Comparativo de garantias

| Método | Tempo no pior caso | Memória auxiliar usual | Estável? |
| --- | --- | --- | --- |
| Insertion | Θ(n²) | O(1) | Sim, se não ultrapassar iguais |
| Merge | Θ(n log n) | O(n) de buffer | Sim, preferindo esquerda no empate |
| Quick | Θ(n²) | Pilha O(log n) esperada e Θ(n) no pior | Normalmente não |
| Heap | O(n log n) | O(1) quando in-place | Normalmente não |
| Python sort / sorted | O(n log n) em comparações no pior caso da família Timsort documentada | Depende da implementação | Sim [3] |

Não confunda **in-place** com **estável**, nem custo esperado com pior caso. O limite inferior Ω(n log n) vale para ordenações gerais baseadas em comparações: com n chaves distintas existem n! permutações, e uma árvore binária de decisões exige ao menos log₂(n!)=Ω(n log n) comparações no pior caminho. Counting/radix sort podem superar isso com estrutura especial das chaves e operações que não são comparações genéricas.

## Escolha para carga concreta

Para sequências pequenas quase ordenadas, insertion sort é simples e pode ser eficiente. Para garantir ordem relativa entre chaves iguais de negócio, escolha algoritmo estável ou associe índice original como critério de desempate. Num ambiente com memória limitada e pior caso O(n log n) obrigatório, heapsort in-place pode ajudar. Para listas comuns de aplicação Python, use ordenação padrão, não um mergesort didático, salvo necessidade medida que justifique a troca [3].

## Exercícios e verificação

1. Trace insertion sort em [4,1,3,2], indicando prefixo ordenado a cada rodada.
2. Explique por que preferir esquerda em empate é essencial para estabilidade do código de merge.
3. Deduza Θ(n log n) do mergesort e compare ao pior caso do quicksort com entrada ordenada.
4. No heap [9,6,7,2,1], retire máximo, repare heap e identifique invariante do sufixo.
5. Gere arrays aleatórios de comprimento 0..20 e compare os algoritmos executáveis com sorted, incluindo duplicatas e negativos.

**Leituras relacionadas:** [Recursão](/pt/topics/recursion-call-stack/) prova a recorrência, [heaps](/pt/topics/heaps-priority-queues/) trabalham prioridade e [busca binária](/pt/topics/binary-search/) exige entrada ordenada.
