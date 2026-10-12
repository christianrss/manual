---
id: floating-point-error-compensated-summation
title: "Cálculo em ponto flutuante: arredondamento, cancelamento e soma compensada"
description: "Analise aproximação binária, adição não associativa e soma compensada de Neumaier com oráculos racionais exatos."
category: foundations
difficulty: foundational
updated: 2026-10-12
prerequisites: [data-types-bytes-and-representation, complexity-analysis]
sources:
  - {title: "Python tutorial — Floating-point arithmetic", url: "https://docs.python.org/3/tutorial/floatingpoint.html", kind: "official language tutorial"}
  - {title: "Python standard library — math.fsum and isclose", url: "https://docs.python.org/3/library/math.html", kind: "official library documentation"}
  - {title: "Python standard library — fractions.Fraction", url: "https://docs.python.org/3/library/fractions.html", kind: "official library documentation"}
---
A adição é associativa nos números reais, mas a aritmética com precisão armazenada finita não preserva sempre essa propriedade. A diferença importa quando medições de magnitudes muito distintas são combinadas. Um programa pode implementar uma fórmula matematicamente correta e ainda devolver resultado impreciso porque **a representação e a ordem das operações de ponto flutuante fazem parte do cálculo**. Esta aula deriva os mecanismos de erro e uma melhoria limitada, sem afirmar que um algoritmo aproximado garante aritmética real exata [1][2].

## A aproximação binária ocorre antes do cálculo

Muitos valores float de Python são representados por frações binárias de precisão limitada. O número decimal um décimo não possui representação fracionária finita em base dois. Portanto, o float escrito como 0.1 é um valor binário próximo, mas não corresponde exatamente à fração 1/10. Imprimir 0.1 não revela todos os bits da representação. O método float.as_integer_ratio e Fraction.from_float exibem o racional exato representado por determinado float finito [1][3].

Esse é o *erro de representação*: uma entrada matemática precisa ser aproximada ao conjunto de valores armazenáveis antes da aritmética. Um *erro de arredondamento* adicional pode ocorrer quando uma operação produz valor entre duas representações possíveis. Converter float já arredondado em Decimal ou Fraction preserva o valor armazenado; não recupera o dado decimal original desconhecido.

Para contagens de centavos, inteiros ou Decimal configurado adequadamente podem ser superiores. Para medições físicas com ruído, float costuma ser apropriado quando existe tolerância de erro declarada. Escolher o tipo requer especificar os erros permitidos pela aplicação.

## Por que a soma de floats não é associativa

Na aritmética exata, (a+b)+c equivale a a+(b+c). Em ponto flutuante, cada operação intermediária pode ser arredondada. Com a=10^16, b=1 e c=-10^16, somar a e b pode eliminar completamente a contribuição pequena de b. A adição seguinte pode devolver zero, embora a soma matemática exata seja um.

Se os valores forem reagrupados ou uma soma mais cuidadosa for usada, essa unidade poderá ser recuperada em alguns casos. É a **perda de significância por cancelamento**. O fenômeno não depende apenas de constantes enormes e artificiais: subtrair medições próximas ou acumular milhões de termos também pode expor problemas semelhantes.

Logo, comparar floats por igualdade não é regra universal adequada para aproximações calculadas independentemente. A função math.isclose usa tolerâncias absolutas e relativas definidas pelo chamador; não conhece o orçamento de incerteza científico necessário [2]. Comparações próximas de zero frequentemente exigem tolerância absoluta justificada.

## Construa uma referência exata para os testes

Uma regra de verificação numérica é comparar com representação independente quando for viável. Para floats finitos, Fraction.from_float transforma o valor representado em racional exato. Somar esses racionais produz a soma matemática exata dos **valores float que já foram arredondados**, não das medições originais desconhecidas.

A distinção é essencial. Um oráculo racional exato demonstra se a rotina introduziu erro aritmético adicional, mas não garante precisão do sensor que forneceu a medição. É teste independente de cálculo, não procedimento de calibração.

Para entradas grandes, a soma racional exata pode ser cara em memória e processamento. É mais adequada a contraexemplos pequenos e casos limitados de teste que à execução habitual de aplicações numéricas.

## Acumulação direta e soma com compensação

A soma direta começa em zero e acrescenta cada termo ao acumulador. Quando uma contribuição pequena é eliminada por arredondamento, normalmente não pode ser recuperada. A variante de Neumaier da soma compensada mantém um termo adicional de correção. A cada iteração compara as magnitudes do acumulador anterior e do termo atual para estimar o resíduo perdido no arredondamento.

