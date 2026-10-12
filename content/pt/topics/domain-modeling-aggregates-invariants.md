---
id: domain-modeling-aggregates-invariants
title: "Modelagem de domínio: entidades, objetos de valor e invariantes de agregados"
description: "Diferencie identidade de valores imutáveis, escolha fronteiras transacionais e imponha invariantes de pedidos com contratos executáveis."
category: engineering
difficulty: intermediate
updated: 2026-10-12
prerequisites: [object-oriented-design, low-level-design, architecture-dependency-boundaries]
sources:
  - {title: "Microsoft Learn — Tactical DDD", url: "https://learn.microsoft.com/en-us/azure/architecture/microservices/model/tactical-ddd", kind: "official architecture guidance"}
  - {title: "Microsoft Learn — Domain model design", url: "https://learn.microsoft.com/en-us/dotnet/architecture/microservices/microservice-ddd-cqrs-patterns/ddd-oriented-microservice", kind: "official architecture guidance"}
  - {title: "Python — decimal module", url: "https://docs.python.org/3/library/decimal.html", kind: "language documentation"}
---
Modelagem de domínio traduz regras de negócio em **identidades, valores, transições e fronteiras de consistência**. Não consiste em dar nomes a tabelas nem gerar classes de um ORM. Um modelo útil rejeita operações inválidas e identifica qual autoridade deve preservar cada invariante quando requisições disputam os mesmos recursos. O DDD tático distingue entidades, objetos de valor e agregados para tornar essas responsabilidades explícitas [1].

## Identidade não é igualdade de atributos

Uma **entidade** possui identidade estável ao longo do tempo: o pedido O-41 continua sendo o mesmo quando muda de situação. Dois pedidos com itens idênticos não são intercambiáveis. Um **objeto de valor** é comparado pelos seus atributos, e não por identificador persistente: 12,50 em determinada moeda representa um valor. Objetos de valor permitem validar representação e aritmética no momento da construção. Uma dataclass congelada não torna automaticamente campos internos mutáveis em imutáveis; neste exemplo, todos os campos internos são strings e Decimal imutáveis [1][3].

Endereço pode ser valor dentro de um pedido, mesmo quando um cadastro de endereços possui identidade própria. A escolha depende de **como o domínio utiliza o conceito**, não da existência de chave primária no banco. Não transforme cada linha numa raiz de agregado. A raiz define quais operações podem modificar seus objetos e deve preservar invariantes locais.

## Formule invariantes antes de desenhar classes

Considere pedido simplificado com ID estável, moeda única, SKUs distintos, quantidades inteiras estritamente positivas e preços com até duas casas decimais. Enquanto está aberto, permite incluir linhas; depois de confirmado, não permite alterações. Um pedido confirmado deve possuir ao menos um item. Seu total é exatamente a soma de preço unitário vezes quantidade. Descontos, impostos, devoluções e captura de pagamento estão fora desse modelo didático, que não representa contabilidade ou checkout de produção.

Essas regras definem pós-condições testáveis. Incluir linha inválida não altera o conjunto anterior. SKU repetido gera erro, em vez de sobrescrever preço silenciosamente. Total não pode misturar moedas: somar 10 USD e 10 EUR sem conversão não produz quantidade monetária bem definida. Com Decimal finito e não negativo, o total permanece não negativo, embora sistemas reais precisem limitar precisão, magnitude e política de arredondamento [3].

## Implemente valor imutável e raiz do agregado

O contrato Python valida tipos recebidos e preserva snapshots após operações do chamador. Money congelado rejeita escala excessiva em vez de arredondar silenciosamente. Order guarda seu estado por convenção de encapsulamento e expõe uma tupla imutável das linhas. Isso impede append direto na coleção devolvida, mas sublinhados não são mecanismo de segurança da linguagem.

~~~python
from dataclasses import dataclass
from decimal import Decimal

@dataclass(frozen=True)
class Money:
    amount: Decimal
    currency: str

    def __post_init__(self):
        if (type(self.amount) is not Decimal or not self.amount.is_finite()
                or self.amount < 0 or self.amount.as_tuple().exponent < -2):
            raise ValueError("invalid monetary amount")
        if (not isinstance(self.currency, str) or len(self.currency) != 3
                or not self.currency.isascii() or not self.currency.isalpha()
                or self.currency != self.currency.upper()):
            raise ValueError("invalid currency")

@dataclass(frozen=True)
class OrderLine:
    sku: str
    quantity: int
    unit_price: Money

    def __post_init__(self):
        if not isinstance(self.sku, str) or not self.sku.strip():
            raise ValueError("missing sku")
        if type(self.quantity) is not int or self.quantity <= 0:
            raise ValueError("invalid quantity")
        if not isinstance(self.unit_price, Money):
            raise ValueError("invalid price")

class Order:
    def __init__(self, order_id, currency):
        Money(Decimal("0"), currency)
        if not isinstance(order_id, str) or not order_id.strip():
            raise ValueError("missing order id")
        self._id, self._currency = order_id, currency
        self._lines = ()
        self._status = "open"

    @property
    def lines(self):
        return self._lines

    @property
    def status(self):
        return self._status

    def add(self, line):
        if self._status != "open":
            raise ValueError("order is closed")
        if not isinstance(line, OrderLine) or line.unit_price.currency != self._currency:
            raise ValueError("incompatible line")
        if any(previous.sku == line.sku for previous in self._lines):
            raise ValueError("duplicate sku")
        self._lines = self._lines + (line,)

    def total(self):
        return Money(sum((line.unit_price.amount * line.quantity
                          for line in self._lines), Decimal("0")), self._currency)

    def place(self):
        if self._status != "open" or not self._lines:
            raise ValueError("cannot place order")
        self._status = "placed"
        return self.total()

