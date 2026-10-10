---
id: clean-code-cohesion-coupling
title: "Fundamentos de Clean Code: coesão, acoplamento e mudanças seguras"
description: "Derive fronteiras de código legível por coesão, acoplamento, funções puras, contratos e testes de um planejador de estoque reproduzível."
category: engineering
difficulty: intermediate
updated: 2026-10-10
prerequisites: [complexity-analysis, arrays-and-strings]
sources:
  - {title: "Google Engineering Practices — What to Look for in a Code Review", url: "https://google.github.io/eng-practices/review/reviewer/looking-for.html", kind: "primary engineering guidance"}
  - {title: "Martin Fowler — Refactoring Boundary", url: "https://martinfowler.com/bliki/RefactoringBoundary.html", kind: "primary engineering essay"}
  - {title: "Python Standard Library — dataclasses", url: "https://docs.python.org/3/library/dataclasses.html", kind: "official language documentation"}
---
Clean Code não é uma lista mecânica de métodos curtos, proibição de comentários ou número de classes. É um objetivo de engenharia: outro profissional deve compreender **comportamentos, invariantes, responsabilidades e pontos prováveis de mudança** e conseguir alterar o sistema sem regressões não relacionadas. As diretrizes de revisão do Google consideram projeto, correção, complexidade, nomes e testes em conjunto, sem transformar uma métrica de estilo em prova de qualidade [1]. Aqui estudaremos esses fundamentos **antes** de SOLID, herança e padrões de projeto.

## Legibilidade envolve decisões e contratos, não só formatação

Indentação consistente e nomes expressivos facilitam leitura, mas código elegante que produz resultado incorreto continua inadequado. Em uma função de estoque, `x` não descreve nada; `quantidade_disponivel` registra significado e unidade. Uma função chamada `validar_estoque` não deveria modificar valores inválidos silenciosamente. Comentários úteis justificam uma restrição inesperada; comentários que apenas repetem o comando aumentam ruído.

Um revisor precisa responder: quais entradas são válidas? Quem possui estado mutável? Que propriedade deve permanecer verdadeira? Qual dependência pode falhar? Onde uma regra futura deverá ser alterada? Quais testes verificam os resultados? Essas são perguntas, não limites universais de linhas por método. Extrair uma função pode explicitar a decisão ou simplesmente espalhar o raciocínio por arquivos diferentes [1].

## Coesão: agrupar responsabilidades que mudam juntas

**Coesão** caracteriza o quanto as operações de uma unidade colaboram para a mesma finalidade. Calcular a quantidade de reposição depende de política de estoque. Autenticar um fornecedor, estabelecer conexão HTTP e registrar uma compra remota dependem de infraestrutura. Quando a mesma função calcula, autentica e envia, testar uma regra simples exige rede ou muitos mocks.

Isso **não significa** criar uma classe para cada linha. Validação e cálculo podem pertencer a uma única função quando preservam o mesmo contrato. Um objeto pode legitimamente ter vários métodos que preservam a mesma invariante. A pergunta é: duas equipes ou razões independentes precisariam alterar o mesmo componente? Separar todo `if` num serviço para cumprir uma contagem artificial reduz a compreensão e acrescenta coordenação.

## Acoplamento: dependências semânticas e dependências de infraestrutura

**Acoplamento** descreve quanto uma mudança em determinada unidade obriga outras unidades a mudar. Dependência da regra de negócio em relação a quantidades e limites de estoque é necessária. Dependência dessa mesma regra da versão do SDK de um fornecedor, de credenciais HTTP ou de uma variável global de ambiente pode ser evitável.

Uma fronteira é justificável quando colaboradores evoluem de maneira independente ou exigem testes e políticas de falha distintos. Uma função de planejamento deve receber dados e devolver um plano; um coordenador decide enviá-lo. A **injeção de dependência** mais simples consiste em passar um objeto com um método e contrato conhecidos. Não exige contêiner, localizador de serviços ou estrutura de plugins.

| Mudança | Unidade que deve mudar | Unidade que normalmente não precisa mudar |
| --- | --- | --- |
| Regra de estoque mínimo | Cálculo de reposição e testes | Adaptador de transporte |
| API do fornecedor | Adaptador de transporte | Aritmética de reposição |
| Rejeição de quantidade inválida | Contrato de entrada e testes | Credenciais de rede |
| Nova unidade de medida | Modelo de domínio, clientes e migrações | Formatação de tela não relacionada |

