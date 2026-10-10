---
id: tls13-hkdf-handshake
title: "TLS 1.3: autenticação, HKDF e derivação de chaves"
description: "Entenda autenticação e derivação de chaves TLS 1.3, diferencie HKDF de cifragem e valide HKDF-SHA256 e rótulos TLS com vetores normativos."
category: security
difficulty: intermediate
updated: 2026-10-10
prerequisites: [network-protocols, tcp-byte-stream-framing-flow-control]
sources:
  - {title: "RFC 9846 — Transport Layer Security (TLS) 1.3, July 2026", url: "https://www.rfc-editor.org/info/rfc9846", kind: "internet standard"}
  - {title: "RFC 5869 — HMAC-based Extract-and-Expand Key Derivation Function", url: "https://www.rfc-editor.org/info/rfc5869", kind: "internet standard"}
  - {title: "RFC 9525 — Service Identity in TLS", url: "https://www.rfc-editor.org/info/rfc9525", kind: "internet standard"}
  - {title: "RFC 9114 — HTTP/3", url: "https://www.rfc-editor.org/info/rfc9114", kind: "internet standard"}
  - {title: "Python hmac and hashlib reference", url: "https://docs.python.org/3/library/hmac.html", kind: "official standard library documentation"}
---
O TLS 1.3 estabelece um canal criptografado e protegido contra adulteração **após autenticar a identidade conforme a política da aplicação**. Não substitui roteamento IP, entrega TCP nem controle de autorização do serviço. O capítulo sobre [requisições de rede](/pt/topics/network-protocols/) diferencia DNS, TCP, TLS e HTTP; o estudo do [fluxo de bytes TCP](/pt/topics/tcp-byte-stream-framing-flow-control/) apresenta a camada de transporte normalmente utilizada por TLS [1].

A especificação atual do TLS 1.3 é a **RFC 9846 (julho de 2026)**, que substituiu a RFC 8446 mantendo compatibilidade no protocolo e reforçando obrigações como não reutilizar valores KeyShare entre conexões. A derivação continua baseada em HKDF. A parte executável aqui cobre **apenas HKDF-SHA256 e codificação de rótulos TLS**, com vetores públicos e material sintético. Não implementa handshake completo, validação de certificados, acordo de chaves, AEAD, gerenciamento de nonces nem record layer [1][2].

## Objetivos de segurança e limites de confiança

Numa conexão HTTPS comum autenticada por certificado, o cliente precisa validar a **identidade do servidor** e estabelecer chaves de tráfego novas. TLS oferece confidencialidade e integridade contra atacantes que observam e modificam pacotes dentro das hipóteses criptográficas do protocolo. Não esconde automaticamente consultas DNS nem endereços IP, não protege um endpoint comprometido e não concede autorização a usuários da API [1].

**Cifragem**, **integridade** e **autenticação** não são sinônimos. Uma cifra oculta o conteúdo; um código de autenticação detecta modificações sem autorização; um handshake autenticado associa os segredos a identidade e transcrição. TLS 1.3 usa cifras **AEAD**, por exemplo AES-GCM ou ChaCha20-Poly1305 quando negociadas. Um hash SHA-256 simples, sem chave, não autentica a origem porque um invasor que substitui a mensagem pode recalcular o hash [1].

A validação da identidade deve comparar os nomes apresentados no certificado com **o serviço que o cliente pretendia alcançar**. Ter uma cadeia sintaticamente válida não é suficiente. Âncoras de confiança, validade, hostname/SAN, usos permitidos e política da implementação importam; a RFC 9525 descreve boas práticas de identidade de serviços [3]. Uma conexão baseada em chave pré-compartilhada segue outro caminho de autenticação e não deve ser descrita como se sempre usasse certificados.

## Handshake completo: funções de cada mensagem

Um handshake conceitual TLS 1.3 sem PSK e com autenticação de servidor percorre:

