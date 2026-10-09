---
id: testing-strategies
title: "Estratégias de testes: unidades, contratos, integração e E2E"
description: "Diferencie testes unitários, de propriedades, integração, contrato e E2E com exemplos executáveis e limites de evidência."
category: engineering
difficulty: intermediate
updated: 2026-10-09
prerequisites: [object-oriented-design, testing-maintainability]
sources:
  - {title: "Martin Fowler — The Practical Test Pyramid", url: "https://martinfowler.com/articles/practical-test-pyramid.html", kind: "engineering article"}
  - {title: "Python unittest — official documentation", url: "https://docs.python.org/3/library/unittest.html", kind: "official language documentation"}
  - {title: "Google Engineering Practices — Code review", url: "https://google.github.io/eng-practices/review/", kind: "engineering guideline"}
---
Uma boa suíte de testes fornece **evidências sobre comportamento numa fronteira definida**, não apenas grande quantidade de asserts. Testes unitários, de integração, contrato, ponta a ponta e de falhas/carga respondem perguntas diferentes. Não são substitutos livres: banco falso torna teste de regra rápido, mas não prova constraints reais; E2E aprovado percorre um fluxo, mas não cobre todas as intercalações concorrentes. Entender fronteiras é mais importante que obedecer a proporção fixa de uma pirâmide de testes [1].

## Comece por contrato de comportamento escrito

Antes do framework, defina entradas permitidas, saídas, efeitos, política de erro e invariantes. Considere subtotal de pedido com preços unitários e quantidades positivas, acrescido de política tributária que precisa produzir total não negativo. O contrato observável inclui entrada vazia resultando zero, item gratuito não alterando total e rejeição de valores negativos ou quantidades não positivas.

Cubra casos comuns, **valores de fronteira**, entrada malformada e regressões já observadas. Assertions sobre exemplos ajudam, mas expectativa calculada repetindo a própria fórmula do código pode reproduzir o mesmo erro. Derive respostas esperadas da regra do negócio e de cálculos independentes.

## Testes unitários isolam uma decisão

Um **teste unitário** exercita fronteira pequena, controlando colaboradores caros ou não determinísticos. Deve ser rápido, repetível e produzir falhas relacionadas ao comportamento local. A unidade pode ser função, objeto ou pequeno conjunto coeso; não existe exigência universal de uma classe por teste.

Python unittest fornece fixtures, asserts e subTest para verificar um contrato em múltiplos casos [2]. A política usa Decimal criado de strings para evitar arredondamento binário inesperado. Retorna total com imposto, arredondando **uma vez sobre o agregado**; jurisdição que exige arredondamento por linha precisaria de outro contrato.

~~~python
import io
import unittest
from decimal import Decimal, ROUND_HALF_UP

def total_cobrado(itens, taxa):
    if not Decimal("0") <= taxa <= Decimal("1"):
        raise ValueError("taxa invalida")
    subtotal = Decimal("0")
    for preco, quantidade in itens:
        if preco < 0 or quantidade <= 0:
            raise ValueError("item invalido")
        subtotal += preco * quantidade
    return (subtotal * (1 + taxa)).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP)

class TestesCobranca(unittest.TestCase):
    def test_exemplos(self):
        casos = [
            ([], "0", "0.00"),
            ([(Decimal("10.00"), 2)], "0.10", "22.00"),
            ([(Decimal("0.00"), 3)], "0.21", "0.00"),
        ]
        for itens, taxa, esperado in casos:
            with self.subTest(itens=itens, taxa=taxa):
                self.assertEqual(
                    total_cobrado(itens, Decimal(taxa)), Decimal(esperado))

    def test_invalidos(self):
        with self.assertRaises(ValueError):
            total_cobrado([(Decimal("-1"), 1)], Decimal("0"))
        with self.assertRaises(ValueError):
            total_cobrado([(Decimal("1"), 0)], Decimal("0"))

resultado = unittest.TextTestRunner(
    stream=io.StringIO(), verbosity=0
).run(unittest.defaultTestLoader.loadTestsFromTestCase(TestesCobranca))
assert resultado.wasSuccessful()
~~~

A suíte aprovada confirma os exemplos e validações do **modelo local**. Não demonstra conformidade fiscal de uma jurisdição, câmbio ou liquidação financeira real. Pressupõe uma única moeda nos preços e taxa já obtida e autorizada corretamente.

## Propriedades e testes metamórficos

Testes de exemplos verificam valores selecionados. Uma **propriedade** expressa relação esperada para muitos dados. Com preços não negativos e quantidades positivas, acrescentar item gratuito não deve alterar o total; aumentar quantidade não deve reduzi-lo quando imposto é não negativo. Uma **relação metamórfica** compara respostas após transformação controlada da entrada, útil quando não é simples calcular um oráculo para cada caso.

~~~python
from itertools import product

for quantidade, centavos in product(range(1, 5), range(4)):
    itens = [(Decimal(centavos) / 100, quantidade)]
    original = total_cobrado(itens, Decimal("0.10"))
    com_gratis = total_cobrado(
        itens + [(Decimal("0"), 1)], Decimal("0.10"))
    assert com_gratis == original
    assert total_cobrado(
        [(itens[0][0], quantidade + 1)], Decimal("0.10")) >= original
