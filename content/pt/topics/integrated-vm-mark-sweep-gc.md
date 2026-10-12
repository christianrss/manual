---
id: integrated-vm-mark-sweep-gc
title: "Garbage Collection Integrado à VM: Raízes, Closures e Ciclos Recursivos"
description: "Integre mark-and-sweep por raízes explícitas à VM de slots, preservando closures mutáveis e coletando ciclos recursivos inacessíveis."
category: foundations
difficulty: advanced
updated: 2026-10-12
prerequisites: [versioned-bytecode-serialization, tracing-garbage-collection-reachability]
sources:
  - {title: "Hans-J. Boehm — Description of a Garbage Collector", url: "https://www.hboehm.info/gc/gcdescr.html", kind: "original collector implementation documentation"}
  - {title: "Robert Nystrom — Crafting Interpreters: Closures", url: "https://craftinginterpreters.com/closures.html", kind: "original engineering textbook"}
  - {title: "Python documentation — gc, Garbage Collector interface", url: "https://docs.python.org/3/library/gc.html", kind: "official standard library documentation"}
  - {title: "Java Virtual Machine Specification — Verification of Class Files", url: "https://docs.oracle.com/javase/specs/jvms/se25/html/jvms-4.html#jvms-4.10", kind: "official virtual machine specification"}
---
O capítulo anterior sobre [alcançabilidade no heap](/pt/topics/tracing-garbage-collection-reachability/) construiu um grafo independente de objetos e um coletor mark-and-sweep. O capítulo de [bytecode versionado](/pt/topics/versioned-bytecode-serialization/) definiu um formato verificável de instruções. Entretanto, essas técnicas somente se tornam parte da arquitetura de execução quando o interpretador conhece **quais valores são raízes**, quais objetos apontam para outros objetos e em quais momentos a coleta pode ocorrer sem destruir uma referência removida temporariamente da pilha.

Este capítulo integra o modelo de grafo anterior a uma **terceira forma de execução** da VM de slots tipados. As VMs anteriores, por nome e por índice, permanecem preservadas como implementações alternativas para comparação. A nova VM executa o mesmo `SlotCode` verificado estaticamente, mas armazena células e closures por identificadores de heap. O resultado é um **modelo didático limitado, implementado em Python**, não uma substituição do alocador nem do coletor de lixo real do Python [1][3].

## Identidade dos objetos e representação do heap

A VM distingue resultados **imediatos** de objetos **gerenciados**. Inteiros e números racionais exatos continuam representados por `Fraction`; booleanos continuam sendo valores `bool`. Uma célula ou closure é alocada no grafo explícito `HeapModel`, e sua referência nas pilhas e nos escopos da VM é o objeto imutável `ManagedRef(object_id)`. Os identificadores crescem monotonicamente e não são reutilizados durante uma execução. Assim, um identificador coletado não passa silenciosamente a representar outra alocação.

Existem dois tipos principais de conteúdo gerenciado. `ManagedCell` contém valor atual, permissão de escrita e estado de inicialização. `ManagedClosure` contém bytecode compilado e cópias das **listas** dos escopos léxicos capturados. Essas listas armazenam valores imediatos ou referências gerenciadas, e não cópias dos objetos apontados. Portanto, duas closures que copiam ambientes podem continuar referenciando **a mesma célula mutável** [2].

O grafo de objetos registra as arestas entre referências. Uma célula cujo valor é uma closure aponta para o ID dessa closure; a closure aponta para todas as referências gerenciadas existentes nos escopos capturados. Quando `STORE_SLOT` altera uma célula, suas arestas de saída precisam ser atualizadas **juntamente com o valor armazenado**. Quando `INIT_REC_SLOT` inicializa uma célula recursiva, acrescenta a ligação da célula para a closure. A ausência dessa atualização é um erro importante: um coletor poderia descartar um objeto ainda alcançável pelo programa.

Os identificadores desse heap **não são endereços de memória reais**. Os conteúdos continuam sendo objetos Python administrados pela linguagem hospedeira. Esse limite impede confundir testes de alcançabilidade com provas de isolamento nativo, segurança de ponteiros ou eficiência de um alocador de produção.

## Raízes de todos os quadros de ativação

Uma **raiz** é uma referência ativa mantida **fora do grafo dos objetos gerenciados**. Nesta VM, as raízes vêm de todos os quadros de ativação em execução: cada valor em todas as pilhas de operandos e em todos os slots de todos os escopos léxicos. O coletor examina **todos os quadros**, não apenas a função no topo da pilha de chamadas. Caso contrário, uma closure armazenada num chamador suspenso poderia ser coletada enquanto outra função executa.