Reduzir acoplamento não significa eliminar todas as dependências. Introduzir uma interface para cada soma pode tornar a dependência **menos visível**, embora o desenho possua mais caixas [1].

## Estudo de caso: derive um planejador puro de reposição

Considere um **retrato instantâneo do estoque**, com códigos SKU não vazios e únicos e quantidades **inteiras e não negativas**. Cada produto informa `disponivel` e `minimo`. A quantidade a repor é `max(0, minimo - disponivel)`. A saída contém apenas déficits positivos, preservando a ordem dos produtos. Códigos repetidos, tipos incorretos e quantidades negativas são rejeitados antes de qualquer ação externa. Estoque vazio resulta em plano vazio.

São requisitos **didáticos e locais**, não um sistema completo: pedidos em trânsito, reservas, avarias, lotes mínimos de fornecedores e alterações concorrentes não fazem parte do contrato. A função percorre uma coleção finita uma vez. A saída é uma tupla de registros imutáveis. O `dataclass(frozen=True)` do Python bloqueia reatribuição dos campos, mas **não** oferece imutabilidade profunda para campos arbitrariamente mutáveis [3].

```python
from dataclasses import dataclass

@dataclass(frozen=True)
class Estoque:
    codigo: str
    disponivel: int
    minimo: int

@dataclass(frozen=True)
class Reposicao:
    codigo: str
    quantidade: int

def planejar_reposicao(estoques):
    vistos = set()
    plano = []
    for item in estoques:
        if not isinstance(item, Estoque):
            raise ValueError("item Estoque obrigatorio")
        if (not isinstance(item.codigo, str) or not item.codigo.strip()
                or item.codigo != item.codigo.strip()):
            raise ValueError("codigo SKU invalido")
        if (type(item.disponivel) is not int or type(item.minimo) is not int
                or item.disponivel < 0 or item.minimo < 0):
            raise ValueError("quantidades inteiras nao negativas obrigatorias")
        if item.codigo in vistos:
            raise ValueError("SKU repetido")
        vistos.add(item.codigo)
        falta = item.minimo - item.disponivel
        if falta > 0:
            plano.append(Reposicao(item.codigo, falta))
    return tuple(plano)

estoques = [Estoque("A", 1, 3), Estoque("B", 9, 5), Estoque("C", 0, 4)]
assert planejar_reposicao(estoques) == (Reposicao("A", 2), Reposicao("C", 4))
assert planejar_reposicao([Estoque("X", 4, 4)]) == ()
assert planejar_reposicao([]) == ()
assert estoques[0] == Estoque("A", 1, 3)
```

O **invariante do laço** é: após processar os `k` primeiros registros, `vistos` contém exatamente os identificadores distintos desses registros; `plano` contém exatamente os déficits positivos desse prefixo, na mesma ordem. A validação impede estender o invariante com item duplicado ou malformado. Cada passo consome um item; para entrada finita, o procedimento termina.

O tempo esperado é `O(n)` e a memória auxiliar `O(n)` sob SKUs de comprimento limitado, inteiros de tamanho limitado e operações de conjunto de custo esperado constante. Hashing de strings longas e colisões adversariais tornam falsa a afirmação de tempo constante incondicional. A função não consulta relógio, banco ou rede: dois retratos iguais geram resultados iguais.

## Coloque efeitos externos numa fronteira estreita

Um **coordenador** pode enviar o plano final a um colaborador externo; o cálculo puro não deveria conhecer endpoints REST, conexões SQL ou retentativas. Um adaptador de gravação local demonstra **a solicitação de envio**, não o recebimento real por um fornecedor.

```python
class ColetorEnvios:
    def __init__(self):
        self.envios = []

    def enviar(self, plano):
        self.envios.append(tuple(plano))

def executar_plano(estoques, destino):
    plano = planejar_reposicao(estoques)
    if plano:
        destino.enviar(plano)
    return plano

coletor = ColetorEnvios()
plano = executar_plano(estoques, coletor)
assert coletor.envios == [plano]
assert executar_plano([Estoque("X", 5, 5)], coletor) == ()
assert len(coletor.envios) == 1
try:
    executar_plano([Estoque("A", 0, 1), Estoque("A", 0, 1)], coletor)
except ValueError:
    pass
else:
    raise AssertionError("SKU repetido deve falhar")
assert len(coletor.envios) == 1
```

