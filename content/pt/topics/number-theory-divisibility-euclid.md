---
id: number-theory-divisibility-euclid
title: "Fundamentos de teoria dos números: divisibilidade, MDC e algoritmo de Euclides"
description: "Derive divisibilidade, algoritmo de Euclides e coeficientes de Bézout com provas, inteiros negativos e exercícios."
category: foundations
difficulty: foundational
updated: 2026-10-12
prerequisites: [logic-proofs-invariants, complexity-analysis]
sources:
  - {title: "MIT 6.1200J — Mathematics for Computer Science", url: "https://ocw.mit.edu/courses/6-1200j-mathematics-for-computer-science-spring-2024/", kind: "university course"}
  - {title: "MIT 6.042J — Number Theory lectures", url: "https://ocw.mit.edu/courses/6-042j-mathematics-for-computer-science-fall-2010/", kind: "university course"}
  - {title: "Python math.gcd and math.lcm", url: "https://docs.python.org/3/library/math.html", kind: "official library documentation"}
---
Teoria dos números estuda propriedades dos inteiros. Na programação, a primeira pergunta importante não é como fatorar um número gigantesco, mas **quando um inteiro divide outro e quais consequências essa relação traz para os algoritmos**. Percursos de arrays, ciclos periódicos, frações racionais e cálculos modulares compartilham essa aritmética básica. O algoritmo de Euclides mostra como transformar um invariante matemático em um programa correto e eficiente [1][2].

## Inteiros, divisibilidade e fatores

Para inteiros a e b, com a diferente de zero, dizemos que a divide b se existe inteiro k tal que b=a vezes k. Escrevemos a | b. Por exemplo, 6 divide 42 porque 42=6 vezes 7. O número 6 não divide 43 porque nenhum multiplicador inteiro produz 43. Divisibilidade é propriedade de inteiros, não de aproximações de ponto flutuante. Divisão que retorna quociente arredondado não prova divisibilidade.

Se d divide simultaneamente a e b, então divide qualquer combinação linear inteira ax+by. De fato, se a=du e b=dv, temos ax+by=d(ux+vy). Essa observação sustenta o máximo divisor comum, a identidade de Bézout e a resolução de equações lineares inteiras. O zero exige cuidado: todo inteiro não nulo divide zero; zero divide apenas zero sob a definição pela igualdade, embora diversos textos elementares excluam zero do conjunto de possíveis divisores.

## Máximo divisor comum e casos com zero

Para inteiros a e b não ambos nulos, mdc(a,b) é o **maior inteiro positivo** que divide os dois. Define-se mdc(0,0)=0 por convenção; não se trata de um máximo entre divisores positivos. Quando a é não nulo, mdc(a,0)=|a|, e sinais negativos não alteram o resultado positivo. A função math.gcd do Python segue essas convenções [3].

Os números a e b são coprimos quando mdc(a,b)=1. Isso não significa que ambos sejam primos: 8 e 15 são compostos, mas coprimos. O mínimo múltiplo comum, mmc(a,b), é o menor múltiplo positivo comum para números não nulos e, convencionalmente, vale zero quando algum argumento é zero. Para valores não nulos, mdc(a,b) vezes mmc(a,b)=|ab|. A identidade ajuda a raciocinar sobre periodicidades.

## Por que o resto preserva o MDC

Suponha a=qb+r, com q e r inteiros e 0 <= r < b para b positivo. Todo inteiro que divide a e b divide também r=a-qb. Reciprocamente, todo inteiro que divide b e r divide a=qb+r. Portanto, o conjunto de divisores positivos comuns não muda: mdc(a,b)=mdc(b,r). Esse é o invariante de Euclides [1][2].

Para 48 e 18, a divisão inteira fornece 48=2 vezes 18+12. Depois 18=1 vez 12+6; finalmente 12=2 vezes 6+0. Assim mdc(48,18)=6. Cada etapa reduz o resto não negativo, e o algoritmo termina quando o resto chega a zero. O último resto não nulo é a resposta.

Não é necessário enumerar todos os fatores de um número enorme. A demonstração também é independente de sintaxe específica. Uma implementação ingênua que subtrai repetidamente o menor número quando um argumento é zero pode entrar em laço infinito; o algoritmo por restos e os casos de zero eliminam esse problema.

## Identidade de Bézout e Euclides estendido

Um resultado mais forte estabelece que, se a e b não são ambos zero, existem inteiros x e y tais que ax+by=mdc(a,b). Para 48 e 18, uma solução é 48 vezes (-1) mais 18 vezes 3=6. Os coeficientes não são únicos. O algoritmo de Euclides estendido encontra um par válido enquanto calcula o MDC, acompanhando como cada resto pode ser escrito como combinação linear dos operandos originais [1][2].

Mantenha dois restos r0 e r1 e pares de coeficientes (s0,t0) e (s1,t1). O invariante é r0=s0 A+t0 B e r1=s1 A+t1 B, com A=|a| e B=|b|. Cada quociente subtrai q vezes a segunda equação da primeira, produzindo novo resto e novos coeficientes. Quando o segundo resto chega a zero, r0 é o MDC e os coeficientes certificam a identidade. Para argumentos com sinal, ajuste os coeficientes conforme os sinais originais.

~~~python
def euclid_gcd(a, b):
    if type(a) is not int or type(b) is not int:
        raise TypeError("integer arguments required")
    x, y = abs(a), abs(b)
    while y:
        x, y = y, x % y
    return x

