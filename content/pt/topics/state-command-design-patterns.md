---
id: state-command-design-patterns
title: "Padrões State e Command: transições, repetição e contratos de falha"
description: "Separe regras de estado de solicitações encapsuladas com State e Command, testando versões, ações inválidas e execução repetida."
category: engineering
difficulty: intermediate
updated: 2026-10-12
prerequisites: [low-level-design, design-pattern-families]
sources:
  - {title: "Refactoring.Guru — State", url: "https://refactoring.guru/design-patterns/state", kind: "technical pattern reference"}
  - {title: "Refactoring.Guru — Command", url: "https://refactoring.guru/design-patterns/command", kind: "technical pattern reference"}
  - {title: "AWS Builders Library — Making retries safe with idempotent APIs", url: "https://aws.amazon.com/builders-library/making-retries-safe-with-idempotent-APIs/", kind: "original engineering guidance"}
---
State e Command pertencem à família dos **padrões comportamentais**, mas resolvem problemas distintos. State delega comportamento conforme a fase atual do ciclo de vida; Command encapsula uma solicitação para separar o solicitante do executor da operação [1][2]. Nenhum padrão garante persistência, segurança entre threads, autorização ou mensagens confiáveis. Essas propriedades dependem de contratos e mecanismos separados. Vamos derivar ambos num fluxo de aprovação de documentos e localizar a fronteira onde uma operação repetida deixa de ser segura.

## Especifique o fluxo antes de escolher classes

Um documento começa em rascunho, entra em revisão e pode ser publicado. Publicar antes da revisão é proibido. Na hipótese deste capítulo, documento publicado é imutável. Existem duas operações: enviar para revisão e publicar. Erros não devem alterar o estado. A versão começa em zero e aumenta uma unidade por transição aceita. Retirada, papéis de moderação e edições concorrentes externas estão fora do modelo até que sejam definidos.

Uma transição é uma função parcial T(estado, operação) → novo_estado. Parcial significa que algumas combinações são inválidas. Com três fases e duas operações existem seis pares; apenas rascunho+enviar e revisão+publicar são permitidos. Enumerar esses casos antes das classes impede que a hierarquia esconda lacunas. O capítulo de [Low-Level Design](/pt/topics/low-level-design/) mostra máquinas de estado sem necessariamente criar uma classe para cada estado.

## Quando State justifica polimorfismo

Uma tabela ou condição simples costuma ser suficiente para poucas fases e ações. Classes de estado passam a fazer sentido quando cada fase acumula comportamento diferente, as regras evoluem independentemente ou blocos condicionais grandes repetem lógica. Com State, o documento mantém uma referência ao objeto de estado atual e delega a ele a ação; o objeto determina a próxima fase permitida [1]. Não confunda com Strategy: a Strategy é escolhida para variar algoritmos intercambiáveis, enquanto o ciclo de vida impõe restrições sobre as operações válidas.

O exemplo é intencionalmente local. Seu invariante é: ação aceita incrementa a versão exatamente uma vez; ação rejeitada não altera versão nem fase. Os objetos de estado não têm identidade durável própria. Somente fase e versão precisariam ser reconstruídas a partir de persistência adequada.

~~~python
class Draft:
    name = "draft"
    def submit(self):
        return Review()
    def publish(self):
        raise ValueError("review required")

class Review:
    name = "review"
    def submit(self):
        raise ValueError("already in review")
    def publish(self):
        return Published()

class Published:
    name = "published"
    def submit(self):
        raise ValueError("immutable document")
    def publish(self):
        raise ValueError("already published")

class Document:
    def __init__(self):
        self.state = Draft()
        self.version = 0
    def apply(self, action):
        if action not in ("submit", "publish"):
            raise ValueError("unknown action")
        next_state = getattr(self.state, action)()
        self.state = next_state
        self.version += 1
        return self.state.name

d = Document()
assert (d.state.name, d.version) == ("draft", 0)
try:
    d.apply("publish")
except ValueError:
    pass
else:
    raise AssertionError("draft was published")
assert (d.state.name, d.version) == ("draft", 0)
assert d.apply("submit") == "review"
assert d.apply("publish") == "published"
assert (d.state.name, d.version) == ("published", 2)
for invalid in ("publish", "submit", "delete"):
    try:
        d.apply(invalid)
    except ValueError:
        pass
    else:
        raise AssertionError("invalid action accepted")
assert d.version == 2
~~~

Esse código não representa uma obrigação de usar polimorfismo em todo fluxo. Acrescentar fase exige revisar a interface e possíveis transições de outras classes. O getattr dinâmico só está restrito porque a entrada passa por uma lista fechada de ações. Sem essa validação, seria possível acessar membros que nunca deveriam ser comandos públicos.

## Command separa intenção e execução

