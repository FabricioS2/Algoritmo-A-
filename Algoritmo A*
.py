# -*- coding: utf-8 -*-
"""
Simulador de caminho A -> B (agente predador) sobre o tabuleiro do exemplo.
Com música (cross-platform), controle de densidade de obstáculos e
comparação visual das duas estratégias com DUAS bolas se movendo.

Estratégias:
    * Busca Gulosa  -> Greedy Best-First Search (só heurística)
    * A*            -> A-Star (custo acumulado g + heurística h admissível)

Ao clicar em "Comparar as duas estratégias":
    - A rota da Gulosa é desenhada em ROSA
    - A rota do A*     é desenhada em LARANJA
    - DUAS bolas percorrem as rotas SIMULTANEAMENTE (uma em cada cor)
"""

import atexit
import heapq
import io
import math
import os
import platform
import random
import shutil
import struct
import subprocess
import tempfile
import threading
import time
import tkinter as tk
import wave
from tkinter import ttk
from collections import deque

# ============================================================
#  MÚSICA (do código original)
# ============================================================
TAXA = 44100

NOTAS = {
    'C4': 261.63, 'D4': 293.66, 'E4': 329.63, 'F4': 349.23,
    'G4': 392.00, 'A4': 440.00, 'B4': 493.88,
    'C5': 523.25, 'D5': 587.33, 'E5': 659.25,
    'R':  0.0,
}

MELODIA = [
    ('C4', 0.20), ('E4', 0.20), ('G4', 0.20), ('C5', 0.30),
    ('R',  0.10),
    ('G4', 0.20), ('E4', 0.20), ('C4', 0.40),
    ('R',  0.15),
    ('D4', 0.20), ('F4', 0.20), ('A4', 0.20), ('D5', 0.30),
    ('R',  0.10),
    ('A4', 0.20), ('F4', 0.20), ('D4', 0.40),
    ('R',  0.20),
]


def gerar_wav_bytes(melodia, taxa=TAXA, volume=0.30):
    frames = bytearray()
    for nota, dur in melodia:
        freq = NOTAS.get(nota, nota)
        n = int(taxa * dur)
        for i in range(n):
            if freq == 0:
                val = 0
            else:
                env = 1.0
                fade = 800
                if i < fade:
                    env = i / fade
                elif i > n - fade:
                    env = (n - i) / fade
                amostra = math.sin(2 * math.pi * freq * i / taxa)
                val = int(32767 * volume * env * amostra)
            frames += struct.pack('<h', val)

    buf = io.BytesIO()
    with wave.open(buf, 'wb') as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(taxa)
        w.writeframes(bytes(frames))
    return buf.getvalue()


def detectar_player():
    sistema = platform.system()
    if sistema == "Windows":
        return "windows"
    if sistema == "Darwin":
        return "afplay"
    for cmd in ("paplay", "aplay", "ffplay", "mpg123", "play"):
        if shutil.which(cmd):
            return cmd
    return None


def tocar_em_loop(caminho_wav):
    player = detectar_player()
    if player is None:
        print("⚠️  Nenhum player de áudio encontrado. Música desativada.")
        return

    print(f"🎵 Tocando música via: {player}")

    if player == "windows":
        try:
            import winsound
        except ImportError:
            return
        while True:
            winsound.PlaySound(caminho_wav, winsound.SND_FILENAME)
            time.sleep(0.2)
        return

    if player == "afplay":
        cmd = ["afplay", caminho_wav]
    elif player == "ffplay":
        cmd = ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", caminho_wav]
    elif player == "paplay":
        cmd = ["paplay", caminho_wav]
    elif player == "aplay":
        cmd = ["aplay", "-q", caminho_wav]
    elif player == "mpg123":
        cmd = ["mpg123", "-q", caminho_wav]
    elif player == "play":
        cmd = ["play", "-q", caminho_wav]
    else:
        return

    try:
        while True:
            subprocess.run(cmd, check=False,
                           stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL)
            time.sleep(0.2)
    except Exception as e:
        print(f"Erro ao tocar música: {e}")


