---
id: legacy-refactoring-assessment
title: "Avaliação de Código Legado: Caracterização, Isolamento por Cliente e Paginação"
description: "Investigue uma busca de tickets deliberadamente defeituosa, caracterize seu comportamento e implemente um contrato corrigido sem expor campos privados."
category: interview-practice
difficulty: intermediate
updated: 2026-10-11
prerequisites: [refactoring-design-patterns, testing-strategies, api-security, api-contracts-pagination]
sources:
  - {title: "Martin Fowler — Refactoring Boundary", url: "https://martinfowler.com/bliki/RefactoringBoundary.html", kind: "primary engineering essay"}
  - {title: "Martin Fowler — Self-Testing Code", url: "https://martinfowler.com/bliki/SelfTestingCode.html", kind: "primary engineering essay"}
  - {title: "OWASP API Security Top 10 — Broken Object Level Authorization", url: "https://api-security.owasp.org/editions/2023/en/0xa1-broken-object-level-authorization/", kind: "security reference"}
  - {title: "OWASP API Security Top 10 — Broken Object Property Level Authorization", url: "https://api-security.owasp.org/editions/2023/en/0xa3-broken-object-property-level-authorization/", kind: "security reference"}
  - {title: "Python Documentation — Sorting HOWTO", url: "https://docs.python.org/3/howto/sorting.html", kind: "official language documentation"}
---
Esta avaliação utiliza um módulo sintético de consulta de tickets que contém defeitos deliberados. O objetivo não é desenhar mais uma arquitetura, mas examinar código executável, reproduzir falhas, definir contratos e justificar uma correção localizada. O capítulo de [refatoração e padrões](/pt/topics/refactoring-design-patterns/) diferencia reorganizar internamente um programa de alterar suas saídas observáveis. Essa distinção importa: **corrigir paginação, impedir exposição de campos privados e rejeitar entradas inválidas altera o comportamento antigo**. Primeiro caracterize o legado; depois implemente o novo contrato. Não apresente todo o trabalho como refatoração com comportamento preservado [1].

