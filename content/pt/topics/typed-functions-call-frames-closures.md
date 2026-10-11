---
id: typed-functions-call-frames-closures
title: "Funções Tipadas, Closures Léxicas e Quadros de Chamada da Máquina Virtual"
description: "Compile funções tipadas, closures e chamadas de ordem superior com quadros de ativação explícitos e testes independentes de execução."
category: foundations
difficulty: advanced
updated: 2026-10-11
prerequisites: [static-types-lexical-scopes]
sources:
  - {title: "Robert Nystrom — Crafting Interpreters: Functions", url: "https://craftinginterpreters.com/functions.html", kind: "original engineering textbook"}
  - {title: "Robert Nystrom — Crafting Interpreters: Closures", url: "https://craftinginterpreters.com/closures.html", kind: "original engineering textbook"}
  - {title: "Robert Nystrom — Crafting Interpreters: Resolving and Binding", url: "https://craftinginterpreters.com/resolving-and-binding.html", kind: "original engineering textbook"}
  - {title: "Benjamin C. Pierce — Types and Programming Languages", url: "https://mitpress.mit.edu/9780262162098/types-and-programming-languages/", kind: "original academic textbook"}
---
A compreensão de variáveis locais fica incompleta quando uma função não consegue **acessar essas variáveis depois que o escopo em que foi criada termina**. O capítulo anterior de [tipos estáticos e escopos léxicos](/pt/topics/static-types-lexical-scopes/) implementou vinculações imutáveis e condicionais tipados, mas ainda não possuía valores invocáveis. Este capítulo acrescenta funções anônimas de primeira classe, parâmetros e retornos tipados, captura léxica, chamadas de ordem superior e uma **pilha explícita de quadros de ativação da máquina virtual**. A implementação e seu oráculo independente são executáveis; isso não implica que exista um compilador geral, uma linguagem recursiva ou bytecode formalmente verificado [1][2].

## Sintaxe e contratos da extensão

A linguagem continua admitindo literais inteiros ASCII, aritmética racional exata, `Int`, `Rat`, `Bool`, `let`, `if` e sombreamento léxico. O modo de funções introduz `fn`, o construtor de tipo `Fn`, a vírgula e duas setas diferentes: `->` indica o tipo de retorno e `=>` introduz o corpo. Os modos anteriores do lexer, tanto aritmético quanto tipado, preservam seus contratos; apenas `tokenize(source, extended=True, functions=True)` habilita os novos símbolos.

A função anônima `fn(x: Int, y: Int) -> Int => x+y` recebe dois inteiros e devolve um inteiro. Seu tipo é `Fn(Int,Int)->Int`: uma lista **ordenada** de tipos dos argumentos, seguida pelo tipo resultante. Funções sem parâmetros também são válidas: `fn()->Int=>3` tem tipo `Fn()->Int`. Tipos de função podem aparecer dentro de outros tipos de função, permitindo `Fn(Int)->Fn(Int)->Int`, por exemplo. Todas as anotações de parâmetros, retorno e `let` são **explícitas**. Não há conversão implícita, sobrecarga, valores padrão de parâmetros, atribuição ou declaração recursiva.

A chamada tem a forma `funcao(arg1,arg2)`. Sua precedência é maior que multiplicação e adição, e os argumentos são avaliados **da esquerda para a direita**. Para invocar uma função anônima imediatamente, utilize agrupamento: `(fn(x:Int)->Int=>x+1)(3)`. O corpo de uma função sem esse agrupamento pode consumir uma expressão maior até alcançar seu delimitador gramatical; os parênteses removem essa ambiguidade. Listas de argumentos malformadas ou símbolos desconhecidos produzem erros sintáticos, sem tentativa de inferir uma intenção diferente.

## Regras de tipos para definições e aplicações

O ambiente Gamma associa cada identificador visível ao seu tipo. Para uma função com parâmetros de tipos T1 até Tk e anotação de retorno U, analise seu corpo no ambiente Gamma estendido pelos k parâmetros. **Somente quando** o corpo possui exatamente o tipo U, a expressão que define a função recebe tipo `Fn(T1,...,Tk)->U`. Nomes duplicados na lista de parâmetros são rejeitados ainda durante a análise sintática. Essas premissas formam a regra de introdução de tipos de função [4].

A regra de aplicação exige que a expressão invocada tenha tipo `Fn(T1,...,Tk)->U` e que cada argumento tenha exatamente o respectivo tipo Ti. A chamada inteira terá tipo U. A quantidade de argumentos precisa coincidir, inclusive quando k=0. Tentar executar `1(2)` é um erro estático; `f(true)` é inválido quando f espera `Int`; e `fn(x:Int)->Bool=>x+1` é rejeitada porque seu corpo possui tipo `Int`, incompatível com a anotação `Bool`.

