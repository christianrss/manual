---
id: versioned-bytecode-serialization
title: "Serialização Versionada de Bytecode, Integridade e Carregamento Verificado"
description: "Defina um formato versionado e limitado para bytecode com JSON determinístico, checksum, decodificação rigorosa e verificação da VM."
category: foundations
difficulty: advanced
updated: 2026-10-11
prerequisites: [lexical-addresses-bytecode-verification]
sources:
  - {title: "RFC 8259 — The JavaScript Object Notation (JSON) Data Interchange Format", url: "https://www.rfc-editor.org/rfc/rfc8259", kind: "Internet standard"}
  - {title: "Python Standard Library — json", url: "https://docs.python.org/3/library/json.html", kind: "official standard library documentation"}
  - {title: "Python Standard Library — hashlib", url: "https://docs.python.org/3/library/hashlib.html", kind: "official standard library documentation"}
  - {title: "Java Virtual Machine Specification — Verification of Class Files", url: "https://docs.oracle.com/javase/specs/jvms/se25/html/jvms-4.html#jvms-4.10", kind: "official virtual machine specification"}
---
O [compilador com endereços léxicos e verificador](/pt/topics/lexical-addresses-bytecode-verification/) utiliza objetos Python imutáveis em memória. Isso permite compilar e executar no mesmo processo, mas não define como gravar um programa em arquivo, carregá-lo em outro processo, distinguir versões incompatíveis ou rejeitar dados corrompidos antes da execução. Este capítulo introduz uma **representação serializada, limitada e versionada** para a VM didática existente. São quatro problemas distintos: codificação, validação de formato, detecção de corrupção acidental e verificação semântica das instruções [1][2][4].

Um formato de arquivo é um contrato entre produtor e consumidor. Converter indiscriminadamente uma dataclass em dicionário não basta: identidade de objetos Python, tuplas, descritores de funções recursivas e opcodes exigem representação explícita e limites. O novo módulo é **opcional** e não altera a sintaxe da linguagem nem o comportamento do backend anterior.

## Envelope v1 e codificação determinística

O formato utiliza um objeto JSON UTF-8 com exatamente quatro propriedades: `magic`, `version`, `sha256` e `payload`. A identificação é `CHRIS-VM-SLOT` e a versão inicial é o inteiro **1**. O payload contém somente `result_type` e `code`. Um objeto de código guarda descritores dos escopos léxicos capturados, parâmetros, tipo de retorno e uma sequência de instruções. Cada instrução corresponde ao vetor de três elementos: opcode, operando e deslocamento não negativo no código-fonte. Closures aninhadas são representadas por objetos de código também aninhados, nunca por código executável da linguagem hospedeira.

O codificador ordena as chaves dos objetos, utiliza separadores compactos e escapa caracteres para ASCII. Dessa forma, um mesmo programa verificado resulta na mesma sequência de bytes segundo **a convenção deste projeto**. Isso não significa conformidade com um padrão externo de JSON canônico, como o JCS. O JSON em si permite representações textuais diferentes para o mesmo conteúdo [1]. A estabilidade dos bytes facilita fixtures, cache, regressões e cálculo de digest.

Os tipos estáticos possuem tags explícitas: `["base","Int"]`, `["base","Rat"]`, `["base","Bool"]` e `["fn",[tipos de argumentos],tipo de resultado]`. Os descritores de slots carregam nome, tipo e três indicadores booleanos de mutabilidade, recursão e inicialização. Um endereço léxico `(distancia,indice)` vira um vetor JSON com dois inteiros e retorna a uma tupla numérica rigidamente validada ao carregar o arquivo. Assim, mudanças acidentais em classes Python não alteram silenciosamente o contrato persistido.

## Limites de decodificação e rejeição de ambiguidades

Um documento JSON sintaticamente válido não equivale a um programa de bytecode válido. A função `load_bytecode` exige um objeto `bytes` e limita a entrada a **131.072 bytes**. O parser exige UTF-8 válido, rejeita chaves duplicadas e não admite números de ponto flutuante nem literais não finitos. Inteiros textuais são limitados a 80 algarismos decimais. Os campos de cada objeto são exatos: propriedades extras, campos ausentes e tipos desconhecidos geram falha. Também existem limites para extensão de vetores, profundidade de código, quantidade total de instruções e de objetos de código.

A reconstrução de `SlotInfo`, `FunctionType`, `SlotCode` e `VerifiedProgram` acontece por meio de construtores enumerados explicitamente. Nenhum dado carregado aciona `pickle`, `eval`, `exec` nem importa funções nomeadas pelo arquivo. Código de closures aninhadas continua sendo **dados**. Versões e identificadores desconhecidos são rejeitados sem tentar interpretar uma versão nova como antiga. Migração exigiria um contrato de compatibilidade separado.

Também há regras para operandos: `LOAD_SLOT` e `STORE_SLOT` exigem exatamente duas coordenadas inteiras não negativas; `PUSH_BOOL` exige um booleano; chamadas e saltos exigem inteiros; e `CLOSURE_SLOT` deve conter um objeto de código. Mesmo depois dessas verificações estruturais, uma sequência pode possuir **semântica inválida de pilha ou tipos**, o que exige a execução do verificador específico da VM.

## SHA-256: integridade não é autenticação