A ordem é intencional: **validar todos os registros e concluir o plano antes de enviá-lo**. Se o último registro for inválido, não há chamada ao destino. Contudo, quando um adaptador real inicia uma requisição, uma falha pode ser ambígua: o fornecedor pode aceitar a compra enquanto o cliente recebe timeout. Composição e mocks não fornecem atomicidade ou idempotência ponta a ponta. Seriam necessários identificadores duráveis de operação, persistência da intenção e política específica de reconciliação, verificados por testes de integração.

## Refatoração pressupõe preservação do comportamento observável

Suponha que duas rotas possuam cópias da mesma regra de estoque mínimo. A extração segura começa por registrar comportamento de entrada e saída, incluindo rejeição de duplicatas, ordem da resposta, erros e a regra de **não enviar um plano vazio**. Em seguida, mova o cálculo para `planejar_reposicao`, compare resultados públicos e introduza o adaptador na fronteira. Martin Fowler caracteriza a refatoração como uma sequência de pequenas transformações estruturais que preservam comportamento observável definido, não como oportunidade para alterar silenciosamente uma regra [2].

Especifique **o que é observável**. Se antes a aplicação enviava uma requisição por SKU e agora envia um lote, quantidade de chamadas e tratamento de falhas mudaram, mesmo que o cálculo seja idêntico. Isso é mudança de integração, não mera renomeação. Se o programa antes aceitava SKU repetido, passar a rejeitá-lo muda entradas aceitas: registre como correção de defeito ou revisão de política, não como refatoração pura.

## Contraexemplos: quando abstrair piora o sistema

Extrair `subtrair(a,b)` para uma classe `FabricaEstrategiasDeSubtracao` sem variação real aumenta indireção, tipos e testes, sem proteger nenhuma mudança independente. Transformar todo condicional em padrão de projeto pode esconder a tabela-verdade da regra. Dividir uma operação em vários serviços assíncronos em nome de “responsabilidade única” introduz timeout, falhas parciais, consistência eventual e custo de infraestrutura. Frequentemente uma função coesa oferece **mais** manutenibilidade que um conjunto distribuído de abstrações.

No extremo oposto, manter cálculo de negócio dentro do callback de um SDK externo atrela seus testes e releases ao fornecedor. Quando vários fornecedores efetivamente possuem APIs que evoluem em ritmos diferentes, um Adapter pode compensar. A decisão é encontrar a **menor fronteira que isola uma causa demonstrável de mudança**, não maximizar interfaces [1][2].

## Exercícios independentes e verificação

1. **Tabela de contrato:** combine `disponivel` = 0, 2, 5 com `minimo` = 0, 2, 5 e calcule de modo independente os nove resultados esperados.
2. **Casos adversariais:** rejeite dois SKUs iguais, mesmo sem reposição; rejeite quantidade `True` (em Python, `bool` herda de `int`); rejeite valores negativos e fracionários.
3. **Propriedade metamórfica:** mantendo `minimo` fixo, aumentar `disponivel` válido não pode elevar `quantidade`; quando o resultado chega a zero, a linha desaparece do plano.
4. **Falha externa:** substitua `ColetorEnvios` por um destino que lança exceção e explique o que o chamador realmente sabe sobre o envio. Justifique identificador de operação para retry.
5. **Exercício de mudança:** introduza reserva de estoque para pedidos pendentes e enumere modelo, regra, contratos, testes e clientes que precisam mudar antes de criar novos padrões.
6. **Complexidade:** explique por que SKUs arbitrariamente longos, colisões de hash ou iteradores não finitos invalidam algumas das hipóteses do limite linear.

**Continuação:** [Projeto orientado a objetos](/pt/topics/object-oriented-design/) organiza estado; [testes e manutenção](/pt/topics/testing-maintainability/) aprofunda contratos; [SOLID](/pt/topics/solid-dependency-inversion/) discute substituição e interfaces; [padrões e refatoração](/pt/topics/refactoring-design-patterns/) mostra quando transformações estruturais se justificam.
