---
id: digital-logic-gates-binary-adders
title: "Lógica digital: portas booleanas, tabelas-verdade e somadores binários"
description: "Derive AND, OR, NOT e XOR por tabelas-verdade e construa meios-somadores, somadores completos e soma de largura fixa."
category: computer-architecture
difficulty: foundational
updated: 2026-10-12
prerequisites: [data-types-bytes-and-representation]
sources:
  - {title: "Nand2Tetris — Course, hardware construction", url: "https://www.nand2tetris.org/course", kind: "open educational course"}
  - {title: "MIT OpenCourseWare — Computation Structures", url: "https://ocw.mit.edu/courses/6-004-computation-structures-spring-2017/", kind: "university course"}
  - {title: "Python Language Reference — Binary bitwise operations", url: "https://docs.python.org/3/reference/expressions.html#binary-bitwise-operations", kind: "official language reference"}
---
Programas são executados por hardware que manipula sinais elétricos, mas compreender a CPU começa com uma abstração matemática menor: **sinais digitais representados por 0 ou 1 e funções que transformam bits de entrada em bits de saída**. Essa base explica como cálculos e decisões podem surgir de componentes simples. Ainda não exige projetar transistores, processos de fabricação nem um processador completo [1][2].

## Dos sinais físicos aos valores lógicos

Um circuito digital trabalha com tensões físicas e temporização. Num nível escolhido de abstração, entradas e saídas são interpretadas como valores binários. Um 1 lógico não significa que todos os fios de todos os computadores utilizam a mesma tensão: níveis elétricos e margens de ruído variam conforme a implementação. Neste capítulo, pressupomos entradas binárias estáveis, portas ideais e ausência de atrasos de propagação. O modelo basta para demonstrar tabelas-verdade, mas não para prever comportamento elétrico real.

Um **circuito combinacional** calcula suas saídas usando apenas entradas atuais, sem lembrar um estado anterior. Um circuito sequencial possui estado e deve ser estudado em seguida. Duas entradas distintas podem produzir a mesma saída: circuito representa uma função, não necessariamente uma função inversível. Precisamos declarar domínio, saídas possíveis e regra de combinação antes de utilizar nomes de portas.

## Tabelas-verdade definem os operadores

Tabela-verdade enumera todas as entradas binárias possíveis e suas saídas. Com duas entradas independentes a e b, existem quatro combinações. AND produz 1 somente quando ambas são 1. OR produz 1 quando pelo menos uma é 1. XOR produz 1 quando exatamente uma é 1. NOT recebe uma única entrada e a inverte [1].

| a | b | AND | OR | XOR |
|---|---|---|---|---|
| 0 | 0 | 0 | 0 | 0 |
| 0 | 1 | 0 | 1 | 1 |
| 1 | 0 | 0 | 1 | 1 |
| 1 | 1 | 1 | 1 | 0 |

A tabela-verdade é mais rigorosa que uma analogia informal. Ela especifica o operador para **cada entrada válida** e permite testar exaustivamente implementações. NAND corresponde a NOT(AND(a,b)); NOR corresponde a NOT(OR(a,b)). NAND e NOR são portas universais: com cópias de uma delas é possível construir funções booleanas finitas arbitrárias, embora circuitos práticos misturem tipos de portas conforme as necessidades [1][2].

## Identidades booleanas e simplificação

Álgebra booleana possui identidades para reorganizar portas. AND com 1 preserva a; OR com 0 preserva a. Dupla negação devolve a. A distributividade estabelece a AND (b OR c) igual a (a AND b) OR (a AND c). As leis de De Morgan dizem que NOT(a AND b) equivale a (NOT a) OR (NOT b), e NOT(a OR b) equivale a (NOT a) AND (NOT b).

Essas igualdades envolvem valores booleanos, não garantem que as duas implementações físicas tenham velocidade ou consumo iguais. Uma expressão pode exigir mais portas ou mais níveis de propagação. Verifique cada simplificação com as oito combinações de três entradas antes de comparar custos físicos. Identidades booleanas reaparecem em condições de programas, permissões e predicados SQL, mas esses contextos podem incluir valores extras ou efeitos colaterais que tornam incorretas certas substituições ingênuas.

## Somar bits exige soma e transporte

Uma única saída não representa todos os resultados de somar dois bits: 1+1=2, escrito como 10 em binário. O **meio-somador** (*half-adder*) devolve bit de soma s e bit de transporte c. As equações são s = a XOR b e c = a AND b. Pela tabela-verdade, 0+0 resulta (0,0); 0+1 e 1+0 produzem (1,0); 1+1 produz (0,1).

Um **somador completo** (*full-adder*) também recebe o transporte da posição menos significativa. Primeiro soma a e b, gerando soma temporária p e transporte c1. Depois soma p e carry_in, gerando s e c2. O transporte final é c1 OR c2. A construção é correta porque a+b+carry_in = s + 2×carry_out para todas as triplas possíveis. Existem somente oito combinações, permitindo verificação exaustiva [1][2].

## Construa o somador de largura fixa

