---
id: python-files-utf8-json-validation
title: "Fundamentos de arquivos e dados: bytes, UTF-8, JSON e validação"
description: "Leia arquivos JSON UTF-8 limitados, rejeite dados ambíguos e grave registros validados com limites explícitos."
category: foundations
difficulty: foundational
updated: 2026-10-12
prerequisites: [python-error-contracts-resource-cleanup, data-types-bytes-and-representation]
sources:
  - {title: "Python standard library — json", url: "https://docs.python.org/3/library/json.html", kind: "official library documentation"}
  - {title: "Python Unicode HOWTO", url: "https://docs.python.org/3/howto/unicode.html", kind: "official language guide"}
  - {title: "Python standard library — io", url: "https://docs.python.org/3/library/io.html", kind: "official library documentation"}
---
Arquivos e dados estruturados conectam um programa ao mundo externo. Para utilizá-los corretamente, é necessário distinguir **bytes armazenados, texto decodificado, sintaxe estruturada e dados validados do domínio**. Cada etapa possui falhas diferentes. Um JSON sintaticamente válido não garante campos, tipos e valores esperados. Este capítulo implementa uma fronteira pequena e verificável antes de introduzir bancos de dados, redes ou garantias de durabilidade [1][2].

## Bytes não são automaticamente caracteres

Um arquivo contém bytes. Texto é obtido ao decodificar esses bytes conforme uma codificação escolhida. UTF-8 é uma codificação de largura variável para caracteres Unicode; uma letra acentuada pode ocupar mais de um byte. Indexar bytes, portanto, não equivale a indexar pontos de código Unicode ou caracteres percebidos visualmente [2].

Uma sequência UTF-8 inválida não deve ser silenciosamente substituída quando o contrato exige conteúdo exato. Utilize decodificação estrita para que entrada malformada provoque UnicodeDecodeError. Não deduza a codificação apenas da extensão do arquivo; o formato precisa declará-la. Um marcador BOM não é obrigatório em UTF-8 e pode ser rejeitado pelo decodificador JSON escolhido.

I/O textual também pode traduzir terminadores de linha, dependendo da configuração. Ler primeiro em modo binário e decodificar UTF-8 explicitamente torna visível essa fronteira, embora um leitor textual com codificação declarada também seja adequado para muitas aplicações [3].

## Sintaxe de serialização e contrato dos dados

JSON representa strings, números, booleanos, null, arrays e objetos. Não representa diretamente qualquer objeto Python nem estabelece esquema de negócio. No exercício, o documento possui exatamente dois campos externos: version igual ao inteiro 1 e records com no máximo 100 entradas. Cada entrada deve conter exatamente id e count.

Um identificador contém de um a 32 caracteres ASCII minúsculos, dígitos, hífens ou sublinhados. Os identificadores são únicos. Contagem é inteiro Python entre 0 e 1000, excluindo valores booleanos. São **invariantes da aplicação**, não exigências universais de JSON. Aceitar um booleano como contagem porque bool deriva de int em Python viola o esquema declarado.

Campos desconhecidos são rejeitados em vez de ignorados. O campo de versão permite distinguir um futuro formato incompatível em vez de interpretá-lo silenciosamente como o atual. Outros formatos podem admitir campos opcionais e estratégias distintas de compatibilidade; esses contratos precisam ser explicitados.

## Chaves duplicadas e números não finitos

O decodificador padrão de JSON em Python normalmente aceita nomes de objeto repetidos e conserva o último valor. Essa escolha gera ambiguidade entre produtores e consumidores. A opção object_pairs_hook recebe pares de cada objeto na ordem original e permite rejeitar duplicações **antes** de construir o dicionário [1].

Por padrão, o decodificador Python também admite tokens não padronizados como NaN e Infinity. A sintaxe interoperável de números JSON não inclui esses valores. O hook parse_constant permite rejeitá-los, e allow_nan=False impede que o codificador emita floats especiais [1].

Rejeitar duplicações e constantes não substitui validar dados de domínio. Um documento sintaticamente correto pode apresentar versão errada, identificadores repetidos, registros demais, caracteres proibidos ou tipos incorretos.

## Limite tamanho antes de decodificar

Arquivos não confiáveis podem ser grandes demais para a aplicação. O exemplo lê no máximo MAX_BYTES+1 bytes. Caso o comprimento exceda MAX_BYTES, rejeita a entrada sem tentar analisar o arquivo inteiro. É estratégia de entrada limitada, **não** promessa de resistência a toda forma de esgotamento de recursos do parser JSON [1].

Com limite de 16384 bytes e 100 registros, o tamanho aceito é finito e testável. O programa ainda cria objetos Python proporcionais à entrada e paga pelo overhead do decodificador. O uso real de memória pode exceder o número de bytes do arquivo; não se deve inferir limite exato de RAM a partir desse teto.

O exemplo converte bytes inválidos e sintaxe JSON malformada em DocumentError. Já OSError de abertura ou leitura mantém seu tipo original: trata-se de erro ambiental, não necessariamente de conteúdo incorreto.

## Validação e leitura/gravação reproduzíveis

