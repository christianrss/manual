---
id: logic-proofs-invariants
title: "Lógica, técnicas de demonstração e invariantes de laço"
description: "Construa argumentos precisos com proposições, quantificadores, contraexemplos, indução, invariantes e provas de terminação."
category: foundations
difficulty: foundational
updated: 2026-10-10
prerequisites: []
sources:
  - {title: "MIT 6.042J — Mathematics for Computer Science", url: "https://ocw.mit.edu/courses/6-042j-mathematics-for-computer-science-spring-2015/", kind: "university course and open textbook"}
  - {title: "Python Language Reference — Expressions", url: "https://docs.python.org/3/reference/expressions.html", kind: "official language reference"}
---
Um argumento sobre algoritmos precisa separar o requisito, o comportamento observado e aquilo que foi demonstrado. Executar um teste comprova o resultado para uma entrada; não prova a correção em todo o domínio admissível. A lógica discreta fornece a linguagem para especificações precisas. Invariantes e argumentos de terminação conectam essa linguagem a laços reais, estruturas de dados e protocolos. O curso de matemática discreta do MIT trata proposições, provas, conjuntos, funções e máquinas de estados como fundamentos da ciência da computação [1].

## Proposições, domínios e operadores lógicos

Uma **proposição** é uma afirmação com valor de verdade. Seja P a proposição "a sequência está ordenada" e Q a proposição "a resposta da busca binária está correta". A implicação P ⇒ Q é falsa apenas quando P é verdadeira e Q é falsa. A implicação não garante que P seja verdadeira. Portanto, demonstrar uma busca sob pré-condição de ordenação não autoriza aplicá-la a uma sequência arbitrária.

A negação inverte o valor lógico, a conjunção P ∧ Q exige as duas proposições e a disjunção P ∨ Q exige pelo menos uma. A tabela expõe a sutileza da implicação quando a premissa é falsa:

| P | Q | P ⇒ Q |
| --- | --- | --- |
| Falso | Falso | Verdadeiro |
| Falso | Verdadeiro | Verdadeiro |
| Verdadeiro | Falso | Falso |
| Verdadeiro | Verdadeiro | Verdadeiro |

A **recíproca** Q ⇒ P não é equivalente à proposição original; a **contrapositiva** ¬Q ⇒ ¬P é equivalente. "Se um número é divisível por quatro, é par" é verdadeiro. A recíproca é falsa, pois seis é par e não é divisível por quatro. Basta um contraexemplo para invalidar uma afirmação universal.

## Quantificadores e a ordem dos requisitos

A escrita ∀x∈D, P(x) significa que P vale para cada elemento do domínio D. A escrita ∃x∈D, P(x) exige apenas uma testemunha. Negar uma afirmação universal equivale a encontrar um caso que a contrarie: ¬(∀x P(x)) equivale a ∃x ¬P(x). O sucesso de uma única tentativa de recuperação não demonstra que **todas** as tentativas sejam seguras.

A ordem dos quantificadores importa. "Para cada requisição existe um trabalhador capaz" (∀r ∃w) não implica "existe um trabalhador capaz de tratar todas" (∃w ∀r). Na primeira, o trabalhador pode depender da requisição; na segunda, um único trabalhador deve servir para todas as requisições.

Toda prova técnica deve declarar seu domínio: inteiros não negativos, sequências finitas, bytes válidos ou requisições admitidas por uma interface. Também não se deve confundir lógica matemática com execução Python: and/or usam avaliação de curto-circuito e podem retornar um operando, não necessariamente um Booleano. A linguagem tem semântica operacional própria [2].

## Pré-condições, pós-condições e correção total

A **pré-condição** delimita estados iniciais válidos. A **pós-condição** define o resultado exigido ao final. Na **correção parcial**, se um programa termina a partir de entrada válida, o resultado satisfaz a pós-condição. A **correção total** exige também que a execução termine. Ignorar essa diferença permite declarar correta uma rotina que entra em laço infinito para parte das entradas.

Considere uma função que localiza a primeira ocorrência de um alvo. A pré-condição pode permitir qualquer sequência finita com igualdade definida. A pós-condição deve exigir um índice válido cujo elemento seja igual ao alvo e nenhum índice anterior corresponda, ou -1 quando não existe ocorrência. Uma função que promete qualquer ocorrência tem contrato mais fraco; são interfaces diferentes.

Contratos formais não substituem validação em execução. Em Python, comandos assert podem ser omitidos com otimizações; portanto, não devem ser o mecanismo que protege fronteiras contra entradas não confiáveis. A verificação de dados externos deve ser explícita, independentemente do modo de execução [2].

## Indução e raciocínio estrutural

A indução matemática demonstra P(n) para naturais: provar um caso-base, assumir P(k) e deduzir P(k+1). Em um laço, a ideia corresponde a inicialização, preservação e condição final. Em estruturas recursivas, demonstram-se casos vazios ou folhas e depois a operação que constrói estruturas maiores. O objetivo é cobrir cada transição possível [1].

