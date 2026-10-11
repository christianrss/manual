---
id: context-free-grammars-parsing
title: "Gramáticas Livres de Contexto, Autômatos com Pilha e Análise Sintática"
description: "Fundamentos de gramáticas livres de contexto: pilha, árvores sintáticas, reconhecimento por tabela e testes independentes em Python."
category: foundations
difficulty: intermediate
updated: 2026-10-11
prerequisites: [formal-languages-finite-automata, recursion-call-stack]
sources:
  - {title: "MIT OpenCourseWare — Automata, Computability and Complexity: Lecture Notes", url: "https://ocw.mit.edu/courses/6-045j-automata-computability-and-complexity-spring-2011/pages/lecture-notes/", kind: "university lecture notes"}
  - {title: "Cornell CS 4120 — Recursive-Descent Parsing and Predictive Parsing", url: "https://www.cs.cornell.edu/courses/cs4120/2023sp/notes.html?id=topdown", kind: "university compiler notes"}
  - {title: "Cornell CS 4120 — Bottom-Up and Earley Parsing", url: "https://www.cs.cornell.edu/courses/cs4120/2023sp/notes.html?id=bottomup", kind: "university compiler notes"}
  - {title: "Jay Earley — An Efficient Context-Free Parsing Algorithm (1970)", url: "https://doi.org/10.1145/362007.362035", kind: "original peer-reviewed algorithm"}
---
O capítulo anterior de [autômatos finitos](/pt/topics/formal-languages-finite-automata/) demonstrou por que um reconhecedor de estados finitos não consegue representar contagens de correspondência arbitrariamente grandes. O próximo modelo incorpora **estruturas recursivas e memória de pilha sem limite matemático pré-definido**. É necessário separar três resultados: pertinência de uma palavra à linguagem, implementação de uma máquina com pilha e construção de uma **árvore sintática** que represente a entrada. O código inclui também um reconhecedor geral por tabela, testado independentemente, sem pretender que isso constitua um front-end completo de compilador [1][3].

## Definir a gramática antes de escrever o analisador

Uma **gramática livre de contexto** é G = (V, Sigma, P, S), formada por um conjunto finito V de não terminais, um alfabeto Sigma de terminais disjunto de V, um conjunto finito P de produções A -> alfa, em que A pertence a V e alfa é uma sequência finita de símbolos de V ou Sigma, e um símbolo inicial S de V. A sequência vazia é denominada épsilon. Numa **derivação**, substitui-se uma ocorrência de não terminal pelo lado direito de uma produção. Uma palavra pertence à linguagem L(G) quando o símbolo inicial produz exatamente seus terminais, sem não terminais restantes [1].

Para parênteses corretamente balanceados de um único tipo, utilize **S -> '(' S ')' S | épsilon**. O primeiro S descreve o interior do primeiro par; o último S descreve a sequência balanceada que aparece depois desse par. Por exemplo, `(()())` possui um par externo, interior `()()` e sufixo vazio. A gramática aceita a palavra vazia, `()`, `(())` e `()()`, mas rejeita `)(`, `(()` e `())`. A gramática é não ambígua: o fechamento correspondente à primeira abertura fixa a divisão entre interior e sufixo.

Uma **árvore de derivação** registra quais produções foram utilizadas e como os constituintes se relacionam. Já um **reconhecedor** pode simplesmente responder verdadeiro ou falso. O compilador também poderá necessitar de uma AST (*abstract syntax tree*) contendo operadores, valores, posições no arquivo e relações relevantes para fases seguintes. Uma árvore concreta pode preservar pontuação e não terminais auxiliares que uma AST elimina. Aceitar uma palavra, por si só, não atribui significado aos símbolos [2].

## Da memória finita ao autômato com pilha

Um autômato com pilha (*pushdown automaton*, PDA) acrescenta ao controle finito uma memória do tipo **último a entrar, primeiro a sair**. Em sua formulação geral, uma transição consulta o estado, um símbolo de entrada (ou épsilon) e o topo da pilha, podendo modificar o estado e empilhar ou remover símbolos. A especificação formal inclui estados, alfabeto de entrada, alfabeto de pilha, relação de transição, estado inicial, marcador inicial de pilha e condição de aceitação. Os PDAs não determinísticos caracterizam as linguagens livres de contexto; os determinísticos reconhecem uma subclasse própria [1].

No caso dos parênteses de um único tipo, existe um procedimento determinístico: empilhe um marcador para cada `(`, desempilhe ao ler `)`, rejeite se tentar remover da pilha vazia e aceite ao final apenas se nada restar. Com apenas um tipo de marcador, a **profundidade inteira** é equivalente à altura da pilha. Isso não generaliza para vários tipos de delimitador. A palavra `([)]` possui quantidades equilibradas de aberturas e fechamentos, mas o fechamento `)` tenta remover `[`, que está no topo da pilha.

