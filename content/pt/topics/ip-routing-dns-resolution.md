---
id: ip-routing-dns-resolution
title: "Roteamento IP e DNS: seleção de prefixos, resolução e cache TTL"
description: "Derive seleção de rotas IPv4 por prefixo e cache de DNS com TTL, expiração e modelos Python avaliados por oráculos independentes."
category: networking
difficulty: intermediate
updated: 2026-10-10
prerequisites: [processes-virtual-memory, complexity-analysis]
sources:
  - {title: "RFC 1812 — Requirements for IPv4 Routers", url: "https://www.rfc-editor.org/info/rfc1812", kind: "IETF internet standard"}
  - {title: "RFC 1034 — DNS Concepts and Facilities", url: "https://www.rfc-editor.org/info/rfc1034", kind: "IETF internet standard"}
  - {title: "RFC 1035 — DNS Implementation and Specification", url: "https://www.rfc-editor.org/info/rfc1035", kind: "IETF internet standard"}
  - {title: "RFC 2308 — DNS Negative Caching", url: "https://www.rfc-editor.org/info/rfc2308", kind: "IETF internet standard"}
  - {title: "RFC 8767 — DNS Serve-Stale", url: "https://www.rfc-editor.org/info/rfc8767", kind: "IETF internet standard"}
  - {title: "RFC 8200 — IPv6 Specification", url: "https://www.rfc-editor.org/info/rfc8200", kind: "IETF internet standard"}
---
**Encaminhamento IP** e **resolução DNS** resolvem problemas diferentes. O IP escolhe para onde encaminhar um pacote com endereço de destino; o DNS ajuda aplicações a descobrir endereços e outros registros associados a nomes. Nenhum garante que a aplicação do destino aceite requisições nem que uma conexão TCP bem-sucedida signifique serviço saudável. O [panorama de protocolos](/pt/topics/network-protocols/) liga essas camadas a transporte, TLS e HTTP; aqui estabeleceremos contratos de seleção e de validade dos dados [1][2].

Construímos dois modelos Python de escopo restrito: um escolhe rota IPv4 estática pelo maior prefixo; outro mantém respostas positivas DNS A/AAAA até o instante de expiração. **Não são** código de roteador, resolvedor DNS de produção, captura de pacotes nem protocolo de segurança. Eles explicitam regras que podem ser confrontadas com oráculos independentes.

## Pacotes IP, sub-redes e tabela de encaminhamento

Um endereço IP identifica um destino usado pelo roteamento, não um serviço HTTP específico. O roteador examina o IP de destino e seleciona próximo salto segundo sua tabela. O hostname originalmente consultado pelo navegador normalmente **não entra** na seleção do encaminhamento [1].

No IPv4, `192.0.2.0/24` define 24 bits de prefixo e compreende endereços de `192.0.2.0` até `192.0.2.255`. A rota `192.0.2.128/25` é mais específica, limitando-se à metade superior. A rota `0.0.0.0/0` é o **padrão** quando nenhuma mais específica se aplica. As faixas `192.0.2.0/24`, `198.51.100.0/24` e `203.0.113.0/24` são reservadas à documentação; não são endereços recomendados para implantação [1].

**Longest-prefix match** seleciona o prefixo válido de maior comprimento que contém o destino. Para rotas de igual comprimento, sistemas reais consideram distâncias administrativas, métricas, protocolos, políticas e caminhos de custo igual, conforme configuração. A nossa convenção de desempate é apenas **menor métrica** e depois **ordem original da entrada**. Seria incorreto afirmar que isso representa todas as implementações IPv4.

## Encaminhar não equivale a descobrir o percurso inteiro

Uma rota escolhe o **próximo salto**, não necessariamente o host final. O gateway precisa estar acessível na rede local por mecanismo de enlace; Ethernet IPv4 costuma usar ARP, enquanto IPv6 utiliza descoberta de vizinhos. Mesmo com prefixo correspondente, firewall, interface inativa ou políticas podem impedir encaminhamento. A função didática ignora essas condições [1][6].

