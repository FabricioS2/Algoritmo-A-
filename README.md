# 🎯 Predador A → B — Simulador de Busca com Gulosa vs A*

Um simulador visual e interativo de algoritmos de busca em grade (grid), desenvolvido em **Python** com **Tkinter**, que coloca **duas estratégias clássicas de pathfinding** frente a frente em uma mesma arena:

- 🟣 **Busca Gulosa** (*Greedy Best-First Search*) — decide apenas pela heurística `h(n)`
- 🟠 **A\*** (*A-Star*) — decide por `f(n) = g(n) + h(n)` com heurística admissível

O programa gera tabuleiros aleatórios com obstáculos, executa ambas as buscas e **anima duas bolas simultaneamente** percorrendo as rotas encontradas, permitindo uma comparação visual direta de desempenho.

---

## 📸 Visão Geral

O simulador combina três pilares:

| Pilar | Descrição |
|-------|-----------|
| 🧠 **Algoritmos** | Gulosa e A\* implementados com fila de prioridade (`heapq`) |
| 🎨 **Visualização** | Tabuleiro estilo xadrez com rotas coloridas e bolas animadas |
| 🎵 **Experiência** | Trilha sonora procedural gerada em tempo real (`.wav`) |

---

## ✨ Funcionalidades

### 🧭 Algoritmos de Busca
- **Busca Gulosa (Greedy Best-First Search)** — explora apenas com base na heurística, rápida porém não ótima.
- **A\* (A-Star)** — considera custo acumulado `g` + heurística `h`, garantindo caminho de custo mínimo com a heurística usada.
- Movimentação em **8 direções** (ortogonal com custo `1.0`, diagonal com custo `√2`).
- Heurística **octile** admissível (nunca superestima o custo real).

### 🗺️ Geração Procedural de Tabuleiro
- Grade de **32×32** células.
- Obstáculos gerados aleatoriamente com **densidade ajustável** (0% a 40%).
- **Garantia de conectividade**: o algoritmo de geração sempre verifica (BFS) se existe caminho entre A e B; caso contrário, regenera.
- **Anti-linhas completas**: linhas/colunas/diagonais totalmente bloqueadas são desfeitas automaticamente para evitar tabuleiros travados.

### 🎬 Animação Simultânea
- Duas bolas (**uma rosa para a Gulosa**, **uma laranja para o A\***) percorrem suas respectivas rotas **ao mesmo tempo**, célula a célula.
- Velocidade ajustável em tempo real (2 a 120 passos/segundo).
- Rota da Gulosa desenhada em **ROSA** (`#E91E63`).
- Rota do A\* desenhada em **LARANJA** (`#FF6D00`).

### 📊 Métricas Comparativas
Uma tabela exibe lado a lado os resultados das duas estratégias:

| Métrica | Descrição |
|---------|-----------|
| ✅ **Caminho encontrado** | Sim/Não |
| 🔍 **Nós explorados** | Quantos nós saíram da fila de prioridade |
| ⏱️ **Tempo de busca (ms)** | Medido com `time.perf_counter()` |
| 💰 **Custo total do caminho** | Soma dos custos das arestas |
| 👣 **Passos (arestas)** | Número de movimentos no caminho final |

### 🎵 Música Procedural
- Melodia gerada **em tempo real** como arquivo WAV (onda senoidal com envelope de fade in/out).
- **Multiplataforma** — detecta automaticamente o player disponível:
  - Windows → `winsound`
  - macOS → `afplay`
  - Linux → `paplay`, `aplay`, `ffplay`, `mpg123` ou `play`
- Arquivo temporário removido automaticamente ao fechar (`atexit`).
- Toca em **loop** em uma thread daemon (não bloqueia a GUI).

---

## 💰 Custos de Movimento (Quanto vale sair e ir em cada direção)

O simulador utiliza uma grade **8-conectada**, ou seja, a partir de qualquer célula o agente pode se mover para **8 vizinhos**. Cada direção tem um custo específico, definido nas constantes `CUSTO_RETA` e `CUSTO_DIAG` do código:

```python
CUSTO_RETA = 1.0                # mover para cima, baixo, esquerda, direita
CUSTO_DIAG = math.sqrt(2.0)     # ≈ 1.41421356… (mover na diagonal)
```

### 📐 Tabela de custos por direção

| Direção | Δlinha (`dl`) | Δcoluna (`dc`) | Custo | Valor aproximado |
|---------|:-------------:|:--------------:|:-----:|:----------------:|
| ⬆️ Cima | −1 | 0 | `CUSTO_RETA` | **1,000** |
| ⬇️ Baixo | +1 | 0 | `CUSTO_RETA` | **1,000** |
| ⬅️ Esquerda | 0 | −1 | `CUSTO_RETA` | **1,000** |
| ➡️ Direita | 0 | +1 | `CUSTO_RETA` | **1,000** |
| ↖️ Diagonal superior-esquerda | −1 | −1 | `CUSTO_DIAG` | **1,414** |
| ↗️ Diagonal superior-direita | −1 | +1 | `CUSTO_DIAG` | **1,414** |
| ↙️ Diagonal inferior-esquerda | +1 | −1 | `CUSTO_DIAG` | **1,414** |
| ↘️ Diagonal inferior-direita | +1 | +1 | `CUSTO_DIAG` | **1,414** |

### 🧠 Por que `√2` na diagonal?

