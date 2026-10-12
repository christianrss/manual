---
id: error-handling-contracts-resource-cleanup
title: "Tratamento de erros: contratos de exceções e liberação de recursos"
description: "Diferencie falhas de domínio e defeitos do chamador, preserve causas e gerencie a duração dos recursos."
category: engineering
difficulty: foundational
updated: 2026-10-12
prerequisites: [programming-semantics-contracts, modular-programming-interfaces]
sources:
  - {title: "Python tutorial — Errors and exceptions", url: "https://docs.python.org/3/tutorial/errors.html", kind: "official Python tutorial"}
  - {title: "Python standard library — contextlib", url: "https://docs.python.org/3/library/contextlib.html", kind: "official Python documentation"}
  - {title: "Python language reference — The with statement", url: "https://docs.python.org/3/reference/compound_stmts.html#the-with-statement", kind: "official language reference"}
  - {title: "Python standard library — Built-in exceptions", url: "https://docs.python.org/3/library/exceptions.html", kind: "official Python documentation"}
---
Programas corretos não apenas devolvem resultados para entradas válidas. Também definem o comportamento diante de texto malformado, recurso indisponível e uso incorreto de uma interface. Converter qualquer falha em zero ou ignorá-la inteiramente torna o sucesso indistinguível do erro. Tratamento de falhas precisa ser projetado junto com o contrato normal de uma função [1][4].

## Erros de domínio e defeitos de programação

Um contrato define tipos e intervalos aceitos, efeitos colaterais, retornos corretos e falhas previstas. Fornecer uma lista quando a função exige string representa tipo de argumento incorreto. Fornecer string que não pode ser interpretada como temperatura representa entrada inválida do domínio. Podemos sinalizar o primeiro caso com TypeError e o segundo com subclasse própria de ValueError.

A diferença importa porque o chamador pode tomar decisões distintas. Dados inválidos podem ser rejeitados e comunicados à origem. Defeito de programação indica que uma interface interna foi utilizada incorretamente e normalmente exige reparação do código. Nenhum dos dois pode se confundir com temperatura legítima igual a zero.

Exceções não são o único mecanismo possível: outras linguagens podem utilizar resultados explícitos ou tipos algébricos. O requisito fundamental é separar precisamente operação aceita de operação rejeitada, incluindo regra sobre estado pertencente ao chamador.

## Capture exceções nas fronteiras relevantes

Capture uma exceção quando existir recuperação justificável ou contexto adicional útil. Por exemplo, converter texto de temperatura em inteiro pode produzir ValueError. O parser pode traduzi-la em ReadingError e preservar a causa original pelo encadeamento explícito de exceções. O agregador pode acrescentar a informação de qual linha estava inválida [1][4].

Capturar indiscriminadamente toda exceção e devolver valor padrão inventado esconde defeitos. Substituir uma falha por mensagem genérica sem preservar a origem também elimina evidência. Tracebacks são mais úteis quando mantêm a causa de baixo nível e explicam a operação de maior nível que falhou.

Uma função incapaz de recuperar pode corretamente propagar a exceção. Repetição automática nem sempre ajuda: texto numérico malformado geralmente continuará malformado, enquanto indisponibilidade transitória de recurso pode justificar política própria de repetição com limites.

## Exemplo: registros numéricos com limites

Considere linhas no formato STATION,CENTIDEGREES. Os identificadores de estação possuem de duas a oito letras maiúsculas ASCII, e o valor inteiro com sinal precisa estar em [-4000,8500]. Espaços externos são aceitos, mas o registro precisa conter exatamente dois campos separados por vírgula. Os valores representam centésimos de grau, evitando misturar arredondamentos de ponto flutuante ao estudo de exceções.

O parser valida a estrutura textual e devolve a estação e o valor inteiro. Um agregador separado consome um iterável finito, calcula totais por estação e devolve dicionário novo. Nenhum componente modifica as strings fornecidas. O agregador acrescenta número do registro ao encontrar erro de domínio.

