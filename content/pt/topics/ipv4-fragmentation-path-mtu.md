---
id: ipv4-fragmentation-path-mtu
title: "Tamanho de pacotes IP: fragmentação IPv4 e descoberta da MTU do caminho"
description: "Deduza offsets IPv4 de oito bytes, flags MF/DF, remontagem e descoberta clássica de MTU com modelos finitos verificáveis."
category: networking
difficulty: intermediate
updated: 2026-10-11
prerequisites: [ip-routing-dns-resolution]
sources:
  - {title: "RFC 791 — Internet Protocol", url: "https://www.rfc-editor.org/info/rfc791", kind: "IETF protocol specification"}
  - {title: "RFC 1191 — Path MTU Discovery", url: "https://www.rfc-editor.org/info/rfc1191", kind: "IETF standards-track specification"}
  - {title: "RFC 8200 — IPv6 Specification", url: "https://www.rfc-editor.org/info/rfc8200", kind: "IETF internet standard"}
  - {title: "RFC 8201 — IPv6 Path MTU Discovery", url: "https://www.rfc-editor.org/info/rfc8201", kind: "IETF internet standard"}
  - {title: "RFC 8899 — Datagram Packetization Layer Path MTU Discovery", url: "https://www.rfc-editor.org/info/rfc8899", kind: "IETF standards-track specification"}
---
Uma rota determina o *próximo salto*, mas não garante que um pacote IP atravesse todos os enlaces **com seu tamanho original**. Cada enlace possui uma unidade máxima de transmissão (MTU) na camada apropriada. A **MTU do caminho (PMTU)** é a menor MTU utilizável no percurso; túneis e encapsulamento ainda podem reduzir o espaço para dados do pacote original [1][2].

O capítulo de [roteamento IP e DNS](/pt/topics/ip-routing-dns-resolution/) explica escolha de endereços e encaminhamento. Aqui deduzimos o **offset de fragmentos IPv4**, os flags More Fragments (MF) e Don't Fragment (DF), a correção da remontagem e a descoberta da PMTU por feedback. **Não** simulamos segmentação TCP, roteadores reais, checksums ICMP, opções IPv4, fragmentação de fragmentos existentes, extensões IPv6 ou autenticação da rede.

## MTU, comprimento do datagrama e diferença para transporte

Um pacote IPv4 com **cabeçalho fixo de 20 bytes**, sem opções, possui comprimento `20 + tamanho_do_payload`. O campo Total Length tem 16 bits; portanto o modelo rejeita payloads com mais de **65.515 bytes**. A MTU limita o pacote IP inteiro, **não apenas os dados da aplicação TCP**. MSS do TCP e cabeçalhos de transporte introduzem restrições adicionais; pacotes DNS, datagramas UDP e segmentos TCP não devem ser confundidos [1].

Considere caminho com enlaces de MTU 1500, 1200 e 900. Um pacote de 1500 bytes cabe no primeiro enlace, mas pode ser grande demais para o segundo. Uma rota válida não prova que o pacote atravesse todo o caminho sem adaptação. O emissor pode reduzir envios futuros ou, em IPv4 sem DF, um roteador pode fragmentar determinados pacotes [1][2].

## Offset em unidades de oito bytes e flags MF/DF

O **Fragment Offset** IPv4 indica a posição inicial dos dados do fragmento em **unidades de oito octetos**, relativas ao payload original. **MF** indica a existência de mais fragmentos; apenas o último possui MF=0. **DF** proíbe fragmentação. Um roteador que recebe pacote acima da MTU com DF não pode dividi-lo: descarta o pacote e pode emitir a mensagem ICMP aplicável de fragmentação necessária [1][2].

Cada fragmento vira pacote com seu próprio cabeçalho IPv4. Em modelo com cabeçalho fixo de 20 bytes e MTU de **68 bytes**, sobram **48 bytes de payload** por pacote. Para payload de 100 bytes, temos fatias 48, 48 e 4, com offsets **0, 6 e 12** em unidades de oito bytes. Todo fragmento não final precisa conter número de bytes divisível por oito; o último pode ter comprimento menor [1].

