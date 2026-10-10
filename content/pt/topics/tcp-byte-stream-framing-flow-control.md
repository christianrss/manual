---
id: tcp-byte-stream-framing-flow-control
title: "TCP como fluxo de bytes: enquadramento, ACK e controle de fluxo"
description: "Derive enquadramento de mensagens TCP, sequência de bytes, ACK cumulativo e limites de envio com modelos Python verificados independentemente."
category: networking
difficulty: intermediate
updated: 2026-10-10
prerequisites: [ip-routing-dns-resolution, network-protocols]
sources:
  - {title: "RFC 9293 — Transmission Control Protocol", url: "https://www.rfc-editor.org/info/rfc9293", kind: "IETF internet standard"}
  - {title: "RFC 5681 — TCP Congestion Control", url: "https://www.rfc-editor.org/info/rfc5681", kind: "IETF internet standard"}
  - {title: "RFC 7323 — TCP Extensions for High Performance", url: "https://www.rfc-editor.org/info/rfc7323", kind: "IETF internet standard"}
  - {title: "RFC 4632 — Classless Inter-Domain Routing", url: "https://www.rfc-editor.org/info/rfc4632", kind: "IETF best current practice"}
---
TCP transporta um **fluxo ordenado de bytes**, e não uma lista de mensagens. A aplicação muitas vezes envia um JSON, objeto serializado ou comando completo e presume que uma chamada `send` corresponde a uma chamada `recv`. Essa correspondência não existe: o receptor pode observar metade do cabeçalho, várias mensagens numa leitura ou uma divisão em qualquer posição. Números de sequência TCP identificam **octetos**, e ACKs cumulativos confirmam um prefixo contínuo de bytes [1].

Os capítulos anteriores de [roteamento IP e DNS](/pt/topics/ip-routing-dns-resolution/) e de [protocolos de rede](/pt/topics/network-protocols/) estabelecem endereço, transporte e aplicação. Aqui aprofundaremos **enquadramento de mensagens**, **chegadas fora de ordem**, **ACK cumulativo** e limites de envio impostos pelo receptor e pelo congestionamento. Os exemplos são **modelos didáticos determinísticos**, não sockets reais nem implementações completas da RFC 9293.

## Fluxo de bytes não preserva limites de mensagens

Imagine o emissor fazendo `send(b"AB")`, `send(b"")` e `send(b"C")`. O peer TCP pode observar os três bytes reais `ABC` em grupos diferentes de chamadas de leitura; uma escrita vazia na aplicação **não cria mensagem vazia visível no fluxo TCP**. Para diferenciar uma mensagem vazia da ausência de mensagem, o protocolo de aplicação precisa codificar explicitamente esse evento [1].

Um **frame com prefixo de tamanho** resolve o problema. Nossa escolha é simples: **dois bytes sem sinal em big-endian**, seguidos por exatamente aquela quantidade de bytes de payload. A mensagem `b"AB"` vira `00 02 41 42` em hexadecimal; um frame vazio vira `00 00`. O maior payload representável contém 65.535 bytes. Isso é limite **do formato da aplicação**, e não tamanho máximo de segmento TCP.

O parser incremental deve aceitar separação do cabeçalho, separação do corpo, vários frames juntos e frames vazios. Também precisa **rejeitar cabeçalhos que anunciem mensagens maiores que o limite autorizado**, antes de aceitar consumo ilimitado de memória. O limite configurável pode ser inferior ao máximo do protocolo de dois bytes. Definir o formato antes da implementação impede que o sistema dependa do agrupamento eventual das leituras do SO.

## Decodificador incremental e falhas sem mutação

O codificador exige payload do tipo Python `bytes`, rejeitando textos, arrays mutáveis e comprimento acima de 65.535. O decodificador só recebe chunks binários. Entrega frames completos e mantém o sufixo incompleto para a próxima chamada.

Um defeito comum é acrescentar dados inválidos ao buffer persistente **antes** de validar o comprimento declarado. Para evitar isso, a implementação trabalha com uma sequência candidata e modifica o buffer real **somente depois** de validar os cabeçalhos completos. Se o tamanho anunciado exceder o limite, retorna `ValueError` sem alterar o prefixo já armazenado. O modelo não tenta se recuperar automaticamente de bytes malformados: o chamador deve tratar o caso como falha de protocolo, não pular posições arbitrárias.