def iniciar_musica():
    wav_bytes = gerar_wav_bytes(MELODIA)
    fd, caminho = tempfile.mkstemp(suffix=".wav", prefix="tabuleiro_musica_")
    os.close(fd)
    with open(caminho, "wb") as f:
        f.write(wav_bytes)
    atexit.register(lambda: os.path.exists(caminho) and os.remove(caminho))
    threading.Thread(target=tocar_em_loop, args=(caminho,), daemon=True).start()


# ============================================================
#  CONFIGURAÇÕES DO TABULEIRO
# ============================================================
TAMANHO_CASA = 20
NUM_CASAS = 32
DENSIDADE_INICIAL = 0.15

COR_CLARA = "#F0D9B5"
COR_ESCURA = "#B58863"
COR_PAREDE = "#1E3A8A"
COR_INICIO = "#E53935"
COR_ALVO = "#FDD835"
COR_EXPLORADO = "#A5D6A7"

# Cores distintas para cada estratégia
COR_CAMINHO_ASTAR = "#FF6D00"    # laranja
COR_CAMINHO_GULOSO = "#E91E63"   # rosa/magenta

# Cor das bolas (mais escuras que as linhas, para destacar)
COR_BOLA_ASTAR = "#BF360C"
COR_BOLA_GULOSO = "#880E4F"

LARGURA = NUM_CASAS * TAMANHO_CASA
ALTURA = LARGURA

CUSTO_RETA = 1.0
CUSTO_DIAG = math.sqrt(2.0)


# ============================================================
#  BUSCA
# ============================================================
def vizinhos(no, paredes):
    l, c = no
    for dl in (-1, 0, 1):
        for dc in (-1, 0, 1):
            if dl == 0 and dc == 0:
                continue
            nl, nc = l + dl, c + dc
            if 0 <= nl < NUM_CASAS and 0 <= nc < NUM_CASAS and (nl, nc) not in paredes:
                yield (nl, nc), (CUSTO_DIAG if dl and dc else CUSTO_RETA)


def heuristica(a, b):
    dl = abs(a[0] - b[0])
    dc = abs(a[1] - b[1])
    return (dl + dc) + (CUSTO_DIAG - 2.0) * min(dl, dc)


def buscar(inicio, alvo, paredes, estrategia):
    t0 = time.perf_counter()
    contador = 0
    aberto = []
    heapq.heappush(aberto, (heuristica(inicio, alvo), 0.0, contador, inicio))

    g = {inicio: 0.0}
    pai = {inicio: None}
    fechado = set()
    ordem_explorados = []

    while aberto:
        _, _, _, atual = heapq.heappop(aberto)
        if atual in fechado:
            continue
        fechado.add(atual)
        ordem_explorados.append(atual)
        if atual == alvo:
            break

        for viz, custo in vizinhos(atual, paredes):
            if viz in fechado:
                continue
            ng = g[atual] + custo

            if estrategia == "guloso":
                if viz in g:
                    continue
                g[viz] = ng
                pai[viz] = atual
                contador += 1
                heapq.heappush(aberto, (heuristica(viz, alvo), ng, contador, viz))
            else:
                if viz in g and ng >= g[viz]:
                    continue
                g[viz] = ng
                pai[viz] = atual
                contador += 1
                heapq.heappush(aberto, (ng + heuristica(viz, alvo), ng, contador, viz))

    t1 = time.perf_counter()

    caminho = []
    if alvo in fechado:
        no = alvo
        while no is not None:
            caminho.append(no)
            no = pai[no]
        caminho.reverse()

    return {
        "estrategia": estrategia,
        "encontrado": bool(caminho),
        "caminho": caminho,
        "explorados": ordem_explorados,
        "n_explorados": len(ordem_explorados),
        "tempo_ms": (t1 - t0) * 1000.0,
        "custo": g.get(alvo) if caminho else None,
        "passos": (len(caminho) - 1) if caminho else 0,
    }


