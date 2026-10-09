---
id: formal-model-checking
title: "Verificação formal: invariantes, exploração de estados e TLA+"
description: "Aprenda safety, liveness, atomicidade e refinamento com exploração finita de estados num protocolo concorrente de reservas e fundamentos TLA+."
category: engineering
difficulty: advanced
updated: 2026-10-09
prerequisites: [low-level-design, concurrency-synchronization, database-consistency]
sources:
  - {title: "TLA+ Tools — TLC model checker", url: "https://github.com/tlaplus/tlaplus", kind: "official tool repository"}
  - {title: "TLA+ Example Specifications", url: "https://github.com/tlaplus/Examples", kind: "official example collection"}
---
Testes executam entradas e escalonamentos escolhidos. **Modelagem formal** representa estados, transições e propriedades de um sistema com precisão suficiente para raciocinar sobre *todos os comportamentos dentro de um modelo definido*. Um model checker procura sistematicamente contraexemplos num espaço finito. Isso não prova automaticamente que a implementação está correta: o resultado depende das ações modeladas, hipóteses ambientais, limites e correspondência entre código e especificação abstrata [1].

## Defina estado, transição e propriedade

Um **estado** atribui valores a variáveis relevantes, como proprietário de um assento e ponto de execução de cada worker. O **predicado inicial** define estados permitidos na partida. Uma **relação de próximo estado** define quais pares de estados podem ocorrer numa etapa atômica. Um comportamento é uma sequência de estados que satisfaz a relação, possivelmente infinita. Propriedades de correção restringem esses comportamentos.

Uma propriedade de **safety** diz que algo ruim nunca acontece; um prefixo finito pode refutá-la. 'Nunca há dois clientes com o mesmo assento confirmado' é safety. Uma propriedade de **liveness** diz que algo bom acaba acontecendo, como toda requisição continuamente elegível ser decidida. Observar uma sequência finita sem conclusão não refuta sozinho liveness: progresso exige hipóteses de escalonamento, falhas e justiça.

## Modele check-then-commit não atômico

Considere dois clientes A e B tentando reservar um assento. Um protocolo inseguro executa duas operações atômicas separadas: (1) ler que está livre e (2) confirmar a reserva do cliente. Entre as etapas, outro cliente também pode ler livre. Testes com requisições sempre sequenciais não revelam a corrida. O modelo precisa permitir **intercalação**: A consulta livre → B consulta livre → A confirma → B confirma.

![Intercalação insegura e reserva atômica possuem resultados distintos para o mesmo invariante.](/diagrams/formal-reservation-states.svg)

O invariante é quantidade de proprietários confirmados ≤1. Observe que até um ID final único é insuficiente se uma cobrança ou notificação externa é executada duas vezes. Inclua no estado cada efeito necessário para comprovar a afirmação de correção do negócio.

## Explore exaustivamente um protocolo finito em Python

O verificador limitado percorre estados alcançáveis de dois trabalhadores e retorna trace de violação. O estado contém ponto de execução de cada worker (0 antes da consulta, 1 após consulta, 2 terminado) e um booleano por reserva confirmada. As etapas são transições atômicas abstratas; Python é ferramenta para **explorar o modelo**, não evidência de todos os escalonamentos reais de CPU.

~~~python
from collections import deque

def explorar(commit_atomico):
    inicial = ((0, 0), (False, False))
    fronteira = deque([(inicial, [])])
    vistos = {inicial}
    while fronteira:
        estado, historico = fronteira.popleft()
        etapas, reservas = estado
        if sum(reservas) > 1:
            return historico
        for ator in range(2):
            if etapas[ator] == 2:
                continue
            novas_etapas = list(etapas)
            novas_reservas = list(reservas)
            if etapas[ator] == 0 and not any(reservas):
                novas_etapas[ator] = 1
                evento = f"{ator}:consulta"
            elif etapas[ator] == 1:
                if not commit_atomico or not any(reservas):
                    novas_reservas[ator] = True
                novas_etapas[ator] = 2
                evento = f"{ator}:confirma"
            else:
                continue
            proximo = (tuple(novas_etapas), tuple(novas_reservas))
            if proximo not in vistos:
                vistos.add(proximo)
                fronteira.append((proximo, historico + [evento]))
    return None

contraexemplo = explorar(commit_atomico=False)
assert contraexemplo is not None
assert set(contraexemplo) == {
    "0:consulta", "1:consulta", "0:confirma", "1:confirma"
}
assert explorar(commit_atomico=True) is None
~~~

No modelo inseguro, as duas consultas passam antes de qualquer commit. O menor contraexemplo contém quatro transições. No modelo corrigido, **a verificação atômica no commit** impede duas reservas confirmadas. Num banco real, essa operação atômica depende de constraint/transação ou autoridade equivalente; checar variável numa função Python não assegura atomicidade distribuída.

## Por que explorar estados supera alguns testes