As regras anteriores continuam valendo dentro das funções. `+` exige valores numéricos; divisão produz `Rat`; `<` produz `Bool`; os dois ramos de `if` precisam ter o mesmo tipo. Também permanece a exigência de que uma variável introduzida por `let` **não esteja disponível no próprio inicializador**. Consequentemente, `let f: Fn(Int)->Int = fn(x:Int)->Int=>f(x) in f(1)` é inválida: esta linguagem possui `let` não recursivo, não `let rec`. Introduzir recursão e grupos mutuamente recursivos exige uma disciplina específica de vinculação e uma análise cuidadosa de limites de execução.

## Captura léxica em oposição à busca dinâmica

Considere a expressão `let x:Int=10 in let f:Fn(Int)->Int=fn(y:Int)->Int=>x+y in let x:Int=99 in f(2)`. A função é definida enquanto x vale 10. Portanto, deve retornar **12**, e não 101, apesar de o chamador criar outra variável x com valor 99. A busca léxica segue o **aninhamento textual existente no momento da definição**, e não a pilha de chamadas do momento da execução [2][3]. O valor da função precisa combinar código executável e um ambiente de vinculações acessíveis: essa combinação é denominada **closure**.

Um exemplo ainda mais decisivo devolve uma closure como resultado de outra função: `fn(x:Int)->Fn()->Int=>fn()->Int=>x`. A função interna continua enxergando x depois que a chamada externa terminou e seu quadro de ativação foi descartado. A implementação registra **cópias dos dicionários de escopo imutáveis visíveis** quando a instrução `CLOSURE` é executada. Isso é suficiente porque não há atribuição: valores inteiros, booleanos e funções já vinculados não são alterados por futuras declarações que apenas sombreiam nomes.

Em uma linguagem com variáveis mutáveis capturadas, seria necessária outra representação, por exemplo células compartilhadas ou *upvalues*. Copiar os dicionários de vínculos imutáveis **não reproduz** a semântica de captura por referência quando existe atribuição. Essa diferença é fundamental: uma implementação correta para closures que apenas leem variáveis pode se tornar incorreta quando o aluno acrescentar comandos de alteração de estado [2].

## Geração de bytecode e quadros de ativação

Depois da análise sintática e da checagem estática, `compile_functions` traduz cada corpo para um objeto `Code` imutável contendo nomes ordenados de parâmetros e instruções. Uma função anônima produz a instrução `CLOSURE` acompanhada desse objeto. Uma chamada produz primeiro o código que calcula a função, depois o código de cada argumento em ordem e finalmente `CALL k`. O corpo de cada função e o programa principal terminam em `RETURN`. As instruções anteriores de aritmética, condicionais e variáveis continuam com a mesma semântica.

Em tempo de execução, cada **quadro de ativação** possui bytecode próprio, ponteiro de instrução, pilha de operandos e quadros de ambiente léxico. Uma instrução `CALL` retira da pilha do chamador o valor da função e os k argumentos; ela cria outro quadro, composto pelos escopos capturados e um escopo de parâmetros que associa nomes aos argumentos recebidos. O quadro do chamador permanece na pilha de chamadas, preservando a próxima instrução e quaisquer resultados intermediários. A função chamada executa até `RETURN`, quando retira exatamente um resultado de sua pilha e o entrega à pilha do chamador [1].

O **invariante da pilha** estabelece que o bytecode compilado fornece k argumentos sobre um valor de função antes de `CALL`, e que cada corpo termina com exatamente um resultado, depois de fechar todos os escopos locais abertos por `let`. Quadros diferentes possuem pilhas de operandos diferentes; por isso uma função interna não pode consumir acidentalmente os temporários do chamador. A VM utiliza uma **lista explícita de quadros em Python**, sem recorrer a chamadas recursivas do Python para executar as instruções de função. Isso distingue claramente a pilha da linguagem implementada da pilha da linguagem hospedeira.

## Exemplo completo com funções de ordem superior

Uma função pode receber outra função e devolver uma função. Por exemplo, `fn(f:Fn(Int)->Int,n:Int)->Int=>f(f(n))` recebe uma transformação de inteiro em inteiro e a aplica duas vezes. Seu tipo é `Fn(Fn(Int)->Int,Int)->Int`. A linguagem não precisa de uma sintaxe especial para callbacks: a expressão chamada é avaliada normalmente até produzir um valor de função.

A função currificada `fn(x:Int)->Fn(Int)->Int=>fn(y:Int)->Int=>x+y` devolve uma closure do tipo `Fn(Int)->Int`. Invocá-la com 3 produz uma função que acrescenta 3 a seu argumento; invocar esta segunda função com 4 produz 7. O x pertence ao ambiente capturado da primeira chamada; y pertence ao quadro criado na segunda chamada. O compilador gera um objeto `Code` para cada corpo de lambda, mas cada **execução** de `CLOSURE` pode produzir um valor de função distinto, com capturas distintas [2].

~~~python
from fractions import Fraction
from examples.python.typed_function_compiler import (
    compile_functions, run_functions, evaluate_functions, format_type,
    TypeCheckError,
)

scope = ("let x:Int=10 in "
         "let f:Fn(Int)->Int=fn(y:Int)->Int=>x+y in "
         "let x:Int=99 in f(2)")
