---
id: file-io-json-schema-safe-updates
title: "Fundamentos de arquivos e JSON: validação de esquema e substituição segura"
description: "Leia JSON em UTF-8, valide registros e substitua arquivos usando um temporário no mesmo diretório."
category: engineering
difficulty: foundational
updated: 2026-10-12
prerequisites: [error-handling-contracts-resource-cleanup, process-cli-arguments-environment-exit-status]
sources:
  - {title: "Python standard library — json", url: "https://docs.python.org/3/library/json.html", kind: "official Python documentation"}
  - {title: "Python standard library — pathlib", url: "https://docs.python.org/3/library/pathlib.html", kind: "official Python documentation"}
  - {title: "Python standard library — tempfile", url: "https://docs.python.org/3/library/tempfile.html", kind: "official Python documentation"}
  - {title: "Python standard library — os.replace", url: "https://docs.python.org/3/library/os.html#os.replace", kind: "official Python documentation"}
---
Muitos programas introdutórios armazenam dados em JSON antes de usar banco de dados. Essa é uma oportunidade para compreender um **contrato completo de arquivo**, em vez de apenas chamar json.dump e pressupor que tudo funcionará. Arquivos possuem codificação, formato de serialização, esquema dos dados, falhas possíveis e política de substituição. Cada propriedade é importante mesmo numa aplicação local pequena [1][2].

## Separe bytes, texto, JSON e objetos do domínio

Arquivo em disco contém bytes. Interpretá-los como UTF-8 produz texto, que pode ou não conter sintaxe JSON válida. Fazer parsing do JSON produz valores genéricos: objetos, arrays, números, strings, booleanos e null. Somente então a validação da aplicação estabelece se o resultado representa registro válido de domínio [1].

Um documento JSON sintaticamente correto não é automaticamente documento válido da aplicação. O número 42 é JSON válido, mas não é lista de anotações. Uma lista contendo objeto sem título pode ser analisada com sucesso e ainda violar o esquema do programa. Os níveis precisam permanecer separados no código e nos testes.

O exemplo suporta deliberadamente apenas documento JSON local pequeno. Não implementa serviço de rede, banco SQL, parser de streaming nem um padrão completo de JSON Schema.

## Declare o esquema antes de implementar o parser

A aplicação guarda lista de registros de anotação. Cada registro possui exatamente três campos: id, title e completed. O id precisa ser inteiro Python de tipo exato, positivo e no máximo um milhão. O title é string não vazia de até 80 caracteres, sem espaços no começo ou no fim. O campo completed exige Boolean verdadeiro ou falso. Identificadores precisam ser exclusivos dentro do documento.

A exigência de tipos exatos é importante. Em Python, bool herda de int; uma verificação simples com isinstance(value, int) aceitaria incorretamente true como identificador. O validador deve rejeitar campos extras e ausentes quando a interface promete estrutura exata. Listas vazias são permitidas, mas null e objetos JSON arbitrários não são valores válidos na raiz.

O validador devolve novos dicionários e nova lista, evitando modificar os contêineres fornecidos pelo chamador. Strings, inteiros e booleanos são valores imutáveis nesse modelo.

## Leia com context manager e depois valide

Um leitor abre o caminho com decodificação UTF-8 explícita e fecha o handle ao terminar o bloco with [2]. Erros de sintaxe JSON devem ser distinguidos de erros do esquema da aplicação: o primeiro significa que o formato não pôde ser interpretado; o segundo significa que houve parsing, mas os dados não cumprem o contrato.

O decoder JSON de Python pode aceitar nomes duplicados num objeto e conservar apenas um valor. Isso cria ambiguidade para identificadores e flags. O exemplo emprega hook de pares para rejeitar explicitamente campos duplicados. Também rejeita os tokens não padronizados NaN e Infinity, usando outro hook em vez de admitir silenciosamente números fora do JSON padrão [1].

Para simplificar, o leitor limita o texto a 100000 caracteres. Não é garantia de limite de bytes nem proteção contra todos os ataques de esgotamento de recursos, mas demonstra controle do trabalho previsto para documentos pequenos. Arquivos ausentes e erros de leitura do sistema operacional são propagados como exceções comuns de I/O.

## Escreva apenas dados previamente validados

O gravador valida o documento inteiro e o serializa para um payload UTF-8 completo **antes de tocar no arquivo de destino**. Emprega serialização JSON com caracteres não ASCII preservados, indentação legível e rejeição de números não finitos. Terminar com quebra de linha é decisão de formatação, não exigência do formato JSON [1].

Se a serialização ou validação falhar, o arquivo anterior não será aberto para sobrescrita. Depois cria-se arquivo temporário dentro do diretório de destino, grava-se o conteúdo e fecha-se o handle. O código utiliza os.replace para substituir o nome de destino após a conclusão da escrita no arquivo temporário [3][4].

Utilizar o mesmo diretório normalmente mantém o temporário no mesmo sistema de arquivos e evita depender de rename entre volumes distintos. Em sistemas POSIX que oferecem as garantias correspondentes, uma substituição de nome concluída é atômica no espaço de nomes. Isso não significa durabilidade garantida após falta de energia.

~~~python
import json
import os
import tempfile
from pathlib import Path

FIELDS = {"id", "title", "completed"}