Suponha n clientes com k estados locais relevantes e algumas variáveis compartilhadas. Um limite simples para combinações locais é k^n antes de considerar o estado compartilhado. Enumerar todas as possibilidades rapidamente se torna caro: é a **explosão de estados**. Mesmo assim, modelos pequenos revelam sequências que testes escolhidos manualmente raramente encontram. O verificador deve guardar estados visitados e fornecer um trace pequeno e interpretável.

O explorador Python verifica alcançabilidade finita de sua condição de **safety**, não liveness nem justiça. Ele não assegura nada sobre partições de rede, queda de processo, efeitos externos duplicados ou persistência durável, porque esses eventos não fazem parte do modelo. Amplie o estado antes de extrair conclusões sobre esses riscos.

## TLA+ descreve comportamentos declarativamente

TLA+ é uma linguagem para especificar sistemas com ações matemáticas, conjuntos e fórmulas temporais. O TLC explora estados e verifica invariantes e propriedades temporais de instâncias finitas [1]. Numa reserva, pode-se declarar `owner = None`, uma ação que altera atomicamente assento sem dono para um cliente, e uma propriedade de que o dono está ausente ou corresponde a cliente autorizado. A implementação precisa ser ligada ao modelo por um **mapeamento de refinamento**, mostrando como seu estado representa o proprietário abstrato.

O repositório oficial de exemplos TLA+ reúne modelos de sistemas e algoritmos de complexidade variada [2]. Verificar exaustivamente dois clientes não demonstra automaticamente correção para qualquer quantidade de clientes. Prova parametrizada ou argumento de limite seguro de instâncias é trabalho adicional.

## Um contrato mínimo ilustrativo em TLA+

~~~text
VARIABLE owner
Init == owner = "none"
Reserve(c) ==
  /\ owner = "none"
  /\ owner' = c
Next == \E c \in {"A", "B"} : Reserve(c)
Safety == owner \in {"none", "A", "B"}
~~~

O fragmento ilustra **guard e atualização atômicos** e **não é apresentado como módulo TLA+ executável completo**: TLC também requer módulo, tupla de variáveis, configuração e tratamento de stuttering. Além disso, a propriedade Safety isolada é fraca: uma variável com um proprietário não representa duas confirmações independentes. Para verificar dupla reserva, inclua explicitamente os estados de confirmação dos clientes, como faz o explorador Python.

## Fairness e progresso têm obrigações diferentes

Se o escalonador pode postergar o cliente B indefinidamente, 'todos eventualmente terminam' não está garantido mesmo sem dupla reserva. **Weak fairness** aproximadamente impede que uma ação permanentemente habilitada seja ignorada para sempre; **strong fairness** trata ações repetidamente habilitadas sob condições adicionais. Não as adicione indiscriminadamente: uma mensagem de rede pode nunca ser entregue ou o cliente pode desistir. Um modelo com banco sempre disponível não comprova progresso sob indisponibilidade arbitrária.

Uma especificação correta separa hipóteses de safety e de progresso. Por exemplo: uma constraint única pode preservar exclusividade de assento sob transação mesmo com concorrência elevada, enquanto uma fila saturada pode postergar determinado cliente indefinidamente se não houver garantias de admissão e escalonamento.

## Contraexemplos, refinamento e revisão

Um **trace de contraexemplo** apresenta passos permitidos que levam à violação. Deve virar teste de regressão quando a implementação permite forçar esse escalonamento. A falha pode indicar bug da própria *especificação*, não só do projeto; reveja hipóteses com especialistas. Da mesma forma, modelo aprovado que omite uma transição de falha relevante passa falsa segurança.

| Técnica | O que demonstra | O que não demonstra |
| --- | --- | --- |
| Teste unitário | Comportamento em casos escolhidos | Todos os escalonamentos e entradas |
| Model checker finito | Propriedades dos estados modelados | Falhas omitidas e escala ilimitada |
| Prova matemática | Teorema segundo axiomas | Mapeamento correto do código sozinho |
| Métricas de produção | Resultados realmente observados | Ausência de bugs raros alcançáveis |

## Exercícios e verificação

1. Explique por que consulta(A), consulta(B), confirma(A), confirma(B) viola o invariante.
2. Amplie explorador para terceiro cliente, meça estados visitados e discuta crescimento.
3. Acrescente contagem de cobranças externas e mostre como reserva única ainda pode acompanhar duas cobranças.
4. Declare propriedade de liveness e suas hipóteses necessárias de escalonamento e rede.
5. Explique qual mapeamento para a implementação seria necessário para confiar no commit atômico corrigido.

**Leituras relacionadas:** [Concorrência](/pt/topics/concurrency-synchronization/) aborda intercalação; [consistência em bancos](/pt/topics/database-consistency/) trata anomalias de transação; [low-level design](/pt/topics/low-level-design/) formaliza transições locais.
