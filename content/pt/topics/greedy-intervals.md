---
id: greedy-intervals
title: "Escalonamento guloso de intervalos: provas e contraexemplos"
description: "Demonstre a escolha pelo menor término, teste casos-limite e distinga o ótimo em quantidade da variante ponderada."
category: algorithms
difficulty: intermediate
updated: 2026-10-09
prerequisites: [sorting-algorithms, complexity-analysis]
sources:
  - {title: "MIT 6.046J — Interval Scheduling", url: "https://ocw.mit.edu/courses/6-046j-design-and-analysis-of-algorithms-spring-2015/resources/lecture-1-course-overview-interval-scheduling/", kind: "university lecture"}
---
Um algoritmo guloso escolhe uma possibilidade e mantém a decisão sem explorar todos os futuros. Um passo localmente promissor **não basta** para garantir solução ótima. A obrigação da prova é: alguma solução ótima pode ser reorganizada para conter a escolha gulosa? Escalonamento de intervalos é um exemplo claro porque a regra do menor término possui prova por troca, enquanto alternativas aparentemente razoáveis falham [1].

## Problema, restrições e extremos

Recebemos n trabalhos representados por intervalos **semiabertos** [início,fim), com início estritamente menor que fim. Queremos escolher a maior quantidade possível de trabalhos sem sobreposição numa máquina. Um trabalho pode seguir outro quando seu início é maior ou igual ao término anterior. Supomos valor unitário igual, nenhum tempo de preparação e execução não interrompida.

Assim [1,3) e [3,5) são compatíveis: o instante 3 pertence ao segundo intervalo, mas não ao primeiro. Na convenção de intervalos fechados, extremos tocados poderiam conflitar. Definir limites faz parte do contrato de entrada. Maximizar quantidade também é diferente de maximizar ocupação ou faturamento.

## Regra de menor término

Ordene por **término crescente**. Escolha o primeiro trabalho, depois o próximo cujo início seja no término da última escolha ou depois; continue até esgotar a lista. A intuição é preservar o maior tempo restante possível, mas o argumento formal abaixo demonstra por que isso é seguro [1].

Considere A=[0,5), B=[1,2), C=[2,3), D=[3,4), E=[4,5). Escolher pelo início mais cedo aceita somente A. Escolher pelo fim mais cedo aceita B,C,D,E: quatro tarefas. Selecionar a **menor duração** tampouco é ótimo universalmente; uma tarefa muito curta ao final do período pode bloquear várias anteriores.

![Escalonamento guloso favorece tarefas compatíveis que terminam cedo.](/diagrams/greedy-interval-scheduling.svg)

## Implementação, limites e complexidade

~~~python
def agendar(tarefas):
    for inicio, fim in tarefas:
        if inicio >= fim:
            raise ValueError("esperado inicio < fim")
    ordenadas = sorted(tarefas, key=lambda p: (p[1], p[0]))
    escolhidas = []
    ultimo_fim = None
    for inicio, fim in ordenadas:
        if ultimo_fim is None or inicio >= ultimo_fim:
            escolhidas.append((inicio, fim))
            ultimo_fim = fim
    return escolhidas

tarefas = [(0,5),(1,2),(2,3),(3,4),(4,5)]
assert agendar(tarefas) == [(1,2),(2,3),(3,4),(4,5)]
assert agendar([]) == []
assert agendar([(1,3),(3,6)]) == [(1,3),(3,6)]
assert len(agendar([(0,4),(1,3),(2,5)])) == 1
try:
    agendar([(2,2)])
    assert False
except ValueError:
    pass
~~~

Ordenação consome O(n log n) comparações e o percurso O(n), dando tempo total O(n log n). A cópia ordenada e a saída usam O(n) memória auxiliar. Se os trabalhos chegam ordenados pelo fim, o percurso isolado é O(n). O código rejeita intervalos de comprimento zero, impedindo que empates distorçam a convenção utilizada.

## Demonstração por troca

Seja g a tarefa compatível que termina mais cedo entre as restantes. Considere uma agenda ótima cujo primeiro trabalho é o. Pela escolha gulosa, fim(g) ≤ fim(o). Substitua o por g: todos os trabalhos posteriores da solução ótima começavam no fim(o) ou depois, logo continuam começando no fim(g) ou depois. A troca preserva viabilidade e quantidade. Portanto **existe uma solução ótima que começa por g**.

