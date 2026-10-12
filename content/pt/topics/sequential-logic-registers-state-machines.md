---
id: sequential-logic-registers-state-machines
title: "Fundamentos de lógica sequencial: relógio, registradores e máquinas de estados"
description: "Derive transições síncronas, flip-flops D, registradores e máquinas de estados com rastreamentos e invariantes executáveis."
category: computer-architecture
difficulty: foundational
updated: 2026-10-12
prerequisites: [digital-logic-gates-binary-adders, programming-control-flow-functions]
sources:
  - {title: "Nand2Tetris — Project 3: Memory", url: "https://www.nand2tetris.org/project03", kind: "open educational course"}
  - {title: "MIT OpenCourseWare — Computation Structures", url: "https://ocw.mit.edu/courses/6-004-computation-structures-spring-2017/", kind: "university course"}
  - {title: "Nand2Tetris — Hardware course", url: "https://www.nand2tetris.org/course", kind: "open educational course"}
---
Portas combinacionais calculam uma saída a partir das entradas observadas num instante. Um computador também precisa **reter valores entre instantes**: endereço da instrução, registradores de operandos e estados intermediários dependem de acontecimentos anteriores. A lógica sequencial acrescenta estado explícito e regra sincronizada para atualizá-lo. Esse é o elo entre tabelas-verdade, armazenamento e execução de máquina, sem exigir construir uma CPU inteira [1][2].

## Lógica combinacional e estado sequencial

Na lógica combinacional, a saída no instante t pode ser descrita por y(t)=f(x(t)). Uma porta AND de duas entradas não recorda se elas eram zero anteriormente. Já um sistema sequencial possui estado interno q(t) e calcula o próximo estado por q(t+1)=F(q(t),x(t)). Uma saída pode depender só do estado, numa máquina de Moore, ou do estado e entrada, numa máquina de Mealy. São dois modelos comuns de máquina de estados finitos, não regras específicas de Python.

Estado é **informação mantida entre atualizações**, não um histórico completo das entradas. Pode ser um bit, uma tupla de bits de registrador ou um índice dentre estados de um protocolo. O contrato deve determinar quando o estado muda e como calcular a próxima versão.

## Flip-flop D e borda de relógio

Um flip-flop D ideal disparado por borda guarda um bit. Imediatamente antes da borda ativa do relógio, amostra sua entrada D; imediatamente depois, a saída armazenada Q passa a representar esse valor amostrado. Entre bordas ativas, Q permanece igual mesmo se D variar. Em tempo discreto, a regra é Q[k+1]=D[k] na borda amostrada [1][3].

Um latch sensível a nível é diferente: enquanto estiver habilitado, modificações de entrada podem atravessar até a saída. Confundir latch transparente e flip-flop de borda gera erros de temporização. Os exemplos assumem um dispositivo ideal de borda, não modelam transistores, violações de setup/hold, metaestabilidade nem atrasos elétricos.

Relógio não significa cronômetro Python. Cada chamada à operação tick representa uma **borda lógica ativa**. O código não pode calcular ou assegurar frequência elétrica nem atrasos de propagação.

## Construa um registrador de n bits

Um registrador reúne n bits armazenados e atualizados na mesma borda lógica. Com sinal de habilitação L, a transição é Q_next=D se L=1 e Q_next=Q se L=0. Isso equivale a selecionar entre o valor anterior e uma nova entrada por multiplexador antes de cada flip-flop. Inicializar todos os bits em zero é um contrato do modelo, não afirmação de que todo circuito físico liga com zeros.

Para registrador de três bits, suponha Q=(0,0,0). A entrada D=(1,0,1) com habilitação falsa não modifica estado. Na próxima borda, com habilitação verdadeira, Q passa a (1,0,1). Consultar o registrador não dispara borda e não deve modificar os bits. Valide todos os elementos da entrada antes de atualizar qualquer bit, evitando alterações parciais quando houver entrada inválida.

## Construa contador de estados finitos

Um contador sem sinal de n bits possui 2^n estados, inteiros de 0 a 2^n-1. Escolha a transição nesta ordem de prioridade: reset força zero; caso contrário, enable incrementa módulo 2^n; na ausência dos dois, mantém o valor anterior. Para contador de três bits, a transição de 7 para 0 é retorno modular esperado, não erro aritmético não tratado.

A prioridade faz parte da interface. Se reset e enable são ativados juntos, **reset prevalece**. Outro contador poderia ter prioridade diferente ou reset assíncrono, mas sua tabela de transições deveria explicitar a política. Nosso contador é uma função pura: recebe estado, largura e sinais, devolvendo próximo estado sem alterar dispositivo físico.

~~~python
def bit(value):
    if type(value) is not int or value not in (0, 1):
        raise ValueError("expected one binary digit")
    return value

