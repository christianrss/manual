---
id: refactoring-design-patterns
title: "Refatoração e padrões: Strategy, Adapter e preservação de comportamento"
description: "Refatore com testes de contrato; compare Strategy, Adapter e Decorator em Python, com exemplos e limites práticos."
category: engineering
difficulty: intermediate
updated: 2026-10-09
prerequisites: [object-oriented-design, solid-dependency-inversion, testing-strategies]
sources:
  - {title: "Martin Fowler — Refactoring Boundary", url: "https://martinfowler.com/bliki/RefactoringBoundary.html", kind: "primary engineering essay"}
  - {title: "Refactoring.Guru — Strategy", url: "https://refactoring.guru/design-patterns/strategy", kind: "pattern reference"}
  - {title: "Refactoring.Guru — Adapter", url: "https://refactoring.guru/design-patterns/adapter", kind: "pattern reference"}
---
**Refatoração** altera a estrutura interna de um programa preservando comportamento observável segundo contrato explícito. Difere de acrescentar funcionalidade ou alterar intencionalmente uma regra de negócio. Padrões de projeto são **soluções nomeadas para problemas recorrentes de design**, não um concurso de sofisticação. Introduzir Strategy, Adapter ou Decorator só ajuda quando há variação ou incompatibilidade real de interface; abstração desnecessária pode dificultar depuração e manutenção [1][2].

## Defina o comportamento que deve ser preservado

Considere serviço que calcula preço com duas políticas de desconto. Entradas são subtotal Decimal não negativo e nome da política; saídas são totais arredondados uma vez em centavos. A interface pode garantir ainda qual exceção ocorre numa política desconhecida. Se refatorar muda arredondamento do total para cada linha, altera o tipo de erro ou introduz efeito externo, **não preserva comportamento** relativo à superfície definida.

Escreva testes de caracterização para casos típicos, zero, limites decimais e políticas inválidas antes de modificar. Testes fornecem evidência dos exemplos cobertos, não equivalência universal. Se há normas monetárias, confira expectativas por contrato de negócio separado em vez de reproduzir fórmula possivelmente defeituosa.

## Encontre uma fronteira útil, não apenas um smell

Um code smell sugere investigação, não comprova defeito. Condicional curta pode ser mais clara que hierarquia de classes. Refatoração compensa quando muitos consumidores repetem seleção de política e novas variações exigem mudanças espalhadas. Pergunte qual regra ou equipe muda, com que frequência e se clientes precisam escolher comportamento em tempo de execução.

Classe que calcula valores, envia e-mail e grava banco pode ter motivos não relacionados para mudar. Porém criar classe nova para cada expressão trivial aumenta boilerplate sem isolar dependências. A fronteira precisa tornar mudança provável mais barata e manter contratos explícitos.

## Antes: seleção condicional

A implementação simples possui duas opções explícitas e **não é automaticamente ruim**. A oportunidade de refatorar surgiria caso muitos componentes duplicassem a ramificação.

~~~python
from decimal import Decimal, ROUND_HALF_UP
CENTAVO = Decimal("0.01")

def total_antigo(subtotal, politica):
    if subtotal < 0:
        raise ValueError("subtotal negativo")
    if politica == "regular":
        multiplicador = Decimal("1.00")
    elif politica == "member":
        multiplicador = Decimal("0.90")
    else:
        raise ValueError("politica desconhecida")
    return (subtotal * multiplicador).quantize(CENTAVO, rounding=ROUND_HALF_UP)

assert total_antigo(Decimal("12.55"), "regular") == Decimal("12.55")
assert total_antigo(Decimal("12.55"), "member") == Decimal("11.30")
~~~

Há dispatch de tempo constante para quantidade fixa de políticas, supondo Decimal de precisão limitada. Um dicionário de implementações oferece outra forma de extensão, mas não muda significativamente a complexidade aritmética. Escolha por manutenção e contratos, não por promessa prematura de velocidade.

## Depois: Strategy com variação explícita

O **padrão Strategy** encapsula algoritmos intercambiáveis sob contrato comum [2]. A próxima versão usa dicionário de funções, representação leve de estratégias em Python. Mantém validação, arredondamento e exceções. Os checks comparam as versões para grade finita de entradas.

![O cálculo delega a estratégias intercambiáveis; adaptador separado traduz interface legada.](/diagrams/refactoring-patterns.svg)

~~~python
def regular(subtotal):
    return subtotal

def membro(subtotal):
    return subtotal * Decimal("0.90")

POLITICAS = {"regular": regular, "member": membro}