O repositório contém o [módulo legado](https://github.com/christianrss/manual/blob/main/examples/python/legacy_ticket_search.py), um [substituto sem implementação](https://github.com/christianrss/manual/blob/main/examples/python/refactor_ticket_search.py) e um [corretor público](https://github.com/christianrss/manual/blob/main/examples/python/ticket_search_grader.py). São materiais didáticos, com dados fictícios; não constituem um sistema pronto de controle de acesso. A nova função lança intencionalmente `NotImplementedError`, pois não há solução completa publicada.

## Caracterizar o programa antes de propor abstrações

A função antiga `legacy_search_tickets(tickets, tenant_id, status=None, offset=0, limit=10)` ordena a lista **no próprio objeto recebido**, em ordem decrescente de `created_at`; extrai a fatia definida por `offset` e `limit`; só então filtra os registros pelo cliente e pelo status; e retorna todos os campos internos. O campo `total` representa apenas a quantidade de registros que sobreviveram naquela página. A função não valida entradas. Cada um desses detalhes é observável mesmo quando a saída aparenta estar correta.

Considere quatro registros: `a1` (cliente a, aberto, instante 10), `b1` (cliente b, aberto, instante 30), `a3` (cliente a, aberto, instante 20) e `a2` (cliente a, fechado, instante 20). Consulte o cliente a com `offset=0, limit=1`. O legado ordena todos os registros, captura primeiro o ticket mais recente, que pertence ao cliente b, e **só depois o descarta**. Retorna `{"items":[],"total":0}`, embora existam três registros válidos do cliente a. O novo contrato deve retornar o primeiro deles segundo um desempate explícito.

Um teste de caracterização registra precisamente a **saída atual**, inclusive quando ela demonstra um erro. Um teste de especificação registra o **comportamento exigido** após a correção. Não altere os valores esperados nos testes do legado como se a função antiga já implementasse o contrato seguro. Fowler destaca a importância de delimitar o que se pretende preservar e de utilizar testes automáticos para detectar alterações não planejadas [1][2].

## Contrato de entrada e saída da nova função

Implemente `search_tickets(tickets, tenant_id, status=None, offset=0, limit=10)` no módulo sem solução. Retorne um dicionário com exatamente duas chaves: `items`, lista de novos registros públicos, e `total`, quantidade de correspondências **antes da paginação**.

O parâmetro `tickets` deve ser lista ou tupla de dicionários. Cada registro exige os campos `id`, `tenant_id` e `status` (strings não vazias, sensíveis a maiúsculas e minúsculas), além de `created_at` (inteiro não negativo, excluindo booleanos Python). Outros campos podem existir na entrada, mas nunca devem aparecer na resposta pública. Um mesmo ID pode ser utilizado por clientes distintos, mas deve ser único **dentro de cada cliente em toda a entrada**. Qualquer violação, mesmo num registro de outro cliente, provoca `ValueError`.

O identificador do cliente consultado deve ser uma string não vazia obtida de um **contexto confiável e previamente autenticado no servidor**. Com `status=None`, não há filtro de status; nos demais casos, o status precisa ser string não vazia. `offset` deve ser inteiro maior ou igual a zero; `limit` deve ser inteiro entre 1 e 100, inclusive. Não aceite booleanos nos parâmetros numéricos. Rejeite entradas inválidas com `ValueError` sem expor registros ou modificar os argumentos.

## Ordenação determinística e paginação após o filtro

Primeiro selecione registros pertencentes ao cliente confiável e que atendam ao status opcional. Depois ordene os resultados por `created_at` **decrescente** e, em caso de empate, por `id` **crescente**. Finalmente aplique o deslocamento e o limite sobre a lista ordenada. Conte todas as correspondências antes de cortar a página. Cada item retornado deve ter **exatamente** `id`, `status` e `created_at`: não inclua `tenant_id`, `owner_email`, `internal_note` nem outros campos armazenados.

No exemplo de quatro tickets, a ordem completa para o cliente a é `[a2,a3,a1]`, com total 3. A página inicial de tamanho 1 retorna `[a2]`; com deslocamento 1 retorna `[a3]`, mantendo total 3. Se o status for `open`, a lista é `[a3,a1]`, total 2. Um deslocamento além da última correspondência produz `items=[]`, mas o `total` continua expressando o conjunto inteiro de registros filtrados. Ordenar somente por timestamp não satisfaz o desempate: a ordenação estável do Python preserva a ordem original dos empates, que pode divergir da ordem de IDs exigida [5].

A paginação não é uma fronteira de autorização. A OWASP distingue violações de autorização ao objeto e exposição indevida de propriedades do objeto [3][4]. Por isso, a saída deve utilizar uma lista explícita de campos permitidos, não uma cópia integral do ticket interno cuja privacidade dependa da interface ocultar valores.

## Mutação, validação e responsabilidade pela autorização

A lista recebida, cada dicionário e os demais valores pertencentes ao chamador devem permanecer inalterados após **qualquer** execução, inclusive uma que lança exceção. Ordenar a entrada no próprio objeto viola a regra mesmo quando a resposta está correta. Retornar dicionários idênticos aos que o chamador forneceu também é proibido: alterar uma linha da resposta não pode modificar silenciosamente os registros armazenados em memória. O corretor verifica mutações da entrada e compartilhamento de objetos em casos representativos.

Comparar `row["tenant_id"]` com uma string **não autentica um cliente**, nem prova que o usuário tem direito de acessar a conta. Num serviço real, identidade autenticada, escopo de organização, permissões e consulta ao armazenamento precisam ser definidos em fronteiras confiáveis. Um parâmetro editável da URL não pode ser aceito como autoridade. Em sistemas persistentes, o escopo do cliente deve participar da consulta na fonte de dados, e a autorização de cada objeto e propriedade precisa ser aplicada [3][4].

A validação deve examinar todos os registros de entrada, inclusive os de outros clientes. Assim, um ID duplicado ou um registro malformado não passa despercebido somente porque não aparece na consulta corrente. Trata-se de uma decisão **intencionalmente rigorosa** para o exercício; APIs reais podem validar durante a ingestão, em vez de revisar toda a base em cada busca. Essa diferença deve ser mencionada na revisão técnica.

## Complexidade, alternativas e custo das abstrações

Se `n` representa o número de registros e `m<=n` a quantidade que corresponde ao cliente e ao status, uma validação linear seguida de ordenação das correspondências exige `O(n+m log m)` tempo no modelo de comparação e `O(n)` memória adicional. Portanto satisfaz o alvo `O(n log n)` em tempo e `O(n)` em espaço. Comparações de strings muito longas e operações sobre inteiros Python de precisão arbitrária introduzem custos adicionais; explicite o modelo antes de declarar limites assintóticos.

Num endpoint de grande volume, paginação por deslocamento pode ficar cara e instável caso os registros mudem entre solicitações. Um cursor associado a uma ordenação total poderia ser preferível, mas seria **outro contrato de API**. Não substitua silenciosamente `offset` por cursor neste exercício. Da mesma forma, uma hierarquia de Repository, Strategy, Factory ou contêiner de injeção de dependências não torna automaticamente uma função determinística mais manutenível. Extraia responsabilidades somente quando houver isolamento, reutilização ou melhoria verificável da testabilidade [1].

## Executar caracterização e verificar o contrato separadamente

A partir da raiz do repositório, execute:

~~~bash
python -m unittest tests/test_legacy_refactoring_assessment.py -v
python examples/python/ticket_search_grader.py
~~~

O primeiro comando executa testes de caracterização e de qualidade do corretor; deve passar **mesmo enquanto a nova função está sem implementação**. O segundo lança `NotImplementedError` até que você implemente a solução. Depois disso, o corretor público valida entradas válidas e inválidas, contagem, ordenação, projeção dos campos, imutabilidade e casos-limite. Os testes são visíveis, não são secretos nem supervisionados por um avaliador independente.

Antes de programar a nova função, crie testes próprios: um ticket de outro cliente com timestamp mais recente que todos os resultados; IDs duplicados num cliente **diferente do consultado**; timestamp zero; empates com IDs em ordem invertida; status inválido; offset após a última página; entrada como tupla; limite exatamente 100; e campos privados que precisam ser removidos. Modifique um item retornado e comprove que o registro-fonte permanece intacto. Testar amostras não demonstra segurança para todas as entradas possíveis.

## Revisão técnica e exercícios

1. **Rastreie a falha antiga:** por que a primeira página fica vazia quando o cliente a possui três tickets? Qual invariante foi violado? **Verificação:** o filtro deve acontecer antes da seleção da página, e total deve refletir todas as correspondências.
2. **Separe caracterização de especificação:** escreva as duas respostas do exemplo com limite 1. **Verificação:** legado sem itens e total 0; contrato novo com item a2 e total 3.
3. **Explique a fronteira de privacidade:** por que retornar todos os campos internos é incorreto mesmo com o filtro de cliente certo? **Verificação:** permissão para acessar um objeto não implica autorização sobre todas as suas propriedades [4].
4. **Projete um teste adversarial:** dois tickets têm timestamps iguais e chegam na ordem inversa de seus IDs. Qual desempate deve prevalecer? **Verificação:** ID crescente, independentemente da ordem da entrada.
5. **Avalie uma correção incompleta:** trocar `tickets.sort(...)` por `sorted(tickets,...)` evita mutação, mas mantém paginação antes do filtro e exposição de campos privados. Identifique quais testes ainda reprovariam.
6. **Avalie um serviço real:** de onde deve vir a identidade confiável do cliente, onde devem ser aplicadas as permissões por registro, e por que o exemplo em memória não comprova isolamento numa base de dados?

A entrega consiste na nova função, testes independentes, um registro sucinto das diferenças entre o legado e o contrato e a justificativa da alteração. Não transforme o módulo legado defeituoso em código de produção. O que se avalia é a capacidade de investigar, corrigir e revisar software existente, não o número de padrões de projeto empregados.
