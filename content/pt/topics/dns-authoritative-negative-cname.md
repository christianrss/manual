---
id: dns-authoritative-negative-cname
title: "DNS autoritativo: cadeias CNAME e cache de respostas negativas"
description: "Estude autoridade DNS, delegações, CNAME, NXDOMAIN/NODATA e TTL negativo da SOA com modelos Python e testes independentes."
category: networking
difficulty: intermediate
updated: 2026-10-10
prerequisites: [ip-routing-dns-resolution]
sources:
  - {title: "RFC 1034 — Domain Names: Concepts and Facilities", url: "https://www.rfc-editor.org/info/rfc1034", kind: "IETF internet standard"}
  - {title: "RFC 1035 — Domain Names: Implementation and Specification", url: "https://www.rfc-editor.org/info/rfc1035", kind: "IETF internet standard"}
  - {title: "RFC 2308 — Negative Caching of DNS Queries", url: "https://www.rfc-editor.org/info/rfc2308", kind: "IETF internet standard"}
  - {title: "RFC 4035 — DNS Security Extensions", url: "https://www.rfc-editor.org/info/rfc4035", kind: "IETF internet standard"}
  - {title: "RFC 8767 — Serving Stale Data to Improve DNS Resiliency", url: "https://www.rfc-editor.org/info/rfc8767", kind: "IETF internet standard"}
---
No DNS, conjuntos de registros (RRsets) são mantidos por operadores **autoritativos de zonas**, enquanto resolvedores recursivos podem responder usando dados armazenados em cache. O capítulo de [roteamento IP e fundamentos de DNS](/pt/topics/ip-routing-dns-resolution/) apresenta encaminhamento por prefixo e cache positivo com TTL. Aqui acrescentamos dois contratos ausentes: **respostas negativas** e **cadeias de aliases CNAME**. Distinguimos ainda delegação, resolução iterativa e o que uma validação DNSSEC realmente acrescentaria [1][2][3].

Resolvedores de produção também precisam cuidar de retransmissão, timeouts, EDNS, truncamento, TCP, delegação e confiança. Nenhuma das duas implementações em Python deste capítulo é servidor DNS, parser de pacotes ou validador DNSSEC. Elas servem para deduzir regras de chave e validade, comparáveis com oráculos desenvolvidos independentemente.

## Zonas, delegação, resolução recursiva e glue

Uma **zona** é parte do espaço de nomes do DNS administrada por determinados servidores autoritativos. Não é sinônimo de domínio inteiro ou de uma única máquina. A zona pai pode delegar uma zona filha por registros NS no ponto de delegação (*zone cut*). Um resolvedor pode partir de referências de servidores raiz e seguir encaminhamentos para TLD e zona de destino; não espera que a raiz armazene todos os registros A dos hosts da internet [1].

O resolvedor **stub** normalmente consulta um serviço recursivo, que realiza consultas iterativas a autoridades ou responde com cache. **Recursão** é o serviço para o cliente; **iteração** corresponde a consultar as autoridades sucessivas. Autoridades guardam os dados de suas zonas e em geral não resolvem recursivamente toda a árvore para o cliente. Referências podem fornecer nomes de NS, e registros adicionais de endereço (*glue*) podem ser necessários para localizar um servidor delegado cujo nome está dentro da própria zona filha [1][2].

Por exemplo, `child.example.` pode ser delegado a `ns.child.example.`. Sem endereço disponível por outro percurso, seria necessário resolver o endereço do NS dentro da zona que ainda não conseguimos alcançar. O glue do pai quebra essa dependência. Entretanto, o resolvedor precisa observar restrições de bailiwick e validação: aceitar sem exame qualquer endereço adicional permite ataques de envenenamento de cache. Nosso código não implementa essas defesas.

## RRsets, CNAME e tipos de consulta

Cada pergunta DNS possui **QNAME**, **QTYPE** e **QCLASS**. Os exemplos fixam classe `IN` e limitam tipos a A, AAAA e TXT. Um nome pode possuir conjuntos A e AAAA distintos e múltiplos endereços. **CNAME** associa um nome a outro canônico e não pode coexistir, no mesmo owner, com registros ordinários de endereço, ressalvadas exceções de metadados DNSSEC que não modelamos [1][2].

