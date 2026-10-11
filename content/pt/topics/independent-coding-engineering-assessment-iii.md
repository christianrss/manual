---
id: independent-coding-engineering-assessment-iii
title: "Avaliação Independente III: Programação Dinâmica e Eventos Idempotentes"
description: "Resolva dois exercícios inéditos de particionamento por programação dinâmica e projeção idempotente, com corretores e critérios de revisão."
category: interview-practice
difficulty: intermediate
updated: 2026-10-11
prerequisites: [dynamic-programming, testing-strategies, programming-semantics-contracts, asynchronous-messaging]
sources:
  - {title: "MIT 6.006 — Dynamic Programming Lecture Notes", url: "https://ocw.mit.edu/courses/6-006-introduction-to-algorithms-spring-2008/pages/lecture-notes/", kind: "university teaching materials"}
  - {title: "Python Language Reference — Standard Type Hierarchy and Mappings", url: "https://docs.python.org/3/library/stdtypes.html", kind: "official language documentation"}
  - {title: "AWS Builders' Library — Making retries safe with idempotent APIs", url: "https://aws.amazon.com/builders-library/making-retries-safe-with-idempotent-APIs/", kind: "original engineering article"}
---
Esta avaliação exige **implementação independente**, não a leitura de mais dois algoritmos resolvidos. O primeiro exercício exige deduzir um estado de otimização para particionar uma sequência sob restrições. O segundo exige projetar um componente de transição de estado cujo contrato inclui validação rigorosa, identidade de eventos, preservação das entradas e falhas determinísticas. Ambos são exercícios educacionais originais, **não** questões reproduzidas de processos seletivos de empresas.

Antes de começar, estude [programação dinâmica](/pt/topics/dynamic-programming/), [estratégias de teste](/pt/topics/testing-strategies/) e [mensageria assíncrona](/pt/topics/asynchronous-messaging/). Derivar uma recorrência não basta se o programa ignora casos de fronteira; elaborar uma API elegante também não basta quando reprocessar um evento produz efeitos incorretos. O MIT apresenta a definição de estados e transições como elemento central do raciocínio algorítmico [1]. A AWS destaca a importância de identificadores estáveis para permitir repetição segura de operações [3].

## Preparação e entregáveis

