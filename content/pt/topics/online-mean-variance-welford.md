---
id: online-mean-variance-welford
title: "Estatística numericamente estável: média online e variância de Welford"
description: "Derive atualizações em uma passagem, diferencie variâncias amostral e populacional e teste com frações exatas."
category: foundations
difficulty: foundational
updated: 2026-10-12
prerequisites: [floating-point-error-compensated-summation, discrete-counting-probability]
sources:
  - {title: "Welford (1962) — Corrected sums of squares and products", url: "https://doi.org/10.1080/00401706.1962.10490022", kind: "original research paper"}
  - {title: "Python standard library — statistics", url: "https://docs.python.org/3/library/statistics.html", kind: "official Python documentation"}
  - {title: "Python tutorial — Floating-point arithmetic", url: "https://docs.python.org/3/tutorial/floatingpoint.html", kind: "official language tutorial"}
  - {title: "Python standard library — fractions", url: "https://docs.python.org/3/library/fractions.html", kind: "official Python documentation"}
---
Média e variância são estatísticas elementares, mas implementar literalmente suas fórmulas pode gerar erros grandes na aritmética de ponto flutuante. O problema aparece quando medições compartilham **um deslocamento comum muito elevado, mas apresentam diferenças pequenas**. A recorrência de Welford calcula média corrente e soma corrigida de desvios quadráticos numa única passagem, sem subtrair momentos de segunda ordem enormes e quase iguais [1][2].

## Defina precisamente média e variância

Para n observações x1 até xn, a média aritmética é a soma dividida por n. A variância populacional representa a média das distâncias quadráticas em relação à média, usando denominador n. A variância amostral utiliza denominador n-1 quando n é maior que um. São definições matemáticas distintas, e não nomes intercambiáveis do resultado.

Uma sequência vazia não tem média aritmética nesse contrato. Uma sequência com um único valor possui média válida e variância populacional igual a zero, mas não tem variância amostral definida pelo denominador n-1. Esta aula escolhe devolver None para a variância amostral indisponível, em vez de dividir por zero silenciosamente.

Todas as observações do modelo executável precisam ser valores finitos de tipo Python float. A restrição evita misturar precisão arbitrária de inteiros, decimais e infinitos especiais sem declarar um modelo de representação.

## Por que a identidade dos segundos momentos pode falhar

Uma identidade matemática exata diz: variância = média dos valores ao quadrado menos quadrado da média. É tentador calcular uma soma de x e uma soma de x ao quadrado para subtrair dois resultados grandes. Porém, quando observações estão próximas de uma base elevada, as duas parcelas quase se igualam e a subtração perde dígitos significativos [3].

Considere três valores representáveis exatamente em binary64: 10^12+0.25, 10^12+0.50 e 10^12+0.75. A média é 10^12+0.50. Os desvios são -0.25, zero e 0.25. A soma de seus quadrados vale exatamente 0.125, logo a variância populacional é 1/24 e a amostral é 1/16.

A expressão média de x² menos média de x elevada ao quadrado subtrai duas quantidades próximas de 10^24 para encontrar diferença inferior a um. Com arredondamento comum de floats, pode devolver zero ou resultado extremamente errado. Isso não demonstra erro da identidade algébrica; mostra que expressões equivalentes podem ter estabilidade numérica distinta.

## Derive a recorrência da média online

Suponha que n-1 observações tenham média m. Ao receber x, a nova média é ((n-1)m+x)/n. Reorganizando, temos nova_media=m+(x-m)/n. A atualização exige somente média anterior, observação nova e quantidade. Não é preciso guardar toda a lista histórica.

Defina delta=x-m. Depois de calcular a média nova, tome delta2=x-nova_media. A soma corrigida de quadrados de Welford é atualizada por novo_M2=M2_anterior+delta*delta2 [1]. A variável M2 representa, em aritmética exata, a soma dos desvios quadráticos em relação à média atual.

Usar delta e delta2 evita calcular diretamente dois momentos enormes para depois subtraí-los. Não torna todas as operações exatas: média, deltas e correção continuam sujeitos à precisão finita dos floats.

## Demonstre a atualização dos desvios quadráticos

Antes da nova observação, suponha que M2 corresponda à soma de (xi-m)² dos primeiros n-1 valores. A nova média difere da anterior em delta/n. Ao recentrar os desvios anteriores, o termo cruzado da expansão vale zero porque a soma dos desvios em relação à antiga média é zero.

O deslocamento das observações anteriores contribui com (n-1)*(delta/n)². A observação nova contribui com (delta*(n-1)/n)². Somadas, essas parcelas simplificam para delta²*(n-1)/n, precisamente delta*(x-nova_media). Portanto, acrescentar delta*delta2 produz a nova soma corrigida de quadrados para todas as observações.

O invariante começa com n=0, média=0 e M2=0 como estado interno. A média inicial não é estatística definida externamente para entrada vazia. Cada valor aceito prolonga o invariante, e a divisão final fornece variância populacional ou amostral conforme o denominador.

