---
id: mutable-cells-recursive-functions
title: "Células Mutáveis, Closures Compartilhadas e Funções Recursivas Tipadas"
description: "Estenda o compilador tipado com células mutáveis, atribuições e let rec, verificando compartilhamento de memória e recursão na VM."
category: foundations
difficulty: advanced
updated: 2026-10-11
prerequisites: [typed-functions-call-frames-closures]
sources:
  - {title: "Robert Nystrom — Crafting Interpreters: Closures", url: "https://craftinginterpreters.com/closures.html", kind: "original compiler engineering textbook"}
  - {title: "Cornell CS3110 — OCaml Programming: Refs", url: "https://cs3110.github.io/textbook/chapters/mut/refs.html", kind: "university programming languages textbook"}
  - {title: "Benjamin C. Pierce — Types and Programming Languages", url: "https://mitpress.mit.edu/9780262162098/types-and-programming-languages/", kind: "academic textbook"}
  - {title: "Robert Nystrom — Crafting Interpreters: Functions", url: "https://craftinginterpreters.com/functions.html", kind: "original compiler engineering textbook"}
---
Uma closure imutável pode guardar cópias das vinculações de seu ambiente léxico. Essa abordagem deixa de ser suficiente quando uma variável capturada pode **receber outro valor**: duas closures que capturam a mesma variável mutável devem acessar **um único local de armazenamento**, e não cópias independentes do valor anterior. Este capítulo amplia o [compilador de funções e quadros de ativação](/pt/topics/typed-functions-call-frames-closures/) com células compartilhadas, atribuições, recursão tipada e bytecode que preserva referências depois do término de chamadas [1][2]. A implementação modifica o compilador existente, sem introduzir exemplos desconectados.

Os valores da linguagem continuam limitados a frações exatas, booleanos e funções de primeira classe. Não existe exposição de ponteiros brutos, controle de coleta de lixo, variáveis globais, objetos ou código nativo.

## Sintaxe, habilitação explícita e compatibilidade

Os três modos anteriores do lexer permanecem inalterados. Apenas `tokenize(source, extended=True, functions=True, stateful=True)` reconhece as novas palavras reservadas `var`, `set` e `rec`. Programas aritméticos, declarações tipadas imutáveis e chamadas de funções já publicadas continuam utilizando as mesmas interfaces sem precisar habilitar o novo modo.

Uma declaração mutável é `var x: Int = 1 in expressao`. Seu inicializador é avaliado **antes** de a nova variável x tornar-se visível, e a vinculação existe somente no corpo. A atribuição possui formato `set x = expressao`: primeiro avalia-se integralmente a expressão da direita, depois atualiza-se o x visível. Nesta linguagem didática, a atribuição **é uma expressão que retorna o valor armazenado**; isso difere do operador de atribuição de OCaml, que retorna `unit` [2]. Parênteses delimitam operações combinadas, por exemplo `(set x=x+1)+x`. A linguagem ainda não possui tipo `Unit` nem um operador geral para sequência de instruções.

A declaração recursiva restrita é `let rec f: Fn(Int)->Int = fn(n:Int)->Int=>... in expressao`. Seu inicializador precisa ser literalmente uma **função anônima anotada**. Não existem valores recursivos arbitrários, grupos mutuamente recursivos ou possibilidade de alterar f por atribuição. Essa restrição impede que um inicializador execute e consulte seu próprio valor ainda inexistente. Não se trata de avaliação de um operador de ponto fixo irrestrito.

## Células de memória, identidade e aliasing léxico

Cada declaração `var` cria uma instância nova de `Cell`, com três propriedades: valor atual, permissão de escrita e estado de inicialização. Os ambientes léxicos continuam representados por dicionários. Ao criar uma closure, os dicionários são **copiados**, mas os objetos `Cell` **não** são copiados. Ao chamar a função, os dicionários capturados são copiados outra vez, preservando as referências às mesmas células. Trata-se de *aliasing*: copiar o **mapa de variáveis** não equivale a duplicar cada **local de armazenamento** [1][2].