A própria correção também é float. A compensação frequentemente melhora resultados com forte cancelamento, mas **não promete resposta exata para qualquer ordem, magnitude ou conjunto de dados**. A função nativa math.fsum acompanha somas parciais de maneira mais completa e geralmente é a escolha apropriada em Python quando a precisão da soma importa [1][2].

Os exemplos executáveis aceitam somente valores exatamente do tipo float e finitos. Essa restrição rejeita inteiros e booleanos intencionalmente para manter um único modelo de representação. Caso um intermediário fique não finito, as funções lançam OverflowError em vez de devolver infinito ou NaN como resultado válido.

## Exemplo executável e cancelamento

O código define uma soma direta da esquerda para a direita e uma soma compensada de Neumaier, ambas com o mesmo contrato de valores finitos. Para a sequência 10^16, 1, -10^16, a soma direta devolve zero, enquanto a compensação devolve um. A soma racional independente e math.fsum também devolvem um para essas entradas exatamente representáveis.

Um segundo exemplo compara o racional exato representado pelo float 0.1 com a fração matemática um décimo. Não são iguais; reorganizar um laço de somatório não consegue eliminar o erro inicial de representação.

~~~python
import math
from fractions import Fraction

def check_float(value):
    if type(value) is not float or not math.isfinite(value):
        raise ValueError("finite Python floats only")
    return value

def naive_sum(values):
    total = 0.0
    for item in values:
        value = check_float(item)
        total += value
        if not math.isfinite(total):
            raise OverflowError("nonfinite intermediate sum")
    return total

def neumaier_sum(values):
    total = 0.0
    correction = 0.0
    for item in values:
        value = check_float(item)
        next_total = total + value
        if not math.isfinite(next_total):
            raise OverflowError("nonfinite intermediate sum")
        if abs(total) >= abs(value):
            correction += (total - next_total) + value
        else:
            correction += (value - next_total) + total
        if not math.isfinite(correction):
            raise OverflowError("nonfinite correction")
        total = next_total
    result = total + correction
    if not math.isfinite(result):
        raise OverflowError("nonfinite final sum")
    return result

values = [1e16, 1.0, -1e16]
assert naive_sum(values) == 0.0
assert neumaier_sum(values) == 1.0
assert math.fsum(values) == 1.0
assert sum((Fraction.from_float(v) for v in values)) == 1
assert Fraction.from_float(0.1) != Fraction(1, 10)
~~~

## Invariante de laço e limites

Na soma direta, o estado acumulado após i iterações é o resultado das adições de ponto flutuante, da esquerda para a direita, nos primeiros i valores. É descrição exata do programa implementado, não da soma matemática real.

Na soma compensada, o estado total+correção procura aproximar a soma exata das entradas processadas. A atualização da correção recupera parte dos resíduos de arredondamento de cada operação. A derivação algébrica considera um modelo usual de arredondamento; a correção também está sujeita à precisão finita. O invariante descreve a recorrência, não um limite universal de erro zero.

O término decorre de consumir um elemento por iteração de uma sequência finita. Para n entradas, ambos fazem O(n) passos escalares e usam O(1) estado auxiliar no modelo de custo unitário. Um teste não deve confundir melhoria frequente com prova de superioridade monotônica para todos os dados.

## Casos-limite, validação e tolerâncias

Entradas não finitas exigem política explícita. Infinito pode esconder um cancelamento matematicamente finito, enquanto comparações com NaN são falsas até quando outro operando é NaN. Rejeitar esses valores é uma escolha válida da aplicação, não regra de toda computação científica.

Uma tolerância apenas relativa não é adequada quando o resultado verdadeiro é zero. Orçamentos de erro relevantes podem usar tolerância absoluta, relativa, incerteza de medição ou distância em ulps, conforme o domínio. É necessário explicar as unidades da tolerância e verificar valores próximos dos limites de decisão.

Somas extremas podem transbordar mesmo quando cada termo é finito, e o exemplo rejeita essa condição. A soma compensada não afirma lidar com todo overflow nem produzir arredondamento correto em qualquer ambiente.

## Exercícios e verificação independente

1. Determine o racional representado exatamente por float 0.1 e compare-o com Fraction(1,10).
2. Explique por que acrescentar 1 a 10^16 perde informação, mas somar um quarto a inteiro pequeno pode não perder.
3. Compare as duas rotinas e math.fsum na sequência de cancelamento construída.
4. Permute os três termos e explique por que a ordem pode alterar o resultado.
5. Rejeite NaN, infinito e Boolean e diferencie entrada inválida de intermediário com overflow.
6. Escolha tolerâncias absoluta e relativa para um problema de medição física e justifique suas unidades.

Continue com [representação de dados](/pt/topics/data-types-bytes-and-representation/), [variância estável online](/pt/topics/online-mean-variance-welford/) e [complexidade](/pt/topics/complexity-analysis/).
