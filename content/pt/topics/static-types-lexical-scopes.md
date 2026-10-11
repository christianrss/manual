---
id: static-types-lexical-scopes
title: "Sistemas de Tipos Estáticos, Escopos Léxicos e Compilador de Expressões Tipadas"
description: "Amplie o compilador com variáveis tipadas, escopos léxicos, verificação estática, expressões condicionais e bytecode testado."
category: foundations
difficulty: advanced
updated: 2026-10-11
prerequisites: [lexing-parsing-expression-compiler, programming-semantics-contracts]
sources:
  - {title: "Benjamin C. Pierce — Types and Programming Languages", url: "https://mitpress.mit.edu/9780262162098/types-and-programming-languages/", kind: "original textbook"}
  - {title: "Cornell CS3110 — Type Checking", url: "https://cs3110.github.io/textbook/chapters/interp/typecheck.html", kind: "university teaching reference"}
  - {title: "Robert Nystrom — Crafting Interpreters: Resolving and Binding", url: "https://craftinginterpreters.com/resolving-and-binding.html", kind: "original engineering textbook"}
  - {title: "Python Standard Library — fractions.Fraction", url: "https://docs.python.org/3/library/fractions.html", kind: "official language reference"}
---
Um parser demonstra apenas que a entrada possui uma **estrutura sintática** admissível. Ele não garante que cada variável foi declarada, que os operandos têm tipos aceitos pelos operadores ou que duas alternativas condicionais sejam compatíveis. Este capítulo estende o [compilador aritmético anterior](/pt/topics/lexing-parsing-expression-compiler/) com **vinculações tipadas, escopo léxico, valores booleanos e expressões condicionais**. A implementação processa caracteres, tokens, árvore sintática abstrata (AST), regras de tipos e bytecode de uma máquina virtual de pilha. A nova condição fundamental é que **a verificação de tipos termina antes de qualquer execução** [1][2].

O resultado é uma linguagem didática de expressões, não um compilador de propósito geral. Suas regras são explícitas, as etapas são executáveis e as limitações permanecem documentadas. Em particular, mesmo um programa corretamente tipado ainda pode produzir erros dinâmicos, como divisão por zero.

## Gramática ampliada e semântica dos novos elementos

A linguagem anterior reconhecia inteiros decimais ASCII não negativos, operadores unários `+` e `-`, operadores binários `+ - * /` e parênteses. O lexer estendido aceita identificadores ASCII (letra ou sublinhado, seguidos de letras, dígitos ou sublinhados), as palavras reservadas `let`, `in`, `if`, `then`, `else`, `true`, `false`, os nomes de tipos `Int`, `Rat`, `Bool` e os sinais `:`, `=` e `<`. A função original `tokenize(source)` **mantém seu contrato anterior**; a extensão é ativada apenas com `tokenize(source, extended=True)`. Palavras reservadas não podem ser nomes de variáveis, e identificadores Unicode não fazem parte desta linguagem específica.

A gramática acrescenta `let IDENT ':' Type '=' expression 'in' expression`, `if expression 'then' expression 'else' expression`, os literais `true` e `false` e referências a identificadores. O operador binário `<` tem precedência inferior à adição e à multiplicação. Aritmética mantém associatividade à esquerda e operadores unários possuem precedência maior. Os parênteses continuam controlando o agrupamento. **Não existem instruções, laços, atribuições, referências mutáveis, funções, igualdade ou operadores booleanos de curto-circuito.**

Há três tipos estáticos. Um literal inteiro recebe tipo `Int`; um literal booleano recebe `Bool`; e uma fração exata possui tipo `Rat`. A divisão `/` retorna sempre `Rat`, inclusive quando seu resultado é matematicamente inteiro. As operações `+`, `-` e `*` retornam `Int` somente quando **ambos** os operandos são `Int`; caso contrário, retornam `Rat` quando ambos são numéricos. Sinais unários preservam o tipo numérico. A comparação `<` aceita operandos numéricos e retorna `Bool`. Nenhuma operação aritmética aceita `Bool`. Essas regras constituem uma escolha semântica própria, não uma reprodução das conversões implícitas do Python.

## Juízos de tipagem e ambiente de símbolos

Utilizamos `Gamma |- e : T` para representar “no ambiente de tipos Gamma, a expressão e possui tipo T”. Gamma é um mapeamento dos nomes visíveis aos respectivos tipos declarados. As regras são **dirigidas pela sintaxe**: o formato do nó na AST determina quais verificações devem ser realizadas [1][2].

Um literal `42` recebe `Int`; `true` recebe `Bool`. Uma referência `x` só é válida quando a **vinculação visível mais interna** de x existe em Gamma. Operadores numéricos exigem operandos numéricos e aplicam a tabela de resultados da linguagem. Assim, `1/3 + 1/6` tem tipo `Rat`, enquanto `1 < 2` tem `Bool`. As expressões `true + 1` e `-false` provocam `TypeCheckError` em compilação; nenhuma instrução correspondente chega a ser executada.