Considere `var x:Int=1 in let f:Fn()->Int=fn()->Int=>set x=x+1 in f()+f()`. A primeira chamada altera x de 1 para 2 e retorna 2; a segunda encontra x igual a 2, altera-o para 3 e retorna 3. O resultado final é **5**. Se o interpretador capturasse valores separados, as chamadas poderiam modificar variáveis diferentes e produziriam outro resultado. Duas closures distintas criadas no mesmo escopo mutável também compartilham a mesma célula. Já um novo `var x` que sombreia a variável anterior aloca outro local, sem sobrescrever a célula antiga.

Uma closure pode sobreviver ao quadro da função que criou a célula. Por exemplo, `fn(seed:Int)->Fn()->Int=>var x:Int=seed in fn()->Int=>set x=x+1` produz uma função que continua acessando x depois de a chamada externa terminar. O Python administra concretamente os objetos `Cell`: a demonstração envolve **alcançabilidade e tempo de vida**, não um alocador manual nem um coletor de lixo implementado pela máquina virtual. Declarações imutáveis `let` continuam guardando seus valores diretamente.

## Juízos estáticos para estado mutável e recursão

O ambiente de tipos passa a associar cada identificador visível ao par **(tipo, gravável)**. Para `let x:T=e1 in e2`, o verificador analisa e1 no ambiente recebido, exige que seu tipo seja exatamente T e analisa o corpo marcando x como **não gravável**. A regra correspondente de `var x:T=e1 in e2` preserva a exigência de tipo, mas marca a nova variável como gravável. O sombreamento mantém a disciplina lexical: existir um x externo mutável não faz com que outro x interno e imutável se torne gravável [3].

A expressão `set x=e` somente é válida se x existir, estiver marcado como gravável e a expressão e possuir **exatamente** o tipo declarado T. A própria expressão de atribuição tem tipo T. Assim, `var x:Int=1 in set x=2` é válida, mas `let x:Int=1 in set x=2`, `var x:Int=1 in set x=true` e uma atribuição fora do escopo são rejeitadas **antes da geração do bytecode**. Delegar essa verificação exclusivamente à VM contrariaria a garantia de tipagem estática da linguagem.

Para `let rec f:Fn(A)->B=fn(x:A)->B=>corpo in e2`, o verificador primeiro amplia o ambiente com f marcada como **imutável** e só então verifica a função inicializadora. O tipo inferido da função deve coincidir exatamente com o tipo declarado; o corpo introduzido por `in` é verificado no mesmo ambiente ampliado. Essa regra permite chamadas recursivas, rejeitando tipos de argumentos incorretos, retornos incompatíveis e atribuições ilegais a f. Uma declaração `let` comum continua **não recursiva** [3][4].

## Inicialização recursiva em duas etapas na máquina virtual

Na declaração `var`, a compilação avalia o inicializador, executa `ENTER`, vincula o valor com `BIND_VAR`, executa o corpo e fecha o escopo com `LEAVE`. `BIND_VAR` aloca uma `Cell` gravável. A instrução `STORE` atualiza a célula gravável visível mais próxima após avaliar seu novo valor, preservando-o na pilha de operandos como resultado da atribuição.

Uma função recursiva exige outra sequência: **`ENTER` → `DECLARE_REC f` → `CLOSURE` → `INIT_REC f` → corpo → `LEAVE`**. `DECLARE_REC` cria uma célula **não inicializada e não gravável**. `CLOSURE` captura uma referência para essa célula, ainda sem conteúdo. `INIT_REC` preenche a célula uma única vez com a função construída. Depois disso, operações recursivas `LOAD f` acessam a mesma referência e encontram a closure completa. Dessa forma, é possível construir um valor que aponta para si mesmo sem expor ao programa uma função parcialmente inicializada [1][4].

O **invariante de inicialização** é que o valor recursivo só pode ser lido depois de `INIT_REC`. A restrição sintática de inicializadores a funções anônimas impede que o programa consulte f prematuramente; a VM rejeita, adicionalmente, bytecode fabricado que tente ler a célula vazia. Embora f utilize internamente uma célula, ela não pode ser alterada por `set`. A inicialização interna não deve ser confundida com mutabilidade permitida ao usuário.

## Exemplo executável, oráculo independente e regressões