Para somar inteiros sem sinal de w bits, percorra posições da menos significativa à mais significativa. Cada somador completo recebe os bits dos operandos e o transporte anterior. O bit de resultado permanece naquela posição; o transporte avança à próxima. O transporte inicial é zero. Se restar transporte após a posição mais significativa, houve overflow sem sinal além da representação de w bits.

Com w=4, o número 5 é 0101 e o número 3 é 0011. A soma 8 é 1000, sem transporte externo. Já 15+1 produz 10000: os quatro bits retidos são 0000 e carry_out=1. Os bits armazenados correspondem a adição módulo 2^w, não à afirmação de que 15+1 vale matematicamente zero.

~~~python
def bit(value):
    if type(value) is not int or value not in (0, 1):
        raise ValueError("expected binary digit 0 or 1")
    return value

def gate_not(a):
    return 1 - bit(a)

def gate_and(a, b):
    return bit(a) & bit(b)

def gate_or(a, b):
    return bit(a) | bit(b)

def gate_xor(a, b):
    return bit(a) ^ bit(b)

def half_adder(a, b):
    return gate_xor(a, b), gate_and(a, b)

def full_adder(a, b, carry_in):
    partial, carry_a = half_adder(a, b)
    result, carry_b = half_adder(partial, carry_in)
    return result, gate_or(carry_a, carry_b)

def add_fixed_width(a, b, width):
    if (type(width) is not int or width <= 0
            or type(a) is not int or type(b) is not int
            or a < 0 or b < 0 or a >= 2 ** width or b >= 2 ** width):
        raise ValueError("invalid unsigned operands or width")
    result = 0
    carry = 0
    for position in range(width):
        digit, carry = full_adder((a >> position) & 1,
                                  (b >> position) & 1, carry)
        result |= digit << position
    return result, carry

assert half_adder(1, 1) == (0, 1)
assert full_adder(1, 1, 1) == (1, 1)
assert add_fixed_width(5, 3, 4) == (8, 0)
assert add_fixed_width(15, 1, 4) == (0, 1)
assert add_fixed_width(7, 9, 4) == (0, 1)
try:
    half_adder(1, 2)
except ValueError:
    pass
else:
    raise AssertionError("nonbinary input accepted")
~~~

## Demonstração, hipóteses e complexidade

Para cada posição i processada, mantenha o invariante: os i bits inferiores do resultado coincidem com os i bits inferiores de a+b, e carry representa o transporte dos bits inferiores à posição i. A identidade do somador completo determina o próximo bit e transporte. Inicialmente i=0, nenhum bit foi processado e carry=0. Após processar w posições, o resultado representa (a+b) módulo 2^w e o transporte externo vale 1 exatamente quando a soma sem sinal é pelo menos 2^w.

O algoritmo faz w iterações e número constante de operações de porta por iteração: O(w) tempo no modelo de custo unitário por porta e O(1) variáveis escalares auxiliares quando o resultado é tratado como registrador de largura fixa. Em Python, o inteiro e os operandos podem ocupar O(w) bits e operações sobre inteiros de precisão arbitrária não custam sempre tempo constante; o código modela um **circuito lógico idealizado**, não serve de benchmark do Python [3].

O transporte se propaga das posições inferiores às superiores, então a profundidade lógica de um somador ripple-carry cresce linearmente com sua largura. Outras topologias reduzem o atraso de transporte com mais lógica, trocando área e consumo. Não se pode medir temporização elétrica com este exemplo Python.

## Inteiros com sinal e contraexemplos

Adição com sinal em complemento de dois utiliza o mesmo mecanismo básico de soma binária, mas interpreta overflow de modo diferente. Transporte externo é indicador apropriado de **overflow sem sinal**, não serve sozinho para identificar overflow com sinal. Na adição com sinal, ocorre overflow quando dois operandos do mesmo sinal geram um resultado de sinal oposto na largura especificada. Essa distinção evita erros em programação de baixo nível.

A função rejeita propositalmente operandos negativos, largura zero, booleanos e valores acima do intervalo. Não é função geral de aritmética com precisão arbitrária. Utilizar simplesmente soma Python e máscara produziria resultado aritmético equivalente, mas esconderia a derivação pelas portas. Aqui o foco é representação e correção antes de ISA, pipelines, caches e simulação física.

## Exercícios e verificação

1. Enumere os quatro pares de entrada e confira AND, OR e XOR manualmente e em código.
2. Valide as duas leis de De Morgan para todos os pares e explique como construir uma porta a partir de outras.
3. Enumere as oito triplas do somador completo e demonstre a+b+carry_in = soma+2×carry_out.
4. Execute add_fixed_width para cada par de 0 a 15 com w=4. Compare com `((a+b)%16, (a+b)//16)`.
5. Explique por que carry_out=1 não implica necessariamente overflow com sinal em quatro bits.
6. Desenhe as dependências de um somador de quatro bits e diferencie quantidade de portas e profundidade do caminho crítico.

Continue por [representação de dados](/pt/topics/data-types-bytes-and-representation/), [lógica e demonstrações](/pt/topics/logic-proofs-invariants/) e [instruções de máquina e cache](/pt/topics/machine-representation-isa-cache/).