A regra de `let` é central. Para tipar `let x: T = e1 in e2`, primeiro verifique `e1` no Gamma **atual** e exija que seu tipo corresponda **exatamente** ao T anotado. Em seguida, verifique o corpo `e2` num **novo** ambiente Gamma estendido com `x:T`. O tipo da expressão completa é o tipo do corpo. Logo, `let x: Rat = 3 in x` é inválido: o inicializador é `Int`, e esta implementação **não realiza conversão implícita na declaração**. É necessário escrever `let x: Rat = 3/1 in x`. A variável recém-declarada ainda não pode ser utilizada em seu próprio inicializador; declarações recursivas não existem.

Para `if c then a else b`, a condição c precisa ter tipo `Bool`, e **ambos os ramos** precisam ter o mesmo tipo exato T. A expressão condicional também terá tipo T. Os dois ramos são verificados estaticamente mesmo quando a condição é literalmente `true` ou `false`: `if true then 1 else false` é inválida, e `if false then unknown else 2` falha porque contém um nome não declarado. Não existe subtipagem, união de tipos, inferência de variáveis de tipo nem promoção implícita entre ramos [2].

## Escopo léxico, sombreamento e isolamento de identificadores

**Escopo léxico** significa que a ligação de um nome depende da estrutura textual de aninhamento, não do contexto dinâmico de quem realiza uma chamada [3]. Considere `let x: Int = 5 in let x: Int = x+1 in x`. O inicializador do segundo x é avaliado no ambiente externo e produz 6. Dentro do corpo do segundo `let`, o nome x representa o novo valor 6. Ao encerrar esse escopo, a vinculação interna deixa de existir. Esse fenômeno é **sombreamento**, não alteração do valor externo.

Compare com `let x: Int = x+1 in x`, que deve ser rejeitada: não há variável x acessível quando o inicializador é analisado. De modo semelhante, `(let x: Int = 2 in x) + x` é inválida porque a segunda referência está **fora** da região definida pelo primeiro `let`. Uma implementação que armazenasse todas as variáveis num único dicionário global poderia aceitar incorretamente a expressão.

O verificador estático representa o ambiente como um dicionário e cria uma cópia com a nova vinculação para cada corpo de `let`. Já a VM mantém uma pilha de **quadros de ambiente em tempo de execução**. A instrução `ENTER` abre um novo quadro, `BIND x` retira o resultado do inicializador da pilha de valores e vincula x ao quadro atual, `LOAD x` procura do quadro mais interno para os externos e `LEAVE` descarta o quadro corrente, preservando o resultado da expressão na pilha de operandos. As representações estática e dinâmica são diferentes, mas descrevem a mesma regra de procura lexical.

## Preservação de tipos e limites da garantia de progresso

O princípio de **preservação** estabelece que os passos válidos da avaliação devem manter o tipo declarado. Na implementação, `Int` utiliza `Fraction` com denominador um, `Rat` também utiliza `Fraction`, e `Bool` utiliza um verdadeiro `bool` do Python. Soma, subtração e multiplicação de inteiros permanecem integrais; divisão numérica produz uma fração exata; a comparação `<` produz um booleano, que é consumido pela operação condicional. Uma declaração `let` exige estaticamente que o inicializador tenha o tipo anotado, e a busca de variável recupera um valor do tipo associado. O argumento é desenvolvido por indução estrutural sobre a AST e sobre a emissão das instruções.

A propriedade de **progresso** precisa de uma ressalva. Uma expressão bem tipada pode ser um valor, pode dar outro passo de execução ou pode atingir um **erro aritmético dinâmico definido**, particularmente divisão por zero. Não existe a promessa de que “bem tipado significa sempre terminar com sucesso”. Numa expressão `if`, apenas o ramo escolhido é executado. Por exemplo, `if false then 1/0 else 1/2` possui tipo estático `Rat` e resulta em um meio: a divisão por zero está num ramo não executado. Entretanto, **os dois ramos** precisam ser tipados antes da execução.

Não existe demonstração formal mecanizada nem verificador completo de bytecode tipado. As garantias aqui descritas são justificadas por argumentos matemáticos e testes finitos. Uma pessoa pode construir manualmente um objeto `TypedProgram` com instruções inválidas e tentar enviá-lo à VM; isso **não equivale** a executar bytecode produzido pelo compilador depois da checagem estática. As verificações defensivas da VM não formam um sandbox nem substituem uma validação integral das instruções.

## Extensão executável e fases da compilação

