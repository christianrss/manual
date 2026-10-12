---
id: data-types-bytes-and-representation
title: "Tipos e representação de dados: inteiros, bytes, texto e precisão"
description: "Aprenda contratos de tipos, limites de inteiros, endianness, UTF-8 e precisão numérica com formato binário verificável."
category: foundations
difficulty: foundational
updated: 2026-10-12
prerequisites: [programming-control-flow-functions]
sources:
  - {title: "Python language reference — Data model", url: "https://docs.python.org/3/reference/datamodel.html", kind: "official language reference"}
  - {title: "Python tutorial — Floating-point arithmetic", url: "https://docs.python.org/3/tutorial/floatingpoint.html", kind: "official language tutorial"}
  - {title: "Python standard library — Binary sequence types", url: "https://docs.python.org/3/library/stdtypes.html#binary-sequence-types-bytes-bytearray-memoryview", kind: "official language reference"}
  - {title: "Python Unicode HOWTO", url: "https://docs.python.org/3/howto/unicode.html", kind: "official language documentation"}
---
Todo programa opera sobre **valores representados em memória**. Um tipo determina quais valores e operações são significativos; a representação determina como os valores são codificados. Confundir os dois conceitos causa defeitos comuns: um preço arredondado por ponto flutuante binário, um booleano aceito como quantidade inteira, um caractere multibyte contado como um único byte transmitido ou um valor truncado ao converter para inteiro de largura fixa. Esses erros surgem muito antes de orientação a objetos ou arquitetura distribuída.

## Valores, tipos e operações

Valor é objeto matemático ou da linguagem, como o inteiro 7, o booleano True ou a string "Ação". Tipo fornece operações e interpretação: somar inteiros difere de concatenar strings. Python associa tipos aos objetos dinamicamente, em vez de exigir tipo declarado estaticamente para cada variável. Nomes referenciam objetos; associar outro objeto ao nome não necessariamente modifica o anterior [1].

Um **contrato de entrada** restringe ainda mais os valores de um tipo. Quantidade positiva não significa apenas "int": exige inteiro maior que zero e talvez limite máximo. Identificador pode ser string, mas rejeitar conteúdo vazio ou somente espaços. Anotações de tipo comunicam expectativas, porém não fazem validação automática de todo valor recebido em execução. Restrições do domínio precisam ser verificadas nas fronteiras em que entra dado inválido.

Em Python, `isinstance(True, int)` é verdadeiro porque bool é subtipo de int [1]. Uma função que exige quantidade inteira e proíbe booleanos pode usar `type(x) is int`. É decisão específica desse contrato e dessa linguagem: não significa que herança de tipos seja sempre erro ou que outras linguagens tratem bool da mesma maneira.

## Intervalos de inteiros e armazenamento fixo

Inteiros matemáticos não possuem valor máximo fixo, mas representações de máquina normalmente reservam quantidade limitada de bits. Um inteiro sem sinal de largura w representa valores de 0 a 2^w−1; um inteiro com sinal de w bits em complemento de dois representa de −2^(w−1) até 2^(w−1)−1. Com oito bits sem sinal, existem 2^8 = 256 padrões possíveis e os valores vão de 0 a 255.

Com dezesseis bits sem sinal, o máximo é 65535. Gravar 65536 num campo de dois bytes exige rejeitar, saturar ou permitir uma operação explícita de retorno modular; essas alternativas não são equivalentes. O int normal do Python não é limitado a dezesseis bits, mas serializá-lo em campo fixo impõe o limite. Defina a política de overflow no encoder e no decoder.

Bit é dígito binário e oito bits formam byte no formato estudado. Se um valor ocupa múltiplos bytes, a **ordem dos bytes** (*endianness*) determina onde ficam os bits menos significativos. Para 513, hexadecimal 0x0201, a sequência little-endian é [0x01,0x02] e a big-endian é [0x02,0x01]. Nenhuma é universalmente correta: o contrato precisa escolher uma [3].

## Ponto flutuante e aritmética decimal exata

Em Python, float representa normalmente valores finitos com ponto flutuante binário. A fração decimal 0,1 não possui representação fracionária binária finita, portanto `0.1 + 0.2 == 0.3` pode resultar em False. Isso decorre de representação e arredondamento, não demonstra que o algoritmo de adição está incorreto [2]. Medições físicas aproximadas muitas vezes toleram erro controlado; centavos exatos e regras contábeis exigem escolhas diferentes.

Alternativas incluem contagem inteira da menor unidade definida, como centavos, Decimal construído de strings para entradas decimais exatas, e números racionais quando adequados. Mesmo Decimal não fornece regras de câmbio, casas decimais de cada moeda nem tributação. Transformar float já impreciso em Decimal não recupera automaticamente a fração decimal pretendida. Escolha representação conforme **o significado do valor e erro permitido**, sem adotar float ou int indiscriminadamente.

## Texto não é sequência de bytes brutos

String Unicode no Python é sequência de pontos de código; bytes contém inteiros de 0 a 255. UTF-8 codifica texto Unicode com quantidade variável de bytes [4]. Assim, `len("Ação")` vale quatro pontos de código, mas `len("Ação".encode("utf-8"))` vale cinco bytes, pois "ç" exige mais de um byte. Um grafema percebido pelo usuário pode conter múltiplos pontos de código. Logo, nenhuma das contagens necessariamente representa quantidade de caracteres visuais.

