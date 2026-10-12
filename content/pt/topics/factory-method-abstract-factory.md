---
id: factory-method-abstract-factory
title: "Padrões criacionais: Factory Method, Abstract Factory e fábricas simples"
description: "Compare seleção de construtores, métodos de criação sobrescritos e famílias de objetos compatíveis em pipelines de exportação testados."
category: engineering
difficulty: intermediate
updated: 2026-10-12
prerequisites: [design-pattern-families, domain-modeling-aggregates-invariants]
sources:
  - {title: "Refactoring.Guru — Factory Method", url: "https://refactoring.guru/design-patterns/factory-method", kind: "technical pattern reference"}
  - {title: "Refactoring.Guru — Abstract Factory", url: "https://refactoring.guru/design-patterns/abstract-factory", kind: "technical pattern reference"}
  - {title: "Python documentation — csv", url: "https://docs.python.org/3/library/csv.html", kind: "official language documentation"}
---
Fábrica é nome genérico para construção de objetos; utilizá-lo não comprova aplicação de um padrão GoF. Uma função condicional que devolve uma entre duas classes é frequentemente uma **fábrica simples**. Factory Method permite que subclasses modifiquem o produto criado por um método, enquanto o criador preserva a lógica compartilhada do fluxo [1]. Abstract Factory fornece uma família de produtos relacionados que precisam ser escolhidos de forma coerente [2]. Diferenciar esses conceitos evita conclusões superficiais em entrevistas e revisões de código.

## Identifique variações e contratos concretos

Um sistema exporta relatórios em JSON ou CSV. As variantes recebem registros, validam seus campos e produzem texto. Cada registro contém nome não vazio e quantidade inteira não negativa; booleanos não são quantidades válidas. Alguns consumidores escolhem formato por parâmetro de requisição; jobs agendados possuem formato fixo. Há também o requisito de devolver a extensão correspondente: um corpo JSON com nome terminado em .csv é defeito de compatibilidade.

Os renderizadores preservam informação equivalente, mas não bytes idênticos. O csv.writer da biblioteca padrão trata separadores, aspas e quebras de linha segundo o dialeto escolhido; concatenar campos com vírgulas não é substituto seguro [3]. O exemplo não grava arquivos e não atende HTTP. Portanto, não comprova persistência, autorização nem proteção contra caminhos arbitrários no sistema de arquivos.

## Fábrica simples versus Factory Method

Uma fábrica simples pode mapear strings de formato para construtores e rejeitar alternativas desconhecidas. Centraliza uma escolha e reduz o conhecimento exigido dos consumidores. Mas não contém uma subclasse que sobrescreve um método de criação, portanto não representa necessariamente o padrão Factory Method clássico. Com dois produtos fixos, uma condicional direta pode ser a implementação mais compreensível.

No Factory Method real abaixo, ExportJob é um criador abstrato responsável por validar e renderizar dados. Os jobs concretos implementam make_renderer e substituem exclusivamente a etapa de criação. Existe um criador e um contrato de produto que oferece render, retornando texto [1]. O custo é mais herança e uma classe por formato. Se não existe necessidade de extensibilidade por subclasses, injetar renderizador no construtor pode ser mais adequado.

~~~python
import csv
import io
import json
from abc import ABC, abstractmethod

def validated(rows):
    if not isinstance(rows, (tuple, list)):
        raise ValueError("rows must be a sequence")
    result = []
    for row in rows:
        if (not isinstance(row, tuple) or len(row) != 2
                or not isinstance(row[0], str) or not row[0].strip()
                or type(row[1]) is not int or row[1] < 0):
            raise ValueError("invalid row")
        result.append(row)
    return result

class CsvRenderer:
    def render(self, rows):
        target = io.StringIO(newline="")
        writer = csv.writer(target, lineterminator="\n")
        writer.writerow(("name", "count"))
        writer.writerows(rows)
        return target.getvalue()

class JsonRenderer:
    def render(self, rows):
        return json.dumps([{"name": name, "count": count}
                           for name, count in rows], ensure_ascii=False)

class ExportJob(ABC):
    @abstractmethod
    def make_renderer(self):
        raise NotImplementedError
    def run(self, rows):
        return self.make_renderer().render(validated(rows))

class CsvExport(ExportJob):
    def make_renderer(self):
        return CsvRenderer()

class JsonExport(ExportJob):
    def make_renderer(self):
        return JsonRenderer()

def simple_factory(kind):
    choices = {"csv": CsvRenderer, "json": JsonRenderer}
    if kind not in choices:
        raise ValueError("unsupported format")
    return choices[kind]()

rows = [("Ada", 2), ("Grace, Hopper", 1)]
assert '"Grace, Hopper",1' in CsvExport().run(rows)
assert json.loads(JsonExport().run(rows))[1]["name"] == "Grace, Hopper"
assert simple_factory("csv").render(validated(rows)) == CsvExport().run(rows)
try:
    CsvExport().run([("invalid", True)])
except ValueError:
    pass
else:
    raise AssertionError("bool count accepted")
~~~

