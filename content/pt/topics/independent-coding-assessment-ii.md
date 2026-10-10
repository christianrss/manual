---
id: independent-coding-assessment-ii
title: "Avaliação independente II: lotes minimax e ilhas dinâmicas"
description: "Resolva desafios inéditos de busca por capacidade e conectividade incremental, com 18 casos públicos sem soluções antecipadas."
category: algorithms
difficulty: intermediate
updated: 2026-10-09
prerequisites: [binary-search, disjoint-set-union]
sources:
  - {title: "CP-Algorithms — Binary Search", url: "https://cp-algorithms.com/num_methods/binary_search.html", kind: "technical algorithm reference"}
  - {title: "CP-Algorithms — Disjoint Set Union", url: "https://cp-algorithms.com/data_structures/disjoint_set_union.html", kind: "technical algorithm reference"}
---
Problemas inéditos devem ser resolvidos pelo **contrato de entrada e pelos invariantes**, não pela memorização de respostas. Esta segunda oficina independente apresenta dois desafios originais que exercitam fundamentos complementares de engenharia de software: **particionamento minimax** com decisão monotônica e **conectividade dinâmica em grade** com atualizações repetidas. Diferentemente dos capítulos com soluções, o código inicial lança `NotImplementedError` e não contém implementação de referência. Não são exercícios oficiais nem vazados de processos seletivos.

## Instruções e limites da avaliação