~~~python
def encode_frame(payload):
    if type(payload) is not bytes or len(payload) > 65535:
        raise ValueError("payload must be bytes of at most 65535 octets")
    return len(payload).to_bytes(2, "big") + payload

class FrameDecoder:
    def __init__(self, max_payload=4096):
        if type(max_payload) is not int or not 0 <= max_payload <= 65535:
            raise ValueError("invalid maximum payload")
        self.max_payload = max_payload
        self.buffer = bytearray()

    def feed(self, chunk):
        if type(chunk) is not bytes:
            raise ValueError("TCP chunks must be bytes")
        candidate = bytes(self.buffer) + chunk
        cursor = 0
        completed = []
        while len(candidate) - cursor >= 2:
            length = int.from_bytes(candidate[cursor:cursor + 2], "big")
            if length > self.max_payload:
                raise ValueError("declared frame exceeds configured limit")
            if len(candidate) - cursor < 2 + length:
                break
            completed.append(candidate[cursor + 2:cursor + 2 + length])
            cursor += 2 + length
        self.buffer = bytearray(candidate[cursor:])
        return tuple(completed)

wire = encode_frame(b"AB") + encode_frame(b"") + encode_frame(b"C")
decoder = FrameDecoder(max_payload=8)
assert decoder.feed(wire[:1]) == ()
assert decoder.feed(wire[1:4]) == (b"AB",)
assert decoder.feed(wire[4:]) == (b"", b"C")
assert decoder.buffer == bytearray()
try:
    decoder.feed(b"\x00\x09")  # over the configured 8-byte payload cap
except ValueError:
    pass
else:
    raise AssertionError("oversized frame must fail")
assert decoder.buffer == bytearray()  # rejected input is transactional
~~~

Na primeira chamada falta parte do cabeçalho. Na segunda, chegam os bytes necessários para completar `AB`. Na terceira, o decodificador entrega o frame vazio explícito e `C`. Esse histórico representa **leituras arbitrárias do fluxo**, não um traço de pacotes TCP. Outras divisões do mesmo conteúdo precisam produzir as mesmas mensagens.

**Invariante:** após cada feed bem-sucedido, todos os frames entregues vieram de um prefixo contínuo e sem sobreposições do fluxo; o buffer guarda exatamente o sufixo ainda não consumido. Ele possui menos de dois bytes de cabeçalho, ou um cabeçalho completo com payload ainda incompleto. Uma chamada inválida não altera mensagens entregues antes nem o buffer persistente.

Essa implementação por cópia do candidato pode ter **custo acumulado quadrático** se o chamador fornecer um byte por vez de um frame longo ainda incompleto. O trabalho de cada feed depende da quantidade armazenada e recebida. O limite máximo de frame limita a memória pendente, mas não elimina cópias repetidas. Em produção, convém usar cursor ou buffer circular, quotas por conexão e testes independentes de ciclo de vida de memória.

## Sequência por byte e ACK cumulativo

No TCP real, um número de sequência representa a posição do **primeiro byte** do segmento no espaço de 32 bits. Um ACK cumulativo de valor `X` significa que todos os bytes até antes de `X` foram recebidos em ordem no fluxo atual. Um segmento acima de uma lacuna pode ficar armazenado, mas o ACK cumulativo não avança através de um byte anterior ausente; reconhecimentos seletivos são mecanismo distinto [1][3].

Para simplificar, usaremos **offsets relativos inteiros a partir de zero**, ignorando SYN/FIN, wraparound, timestamps, retransmissão, SACK e estabelecimento de conexão. Não é a aritmética de números de sequência TCP de 32 bits. A representação didática permite verificar continuidade sem fazer comparações numéricas incorretas quando a sequência real ultrapassa seu limite circular.

Se `DEF` chega com offset 3 antes de `ABC` em 0, ainda falta o prefixo inicial, e o próximo byte esperado continua sendo zero. Após `ABC`, os seis bytes tornam-se contínuos; o ACK relativo passa a seis. Duplicar dados antigos não pode avançar novamente a confirmação cumulativa.

## Receptor de janela fixa com dados fora de ordem