order = Order("O-41", "USD")
first = OrderLine("BOOK", 2, Money(Decimal("12.50"), "USD"))
order.add(first)
snapshot = order.lines
order.add(OrderLine("PEN", 1, Money(Decimal("1.25"), "USD")))
assert len(snapshot) == 1 and len(order.lines) == 2
assert order.total() == Money(Decimal("26.25"), "USD")
assert order.place() == Money(Decimal("26.25"), "USD")
try:
    order.add(first)
except ValueError:
    pass
else:
    raise AssertionError("placed order was modified")
try:
    Money(Decimal("1.234"), "USD")
except ValueError:
    pass
else:
    raise AssertionError("excessive scale accepted")
~~~

Com n linhas armazenadas, add percorre no máximo n entradas e copia a tupla, custando O(n) tempo por inclusão bem-sucedida. Montar n linhas com cópias sucessivas tem custo acumulado O(n²), com O(n) espaço retido. Essa escolha privilegia snapshots previsíveis no exemplo pequeno, não desempenho. Dicionário por SKU pode reduzir verificações de duplicidade para tempo esperado O(1), mas muda o contrato de mutação e iteração. Calcular total percorre n linhas, exigindo O(n) operações aritméticas; precisão dos operandos Decimal também influencia o custo real.

## Agregado não é sinônimo de grafo inteiro do ORM

Agregado constitui fronteira de consistência transacional em torno de uma raiz e seus valores ou entidades subordinadas [1]. Pedido e linhas podem formar um agregado porque a raiz garante que “pedido confirmado contém linhas válidas e total estável” numa transição local. Entretanto, disponibilidade de estoque não é propriedade que esse objeto Order possa garantir em memória: pedidos diferentes disputam unidades. Confirmar pedido **não significa** que o estoque tenha sido reservado. Inventário exige autoridade transacional própria ou protocolo de reserva.

Erro frequente é montar agregado gigante que incorpora pedido, cliente, estoque, pagamento e transporte. Exigir bloqueio atômico de tudo gera contenção, acopla disponibilidade e cria dependências distribuídas inviáveis. Use a menor fronteira que contenha os invariantes que realmente exigem consistência imediata, não todos os objetos associados no mapeamento relacional [1][2].

## Validade local não garante concorrência correta

A raiz local impede dois SKUs iguais na mesma tupla, mas dois processos trabalhando sobre cópias do pedido O-41 podem aceitar alterações e depois sobrescrever o estado um do outro. Persistência geralmente exige atualização condicional por versão esperada, lock de linha ou estratégia de isolamento suportada pelo banco. A versão precisa ser verificada **atomicamente** com a escrita. Propriedade Python, valor congelado e campo “privado” não fornecem isolamento entre workers.

Autorização é obrigação independente. Um cliente pode informar ID e linha válidos e ainda não possuir permissão de editar o pedido. A aplicação deve autenticar ator, carregar o agregado autorizado e executar a transição atômica. Invariantes de domínio dizem se uma mudança faz sentido; não definem sozinhos quem pode solicitá-la.

## Falhas e situações em que DDD custa demais

Objetos de domínio não são obrigatórios em CRUD simples com pouco comportamento. Uma função de serviço clara e linhas SQL validadas podem ser mais fáceis de manter que uma hierarquia extensa. No outro extremo, armazenar fluxo complexo em colunas livremente editáveis permite combinações inválidas. Vocabulário DDD prejudica quando esconde transações reais, multiplica interfaces redundantes ou trata mensagens atrasadas como chamadas síncronas.

Money revela outra fronteira: Decimal evita problemas característicos de representação binária para números decimais, mas não determina taxa de câmbio, imposto, arredondamento legal ou exatidão da liquidação financeira [3]. Impedir valor negativo é decisão adequada ao preço unitário deste domínio, porém inadequada a um lançamento contábil com sinal ou ajuste de estorno. Premissas precisam ficar visíveis, não ser propagadas a todos os sistemas.

## Exercícios e verificação

1. Enumere OrderLine inválidas (quantidade booleana, SKU repetido, outra moeda, identificador vazio e preço com três casas). Confirme que cada erro preserva o estado anterior.
2. Derive o custo O(n²) de n inclusões em tupla imutável. Implemente alternativa por chave e explique o novo contrato de mutação e ordem.
3. Acrescente versão explícita e comando com expected_version. Explique por que comparar somente em memória não impede atualização perdida entre servidores.
4. Desenhe fronteiras distintas para pedido, estoque e pagamento. Identifique invariante local e outro que precisa de coordenação entre autoridades.
5. Explique por que Money imutável e válido não comprova correção de devoluções nem cálculos tributários.

Continue em [fronteiras arquiteturais](/pt/topics/architecture-dependency-boundaries/), [SOLID](/pt/topics/solid-dependency-inversion/) e [isolamento de transações](/pt/topics/transactional-indexing-isolation/).