## Estado executável e limites de falha

A implementação utiliza acumulador com quantidade, média corrente e M2. A operação add valida o novo dado e calcula os valores atualizados primeiro em variáveis locais. Verifica intermediários não finitos **antes de gravar nos campos do objeto**. Assim, um valor rejeitado ou overflow detectado conserva o estado anterior.

É garantia de segurança diante de exceções, não promessa de eliminar qualquer overflow. Subtrair valores finitos enormes de sinais opostos pode transbordar o intervalo finito do tipo. O exemplo sinaliza a falha em vez de tentar construir resultado enganoso.

Após pelo menos uma observação válida, summary devolve quantidade, média, variância populacional e variância amostral ou None. Chamadas repetidas ao resumo não alteram estado; isso permite consultar estatísticas ao longo de um fluxo ainda em processamento.

~~~python
import math

class OnlineMoments:
    def __init__(self):
        self.count = 0
        self.mean = 0.0
        self.m2 = 0.0

    def add(self, value):
        if type(value) is not float or not math.isfinite(value):
            raise ValueError("finite Python float required")
        next_count = self.count + 1
        delta = value - self.mean
        next_mean = self.mean + delta / next_count
        delta2 = value - next_mean
        next_m2 = self.m2 + delta * delta2
        if not all(math.isfinite(v) for v in
                   (delta, next_mean, delta2, next_m2)):
            raise OverflowError("nonfinite numerical intermediate")
        self.count = next_count
        self.mean = next_mean
        self.m2 = next_m2

    def summary(self):
        if self.count == 0:
            raise ValueError("no observations")
        return {
            "count": self.count,
            "mean": self.mean,
            "population_variance": self.m2 / self.count,
            "sample_variance":
                self.m2 / (self.count - 1) if self.count > 1 else None,
        }

acc = OnlineMoments()
for x in (1e12 + 0.25, 1e12 + 0.5, 1e12 + 0.75):
    acc.add(x)
result = acc.summary()
assert result["count"] == 3
assert result["mean"] == 1e12 + 0.5
assert math.isclose(result["population_variance"], 1 / 24,
                    rel_tol=1e-14)
assert result["sample_variance"] == 1 / 16
try:
    acc.add(float("nan"))
except ValueError:
    pass
else:
    raise AssertionError("NaN accepted")
assert acc.summary() == result
~~~

## Verifique com aritmética racional exata

As frações Python representam precisamente cada float de entrada por Fraction.from_float [4]. Para sequências pequenas, calcule média racional e desvios quadráticos exatos dos valores float representados e converta a referência final para float na comparação.

Essa referência responde a uma pergunta restrita: o algoritmo online aproximou de forma razoável as estatísticas exatas das entradas float? Não recupera medições reais desconhecidas que foram arredondadas antes da coleta. Correção algorítmica não significa automaticamente amostragem imparcial, representatividade ou conclusões causais válidas.

O exemplo com diferenças de um quarto é útil porque todos os valores são representáveis exatamente e as variâncias esperadas podem ser obtidas manualmente. Compare a saída com 1/24 e 1/16 usando tolerância explícita.

## Complexidade e garantias numéricas

Uma atualização online executa quantidade constante de operações e mantém três campos escalares: processar n observações custa O(n) tempo e O(1) armazenamento auxiliar no modelo de custo unitário. Guardar todos os dados para recalcular a variância exigiria O(n) memória, embora algoritmo de duas passagens também possa ser preciso quando os dados podem ser percorridos novamente.

A recorrência de Welford costuma ter estabilidade muito superior à subtração de segundos momentos enormes, mas **não é universalmente exata**. Precisão finita continua afetando resultados, e amplitudes adversas podem provocar overflow. A variância amostral não existe para n inferior a dois neste contrato; não substitua silenciosamente pela variância populacional.

Unidades importam: se observações são medidas em volts, a variância usa volts ao quadrado. O desvio padrão, calculado pela raiz quadrada da variância, retorna à unidade original. Nenhuma das duas grandezas demonstra, sozinha, confiabilidade do processo de medição.

## Exercícios e verificação independente

1. Calcule manualmente as duas variâncias das três observações com diferenças de um quarto.
2. Derive a recorrência da média a partir da fórmula aritmética comum.
3. Demonstre a atualização de M2 usando a soma nula dos desvios em relação à média anterior.
4. Compare a identidade de momentos brutos à recorrência de Welford em dados com grande deslocamento.
5. Confirme que entrada vazia falha e observação única não possui variância amostral.
6. Compare sequências curtas com oráculo Fraction exato e justifique tolerâncias e erros remanescentes.

Continue com [erros de ponto flutuante](/pt/topics/floating-point-error-compensated-summation/), [probabilidade exata](/pt/topics/discrete-counting-probability/) e [representação de dados](/pt/topics/data-types-bytes-and-representation/).
