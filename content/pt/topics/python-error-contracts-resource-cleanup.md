---
id: python-error-contracts-resource-cleanup
title: "Contratos de erro em Python: exceções e liberação de recursos"
description: "Defina entradas inválidas, propague exceções e verifique limpeza com context managers e streams reproduzíveis."
category: foundations
difficulty: foundational
updated: 2026-10-12
prerequisites: [programming-semantics-contracts, modular-programming-interfaces]
sources:
  - {title: "Python tutorial — Errors and Exceptions", url: "https://docs.python.org/3/tutorial/errors.html", kind: "official tutorial"}
  - {title: "Python language reference — The with statement", url: "https://docs.python.org/3/reference/compound_stmts.html#the-with-statement", kind: "official language reference"}
  - {title: "Python standard library — contextlib", url: "https://docs.python.org/3/library/contextlib.html", kind: "official library documentation"}
---
Uma função que devolve resultados corretos para entradas válidas, mas esconde falhas, gera diagnósticos enganosos ou abandona recursos adquiridos não possui contrato completo. Exceções e context managers de Python estabelecem **o que pode falhar, como o erro se propaga e quais ações de liberação ainda ocorrem**. São fundamentos da programação, não recursos exclusivos de frameworks [1][2].

## Especifique sucesso e falha conjuntamente

O exemplo aceita representação decimal ASCII canônica de uma contagem entre zero e 1000. Strings válidas incluem 0, 7 e 1000. Exemplos inválidos incluem texto vazio, zeros iniciais como 07, valores negativos, 1001 e algarismos não ASCII. São decisões da aplicação: a conversão padrão de inteiros em Python é mais permissiva.

Uma interpretação bem-sucedida devolve inteiro não negativo. Um registro malformado lança RecordError, derivado de ValueError. Separar entrada inválida de falha de leitura do sistema operacional importa porque o chamador pode recuperar-se de modos diferentes. Um erro não deve ser disfarçado de contagem válida igual a zero [1].

O contrato também estabelece que o parser não modifica dados do chamador nem devolve resultado parcial. Definir formas permitidas e tipos antes de implementar facilita a elaboração de testes positivos e negativos.

## Exceções possuem fluxo de controle próprio

Lançar exceção interrompe a avaliação normal até encontrar tratador compatível. Um tratador pode recuperar, relançar ou adicionar contexto. Capturar todas as Exception e devolver valor padrão pode esconder defeitos de programação, falta de recursos e dados corrompidos sob uma resposta aparentemente válida.

O parser lança erro nomeado quando seu contrato de dados é violado. A função leitora captura especificamente esse erro para acrescentar o número da linha. Emprega encadeamento de exceções, preservando a causa original. Erros de abertura ou leitura de arquivo devem conservar seu significado em vez de virar entrada decimal malformada [1].

Captura ampla só se justifica numa fronteira externa que consiga relatar falhas sem destruir diagnósticos. A simples presença de try não representa recuperação adequada.

## Efeitos externos e trabalho parcial

Considere várias linhas contendo contagens. A função mantém acumulador local. O invariante após k registros aceitos afirma que o acumulador corresponde à soma desses registros e cada valor pertence ao intervalo entre zero e 1000. Processar outro registro válido preserva a propriedade.

Quando uma linha é inválida, ocorre exceção antes do retorno. O chamador nunca observa total parcialmente confirmado. Isso **não** significa que alterações externas em banco de dados ou arquivo seriam revertidas: variáveis locais e efeitos persistentes apresentam semânticas distintas.

Uma fonte vazia corresponde à soma zero no contrato escolhido. Cada linha não vazia contém uma contagem e opcionalmente um terminador convencional. Linha vazia entre registros é inválida. Numerar a partir de um melhora os diagnósticos sem modificar a fonte.

## Context managers delimitam propriedade de recursos

Um context manager possui comportamento de entrada e saída. A instrução with invoca seu método de saída quando o bloco controlado termina normalmente ou lança exceção, desde que o gerenciador tenha sido iniciado com sucesso [2]. Um gerenciador de arquivo normalmente fecha o arquivo; outro pode liberar uma trava. A ação, entretanto, precisa ser implementada corretamente.