Command contém a operação desejada e seus argumentos; um invocador decide quando chamá-la no receptor [2]. É útil para handlers HTTP, agendamento, histórico e filas. A existência do objeto Command representa uma **solicitação**, não comprova que o efeito tenha sido confirmado. Repetir a chamada após timeout pode duplicar efeitos, a menos que o receptor defina deduplicação estável.

O exemplo utiliza a versão esperada como pré-condição otimista. Comandos com versão desatualizada falham em vez de sobrescrever silenciosamente uma atualização nova. Construir o comando não altera o documento.

~~~python
from dataclasses import dataclass

@dataclass(frozen=True)
class TransitionCommand:
    action: str
    expected_version: int
    def execute(self, receiver):
        if not isinstance(self.expected_version, int) or self.expected_version < 0:
            raise ValueError("invalid version")
        if receiver.version != self.expected_version:
            raise ValueError("version conflict")
        return receiver.apply(self.action)

doc = Document()
cmd = TransitionCommand("submit", 0)
assert doc.version == 0
assert cmd.execute(doc) == "review"
try:
    cmd.execute(doc)
except ValueError:
    pass
else:
    raise AssertionError("stale command replayed")
assert (doc.state.name, doc.version) == ("review", 1)
assert TransitionCommand("publish", 1).execute(doc) == "published"
~~~

Rejeitar execução duplicada **não equivale a sucesso idempotente**. Cliente que repete submit com versão zero recebe conflito, não a resposta anterior. Um contrato de idempotência pode exigir armazenar de forma durável (solicitante, ID da operação, hash do payload, resultado concluído), na mesma fronteira transacional da mudança. A mesma chave com corpo diferente precisa de regra explícita. A Builders Library discute a importância da identidade estável da requisição durante retentativas [3].

## Complexidade e limites de consistência

Cada transição local realiza quantidade fixa de acessos e atribuições; por isso, tempo e memória adicional são O(1) para ações de tamanho fixo **neste modelo em memória**. Não se deve transferir a conclusão para o banco: índice, bloqueio, rede, log de transações e contenção têm custos próprios. A checagem ingênua de versão também falha entre processos se leitura e escrita forem operações separadas.

Uma implementação autoritativa pode usar UPDATE documents SET state=?, version=version+1 WHERE id=? AND version=? AND state=?. Quando o banco avalia a condição e atualiza atomicamente, no máximo uma requisição vence para uma dada versão. Verifique linhas afetadas e diferencie versão obsoleta, estado inválido e documento inexistente segundo o contrato. Essa consulta não autoriza o solicitante, não publica notificações e não fornece semântica exatamente uma vez para efeitos externos.

## Falhas, eventos e contraexemplos

Se publicar também envia uma notificação externa, notificar antes do commit pode anunciar publicação que sofreu rollback. Notificar depois do commit pode perder a mensagem se o processo cair. Uma outbox ou protocolo equivalente define a ligação entre commit e entrega. Mesmo assim, um relay pode entregar duplicatas; consumidores precisam de IDs de evento e política de repetição [3].

Uma fila de objetos Command não é event sourcing automaticamente. Comando descreve **o que foi solicitado**, enquanto evento de domínio descreve **o que aconteceu**. Um comando rejeitado não deve reaparecer no histórico como publicação confirmada. Undo também não é propriedade automática: desfazer pagamento ou publicação pode exigir compensação nova e autorizada, não restauração de objeto em memória.

## Escolha orientada pelo problema

Use tabela para transições pequenas e estáveis; State para comportamento substancial que varia por fase; Command para invocação desacoplada ou adiada; Strategy para escolher entre algoritmos. Ao introduzir persistência e fila, projete antes o contrato de retry e deduplicação. Não crie uma classe de comando para cada função de uma linha só para reproduzir um diagrama. Evite concentrar permissões, regras de estado, transmissão e retentativas num objeto monolítico.

Revise o código pelos efeitos observáveis, não pelos nomes dos padrões. Mudança de versão, ações inválidas, identidade do ator, durabilidade e recuperação são promessas que precisam de verificações independentes. Padrões localizam responsabilidades; não substituem testes.

## Exercícios e verificação

1. Enumere seis combinações de fase e ação. Identifique sucesso ou erro e versão final; justifique por que erro mantém estado.
2. Adicione operação withdraw, válida apenas durante revisão. Atualize o modelo e os testes e discuta o custo de acrescentar método a todos os estados.
3. Faça duas requisições com expected_version=1 sobre documento durável. Especifique UPDATE atômico e resultado esperado para a requisição perdedora.
4. Compare contratos de repetição: devolver conflito ou retornar resposta armazenada. Indique os dados duráveis necessários à segunda opção.
5. Diferencie Command, evento de domínio, Strategy e State em autorização de pagamento. Explique por que histórico em memória não constitui livro-razão confiável.

Leituras relacionadas: [famílias de padrões](/pt/topics/design-pattern-families/), [refatoração e padrões](/pt/topics/refactoring-design-patterns/) e [confiabilidade de API](/pt/topics/api-reliability/).