O receptor mantém posições ainda não entregues em `pending`, aceitando byte novo apenas se sua posição estiver em `[next_seq, next_seq + window)`. É uma **janela constante didática**, que pressupõe consumo imediato dos bytes entregues pela aplicação. No TCP real, a janela anunciada depende do espaço disponível no buffer e pode aumentar ou diminuir separadamente do enquadramento de mensagens [1].

Quando segmentos sobrepostos discordam do valor de um byte, este modelo mantém **o primeiro byte aceito**. É regra determinística do exemplo, **não garantia universal de tratamento de sobreposição no TCP**. A entrada já é sequência Python íntegra de bytes; checksum, sobreposições maliciosas, tempo de retransmissão e segurança ficam fora do escopo.

~~~python
class ToyReceiver:
    def __init__(self, window=8):
        if type(window) is not int or window <= 0:
            raise ValueError("positive integer window required")
        self.window = window
        self.next_seq = 0
        self.pending = {}  # relative byte offset -> byte value
        self.delivered = bytearray()

    def accept(self, seq, payload):
        if type(seq) is not int or seq < 0 or type(payload) is not bytes:
            raise ValueError("nonnegative relative sequence and byte payload required")
        for offset, value in enumerate(payload):
            position = seq + offset
            if self.next_seq <= position < self.next_seq + self.window:
                self.pending.setdefault(position, value)  # first arrival wins
        newly = bytearray()
        while self.next_seq in self.pending:
            newly.append(self.pending.pop(self.next_seq))
            self.next_seq += 1
        self.delivered.extend(newly)
        return self.next_seq, bytes(newly)

receiver = ToyReceiver(window=8)
assert receiver.accept(3, b"DEF") == (0, b"")
assert receiver.accept(0, b"ABC") == (6, b"ABCDEF")
assert receiver.accept(2, b"CDE") == (6, b"")  # duplicate retransmission
assert receiver.accept(8, b"I") == (6, b"")
assert receiver.accept(6, b"GH") == (9, b"GHI")
assert bytes(receiver.delivered) == b"ABCDEFGHI"
assert receiver.pending == {}

def send_allowance(cwnd, rwnd, in_flight):
    if any(type(v) is not int or v < 0 for v in (cwnd, rwnd, in_flight)):
        raise ValueError("windows and in-flight data must be nonnegative integers")
    return max(0, min(cwnd, rwnd) - in_flight)

assert send_allowance(12, 8, 5) == 3
assert send_allowance(8, 12, 5) == 3
assert send_allowance(12, 8, 9) == 0  # windows can shrink
~~~

A segunda chegada transforma `ABCDEF` em sequência contínua. Duplicata na posição dois não entrega nada. O byte em posição oito fica pendente até que `GH` preencha a lacuna; então `GHI` pode ser entregue. O método devolve `(próximo_offset_esperado, bytes_novos_entregues)`. Ele **não envia pacotes ACK reais** nem controla um socket.

**Invariante:** cada posição menor que `next_seq` foi entregue exatamente uma vez; posições pendentes nunca são inferiores a `next_seq`; e `next_seq` não diminui. O armazenamento de bytes fora de ordem usa no máximo `window` posições, com operação média constante por chave de dicionário. O processamento de cada chegada é proporcional ao tamanho recebido somado aos bytes liberados. O modelo também conserva **todo** o fluxo entregue para inspeção, de modo que sua memória total **não** é limitada pela janela; uma aplicação real pode consumir e descartar o conteúdo.

## Controle de fluxo e controle de congestionamento são diferentes

Dois limites independentes restringem o volume pendente de envio. A **janela do receptor (`rwnd`)** comunica capacidade de receber; a **janela de congestionamento (`cwnd`)** limita dados em trânsito segundo medições e algoritmos que buscam preservar a rede. Num instante estável simplificado, o volume adicional pode ser limitado por `max(0, min(cwnd, rwnd) - in_flight)` [2]. Prevalece a menor janela.

Com `cwnd=12`, `rwnd=8` e cinco unidades em trânsito, restam três para novo envio. Se a janela anunciada diminui abaixo dos nove bytes já enviados, a permissão para **novos** bytes é zero, sem cancelar fisicamente os dados em trânsito. O helper valida apenas inteiros não negativos; ele não representa um algoritmo real de congestionamento.

