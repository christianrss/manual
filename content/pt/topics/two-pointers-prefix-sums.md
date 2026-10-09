---
id: two-pointers-prefix-sums
title: "Two pointers e prefix sums: invariantes e consultas em subarrays"
description: "Deduza ponteiros opostos e somas prefixadas, prove invariantes e resolva problemas de intervalos e subarrays com negativos."
category: algorithms
difficulty: intermediate
updated: 2026-10-09
prerequisites: [arrays-and-strings, sorting-algorithms, hash-tables]
sources:
  - {title: "USACO Guide — Two Pointers", url: "https://usaco.guide/silver/two-pointers", kind: "algorithm teaching guide"}
  - {title: "USACO Guide — Prefix Sums", url: "https://usaco.guide/silver/prefix-sums", kind: "algorithm teaching guide"}
  - {title: "Python Documentation — itertools.accumulate", url: "https://docs.python.org/3/library/itertools.html#itertools.accumulate", kind: "official language documentation"}
---
Muitos problemas de sequências ficam mais simples quando descobrimos **informações que podem ser mantidas de forma incremental**. Two pointers preserva um intervalo ou par candidato sem refazer buscas. Somas prefixadas pré-calculam totais acumulados para que a soma de um intervalo vire uma subtração. As técnicas não são intercambiáveis: cada uma exige hipóteses, invariantes e tratamento próprios de atualização. Reconhecer esses requisitos importa mais que memorizar um template de entrevista [1][2].

## Ponteiros em extremidades opostas

Suponha sequência de n números ordenada em ordem não decrescente e busque duas **posições distintas** cuja soma seja T. Comece esquerda=0 e direita=n−1. Se a[esquerda]+a[direita] é menor que T, aumentar direita não ajudaria porque já estamos no maior valor restante; todos os pares usando essa posição esquerda ficam abaixo de T, então avance esquerda. Se a soma supera T, nenhum par com o valor atual da direita e uma posição à esquerda pode servir, então reduza direita. Se a soma é T, devolva o par [1].

É uma **prova por eliminação**: cada etapa descarta pelo menos um índice sem descartar soluções possíveis. Portanto ocorrem no máximo n−1 movimentos de ponteiros, com tempo O(n) e memória O(1) para entrada ordenada com indexação aleatória. Se a entrada não está ordenada, ordenar antes pode custar O(n log n). Se é preciso preservar índices originais, ordene pares (valor,índice) em vez de perder suas identidades.

![Números ordenados e decisão dos ponteiros pela comparação com a soma desejada.](/diagrams/two-pointers-prefix.svg)

~~~python
def par_soma_ordenada(valores, alvo):
    esquerda, direita = 0, len(valores) - 1
    while esquerda < direita:
        soma = valores[esquerda] + valores[direita]
        if soma == alvo:
            return (esquerda, direita)
        if soma < alvo:
            esquerda += 1
        else:
            direita -= 1
    return None

assert par_soma_ordenada([-4, -1, 2, 5, 9], 4) == (1, 3)
assert par_soma_ordenada([3, 3], 6) == (0, 1)
assert par_soma_ordenada([7], 14) is None
assert par_soma_ordenada([], 1) is None
assert par_soma_ordenada([1, 3, 5], 20) is None
~~~

A função exige dados ordenados e comparações/somas de custo constante. Nunca combina um elemento consigo mesmo, pois esquerda precisa ser estritamente menor que direita. Duplicatas são permitidas. Com entrada não ordenada, quando queremos apenas uma passagem e não importa usar memória extra, two-sum por hash pode alcançar O(n) esperado com armazenamento O(n).

## Ponteiros movendo-se na mesma direção

Uma **janela deslizante** mantém intervalo [esquerda,direita), expandindo a extremidade direita quando chegam elementos e avançando esquerda quando uma restrição é violada. Para valores não negativos e limite B≥0, a soma cresce ou permanece igual quando direita avança e diminui ou permanece igual quando esquerda avança. Essa monotonicidade permite procurar a janela mais longa com soma ≤B movendo cada ponteiro O(n) vezes ao todo [1].

Com valores negativos, descartar prefixo pode eliminar resposta ótima: expandir direita pode **diminuir** a soma. A regra simples 'encolha enquanto soma>B' deixa de ser demonstravelmente correta. Exemplo [4,−3,2] com limite 3: ao ver o 4 inicial, uma rotina ingênua encolhe e perde a sequência inteira de tamanho três cuja soma é 3. Use somas prefixadas ou outra estrutura monotônica conforme o problema.

## Definição de prefix sums e cancelamento algébrico

Para array a de comprimento n, defina P[0]=0 e P[i+1]=P[i]+a[i] para 0≤i<n. Assim P[k] é a soma dos **primeiros k elementos**. A soma do subarray semiaberto a[l:r] vale P[r]−P[l], pois os primeiros l termos aparecem nas duas somas e se cancelam. É uma identidade exata, não estimativa. Serve para negativos e zeros, além de positivos [2].

Para a=[3,−2,5,1], os prefixos são P=[0,3,1,6,7]. A consulta [1,3) fornece P[3]−P[1]=6−3=3, igual a −2+5. O intervalo [0,4) resulta 7. Construir os prefixos custa O(n) tempo e O(n) espaço; cada soma de intervalo **estático** custa O(1) operações aritméticas. Se dados mudam, recalcular pode custar O(n), motivo para estudar Fenwick ou segment tree quando há muitas atualizações.