def bezout(a, b):
    """Return (g, x, y), with g >= 0 and a*x + b*y == g."""
    if type(a) is not int or type(b) is not int:
        raise TypeError("integer arguments required")
    if a == 0 and b == 0:
        return (0, 0, 0)
    old_r, r = abs(a), abs(b)
    old_s, s = 1, 0
    old_t, t = 0, 1
    while r:
        q = old_r // r
        old_r, r = r, old_r - q * r
        old_s, s = s, old_s - q * s
        old_t, t = t, old_t - q * t
    sign_a = -1 if a < 0 else 1
    sign_b = -1 if b < 0 else 1
    return (old_r, old_s * sign_a, old_t * sign_b)

def least_common_multiple(a, b):
    g = euclid_gcd(a, b)
    return 0 if g == 0 else abs((a // g) * b)

assert euclid_gcd(48, 18) == 6
assert euclid_gcd(0, 0) == 0
assert euclid_gcd(-24, 18) == 6
assert bezout(0, 0) == (0, 0, 0)
for a, b in ((48, 18), (17, 31), (0, -7), (-9, -6)):
    g, x, y = bezout(a, b)
    assert g == euclid_gcd(a, b)
    assert a * x + b * y == g
assert least_common_multiple(12, 18) == 36
assert least_common_multiple(0, 5) == 0
try:
    euclid_gcd(True, 2)
except TypeError:
    pass
else:
    raise AssertionError("Boolean input was accepted")
~~~

## Demonstração de término e complexidade

Após normalizar os valores para não negativos, cada iteração não final substitui r1 por r0 módulo r1, inteiro não negativo estritamente menor que r1. Existe, portanto, uma medida inteira não negativa decrescente, demonstrando término. O invariante dos divisores comuns prova que trocar (r0,r1) por (r1,r0 módulo r1) mantém o MDC. No encerramento, mdc(r0,0)=r0.

Para operandos não nulos cuja maior magnitude é M, Euclides usa O(log M) iterações com resto; as sequências mais lentas estão relacionadas a números consecutivos de Fibonacci [1]. No modelo de custo unitário, são O(log M) tempo e O(1) variáveis escalares. Em inteiros de precisão arbitrária, divisão e multiplicação não mantêm custo constante quando M cresce: **complexidade em bits precisa ser analisada separadamente**. A implementação mantém quantidade fixa de inteiros Python, cujos tamanhos dependem das magnitudes.

Os coeficientes de Bézout podem ser negativos. O algoritmo verifica sua validade por substituição, não por confiança no resultado. Para entrada (0,0), a implementação devolve explicitamente (0,0,0), convenção que preserva a igualdade 0 vezes 0 mais 0 vezes 0 = 0.

## Equações inteiras e interpretações práticas

Considere ax+by=c com a,b,c inteiros. Se algum entre a e b não é zero, existe solução inteira x,y **se e somente se mdc(a,b) divide c**. A necessidade decorre de que qualquer combinação inteira de a e b é múltipla do MDC. A suficiência decorre de multiplicar os coeficientes de Bézout por c/g quando g=mdc(a,b) divide c.

Por exemplo, 12x+18y=30 possui solução porque mdc(12,18)=6 e 6 divide 30. Já 12x+18y=31 não possui solução inteira. Se a=b=0, só existe solução quando c=0; o caso degenerado não pode ser resolvido dividindo por mdc(0,0)=0. Esses limites devem constar do contrato de uma API, não apenas de comentário não testado.

Se tarefas periódicas se repetem a cada 12 e 18 unidades, seu próximo período comum positivo é mmc(12,18)=36. O cálculo indica coincidências **num modelo ideal de tempo inteiro**, sem modelar fuso horário, deriva de relógio, atraso de rede ou garantias de agendamento em produção.

## Contraexemplos, testes e exercícios

A igualdade mdc(a,b)=a módulo b é falsa em geral: mdc(48,18)=6, mas 48 módulo 18=12. Coprimalidade não implica primalidade, e operações de resto com divisor negativo podem seguir convenções específicas da linguagem. Normalizar sinais antes da recorrência torna a prova mais fácil de transportar entre linguagens.

Um oráculo independente para entradas pequenas pode enumerar divisores candidatos positivos e escolher o maior divisor comum. Seu custo alto é aceitável como teste. Compare todos os pares num intervalo pequeno, incluindo zero e negativos, com a implementação e com math.gcd [3]. Valide Bézout recalculando ax+by.

## Exercícios e verificação

1. Execute as divisões de Euclides para mdc(252,198) e calcule um par de coeficientes de Bézout.
2. Prove que os divisores comuns de a,b coincidem com os de b,a-qb para qualquer inteiro q.
3. Compare o algoritmo ao oráculo de enumeração para todos os pares entre -20 e 20.
4. Dê exemplo de dois inteiros compostos coprimos.
5. Determine se 14x+21y=22 tem solução inteira, justificando pelo MDC.
6. Explique por que O(log M) iterações não representa necessariamente o custo total em operações sobre bits.

Continue por [aritmética modular](/pt/topics/modular-arithmetic-inverses-exponentiation/), [provas e invariantes](/pt/topics/logic-proofs-invariants/) e [complexidade](/pt/topics/complexity-analysis/).