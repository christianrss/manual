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
