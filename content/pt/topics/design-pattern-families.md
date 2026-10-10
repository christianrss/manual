---
id: design-pattern-families
title: "Famílias de padrões de projeto: Builder, Facade e Observer"
description: "Derive padrões criacionais, estruturais e comportamentais com exemplos executáveis de Builder, Facade e Observer e contratos de falha."
category: engineering
difficulty: intermediate
updated: 2026-10-10
prerequisites: [clean-code-cohesion-coupling, refactoring-design-patterns]
sources:
  - {title: "Refactoring.Guru — Design patterns catalog", url: "https://refactoring.guru/design-patterns/catalog", kind: "technical pattern catalog"}
  - {title: "Refactoring.Guru — Builder", url: "https://refactoring.guru/design-patterns/builder", kind: "technical pattern reference"}
  - {title: "Refactoring.Guru — Facade", url: "https://refactoring.guru/design-patterns/facade", kind: "technical pattern reference"}
  - {title: "Refactoring.Guru — Observer", url: "https://refactoring.guru/design-patterns/observer", kind: "technical pattern reference"}
---
Padrões de projeto são respostas reutilizáveis a **pressões recorrentes sobre responsabilidades**, não certificados de arquitetura correta. Primeiro identifique o requisito de mudança, o comportamento público, a falha possível e uma alternativa simples; depois nomeie o padrão. O catálogo distingue padrões **criacionais** (construção), **estruturais** (composição de colaboradores) e **comportamentais** (algoritmos, eventos e interação) [1]. Nenhuma categoria fornece, por si, garantias de execução, e padrões podem coexistir.

O capítulo existente de [Strategy, Adapter e Decorator](/pt/topics/refactoring-design-patterns/) já demonstra seleção de algoritmos, tradução de interfaces e envolvimento de chamadas. Aqui adicionaremos exemplos **executáveis** de Builder, Facade e Observer. Conhecer nomes ajuda a conversar sobre soluções; engenharia exige entender também **quando não utilizar** uma abstração.

## Escolha a partir de uma necessidade de mudança

| Pressão de mudança | Padrão candidato | Alternativa mais simples | Custo principal |
| --- | --- | --- | --- |
| Produto montado em etapas com validação | Builder | Construtor com argumentos nomeados | Estado mutável da montagem |
| Cliente coordena vários subsistemas | Facade | Função pequena de aplicação | Indireção e falhas ocultas |
| Assinantes entram e saem independentemente | Observer | Callback direto | Exceções, ordem e entrega |
| Algoritmos diferentes sob um contrato | Strategy | Condicional pequeno | Hierarquia desnecessária |
| Interface externa incompatível | Adapter | Função de conversão | Diferenças semânticas |
| Comportamento extra em torno da operação | Decorator | Wrapper explícito | Ordem dos efeitos |

A decisão depende de quem muda, com que frequência e do contrato. Uma expressão aritmética simples não melhora automaticamente ao receber três interfaces e uma fábrica. No extremo oposto, codificar regras de negócio dentro do SDK de um fornecedor dificulta testes e versões [1].

## Criacional: Builder para um relatório validado

O relatório precisa de título não vazio, ao menos uma seção e **títulos de seção únicos**. O cliente acrescenta seções gradualmente, mas o relatório construído deve continuar igual se o builder for reutilizado depois. É um cenário plausível de Builder porque sequência de montagem e validação têm responsabilidade comum [2]. Se todos os campos fossem obrigatórios e definidos de uma vez, um construtor direto provavelmente seria melhor.

```python
from dataclasses import dataclass

@dataclass(frozen=True)
class Relatorio:
    titulo: str
    secoes: tuple[tuple[str, str], ...]

class ConstrutorRelatorio:
    def __init__(self, titulo):
        if not isinstance(titulo, str) or not titulo.strip() or titulo.strip() != titulo:
            raise ValueError("titulo invalido")
        self._titulo = titulo
        self._secoes = []
        self._titulos = set()

    def adicionar(self, titulo, texto):
        if (not isinstance(titulo, str) or not titulo.strip()
                or titulo.strip() != titulo or not isinstance(texto, str)
                or not texto.strip()):
            raise ValueError("secao invalida")
        if titulo in self._titulos:
            raise ValueError("titulo repetido")
        self._titulos.add(titulo)
        self._secoes.append((titulo, texto))
        return self

    def construir(self):
        if not self._secoes:
            raise ValueError("exige ao menos uma secao")
        return Relatorio(self._titulo, tuple(self._secoes))

construtor = ConstrutorRelatorio("Operacao").adicionar("Riscos", "Baixo")
primeiro = construtor.construir()
construtor.adicionar("Acoes", "Revisar")
segundo = construtor.construir()
assert primeiro.secoes == (("Riscos", "Baixo"),)
assert len(segundo.secoes) == 2
try:
    construtor.adicionar("Riscos", "Repetido")
except ValueError:
    pass
else:
    raise AssertionError("duplicata foi aceita")
```

