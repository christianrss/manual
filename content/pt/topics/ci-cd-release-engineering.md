---
id: ci-cd-release-engineering
title: "CI/CD e engenharia de releases: canary, schema e rollback"
description: "Projete gates de CI, artefatos imutáveis, canary, migrações seguras, segredos e procedimentos de recuperação."
category: engineering
difficulty: intermediate
updated: 2026-10-09
prerequisites: [testing-strategies, production-incident-response]
sources:
  - {title: "Google SRE Workbook — Canarying Releases", url: "https://sre.google/workbook/canarying-releases/", kind: "engineering workbook"}
  - {title: "GitHub Docs — Deployment environments", url: "https://docs.github.com/en/actions/concepts/workflows-and-actions/deployment-environments", kind: "official CI/CD documentation"}
---
Integração contínua (CI) verifica cada mudança proposta por controles automatizados. Entrega contínua torna um artefato testado **apto a ser publicado**; implantação contínua libera automaticamente mudanças aprovadas. Engenharia de releases controla como código, dependências, artefatos, aprovações, migrações de banco e tráfego de produção evoluem. São atividades relacionadas, não sinônimos. Pipeline verde demonstra apenas as condições efetivamente testadas; não prova implantação segura sob qualquer carga real [1][2].

## Rastreie da alteração até a produção

Um fluxo confiável é: commit revisado → build reproduzível → testes unitários/contratos → análise estática/segurança → artefato versionado imutável → ambiente controlado → implantação parcial → avaliação por métricas → expansão ou rollback. Quando possível, promova o **mesmo artefato** entre ambientes, evitando recompilar dependências diferentes sem revisão.

Fixe versões e registre hash/digest do artefato. Proteja credenciais com segredos por ambiente, permissões restritas e autenticação de vida curta. GitHub Actions possui ambientes, aprovação, regras de proteção e controle de concorrência, mas tudo isso precisa ser configurado e testado explicitamente [2]. A presença de workflow YAML não prova que existe um gate de produção.

## Quais checks bloqueiam merge?

Testes unitários rápidos oferecem feedback curto. Build e lint verificam sintaxe e convenções. Type checking verifica contratos declarados conforme capacidades da linguagem. Integração testa constraints reais de banco; contratos entre cliente/provedor detectam deriva de APIs. Pequena suíte E2E cobre fluxos críticos, e segurança/performance podem ter etapas específicas. Atribua **responsáveis** pelos testes instáveis em vez de permitir retry indefinido até todos passarem.

A matriz de testes acompanha riscos. Alteração puramente visual pode dispensar carga de banco, enquanto cálculo monetário e isolamento de transações exigem concorrência e falhas específicas. Gates devem ser determinísticos o bastante para separar regressão de pane de infraestrutura. Se existe bypass emergencial, audite quem o utilizou e como os testes ignorados serão compensados.

## Canary, controle e liberação progressiva

Uma **implantação canary** publica mudança a parte limitada de produção, compara com grupo de controle e amplia apenas se sinais predefinidos indicarem segurança [1]. Etapas como 1%, 5%, 25% e 100% são exemplos, não padrão universal. Escolha janelas suficientes para carga representativa e preserve mecanismos de rollback.

Observe taxa de erros, p95/p99, saturação e um indicador próprio do negócio. Compare canary e controle com **misturas de tráfego comparáveis**; volume pequeno pode parecer saudável por acaso. Canary sem requisições não recebe autorização para expansão só por mostrar zero erros.

![Gates de CI promovem artefato imutável por avaliação canary com possibilidade de rollback.](/diagrams/cicd-rollout.svg)

## Guardrail canary propositalmente simples

A função pura representa **exercício didático**, não inferência estatística pronta para produção. Exige amostra mínima nos dois grupos, interrompe canary claramente pior por limiares absolutos de erro e libera os demais para revisão. Não calcula confiança estatística nem verifica latência, sazonalidade ou assimetria de tráfego; decisões reais podem exigir teste sequencial e modelos de incerteza.

~~~python
def decisao_rollout(erros_canary, total_canary,
                    erros_controle, total_controle):
    valores = (erros_canary, total_canary, erros_controle, total_controle)
    if any(not isinstance(v, int) or v < 0 for v in valores):
        raise ValueError("contagens inteiras nao negativas")
    if erros_canary > total_canary or erros_controle > total_controle:
        raise ValueError("erros superam amostras")
    if min(total_canary, total_controle) < 200:
        return "aguardar"
    taxa = erros_canary / total_canary
    base = erros_controle / total_controle
    if taxa > 0.02 or taxa - base > 0.01:
        return "reverter"
    return "apto_para_revisao"