Para n linhas com tamanhos de campos limitados, a validação percorre O(n) elementos. Renderizar exige no mínimo trabalho proporcional aos caracteres produzidos, que podem crescer além de n com nomes longos. A lista validada e o texto final consomem memória; não são operações de espaço constante. Chamar renderizador diretamente ignora a validação de ExportJob. Ele é componente interno; o ponto público de exportação deve impor seu contrato de entrada.

## Abstract Factory mantém uma família compatível

O pacote também precisa escolher extensão de arquivo. Surgem dois produtos relacionados: renderizador e política de nome. Se alguém combinar JsonRenderer com CsvName, o pacote parece válido sintaticamente, mas o consumidor interpreta conteúdo errado. Uma família fornece as duas escolhas coordenadas [2]. O cliente seleciona CsvFamily ou JsonFamily e pede os componentes sem conhecer os nomes concretos.

~~~python
class CsvName:
    def filename(self, base):
        return base + ".csv"

class JsonName:
    def filename(self, base):
        return base + ".json"

class CsvFamily:
    def renderer(self):
        return CsvRenderer()
    def naming(self):
        return CsvName()

class JsonFamily:
    def renderer(self):
        return JsonRenderer()
    def naming(self):
        return JsonName()

def export_package(family, rows, base):
    if not isinstance(base, str) or not base.isidentifier():
        raise ValueError("invalid base filename")
    data = validated(rows)
    return family.naming().filename(base), family.renderer().render(data)

assert export_package(CsvFamily(), rows, "quarter")[0] == "quarter.csv"
name, data = export_package(JsonFamily(), rows, "quarter")
assert name == "quarter.json"
assert json.loads(data)[0] == {"name": "Ada", "count": 2}
try:
    export_package(CsvFamily(), rows, "../quarter")
except ValueError:
    pass
else:
    raise AssertionError("unsafe filename accepted")
~~~

A função de pacote aceita identificadores como base de nome e rejeita barras e caminhos. Trata-se de um contrato restrito para este exemplo, **não** de sanitizador geral de nomes. A família não impede que outro trecho do programa combine objetos incompatíveis. Na fronteira HTTP ou de armazenamento, confira separadamente tipo de conteúdo, extensão, chave, autorização e modo de download.

## Quadro de decisão e dependências

| Variação | Alternativa | Custo |
| --- | --- | --- |
| Formato fixo escolhido por string | Condicional ou fábrica simples | Registro ainda precisa de validação |
| Criador reutilizável com construção sobrescrita | Factory Method | Hierarquia e indireção |
| Vários produtos devem pertencer à mesma variante | Abstract Factory | Mais uma camada e famílias a manter |
| Produto montado por etapas opcionais validadas | Builder | Estado intermediário mutável |
| Dependência escolhida na inicialização | Injeção no construtor | Composição explícita na inicialização |

Factory Method responde à variação de um método de criação num fluxo reutilizado. Abstract Factory responde à necessidade de **famílias** compatíveis. Builder controla as **etapas** de construir um produto acabado. Service locator que constrói dependências ocultamente não é equivalente à injeção de dependências: pode esconder os colaboradores exigidos pela política de domínio. Prefira a menor abstração capaz de impedir um erro real [1][2].

## Falhas e contraexemplos

Trocar formato desconhecido por CSV silenciosamente viola expectativas de quem solicitou JSON. É preferível rejeitar a entrada a fabricar sucesso. Criar renderizador que acessa rede não comprova que a chamada completará; timeout, repetição e liberação de recursos precisam de contratos próprios. Quando formatos exigem semânticas de entrada incompatíveis, obrigá-los a ter a mesma interface pode quebrar substituição comportamental. Uma tabela CSV sem esquema estável não é equivalente a uma lista JSON arbitrária.

Abstract Factory também pode ampliar trabalho quando surge novo tipo de produto: todas as famílias passam a exigir uma implementação. Esse custo é correto se a completude das famílias for parte do requisito; é desperdício se as variações são independentes. Fábrica simples não é inferior por princípio e frequentemente representa o menor acoplamento necessário.

## Complexidade, testes e alcance das evidências

O código verifica registro inválido, escape CSV e duas famílias coerentes. Não testa nomes Unicode arbitrários, todos os dialetos CSV, entradas gigantes, exaustão de recursos ou armazenamento externo. Uma implantação real exige limites de tamanho e compatibilidade explícita de esquemas. Teste os mesmos registros via parsers CSV e JSON e compare seu significado, não os bytes. O invariante essencial é compatibilidade entre corpo exportado e formato declarado, não quantidade de classes.

## Exercícios e verificação

1. Adicione TSV. Decida se basta entrada na fábrica simples, nova subclasse Factory Method ou família inteira; justifique.
2. Use campo com vírgula, aspas e quebra de linha, faça leitura com csv.reader e comprove ida e volta [3].
3. Combine manualmente renderizador JSON com extensão CSV fora da família. Defina em qual fronteira a aplicação deve detectar o defeito.
4. Refaça ExportJob com renderizador injetado e compare testabilidade e quantidade de abstrações.
5. Avalie se devolver formato padrão após erro viola o contrato do consumidor; especifique alternativa previsível.

Relacionados: [famílias de padrões](/pt/topics/design-pattern-families/), [SOLID](/pt/topics/solid-dependency-inversion/) e [agregados de domínio](/pt/topics/domain-modeling-aggregates-invariants/).