**Invariante:** `_titulos` contém exatamente os títulos presentes em `_secoes` após cada chamada válida. Como a validação ocorre **antes** da mutação, uma chamada inválida não altera o estado. A transformação da lista em tupla impede que adições posteriores mudem o produto anterior: neste exemplo, `Relatorio` contém apenas strings e tuplas imutáveis. Com comprimento limitado de strings e hashing esperado constante, cada adição custa `O(1)` esperado; construir `k` seções custa `O(k)` tempo e memória extra. Esse construtor não é thread-safe nem fornece persistência.

**Builder versus Factory:** Builder controla **etapas da montagem**. Uma fábrica escolhe a implementação ou produto a criar. No Factory Method clássico, subclasses especializam um ponto de criação; um dicionário que mapeia nomes para construtores é apenas uma fábrica simples e não necessariamente o padrão formal. Não chame toda função que devolve objeto de Builder ou Factory Method [1][2].

## Estrutural: Facade sobre duas fontes de dados

Considere uma tela que exibe nome do produto e quantidade disponível. Sem fronteira, cada consumidor precisa conhecer o catálogo, o estoque, a política para dados ausentes e a ordem das chamadas. Facade oferece uma entrada menor. Sua função é **simplificar o uso de um subsistema**, ao contrário de Adapter, que converte uma interface incompatível em outra [3].

```python
class Catalogo:
    def __init__(self, nomes):
        self.nomes = dict(nomes)

    def nome(self, codigo):
        return self.nomes.get(codigo)

class EstoqueAtual:
    def __init__(self, quantidades):
        self.quantidades = dict(quantidades)

    def quantidade(self, codigo):
        return self.quantidades.get(codigo)

class VisaoProduto:
    def __init__(self, catalogo, estoque):
        self.catalogo, self.estoque = catalogo, estoque

    def resumo(self, codigo):
        if not isinstance(codigo, str) or not codigo:
            raise ValueError("codigo invalido")
        nome = self.catalogo.nome(codigo)
        if nome is None:
            raise KeyError(codigo)
        qtd = self.estoque.quantidade(codigo)
        if type(qtd) is not int or qtd < 0:
            raise ValueError("estoque ausente ou invalido")
        return (codigo, nome, qtd)

visao = VisaoProduto(Catalogo({"A": "Caderno"}), EstoqueAtual({"A": 4}))
assert visao.resumo("A") == ("A", "Caderno", 4)
try:
    VisaoProduto(Catalogo({"A": "Caderno"}), EstoqueAtual({})).resumo("A")
except ValueError:
    pass
else:
    raise AssertionError("estoque ausente foi aceito")
```

As duas consultas em dicionário têm tempo `O(1)` **esperado** sob hipóteses usuais de hashing. A tupla resultante é um **resultado local imutável**, não uma prova de snapshot consistente no banco: os dados podem mudar entre as leituras, e rede e banco introduzem latência e falhas. Facade não fornece atomicidade, autenticação, isolamento nem retentativas automaticamente. Uma fachada que captura qualquer exceção e devolve sucesso inventado ou que concentra todas as responsabilidades da aplicação pode piorar o sistema [3].

## Comportamental: Observer com contrato de callbacks explícito

Observer permite que um publicador notifique ouvintes cadastrados independentemente [4]. Seu nome não define questões decisivas: callbacks são síncronos? Uma exceção interrompe o envio? O que ocorre quando alguém sai durante a publicação? O evento é persistido? Definiremos as respostas **antes** da implementação.

Neste modelo, callbacks executam **sincronamente numa única thread**, na ordem do cadastro. Uma cópia dos ouvintes é criada no início da publicação. Cancelamentos feitos por callbacks, portanto, afetam apenas **publicações posteriores**. Cadastro duplicado é rejeitado; exceções se propagam e impedem chamar os demais ouvintes. Não existe fila durável nem replay.