Use `str.encode("utf-8")` para gerar bytes e `bytes.decode("utf-8", errors="strict")` para recuperar texto. Sequências de bytes inválidas podem ser rejeitadas em vez de substituídas silenciosamente. Alguns sistemas normalizam Unicode antes de comparar identificadores, mas isso é política diferente da codificação UTF-8. Não corte uma sequência UTF-8 em offset arbitrário de byte e pressuponha que continuará válida.

## Derive um formato binário explícito

Defina formato didático para contador com rótulo. Seu registro possui: um byte N, seguido de exatamente N bytes UTF-8 de rótulo não vazio, seguido de contador unsigned de dois bytes little-endian. Exija 1 ≤ N ≤ 255 e 0 ≤ contador ≤ 65535. O decodificador deve consumir **todo o registro**; aceitar bytes adicionais gera interpretação ambígua quando o chamador espera somente um registro.

Para "Ação", UTF-8 utiliza cinco bytes, portanto o primeiro byte será 5. Para contador 513, os bytes finais serão 1 e 2. O registro completo possui oito bytes: um de tamanho, cinco de texto e dois de contador. Encoder e decoder precisam concordar sobre comprimento e endianness. É exercício de representação, não protocolo produtivo: não inclui versão, autenticação, checksum nem framing de múltiplos registros.

~~~python
def encode_record(label, count):
    if not isinstance(label, str) or not label.strip():
        raise ValueError("invalid label")
    if type(count) is not int or not 0 <= count <= 65535:
        raise ValueError("count outside uint16")
    name_bytes = label.encode("utf-8")
    if not 1 <= len(name_bytes) <= 255:
        raise ValueError("label exceeds byte limit")
    return bytes([len(name_bytes)]) + name_bytes + count.to_bytes(2, "little")

def decode_record(data):
    if not isinstance(data, bytes) or not data:
        raise ValueError("invalid record")
    name_size = data[0]
    if name_size == 0 or len(data) != 1 + name_size + 2:
        raise ValueError("invalid record length")
    label = data[1:1 + name_size].decode("utf-8", errors="strict")
    if not label.strip():
        raise ValueError("invalid label")
    count = int.from_bytes(data[-2:], "little")
    return (label, count)

example = encode_record("Ação", 513)
assert example[0] == len("Ação".encode("utf-8")) == 5
assert example[-2:] == bytes([1, 2])
assert decode_record(example) == ("Ação", 513)
assert decode_record(encode_record("max", 65535)) == ("max", 65535)
for invalid in (b"", b"\x00\x01\x00", b"\x01\xff\x01\x00",
                example + b"\x00", example[:-1]):
    try:
        decode_record(invalid)
    except ValueError:
        pass
    else:
        raise AssertionError("malformed record accepted")
for bad in (-1, 65536, True, 1.5):
    try:
        encode_record("item", bad)
    except ValueError:
        pass
    else:
        raise AssertionError("invalid count accepted")
~~~

## Correção e complexidade

O codificador primeiro rejeita tipos errados e números fora do intervalo. Converte rótulo para UTF-8, verifica *quantidade de bytes* e guarda o inteiro sem sinal em exatamente dois bytes. O decodificador verifica tamanho total exato, interpreta a região UTF-8 estritamente e converte os dois bytes finais pela mesma regra de ordem. Para qualquer rótulo e contador válidos, as operações são inversas: o comprimento identifica a região textual, UTF-8 recupera string e a conversão de inteiro devolve o valor original.

Considere L como número de bytes UTF-8 do rótulo. Codificar e decodificar exigem O(L) operações e O(L) memória para rótulo ou registro; o campo inteiro final tem tamanho constante. Neste formato, L está limitado a 255, mas a variável ainda identifica de onde vem o trabalho. Um decoder robusto não pressupõe que alguém tenha alocado antecipadamente tamanho correto.

## Contraexemplos e escolhas de projeto

Converter 65536 módulo 65536 transformaria quantidade positiva fora do limite em zero. Contar pontos de código no lugar de bytes codificados provoca rejeições e erros ao ler textos internacionais. Ler registro sem validar comprimento declarado pode misturar mensagens. Substituir bytes UTF-8 inválidos por caracteres especiais talvez seja apropriado para exibição, mas não para contrato de ida e volta exata do rótulo.

O layout proposto privilegia simplicidade e não evolução futura. Inteiros variáveis poderiam compactar valores pequenos; campo de versão permitiria novas estruturas; checksum ajudaria a detectar corrupção acidental. Esses mecanismos não são pré-requisitos para tipos, limites e representação. Primeiro estabeleça o invariante do formato e teste-o.

## Exercícios e verificação

1. Derive os intervalos com sinal e sem sinal para inteiros de 8, 16 e 32 bits. Indique a diferença quando se usa int Python.
2. Preveja o resultado de `0.1 + 0.2 == 0.3` e compare com aritmética decimal a partir de strings [2].
3. Codifique rótulos com acento e sequência combinante. Conte pontos de código, bytes UTF-8 e grafemas separadamente.
4. Escreva decoder que rejeita registros truncados, maiores que o declarado, UTF-8 inválido e rótulo de tamanho zero. Justifique cada erro.
5. Troque a ordem do campo contador para big-endian e demonstre um registro lido incorretamente pelo decoder original.
6. Especifique contrato de função que recebe número de passageiros. Explique por que aceitar True como quantidade um pode ser defeito.

Continue com [semântica de programação](/pt/topics/programming-semantics-contracts/), [arrays e strings](/pt/topics/arrays-and-strings/) e [representação de máquina](/pt/topics/machine-representation-isa-cache/).