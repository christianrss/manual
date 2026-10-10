---
id: machine-representation-isa-cache
title: "Representação de máquina, instruções de CPU e mapeamento de cache"
description: "Derive complemento de dois, endianness, execução de instruções e conflitos de cache com modelos Python reproduzíveis e casos-limite."
category: computer-architecture
difficulty: foundational
updated: 2026-10-10
prerequisites: [complexity-analysis]
sources:
  - {title: "RISC-V — RV32I Base Integer Instruction Set", url: "https://docs.riscv.org/reference/isa/v20260120/unpriv/rv32.html", kind: "ratified ISA specification"}
  - {title: "Intel — 64 and IA-32 Optimization Manuals", url: "https://www.intel.com/content/www/us/en/developer/articles/technical/intel64-and-ia32-architectures-optimization.html", kind: "official optimization manuals"}
  - {title: "Python — Built-in Types and integer byte conversion", url: "https://docs.python.org/3/library/stdtypes.html", kind: "official language specification"}
---
Um programa de alto nível termina manipulando representações binárias, executando instruções e acessando uma hierarquia de memória. Essas camadas explicam fenômenos que a notação Big O não prevê sozinha: algoritmos da mesma classe assintótica podem ter desempenho muito diferente devido a caches, alinhamento, desvios e disposição de dados. É essencial separar **representação de máquina** (como bits codificam valores), **ISA** (operações e estado visível ao software), **microarquitetura** (como um processador implementa a ISA) e **abstrações de sistema operacional** (memória virtual e escalonamento) [1][2].

Este capítulo constrói uma base delimitada. **Não** pretende cobrir processadores inteiros, lógica digital, pipeline, coerência de cache, privilégio RISC-V ou execução real de x86. Os exemplos Python são **máquinas didáticas**, não emuladores fiéis de um processador. A vantagem é tornar contratos pequenos reproduzíveis antes de estudar equipamentos reais.

## Bits, bytes, inteiros sem sinal e complemento de dois

Um bit pode valer 0 ou 1. Oito bits possuem `2^8=256` combinações. Interpretadas **sem sinal**, representam 0 a 255; interpretadas em **complemento de dois**, representam -128 a 127. Quando o bit de maior peso é 1, subtraímos 256 do valor sem sinal. Portanto, os **mesmos bits** podem ser interpretados de maneiras diferentes: não são duas memórias distintas [1].

Para uma largura fixa `w`, a soma de inteiros em diversos registradores conserva apenas os `w` bits inferiores, equivalendo ao módulo `2^w`. Isso não é igual aos inteiros de precisão arbitrária do Python nem determina a semântica de toda linguagem: overflow assinado em C/C++ é regido por regras próprias; outros ambientes lançam exceções. Não deduza as regras de uma linguagem a partir deste exemplo de hardware [1].

```python
def interpretar_assinado8(bruto):
    if type(bruto) is not int or not 0 <= bruto < 256:
        raise ValueError("inteiro de oito bits sem sinal obrigatorio")
    return bruto - 256 if bruto & 0x80 else bruto

def somar8(esquerda, direita):
    if (type(esquerda) is not int or type(direita) is not int
            or not 0 <= esquerda < 256 or not 0 <= direita < 256):
        raise ValueError("operandos de oito bits obrigatorios")
    return (esquerda + direita) & 0xff

assert interpretar_assinado8(0b01111111) == 127
assert interpretar_assinado8(0b10000000) == -128
assert interpretar_assinado8(0b11111111) == -1
assert somar8(255, 1) == 0
assert interpretar_assinado8(somar8(127, 1)) == -128
```

**Dedução:** a máscara `0xff` conserva os bits 0–7. Logo `somar8(a,b)=(a+b) mod 256`. A interpretação com sinal subtrai 256 precisamente quando o bit 7 está definido. É possível testar exaustivamente todos os 256 bytes e 65.536 pares de somas porque o modelo é finito. Para inteiros de 64 bits, tal enumeração não é prática; provas algébricas e casos de fronteira ganham importância.

## Ordem dos bytes, endereçamento e alinhamento

Uma memória **endereçada por bytes** atribui endereços a bytes individuais. Endianness especifica a ordem dos bytes de um valor composto em endereços consecutivos; **não** inverte os bits dentro de cada byte. Para 0x12345678, a sequência big-endian é `12 34 56 78`; a little-endian é `78 56 34 12`. A especificação RISC-V define expressamente essa diferença para ambientes com operações de carga e armazenamento [1].

```python
valor = 0x12345678
grande = valor.to_bytes(4, "big")
pequena = valor.to_bytes(4, "little")
assert grande.hex() == "12345678"
assert pequena.hex() == "78563412"
assert int.from_bytes(grande, "big") == valor
assert int.from_bytes(pequena, "little") == valor
assert int.from_bytes(grande, "little") != valor
assert (-2).to_bytes(2, "little", signed=True) == bytes([254, 255])
assert int.from_bytes(bytes([254, 255]), "little", signed=True) == -2
```