A fonte [unsolved_drills_2.py](https://github.com/christianrss/manual/blob/main/examples/python/unsolved_drills_2.py) possui duas assinaturas e docstrings com contratos. Implemente sem renomear funções nem modificar dados fornecidos. Execute o [verificador público](https://github.com/christianrss/manual/blob/main/examples/python/drill_grader_2.py), que testa **18 casos** entre as duas tarefas. Como as respostas dos exemplos são públicas, passar apenas por elas não demonstra correção em novos grafos, sequências ou casos-limite.

Uma simulação didática de 90 minutos pode reservar tempo para esclarecer limites, derivar abordagem, codificar e examinar contraexemplos e complexidade. Isso **não** descreve necessariamente o tempo de uma seleção real. Registre tentativas, falhas e como sua solução reage a novos requisitos. A revisão deve avaliar se a implementação continua compreensível e sustentável.

## Desafio A: menor pico de carga por lote

Um pipeline recebe tarefas com **cargas inteiras não negativas** em ordem fixa. Deve dividi-las em **no máximo k lotes contíguos não vazios**, sem alterar a ordem. A capacidade necessária é a maior soma entre os lotes. Retorne a **menor capacidade possível**. Para lista vazia, devolva zero. Suponha k≥1, inteiros de tamanho arbitrário e comparação exata, sem arredondamentos em ponto flutuante.

Exemplo: cargas [7,2,5,10,8], k=2. A partição [7,2,5] | [10,8] tem somas 14 e 18, logo exige capacidade 18. Capacidade 17 não permite agrupar as duas últimas tarefas nem colocar as outras dentro de um único lote adicional. Portanto, o mínimo esperado é **18**.

Uma pista geral: determine quais valores de capacidade são *viáveis* e prove se a viabilidade pode voltar de verdadeira para falsa quando a capacidade aumenta. É necessário demonstrar que o teste de viabilidade escolhido nunca subestima lotes necessários. Derive e programe os detalhes por conta própria [1].

## Mudanças de regra e respostas tentadoras

Se k supera a quantidade de tarefas, não invente lotes vazios obrigatórios. O contrato permite **até** k, não exatamente k, e o ótimo pode usar menos grupos. Quando cargas são zero, capacidade zero pode ser possível; código que presume somas positivas falha. Se há apenas tarefa uma única carga de dez e k=10, o limite ainda precisa ser dez.

Não ordene cargas: isso altera a contiguidade e resolve outro problema. Não acumule valores inteiros muito grandes em ponto flutuante quando o contrato exige resultado exato. Na complexidade, distinga quantidade de tarefas n, limite k e amplitude numérica das capacidades candidatas. Busca binária sobre valores só se justifica **depois da prova de monotonicidade**.

## Desafio B: ilhas após ativação incremental

Você recebe uma grade rows × columns, inicialmente inativa. Cada ação fornece coordenada válida (r,c) e ativa essa célula permanentemente. Após **cada ação**, devolva número de componentes conexos de células ativas considerando apenas **quatro vizinhos**: acima, abaixo, esquerda e direita. Células diagonais **não são vizinhas conexas**. Ativação repetida não faz nada; não cria componente nem reduz contagem indevidamente.

Exemplo: grade 3×3, ações [(0,0),(0,1),(1,2),(1,1),(0,0)]. As contagens são **[1,1,2,1,1]**. Ativar (1,1) une a região de (0,0),(0,1) à célula (1,2), reduzindo dois componentes a um. A última ação repete (0,0), mantendo contagem.

Uma solução direta recalcula componentes desde o início após cada ação, mas avalie sua complexidade quando grade e quantidade de ações crescem. Estratégia eficiente mantém identidades de componentes e une vizinhos ativos; derive invariantes e trate duplicatas antes de escolher estrutura de dados [2].

## Contraexemplos para soluções superficiais

Células diagonais (0,0) e (1,1) continuam separadas até surgir conexão ortogonal. Uma ativação pode juntar **mais de dois componentes existentes**, mas cada componente distinto deve ser fundido uma única vez. Vizinhos ativos diferentes podem já pertencer à mesma região: decrementar por vizinho em vez de por união efetiva dá resposta incorreta.

Não aloque rows×columns células indiscriminadamente se a grade é enorme, mas só poucas posições são ativadas. Declare limites assumidos e compare representações densas e esparsas. Lista de ações vazia devolve lista vazia mesmo quando dimensões são positivas. Em grade com dimensão zero, não há coordenadas de ativação válidas.

## Como verificar sem soluções publicadas

O verificador inclui lista vazia, ativações repetidas, diagonal, ponte entre componentes, cargas zero, tarefa única grande, excesso de lotes e ativação que une **quatro componentes**. A implementação de referência permanece ausente; o CI comprova somente que as funções iniciais continuam sem solução e que o avaliador público rejeita implementações trivialmente erradas.

~~~python
from pathlib import Path
exemplos = Path("examples/python")
assert (exemplos / "unsolved_drills_2.py").is_file()
assert (exemplos / "drill_grader_2.py").is_file()
assert len([1,1,2,1,1]) == 5
~~~

Crie testes independentes após passar os públicos. Para n pequeno, enumere todas as partições possíveis e compare com algoritmo otimizado. Em grades curtas, recalcule ilhas por busca em largura após cada ativação; é um oráculo independente da estrutura incremental. Limite tamanhos, pois enumeração exponencial ou buscas repetidas não escalam como algoritmo de produção.

## Rubrica técnica e comunicação

| Dimensão | Evidência | Pontos |
| --- | --- | ---: |
| Contrato e limites | Hipóteses e entradas adversariais explícitas | 20 |
| Implementação executável | Casos públicos e testes novos corretos | 30 |
| Argumentação | Invariantes e prova de término | 20 |
| Recursos | Tempo/memória com parâmetros definidos | 15 |
| Manutenção | Nomes claros, sem mutação inesperada, testes úteis | 15 |

A rubrica de 100 pontos é editorial, não modelo de pontuação de empregador. Como fixtures públicas podem ser decoradas, avaliação rigorosa deve usar **entradas inéditas adicionais**. Um verificador disponível não significa que as funções foram resolvidas.

## Exercícios e verificação

1. Implemente ambas as funções sem mudar assinaturas ou respostas das fixtures.
2. Construa exemplo de cargas no qual ordenar parece vantajoso, mas altera partições permitidas.
3. Explique por que viabilidade não depende apenas da média de soma e precisa contar grupos contíguos.
4. Projete sequência de ilhas onde uma ativação conecta quatro componentes distintos.
5. Compare memória de uma grade booleana densa com mapa esparso por coordenadas ativadas.

**Capítulos relacionados:** [Busca binária por resposta](/pt/topics/binary-search/), [Conjuntos disjuntos](/pt/topics/disjoint-set-union/), [Busca em grafos](/pt/topics/graph-traversal/) e [Avaliação independente I](/pt/topics/independent-coding-assessment/) oferecem fundamentos sem implementar as tarefas.
