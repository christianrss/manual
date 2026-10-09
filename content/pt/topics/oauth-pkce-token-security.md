---
id: oauth-pkce-token-security
title: "Segurança OAuth 2.0: PKCE, vinculação de tokens e replay"
description: "Deduza o fluxo de código com PKCE, fronteiras de ameaça, rotação de refresh tokens, audiência e resistência a replay a partir de RFCs."
category: system-design
difficulty: advanced
updated: 2026-10-09
prerequisites: [api-security, network-protocols]
sources:
  - {title: "RFC 9700 — OAuth 2.0 Security Best Current Practice", url: "https://www.rfc-editor.org/rfc/rfc9700.html", kind: "IETF standard"}
  - {title: "RFC 7636 — Proof Key for Code Exchange", url: "https://www.rfc-editor.org/rfc/rfc7636.html", kind: "IETF standard"}
  - {title: "RFC 9449 — OAuth 2.0 Demonstrating Proof of Possession (DPoP)", url: "https://www.rfc-editor.org/rfc/rfc9449.html", kind: "IETF standard"}
---
OAuth 2.0 permite que um cliente obtenha autorização para acessar recursos protegidos por um servidor de autorização sem receber a senha do proprietário. Esse fluxo não equivale a identificar uma pessoa: **OAuth concede acesso**, enquanto autenticar o usuário perante o cliente geralmente exige protocolo de identidade adicional, como OpenID Connect. Uma integração robusta define emissor, cliente, servidor de recursos, audiência do token, fronteira de autorização e capacidades do atacante antes de implementar redirecionamentos [1].

## Participantes, ativos e modelo de ameaça

O proprietário controla recursos; o cliente solicita acesso; o servidor de autorização emite códigos ou tokens; e o servidor de recursos valida os tokens e aplica autorização. São papéis logicamente distintos mesmo dentro da mesma organização. Um atacante pode interceptar código, substituir redirect, roubar bearer token de logs ou injetar uma resposta de outro emissor. HTTPS é necessário, mas uma conexão HTTPS isoladamente não demonstra que o token recebido corresponde à transação esperada.

O **access token** é destinado ao servidor de APIs. Um **ID token** não o substitui: descreve resultado de autenticação para o cliente correspondente. Um bearer token pode ser reutilizado por quem o possuir, caso não haja restrição criptográfica de remetente. Escopos e claims devem ser interpretados para a audiência correta e confrontados com o recurso solicitado, não tratados como autorização universal [1].

## Authorization code e PKCE como valores vinculados

Num cliente público com authorization-code grant, o cliente cria um **code verifier** criptograficamente aleatório, deriva dele um **code challenge S256** e envia o challenge na requisição inicial de autorização. Depois da autorização, o servidor redireciona o navegador para a URI previamente registrada, portando um código. O cliente troca esse código no token endpoint apresentando o verifier original. O servidor verifica que o verifier corresponde ao challenge associado ao código [2].

![PKCE vincula a troca do código à instância de cliente que iniciou a autorização.](/diagrams/oauth-pkce-flow.svg)

Um atacante que obtém apenas o código normalmente não consegue resgatá-lo sem o verifier. PKCE não autoriza acesso a quaisquer IDs de recursos e não torna um navegador comprometido confiável. A RFC 9700 exige PKCE para clientes públicos no fluxo de código e recomenda para clientes confidenciais; o challenge deve ser específico da transação [1].

## Reprodução de S256 sem criar credenciais reais

O exemplo usa o verifier público do teste da RFC 7636 para demonstrar a transformação; **não** use esse valor fixo numa aplicação real. Verifiers reais precisam ser gerados por fonte criptográfica segura e respeitar o tamanho e alfabeto permitidos pela RFC.

~~~python
import base64
import hashlib

def desafio_pkce(verifier):
    if not isinstance(verifier, str) or not 43 <= len(verifier) <= 128:
        raise ValueError("tamanho de verifier invalido")
    permitidos = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~"
    if any(c not in permitidos for c in verifier):
        raise ValueError("caractere invalido")
    resumo = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(resumo).rstrip(b"=").decode("ascii")

verifier_rfc = "dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk"
assert desafio_pkce(verifier_rfc) == "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM"
try:
    desafio_pkce("curto")
    assert False
except ValueError:
    pass
~~~