1. **ClientHello:** anuncia parâmetros suportados e key share nova, frequentemente com informações de SNI e ALPN.
2. **ServerHello:** escolhe parâmetros e fornece sua key share. Os participantes calculam um segredo ECDHE; **ele não é enviado pela rede como chave de tráfego pronta**.
3. **EncryptedExtensions e Certificate:** o servidor comunica parâmetros adicionais protegidos e certificado usado na validação de identidade; o certificado não substitui a chave simétrica da conexão.
4. **CertificateVerify:** demonstra posse de credencial de assinatura sobre o contexto; **Finished** verifica integridade da transcrição negociada por meio de uma chave derivada.
5. **Tráfego da aplicação:** cliente e servidor derivam segredos de tráfego separados, com chaves e IVs de AEAD para cada direção, e passam a trocar registros autenticados [1].

O hash de transcrição incorpora mensagens de handshake **tipadas e com comprimentos codificados**. Não se trata de juntar strings arbitrárias. Caminhos de erro e retry, certificados de cliente, retomada de sessão, HelloRetryRequest e mensagens pós-handshake acrescentam etapas. Esta sequência é um mapa conceitual, não serialização completa do protocolo.

## Acordo de chaves, HKDF e transcrição não são intercambiáveis

ECDHE efêmero produz um segredo compartilhado a partir de material privado novo. **HKDF-Extract** processa esse material de entrada (IKM) e um salt, produzindo uma chave pseudorrandômica (PRK). **HKDF-Expand** deriva material adicional usando a PRK e contexto identificado. Hashes de transcrição vinculam derivações às mensagens negociadas, enquanto verificações de Finished autenticam o contexto com os segredos estabelecidos [1][2].

HKDF **não** comprova que um servidor controla a chave de um certificado, não cria keypairs ECDHE seguros, não cifra bytes de aplicação nem valida tags AEAD. Acordo de chaves sem autenticação admite interceptação por adversário ativo; derivar uma PRK aparentemente aleatória não resolve a identidade.

A agenda de chaves do TLS usa PSK (ou valor zerado), segredo assimétrico ECDHE e transcrições cada vez mais completas. Deriva segredos distintos de handshake e de aplicação, nos sentidos cliente→servidor e servidor→cliente. Na RFC 9846, o valor conceitualmente antes chamado *master secret* recebe o nome **main secret** no texto, embora alguns rótulos normativos mantenham a grafia antiga por compatibilidade [1]. Não é permitido modificar rótulos literais do protocolo só para alinhar nomenclatura.

## RFC 5869: extract e expand com vetores oficiais

A variante SHA-256 da RFC 5869 define `PRK=HMAC-SHA256(salt, IKM)`. Com salt ausente ou vazio, utiliza 32 bytes zero como padrão. A expansão calcula `T(i)=HMAC-SHA256(PRK, T(i−1) || info || i)`, iniciando com `T(0)` vazio e contador `i` codificado em **um byte** [2]. A saída é o prefixo da concatenação dos blocos.

Esse contador limita a expansão a **255 blocos de 32 bytes**, ou 8160 bytes. Nosso código aplica o limite, exige PRK com pelo menos 32 bytes e aceita apenas entradas binárias explícitas. Os vetores conhecidos da RFC são **públicos** e servem para teste; nunca copie esses valores fixos como segredos de conexões reais.

~~~python
import hashlib
import hmac

HASH_LENGTH = hashlib.sha256().digest_size

def hkdf_extract(salt, ikm):
    if type(salt) is not bytes or type(ikm) is not bytes:
        raise ValueError("salt and input keying material must be bytes")
    key = salt if salt else bytes(HASH_LENGTH)
    return hmac.new(key, ikm, hashlib.sha256).digest()

