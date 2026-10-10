---
id: low-level-design
title: "Low-Level Design: contratos, máquinas de estados e dependências"
description: "Projete componentes sustentáveis a partir de invariantes, transições, interfaces e direção de dependências, com modelo testado."
category: engineering
difficulty: advanced
updated: 2026-10-10
prerequisites: [testing-maintainability, database-consistency]
sources:
  - {title: "Microsoft Learn — Architectural principles", url: "https://learn.microsoft.com/en-us/dotnet/architecture/modern-web-apps-azure/architectural-principles", kind: "official engineering guide"}
  - {title: "Google Engineering Practices — The Standard of Code Review", url: "https://google.github.io/eng-practices/review/reviewer/standard.html", kind: "engineering guideline"}
---
**Low-Level Design (LLD)** traduz regras do produto em componentes, interfaces, estruturas de dados e transições válidas de estado. Não é competição por quantidade de padrões nem apenas desenhar diagrama UML de classes. Um projeto é útil quando outro engenheiro compreende seus contratos, implementa comportamento e altera o código sem quebrar invariantes fundamentais [1][2].

## Comece pelos invariantes, não pelas classes

Considere serviço de reservas. Uma reserva pode estar **pendente**, **confirmada** ou **cancelada**. Reserva confirmada não volta a pendente. Cancelamento é terminal no contrato deste exemplo. O identificador não muda depois da criação. Transições válidas: pendente→confirmada, pendente→cancelada e confirmada→cancelada. Não existe cancelada→confirmada; nova reserva exige novo objeto. Outro negócio pode escolher regras diferentes, mas elas devem ser explícitas antes de decidir nomes de classes.

Diferencie **invariante** ('reserva cancelada não pode ser confirmada') de **fluxo** ('API consulta inventário e reserva'). Uma classe impõe regras locais, mas unicidade global de assento compartilhado entre processos cabe ao banco transacional ou outro mecanismo autoritativo. Um objeto não bloqueia um assento distribuído apenas porque seu método se chama reservar().

## Modele a máquina de estados

Desenhe antes da implementação para permitir que revisores questionem transições ausentes. Cada transição envolve estado inicial, evento, pré-condições, estado resultante e política de erro caso seja inválida. Determine se cancelar novamente é operação sem efeito (idempotente) ou erro; ambas podem ser válidas, mas ambiguidade prejudica clientes.

![Estados de uma reserva e transições permitidas.](/diagrams/reservation-state-machine.svg)

## Implementação reproduzível com responsabilidades pequenas

~~~python
from enum import Enum, auto

class Estado(Enum):
    PENDENTE = auto()
    CONFIRMADA = auto()
    CANCELADA = auto()

class Reserva:
    def __init__(self, identificador):
        if not identificador:
            raise ValueError("identificador obrigatorio")
        self._identificador = identificador
        self._estado = Estado.PENDENTE

    @property
    def estado(self):
        return self._estado

    @property
    def identificador(self):
        return self._identificador

    def confirmar(self):
        if self._estado != Estado.PENDENTE:
            raise ValueError("apenas pendentes podem ser confirmadas")
        self._estado = Estado.CONFIRMADA

    def cancelar(self):
        if self._estado == Estado.CANCELADA:
            return False
        self._estado = Estado.CANCELADA
        return True

reserva = Reserva("R-1")
assert reserva.estado == Estado.PENDENTE
reserva.confirmar()
assert reserva.estado == Estado.CONFIRMADA
assert reserva.cancelar()
assert not reserva.cancelar()
try:
    reserva.confirmar()
    assert False
except ValueError:
    pass
~~~

O exemplo funciona apenas em memória. Trata um objeto, sem transação concorrente de banco, sem autorização e sem eventos duráveis. Uma versão de produção precisa de persistência e política de acesso. O sublinhado dos atributos Python é **convenção**, não fronteira de segurança real. Encapsulamento ajuda colaboradores a respeitar o contrato; não substitui constraints do banco.

## Separe domínio, aplicação e infraestrutura