O leitor obtém bytes com context manager, verifica tamanho, decodifica UTF-8 estrito e analisa JSON usando hooks de validação. A função de validação reconstrói os campos aceitos numa nova estrutura. O gravador valida e serializa **antes** de abrir o destino; assim dados semanticamente inválidos não truncam um arquivo existente.

~~~python
import json
from pathlib import Path

MAX_BYTES = 16384

class DocumentError(ValueError):
    pass

def unique_fields(pairs):
    obj = {}
    for key, value in pairs:
        if key in obj:
            raise DocumentError("duplicate object field")
        obj[key] = value
    return obj

def reject_constant(value):
    raise DocumentError("nonfinite numeric token")

def validate_document(doc):
    if (type(doc) is not dict or set(doc) != {"version", "records"}
            or type(doc["version"]) is not int or doc["version"] != 1):
        raise DocumentError("invalid document header")
    records = doc["records"]
    if type(records) is not list or len(records) > 100:
        raise DocumentError("invalid record collection")
    seen = set()
    normalized = []
    alphabet = "abcdefghijklmnopqrstuvwxyz0123456789-_"
    for record in records:
        if type(record) is not dict or set(record) != {"id", "count"}:
            raise DocumentError("invalid record fields")
        ident, count = record["id"], record["count"]
        if (type(ident) is not str or not 1 <= len(ident) <= 32
                or any(ch not in alphabet for ch in ident) or ident in seen
                or type(count) is not int or not 0 <= count <= 1000):
            raise DocumentError("invalid record value")
        seen.add(ident)
        normalized.append({"id": ident, "count": count})
    return {"version": 1, "records": normalized}

def read_document(path):
    with open(path, "rb") as source:
        raw = source.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise DocumentError("file too large")
    try:
        text = raw.decode("utf-8")
        parsed = json.loads(text, object_pairs_hook=unique_fields,
                            parse_constant=reject_constant)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise DocumentError("invalid UTF-8 JSON") from exc
    return validate_document(parsed)

def write_document(path, doc):
    checked = validate_document(doc)
    raw = (json.dumps(checked, ensure_ascii=False, sort_keys=True,
                      allow_nan=False, separators=(",", ":")) + "\n").encode("utf-8")
    if len(raw) > MAX_BYTES:
        raise DocumentError("serialized file too large")
    with open(path, "wb") as destination:
        destination.write(raw)

example = {"version": 1, "records": [{"id": "a-1", "count": 7}]}
assert validate_document(example) == example
~~~

O exemplo utiliza operações binárias intencionalmente, tornando a codificação explícita. Não há normalização de identificadores Unicode porque o contrato selecionou somente ASCII. Se nomes humanos forem incluídos depois, será necessário declarar normalização, sensibilidade a maiúsculas e regras de comprimento separadamente.

## Invariantes e ida e volta dos dados

Depois da validação, cada registro contém apenas campos permitidos, valores nos intervalos e identificador único. O conjunto seen contém exatamente os identificadores já aceitos. O próximo registro é rejeitado se a identidade estiver nesse conjunto, preservando a unicidade por indução.

O gravador produz uma estrutura normalizada antes de serializar e gerar bytes UTF-8. O leitor executa as etapas inversas. Para qualquer documento aceito cujo tamanho serializado seja menor que MAX_BYTES, gravar e ler resulta numa estrutura igual, supondo I/O bem-sucedido e ausência de alterações intermediárias. **Identidade dos objetos** não se conserva, porque a desserialização cria novos objetos.

Para n bytes de entrada e r registros, decodificação, parsing e validação demandam trabalho relacionado ao tamanho da representação, com memória adicional O(n+r) no modelo usual de campos limitados. Strings e dicionários acrescentam overhead. O conjunto identifica duplicações com consultas de custo esperado constante no modelo de hash; colisões adversariais e custos do interpretador impedem garantir pior caso constante.

## O que a gravação não assegura

Abrir arquivo em modo de escrita pode truncar seu conteúdo anterior. Validação antes da abertura protege contra erros semânticos dos dados, mas **não** contra erro do armazenamento ou crash após truncamento e antes do término. Fechar o arquivo e receber sucesso na escrita não demonstra troca atômica nem persistência após falta de energia.

Uma estratégia de substituição mais robusta pode usar arquivo temporário, permissões apropriadas, sincronização e rename atômico se o sistema oferecer as garantias necessárias. A correção depende da plataforma e do modelo de falhas. O capítulo de descritores e fsync aprofunda esses limites; esta aula não reivindica recuperação após crash.

## Exercícios e verificação

1. Grave e leia um documento válido num diretório temporário e compare os registros decodificados.
2. Insira nomes de propriedades duplicados num JSON e confirme a rejeição.
3. Teste contagem booleana, token não finito, sequência UTF-8 inválida e campo desconhecido.
4. Tente gravar dados inválidos num caminho que já contém arquivo válido e confirme que esse arquivo permanece intacto.
5. Crie documento maior que MAX_BYTES e verifique a rejeição na leitura.
6. Explique por que decodificar JSON, validar um esquema e garantir substituição atômica são três responsabilidades diferentes.

Continue por [contratos de erro](/pt/topics/python-error-contracts-resource-cleanup/), [representação de dados](/pt/topics/data-types-bytes-and-representation/) e [descritores e durabilidade](/pt/topics/file-descriptors-buffering-fsync/).