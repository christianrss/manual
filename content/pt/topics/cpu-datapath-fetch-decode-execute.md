---
id: cpu-datapath-fetch-decode-execute
title: "Fundamentos de CPU: caminho de dados, controle e ciclo de instruções"
description: "Rastreie PC, acumulador, memória, ALU e desvios em uma CPU didática de oito bits com semântica explícita."
category: computer-architecture
difficulty: foundational
updated: 2026-10-12
prerequisites: [digital-logic-gates-binary-adders, sequential-logic-registers-state-machines, machine-representation-isa-cache]
sources:
  - {title: "MIT 6.004 — Computation Structures: The Digital World", url: "https://ocw.mit.edu/courses/6-004-computation-structures-spring-2017/pages/c9/c9s1/", kind: "university architecture course"}
  - {title: "MIT 6.004 — Building the Beta", url: "https://ocw.mit.edu/courses/6-004-computation-structures-spring-2017/pages/c13/c13s1/", kind: "university architecture course"}
  - {title: "Nand2Tetris — Project 5 Computer Architecture", url: "https://www.nand2tetris.org/project05", kind: "open educational course"}
---
Portas lógicas calculam funções booleanas e registradores sincronizados conservam estado. Uma CPU conecta esses conceitos para que **os bits armazenados na memória determinem a próxima operação**. O caminho de dados transporta e transforma operandos; a lógica de controle interpreta campos das instruções e escolhe a ação realizada. Este capítulo deriva esses papéis por meio de uma máquina didática executável antes de tratar pipelines, caches ou execução especulativa [1][2].

## Estado arquitetural e ciclo das instruções

A máquina possui contador de programa PC, acumulador A de oito bits, dezesseis células de memória com endereçamento por byte e um indicador de encerramento. Seu estado observável é (PC,A,M,halted). A instrução armazenada no endereço PC define como calcular o próximo estado. Uma instrução pode ler valor, gravar dado, alterar PC ou encerrar o programa.

A sequência conceitual é **busca, decodificação, leitura de operandos, execução, escrita do resultado e atualização do PC**. A busca lê M[PC]. A decodificação separa o byte em opcode e operando. A leitura obtém dados do acumulador ou da memória. A ALU realiza cálculos quando solicitado. A escrita atualiza acumulador ou memória conforme a operação. O PC avança uma posição, exceto quando um desvio tomado escolhe outro endereço [2].

Essas etapas descrevem funções, não necessariamente ciclos elétricos diferentes. Nosso interpretador executa uma instrução completa por chamada; não é modelo de temporização de pipeline físico.

## Formato de instrução de apenas um byte

Uma instrução ocupa oito bits. Os quatro superiores identificam a operação, enquanto os quatro inferiores codificam endereço ou imediato de 0 a 15. A memória tem dezesseis células de byte, endereçadas de 0 a 15. As operações são:

| Opcode | Instrução | Efeito |
|---|---|---|
| 1 | LOAD endereço | A recebe M[endereço] |
| 2 | STORE endereço | M[endereço] recebe A |
| 3 | ADD endereço | A recebe (A+M[endereço]) módulo 256 |
| 4 | JNZ endereço | Se A não for zero, PC recebe endereço |
| 5 | LDI valor | A recebe valor imediato de 0 a 15 |
| 6 | SUB endereço | A recebe (A−M[endereço]) módulo 256 |
| F com operando 0 | HALT | Encerra execução |

Opcode zero e demais valores não listados são inválidos. HALT com campo inferior diferente de zero também é inválido. Trata-se de uma **ISA didática fictícia**: 0x53 significa LDI 3 aqui, não em RISC-V nem x86. Ao contrário de processadores reais, não foram incluídos alinhamento, interrupções, níveis de privilégio, caches ou pipelines [1][3].

## Caminho de dados e sinais de controle

O PC é um registrador que alimenta o seletor de endereço da memória. Um registrador de instrução conserva conceitualmente o byte buscado durante a decodificação. Os bits do opcode selecionam a operação, enquanto o campo inferior fornece endereço, imediato ou destino do desvio. Um multiplexador escolhe conceitualmente as entradas da ALU. A ALU soma ou subtrai valores de oito bits; o acumulador registra o resultado.

O controle também seleciona **de onde vem o próximo PC**: normalmente PC+1, ou o operando da instrução quando JNZ é tomado. Isso diferencia caminho de dados e fluxo de controle. STORE exemplifica outro destino: o acumulador fica inalterado enquanto uma célula de memória recebe novo conteúdo. O sinal de habilitação de escrita na memória é, portanto, conceitualmente diferente da habilitação de escrita no acumulador [1][2].

Programa e dados compartilham a mesma memória de dezesseis células. Por isso uma instrução STORE poderia sobrescrever bytes de instruções. Os testes deixam os dados nas células 14 e 15, afastados do programa. Arquiteturas reais podem separar caminhos de instruções e dados ou até espaços de endereços; essas são decisões posteriores ao modelo básico.

## Modelo completo da CPU executável

O construtor copia e valida dezesseis bytes, impedindo que alterações na lista original modifiquem silenciosamente a CPU. Cada passo valida a instrução **antes de efetivar qualquer atualização**. Opcode malformado provoca ValueError sem alterar o estado. Tentar buscar com PC fora de 0–15 produz IndexError; executar depois de HALT produz RuntimeError.