~~~python
def prefixos(valores):
    saida = [0]
    for valor in valores:
        saida.append(saida[-1] + valor)
    return saida

def soma_intervalo(prefixo, inicio, fim):
    n = len(prefixo) - 1
    if not 0 <= inicio <= fim <= n:
        raise ValueError("intervalo semiaberto invalido")
    return prefixo[fim] - prefixo[inicio]

p = prefixos([3, -2, 5, 1])
assert p == [0, 3, 1, 6, 7]
assert soma_intervalo(p, 1, 3) == 3
assert soma_intervalo(p, 0, 4) == 7
assert soma_intervalo(prefixos([]), 0, 0) == 0
try:
    soma_intervalo(p, 2, 5)
    assert False
except ValueError:
    pass
~~~

A biblioteca padrão oferece itertools.accumulate para totais acumulados [3], mas é necessário acrescentar P[0]=0 quando o algoritmo assume índices correspondentes a intervalos semiabertos. Misturar indexação de base zero e base um é origem comum de erros de limites.

## Contagem de subarrays-alvo, mesmo com negativos

A equação soma(a[l:r])=T equivale a P[r]−P[l]=T, ou P[l]=P[r]−T. Processe cada limite direito r e mantenha frequência dos prefixos **anteriores**. Antes de inserir P[r], conte quantas vezes P[r]−T apareceu. Isso equivale exatamente à quantidade de índices l<r que iniciam subarrays de soma T. Inicialize frequência de P[0]=0 como um para contar intervalos começando no índice zero.

~~~python
def contar_subarrays(valores, alvo):
    vistos = {0: 1}
    prefixo = 0
    total = 0
    for valor in valores:
        prefixo += valor
        total += vistos.get(prefixo - alvo, 0)
        vistos[prefixo] = vistos.get(prefixo, 0) + 1
    return total

assert contar_subarrays([1, -1, 1], 1) == 3
assert contar_subarrays([0, 0], 0) == 3
assert contar_subarrays([], 0) == 0
assert contar_subarrays([2, -2, 3], 3) == 2
~~~

A última afirmação tem dois intervalos: [2,−2,3] e [3], ambos com soma três. O dicionário pode guardar O(n) prefixos distintos. Supondo hash esperado O(1) e aritmética de custo constante, tempo esperado O(n), com memória O(n). Não afirme pior caso O(n) sem hipóteses sobre colisões e custo de hash.

## Prefix sums, difference arrays e alterações por intervalo

Prefix sums aceleram **consultas estáticas**, não necessariamente mudanças em posições arbitrárias. Um **array de diferenças** resolve outra tarefa: representar muitas adições em faixas quando os valores podem ser reconstruídos no fim. Defina D[0]=a[0] e D[i]=a[i]−a[i−1]. Somar delta aos elementos de [l,r) modifica apenas D[l]+=delta e, se r<n, D[r]−=delta. A reconstrução por soma cumulativa custa O(n).

Funciona porque toda posição reconstruída de l a r−1 incorpora delta, enquanto o negativo em r o cancela para posições posteriores. Difference array serve quando **as alterações podem ser acumuladas** e o array final é obtido depois. Consultas e atualizações online intercaladas podem exigir Fenwick/segment tree, com operações e custos distintos.

## Reconheça a pergunta antes de escolher a técnica

| Problema | Método | Hipótese oculta |
| --- | --- | --- |
| Soma de par em lista ordenada | Ponteiros opostos | Entrada ordenada |
| Restrição por soma numa janela | Sliding window | Frequentemente requer não negativos |
| Muitas somas de intervalos sem alterações | Prefix sums | Snapshot estático |
| Quantidade de subarrays com soma alvo | Prefixo + frequências | Hash esperado |
| Muitas adições em intervalos | Difference array | Reconstrução posterior |
| Somas dinâmicas de intervalos | Fenwick/segment tree | Custos de atualização e consulta |

Two pointers não é garantia de O(n) se o loop reiniciar constantemente um ponteiro; prove que cada um se move monotonicamente no máximo n vezes. Prefix preprocessing é desperdício quando há só uma consulta simples. Frequências contam **subarrays**, não apenas valores prefixados distintos, então trocar o mapa por um set ignora repetições de soma zero.

## Exercícios e verificação

1. Trace movimentos de esquerda/direita em [-4,−1,2,5,9] procurando soma 4 e justifique descartes.
2. Explique por que ponteiros opostos não servem diretamente para lista não ordenada como [8,1,7,2].
3. Calcule prefixos de [3,−2,5,1] e somas [0,2), [1,3) e intervalo vazio [2,2).
4. Mostre por que [4,−3,2] quebra a regra de janela simples baseada em não negativos.
5. Enumere os subarrays não vazios de [0,0] e verifique que contar_subarrays retorna três para alvo zero.

**Leituras relacionadas:** [Arrays e strings](/pt/topics/arrays-and-strings/) definem faixas semiabertas; [ordenação](/pt/topics/sorting-algorithms/) prepara entrada ordenada; [sliding window](/pt/topics/sliding-window/) estende os ponteiros na mesma direção.
