---
id: algorithmic-problem-solving-method
title: "Raciocínio algorítmico: especificação, força bruta, invariantes e otimização"
description: "Aprenda um método de resolução de problemas ao derivar um algoritmo linear correto a partir de uma solução quadrática."
category: foundations
difficulty: foundational
updated: 2026-10-12
prerequisites: [programming-control-flow-functions, logic-proofs-invariants, complexity-analysis]
sources:
  - {title: "MIT OCW — Introduction to Algorithms (6.006)", url: "https://ocw.mit.edu/courses/6-006-introduction-to-algorithms-spring-2020/", kind: "university course"}
  - {title: "MIT Mathematics for Computer Science (6.042J)", url: "https://ocw.mit.edu/courses/6-042j-mathematics-for-computer-science-spring-2015/", kind: "university course and textbook"}
  - {title: "Python documentation — Built-in types", url: "https://docs.python.org/3/library/stdtypes.html", kind: "official language documentation"}
---
Algoritmo não é somente código que devolve a resposta esperada num exemplo. É um **procedimento finito com domínio de entradas e resultado observável especificados**, acompanhado de uma justificativa de correção. Soluções eficientes começam pela compreensão do problema, não pela memorização de receitas. Os fundamentos de análise de algoritmos distinguem correção, representação, custo e implementação [1][2]. Um problema pequeno de otimização servirá para derivar todo o raciocínio, da especificação à prova.

## Defina o contrato antes de escolher estruturas de dados

Dada uma sequência ordenada de preços diários, encontre um dia de compra e um dia **posterior** de venda que maximizem lucro estritamente positivo. Comprar e vender no mesmo dia é proibido. Os preços são inteiros não negativos em unidades hipotéticas; impostos, conversão monetária, taxas e venda a descoberto ficam de fora. Caso não exista lucro positivo, devolva None. Em empates de lucro máximo, selecione primeiro o menor índice de compra e depois o menor índice de venda. O retorno é uma tripla de índices e lucro.

A especificação elimina ambiguidades. Numa sequência decrescente não existe operação lucrativa válida; não se deve devolver lucro negativo só porque a venda pode acontecer. Preços iguais não geram lucro positivo. Zero é preço permitido. Inteiros evitam imprecisões binárias desnecessárias neste exemplo, mas aplicações financeiras reais exigem políticas de precisão, moeda e limites de magnitude.

## Transforme exemplos em afirmações matemáticas

Na sequência [9,1,5,3,6], comprar no índice 1 e vender no índice 4 gera lucro 6−1=5. Vender no índice 2 produziria apenas 4. Comprar no índice 0 não melhora a resposta, pois todos os preços posteriores são inferiores a 9. O algoritmo deve impor compra < venda; subtrair apenas o menor preço global do maior preço global pode gerar resultado impossível se o maior ocorrer primeiro.

A sequência [8,7,7,3] mostra a regra de ausência de lucro. A sequência [3,1,4,1,4] deixa explícito o desempate: (1,2) precisa vencer pares equivalentes que ocorram depois. Casos de borda pertencem à especificação, não são complementos opcionais depois do algoritmo principal.

## Comece pela enumeração exaustiva correta

Uma solução de referência enumera todos os pares ordenados (compra, venda) com compra < venda, calcula preço[venda] − preço[compra] e guarda o par positivo com maior lucro. Para cumprir o desempate, percorra índices de compra e depois índices de venda em ordem crescente, atualizando somente diante de lucro **estritamente** maior. Como todos os pares permitidos são comparados, o resultado é correto por exaustão. Para n elementos existem n(n−1)/2 pares válidos, logo O(n²) tempo e O(1) memória adicional no modelo de aritmética constante.

Força bruta não é fracasso. Ela serve de oráculo independente para entradas curtas e esclarece o que uma otimização precisa preservar. Demonstrar que todos os pares são examinados costuma ser mais simples que provar a versão otimizada, motivo pelo qual é valiosa para testes diferenciais.

## Derive uma recorrência usando o espaço de busca

Fixe um dia de venda s. O melhor dia anterior de compra será algum índice b < s no qual o preço é mínimo. Portanto, não é necessário revisitar todos os dias anteriores para avaliar uma venda: basta conhecer o menor preço anterior e seu **primeiro** índice. Depois de avaliar a venda em s, o preço atual pode se tornar mínimo para futuras vendas. A ordem das operações é importante: o dia atual precisa ser considerado como venda **antes** de passar a ser elegível como compra de dias posteriores.

Mantenha três informações: menor preço entre os dias anteriores processados, primeiro índice desse mínimo e melhor par lucrativo observado. As duas primeiras resumem todo o prefixo relevante para lucros futuros; não é necessário armazenar todos os pares anteriores.

