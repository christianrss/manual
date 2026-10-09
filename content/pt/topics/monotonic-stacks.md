---
id: monotonic-stacks
title: "Pilhas monotônicas: próximo maior, temperaturas e histogramas"
description: "Demonstre limites lineares de pilhas monotônicas, calcule próximos maiores e maior área de histograma com testes executáveis."
category: algorithms
difficulty: intermediate
updated: 2026-10-09
prerequisites: [stacks-queues, arrays-and-strings]
sources:
  - {title: "Princeton Algorithms — Bags, Queues and Stacks", url: "https://algs4.cs.princeton.edu/13stacks/", kind: "university textbook"}
---
Uma **pilha monotônica** [1] mantém índices candidatos ordenados pelos valores para responder perguntas sobre próximo maior ou próximo menor sem refazer buscas desde cada elemento. Quando um valor novo domina candidato anterior, esse candidato pode ser resolvido ou descartado definitivamente. Embora exista while dentro de for, se cada índice entra uma vez e sai no máximo uma vez, a quantidade total de operações continua linear.

## Qual invariante permanece na pilha?

Para encontrar o **próximo valor estritamente maior à direita**, percorra da esquerda para a direita guardando índices cujos valores são não crescentes da base ao topo. Quando o valor novo x supera estritamente o valor do topo, o próximo maior do índice no topo é a posição atual: todas as posições intermediárias foram examinadas sem achar valor maior. Retire e repita até restaurar a ordem; em seguida empilhe o índice atual.

Índices, e não somente valores, preservam posições e distâncias. Valores iguais **não** resolvem uma pergunta de maior estrito. Se a questão pede maior-ou-igual ou menor-ou-igual, o operador de comparação deve mudar. O sinal da comparação integra o contrato matemático, não apenas a otimização.

## Implementação completa do próximo maior

~~~python
def indice_proximo_maior(valores):
    resposta = [-1] * len(valores)
    pendentes = []
    for i, valor in enumerate(valores):
        while pendentes and valores[pendentes[-1]] < valor:
            resposta[pendentes.pop()] = i
        pendentes.append(i)
    return resposta

assert indice_proximo_maior([2,1,3,2,4]) == [2,2,4,4,-1]
assert indice_proximo_maior([4,4,2]) == [-1,-1,-1]
assert indice_proximo_maior([]) == []
assert indice_proximo_maior([7]) == [-1]
~~~

Em [2,1,3,2,4], a posição zero espera quando chega o 1; o 3 resolve as posições um e zero, ambas apontando à posição dois. O 2 seguinte aguarda; o 4 resolve esse 2 e o 3 anterior. O 4 final não possui valor estritamente maior depois e fica com -1. A resposta guarda **índices**, não valores, permitindo reutilização para distâncias.

## Por que dois laços não geram O(n²)?

Cada índice é empilhado **exatamente uma vez**. No máximo uma vez será retirado: após pop, não volta à estrutura. Assim, somadas todas as iterações, existem até n pushes e n pops, além de O(n) comparações de topo. Tempo total O(n), memória auxiliar O(n) no pior caso, como entrada decrescente que mantém muitos candidatos pendentes.

É argumento agregado amortizado, não promessa de trabalho constante em cada rodada externa. Um único elemento grande pode resolver muitos candidatos, mas esses índices não serão removidos outra vez. Contar operações ao longo da execução evita multiplicar limites dos laços sem observar o comportamento.

![Uma pilha decrescente resolve posições pendentes quando chega um valor maior.](/diagrams/monotonic-stack.svg)

## Temperaturas diárias e transformação em distância

Se os números são temperaturas de dias, a pergunta pode ser quantos dias faltam até um dia **estritamente mais quente**. Quando posição j resolve i, devolva j−i em vez de j. Se não há dia mais quente, devolva zero. O mesmo invariante da pilha é preservado; muda somente o contrato de saída.

~~~python
def dias_ate_aquecer(temperaturas):
    dias = [0] * len(temperaturas)
    pilha = []
    for i, temperatura in enumerate(temperaturas):
        while pilha and temperaturas[pilha[-1]] < temperatura:
            anterior = pilha.pop()
            dias[anterior] = i - anterior
        pilha.append(i)
    return dias

