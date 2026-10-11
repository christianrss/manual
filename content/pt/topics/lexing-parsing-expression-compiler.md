---
id: lexing-parsing-expression-compiler
title: "Compilador de Expressões: Análise Léxica, AST, Bytecode e Máquina Virtual"
description: "Implemente uma linguagem aritmética: tokens ASCII, parser com precedência, AST, bytecode de pilha e avaliação racional exata."
category: foundations
difficulty: advanced
updated: 2026-10-11
prerequisites: [formal-languages-finite-automata, context-free-grammars-parsing, programming-semantics-contracts]
sources:
  - {title: "Cornell CS 4120 — Introduction to Compilers, 2026 Lecture Notes", url: "https://www.cs.cornell.edu/courses/cs4120/2026sp/notes/", kind: "university compiler course"}
  - {title: "Robert Nystrom — Crafting Interpreters: Compiling Expressions", url: "https://craftinginterpreters.com/compiling-expressions.html", kind: "original engineering textbook"}
  - {title: "Python Standard Library — fractions.Fraction", url: "https://docs.python.org/3/library/fractions.html", kind: "official language reference"}
  - {title: "Python Standard Library — ast", url: "https://docs.python.org/3/library/ast.html", kind: "official language reference"}
---
Um compilador transforma um programa escrito numa linguagem em outra representação, executável por alguma máquina. Em comparação com o capítulo de [gramáticas livres de contexto](/pt/topics/context-free-grammars-parsing/), reconhecer uma palavra não basta: a tradução deve preservar precedência, posições do código-fonte, semântica das operações e informações sobre erros. Aqui será desenvolvido um **compilador pequeno, mas completo, para expressões aritméticas**: texto de entrada, tokens, árvore sintática abstrata (AST), bytecode pós-fixo e execução numa máquina virtual de pilha [1][2]. A linguagem é intencionalmente limitada; não se trata de Python, de um compilador de propósito geral ou de um ambiente isolado para execução segura.

## Contrato da linguagem e fronteiras das etapas

A linguagem contém literais inteiros decimais **ASCII não negativos** e os operadores `+ - * /`, além de `(` e `)`. O espaço em branco admitido inclui apenas espaço ASCII, tabulação, retorno de carro e quebra de linha. Não existem nomes, variáveis, atribuições, strings, funções, valores booleanos, dígitos Unicode nem multiplicação implícita. O sinal de menos é sempre um token independente: `-12` significa um operador unário aplicado ao literal 12. A operação `/` representa **divisão racional exata**, não divisão inteira nem ponto flutuante binário do Python [3].

A gramática não ambígua pode ser descrita como `expression -> additive`; `additive -> multiplicative (('+' | '-') multiplicative)*`; `multiplicative -> unary (('*' | '/') unary)*`; `unary -> ('+' | '-') unary | primary`; e `primary -> INT | '(' expression ')'`. A repetição dos operadores aditivos e multiplicativos tem associação **à esquerda**. Os operadores unários possuem precedência maior que multiplicação e divisão. A entrada deve ser consumida integralmente até EOF: um prefixo válido seguido de símbolos extras é inválido. Uma regra vaga como `E -> E + E | E * E | INT` não define sozinha como resolver ambiguidades de precedência.

