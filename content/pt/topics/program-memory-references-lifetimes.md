---
id: program-memory-references-lifetimes
title: "Fundamentos de memória: referências, aliasing e duração de objetos"
description: "Compreenda associação de nomes, identidade, referências mutáveis, quadros de chamadas e snapshots imutáveis com exemplos."
category: foundations
difficulty: foundational
updated: 2026-10-12
prerequisites: [programming-semantics-contracts, data-types-bytes-and-representation]
sources:
  - {title: "Python language reference — Data model", url: "https://docs.python.org/3/reference/datamodel.html", kind: "official language reference"}
  - {title: "Python language reference — Execution model", url: "https://docs.python.org/3/reference/executionmodel.html", kind: "official language reference"}
  - {title: "Python standard library — Copy", url: "https://docs.python.org/3/library/copy.html", kind: "official library documentation"}
  - {title: "Python standard library — Garbage collector", url: "https://docs.python.org/3/library/gc.html", kind: "official library documentation"}
---
Nome de variável, objeto e memória usada para armazená-lo são conceitos relacionados, mas **não são equivalentes**. Quando um programador pressupõe que atribuir uma lista a outro nome cria uma lista independente, aparecem mutações inesperadas. Antes de estudar alocadores, memória virtual ou coletores de lixo, é necessário compreender quais nomes e coleções referenciam quais objetos [1][2].

## Nomes, identidade e igualdade

Em Python, atribuição associa um nome a um objeto. Associar um segundo nome ao mesmo objeto não o duplica. O operador de identidade verifica se duas expressões identificam o mesmo objeto; igualdade verifica se seus valores são equivalentes segundo a semântica do tipo. Duas listas distintas podem ser iguais, e dois nomes que apontam para uma lista mutável representam exatamente o mesmo objeto. Uma mutação feita por um nome afeta todos os observadores desse objeto [1].

O parâmetro de uma função é um nome local associado ao objeto argumento. Se uma função acrescenta item a uma lista recebida, o chamador percebe a alteração. Se a função associa outra lista ao nome do parâmetro, a variável original do chamador não é reatribuída. As descrições “Python sempre copia os argumentos” e “Python passa a própria variável do chamador por referência” escondem essas regras reais de associação.

## Mutabilidade, referências e propriedade

Inteiros e strings são objetos imutáveis; listas e dicionários admitem atualizações. Uma tupla não permite reatribuir suas posições, mas pode conter uma lista mutável. A lista contida ainda pode ser modificada. Logo, colocar objeto arbitrário numa tupla não oferece garantia de imutabilidade profunda. Essa propriedade depende de **todos os objetos alcançáveis** pela estrutura, não somente do contêiner externo.

Propriedade é um contrato de projeto: qual componente pode modificar um objeto e em que momento? Python não impõe propriedade exclusiva de listas comuns. APIs podem prometer que nunca modificam entradas, copiar dados ao recebê-los ou fornecer visualizações mutáveis documentadas. Cada escolha produz custos distintos de tempo e memória. Propriedade indefinida é especialmente perigosa quando várias funções compartilham coleções aninhadas.

## Quadros de chamadas e duração de objetos

Um quadro de chamada representa uma invocação ativa de função, incluindo associações locais e informações de controle. Chamadas recursivas criam diversos quadros lógicos. Quando a função retorna, seu quadro deixa de estar ativo; isso não significa que todos os objetos criados durante a chamada sejam destruídos. Um objeto retornado para outra função pode continuar acessível após o encerramento da criadora [2].

Os termos stack e heap representam estratégias comuns de implementação. Uma pilha pode organizar registros de ativação aninhados; armazenamento em heap permite que objetos sobrevivam à chamada criadora. Entretanto, a linguagem Python não exige que toda variável local corresponda a uma posição física específica na stack da máquina. Diferentes implementações e linguagens utilizam estratégias distintas de alocação e otimização. Um diagrama de quadros e referências é um **modelo conceitual**, não mapa portátil de endereços.

## Cópia rasa e objetos internos compartilhados

Cópia rasa cria contêiner externo novo, mas mantém referências para os elementos. Copiar lista de listas usando list(original) cria uma lista externa diferente, porém as linhas internas continuam compartilhadas. Alterar uma linha interna torna a modificação visível nos dois contêineres. Cópia profunda tenta duplicar objetos recursivamente conforme a política de cópia de cada tipo, inclusive tipos especiais e classes personalizadas [3].

Nem a cópia profunda nem a rasa são sempre melhores. Duplicar uma estrutura imutável imensa desperdiça trabalho; copiar superficialmente um cadastro aninhado mutável pode violar a expectativa de independência. A decisão correta exige um contrato claro sobre quais objetos aninhados podem mudar e quais alterações devem tornar-se visíveis em outros componentes.

