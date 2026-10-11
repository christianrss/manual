---
id: lexical-addresses-bytecode-verification
title: "Endereços Léxicos, Verificação de Bytecode Tipado e Máquina Virtual por Slots"
description: "Resolva variáveis por slots, analise controle de fluxo e tipos da pilha do bytecode e confira os resultados com uma VM independente."
category: foundations
difficulty: advanced
updated: 2026-10-11
prerequisites: [mutable-cells-recursive-functions]
sources:
  - {title: "Robert Nystrom — Crafting Interpreters: Resolving and Binding", url: "https://craftinginterpreters.com/resolving-and-binding.html", kind: "original engineering textbook"}
  - {title: "Robert Nystrom — Crafting Interpreters: Closures", url: "https://craftinginterpreters.com/closures.html", kind: "original engineering textbook"}
  - {title: "Java Virtual Machine Specification, Java SE 25 — Verification of Class Files", url: "https://docs.oracle.com/javase/specs/jvms/se25/html/jvms-4.html#jvms-4.10", kind: "official virtual machine specification"}
  - {title: "Benjamin C. Pierce — Types and Programming Languages", url: "https://mitpress.mit.edu/9780262162098/types-and-programming-languages/", kind: "academic textbook"}
---
O [compilador de células mutáveis e funções recursivas](/pt/topics/mutable-cells-recursive-functions/) já apresenta comportamento léxico correto nos casos testados, mas cada acesso a variável procura seu nome nos dicionários de escopos. Além disso, depende da checagem de tipos do programa-fonte, sem validar separadamente a **estrutura da pilha e do fluxo de controle do bytecode gerado**. Essas duas limitações revelam uma fronteira entre analisar uma expressão tipada e executar um programa estruturalmente válido na máquina virtual. Neste capítulo será criado um **segundo backend opcional**, que transforma nomes em endereços de slots e verifica as instruções antes de executá-las [1][3].

A VM anterior permanece preservada e funciona como uma implementação alternativa para comparação dos resultados. O novo backend reutiliza o parser, a AST e a checagem de tipos existentes. Portanto, as duas máquinas **não são independentes no front-end**; seus formatos de instruções e mecanismos de execução são distintos, o que permite identificar erros na geração de código e na captura léxica.

## Endereços léxicos e identidade das declarações

Um endereço léxico é o par **(distância, índice)**. Distância representa a quantidade de quadros de escopo entre o quadro atual e o quadro que declarou a variável; índice identifica a posição da variável dentro desse quadro. Ambos são inteiros não negativos. Considere `let x:Int=10 in let f:Fn(Int)->Int=fn(y:Int)->Int=>x+y in f(2)`. Dentro da função, o parâmetro y está em `(0,0)`; a variável x, declarada no escopo capturado imediatamente anterior, está em `(1,0)` [1].

Durante a compilação, o resolvedor mantém uma lista de descritores de escopos. Cada descritor registra nome, tipo estático, permissão de escrita, indicação de recursão e estado de inicialização. Ao encontrar uma referência de variável, percorre os descritores do mais interno ao externo, escolhe a primeira declaração correspondente e incorpora seu endereço numérico à instrução `LOAD_SLOT`. A atribuição usa `STORE_SLOT (distância,índice)`. A procura pelo nome ocorre **uma vez durante a compilação**, e não em todas as execuções da instrução.

Assim, o nome textual é uma representação conveniente para o programador, não uma exigência para acessar variáveis na VM. A resolução depende da **estrutura léxica**, não da pilha dinâmica de chamadas nem de um dicionário global. Declarações diferentes com o mesmo identificador têm endereços distintos: sombreamento não significa sobrescrever o slot anterior. A distinção segue o princípio utilizado em compiladores que resolvem locais e variáveis capturadas antes da execução [1][2].

## Representação por slots e tempo de vida de células

A VM indexada representa cada escopo léxico como uma **lista de slots**, em vez de um dicionário cujas chaves são nomes. A leitura utiliza `scopes[-1-distance][index]`, depois de o verificador conferir a validade dos índices. A operação de indexação em listas de Python tem custo abstrato constante, dispensando a procura sequencial de nomes a cada leitura. Isso **não** significa que toda operação envolvendo closures tenha custo constante: ainda existe cópia de escopos durante captura e criação de chamadas.

Variáveis imutáveis armazenam seus valores diretamente no slot; variáveis mutáveis armazenam referências a um mesmo objeto `Cell`. Copiar a lista de slots preserva a identidade dessas células, de forma que closures diferentes que capturam o mesmo `var` enxergam o mesmo local. Duas declarações diferentes de x, em contraste, recebem slots e células próprios. A criação de uma função recursiva utiliza `DECLARE_REC_SLOT` para abrir uma célula inicialmente não gravável e ilegível, `CLOSURE_SLOT` para capturá-la e `INIT_REC_SLOT` para preencher a célula uma única vez.

