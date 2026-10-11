---
id: programming-semantics-contracts
title: "Semântica de programação, aliasing e contratos executáveis"
description: "Analise avaliação, igualdade, mutação, exceções e contratos de funções antes de aplicar recursos da linguagem em algoritmos."
category: foundations
difficulty: foundational
updated: 2026-10-10
prerequisites: [logic-proofs-invariants]
sources:
  - {title: "Python Language Reference — Execution Model", url: "https://docs.python.org/3/reference/executionmodel.html", kind: "official language reference"}
  - {title: "Python Language Reference — Expressions", url: "https://docs.python.org/3/reference/expressions.html", kind: "official language reference"}
  - {title: "Python Language Reference — Simple Statements", url: "https://docs.python.org/3/reference/simple_stmts.html", kind: "official language reference"}
  - {title: "Python Standard Library — unittest", url: "https://docs.python.org/3/library/unittest.html", kind: "official language documentation"}
---
Duas implementações da mesma fórmula matemática podem ter comportamentos distintos porque a linguagem determina ordem de avaliação, conversões, identidade de objetos, mutação, propagação de exceções e tempo de vida dos recursos. O engenheiro precisa distinguir garantias da especificação e comportamentos observados numa implementação. Este capítulo usa contratos concretos de Python, sem supor que cada regra também valha em C++, JavaScript, Rust ou Java. A referência da linguagem documenta associação de nomes, expressões, operadores e execução [1][2].

## Valores, objetos, identidade e igualdade

Um nome Python está associado a um objeto; atribuição não significa, em geral, cópia desse objeto. Igualdade compara valores segundo a operação oferecida pelo objeto; identidade pergunta se duas referências designam o mesmo objeto. São propriedades diferentes, mesmo que às vezes produzam respostas coincidentes. Uma coleção contém referências a objetos potencialmente mutáveis, portanto copiar a coleção externa não copia automaticamente todos os objetos alcançáveis [1][2].

~~~python
original = [[1], [2]]
raso = original.copy()
assert original == raso
assert original is not raso
assert original[0] is raso[0]
raso[0].append(3)
assert original == [[1, 3], [2]]
~~~

A pós-condição "a lista copiada é independente de todas as listas internas" é falsa: a lista interna continua compartilhada. Uma cópia profunda assume outro contrato e nem sempre é adequada para grafos arbitrários de objetos. Melhor explicitar propriedade, compartilhamento e regras de mutação do que inserir cópias por costume.

## Ordem de avaliação e curto-circuito

Uma expressão tem valor e pode produzir efeitos. Em Python, os operadores and e or avaliam apenas o necessário e retornam um operando; não precisam retornar bool. Isso afeta valores padrão e validação de entrada, sobretudo quando zero e string vazia são valores válidos, embora avaliados como falsos em testes de verdade [2].

~~~python
def escolher_porta(solicitada, padrao):
    return padrao if solicitada is None else solicitada

assert escolher_porta(0, 8080) == 0
assert escolher_porta(None, 8080) == 8080
assert (0 or 8080) == 8080
assert (3 and 5) == 5
~~~

Substituir um teste de ausência por "solicitada or padrao" altera o comportamento para zero. Logo, **um atalho baseado em truthiness não equivale a um contrato explícito para valor opcional**. Operandos com efeitos colaterais criam outras sutilezas, pois parte das chamadas pode ser omitida pelo curto-circuito. Em entrevistas e APIs, diferencie ausente, vazio, nulo e inválido.

## Argumentos mutáveis, aliasing e raciocínio local

Os parâmetros são associados aos objetos passados nas chamadas. Um objeto mutável declarado como valor padrão pode permanecer compartilhado entre chamadas, pois a expressão padrão é avaliada na definição da função, e não a cada execução. Trata-se de semântica da linguagem, não apenas de convenção de nomes [2].

~~~python
def acumular(valor, coletados=None):
    if coletados is None:
        coletados = []
    coletados.append(valor)
    return coletados

um = acumular(1)
dois = acumular(2)
assert um == [1] and dois == [2]
assert um is not dois
externo = []
assert acumular(3, externo) is externo
assert externo == [3]
~~~

O contrato intencionalmente modifica uma lista explicitamente fornecida, mas cria outra quando nenhuma lista é passada. Seria incorreto afirmar que a função é pura ou que todos os resultados são independentes das entradas. Uma API alternativa pode copiar a entrada, retornar uma tupla imutável ou documentar transferência de propriedade. Cada decisão equilibra custos de alocação e efeitos observáveis.

## Erros também pertencem ao contrato

