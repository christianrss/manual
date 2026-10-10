---
id: network-protocols
title: "Fundamentos de redes: DNS, TCP, TLS e HTTP"
description: "Acompanhe uma requisição por DNS, transporte, TLS e HTTP; derive custos de latência e falhas e diferencie TCP de QUIC."
category: system-design
difficulty: intermediate
updated: 2026-10-10
prerequisites: [capacity-estimation, processes-virtual-memory, ip-routing-dns-resolution]
sources:
  - {title: "RFC 9293 — Transmission Control Protocol", url: "https://www.rfc-editor.org/info/rfc9293", kind: "internet standard"}
  - {title: "RFC 9846 — TLS Protocol Version 1.3", url: "https://www.rfc-editor.org/info/rfc9846", kind: "internet standard"}
  - {title: "RFC 9114 — HTTP/3", url: "https://www.rfc-editor.org/info/rfc9114", kind: "internet standard"}
  - {title: "RFC 8305 — Happy Eyeballs Version 2", url: "https://www.rfc-editor.org/info/rfc8305", kind: "internet standard"}
---
O capítulo de [roteamento IP e DNS](/pt/topics/ip-routing-dns-resolution/) deduz seleção por prefixo, responsabilidades de resolução e cache positivo com TTL, preparando esta visão ponta a ponta.

Uma requisição web atravessa protocolos com garantias diferentes. **DNS** ajuda a descobrir destinos; **IP** encaminha pacotes; **TCP** fornece fluxo confiável e ordenado de bytes; **TLS** protege uma conexão contra interceptação e adulteração sob suas hipóteses de autenticação; **HTTP** define semântica de requisições e respostas. Misturar essas camadas leva a diagnósticos errados, como acreditar que uma conexão TCP aceita garante aplicação saudável [1][2].

## Caminho explícito de uma requisição

Considere um navegador abrindo recurso HTTPS em um nome de domínio. Ele precisa descobrir endereços, alcançar um destino, estabelecer transporte e negociar proteção antes de trocar dados de aplicação. Caches, sessões reutilizadas, proxies e diferentes protocolos podem dispensar ou sobrepor etapas. Uma resposta DNS informa destino possível, mas não comprova o comportamento de negócio do serviço. Resolver do sistema, navegador, resolver recursivo e servidores DNS autoritativos têm responsabilidades diferentes.

![Sequência de resolução de nomes, transporte, criptografia e HTTP.](/diagrams/network-request-sequence.svg)

O domínio pode apontar para IPv4, IPv6 ou uma CDN. Estratégias de conexão podem testar famílias de endereço com pequeno deslocamento temporal, evitando aguardar excessivamente uma rota inicialmente indisponível; Happy Eyeballs é um mecanismo documentado [4]. Respostas de DNS não são mapeamentos permanentes: TTL, conjuntos de IP e destinos mudam com implantação e operação.

## TCP transporta bytes, não mensagens

TCP identifica conexões por endereços e portas e oferece **fluxo confiável e ordenado de bytes**. Usa numeração de sequência, confirmações e retransmissões para tratar perda [1]. Não preserva automaticamente os limites das gravações da aplicação. Uma chamada send pode exigir diversas chamadas read; várias gravações podem chegar na mesma leitura. O protocolo da aplicação precisa enquadrar suas mensagens, por tamanho, delimitador ou sintaxe estruturada de HTTP.

Separe **controle de fluxo**, que limita dados em trânsito segundo capacidade do receptor, de **controle de congestionamento**, que restringe o envio para proteger a rede compartilhada. Janela de recepção ampla não significa banda infinita. Da mesma forma, completar o handshake TCP não impede o servidor de rejeitar ou exceder o timeout de requisição depois.

## TLS e fronteira de confiança

TLS 1.3 negocia parâmetros criptográficos, autentica participantes conforme o mecanismo escolhido e deriva chaves que protegem os registros posteriores. Para HTTPS público, verificar cadeia de certificados e nome do host é essencial; cifrar dados sem autenticar corretamente a outra ponta não impede um intermediário malicioso de se fazer passar pelo servidor [2]. Handshakes modernos têm custos distintos de versões antigas, e dados antecipados 0-RTT podem ser reproduzidos: não são mecanismo universalmente seguro para efeitos não idempotentes.

Quando TLS termina num proxy reverso, muda o ponto onde existe texto claro e quem passa a ser confiável. Se o proxy encaminha a requisição por outra conexão, a segurança desse **segundo** percurso exige análise independente. Cabeçalhos com IP do cliente só devem ser aceitos de proxies definidos e confiáveis, nunca de clientes diretos arbitrários.