O **TTL de pacote IPv4** e o **Hop Limit IPv6** limitam o número de encaminhamentos e mitigam loops. São campos de cabeçalho e **não** equivalem ao TTL do cache DNS nem ao timeout da requisição. O IPv6 usa endereços de 128 bits e regras descritas pelo RFC 8200; o exemplo a seguir cobre somente IPv4 de 32 bits [6].

MTU do caminho, fragmentação, ICMP e tradução de endereços acrescentam outras condições. Uma rota correta pode corresponder ao destino e ainda não entregar o pacote. O retorno do seletor não comprova conectividade.

## Contrato executável de seleção por prefixo

A função recebe entradas `(CIDR, gateway, metric)`. Prefixo e próximo salto precisam ser endereços IPv4 válidos, e a métrica deve ser inteiro não negativo (excluímos `bool`). Exigimos que a rede CIDR seja **canônica**: `192.0.2.1/24` é rejeitada, em vez de convertida silenciosamente para `192.0.2.0/24`.

A função valida **todas** as entradas, inclusive aquelas que não correspondem ao destino, antes de responder. Isso impede aceitar configuração malformada só porque a rota padrão já foi encontrada. Retorna `(prefixo, gateway)` ou `None` quando não há rota.

~~~python
from ipaddress import IPv4Address, IPv4Network

def choose_ipv4_route(entries, destination):
    if not isinstance(entries, (tuple, list)):
        raise ValueError("routes must be a sequence")
    if type(destination) is not str:
        raise ValueError("destination must be an IPv4 string")
    try:
        address = IPv4Address(destination)
    except ValueError as exc:
        raise ValueError("invalid IPv4 destination") from exc
    candidates = []
    for index, entry in enumerate(entries):
        if (not isinstance(entry, tuple) or len(entry) != 3
                or type(entry[0]) is not str or type(entry[1]) is not str
                or type(entry[2]) is not int or entry[2] < 0):
            raise ValueError("expected (CIDR, gateway, nonnegative metric)")
        prefix, gateway, metric = entry
        try:
            network = IPv4Network(prefix, strict=True)
            next_hop = IPv4Address(gateway)
        except ValueError as exc:
            raise ValueError("invalid IPv4 route") from exc
        if address in network:
            candidates.append((-network.prefixlen, metric, index,
                               str(network), str(next_hop)))
    if not candidates:
        return None
    _, _, _, prefix, gateway = min(candidates)
    return (prefix, gateway)

routes = (
    ("0.0.0.0/0", "198.51.100.1", 100),
    ("192.0.2.0/24", "198.51.100.2", 10),
    ("192.0.2.128/25", "198.51.100.3", 20),
    ("192.0.2.128/25", "198.51.100.4", 5),
)
assert choose_ipv4_route(routes, "192.0.2.200") == (
    "192.0.2.128/25", "198.51.100.4")
assert choose_ipv4_route(routes, "192.0.2.50") == (
    "192.0.2.0/24", "198.51.100.2")
assert choose_ipv4_route(routes, "203.0.113.1") == (
    "0.0.0.0/0", "198.51.100.1")
assert choose_ipv4_route((), "203.0.113.1") is None
~~~

O prefixo `/25` supera `/24` e `/0` mesmo que sua métrica numérica seja maior. Dentre os dois `/25`, vence métrica 5. Sem prefixo compatível ou rota padrão, retorna `None` sem adivinhar gateway.

O invariante de correção é: todo candidato está validado e contém o IP de destino. Minimizar a tupla `(-tamanho_prefixo, metrica, indice_original)` seleciona a rota mais específica, depois menor métrica e entrada mais antiga. Varrer `r` entradas custa `O(r)` para endereços IPv4 de largura fixa, com `O(r)` memória para candidatos. Roteadores reais podem usar tries, TCAM ou outras estruturas.

## Hierarquia DNS, delegação e tipos de resposta

Uma pergunta DNS identifica **nome**, **tipo** e **classe**. A hierarquia distribui a autoridade entre zonas: resolvedores recursivos acompanham delegações ou usam informações prévias até alcançar resposta autoritativa. Stub resolver, resolvedor recursivo com cache e servidor autoritativo cumprem funções diferentes [2][3].

