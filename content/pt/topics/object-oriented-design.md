---
id: object-oriented-design
title: "Design orientado a objetos: encapsulamento, composição e polimorfismo"
description: "Projete fronteiras orientadas a objetos com encapsulamento, composição, polimorfismo, contratos e modelo testado de preços."
category: engineering
difficulty: intermediate
updated: 2026-10-09
prerequisites: [testing-maintainability]
sources:
  - {title: "Microsoft Learn — Architectural principles", url: "https://learn.microsoft.com/en-us/dotnet/architecture/modern-web-apps-azure/architectural-principles", kind: "official engineering guide"}
  - {title: "Python typing — Protocols and structural subtyping", url: "https://typing.python.org/en/latest/reference/protocols.html", kind: "language typing documentation"}
---
O design orientado a objetos organiza comportamento em torno de **objetos com responsabilidades e contratos verificáveis**. Uma classe define como objetos são criados; o objeto tem identidade, estado e operações. Qualidade não depende de quantidade de classes ou caixas UML. Depende de invariantes preservados, colaboradores substituíveis com segurança e mudanças que não obriguem editar partes não relacionadas do sistema [1].

## Transforme requisitos em responsabilidades

Considere pedido com itens. As regras dizem que cada quantidade é positiva, preços unitários são não negativos, totais monetários usam duas casas decimais e um pedido enviado não aceita novos itens. O objeto de pedido deve **controlar** sua coleção de linhas mutáveis e decidir quando adicionar é permitido. Controller ou interface podem solicitar operação, mas não deveriam alterar a lista interna ignorando as transições do objeto.

**Encapsulamento** significa limitar, pela interface pública, quais mudanças clientes podem efetuar sobre o estado interno. Um atributo iniciado por underscore em Python não garante isso sozinho. Se o cliente recebe a referência à lista mutável, consegue alterá-la. Cópias defensivas ou visões imutáveis são necessárias em fronteiras relevantes. Para um valor simples e imutável, um módulo ou função pode ser mais adequado que criar uma classe artificial.

## Identidade, valor e invariantes

Dois pedidos distintos podem ter valor total e itens iguais, mas continuam objetos diferentes, com identificadores e históricos próprios. Isso ilustra **identidade**. Um montante de USD 12,50 costuma ser **valor**, cujo significado vem de quantia e moeda, não do endereço de memória. Misturar identidade com semântica de valor introduz erros em igualdade, cache e persistência.

Floats Python representam aproximações binárias e não garantem arredondamento decimal exato para negócios. O exemplo usa Decimal criado a partir de strings e uma regra explícita para arredondar descontos. O contrato aplica desconto ao **subtotal do pedido**; calcular por item pode produzir centavos diferentes e precisaria ser definido separadamente.

## Implemente pedido com política de preço composta

Composição faz o pedido referenciar uma política de preço em vez de herdar de uma classe de pedido especializada. O contrato da política é calcular um total válido sobre subtotal não negativo. O typing.Protocol do Python permite compatibilidade estrutural para verificadores estáticos, mas a segurança em execução ainda depende de validações e testes [2].

![O pedido compõe uma política de preços e mantém controle das linhas.](/diagrams/oop-composition.svg)

~~~python
from decimal import Decimal, ROUND_HALF_UP
from typing import Protocol

CENTAVO = Decimal("0.01")

class PoliticaPreco(Protocol):
    def total(self, subtotal: Decimal) -> Decimal: ...

class DescontoPercentual:
    def __init__(self, fracao: Decimal):
        if not Decimal("0") <= fracao <= Decimal("1"):
            raise ValueError("fracao deve estar em [0,1]")
        self.fracao = fracao

    def total(self, subtotal: Decimal) -> Decimal:
        return (subtotal * (1 - self.fracao)).quantize(
            CENTAVO, rounding=ROUND_HALF_UP)

class Pedido:
    def __init__(self, politica: PoliticaPreco):
        self._itens = []
        self._enviado = False
        self._politica = politica

    def adicionar(self, preco: Decimal, quantidade: int):
        if self._enviado or preco < 0 or quantidade <= 0:
            raise ValueError("alteracao invalida")
        if preco != preco.quantize(CENTAVO):
            raise ValueError("preco exige duas casas")
        self._itens.append((preco, quantidade))

    def enviar(self) -> Decimal:
        if self._enviado or not self._itens:
            raise ValueError("nao pode enviar")
        subtotal = sum((p * n for p, n in self._itens), Decimal("0"))
        total = self._politica.total(subtotal)
        if not Decimal("0") <= total <= subtotal:
            raise ValueError("politica invalida")
        self._enviado = True
        return total