| Intervalo original | Offset | Bytes de payload | MF | Tamanho IP |
| --- | ---: | ---: | --- | ---: |
| 0–47 | 0 | 48 | 1 | 68 |
| 48–95 | 6 | 48 | 1 | 68 |
| 96–99 | 12 | 4 | 0 | 24 |

Na rede real, identificação de datagrama, origem, destino e protocolo também entram na associação correta de fragmentos [1]. Nosso registro `Fragment` representa **um datagrama já identificado**. Não existe tabela de remontagem entre vários fluxos; fragmentos podem chegar atrasados, duplicados, fora de ordem ou jamais chegar.

## Implementação de fragmentação e remontagem estrita

O código modela **um datagrama IPv4 novo, sem opções**. Valida dados e MTU antes de construir fatias, alinha todo fragmento não final e rejeita requisição excessiva com DF. O exemplo exige MTU de **pelo menos 68**, mínimo de encaminhamento de roteadores IPv4 definido no RFC 791. Esse é um **limite adotado pelo modelo**, não uma descrição exaustiva dos enlaces de produção [1].

A remontagem precisa encontrar **exatamente um fragmento final**, nenhum intervalo faltante e nenhuma sobreposição. Uma tabela de posições verifica que cada byte tenha proprietário único, em vez de confiar apenas no maior offset. Duplicatas também são rejeitadas. É uma política **didática estrita**: não implementa timeouts, quotas, checksums, IDs ou regras completas de remontagem do Linux. Os registros podem ser apresentados fora de ordem, mas precisam cobrir um intervalo contíguo.

~~~python
from dataclasses import dataclass

@dataclass(frozen=True)
class Fragment:
    offset_units: int
    more: bool
    payload: bytes

