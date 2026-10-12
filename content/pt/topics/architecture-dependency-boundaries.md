---
id: architecture-dependency-boundaries
title: "Arquitetura de software: fronteiras de dependência e projeto modular"
description: "Derive arquiteturas em camadas e portas/adaptadores, imponha dependências entre módulos, registre decisões e teste um monólito modular."
category: engineering
difficulty: intermediate
updated: 2026-10-12
prerequisites: [clean-code-cohesion-coupling, solid-dependency-inversion]
sources:
  - {title: "Microsoft Learn — Architectural principles", url: "https://learn.microsoft.com/en-us/dotnet/architecture/modern-web-apps-azure/architectural-principles", kind: "official engineering guide"}
  - {title: "Alistair Cockburn — Hexagonal architecture", url: "https://alistair.cockburn.us/hexagonal-architecture/", kind: "original architecture article"}
  - {title: "Martin Fowler — Monolith First", url: "https://martinfowler.com/bliki/MonolithFirst.html", kind: "original engineering essay"}
---
Arquitetura de software define **as restrições sob as quais componentes podem mudar, comunicar-se e falhar**. Organização de classes não basta: dois programas com diagramas idênticos podem ter propriedades operacionais muito diferentes se um chama funções locais e outro atravessa a rede. Uma decisão arquitetural útil preserva invariantes críticos, limita efeitos de mudança e admite verificação. Princípios arquiteturais distinguem separação de responsabilidades e direção de dependências da escolha de frameworks [1].

## Comece pelas mudanças e pelas falhas exigidas

Considere um sistema pequeno de pedidos com precificação, reserva de estoque, faturas e interface HTTP. Suponha que a primeira versão seja uma única aplicação implantável com um banco transacional. A regra de negócio determina que o total cobrado deve resultar da soma de preços de linhas validadas e que uma reserva confirmada não pode ultrapassar o estoque disponível. O framework HTTP não deve decidir preços; a política de preços não deveria importar o cliente SQL. São restrições arquiteturais, não preferências de nomes de pastas.

Antes do desenho, registre três perguntas: quem é responsável por cada invariante, qual componente possui autoridade para alterar os dados e o que ocorre quando a dependência falha? O módulo de pedidos pode coordenar operações, mas não deve alterar o estoque acessando tabelas privadas. Isso vale dentro do monólito: uma fronteira define dependências permitidas e não necessariamente uma chamada de rede.

## Compare arquitetura em camadas e portas/adaptadores

Uma arquitetura em camadas separa apresentação, aplicação, domínio e infraestrutura. Um possível fluxo de execução é controlador HTTP → caso de uso → regra de domínio → repositório. A **direção das chamadas** expressa colaboração em tempo de execução; a **direção das dependências no código-fonte** define se as políticas podem ser compiladas e testadas sem a infraestrutura. Essas direções não precisam coincidir.

Num projeto ingênuo, a entidade de domínio instancia diretamente um repositório SQL. A interface pode parecer organizada, mas o núcleo continua dependente da borda. Na arquitetura hexagonal, uma porta é um contrato comportamental estreito definido pela aplicação ou domínio; um adaptador implementa esse contrato na fronteira externa [2]. O adaptador de banco implementa persistência e o controlador web atua como adaptador de entrada. Essa inversão reduz acoplamento do código sem eliminar as consequências de uma falha de banco.

Uma porta não exige obrigatoriamente classe abstrata: Python Protocol, argumento de função e interfaces pequenas podem representar contratos. Criar adaptadores para cálculos puros sem possibilidade real de variação introduz complexidade gratuita. Cada fronteira deve corresponder a uma mudança previsível, uma oportunidade de teste, regra de segurança ou exigência de implantação.

## Monólito modular é escolha deliberada

Um monólito modular possui módulos compreensíveis separadamente, mas roda como uma unidade implantável. Chamadas locais e uma transação ACID podem preservar certos invariantes entre módulos, desde que eles se comuniquem por contratos públicos. Não há implantação independente nem isolamento de falha de processo entre módulos. Extrair serviços introduz timeouts de rede, compatibilidade de versões, telemetria distribuída, operações adicionais e consistência entre bancos. O argumento de Fowler a favor de começar por um monólito alerta para esses custos antes de compreender os limites do sistema [3].

Monólito modular não autoriza alterações arbitrárias em tabelas compartilhadas. Se checkout modifica diretamente linhas internas de estoque, o proprietário perde a capacidade de impor suas regras. Mesmo num banco único, defina autoridade de escrita e pontos de integração. Ao extrair um módulo para outro processo, uma chamada local que passa a atravessar a rede **muda de contrato de falha**: timeout pode deixar resultado remoto desconhecido.

## Transforme regras de dependência em testes

O verificador abaixo usa um grafo orientado de módulos. Uma aresta A → B significa que A importa B. A tabela de permissões expressa a política de uma aplicação hipotética; não é regra universal para todos os projetos. O programa rejeita módulos desconhecidos e arestas proibidas, inclusive domínio importando adaptador HTTP.