O codificador calcula um digest SHA-256 do **payload canonicamente codificado**, incluindo sua representação hexadecimal minúscula no envelope [3]. O carregador recalcula esse digest e compara as cadeias hexadecimais com uma operação de comparação em tempo constante. Se uma falha de armazenamento modificar algum dado sem atualizar o digest, o carregamento é interrompido. Isso constitui uma **checagem de integridade contra corrupção acidental**, não a prova da identidade do emissor.

Quem pode alterar tanto o payload quanto seu checksum consegue produzir um SHA-256 novo. A comparação em tempo constante não altera essa conclusão. Para autenticar a origem do bytecode seria necessário definir um modelo de confiança e utilizar MAC com chave secreta ou assinatura digital com verificação de chaves gerenciadas. Este módulo não implementa autenticação, sigilo, isolamento de processos nem um carregador de plugins seguro. A distinção é particularmente importante quando um digest criptográfico é apresentado como mecanismo de segurança.

## Verificação obrigatória antes da execução

Depois de decodificar os objetos, o carregador executa `verify_slots`. O verificador existente interpreta abstratamente os caminhos alcançáveis e confere tipos da pilha, endereços léxicos, permissões de escrita, escopos, retornos, junções de controle e a ordem restrita da inicialização recursiva [4]. Somente depois disso o programa reconstruído é devolvido. A função `run_slots` também verifica antes da execução: é uma validação redundante intencional. Recalcular um checksum SHA-256 não permite executar `ADD` com pilha vazia nem `LOAD_SLOT` com endereço inexistente.

O [módulo de bytecode versionado](https://github.com/christianrss/manual/blob/main/examples/python/versioned_bytecode.py) disponibiliza `dump_bytecode`, `load_bytecode`, `evaluate_wire` e `WireFormatError`. O exemplo executa uma serialização e desserialização completas:

~~~python
from fractions import Fraction
from examples.python.lexical_slot_verifier import compile_slots, run_slots
from examples.python.versioned_bytecode import (
    dump_bytecode, load_bytecode, WireFormatError,
)

source = ("let rec fact:Fn(Int)->Int="
          "fn(n:Int)->Int=>if n<2 then 1 else n*fact(n-1) "
          "in fact(5)")
blob = dump_bytecode(compile_slots(source))
restored = load_bytecode(blob)
assert run_slots(restored) == Fraction(120)
assert blob == dump_bytecode(restored)

try:
    load_bytecode(blob.replace(b'"version":1', b'"version":2'))
    assert False, "unsupported format versions must fail"
except WireFormatError:
    pass
~~~

A [suíte de contratos](https://github.com/christianrss/manual/blob/main/tests/test_versioned_bytecode_contracts.py) compara resultados de programas reconstruídos com o interpretador direto independente da AST e com o programa compilado antes da serialização. Os testes recalculam propositalmente checksums de **instruções inválidas**, demonstrando que a rejeição de endereços incorretos, opcodes inexistentes, fluxo de controle e tipos incompatíveis depende do verificador, não apenas do SHA-256.

## Custos, riscos residuais e política de compatibilidade

Serializar o código exige percorrer objetos, instruções e todos os descritores de tipos léxicos. Se m representa as instruções e s os campos serializados de descritores, o custo de percorrer os dados depende do tamanho da representação **inteira**, não somente de m. O hashing e a escrita JSON também processam os bytes codificados. O limite da entrada é de 128 KiB; quantidades de objetos e instruções possuem tetos próprios. Essas restrições diminuem a exposição a entradas malformadas, mas não provam um limite absoluto de CPU e memória contra entradas adversariais.

A linguagem continua admitindo frações com precisão arbitrária e chamadas recursivas. Uma única instrução válida pode demandar cálculo caro; um programa estruturalmente correto ainda pode esgotar o orçamento de execução ou lançar divisão por zero. O bytecode não possui assinatura, compressão, parser de fluxo contínuo, migração entre versões, otimizador nem isolamento pelo sistema operacional.

A política de compatibilidade é deliberadamente conservadora: a versão **1** rejeita campos desconhecidos e versões não reconhecidas. Uma eventual v2 precisa documentar novos opcodes, codificações e invariantes. Compatibilidade retroativa deve ser demonstrada usando arquivos reais preservados de versões anteriores, e não presumida apenas porque os arquivos compartilham uma extensão.

## Exercícios e verificação

1. Por que dois textos JSON semanticamente equivalentes podem gerar hashes diferentes sem padronização? **Verificação:** ordem das chaves e espaços alteram os bytes.
2. Modifique o payload mantendo o checksum original. **Verificação:** `load_bytecode` rejeita a divergência.
3. Recalcule o checksum de uma sequência contendo `ADD` sem operandos. **Verificação:** o hash confere, mas o verificador tipado rejeita a pilha insuficiente.
4. Mude a versão de 1 para 2. **Verificação:** o carregador falha, sem assumir compatibilidade.
5. Explique por que um arquivo de 128 KiB não impõe limite de 128 KiB na memória de execução. **Verificação:** os objetos decodificados, pilhas, ambientes e frações precisam de memória adicional.
6. Qual mecanismo extra permitiria verificar quem publicou o bytecode? **Verificação:** assinatura digital ou MAC e uma política explícita de confiança e gerenciamento de chaves.

As próximas camadas envolvem fixtures persistentes de compatibilidade, distribuição autenticada e um modelo independente de alcançabilidade de memória. Nenhuma dessas capacidades decorre automaticamente do serializador v1.