pedido = Pedido(DescontoPercentual(Decimal("0.10")))
pedido.adicionar(Decimal("12.50"), 2)
assert pedido.enviar() == Decimal("22.50")
try:
    pedido.adicionar(Decimal("3.00"), 1)
    assert False
except ValueError:
    pass
~~~

É exemplo **em memória**. Não garante unicidade entre processos, persistência ou autorização de usuários. A política é presumidamente determinística e sem efeitos externos; se consultar serviço de preços remoto, novas condições de falha e retries idempotentes precisam ser projetados.

## Polimorfismo, interfaces e substituição

**Polimorfismo** permite que objetos diferentes satisfaçam o mesmo contrato de comportamento. Outra política, como desconto fixo limitado ao subtotal, pode ser passada ao Pedido sem alterar as chamadas existentes. Protocol descreve formato de métodos, mas o contrato contém regras semânticas, como não devolver total negativo. Uma classe com método total que também efetua cobrança escondida atende ao formato e viola o comportamento esperado.

A **interface** reúne operações disponíveis e respectivas expectativas. Python pode representá-la com Protocol ou classe base abstrata; Java e C# usam outras construções. Compatibilidade de assinatura não implica substituibilidade semântica. Defina pré-condições, pós-condições e testes quando consumidores dependem de garantias de preço, ausência de efeitos ou ordem de eventos.

## Herança versus composição

Herança representa relação **é um tipo de** e pode compartilhar implementação. É adequada quando instâncias do subtipo respeitam contrato da classe-base. Uma classe Quadrado herdando Retângulo que permita setters independentes de largura e altura pode quebrar código que assume independência: é a armadilha clássica de substituição. Composição representa **tem um/colabora com** e permite trocar comportamento sem herdar métodos irrelevantes.

Hierarquia pequena pode ser econômica; composição não é regra absoluta. Prefira composição quando variações são políticas de comportamento ou quando herança exporia detalhes internos. Em sentido contrário, criar dezenas de classes para um cálculo simples pode prejudicar a clareza.

## Ciclo de vida e transições de falha

O pedido começa como **rascunho** mutável e fica imutável após enviar, neste modelo. O invariante é: _pedido enviado implica ausência de novas alterações_. Conferir isso apenas no controller não basta, pois outros clientes podem invocar o mesmo objeto em rotinas assíncronas ou testes. Cada operação mutadora deve protegê-lo.

Se enviar também envolve pagamento ou persistência, uma variável local booleana não torna a transação distribuída atômica. O modelo de domínio expressa transições; repositório e idempotência durável devem garantir persistência e políticas de repetição. Um objeto bem encapsulado não substitui uma constraint de banco nem um lock distribuído.

## Custos e observabilidade

A função enviar soma n itens e custa O(n), supondo precisão Decimal limitada de forma razoável e política O(1). Adicionar usa O(1) amortizado sob crescimento de listas Python. O pedido ocupa O(n) memória. Recalcular subtotal pode ser mais seguro que manter soma em cache mutável, que precisaria ser atualizada em cada alteração; escolha conforme a carga medida.

| Decisão | Abordagem | Suposição falsa |
| --- | --- | --- |
| Bloquear alterações após envio | Validar cada método mutador | Underscore já impõe privacidade |
| Trocar regras de desconto | Compor contrato da política | Herança sempre é necessária |
| Representar dinheiro | Decimal e arredondamento definido | Float é decimal exato |
| Compartilhar pedido entre processos | Repositório e coordenação duráveis | Objeto Python impõe unicidade global |
| Substituir implementações | Conferir forma **e** semântica | Nome igual do método basta |

## Exercícios e verificação

1. Distinga identidade do objeto Pedido e valor representado pelo subtotal.
2. Substitua DescontoPercentual por desconto fixo que limita o resultado a zero e teste arredondamento.
3. Demonstre que não se pode adicionar item após envio nem enviar novamente o mesmo objeto.
4. Explique por que expor lista mutável quebra o contrato de encapsulamento mesmo com nome iniciado por underscore.
5. Identifique onde persistência, controle de acesso e envio duplicado exigem infraestrutura além da classe local.

**Capítulos relacionados:** [Low-level design](/pt/topics/low-level-design/) introduz transições; [testes e manutenção](/pt/topics/testing-maintainability/) explica contratos verificáveis [1].