A função executável `pushdown_accepts` conserva os símbolos de abertura efetivos para reconhecer palavras de `()[]`. `([][()])` é aceita. Como cada símbolo ocasiona no máximo uma operação de empilhar ou desempilhar, o custo é O(n) em tempo e O(n) em memória de pilha, no pior caso, para n símbolos sob o modelo de operação unitária por caractere. Esse procedimento **não reconhece gramáticas livres de contexto arbitrárias**: ele implementa a máquina determinística específica para colchetes e parênteses balanceados.

## Da produção gramatical à árvore por descida recursiva

A mesma gramática `S -> '(' S ')' S | épsilon` admite um analisador por descida recursiva: se o próximo caractere é `(`, escolhe-se a primeira produção; se for `)` ou fim da entrada, escolhe-se épsilon. Defina `parse_sequence(posicao)`: caso haja fechamento ou fim, devolva árvore vazia e a mesma posição; caso contrário, consuma `(`, analise recursivamente seu interior, exija o fechamento `)` e analise o sufixo posterior. A chamada inicial precisa consumir **toda a entrada**, pois um `)` remanescente não pode ser silenciosamente ignorado.

A função publicada `parse_balanced(word)` devolve `None` para épsilon e um par `(inner, tail)` para um grupo entre parênteses mais a sequência seguinte. Essa estrutura é uma **árvore real**, não apenas uma decisão de aceitação. Para `()()`, o primeiro grupo possui interior vazio e seu sufixo contém mais um grupo, também com interior vazio. Percorrer a árvore e reconstruir as aberturas, os fechamentos e os sufixos reproduz exatamente a palavra original. Essa propriedade de ida e volta não significa que toda AST semântica tenha obrigação de preservar a pontuação.

Se a entrada válida possui comprimento n, cada caractere realiza uma quantidade constante de trabalho, dando O(n) em tempo e O(n) nós na árvore para essa gramática. A implementação recursiva pode empilhar O(n) chamadas. O Python pode lançar `RecursionError` para palavras muito aninhadas ou sequências muito compridas, ainda que elas pertençam matematicamente à linguagem. Analisadores de produção podem utilizar pilhas explícitas, técnicas baseadas em tabelas ou limites de profundidade [2].

## Recursão à esquerda, escolha de alternativas e reconhecimento por tabela

Considere a gramática **S -> S a | épsilon**, que gera zero ou mais letras `a`. Uma implementação ingênua da primeira produção por descida recursiva chama novamente a função S **sem consumir nenhum símbolo**. O resultado pode ser recursão infinita. Mesmo gramáticas sem recursão à esquerda podem ter alternativas que não se decidem apenas pelo próximo token. É possível reescrever produções para análise preditiva, mas mudanças de associatividade e da forma da árvore exigem revisão. Nem toda gramática válida é LL(1) [2][3].

O reconhecedor por tabela do repositório utiliza **itens com ponto**. Um item `[A -> alfa • beta, j]`, armazenado na posição i da entrada, registra o progresso numa produção e sua posição inicial j. Existem três operações: **predição**, que insere as produções de um não terminal esperado; **leitura** (*scan*), que consome um terminal correspondente e avança à próxima coluna; e **completação**, que avança itens da coluna de origem que aguardavam o não terminal recém-concluído [3][4].

Na palavra `()` com a gramática de parênteses, a primeira coluna prevê as alternativas de S. A leitura de `(` inicia um item que espera o S interior. Como S também produz épsilon, pode terminar **sem avançar na entrada**. A completação desse S permite ler `)`; a completação final do S de sufixo vazio encerra a derivação. Se os itens não forem revisitados até um **ponto fixo**, produções vazias inseridas após uma primeira varredura poderão provocar rejeições incorretas.

## Reconhecedor finito: implementação e seus contratos

A função `earley_accepts(grammar, start, word)` mantém um conjunto de itens para cada fronteira da palavra. A gramática é um mapeamento de nomes de não terminais para listas ou tuplas de lados direitos; cada lado direito é uma sequência de símbolos. Uma sequência vazia representa épsilon. As chaves do mapeamento definem os não terminais; os outros símbolos devem ter exatamente um caractere e são interpretados como terminais. Isso é um **contrato de entrada didático**, baseado em caracteres, não um leitor de arquivos gramaticais com tokens, diagnósticos e convenções de nomenclatura.

Em cada posição, o algoritmo repete predição e completação **até que não apareçam novos itens**. Só então termina a varredura dos terminais correspondentes para a coluna seguinte. A deduplicação por conjuntos assegura terminação até para ciclos anuláveis como `S -> S | épsilon`. A aceitação exige que uma produção inicial sintética esteja completamente reconhecida na última posição, tendo começado na posição zero. Uma gramática malformada provoca `ValueError`. Uma palavra válida como string, mas não pertencente à linguagem, simplesmente produz `False`.

A **correção** possui duas partes. Na direção da ausência de falsos positivos, os itens previstos correspondem a produções existentes, cada leitura consome o terminal exigido e a completação une constituintes concluídos às produções que os aguardavam desde a origem correta. Na direção da ausência de falsos negativos, percorra uma árvore finita de derivação: seus filhos podem ser previstos, lidos ou completados recursivamente; o ponto fixo também encerra filhos anuláveis. Por indução estrutural, qualquer derivação aceita leva ao item inicial concluído. Essa argumentação justifica o reconhecimento, não a construção de todas as árvores possíveis, que não foi implementada [3][4].