A API do Python explicita byte order e interpretação assinada [3]. Protocolos, formatos binários e interfaces devem declarar esses parâmetros; adivinhar a configuração do processador provoca incompatibilidade. **Alinhamento** é conceito diferente: uma palavra de quatro bytes tem alinhamento natural quando começa em endereço múltiplo de quatro. Dependendo da ISA e do ambiente, acessos desalinhados podem ser suportados, tratados lentamente por exceções ou rejeitados. Não existe regra universal de que todo acesso desalinhado provoque falha [1].

## ISA e microarquitetura: o que o programa observa?

A **arquitetura do conjunto de instruções** é o contrato visível ao software: registradores, instruções, exceções e demais efeitos arquiteturalmente definidos. A RV32I possui 32 registradores inteiros de 32 bits, `x0` permanentemente zero, além do contador de programa. Instruções aritméticas como `ADD` operam nos registradores; `load` e `store` movem valores entre registradores e memória. É uma arquitetura **load/store**. CPUs com pipelines e caches diferentes podem manter os mesmos resultados arquiteturais [1].

A **microarquitetura** é a implementação: busca e decodificação de instruções, unidades de execução, predição de desvios, especulação, execução fora de ordem e organização das caches. Dois processadores com a mesma ISA podem diferir muito em latência e energia. Nem a quantidade de linhas de código nem a de instruções determina isoladamente o tempo: dependências e espera por memória importam [2]. O compilador também transforma código de alto nível, distribui registradores e seleciona instruções, portanto uma instrução da linguagem não equivale necessariamente a uma instrução de máquina.

## Programa demonstrativo: máquina simplificada, sem reproduzir RISC-V

Para visualizar estados, construiremos uma máquina com **quatro registradores de oito bits**, memória endereçada por byte e sem saltos, modos privilegiados ou interrupções. As instruções fictícias `LI`, `LD`, `ADD` e `ST` carregam literal, leem memória, somam com overflow de oito bits e armazenam resultado. A sintaxe **não é Assembly RISC-V**. Apenas reproduz a ideia de transições sequenciais de estado arquitetural [1].

```python
class MaquinaDidatica:
    def __init__(self, memoria):
        if any(type(v) is not int or not 0 <= v < 256 for v in memoria):
            raise ValueError("memoria deve conter bytes")
        self.memoria = bytearray(memoria)
        self.registradores = [0, 0, 0, 0]
        self.pc = 0

    def executar(self, programa):
        for instrucao in programa:
            op, *argumentos = instrucao
            if op == "LI" and len(argumentos) == 2:
                destino, imediato = argumentos
                self._reg(destino)
                if type(imediato) is not int or not 0 <= imediato < 256:
                    raise ValueError("imediato invalido")
                self.registradores[destino] = imediato
            elif op == "LD" and len(argumentos) == 2:
                destino, endereco = argumentos
                self._reg(destino)
                self._end(endereco)
                self.registradores[destino] = self.memoria[endereco]
            elif op == "ADD" and len(argumentos) == 3:
                destino, a, b = argumentos
                for r in (destino, a, b):
                    self._reg(r)
                self.registradores[destino] = somar8(
                    self.registradores[a], self.registradores[b])
            elif op == "ST" and len(argumentos) == 2:
                origem, endereco = argumentos
                self._reg(origem)
                self._end(endereco)
                self.memoria[endereco] = self.registradores[origem]
            else:
                raise ValueError("instrucao desconhecida ou incompleta")
            self.pc += 1

    def _reg(self, indice):
        if type(indice) is not int or not 0 <= indice < len(self.registradores):
            raise ValueError("registrador invalido")

    def _end(self, endereco):
        if type(endereco) is not int or not 0 <= endereco < len(self.memoria):
            raise ValueError("endereco invalido")

maquina = MaquinaDidatica([250, 9, 0])
maquina.executar([
    ("LD", 0, 0), ("LD", 1, 1), ("ADD", 2, 0, 1), ("ST", 2, 2)
])
assert maquina.registradores[2] == 3
assert list(maquina.memoria) == [250, 9, 3]
assert maquina.pc == 4
```

O resultado de oito bits é `(250+9) mod 256 = 3`. O `pc` avança **uma posição na lista** por instrução concluída, *não* um número real de bytes de instrução. Uma validação pode falhar depois que instruções anteriores já modificaram o estado: não há atomicidade, transação, isolamento de segurança nem execução concorrente. Mesmo `ADD` demonstra apenas a noção de aritmética entre registradores, não codificação real. O exercício consiste em deduzir **transições observáveis**, sem confundir demonstração e emulação.

## Linhas de cache: deslocamento, conjunto, tag e conflito

Uma cache armazena **blocos/linhas** recentemente usados, normalmente abrangendo vários bytes. Num modelo didático de cache de **mapeamento direto**, com `S` posições e linha de `B` bytes, para endereço não negativo `a`:

`bloco = floor(a/B)`, `deslocamento = a mod B`, `posicao = bloco mod S`, `tag = floor(bloco/S)`.