Resolver `www.example.` por `CNAME app.example.` até `CNAME edge.example.` exige seguir aliases até o RRset final ou alguma falha. Um ciclo A→B→A não resolve nome nenhum. Quando o alvo está fora da zona local, o resolvedor precisa continuar consultando outras autoridades: isso **não prova NXDOMAIN**. Cada alias e registro final possui TTL próprio; a resposta positiva combinada não deve permanecer válida além do menor TTL necessário à cadeia.

O mapeamento Python é um conjunto de dados **local e completamente materializado**. Não executa consultas de rede, delegações, wildcard, prova de inexistência, assinaturas DNSSEC ou tipos de classe adicionais. Se um nome ou tipo não aparece, a função levanta exceção; não fabrica uma resposta negativa autoritativa.

## NXDOMAIN e NODATA possuem alcances diferentes

**NXDOMAIN** sinaliza ausência do nome consultado no contexto autoritativo correspondente. **NODATA** sinaliza nome existente, mas sem o tipo solicitado (NOERROR sem resposta daquele tipo e com evidência da SOA pertinente). Não se deve usar a mesma chave para ambos no cache negativo [3].

Com classe fixa `IN`, NXDOMAIN é associado ao **nome**, isto é, à chave `(QNAME,QCLASS)`, independente de QTYPE. Já NODATA depende do tipo, usando `(QNAME,QTYPE,QCLASS)`. Ausência de AAAA para nome existente não apaga seu endereço A. Por outro lado, NXDOMAIN para esse nome pode servir consultas de A, AAAA e TXT, sem produzir uma entrada negativa separada para cada tipo [3].

CNAME e delegações complicam respostas negativas: um pacote contendo CNAME pode informar que o **alvo** canônico não existe, em vez de comprovar inexistência do alias original. DNSSEC adiciona exigências de prova autenticada. O cache didático recebe uma classificação negativa já normalizada de uma fonte confiável; não interpreta cabeçalho DNS real nem decide se uma resposta remota é autêntica.

## Como deduzir o TTL negativo pela SOA

A RFC 2308 determina a vida útil de uma resposta negativa a partir da SOA que acompanha a resposta na seção de autoridade. O valor é limitado pelo **menor entre TTL apresentado da SOA e campo SOA MINIMUM**: `ttl_negativo = min(soa_ttl, soa_minimum)` [3].

Se a resposta entra em cache no instante `t`, expira em `t + ttl_negativo`. Uma consulta em `u` só pode usar a entrada se `u < expiração`; no instante exato da expiração, o TTL restante é zero. TTL zero não gera resposta negativa reutilizável. O exemplo usa inteiros não negativos como relógio explícito, **não tempo real**, evitando testes que dependem de `sleep`.

Quando TTL da SOA é 120 s e SOA MINIMUM é 30 s, o cache negativo dura **30 segundos**. Mantê-lo por 120 contrariaria o limite. Se o TTL do registro SOA for menor, ele prevalece. Políticas de resolvedor podem impor teto ainda inferior, mas nunca devem concluir que um nome será inexistente para sempre porque faltava em uma resposta anterior [3].

## Cache negativo executável com chaves explícitas

A função aceita somente nomes ASCII simplificados e classe `IN`. Normaliza maiúsculas/minúsculas e o ponto final facultativo, mas não implementa IDNA nem valida completamente nomes no formato de pacotes DNS. O owner é sempre nome absoluto minúsculo terminado em ponto. O cache recebe somente **eventos NXDOMAIN/NODATA confiáveis já classificados** junto com TTL da SOA.

~~~python
import re
from dataclasses import dataclass

