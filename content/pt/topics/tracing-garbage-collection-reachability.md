---
id: tracing-garbage-collection-reachability
title: "Alcançabilidade no Heap, Tempo de Vida e Coleta Mark-and-Sweep"
description: "Derive alcançabilidade e construa um coletor mark-and-sweep limitado com closures, células compartilhadas, ciclos e testes independentes."
category: foundations
difficulty: advanced
updated: 2026-10-11
prerequisites: [mutable-cells-recursive-functions]
sources:
  - {title: "Hans-J. Boehm — A garbage collector for C and C++", url: "https://www.hboehm.info/gc/", kind: "original collector author and project"}
  - {title: "Hans-J. Boehm — Description of a Garbage Collector", url: "https://www.hboehm.info/gc/gcdescr.html", kind: "original implementation documentation"}
  - {title: "Python Data Model — Objects, values and types", url: "https://docs.python.org/3/reference/datamodel.html", kind: "official language reference"}
  - {title: "Robert Nystrom — Crafting Interpreters: Closures", url: "https://craftinginterpreters.com/closures.html", kind: "original compiler engineering textbook"}
---
Um quadro de ativação pode terminar enquanto uma closure continua referenciando uma variável criada por esse quadro. No [compilador de células mutáveis](/pt/topics/mutable-cells-recursive-functions/), o runtime do Python retém automaticamente a célula capturada. Dessa observação surgem duas questões distintas: **quais objetos precisam continuar vivos** e **quais objetos podem ser liberados com segurança**? O capítulo deriva o modelo de grafo utilizado na coleta de lixo por rastreamento e implementa um **heap mark-and-sweep didático e limitado**, com interrupção do mutador durante a coleta [1][2].

O coletor **não foi incorporado à VM de bytecode**. Trata-se de uma simulação explícita de grafo com identificadores inteiros estáveis. Essa distinção evita chamar de gerenciamento de memória de produção um algoritmo que não interpreta ponteiros reais, pilhas nativas, metadados de alocação, sincronização nem layout físico de objetos.

## Objetos, referências e conjunto de raízes

Considere o heap como um grafo dirigido G=(V,E). Cada vértice corresponde a um objeto alocado e cada aresta dirigida representa uma **referência forte** de um objeto para outro. Na implementação são reconhecidas as categorias `closure`, `environment`, `cell`, `value` e `pair`. Essas categorias servem à demonstração: um runtime de produção precisaria de cabeçalhos, formatos de campos e mapas de ponteiros. Um identificador inteiro distingue a identidade do objeto do valor que ele representa.

O **conjunto de raízes R** contém endereços mantidos diretamente pelo estado do programa fora do rastreamento do heap, por exemplo slots de quadros de ativação ainda ativos, variáveis globais e registradores da VM. Neste laboratório, as raízes são entregues explicitamente ao método `collect(roots)`. O programa não procura ponteiros automaticamente na pilha Python ou em registradores reais. Exigir raízes explícitas impede confundir variáveis locais da linguagem hospedeira com ponteiros da linguagem modelada.

Defina Reach(R) como o menor conjunto que contém R e está fechado pelas referências: se u está alcançável e u aponta para v, então v também está alcançável. O invariante central do coletor é **nunca liberar um vértice alcançável**. Por outro lado, considerando raízes e arestas completas e corretas, todo vértice fora de Reach(R) pode ser recuperado neste modelo fechado. Esquecer uma raiz não é apenas um problema de contabilização: pode provocar liberação de objeto que o programa ainda pretende utilizar.

## Exemplo: uma closure que mantém a célula viva

Imagine uma função que cria uma célula de contador mutável e retorna uma closure que lê ou modifica esse contador. O grafo contém três vértices: uma `closure` que aponta para um `environment`, que aponta para uma `cell`. O quadro da chamada externa já terminou e deixou de ser uma raiz. A closure devolvida, contudo, permanece armazenada pelo chamador e, portanto, funciona como raiz. O caminho relevante é:

`closure raiz -> environment -> cell`

Os três objetos permanecem alcançáveis. Um objeto temporário `pair` que não recebe qualquer caminho vindo de uma raiz pode ser liberado. Quando o chamador remove a última referência à closure e o conjunto de raízes fica vazio, a closure, o ambiente e a célula passam a ser inalcançáveis e podem ser liberados juntos. O tempo de vida é determinado pela **alcançabilidade**, não apenas pela ordem dos retornos das funções [3][4].

A mesma lógica explica o compartilhamento: duas closures podem apontar para o mesmo ambiente e a mesma célula mutável. Remover apenas a primeira closure não libera a célula enquanto a segunda permanecer enraizada. O coletor precisa percorrer o grafo completo; contar identificadores léxicos diferentes no código-fonte não é critério suficiente de vida útil.

## Fases de marcação e varredura

O algoritmo mark-and-sweep possui duas fases conceituais. **Marcação:** partir de todas as raízes e percorrer referências até visitar todos os objetos alcançáveis; um conjunto de visitados impede repetições e caminhadas infinitas por ciclos. **Varredura:** percorrer os objetos alocados, liberar os que não foram marcados e manter os marcados [1][2].

A implementação utiliza uma `deque` explícita para rastrear o grafo em vez de fazer chamadas recursivas Python a cada referência. Isso evita consumir um quadro de pilha da linguagem hospedeira por aresta. `HeapModel.mark` devolve os identificadores alcançáveis ordenados. `HeapModel.collect` calcula esse conjunto, remove os objetos restantes do dicionário de propriedade e retorna um objeto `Collection` com os identificadores preservados, recuperados e a quantidade restante. Os IDs crescem monotonamente e **não são reutilizados**, simplificando a identificação de referências antigas e casos de teste de endereços inválidos.