Um registro **A** contém IPv4 e um **AAAA** contém IPv6. CNAME indica alias e requer resolução adicional; não vira automaticamente um A. NS indica delegação; SOA contém metadados relevantes para cache negativo. Um nome pode ter A sem AAAA, ou vice-versa. Ausência de AAAA não comprova necessariamente que o nome inexiste [2][3][4].

Consultas DNS podem usar UDP ou TCP dependendo do tamanho, truncamento e políticas. DNS **não equivale exclusivamente a UDP na porta 53**. Também podem retornar vários endereços; escolher um ou comparar conectividade IPv4/IPv6 é decisão de cliente distinta de encaminhar pacotes até ele.

## Cache positivo, TTL e fronteira de expiração

O TTL do registro DNS define duração de cache permitida pelas normas e pela política do resolvedor. Para resposta inserida no instante `t` com TTL `q`, nosso contrato é validade em `t <= agora < t+q`; exatamente em `t+q`, a entrada expira. **TTL zero** impede armazenamento reutilizável [2][3].

Usaremos relógio **monotônico de segundos inteiros**, não relógio de parede. Consultas e inserções devem ter tempos não decrescentes; permitir voltar o tempo faria resposta expirada parecer válida. Normalizamos nomes ASCII para minúsculas e aceitamos um ponto terminal opcional. A e AAAA usam chaves **separadas** porque o tipo do registro faz parte da pergunta.

DNS real permite nomes e registros além deste subconjunto; nomes internacionalizados demandam codificação apropriada e há classes, CNAME, delegações e respostas negativas. Nosso exemplo aceita somente respostas positivas IN A/AAAA de origem considerada confiável e não realiza recursão nem validação DNSSEC.

## Implementação executável do cache

~~~python
from ipaddress import ip_address

class PositiveDnsCache:
    def __init__(self):
        self.entries = {}
        self.last_time = 0

    @staticmethod
    def _key(name, kind):
        if type(name) is not str or type(kind) is not str:
            raise ValueError("name and type must be strings")
        lowered = name.lower()
        if lowered.endswith("."):
            lowered = lowered[:-1]
        labels = lowered.split(".")
        if (not lowered.isascii() or len(lowered) > 253
                or any(not 1 <= len(label) <= 63
                       or label[0] == "-" or label[-1] == "-"
                       or any(not (char.isascii() and
                                   (char.isalnum() or char == "-"))
                              for char in label)
                       for label in labels)
                or kind not in ("A", "AAAA")):
            raise ValueError("unsupported name or record type")
        return (lowered, kind)

    def _clock(self, now):
        if type(now) is not int or now < self.last_time:
            raise ValueError("clock must be monotone integer seconds")
        self.last_time = now

    def put(self, name, kind, addresses, ttl, now):
        key = self._key(name, kind)
        if (not isinstance(addresses, tuple) or not addresses
                or type(ttl) is not int or ttl < 0
                or type(now) is not int or now < self.last_time):
            raise ValueError("invalid answer, TTL or clock")
        expected_version = 4 if kind == "A" else 6
        try:
            valid = all(type(item) is str
                        and ip_address(item).version == expected_version
                        for item in addresses)
        except ValueError as exc:
            raise ValueError("invalid IP address record") from exc
        if not valid:
            raise ValueError("address family mismatch")
        self._clock(now)
        if ttl == 0:
            self.entries.pop(key, None)
            return False
        self.entries[key] = (addresses, now + ttl)
        return True

    def get(self, name, kind, now):
        key = self._key(name, kind)
        self._clock(now)
        value = self.entries.get(key)
        if value is None:
            return None
        addresses, expires_at = value
        if now >= expires_at:
            del self.entries[key]
            return None
        return (addresses, expires_at - now)

cache = PositiveDnsCache()
assert cache.put("WWW.Example.test.", "A", ("192.0.2.9",), 5, 10)
assert cache.get("www.example.test", "A", 13) == (("192.0.2.9",), 2)
assert cache.get("www.example.test", "AAAA", 14) is None
assert cache.get("www.example.test", "A", 15) is None
assert not cache.put("www.example.test", "A", ("192.0.2.10",), 0, 16)
assert cache.get("www.example.test", "A", 16) is None
~~~