A descoberta de raízes percorre as pilhas e os escopos de cada quadro, selecionando valores do tipo `ManagedRef`. Em seguida, a fase *mark* visita recursivamente por meio de uma fila todas as ligações que partem dessas raízes. A fase *sweep* remove objetos que não foram marcados. Os registros de conteúdo correspondentes também são descartados, garantindo que o grafo e a tabela de conteúdos mantenham exatamente os mesmos identificadores vivos após a coleta.

O retorno final de uma closure exige atenção. No instante em que `RETURN` termina, nenhum quadro continua ativo para preservar o valor retornado. Por isso, a VM trata a referência do resultado como uma **raiz externa temporária durante a última coleta**. Resultados numéricos são imediatos e não exigem essa raiz; logo, todos os objetos gerenciados que se tornaram inacessíveis podem ser recuperados. A referência final a uma função permanece **opaca e não pode ser invocada por uma API externa** neste módulo. Sua sobrevivência demonstra o modelo de alcançabilidade, não um novo protocolo de chamadas.

## Pontos seguros, raízes temporárias e limites de alocação

Um coletor mark-and-sweep não deve executar quando as referências do programa estão num estado intermediário inconsistente. Esta implementação coleta **entre instruções completas de bytecode**. O intervalo é um inteiro positivo denominado `gc_interval`, medido em instruções despachadas. Por exemplo, `gc_interval=1` solicita coleta depois de cada instrução concluída. É útil para testes adversariais de correção, mas normalmente inadequado para desempenho.

A alocação apresenta outro caso. `BIND_SLOT` retira primeiro o valor do inicializador da pilha e só depois aloca uma célula mutável para armazená-lo. Se o heap estiver cheio e o alocador executar uma coleta antes de criar essa célula, o valor retirado **não aparece mais entre as raízes normais**. Quando o valor é uma closure, a coleta poderia destruir a referência que a célula ainda precisa armazenar. Por isso, o alocador registra esse valor como **raiz temporária de alocação**. Essa regra fecha uma janela de inconsistência que se tornaria evidente sob coletas muito frequentes.

O heap possui um limite explícito de objetos. Uma tentativa de alocar quando ele está cheio aciona coleta com as raízes dos quadros e as referências temporárias. Se não houver espaço suficiente depois da coleta, a VM lança `MemoryError`. Permanecem também os limites de instruções e de profundidade da pilha de chamadas. Esses mecanismos **não garantem contenção de todos os recursos**: uma única operação sobre números `Fraction` de precisão arbitrária ainda pode consumir muito tempo e memória do processo hospedeiro.

## Ciclos recursivos e tempo de vida das closures

A instrução `let rec` do compilador anterior cria uma célula inicialmente vazia antes de construir a função. A closure captura essa célula. A inicialização então armazena a própria closure dentro dela, formando o ciclo **célula → closure → célula**. A simples contagem de referências não necessariamente recuperaria esse ciclo quando todas as referências externas desaparecessem. Um coletor por rastreamento consegue fazê-lo: sem raízes nas pilhas, nos escopos ou no resultado retido, nenhum dos dois objetos é marcado e ambos são eliminados [1].

Durante a execução da função recursiva, entretanto, quadros ativos e escopos capturados mantêm a célula como raiz. O coletor **não pode** recuperar o ciclo enquanto uma chamada aninhada depende dele. Um teste forte executa fatorial com coleta após cada instrução, verifica o resultado numérico exato e confirma que não existem objetos gerenciados restantes quando a execução termina. A coleta final recupera a célula e a closure porque o resultado é um número imediato.

Outro teste retorna uma closure que captura um contador mutável. A closure sobrevive ao quadro da função que a criou porque ainda está armazenada num slot do chamador. O contador precisa sobreviver às coletas e preservar seu estado entre chamadas. Alterar a frequência da coleta **não pode modificar o resultado do programa**. Trata-se de um invariante semântico, não de um benchmark de velocidade.

## Implementação executável e observabilidade