~~~python
class TinyCPU:
    def __init__(self, memory):
        if (len(memory) != 16 or
                any(type(byte) is not int or not 0 <= byte <= 255
                    for byte in memory)):
            raise ValueError("16 unsigned bytes required")
        self.memory = list(memory)
        self.pc = 0
        self.acc = 0
        self.halted = False

    def step(self):
        if self.halted:
            raise RuntimeError("CPU has halted")
        if not 0 <= self.pc < 16:
            raise IndexError("program counter outside memory")
        old_pc = self.pc
        instruction = self.memory[old_pc]
        opcode, operand = instruction >> 4, instruction & 15
        if opcode not in (1, 2, 3, 4, 5, 6, 15):
            raise ValueError("unknown opcode")
        if opcode == 15 and operand != 0:
            raise ValueError("invalid HALT encoding")

        next_pc = old_pc + 1
        next_acc = self.acc
        if opcode == 1:
            next_acc = self.memory[operand]
        elif opcode == 3:
            next_acc = (self.acc + self.memory[operand]) % 256
        elif opcode == 4 and self.acc != 0:
            next_pc = operand
        elif opcode == 5:
            next_acc = operand
        elif opcode == 6:
            next_acc = (self.acc - self.memory[operand]) % 256

        if opcode == 2:
            self.memory[operand] = self.acc
        self.acc = next_acc
        self.pc = next_pc
        if opcode == 15:
            self.halted = True
        return (old_pc, opcode, operand, self.pc, self.acc)

program = [0x53, 0x2F, 0x1F, 0x6E, 0x2F, 0x42, 0xF0]
program += [0] * 7 + [1, 0]
cpu = TinyCPU(program)
trace = []
while not cpu.halted:
    trace.append(cpu.step())
assert len(trace) == 15
assert cpu.memory[15] == 0 and cpu.acc == 0
assert cpu.pc == 7 and cpu.halted
~~~ 

## Rastreie um laço instrução por instrução

A primeira operação LDI 3 inicializa A=3. STORE 15 grava o contador em M[15]. LOAD 15 recupera seu valor; SUB 14 subtrai M[14]=1; STORE 15 grava o valor reduzido. JNZ 2 retorna ao LOAD se o acumulador não for zero. Após três repetições o contador chega a zero, o desvio não é tomado e HALT encerra a execução.

A sequência contém duas instruções de inicialização, três repetições de quatro instruções e um HALT: **2+3×4+1=15 passos**. O acumulador e M[15] terminam em zero. Há uma dependência importante: JNZ observa o acumulador atualizado, enquanto o contador na memória só muda na instrução STORE.

Aqui SUB não modifica uma flag de zero separada; JNZ consulta diretamente o acumulador. É uma simplificação consciente, não descrição universal das ISAs reais.

## Invariantes, erros e correção

Após todo passo válido, acumulador e células de memória continuam inteiros no intervalo [0,255]. LOAD copia byte existente, LDI produz no máximo 15, ADD/SUB aplicam módulo 256 e STORE grava o valor do acumulador. Desvios selecionam destinos entre 0 e 15. O PC após uma operação sequencial pode tornar-se 16 caso a instrução tenha sido buscada na posição 15; a tentativa posterior de busca falha. Essa fronteira não constitui mecanismo de exceção de sistema operacional.

O método valida opcode e codificação de HALT antes de efetivar escritas. Portanto, instruções inválidas preservam memória, PC e acumulador. HALT é terminal sob este contrato. As transições são verificáveis independentemente: dado estado válido e instrução, existe no máximo um próximo estado definido.

Essas demonstrações se referem ao **contrato de transição arquitetural do interpretador**. Não comprovam limites elétricos do relógio, coerência de cache ou precisão de exceções de hardware. São responsabilidades de camadas posteriores [2][3].

## Complexidade e implementação física

Cada instrução realiza quantidade constante de operações Python nesta memória fixa de dezesseis células, supondo custo limitado das operações inteiras. Rastrear k instruções requer O(k) passos e O(k) espaço se toda transição for armazenada; executar sem acumular o trace requer O(1) de estado adicional para esta máquina de tamanho fixo.

Processadores reais podem apresentar latências diferentes para instruções distintas, cache misses e desvios que interferem em pipelines especulativos. Contar quinze passos do interpretador **não equivale a medir quinze ciclos elétricos em outra CPU**. Relacionar semântica de instruções e desempenho microarquitetural exige um modelo próprio [2].

## Exercícios e verificações

1. Desenhe ligações entre PC, busca de instrução, decodificador, acumulador, ALU e memória.
2. Decodifique 0x53, 0x2F e 0x42 conforme esta ISA *didática*.
3. Explique por que STORE altera memória sem mudar A, e JNZ altera PC sem escrever dados.
4. Modifique o imediato inicial de 3 para 2, rastreie o programa e calcule a quantidade de passos.
5. Verifique retorno modular de ADD em 255 e SUB em zero; compare com inteiros de precisão arbitrária do Python.
6. Teste opcode desconhecido e HALT malformado e demonstre ausência de atualizações parciais.

Continue por [portas lógicas](/pt/topics/digital-logic-gates-binary-adders/), [registradores síncronos](/pt/topics/sequential-logic-registers-state-machines/), [ISA e cache](/pt/topics/machine-representation-isa-cache/) e [pipelines](/pt/topics/cpu-pipeline-hazards-branch-prediction/).