def total_novo(subtotal, politica):
    if subtotal < 0:
        raise ValueError("subtotal negativo")
    if politica not in POLITICAS:
        raise ValueError("politica desconhecida")
    return POLITICAS[politica](subtotal).quantize(CENTAVO, rounding=ROUND_HALF_UP)

for centavos in range(200):
    subtotal = Decimal(centavos) / 100
    for nome in ("regular", "member"):
        assert total_antigo(subtotal, nome) == total_novo(subtotal, nome)
for funcao in (total_antigo, total_novo):
    try:
        funcao(Decimal("1"), "invalid")
        assert False
    except ValueError:
        pass
~~~

Nova política altera o registro em vez da lógica central. Mas, se o requisito é uma única política fixa, mesmo registro é desnecessário. Strategy não implica receber funções arbitrárias da entrada do cliente: nomes devem mapear para **allowlist controlada pelo servidor** e implementações precisam de testes de contrato.

## Adapter, Decorator e Strategy não são iguais

**Adapter** traduz uma interface em outra. Imagine biblioteca legada com `quote_cents(inteiro)` enquanto serviço atual espera `total(Decimal)`; o adaptador valida conversão e devolve tipo esperado sem alterar biblioteca [3]. **Decorator** preserva interface externa e acrescenta comportamento ao redor, como tracing ou cache. Strategy troca algoritmo; Adapter traduz compatibilidade; Decorator envolve execução [2][3].

~~~python
class CotacaoLegada:
    def quote_cents(self, centavos):
        return centavos + 25

class AdaptadorLegado:
    def __init__(self, legado):
        self.legado = legado
    def total(self, valor):
        if valor < 0 or valor != valor.quantize(CENTAVO):
            raise ValueError("valor exige centavos nao negativos")
        centavos = int(valor * 100)
        return Decimal(self.legado.quote_cents(centavos)) / 100

adaptador = AdaptadorLegado(CotacaoLegada())
assert adaptador.total(Decimal("1.50")) == Decimal("1.75")
try:
    adaptador.total(Decimal("1.505"))
    assert False
except ValueError:
    pass
~~~

O exemplo pressupõe API legada em centavos inteiros e taxa fixa de 25 centavos. Em sistema financeiro real, é preciso definir moeda, overflow, falhas e se valor já inclui tarifas. Tradução de tipos não prova que provedor é correto, autorizado ou durável.

## Refatoração incremental e verificação

Um ciclo seguro é: estabelecer testes de comportamento → extrair operação pequena → validar → examinar diff → repetir. Prefira commits que separem mudanças estruturais de novos requisitos. Teste saídas e interações externas relevantes, não toda chamada privada, para permitir mover e renomear internals sem quebrar suíte [1].

Ao dividir classe grande, verifique clientes dependentes de estado mutável compartilhado, escopo transacional e ordem de execução. Extrair função pura é mais simples de provar que mover escrita entre bancos. Refatorar atravessando rede geralmente introduz **comportamentos novos**—timeouts, consistência eventual, mensagens duplicadas—e passa a ser migração arquitetural, não simples limpeza de código.

## Erros e escolha de padrões

| Pressão da mudança | Possibilidade | Erro comum |
| --- | --- | --- |
| Vários algoritmos intercambiáveis | Strategy | Classe por operação trivial |
| Método externo incompatível | Adapter | Supor que conversão garante semântica |
| Tracing ou cache opcional | Decorator | Camadas escondidas dependentes da ordem |
| Classe com assuntos distintos | Extrair componente coeso | Dependências circulares |
| Condicionais duplicadas | Função ou registro comum | Abstrair antes de entender comportamento |
| Separação de transações entre serviços | Redesenho explícito de workflow | Chamar mudança distribuída de simples refatoração |

Padrões podem coexistir: cliente de pagamento usa Adapter para PSP e Decorator para métricas, enquanto política de repetição pode usar Strategy. Cada camada acrescenta custos e modos de falha; revisar apenas diagramas não demonstra correção.

## Exercícios e verificação

1. Explique por que alterar arredondamento do subtotal para cada linha é mudança de comportamento, não refatoração pura.
2. Acrescente estratégia `vip` com desconto 15% e teste sem modificar opções anteriores.
3. Trace conversão de 1,50 no AdaptadorLegado e justifique rejeição de três casas decimais.
4. Dê um caso em que if/elif é mais claro que um registro de Strategy.
5. Explique por que mover escrita SQL para serviço remoto obriga rever idempotência e transações.

**Capítulos relacionados:** [Orientação a objetos](/pt/topics/object-oriented-design/), [SOLID](/pt/topics/solid-dependency-inversion/), [testes](/pt/topics/testing-strategies/) e [fronteiras de serviço](/pt/topics/service-boundaries/) fornecem contratos próximos [1].