def hkdf_expand(prk, info, length):
    if type(prk) is not bytes or len(prk) < HASH_LENGTH:
        raise ValueError("PRK must be at least 32 bytes")
    if type(info) is not bytes:
        raise ValueError("info must be bytes")
    if type(length) is not int or not 0 <= length <= 255 * HASH_LENGTH:
        raise ValueError("invalid HKDF output length")
    blocks = []
    previous = b""
    for counter in range(1, (length + HASH_LENGTH - 1) // HASH_LENGTH + 1):
        previous = hmac.new(prk, previous + info + bytes([counter]),
                            hashlib.sha256).digest()
        blocks.append(previous)
    return b"".join(blocks)[:length]

# RFC 5869 Appendix A.1, SHA-256: published public test values, NOT keys.
test_ikm = bytes([0x0b]) * 22
test_salt = bytes(range(13))
test_info = bytes(range(0xf0, 0xfa))
prk = hkdf_extract(test_salt, test_ikm)
assert prk.hex() == (
    "077709362c2e32df0ddc3f0dc47bba63"
    "90b6c73bb50f9c3122ec844ad7c2b3e5"
)
assert hkdf_expand(prk, test_info, 42).hex() == (
    "3cb25f25faacd57a90434f64d0362f2a"
    "2d2d0a90cf1a5a4c5db02d56ecc4c5bf"
    "34007208d5b887185865"
)
assert hkdf_expand(prk, b"", 0) == b""
~~~

Trata-se de implementação didática apoiada nas primitivas SHA-256 e HMAC da biblioteca padrão Python. Isso **não autoriza criar protocolos criptográficos próprios em produção**. Uma biblioteca TLS consolidada deve controlar entropia, ciclo de vida de segredos, resistência a canais laterais, negociação de algoritmos e tratamento de erros.

## HKDF-Expand-Label: cada byte da estrutura importa

TLS 1.3 empacota o `info` usado por HKDF com uma estrutura precisa: **comprimento de saída em dois bytes big-endian**, **rótulo ASCII prefixado por comprimento de um byte** com texto `tls13 ` seguido do nome, e **contexto binário prefixado por comprimento de um byte**. O resultado é passado à expansão HKDF [1].

Mudar um byte do rótulo altera a derivação; mudar hash de transcrição, contexto, prefixos de tamanho ou sua ordem também. O rótulo completo precisa de ao menos sete bytes pelo prefixo de seis mais nome não vazio, e o total deve caber em um byte. O contexto pode ter de zero a 255 bytes. Esses limites de serialização são **diferentes** do máximo de expansão HKDF.

~~~python
def tls13_hkdf_label(label, context, length):
    if type(label) is not str or not label or not label.isascii():
        raise ValueError("TLS label must be nonempty ASCII")
    if type(context) is not bytes or len(context) > 255:
        raise ValueError("TLS context must be at most 255 bytes")
    if type(length) is not int or not 0 <= length <= 65535:
        raise ValueError("TLS length must fit a two-byte integer")
    label_bytes = b"tls13 " + label.encode("ascii")
    if len(label_bytes) > 255:
        raise ValueError("TLS prefixed label exceeds one byte of length")
    return (
        length.to_bytes(2, "big")
        + bytes([len(label_bytes)]) + label_bytes
        + bytes([len(context)]) + context
    )

def tls13_expand_label(secret, label, context, length):
    return hkdf_expand(secret, tls13_hkdf_label(label, context, length), length)

assert tls13_hkdf_label("key", b"", 16).hex() == (
    "001009746c733133206b657900"
)
# Public, synthetic material ONLY; this does not negotiate any TLS keys.
synthetic_secret = hashlib.sha256(b"public teaching example, no secret").digest()
demo_key = tls13_expand_label(synthetic_secret, "key", b"", 16)
demo_iv = tls13_expand_label(synthetic_secret, "iv", b"", 12)
assert len(demo_key) == 16 and len(demo_iv) == 12
assert demo_key != tls13_expand_label(synthetic_secret, "iv", b"", 16)
assert tls13_expand_label(synthetic_secret, "key", b"A", 16) != demo_key
~~~

O exemplo `"key"` produz os bytes `001009746c733133206b657900`: comprimento desejado 16, rótulo prefixado com nove bytes e contexto vazio. O segredo sintético é público, repetível e **não provém de handshake real**. O TLS deriva um IV separado com rótulo `"iv"`; chave e IV não podem ser considerados intercambiáveis [1].

Em TLS real, o nonce de cada registro depende do IV e do número de sequência, respeitando regras do record layer e limites de uso da chave AEAD. Este capítulo **não** implementa AEAD ou nonces por registro. A saída destes exemplos nunca deve ser usada diretamente como esquema próprio de cifragem de aplicação.

## Autenticação de certificado e erros de implantação

Falhas operacionais de TLS normalmente estão em camadas diferentes da derivação de chaves: certificados expirados, SAN errado, cadeia incompleta, raiz não confiável, relógio incorreto, ALPN incompatível, versões TLS obsoletas, suites incompatíveis ou terminação TLS em proxy. Cada problema precisa ser verificado na etapa correta; resolver DNS e conectar à porta TCP 443 **não prova** que o certificado corresponde ao serviço pretendido [1][3].

Um proxy que termina TLS autentica o tráfego **até aquele ponto**. O trecho proxy→origem requer sua própria política de proteção. Promessas de segurança ponta a ponta devem identificar todas as terminações. TLS e certificado válido também não impedem um usuário autenticado de realizar operações indevidas: autorização, auditoria, tokens e regras de negócio são controles distintos.

Retomada de sessão TLS 1.3 pode diminuir o custo de conexão, mas **dados antecipados 0-RTT podem sofrer replay** e não são automaticamente seguros para operações não idempotentes. Um endpoint de escrita não deve presumir que negociação TLS correta elimina repetição de solicitações. A norma trata mitigações e limites, não garantia global de ausência de replay [1].

## TLS sobre TCP, QUIC e medição de desempenho

A discussão anterior considera principalmente TLS sobre **fluxo confiável de bytes em ordem**, usualmente TCP. QUIC integra o handshake TLS 1.3 a outra arquitetura de proteção de pacotes; **HTTP/3 utiliza QUIC**, não o record layer TLS convencional sobre TCP. Não devemos aplicar indiscriminadamente a estrutura de registros deste capítulo ao QUIC [1][4].

Latência do handshake depende de RTT, processamento, reuso de sessão e transporte. Atribuir número fixo de RTTs a toda conexão TLS 1.3 ignora retomada, variantes, tempo dos dados e conexões já estabelecidas. Nas medições, DNS, abertura do transporte, handshake TLS, falhas de certificado e tempo até o primeiro byte devem ser avaliados **separadamente**. Mediana baixa não descarta cauda elevada ou falhas sob carga.

## Verificação independente e limites

Os testes do repositório checam **vetores normativos da RFC 5869** e confrontam HKDF-SHA256 com implementação separada de HMAC por paddings interno/externo e `hashlib`, **sem reutilizar `hmac.new`**. Verificam também os bytes de rótulos TLS, limites de tamanho e entradas inválidas, em **ambos os idiomas**. Isso é evidência funcional limitada aos domínios testados.

Não comprova boa entropia, autenticação de certificados, conformidade integral TLS, confidencialidade do tráfego, resistência a MITM, integridade da transcrição perante ataques ou resistência a temporização. Essas propriedades exigiriam bibliotecas TLS interoperáveis, vetores de handshake, revisão criptográfica e testes adversariais de integração.

## Exercícios e verificação

1. Explique por que DNS, conexão TCP, autenticação TLS e autorização HTTP resolvem **quatro problemas distintos**.
2. Deduza os dois primeiros blocos de HKDF-Expand e explique o limite `255 × 32` bytes para SHA-256.
3. Decodifique `001009746c733133206b657900` campo a campo. Troque `"key"` por `"iv"` e justifique a mudança no material derivado.
4. Demonstre por que HKDF-Expand-Label não consegue derivar 9000 bytes com SHA-256, apesar de a estrutura ter campo de comprimento em dois bytes.
5. Descreva um ataque MITM contra ECDHE sem autenticação e identifique mensagens e validações TLS que reduzem o risco.
6. Explique por que certificado válido para um nome não pode ser aceito automaticamente para outro hostname.
7. Construa exemplo de solicitação 0-RTT que altera banco de dados e determine a política adicional necessária contra replay.
8. Compare TLS records sobre TCP com proteção de pacotes QUIC em HTTP/3, apontando código que não pode ser reaproveitado.
9. Proponha testes negativos para falta de campo de tamanho do contexto, label não ASCII, saída excessiva e PRK curta.

**Continuidade:** capítulos de AEAD e nonces, assinaturas, PKI/X.509, DNSSEC e interoperabilidade real TLS ainda exigem estudo independente. [Fundamentos de rede](/pt/topics/network-protocols/) e [segurança de API](/pt/topics/api-security/) integram a segurança do transporte ao projeto de serviços [1][2][3][4][5].