O TCP ainda requer estado de retransmissão, atualização de janelas, aritmética circular, persist timer, zero-window probes, delayed ACKs, slow start, congestion avoidance, fast recovery e eventuais extensões. A RFC 5681 estabelece princípios de congestionamento; a RFC 7323 define window scaling e timestamps. Nenhum desses mecanismos se resume à subtração de três inteiros [2][3].

## Perda, retransmissão e bloqueio por ordem

Se faltam bytes anteriores, outros podem chegar, mas a aplicação TCP recebe **fluxo ordenado** e normalmente não consome o que chegou depois enquanto a lacuna persiste. Esse **head-of-line blocking** na camada de transporte afeta latência mesmo que o protocolo de aplicação possua vários frames. O exemplo representa essa propriedade de ordem, mas não detecta perda nem calcula timer de retransmissão.

TCP retransmite dados conforme o protocolo; a aplicação ainda precisa resolver dúvidas sobre seus **efeitos de negócio**. Um ACK de transporte não significa commit de uma transação. Um timeout depois do envio de um comando também não comprova que o servidor deixou de executá-lo. Retries de operações não idempotentes exigem identidade de operação e disciplina transacional fora da camada TCP [1].

O transporte TCP é bidirecional: cada direção possui sequência e estado de fluxo próprios. Aqui demonstramos apenas um receptor de uma direção. Fechamento parcial, `TIME_WAIT`, RST, estabelecimento de conexão, autenticação e API de sockets não estão implementados.

## Implicações de arquitetura para serviços reais

Um serviço que recebe dados de clientes desconhecidos deve limitar **o tamanho do frame e o número de conexões/buffers mantidos**. O cabeçalho de dois bytes limita cada frame a 65.535, mas milhares de conexões guardando quase esse limite podem consumir memória elevada. É necessário definir quotas, timeouts de leitura, cancelamento e backpressure. Um parser com limite por frame isolado não é automaticamente resistente a exaustão de recursos.

Uma janela `rwnd` grande não corrige congestionamento do caminho; uma `cwnd` grande não obriga um receptor saturado a aceitar dados. Produto banda-latência ajuda a entender por que caminhos rápidos com RTT elevado podem precisar de janelas maiores e por que existe window scaling. Previsões reais de throughput dependem também de perda, algoritmo, peer e medições [2][3]. Selecionar próximo salto por CIDR, descrito no [capítulo de roteamento](/pt/topics/ip-routing-dns-resolution/), não implementa retransmissão nem enquadramento [4].

## Exercícios e verificação

1. Codifique `b"A"`, `b""` e `b"BC"` com dois bytes de tamanho em big-endian. Divida o fluxo em **cada posição possível** e verifique que os frames reconstruídos são os mesmos.
2. Prove por que `send(b"")` não serve como delimitador TCP, enquanto o frame explícito `00 00` representa mensagem vazia.
3. Modifique `FrameDecoder` para rejeitar um frame acima do limite sem apagar prefixo parcial válido anterior. Especifique o estado que deve permanecer inalterado.
4. Acompanhe segmentos em offsets 3, 0, 8 e 6. Desenhe os bytes pendentes e o ACK cumulativo depois de cada evento.
5. Forneça segmento parcialmente fora da janela didática e indique que bytes são aceitos. Explique por que a janela anunciada real tem regras adicionais.
6. Calcule a permissão de novo envio para `(cwnd, rwnd, in_flight)=(12,8,5)`, `(8,12,5)` e `(12,8,9)`, distinguindo dados já enviados de envio futuro.
7. Explique slow start e recuperação de perda **sem** presumir que o helper aritmético implementa esses mecanismos. Liste estado que um emissor real precisaria manter.
8. Separe propriedades de transporte TCP, de enquadramento da aplicação e de confirmação durável que requer protocolo transacional além do ACK.

**Continuação:** [temporizadores de retransmissão TCP e janelas de congestionamento](/pt/topics/tcp-rto-retransmission-congestion/) deriva estimativa RTO e simulação simplificada por rodadas; [protocolos de rede](/pt/topics/network-protocols/) apresenta TLS/HTTP e diagnóstico de conexões; [APIs confiáveis](/pt/topics/api-reliability/) trata retries e efeitos duráveis. Implementação TCP do kernel, estado QUIC, captura real de pacotes e simulações de congestionamento exigem capítulos específicos [1][2][3][4].