## Executar os modelos e conferir resultados

O [módulo Python](https://github.com/christianrss/manual/blob/main/examples/python/context_free_parser.py) contém os três métodos e duas gramáticas representativas. Os mesmos exemplos são executados durante os testes em português e inglês:

~~~python
from examples.python.context_free_parser import (
    earley_accepts, parse_balanced, pushdown_accepts,
    BALANCED_GRAMMAR, ANBN_GRAMMAR,
)

assert earley_accepts(BALANCED_GRAMMAR, "S", "(()())")
assert not earley_accepts(BALANCED_GRAMMAR, "S", "([)]")
assert earley_accepts(ANBN_GRAMMAR, "S", "aaabbb")
assert not earley_accepts(ANBN_GRAMMAR, "S", "aabbb")
assert earley_accepts({"S": (("S", "a"), ())}, "S", "aaaa")
assert parse_balanced("()") == (None, None)
assert pushdown_accepts("([][()])")
assert not pushdown_accepts("([)]")
~~~

A segunda gramática é `S -> a S b | épsilon`, que reconhece `a^n b^n`, para n maior ou igual a zero. Cada expansão recursiva acrescenta exatamente um `a` antes e um `b` depois da derivação interior. Uma máquina de estados finitos não pode armazenar uma contagem sem limite e verificar depois sua correspondência; a recursão ou pilha fornece essa memória. A palavra `aabbb` é inválida porque as quantidades diferem, ainda que a ordem de símbolos pareça correta.

## Complexidade, ambiguidade e limites do algoritmo

Considere n como o comprimento da entrada e d como a quantidade de **posições possíveis para o ponto** nas produções, incluindo o símbolo inicial sintético. Cada coluna pode conter O((n+1)d) itens distintos, pois cada item possui uma origem entre zero e n. Nas n+1 colunas, o número total de entradas é limitado por O((n+1)^2 d). Esse é um limite de **quantidade de itens**, sem incluir o tamanho dos objetos Python, o custo de hashing de tuplas ou as estruturas da gramática.

Como o código didático percorre toda a coluna repetidamente até um ponto fixo, em vez de utilizar filas incrementais e índices eficientes de completação, **não se afirma que possua o limite clássico O(n³) de Earley**. O algoritmo original de Earley possui limite O(n³) no pior caso sob suas hipóteses de implementação, com melhores limites para certas famílias de gramáticas [4]. Seria incorreto transferir automaticamente esse resultado para a implementação simplificada. Aplicações reais precisam considerar custo de fechamento anulável, índices, floresta de análise compartilhada, ambiguidades, consumo de memória e limites de recursos.

A gramática `S -> S S | a | épsilon` é ambígua: uma mesma sequência de letras `a` pode ter várias árvores de derivação. A estrutura de itens com conjunto informa apenas se **alguma** derivação existe. Não conta árvores nem decide uma AST preferida. Uma gramática de expressões sem precedência também pode aceitar `a+a*a` e ainda não definir se a multiplicação deve ser avaliada primeiro. Um compilador precisa decidir precedência, associatividade, resolução de ambiguidades, mensagens de erro e regras semânticas. Nada disso é resolvido por um único resultado booleano [2][3].

## Exercícios e verificação

1. Derive `()()` a partir de `S -> (S)S | épsilon`. Qual produção representa o primeiro interior e qual produz o sufixo? **Verificação:** interior vazio; o sufixo produz o segundo `()`.
2. Rastreie `([)]` pela pilha. **Verificação:** o terceiro símbolo `)` encontra `[` no topo e deve rejeitar, apesar das quantidades totais equilibradas.
3. Justifique por que uma produção épsilon concluída pode avançar outro item sem consumir caractere. **Verificação:** o constituinte anulável cobre intervalo de comprimento zero.
4. Compare `S -> S a | épsilon` e `S -> a S | épsilon`. Reconhecem a mesma linguagem? **Sim**, ambas produzem `a*`, mas uma descida recursiva ingênua comporta-se de modo diferente.
5. Dê um contraexemplo para `S -> a S b | épsilon`, considerando a ordem e a quantidade. **Verificação:** `aabb` é válida; `abab` e `aab` são inválidas.
6. Separe os contratos de reconhecimento, geração de árvore sintática e checagem de tipos. Por que uma expressão sintaticamente válida ainda pode conter erro de tipo?

Os testes independentes comparam o reconhecedor com uma pilha explícita, usam remoção repetida de pares adjacentes para dois tipos de delimitadores e enumeram palavras para `a^n b^n`, recursão à esquerda e gramáticas ambíguas. Isso demonstra **concordância em casos finitos**, não prova universal nem desempenho industrial. Os próximos passos curriculares são avaliação dirigida pela sintaxe, tokenização e construção de um compilador com verificação de tipos. Computabilidade de Turing e classes de complexidade permanecem fundamentos separados.