~~~

O exemplo verifica uma grade finita, não todos os valores monetários. Ferramentas property-based podem gerar mais casos e reduzir entradas que falham. Para testes aleatórios, controle seeds quando apropriado, preserve entradas de falha e garanta que a propriedade seja justificada independentemente do código.

## Testes de integração validam a fronteira real

Um **teste de integração** verifica componentes juntos através de fronteira real: esquema de banco, transações, serialização, cliente de rede, broker ou arquivo. Substituir banco relacional por dicionário em memória pode invalidar hipóteses sobre isolamento, collations e índices. Para provar unicidade sob concorrência, use banco real em ambiente isolado, conexões separadas e barreira para provocar conflito.

Serviços externos podem ser instáveis ou custosos, então a integração deve usar instâncias controladas e limpeza de dados. Testes unitários podem executar a cada edição; integrações mais lentas podem rodar em gates do CI, mas deixar validações críticas apenas para produção aumenta risco.

## Testes de contrato e compatibilidade

Um **teste de contrato do consumidor** registra expectativas de formato de resposta de API, semântica de erros, tipos e compatibilidade de versões. O teste no provedor verifica que o serviço cumpre o combinado. Detecta quebra de integração, mas não demonstra todas as regras de negócio nem a segurança das permissões.

Por exemplo, cliente pode exigir cursor estável de paginação e erro documentado para recurso inexistente. Uma API pode cumprir esse contrato de rede e ainda vazar dados de outro tenant; autorização precisa de testes separados. Mock que respeita OpenAPI também não prova latência em produção ou transação no banco.

## Testes E2E e injeção de falhas

Um teste **end-to-end** executa caminho relevante ao usuário através dos componentes implantados: criar pedido, persistir, gerar evento e consultar estado final. É valioso porque muitos defeitos aparecem em fronteiras invisíveis aos testes isolados. Mas uma suíte E2E muito grande pode ser lenta e instável quando depende de relógios não controlados, estado compartilhado, quotas externas e atrasos de consistência eventual [1].

Um **teste de falhas** injeta timeout, dependência indisponível, evento duplicado, queda de processo ou escrita parcial. Se API promete idempotência, teste a mesma chave/payload repetidos, a mesma chave com outro payload e replay após queda. Retry bem-sucedido num mock não prova cobrança externa exatamente uma vez; verifique chaves duráveis e reconciliação numa integração real.

## Doubles: mocks, stubs e fakes

Um **stub** devolve respostas predefinidas. Um **fake** implementa comportamento simplificado útil, como repositório em memória. Um **mock** verifica interações, por exemplo se um remetente recebeu uma chamada. Esses nomes podem variar entre bibliotecas; a distinção central é **qual afirmação o teste faz**. Asserts de interação podem acoplar demais ao detalhe interno, enquanto asserts de estado podem tolerar mais refatoração.

Fake não é substituto fiel de armazenamento distribuído. Mock que confirma send() chamado não comprova que mensagem remota foi aceita, entregue ou visualizada. Prefira resultados externos relevantes e verifique quantidade/ordem de chamadas quando esses elementos integram o contrato.

## Determinismo, isolamento e CI confiável

Testes devem controlar aleatoriedade, tempo, armazenamento e concorrência quando possível. Injete relógio em vez de dormir esperando o dia seguinte. Use bancos temporários, identificadores exclusivos e limpeza. Suítes paralelas não devem depender de fixtures globais mutáveis; isso causa testes que passam isolados e falham conforme a ordem. Repetir testes instáveis até ficarem verdes esconde regressões.

Pipeline precisa de verificações em fronteiras diferentes: unitários rápidos e propriedades, integrações focalizadas, poucos E2E críticos, carga/falha quando risco justifica e observabilidade após deploy. Passar em pipeline oferece **evidência delimitada**, não prova universal de correção [1][3].

| Tipo | Evidência principal | O que não prova sozinho |
| --- | --- | --- |
| Unitário | Regra local e casos-limite | Banco/rede reais |
| Propriedades | Relações sob casos gerados | Requisitos não modelados |
| Integração | Compatibilidade real de componentes | Fluxo inteiro do usuário |
| Contrato | Expectativas cliente/provedor | Autorização e correção de negócio |
| E2E | Caminho crítico entre componentes | Corridas e falhas raras |
| Falha/carga | Comportamento em condições provocadas | Todos os desastres possíveis |

## Exercícios e verificação

1. Adicione teste no limite taxa=1 e rejeição de taxa acima de 1.
2. Por que dicionário Python não comprova SQL UNIQUE sob inserções concorrentes?
3. Declare propriedade metamórfica para permutação da ordem dos itens e discuta arredondamento.
4. Descreva um E2E que passa enquanto uma segunda requisição concorrente viola um invariante.
5. Proponha matriz de CI com feedback rápido e verificação de armazenamento/contratos reais antes do deploy.

**Capítulos relacionados:** [Testes e manutenção](/pt/topics/testing-maintainability/) define invariantes; [orientação a objetos](/pt/topics/object-oriented-design/) cria fronteiras; [índices transacionais](/pt/topics/transactional-indexing-isolation/) explica concorrência [1].