~~~python
def best_trade(prices):
    """Earliest (buy_index, sell_index, profit), or None if no gain."""
    if not isinstance(prices, (list, tuple)):
        raise TypeError("prices must be a sequence")
    for price in prices:
        if type(price) is not int or price < 0:
            raise ValueError("prices must be nonnegative integers")
    if len(prices) < 2:
        return None

    min_price = prices[0]
    min_index = 0
    best_profit = 0
    best = None

    for sell in range(1, len(prices)):
        profit = prices[sell] - min_price
        if profit > best_profit:
            best_profit = profit
            best = (min_index, sell, profit)
        if prices[sell] < min_price:
            min_price = prices[sell]
            min_index = sell
    return best

assert best_trade([]) is None
assert best_trade([5]) is None
assert best_trade([9, 1, 5, 3, 6]) == (1, 4, 5)
assert best_trade([8, 7, 7, 3]) is None
assert best_trade([3, 1, 4, 1, 4]) == (1, 2, 3)
assert best_trade([0, 1, 0, 2]) == (0, 3, 2)
try:
    best_trade([1, True, 4])
except ValueError:
    pass
else:
    raise AssertionError("boolean is not a price")
~~~


## Prove invariante e término

Antes da iteração s, variando de 1 a n−1, `min_price` é o mínimo de prices[0:s] e `min_index` sua primeira ocorrência. `best` é o primeiro par na ordem lexicográfica entre os pares lucrativos cuja venda ocorre antes de s e que atingem o maior lucro encontrado. Inicialmente s=1, existe um único valor no prefixo e nenhuma venda anterior válida: a propriedade é verdadeira.

Na iteração s, `prices[s] - min_price` é o maior lucro possível para vendas naquele dia. Se for estritamente maior que `best_profit`, substitui o par. Se empatar, não substitui: dias anteriores de venda já foram avaliados, e o índice do primeiro mínimo foi preservado porque só se atualiza diante de preço estritamente menor. Finalmente, compare prices[s] ao mínimo para preparar a propriedade da iteração s+1. Após avaliar a última venda, o par escolhido é globalmente ótimo. O laço avança uma unidade até um limite fixo, portanto termina.

Há no máximo n−1 iterações e n validações; tempo O(n) com operações inteiras de custo fixo. O estado utiliza quantidade constante de escalares: O(1) de memória auxiliar. Em Python, inteiros não possuem limite fixo de bits, então uma análise detalhada incluiria o tamanho dos operandos; O(n) segue o modelo usual de custo unitário [1].

## Rastreie a execução

Em [9,1,5,3,6], o mínimo inicial é (preço=9, índice=0). Na venda do índice 1, o lucro é negativo; em seguida o novo mínimo passa a ser (1,1). Vender no índice 2 rende 4, criando o melhor candidato (1,2,4). O índice 3 produz apenas 2, sem alteração. O índice 4 rende 5, levando à resposta (1,4,5).

Um erro frequente é atualizar o mínimo antes de avaliar a venda e esquecer que compra e venda devem ocorrer em dias distintos. Com exigência de lucro positivo, esse erro pode não aparecer em exemplos comuns, embora a prova do invariante fique incorreta. Outro erro é substituir o índice do mínimo quando o preço é igual, quebrando o desempate pelo primeiro dia.

## Testes e limites das evidências

Compare a implementação otimizada ao oráculo quadrático para todas as sequências curtas de um alfabeto pequeno. Isso detecta erros de índice, desempate e sequências decrescentes. Não constitui prova para todos os comprimentos e magnitudes: o invariante fornece o argumento geral. Testes aleatórios complementam a exploração exaustiva pequena. Em linguagens com inteiros de largura fixa, considere overflow e escolha aritmética verificada ou outra representação.

Nem todo problema admite esse resumo por mínimo de prefixo. Aqui ele funciona porque vendas futuras dependem dos dias anteriores somente por seu menor preço elegível. Restrições sobre múltiplas compras, quantidade de operações ou taxas variáveis podem exigir estado adicional e programação dinâmica. A otimização deve nascer de uma propriedade demonstrada, não de uma estrutura de dados escolhida por hábito.

## Exercícios e verificação

1. Implemente o algoritmo quadrático e compare as triplas de todas as sequências com até cinco elementos de {0,1,2,3}, incluindo empates.
2. Demonstre por que atualizar `min_index` diante de preço **igual** modifica o desempate.
3. Altere o contrato para permitir prejuízo. Explique como a inicialização deve mudar.
4. Acrescente taxa fixa por operação. Identifique quais partes do invariante permanecem e como muda o critério de lucro positivo.
5. Mostre por que subtrair máximo global de mínimo global não respeita a ordem temporal em [10,1,4].
6. Compare as complexidades de enumeração exaustiva e mínimo de prefixo, explicitando n e hipóteses sobre operações inteiras.

Relacionados: [controle de fluxo](/pt/topics/programming-control-flow-functions/), [provas](/pt/topics/logic-proofs-invariants/), [complexidade](/pt/topics/complexity-analysis/) e [arrays](/pt/topics/arrays-and-strings/).