O exemplo também incluirá verificações independentes de limites permitidos, texto não numérico, tipos inadequados e campos ausentes. Não inventa medições faltantes nem tenta deduzir uma estação a partir de identificador inválido.

## Demonstre a propriedade de segurança diante de erros

Após processar i registros aceitos, o dicionário local de totais contém a soma dos valores de cada estação exatamente nesses primeiros i registros. Esse é o invariante do laço. Inicialmente o mapeamento está vazio, e acrescentar a próxima medição válida preserva a afirmação. Ao terminar normalmente, o dicionário retornado satisfaz a pós-condição para toda a entrada.

Se o registro i estiver inválido, a função lança exceção sem devolver o dicionário local parcialmente construído. O chamador não recebe resumo incompleto. Essa é garantia observável de segurança diante de exceções, mas não constitui mecanismo geral de rollback: um gerador pode alterar variáveis globais ou enviar requisições enquanto fornece valores. O agregador não consegue desfazer esses efeitos.

O contrato mais forte que se pode afirmar é que a função não publica resultado parcial e não modifica os registros textuais fornecidos. Garantias maiores exigem controle sobre a fonte de dados e os recursos externos envolvidos.

## Limpeza e context managers

A liberação de recursos é preocupação independente. Arquivo, stream ou lock precisa de política explícita de aquisição e liberação. O comando with de Python invoca o comportamento de saída ao terminar o bloco normalmente ou por propagação de exceção [2][3]. Um stream em memória que pode ser fechado demonstra isso de maneira reproduzível: após sair do bloco, o atributo closed será verdadeiro mesmo se o parsing falhar.

Entretanto, fechar arquivo não desfaz bytes gravados anteriormente, e liberar lock não reverte mutações realizadas enquanto estava protegido. A existência de um bloco with não garante uma transação. Um context manager específico pode implementar rollback, mas isso precisa fazer parte do seu contrato documentado.

Um bloco finally também pode executar limpeza independentemente de retorno normal ou falha. A própria limpeza pode falhar, e fechar um arquivo com sucesso não significa necessariamente persistência após falta de energia. Liberação de recurso e durabilidade diante de falha física são propriedades diferentes.

## Observabilidade, testes e custos

Testes devem confirmar classes de exceção esperadas, contexto causal, preservação do estado do chamador e fechamento correto do recurso. Evite depender da redação exata de mensagens destinadas a pessoas, exceto quando for contrato explícito. Registre falhas inesperadas numa fronteira apropriada, sem repetir dados brutos possivelmente sensíveis por várias camadas.

Se n registros possuem L caracteres totais e k estações distintas, o parsing demanda tempo proporcional a L, atualizações no dicionário custam O(n) esperado e ordenação das chaves custa O(k log k). O tempo esperado é O(L+n+k log k), com O(k) de espaço no resultado. Não é limite incondicional no pior caso de hashing, e um iterável infinito não fornece resultado final.

Entre os contraexemplos estão devolver zero para dado malformado, ignorar exceções, expor totais parciais e pressupor que context manager desfaz escritas. Cada situação viola garantia diferente do contrato.

## Exercícios e verificação

1. Diferencie TypeError causado por argumento não textual de conteúdo numérico malformado.
2. Teste os limites extremos de temperatura e rejeite um valor fora de cada extremidade.
3. Prove que falha no terceiro registro não resulta em dicionário parcial retornado.
4. Confirme fechamento do stream quando uma exceção deixa o comando with.
5. Descreva efeitos colaterais de gerador que este algoritmo não consegue reverter.
6. Explique por que limpeza de recursos, rollback lógico e durabilidade física precisam ser analisados separadamente.

Continue com [semântica de programação](/pt/topics/programming-semantics-contracts/), [arquivos JSON seguros](/pt/topics/file-io-json-schema-safe-updates/) e [contratos de teste](/pt/topics/testing-maintainability/).