Como exemplo, a soma dos n primeiros inteiros não negativos é n(n−1)/2. Para n=0, ambos os lados são zero. Assumindo a fórmula para n=k, acrescenta-se o termo k: k(k−1)/2 + k = k(k+1)/2, expressão correta para n=k+1. O argumento cobre todos os naturais, mas não garante ausência de overflow em aritmética de largura fixa.

Contraexemplos detectam hipóteses incorretas. A afirmação "escolher sempre a maior moeda produz a solução mínima" falha para moedas 1, 3 e 4 e alvo 6: a estratégia gulosa obtém 4+1+1, três moedas; a solução 3+3 usa duas. Uma regra pode funcionar em certos sistemas de moedas e fracassar em outros.

## Exemplo completo: invariante de primeira ocorrência

Para uma sequência com n elementos, mantenha índice i e o invariante **todos os índices j inferiores a i têm valor diferente do alvo**. Inicialmente i=0; o conjunto inspecionado é vazio e a afirmação é verdadeira. Se o elemento atual não corresponde, incrementar i preserva o invariante. Se corresponde, nenhum anterior corresponde, logo o índice retornado é mínimo. Se i chega a n, todas as possibilidades foram descartadas e o retorno -1 é correto.

A variante de terminação n−i é inteira, não negativa durante o laço e diminui a cada iteração sem retorno. Assim, o laço não pode executar infinitamente sobre uma sequência finita e estável.

~~~python
def primeiro_indice(itens, alvo):
    i = 0
    while i < len(itens):
        if itens[i] == alvo:
            return i
        i += 1
    return -1

assert primeiro_indice([], 7) == -1
assert primeiro_indice([3, 7, 3, 7], 7) == 1
assert primeiro_indice([3, 3, 3], 3) == 0
assert primeiro_indice([1, 2, 3], 4) == -1
~~~

A execução custa O(n) no pior caso e O(1) de memória auxiliar, com n representando o comprimento e igualdade de custo constante. Se comparações forem caras, tiverem efeitos colaterais ou a coleção sofrer mutação concorrente, o modelo precisa mudar. A rotina não modifica a entrada.

## Caso mais exigente: busca binária e intervalo candidato

Em sequência finita **ordenada em ordem não decrescente**, encontre a primeira posição cujo valor seja maior ou igual ao alvo. Mantenha um intervalo semiaberto [lo, hi): todo índice abaixo de lo tem valor estritamente menor que o alvo; todo índice a partir de hi tem valor maior ou igual. Inicialmente lo=0 e hi=n; a segunda condição é trivial porque não há índices válidos a partir de n. Se o valor central é menor, todos os anteriores também são, então lo=m+1. Caso contrário, hi=m. Em ambos os ramos o intervalo encolhe.

~~~python
def limite_inferior(itens, alvo):
    lo, hi = 0, len(itens)
    while lo < hi:
        meio = lo + (hi - lo) // 2
        if itens[meio] < alvo:
            lo = meio + 1
        else:
            hi = meio
    return lo

for xs in ([], [1], [1, 1, 3, 3, 9], [-5, -1, 0]):
    for alvo in range(-6, 11):
        esperado = sum(x < alvo for x in xs)
        assert limite_inferior(xs, alvo) == esperado
~~~

Ao terminar, lo=hi, e os dois grupos excluídos identificam o primeiro índice possível ou n quando não há candidato. A variante hi−lo diminui estritamente e permanece não negativa. O número de comparações é O(log(n+1)), com O(1) de memória auxiliar, supondo acesso por índice constante. Em sequência desordenada, a pré-condição falha; o algoritmo e sua prova deixam de ter validade.

## Verificação e limites das provas

Uma prova depende das hipóteses declaradas e da correspondência entre implementação e modelo demonstrado. Enumeração exaustiva de um domínio finito garante propriedades **nesse domínio**; testes aleatórios podem revelar contraexemplos, mas não estabelecem universalidade. Por isso, testes, revisão e demonstrações formais são complementares.

Na busca binária, é útil enumerar todas as sequências curtas ordenadas com elementos de {-1, 0, 1} e confrontar o índice com um oráculo linear. O oráculo deve ser independente da mesma lógica de ponto médio, para evitar reproduzir o defeito. Teste vazio, repetidos, alvo ausente e extremos. Uma prova baseada em entradas estáveis não cobre modificação concorrente.

## Exercícios

1. Negue a proposição exata ∀x∈D, ∃y∈E, R(x,y). **Resposta:** ∃x∈D, ∀y∈E, ¬R(x,y), preservando os domínios.
2. Especifique a primeira ocorrência em sequência finita e explique inicialização, manutenção, pós-condição e variante estritamente decrescente. **Verificação:** confronte sua prova com o exemplo anterior.
3. Refute "se uma função termina, então é correta". **Resposta:** uma função que sempre retorna zero termina, mas viola contrato de calcular o quadrado quando a entrada é 2.
4. Explique por que o limite superior da busca binária começa em n, e não n−1. **Resposta:** o intervalo semiaberto deve comportar a posição de inserção n e uma sequência inicialmente vazia.

Os exercícios reforçam raciocínio de prova; não substituem avaliações inéditas e independentes de programação.