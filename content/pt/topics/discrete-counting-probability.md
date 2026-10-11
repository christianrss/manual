---
id: discrete-counting-probability
title: "Matemática discreta: conjuntos, contagem e probabilidade exata"
description: "Demonstre identidades de contagem, permutações, combinações, probabilidade condicional, Bayes e esperança com frações exatas e verificações exaustivas."
category: foundations
difficulty: foundational
updated: 2026-10-10
prerequisites: [logic-proofs-invariants, programming-semantics-contracts]
sources:
  - {title: "MIT 6.042J — Mathematics for Computer Science", url: "https://ocw.mit.edu/courses/6-042j-mathematics-for-computer-science-spring-2015/", kind: "university open course"}
  - {title: "MIT 6.042J — Counting and Probability Readings", url: "https://ocw.mit.edu/courses/6-042j-mathematics-for-computer-science-spring-2015/pages/readings/", kind: "university open textbook contents"}
  - {title: "Stanford CS109 — Probability for Computer Scientists", url: "https://web.stanford.edu/class/cs109/", kind: "university probability course"}
  - {title: "Python itertools documentation", url: "https://docs.python.org/3/library/itertools.html", kind: "official library reference"}
  - {title: "Python fractions documentation", url: "https://docs.python.org/3/library/fractions.html", kind: "official exact arithmetic reference"}
---
A matemática discreta oferece linguagem rigorosa para estruturas finitas, espaços de entrada, limites de algoritmos, hashing e algoritmos aleatorizados. Uma demonstração sobre um programa depende de conjuntos definidos, regras explícitas de ordem e reposição e de um modelo de probabilidade cujos resultados tenham pesos conhecidos. O capítulo de [lógica e invariantes](/pt/topics/logic-proofs-invariants/) explica obrigações de prova; [semântica de programação](/pt/topics/programming-semantics-contracts/) define contratos executáveis. Aqui estendemos esses fundamentos para **combinatória finita e probabilidade**, em linha com o currículo de matemática para ciência da computação do MIT [1][2].

Um teste exaustivo em domínio finito não demonstra teorema para todos os números naturais. Apresentaremos argumentos algébricos e combinatórios; Python verifica casos independentes. O cálculo usa **frações racionais exatas**, sem estimativas por Monte Carlo nem hipóteses irreais sobre a distribuição verdadeira de aniversários.

## Conjuntos, subconjuntos e inclusão–exclusão

Um conjunto contém **elementos distintos**, sem multiplicidade nem ordem estabelecida. Uma sequência finita pode ter ocorrências repetidas; um multiconjunto mantém multiplicidades, mas não necessariamente ordenação. A distinção importa em arrays, tabelas hash e bancos de dados: uma lista de clientes com identificadores duplicados não é o mesmo objeto matemático que o conjunto de identificadores únicos.

Para conjuntos finitos `A` e `B`, contar os elementos separadamente duplica aqueles da interseção `A ∩ B`. Corrigindo a dupla contagem, obtemos

`|A ∪ B| = |A| + |B| − |A ∩ B|`.

É a **inclusão–exclusão para dois conjuntos**, não a regra de apenas somar os tamanhos de três conjuntos. Com três, somamos conjuntos individuais, subtraímos interseções de pares e **somamos novamente** a interseção tripla. Uma prova considera cada elemento individualmente: se pertence exatamente a `r` conjuntos, seu coeficiente total da expansão é `sum((-1)^(j+1) × C(r,j), j=1..r)=1`.

Cada subconjunto de conjunto com `n` elementos corresponde a uma escolha binária por elemento: incluir ou não incluir. Portanto o conjunto das partes possui `2^n` subconjuntos. Isso mostra por que enumerar **todos** os subconjuntos custa exponencialmente mesmo com entrada pequena. O fato de Python possuir tipo `set` não torna barata uma enumeração de subconjuntos [1][2].

## Princípios aditivo, multiplicativo e da casa dos pombos

Se uma escolha possui `a` opções e, para **cada** uma delas, a segunda possui `b` opções, existem `a×b` pares ordenados. A regra multiplicativa requer a mesma quantidade `b` em todos os ramos; se escolhas posteriores dependem das anteriores, some os produtos adequados por ramo. Para alternativas disjuntas, o total é a soma dos tamanhos; havendo interseção, é necessário usar inclusão–exclusão.

O **princípio da casa dos pombos** afirma: distribuir `n+1` itens entre `n` recipientes obriga pelo menos um recipiente a conter dois ou mais itens. Uma prova por contradição supõe que cada recipiente contém no máximo um, o que comportaria apenas `n` itens. Mais geralmente, `m` itens distribuídos por `n>0` recipientes garantem pelo menos um com `ceil(m/n)` itens. É garantia determinística, não valor esperado.