O [módulo executável](https://github.com/christianrss/manual/blob/main/examples/python/expression_compiler.py) expõe `tokenize`, `parse_expression`, `compile_expression`, `run_bytecode`, `interpret_ast` e `evaluate`. O Python é apenas a **linguagem de implementação**. O texto de entrada não é código Python: identificadores, aspas, indexação, atributos e instruções são rejeitados. Essa restrição diminui a superfície sintática, mas não significa que o programa possa processar quantidades arbitrárias de dados não confiáveis sem limites de recursos.

## Lexer: tokens, posições e falhas lexicais

O analisador léxico percorre a string caractere por caractere. Ele ignora espaços permitidos, consome sequências máximas de dígitos ASCII para construir inteiros, reconhece operadores ou parênteses de um caractere e lança `CompileError` para caracteres inesperados. Cada token registra `(kind, text, start, end)`, com intervalos de caracteres **semiabertos**; um token `EOF` é acrescentado na posição final. Para `"12 +3"`, os intervalos são `INT[0,2)`, `+[3,4)`, `INT[4,5)` e `EOF[5,5)`. As posições são índices de caracteres da string Python, não deslocamentos em bytes UTF-8. Como os tokens admitidos são ASCII, essa distinção não altera os exemplos.

**Invariante de leitura:** antes de cada iteração, o prefixo anterior ao cursor foi particionado em tokens válidos e espaços permitidos; nada posterior ao cursor foi consumido. A leitura de todos os dígitos consecutivos impede que `123` seja tratado como três inteiros separados. Um caractere inválido faz a leitura falhar na posição correspondente, em vez de ser descartado e possivelmente alterar o significado da expressão. A separação entre análise léxica e sintática é uma das bases da organização de compiladores [1].

O lexer rejeita `0x10`, `1.5`, `2_000` e dígitos não ASCII. Por outro lado, `2**3` e `2//3` contêm operadores lexicalmente válidos, mas o **parser** rejeita essas sequências por não formarem expressões válidas. Erro lexical não equivale a erro gramatical: todos os caracteres de `"1+"` são tokens válidos, mas falta o operando da soma. Separar essas etapas fornece diagnósticos mais precisos do que simplesmente passar a string ao `eval` da linguagem hospedeira.

## Parser de precedência e AST imutável

O parser implementa o método de **precedence climbing** por uma rotina `expression(minimum, depth)`. Primeiro reconhece um literal, operador unário ou expressão entre parênteses. Depois consome operadores binários enquanto a precedência for suficiente. Soma e subtração têm precedência 10; multiplicação e divisão têm 20; os prefixos, 30. Para obter associação **à esquerda**, o operando direito é analisado com precedência mínima `power + 1`. Assim, o próximo operador de mesmo nível é processado pelo laço externo, e não incorporado ao lado direito [2].

Em `10-3-2`, a AST equivale a `Binary('-', Binary('-', 10, 3), 2)`, cujo valor é 5. Se a construção fosse `10-(3-2)`, o valor seria 9. Em `1+2*3`, a multiplicação constitui uma subárvore da soma, gerando 7. Os parênteses alteram essa relação: `(1+2)*3` resulta em 9. Prefixos repetidos, como `--5`, são válidos e se compõem na ordem reconhecida.

A AST utiliza as classes de dados imutáveis `Literal`, `Unary` e `Binary`, incluindo operador e posições da origem. Os parênteses não são mantidos como nós: eles já influenciaram a estrutura. Portanto, os intervalos dos nós preservados **não formam uma árvore concreta e sem perdas**. Eles são suficientes para o exercício de avaliação, mas não permitem reconstruir automaticamente os mesmos espaços, sinais de agrupamento e formatação originais.

## Tradução da AST para instruções de pilha

A geração de bytecode percorre a árvore **após processar os operandos**. Literais produzem `PUSH n`; operadores unários geram `NEG` ou `POS`; operadores binários geram `ADD`, `SUB`, `MUL` ou `DIV`. Cada instrução também registra a posição do operador no texto para possibilitar diagnósticos. O compilador percorre a AST com uma pilha de trabalho explícita, evitando recursão na geração de código mesmo para sequências longas com associação à esquerda.

Para a expressão `8/(2+2)+-3`, ignorando as posições, o bytecode gerado é:

```text
PUSH 8
PUSH 2
PUSH 2
ADD
DIV
PUSH 3
NEG
ADD
```

A máquina virtual interpreta as instruções em sequência. `PUSH` aumenta a pilha de operandos em uma posição; `NEG` ou `POS` transforma o elemento superior sem modificar a quantidade; um operador binário retira dois valores e deposita um resultado, reduzindo a altura em um. **Invariante de pilha:** cada prefixo das instruções geradas pelo compilador possui operandos suficientes para a operação seguinte, e a expressão completa deixa exatamente um valor. O resultado é `8/4 + (-3) = -1`. Esse bytecode não é código nativo de processador: alocação de registradores, montagem, linking e emissão de executável não fazem parte do exercício [2].

## Avaliação dirigida pela sintaxe e aritmética exata

A semântica da AST pode ser dada recursivamente: `value(Literal(n)) = n`; `value(Unary(op,e)) = op(value(e))`; e `value(Binary(op,l,r)) = value(l) op value(r)`, quando a operação estiver definida. A função `interpret_ast` implementa essas regras usando uma pilha explícita para percorrer a árvore, **sem executar o bytecode compilado**. Já `run_bytecode` combina valores a partir da pilha de operandos. Comparar os dois caminhos identifica certas falhas na tradução ou na VM, embora os dois compartilhem a semântica aritmética pretendida.

Foi escolhido `fractions.Fraction` para garantir que `1/3+1/6` tenha resultado matemático exato `1/2`, sem aproximação em ponto flutuante binário [3]. O modelo simplifica a discussão sobre arredondamento IEEE 754, mas introduz outro cuidado: o número de bits dos numeradores e denominadores intermediários pode aumentar. Despachar uma instrução da VM não significa que sua operação aritmética seja de custo constante para inteiros arbitrariamente grandes.

Uma divisão por zero é erro **de execução**, não erro lexical ou sintático: `1/(2-2)` é reconhecida e compilada, mas gera `ZeroDivisionError` na avaliação. Um compilador com otimizações poderia descobrir algumas divisões por zero durante o processamento de constantes; essa otimização não está implementada. O ponto essencial é que aceitar uma expressão sintaticamente não garante que sua execução possua resultado definido.

## Exemplo executável e oráculo independente

O exemplo a seguir é idêntico ao do capítulo em inglês e é executado no processo de validação do site:

~~~python
from fractions import Fraction
from examples.python.expression_compiler import (
    tokenize, parse_expression, compile_expression,
    run_bytecode, interpret_ast, evaluate,
)

source = "8/(2+2)+-3"
assert [token.kind for token in tokenize(source)] == [
    "INT", "/", "(", "INT", "+", "INT", ")",
    "+", "-", "INT", "EOF",
]
assert [op for op, value, offset in compile_expression(source)] == [
    "PUSH", "PUSH", "PUSH", "ADD", "DIV",
    "PUSH", "NEG", "ADD",
]
assert run_bytecode(compile_expression(source)) == Fraction(-1)
assert interpret_ast(parse_expression(source)) == Fraction(-1)
assert evaluate("1/3+1/6") == Fraction(1, 2)
assert evaluate("10-3-2") == Fraction(5)
~~~

O lexer didático permite inteiros decimais com zeros iniciais, como `00012`; a gramática do Python rejeita esse literal, portanto o oráculo independente exclui deliberadamente esse caso de diferença gramatical, sem declará-lo um defeito do compilador. Os [testes independentes](https://github.com/christianrss/manual/blob/main/tests/test_expression_compiler_contracts.py) utilizam `ast.parse` do CPython e um **visitante restrito**, implementado separadamente, para obter resultados de referência. As strings de entrada nunca são entregues a `eval` ou `exec`; o oráculo interpreta apenas constantes inteiras e os operadores aritméticos autorizados [4]. Expressões geradas com semente determinística exercitam parênteses, prefixos, precedência, associatividade e divisão. A VM e o interpretador de AST precisam concordar com o oráculo nos casos definidos e reconhecer divisões por zero.

Outros casos testam posições dos tokens, mensagens de erro, cadeias aditivas extensas e o comportamento da altura da pilha. Esses testes oferecem evidência mais forte que meia dúzia de exemplos manuais, mas continuam **finitos**. A correção da tradução pode ser argumentada por indução sobre os nós: um literal deixa seu valor na pilha; o código de uma subárvore deixa seu valor; e a instrução do operador consome os operandos previstos para deixar o resultado semântico correspondente.

## Custo computacional, limites e decisões de engenharia

Para um texto de comprimento n e t tokens, a leitura léxica limitada executa O(n) operações de inspeção de caracteres e produz O(t) tokens. A análise por precedência e a construção de nós utilizam O(t) operações abstratas para esta gramática, assumindo custos unitários para as estruturas utilizadas. A geração do bytecode e o despacho das instruções também exigem O(t) operações da máquina abstrata, com O(t) memória para tokens, nós e código, além de até O(t) espaço da pilha da VM. A **complexidade em bits da aritmética racional** constitui custo adicional e depende da magnitude dos intermediários; seria incorreto declarar incondicionalmente que a execução inteira exige O(n) operações de bits.

A implementação limita a entrada a 4.096 caracteres, a lista a 2.048 tokens, cada literal a 100 dígitos e a profundidade de análise a 80. Essas são **restrições didáticas**, não um isolamento completo contra negação de serviço. Resultados racionais intermediários podem consumir muita memória e CPU; ainda é necessário considerar limites de processo, exceções e políticas de execução quando uma aplicação recebe entradas não confiáveis. A VM supõe bytecode produzido pelo compilador e rejeita opcodes desconhecidos e estouro negativo da pilha; não existe formato persistente de código com autenticação ou verificação completa.

A organização em fases permite examinar cada transformação, mas o escopo permanece reduzido: não há instruções, identificadores, tabela de símbolos, variáveis, regras estáticas de tipos, otimizações, funções, controle de fluxo, gerenciamento de memória nem backend nativo. Não seria correto anunciar essa ferramenta como linguagem geral pronta para uso. O passo seguinte consiste em introduzir **variáveis tipadas e ambiente semântico**, definindo regras de tipos antes de acrescentar operações com nomes ao bytecode [1].

## Exercícios e verificação

1. Construa a AST de `8/4/2`. **Verificação:** a associação à esquerda exige `(8/4)/2 = 1`, enquanto `8/(4/2) = 4`.
2. Gere bytecode para `-(2+3)*5/7` e acompanhe a altura da pilha. **Verificação:** `PUSH 2; PUSH 3; ADD; NEG; PUSH 5; MUL; PUSH 7; DIV` deixa apenas `-25/7`.
3. Explique por que `1+2*3` e `(1+2)*3` têm ASTs diferentes. **Verificação:** precedência e agrupamento modificam a estrutura, determinando a ordem de combinação dos valores.
4. Analise `1/(3-3)`. **Verificação:** lexer, parser e compilador aceitam; a VM gera `ZeroDivisionError`.
5. Altere uma regra de precedência e apresente um contraexemplo antes de executá-lo. **Verificação:** se `+` tiver precedência maior que `*`, `1+2*3` passa de 7 para 9.
6. Justifique por que o oráculo externo usa apenas um subconjunto de nós do AST do Python. **Verificação:** permitir a semântica completa da linguagem hospedeira ou usar `eval` introduziria chamadas, atributos e outras operações proibidas pela linguagem didática.

O capítulo estabelece uma tradução verdadeira, executável e verificável para um **domínio aritmético pequeno**. Seus testes não demonstram segurança de compiladores de produção, correção de uma linguagem com tipos ou semântica geral de programas.