Agora descarte trabalhos que começam antes de fim(g). O problema restante possui a mesma estrutura, só com menos candidatos viáveis. Repetir a troca prova indutivamente que cada escolha gulosa pode integrar agenda de cardinalidade máxima. A prova **não** afirma que g participa de toda solução ótima nem que maximiza lucro [1].

A propriedade estrutural chama-se *greedy-choice property*: alguma solução ótima contém a escolha local. Se o objetivo ou as restrições impedem a troca, o algoritmo perde sua prova de correção.

## Intervalos ponderados: contraexemplo

Suponha X=[0,2) paga 1, Y=[0,3) paga 100 e Z=[2,4) paga 1. Menor término escolhe X e Z, dois trabalhos com lucro 2. A melhor agenda ponderada escolhe somente Y, lucro 100. Trocar Y por X mantém quantidade, mas destrói o resultado monetário, exatamente onde a prova anterior não serve.

O escalonamento ponderado normalmente usa programação dinâmica. Ordene pelo fim, defina p(i) como o último trabalho anterior que termina antes do início de i e calcule OPT(i)=max(OPT(i−1), peso(i)+OPT(p(i))). O primeiro termo ignora i; o segundo o inclui. Busca binária de predecessores permite O(n log n) com representação apropriada. O objetivo não é o mesmo do problema sem pesos [1].

## União de intervalos é outra operação

Outra questão comum pede a **união** de faixas sobrepostas, não um subconjunto compatível. Ordene por início. Una o próximo intervalo ao último produzido se ele começar **estritamente antes** do término atual; estenda o fim ao máximo. Dois intervalos semiabertos que apenas se tocam podem permanecer separados se o contrato mescla apenas sobreposição.

~~~python
def unir_sobrepostos(intervalos):
    for inicio, fim in intervalos:
        if inicio >= fim:
            raise ValueError("esperado inicio < fim")
    saida = []
    for inicio, fim in sorted(intervalos):
        if saida and inicio < saida[-1][1]:
            saida[-1] = (saida[-1][0], max(fim, saida[-1][1]))
        else:
            saida.append((inicio, fim))
    return saida

assert unir_sobrepostos([(1,4),(2,6),(8,9)]) == [(1,6),(8,9)]
assert unir_sobrepostos([(1,3),(3,5)]) == [(1,3),(3,5)]
assert unir_sobrepostos([]) == []
~~~

O invariante afirma que a saída representa exatamente a união das faixas processadas e os segmentos consecutivos não se sobrepõem. Mesclar pode criar intervalo que não era trabalho original; por isso a união não substitui o escalonamento por quantidade.

## Reconhecendo uma regra gulosa falsa

| Objetivo | Estratégia apropriada | Hipótese central |
| --- | --- | --- |
| Mais tarefas compatíveis | Menor término | Valor igual |
| Maior lucro ponderado | Programação dinâmica | Objetivo diferente |
| União de cobertura | Ordenar e unir | Saída pode criar novos intervalos |
| Menor número de salas | Heap ou varredura de sobreposição | É preciso aceitar todas as tarefas |

Desconfie de algoritmos por menor início, menor duração, maior lucro ou menor sobreposição quando não existe prova de troca. Um contraexemplo com três tarefas muitas vezes refuta a regra universal. Passar poucos testes não constitui demonstração; a prova por troca justifica a solução.

## Exercícios e verificação

1. Percorra A até E e explique por que o greedy aceita quatro tarefas.
2. Mostre por que fim(g) ≤ fim(o) preserva viabilidade após trocar a primeira tarefa ótima.
3. Compare lucros 2 e 100 no contraexemplo e identifique a hipótese violada.
4. Explique exatamente por que [1,3) e [3,5) podem ocupar a mesma máquina.
5. Implemente oráculo exaustivo para até oito trabalhos, verificando subconjuntos compatíveis, e compare o ótimo com agendar.

**Capítulos relacionados:** [Ordenação](/pt/topics/sorting-algorithms/) prepara a ordem; [programação dinâmica](/pt/topics/dynamic-programming/) resolve a versão com pesos.