assert decisao_rollout(1, 1000, 2, 1000) == "apto_para_revisao"
assert decisao_rollout(40, 1000, 2, 1000) == "reverter"
assert decisao_rollout(0, 25, 1, 1000) == "aguardar"
try:
    decisao_rollout(11, 10, 0, 100)
    assert False
except ValueError:
    pass
~~~

O último estado significa *apto para outra avaliação humana ou automática*, não promoção garantida. Usar somente taxa de erros é perigoso quando uma cobrança duplicada ou violação de privacidade afeta poucas chamadas, mas representa incidente crítico.

## Evolução de schema em deploy gradual

Rollback de código pode se tornar inviável se a versão nova altera destrutivamente o schema compartilhado. Use **expandir → migrar → contrair** para mudanças incompatíveis. Exemplo: renomear `customer_name` para `buyer_name`; primeiro acrescente campo novo opcional; publique leitores compatíveis com ambos; faça backfill; migre escritores sob política explícita; verifique todos os leitores ativos; só então retire campo antigo.

Durante coexistência, escrita dupla exige **autoridade única e política de conciliação**. Atualizar duas colunas em transações assíncronas desconectadas gera divergência. Na mesma linha relacional, uma transação pode atualizar ambas; se serviços de versões diferentes escrevem valores conflitantes, exija versionamento e evite sobrescrita de fonte autoritativa por leitor desatualizado.

Migração online ainda pode bloquear tabelas ou consumir I/O, conforme motor, versão, operação e tráfego. Teste em dados representativos, observe atraso de réplica e mantenha restauração validada. Backup não equivale a rollback; restaurá-lo pode perder escritas válidas posteriores.

## Rollback, flags e efeitos irreversíveis

Reverter binário muda versão da aplicação, não o passado. Não desfaz email enviado, pagamento capturado nem dado excluído. Feature flags podem desligar um fluxo rapidamente, mas criam complexidade de configuração e ciclo de vida. Registre dono, padrão e prazo de remoção da flag; opções eternas geram branches ocultos sem cobertura.

Incidentes podem exigir **roll forward** para corrigir registros e ao mesmo tempo interromper tráfego do recurso quebrado. Defina RPO e RTO de dados separadamente da disponibilidade HTTP. Canary limita alcance do impacto, mas pode gerar efeitos irreversíveis mesmo com público pequeno.

## Segurança, cadeia de suprimentos e auditoria

Runners CI podem executar código hostil de pull requests. Restrinja tokens, não exponha segredos de deploy a forks não confiáveis, fixe ações/dependências confiáveis, registre proveniência quando possível e controle promoção de artefatos. Acesso a produção deve depender de identidade auditável e política de ambiente, não credencial pessoal compartilhada [2].

Guarde por release SHA de commit, digest do artefato, versão de migração, início/fim do rollout, aprovação quando exigida, coortes afetadas, guardrails medidos e ação de rollback. Isso ajuda a relacionar alteração e regressão sem depender de memória. Recompilar código antigo não garante bits idênticos sem inputs reproduzíveis.

## Falhas e checklist de release

| Falha | Proteção | Métrica |
| --- | --- | --- |
| Testes passam, migração falha | Ensaio em dados representativos | Locks e lag |
| Canary sem carga | Amostra mínima e aguardar | Volume exposto |
| Cache oculta defeitos | Coortes comparáveis | Cache hit e p99 |
| Rollback incompatível com schema | Expand/contract | Versões misturadas |
| Pagamento externo já executado | Compensação e conciliação | Referências do provedor |
| Segredo exposto no CI | Menor privilégio e ambientes | Auditoria de acesso |

Maturidade de pipeline depende da capacidade de recuperação e da segurança da mudança, não apenas da frequência de implantação. Automatizar entrega vale quando validação e rollback recebem o mesmo rigor.

## Exercícios e verificação

1. Diferencie entrega contínua de implantação contínua e identifique quem autoriza promover artefato.
2. Por que o guardrail devolve `aguardar` com apenas 25 chamadas e zero erros?
3. Planeje expand-migrate-contract compatível com duas versões da aplicação rodando simultaneamente.
4. Por que rollback de código não desfaz pagamento no PSP e qual conciliação seria necessária?
5. Liste dados mínimos do artefato, migração e telemetria para investigar incidente após release.

**Capítulos relacionados:** [Estratégias de testes](/pt/topics/testing-strategies/), [incidentes](/pt/topics/production-incident-response/), [contratos de API](/pt/topics/api-contracts-pagination/) e [replicação](/pt/topics/database-replication-failover/) fundamentam as decisões [1][2].