O código apenas calcula o desafio, **não** implementa servidor OAuth, autenticação do emissor ou geração segura de verifiers. Também não prova que um código pertence à sessão do navegador. A validação da resposta de redirecionamento e do vínculo com o cliente requer o protocolo completo [2].

## Redirect, CSRF e mix-up

O servidor deve comparar URIs de redirecionamento registradas conforme as regras estritas do padrão; correspondência permissiva por prefixo ou wildcard pode enviar o código a domínio controlado pelo atacante. O cliente deve correlacionar o callback à sessão e transação iniciadas por defesa de CSRF apropriada, como estado vinculado à transação ou as proteções PKCE/OIDC nas condições previstas [1]. Clientes com múltiplos emissores precisam de defesa contra **mix-up**, validando o emissor da resposta ou mecanismo equivalente aceito; chegar ao endpoint de callback não prova a origem correta.

Um **open redirector** no domínio do cliente ou do servidor pode inutilizar callbacks bem registrados. Não encaminhe parâmetros da resposta para URL arbitrária vinda de query string. Códigos são normalmente curtos e de uso único, mas o sistema ainda deve tratar callbacks duplicados e falha durante a troca de tokens.

## Replay de access tokens e prova de remetente

Um bearer token pode ser repetido após roubo enquanto for aceito. Tokens com **sender constraint** restringem esse risco ao exigir prova do remetente legítimo, por exemplo TLS mútuo ou Demonstrating Proof of Possession (DPoP) [1][3]. DPoP acrescenta prova assinada e específica da requisição, envolvendo método HTTP e URI, e mecanismos para timestamps, identificadores de replay e vínculo da chave. O servidor precisa validar a prova e compará-la ao token apresentado; acrescentar cabeçalho DPoP sem verificação criptográfica não protege nada.

DPoP não resolve completamente scripts maliciosos executados no próprio cliente legítimo ou roubo de capacidades de assinatura. O modelo de ameaça precisa incluir proteção da chave, normalização de caminhos, desvio de relógio, caches de replay e validação do recurso HTTP pretendido.

## Refresh tokens, expiração e revogação

Refresh tokens permitem obter acesso novo sem novo login interativo. A RFC 9700 exige proteção adicional para refresh tokens, incluindo vínculo do remetente ou rotação para clientes públicos sob condições relevantes [1]. Na **rotação**, trocar o token produz substituto e invalida o anterior; reutilizar o antigo pode sinalizar comprometimento. Duas abas legítimas atualizando simultaneamente também podem gerar conflitos, se o cliente não coordenar a sessão. Logs, parâmetros de URLs e ferramentas de analytics jamais devem receber esses segredos.

| Ativo | Quem valida | Falha típica |
| --- | --- | --- |
| Código de autorização | Token endpoint | Cliente errado ou ausência de PKCE |
| Access token | Servidor de recursos | Audiência errada ou expiração |
| Prova DPoP | Servidor de recursos | Assinatura inválida ou replay |
| Refresh token | Servidor de autorização | Reutilização após rotação |
| ID de recurso de negócio | Política da aplicação | Acesso a outro tenant com token válido |

Rapidez da revogação depende do tipo de token e do mecanismo de verificação. Um JWT assinado de curta duração pode continuar aceito até vencer se o servidor não consultar revogação. Identidade e token corretamente validados **não** dispensam autorização por objeto [1].

## Verificação e testes negativos

Teste o fluxo completo num ambiente apropriado do provedor: verifier diferente, estado adulterado, URI inválida, emissor errado, código duplicado, código expirado, token destinado a outra API, prova DPoP repetida e reutilização de refresh token. Confira que logs e traces nunca guardem segredos. Correção de produção depende da configuração real do provedor e de bibliotecas de protocolo verificadas, não de um manipulador de redirects criado como exemplo.

## Exercícios e verificação

1. Identifique a credencial faltante ao atacante que roubou somente código protegido por PKCE.
2. Reproduza o S256 do verifier de teste e explique a remoção do padding base64url.
3. Por que token destinado à API A não deve ser automaticamente aceito na API B?
4. Compare PKCE, que vincula resgate do código, com DPoP, que prova posse na apresentação do access token.
5. Modele disputa entre duas abas na rotação de refresh token e indique coordenação segura.

**Pré-requisitos:** [Autenticação e autorização de APIs](/pt/topics/api-security/) trata acesso a objetos; [protocolos de rede](/pt/topics/network-protocols/) explica fronteiras de confiança TLS.
