---
id: modular-programming-interfaces
title: "Programação modular: coesão, interfaces explícitas e funções puras"
description: "Aprenda a decompor programas em módulos coesos, separar cálculos de entrada/saída e testar contratos sem depender de frameworks."
category: engineering
difficulty: foundational
updated: 2026-10-12
prerequisites: [programming-control-flow-functions, programming-semantics-contracts]
sources:
  - {title: "Python tutorial — Modules", url: "https://docs.python.org/3/tutorial/modules.html", kind: "official programming tutorial"}
  - {title: "Python language reference — Import system", url: "https://docs.python.org/3/reference/import.html", kind: "official language reference"}
  - {title: "Python standard library — unittest", url: "https://docs.python.org/3/library/unittest.html", kind: "official testing documentation"}
  - {title: "Python standard library — decimal", url: "https://docs.python.org/3/library/decimal.html", kind: "official numeric documentation"}
---
Um programa se torna difícil de modificar quando cada função lê variáveis globais, abre arquivos, formata resultados e executa cálculos de negócio simultaneamente. **Programação modular** separa responsabilidades entre funções e módulos e torna sua colaboração explícita. Esse princípio é anterior a orientação a objetos, inversão de dependências e serviços distribuídos: um programa procedural pequeno pode ter boa arquitetura sem classes. Módulos Python são namespaces carregados pelo sistema de importação, e seus nomes públicos constituem interfaces práticas para consumidores [1][2].

## Funções, módulos e fronteiras de programas

Uma função abstrai uma computação por um nome e um contrato. Um módulo reúne definições relacionadas em arquivo-fonte e namespace próprios. Um pacote organiza módulos sob um caminho comum de importação. São níveis diferentes de organização: colocar quarenta funções sem relação num arquivo não as torna coesas; dividir um cálculo de três linhas em vários pacotes não garante qualidade.

Uma fronteira útil possui objetivo conciso, hipóteses de entrada, retorno e efeitos colaterais definidos. Um parser interpreta representações brutas. Um módulo de cálculo processa valores validados. Um apresentador formata resultados. Uma função de composição ou entrada conecta essas etapas com a entrada e saída reais. Essa separação torna cada componente compreensível sem obrigar o leitor a reproduzir o programa inteiro.

## Coesão e acoplamento

**Coesão** pergunta se os elementos de um módulo pertencem à mesma responsabilidade. **Acoplamento** pergunta quanto um componente precisa conhecer sobre outro. Alta coesão e acoplamento limitado frequentemente tornam mudanças mais locais, mas não são indicadores calculados pela quantidade de arquivos. Módulo que interpreta texto, consulta banco, envia email e calcula médias possui razões independentes para mudar. Módulo cuja única operação passa por quinze camadas triviais pode ter indireção excessiva.

Acoplamento não se limita a imports. Dois módulos podem importar apenas pequenas funções um do outro e ainda compartilhar estado global implícito ou depender do formato exato de apresentação. Por outro lado, importar uma biblioteca padrão não indica necessariamente acoplamento nocivo. A questão é se uma mudança de responsabilidade obriga consumidores não relacionados a mudar.

## Funções puras e efeitos colaterais

Uma **função pura** devolve o mesmo resultado para os mesmos valores de entrada, dentro do modelo declarado, sem produzir efeitos observáveis externos. Cálculos e validações são candidatos naturais. Ler arquivos, imprimir, chamar serviços e atualizar estado externo geram efeitos colaterais. Nem toda função pode ou deve ser pura: aplicações precisam interagir com o mundo. A decisão de projeto é deixar esses efeitos visíveis em fronteiras pequenas, enquanto cálculos comuns não dependem deles.

Função que lê `global current_temperature` possui entrada escondida. Outra que escreve logs, altera argumento e devolve número apresenta três efeitos observáveis, não um. Prefira parâmetros e retornos explícitos sempre que possível. Argumento mutável não é copiado simplesmente porque o parâmetro recebe nome diferente; valem as regras de associação de objetos do Python.

## Derive o projeto de um requisito simples

Considere exercício que processa leituras decimais de temperatura e calcula mínimo, máximo e média aritmética. A entrada é sequência finita de strings decimais não vazias. Entrada vazia é inválida para média; NaN e infinitos não representam medições neste modelo. Os cálculos centrais não devem abrir arquivo nem imprimir, pois serão reutilizáveis em aplicativo de linha de comando, notebook ou handler web. O exemplo não trata unidades, calibração de sensores e estatísticas temporais, que exigem contratos adicionais.

Identificamos quatro responsabilidades: interpretar texto, calcular valores, apresentar resumo e coordenar dependências reais de leitura/escrita. O orquestrador recebe funções como argumentos de leitura e gravação. É passagem de parâmetros comum, sem necessidade de classes abstratas ou framework de injeção de dependências.

~~~python
from decimal import Decimal, InvalidOperation

def parse_readings(lines):
    """Parse one decimal reading per line, without I/O side effects."""
    if not isinstance(lines, (list, tuple)):
        raise TypeError("lines must be a sequence")
    values = []
    for raw in lines:
        if not isinstance(raw, str) or not raw.strip():
            raise ValueError("invalid reading")
        try:
            number = Decimal(raw.strip())
        except InvalidOperation as exc:
            raise ValueError("invalid decimal") from exc
        if not number.is_finite():
            raise ValueError("non-finite reading")
        values.append(number)
    return tuple(values)

def summarize_readings(readings):
    """Return a value summary, never mutate input."""
    if not readings:
        raise ValueError("empty readings")
    total = sum(readings, Decimal("0"))
    return (min(readings), max(readings), total / len(readings))

