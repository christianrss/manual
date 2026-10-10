---
id: tcp-rto-retransmission-congestion
title: "Temporizadores TCP: estimativa de RTT, retransmissão e janelas de congestionamento"
description: "Derive SRTT, RTTVAR, RTO e backoff da RFC 6298; diferencie uma simulação por rodadas de cwnd/ssthresh do TCP real."
category: networking
difficulty: advanced
updated: 2026-10-10
prerequisites: [tcp-byte-stream-framing-flow-control]
sources:
  - {title: "RFC 6298 — Computing TCP's Retransmission Timer", url: "https://www.rfc-editor.org/info/rfc6298", kind: "IETF standards-track RFC"}
  - {title: "RFC 5681 — TCP Congestion Control", url: "https://www.rfc-editor.org/info/rfc5681", kind: "IETF standards-track RFC"}
  - {title: "RFC 9293 — Transmission Control Protocol", url: "https://www.rfc-editor.org/info/rfc9293", kind: "IETF Internet Standard"}
  - {title: "RFC 8985 — RACK-TLP Loss Detection for TCP", url: "https://www.rfc-editor.org/info/rfc8985", kind: "IETF standards-track RFC"}
---
Um emissor TCP não pode interpretar um ACK ausente como prova imediata de perda. Redes apresentam atrasos variáveis, filas e segmentos fora de ordem. Por isso, o transporte precisa de **temporizador de retransmissão (RTO)** estimado a partir de RTTs observados, enquanto mecanismos separados de congestionamento determinam quanto tráfego pode ser introduzido na rede [1][2].

O capítulo de [fluxo TCP](/pt/topics/tcp-byte-stream-framing-flow-control/) apresentou posições de bytes, ACK cumulativo, `rwnd`, `cwnd` e enquadramento de mensagens. Agora construiremos (1) estimador compacto da aritmética principal da **RFC 6298**, e (2) modelo **simplificado de janela por rodadas de RTT**. O primeiro demonstra estimativa e backoff; o segundo, crescimento de janela e reação à perda. Nenhum é uma implementação completa da pilha TCP, do RFC 5681 ou do Linux [1][2][3].

## Estado de temporizador e estado de congestionamento

O **RTT suavizado (SRTT)** estima o tempo de ida e volta observado. A **variação do RTT (RTTVAR)** registra mudanças desse tempo; combiná-los evita usar simplesmente a última medição como prazo para retransmitir. O **RTO** é o período de espera antes de reagir à falta de confirmação. Um timer excessivamente curto causa retransmissões espúrias; um prazo excessivamente longo prejudica latência de cauda diante de perda real [1].

Congestionamento mantém variáveis diferentes. **cwnd** limita tráfego em voo permitido pelo estado do caminho; **rwnd** anuncia capacidade do receptor; **ssthresh** separa crescimento rápido de slow start e crescimento conservador. **FlightSize** representa dados já enviados e ainda não confirmados cumulativamente. RTT não é tamanho de janela, e vencimento de RTO não equivale a ACK que confirma novos bytes [2].

Neste capítulo o temporizador usa **segundos**, enquanto o modelo de congestionamento usa **unidades inteiras de segmento MSS**. Essa diferença de unidades é intencional; não podemos operar diretamente com os inteiros da simulação como se fossem contagens reais de bytes TCP.

## Estimativa da RFC 6298 e ordem das operações

Antes de RTT utilizável, a RFC 6298 recomenda um RTO inicial de um segundo, admitindo casos com valores maiores. Após a **primeira** medição elegível `R`, define-se `SRTT=R` e `RTTVAR=R/2`. Calcula-se `RTO=SRTT+max(G,4×RTTVAR)`, com `G` sendo a granularidade do relógio. A RFC recomenda mínimo de um segundo para o temporizador calculado e permite teto de pelo menos 60 segundos [1].

Para observação posterior `R'`, é obrigatório atualizar **primeiro a variação, usando o SRTT ANTIGO**:

`RTTVAR <- 0,75×RTTVAR + 0,25×|SRTT_antigo − R'|`.