NAME_PART = re.compile(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")

def dns_name(value):
    if not isinstance(value, str) or not value:
        raise ValueError("nonempty ASCII DNS name required")
    name = value.lower().removesuffix(".")
    parts = name.split(".")
    if (len(name) > 253 or any(not NAME_PART.fullmatch(part)
                                for part in parts)):
        raise ValueError("invalid teaching DNS name")
    return name + "."

def dns_type(value):
    if value not in ("A", "AAAA", "TXT"):
        raise ValueError("A/AAAA/TXT only in this model")
    return value

class NegativeDNSCache:
    def __init__(self):
        self.entries = {}

    def store(self, name, outcome, qtype, soa_ttl, soa_minimum, now):
        owner = dns_name(name)
        dns_type(qtype)
        if outcome not in ("NXDOMAIN", "NODATA"):
            raise ValueError("invalid negative outcome")
        if any(type(v) is not int or v < 0
               for v in (soa_ttl, soa_minimum, now)):
            raise ValueError("nonnegative integer TTL and clock required")
        ttl = min(soa_ttl, soa_minimum)
        key = (owner, None if outcome == "NXDOMAIN" else qtype)
        # A zero TTL means do not cache this answer.
        if ttl:
            # Avoid contradictory NXDOMAIN and NODATA entries in this
            # deliberately single-zone, single-class teaching cache.
            for previous in list(self.entries):
                if previous[0] == owner and (outcome == "NXDOMAIN"
                                             or previous[1] is None):
                    del self.entries[previous]
            self.entries[key] = (outcome, now + ttl)
        return ttl

    def lookup(self, name, qtype, now):
        owner = dns_name(name)
        dns_type(qtype)
        if type(now) is not int or now < 0:
            raise ValueError("nonnegative integer clock required")
        for key in ((owner, None), (owner, qtype)):
            entry = self.entries.get(key)
            if entry is None:
                continue
            outcome, expiry = entry
            remaining = expiry - now
            if remaining > 0:
                return (outcome, remaining)
            del self.entries[key]
        return None

cache = NegativeDNSCache()
assert cache.store("missing.example.", "NXDOMAIN", "A", 120, 30, 10) == 30
assert cache.lookup("MISSING.EXAMPLE", "AAAA", 39) == ("NXDOMAIN", 1)
assert cache.lookup("missing.example.", "A", 40) is None
assert cache.store("host.example", "NODATA", "AAAA", 60, 20, 50) == 20
assert cache.lookup("host.example", "A", 60) is None
assert cache.lookup("host.example", "AAAA", 60) == ("NODATA", 10)
assert cache.lookup("host.example", "AAAA", 70) is None
~~~

A resposta NXDOMAIN para `missing.example.` entra no instante 10 e dura até 40. No instante 39 ainda resta um segundo, inclusive para consultas AAAA; no 40 não há hit. Já `host.example.` recebe NODATA somente para AAAA: uma consulta A não é negativada. Na fronteira exata de expiração, a resposta negativa deixa de valer.

**Invariante:** cada entrada representa um NXDOMAIN baseado apenas no nome ou um NODATA baseado no nome e tipo, com expiração inteira. A consulta procura primeiro NXDOMAIN e depois NODATA, exige TTL estritamente positivo e remove entradas vencidas quando consultadas. Para manter coerência na simulação, substituir nome por NXDOMAIN apaga negativas específicas; inserir NODATA remove NXDOMAIN contraditório. Essa invalidação local é uma **simplificação**; não define a política de um resolvedor recursivo real diante de alterações em autoridades inconsistentes.

A verificação de entradas contraditórias em `store` percorre até `m` registros, custando `O(m)`; consulta verifica no máximo duas chaves do dicionário, com `O(1)` esperado. Não há limite de memória, política de evicção, classes adicionais, confiança DNSSEC, cache de ancestrais, TTL decrescente formatado em pacotes ou reaproveitamento excepcional de respostas vencidas. O modelo não detecta uma SOA falsificada.

## Cadeia CNAME executável, ciclos e limites

Um segundo modelo resolve um **mapa local completo** de registros. Cada owner possui CNAME ou RRsets A/AAAA, cada um com TTL não negativo. A validação rejeita nomes duplicados após normalização e CNAME misturado a endereços ordinários. A resolução limita saltos, detecta ciclos e devolve nome canônico, endereços e mínimo TTL dentre registros percorridos [1][2].

~~~python
@dataclass(frozen=True)
class AliasAnswer:
    name: str
    data: tuple
    ttl: int
    chain: tuple

def follow_cname(records, name, qtype="A", max_hops=8):
    if type(max_hops) is not int or max_hops < 0:
        raise ValueError("nonnegative integer hop limit required")
    dns_type(qtype)
    if qtype not in ("A", "AAAA"):
        raise ValueError("only address lookups are modeled")
    if not isinstance(records, dict):
        raise ValueError("records must be a mapping")

    validated = {}
    for owner, rrsets in records.items():
        key = dns_name(owner)
        if key in validated or not isinstance(rrsets, dict) or not rrsets:
            raise ValueError("invalid or duplicate normalized owner")
        if "CNAME" in rrsets and len(rrsets) != 1:
            raise ValueError("CNAME owner cannot have address RRsets")
        typed = {}
        for record_type, record in rrsets.items():
            if record_type not in ("CNAME", "A", "AAAA"):
                raise ValueError("unsupported record type")
            if (not isinstance(record, tuple) or len(record) != 2
                    or type(record[1]) is not int or record[1] < 0):
                raise ValueError("record must be (value, nonnegative TTL)")
            value, ttl = record
            if record_type == "CNAME":
                typed[record_type] = (dns_name(value), ttl)
            else:
                if (not isinstance(value, tuple) or not value
                        or any(not isinstance(v, str) or not v for v in value)):
                    raise ValueError("address RRset must be a nonempty tuple")
                typed[record_type] = (value, ttl)
        validated[key] = typed

    current = dns_name(name)
    visited = set()
    path = []
    budget = []
    while True:
        if current in visited:
            raise ValueError("CNAME cycle")
        visited.add(current)
        rrsets = validated.get(current)
        if rrsets is None:
            raise KeyError(current)  # no delegation/wildcards in this model
        if "CNAME" not in rrsets:
            if qtype not in rrsets:
                raise KeyError((current, qtype))  # no SOA proof modeled here
            addresses, ttl = rrsets[qtype]
            return AliasAnswer(current, addresses,
                               min([ttl] + budget), tuple(path))
        if len(path) >= max_hops:
            raise ValueError("CNAME hop limit exceeded")
        target, ttl = rrsets["CNAME"]
        path.append(current)
        budget.append(ttl)
        current = target

zone = {
    "www.example": {"CNAME": ("app.example", 50)},
    "app.example": {"CNAME": ("edge.example", 40)},
    "edge.example": {"A": (("192.0.2.10", "192.0.2.11"), 20)},
}
result = follow_cname(zone, "WWW.EXAMPLE.", max_hops=2)
assert result == AliasAnswer(
    "edge.example.", ("192.0.2.10", "192.0.2.11"), 20,
    ("www.example.", "app.example."))
assert follow_cname(zone, "edge.example").chain == ()
try:
    follow_cname(zone, "www.example", max_hops=1)
except ValueError:
    pass
else:
    raise AssertionError("hop limit must be enforced")
~~~

`www.example.` é alias e `edge.example.` é destino canônico. A cadeia possui TTLs 50, 40 e 20: o máximo de vida de uma resposta composta é **20 segundos**. Se o último RRset tivesse TTL 60, o alias TTL 40 continuaria limitando o conjunto. Ciclos causam erro em vez de loop infinito.

**Invariante:** a cada salto, `current` indica o próximo nome, `visited` mantém owners previamente analisados, e `budget` registra os TTLs dos aliases percorridos. Uma resolução termina em RRset final, ciclo ou limite de saltos. Com `r` registros e `h` aliases, validar o mapa custa `O(r)` para valores de tamanho limitado; seguir a cadeia custa `O(h)` esperado. Memória é `O(r+h)` incluindo cópia validada e caminho. Não são estimativas de latência de consultas remotas, que dependeriam de redes e delegações adicionais.

## DNSSEC autentica dados, não criptografa consultas

DNSSEC introduz RRsets assinados, DNSKEY, ligações de confiança DS e provas autenticadas de determinadas respostas negativas. Um validador precisa construir cadeia a partir de **âncora de confiança** aceita, verificar assinaturas e relações de chave/digest e, quando aplicável, prova de inexistência [4]. Apenas encontrar RRSIG na resposta não equivale a validação.

Delegação de zona filha pode ser **insegura** quando não há ligação de autenticação, conforme prova de ausência de DS. Isso difere de resposta **bogus** cuja validação exigida falha. Nenhum desses estados corresponde automaticamente a NXDOMAIN ou NODATA. DNSSEC autentica dados sob seu modelo de confiança, mas **não esconde** consultas de observadores nem garante que a aplicação hospedada no endereço retornado seja confiável. HTTPS ainda requer autenticação própria.

Este capítulo **não implementa DNSSEC**, assinatura, NSEC/NSEC3 ou wildcard autenticado. Adicionar um campo `signed=True` à resposta não provaria nada. Distinguir secure, insecure, bogus e indeterminate exige estudo próprio de criptografia e protocolo conforme RFC 4035, além de cache e alias [4].

## Falhas, serve-stale e observabilidade

Um resolvedor pode falhar porque uma autoridade não responde, há loop de delegação, a validação DNSSEC falha, transporte expira ou nome realmente não existe. **SERVFAIL não é NXDOMAIN.** Guardar SERVFAIL como inexistência permanente quebraria consultas legítimas. Para diagnosticar, examine QTYPE, autoridade, TTL, caminho de resolução e estado DNSSEC antes de afirmar que o host foi removido [1][3][4].

RFC 8767 define a possibilidade de **serve-stale**: sob condições explícitas, um resolvedor pode devolver dados anteriormente armazenados mas já vencidos, para aumentar disponibilidade. Isso exige política de timeout, limite e atualização; não significa que todo TTL vencido continua válido. Os modelos deste capítulo expiram estritamente em zero e **não implementam serve-stale** [5].

Caches DNS podem diminuir latência e carga das autoridades, mas sua correção depende de validade, origem, alcance da chave e confiança. Cache hit comprova apenas que um dado está dentro de seu período modelado; não prova roteabilidade, conexão TCP nem certificado HTTPS do destino. Esses contratos são explicados no [caminho da requisição](/pt/topics/network-protocols/).

## Exercícios e verificação

1. Construa chaves de cache para `host.example.` consultado como A, AAAA e TXT sob NXDOMAIN e NODATA. Explique por que ausência de AAAA não apaga A.
2. Para SOA TTL 75 e MINIMUM 20, calcule TTL restante em t=10, t=29 e t=30, com entrada no instante 10.
3. Explique por que NXDOMAIN para **alvo** de CNAME não comprova automaticamente inexistência do alias original.
4. Desenhe cadeia de delegação de uma zona cujo NS pertence à própria zona filha; justifique glue e seus limites de confiança.
5. Implemente oráculo independente de cache negativo por **lista de eventos**, sem reproduzir a estratégia de dicionários, e teste os limites de expiração.
6. Construa ciclo CNAME, cadeia superior ao limite e nome com A mas sem AAAA. Diferencie as exceções didáticas de respostas DNS reais.
7. Calcule TTL composto de aliases 30, 10 e 60 e RRset A final com TTL 45.
8. Diferencie negação autenticada DNSSEC, NXDOMAIN comum sem assinatura e timeout de autoridade. Qual situação requer prova criptográfica?
9. Proponha serve-stale separado, com período máximo e comportamento explícito para refresh que retorne resposta negativa. Não enfraqueça silenciosamente a regra de TTL.

**Continuação:** [DNS, TCP, TLS e HTTP](/pt/topics/network-protocols/) conecta respostas DNS ao transporte e autenticação de aplicações. Validação DNSSEC completa, formato de pacotes, aceitação de glue/bailiwick e consultas iterativas reais são tarefas de implementação independentes [1][2][3][4][5].