O objeto de domínio possui regras locais, não parsing HTTP nem pooling SQL. O **serviço de aplicação** coordena um caso de uso: verificar ator, acessar repositório, iniciar transação necessária, executar regra e persistir resultado. Uma **interface de repositório** descreve carregar e salvar reserva; um adaptador de banco implementa esse contrato. Controller web mapeia HTTP para serviço de aplicação e não deveria duplicar silenciosamente invariantes [1].

A direção da dependência importa. Se o domínio importa um cliente SQL concreto, fica acoplado à persistência. Serviço que depende de contrato abstrato pode trocar adaptador de banco e usar fake em testes limitados. Isso não significa criar interface para toda função: abstração extra deve corresponder a variação ou fronteira de teste real.

## Escolha padrões quando adicionam valor

| Problema | Ferramenta possível | Exagero |
| --- | --- | --- |
| Provedores de pagamento substituíveis | Strategy com interface pequena | Interface para helper trivial |
| Construção de objeto complexo válido | Builder ou construtor nomeado | Boilerplate para dois parâmetros |
| Integrar resposta legada | Adapter na fronteira | Classes que só copiam dados |
| Avisar observadores independentes | Eventos com contrato de entrega | Efeitos ocultos e ordem ambígua |
| Comportamento que depende de estado | Máquina de estados explícita | Dezenas de classes inúteis |

SOLID oferece heurísticas, não prova de correção. Responsabilidade única significa razões coerentes para mudar, não uma classe por linha. Inversão de dependência protege regra estável contra infraestrutura mutável, mas indireção sem fronteira real torna o sistema mais difícil de investigar [1].

## Falhas: concorrência, persistência e titularidade

Dois workers podem ler a mesma reserva pendente, concluir simultaneamente que ela pode ser confirmada e sobrescrever dados. Se confirmação dispara efeitos externos, ambas podem enviar avisos duplicados. Empregue lock transacional ou verificação otimista de versão na linha autoritativa; coordene notificações por outbox ou outro protocolo deliberado. Métodos do ORM não resolvem sozinhos corridas, retries e dual write.

Autorização deve conferir tenant e proprietário da reserva carregada, não tenant enviado arbitrariamente pelo cliente. Estado cancelado em memória não comprova commit durável. Após crash, recarregar precisa reconstruir estado permitido; teste serialização, mapping e migrações.

## Testar todas as transições, não apenas o caminho feliz

A máquina de estados descrita acima possui três estados e duas operações: são apenas seis combinações. O contrato especifica quais transições são permitidas e o que significa repetir um cancelamento.

```python
def criar_no_estado(estado):
    r = Reserva("R-teste")
    if estado == Estado.CONFIRMADA:
        r.confirmar()
    elif estado == Estado.CANCELADA:
        r.cancelar()
    return r

for estado in Estado:
    r = criar_no_estado(estado)
    if estado == Estado.PENDENTE:
        r.confirmar()
        assert r.estado == Estado.CONFIRMADA
    else:
        try:
            r.confirmar()
        except ValueError:
            pass
        else:
            raise AssertionError("transicao proibida")

for estado in Estado:
    r = criar_no_estado(estado)
    assert r.cancelar() == (estado != Estado.CANCELADA)
    assert r.estado == Estado.CANCELADA
    assert not r.cancelar()
```

Esses ensaios abrangem todas as combinações locais, **não** concorrência ou durabilidade. Cancelamento idempotente em objeto Python não demonstra que um serviço com banco, rede e retries preserva exatamente o mesmo resultado. Essa propriedade requer índices, condições transacionais, persistência, autorização por titular e testes sob falha. A revisão independente deve conseguir derivar a tabela de transições antes de ler o código [2].
## Exercícios e verificação

1. Construa tabela de transições com estados nas linhas e confirmar/cancelar nas colunas. Compare com o código.
2. Acrescente expiração e explique se o estado é terminal, se pode reativar e quem decide o horário autoritativamente.
3. Esboce interface de repositório e transação para confirmar reserva uma vez **dentro de um banco**.
4. Explique por que um diagrama com ReservationRepository não demonstra atomicidade de cancelamento distribuído.
5. Compare classe única com HTTP, SQL e regras a componentes separados por domínio/aplicação/adaptadores. Identifique mudança **específica** facilitada pela separação e situações em que o modelo simples é aceitável.