def fragment_ipv4(payload, mtu, df=False):
    if type(payload) is not bytes:
        raise ValueError("payload must be bytes")
    if (type(mtu) is not int or not 68 <= mtu <= 65535
            or type(df) is not bool or len(payload) > 65515):
        raise ValueError("invalid fixed-header IPv4 datagram")
    capacity = mtu - 20
    if len(payload) <= capacity:
        return (Fragment(0, False, payload),)
    if df:
        raise ValueError("DF prohibits fragmentation")
    aligned = (capacity // 8) * 8
    fragments = []
    start = 0
    while len(payload) - start > capacity:
        fragments.append(Fragment(start // 8, True,
                                  payload[start:start + aligned]))
        start += aligned
    fragments.append(Fragment(start // 8, False, payload[start:]))
    return tuple(fragments)

def reassemble_ipv4(fragments):
    parts = tuple(fragments)
    if not parts or any(not isinstance(p, Fragment) for p in parts):
        raise ValueError("expected fragment records")
    end = None
    occupied = {}
    for p in parts:
        if (type(p.offset_units) is not int
                or not 0 <= p.offset_units < 8192
                or type(p.more) is not bool
                or type(p.payload) is not bytes
                or (p.more and (not p.payload or len(p.payload) % 8))):
            raise ValueError("invalid fragment")
        start = 8 * p.offset_units
        stop = start + len(p.payload)
        if stop > 65515:
            raise ValueError("reassembled IPv4 length exceeded")
        if not p.more:
            if end is not None:
                raise ValueError("multiple final fragments")
            end = stop
        for i, octet in enumerate(p.payload, start):
            if i in occupied:
                raise ValueError("overlapping fragments")
            occupied[i] = octet
    if end is None or len(occupied) != end or any(i not in occupied for i in range(end)):
        raise ValueError("incomplete fragment set")
    return bytes(occupied[i] for i in range(end))

data = bytes(range(100))
parts = fragment_ipv4(data, mtu=68)
assert [(p.offset_units, p.more, len(p.payload)) for p in parts] == [
    (0, True, 48), (6, True, 48), (12, False, 4)]
assert reassemble_ipv4(parts[::-1]) == data
assert fragment_ipv4(b"", mtu=68) == (Fragment(0, False, b""),)
try:
    fragment_ipv4(data, mtu=68, df=True)
except ValueError:
    pass
else:
    raise AssertionError("oversized DF packet must be rejected")
~~~

**Invariantes:** `inicio=8×offset_units`; payload de fragmento MF=1 tem comprimento positivo múltiplo de oito; `cabeçalho+payload ≤ MTU` para os fragmentos produzidos; cada byte original aparece exatamente uma vez. Na remontagem, cada índice recebe um byte único e o fragmento MF=0 define o final. Se todos os índices de `[0,fim)` existem, a reconstrução crescente devolve exatamente o payload original.

Para payload de `n` bytes e `k` fragmentos, construir as fatias custa `O(n+k)` em cópias e registros. A remontagem guarda `n` entradas em dicionário e verifica continuidade; tempo esperado `O(n+k)` e memória `O(n)`, sob hipóteses usuais de hashing. São custos **do exemplo Python**, não estimativas de um kernel.

## PMTUD clássico: descoberta iterativa por feedback

A descoberta clássica da MTU do caminho no IPv4 envia pacotes com **DF=1** e ajusta o tamanho quando algum roteador não consegue encaminhar. O erro ICMPv4 correspondente é Destination Unreachable, **tipo 3, código 4**, e pode indicar a MTU do próximo salto [2]. No percurso 1500, 1200 e 900, uma tentativa de 1500 bytes encontra restrição no **segundo enlace**, informando 1200; o envio de 1200 alcança o **terceiro enlace**, que informa 900. O pacote de 900 consegue atravessar todos.

O simulador abaixo percorre os enlaces e retorna apenas o **primeiro** que não comporta a tentativa. Outra função atualiza o tamanho após cada relatório ideal até conseguir entregar. É mais fiel ao aprendizado iterativo que devolver diretamente `min(MTUs)` como se o emissor conhecesse de antemão todo o caminho.

~~~python
def probe_df_path(link_mtus, packet_size):
    hops = tuple(link_mtus)
    if (not hops or any(type(x) is not int or not 68 <= x <= 65535
                        for x in hops)
            or type(packet_size) is not int
            or not 20 <= packet_size <= 65535):
        raise ValueError("invalid path or IPv4 packet length")
    for position, hop_mtu in enumerate(hops):
        if packet_size > hop_mtu:
            return ("too-big", position, hop_mtu)
    return ("delivered", None, None)

def classical_pmtud_trace(link_mtus, initial_size):
    hops = tuple(link_mtus)
    current = initial_size
    trace = []
    while True:
        status, position, reported_mtu = probe_df_path(hops, current)
        trace.append((current, status, position, reported_mtu))
        if status == "delivered":
            return tuple(trace)
        current = reported_mtu  # ideal, authenticated, delivered ICMP feedback

assert classical_pmtud_trace((1500, 1200, 900), 1500) == (
    (1500, "too-big", 1, 1200),
    (1200, "too-big", 2, 900),
    (900, "delivered", None, None))
assert probe_df_path((1500, 1400), 1400) == ("delivered", None, None)
~~~

Assumimos feedback correto, entregue e confiável, rota estável, MTUs constantes e nova tentativa imediata. Sistemas reais devem verificar mensagens ICMP, considerar spoofing e bloqueios, timers, mudanças de rota e contratos da camada de transporte. ICMP de MTU não é sinônimo de sinal de congestionamento TCP. Reduzir tamanho pode permitir envio sem comprovar que o serviço de aplicação esteja saudável [2][5].

## IPv4 e IPv6: regras de fragmentação diferentes

**Roteadores IPv6 não fragmentam pacotes em trânsito.** Na presença de fragmentação IPv6, ela é feita pela origem usando cabeçalho de extensão específico; o cabeçalho básico IPv6 tem 40 bytes e semântica diferente da do IPv4. A descoberta de MTU IPv6 utiliza ICMPv6 **Packet Too Big** e a MTU mínima do enlace IPv6 é **1280 bytes** sob RFC 8200 [3][4]. Portanto não se pode reutilizar o código IPv4 trocando simplesmente 20 por 40.

Fragmentação envolve disponibilidade e segurança: conjuntos incompletos não podem ser entregues como payload original, fragmentos sobrepostos causam ambiguidade e firewalls podem inspecionar partes diferentes dos cabeçalhos. O IPv6 especifica descarte em casos de sobreposição; a rejeição estrita do Python ilustra o princípio, **sem implementar o protocolo completo** [3].

## Black holes de PMTU e testes pela camada de pacotização

PMTUD clássico pode falhar quando middleboxes ou firewalls descartam o ICMP necessário, causando **PMTU black hole**: handshake e pacotes pequenos funcionam, mas transmissões maiores ficam paradas. O sintoma pode ser confundido com timeout da aplicação ou congestionamento [4][5].

O **DPLPMTUD** do RFC 8899 utiliza sondagens na camada que escolhe os tamanhos dos pacotes, permitindo adaptar-se a sinais de sucesso/falha mesmo sem receber todos os erros ICMP. Requer validações, limites e tratamento dos testes, não apenas o laço simplificado de reduzir para a MTU reportada [5]. **Não implementamos DPLPMTUD.** Ausência de ICMP não demonstra entrega do pacote, e o exemplo não consegue medir PMTU de uma rede real.

## Verificação e limites de correção

Os testes associados usam **aritmética independente e bitmap de propriedade dos bytes**. Para diferentes tamanhos e MTUs, conferem offsets, flags MF e limites. A remontagem é conferida com coleções reordenadas e entradas com sobreposição, duplicação, fragmentos ausentes ou malformados. Um verificador separado percorre enlace por enlace para conferir a sequência ideal de descobertas da PMTU.

Dois limites são fundamentais: não existe identificação de fragmentos de múltiplos datagramas e não existe modelagem de tempo nem autenticidade ICMP. Os testes finitos demonstram somente os **contratos delimitados do software**, não conformidade completa IPv4/IPv6, segurança sob tráfego adversarial ou garantias de disponibilidade.

## Exercícios e verificação

1. Fragmente payload IPv4 de 150 bytes com cabeçalho de 20 e MTU 68. Calcule manualmente offset, MF e tamanho IP de cada fragmento.
2. Explique por que **fragmentos não finais** precisam de payload múltiplo de oito. O que acontece ao fragmentar em 45 bytes?
3. Reordene três fragmentos ao contrário, remonte e identifique verificações necessárias; depois remova o fragmento intermediário.
4. Compare cabeçalho IPv4 fixo de 20 bytes com opções: por que a implementação não pode ser generalizada sem mudar cálculos?
5. Derive o primeiro enlace que rejeita pacote DF de 1500 bytes no caminho 1500/1200/900; repita após cada resposta.
6. Diferencie black hole de PMTU, falha DNS, congestionamento TCP e timeout HTTP no servidor.
7. Compare fragmentação permitida no roteador IPv4 e fragmentação exclusivamente na origem do IPv6.
8. Desenhe experimento DPLPMTUD que teste tamanhos sem depender de qualquer mensagem ICMP, explicitando ambiguidades.

**Continuidade:** [DNS autoritativo](/pt/topics/dns-authoritative-negative-cname/) cobre nomes e caching; [TCP: enquadramento e fluxo](/pt/topics/tcp-byte-stream-framing-flow-control/) cobre fluxo ordenado, e [temporizadores TCP](/pt/topics/tcp-rto-retransmission-congestion/) aborda outra resposta a perdas [1][2][3][4][5].