```python
class FonteEventos:
    def __init__(self):
        self.ouvintes = []

    def inscrever(self, ouvinte):
        if not callable(ouvinte) or ouvinte in self.ouvintes:
            raise ValueError("ouvinte invalido ou repetido")
        self.ouvintes.append(ouvinte)

    def remover(self, ouvinte):
        if ouvinte not in self.ouvintes:
            raise ValueError("ouvinte nao encontrado")
        self.ouvintes.remove(ouvinte)

    def publicar(self, evento):
        for ouvinte in tuple(self.ouvintes):
            ouvinte(evento)

fonte = FonteEventos()
eventos = []

def primeiro_ouvinte(evento):
    eventos.append(("primeiro", evento))
    fonte.remover(primeiro_ouvinte)

def segundo_ouvinte(evento):
    eventos.append(("segundo", evento))

fonte.inscrever(primeiro_ouvinte)
fonte.inscrever(segundo_ouvinte)
fonte.publicar("criado")
fonte.publicar("atualizado")
assert eventos == [
    ("primeiro", "criado"), ("segundo", "criado"), ("segundo", "atualizado")
]
```

O snapshot da lista é uma invariante **da publicação**, não um lock. Uma segunda thread ainda pode modificar o cadastro durante a operação; publicação recursiva pode chamar ouvintes novamente e causar recursão sem limite. Um callback lento bloqueia os próximos. Quando um falha, o evento foi entregue **parcialmente** e repetir tudo pode duplicar efeitos anteriores. Para oferecer entrega durável ou assíncrona, é preciso reprojetar identidade de eventos, confirmação, isolamento de falhas, ordem, replay e backpressure — não apenas acrescentar um broker [4].

## Distinga padrões próximos pela responsabilidade

**State e Strategy:** ambos delegam comportamento, mas State representa transições válidas do objeto, enquanto Strategy escolhe algoritmo sob um contrato de entrada e saída. Uma reserva confirmada não pode voltar a pendente apenas porque um objeto Strategy é substituível. **Facade e Mediator:** Facade simplifica acesso **externo** ao subsistema; Mediator coordena comunicação **entre** colaboradores. **Observer e Command:** Observer notifica inscritos; Command representa uma ação solicitada que só pode ser armazenada ou repetida segundo um contrato explícito. São distinções de projeto, não provas de consistência transacional [1].

Evite Singletons globais sem análise: podem ocultar estado mutável, prejudicar testes e complicar ciclo de vida. Também não assuma que padrões exigem herança: funções e composição em Python frequentemente expressam a intenção com menos código. A escolha deve refletir a mudança provável, não o número de caixas no diagrama.

## Exercícios e verificação

1. Construa relatório, reutilize o Builder e prove que o snapshot anterior não muda. Teste construção vazia, títulos duplicados e espaços inválidos.
2. Faça a fachada consultar produto existente sem estoque e explique por que a quantidade não deve ser presumida zero. Como garantir snapshot consistente com dois serviços?
3. Durante o Observer, cadastre um terceiro ouvinte. Determine se ele será chamado na publicação **atual** ou na **próxima** e confira por teste independente.
4. Faça o primeiro inscrito lançar exceção; rastreie quem executou. Compare propagação com política de isolamento que coleta erros e discuta o contrato alterado.
5. Compare chamada direta, fábrica simples, Builder, Strategy e Facade; descreva um cenário em que cada um **reduz ou aumenta** acoplamento.
6. Derive o custo esperado de construir relatório com `k` seções, explicitando hipóteses de hashing e comprimento das strings.
7. Explique por que migrar Observer síncrono para broker muda tratamento de falhas, confirmações, duplicatas e ordenação, não sendo refatoração pura.

**Pré-requisitos e continuidade:** [Clean Code](/pt/topics/clean-code-cohesion-coupling/) aborda coesão; [SOLID](/pt/topics/solid-dependency-inversion/) discute substituição; [Strategy/Adapter/Decorator](/pt/topics/refactoring-design-patterns/) cobre os padrões anteriores. [Low-level design](/pt/topics/low-level-design/) desenvolve máquinas de estado; [mensageria](/pt/topics/asynchronous-messaging/) analisa fronteiras assíncronas duráveis.