O coletor é **stop-the-world** por contrato: o grafo não pode sofrer mutações durante a execução de uma coleta. Não existem barreiras de escrita, marcação concorrente, snapshots incrementais nem conjuntos de gerações. Permitir escrita concorrente durante o rastreamento invalidaria as premissas. Coletores reais incrementais e concorrentes necessitam de regras adicionais de sincronização, invariantes de três cores e barreiras específicas [2].

## Por que ciclos não significam objetos vivos

Considere dois objetos `pair` A e B que apontam um para o outro, sem que nenhum seja alcançável a partir das raízes. Eles formam um ciclo dirigido, mas **ciclos não criam alcançabilidade por si só**. Uma estratégia simples baseada apenas em contagem de referências pode deixar A e B alocados indefinidamente, já que ambos continuam contando a referência recebida do outro. Um coletor por rastreamento não apresenta essa limitação: se nenhum aparece na marcação iniciada nas raízes, ambos são liberados na varredura.

No caso contrário, se A é raiz, sua aresta A→B torna B alcançável, e B→A não altera a conclusão. O conjunto de visitados garante o término mesmo quando o grafo possui ciclos. Esse exemplo demonstra por que alcançabilidade de raízes é um critério mais apropriado do que a contagem bruta de referências recebidas por cada objeto.

É importante distinguir referências fortes de referências fracas. **Somente arestas fortes** são modeladas neste capítulo. Referências fracas, finalizadores, ressurreição de objetos e filas de referência não existem; acrescentá-las mudaria quais objetos podem ser liberados e em que momento, exigindo regras próprias.

## Laboratório executável e oráculo independente

A [simulação de heap](https://github.com/christianrss/manual/blob/main/examples/python/mark_sweep_heap.py) implementa `allocate`, `set_references`, `mark`, `collect` e `get`, incluindo duas demonstrações completas. A primeira mostra uma closure retornada preservando uma célula; a segunda libera um ciclo sem raízes:

~~~python
from examples.python.mark_sweep_heap import (
    HeapModel, closure_lifetime_example, cyclic_collection_example,
)

first, last = closure_lifetime_example()
assert len(first.reachable) == 3
assert len(first.reclaimed) == 1
assert last.remaining == 0

cycle = cyclic_collection_example()
assert len(cycle.reclaimed) == 2

heap = HeapModel()
cell = heap.allocate("cell")
env = heap.allocate("environment", (cell,))
closure = heap.allocate("closure", (env,))
assert heap.collect((closure,)).reclaimed == ()
assert heap.collect(()).reclaimed == (cell, env, closure)
~~~

A [suíte independente](https://github.com/christianrss/manual/blob/main/tests/test_mark_sweep_heap_contracts.py) gera grafos aleatórios pequenos com uma semente fixa. Em vez de reutilizar a `deque` do coletor, seu **oráculo de ponto fixo** expande repetidamente um conjunto de vértices alcançáveis até que nenhuma referência adicional possa ser incluída. Esse resultado independente é comparado com marcação e varredura. Outros testes tratam ciclos, células compartilhadas, alterações de referências, raízes inexistentes, IDs inválidos, coletas repetidas e esgotamento de capacidade de alocação.

## Custos e limites explícitos

Se V representa objetos alocados, E a quantidade de arestas de referência e R a quantidade de raízes, assumindo custo esperado constante de operações em conjuntos e dicionários, a marcação consome **O(V_alcançável + E_alcançável + R)** em tempo esperado. A varredura percorre os O(V) objetos alocados. O custo total esperado é O(V+E+R); o conjunto de visitados e a lista de trabalho exigem O(V_alcançável+R) de memória auxiliar. Essas são medidas de **operações sobre o grafo**, não medições de bytes do alocador ou garantias no pior caso de colisões de hash.

O heap simulado limita a **8.192 objetos vivos** e impõe limites nas listas de referências. A alocação falha explicitamente ao atingir a capacidade; não existe coleta automática ao tentar alocar. Os registros `HeapObject` são imutáveis e guardados num dicionário Python, cuja memória continua administrada pelo próprio Python. O modelo não utiliza as closures reais da VM e **não recupera memória da VM**. Para integrar um coletor real seria necessário localizar todas as referências contidas nas pilhas de operandos, quadros de ativação, células capturadas, tabelas de constantes e raízes globais. Também seria necessário especificar layouts, fragmentação e sincronização.

## Exercícios e verificação

1. Desenhe uma closure retornada, seu ambiente e uma célula de contador. **Verificação:** se a closure é raiz, os três objetos permanecem vivos após o retorno externo.
2. Acrescente outra closure que aponta para o mesmo ambiente. Remova a primeira raiz. **Verificação:** ambiente e célula continuam alcançáveis pela segunda.
3. Crie A→B e B→A sem raízes. **Verificação:** os dois são recuperados; o ciclo não cria raiz.
4. Forneça como raiz um ID inexistente. **Verificação:** o modelo rejeita o endereço em vez de ignorá-lo.
5. Explique a falha se o grafo puder ser alterado simultaneamente ao rastreamento. **Verificação:** uma nova aresta para um objeto ainda não marcado poderia surgir depois da passagem do coletor pelo seu pai.
6. Compare com contagem de referências. **Verificação:** rastreamento recupera ciclos inalcançáveis; uma implementação simples de contagem pode retê-los.

Uma continuação real precisará ligar as pilhas da VM e as closures a objetos do heap, estabelecer enumeração de raízes e invariantes de tempo de vida e estudar fragmentação, políticas geracionais e barreiras concorrentes. O laboratório demonstra alcançabilidade, mas **não implementa um coletor de lixo de produção**.