## Exemplo: snapshot de matriz de inteiros

Uma matriz é representada por sequência de linhas. O contrato de entrada aceita sequência externa vazia ou matriz retangular não vazia de inteiros exatos. Rejeita larguras divergentes, células não inteiras e matrizes não vazias com zero colunas. A operação de congelamento cria tuplas contendo tuplas de linhas. Como todos os valores são inteiros imutáveis, **esta representação específica** permite snapshots imutáveis em todos os níveis.

Trocar uma célula cria tupla externa nova e tupla nova para a linha modificada; as demais linhas permanecem compartilhadas. É uma forma elementar de *copy-on-write*. O chamador pode continuar modificando a lista de entrada sem alterar o snapshot, pois nenhuma lista mutável interna foi retida. O código demonstra por que uma simples cópia rasa não seria suficiente.

~~~python
def freeze_grid(rows):
    if not isinstance(rows, (list, tuple)):
        raise TypeError("sequence required")
    if not rows:
        return ()
    if any(not isinstance(row, (list, tuple)) for row in rows):
        raise ValueError("invalid row")
    width = len(rows[0])
    if width == 0 or any(len(row) != width for row in rows):
        raise ValueError("nonrectangular grid")
    if any(type(cell) is not int for row in rows for cell in row):
        raise ValueError("integer cells required")
    return tuple(tuple(row) for row in rows)

def replace_cell(grid, row, col, value):
    if type(row) is not int or type(col) is not int:
        raise IndexError("invalid indices")
    if type(value) is not int:
        raise ValueError("invalid value")
    if row < 0 or row >= len(grid) or col < 0 or col >= len(grid[0]):
        raise IndexError("outside grid")
    return tuple(
        old[:col] + (value,) + old[col+1:] if index == row else old
        for index, old in enumerate(grid)
    )

source = [[1, 2], [3, 4]]
alias = source
shallow = list(source)
snapshot = freeze_grid(source)
assert alias is source and shallow is not source
assert shallow[0] is source[0]
source[0][0] = 99
assert shallow[0][0] == 99 and snapshot[0][0] == 1
new = replace_cell(snapshot, 0, 1, 7)
assert new == ((1, 7), (3, 4))
assert snapshot == ((1, 2), (3, 4))
assert new[1] is snapshot[1]
~~~

## Correção e análise de custos

Para R linhas e C colunas, congelar percorre RC células para validar a representação e constrói RC referências de células em tuplas imutáveis. Sob hipóteses de operações constantes sobre referências, tempo e espaço adicional são O(RC). Trocar uma célula copia C referências na linha e R referências na tupla externa: O(R+C) tempo e referências adicionais. As outras linhas podem ser compartilhadas com segurança por conter apenas valores imutáveis.

O invariante central determina que todas as linhas possuem mesma largura e todas as células armazenadas são inteiros imutáveis. A operação de congelamento preserva o conteúdo na ordem das linhas; trocar uma célula modifica somente uma posição no novo resultado. A matriz anterior continua igual. Se as células contivessem objetos mutáveis, a demonstração não seria válida. O método também rejeita índices negativos por escolha explícita da API, embora Python normalmente aceite índices negativos.

## Coleta de lixo, finalização e limites

Um objeto permanece alcançável enquanto existe um caminho de referências vivas até ele. Remover um nome não torna necessariamente um objeto inalcançável: outra lista ou closure pode conservá-lo. Ciclos de referências complicam a recuperação de memória, e o instante exato da coleta não é um contrato portátil para fechar arquivos e sockets [4]. A duração de recursos deve ser gerenciada explicitamente, por exemplo com context managers.

Snapshots imutáveis e semântica de referências também não garantem segurança entre threads quando dois processos de execução tentam atribuir valor à mesma variável compartilhada. Essa é uma questão separada de sincronização. O exemplo não representa o layout de memória virtual do sistema operacional nem a execução física de instruções na CPU. São abstrações posteriores, não pré-requisitos para aprender aliasing.

## Exercícios e verificação

1. Desenhe o grafo de referências de dois nomes e uma lista compartilhada. Diferencie mutação e reatribuição.
2. Crie duas listas diferentes que sejam iguais por conteúdo, mas não idênticas.
3. Construa tupla com uma lista interna e explique por que ela continua mutável indiretamente.
4. Compare a substituição de todas as células de uma matriz 2 por 3 com uma implementação que copia a matriz inteira.
5. Derive o custo O(RC) do congelamento e O(R+C) da atualização de uma célula.
6. Explique por que objetos retornados sobrevivem à função criadora e por que coleta de lixo não garante fechamento de arquivos [4].

Continue em [semântica de programação](/pt/topics/programming-semantics-contracts/), [recursão](/pt/topics/recursion-call-stack/) e [memória virtual](/pt/topics/processes-virtual-memory/).