def encontrar_linhas_completas(paredes):
    N = NUM_CASAS
    completas = []
    for l in range(N):
        cells = [(l, c) for c in range(N)]
        if all(x in paredes for x in cells):
            completas.append(cells)
    for c in range(N):
        cells = [(l, c) for l in range(N)]
        if all(x in paredes for x in cells):
            completas.append(cells)
    for d in range(-(N - 1), N):
        cells = [(i, i - d) for i in range(N) if 0 <= i - d < N]
        if len(cells) >= 2 and all(x in paredes for x in cells):
            completas.append(cells)
    for s in range(2 * N - 1):
        cells = [(i, s - i) for i in range(N) if 0 <= s - i < N]
        if len(cells) >= 2 and all(x in paredes for x in cells):
            completas.append(cells)
    return completas


# ============================================================
#  APLICAÇÃO
# ============================================================
class Aplicacao:
    def __init__(self, root):
        self.root = root
        root.title("Predador A → B  •  Gulosa vs A*  •  Duas bolas")
        root.resizable(False, False)

        self.estrategia = tk.StringVar(value="astar")
        self.vel_var = tk.DoubleVar(value=25.0)
        self.densidade_var = tk.DoubleVar(value=DENSIDADE_INICIAL)

        self.paredes = set()
        self.inicio = None
        self.alvo = None

        self.resultados = {}

        # Lista de agentes (bolas) atualmente no canvas
        self.agentes = []

        # Estado da animação
        self._animacoes = []
        self.anim_id = None
        self.animando = False

        self._montar_ui()
        self.novo_tabuleiro()

        iniciar_musica()

        self.root.protocol("WM_DELETE_WINDOW", self._fechar)

    # ---------------- INTERFACE ----------------
    def _montar_ui(self):
        self.root.configure(bg="#ECECEC")
        cont = tk.Frame(self.root, bg="#ECECEC")
        cont.pack(padx=10, pady=10)

        self.canvas = tk.Canvas(cont, width=LARGURA, height=ALTURA,
                                highlightthickness=1, highlightbackground="#888888")
        self.canvas.grid(row=0, column=0, sticky="n")

        painel = tk.Frame(cont, bg="#ECECEC")
        painel.grid(row=0, column=1, sticky="n", padx=(12, 0))

        tk.Label(painel, text="Estratégia de busca", bg="#ECECEC",
                 font=("Segoe UI", 11, "bold")).pack(anchor="w")

        ttk.Radiobutton(painel, text="Busca Gulosa (Greedy Best-First)",
                        variable=self.estrategia, value="guloso").pack(anchor="w")
        ttk.Radiobutton(painel, text="A*  (A-Star)",
                        variable=self.estrategia, value="astar").pack(anchor="w")

        ttk.Separator(painel, orient="horizontal").pack(fill="x", pady=8)

        # ---- DENSIDADE DE OBSTÁCULOS ----
        tk.Label(painel, text="Densidade de obstáculos", bg="#ECECEC",
                 font=("Segoe UI", 11, "bold")).pack(anchor="w")

        self.dens_label = tk.Label(painel, text="15%", bg="#ECECEC", fg="#444444",
                                   font=("Segoe UI", 9))
        self.dens_label.pack(anchor="e")

        self.dens_scale = ttk.Scale(
            painel, from_=0.0, to=0.40,
            variable=self.densidade_var,
            orient="horizontal",
            command=self._on_densidade_mudar,
        )
        self.dens_scale.pack(fill="x")

        tk.Label(painel, text="(0% = livre  •  40% = muito denso)",
                 bg="#ECECEC", fg="#777777",
                 font=("Segoe UI", 8, "italic")).pack(anchor="w")

        ttk.Separator(painel, orient="horizontal").pack(fill="x", pady=8)

        self.btn_exec = ttk.Button(painel, text="▶  Executar busca", command=self.executar)
        self.btn_exec.pack(fill="x")

        self.btn_comp = ttk.Button(painel, text="⚖  Comparar as duas estratégias",
                                   command=self.comparar)
        self.btn_comp.pack(fill="x", pady=4)

        self.btn_novo = ttk.Button(painel, text="🔄  Novo tabuleiro",
                                   command=self.novo_tabuleiro)
        self.btn_novo.pack(fill="x")

        ttk.Separator(painel, orient="horizontal").pack(fill="x", pady=8)

        tk.Label(painel, text="Velocidade da animação", bg="#ECECEC").pack(anchor="w")
        ttk.Scale(painel, from_=2, to=120, variable=self.vel_var,
                  orient="horizontal").pack(fill="x")

        ttk.Separator(painel, orient="horizontal").pack(fill="x", pady=8)

        tk.Label(painel, text="Métricas comparativas", bg="#ECECEC",
                 font=("Segoe UI", 11, "bold")).pack(anchor="w")

        colunas = ("metrica", "guloso", "astar")
        self.tabela = ttk.Treeview(painel, columns=colunas, show="headings", height=5)
        self.tabela.heading("metrica", text="Métrica")
        self.tabela.heading("guloso", text="Gulosa")
        self.tabela.heading("astar", text="A*")
        self.tabela.column("metrica", width=170, anchor="w")
        self.tabela.column("guloso", width=80, anchor="center")
        self.tabela.column("astar", width=80, anchor="center")
        self.tabela.pack(fill="x")

        self._iids = []
        for rotulo in ("Caminho encontrado", "Nós explorados",
                       "Tempo de busca (ms)", "Custo total do caminho",
                       "Passos (arestas)"):
            self._iids.append(self.tabela.insert("", "end", values=(rotulo, "—", "—")))

        # ---- LEGENDA ----
        legenda = tk.Frame(painel, bg="#ECECEC")
        legenda.pack(anchor="w", pady=(10, 0))
        for cor, texto in ((COR_INICIO, "A (predador)"),
                           (COR_ALVO, "B (alvo)"),
                           (COR_PAREDE, "obstáculo"),
                           (COR_EXPLORADO, "explorado"),
                           (COR_CAMINHO_GULOSO, "rota da Gulosa"),
                           (COR_CAMINHO_ASTAR, "rota do A*")):
            linha = tk.Frame(legenda, bg="#ECECEC")
            linha.pack(anchor="w")
            tk.Canvas(linha, width=12, height=12, bg=cor, highlightthickness=0).pack(side="left")
            tk.Label(linha, text=" " + texto, bg="#ECECEC",
                     font=("Segoe UI", 8)).pack(side="left")

    def _on_densidade_mudar(self, _valor):
        pct = int(round(self.densidade_var.get() * 100))
        self.dens_label.configure(text=f"{pct}%")

    # ---------------- GERAÇÃO DO TABULEIRO ----------------
    def novo_tabuleiro(self):
        self._parar_animacao()
        self.resultados = {}
        self._gerar_tabuleiro()
        self.desenhar()
        self._atualizar_tabela()

    def _gerar_tabuleiro(self):
        N = NUM_CASAS
        densidade_base = self.densidade_var.get()
        tentativa = 0

        while True:
            tentativa += 1
            densidade = densidade_base if tentativa < 80 else max(0.02, densidade_base * 0.3)

            paredes = {(l, c)
                       for l in range(N) for c in range(N)
                       if random.random() < densidade}

            while True:
                linhas = encontrar_linhas_completas(paredes)
                if not linhas:
                    break
                for linha in linhas:
                    paredes.discard(random.choice(linha))

            livres = [(l, c) for l in range(N) for c in range(N) if (l, c) not in paredes]
            if len(livres) < 2:
                continue

            inicio = random.choice(livres)
            alvo = random.choice([p for p in livres if p != inicio])

            if self._conectados(inicio, alvo, paredes):
                self.paredes = paredes
                self.inicio = inicio
                self.alvo = alvo
                return

    @staticmethod
    def _conectados(a, b, paredes):
        if a == b:
            return True
        vistos = {a}
        fila = deque([a])
        while fila:
            atual = fila.popleft()
            for viz, _ in vizinhos(atual, paredes):
                if viz == b:
                    return True
                if viz not in vistos:
                    vistos.add(viz)
                    fila.append(viz)
        return False

    # ---------------- DESENHO ----------------
    def _marcador(self, pos, cor, texto, cor_texto):
        T = TAMANHO_CASA
        l, c = pos
        x, y = c * T, l * T
        self.canvas.create_rectangle(x, y, x + T, y + T, fill=cor, outline="")
        self.canvas.create_text(x + T / 2, y + T / 2, text=texto,
                                font=("Segoe UI", max(8, int(T * 0.6)), "bold"),
                                fill=cor_texto)

    def _desenhar_caminho(self, caminho, cor, largura=4):
        if not caminho or len(caminho) < 2:
            return
        T = TAMANHO_CASA
        pontos = []
        for (l, c) in caminho:
            pontos.extend([c * T + T / 2, l * T + T / 2])
        self.canvas.create_line(*pontos, fill=cor, width=largura,
                                capstyle=tk.ROUND, joinstyle=tk.ROUND)

    def desenhar(self, explorados=None, caminhos=None):
        cv = self.canvas
        cv.delete("all")
        T = TAMANHO_CASA
        N = NUM_CASAS

        # 1) Tabuleiro xadrez
        for l in range(N):
            for c in range(N):
                x1, y1 = c * T, l * T
                cor = COR_CLARA if (l + c) % 2 == 0 else COR_ESCURA
                cv.create_rectangle(x1, y1, x1 + T, y1 + T, fill=cor, outline=cor)

        # 2) Nós explorados
        if explorados:
            for (l, c) in explorados:
                cv.create_rectangle(c * T + 1, l * T + 1,
                                    c * T + T - 1, l * T + T - 1,
                                    fill=COR_EXPLORADO, outline="")

        # 3) Obstáculos
        for (l, c) in self.paredes:
            cv.create_rectangle(c * T, l * T, c * T + T, l * T + T,
                                fill=COR_PAREDE, outline=COR_PAREDE)

        # 4) Caminhos + criação das bolas
        self.agentes = []
        if caminhos:
            for item in caminhos:
                cam, cor_linha, cor_bola, rotulo = item
                if not cam:
                    continue

                self._desenhar_caminho(cam, cor_linha, largura=4)

                l, c = cam[0]
                r = T * 0.34
                x, y = c * T + T / 2, l * T + T / 2
                oid = cv.create_oval(x - r, y - r, x + r, y + r,
                                     fill=cor_bola, outline="#FFFFFF", width=2)
                self.agentes.append({
                    "id": oid,
                    "caminho": cam,
                    "cor": cor_bola,
                    "rotulo": rotulo,
                })

        # 5) Pontos A e B
        self._marcador(self.inicio, COR_INICIO, "A", "#FFFFFF")
        self._marcador(self.alvo, COR_ALVO, "B", "#333333")

    # ---------------- EXECUÇÃO ----------------
    def executar(self):
        self._parar_animacao()
        est = self.estrategia.get()
        res = buscar(self.inicio, self.alvo, self.paredes, est)

        self.resultados = {est: res}
        self._atualizar_tabela()

        if res["encontrado"]:
            if est == "astar":
                cor_linha, cor_bola, rotulo = COR_CAMINHO_ASTAR, COR_BOLA_ASTAR, "A*"
            else:
                cor_linha, cor_bola, rotulo = COR_CAMINHO_GULOSO, COR_BOLA_GULOSO, "Gulosa"
            self.desenhar(explorados=res["explorados"],
                          caminhos=[(res["caminho"], cor_linha, cor_bola, rotulo)])
            self._iniciar_animacoes()
        else:
            self.desenhar(explorados=res["explorados"], caminhos=None)

    def comparar(self):
        self._parar_animacao()

        for est in ("guloso", "astar"):
            self.resultados[est] = buscar(self.inicio, self.alvo, self.paredes, est)

        self._atualizar_tabela()

        r_g = self.resultados["guloso"]
        r_a = self.resultados["astar"]

        caminhos = []
        if r_g["encontrado"]:
            caminhos.append((r_g["caminho"], COR_CAMINHO_GULOSO, COR_BOLA_GULOSO, "Gulosa"))
        if r_a["encontrado"]:
            caminhos.append((r_a["caminho"], COR_CAMINHO_ASTAR, COR_BOLA_ASTAR, "A*"))

        est_sel = self.estrategia.get()
        explorados_sel = self.resultados[est_sel]["explorados"]

        self.desenhar(explorados=explorados_sel, caminhos=caminhos)
        self._iniciar_animacoes()

    # ---------------- ANIMAÇÃO (DUAS OU MAIS BOLAS) ----------------
    def _iniciar_animacoes(self):
        self._animacoes = []

        for ag in self.agentes:
            cam = ag["caminho"]
            if len(cam) < 2:
                continue

            acum = [0.0]
            for i in range(1, len(cam)):
                dl = abs(cam[i][0] - cam[i - 1][0])
                dc = abs(cam[i][1] - cam[i - 1][1])
                acum.append(acum[-1] + (CUSTO_DIAG if dl and dc else CUSTO_RETA))

            self._animacoes.append({
                "id": ag["id"],
                "caminho": cam,
                "custos": acum,
                "indice": 0,
                "rotulo": ag["rotulo"],
                "cor": ag["cor"],
            })

        if not self._animacoes:
            return

        self.animando = True
        self._atualizar_botoes()
        self._passo_animacoes()

    def _passo_animacoes(self):
        T = TAMANHO_CASA
        r = T * 0.34

        alguem_ainda_move = False

        for anim in self._animacoes:
            cam = anim["caminho"]
            i = anim["indice"]
            l, c = cam[i]
            x, y = c * T + T / 2, l * T + T / 2
            self.canvas.coords(anim["id"], x - r, y - r, x + r, y + r)

            if i < len(cam) - 1:
                anim["indice"] = i + 1
                alguem_ainda_move = True

        if not alguem_ainda_move:
            self.animando = False
            self._atualizar_botoes()
            return

        delay = max(1, int(1000.0 / max(1.0, self.vel_var.get())))
        self.anim_id = self.root.after(delay, self._passo_animacoes)

    def _parar_animacao(self):
        if self.anim_id is not None:
            try:
                self.root.after_cancel(self.anim_id)
            except Exception:
                pass
            self.anim_id = None
        self.animando = False
        self._animacoes = []
        self._atualizar_botoes()

    def _atualizar_botoes(self):
        estado = "disabled" if self.animando else "normal"
        self.btn_exec.configure(state=estado)
        self.btn_comp.configure(state=estado)
        self.btn_novo.configure(state=estado)

    # ---------------- MÉTRICAS ----------------
    def _atualizar_tabela(self):
        def cel(est, chave, fmt=None):
            r = self.resultados.get(est)
            if r is None:
                return "—"
            v = r.get(chave)
            if v is None:
                return "—"
            if fmt == "bool":
                return "Sim" if v else "Não"
            if fmt == "ms":
                return f"{v:.2f}"
            if fmt == "f":
                return f"{v:.3f}"
            return str(v)

        linhas = [
            ("encontrado", "bool"),
            ("n_explorados", None),
            ("tempo_ms", "ms"),
            ("custo", "f"),
            ("passos", None),
        ]

        for iid, (chave, fmt) in zip(self._iids, linhas):
            valores = self.tabela.item(iid, "values")
            self.tabela.item(iid, values=(valores[0],
                                          cel("guloso", chave, fmt),
                                          cel("astar", chave, fmt)))

    # ---------------- ENCERRAMENTO ----------------
    def _fechar(self):
        self._parar_animacao()
        self.root.destroy()


# ============================================================
if __name__ == "__main__":
    root = tk.Tk()
    app = Aplicacao(root)
    root.mainloop()