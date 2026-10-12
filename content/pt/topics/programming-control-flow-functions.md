---
id: programming-control-flow-functions
title: "Fundamentos de programação: controle de fluxo, funções e invariantes"
description: "Aprenda condicionais, laços, funções, escopo e invariantes ao derivar um algoritmo linear de arrays com casos-limite."
category: foundations
difficulty: foundational
updated: 2026-10-12
prerequisites: []
sources:
  - {title: "Python tutorial — Control flow tools", url: "https://docs.python.org/3/tutorial/controlflow.html", kind: "official programming tutorial"}
  - {title: "Python language reference — Compound statements", url: "https://docs.python.org/3/reference/compound_stmts.html", kind: "official language reference"}
  - {title: "Python language reference — Execution model", url: "https://docs.python.org/3/reference/executionmodel.html", kind: "official language reference"}
---
Um programa executa **instruções em ordem definida**, avalia expressões e altera a próxima instrução por condições, laços e chamadas de funções. Esses conceitos precedem classes, padrões, bancos de dados e sistemas distribuídos. Sem eles, mesmo algoritmos pequenos parecem corretos enquanto tratam incorretamente entradas vazias ou repetem trabalho. A documentação do Python especifica controle de fluxo, blocos e avaliação [1][2]. O objetivo é compreender os mecanismos, não apresentar outro framework.

## Expressões, condições e desvios

Uma *expressão* produz um valor; uma *instrução* governa a execução ou modifica associações e estado. Por exemplo, `quantidade > 0` devolve um booleano e `if quantidade > 0:` usa o resultado para selecionar um bloco. O bloco `else` é executado se a condição é falsa. Python utiliza indentação para delimitar blocos: ela participa da sintaxe, não é somente formatação [1].

Não confunda predicado com efeito. `if items:` verifica se a coleção é considerada verdadeira; `if items is None:` verifica especificamente a ausência representada por None. Não são equivalentes: uma lista vazia pode ser entrada válida, enquanto None pode ser inválido. A condição deve responder à pergunta de negócio correta. Prefira comparações explícitas quando zero, string vazia ou coleção vazia são valores aceitáveis e não devem ser tratados como ausência.

## Laços, progresso e término

O laço `for` percorre um iterável; `range(1, n)` produz os inteiros de 1 a n−1. O `while` testa a condição antes de cada iteração. Ambos podem não terminar se o estado que controla o progresso permanecer inalterado. Para provar término, identifique uma **medida variante**, como o número de elementos ainda não processados, que diminui até zero. A referência da linguagem também explica `break`, `continue` e `else` associado a laços [2].

Um invariante é uma propriedade verdadeira num ponto determinado de todas as iterações. A prova exige inicialização (verdade antes da primeira iteração), manutenção (a iteração preserva a propriedade) e término (o invariante final implica a resposta). Esse raciocínio aplica a indução matemática ao código. É particularmente útil quando o algoritmo mantém índices, janelas ou dois ponteiros.

## Funções, argumentos, retorno e escopo

Função dá nome a um cálculo e estabelece contrato de entrada e saída. Um parâmetro é um nome local associado ao objeto argumento no momento da chamada; Python não copia automaticamente objetos mutáveis [3]. Portanto, fazer `append` na lista recebida pode alterar a lista do chamador, mas reatribuir o nome local não altera a associação original. Um contrato claro declara tipos permitidos, condições de borda, retorno, exceções e efeitos sobre a entrada.

Prefira retornar resultado em vez de imprimir valor intermediário: o retorno permite composição e testes independentes. `return` encerra a chamada; terminar sem retorno explícito produz None. Variáveis criadas dentro da função normalmente têm escopo local sob as regras de associação do Python, com exceções como `global` e `nonlocal` [3]. Funções pequenas e coesas são úteis, mas quebrar um laço simples em dez funções auxiliares pode dificultar o raciocínio.

## Exemplo derivado: maior segmento não decrescente

