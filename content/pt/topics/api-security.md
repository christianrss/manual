---
id: api-security
title: "Segurança de APIs: identidade, autorização e modelos de ameaça"
description: "Distinga autenticação da autorização por objeto, analise fronteiras OAuth e JWT e derive isolamento multi-tenant e controles de API."
category: system-design
difficulty: advanced
updated: 2026-10-09
prerequisites: [network-protocols, database-consistency, rate-limiting]
sources:
  - {title: "OWASP API Security Top 10 — 2023", url: "https://owasp.org/API-Security/editions/2023/en/0x11-t10/", kind: "security project"}
  - {title: "RFC 9700 — Best Current Practice for OAuth 2.0 Security", url: "https://www.rfc-editor.org/info/rfc9700", kind: "internet standard"}
  - {title: "RFC 7519 — JSON Web Token (JWT)", url: "https://www.rfc-editor.org/info/rfc7519", kind: "internet standard"}
---
**Autenticação** estabelece a identidade de quem chama o serviço segundo um modelo de confiança. **Autorização** decide se essa identidade pode executar uma ação sobre um recurso específico. São verificações diferentes: um token com assinatura correta que identifica Alice não implica permissão para ler os pedidos de Bob. A API segura define propriedade dos dados e decisões de acesso no backend autoritativo, não apenas na interface do navegador [1].

## Ativos, agentes e fronteiras de confiança

Comece com ativos: dados de contas, pedidos, tokens de acesso, segredos e eventos de auditoria. Existem usuários legítimos, administradores, integrações e atacantes que controlam suas próprias contas. Mapeie fronteiras entre navegador, provedor de identidade, gateway, serviço e banco. Um cliente malicioso pode modificar URLs, IDs, métodos e corpos HTTP, mesmo quando a interface oficial esconde esses controles.

Para cada operação sensível, declare **sujeito**, **ação**, **recurso**, **contexto** e o componente responsável pela decisão. 'Precisa estar autenticado' é regra insuficiente em aplicativo multi-tenant: usuário do tenant A não pode ler dados do B apenas por adivinhar um ID de pedido. O OWASP destaca falhas de autorização por objeto entre riscos centrais em APIs [1].

## Autorização por objeto em cada requisição

Considere GET /orders/42. Valide credenciais, obtenha o principal autenticado e procure o pedido respeitando o **tenant e as regras de acesso**. Se o registro não existe ou está fora do escopo, responda conforme política sem revelar detalhes privados. Não confie em tenant_id enviado pelo cliente quando o tenant efetivo deve derivar de credenciais validadas ou associação mantida pelo servidor.

![Autorização considera principal e recurso dentro da fronteira autoritativa.](/diagrams/api-authorization-boundary.svg)

~~~python
from dataclasses import dataclass

@dataclass(frozen=True)
class Principal:
    usuario: int
    tenant: int
    papeis: frozenset[str]

def pode_ler_pedido(principal, pedido):
    if principal is None or pedido is None:
        return False
    if pedido["tenant"] != principal.tenant:
        return False
    return pedido["proprietario"] == principal.usuario or "auditor_tenant" in principal.papeis

alice = Principal(10, 2, frozenset())
pedido = {"tenant": 2, "proprietario": 10}
outro_tenant = {"tenant": 3, "proprietario": 10}
assert pode_ler_pedido(alice, pedido)
assert not pode_ler_pedido(alice, outro_tenant)
assert not pode_ler_pedido(Principal(11,2,frozenset()), pedido)
assert pode_ler_pedido(Principal(11,2,frozenset({"auditor_tenant"})), pedido)
~~~

Isso é apenas um **predicado de política**, não implementação completa de verificação de identidade. Pressupõe principal e pedido vindos de fontes confiáveis, e papel auditor_tenant limitado ao tenant apropriado. Uma política real pode considerar situação, sigilo, concessões explícitas e delegações. O invariante de segurança é que alterar um ID arbitrário não amplie os privilégios do usuário autenticado.

## OAuth delega; JWT é um formato

OAuth 2.0 oferece fluxos de autorização em que clientes obtêm acesso a recursos protegidos. Um **access token** é destinado ao servidor de recursos; não se confunde com o **ID token** de OpenID Connect, que comunica autenticação ao cliente. JWT é um possível **formato** de declarações, não um protocolo completo de autorização. Alguns tokens de acesso são opacos e demandam introspecção segundo o mecanismo do emissor [2][3].