def validate_notes(notes):
    if type(notes) is not list:
        raise ValueError("expected a list of notes")
    seen = set()
    result = []
    for note in notes:
        if type(note) is not dict or set(note) != FIELDS:
            raise ValueError("note fields must match the schema")
        note_id, title, completed = (note["id"], note["title"],
                                     note["completed"])
        if type(note_id) is not int or not 1 <= note_id <= 1_000_000:
            raise ValueError("id must be a positive bounded integer")
        if note_id in seen:
            raise ValueError("duplicate note id")
        if (type(title) is not str or not 1 <= len(title) <= 80
                or title != title.strip()):
            raise ValueError("invalid title")
        if type(completed) is not bool:
            raise ValueError("completed must be Boolean")
        seen.add(note_id)
        result.append({"id": note_id, "title": title,
                       "completed": completed})
    return result

def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON object key")
        result[key] = value
    return result

def reject_constant(value):
    raise ValueError("nonstandard JSON constant")

def load_notes(path):
    with Path(path).open("r", encoding="utf-8") as handle:
        content = handle.read(100_001)
    if len(content) > 100_000:
        raise ValueError("document exceeds character limit")
    try:
        data = json.loads(content, object_pairs_hook=unique_object,
                          parse_constant=reject_constant)
    except json.JSONDecodeError as exc:
        raise ValueError("invalid JSON syntax") from exc
    return validate_notes(data)

def save_notes(path, notes):
    target = Path(path)
    checked = validate_notes(notes)
    payload = json.dumps(checked, ensure_ascii=False,
                         allow_nan=False, indent=2) + "\n"
    if len(payload) > 100_000:
        raise ValueError("document exceeds character limit")
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", newline="\n",
            prefix=".notes-", suffix=".tmp",
            dir=target.parent, delete=False
        ) as handle:
            temporary = Path(handle.name)
            handle.write(payload)
        os.replace(temporary, target)
        temporary = None
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)

with tempfile.TemporaryDirectory() as folder:
    path = Path(folder) / "notes.json"
    notes = [{"id": 1, "title": "Ação", "completed": False},
             {"id": 2, "title": "Review", "completed": True}]
    save_notes(path, notes)
    previous = path.read_bytes()
    assert load_notes(path) == notes
    try:
        save_notes(path, [{"id": True, "title": "Bad",
                           "completed": False}])
    except ValueError:
        pass
    else:
        raise AssertionError("invalid schema accepted")
    assert path.read_bytes() == previous
~~~

## Exemplo executável e casos negativos

O código fornecido define validador de esquema, leitor JSON e gravador com arquivo temporário. Seus testes internos escrevem duas anotações, leem os mesmos dados e rejeitam um título inválido antes de modificar o documento existente.

Uma falha após criação do temporário e antes da substituição provoca tentativa de limpeza desse arquivo. O destino antigo permanece intacto até a tentativa de substituição. Se os.replace falhar, a exceção chega ao chamador e o programa limpa o nome temporário quando possível.

Isso não oferece transação envolvendo múltiplos arquivos. Dois gravadores concorrentes ainda podem sobrescrever alterações válidas um do outro. Nem arquivo temporário nem rename resolvem concorrência sem política própria.

## Atomicidade de nome não é durabilidade após falha

As garantias precisam ser precisas. Concluir a serialização em memória impede que conteúdo parcialmente validado substitua dados antigos. Gravar um temporário evita truncar o destino anterior por falha comum antes da substituição. Substituir o caminho muda qual arquivo completo será aberto pelos leitores, sujeito às regras de sistema operacional e filesystem [4].

Nenhuma dessas etapas comprova, isoladamente, que novos dados sobreviverão a uma falta de energia. Durabilidade após falha pode exigir sincronizar dados e metadados do diretório, com garantias dependentes do filesystem. Os detalhes avançados pertencem ao capítulo separado de descritores, buffering e fsync.

Um caminho pode ainda ser substituído concorrentemente entre leitura e gravação. Se o programa precisa evitar perda de atualizações, deve empregar verificação de versões, locks ou armazenamento transacional. O exemplo básico não faz promessas de concorrência.

## Complexidade, correção e evidência dos testes

Para documento de n registros e L caracteres, decodificar, interpretar, validar e serializar exigem trabalho relacionado a L+n num modelo comum de processamento linear. O conjunto de unicidade utiliza O(n) espaço. O gravador também mantém payload serializado em memória, O(L). Operações da tabela hash possuem custo médio, não constante no pior caso incondicional.

O invariante da validação é que todo prefixo já aceito contém apenas registros que satisfazem a estrutura e identificadores distintos. Ao terminar normalmente, a nova lista completa satisfaz o esquema. Um registro rejeitado provoca exceção sem alterar a lista do chamador ou o arquivo já existente.

Os testes precisam cobrir JSON inválido, chaves duplicadas, identificadores repetidos, tokens numéricos não padronizados, tipos incorretos, arquivos ausentes, títulos Unicode e round trip bem-sucedido. Injetar falha antes de os.replace deve confirmar preservação do arquivo anterior e remoção dos temporários.

## Exercícios e verificação

1. Explique por que sintaxe JSON válida não garante um registro válido da aplicação.
2. Demonstre por que true não deve ser aceito como identificador inteiro.
3. Teste campos duplicados, ids repetidos e título maior que o limite.
4. Injete falha de escrita antes da substituição e verifique que o destino anterior continua intacto.
5. Diferencie substituição atômica do nome de durabilidade física e de proteção contra atualizações concorrentes.
6. Derive custo de memória ao carregar e serializar o documento JSON inteiro.

Continue com [contratos de exceção](/pt/topics/error-handling-contracts-resource-cleanup/), [descritores e fsync](/pt/topics/file-descriptors-buffering-fsync/) e [integridade SQL](/pt/topics/relational-model-sql-basics/).