Cada quadro de ativação possui ponteiro de instrução, pilha de operandos e escopos léxicos. Uma chamada retira a função e seus argumentos da pilha do chamador e cria novo quadro cujos parâmetros aparecem **após** os escopos capturados. O retorno deposita o resultado na pilha independente do chamador. Essa organização preserva o escopo léxico mesmo quando uma closure continua ativa depois do término do quadro que criou a célula capturada [2].

## Por que verificar bytecode antes da execução

Mesmo que o programa-fonte seja válido, um erro do backend pode produzir instruções inválidas. Uma sequência pode tentar executar `ADD` com apenas um operando, saltar para dentro de um escopo sem passar por `ENTER`, ler o slot 3 de um quadro que possui apenas um slot ou devolver `Bool` de um corpo declarado como `Int`. Esses problemas devem ser detectados **antes da execução**, sem depender de exceções imprevisíveis da VM.

O verificador didático recebe uma representação tipada e limitada chamada `VerifiedProgram`, composta por objetos `SlotCode`. Ele examina formatos das instruções, opcodes conhecidos, valores imediatos, limites dos endereços léxicos, permissões de escrita, suficiência da pilha, tipos dos argumentos, retornos, balanço de escopos e ordem de inicialização recursiva. Também compara os corpos de closures com os descritores de ambiente que capturam. O objetivo geral é semelhante ao da verificação de arquivos de classe da JVM: rejeitar código inválido conforme regras de tipos e fluxo de controle antes de executá-lo [3]. **Esta ferramenta não lê arquivos de classe Java nem implementa o verificador completo da JVM.**

O verificador também rejeita instruções desconhecidas, saltos para trás, trechos inalcançáveis e sequências maiores que o limite estabelecido. O compilador deste manual não gera saltos de retorno para implementar laços: a recursão utiliza chamadas de função, enquanto os condicionais usam apenas saltos para a frente. Essa restrição permite simplificar a análise sem sugerir que uma VM de propósito geral possa dispensar saltos retroativos.

## Interpretação abstrata de tipos e junções de fluxo

O verificador **não calcula os resultados numéricos** do programa. Em cada índice de instrução alcançável, ele registra um estado abstrato: **(pilha de tipos dos operandos, descritores de escopos léxicos)**. Depois de `PUSH_INT 3`, a pilha abstrata contém `[Int]`; dois inteiros seguidos de `ADD` devolvem `[Int]`. A divisão de valores numéricos sempre produz o tipo estático `Rat`. A transferência de `STORE_SLOT` exige um destino gravável e um operando do mesmo tipo declarado, mantendo esse tipo na pilha porque a atribuição é uma expressão [4].

A instrução `JUMP_IF_FALSE` exige `Bool` no topo, remove-o e explora **ambos os sucessores possíveis**. Cada caminho recebe cópias dos estados abstratos produzidos até aquele ponto. Quando dois caminhos chegam à mesma instrução, seus estados precisam coincidir: alturas distintas da pilha, tipos incompatíveis ou escopos diferentes revelam bytecode inválido. `JUMP` possui um único destino, e ambos os saltos exigem um alvo estritamente posterior, dentro dos limites do código. Uma fila de trabalho permite visitar todos os índices alcançáveis. Como o grafo verificado é finito e permite apenas saltos para a frente, o algoritmo termina.

`RETURN` exige precisamente um valor com o tipo declarado pelo bloco, além de nenhum escopo local aberto. Objetos `SlotCode` aninhados registram tipos dos parâmetros, retorno esperado e descritores capturados. `CALL` verifica a quantidade e os tipos dos argumentos comparando-os com o tipo de função existente na pilha abstrata. Isso identifica erros que uma conferência de **altura** da pilha, isoladamente, não conseguiria distinguir.

## A exceção controlada das células recursivas

Uma função recursiva captura uma referência para si mesma que ainda não possui valor durante a construção da closure. O corpo da função pode legitimamente conter `LOAD_SLOT` desse slot recursivo **capturado**: o corpo somente será executado depois da inicialização. Entretanto, uma leitura direta desse mesmo slot antes de `INIT_REC_SLOT` deve ser proibida.

Por isso, o verificador exige a sequência **adjacente** `DECLARE_REC_SLOT`, `CLOSURE_SLOT`, `INIT_REC_SLOT` para uma nova declaração recursiva. Ele permite que o código da closure mantenha o descritor temporariamente não inicializado, mas impede a leitura direta da célula vazia. `INIT_REC_SLOT` atualiza o descritor para inicializado somente depois de verificar que a pilha contém uma função do tipo esperado. A VM também rejeita leituras de células recursivas não inicializadas em tempo de execução. A combinação de restrições sintáticas, regras estruturais e verificações dinâmicas é mais limitada que uma prova geral de segurança de bytecode recursivo.