Pré-condições devem informar o que acontece com entradas inválidas. Uma divisão com divisor positivo pode rejeitar zero por ValueError, enquanto outra API pode devolver um objeto de erro. Deixar ZeroDivisionError escapar pode ser aceitável internamente, mas não se uma interface pública promete erros estruturados. Exceções são parte do fluxo de controle e da interface, não um detalhe separado dos resultados corretos [3].

~~~python
def dividir_por_contagem_positiva(total, quantidade):
    if type(total) not in (int, float) or type(quantidade) is not int:
        raise TypeError("total numerico e quantidade inteira obrigatorios")
    if quantidade <= 0:
        raise ValueError("quantidade deve ser positiva")
    return total / quantidade

assert dividir_por_contagem_positiva(9, 3) == 3.0
for invalido in (0, -1):
    try:
        dividir_por_contagem_positiva(9, invalido)
        raise AssertionError("quantidade invalida aceita")
    except ValueError:
        pass
try:
    dividir_por_contagem_positiva(9, "3")
    raise AssertionError("tipo incorreto aceito")
except TypeError:
    pass
~~~

O exemplo valida apenas positividade da quantidade e tipos básicos. Não impõe que o total seja não negativo; esse requisito não pode ser inferido do nome da função. NaN, infinito, overflow em outras linguagens, aritmética racional exata e regras de arredondamento precisam de decisões explícitas. Quando o nome promete uma propriedade, a validação ou a documentação precisam cumpri-la.

## Invariantes e substituição em interfaces

Considere uma função que processa comandos em lote. Um invariante útil é "cada comando aceito produz exatamente um resultado ou a operação comunica falha". Trata-se de contrato sobre comportamento observável, não sobre herança de classes. Uma implementação substituta que elimina comandos silenciosamente viola o contrato, embora tenha a mesma assinatura.

A mutação dificulta substituição: um processador que altera a entrada do chamador pode quebrar consumidores que dependem de argumentos intactos. A substituibilidade comportamental exige compatibilidade de pré-condições, pós-condições e comportamento de falha. Antes de aplicar SOLID ou padrões de projeto, é necessário definir obrigações observáveis. Custos de despacho dinâmico, cópia e alocação devem ser considerados depois da correção.

Para uma função pura, uma propriedade importante é a transparência referencial: substituir uma chamada por seu resultado não muda o comportamento observável dentro do modelo adotado. A função acumular, quando recebe uma lista existente, deliberadamente não é pura. Entender isso evita erros em cache, testes e paralelização.

## Verificação com exemplos e testes independentes

Executar algumas asserções detecta regressões, mas não comprova comportamento para todos os objetos Python ou padrões de acesso concorrente. Os testes devem cobrir limites, entradas inválidas e transições de estado. O módulo unittest permite métodos de teste isolados, fixtures e expectativas explícitas de exceções [4]. Para uma API de listas, compare ausência de argumento com lista vazia explícita, chamadas repetidas, objetos internos compartilhados e tipos incorretos.

Um oráculo independente ajuda a descobrir defeitos: um parser pode ser confrontado com implementação de referência mais simples; um otimizador pode ser comparado com enumeração exaustiva de entradas pequenas. O oráculo deve evitar repetir a mesma lógica defeituosa da implementação principal. Verifique também efeitos proibidos, não apenas o valor retornado. "Não modificar a entrada" é um contrato; "usar dicionário" é uma decisão de implementação.

Não dependa de IDs internos dos objetos, escolhas de internamento ou tempos de execução não garantidos. O teste correto observa aquilo que a linguagem ou a API promete, isolando detalhes incidentais.

## Exercícios

1. Explique o resultado de atribuir uma lista aninhada a dois nomes e copiar apenas a lista externa. **Resposta:** as coleções externas podem diferir, mas os objetos internos mutáveis continuam compartilhados e visíveis por ambas.
2. Justifique por que "solicitada or padrao" não significa "usar padrão somente se solicitada for None". **Resposta:** zero, False e coleções vazias são falsos em contexto lógico, mas podem ser escolhas legítimas.
3. Especifique integralmente uma função de mediana: domínio, comportamento para entrada vazia, política para comprimentos pares, mutação e custos. **Critério:** convenções diferentes para tamanhos pares definem contratos distintos.
4. Proponha teste para um processador que promete não mutar entradas. **Resposta:** preserve uma cópia suficientemente profunda da estrutura documentada, execute e compare; uma cópia rasa não detecta todas as mutações internas.

Aqui são demonstrados o comportamento documentado de Python e exemplos específicos. Modelos de memória de outras linguagens, compilação, máquinas virtuais e concorrência exigem estudo próprio.