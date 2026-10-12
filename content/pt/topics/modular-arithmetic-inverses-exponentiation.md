---
id: modular-arithmetic-inverses-exponentiation
title: "Aritmética modular: congruências, inversos e exponenciação rápida"
description: "Derive congruências, inversos modulares e quadrados sucessivos com invariantes de correção e testes exaustivos."
category: foundations
difficulty: foundational
updated: 2026-10-12
prerequisites: [number-theory-divisibility-euclid, complexity-analysis]
sources:
  - {title: "MIT 6.1200J — Mathematics for Computer Science", url: "https://ocw.mit.edu/courses/6-1200j-mathematics-for-computer-science-spring-2024/", kind: "university course"}
  - {title: "MIT 6.042J — Mathematics for Computer Science", url: "https://ocw.mit.edu/courses/6-042j-mathematics-for-computer-science-spring-2015/", kind: "university textbook"}
  - {title: "Python built-in pow", url: "https://docs.python.org/3/library/functions.html#pow", kind: "official language documentation"}
---
Aritmética modular estuda inteiros identificando como equivalentes valores que produzem o mesmo resto. Ela transforma um conjunto ilimitado em uma quantidade finita de classes sem eliminar as regras usuais de adição e multiplicação. Essa base aparece em arrays circulares, tarefas periódicas, hashing e na matemática subjacente à criptografia de chave pública. A principal questão é compreender **quais operações preservam congruência e quando dividir é permitido** [1][2].

## Defina congruência antes de calcular restos

Para módulo positivo m, inteiros a e b são congruentes módulo m quando m divide a-b. Escrevemos a ≡ b (mod m). Por exemplo, 17 ≡ 5 (mod 12), porque 17-5=12. Também -1 ≡ 11 (mod 12), pois -1-11=-12. Congruência é relação de equivalência: reflexividade é imediata, simetria decorre de trocar o sinal e transitividade decorre da soma de múltiplos de m [1].

As classes residuais módulo m particionam os inteiros em exatamente m classes distintas, representadas usualmente por 0 até m-1. Operadores de resto escolhem representantes; diferentes linguagens podem discordar sobre o sinal do resto com operandos negativos. Em Python, para m positivo, a % m devolve o representante não negativo. A definição matemática de congruência não depende dessa escolha da linguagem.

## Por que soma e multiplicação funcionam com restos

Se a ≡ b módulo m e c ≡ d módulo m, então a+c ≡ b+d e ac ≡ bd módulo m. Para demonstrar multiplicação, escreva a=b+km e c=d+lm. Expandindo, ac=bd+m(bl+dk+klm), logo ac-bd é divisível por m. Assim, reduzir valores intermediários módulo m preserva o resto final das somas e produtos [1][2].

No módulo 7, 10 ≡ 3 e 12 ≡ 5. O produto 120 ≡ 15 ≡ 1 (mod 7). Multiplicar os representantes menores 3 vezes 5 fornece a mesma classe. Isso permite construir algoritmos sem conservar resultados intermediários enormes, desde que as operações e representações numéricas respeitem o contrato escolhido.

Congruência não é igualdade usual: a≡b não implica a=b como inteiros. Aplicar módulo também não constitui criptografia. Quando muitos valores são mapeados para poucos buckets, colisões são matematicamente inevitáveis.

## Divisão modular exige inverso multiplicativo

Para números reais não nulos, dividir por a equivale a multiplicar por 1/a. Em aritmética modular, dividir por a exige inteiro x que satisfaça a vezes x ≡1 módulo m. Esse x é um **inverso multiplicativo**. Ele existe exatamente quando mdc(a,m)=1, consequência direta da identidade de Bézout do capítulo anterior [1][2].

Para módulo 11, o inverso de 3 é 4, pois 3 vezes 4=12 ≡1. No módulo 4, o número 2 não tem inverso: todo produto 2x é par e não pode ser congruente a 1. Cancelar fator comum numa congruência como se estivéssemos nos reais pode ser incorreto quando o fator não é coprimo com o módulo.

O algoritmo de Euclides estendido fornece inteiros x,y tais que ax+my=mdc(a,m). Se esse MDC é 1, o resto de x módulo m corresponde ao inverso. O exemplo executável utiliza o mesmo invariante dos restos, acompanhando o coeficiente do representante inicial não negativo a%m.

## Congruências lineares e cancelamento inválido

A congruência ax ≡ b módulo m significa que m divide ax-b. Equivale a existir solução inteira de ax-my=b. Considere g=mdc(a,m). Existe solução se e somente se g divide b. Quando g=1, há uma única classe residual solução, dada por inverso(a) vezes b módulo m. Se g>1 divide b, existem exatamente g soluções distintas entre os m restos possíveis [1].

Na equação 2x ≡2 módulo 4, tanto x=1 quanto x=3 resolvem o problema. Cancelar o fator 2 preservando módulo 4 apagaria incorretamente uma solução. Divida a, b e m por g; resolva a congruência reduzida módulo m/g; depois recupere as g soluções originais módulo m.