Aplicações incluem colisões inevitáveis quando existem mais entradas distintas que valores possíveis de hash. O princípio não determina, sozinho, o desempenho médio de hash: distribuição, entradas adversariais e crescimento da tabela são aspectos separados.

## Arranjos e combinações não são equivalentes

Escolha `k` objetos **distintos**, de `n` objetos distinguíveis.

Se **a ordem importa** e não pode haver repetição, a primeira posição possui `n` possibilidades, a segunda `n−1`, e assim por diante. Logo os arranjos são

`P(n,k)=n!/(n−k)!`, para `0≤k≤n`.

Se **a ordem não importa**, cada subconjunto escolhido tem `k!` permutações diferentes, então

`C(n,k)=n!/(k!(n−k)!)`.

Pela simetria, `C(n,k)=C(n,n−k)`: escolher o que fica equivale a escolher o que sai. A identidade de Pascal, `C(n,k)=C(n−1,k−1)+C(n−1,k)`, decorre de separar todos os subconjuntos de tamanho `k` entre os que contêm um elemento fixo e os que não contêm. Se `k>n`, não existe seleção sem reposição; por contrato da API, o resultado é zero. Para `k=0`, existe uma única escolha vazia.

Permitir repetição altera as contas: `n^k` sequências ordenadas de `k` escolhas **com reposição**; já multisets de `k` objetos obtidos de `n` categorias resultam em `C(n+k−1,k)` quando `n>0`. Misturar as regras é erro comum de entrevistas. O custo de **enumerar** possibilidades também difere do custo de apenas **calcular a quantidade**.

## Identidades de contagem executáveis

As funções rejeitam valores negativos e não inteiros, inclusive `bool` do Python, e usam produtos iterativos em vez de calcular três fatoriais grandes. O laço preserva coeficiente binomial inteiro em cada produto parcial. O cálculo é exato porque `C(n−k+i,i)` é inteiro em cada etapa.

~~~python
from math import factorial
from itertools import product

def choose(n, k):
    """Unordered distinct k-subsets from n distinguishable objects."""
    if type(n) is not int or type(k) is not int or n < 0 or k < 0:
        raise ValueError("n and k must be nonnegative integers")
    if k > n:
        return 0
    k = min(k, n - k)
    count = 1
    for i in range(1, k + 1):
        count = count * (n - k + i) // i
    return count

def arrangements(n, k):
    """Ordered k-tuples chosen without replacement."""
    if type(n) is not int or type(k) is not int or n < 0 or k < 0:
        raise ValueError("n and k must be nonnegative integers")
    if k > n:
        return 0
    count = 1
    for i in range(k):
        count *= n - i
    return count

assert choose(5, 2) == 10
assert arrangements(5, 2) == 20
assert choose(0, 0) == arrangements(0, 0) == 1
assert choose(4, 7) == arrangements(4, 7) == 0
assert choose(8, 3) == choose(8, 5) == 56
assert sum(choose(5, k) for k in range(6)) == 2 ** 5

def union_cardinality(a, b):
    if not isinstance(a, (set, frozenset)) or not isinstance(b, (set, frozenset)):
        raise ValueError("finite sets required")
    return len(a) + len(b) - len(a.intersection(b))

assert union_cardinality({1, 2, 3}, {3, 4}) == 4
~~~

Após selecionar o menor valor entre `k` e `n−k`, `choose` executa `O(min(k,n−k))` iterações e `arrangements` realiza `O(k)` multiplicações. São limites de **operações aritméticas**; com inteiros muito grandes o custo em bits não é constante. Não se deve alegar operações aritméticas de tempo constante com `n` arbitrariamente grande. A enumeração por `itertools.combinations` e `itertools.permutations` da biblioteca padrão fornece **oráculo independente** em casos pequenos [4].

## Espaço amostral e probabilidades precisam de pesos definidos

Um espaço de probabilidade finito possui resultados possíveis `Ω` com peso total um. Se todos são equiprováveis, `P(A)=|A|/|Ω|` para evento `A⊆Ω`. Sem a equiprobabilidade, contar resultados produz resposta errada: uma moeda enviesada continua tendo cara e coroa, mas não com peso um meio cada.

Dados eventos `A`, `B` e `P(B)>0`, a probabilidade condicional é

`P(A|B)=P(A∩B)/P(B)`.

Eventos são **independentes** se `P(A∩B)=P(A)P(B)`; isso não é sinônimo de serem **disjuntos**. Eventos disjuntos, cada qual com probabilidade positiva, não podem ser independentes: interseção nula contradiz o produto positivo.