assert dias_ate_aquecer([73,74,75,71,69,72,76,73]) == [1,1,4,2,1,1,0,0]
assert dias_ate_aquecer([5,5,5]) == [0,0,0]
~~~

A diferença entre **mais próximo** e **maior absoluto** importa. O próximo dia mais quente é o primeiro índice posterior com temperatura superior, não o dia mais quente de toda a sequência restante.

## Maior retângulo no histograma

Outro padrão mantém índices de barras em ordem de altura **não decrescente**. Para uma barra de altura h, a maior largura de retângulo limitada por h se estende até barras estritamente menores à esquerda e à direita. Quando a altura corrente é menor que o topo, retire o topo: a posição corrente limita à direita e o novo topo informa uma fronteira à esquerda com altura não superior à retirada. Uma barra sentinela no final força o processamento das barras pendentes.

~~~python
def maior_retangulo(alturas):
    if any(altura < 0 for altura in alturas):
        raise ValueError("alturas nao podem ser negativas")
    pilha = []
    melhor = 0
    for i in range(len(alturas) + 1):
        atual = 0 if i == len(alturas) else alturas[i]
        while pilha and alturas[pilha[-1]] > atual:
            altura = alturas[pilha.pop()]
            esquerda = pilha[-1] if pilha else -1
            largura = i - esquerda - 1
            melhor = max(melhor, altura * largura)
        pilha.append(i)
    return melhor

assert maior_retangulo([2,1,5,6,2,3]) == 10
assert maior_retangulo([]) == 0
assert maior_retangulo([2,2]) == 4
assert maior_retangulo([0,1,0]) == 1
~~~

A barra de altura 5 ao lado da barra 6 forma retângulo 5×2=10 no exemplo. O algoritmo usa O(n) tempo e O(n) espaço de pilha. Alturas iguais permanecem até aparecer barra estritamente menor; as retiradas subsequentes avaliam corretamente suas larguras. A barra virtual zero só serve para esvaziar a pilha, não faz parte do histograma original.

## Pilha monotônica versus deque monotônico

Um **deque monotônico** remove adicionalmente índices da *frente* quando expiram de uma janela deslizante. Isso permite máximo de janela, onde candidatos devem obedecer a um limite temporal. Pilha monotônica expõe uma ponta e resolve perguntas de vizinho e fronteiras de retângulos. Tratar pilha e deque como idênticos falha quando índices antigos saem de uma janela mesmo sem chegar valor maior ou menor.

| Pergunta | Invariante | Resultado |
| --- | --- | --- |
| Próximo maior estrito | Pendentes não crescentes | Índice à direita |
| Dias até aquecer | Temperaturas pendentes não crescentes | Distância em dias |
| Maior retângulo | Alturas pendentes não decrescentes | Área máxima |
| Máximo da janela | Deque decrescente com expiração | Máximo por janela |

## Contraexemplos e erros comuns

Trocar `<` por `<=` altera tratamento de iguais. Devolver **valor** em vez de **índice** impede calcular distância. Esquecer esvaziar a pilha no fim perde retângulos até a borda direita. Sentinela zero serve aqui porque as alturas reais são não negativas e áreas com altura zero não superam o melhor valor; alturas negativas são rejeitadas.

Pilha também não resolve genericamente máximo de faixa com atualizações arbitrárias. Os exercícios monotônicos pressupõem uma relação específica em uma passagem; mudanças frequentes podem exigir árvore de segmentos ou outra estrutura.

## Exercícios e verificação

1. Trace os índices pendentes de [2,1,3,2,4] e justifique cada posição resolvida.
2. Prove O(n) operações totais contando inserções e remoções de cada índice.
3. Explique por que temperaturas iguais não constituem dia mais quente.
4. Calcule a maior área de [2,1,5,6,2,3] e identifique altura limitante e largura.
5. Implemente oráculo quadrático de próximo maior e compare com indice_proximo_maior para todas as listas de comprimento até quatro sobre {0,1,2}.

**Capítulos relacionados:** [Pilhas e filas](/pt/topics/stacks-queues/) apresentam a estrutura; [janelas deslizantes](/pt/topics/sliding-window/) tratam da expiração de candidatos.