Um context manager pode suprimir uma exceção pelo valor devolvido pelo método de saída. Encontrar with no código não prova que todo erro será propagado. Liberar recurso e suprimir exceção são obrigações diferentes. A biblioteca contextlib fornece recursos para implementar esses padrões de ciclo de vida [3].

A função recebe fábrica de gerenciador que fornece linhas. O teste injeta StringIO; uma aplicação pode injetar função que abre arquivo. A separação deixa a validação independente do sistema de arquivos e permite conferir liberação usando um objeto observável.

## Exemplo executável com cadeia de erros

A implementação rejeita linhas que não sejam strings em vez de convertê-las silenciosamente. Confere dígitos decimais canônicos e intervalo antes de somar. Uma segunda linha incorreta produz erro com número de linha e mantém a causa inicial acessível.

~~~python
from io import StringIO

class RecordError(ValueError):
    """A record violates the count contract."""

def parse_count(text):
    if (type(text) is not str or not text or len(text) > 4
            or not text.isascii() or not text.isdecimal()
            or (len(text) > 1 and text[0] == "0")):
        raise RecordError("expected canonical ASCII decimal")
    count = int(text)
    if count > 1000:
        raise RecordError("count exceeds 1000")
    return count

def total_from_source(factory):
    total = 0
    with factory() as lines:
        for number, line in enumerate(lines, 1):
            if type(line) is not str:
                raise TypeError("text lines required")
            record = line.removesuffix("\n").removesuffix("\r")
            try:
                total += parse_count(record)
            except RecordError as exc:
                raise RecordError(f"line {number}: {exc}") from exc
    return total

assert total_from_source(lambda: StringIO("4\n9\n0\n")) == 13
assert total_from_source(lambda: StringIO("")) == 0
try:
    total_from_source(lambda: StringIO("4\n01\n"))
except RecordError as exc:
    assert "line 2:" in str(exc)
    assert isinstance(exc.__cause__, RecordError)
else:
    raise AssertionError("invalid record accepted")
~~~

O leitor recebe linhas textuais, não blocos binários arbitrários. Cabe ao chamador determinar a política de decodificação no limite do arquivo. Uma fonte que forneça objeto diferente de string lança TypeError, apontando uso incorreto da interface, não contagem malformada.

## Demonstração de correção e custos

Interpretar um registro examina no máximo quatro caracteres ASCII. Com n caracteres distribuídos por r registros, o processamento faz O(n+r) operações básicas, usando O(1) variáveis escalares auxiliares sob hipóteses de aritmética de tamanho limitado. Buffers da fonte textual pertencem à própria abstração de entrada.

O invariante demonstra que o total normalmente devolvido corresponde à soma de todas as contagens válidas. Dados inválidos não devolvem total porque a exceção encerra o laço. A semântica de with assegura a invocação do método de saída após entrada bem-sucedida, mesmo em erro. Testes devem verificar a **liberação observável**, pois um gerenciador personalizado incorreto pode falhar ao fechar seu recurso.

Uma fábrica pode lançar exceção antes de fornecer o gerenciador. Nesse caso, a função leitora não chegou a entrar no contexto. Qualquer recurso parcialmente adquirido é responsabilidade da fábrica.

Blocos finally também expressam liberação, mas a limpeza pode lançar exceção e ocultar o erro original. Context manager não garante rollback de transação, e fechar arquivo não comprova persistência de dados após falha de energia. São contratos distintos de armazenamento.

## Exercícios e verificação

1. Classifique 0, 07, 1001, texto vazio e algarismos não ASCII pelo contrato.
2. Rastreie o acumulador antes de uma terceira linha inválida e explique por que não há retorno.
3. Crie gerenciador falso que registre entrada e saída nos caminhos normais e de exceção.
4. Faça esse gerenciador suprimir exceções e explique como isso pode esconder dados malformados.
5. Forneça iterador que lance OSError e confirme que o erro não se converte em RecordError.
6. Diferencie liberação de recurso e durabilidade de dados anteriormente gravados.

Continue por [semântica de programação](/pt/topics/programming-semantics-contracts/), [arquivos e JSON](/pt/topics/python-files-utf8-json-validation/) e [estratégias de testes](/pt/topics/testing-strategies/).