O [compilador tipado](https://github.com/christianrss/manual/blob/main/examples/python/typed_expression_compiler.py) reutiliza as estruturas `Literal`, `Unary` e `Binary`, a representação de tokens, as exceções e a precedência aritmética da implementação anterior. Os nós adicionais são `Name`, `Boolean`, `Let` e `If`. A função `parse_typed` constrói a AST; `typecheck` calcula seu tipo ou lança `TypeCheckError` com posição da origem; `compile_typed` executa a checagem **antes** de gerar bytecode; `evaluate_typed` devolve tipo e valor calculado.

~~~python
from fractions import Fraction
from examples.python.typed_expression_compiler import (
    evaluate_typed, parse_typed, typecheck,
    compile_typed, run_typed, TypeCheckError,
)

source = "let x: Int = 5 in let x: Int = x+1 in x"
assert typecheck(parse_typed(source)) == "Int"
assert evaluate_typed(source) == ("Int", Fraction(6))
assert run_typed(compile_typed("let r: Rat = 1/3 in r+1/6")) == Fraction(1, 2)
assert evaluate_typed("if false then 1/0 else 1/2") == (
    "Rat", Fraction(1, 2)
)
assert evaluate_typed("3<4") == ("Bool", True)
try:
    compile_typed("if true then 1 else false")
    assert False, "a mistyped branch must be rejected"
except TypeCheckError:
    pass
~~~

Na compilação de um condicional, são emitidas as instruções `JUMP_IF_FALSE` e `JUMP` com os **destinos corrigidos** após a geração dos ramos, impedindo a execução de ambos. Uma declaração `let` gera seu inicializador, abre um quadro, vincula o nome, compila o corpo e fecha o quadro. O bytecode válido produzido pelo compilador encerra com apenas um valor na pilha e todos os quadros internos fechados. Literais booleanos e comparações possuem instruções próprias; utilizar simplesmente inteiros no lugar de booleanos ocultaria uma distinção essencial para as regras estáticas.

## Testes independentes, complexidade e limitações

A [suíte de contratos](https://github.com/christianrss/manual/blob/main/tests/test_typed_expression_compiler_contracts.py) utiliza resultados deduzidos manualmente e um **avaliador direto da AST** independente da geração de bytecode e da VM. Também cria expressões determinísticas que exercitam sombreamento, cálculo, comparações e os dois resultados possíveis de condicionais. Outros testes exigem rejeição de nomes inexistentes, referências fora de escopo, declarações incompatíveis, ramos de tipos diferentes e operações numéricas sobre booleanos. Há verificações de `ENTER` e `LEAVE` e de não execução de divisões por zero em ramos descartados. Esses testes são finitos e não constituem prova de correção universal.

Considere n como quantidade de nós da AST e d como profundidade máxima de vinculações léxicas. A checagem percorre O(n) nós, mas **copiar o dicionário de ambiente** a cada `let` pode exigir O(d) por declaração, produzindo O(n d) em tempo e até O(d²) entradas de dicionários simultâneos ao longo de uma cadeia aninhada. A VM procura uma variável em até d quadros, permitindo custo de despacho de O(n d) no pior caso para n instruções. As operações aritméticas exatas ainda têm custo adicional dependente da quantidade de bits dos valores. Endereços léxicos pré-calculados, slots e ambientes persistentes poderiam diminuir esses custos [3].

O código mantém limites de comprimento de entrada, quantidade de tokens e profundidade de análise da AST. Não implementa funções, recursão de nomes, atribuição, instruções, closures, polimorfismo, inferência por restrições, conversões dinâmicas, tratamento de exceções como valores de linguagem ou geração de código de máquina. `Rat` e `Int` são armazenados fisicamente com `Fraction`; sua diferença reside nas **regras estáticas** do compilador, e não em tags distintos de valores numéricos na VM. A implementação de linguagens de produção exige mecanismos adicionais.

## Exercícios e verificação

1. Determine o resultado de `let x: Int = 4 in let x: Int = x*2 in x`. **Verificação:** o inicializador interno enxerga o x externo; tipo `Int`, valor 8.
2. `let r: Rat = 5 in r` é válido? **Não**: o inicializador tem tipo `Int`. Utilize `5/1` para produzir `Rat`.
3. Dê um contraexemplo à ideia de verificar somente o ramo escolhido quando a condição é constante. **Verificação:** `if true then 1 else false` deve falhar estaticamente mesmo que o segundo ramo nunca seja executado.
4. Rastreie `ENTER`, `BIND`, `LOAD` e `LEAVE` num `let` aninhado com sombreamento. **Verificação:** fechar o quadro interno restaura a visibilidade do vínculo externo; fora de ambos, o nome não existe.
5. Derive o tipo de `let x: Int = 2 in if x<3 then x/2 else x/4`. **Verificação:** condição `Bool`, dois ramos `Rat`, resultado `Rat`.
6. Explique por que uma expressão bem tipada pode lançar `ZeroDivisionError`, distinguindo erro dinâmico definido de uma garantia de término bem-sucedido.

Uma continuação natural é introduzir **armazenamento atribuível e funções com parâmetros e retorno tipados**, seguido por endereçamento léxico, formato de bytecode verificável e testes de integração mais profundos. Esses mecanismos ainda não foram implementados.