Considere dois dados justos. O evento `A` indica “soma pelo menos dez”: seis dos 36 pares ordenados. `B` indica “primeiro dado pelo menos cinco”: 12 resultados. Cinco resultados satisfazem os dois, então `P(A|B)=5/12`, mas `P(A)=1/6`; portanto os eventos são dependentes. É necessário considerar pares ordenados, com dado identificado como primeiro e segundo.

## Colisões, esperança e hipóteses de distribuição

Suponha `r` escolhas independentes e **uniformes, com reposição**, entre `d` categorias. A probabilidade de todas serem diferentes é

`P(sem colisões) = produto((d−i)/d, i=0..r−1)`, se `r≤d`.

A probabilidade de pelo menos uma colisão é **um menos** essa quantidade, pois os eventos são complementares. Se `r>d`, a colisão é certa pelo princípio da casa dos pombos. No modelo simplificado de 365 dias equiprováveis, 23 pessoas já produzem chance superior a 50% de aniversários coincidentes. Isso **não** representa distribuição sazonal real, dias bissextos nem dependência entre nascimentos [2][3].

A **quantidade esperada de categorias distintas** admite outra prova: para cada categoria `j`, defina `I_j=1` quando aparece pelo menos uma vez, caso contrário zero. Então `D=sum(I_j)`. Pela linearidade da esperança, `E[D]=sum(E[I_j])`, e `E[I_j]=1−((d−1)/d)^r`. Logo `E[D]=d(1−(1−1/d)^r)`. Esses indicadores **não são independentes**; a linearidade da esperança, contudo, não exige independência. Quantidade esperada de categorias distintas é diferente da probabilidade de **alguma** colisão.

## Regra de Bayes e influência da prevalência

Para um classificador binário, sejam `p=P(condição)`, `s=P(positivo|condição)` (sensibilidade) e `f=P(positivo|sem condição)` (taxa de falso positivo). Separando os positivos segundo o estado real,

`P(condição|positivo)=ps/(ps+(1−p)f)`.

A expressão é Bayes aplicado a uma partição em dois ramos. O denominador é a probabilidade **total** de teste positivo, e não só o ramo verdadeiro positivo. Com prevalência de 1%, sensibilidade de 90% e falso positivo de 5%, a probabilidade posterior da condição após o teste positivo é exatamente `2/13`, cerca de 15,4%, e não 90%. É exercício genérico de probabilidade, não aconselhamento médico ou estimativa de desempenho de exame real [3].

O evento condicionante precisa ter **probabilidade positiva**. Se tanto a massa de verdadeiro positivo quanto a de falso positivo são zero, positivo jamais ocorre no modelo e a probabilidade condicional é indefinida. Nossa função lança exceção nesse caso, evitando dividir por zero ou inventar resultado.

## Modelo de probabilidade finita exata

O exemplo seguinte usa `fractions.Fraction` para evitar arredondamentos de ponto flutuante mascarando diferenças em identidades finitas. Os parâmetros probabilísticos devem ser `Fraction` em `[0,1]`. Eventos condicionados precisam ser subconjuntos explícitos do espaço finito, com evento condicionante não vazio. Domínios inválidos lançam `ValueError`. Nenhuma função realiza amostragem aleatória.

~~~python
from fractions import Fraction
from itertools import product

def collision_probability(days, people):
    """Independent uniform draws with replacement from days choices."""
    if (type(days) is not int or days <= 0
            or type(people) is not int or people < 0):
        raise ValueError("positive days and nonnegative people required")
    if people > days:
        return Fraction(1)
    no_collision = Fraction(1)
    for i in range(people):
        no_collision *= Fraction(days - i, days)
    return 1 - no_collision

def expected_distinct(days, people):
    """Linearity of expectation over indicators for used categories."""
    if (type(days) is not int or days <= 0
            or type(people) is not int or people < 0):
        raise ValueError("positive days and nonnegative people required")
    probability_unused = Fraction(days - 1, days) ** people
    return days * (1 - probability_unused)

def conditional_probability(space, event, given):
    if (not all(isinstance(x, (set, frozenset))
                for x in (space, event, given))
            or not event.issubset(space)
            or not given.issubset(space)
            or not given):
        raise ValueError("event and nonempty condition must belong to space")
    return Fraction(len(event.intersection(given)), len(given))