A [interface do compilador com estado](https://github.com/christianrss/manual/blob/main/examples/python/stateful_function_compiler.py) disponibiliza `parse_stateful`, `compile_stateful` e `evaluate_stateful`, aproveitando o gerador de bytecode e a VM existentes. O trecho seguinte é idêntico ao publicado no capítulo em inglês e executado nos testes.

~~~python
from fractions import Fraction
from examples.python.stateful_function_compiler import (
    compile_stateful, evaluate_stateful,
)
from examples.python.typed_function_compiler import run_functions

counter = ("var x:Int=1 in "
           "let inc:Fn()->Int=fn()->Int=>set x=x+1 in "
           "inc()+inc()")
assert evaluate_stateful(counter) == ("Int", Fraction(5))

factorial = ("let rec fact:Fn(Int)->Int="
             "fn(n:Int)->Int=>if n<2 then 1 else n*fact(n-1) "
             "in fact(5)")
assert evaluate_stateful(factorial) == ("Int", Fraction(120))
assert run_functions(compile_stateful(factorial)) == Fraction(120)

escaped = ("let make:Fn(Int)->Fn()->Int="
           "fn(seed:Int)->Fn()->Int=>var x:Int=seed in "
           "fn()->Int=>set x=x+1 in "
           "let next:Fn()->Int=make(5) in next()+next()")
assert evaluate_stateful(escaped) == ("Int", Fraction(13))
~~~

Os [testes independentes](https://github.com/christianrss/manual/blob/main/tests/test_mutable_recursion_compiler_contracts.py) implementam um **interpretador direto da AST**, com representação própria de células. Esse oráculo não executa bytecode do compilador. Casos deduzidos manualmente e cenários gerados com semente fixa verificam contadores, sombreamento, closures mutáveis que escapam, fatorial e funções recursivas de contagem. Os casos negativos incluem atribuição a imutáveis, tipos incompatíveis, declarações recursivas que não produzem funções, leitura de células não inicializadas e limites da VM. Concordância sobre casos finitos constitui evidência, não prova universal mecanizada.

## Complexidade, duração dos objetos e condições de falha

Se n é a quantidade de nós da AST, d a profundidade léxica e c a quantidade de entradas copiadas numa captura, a checagem estática visita O(n) nós; cópias repetidas de ambientes podem acrescentar até O(n d) operações. Uma captura custa O(c) na cópia dos dicionários, mantendo a **identidade das células**. Buscar uma variável pode percorrer O(d) escopos. Chamadas recursivas do programa consomem um quadro adicional da VM por chamada, embora o despacho das instruções seja feito por um laço iterativo em Python.

Os limites padrão continuam sendo **50.000 instruções despachadas** e **128 quadros simultâneos**, além das restrições de origem, tokens e profundidade sintática. São **limites didáticos**, não um sandbox robusto: uma única operação racional de precisão arbitrária pode consumir CPU ou memória consideráveis, e closures mantidas vivas podem reter várias células. Não existem atribuições atômicas, threads, modelo de memória concorrente, coletor de ciclos próprio da VM, verificador geral de bytecode ou backend de código nativo.

## Exercícios e verificação

1. Rastreie as duas chamadas em `var x:Int=1 in let f:Fn()->Int=fn()->Int=>set x=x+1 in f()+f()`. **Verificação:** a mesma célula recebe valores 2 e 3; resultado 5.
2. Substitua `var` por `let` no exemplo anterior. **Verificação:** erro estático de atribuição a variável imutável.
3. Calcule `let rec f:Fn(Int)->Int=fn(n:Int)->Int=>if n<1 then 0 else 1+f(n-1) in f(8)`. **Verificação:** resultado 8.
4. Justifique a ordem `DECLARE_REC`, `CLOSURE`, `INIT_REC`. **Verificação:** primeiro existe uma célula, a função captura essa referência e, depois, a referência recebe a própria função.
5. Faça duas closures diferentes capturarem a mesma variável `var`. **Verificação:** as duas observam alterações feitas na mesma célula.
6. Explique por que um limite de instruções não limita todos os custos de CPU e memória. **Verificação:** aritmética de precisão arbitrária e retenção de closures podem custar muito numa única instrução.

Os próximos capítulos devem formalizar **semântica de armazenamento, endereços léxicos, verificação de bytecode e análise de tempo de vida**. Nenhum desses componentes deve ser considerado implementado por esta extensão intencionalmente limitada.