A resposta inserida em t=10 com TTL=5 pode ser lida em t=13, com dois segundos restantes. Em **t=15** já está expirada. Consulta AAAA não reutiliza um A. Uma inserção com TTL zero descarta a versão em cache da mesma chave; resolvedores reais também podem utilizar registros TTL zero durante a transação corrente [3].

O invariante é: cada entrada tem nome/tipo válidos, tupla não vazia de endereços compatíveis e prazo absoluto. Toda resposta devolvida mantém TTL restante positivo. Operações inválidas não devem mudar dados nem relógio. O custo de busca esperado é constante no dicionário, além da normalização do nome; inserir envolve validação de todos os endereços.

## NXDOMAIN, NODATA e serve-stale

O código trata **somente cache positivo**. RFC 2308 diferencia **NXDOMAIN** (nome não existe) de **NODATA** (nome existe, mas não há o tipo pedido). O escopo das chaves de cache e o TTL negativo envolvem informações do SOA. Representar os dois por tupla vazia seria incorreto [4].

Existe exceção padronizada de resiliência: RFC 8767 permite que resolvedores qualificados **respondam com dados expirados** em certas situações em que não conseguem atualizar a informação junto aos servidores autoritativos. Portanto, afirmar que todo resolvedor conforme às normas **jamais** devolve respostas após o TTL original é falso. O nosso cache deliberadamente **não implementa serve-stale**; expira exatamente no limite [5].

DNSSEC autentica dados DNS por cadeia de confiança própria. DoT e DoH protegem o transporte entre cliente e resolvedor sob determinadas hipóteses, mas não comprovam por si a autenticidade do registro na zona original. Segurança criptográfica precisa de aprofundamento independente.

## Da resposta DNS ao TCP e à aplicação

Depois de receber endereços candidatos, o cliente ainda precisa selecionar destino, estabelecer transporte e validar identidade do serviço. TCP oferece **fluxo ordenado de bytes**, e não mensagens da aplicação. UDP opera com datagramas e outras garantias. HTTP/3 utiliza QUIC sobre UDP. O capítulo de [protocolos de rede](/pt/topics/network-protocols/) aborda as etapas posteriores e a fronteira de confiança TLS [1][6].

No diagnóstico, teste cada hipótese na camada certa. NXDOMAIN sugere namespace ou configuração de DNS. Resposta A válida sem rota indica problema de encaminhamento, não resolução do nome. TCP estabelecido seguido de HTTP 503 significa que a rede funcionou até determinado ponto, enquanto o gateway ou dependência pode continuar indisponível. Alterar o TTL de DNS não resolve erro da tabela de rotas.

## Exercícios e verificação

1. Para `192.0.2.50`, `192.0.2.200` e `203.0.113.5`, derive os prefixos compatíveis e selecione maior prefixo, menor métrica e índice.
2. Retire `/0`. Explique por que retornar `None` em endereço sem correspondência é mais correto que inventar gateway.
3. Adicione prefixo e métrica idênticos com outro próximo salto. Mostre o efeito do desempate pela ordem original.
4. Construa rede inválida `192.0.2.7/24`; justifique a rejeição antes de retornar qualquer match.
5. Faça cache A em t=100 com TTL=30 e consulte t=129 e t=130. Explique TTL zero e limites desta implementação.
6. Diferencie cache negativo para nome inexistente e nome existente sem AAAA, com as chaves especificadas no RFC 2308 [4].
7. Proponha extensão serve-stale com condições excepcionais, prazo máximo, TTL devolvido e falhas declaradas [5].
8. Desenhe consulta recursiva sem cache passando por delegações até servidor autoritativo. Indique quais entidades fornecem cache e quais administram zona.
9. Distinga TTL do pacote IP, TTL do registro DNS, temporização de retransmissão TCP e deadline de HTTP, indicando uma medição apropriada a cada camada.

**Continuação:** [DNS, TCP, TLS e HTTP](/pt/topics/network-protocols/) aplica estes fundamentos à conectividade de aplicações. Aritmética de sequência TCP, retransmissão, controle de congestionamento, DNSSEC e políticas de BGP permanecem tópicos distintos [1][2][3][4][5][6].
