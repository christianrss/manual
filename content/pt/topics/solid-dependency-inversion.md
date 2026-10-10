---
id: solid-dependency-inversion
title: "SOLID, inversão de dependências e contratos de comportamento"
description: "Aplique SRP, OCP, LSP, ISP e DIP com contratos Python, fronteiras estáveis e testes de comportamento verificáveis."
category: engineering
difficulty: intermediate
updated: 2026-10-10
prerequisites: [object-oriented-design, low-level-design]
sources:
  - {title: "Microsoft Learn — Architectural principles", url: "https://learn.microsoft.com/en-us/dotnet/architecture/modern-web-apps-azure/architectural-principles", kind: "official engineering guide"}
  - {title: "Python typing — Protocols and structural subtyping", url: "https://typing.python.org/en/latest/reference/protocols.html", kind: "language typing documentation"}
  - {title: "Google Engineering Practices — Code review", url: "https://google.github.io/eng-practices/review/", kind: "engineering guideline"}
---
SOLID reúne cinco heurísticas de design orientado a objetos: responsabilidade única, aberto/fechado, substituição de Liskov, segregação de interfaces e inversão de dependências. São **guias de decisão**, não axiomas matemáticos nem obrigação de maximizar abstrações. O objetivo é localizar mudanças, explicitar promessas de comportamento e testar componentes sem inicializar toda a infraestrutura de produção. Uma abstração vale quando protege política ou fronteira real; prejudica quando apenas repete uma chamada óbvia [1].

## Coesão antes de classes

Um componente possui **alta coesão** quando seus métodos contribuem para uma responsabilidade reconhecível. O SRP costuma ser resumido como uma razão para mudar. Refere-se a agentes ou políticas que causam mudanças, não literalmente um método por classe. Uma regra de alerta pode decidir se a temperatura supera limite; um adaptador de rede envia a mensagem resultante. Misturar hardware, comparação, e-mail e auditoria numa classe dificulta testar a decisão sem infraestrutura externa.

Um serviço coeso pode ter vários métodos. Por outro lado, separar todo getter ou operação de uma linha em serviços diferentes introduz indireção e coordenação. A pergunta é: acrescentar novo canal de entrega deveria exigir mudar a regra do limite? Se não, provavelmente são responsabilidades diferentes.

## OCP: estender variações controladas

O **princípio aberto/fechado** favorece estender um contrato estável em vez de editar a regra central a cada variante nova. Vários if/elif para selecionar SMTP, SMS e push podem justificar uma interface pequena MessageSender quando novas entregas são exigência real. Mas criar infraestrutura de plugins num programa com um único remetente fixo pode ser especulação dispendiosa.

'Fechado para modificação' não significa 'jamais edite classe existente'. Bugs e requisitos novos legitimamente exigem mudanças. A meta é evitar alterações não relacionadas e manter compatibilidade dos clientes. Use composição quando apropriado, exigindo que novas implementações respeitem contratos de entrada e saída [1].

## LSP: substituição trata semântica

O **princípio de substituição de Liskov** determina que subtipo ou implementação possa substituir outra sem violar expectativas de quem usa o contrato. Assinaturas iguais não bastam. Suponha que read(key) prometa retornar None quando a chave não existe. Uma implementação que inesperadamente lança exceção quebra consumidores, mesmo que a assinatura passe na verificação de tipos. Um notificador que retorna sucesso e descarta mensagens silenciosamente também pode violar a garantia.

Um exemplo clássico é Quadrado herdando Retângulo mutável com set_width e set_height independentes. Alterar a largura do quadrado também altera a altura, contrariando a expectativa de clientes. O problema é a **promessa comportamental** herdada, não a relação matemática entre quadrados e retângulos.

## ISP: interfaces específicas dos consumidores

O **princípio de segregação de interfaces** recomenda que clientes dependam só das operações necessárias. Uma tela de relatório somente de leitura não deveria implementar escrever, excluir, iniciar transação e migrar esquema apenas para consultar um registro. Separe leitura e escrita quando consumidores possuem requisitos ou permissões diferentes. Mas não fracione uma interface pequena em dezenas de tipos de método único sem uma fronteira real.

Contrato estreito reduz dependências e facilita doubles de teste. Ele **não** impõe autorização sozinho: um serviço pode cumprir interface de consulta e ainda acessar dados de outro tenant indevidamente. Políticas de domínio e identidade precisam ser verificadas à parte.

## DIP: política acima da infraestrutura

**Inversão de dependência** significa que políticas de alto nível dependem de abstrações comportamentais, não criam infraestrutura concreta no núcleo. No exemplo, RegraAlerta conhece apenas o contrato do remetente. A aplicação conecta adaptador de produção ou coletor de testes. Python Protocol suporta verificação estrutural, então classes implementadoras não precisam herdar explicitamente do protocolo [2].

![A política de alertas depende de um contrato, enquanto adaptadores fornecem entrega.](/diagrams/solid-boundaries.svg)

~~~python
from decimal import Decimal
from typing import Protocol

class Remetente(Protocol):
    def enviar(self, destino: str, mensagem: str) -> None: ...