## HTTP independe de um único transporte

Métodos e códigos HTTP são semânticas de **aplicação**, não confirmações do transporte. Um status 200 não garante conclusão de efeitos assíncronos. Um POST pode significar aceitação de processamento futuro; o contrato precisa especificar quando o trabalho é durável. Se a conexão termina depois que o servidor confirma uma operação, o cliente não sabe necessariamente se ela ocorreu; repetir sem idempotência pode duplicar efeitos.

HTTP/3 usa **QUIC** sobre UDP, com transporte criptografado e streams próprios [3]. Portanto, 'HTTP só usa TCP' é falso. HTTP/2 multiplexa streams sobre TCP, mas perda de pacotes pode retardar entrega do fluxo TCP; QUIC oferece mecanismos por stream que reduzem parte do bloqueio entre streams. Nenhum dos dois elimina limites de banda, sobrecarga ou dependências da aplicação.

## Dedução do orçamento de latência

Seja T o tempo total. Um modelo simplificado de conexão fria é T = T_dns + T_conexao + T_tls + T_transferencia + T_servidor. Em protocolos modernos algumas etapas se sobrepõem, então somá-las sem cuidado superestima certos handshakes. Para cenário **hipotético sequencial**, DNS 15 ms, transporte 35 ms, TLS 40 ms, transferência 25 ms e execução 85 ms produzem T = 200 ms. Com DNS em cache e conexão reutilizada, três termos podem desaparecer; a execução e a transferência continuam custando tempo.

O percentil p99(T) **não é necessariamente** a soma dos p99 individuais. O pior 1% de cada etapa pode ocorrer em requisições diferentes. Correlações e falhas condicionais importam: calcule percentis usando traces completos, não a soma de resumos de diferentes serviços.

## Exercício reproduzível de endereçamento

~~~python
from ipaddress import ip_network, ip_address

subrede = ip_network("192.0.2.0/27")
assert subrede.num_addresses == 32
assert ip_address("192.0.2.30") in subrede
assert ip_address("192.0.2.32") not in subrede

def latencia_total_ms(dns, conexao, tls, transferencia, servidor):
    valores = [dns, conexao, tls, transferencia, servidor]
    if any(x < 0 for x in valores):
        raise ValueError("latencia negativa")
    return sum(valores)

assert latencia_total_ms(15,35,40,25,85) == 200
~~~

A conta ensina unidades e decomposição; **não** mede rede real nem representa tentativas paralelas. A faixa de endereço é reservada para documentação, não indicação de implantação. Em produção, inspecione consultas DNS, validação TLS, conexões e rastreamento distribuído nas fronteiras de serviço.

## Falhas comuns e decisões de arquitetura

| Sintoma | Camada possível | Verificação |
| --- | --- | --- |
| Nome não resolve | DNS/resolver | Consultar resolvers e registros autoritativos |
| TCP conecta, HTTP 503 | Aplicação ou gateway | Inspecionar saúde e saturação |
| Erro de certificado | Identidade TLS | Conferir nome, confiança e vencimento |
| Regiões lentas | Rota, distância, dependências | Medir traces completos por região |
| Escrita repetida após timeout | Idempotência de aplicação | Confirmar operação e efeito persistente |

Um timeout único não cobre necessariamente DNS, conexão, TLS, primeiro byte e resposta completa. Use orçamentos distintos se a biblioteca permitir. Fechar conexão ociosa reduz uso de recursos, mas aumenta custo de próximo handshake; pooling economiza handshakes, exigindo limites e política de saúde.

**Capítulos relacionados:** [Balanceamento de carga](/pt/topics/load-balancing/) trata roteamento; [estimativa de capacidade](/pt/topics/capacity-estimation/) quantifica demanda; [APIs confiáveis](/pt/topics/api-reliability/) aprofunda timeouts e retries.

## Exercícios e verificação

1. Explique por que uma leitura TCP de 100 bytes não garante que uma mensagem HTTP inteira chegou.
2. Descreva uma resposta HTTPS desde DNS até autenticação e execução, indicando etapas reutilizáveis.
3. Compare resposta de cache com conexão TLS nova versus origem fria; declare hipóteses antes de afirmar qual é mais rápida.
4. Explique por que repetir POST após perda de conexão requer identidade da operação no nível da aplicação.
5. Com prazo total de 250 ms e dependência que pode gastar 150 ms, distribua orçamento para conexão, parsing, retries e resposta sem dar 250 ms a cada camada.
