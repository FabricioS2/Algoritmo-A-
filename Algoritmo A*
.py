import tkinter as tk
import random
import math
import struct
import wave
import io
import os
import sys
import time
import shutil
import platform
import tempfile
import subprocess
import threading

# ---------- CONFIGURAÇÕES DO TABULEIRO ----------
TAMANHO_CASA = 80 // 4
NUM_CASAS = 8 * 4
COR_CLARA = "#F0D9B5"
COR_ESCURA = "#B58863"
COR_AZUL = "#0000CD"
COR_VERMELHO = "#FF0000"
COR_AMARELO = "#FFD700"
DENSIDADE = 0.15

# ---------- GERADOR DE MÚSICA ----------
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
    """Gera bytes de um WAV com a melodia, sem salvar nada em disco ainda."""
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
    """Detecta o player de áudio disponível no sistema."""
    sistema = platform.system()

    if sistema == "Windows":
        return "windows"
    if sistema == "Darwin":
        return "afplay"

    # Linux: tenta na ordem de preferência
    for cmd in ("paplay", "aplay", "ffplay", "mpg123", "play"):
        if shutil.which(cmd):
            return cmd

    return None


def tocar_em_loop(caminho_wav):
    """Toca o WAV em loop infinito, usando o player nativo."""
    player = detectar_player()

    if player is None:
        print("⚠️  Nenhum player de áudio encontrado. Música desativada.")
        print("   No Linux, instale um dos: pulseaudio-utils (paplay),")
        print("   alsa-utils (aplay) ou ffmpeg (ffplay).")
        return

    print(f"🎵 Tocando música via: {player}")

    if player == "windows":
        import winsound
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
    """Gera o WAV, salva em temp e inicia a reprodução em uma thread."""
    wav_bytes = gerar_wav_bytes(MELODIA)

    # Cria arquivo temporário que persiste durante a execução
    fd, caminho = tempfile.mkstemp(suffix=".wav", prefix="tabuleiro_musica_")
    os.close(fd)
    with open(caminho, "wb") as f:
        f.write(wav_bytes)

    # Registra para apagar quando o programa sair
    import atexit
    atexit.register(lambda: os.path.exists(caminho) and os.remove(caminho))

    threading.Thread(target=tocar_em_loop, args=(caminho,), daemon=True).start()


# ---------- TABULEIRO ----------
root = tk.Tk()
root.title("Tabuleiro com Música (cross-platform)")
root.resizable(False, False)

tamanho_total = TAMANHO_CASA * NUM_CASAS
canvas = tk.Canvas(root, width=tamanho_total, height=tamanho_total)
canvas.pack()


def encontrar_linhas_completas(azuis):
    completas = []
    for l in range(NUM_CASAS):
        cells = [(l, c) for c in range(NUM_CASAS)]
        if all(c in azuis for c in cells):
            completas.append(cells)
    for c in range(NUM_CASAS):
        cells = [(l, c) for l in range(NUM_CASAS)]
        if all(cell in azuis for cell in cells):
            completas.append(cells)
    for d in range(-(NUM_CASAS - 1), NUM_CASAS):
        cells = [(i, i - d) for i in range(NUM_CASAS) if 0 <= i - d < NUM_CASAS]
        if len(cells) >= 2 and all(c in azuis for c in cells):
            completas.append(cells)
    for s in range(2 * NUM_CASAS - 1):
        cells = [(i, s - i) for i in range(NUM_CASAS) if 0 <= s - i < NUM_CASAS]
        if len(cells) >= 2 and all(c in azuis for c in cells):
            completas.append(cells)
    return completas


azuis = set()
for l in range(NUM_CASAS):
    for c in range(NUM_CASAS):
        if random.random() < DENSIDADE:
            azuis.add((l, c))

while True:
    linhas = encontrar_linhas_completas(azuis)
    if not linhas:
        break
    for linha in linhas:
        azuis.discard(random.choice(linha))

livres = [(l, c) for l in range(NUM_CASAS) for c in range(NUM_CASAS)
          if (l, c) not in azuis]

vermelho = random.choice(livres)
livres_restantes = [p for p in livres if p != vermelho]
amarelo = random.choice(livres_restantes)

for linha in range(NUM_CASAS):
    for coluna in range(NUM_CASAS):
        x1 = coluna * TAMANHO_CASA
        y1 = linha * TAMANHO_CASA
        x2 = x1 + TAMANHO_CASA
        y2 = y1 + TAMANHO_CASA

        cor = COR_CLARA if (linha + coluna) % 2 == 0 else COR_ESCURA
        canvas.create_rectangle(x1, y1, x2, y2, fill=cor, outline=cor)

        pos = (linha, coluna)
        if pos == vermelho:
            canvas.create_rectangle(x1, y1, x2, y2, fill=COR_VERMELHO, outline=COR_VERMELHO)
        elif pos == amarelo:
            canvas.create_rectangle(x1, y1, x2, y2, fill=COR_AMARELO, outline=COR_AMARELO)
        elif pos in azuis:
            canvas.create_rectangle(x1, y1, x2, y2, fill=COR_AZUL, outline=COR_AZUL)

# Inicia a música
iniciar_musica()

root.mainloop()