~~~python
ALLOWED = {
    "http": {"application"},
    "application": {"domain", "ports"},
    "domain": set(),
    "ports": {"domain"},
    "sql_adapter": {"ports", "domain"},
    "bootstrap": {"http", "application", "sql_adapter"},
}

def check_imports(imports):
    for source, targets in imports.items():
        if source not in ALLOWED:
            raise ValueError("unknown source module")
        for target in targets:
            if target not in ALLOWED:
                raise ValueError("unknown target module")
            if target not in ALLOWED[source]:
                raise ValueError("forbidden dependency: " + source + " -> " + target)
    return True

good = {
    "http": {"application"}, "application": {"domain", "ports"},
    "sql_adapter": {"ports"}, "bootstrap": {"sql_adapter", "http"}
}
assert check_imports(good)
for bad in ({"domain": {"http"}}, {"http": {"sql_adapter"}},
            {"application": {"missing"}}):
    try:
        check_imports(bad)
    except ValueError:
        pass
    else:
        raise AssertionError("invalid dependency was accepted")
~~~

Se V representa os módulos declarados e E as arestas de importação fornecidas, a verificação percorre O(V + E) elementos quando cada módulo aparece uma vez, com O(1) de memória adicional além das variáveis locais e da política fixa. Para políticas dinâmicas, armazená-las e conferi-las também tem custo. Este modelo verifica apenas *arestas permitidas*: não detecta ciclos internos permitidos, chamadas dinâmicas, reflexão ou qualidade semântica dos contratos. Em produção, testes arquiteturais precisam extrair o grafo dos arquivos reais em vez de confiar num grafo fornecido manualmente.

## Não confunda modularidade com correção transacional

Imagine checkout lendo estoque=1, validando disponibilidade e escrevendo estoque=0. Duas requisições simultâneas podem ler 1 e ambas confirmar a reserva. Fronteiras impecáveis entre pacotes não evitam essa corrida. É necessário UPDATE condicional no banco, transação serializável com retry ou protocolo equivalente na autoridade de estoque. A fronteira da aplicação decide **quem pode solicitar** a reserva; concorrência e persistência decidem **se solicitações simultâneas serão corretas**.

Da mesma forma, um repositório falso aprovado nos testes demonstra apenas um contrato local. Não comprova tratamento de deadlocks, requisições duplicadas, autorização, rollback ou repetição após timeout. Ao trocar adaptadores, execute testes de contrato com a implementação real para verificar as mesmas expectativas observáveis.

## Registre decisões e condições de revisão

Um registro de decisão arquitetural (ADR) deve informar contexto, decisão, alternativas, consequências e gatilho de revisão. Para o exemplo: escolher implantação modular única, porque transações entre módulos são exigidas e não foi medida necessidade de escala independente. Rejeitar inicialmente microsserviços, porque acrescentariam ambiguidade de rede. Reconsiderar após perfilamento demonstrar contenção de recursos, surgir exigência explícita de deploy independente ou tornar-se impossível manter autoridade sobre dados.

Meça acoplamento com evidências: quais módulos são alterados para introduzir novo provedor de pagamento, quais testes precisam rodar, quais equipes precisam aprovar e por onde falhas se propagam. Um diagrama escrito “baixo acoplamento” não constitui evidência. Se toda funcionalidade modifica helper compartilhado e esquema comum, a modularidade provavelmente é superficial.

## Antipadrões e contraexemplos

Uma interface de repositório com dezenas de operações pode vazar detalhes de tabela para o domínio; a inversão vira apenas cosmética. Um controlador enxuto pode autorizar tarde demais. Uma fachada pode ocultar várias escritas sem transação única. Microsserviço com banco próprio pode continuar altamente acoplado por cadeia síncrona obrigatória. Proibir toda colaboração entre módulos também pode levar à duplicação de regras. Mantenha interfaces pequenas, mas permita a cooperação necessária.

Estilos arquiteturais não formam uma escala de maturidade. Uma aplicação simples em camadas pode ser superior se a política de domínio é pequena e a equipe se beneficia de menos abstrações. Portas/adaptadores ajudam quando regras centrais precisam ser testadas diante de infraestrutura variável. Serviços independentes precisam justificar custos operacionais e de consistência.

## Exercícios e verificação

1. Adicione adaptador de relatório que lê pedidos. Decida se ele deve usar contrato público do módulo ou SQL privado e descreva as consequências para propriedade dos dados.
2. Acrescente publicador de eventos. Defina uma porta e explique como publicar depois do commit pode perder eventos; proponha outbox transacional.
3. Tente inserir domínio → sql_adapter no grafo. Confirme a reprovação e explique qual princípio arquitetural ela representa.
4. Projete teste concorrente de duas reservas para uma unidade. Explique por que o verificador de dependências não prova esse invariante.
5. Escreva ADR comparando monólito em camadas, monólito modular e microsserviços com carga, equipe e falhas explicitadas. Defina uma métrica que possa mudar a escolha.

Continue por [SOLID e contratos](/pt/topics/solid-dependency-inversion/), [fronteiras de serviço](/pt/topics/service-boundaries/) e [método de System Design](/pt/topics/system-design-process/).