Depois, `SRTT <- 0,875×SRTT_antigo + 0,125×R'`. Finalmente, recalcula-se RTO. Trocar a ordem altera o resultado; não é detalhe cosmético de código [1]. O exemplo estabelece `G=0,01` segundo, piso de 1 segundo e **teto de 60 segundos escolhido para este modelo**; sistemas reais podem usar outros relógios e limites permitidos.

## Regra de Karn e backoff por retransmissão

Se um segmento foi retransmitido e posteriormente confirmado, o ACK isolado não indica se a cópia original ou a retransmissão provocou a confirmação. Usar essa demora ambígua como medição de RTT distorce o estimador. A **regra de Karn** exclui essas observações do cálculo convencional; extensões de timestamp podem permitir tratamento mais elaborado nas implementações reais [1].

Ao vencer RTO, o prazo pode sofrer **backoff exponencial**, normalmente dobrando. Nosso código aplica `min(60,2×RTO)`, preservando o teto da simulação. Ele não agenda timers reais, retransmite pacotes, rastreia intervalos confirmados nem detecta perda efetiva. O argumento `retransmitted=True` só representa medição descartada por ambiguidade, não um processador real de ACKs.

~~~python
import math

class RtoEstimator:
    """Illustrative RFC 6298 estimator; seconds, G=10 ms, max RTO=60 s."""
    def __init__(self, granularity=0.01):
        if (type(granularity) not in (int, float)
                or not math.isfinite(granularity) or granularity <= 0):
            raise ValueError("positive finite clock granularity required")
        self.g = float(granularity)
        self.srtt = None
        self.rttvar = None
        self.rto = 1.0

    def observe(self, rtt, retransmitted=False):
        if (type(rtt) not in (int, float)
                or not math.isfinite(rtt) or rtt <= 0
                or type(retransmitted) is not bool):
            raise ValueError("positive finite RTT and boolean flag required")
        if retransmitted:
            return self.rto  # Karn: ambiguous ACK is not an RTT sample
        rtt = float(rtt)
        if self.srtt is None:
            self.srtt = rtt
            self.rttvar = rtt / 2
        else:
            old_srtt = self.srtt
            self.rttvar = 0.75 * self.rttvar + 0.25 * abs(old_srtt - rtt)
            self.srtt = 0.875 * old_srtt + 0.125 * rtt
        self.rto = min(60.0, max(1.0, self.srtt + max(self.g, 4 * self.rttvar)))
        return self.rto

    def timeout(self):
        self.rto = min(60.0, self.rto * 2)
        return self.rto

clock = RtoEstimator()
assert clock.rto == 1.0
assert abs(clock.observe(0.4) - 1.2) < 1e-12
assert abs(clock.observe(0.6) - 1.225) < 1e-12
assert abs(clock.timeout() - 2.45) < 1e-12
before = (clock.srtt, clock.rttvar, clock.rto)
assert clock.observe(0.9, retransmitted=True) == before[2]
assert (clock.srtt, clock.rttvar, clock.rto) == before
assert abs(clock.observe(0.5) - 1.109375) < 1e-12
~~~

O primeiro RTT de 400 ms produz SRTT=0,4, variação=0,2 e RTO=1,2 segundo. A observação de 600 ms produz SRTT=0,425, variação=0,2 e RTO=1,225. Um vencimento dobra o RTO para 2,45. Uma medição ambígua de 900 ms **não modifica** o estado. O próximo RTT elegível de 500 ms atualiza as estimativas válidas, sem perpetuar a duração expandida pelo vencimento anterior.

**Invariante:** antes da primeira amostra válida, SRTT e RTTVAR não existem; depois são finitos e não negativos. O RTO permanece no intervalo `[1,60]` segundos. Entradas rejeitadas e medições ambíguas não modificam estado. Cada medição aceita é RTT positivo e finito; timeout muda RTO sem recalcular SRTT ou RTTVAR.

Cada evento executa quantidade constante de aritmética e guarda `O(1)` valores. Isso não comprova temporização precisa do relógio do SO. Números `float` são aproximados e, por isso, a suíte compara resultados com tolerância, não por igualdade textual de decimais.