Essa é a razão matemática para tratar ausência de inverso como erro explícito na API. Devolver algum número arbitrário para uma entrada não invertível não é alternativa válida; devolver zero confundiria erro com um resto permitido.

## Derive a exponenciação por quadrados sucessivos

Para encontrar o resto de a elevado ao expoente não negativo e, a solução direta executa e multiplicações. A exponenciação binária utiliza os dígitos binários de e. Comece com acumulador 1 e fator a módulo m. Quando o expoente corrente for ímpar, multiplique o acumulador pelo fator. Eleve o fator ao quadrado e substitua e pelo piso da sua metade. A cada repetição o expoente restante é aproximadamente dividido por dois.

Para 2^10 módulo 17, a representação binária de 10 é 1010. As potências escolhidas são 2^2=4 e 2^8=256. O produto é 1024, com resto 4 módulo 17. Reduzir após cada multiplicação produz a mesma classe sem precisar construir potências gigantescas. A técnica resulta de álgebra elementar, não de uma instrução especial de CPU [1][3].

~~~python
def mod_inverse(a, modulus):
    if type(a) is not int or type(modulus) is not int or modulus <= 1:
        raise ValueError("integers and modulus > 1 required")
    old_r, r = modulus, a % modulus
    old_t, t = 0, 1
    while r:
        q = old_r // r
        old_r, r = r, old_r - q * r
        old_t, t = t, old_t - q * t
    if old_r != 1:
        raise ValueError("modular inverse does not exist")
    return old_t % modulus

def modular_power(base, exponent, modulus):
    if (type(base) is not int or type(exponent) is not int
            or type(modulus) is not int or exponent < 0 or modulus <= 1):
        raise ValueError("invalid arguments")
    result = 1
    factor = base % modulus
    while exponent:
        if exponent % 2 == 1:
            result = (result * factor) % modulus
        factor = (factor * factor) % modulus
        exponent //= 2
    return result

assert mod_inverse(3, 11) == 4
assert mod_inverse(-3, 11) == 7
assert modular_power(2, 10, 17) == 4
assert modular_power(-2, 3, 5) == 2
assert modular_power(0, 0, 7) == 1
for value, modulus in ((2, 4), (0, 7)):
    try:
        mod_inverse(value, modulus)
    except ValueError:
        pass
    else:
        raise AssertionError("noninvertible value accepted")
try:
    modular_power(2, -1, 7)
except ValueError:
    pass
else:
    raise AssertionError("negative exponent accepted")
~~~

## Demonstre os invariantes e o término

No inverso modular, cada resto de Euclides estendido é uma combinação linear de m e do representante inicial de a. Quando o MDC final vale 1, o coeficiente t obtido satisfaz a vezes t ≡1 módulo m. Se o MDC é maior que 1, não existe inverso, pois toda combinação continua divisível pelo divisor comum.

Na exponenciação, tome A como base original e E como expoente inicial. O invariante afirma que acumulador vezes fator elevado ao expoente restante ≡ A^E módulo m. Inicialmente o acumulador é 1. Se o expoente é ímpar, transferir um fator para o acumulador preserva a igualdade. Elevar o fator ao quadrado e usar metade inteira do expoente restante mantém a propriedade. Ao final o expoente vale zero, restando o resultado procurado.

Para E>0, são O(log E) iterações, cada qual com quantidade limitada de multiplicações modulares. No modelo de custo unitário, isso significa O(log E) tempo e O(1) variáveis escalares. Na aritmética com inteiros de precisão arbitrária, também contam os bits do módulo. Expoente zero devolve a identidade do produto vazio 1; portanto o código adota 0^0=1 como convenção computacional. O contrato exclui intencionalmente módulo 1.

## Limites de segurança, contraexemplos e exercícios

Uma base pode ser negativa porque seu resto módulo positivo é definido. O exemplo rejeita expoentes negativos, que exigiriam regra distinta sobre existência de inverso. A função pow do Python com três argumentos serve como referência independente para exponenciação modular e, nas condições documentadas, admite expoentes negativos por inverso [3].

A implementação decide caminhos conforme bits do expoente e **não é software criptográfico de tempo constante**. Operações que manipulam segredos exigem bibliotecas auditadas, validação de parâmetros e análise de canais laterais. Um índice de bucket obtido por resto não garante distribuição uniforme nem resistência a colisões.

## Exercícios e verificação

1. Prove que congruência módulo positivo m é reflexiva, simétrica e transitiva.
2. Calcule com Euclides os inversos de 3 módulo 11 e 5 módulo 12, além de um exemplo sem inverso.
3. Resolva 6x ≡8 módulo 14 e liste todas as soluções entre 0 e 13.
4. Rastreie acumulador, fator e expoente de 3^13 módulo 7.
5. Compare modular_power com pow do Python para bases de -10 até 10, expoentes de 0 até 20 e módulos de 2 até 20 [3].
6. Explique por que cancelar 2 na equação 2x ≡2 módulo 4 elimina uma solução válida.

Continue por [Euclides e divisibilidade](/pt/topics/number-theory-divisibility-euclid/), [relações discretas](/pt/topics/discrete-relations-orders/) e [complexidade](/pt/topics/complexity-analysis/).