class RegraAlerta:
    def __init__(self, remetente: Remetente, limite: Decimal):
        if limite < 0:
            raise ValueError("limite deve ser nao negativo")
        self._remetente = remetente
        self._limite = limite

    def verificar(self, destino: str, valor: Decimal) -> bool:
        if not destino:
            raise ValueError("destino obrigatorio")
        if valor > self._limite:
            self._remetente.enviar(destino, f"acima de {self._limite}")
            return True
        return False

class RemetenteColetor:
    def __init__(self):
        self.mensagens = []
    def enviar(self, destino: str, mensagem: str) -> None:
        self.mensagens.append((destino, mensagem))

falso = RemetenteColetor()
regra = RegraAlerta(falso, Decimal("30"))
assert not regra.verificar("ops", Decimal("30"))
assert regra.verificar("ops", Decimal("30.01"))
assert falso.mensagens == [("ops", "acima de 30")]
try:
    RegraAlerta(falso, Decimal("-1"))
    assert False
except ValueError:
    pass
~~~

O exemplo é **síncrono e local**. Não garante entrega, tentativas, limites de envio nem durabilidade. Se enviar lança exceção, verificar propaga a falha; o chamador deve decidir como reagir. Integrações reais distinguem intenção de notificação e confirmação da entrega: padrões de interface não tornam uma chamada de rede atômica.

## Raiz de composição e controle das dependências

A **composition root** é a fronteira da aplicação que cria objetos e conecta dependências. Código de inicialização pode instanciar adaptadores SMTP, bancos e clientes HTTP, enquanto regras de domínio recebem contratos. Configuração fica fora da política e testes podem usar colaboradores determinísticos.

Injeção de dependência é apenas uma maneira de fornecer dependências. Não requer container nem framework. Passar colaborador no construtor, como no exemplo, normalmente basta. Usar service locator oculto no domínio pode tornar dependências menos visíveis e testes mais difíceis, mesmo sob o discurso de inversão.

## Fronteiras de teste e substituição comportamental

O `Protocol` define forma de métodos para tipagem estática, não garante comportamento, ordem, efeitos nem entrega na rede [2]. Especifique a promessa observável: para valor igual ao limite, nenhuma solicitação; para valor acima, **uma única solicitação** ao remetente. Isso pode ser testado localmente usando o coletor definido anteriormente.

```python
def contrato_remetente(fabrica):
    remetente = fabrica()
    regra = RegraAlerta(remetente, Decimal("30"))
    assert regra.verificar("ops", Decimal("30")) is False
    assert regra.verificar("ops", Decimal("31")) is True
    assert remetente.mensagens == [("ops", "acima de 30")]

contrato_remetente(RemetenteColetor)

class RemetenteDuplicador(RemetenteColetor):
    def enviar(self, destino, mensagem):
        super().enviar(destino, mensagem)
        super().enviar(destino, mensagem)

try:
    contrato_remetente(RemetenteDuplicador)
except AssertionError:
    pass
else:
    raise AssertionError("LSP: duplicacao nao detectada")
```

O segundo remetente tem assinatura compatível e viola a cardinalidade declarada. O teste não comprova SMTP, autenticação ou entrega; essas propriedades exigem contratos de adaptação e testes de integração próprios. Uma exceção de rede pode representar resultado desconhecido, não falha definitiva. Revise esses efeitos observáveis e não atributos privados ao refatorar [3]. Uma abstração só compensa quando protege mudanças independentes reais, não quando replica trivialmente uma chamada.
## Custos, falhas e excesso de abstração

| Princípio | Mudança visada | Risco do exagero |
| --- | --- | --- |
| SRP | Separar motivos não relacionados | Classe para cada linha |
| OCP | Acrescentar variante necessária | Framework de plugins desnecessário |
| LSP | Preservar contratos comportamentais | Interface fraca escondendo falhas |
| ISP | Restringir dependências do consumidor | Muitos protocolos triviais |
| DIP | Isolar política da infraestrutura | Service locator/abstrair tudo |

Toda interface aumenta vocabulário e custo de manutenção. Se há só uma implementação, sem necessidade de isolamento de testes ou fronteira política, função direta pode ser melhor. Por outro lado, chamadas de infraestrutura espalhadas pelas regras dificultam injeção de falhas, migração e revisão. Avalie cenários de mudança, não conformidade mecânica às siglas.

## Exercícios e verificação

1. Identifique o que muda ao incluir um canal novo de notificação sem alterar a regra de limite.
2. Explique por que um remetente que responde sucesso descartando mensagens pode violar LSP.
3. Acrescente outro coletor com representação interna diferente e mesmo contrato observável.
4. Teste igualdade ao limite, valor imediatamente acima e destino inválido sem rede.
5. Explique por que enviar mensagem e confirmar uma transação de banco exige mais que DIP para garantir confiabilidade.

**Capítulos relacionados:** [Orientação a objetos](/pt/topics/object-oriented-design/) introduz composição; [low-level design](/pt/topics/low-level-design/) trata transições e fronteiras; [testes](/pt/topics/testing-maintainability/) desenvolve contratos [1][3].