## Um ACK não corresponde necessariamente a um pacote ou RTT

Podem existir ACKs atrasados, ACKs cumulativos para múltiplos segmentos, duplicatas, SACKs e confirmações após retransmissão. Esses eventos não autorizam as mesmas atualizações. Amostra de RTT exige relacionar **envio mensurável e confirmação correspondente**; caso contrário, ocorre a ambiguidade estudada por Karn [1].

O estimador recebe amostras que o chamador já classificou como elegíveis. Ele não identifica ACK duplicado, não agenda fast retransmit nem detecta entrega fora de ordem com SACK; tampouco sabe quando iniciar ou cancelar timers de transmissões individuais. Isso exigiria estado de intervalos de bytes ainda pendentes e lógica de transporte ausentes [3][4].

## Slow start, congestion avoidance e perda

Durante slow start, `cwnd` pode crescer rapidamente conforme novos bytes são confirmados. Quando alcança o limiar, congestion avoidance cresce de maneira mais lenta. A RFC 5681 define mecanismos **por ACK elegível**, em bytes, com regras de contagem apropriada, ACKs atrasados e recuperação. Diante de timeout, `ssthresh` se relaciona com **FlightSize**, e não simplesmente com o valor anterior de `cwnd`; a janela de congestionamento é reduzida para a janela de perda [2].

Para estudo manual, definiremos **uma rodada de RTT bem-sucedida** como evento agregado que confirma uma janela inteira anterior. Se `cwnd<ssthresh`, o modelo dobra a janela até atingir o limiar; após isso soma uma unidade MSS. Quando o chamador sinaliza timeout, define `ssthresh=max(2,piso(FlightSize/2))` e reinicia `cwnd=1`. É uma **aproximação por rodadas**, não implementação ACK a ACK da RFC 5681. Ela não reproduz crescimento parcial nem fast recovery.

## Modelo executável de evolução das janelas