A [VM gerenciada](https://github.com/christianrss/manual/blob/main/examples/python/managed_slot_vm.py) disponibiliza `run_managed` e `evaluate_managed`. Antes de executar, ela chama o verificador de bytecode já existente. O objeto `ManagedResult` informa resultado, quantidade de coletas, total de objetos recuperados, máximo de objetos gerenciados simultâneos e quantidade restante. O mesmo código aparece no capítulo em inglês:

~~~python
from fractions import Fraction
from examples.python.lexical_slot_verifier import compile_slots, run_slots
from examples.python.managed_slot_vm import (
    run_managed, evaluate_managed, ManagedRef,
)

source = ("var x:Int=1 in "
          "let inc:Fn()->Int=fn()->Int=>set x=x+1 in "
          "inc()+inc()")
program = compile_slots(source)
managed = run_managed(program, gc_interval=1)
assert managed.value == run_slots(program) == Fraction(5)
assert managed.reclaimed == managed.allocated_objects
assert managed.live_objects == 0

recursive = ("let rec fact:Fn(Int)->Int="
             "fn(n:Int)->Int=>if n<2 then 1 else n*fact(n-1) "
             "in fact(5)")
typ, collected = evaluate_managed(recursive, gc_interval=1)
assert typ == "Int" and collected.value == Fraction(120)
assert collected.live_objects == 0

closure = run_managed(compile_slots("fn(x:Int)->Int=>x+1"))
assert isinstance(closure.value, ManagedRef)
assert closure.live_objects == 1
~~~

A [suíte de contratos](https://github.com/christianrss/manual/blob/main/tests/test_integrated_vm_gc_contracts.py) compara resultados com a VM por slots anterior e com um interpretador direto da AST escrito separadamente. Outros testes com semente fixa verificam mutação, sombreamento léxico, fatorial e diferentes frequências de coleta. Os casos negativos cobrem bytecode inválido, limites de execução inconsistentes e esgotamento do heap. Essas verificações são finitas e **não constituem prova formal de segurança de memória para programas arbitrários**.

## Complexidade, limites e extensões

Considere V como quantidade de objetos gerenciados existentes e E como quantidade de arestas entre eles. Uma coleta mark-and-sweep visita vértices e arestas alcançáveis e examina todos os objetos durante a varredura. Seu custo é **O(V + E)** em tempo e O(V) em memória auxiliar no modelo de grafo limitado. Descobrir as raízes custa adicionalmente O(R), sendo R a quantidade de valores ativos distribuídos pelas pilhas e pelos escopos. Portanto, coletar após cada uma das I instruções pode produzir até O(I(V+E+R)) operações no pior caso. Essa frequência foi concebida para verificar invariantes, não para otimizar throughput.

Os contadores de alocação, pico e coleta são **estatísticas do modelo**, não medições do heap real do Python, da memória residente ou da latência de alocação do sistema operacional. O coletor é stop-the-world, de execução única, não geracional e não move objetos. Não implementa compactação, inspeção de pilhas de máquina, referências fracas, finalizadores, barreiras de escrita concorrentes nem pausas incrementais. A VM continua dependendo dos mecanismos de alocação do Python, e o verificador de instruções permanece restrito ao subconjunto de bytecode em memória já publicado [3][4].

O princípio de engenharia estabelecido é específico: **toda referência ativa precisa estar representada por uma raiz em cada ponto de coleta; toda alteração de referência gerenciada deve atualizar o grafo correspondente**. Futuras extensões podem acrescentar layouts de objetos, marcação incremental, *remembered sets* ou um alocador nativo, mas cada uma exige invariantes e testes próprios.

## Exercícios e verificação

1. Identifique as raízes quando uma função chamada está em execução e seu chamador aguarda o retorno. **Verificação:** pilhas e escopos dos dois quadros devem ser examinados.
2. Explique por que uma closure removida da pilha imediatamente antes da alocação de uma célula exige uma raiz temporária. **Verificação:** uma coleta provocada por heap cheio não pode perder a referência do inicializador.
3. Desenhe o ciclo criado por `let rec`. **Verificação:** a célula aponta para a closure, e os escopos capturados da closure apontam para a célula.
4. Preveja o efeito de mudar `gc_interval` de 1 para 100. **Verificação:** estatísticas de coleta podem mudar, mas o resultado numérico exato permanece igual.
5. Determine quando surge `MemoryError`. **Verificação:** a capacidade foi atingida, a coleta não libera espaço suficiente e outra alocação é solicitada.
6. Compare o modelo didático com um coletor de produção. **Verificação:** identidades e contagens são simuladas; não existe isolamento da memória hospedeira nem coleta concorrente.