O custo diagonal é `√2 ≈ 1,414` porque corresponde à **distância euclidiana real** percorrida ao se mover em diagonal em uma grade de células quadradas de lado 1:

```
(0,0) → (1,1):  √(1² + 1²) = √2 ≈ 1.414
```

Usar exatamente esse valor é essencial para que o A\* encontre o **caminho geometricamente mais curto** — se a diagonal tivesse custo `1.0`, o algoritmo preferiria sempre "ziguezaguear" pela diagonal (efeito conhecido como *diagonal shortcut*). Se tivesse custo `2.0`, o algoritmo evitaria diagonais mesmo quando elas fossem mais eficientes.

### 🔎 Heurística Octile (consistente com os custos)

A heurística usada por ambas as buscas é a **distância octile**, projetada especificamente para grades 8-conectadas com esses custos:

```python
h(a, b) = (dl + dc) + (√2 − 2) · min(dl, dc)
```

Onde `dl = |a.linha − b.linha|` e `dc = |a.coluna − b.coluna|`.

Ela representa **o custo mínimo possível** para ir de `a` até `b` supondo terreno livre: o agente anda o máximo possível na diagonal (`min(dl, dc)` passos) e o restante em linha reta (`|dl − dc|` passos).

**Propriedades importantes:**
- ✅ **Admissível** — nunca superestima o custo real (por isso o A\* é ótimo).
- ✅ **Consistente (monotônica)** — satisfaz a desigualdade triangular, o que garante que nenhum nó precise ser reaberto.
- ✅ **Exata em terreno livre** — quando não há obstáculos, `h` coincide exatamente com o custo real do caminho.

### 📊 Exemplo prático

Do ponto **A = (0, 0)** até **B = (5, 3)** em terreno livre:

| Passos | Quantidade | Custo unitário | Subtotal |
|--------|:----------:|:--------------:|:--------:|
| Diagonais (↘) | `min(5, 3) = 3` | `√2 ≈ 1,414` | 4,242 |
| Retas (⬇) | `|5 − 3| = 2` | `1,000` | 2,000 |
| **Total do caminho ótimo** | **5 arestas** | — | **≈ 6,242** |

E a heurística octile para esse mesmo par retorna exatamente o mesmo valor:

```
h = (5 + 3) + (√2 − 2) · 3
  = 8 + (−0,586) · 3
  = 8 − 1,757
  ≈ 6,243   ✔
```

Como `h` coincide com o custo real, o A\* encontra o caminho ótimo **sem explorar nenhum nó desnecessário** — comportamento ideal.

---

## 🚀 Como Executar

### Pré-requisitos
- **Python 3.8+**
- **Tkinter** (geralmente já incluso; no Linux pode exigir `sudo apt install python3-tk`)
- Nenhuma dependência externa obrigatória ✅

Se nenhum player de áudio for encontrado, a música é simplesmente desativada com um aviso no console — o programa continua funcionando normalmente.

---

## 🎮 Como Usar

1. **Ajuste a densidade de obstáculos** no slider (0% a 40%).
2. Clique em **🔄 Novo tabuleiro** para gerar uma nova configuração aleatória.
3. Escolha uma estratégia nos radio buttons e clique em:
   - **▶ Executar busca** — anima apenas a estratégia selecionada.
4. Ou clique em:
   - **⚖ Comparar as duas estratégias** — executa Gulosa e A\* **simultaneamente** e anima **as duas ao mesmo tempo**.
5. Ajuste a **velocidade da animação** durante a execução (o slider tem efeito imediato).
6. Observe a tabela de métricas para comparar o desempenho.

---

## 🧩 Arquitetura do Código

```
├── Música
│   ├── gerar_wav_bytes()      → sintetiza a melodia em memória
│   ├── detectar_player()      → identifica o reprodutor do SO
│   ├── tocar_em_loop()        → toca em loop em thread separada
│   └── iniciar_musica()       → orquestra tudo
│
├── Algoritmos de Busca
│   ├── vizinhos()             → gera vizinhos válidos (8 direções)
│   ├── heuristica()           → distância octile admissível
│   ├── buscar()               → Gulosa ou A* (parametrizado)
│   └── encontrar_linhas_completas() → anti-bloqueio total
│
└── GUI (Tkinter)
    └── Aplicacao
        ├── _montar_ui()          → layout dos controles
        ├── _gerar_tabuleiro()    → tabuleiro aleatório conectado
        ├── desenhar()            → renderização no Canvas
        ├── executar()            → busca única
        ├── comparar()            → busca dupla + animação
        ├── _iniciar_animacoes()  → prepara as bolas
        ├── _passo_animacoes()    → loop de animação por frame
        └── _atualizar_tabela()   → atualiza métricas
```

---

## 🔬 O que Observar na Comparação

Ao clicar em **⚖ Comparar as duas estratégias**, repare que tipicamente:

- 🟣 **A Gulosa** explora **menos nós** e chega **mais rápido** — mas o caminho pode ser **mais longo ou sinuoso** (ela ignora o custo `g` já gasto).
- 🟠 **O A\*** explora **mais nós**, mas encontra o **caminho de custo mínimo** (respeitando os custos `1.0` e `√2` de cada aresta).
- Em tabuleiros com **muitos obstáculos**, a diferença de custo entre as duas rotas fica mais evidente.
- A tabela de métricas confirma numericamente essas diferenças — compare principalmente **Custo total** vs **Nós explorados**.

Esse é o trade-off clássico entre **velocidade de busca** e **qualidade da solução**.