class ClockedRegister:
    def __init__(self, width):
        if type(width) is not int or width <= 0:
            raise ValueError("positive register width required")
        self._bits = (0,) * width

    def read(self):
        return self._bits

    def tick(self, data, load):
        if type(load) is not bool:
            raise ValueError("load must be Boolean")
        incoming = tuple(bit(x) for x in data)
        if len(incoming) != len(self._bits):
            raise ValueError("data bus width mismatch")
        if load:
            self._bits = incoming
        return self._bits

def counter_tick(value, width, reset, enable):
    if (type(value) is not int or type(width) is not int
            or type(reset) is not bool or type(enable) is not bool
            or width <= 0 or not 0 <= value < 2 ** width):
        raise ValueError("invalid counter state or control")
    if reset:
        return 0
    if enable:
        return (value + 1) % (2 ** width)
    return value

r = ClockedRegister(3)
assert r.read() == (0, 0, 0)
assert r.tick((1, 0, 1), False) == (0, 0, 0)
assert r.tick((1, 0, 1), True) == (1, 0, 1)
assert r.read() == (1, 0, 1)
assert counter_tick(7, 3, False, True) == 0
assert counter_tick(7, 3, True, True) == 0
try:
    r.tick((1, 2, 1), True)
except ValueError:
    pass
else:
    raise AssertionError("invalid bit accepted")
assert r.read() == (1, 0, 1)
~~~

## Atualizações simultâneas e invariantes

Um conjunto de registradores síncronos atualiza seu estado lógico na mesma borda de relógio. Se registradores dependerem uns dos outros, cada próximo valor deve ser calculado com base no **estado anterior**, e somente depois todas as atualizações devem ser efetivadas. Alterar A antes de calcular B pode fazer B observar o A novo, mudando o circuito que se pretendia representar.

No exemplo do registrador, o invariante é Q possuir sempre a largura declarada e conter apenas bits 0 ou 1. O construtor o satisfaz. Entrada inválida causa exceção antes da mutação. Transição de retenção mantém Q e transição de carga substitui Q por tupla validada. Por indução, toda borda válida preserva o invariante.

Para o contador, o estado satisfaz 0 <= valor < 2^n. Reset devolve zero; retenção devolve o valor anterior; incremento modular devolve número no mesmo intervalo. Isso demonstra que **toda transição válida** mantém os limites, independentemente da quantidade de ciclos anteriores.

## Tabelas de transição e rastreamentos

Antes de implementar máquina de estados, enumere estados, entradas relevantes e estados esperados após cada evento. Um contador de três bits tem oito estados; reset e enable possuem duas possibilidades cada. Um rastreamento 5 → 6 → 7 → 0 com enable ativo torna visível o retorno modular. Sem enable, o estado seguinte é igual ao atual.

Uma máquina de semáforo pode possuir estados VERDE, AMARELO e VERMELHO e eventos de relógio que provocam avanços determinísticos. Os nomes sozinhos não garantem temporização ou segurança: durações e entradas de sensores exigem contratos adicionais. Também é possível modelar estados de interface de usuário, mas não se deve confundir seus eventos com bordas de circuito físico. A estrutura matemática das transições é comum, apesar das hipóteses diferentes.

## Capacidade, complexidade e falhas de modelo

Um registrador de n bits armazena um dentre 2^n estados e exige fisicamente n bits de estado. No modelo simples de contagem de operações lógicas, atualizar seus bits custa O(n) operações e O(n) bits armazenados. Num registrador físico de largura fixa, um contador incrementa módulo 2^n; a função Python não modela a atividade elétrica nem o circuito de transporte que implementa a soma.

Circuitos síncronos reais precisam considerar skew de relógio, atraso de propagação e requisitos de setup/hold. Metaestabilidade pode ocorrer em fronteiras assíncronas; este modelo lógico não a descreve. Passar nos testes demonstra apenas a correção do **modelo de transição discreta**, não a viabilidade temporal de um circuito físico [2].

## Exercícios e verificação

1. Diferencie o comportamento de latch e flip-flop D quando a entrada muda entre bordas.
2. Escreva tabela-verdade do registrador de um bit com Q anterior, D e habilitação.
3. Enumere transições de contador de dois bits para todos os estados e ambos os valores de enable, com reset falso.
4. Comprove que reset prevalece quando reset e enable estão ativos; depois defina política inversa e compare resultados.
5. Modele dois registradores A e B que trocam valores na mesma borda e explique o erro de calcular B após modificar A.
6. Diferencie passos lógicos do modelo Python de atraso de propagação de circuito físico.

Continue com [portas lógicas e somadores](/pt/topics/digital-logic-gates-binary-adders/), [representação e instruções de máquina](/pt/topics/machine-representation-isa-cache/) e [autômatos finitos](/pt/topics/formal-languages-finite-automata/).