~~~python
class RoundCongestionSketch:
    """One RTT-level aggregate per success event; NOT packet-level TCP Reno."""
    def __init__(self, ssthresh=8):
        if type(ssthresh) is not int or ssthresh < 2:
            raise ValueError("threshold must be at least two segment units")
        self.cwnd = 1
        self.ssthresh = ssthresh

    def successful_round(self):
        if self.cwnd < self.ssthresh:
            self.cwnd = min(self.ssthresh, self.cwnd * 2)
        else:
            self.cwnd += 1
        return self.cwnd

    def timeout(self, flight):
        if type(flight) is not int or flight < 0:
            raise ValueError("nonnegative outstanding segment count required")
        self.ssthresh = max(flight // 2, 2)
        self.cwnd = 1
        return self.cwnd, self.ssthresh

    def available(self, rwnd, in_flight):
        if any(type(x) is not int or x < 0 for x in (rwnd, in_flight)):
            raise ValueError("nonnegative integer segment counts required")
        return max(0, min(self.cwnd, rwnd) - in_flight)

model = RoundCongestionSketch(8)
assert [model.successful_round() for _ in range(5)] == [2, 4, 8, 9, 10]
assert model.available(rwnd=6, in_flight=4) == 2
assert model.timeout(flight=9) == (1, 4)
assert [model.successful_round() for _ in range(4)] == [2, 4, 5, 6]
assert model.available(rwnd=3, in_flight=5) == 0
~~~

Com limiar inicial oito, cinco rodadas retornam janelas 2, 4, 8, 9 e 10. Se o receptor anuncia seis segmentos e quatro já estão em trânsito, só duas unidades adicionais podem ser enviadas. Vencimento com nove unidades pendentes estabelece limiar quatro e janela de congestionamento um; próximas rodadas crescem para 2, 4, 5 e 6.

A fórmula `max(0,min(cwnd,rwnd)-in_flight)` limita **novos envios** num instante do modelo. Quando a janela diminui abaixo do já enviado, o resultado é zero; isso não retira bytes da rede. O helper não conhece retransmissões nem calcula a remoção de dados em voo após ACK. O estado é fornecido explicitamente por quem faz a chamada.

**Invariante:** `cwnd>=1`, `ssthresh>=2` e ambos são unidades inteiras. Cada rodada de sucesso aumenta a janela; cada timeout abstrato a reduz a um. O modelo não tem limite de janela ligado a capacidades do caminho. Os testes verificam transições, mas não justiça, largura de banda ou latência real.

## RTO não equivale a fast retransmit

Vencimento de RTO significa ausência de confirmação dentro da política temporal. Já fast retransmit, ACK seletivo e mecanismos posteriores como RACK-TLP usam informações distintas para inferir perda sem esperar todo o RTO [2][4]. O segundo modelo possui somente evento explícito de **timeout** e exclui recuperação por ACKs duplicados.

Perdas podem surgir por congestionamento, ruído, falhas de rádio ou outras causas. Algoritmos clássicos de TCP muitas vezes as tratam como sinais de congestionamento sob hipóteses específicas. Nossos modelos não determinam a causa. Uma simulação sem dinâmica de fila e ACKs reais não comprova comportamento em enlaces congestionados, nem deve ser apresentada como política de congestionamento do kernel atual.

Há quatro contratos separados: **temporização** indica quando desconfiar da ausência de ACK; **recuperação** escolhe quais bytes retransmitir; **congestionamento** controla entrada de tráfego na rede; **controle de fluxo do receptor** evita consumir capacidade além do buffer anunciado. Misturar essas funções conduz a diagnósticos errados de latência e throughput.

## Implicações de arquitetura e deadlines

RTO excessivo pode deixar conexão ociosa após perda real; RTO pequeno demais provoca retransmissões desnecessárias e reação de congestionamento. RTT altamente variável torna frágil uma regra de “retransmitir sempre depois de 100 ms”. O comportamento real depende de amostras válidas, deadlines da aplicação, estabelecimento de conexão, ACKs, backoff e outros mecanismos [1].

O deadline de uma requisição de aplicação **não é o RTO TCP**. A requisição pode expirar enquanto o transporte continua, e um ACK de bytes não confirma que uma transação foi efetivada. Em APIs distribuídas, operações não idempotentes precisam de IDs e status durável de execução, além de política explícita de timeout e retry.

Para desempenho, `cwnd/RTT` fornece apenas intuição de limite sob condições estáveis. `rwnd`, ACKs reais, filas, perdas, outros fluxos e tamanho de segmentos alteram o resultado. O modelo por rodadas não possui informações para prever goodput, latência ou throughput de produção.

## Exercícios e verificação

1. Derive SRTT, RTTVAR e RTO a partir de 0,4 e 0,6 segundo, respeitando a ordem de atualização.
2. Recalcule RTTVAR usando equivocadamente SRTT novo. Mostre por que o resultado diverge.
3. Aplique três timeouts consecutivos e diferencie RTO expandido de estimativas suavizadas inalteradas.
4. Explique por que confirmação depois de retransmissão é ambígua e como timestamps poderiam ajudar.
5. Trace cinco rodadas de sucesso partindo de `cwnd=1` e `ssthresh=8`; depois simule timeout com FlightSize nove.
6. Explique por que `rwnd=3` impede novos envios adicionais mesmo quando `cwnd=6` e dados pendentes já excedem três.
7. Compare crescimento real por ACK da RFC 5681 com a aproximação por RTT, especialmente com ACKs atrasados e parciais.
8. Projete estado de intervalos pendentes para distinguir envio inicial, retransmissão, ACK cumulativo, ACK duplicado e timer expirado.
9. Descreva caso em que o deadline da aplicação vence antes do RTO TCP e como evitar duplicação de efeitos no retry.

**Continuação:** o capítulo de [frames e ACK cumulativo](/pt/topics/tcp-byte-stream-framing-flow-control/) estabelece limites e reordenação do receptor; [protocolos de rede](/pt/topics/network-protocols/) contextualiza TLS/HTTP. Traços reais, congestionamento completo, wrap de sequência e segurança exigem projetos separados [1][2][3][4].