A posição define **onde** o bloco pode ficar e a tag identifica **qual bloco** ocupa aquela posição. Blocos diferentes com a mesma posição expulsam um ao outro: são **faltas por conflito**. Uma falta compulsória ocorre no primeiro acesso ao bloco. Caches reais podem ser associativas por conjuntos, de vários níveis e com regras de substituição e coerência ausentes deste modelo [2].

```python
class CacheDireta:
    def __init__(self, bytes_linha, posicoes):
        if (type(bytes_linha) is not int or type(posicoes) is not int
                or bytes_linha <= 0 or posicoes <= 0):
            raise ValueError("geometria inteira positiva obrigatoria")
        self.bytes_linha = bytes_linha
        self.posicoes = posicoes
        self.tags = [None] * posicoes
        self.acertos = self.faltas = 0

    def acessar(self, endereco):
        if type(endereco) is not int or endereco < 0:
            raise ValueError("endereco de byte nao negativo obrigatorio")
        bloco = endereco // self.bytes_linha
        posicao = bloco % self.posicoes
        tag = bloco // self.posicoes
        acerto = self.tags[posicao] == tag
        if acerto:
            self.acertos += 1
        else:
            self.faltas += 1
            self.tags[posicao] = tag
        return acerto

cache = CacheDireta(4, 2)
sequencia = [0, 1, 8, 0, 4, 5, 0]
assert [cache.acessar(a) for a in sequencia] == [
    False, True, False, False, False, True, True
]
assert (cache.acertos, cache.faltas) == (3, 4)
```

O simulador considera **um acesso de byte por posição da sequência**, ignora escrita, não armazena valores nem modela tempo. Cada acesso requer `O(1)` operações abstratas e o vetor de tags ocupa `O(S)` posições sob aritmética de custo constante; não é uma cache física. Endereços 0 e 8 mapeiam na posição 0 para linhas de quatro bytes e duas posições, causando substituição; 0 e 1 ficam na mesma linha, então o segundo acesso acerta. A saída é determinada pelo modelo, mas **não** prevê miss rate ou tempo de uma CPU moderna.

## Localidade de memória e desempenho de algoritmos

**Localidade espacial** ocorre quando endereços próximos são usados em intervalo pequeno: carregar uma linha pode atender a vários acessos futuros. **Localidade temporal** ocorre quando o mesmo bloco é reutilizado antes da expulsão. Percorrer sequencialmente um array denso muitas vezes explora melhor a localidade que seguir nós espalhados de uma lista ligada. Assim, dois algoritmos `O(n)` podem apresentar tempos muito diferentes. Porém o resultado depende de layout, geometria de cache, compilador, conjunto de trabalho e concorrência; afirmações sobre performance exigem medição [2].

O **TLB** não é cache de dados: acelera a tradução de endereços virtuais para físicos. Page fault não é o mesmo que falta de cache, e chamada de sistema não é uma simples função lenta. Cache, TLB, coerência, páginas virtuais, permissões e escalonamento são mecanismos relacionados mas distintos. O capítulo de [processos e memória virtual](/pt/topics/processes-virtual-memory/) desenvolve tradução e proteção. O capítulo de [pipeline e previsão de desvios](/pt/topics/cpu-pipeline-hazards-branch-prediction/) agora aborda stalls e dependências em modelo didático. Associatividade, coerência multicore e medições de hardware ainda exigem tratamento próprio.

## Exercícios e verificação

1. Enumere as representações de -128, -1, 0 e 127 em oito bits. Prove que `interpretar_assinado8((x+256) % 256)` devolve `x` para todo `-128 <= x <= 127`.
2. Derive independentemente o resultado de todas as 65.536 somas de bytes pelo módulo 256. Explique quando a interpretação assinada diverge da soma matemática.
3. Escreva os quatro bytes de 0x01020304 em big e little-endian. Explique por que endianness e alinhamento são conceitos distintos.
4. Trace o programa da máquina didática manualmente; altere o segundo operando e identifique a primeira instrução cujo resultado muda, bem como o estado afetado.
5. Para `B=4` e `S=2`, calcule bloco, posição e tag de 0, 1, 4, 8 e 12. Preveja acertos antes de executar a cache.
6. Construa uma sequência de endereços diferentes com muitos acertos por localidade espacial; depois uma sequência que cause conflitos repetidos.
7. Explique por que um simulador de cache isolado não demonstra o desempenho real de consulta SQL ou programa paralelo.
8. Classifique cada aspecto como **ISA**, **microarquitetura**, **SO** ou **runtime**: largura de registradores, política de cache, permissões em tabelas de páginas e inteiros arbitrários Python.

**Continuação:** [pipeline, hazards e previsão de desvios](/pt/topics/cpu-pipeline-hazards-branch-prediction/) explica o tempo das instruções; [processos e memória virtual](/pt/topics/processes-virtual-memory/) explica tradução e proteção; [concorrência](/pt/topics/concurrency-synchronization/) explica condições de corrida; [complexidade](/pt/topics/complexity-analysis/) fornece modelo de custos. Uma explicação executável não substitui revisão técnica independente nem medição real [1][2][3].