O [arquivo inicial](https://github.com/christianrss/manual/blob/main/examples/python/unsolved_drills_3.py) contém duas assinaturas sem implementação. O [corretor público](https://github.com/christianrss/manual/blob/main/examples/python/drill_grader_3.py) verifica casos representativos válidos e inválidos. Faça o clone do repositório, implemente ambas as funções sem alterar suas assinaturas e execute:

~~~bash
python examples/python/drill_grader_3.py
~~~

As entradas e saídas esperadas são públicas. Portanto, passar no corretor não impede soluções que decoram resultados; ele não é um serviço com testes secretos, não emite certificados e não comprova desempenho em entrevistas. Como convenção de estudo, reserve 45 minutos para o primeiro problema, 30 minutos para o segundo e 15 minutos para testes e revisão. Esses **90 minutos são apenas uma proposta didática**, não a reprodução de um cronograma oficial de qualquer seleção.

Entregue o código junto de uma explicação curta contendo domínio de entrada, invariantes, custo temporal e espacial, um teste adversarial criado por você e uma decisão de projeto justificada. Código que modifica dados pertencentes ao chamador ou apresenta custo esperado como limite garantido de pior caso deve ser reprovado na revisão.

## Problema A — Penalidade mínima para grupos contíguos

Dada uma sequência ordenada `loads` com `n` valores inteiros **não negativos**, divida-a em grupos contíguos não vazios. Um grupo pode ter no máximo `max_group_size=L` elementos. Se a soma das cargas de um grupo for `s`, seu custo será `s² + overhead`, onde `overhead=h` é um inteiro não negativo. Retorne o **menor custo total** entre todas as partições válidas, sem precisar retornar os grupos.

Exemplo: `loads=[2,3,1]`, `L=2`, `h=2`. Três grupos unitários custam `(4+2)+(9+2)+(1+2)=20`. A partição `[2]|[3,1]` custa `(4+2)+(16+2)=24`; a partição `[2,3]|[1]` custa `(25+2)+(1+2)=30`. Portanto o ótimo é **20**. Se o custo fixo aumenta para 20, `[2]|[3,1]` custa 60 e torna-se melhor que os três grupos unitários, que custariam 74. A escolha ótima depende do custo fixo e da penalização quadrática.

A assinatura é `minimum_partition_penalty(loads, max_group_size, overhead)`. Entrada vazia retorna zero. `loads` deve ser lista ou tupla de inteiros não negativos; `L` deve ser inteiro positivo e `h` inteiro não negativo. `bool` não é aceito como inteiro. Entradas inválidas provocam `ValueError`. Use aritmética inteira exata e não altere nem reordene a sequência original.

## Estados, provas e complexidade

É necessário diferenciar uma *fronteira de partição* de um *comprimento de grupo*. Um grupo que termina no índice exclusivo `i` pode começar em `j`, com `max(0,i-L) <= j < i`. Escolher imediatamente o grupo de menor penalidade local parece atraente, mas pode impedir a partição global ótima. Quando `h` cresce, consolidar grupos economiza custo fixo; quando a soma cresce, elevar ao quadrado pode tornar a consolidação cara.

Especifique rigorosamente o significado de `dp[i]`, quais estados podem antecedê-lo e por que toda alternativa válida para o último grupo está entre as opções consideradas. A demonstração deve cobrir o prefixo vazio, a propriedade de subestrutura ótima e a terminação das transições, pois todo estado predecessor tem índice menor que `i`. Essas orientações são um roteiro de prova, **não uma implementação entregue**. Caso use somas prefixadas, explique qual trabalho repetitivo elas evitam.

O alvo de implementação é `O(n·min(n,L))` tempo e `O(n)` espaço adicional, num modelo de aritmética inteira de custo unitário. Declarar apenas `O(n²)` perde a informação do limite de grupo; declarar `O(n)` supondo que sempre basta examinar o predecessor imediato está incorreto em geral. Como inteiros Python podem possuir precisão arbitrária, operações sobre números gigantes não possuem custo constante em bits.

## Problema B — Projeção de saldos com idempotência

Implemente `apply_idempotent_events(opening, events)`. `opening` é um dicionário que associa identificadores de contas não vazios e sensíveis a maiúsculas/minúsculas a saldos inteiros não negativos, expressos na menor unidade monetária. A sequência ordenada de eventos contém triplas `(event_id, account_id, delta)`, em que os dois identificadores são strings não vazias e `delta` é um inteiro com sinal.

Cada evento pode alterar somente uma conta já existente no dicionário inicial. A aplicação do delta não pode produzir saldo negativo. A **primeira ocorrência** de um identificador aplica sua alteração; uma ocorrência posterior com **mesmo ID, mesma conta e mesmo delta** é uma repetição e não produz novo efeito. Reutilizar o ID com qualquer conteúdo diferente é erro, mesmo quando o delta for zero. O escopo dos IDs abrange todas as contas **dentro da mesma chamada**.

Por exemplo, começando de `{"a":10}`, os eventos `[("x","a",-3),("x","a",-3),("y","a",3)]` produzem `{"a":10}`. Já `[("x","a",-3),("x","a",-4)]` deve ser rejeitado: o mesmo identificador não pode representar intenções diferentes. Rejeite também contas desconhecidas, formatos inválidos, tipos errados, IDs vazios e operações que provoquem saldo negativo. Devolva sempre um novo dicionário, sem alterar os argumentos fornecidos pelo chamador.

## Identidade, ordem e limites transacionais

A ordem dos eventos faz parte da semântica. Para saldo inicial zero, `+5,-5` é válido; `-5,+5` falha na primeira operação. Somar antecipadamente todos os deltas de uma conta descarta essa restrição cronológica. Comparar só identificadores, sem guardar a carga original do evento, permite mascarar reutilização conflituosa de IDs. A AWS também diferencia repetições legítimas de requisições que apresentam conteúdo divergente sob o mesmo identificador [3].

O novo dicionário fornece uma garantia limitada de **não modificação dos dados do chamador**: se ocorrer exceção, a entrada permanece inalterada. Não equivale a uma transação durável. Não há banco de dados, efeitos externos, deduplicação entre chamadas, bloqueios entre processos ou entrega exatamente uma vez em rede. Um serviço persistente precisaria coordenar atomicamente o registro do identificador e a alteração de estado, definir retenção de registros, autorização e concorrência [3].

Se houver `A` contas e `E` eventos, o alvo é `O(A+E)` operações **em tempo esperado** e `O(A+E)` espaço, considerando as hipóteses usuais de hashing dos dicionários Python [2]. O modelo não garante desempenho constante de acesso a hashes sob adversários nem ignora o custo em bits de inteiros muito grandes.

## Critérios de revisão de engenharia

No problema A, explique a diferença entre calcular o custo ótimo e reconstruir os grupos, derive o custo em função de `n` e `L`, e apresente um contraexemplo para a escolha gulosa. No problema B, defina qual estado tem autoridade, o escopo dos IDs, o momento das validações e as condições que tornam seguro ignorar uma repetição. Idempotência dentro de uma chamada não é o mesmo que processamento exatamente uma vez após falhas de servidores.

Usar apenas um conjunto `seen_ids` não detecta uma repetição com payload conflitante. Modificar o dicionário `opening` e tentar desfazer alterações quando ocorre erro também aumenta os riscos de deixar estado parcialmente alterado. Separe validação, transições de estado e responsabilidades de infraestrutura. O princípio não exige criar classes ou camadas artificiais para uma função curta, mas exige fronteiras de responsabilidade explícitas.

## Avaliação independente e contraexemplos

Crie testes **antes** de executar o corretor. No problema A, enumere todas as formas de inserir separadores em sequências pequenas e compare seus mínimos com a versão otimizada. Inclua `L=1`, `L>=n`, entrada vazia, zeros, números grandes e overhead elevado. O algoritmo de força bruta tem crescimento exponencial e deve servir apenas como oráculo para entradas reduzidas.

No problema B, produza IDs únicos com deltas que preservem saldos não negativos e insira cópias de eventos em posições posteriores às ocorrências originais. O saldo final não deve mudar. Troque o payload mantendo o ID e exija `ValueError`. Teste se uma falha ao final da lista mantém os argumentos originais intactos e se duas chamadas independentes realmente não compartilham uma memória de deduplicação.

Registre pelo menos dois contraexemplos por exercício e o erro conceitual que cada um evidencia. O corretor público cobre apenas os casos publicados. O repositório mantém as duas funções sem solução e não possui uma infraestrutura privada de avaliação.

## Exercícios e verificação

1. Enumere as partições de `[2,3,1]` com `L=2` e `h=20`. **Resposta esperada:** 60. Justifique a mudança em relação ao resultado com `h=2`.
2. Para `[0,0,0]`, `L=2` e `h=0`, demonstre que qualquer divisão válida custa zero. Explique por que a entrada vazia retorna zero sem criar um grupo vazio.
3. Partindo de `{"a":5}`, avalie `[("x","a",-5),("x","a",-5),("y","a",2)]`. **Resultado esperado:** `{"a":2}`.
4. Para `{"a":1,"b":1}` e `[("x","a",0),("x","b",0)]`, determine o resultado. **Resposta:** `ValueError`, pois o segundo uso de `x` possui payload diferente, apesar de ambos os deltas serem zero.
5. Qual mudança mínima de infraestrutura permitiria persistência entre reinicializações? **Verificação:** adicionar um banco não basta; mudança de saldo e registro da idempotência precisam integrar uma operação atômica, inclusive sob concorrência [3].

O programa fornece uma interface reproduzível de estudo. O que constitui evidência de aprendizagem é implementar as funções de modo independente, escrever novos testes e explicar suas limitações — não a quantidade de páginas publicadas.