typ, result = evaluate_functions(scope)
assert format_type(typ) == "Int" and result == Fraction(12)

higher = ("let make:Fn(Int)->Fn(Int)->Int="
          "fn(x:Int)->Fn(Int)->Int=>fn(y:Int)->Int=>x+y in "
          "let plus3:Fn(Int)->Int=make(3) in plus3(4)")
assert run_functions(compile_functions(higher)) == Fraction(7)

twice = ("let twice:Fn(Fn(Int)->Int,Int)->Int="
         "fn(f:Fn(Int)->Int,n:Int)->Int=>f(f(n)) in "
         "let inc:Fn(Int)->Int=fn(x:Int)->Int=>x+1 in twice(inc,4)")
assert evaluate_functions(twice)[1] == Fraction(6)

try:
    compile_functions("fn(x:Int)->Bool=>x+1")
    assert False
except TypeCheckError:
    pass
~~~

Este código é executado nos dois idiomas usando o [compilador de funções tipadas](https://github.com/christianrss/manual/blob/main/examples/python/typed_function_compiler.py). Não se trata de pseudocódigo: a transformação e a execução são reais, embora limitadas. Nem o compilador nem o oráculo executam strings fornecidas pelo aluno por meio de `eval` ou `exec`.

## Oráculo independente, custos e restrições de execução

Os [testes de contratos](https://github.com/christianrss/manual/blob/main/tests/test_typed_function_compiler_contracts.py) também avaliam a AST com um **interpretador direto escrito separadamente**, cujo modelo de ambiente armazena sequências de mapas imutáveis capturados. Esse oráculo não gera bytecode, não cria quadros da VM nem reutiliza seu despachante de instruções. Casos derivados manualmente abrangem escopo léxico e dinâmico, closures retornadas por funções, chamadas de ordem superior, sombreamento e resultados racionais exatos. Casos gerados com semente variam valores capturados e argumentos; os testes negativos verificam nomes inexistentes, parâmetros duplicados, retorno incompatível, aridade incorreta e tentativas de chamar valores não funcionais. São verificações **finitas**, não uma prova formal mecanizada.

Se n representa a quantidade de nós da AST, d a profundidade de vinculações léxicas e s a quantidade de entradas copiadas ao criar uma closure, a checagem de tipos pode exigir O(n d) operações quando copia o ambiente em expressões muito aninhadas. A instrução `LOAD` pode consultar até O(d) escopos. Criar uma closure copia O(s) vínculos, e invocá-la copia os escopos capturados e acrescenta um quadro de parâmetros. A implementação privilegia semântica clara em detrimento de memória e velocidade; endereços léxicos pré-resolvidos e ambientes persistentes reduziriam partes desses custos [3]. Operações com números racionais exatos também dependem da quantidade de bits dos operandos.

Por padrão, a VM limita a execução a **50.000 instruções despachadas** e 128 quadros simultâneos, além dos limites anteriores de comprimento de entrada, tokens e profundidade sintática. São restrições didáticas, **não um sandbox de segurança** nem isolamento completo contra consumo excessivo de CPU e memória. Valores racionais intermediários podem crescer bastante mesmo dentro do limite de instruções. Não há `let rec`, laços, atribuições, entrada/saída, exceções como valores da linguagem, threads, capturas mutáveis, otimização geral ou código de máquina nativo. A VM não promete tipagem segura para bytecode fabricado manualmente; a checagem estática se aplica aos programas produzidos pelo compilador.

## Exercícios e verificação

1. Substitua o x do chamador no exemplo de escopo por 1.000. **Verificação:** o resultado continua 12, pois a closure foi criada no escopo em que x valia 10.
2. Determine o tipo de `fn(x:Int)->Rat=>x/2`. **Verificação:** `Fn(Int)->Rat`; chamada com 3 retorna exatamente `3/2`.
3. Avalie `let f:Fn()->Int=fn()->Int=>11 in f()`. **Verificação:** a aridade é zero; `Fn()->Int` é distinto de `Fn(Int)->Int`.
4. Crie uma função anotada para devolver `Bool`, mas cujo corpo devolva um inteiro. **Verificação:** a definição precisa ser rejeitada mesmo que a função nunca seja invocada.
5. Rastreie a pilha do chamador, os parâmetros e os retornos em `f(f(3))`. **Verificação:** o retorno interno restabelece o quadro do chamador sem compartilhar suas variáveis locais.
6. Explique por que copiar ambientes imutáveis capturados funciona nesta linguagem, mas não basta para uma linguagem que permita atribuições. **Verificação:** valores mutáveis capturados exigiriam células compartilhadas ou modelo equivalente.

Os próximos componentes — estado mutável, declarações recursivas, bytecode verificável, endereçamento léxico, representação de memória e geração nativa — permanecem fora do escopo. Devem ser desenvolvidos com pré-requisitos e testes próprios, sem serem considerados cobertos por este interpretador restrito.