Ao usar JWT assinado, valide emissor confiável, audiência, algoritmo e chaves permitidos, vencimento e eventual restrição de início de validade. Interpretar JSON do token **sem conferir assinatura** não autentica ninguém. Nunca aceite chave ou algoritmo escolhidos pelo atacante apenas com base num cabeçalho não confiável. Rotação de chaves, margem de relógio, revogação e credenciais curtas exigem política explícita.

## Fluxo moderno de autorização

Em clientes OAuth que usam redirecionamento, a prática de segurança atual favorece código de autorização com proof key for code exchange (PKCE) e conferência estrita da redirect URI. Clientes públicos devem utilizar PKCE; clientes confidenciais também recebem recomendação de adotá-lo. Não introduza fluxos legados inseguros de implicit ou password apenas para reduzir código. Estado/nonce por transação, ou defesa equivalente prevista no fluxo escolhido, protege contra substituição de requisição e parte dos ataques CSRF [2].

Não inclua tokens em parâmetros de URL, logs, analytics ou mensagens de erro. Sessões mantidas no servidor podem simplificar revogação e gerenciamento de segredos para aplicações web tradicionais. Cookies no navegador trazem questões de CSRF; tokens bearer em JavaScript trazem risco de roubo via XSS. Não existe regra universal de que JWT seja sempre mais seguro.

## Proteção em camadas

Valide formatos de entrada, invariantes de negócio, tamanho de payload e custo computacional. Use parâmetros em consultas SQL em vez de concatenar strings recebidas. Limite destinos acessados pelo servidor para reduzir SSRF, especialmente endereços internos e serviços de metadados. Conceda a integrações apenas os privilégios necessários e mantenha separação de responsabilidades em operações administrativas.

| Risco | Exemplo | Controle |
| --- | --- | --- |
| Autorização por objeto quebrada | Trocar ID do pedido | Conferir principal contra *recurso obtido* |
| Exposição de dados excessiva | Retornar campos privados extras | Schema de resposta por privilégio |
| Autenticação defeituosa | Aceitar token não verificado | Assinatura, emissor, audiência e tempo |
| Exaustão de recursos | Filtro caríssimo | Limitar custo, concorrência e paginação |
| SSRF | Buscar URL arbitrária recebida | Restringir destinos e resolução |

Rate limiting ajuda contra esgotamento, mas não substitui autorização. CORS é uma **política de navegador**, não bloqueio de clientes HTTP arbitrários que desejam realizar requisições [1].

## Auditoria, privacidade e gestão de chaves

Logs de segurança devem guardar ator, operação, recurso, resultado e correlação sem registrar senha, access token ou dados pessoais desnecessários. Tentativas indevidas devem ser detectáveis sem expor existência de recursos sigilosos nas respostas. Auditoria só é confiável se o aplicativo não puder reescrever facilmente seu próprio histórico.

Defina resposta a credencial comprometida: revogar ou expirar, rotacionar chaves cuidadosamente, invalidar sessões afetadas e analisar acessos. Reduzir a validade de JWT limita parte do risco, mas não revoga instantaneamente token já emitido. Refresh tokens de longa duração exigem rotação e detecção de repetição conforme recursos do emissor [2].

## Verifique a fronteira real

Teste o predicado e, depois, o endpoint HTTP com configuração real de autenticação e restrições de banco. Inclua dois usuários do mesmo tenant, usuário de outro tenant, credenciais revogadas, assinatura falsificada, claims ausentes, tokens expirados e associação de usuário alterada durante a sessão. Botão oculto no frontend não deve ser barreira principal. Se privilégios mudam durante sessão ativa, defina quando a nova regra passa a valer e se caches podem devolver decisões obsoletas.

## Exercícios e verificação

1. Por que assinatura válida e scope amplo não autorizam automaticamente ler qualquer ID de pedido?
2. Projete teste de integração comprovando que tenant A não lê registros de B, mesmo quando IDs numéricos se sobrepõem.
3. Diferencie ID token, access token, JWT assinado e token opaco. Quem valida cada um?
4. Por que configurar CORS não impede curl de enviar requisições não autorizadas?
5. Monte plano de resposta ao vazamento de refresh token sem supor que trocar apenas a chave de assinatura resolve todas as sessões.