def render_summary(summary):
    low, high, mean = summary
    return "min=" + str(low) + "; max=" + str(high) + "; mean=" + str(mean)

def run_report(read_lines, write_text):
    """Orchestrate data access; dependencies are passed explicitly."""
    readings = parse_readings(read_lines())
    result = render_summary(summarize_readings(readings))
    write_text(result)
    return result

messages = []
result = run_report(lambda: ["18.5", "20.0", "21.5"], messages.append)
assert result == "min=18.5; max=21.5; mean=20.0"
assert messages == [result]
assert parse_readings(["1", "2"]) == (Decimal("1"), Decimal("2"))
for invalid in (["NaN"], [""], ["abc"]):
    try:
        parse_readings(invalid)
    except ValueError:
        pass
    else:
        raise AssertionError("invalid reading accepted")
try:
    summarize_readings(())
except ValueError:
    pass
else:
    raise AssertionError("empty summary accepted")
~~~

## Verifique cada fronteira isoladamente

`parse_readings` define contrato de representação: lista ou tupla de strings decimais não vazias, retornando tupla imutável de valores Decimal finitos. Seus erros impedem cálculos com dados inválidos. `summarize_readings` supõe valores já validados e rejeita sequência vazia; não interpreta strings, imprime ou modifica dados. `render_summary` cuida exclusivamente da apresentação. `run_report` coordena e delega I/O às funções fornecidas.

A separação permite testes com lambda como leitor falso e `messages.append` como escritor falso. Não são necessários arquivos nem rede. Mais importante, o escritor falso permite verificar que houve **exatamente uma saída** e analisar seu texto. Testes de parsing e aritmética não precisam chamar o orquestrador. Integrações reais testariam se seus adaptadores de arquivos ou rede respeitam esses mesmos contratos [3].

## Complexidade e custo de recursos

Com n leituras e L caracteres de entrada no total, o parsing executa trabalho proporcional a L sob hipóteses de operações decimais com precisão limitada e armazena O(n) referências a valores. Calcular mínimo, máximo e soma percorre n elementos quantidade fixa de vezes, portanto O(n) operações aritméticas, com custo real influenciado pela precisão [4]. O formato do resultado possui estrutura constante, mas representações dos números podem crescer. O pipeline retém O(n) objetos Decimal no exemplo. Uma alternativa em streaming mantém soma, mínimo, máximo e quantidade com O(1) valores armazenados, porém modifica qual etapa responde por validação e erros.

Não conclua que funções puras são sempre mais rápidas ou que criar módulos melhora desempenho. O benefício principal aqui é **raciocínio local e testabilidade**. Perfilamento e requisitos de memória podem justificar combinar passagens posteriormente, desde que os contratos continuem verificáveis.

## Interfaces, imports e ciclos de dependência

Suponha os arquivos `parsing.py`, `statistics.py`, `presentation.py` e `main.py`. Uma direção simples é main → parser/estatística/apresentação; os módulos de cálculo puro não importam `main`. Se presentation importar main para obter configuração enquanto main importa presentation, uma importação circular pode encontrar estado parcialmente inicializado, conforme a ordem de execução [2]. Extraia constantes compartilhadas para módulo inferior ou passe por parâmetros, em vez de contornar ciclos com imports escondidos.

Interface não exige árvore de herança. Aqui, o leitor é qualquer função sem argumentos que devolva sequência, e o escritor é função que aceite string. Se esses contratos ficarem complexos, considere protocolos ou anotações e validação mais forte nos pontos externos. Anotações Python não impõem automaticamente todas as restrições em tempo de execução. Mantenha a interface do tamanho necessário ao consumidor.

## Contraexemplos e refatoração

Transformar cada expressão aritmética de uma linha em módulo separado fragmenta uma operação coesa. Para script descartável de três leituras, código direto pode ser mais simples que quatro abstrações. Em contraste, uma única função contendo abertura de arquivos, parsing, cálculos e apresentação é difícil de reutilizar ou testar sem efeitos. Escolha fronteiras diante de variações concretas: novo formato de entrada não deveria exigir reescrever a média; nova forma de apresentar não deve alterar parsing.

Refatoração precisa preservar um contrato observável explícito. Compare resultados, erros, quantidade de saídas e mutações antes e depois da extração. Adicionar método não é automaticamente melhoria se muda o momento de lançar exceções ou quais entradas inválidas são aceitas. Mantenha testes originais como evidência de regressão.

## Exercícios e verificação

1. Distribua o programa em quatro módulos físicos e desenhe apenas as setas de importação permitidas. Explique por que os módulos puros não devem importar `main`.
2. Altere a saída para JSON. Identifique qual módulo precisa mudar e por que a aritmética permanece igual.
3. Acrescente adaptador para ler CSV sem modificar `summarize_readings`; explicite o contrato de entrada do parser.
4. Construa um escritor falso que registra chamadas; prove que `run_report` escreve exatamente uma vez para entrada válida e nenhuma vez após erro de parsing.
5. Substitua a lista em memória por iterador e implemente acumulador em streaming. Explique o efeito de entrada vazia e erros tardios.
6. Compare dois projetos de módulos para script de cinco linhas e aplicação de dez mil linhas, identificando custos de abstração prematura.

Continue com [semântica](/pt/topics/programming-semantics-contracts/), [coesão e acoplamento](/pt/topics/clean-code-cohesion-coupling/) e [orientação a objetos](/pt/topics/object-oriented-design/).