Dada uma sequência de valores comparáveis, encontre o **primeiro segmento contíguo de comprimento máximo** em que cada elemento é maior ou igual ao anterior. Segmento contíguo difere de subsequência: não pode ignorar posições. Em `[4,4,2,3,3,0]` existem segmentos `[4,4]`, `[2,3,3]` e `[0]`; a resposta é início=2, comprimento=3. Se vários empatarem, vence o primeiro. Entrada vazia retorna (0,0), convenção explícita que não representa segmento não vazio.

O laço compara cada par vizinho uma única vez. `start` e `length` descrevem o segmento atual; `best_start` e `best_length` descrevem o melhor encontrado até então. Atualizar o melhor somente quando `length > best_length` preserva o vencedor mais antigo nos empates.

~~~python
def longest_non_decreasing_run(values):
    """Return (start, length) for the earliest longest contiguous run."""
    if not isinstance(values, (list, tuple)):
        raise TypeError("expected a sequence")
    if not values:
        return (0, 0)
    start = best_start = 0
    length = best_length = 1
    for index in range(1, len(values)):
        if values[index] >= values[index - 1]:
            length += 1
        else:
            start, length = index, 1
        if length > best_length:
            best_start, best_length = start, length
    return (best_start, best_length)

assert longest_non_decreasing_run([]) == (0, 0)
assert longest_non_decreasing_run([5]) == (0, 1)
assert longest_non_decreasing_run([4, 4, 2, 3, 3, 0]) == (2, 3)
assert longest_non_decreasing_run([1, 2, 0, 1]) == (0, 2)
assert longest_non_decreasing_run([-2, -1, -1, -3]) == (0, 3)
try:
    longest_non_decreasing_run(None)
except TypeError:
    pass
else:
    raise AssertionError("invalid input accepted")
~~~

## Demonstração de correção

Antes da iteração `index`, foram processados os primeiros `index` elementos; o segmento atual termina em `index−1`, e o melhor par representa o primeiro segmento de comprimento máximo no prefixo analisado. Se o próximo elemento é maior ou igual ao anterior, estendemos o segmento. Caso contrário, o segmento termina e outro começa no índice atual. Em qualquer dos casos, a comparação do comprimento atual com o melhor mantém o invariante. Ao terminar, o par registrado é o segmento contíguo mais longo exigido.

O laço termina porque percorre o conjunto finito de índices de 1 a n−1 uma vez. Para n valores, executa max(n−1,0) comparações, portanto O(n) tempo. O algoritmo armazena quantidade fixa de índices e comprimentos: espaço **auxiliar** O(1), sem copiar a entrada. Se comparar elementos não for operação constante, o custo total deve incluir essa comparação. A verificação inicial rejeita entradas fora de lista/tupla, mas a comparabilidade entre elementos permanece sujeita à semântica do Python.

## Contraexemplos e depuração

Trocar `>` por `>=` ao atualizar o melhor faz vencer um segmento posterior em caso de empate, alterando o contrato. Usar `values[index] > values[index−1]` em vez de `>=` quebra sequências com elementos iguais. Inicializar incorretamente o melhor comprimento também pode falhar para uma entrada unitária. Não são preferências de estilo: são diferenças observáveis no resultado.

Rastreie uma entrada curta em papel, usando colunas para índice, início/comprimento atuais e início/comprimento máximos. Comece com entrada vazia, um elemento, empates, repetições e sequência decrescente. Só depois compare com testes automáticos. Tipos de erro devem ter significado: entrada inválida é diferente de sequência válida vazia.

## Exercícios e verificação

1. Rastreie todas as variáveis em `[3,3,1,2,2,0]` e confira o resultado. Explique a mudança causada por comparação estrita.
2. Justifique por que `[1,4,2,5]` não pode devolver a subsequência descontínua `[1,2,5]`.
3. Altere o retorno para devolver os elementos do segmento; explique a memória adicional criada pelo slice.
4. Escreva solução quadrática de referência que enumere os inícios e estenda cada segmento; compare as respostas em todas as sequências de até cinco elementos do conjunto {0,1,2}.
5. Crie uma função que altera uma lista parâmetro e outra que somente reatribui seu nome. Explique a diferença sem afirmar que Python copia argumentos [3].

Continue em [arrays](/pt/topics/arrays-and-strings/), [complexidade](/pt/topics/complexity-analysis/) e [provas de laços](/pt/topics/logic-proofs-invariants/).