def posterior_positive(prevalence, sensitivity, false_positive_rate):
    if (any(type(p) is not Fraction or not 0 <= p <= 1
            for p in (prevalence, sensitivity, false_positive_rate))):
        raise ValueError("all probabilities must be fractions in [0,1]")
    true_positive = prevalence * sensitivity
    false_positive = (1 - prevalence) * false_positive_rate
    if true_positive + false_positive == 0:
        raise ValueError("cannot condition on a probability-zero test result")
    return true_positive / (true_positive + false_positive)

rolls = set(product(range(1, 7), repeat=2))
sum_ten_or_more = {pair for pair in rolls if sum(pair) >= 10}
first_at_least_five = {pair for pair in rolls if pair[0] >= 5}
assert Fraction(len(sum_ten_or_more), len(rolls)) == Fraction(1, 6)
assert conditional_probability(rolls, sum_ten_or_more, first_at_least_five) == Fraction(5, 12)
assert collision_probability(365, 23) > Fraction(1, 2)
assert collision_probability(5, 6) == 1
assert expected_distinct(2, 2) == Fraction(3, 2)
assert posterior_positive(Fraction(1, 100),
                          Fraction(9, 10),
                          Fraction(1, 20)) == Fraction(2, 13)
~~~

Um teste independente pode enumerar todas as sequências pequenas de escolhas com reposição e contar quais possuem valores repetidos. Também pode enumerar cada sequência para calcular a média de categorias distintas e comparar com a fórmula derivada de indicadores. Separadamente, um oráculo de resultados ponderados em dois estágios permite testar Bayes em grades de probabilidades racionais, em vez de apenas chamar a mesma expressão algébrica.

## Complexidade, incerteza e projetos de algoritmos

Um espaço amostral exponencial pode ser fácil de **contar analiticamente** e caro de enumerar. Com `n` escolhas independentes a cada uma de `r` etapas, temos `n^r` sequências. Enumerar custa pelo menos essa quantidade de passos, enquanto calcular a probabilidade de colisão por produto demanda no máximo `O(min(n,r))` multiplicações racionais sob o modelo definido. Frações exatas podem adquirir numeradores e denominadores grandes, portanto a **complexidade em bits** precisa ser considerada em parâmetros elevados.

Na análise de algoritmos, falar em **custo esperado** só faz sentido diante de uma distribuição especificada sobre entradas ou aleatoriedade do procedimento. Não substitui automaticamente um limite de pior caso. Tabelas hash frequentemente têm boa consulta esperada sob hipóteses de hashing, mas colisões adversariais e políticas de resize continuam importantes. Isso se relaciona com [análise de complexidade](/pt/topics/complexity-analysis/) e [tabelas hash](/pt/topics/hash-tables/).

A separação entre prova e teste permanece: a enumeração exaustiva para `n≤8` valida implementação diante de oráculos independentes em domínio limitado; uma identidade matemática demonstra todos os `n` admitidos pelas hipóteses. Os exemplos supõem escolhas independentes uniformes, espaços finitos e aritmética inteira exata. Não constituem benchmark aleatório ou avaliação real de entropia criptográfica.

## Exercícios e verificação

1. Prove inclusão–exclusão para dois conjuntos examinando se um elemento pertence a zero, um ou dois conjuntos. Generalize para três.
2. Demonstre a identidade de Pascal dividindo subconjuntos de tamanho `k` entre aqueles que contêm um elemento fixo e os que não contêm.
3. Diferencie arranjos sem reposição, sequências ordenadas com reposição e multisets para `n=3,k=2`; enumere cada espaço e explique as contagens.
4. Aplique o princípio da casa dos pombos a 13 itens e 12 recipientes. Explique por que a garantia de colisão não estabelece custo médio de busca.
5. Enumere os 36 resultados de dois dados para verificar `P(soma≥10)=1/6` e `P(soma≥10|primeiro≥5)=5/12`.
6. Mostre que indicadores de presença de duas categorias distintas podem ser dependentes, embora a esperança total seja a soma das esperanças individuais.
7. Derive a probabilidade de colisão entre quatro escolhas independentes de três categorias, comparando conta analítica e enumeração completa.
8. Com prevalência zero e falso positivo zero, explique por que a probabilidade posterior condicionada a um resultado positivo é indefinida.
9. Proponha problema cuja **contagem** seja feita em tempo polinomial, enquanto listar todos os resultados exige tempo exponencial. Diferencie número de operações aritméticas de custo em bits.

**Próximos estudos:** [análise de complexidade](/pt/topics/complexity-analysis/) aplica essas contagens; [tabelas hash](/pt/topics/hash-tables/) exigem hipóteses de colisões; [lógica e invariantes](/pt/topics/logic-proofs-invariants/) fornece técnicas de demonstração. Este capítulo não substitui um currículo completo de matemática discreta ou estatística [1][2][3][4][5].