Esse limite é relevante: o verificador recebe objetos `SlotCode` confiáveis construídos em memória e rejeita estruturas de código aninhadas compartilhadas ou cíclicas. Ele **não autentica bytes**, não impede mutações externas arbitrárias depois da verificação e não comprova segurança de recursos. Trata-se de uma ferramenta de engenharia didática, não de um serviço para executar código arbitrário de terceiros.

## Exemplo executável e comparação entre duas VMs

O [backend de slots e verificador](https://github.com/christianrss/manual/blob/main/examples/python/lexical_slot_verifier.py) disponibiliza `compile_slots`, `verify_slots`, `run_slots`, `evaluate_slots`, `SlotInfo` e `BytecodeError`. O exemplo a seguir demonstra captura mutável, verificação estática e rejeição de endereços inexistentes:

~~~python
from fractions import Fraction
from examples.python.lexical_slot_verifier import (
    compile_slots, verify_slots, run_slots, evaluate_slots,
    SlotInfo, SlotCode, VerifiedProgram, BytecodeError,
)

source = ("var x:Int=1 in "
          "let f:Fn()->Int=fn()->Int=>set x=x+1 in "
          "f()+f()")
program = compile_slots(source)
assert verify_slots(program)
assert run_slots(program) == Fraction(5)
assert evaluate_slots(source) == ("Int", Fraction(5))

bad = VerifiedProgram(
    "Int", SlotCode((), (), "Int", (
        ("LOAD_SLOT", (0, 0), 0),
        ("RETURN", None, 0),
    ))
)
try:
    verify_slots(bad)
    assert False, "out-of-bounds slot must fail verification"
except BytecodeError:
    pass
~~~

A [suíte independente](https://github.com/christianrss/manual/blob/main/tests/test_lexical_bytecode_verifier_contracts.py) compara a VM antiga por nomes, a nova VM por slots e um interpretador direto da AST em programas idênticos selecionados. Também cria casos determinísticos de contadores e fatoriais e instrui o verificador a rejeitar sequências fabricadas com estouro negativo da pilha, tipos incompatíveis, endereços inválidos, saltos incorretos, escopos desbalanceados e erros de inicialização recursiva. Os testes abrangem equivalência positiva e rejeição negativa. Permanecem verificações finitas, não uma demonstração de correção universal.

## Complexidade, limites de segurança e próximas etapas

Considere n como quantidade de nós da AST, d como quantidade de escopos léxicos visíveis, m como quantidade de instruções e c como número de entradas capturadas em um ambiente. Resolver um identificador exige, no pior caso, visitar **O(d)** escopos, além de procurar declarações dentro de cada escopo; esse custo ocorre durante a **compilação**. `LOAD_SLOT` realiza **O(1) indexação abstrata**, desde que o endereço seja válido e as listas Python ofereçam acesso de custo constante. A criação de closures e de chamadas ainda pode copiar O(c) slots. O verificador percorre o grafo de fluxo com estados cuja dimensão depende da altura da pilha e dos descritores léxicos; como esses estados são materializados, afirmar custo total O(m) sem ressalvas seria incorreto.

A VM mantém limites explícitos de instruções executadas e quadros de chamada. A verificação de tipos e de estrutura **não equivale a impor isolamento de CPU, memória, arquivos ou processos**. Cálculos racionais de precisão arbitrária podem consumir recursos consideráveis e células capturadas podem sobreviver aos seus quadros originais. Grafos de código compartilhados, formatos persistentes de bytecode, assinaturas, exceções como arestas de fluxo, saltos retroativos, concorrência com estado mutável e geração nativa continuam não implementados.

## Exercícios e verificação

1. Resolva as duas leituras em `fn(y:Int)->Int=>x+y` quando x pertence ao escopo imediatamente capturado. **Verificação:** x está em `(1,0)` e y em `(0,0)`.
2. Construa `ADD` depois de somente um `PUSH_INT`. **Verificação:** o verificador rejeita insuficiência de operandos antes da execução.
3. Faça dois ramos de uma condição chegarem à mesma instrução com pilhas abstratas `[Int]` e `[Bool]`. **Verificação:** os estados incompatíveis precisam ser rejeitados, mesmo quando um ramo não seria executado.
4. Substitua o destino de `STORE_SLOT` por um endereço que aponta para variável imutável. **Verificação:** o verificador rejeita a escrita apesar da compatibilidade numérica de tipos.
5. Explique por que uma closure recursiva pode capturar uma célula não inicializada, mas não pode lê-la diretamente antes de `INIT_REC_SLOT`. **Verificação:** a identidade da célula precisa existir antes da construção da closure; o valor torna-se acessível somente depois.
6. Compare procura de nomes na compilação com indexação por slots durante a execução. **Verificação:** a procura textual migra para o compilador, enquanto cópias e capturas de ambiente continuam com custo próprio.

A continuação deverá reduzir o tamanho dos descritores, definir um **formato de bytecode serializado e versionado** e aprofundar o estudo de alcance e duração de objetos na memória. Esses componentes não são cobertos pelo verificador em memória desenvolvido neste capítulo.
