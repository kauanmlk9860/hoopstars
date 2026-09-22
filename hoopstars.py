"""
HOOP STARS — Basquete 2D em Pygame
====================================
Um jogo de arremessos de basquete com personagem animado, física de bola
com quique e gravidade, cesta com aro/tabela/rede, partículas, combo e
placar com recorde salvo em disco.

CONTROLES
  A / D  ou  Setas ESQUERDA/DIREITA .... andar
  ESPAÇO (segure e solte) ............... ARREMESSA — quanto mais tempo segurar,
      mais força; a linha pontilhada mostra a trajetória enquanto você carrega
  ESPAÇO 2x perto da cesta .............. ENTERRA (dunk garantido!)
      segure a 2ª batida para ficar pendurado no aro — solte para cair
  --- NA DEFESA (sem a bola) ---
  ESPAÇO ................................ BOTE DE ROUBO, sem sair do chão
  ESPAÇO 2x ............................. TOCO (pula com o braço esticado)
  Errou a cesta? quem pegar o ressalto precisa levar a bola para trás da
  linha de 3 antes de poder atacar.
  Clique e ARRASTE a partir da bola ..... mira manual (estilingue), pro arremesso
      preciso: quanto maior o arrasto, mais força
  R ...................................... reiniciar
  ESC ..................................... sair

Requisitos: pip install pygame
Executar:   python hoopstars.py
"""

import pygame
import math
import array
import time
import sys
import random
import asyncio
import json
import os

# --------------------------------------------------------------------------
# CONFIGURAÇÃO GERAL
# --------------------------------------------------------------------------
WIDTH, HEIGHT = 1000, 600
FLOOR_Y = 520
GRAVITY = 0.55
FPS = 60
# O jogo tambem roda no navegador (pygbag/WebAssembly), onde o mesmo quadro
# custa 2 a 3 vezes mais. E o unico lugar do codigo que olha a plataforma.
NO_NAVEGADOR = sys.platform == "emscripten"
GAME_SECONDS = 60
def _pasta_de_dados():
    """Onde guardar o recorde. Ao lado do .py não serve pra distribuir: num
    .exe de arquivo único essa pasta é temporária e some ao fechar, e numa
    pasta só-leitura a gravação falha."""
    base = os.environ.get("APPDATA") or os.path.join(
        os.path.expanduser("~"), ".local", "share")
    alvo = os.path.join(base, "HoopStars")
    try:
        os.makedirs(alvo, exist_ok=True)
        return alvo
    except OSError:
        return os.path.dirname(os.path.abspath(__file__))


HIGHSCORE_FILE = os.path.join(_pasta_de_dados(), "hoopstars_highscore.json")

THREE_POINT_X = 330       # arremessos com origem à esquerda disso valem 3
# A zona começa na LINHA DE LANCE LIVRE (FT_X ≈ 481, calculado mais abaixo a
# partir da escala da quadra): colado no aro não sobra espaço pra enterrada
# acontecer. O tempo do preparo se estica com a distância (ver trigger_dunk).
DUNK_ZONE = (470, 790)    # faixa de x onde dá pra enterrar
DUNK_SLAM_FRAMES = 23     # duração do estouro, depois do preparo

# Força do arremesso. A mão fica em y=460 e o aro em y=292, mas o mouse só pode
# descer até a borda da janela (~135px de arrasto útil) — por isso a conversão
# de arrasto em velocidade precisa ser generosa, senão a bola nunca alcança a cesta.
SHOT_MAX_POWER = 220      # arrasto máximo considerado, em pixels
# Piso de força. Existe pra que força zero não conte como arremesso, mas
# precisa ficar ABAIXO da força ideal do tiro mais curto possível: em 20
# ele atropelava a conta debaixo do aro e mandava a bola 148 px além.
SHOT_MIN_POWER = 6.0
SHOT_POWER = 0.16         # velocidade por pixel de arrasto

# Arremesso pelo teclado: segurar ESPAÇO carrega a força, soltar arremessa.
SPACE_ANGLE_NEAR = 80     # graus do arco quando está colado na cesta
SPACE_ANGLE_FAR = 62      # graus do arco do outro lado da quadra
# O medidor é calibrado pela distância: varre de (1-CHARGE_SPAN) a (1+CHARGE_SPAN)
# da força ideal daquela posição, com o ponto certo no meio da barra.
CHARGE_FRAMES = 55        # frames para varrer o medidor inteiro
CHARGE_SPAN = 0.30
# Erro de forca, relativo a forca ideal, que a cesta ainda perdoa. MEDIDO
# varrendo 0,80..1,20 da ideal em varias distancias: a faixa que entra fica
# entre 0,02 e 0,035. E daqui que sai a largura da ZONA VERDE do medidor --
# desenhar a zona num tamanho escolhido a olho faria a barra mentir.
SHOT_TOL = 0.030
SHOT_TOL_QUASE = 2.4      # quantas vezes a zona verde vale o amarelo em volta
MEDIDOR_FLASH = 30        # quadros que a barra fica congelada mostrando o resultado
DOUBLE_TAP_FRAMES = 18    # janela para a 2ª batida do espaço (enterrada)
QUICK_TAP_FRAMES = 10     # até aqui o toque conta como "batida", não como carga

# Cesta
BACKBOARD_X = 862
BACKBOARD_TOP = 120
BACKBOARD_H = 140
RIM_Y = 262               # 258 px acima do chao, ~1,9x a altura do jogador
RIM_LEFT = 792
RIM_RIGHT = 858
RIM_GRAB_INSET = 28       # onde a mão agarra o aro, contado a partir da borda esquerda
# nomes dos estilos de enterrada, na ordem de Player.dunk_style
# Uma cravada por jogador: o dono de cada indice esta ao lado. O JUMPMAN e a
# excecao — e de todos, mas so sai de longe, porque precisa de espaco pra voar.
DUNK_NAMES = ["MARTELO!",       # 0  reserva (ninguém assina esta)
              "TOMAHAWK!",      # 1  Kobe
              "MOLINETE!",      # 2  Magic
              "DUAS MÃOS!",     # 3  Duncan
              "BERÇO!",         # 4  Iverson
              "BOMBA DUPLA!",   # 5  Pippen
              "JUMPMAN!",       # 6  Jordan
              "TREM-BALA!",     # 7  LeBron
              "QUEBRA-TABELA!", # 8  Shaq
              "GANCHO CRAVADO!",# 9  Kareem
              "BALANÇO!",       # 10 Curry
              "REVERSA!",       # 11 Bird
              "TORRE!"]         # 12 Dirk
# O mesmo gesto feito em VOO (do lance livre pra trás) tem outro nome — é o que
# avisa o jogador de que aquilo foi a versão grande da cravada dele.
DUNK_NAMES_VOO = ["MARTELO VOADOR!",
                  "TOMAHAWK VOADOR!",
                  "MOLINETE AÉREO!",
                  "VOO DE DUAS MÃOS!",
                  "BERÇO NO AR!",
                  "BOMBA VOADORA!",
                  "JUMPMAN!",
                  "TREM-BALA DESGOVERNADO!",
                  "DEMOLIÇÃO!",
                  "GANCHO VOADOR!",
                  "BALANÇO AÉREO!",
                  "REVERSA VOADORA!",
                  "TORRE VOADORA!"]
DUNK_JUMPMAN = 6          # não entra no sorteio: é a cravada de longe
DUNK_JUMPMAN_DIST = 190   # a partir daqui a cravada vira o voo do Jumpman

# --------------------------- X1 ---------------------------
# ------------------------ FISICA DO CORPO ------------------------
ACEL_BASE = 2.20        # px por quadro^2 no arranque, no peso de referencia
ATRITO = 0.78           # quanto da velocidade sobra por quadro sem tecla
PARADO = 0.06           # abaixo disso a velocidade zera, pra nao ficar deslizando
CONTATO = 0.44          # fracao das larguras somadas em que os corpos se tocam
FOLEGO_GASTO = 0.0022   # por quadro correndo
FOLEGO_SALTO = 0.055    # por salto
FOLEGO_VOLTA = 0.0042   # por quadro parado
FOLEGO_MIN_VEL = 0.80   # velocidade maxima com o folego no fim
# ------------------------ ACOES ------------------------
SPRINT_FRAMES = 38      # duracao do pique
SPRINT_BOOST = 1.52     # quanto a velocidade maxima sobe no pique
# Empurrao na hora da arrancada, em fracao da velocidade dele. Sem isto o
# arranque so levantava o TETO e a inercia levava quadros pra chegar la -- o
# comeco do pique ficava igual ao comeco de qualquer caminhada.
SPRINT_IMPULSO = 0.85
SPRINT_CUSTO = 0.22     # folego gasto no arranque
FINTA_FRAMES = 20       # duracao da finta
FINTA_RANGE = 96        # ate onde o defensor pode comprar a finta
BANDEJA_RANGE = 150     # perto do aro, BAIXO + acao vira bandeja

MATCH_POINTS = 11         # alvo padrão; o jogador troca na tela de quadra
PONTOS_OPCOES = (7, 11, 15, 21)
# (rotulo na tela, valor em Player.roupa)
ROUPA_OPCOES = (("UNIFORME", "uniforme"), ("MOLETOM", "moletom"))

# ------------------------ MODO (habilidade ativavel) ------------------------
# O medidor enche JOGANDO, e nao com o tempo: tempo premiaria quem fica parado.
SUPER_CESTA = 0.17        # quanto uma cesta enche
SUPER_CRAVADA = 0.26
SUPER_ROUBO = 0.22
SUPER_TOCO = 0.22
SUPER_SOFREU = 0.10       # tomar cesta tambem enche: quem perde reage
SUPER_FRAMES = 330        # quanto dura o modo, em quadros (~5,5 s)

# As familias de efeito. Cada uma amplifica o traco que o jogador JA tinha --
# uma habilidade inventada criaria um segundo personagem dentro do mesmo.
SUPER_TIRO_CERTO = ("chuva3", "mentalidade", "sanguefrio")
SUPER_INTOCAVEL = ("gancho", "flamingo")
SUPER_DONO_DA_BOLA = ("trem", "crossover", "alicate", "fundamento")
SUPER_VOO = ("jumpman", "quebra", "showtime")
# O que aparece na tela quando o modo liga, por habilidade.
# O que o MODO faz, em uma linha, pra ficha do personagem. Sai por
# HABILIDADE e nao por familia: quem esta escolhendo quer saber o que ESTE
# jogador faz, nao a que grupo ele pertence.
SUPER_DESC = {
    "jumpman": "crava de qualquer lugar da quadra",
    "trem": "ninguém tira a bola da mão dele",
    "chuva3": "a janela do arremesso vira o medidor inteiro",
    "quebra": "a cravada arrebenta a tabela",
    "mentalidade": "a janela do arremesso vira o medidor inteiro",
    "showtime": "corre mais e não cansa",
    "sanguefrio": "arremessa como se estivesse sozinho",
    "gancho": "o arremesso não pode ser tocado nem contestado",
    "crossover": "o bote de roubo não falha e quase não recarrega",
    "fundamento": "o bote de roubo não falha e alcança de longe",
    "alicate": "o bote de roubo não falha e alcança de longe",
    "flamingo": "ninguém consegue contestar o arremesso",
}
SUPER_GRITO = {
    "jumpman": "DO LANCE LIVRE!", "trem": "NINGUÉM SEGURA!",
    "chuva3": "CHOVEU!", "quebra": "MODO DEMOLIDOR",
    "mentalidade": "MAMBA!", "showtime": "SHOWTIME!",
    "sanguefrio": "GELADO!", "gancho": "INALCANÇÁVEL!",
    "crossover": "QUEBROU!", "fundamento": "FUNDAMENTO!",
    "alicate": "ALICATE!", "flamingo": "FLAMINGO!",
}
# Niveis: `erro` multiplica o erro de pontaria da IA (maior = ela erra mais),
# o resto multiplica a chance por quadro de cada acao dela. DIFICIL e o
# comportamento cru, sem nenhum afrouxamento.
DIFICULDADES = [
    dict(nome="FÁCIL",   erro=3.2, roubo=0.30, toco=0.25, vel=0.84, cravada=0.40),
    dict(nome="NORMAL",  erro=1.8, roubo=0.62, toco=0.55, vel=0.93, cravada=0.75),
    dict(nome="DIFÍCIL", erro=0.78, roubo=1.25, toco=1.20, vel=1.06, cravada=1.15),
]
DIFICULDADE_PADRAO = 1

# As tres telas do jogo. `selecting` continua existindo como fachada, porque
# meio codigo (e os testes) pergunta so "esta escolhendo?".
TELA_INICIO, TELA_QUADRA, TELA_ESCOLHA, TELA_JOGO = \
    "inicio", "quadra", "escolha", "jogo"
STEAL_RANGE = 52          # distância da mão à bola pra o roubo pegar
STEAL_CHANCE = 0.5        # chance quando a tentativa acontece no alcance
STEAL_COOLDOWN = 24       # frames entre tentativas de roubo
BLOCK_WINDOW = 18         # frames em que o toco fica ativo depois do salto
BLOCK_RANGE = 44          # alcance da mão pra tocar a bola
CONTESTE_RANGE = 86       # defensor mais perto que isso atrapalha o arremesso
CONTESTE_FORCA = 0.34     # erro maximo de forca num arremesso muito contestado
CONTESTE_ANGULO = 0.135   # erro maximo de angulo, em radianos
AFUNDA_RANGE = 70         # defensor no ar mais perto que isso derruba a cravada
POSTER_RANGE = 76         # cravar mais perto que isso derruba o defensor
POSTER_FRAMES = 84        # queda + tempo no chao + levantar
MARK_RANGE = 60           # colado o bastante pra tentar o bote / o toco
MARK_DIST = MARK_RANGE - 14   # onde a IA se planta: dentro do próprio alcance
# ------------------------- ELENCO -------------------------
# Cada perfil descreve o jogador INTEIRO, nao so a cor da camisa:
#   altura/peso  -> escala o corpo desenhado E o alcance (mais alto agarra o
#                   aro com um salto menor; mais pesado tem o corpo mais largo)
#   pele/cabelo  -> o rosto de cada um
#   drible       -> quadros por quique; `cross` e a amplitude do crossover
#   tiro         -> a forma do arremesso ("normal", "rapido", "fadeaway", "gancho")
#   dunks        -> a cravada dele (indice de DUNK_NAMES). Cada um tem a sua,
#                   de perto E de longe -- de longe ela so ganha a versao em voo
#   hab          -> a habilidade unica, com efeito de verdade na partida
#   tenis        -> (cabedal, detalhe do modelo, sola, cano alto): o par que
#                   ele calca, do Grinch verde-limao do Kobe ao Bred do Jordan
#   trim         -> a cor do acabamento do uniforme (gola, friso do calcao)
#   faixa/manga/joelheira/meia/oculos -> os acessorios que identificam cada um
ROSTER = [
    dict(nome="JORDAN", num="23", cam=(204, 22, 52), cam_esc=(150, 14, 36),
         calc=(30, 34, 48), pele=(120, 76, 48), cabelo="careca",
         cor_cabelo=(26, 20, 18), barba="nao", queixo=1.00, altura=198, peso=98,
         arr=9, vel=9, forca=8, defe=9, drible=34, dip=14, cross=6,
         tiro="normal", set_point=28, ext=0.26, hop=10.2, arm=34,
         tenis=((28, 28, 34), (206, 26, 54), (238, 238, 240), True), trim=(238, 238, 240), faixa=None,
         manga=None, joelheira=False, meia=5, oculos=False,
         dunks=[6], hab="jumpman", cranio=1.00, ombros=1.00, envergadura=1.04, lingua=True, traco="LÍNGUA DE FORA",
         traco_desc="crava do lance livre de muito mais longe"),
    dict(nome="LEBRON", num="23", cam=(120, 40, 140), cam_esc=(84, 26, 100),
         calc=(30, 30, 44), pele=(104, 66, 42), cabelo="curto",
         cor_cabelo=(24, 18, 16), barba="cheia", queixo=1.10, altura=206, peso=113,
         arr=7, vel=9, forca=10, defe=8, drible=36, dip=12, cross=5,
         tiro="normal", set_point=22, ext=0.34, hop=10.4, arm=30,
         tenis=((26, 26, 32), (232, 190, 64), (40, 42, 50), True), trim=(232, 190, 64), faixa=(238, 238, 242),
         manga=(26, 26, 32), joelheira=True, meia=4, oculos=False,
         dunks=[7], hab="trem", cranio=0.97, ombros=1.12, envergadura=1.02, traco="TREM DESGOVERNADO",
         traco_desc="roubar a bola dele é quase impossível"),
    dict(nome="CURRY", num="30", cam=(255, 196, 40), cam_esc=(198, 146, 20),
         calc=(26, 44, 96), pele=(168, 122, 84), cabelo="curto",
         cor_cabelo=(34, 24, 18), barba="cavanhaque", queixo=0.92, altura=188, peso=84,
         arr=10, vel=8, forca=4, defe=6, drible=26, dip=15, cross=12,
         tiro="rapido", set_point=24, ext=0.16, hop=8.8, arm=30,
         tenis=((240, 242, 246), (36, 72, 180), (240, 242, 246), False), trim=(36, 72, 180), faixa=None,
         manga=None, joelheira=False, meia=9, oculos=False,
         dunks=[10], hab="chuva3", cranio=0.99, ombros=0.90, envergadura=0.98, traco="CHUVA DE 3",
         traco_desc="de fora da linha de 3 quase não erra"),
    dict(nome="SHAQ", num="34", cam=(86, 44, 148), cam_esc=(58, 28, 104),
         calc=(232, 190, 40), pele=(96, 60, 38), cabelo="careca",
         cor_cabelo=(22, 18, 16), barba="nao", queixo=1.20, altura=216, peso=147,
         arr=3, vel=4, forca=10, defe=8, drible=44, dip=9, cross=2,
         tiro="normal", set_point=16, ext=0.42, hop=8.6, arm=28,
         tenis=((34, 34, 40), (188, 192, 204), (60, 62, 70), False), trim=(232, 190, 40), faixa=None,
         manga=None, joelheira=True, meia=3, oculos=False,
         dunks=[8], hab="quebra", cranio=0.93, ombros=1.18, envergadura=1.02, traco="QUEBRA-TABELA",
         traco_desc="a cravada dele não pode ser tocada"),
    dict(nome="KOBE", num="24", cam=(250, 200, 44), cam_esc=(196, 150, 22),
         calc=(86, 44, 148), pele=(126, 82, 52), cabelo="careca",
         cor_cabelo=(24, 20, 18), barba="nao", queixo=1.02, altura=198, peso=96,
         arr=9, vel=8, forca=7, defe=8, drible=32, dip=14, cross=8,
         tiro="fadeaway", set_point=30, ext=0.24, hop=10.2, arm=34,
         tenis=((150, 226, 40), (208, 32, 44), (30, 30, 36), False), trim=(86, 44, 148), faixa=None,
         manga=(238, 238, 242), joelheira=False, meia=4, oculos=False,
         dunks=[1], hab="mentalidade", cranio=1.02, ombros=0.98, envergadura=1.03, traco="MENTALIDADE",
         traco_desc="quando está perdendo, acerta muito mais"),
    dict(nome="MAGIC", num="32", cam=(250, 200, 44), cam_esc=(196, 150, 22),
         calc=(86, 44, 148), pele=(132, 88, 56), cabelo="afro",
         cor_cabelo=(26, 22, 20), barba="nao", queixo=1.06, altura=206, peso=100,
         arr=7, vel=8, forca=8, defe=7, drible=28, dip=18, cross=10,
         tiro="normal", set_point=24, ext=0.30, hop=9.5, arm=32,
         tenis=((128, 72, 190), (250, 200, 44), (238, 236, 230), True), trim=(86, 44, 148), faixa=None,
         manga=None, joelheira=False, meia=3, oculos=False,
         dunks=[2], hab="showtime", cranio=1.00, ombros=1.05, envergadura=1.02, traco="SHOWTIME",
         traco_desc="depois de roubar, dispara em contra-ataque"),
    dict(nome="BIRD", num="33", cam=(238, 238, 240), cam_esc=(176, 176, 182),
         calc=(24, 108, 66), pele=(226, 188, 152), cabelo="loiro",
         cor_cabelo=(196, 150, 84), barba="nao", queixo=0.98, altura=206, peso=100,
         arr=9, vel=5, forca=7, defe=7, drible=38, dip=12, cross=4,
         tiro="normal", set_point=30, ext=0.22, hop=9.0, arm=33,
         tenis=((240, 240, 238), (24, 116, 72), (232, 228, 218), True), trim=(24, 108, 66), faixa=None,
         manga=None, joelheira=False, meia=10, oculos=False,
         dunks=[11], hab="sanguefrio", cranio=1.03, ombros=0.99, envergadura=0.98, traco="SANGUE FRIO",
         traco_desc="a janela do arremesso dele é sempre maior"),
    dict(nome="KAREEM", num="33", cam=(86, 44, 148), cam_esc=(58, 28, 104),
         calc=(250, 200, 44), pele=(110, 70, 46), cabelo="careca",
         cor_cabelo=(22, 18, 16), barba="cavanhaque", queixo=1.12, altura=218, peso=102,
         arr=8, vel=5, forca=9, defe=9, drible=40, dip=11, cross=3,
         tiro="gancho", set_point=34, ext=0.26, hop=8.8, arm=36,
         tenis=((238, 238, 240), (86, 44, 148), (240, 240, 242), False), trim=(250, 200, 44), faixa=None,
         manga=None, joelheira=True, meia=9, oculos=True,
         dunks=[9], hab="gancho", cranio=1.08, ombros=0.93, envergadura=1.09, traco="GANCHO CÉU",
         traco_desc="o gancho sai tão alto que ninguém toca"),
    dict(nome="IVERSON", num="3", cam=(40, 62, 140), cam_esc=(24, 40, 100),
         calc=(216, 44, 60), pele=(118, 76, 50), cabelo="trancas",
         cor_cabelo=(20, 16, 14), barba="cavanhaque", queixo=0.88, altura=183, peso=75,
         arr=7, vel=10, forca=3, defe=9, drible=22, dip=17, cross=22,
         tiro="rapido", set_point=28, ext=0.18, hop=9.9, arm=30,
         tenis=((238, 240, 246), (216, 44, 60), (40, 62, 140), True), trim=(216, 44, 60), faixa=(28, 30, 38),
         manga=(28, 30, 38), joelheira=True, meia=6, oculos=False,
         dunks=[4], hab="crossover", cranio=0.96, ombros=0.88, envergadura=1.02, traco="CROSSOVER",
         traco_desc="drible relâmpago e bote de roubo sem descanso"),
    dict(nome="DUNCAN", num="21", cam=(44, 46, 52), cam_esc=(26, 28, 34),
         calc=(200, 200, 206), pele=(122, 80, 52), cabelo="curto",
         cor_cabelo=(24, 20, 18), barba="nao", queixo=1.08, altura=211, peso=113,
         arr=7, vel=5, forca=9, defe=9, drible=40, dip=11, cross=3,
         tiro="normal", set_point=24, ext=0.32, hop=8.8, arm=32,
         tenis=((32, 34, 40), (232, 232, 236), (232, 232, 236), False), trim=(200, 200, 206), faixa=None,
         manga=None, joelheira=True, meia=4, oculos=False,
         dunks=[3], hab="fundamento", cranio=1.02, ombros=1.07, envergadura=1.03, traco="FUNDAMENTO",
         traco_desc="quando erra, a bola morre no aro e volta pra ele"),
    dict(nome="PIPPEN", num="33", cam=(24, 26, 34), cam_esc=(14, 16, 22),
         calc=(204, 22, 52), pele=(108, 70, 44), cabelo="careca",
         cor_cabelo=(22, 18, 16), barba="nao", queixo=0.90, altura=201, peso=103,
         arr=7, vel=8, forca=7, defe=10, drible=32, dip=14, cross=7,
         tiro="normal", set_point=26, ext=0.28, hop=9.9, arm=33,
         tenis=((240, 240, 244), (24, 26, 34), (204, 22, 52), True), trim=(204, 22, 52), faixa=None,
         manga=None, joelheira=True, meia=5, oculos=False,
         dunks=[5], hab="alicate", cranio=1.05, ombros=0.96, envergadura=1.11, traco="MÃOS DE ALICATE",
         traco_desc="alcança a bola de muito mais longe pra roubar"),
    dict(nome="DIRK", num="41", cam=(14, 40, 92), cam_esc=(8, 26, 62),
         calc=(200, 200, 206), pele=(230, 194, 158), cabelo="loiro",
         cor_cabelo=(188, 146, 90), barba="nao", queixo=0.96, altura=213, peso=111,
         arr=9, vel=5, forca=8, defe=6, drible=38, dip=12, cross=4,
         tiro="fadeaway", set_point=34, ext=0.24, hop=9.2, arm=36,
         tenis=((238, 240, 246), (14, 40, 92), (200, 200, 206), False), trim=(200, 200, 206), faixa=None,
         manga=None, joelheira=False, meia=6, oculos=False,
         dunks=[12], hab="flamingo", cranio=1.06, ombros=0.93, envergadura=1.02, traco="PERNA DE FLAMINGO",
         traco_desc="pula pra trás no arremesso e foge do toco"),
]

# Corpo de referencia (198 cm): quadril, tronco e alcance do braco somam a
# altura da mao acima dos pes. A cravada foi calibrada com essa soma, entao
# escalar o corpo escala o alcance junto -- e o salto se recalcula sozinho.
BODY_HIP = 58        # do chao ao quadril (~47% da altura total)
BODY_TORSO = 37.5    # do quadril ao ombro
# Raio do cranio. 5,9 cabecas de altura, nao as 7,5 da anatomia real: num
# corpo de 126 px na tela, cabeca realista da 17 px e nao cabe rosto
# nenhum dentro. O rosto inteiro e normalizado por este raio, entao olho,
# nariz, orelha e barba crescem junto.
BODY_HEAD_R = 11.8
# O centro da cabeca sai do PROPRIO raio: assim o cranio sempre encosta na
# gola. Com um numero solto, encolher a cabeca a fazia boiar sobre os ombros.
BODY_NECK = BODY_HEAD_R + 6.5
# altura da bola na mao, medida do OMBRO pra baixo -- e o que mantem a
# cravada e o arremesso alinhados com o corpo quando a proporcao muda
BODY_BALL_DROP = 6.0
BODY_REACH = 50      # do ombro a mao esticada pra cima
# (a soma quadril+tronco+braco agora e por jogador, em `Player.pilha`: o
# braco varia com a envergadura do perfil, entao ela nao cabe mais numa
# constante de modulo)
# Onde a mao precisa estar, medida dos PES, pra pousar sobre o aro. Sai da
# geometria (chao menos aro, mais uma folga), nao de um literal: escrito a
# mao, mudar a altura do aro deixava a cravada acontecendo POR BAIXO dele --
# o salto continuava resolvido pra altura antiga.
DUNK_HAND_ABOVE_FEET = (FLOOR_Y - RIM_Y) + 8

RIVAL_JERSEY = (46, 78, 174)
RIVAL_JERSEY_DARK = (28, 48, 120)
RIVAL_SHORTS = (22, 26, 38)


class RivalKeys:
    """Teclado falso: a IA anda pelo mesmo caminho que o jogador humano."""

    def __init__(self, esq=False, dir=False):
        self.esq, self.dir = esq, dir

    def __getitem__(self, k):
        if k in (pygame.K_a, pygame.K_LEFT):
            return self.esq
        if k in (pygame.K_d, pygame.K_RIGHT):
            return self.dir
        return 0

# Aro flexível: afunda com o peso do jogador pendurado e volta com mola ao soltar.
# É só visual — a pontuação continua usando RIM_Y fixo, pra não bagunçar a
# calibragem do arremesso.
RIM_FLEX_HANG = 15        # quanto o aro afunda com o jogador dependurado
RIM_FLEX_SPRING = 0.30
RIM_FLEX_DAMP = 0.78
RIM_SLAM_IMPULSE = 5.0    # tranco pra baixo no instante da cravada
HANG_MAX_FRAMES = 150     # rede de seguranca: nunca ficar preso no aro
POLE_X = BACKBOARD_X + 7

# --------------------------------------------------------------------------
# CORES
# --------------------------------------------------------------------------
NAVY_DARK = (18, 24, 43)
NAVY_MID = (33, 43, 74)
NAVY_LIGHT = (52, 66, 102)
WOOD_1 = (176, 118, 68)
WOOD_2 = (161, 104, 56)
WOOD_LINE = (120, 76, 40)
CREAM = (240, 231, 210)
WHITE = (255, 255, 255)
RED = (214, 63, 62)
ORANGE = (235, 122, 40)
ORANGE_DARK = (190, 90, 25)
BLACK = (20, 20, 20)
SKIN = (120, 76, 48)
GOLD = (255, 205, 60)
SKY_TOP = (24, 20, 46)
SKY_BOT = (70, 45, 90)

JERSEY = (204, 22, 52)      # vermelho de Chicago
JERSEY_DARK = (150, 14, 36)
SHORTS = (30, 34, 48)
SHOE = (235, 235, 235)
# Conjunto de moletom all black: a cor do time nao some, so muda de lugar --
# vai pro emblema, pro capuz, pros punhos e pra faixa da calca.
MOLETOM = (30, 30, 35)
MOLETOM_ESC = (18, 18, 22)
# a calca e do MESMO conjunto do casaco: com ela mais escura, a cintura
# virava a emenda de duas pecas diferentes
MOLETOM_CALCA = (29, 29, 34)
MEIA_COLOR = (240, 240, 244)   # meia branca
# (cabedal, detalhe do modelo, sola, cano alto) -- o par de cada jogador
TENIS_PADRAO = ((235, 235, 235), (204, 22, 52), (238, 238, 240), False)

try:
    # buffer curto = som logo no toque. Tem que vir ANTES do pygame.init():
    # depois dele o mixer já abriu com o tamanho padrão, e aí o quique sai
    # atrasado em relação à bola batendo no chão.
    pygame.mixer.pre_init(22050, -16, 2, 512)
except Exception:
    pass
pygame.init()
pygame.display.set_caption("Hoop Stars — Basquete 2D")
# SCALED: o jogo desenha sempre em 1000x600 e o pygame estica pro tamanho da
# janela mantendo a proporção. Nenhuma coordenada muda de lugar — inclusive a
# do mouse, que o pygame traduz de volta. Sem essa bandeira, tela cheia
# esticaria a imagem e o clique do arremesso cairia deslocado.
JANELA = 0 if NO_NAVEGADOR else pygame.SCALED
try:
    screen = pygame.display.set_mode((WIDTH, HEIGHT), JANELA)
except Exception:
    # SCALED precisa de um renderizador; numa máquina sem ele, abrir em janela
    # comum é melhor que não abrir. Perde-se a tela cheia, não o jogo.
    JANELA = 0
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
clock = pygame.time.Clock()


def alternar_tela_cheia():
    """Liga/desliga a tela cheia. Devolve o estado depois da troca.

    No navegador não faz nada: lá quem manda no tamanho é a página, e a tela
    cheia é a do próprio navegador. E é embrulhado em try porque um ambiente
    sem vídeo de verdade (o modo dummy dos testes) recusa a troca — o certo ali
    é seguir jogando em janela, não quebrar.
    """
    if NO_NAVEGADOR:
        return False
    try:
        pygame.display.toggle_fullscreen()
        return bool(pygame.display.get_surface().get_flags() & pygame.FULLSCREEN)
    except Exception:
        return False

def fonte(nome, tamanho):
    """Fonte do sistema, com recuo pra embutida.

    No navegador nao existe fonte de sistema nenhuma, e fora do Windows a
    Arial Black costuma faltar. Sem este recuo a falha acontece na CARGA do
    modulo: pagina em branco, sem mensagem. Todo texto e posicionado pela
    largura MEDIDA, entao trocar a fonte muda o traco mas nao desalinha nada."""
    if not NO_NAVEGADOR:
        try:
            return pygame.font.SysFont(nome, tamanho)
        except Exception:
            pass
    return pygame.font.Font(None, int(tamanho * 1.25))


FONT_BIG = fonte("arialblack", 54)
FONT_MED = fonte("arialblack", 30)
FONT_SMALL = fonte("arial", 20)
FONT_TINY = fonte("arial", 15)


# --------------------------------------------------------------------------
# SOM — sintetizado aqui dentro, sem arquivo nenhum
# --------------------------------------------------------------------------
# O jogo é um .py só. Um banco de .wav ao lado quebraria isso: o build web teria
# que empacotar a pasta e o executável teria que desempacotar em algum lugar.
# Então cada som é uma conta curta, montada uma vez na abertura.
SOM_HZ = 22050


def _para_som(amostras, vol=1.0, repetir=1):
    """Lista de floats em [-1, 1] vira um Sound estéreo de 16 bits.

    `repetir` reamostra para cima segurando cada valor: serve pros sons feitos
    numa taxa menor que a do mixer, onde o conteúdo é todo grave e as amostras
    intermediárias não carregam nada."""
    g = 32767.0 * vol
    par = []
    if repetir == 1:
        ap = par.append
        for v in amostras:
            if v > 1.0:
                v = 1.0
            elif v < -1.0:
                v = -1.0
            q = int(v * g)
            ap(q)      # os dois canais levam a mesma amostra
            ap(q)
    else:
        # extend de uma tupla pronta roda em C; um laço Python por amostra
        # custaria a montagem do laço em cada uma delas
        estende = par.extend
        bloco = 2 * repetir
        for v in amostras:
            if v > 1.0:
                v = 1.0
            elif v < -1.0:
                v = -1.0
            estende((int(v * g),) * bloco)
    return pygame.mixer.Sound(buffer=array.array("h", par).tobytes())


def _media_movel(a, janela):
    """Passa-baixa pobre e barato: tira o brilho do ruído branco.

    Sem isso, todo ruído do jogo soa igual — um chiado de rádio. É a largura da
    janela que separa "torcida ao longe" de "rede de barbante"."""
    if janela < 2:
        return a
    saida = [0.0] * len(a)
    soma = 0.0
    for i, v in enumerate(a):
        soma += v
        if i >= janela:
            soma -= a[i - janela]
        saida[i] = soma / min(i + 1, janela)
    return saida


def _ruido(n, semente=None):
    r = random.Random(semente).random
    return [r() * 2.0 - 1.0 for _ in range(n)]


def _quique(grave=False):
    """Couro no chão: o corpo CAI de tom enquanto decai, com um estalo por cima.

    Tom fixo soaria a tambor. A queda de tom é o que dá a leitura de bola."""
    dur = 0.22 if grave else 0.15
    n = int(SOM_HZ * dur)
    f0, f1 = (150.0, 48.0) if grave else (215.0, 68.0)
    out = [0.0] * n
    fase = 0.0
    r = random.Random()
    for i in range(n):
        t = i / SOM_HZ
        f = f1 + (f0 - f1) * math.exp(-t * 24.0)
        fase += 2 * math.pi * f / SOM_HZ
        estalo = r.uniform(-1, 1) * math.exp(-t * 200.0) * 0.5
        out[i] = (math.sin(fase) * 0.9 + estalo) * math.exp(-t * (22.0 if grave else 32.0))
    return out


def _aro():
    """Ferro do aro.

    As parciais são INARMÔNICAS de propósito: 438, 772, 1245… não são múltiplos
    de nada. Parcial harmônica sairia como nota de instrumento; é a razão
    quebrada que o ouvido lê como metal. E cada parcial aguda morre mais
    depressa que a grave, como no metal de verdade."""
    dur = 0.44
    n = int(SOM_HZ * dur)
    parciais = ((438.0, 1.00), (772.0, 0.58), (1245.0, 0.40),
                (1913.0, 0.24), (2687.0, 0.14))
    out = [0.0] * n
    for f, amp in parciais:
        # senoide amortecida por recorrência: y[n] = 2r·cos(w)·y[n-1] − r²·y[n-2].
        # Duas multiplicações por amostra, nenhum sin() nem exp() dentro do laço.
        w = 2 * math.pi * f / SOM_HZ
        r = math.exp(-(6.0 + f * 0.0042) / SOM_HZ)
        c, rr = 2 * r * math.cos(w), r * r
        y2, y1 = 0.0, amp * r * math.sin(w) * 0.42
        out[1] += y1
        for i in range(2, n):
            y = c * y1 - rr * y2
            out[i] += y
            y2, y1 = y1, y
    # o estalo do impacto some em ~20 ms: não tem por que percorrer o resto
    rnd = random.Random().random
    env, k = 0.42 * 0.6, math.exp(-260.0 / SOM_HZ)
    for i in range(min(n, 600)):
        out[i] += (rnd() * 2.0 - 1.0) * env
        env *= k
    return out


def _tabela():
    """Vidro da tabela: batida seca, quase sem cauda."""
    dur = 0.20
    n = int(SOM_HZ * dur)
    out = [0.0] * n
    r = random.Random()
    for i in range(n):
        t = i / SOM_HZ
        corpo = (math.sin(2 * math.pi * 286.0 * t) * 0.7
                 + math.sin(2 * math.pi * 1190.0 * t) * 0.25)
        out[i] = (corpo + r.uniform(-1, 1) * 0.5 * math.exp(-t * 150.0)) * math.exp(-t * 34.0)
    return out


def _rede():
    """Barbante: só o "sh", sem tom nenhum.

    Ruído passado por DIFERENÇA — um passa-alta de uma linha. A rede não tem
    altura definida; qualquer senoide aqui soaria a brinquedo."""
    dur = 0.30
    n = int(SOM_HZ * dur)
    br = _ruido(n + 1)
    out = [0.0] * n
    for i in range(n):
        t = i / SOM_HZ
        # ataque rápido e queda: a bola varre a rede e sai
        env = (1.0 - math.exp(-t * 180.0)) * math.exp(-t * 15.0)
        out[i] = (br[i + 1] - br[i]) * 0.5 * env
    return out


def _apito():
    """Apito: duas senoides quase juntas, com vibrato. A batida entre elas é o
    ronco do apito de verdade."""
    dur = 0.42
    n = int(SOM_HZ * dur)
    out = [0.0] * n
    for i in range(n):
        t = i / SOM_HZ
        vib = 1.0 + 0.012 * math.sin(2 * math.pi * 34.0 * t)
        env = min(1.0, t * 60.0) * min(1.0, (dur - t) * 26.0)
        out[i] = (math.sin(2 * math.pi * 2380.0 * vib * t) * 0.55
                  + math.sin(2 * math.pi * 2630.0 * vib * t) * 0.40) * env
    return out


# a torcida é sintetizada nesta fração da taxa do mixer e esticada na
# conversão: depois da média móvel de 90 amostras não sobra nada agudo ali, e
# gerar na taxa cheia seria fazer três amostras para cada uma que diz algo
TORCIDA_DIV = 3


def _torcida(dur=1.6, brilho=1.0):
    """Gente gritando longe: ruído grave com um inchaço lento.

    A média móvel larga é o que faz virar "muita gente a certa distância" em
    vez de chiado. O inchaço lento é o tempo que uma arquibancada leva pra
    reagir — reação instantânea soaria a efeito sonoro, não a público."""
    taxa = SOM_HZ / float(TORCIDA_DIV)
    n = int(taxa * dur)
    # um ruído só, com duas larguras de janela: a estreita dá o chiado da
    # multidão, a larga dá o corpo grave. Gerar dois ruídos era pagar dobrado
    # por algo que a média já descorrelaciona.
    br = _ruido(n)
    base = _media_movel(br, 26 // TORCIDA_DIV)
    corpo = _media_movel(br, 90 // TORCIDA_DIV)
    out = [0.0] * n
    # os dois envelopes são exponenciais em t, então andam por multiplicação
    sobe, k_sobe = 1.0, math.exp(-7.0 / taxa)
    desce, k_desce = 1.0, math.exp(-2.1 / taxa)
    inicio_queda = int(0.35 * taxa)
    g = 3.2 * brilho
    for i in range(n):
        sobe *= k_sobe
        if i >= inicio_queda:
            desce *= k_desce
        out[i] = (base[i] * g + corpo[i] * 5.0) * (1.0 - sobe) * desce
    return out


def _tenis():
    """Rangido de solado: tom agudo escorregando, com tremor."""
    dur = 0.15
    n = int(SOM_HZ * dur)
    out = [0.0] * n
    fase = 0.0
    for i in range(n):
        t = i / SOM_HZ
        f = 1520.0 - 620.0 * (t / dur)
        fase += 2 * math.pi * f / SOM_HZ
        trem = 0.72 + 0.28 * math.sin(2 * math.pi * 58.0 * t)
        env = min(1.0, t * 90.0) * math.exp(-t * 16.0)
        out[i] = math.sin(fase) * trem * env * 0.8
    return out


def _tapa():
    """Mão na bola: estalo curto, sem cauda."""
    dur = 0.11
    n = int(SOM_HZ * dur)
    br = _media_movel(_ruido(n), 3)
    out = [0.0] * n
    for i in range(n):
        t = i / SOM_HZ
        out[i] = (br[i] * 1.6 + math.sin(2 * math.pi * 195.0 * t) * 0.4) * math.exp(-t * 62.0)
    return out


def _cravada():
    """Cravada: o ferro do aro com um estrondo grave por baixo."""
    ferro = _aro()
    grave = _quique(grave=True)
    n = len(ferro)
    out = list(ferro)
    for i in range(min(n, len(grave))):
        out[i] = out[i] * 0.9 + grave[i] * 1.25
    return out


class Som:
    """Todo o áudio do jogo.

    Se o mixer não abrir — máquina sem placa, teste rodando headless, navegador
    que ainda não liberou áudio por falta de um clique do usuário — `ok` fica
    False e `toca` não faz nada. O jogo roda mudo em vez de quebrar, que é o
    comportamento certo: som é enfeite, partida é o produto.

    Cada nome guarda VÁRIAS gravações do mesmo som. O quique toca umas duas
    vezes por segundo o jogo inteiro; com uma amostra só, a repetição idêntica
    fica óbvia em dez segundos e passa a irritar.
    """

    # intervalo mínimo entre duas tocadas do mesmo som, em ms: sem isso a
    # colisão com o aro dispara o clangor várias vezes no mesmo quique
    ESPERA = {"aro": 70, "tabela": 90, "quique": 90, "tenis": 130, "rede": 120}

    # (nome, receita, volume, quantas gravações, esticar na conversão)
    # a ordem é a de urgência: o quique toca no primeiro drible, a torcida só
    # na primeira cesta, e até lá sobrou menu de sobra pra montá-la
    RECEITAS = (
        ("quique", _quique, 0.30, 3, 1),
        ("tenis", _tenis, 0.24, 2, 1),
        ("aro", _aro, 0.34, 2, 1),
        ("rede", _rede, 0.60, 2, 1),
        ("tapa", _tapa, 0.40, 2, 1),
        ("tabela", _tabela, 0.36, 1, 1),
        ("cravada", _cravada, 0.52, 1, 1),
        ("apito", _apito, 0.30, 1, 1),
        ("torcida", _torcida, 0.34, 1, TORCIDA_DIV),
        ("torcida_forte", lambda: _torcida(1.9, 1.5), 0.44, 1, TORCIDA_DIV),
    )

    def __init__(self):
        self.ok = False
        self.mudo = False
        self.banco = {}
        self._quando = {}
        self._fila = []
        try:
            if pygame.mixer.get_init() is None:
                pygame.mixer.init(SOM_HZ, -16, 2, 512)
            pygame.mixer.set_num_channels(16)
        except Exception:
            return
        self.ok = True
        # a fila é por GRAVAÇÃO, não por nome: com as três vozes do quique numa
        # entrada só, elas cairiam todas no mesmo quadro
        self._fila = [(nome, receita, vol, esticar)
                      for nome, receita, vol, vozes, esticar in self.RECEITAS
                      for _ in range(vozes)]

    def preparar(self, orcamento_ms=3.0 if NO_NAVEGADOR else 9.0):
        """Monta parte do banco e devolve True quando acabou.

        Sintetizar tudo no import custaria quase um segundo de tela preta antes
        do título — e no navegador, onde Python é bem mais lento, vários. Como
        nenhum som toca no menu, o banco é montado um por quadro ENQUANTO a
        tela de início já está na frente do jogador. `toca` de um som que ainda
        não nasceu não faz nada, que é o mesmo que ele já fazia com o mixer
        fechado."""
        if not self.ok:
            return True
        # por tempo, não por contagem: tapa custa 4 ms e torcida custa 40, e
        # "um som por quadro" deixaria a torcida estourar o orçamento sozinha
        fim = time.perf_counter() + orcamento_ms / 1000.0
        while self._fila:
            nome, receita, vol, esticar = self._fila.pop(0)
            try:
                self.banco.setdefault(nome, []).append(
                    _para_som(receita(), vol, esticar))
            except Exception:
                pass
            if time.perf_counter() >= fim:
                break
        return not self._fila

    def toca(self, nome, vol=1.0):
        if not self.ok or self.mudo:
            return
        agora = pygame.time.get_ticks()
        espera = self.ESPERA.get(nome, 0)
        if espera and agora - self._quando.get(nome, -9999) < espera:
            return
        self._quando[nome] = agora
        vozes = self.banco.get(nome)
        if not vozes:
            return
        som = random.choice(vozes)
        try:
            som.set_volume(max(0.0, min(1.0, vol)))
            som.play()
        except Exception:
            pass

    def alternar_mudo(self):
        self.mudo = not self.mudo
        if self.mudo:
            try:
                pygame.mixer.stop()
            except Exception:
                pass
        return self.mudo


SOM = Som()



# --------------------------------------------------------------------------
# ARQUIBANCADA — geometria (usada pelo fundo estático e pela torcida viva)
# --------------------------------------------------------------------------
# Vista de lado, as fileiras SOBEM afastando-se da quadra: a de baixo é a mais
# próxima (maior e mais clara) e a de cima a mais distante (menor e escura).
CROWD_ROWS = 7
STAND_TOP = 150            # fileira do fundo
STAND_BOTTOM = 404         # fileira da frente, logo acima do alambrado
STAND_RAIL_Y = 430         # mureta que separa a torcida da quadra


def stand_row_y(r, n=CROWD_ROWS):
    """Altura da fileira r (0 = fundo). O espaçamento cresce para baixo, que é
    o que dá a sensação de arquibancada se afastando."""
    k = r / (max(1, n - 1))
    return STAND_TOP + (STAND_BOTTOM - STAND_TOP) * (k ** 1.35)


def stand_row_scale(r):
    return 0.50 + 0.50 * (r / (CROWD_ROWS - 1))


def lerp_color(c1, c2, t):
    return tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3))


# --------------------------------------------------------------------------
# QUADRA EM PERSPECTIVA — projeção do piso
# --------------------------------------------------------------------------
# O jogo é em visão lateral. A faixa de FLOOR_Y até HEIGHT é o PLANO DO CHÃO:
# a largura da quadra (lateral a lateral) foge "pra dentro" da tela. Toda a
# pintura é gerada em coordenadas de quadra e projetada ponto a ponto.
VP_X = WIDTH / 2          # ponto de fuga
SPREAD = 0.22             # quanto as linhas se abrem ao vir pra frente
FLOOR_H = HEIGHT - FLOOR_Y
COURT_SS = 3              # supersampling do piso (desenha em 3x e reduz: antialias)


def floor_point(x, d):
    """x = posição ao longo da quadra; d = profundidade 0 (longe) a 1 (perto)."""
    y = FLOOR_Y + d * (HEIGHT - FLOOR_Y)
    sx = VP_X + (x - VP_X) * (1 + d * SPREAD)
    return sx, y


# Eixo lateral da quadra em "u": -1 = lateral de trás (d=0), +1 = lateral da
# frente (d=1), 0 = meio da quadra. LAT_HALF converte px de quadra em "u".
LAT_HALF = 520.0
RIM_CX = (RIM_LEFT + RIM_RIGHT) / 2.0     # centro do aro (825)
BASELINE_X = 878.0                        # linha de fundo, logo à direita do aro
M_PX = (RIM_CX - THREE_POINT_X) / 7.24    # px por metro, derivado DA REGRA DO JOGO
# Raio do arco de 3 escolhido para que o PONTO MAIS DISTANTE do arco caia, já
# projetado, exatamente em x = THREE_POINT_X — onde a regra dos 3 pontos começa
# no código. Assim a pintura ensina a regra em vez de mentir.
THREE_R = RIM_CX - (VP_X + (THREE_POINT_X - VP_X) / (1 + 0.5 * SPREAD))
FT_X = BASELINE_X - 5.80 * M_PX           # linha de lance livre (5,80 m do fundo)
FT_R = 1.80 * M_PX                        # raio do círculo do lance livre
RESTRICT_R = 1.25 * M_PX                  # semicírculo de não-carga
PAINT_U = 0.40                            # meia-largura do garrafão (em u)
CORNER_U = 0.84                           # retas de canto da linha de 3
SIDE_FAR_U = -0.96                        # lateral de trás
SIDE_NEAR_U = 0.93                        # lateral da frente
MID_X = 140.0                             # linha de meio-quadra (o resto fica fora)
CENTER_R = 1.80 * M_PX

WOOD_DEEP = (136, 82, 41)
WOOD_PALE = (203, 148, 92)
WOOD_SEAM = (68, 40, 20)
PAINT_STAIN = (108, 40, 28)
LINE_WHITE = (248, 244, 235)

# ------------------------------- QUADRAS -------------------------------
# Cada entrada e um CENARIO inteiro: ceu, piso, cor de linha, que fundo
# desenhar e como o publico se comporta. Uma quadra nova e uma linha a mais.
QUADRAS = [
    dict(id="arena", nome="ARENA",
         desc="ginásio lotado, luz de refletor",
         ceu=((24, 20, 46), (70, 45, 90)),
         piso="taco", piso_a=(136, 82, 41), piso_b=(203, 148, 92),
         linha=(248, 244, 235),
         fundo="arquibancada", fileiras=7, passo=20, bandeiras=0.14,
         refletor=True, chao_fundo=(34, 29, 50), publico="sentado"),
    dict(id="rua", nome="QUADRA DE RUA",
         desc="asfalto, alambrado e poste de luz",
         ceu=((26, 28, 58), (188, 104, 76)),        # fim de tarde na cidade
         piso="asfalto", piso_a=(56, 56, 64), piso_b=(108, 108, 116),
         linha=(212, 204, 178),
         fundo="rua", fileiras=2, passo=54, bandeiras=0.0,
         refletor=False, chao_fundo=(44, 44, 52), publico="em pe"),
    dict(id="ginasio", nome="GINÁSIO",
         desc="escola de dia, luz pelas janelas",
         ceu=((206, 214, 226), (128, 142, 164)),
         piso="taco", piso_a=(150, 100, 56), piso_b=(226, 186, 138),
         linha=(58, 66, 92),
         fundo="ginasio", fileiras=4, passo=30, bandeiras=0.04,
         refletor=False, chao_fundo=(104, 88, 72), publico="sentado"),
]


def court_xu(x, u):
    """Ponto de quadra (x ao longo, u lateral) -> pixel de tela.

    u=0 é a LINHA DE CENTRO da quadra, que é exatamente por onde o jogador
    anda; u=1 é a lateral próxima, na base da tela. Ou seja, a tela mostra a
    METADE da quadra que fica na frente dele. Antes o mapa punha o jogador
    atrás de toda a pintura, e embaixo da cesta ele parecia estar na lateral
    em vez de dentro do garrafão."""
    return floor_point(x, max(0.0, u))


def _ss(pt):
    """Tela -> coordenadas da superfície supersampleada do piso."""
    return (pt[0] * COURT_SS, (pt[1] - FLOOR_Y) * COURT_SS)


def _ring(cx, radius, a0, a1, steps=110):
    """Amostra um CÍRCULO REAL da quadra e devolve só a METADE PRÓXIMA, já
    projetada. A metade de trás fica além da linha de centro (atrás do
    jogador, fora da tela): se fosse desenhada, viraria um risco reto colado
    nos pés dele."""
    out = []
    for i in range(steps + 1):
        a = a0 + (a1 - a0) * i / steps
        u = radius * math.sin(a) / LAT_HALF
        if u < 0:
            if out:
                break          # já saiu da metade visível
            continue
        out.append(_ss(court_xu(cx + radius * math.cos(a), u)))
    return out


def _resample(pts, step):
    """Reamostra a polilinha em passos de comprimento ~constante, medindo sempre
    a partir do ÚLTIMO ponto emitido (senão uma curva bem amostrada colapsaria
    numa reta entre a primeira e a última amostra)."""
    out = [pts[0]]
    ax, ay = pts[0]
    for qx, qy in pts[1:]:
        while True:
            d = math.hypot(qx - ax, qy - ay)
            if d < step:
                break
            t = step / d
            ax, ay = ax + (qx - ax) * t, ay + (qy - ay) * t
            out.append((ax, ay))
    out.append(pts[-1])
    return out


def _wear(layer, pts, width, rng, alpha=238, color=LINE_WHITE, dashed=False):
    """Pinta uma linha da quadra com DESGASTE: cada trecho curto recebe um alpha
    um pouco diferente e de vez em quando um trecho quase apagado — tinta de
    quadra usada, não adesivo novo."""
    if len(pts) < 2:
        return
    pts = _resample(pts, (7.0 if dashed else 8.0) * COURT_SS)
    for i in range(len(pts) - 1):
        if dashed and i % 2:
            continue
        a = alpha * rng.uniform(0.88, 1.0)
        if rng.random() < 0.10:
            a *= rng.uniform(0.55, 0.80)
        c = (color[0], color[1], color[2], max(0, min(255, int(a))))
        p, q = pts[i], pts[i + 1]
        pygame.draw.line(layer, c, (int(p[0]), int(p[1])), (int(q[0]), int(q[1])), width)
        if width > 3 and not dashed:
            pygame.draw.circle(layer, c, (int(q[0]), int(q[1])), width // 2)


def _build_floor(q):
    """Piso da quadra + marcações de basquete, desenhado em 3x e reduzido no
    fim (antialias das elipses e das linhas). As cores vêm do cenário `q`."""
    SS = COURT_SS
    piso_a, piso_b, cor_linha = q["piso_a"], q["piso_b"], q["linha"]
    W, H = WIDTH * SS, FLOOR_H * SS
    floor = pygame.Surface((W, H))
    detail = pygame.Surface((W, H), pygame.SRCALPHA)   # veios, emendas
    rng = random.Random(20260909)

    # ---------------- tábuas ----------------
    # larguras levemente diferentes (crescendo com a proximidade) e tom próprio
    # por tábua, vindo de um passeio aleatório — nunca duas cores alternadas.
    edges, d = [], 0.0
    while d < 1.0:
        w = (0.047 + 0.052 * d) * rng.uniform(0.78, 1.24)
        edges.append((d, min(1.0, d + w)))
        d += w

    if q["piso"] == "asfalto":
        # asfalto: sem tábua e sem emenda. Uma base fria com manchas largas de
        # desgaste e rachaduras finas — recolorir a madeira deixaria o veio da
        # tábua aparecendo num chão que não tem tábua nenhuma.
        floor.fill(piso_a)
        for _ in range(320):
            mx, my = rng.uniform(0, W), rng.uniform(0, H)
            rr = rng.uniform(26, 150) * SS / 3.0
            t = rng.uniform(0.0, 1.0)
            cor = lerp_color(piso_a, piso_b, t * 0.75)
            pygame.draw.ellipse(detail, (*cor, rng.randint(16, 46)),
                                (mx - rr, my - rr * 0.34, rr * 2, rr * 0.68))
        for _ in range(70):
            cx0, cy0 = rng.uniform(0, W), rng.uniform(0, H)
            pts = [(cx0, cy0)]
            for _ in range(rng.randint(2, 5)):
                cx0 += rng.uniform(-40, 40) * SS / 3.0
                cy0 += rng.uniform(-14, 14) * SS / 3.0
                pts.append((cx0, cy0))
            escura = tuple(int(c * 0.62) for c in piso_a)
            for a, b in zip(pts, pts[1:]):
                pygame.draw.line(detail, (*escura, rng.randint(70, 130)),
                                 a, b, max(1, SS // 2))
        edges = []

    tone = 0.15
    for d0, d1 in edges:
        tone = max(-1.0, min(1.0, tone + rng.uniform(-0.62, 0.62)))
        base = lerp_color(piso_a, piso_b, 0.5 + 0.5 * tone)
        k = 0.84 + 0.30 * ((d0 + d1) * 0.5)            # mais luz na frente
        col = tuple(max(0, min(255, int(c * k))) for c in base)
        y0, y1 = d0 * H, d1 * H
        pygame.draw.rect(floor, col, (0, int(y0), W, int(y1 - y0) + 1))
        # chanfro da tábua: topo um tico mais escuro, base um tico mais clara
        ch = max(1, int((y1 - y0) * 0.22))
        pygame.draw.rect(floor, tuple(int(c * 0.93) for c in col), (0, int(y0), W, ch))
        pygame.draw.rect(floor, tuple(min(255, int(c * 1.05)) for c in col),
                         (0, int(y1) - ch, W, ch))

        # veios: linhas finas irregulares ao longo da tábua
        for _ in range(2 + rng.randrange(3)):
            gy = rng.uniform(y0 + 1.5 * SS, max(y0 + 1.6 * SS, y1 - 1.0 * SS))
            amp = rng.uniform(0.25, 1.1) * SS
            freq = rng.uniform(0.003, 0.011)
            ph = rng.uniform(0, 6.3)
            light = rng.random() < 0.32
            gc = (255, 236, 200, rng.randint(16, 32)) if light else \
                 (52, 28, 12, rng.randint(26, 58))
            pts = [(gx, gy + math.sin(gx * freq + ph) * amp
                    + math.sin(gx * freq * 3.7 + ph) * amp * 0.35)
                   for gx in range(0, W + 24 * SS, 9 * SS)]
            pygame.draw.lines(detail, gc, False, pts, max(1, SS - 1))

        # emenda entre tábuas: linha escura fina + um fio de luz embaixo
        pygame.draw.line(detail, (*WOOD_SEAM, 130), (0, int(y0)), (W, int(y0)), SS)
        pygame.draw.line(detail, (255, 226, 186, 26),
                         (0, int(y0) + SS), (W, int(y0) + SS), max(1, SS - 2))

        # emendas de topo (butt joints), escalonadas ao longo da tábua
        jx = rng.uniform(0, 190) * SS
        while jx < W:
            pygame.draw.line(detail, (*WOOD_SEAM, 120),
                             (int(jx), int(y0) + SS), (int(jx), int(y1)), max(1, SS - 1))
            jx += rng.uniform(120, 260) * SS

    floor.blit(detail, (0, 0))

    # ---------------- garrafão: taco tingido de vermelho escuro --------------
    tint = pygame.Surface((W, H), pygame.SRCALPHA)
    pygame.draw.polygon(tint, (*PAINT_STAIN, 168),
                        [_ss(court_xu(BASELINE_X, -PAINT_U)),
                         _ss(court_xu(FT_X, -PAINT_U)),
                         _ss(court_xu(FT_X, PAINT_U)),
                         _ss(court_xu(BASELINE_X, PAINT_U))])
    # fora de quadra (além das laterais): tábua mais escura
    pygame.draw.rect(tint, (34, 20, 10, 115),
                     (0, int(SIDE_NEAR_U * H), W, H))
    floor.blit(tint, (0, 0))

    # ---------------- verniz: faixas de brilho atravessando o piso -----------
    sheen = pygame.Surface((W, H), pygame.SRCALPHA)

    def streak(x_top, x_bot, half, layers, peak):
        for i in range(layers):
            hw = half * (1.0 - i / layers)
            pygame.draw.polygon(sheen, (255, 246, 224, peak),
                                [(x_top - hw, -4), (x_top + hw, -4),
                                 (x_bot + hw, H + 4), (x_bot - hw, H + 4)])

    streak(250 * SS, 540 * SS, 190 * SS, 20, 4)          # faixa principal
    streak(890 * SS, 1090 * SS, 120 * SS, 14, 4)         # reflexo perto da cesta
    streak(-40 * SS, 70 * SS, 85 * SS, 12, 3)            # reflexo à esquerda
    # halo quente do refletor atrás da tabela, caindo no chão
    for i in range(14):
        rr = (250 - i * 16) * SS
        pygame.draw.ellipse(sheen, (255, 224, 160, 5),
                            (int(RIM_CX * SS - rr), int(H * 0.30 - rr * 0.32),
                             int(rr * 2), int(rr * 0.64 * 2)))
    floor.blit(sheen, (0, 0))

    # ---------------- linhas brancas da quadra ----------------
    lines = pygame.Surface((W, H), pygame.SRCALPHA)
    LW = 3 * SS
    rl = random.Random(4242)

    def seg(a, b, w=LW, alpha=238):
        """a e b em coordenadas de quadra (x, u) — projetadas ponto a ponto."""
        pts = [_ss(court_xu(a[0] + (b[0] - a[0]) * i / 24.0,
                            a[1] + (b[1] - a[1]) * i / 24.0)) for i in range(25)]
        _wear(lines, pts, w, rl, alpha=alpha)

    # lateral próxima (a de trás fica fora da tela, atrás do jogador)
    y = _ss(court_xu(0, SIDE_NEAR_U))[1]
    _wear(lines, [(0, y), (W, y)], LW, rl, alpha=226)

    # LINHA DE FUNDO: da linha de centro até a lateral próxima
    seg((BASELINE_X, 0), (BASELINE_X, SIDE_NEAR_U))

    # GARRAFÃO: só a metade da frente (a de trás está atrás do jogador)
    seg((BASELINE_X, PAINT_U), (FT_X, PAINT_U))
    seg((FT_X, 0), (FT_X, PAINT_U))

    # blocos e marcas do garrafão, pra fora da linha do lane
    for s in (1,):
        blk = [_ss(court_xu(BASELINE_X - 1.75 * M_PX, s * PAINT_U)),
               _ss(court_xu(BASELINE_X - 2.60 * M_PX, s * PAINT_U)),
               _ss(court_xu(BASELINE_X - 2.60 * M_PX, s * (PAINT_U + 0.075))),
               _ss(court_xu(BASELINE_X - 1.75 * M_PX, s * (PAINT_U + 0.075)))]
        pygame.draw.polygon(lines, (*cor_linha, 196), blk)
        for dist in (3.45, 4.30, 5.15):
            bx = BASELINE_X - dist * M_PX
            _wear(lines, [_ss(court_xu(bx, s * PAINT_U)),
                          _ss(court_xu(bx, s * (PAINT_U + 0.075)))],
                  max(2, LW - 2), rl, alpha=200)

    # CÍRCULO DO LANCE LIVRE: elipse achatada; a metade de dentro do garrafão
    # é tracejada, como na quadra de verdade.
    _wear(lines, _ring(FT_X, FT_R, math.pi / 2, 3 * math.pi / 2), LW, rl)
    _wear(lines, _ring(FT_X, FT_R, -math.pi / 2, math.pi / 2), LW, rl, dashed=True)

    # semicírculo de não-carga, debaixo da cesta
    _wear(lines, _ring(RIM_CX, RESTRICT_R, math.pi / 2, 3 * math.pi / 2),
          max(2, LW - 3), rl, alpha=205)
    _wear(lines, [_ss(court_xu(RIM_CX, RESTRICT_R / LAT_HALF)),
                  _ss(court_xu(BASELINE_X, RESTRICT_R / LAT_HALF))],
          max(2, LW - 3), rl, alpha=205)

    # ARCO DE 3 PONTOS — centrado no aro. O ponto mais distante cai EXATAMENTE
    # em THREE_POINT_X, que é onde a regra dos 3 pontos começa no código; nos
    # cantos vira reta, como no arco oficial.
    a_corner = math.asin(min(1.0, CORNER_U * LAT_HALF / THREE_R))
    x_corner = RIM_CX - THREE_R * math.cos(a_corner)
    _wear(lines, _ring(RIM_CX, THREE_R, math.pi - a_corner, math.pi + a_corner),
          LW, rl, alpha=246)
    seg((BASELINE_X, CORNER_U), (x_corner, CORNER_U), alpha=246)

    # rótulo discreto, PINTADO no chão do lado de fora do arco
    lab = fonte("arialblack", 21 * SS).render("3 PTS", True, cor_linha)
    lab = pygame.transform.smoothscale(lab, (int(lab.get_width() * 0.88),
                                             int(lab.get_height() * 0.44)))
    lab.set_alpha(132)
    lp = _ss(floor_point(268, 0.175))
    lines.blit(lab, (int(lp[0] - lab.get_width() / 2), int(lp[1] - lab.get_height() / 2)))

    floor.blit(lines, (0, 0))

    # um último véu de verniz por cima da tinta (a linha fica SOB o brilho)
    sheen.set_alpha(62)
    floor.blit(sheen, (0, 0))

    return pygame.transform.smoothscale(floor, (WIDTH, FLOOR_H))


# --------------------------------------------------------------------------
# FUNDO PRÉ-RENDERIZADO (gradiente do céu/ginásio + arquibancada + quadra)
# --------------------------------------------------------------------------
def _fundo_arquibancada(bg, q):
    """Degraus e alambrado. Só a ESTRUTURA — as pessoas são desenhadas a cada
    quadro pela classe Crowd."""
    n = q["fileiras"]
    for row in range(n):
        y = stand_row_y(row, n)
        prox = stand_row_y(row + 1, n) if row + 1 < n else STAND_RAIL_Y
        k = 0.42 + 0.58 * (row / max(1, n - 1))
        degrau = (int(30 * k + 16), int(26 * k + 14), int(44 * k + 22))
        pygame.draw.rect(bg, degrau, (0, int(y), WIDTH, int(prox - y) + 1))
        pygame.draw.line(bg, tuple(int(c * 1.35) for c in degrau),
                         (0, int(y)), (WIDTH, int(y)), 1)
    pygame.draw.rect(bg, (30, 26, 44), (0, STAND_RAIL_Y, WIDTH, 16))
    pygame.draw.line(bg, (86, 78, 112), (0, STAND_RAIL_Y), (WIDTH, STAND_RAIL_Y), 2)
    for x in range(0, WIDTH, 26):
        pygame.draw.line(bg, (58, 52, 78), (x, STAND_RAIL_Y + 2),
                         (x, STAND_RAIL_Y + 14), 1)


def _fundo_ginasio(bg, q):
    """Parede clara com janelas altas e uma arquibancada baixa, de escola."""
    pygame.draw.rect(bg, (168, 172, 186), (0, 0, WIDTH, STAND_TOP - 14))
    for x in range(30, WIDTH - 40, 118):
        jan = pygame.Rect(x, 40, 78, 96)
        pygame.draw.rect(bg, (214, 228, 240), jan)
        pygame.draw.rect(bg, (128, 132, 148), jan, 3)
        pygame.draw.line(bg, (128, 132, 148), (jan.centerx, jan.top),
                         (jan.centerx, jan.bottom), 2)
        pygame.draw.line(bg, (128, 132, 148), (jan.left, jan.centery),
                         (jan.right, jan.centery), 2)
    pygame.draw.rect(bg, (150, 154, 168), (0, STAND_TOP - 16, WIDTH, 16))
    n = q["fileiras"]
    for row in range(n):
        y = stand_row_y(row, n)
        prox = stand_row_y(row + 1, n) if row + 1 < n else STAND_RAIL_Y
        k = 0.55 + 0.45 * (row / max(1, n - 1))
        degrau = (int(96 * k + 40), int(78 * k + 34), int(62 * k + 28))
        pygame.draw.rect(bg, degrau, (0, int(y), WIDTH, int(prox - y) + 1))
        pygame.draw.line(bg, tuple(min(255, int(c * 1.28)) for c in degrau),
                         (0, int(y)), (WIDTH, int(y)), 1)
    pygame.draw.rect(bg, (74, 62, 52), (0, STAND_RAIL_Y, WIDTH, 16))
    pygame.draw.line(bg, (150, 130, 108), (0, STAND_RAIL_Y), (WIDTH, STAND_RAIL_Y), 2)


def _fundo_rua(bg, q):
    """Silhueta de prédios com janelas acesas, poste de luz e alambrado de
    tela. O alambrado vem por ÚLTIMO, na frente de tudo: é o que diz que a
    quadra é fechada por grade e não uma arquibancada aberta."""
    rng = random.Random(4242)
    # prédios, do mais distante (claro) ao mais próximo (escuro)
    for camada, (tom, alt0, alt1) in enumerate((
            ((58, 52, 78), 120, 190), ((40, 36, 58), 150, 250),
            ((26, 24, 40), 190, 300))):
        x = -20
        while x < WIDTH + 20:
            larg = rng.randint(52, 128)
            alt = rng.randint(alt0, alt1)
            topo = STAND_RAIL_Y - alt
            pygame.draw.rect(bg, tom, (x, topo, larg, alt))
            pygame.draw.line(bg, tuple(min(255, int(c * 1.4)) for c in tom),
                             (x, topo), (x + larg, topo), 2)
            if camada >= 1:
                for jy in range(topo + 14, STAND_RAIL_Y - 16, 22):
                    for jx in range(x + 8, x + larg - 10, 18):
                        if rng.random() < 0.34:
                            luz = (252, 214, 130) if rng.random() < 0.8 else (170, 206, 236)
                            pygame.draw.rect(bg, luz, (jx, jy, 7, 11))
            x += larg + rng.randint(2, 14)

    # poste de luz, com o cone caindo sobre a quadra
    px = 150
    pygame.draw.rect(bg, (34, 32, 40), (px - 4, STAND_RAIL_Y - 210, 8, 210))
    pygame.draw.line(bg, (34, 32, 40), (px, STAND_RAIL_Y - 208),
                     (px + 44, STAND_RAIL_Y - 224), 7)
    pygame.draw.ellipse(bg, (255, 238, 176), (px + 36, STAND_RAIL_Y - 232, 26, 16))
    cone = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    pygame.draw.polygon(cone, (255, 236, 170, 26),
                        [(px + 40, STAND_RAIL_Y - 224), (px - 130, HEIGHT),
                         (px + 250, HEIGHT)])
    bg.blit(cone, (0, 0))

    # mureta baixa de concreto onde o público se encosta
    pygame.draw.rect(bg, (62, 60, 70), (0, STAND_RAIL_Y, WIDTH, 16))
    pygame.draw.line(bg, (108, 106, 118), (0, STAND_RAIL_Y), (WIDTH, STAND_RAIL_Y), 2)


def _tela_alambrado(q):
    """A tela do alambrado, desenhada POR CIMA do público — é isso que põe as
    pessoas atrás da grade em vez de na frente dela."""
    if q["fundo"] != "rua":
        return None
    tela = pygame.Surface((WIDTH, STAND_RAIL_Y + 16), pygame.SRCALPHA)
    for x in range(-STAND_RAIL_Y, WIDTH + STAND_RAIL_Y, 17):
        pygame.draw.line(tela, (150, 154, 162, 54), (x, 0),
                         (x + STAND_RAIL_Y, STAND_RAIL_Y), 1)
        pygame.draw.line(tela, (150, 154, 162, 54), (x, STAND_RAIL_Y),
                         (x + STAND_RAIL_Y, 0), 1)
    for y in (STAND_RAIL_Y - 150, STAND_RAIL_Y - 80, STAND_RAIL_Y - 4):
        pygame.draw.line(tela, (176, 180, 188, 120), (0, y), (WIDTH, y), 3)
    for x in range(40, WIDTH, 190):
        pygame.draw.line(tela, (176, 180, 188, 130), (x, STAND_RAIL_Y - 210),
                         (x, STAND_RAIL_Y + 10), 4)
    return tela


def build_background(q):
    """Céu + fundo do cenário + piso. Cada quadra é uma entrada de QUADRAS."""
    bg = pygame.Surface((WIDTH, HEIGHT))
    ceu_topo, ceu_baixo = q["ceu"]
    for y in range(HEIGHT):
        t = y / HEIGHT
        pygame.draw.line(bg, lerp_color(ceu_topo, ceu_baixo, min(t * 1.4, 1)),
                         (0, y), (WIDTH, y))

    if q["fundo"] == "rua":
        _fundo_rua(bg, q)
    elif q["fundo"] == "ginasio":
        _fundo_ginasio(bg, q)
    else:
        _fundo_arquibancada(bg, q)

    # o refletor da cesta NÃO entra aqui: é desenhado por cima da torcida,
    # senão a multidão passaria na frente dele e o aro, que é o elemento mais
    # importante da tela, sumiria no meio do público.

    # entre o fim do fundo e o inicio do piso sobravam 74 px de CEU: no fim de
    # tarde da rua isso virava uma faixa laranja atravessando a tela
    pygame.draw.rect(bg, q["chao_fundo"],
                     (0, STAND_RAIL_Y + 16, WIDTH, FLOOR_Y - STAND_RAIL_Y - 16))
    bg.blit(_build_floor(q), (0, FLOOR_Y))
    pygame.draw.line(bg, tuple(int(c * 0.4) for c in q["piso_a"]),
                     (0, FLOOR_Y), (WIDTH, FLOOR_Y), 3)
    return bg


# os cenários são caros de montar (o piso vai em 3x), então cada um é
# construído uma vez só e guardado
_CENARIOS = {}


def cenario(q):
    """Fundo, tela do alambrado e RETRATO de uma quadra, montados sob demanda.

    O retrato e o fundo com uma passada do publico por cima: e o que a tela de
    escolha mostra. Sem ele a arena -- justamente a quadra lotada -- aparecia
    como uma caixa escura e vazia, porque a torcida so existe em tempo de jogo.
    """
    if q["id"] not in _CENARIOS:
        bg = build_background(q)
        grade = _tela_alambrado(q)
        retrato = bg.copy()
        Crowd(q).draw(retrato)
        if grade is not None:
            retrato.blit(grade, (0, 0))
        if q["refletor"]:
            retrato.blit(HOOP_GLOW, (RIM_CX - HOOP_GLOW.get_width() // 2,
                                     RIM_Y - HOOP_GLOW.get_height() // 2))
        _CENARIOS[q["id"]] = (bg, grade, retrato)
    return _CENARIOS[q["id"]]


def _build_hoop_glow():
    """Halo do refletor sobre a cesta. Vai por CIMA da torcida pra destacar o
    aro da multidão — sem ele o elemento mais importante da tela se perde."""
    r = 158
    s = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
    # primeiro escurece o fundo em volta da cesta, depois acende por cima:
    # é o contraste dos dois que descola o aro da multidão
    for i in range(20):
        pygame.draw.circle(s, (14, 10, 26, 9), (r, r), int(r * (1 - i / 20)))
    for i in range(24):
        pygame.draw.circle(s, (255, 238, 196, 15), (r, r), int(r * 0.72 * (1 - i / 24)))
    return s


HOOP_GLOW = _build_hoop_glow()


def rim_edge_y(flex):
    """Altura das duas pontas do aro afundado `flex` pixels. O aro é preso na
    tabela (lado direito), então a ponta da frente mergulha bem mais."""
    return RIM_Y + flex, RIM_Y + flex * 0.2


def draw_three_point_label(surface):
    """O rótulo dos 3 pontos agora é PINTADO NO CHÃO (ver _build_floor), junto
    do arco — nada de linha vertical dourada boiando no ar."""
    return


# --------------------------------------------------------------------------
# PARTICULAS
# --------------------------------------------------------------------------
class Particle:
    def __init__(self, x, y, color, vx=None, vy=None, life=40, size=5, gravity=0.25):
        self.x, self.y = x, y
        self.vx = vx if vx is not None else random.uniform(-4, 4)
        self.vy = vy if vy is not None else random.uniform(-7, -2)
        self.life = life
        self.max_life = life
        self.color = color
        self.size = size
        self.gravity = gravity

    def update(self):
        self.vy += self.gravity
        self.x += self.vx
        self.y += self.vy
        self.life -= 1

    def draw(self, surface):
        if self.life <= 0:
            return
        t = self.life / self.max_life
        s = max(1, int(self.size * t))
        alpha_surf = pygame.Surface((s * 2, s * 2), pygame.SRCALPHA)
        pygame.draw.circle(alpha_surf, (*self.color, int(255 * t)), (s, s), s)
        surface.blit(alpha_surf, (self.x - s, self.y - s))

    @property
    def alive(self):
        return self.life > 0


class FloatingText:
    def __init__(self, x, y, text, color, size=30, life=55):
        self.x, self.y = x, y
        self.text = text
        self.color = color
        self.life = life
        self.max_life = life
        self.font = FONT_MED if size >= 30 else FONT_SMALL

    def update(self):
        self.y -= 0.9
        self.life -= 1

    def draw(self, surface):
        if self.life <= 0:
            return
        t = self.life / self.max_life
        surf = self.font.render(self.text, True, self.color)
        surf.set_alpha(int(255 * t))
        rect = surf.get_rect(center=(self.x, self.y))
        surface.blit(surf, rect)

    @property
    def alive(self):
        return self.life > 0


# --------------------------------------------------------------------------
# TORCIDA — reage às cestas
# --------------------------------------------------------------------------
CROWD_SHIRTS = [(118, 126, 174), (152, 106, 152), (92, 134, 150),
                (162, 130, 100), (126, 102, 140), (98, 148, 130),
                (176, 96, 96), (108, 116, 132)]
CROWD_HEADS = [(214, 172, 132), (158, 112, 78), (112, 78, 54), (232, 196, 158)]
CROWD_HAIRS = [(46, 34, 28), (28, 22, 20), (92, 62, 34), (176, 148, 96),
               (60, 44, 40), (32, 28, 26)]
CAP_COLORS = [(206, 60, 62), (230, 196, 76), (60, 70, 130), (236, 236, 240)]
FLAG_COLORS = [(214, 60, 70), (240, 200, 70), (238, 238, 242)]




SPRITE_W, SPRITE_H = 34, 50    # torcedor desenhado grande e reduzido depois


def _draw_spectator(s, shirt, head_col, hair_col, cap_col, pose):
    """Desenha UM torcedor em tamanho grande: cabeça com rosto (olhos e boca
    que abre ao gritar), cabelo ou boné, tronco e braços."""
    cx = SPRITE_W // 2
    hy = 16                                  # centro da cabeça
    r = 10

    # --- tronco (ombros arredondados) ---
    corpo = pygame.Rect(cx - 11, hy + 7, 22, 27)
    pygame.draw.ellipse(s, shirt, corpo)
    pygame.draw.rect(s, shirt, (cx - 11, hy + 16, 22, 18))
    pygame.draw.line(s, tuple(int(c * 0.78) for c in shirt),
                     (cx, hy + 12), (cx, hy + 33), 1)      # dobra da camisa

    # --- braços ---
    for lado in (-1, 1):
        ombro = (cx + lado * 9, hy + 14)
        if pose == 0:
            cotovelo = (cx + lado * 12, hy + 24)
            mao = (cx + lado * 11, hy + 32)
        else:
            alt = 10 + pose * 7
            cotovelo = (cx + lado * 13, hy + 12 - alt * 0.45)
            mao = (cx + lado * (11 + pose * 2), hy + 10 - alt)
        pygame.draw.line(s, shirt, ombro, cotovelo, 5)
        pygame.draw.line(s, head_col, cotovelo, mao, 4)
        pygame.draw.circle(s, head_col, (int(mao[0]), int(mao[1])), 3)

    # --- cabeça ---
    pygame.draw.circle(s, head_col, (cx, hy), r)
    pygame.draw.circle(s, tuple(int(c * 0.66) for c in head_col), (cx, hy), r, 1)
    if cap_col is not None:                   # boné
        pygame.draw.circle(s, cap_col, (cx, hy - 1), r, draw_top_left=True,
                           draw_top_right=True)
        pygame.draw.ellipse(s, cap_col, (cx - r - 3, hy - 4, 10, 4))
    else:                                     # cabelo
        pygame.draw.circle(s, hair_col, (cx, hy - 2), r, draw_top_left=True,
                           draw_top_right=True)
        pygame.draw.rect(s, hair_col, (cx - r, hy - 3, r * 2, 3))

    # --- rosto ---
    olho = (28, 24, 22)
    pygame.draw.circle(s, olho, (cx - 4, hy + 1), 2)
    pygame.draw.circle(s, olho, (cx + 4, hy + 1), 2)
    if pose == 0:
        pygame.draw.line(s, olho, (cx - 3, hy + 6), (cx + 3, hy + 6), 1)
    else:
        # boca aberta: está gritando
        alt = 4 + pose * 2
        pygame.draw.ellipse(s, (86, 40, 44), (cx - 3, hy + 3, 6, alt))


def _build_spectator_sprites():
    """Pré-renderiza cada torcedor em 3 poses (parado, gritando com braços meio
    erguidos, gritando com braços no alto). São centenas de pessoas na tela:
    desenhar cada uma com primitivas todo frame sairia caro, então no jogo é só
    um blit por pessoa.

    Há uma cópia por FILEIRA, menor e mais escura quanto mais ao fundo — é o que
    dá profundidade à arquibancada e evita que a torcida colorida roube a
    atenção da quadra."""
    variantes = []
    for idx, shirt in enumerate(CROWD_SHIRTS):
        head_col = CROWD_HEADS[idx % len(CROWD_HEADS)]
        hair_col = CROWD_HAIRS[idx % len(CROWD_HAIRS)]
        cap_col = CAP_COLORS[idx % len(CAP_COLORS)] if idx % 3 == 0 else None
        poses = []
        for pose in range(3):
            s = pygame.Surface((SPRITE_W, SPRITE_H), pygame.SRCALPHA)
            _draw_spectator(s, shirt, head_col, hair_col, cap_col, pose)
            poses.append(s)
        variantes.append(poses)

    por_fileira = []
    for row in range(CROWD_ROWS):
        esc = stand_row_scale(row)
        k = 0.38 + 0.42 * (row / (CROWD_ROWS - 1))
        w, h = max(1, int(SPRITE_W * esc)), max(1, int(SPRITE_H * esc))
        linha = []
        for poses in variantes:
            reduzidas = []
            for s in poses:
                t = pygame.transform.smoothscale(s, (w, h))
                v = int(255 * k)
                t.fill((v, v, v, 255), special_flags=pygame.BLEND_RGBA_MULT)
                reduzidas.append(t)
            linha.append(reduzidas)
        por_fileira.append(linha)
    return por_fileira


def _build_flag_sprites():
    """Bandeirinhas em 4 quadros de tremulação, uma cópia por fileira (as de
    trás mais escuras, igual às pessoas)."""
    base = []
    for col in FLAG_COLORS:
        quadros = []
        for f in range(4):
            s = pygame.Surface((26, 30), pygame.SRCALPHA)
            pygame.draw.line(s, (74, 62, 54), (3, 2), (3, 29), 3)          # mastro
            ph = f * math.pi / 2
            cima, baixo = [], []
            for j in range(6):
                t = j / 5
                onda = math.sin(ph + t * 3.4) * 3.4 * t
                cima.append((4 + 19 * t, 3 + onda))
                baixo.append((4 + 19 * t, 15 + onda))
            pygame.draw.polygon(s, col, cima + baixo[::-1])
            pygame.draw.polygon(s, tuple(int(c * 0.7) for c in col),
                                cima + baixo[::-1], 1)
            quadros.append(s)
        base.append(quadros)

    por_fileira = []
    for row in range(CROWD_ROWS):
        esc = stand_row_scale(row)
        k = 0.38 + 0.42 * (row / (CROWD_ROWS - 1))
        w, h = max(1, int(26 * esc)), max(1, int(30 * esc))
        todas = []
        for quadros in base:
            reduzidos = []
            for s in quadros:
                t = pygame.transform.smoothscale(s, (w, h))
                v = int(255 * k)
                t.fill((v, v, v, 255), special_flags=pygame.BLEND_RGBA_MULT)
                reduzidos.append(t)
            todas.append(reduzidos)
        por_fileira.append(todas)
    return por_fileira


SPECTATOR_SPRITES = _build_spectator_sprites()
FLAG_SPRITES = _build_flag_sprites()


class Spectator:
    __slots__ = ("x", "y", "row", "var", "flag", "phase",
                 "delay", "timer", "jump", "jump_v")


class Crowd:
    """Arquibancada viva. Na cesta a comemoração SAI DA CESTA e se espalha pelos
    lados como uma onda — cada pessoa começa a pular com um atraso proporcional
    à distância dela até o aro, em vez de todo mundo pular junto."""

    WAVE_PX_POR_FRAME = 26.0

    def __init__(self, q=None):
        q = q or QUADRAS[0]
        self.q = q
        self.rng = random.Random(7)
        self.t = 0
        self.flashes = []
        self.people = []
        # enquanto isto durar a galera pula de verdade, e o cenário precisa ser
        # recomposto mais vezes: ver `Game._fundo_composto`
        self._festa = 0
        n = q["fileiras"]
        em_pe = q["publico"] == "em pe"
        for row in range(n):
            if em_pe:
                # na rua ninguém senta em degrau: fica em pé atrás da mureta,
                # quase tudo na mesma altura, com o fundo mais afastado
                y = STAND_RAIL_Y - 4 - row * 19
                esc = 1.0 - row * 0.08
            else:
                y = stand_row_y(row, n)
                esc = stand_row_scale(row)
            passo = max(9, int(q["passo"] * esc))
            if NO_NAVEGADOR:
                # mais espaçada: menos gente na MESMA área. O público é cenário
                # a 400 px de distância — ninguém conta cabeça, e cada pessoa é
                # uma travessia Python->WASM a cada repinte do cache.
                passo = int(passo * 1.6)
            for x in range(-12, WIDTH + 24, passo):
                p = Spectator()
                # na rua a galera se junta em grupos, não em fila regular
                jitter = self.rng.randint(-14, 14) if em_pe else self.rng.randint(-3, 3)
                p.x = x + jitter
                p.y = y
                p.row = row
                p.var = self.rng.randrange(len(CROWD_SHIRTS))
                p.flag = (self.rng.randrange(len(FLAG_COLORS))
                          if self.rng.random() < q["bandeiras"] else -1)
                p.phase = self.rng.uniform(0, 6.283)
                p.delay = 0
                p.timer = 0
                p.jump = 0.0
                p.jump_v = 0.0
                self.people.append(p)

    def cheer(self, origin_x, strength=1.0):
        # as pessoas passam a pular de verdade: enquanto isso durar, congelar o
        # cenário por quatro quadros apareceria
        self._festa = 120
        for p in self.people:
            atraso = int(abs(p.x - origin_x) / self.WAVE_PX_POR_FRAME)
            p.delay = atraso
            p.timer = max(p.timer, int((36 + self.rng.randrange(20)) * strength))
        # flashes de câmera pipocando na arquibancada durante a comemoração
        for _ in range(int(26 * strength)):
            self.flashes.append([self.rng.randrange(WIDTH),
                                 self.rng.randrange(int(STAND_TOP), int(STAND_BOTTOM)),
                                 self.rng.randrange(0, 46), 5])

    def update(self):
        self.t += 1
        rng = self.rng
        for p in self.people:
            if p.delay > 0:
                p.delay -= 1
            elif p.timer > 0:
                p.timer -= 1
                if p.jump <= 0.01 and p.jump_v <= 0.0:
                    p.jump_v = 2.3 + rng.random() * 1.7      # pula de novo
            if p.jump > 0.0 or p.jump_v > 0.0:
                p.jump_v -= 0.42
                p.jump += p.jump_v
                if p.jump < 0.0:
                    p.jump = 0.0
                    p.jump_v = 0.0
        vivos = []
        for f in self.flashes:
            if f[2] > 0:
                f[2] -= 1
                vivos.append(f)
            elif f[3] > 0:
                f[3] -= 1
                vivos.append(f)
        self.flashes = vivos
        if self._festa > 0:
            self._festa -= 1

    def draw(self, surface):
        """A torcida pintada direto na superfície que vier.

        No navegador quem chama isto é o cache do CENÁRIO (ver
        `Game._fundo_composto`), que compõe fundo, público, alambrado e
        refletor numa imagem opaca só. A torcida não guarda mais cache
        próprio: o dela deixava de pé justamente a metade cara da conta, uma
        blit de tela cheia COM ALFA a cada quadro."""
        return self._pintar(surface)

    def _pintar(self, surface, flashes=True):
        t = self.t
        for p in self.people:
            comemorando = p.timer > 0 and p.delay <= 0
            pose = (2 if p.jump > 1.5 else 1) if comemorando else 0
            bob = math.sin(t * 0.05 + p.phase) * 1.2
            spr = SPECTATOR_SPRITES[p.row][p.var][pose]
            w, h = spr.get_size()
            # ancorado pelos PÉS: assim o pulo levanta a pessoa da bancada
            y = p.y - h + bob - p.jump
            surface.blit(spr, (p.x - w // 2, y))
            if p.flag >= 0:
                vel = 0.42 if comemorando else 0.12
                fl = FLAG_SPRITES[p.row][p.flag][int(t * vel + p.phase * 2) % 4]
                surface.blit(fl, (p.x + w // 3, y - fl.get_height() // 2))
        if flashes:
            self._flashes(surface)

    def _flashes(self, surface):
        for fx, fy, espera, vida in self.flashes:
            if espera <= 0 and vida > 0:
                r = 2 + vida // 2
                brilho = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
                pygame.draw.circle(brilho, (255, 255, 240, 40 * vida), (r, r), r)
                surface.blit(brilho, (fx - r, fy - r))


# --------------------------------------------------------------------------
# REDE (net) — cordas simples que balançam quando a bola passa
# --------------------------------------------------------------------------
def arco_pontos(cx, cy, r, a0, a1, n=20):
    """Pontos ao longo de um arco, em radianos, com y pra CIMA positivo."""
    if n < 2:
        n = 2
    return [(cx + r * math.cos(a0 + (a1 - a0) * i / (n - 1.0)),
             cy - r * math.sin(a0 + (a1 - a0) * i / (n - 1.0)))
            for i in range(n)]


def faixa_arco(surface, cor, cx, cy, r_int, r_ext, a0, a1):
    """Uma fatia de anel: o arco de fora na ida, o de dentro na volta.

    O pygame nao tem arco grosso preenchido -- `draw.arc` desenha linha fina e
    nao aceita espessura de verdade -- entao a faixa e montada como poligono.
    """
    if abs(a1 - a0) < 1e-4:
        return
    pts = (arco_pontos(cx, cy, r_ext, a0, a1)
           + arco_pontos(cx, cy, r_int, a1, a0))
    if len(pts) >= 3:
        pygame.draw.polygon(surface, cor, pts)


def _tabela_angulos(n):
    """Cosseno e seno dos nós, por paridade de anel. O ângulo de um nó só
    depende do índice e de o anel estar girado meio passo ou não — então isso
    é constante, e não tem por que voltar ao math a cada quadro."""
    passo = 2 * math.pi / n
    cos = [[math.cos((i + 0.5 * p) * passo) for i in range(n)] for p in (0, 1)]
    sen = [[math.sin((i + 0.5 * p) * passo) for i in range(n)] for p in (0, 1)]
    return cos, sen


def _rampa_fio(fundo, frente, n):
    """Rampa de cor do barbante, do fio do fundo ao da frente."""
    return [lerp_color(fundo, frente, k / (n - 1.0)) for k in range(n)]


class Net:
    """Rede de verdade: um tronco de cone de barbante.

    Os nós ficam em ANÉIS ao redor do aro, e cada anel é girado meio passo em
    relação ao de cima. Cada nó desce para os DOIS vizinhos do anel de baixo —
    são esses dois feixes cruzados que desenham o losango. (A versão anterior
    ligava fio vertical com anel horizontal, o que de perto lê como grade.)

    Cada nó carrega a profundidade dele: o seno do ângulo no anel, +1 do lado
    de cá e −1 do lado de lá. Os segmentos são pintados do fundo pra frente,
    escuros e finos atrás, claros e grossos na frente. É só isso que faz a
    rede parecer um tubo em vez de uma cortina pintada.

    A deformação é de anel — o raio abre (`bulge`) e o anel desce (`sag`) —
    com um tremor por nó (`jit`) por cima, pra malha não se mexer em bloco.
    Anel é a unidade certa porque é assim que a bola deforma uma rede: ela não
    empurra um barbante, ela estufa a circunferência inteira naquela altura.
    """

    # 12 x 9 dão 192 segmentos por quadro. No navegador cada segmento é uma
    # travessia Python->WASM, então a malha afina pra 8 x 6 = 80. Mais grossa,
    # ainda legível como losango — e isso num aro de 66 px de largura.
    STRANDS = 8 if NO_NAVEGADOR else 12      # nós em volta do anel
    ROWS = 6 if NO_NAVEGADOR else 9          # anéis ao longo do comprimento
    # o comprimento da rede é próximo do diâmetro do aro, como na de verdade
    LENGTH = 54
    TOP_R = (RIM_RIGHT - RIM_LEFT) / 2.0
    ESTREITA = 0.44          # quanto o cone fecha até a boca de baixo
    ELIPSE = 0.22            # achatamento do anel visto de lado
    MAX_BULGE = 16.0

    FIO_FRENTE = (250, 250, 253)
    FIO_FUNDO = (96, 99, 114)
    _COS, _SEN = _tabela_angulos(STRANDS)
    _CORES = _rampa_fio(FIO_FUNDO, FIO_FRENTE, 24)

    # a rede é pintada ampliada e reduzida com smoothscale: com linha dura o
    # barbante serrilha, e o resto do jogo já é supersampleado. No navegador,
    # onde SUPER cai pra 1, isso desliga junto.
    SS = 1 if NO_NAVEGADOR else 2
    CAIXA = pygame.Rect(RIM_LEFT - 30, RIM_Y - 6,
                        (RIM_RIGHT - RIM_LEFT) + 60, LENGTH + 54)

    def __init__(self):
        # estado por ANEL: o raio abre e o anel desce
        self.bulge = [0.0] * self.ROWS
        self.bv = [0.0] * self.ROWS
        self.sag = [0.0] * self.ROWS
        self.sv = [0.0] * self.ROWS
        # tremor por NÓ, pra malha não se mover em bloco
        self.jit = [[0.0] * self.STRANDS for _ in range(self.ROWS)]
        self.jv = [[0.0] * self.STRANDS for _ in range(self.ROWS)]
        # onda de cesta viajando pra baixo
        self.onda = 0.0
        self.onda_r = 0.0
        self._tela = pygame.Surface(
            (self.CAIXA.w * self.SS, self.CAIXA.h * self.SS), pygame.SRCALPHA)
        # a imagem pronta do ultimo quadro, e em que condicoes ela foi feita
        self._pronta = None
        self._pronta_parada = False
        self._pronta_flex = None
        self.parado = True

    # ------------------------------------------------------------------ forma
    def _raio(self, t):
        """Raio do anel a `t` do comprimento. O cone fecha mais depressa perto
        da boca, como a rede de verdade."""
        return self.TOP_R * (1.0 - self.ESTREITA * t ** 1.35)

    def _no(self, r, i, flex=0.0):
        """Posição na tela e profundidade do nó (r, i).

        Devolve (x, y, z) com z em [-1, 1]: +1 é o fio que está do lado de cá.
        """
        t = r / (self.ROWS - 1.0)
        passo = 2 * math.pi / self.STRANDS
        # anéis alternados giram meio passo: é daí que sai o losango
        ang = (i + 0.5 * (r % 2)) * passo
        cos_a, z = math.cos(ang), math.sin(ang)

        raio = self._raio(t) + self.bulge[r] * (1.0 if r else 0.0)
        cx = (RIM_LEFT + RIM_RIGHT) / 2.0
        x = cx + raio * cos_a + self.jit[r][i]

        # o aro inclina quando afunda: o anel inclina junto, interpolando a
        # altura das duas pontas na posição x do nó
        left_y, right_y = rim_edge_y(flex)
        u = (x - RIM_LEFT) / float(RIM_RIGHT - RIM_LEFT)
        base = left_y + (right_y - left_y) * max(0.0, min(1.0, u))
        # a frente do anel aparece MAIS BAIXA que o fundo: é a elipse vista de
        # lado, e é o que impede a rede de ler como um desenho plano
        y = base + 2 + self.LENGTH * t + raio * self.ELIPSE * z + self.sag[r]
        return x, y, z

    # --------------------------------------------------------------- estímulos
    def wiggle(self, strength=6.0):
        """Chacoalhada geral — aro tremendo, bola raspando."""
        for r in range(1, self.ROWS):
            t = r / (self.ROWS - 1.0)
            self.bv[r] += random.uniform(0.2, 1.0) * strength * 0.30 * t
            self.sv[r] += random.uniform(0.0, 1.0) * strength * 0.22 * t
            for i in range(self.STRANDS):
                self.jv[r][i] += random.uniform(-1, 1) * strength * 0.22 * t

    def swish(self, forca=1.0):
        """A animação da cesta: uma onda que DESCE pela rede.

        Um empurrão só, aplicado em tudo de uma vez, faz a rede inchar e
        desinchar como um balão. O que se vê numa cesta de verdade é a bola
        arrastando a deformação pra baixo, anel por anel, e a boca da rede
        chicoteando depois que ela sai. Por isso a onda tem uma frente que
        viaja: `onda_r` desce um pouco a cada quadro.
        """
        self.onda = max(self.onda, forca)
        self.onda_r = 0.0

    def push(self, ball):
        """A bola estufa os anéis na altura dela.

        Não é fio a fio: a bola tem 30px de diâmetro e a boca da rede tem 66,
        então ela abre a circunferência inteira daquela altura. Quanto mais
        rápido ela desce, mais a rede é arrastada junto.
        """
        for r in range(1, self.ROWS):
            # o nó de ângulo 0 está na borda lateral, onde a elipse não desloca
            # nada: o y dele É a altura do anel
            _, cy, _ = self._no(r, 0)
            t = r / (self.ROWS - 1.0)
            sep = cy - ball.y
            if abs(sep) > 30:
                continue
            cx = (RIM_LEFT + RIM_RIGHT) / 2.0
            # a bola só mexe na rede se estiver DENTRO dela
            if abs(ball.x - cx) > self._raio(t) + ball.RADIUS:
                continue
            w = 1.0 - abs(sep) / 30.0
            vel = min(abs(ball.vy), 26)
            # o quanto a bola é mais larga que o anel é o quanto ele tem que abrir
            aperto = max(0.0, ball.RADIUS - self._raio(t) * 0.72)
            self.bv[r] += w * (0.55 + aperto * 0.10 + vel * 0.055)
            self.sv[r] += w * (0.35 + vel * 0.050)
            for i in range(self.STRANDS):
                self.jv[r][i] += random.uniform(-1, 1) * w * 0.5

    # ----------------------------------------------------------------- física
    def update(self, ball=None):
        if ball is not None and not ball.held:
            self.push(ball)

        if self.onda > 0.0:
            for r in range(1, self.ROWS):
                # a frente de onda é estreita: é ela que dá a leitura de algo
                # descendo, em vez de a rede toda inchar junto
                w = max(0.0, 1.0 - abs(r - self.onda_r) * 0.85)
                if w > 0.0:
                    self.bv[r] += self.onda * 3.1 * w
                    self.sv[r] += self.onda * 1.9 * w
            self.onda_r += 0.62
            if self.onda_r > self.ROWS + 0.5:
                # chicote: a boca fecha e sobe depois que a bola sai
                b = self.ROWS - 1
                self.bv[b] -= self.onda * 2.4
                self.sv[b] -= self.onda * 2.6
                self.bv[b - 1] -= self.onda * 1.4
                self.onda = 0.0

        bulge0 = list(self.bulge)
        sag0 = list(self.sag)
        # o maior deslocamento de qualquer no: e o que diz se a rede ainda tem
        # o que mostrar ou se ja assentou
        mexe = 0.0
        for r in range(self.ROWS):
            if r == 0:
                # a boca de cima é amarrada no aro: não abre nem desce
                self.bulge[r] = self.sag[r] = 0.0
                self.bv[r] = self.sv[r] = 0.0
                continue
            viz = [bulge0[r + d] for d in (-1, 1) if 0 <= r + d < self.ROWS]
            # o anel é puxado pelos vizinhos: é o que faz a onda ESCORRER pela
            # rede em vez de cada anel viver a vida dele
            self.bv[r] += (sum(viz) / len(viz) - bulge0[r]) * 0.34
            self.bv[r] += -self.bulge[r] * 0.20
            self.bv[r] *= 0.885          # pouco amortecimento: sobra o chicote
            self.bulge[r] = max(-4.0, min(self.MAX_BULGE,
                                          self.bulge[r] + self.bv[r]))

            vizs = [sag0[r + d] for d in (-1, 1) if 0 <= r + d < self.ROWS]
            self.sv[r] += (sum(vizs) / len(vizs) - sag0[r]) * 0.30
            self.sv[r] += -self.sag[r] * 0.24
            self.sv[r] *= 0.87
            self.sag[r] = max(-6.0, min(18.0, self.sag[r] + self.sv[r]))

            for i in range(self.STRANDS):
                self.jv[r][i] += -self.jit[r][i] * 0.34
                self.jv[r][i] *= 0.84
                self.jit[r][i] = max(-4.0, min(4.0,
                                               self.jit[r][i] + self.jv[r][i]))
            mexe = max(mexe, abs(self.bulge[r]), abs(self.sag[r]),
                       max(map(abs, self.jit[r])))
        # meio decimo de pixel: abaixo disso o desenho novo cai nos mesmos
        # pixels do antigo, entao nao ha o que redesenhar
        self.parado = self.onda <= 0.0 and mexe < 0.05

    # ---------------------------------------------------------------- desenho
    def _nos(self, flex):
        """Todos os nós de uma vez, como (x, y, z).

        Mesma conta do `_no`, só que com o que é constante içado pra fora do
        laço: as tabelas de ângulo e a inclinação do aro.
        """
        left_y, right_y = rim_edge_y(flex)
        larg = float(RIM_RIGHT - RIM_LEFT)
        incl = (right_y - left_y) / larg
        cx = (RIM_LEFT + RIM_RIGHT) / 2.0
        elipse = self.ELIPSE
        linhas = []
        for r in range(self.ROWS):
            t = r / (self.ROWS - 1.0)
            raio = self._raio(t) + (self.bulge[r] if r else 0.0)
            cos_r = self._COS[r % 2]
            sen_r = self._SEN[r % 2]
            jit = self.jit[r]
            desce = 2 + self.LENGTH * t + self.sag[r]
            el = raio * elipse
            linha = []
            for i in range(self.STRANDS):
                x = cx + raio * cos_r[i] + jit[i]
                # a altura da ponta do aro na posição x do nó (o aro inclina
                # quando afunda); presa às bordas pra não extrapolar no bulge
                u = (x - RIM_LEFT)
                u = 0.0 if u < 0.0 else (larg if u > larg else u)
                z = sen_r[i]
                linha.append((x, left_y + u * incl + desce + el * z, z))
            linhas.append(linha)
        return linhas

    def _ligacoes(self, flex):
        """Os segmentos da malha, cada um com a profundidade média dele.

        Cada nó liga nos DOIS vizinhos do anel de baixo. Com os anéis girados
        meio passo, esses dois feixes se cruzam e fecham o losango.
        """
        nos = self._nos(flex)
        S = self.STRANDS
        segs = []
        ap = segs.append
        for r in range(self.ROWS - 1):
            baixo = nos[r + 1]
            # o outro vizinho muda de lado conforme o anel girou pra cá
            desloca = -1 if r % 2 == 0 else 1
            for i in range(S):
                ax, ay, az = nos[r][i]
                for k in (i, (i + desloca) % S):
                    bx, by, bz = baixo[k]
                    ap(((az + bz) * 0.5, ax, ay, bx, by))
        return segs

    def draw(self, surface, flex=0.0):
        if (self._pronta is not None and self.parado and self._pronta_parada
                and flex == self._pronta_flex):
            surface.blit(self._pronta, self.CAIXA.topleft)
            return
        segs = self._ligacoes(flex)
        # do fundo pra frente: quem está do lado de cá tapa quem está do lado
        # de lá, que é o que dá volume ao tubo
        segs.sort()
        ss = self.SS
        ox, oy = self.CAIXA.x, self.CAIXA.y
        tela = self._tela
        tela.fill((0, 0, 0, 0))
        cores = self._CORES
        linha = pygame.draw.line
        grosso, fino = 2 * ss, ss
        for z, ax, ay, bx, by in segs:
            cor = cores[int((z + 1.0) * 11.5)]
            linha(tela, cor, ((ax - ox) * ss, (ay - oy) * ss),
                  ((bx - ox) * ss, (by - oy) * ss),
                  grosso if z > -0.15 else fino)
        # guardada no tamanho FINAL: com SUPER ligado, reduzir de novo no
        # quadro seguinte custaria quase tanto quanto redesenhar
        self._pronta = (tela if ss == 1 else
                        pygame.transform.smoothscale(tela, self.CAIXA.size))
        self._pronta_parada = self.parado
        self._pronta_flex = flex
        surface.blit(self._pronta, self.CAIXA.topleft)


# --------------------------------------------------------------------------
# BOLA — couro laranja estilo Wilson NBA
# --------------------------------------------------------------------------
# A bola tem só 30 px de diâmetro, então ela é desenhada 4x maior numa surface
# própria e reduzida com smoothscale: as costuras e o sombreado esférico saem
# suaves em vez de serrilhados. Como a aparência só depende da rotação, as
# surfaces são cacheadas por "fatia" de ângulo.
BALL_SS = 4
BALL_ROT_STEPS = 48
BALL_SHADOW = (94, 36, 11)
BALL_MID = (216, 106, 32)
BALL_LIGHT = (255, 197, 130)
BALL_SEAM = (24, 15, 11)
_BALL_CACHE = {}

# pontinhos de couro (pebbling) em coordenadas locais do disco unitário
_PEBBLE = []
_prng = random.Random(31337)
while len(_PEBBLE) < 34:
    px, py = _prng.uniform(-1, 1), _prng.uniform(-1, 1)
    if 0.10 < math.hypot(px, py) < 0.86:
        _PEBBLE.append((px, py))
del _prng


def _ball_ramp(t):
    """Rampa de cor do couro: sombra -> laranja -> luz."""
    if t < 0.55:
        return lerp_color(BALL_SHADOW, BALL_MID, t / 0.55)
    return lerp_color(BALL_MID, BALL_LIGHT, (t - 0.55) / 0.45)


def _ball_seams(ang):
    """Costuras clássicas em coordenadas locais (disco unitário), já giradas:
    o 'equador', a perpendicular e os dois arcos curvos laterais."""
    curves = [[(t / 10.0, 0.0) for t in range(-10, 11)],      # equador
              [(0.0, t / 10.0) for t in range(-10, 11)]]      # perpendicular
    for s in (-1, 1):                                          # arcos laterais
        curve = []
        for i in range(-12, 13):
            v = i / 12.0
            curve.append((s * (0.30 + 0.52 * (1 - v * v)), 0.95 * v))
        curves.append(curve)
    ca, sa = math.cos(ang), math.sin(ang)
    return [[(x * ca - y * sa, x * sa + y * ca) for x, y in c] for c in curves]


def _build_ball_surface(ang):
    R, SS = Ball.RADIUS, BALL_SS
    pad = 2
    size = (R + pad) * 2 * SS
    c = size / 2.0
    r = R * SS
    surf = pygame.Surface((size, size), pygame.SRCALPHA)

    # --- volume esférico: círculos concêntricos deslocados pro alto/esquerda ---
    pygame.draw.circle(surf, BALL_SHADOW, (int(c), int(c)), int(r))
    steps = 22
    for i in range(1, steps + 1):
        t = i / steps
        rr = r * (1.0 - 0.68 * t)
        off = (r - rr) * 0.60
        pygame.draw.circle(surf, _ball_ramp(t), (int(c - off), int(c - off)), int(rr))
    # luz de retorno (bounce) na quina de baixo à direita, pra fechar a esfera
    bounce = pygame.Surface((size, size), pygame.SRCALPHA)
    pygame.draw.arc(bounce, (255, 150, 80, 70),
                    (c - r + SS, c - r + SS, 2 * (r - SS), 2 * (r - SS)),
                    -1.35, 0.35, max(2, int(SS * 1.4)))
    surf.blit(bounce, (0, 0))

    # --- textura de couro: pontinhos escuros discretos, girando com a bola ---
    peb = pygame.Surface((size, size), pygame.SRCALPHA)
    ca, sa = math.cos(ang), math.sin(ang)
    for px, py in _PEBBLE:
        x, y = px * ca - py * sa, px * sa + py * ca
        shade = 34 + int(46 * max(0.0, (x + y) * 0.5 + 0.5))   # some no lado claro
        pygame.draw.circle(peb, (90, 44, 18, shade),
                           (int(c + x * r * 0.94), int(c + y * r * 0.94)),
                           max(1, int(SS * 0.55)))
    surf.blit(peb, (0, 0))

    # --- costuras ---
    sw = max(2, int(SS * 1.7))
    for curve in _ball_seams(ang):
        pts = [(c + x * r * 0.97, c + y * r * 0.97) for x, y in curve]
        pygame.draw.lines(surf, BALL_SEAM, False, pts, sw)

    # --- brilho especular no canto superior esquerdo ---
    hi = pygame.Surface((size, size), pygame.SRCALPHA)
    for i in range(5):
        f = 1.0 - i / 5.0
        pygame.draw.ellipse(hi, (255, 246, 230, 26),
                            (c - r * 0.62 - r * 0.30 * f, c - r * 0.66 - r * 0.22 * f,
                             r * 0.60 * f + r * 0.18, r * 0.44 * f + r * 0.12))
    pygame.draw.ellipse(hi, (255, 252, 244, 120),
                        (c - r * 0.60, c - r * 0.64, r * 0.30, r * 0.21))
    surf.blit(hi, (0, 0))

    # --- contorno escuro fechando a silhueta ---
    pygame.draw.circle(surf, (38, 20, 10), (int(c), int(c)), int(r), max(2, int(SS * 0.9)))

    out = pygame.transform.smoothscale(surf, ((R + pad) * 2, (R + pad) * 2))
    return out


def ball_sprite(rotation):
    """Sprite da bola para uma rotação (cacheado por fatia de ângulo)."""
    key = int(round(rotation / (2 * math.pi) * BALL_ROT_STEPS)) % BALL_ROT_STEPS
    surf = _BALL_CACHE.get(key)
    if surf is None:
        surf = _build_ball_surface(key * 2 * math.pi / BALL_ROT_STEPS)
        _BALL_CACHE[key] = surf
    return surf


class Ball:
    RADIUS = 15

    def __init__(self):
        self.reset_state()

    def reset_state(self):
        self.x, self.y = 150, FLOOR_Y - 60
        self.vx, self.vy = 0.0, 0.0
        self.held = True
        self.rotation = 0.0
        self.touched_rim = False
        self.scored_this_flight = False
        self.in_air = False
        self.shot_origin_x = None
        self.ignore_rim = False
        self.so_na_descida = False
        self.trail = []

    def launch(self, vx, vy, origin_x):
        self.held = False
        self.vx, self.vy = vx, vy
        self.touched_rim = False
        self.scored_this_flight = False
        self.in_air = True
        self.shot_origin_x = origin_x
        self.ignore_rim = False
        self.so_na_descida = False

    def snap_to_hand(self, pos):
        self.x, self.y = pos
        self.vx = self.vy = 0
        self.held = True
        self.in_air = False

    def update(self):
        if self.held:
            return
        self.vy += GRAVITY
        self.x += self.vx
        self.y += self.vy
        self.rotation += self.vx * 4

        self.trail.append((self.x, self.y))
        if len(self.trail) > 8:
            self.trail.pop(0)

        # paredes laterais
        if self.x - self.RADIUS < 0:
            self.x = self.RADIUS
            self.vx *= -0.6
        if self.x + self.RADIUS > WIDTH:
            self.x = WIDTH - self.RADIUS
            self.vx *= -0.6

        # chão
        if self.y + self.RADIUS > FLOOR_Y:
            self.y = FLOOR_Y - self.RADIUS
            if abs(self.vy) > 1:
                # o volume sai da velocidade: bola despencando do aro bate
                # mais forte que bola rolando morta
                SOM.toca("quique", min(1.0, 0.25 + abs(self.vy) * 0.05))
                self.vy *= -0.55
                self.vx *= 0.85
            else:
                self.vy = 0
                self.vx *= 0.7

        # tabela (face frontal, bola vindo da esquerda)
        if (BACKBOARD_TOP < self.y < BACKBOARD_TOP + BACKBOARD_H
                and self.x + self.RADIUS > BACKBOARD_X and self.vx > 0
                and self.x < BACKBOARD_X + 20):
            self.x = BACKBOARD_X - self.RADIUS
            SOM.toca("tabela", min(1.0, 0.35 + abs(self.vx) * 0.05))
            self.vx *= -0.65
            self.touched_rim = True

        # postes do aro (colisão circular simples) — a bola cravada atravessa
        # o aro sem bater nos postes (a enterrada é garantida por design)
        for post_x in () if self.ignore_rim else (RIM_LEFT, RIM_RIGHT):
            dx, dy = self.x - post_x, self.y - RIM_Y
            dist = math.hypot(dx, dy)
            min_dist = self.RADIUS + 6
            if dist < min_dist and dist > 0.01:
                overlap = min_dist - dist
                nx, ny = dx / dist, dy / dist
                self.x += nx * overlap
                self.y += ny * overlap
                dot = self.vx * nx + self.vy * ny
                self.vx -= 2 * dot * nx
                self.vy -= 2 * dot * ny
                SOM.toca("aro", min(1.0, 0.30 + math.hypot(self.vx, self.vy) * 0.045))
                self.vx *= 0.7
                self.vy *= 0.7
                self.touched_rim = True

    def draw(self, surface):
        # rastro: cometa quente que afina e apaga pra trás
        n = len(self.trail)
        for i, (tx, ty) in enumerate(self.trail):
            f = (i + 1) / max(1, n)
            rad = max(2, int(self.RADIUS * (0.42 + 0.52 * f)))
            s = pygame.Surface((rad * 2, rad * 2), pygame.SRCALPHA)
            pygame.draw.circle(s, (255, 138, 52, int(70 * f * f)), (rad, rad), rad)
            pygame.draw.circle(s, (255, 196, 120, int(46 * f * f * f)),
                               (rad, rad), max(1, int(rad * 0.55)))
            surface.blit(s, (tx - rad, ty - rad))

        # couro Wilson: sprite pré-renderizado em 4x e reduzido (ver ball_sprite)
        sprite = ball_sprite(self.rotation)
        surface.blit(sprite, (int(self.x) - sprite.get_width() // 2,
                              int(self.y) - sprite.get_height() // 2))

    @property
    def rect(self):
        return pygame.Rect(self.x - self.RADIUS, self.y - self.RADIUS, self.RADIUS * 2, self.RADIUS * 2)


# --------------------------------------------------------------------------
# JOGADOR
# --------------------------------------------------------------------------
# --- HELPERS DE DESENHO DO PERSONAGEM ---
class Pincel:
    """Camada de desenho com escala e deslocamento próprios.

    Todo traço do personagem passa por aqui, e é isso que permite montá-lo numa
    superfície maior que a da tela e reduzi-la depois: a redução É o
    antisserrilhado, e vale pro corpo inteiro de uma vez. Sem isso seria
    preciso uma versão suavizada de cada primitiva — e o pygame não tem
    polígono suavizado."""

    def __init__(self, surf, k=1.0, ox=0.0, oy=0.0):
        self.s = surf
        self.k = k
        self.ox, self.oy = ox, oy

    def pt(self, p):
        return ((p[0] - self.ox) * self.k, (p[1] - self.oy) * self.k)

    def pts(self, ps):
        return [self.pt(p) for p in ps]

    def esp(self, n):
        """Espessura de traço: nunca desce de 1 px, senão o traço some."""
        return max(1, int(round(n * self.k)))

    def _rect(self, r):
        x, y, w, h = (r.x, r.y, r.width, r.height) if isinstance(r, pygame.Rect) else r
        return pygame.Rect(int(round((x - self.ox) * self.k)),
                           int(round((y - self.oy) * self.k)),
                           max(1, int(round(w * self.k))),
                           max(1, int(round(h * self.k))))

    def line(self, cor, a, b, w=1):
        pygame.draw.line(self.s, cor, self.pt(a), self.pt(b), self.esp(w))

    def polygon(self, cor, ps, w=0):
        pygame.draw.polygon(self.s, cor, self.pts(ps), self.esp(w) if w else 0)

    def circle(self, cor, c, r, w=0):
        px, py = self.pt(c)
        pygame.draw.circle(self.s, cor, (int(px), int(py)),
                           max(1, int(round(r * self.k))), self.esp(w) if w else 0)

    def ellipse(self, cor, r, w=0):
        pygame.draw.ellipse(self.s, cor, self._rect(r), self.esp(w) if w else 0)

    def arc(self, cor, r, a0, a1, w=1):
        pygame.draw.arc(self.s, cor, self._rect(r), a0, a1, self.esp(w))

    def rect(self, cor, r, w=0, border_radius=0):
        pygame.draw.rect(self.s, cor, self._rect(r), self.esp(w) if w else 0,
                         border_radius=max(0, int(round(border_radius * self.k))))

    def blit(self, src, pos):
        if self.k != 1.0:
            src = pygame.transform.smoothscale(
                src, (max(1, int(round(src.get_width() * self.k))),
                      max(1, int(round(src.get_height() * self.k)))))
        self.s.blit(src, self.pt(pos))


def ease_out_cubic(t):
    """Ease-out cúbica: a grandeza muda rápido no início e desacelera suavemente
    no fim. Usada nos instantes de "impacto" (aterrissagem, arremesso, slam)."""
    t = 0.0 if t < 0 else (1.0 if t > 1 else t)
    return 1 - (1 - t) ** 3


def ease_out_quad(t):
    """Variante mais suave da ease-out, usada nas fases de preparo (windup)."""
    t = 0.0 if t < 0 else (1.0 if t > 1 else t)
    return 1 - (1 - t) ** 2


def ease_antecipa(t, recuo=0.26):
    """Ease com ANTECIPACAO: recua antes de disparar, e assenta no fim.

    E o que separa um gesto de um teleporte. Sem o recuo, o braço simplesmente
    aparece na posição final — foi o que deixava o bote e o toco "secos"."""
    t = 0.0 if t < 0 else (1.0 if t > 1 else t)
    if t < 0.28:
        return -recuo * math.sin(t / 0.28 * math.pi)
    k = (t - 0.28) / 0.72
    # o 1.06 passa um pouco do alvo e volta: o amortecimento do fim do gesto
    return 1.06 * (1 - (1 - k) ** 3) - 0.06 * math.sin(k * math.pi)


def ease_in_out(t):
    """Começa e termina suave, acelerando no meio. Usada no salto em direção
    à cesta, pra o deslocamento não arrancar de repente."""
    t = 0.0 if t < 0 else (1.0 if t > 1 else t)
    return t * t * (3 - 2 * t)


def _shade(color, factor):
    """Clareia (factor>1) ou escurece (factor<1) uma cor — sombreamento simples
    de 2 tons por peça de roupa/pele, pra sugerir volume sem poluir o traço."""
    return tuple(max(0, min(255, int(c * factor))) for c in color)


# Direcao da luz da arena, usada por todo membro cilindrico: de cima e da
# frente. E o que mantem o brilho coerente entre pecas desenhadas em ordens
# diferentes.
LUZ_X, LUZ_Y = 0.45, -0.89


def _lift(color, n):
    """Clareia SOMANDO luz, em vez de multiplicar como o _shade.

    Num tecido quase preto o _shade não separa nada: (30,30,35) vezes 1,3 dá
    (39,39,45), que o olho lê como a mesma cor. Toda a forma do moletom
    depende disto — sem somar luz, o tronco fica uma laje chapada por mais
    faixas que se desenhe."""
    return tuple(max(0, min(255, int(c + n))) for c in color)


def draw_limb(d, p1, p2, w1, w2, color, outline=None,
              w_meio=None, t_meio=0.40):
    """Desenha um segmento de membro (coxa/panturrilha, bíceps/antebraço).

    A largura passa por até TRÊS estações: p1 (raio w1), um ponto intermediário
    em `t_meio` (raio `w_meio`) e p2 (raio w2). Sem a do meio o segmento é um
    cone — e cone lê como tubo, não como músculo. Num corpo real o ponto mais
    grosso não fica na ponta: a panturrilha incha logo abaixo do joelho, o
    bíceps no meio do braço.

    O volume vem de QUATRO faixas ao longo do eixo — borda em sombra, base,
    brilho e a borda que curva de volta pra luz. Com duas metades, claro de um
    lado e escuro do outro, a costura no meio ficava dura e o membro lia como
    duas placas coladas. As pontas são arredondadas: cortadas reto, os braços
    e as pernas pareciam tábuas."""
    vx, vy = p2[0] - p1[0], p2[1] - p1[1]
    comp = math.hypot(vx, vy)
    if comp < 0.01:
        return
    px, py = -vy / comp, vx / comp          # perpendicular ao eixo
    # orienta a perpendicular pela LUZ, e não pela ordem em que o segmento foi
    # desenhado: senão o brilho cai de um lado no braço e do outro na perna
    if px * LUZ_X + py * LUZ_Y < 0:
        px, py = -px, -py
    escuro = _shade(color, 0.58)
    claro = _shade(color, 1.22)
    meio_cor = _shade(color, 1.06)

    estacoes = ([(0.0, w1), (t_meio, w_meio), (1.0, w2)] if w_meio is not None
                else [(0.0, w1), (1.0, w2)])

    def ponto(t, w, lado):
        return (p1[0] + vx * t + px * w * lado, p1[1] + vy * t + py * w * lado)

    def faixa(l0, l1, cor):
        d.polygon(cor, [ponto(t, w, l0) for t, w in estacoes] +
                       [ponto(t, w, l1) for t, w in reversed(estacoes)])

    # Pontas arredondadas. Quase sem escurecer, de propósito: a tampa cai em
    # cima do deltoide (que é desenhado no mesmo ponto) e de qualquer tom mais
    # escuro ela apaga o ombro inteiro. Arredondar é tudo o que ela precisa
    # fazer — a sombra da junta é do draw_joint e do deltoide.
    tampa = _lift(color, -5)
    d.circle(tampa, p1, w1)
    d.circle(tampa, p2, w2)

    faixa(-1.00, -0.42, escuro)
    faixa(-0.42, 0.12, color)
    faixa(0.12, 0.58, claro)
    faixa(0.58, 1.00, meio_cor)

    out_col = outline if outline is not None else _shade(color, 0.40)
    d.polygon(out_col, [ponto(t, w, 1) for t, w in estacoes] +
                       [ponto(t, w, -1) for t, w in reversed(estacoes)], 1)
    # fio de luz na aresta iluminada, a mesma que recebe a faixa clara — é o
    # que separa braço e perna escuros do fundo
    luz = [ponto(t, w, 0.92) for t, w in estacoes]
    for a, b in zip(luz, luz[1:]):
        d.line(_lift(color, 26), a, b, 1)


def draw_deltoide(d, ombro, cotovelo, raio, cor):
    """A massa arredondada do ombro, desenhada ANTES do braço.

    Sem ela o braço nasce de um corte reto no tronco e lê como peça encaixada.
    O centro é deslocado na direção do cotovelo, que é onde o deltoide de fato
    se apoia — centrado na junta, ele viraria só um disco."""
    dx, dy = cotovelo[0] - ombro[0], cotovelo[1] - ombro[1]
    comp = max(1e-3, math.hypot(dx, dy))
    cxd = ombro[0] + dx / comp * raio * 0.30
    cyd = ombro[1] + dy / comp * raio * 0.30
    d.circle(_lift(cor, -6), (cxd, cyd), raio)
    d.circle(_lift(cor, 6), (cxd + LUZ_X * raio * 0.26, cyd + LUZ_Y * raio * 0.26),
             raio * 0.76)
    d.circle(_lift(cor, 18),
             (cxd + LUZ_X * raio * 0.46, cyd + LUZ_Y * raio * 0.46),
             raio * 0.34)


def draw_joint(d, pos, radius, color):
    """Bolinha de junta (joelho/cotovelo) que suaviza a quebra entre dois
    segmentos, com um brilho deslocado pro alto.

    A variação é por SOMA e não por fator: em tecido quase preto, multiplicar
    por 0,62 tira pouca luz em valor absoluto mas o bastante pra virar um disco
    escuro visível no meio do braço."""
    d.circle(_lift(color, -6), pos, radius)
    d.circle(color, (pos[0], pos[1] - radius * 0.15), radius * 0.82)
    d.circle(_lift(color, 11), (pos[0], pos[1] - radius * 0.35), radius * 0.42)


def draw_hand(d, pos, f, aberta=False, snap=0.0, pele=SKIN, e=1.0):
    """Mão: um punho arredondado com o polegar marcado. Sem isso o braço
    terminava num toco e a silhueta ficava pobre.

    `snap` (0..1) quebra o punho pra baixo com os dedos apontando pro chão — o
    acompanhamento do arremesso, que é a imagem mais reconhecível da forma."""
    x, y = pos[0], pos[1]
    r = 2.9 * e
    d.circle(_shade(pele, 0.74), (x, y), r)
    d.circle(pele, (x - f * 0.5, y - 0.8), r * 0.78)
    d.circle(_shade(pele, 0.52), (x, y), r, 1)
    if snap > 0.02:
        for i in (-1.2, 0, 1.2):
            fim = (x + f * (2 + i) - f * 2 * snap, y + 3 + 6 * snap)
            d.line(pele, (x + f * i * 0.6, y + 1), fim, 2)
        d.line(_shade(pele, 0.66),
                         (x - f * 3, y - 1), (x - f * 1, y + 3 + 3 * snap), 2)
    elif aberta:
        for i in (-1, 0, 1):
            d.line(pele, (x, y),
                             (x + f * 5, y + i * 3), 2)
    else:
        d.line(_shade(pele, 0.7),
                         (x - f * 1, y - 3), (x + f * 3, y - 1), 2)   # polegar


# Perfil do tênis, em fração do comprimento (x) e da altura (y, positivo pra
# cima a partir do chão). Um molde só, escalado pelo porte do jogador.
TENIS_CABEDAL = [
    (-0.47, 0.16), (-0.51, 0.52), (-0.47, 0.86), (-0.32, 0.97),   # calcanhar
    (-0.12, 0.94), (0.06, 0.80), (0.22, 0.64),                    # peito do pé
    (0.42, 0.52), (0.54, 0.38), (0.57, 0.24), (0.52, 0.16),       # biqueira
]
TENIS_SOLA = [
    (-0.52, 0.00), (-0.55, 0.13), (-0.50, 0.24), (-0.20, 0.20),
    (0.16, 0.18), (0.46, 0.22), (0.58, 0.28), (0.60, 0.14),
    (0.54, 0.02), (0.20, -0.02), (-0.20, -0.02),
]


def draw_shoe(d, foot, f, e=1.0, tenis=TENIS_PADRAO, meia=0, atras=False):
    """Tênis de basquete de perfil: meia, cano, cabedal, entressola, sola e o
    detalhe de cor do modelo.

    `tenis` é (cabedal, detalhe, sola, cano_alto) — o par que cada jogador
    calça. O cano alto muda a silhueta do tornozelo, que é o que separa um
    Converse dos anos 80 de um tênis baixo moderno. `atras` escurece o pé de
    trás: sem isso os dois sapatos viram um bloco só numa vista de perfil."""
    base, detalhe, sola, alto = tenis
    if atras:
        base, detalhe, sola = (_lift(base, -26), _lift(detalhe, -26),
                               _lift(sola, -26))
    x, y = foot
    L, H = 21 * e, 11 * e

    def P(lista):
        return [(x + f * px * L, y - py * H) for px, py in lista]

    # a meia aparecendo entre a panturrilha e o cano
    if meia > 0:
        cor_meia = _lift(MEIA_COLOR, -26) if atras else MEIA_COLOR
        d.line(cor_meia, (x, y - H * 0.55), (x, y - H * 0.55 - meia * e),
               8 * e)
        d.line(_shade(cor_meia, 0.84), (x - 3.6 * e, y - H * 0.55 - meia * e),
               (x + 3.6 * e, y - H * 0.55 - meia * e), 1)

    if alto:
        # cano alto: o colarinho acolchoado subindo pelo tornozelo
        cano = [(-0.30, 0.88), (0.02, 0.84), (0.06, 1.30),
                (-0.26, 1.36), (-0.40, 1.12)]
        d.polygon(base, P(cano))
        d.polygon(_shade(base, 1.14), P([(-0.30, 0.88), (0.02, 0.84),
                                         (0.04, 1.06), (-0.28, 1.10)]))
        d.polygon(_shade(base, 0.52), P(cano), 1)

    # sola e entressola: acompanham a curva da biqueira em vez de cortar reto
    d.polygon(_shade(sola, 0.45), P(TENIS_SOLA))
    d.polygon(sola, P([(px, py + 0.10) for px, py in TENIS_SOLA[:8]] +
                      [(0.54, 0.16), (0.20, 0.12), (-0.20, 0.12)]))

    d.polygon(base, P(TENIS_CABEDAL))
    # luz no alto do cabedal e sombra na dobra do peito do pé
    d.polygon(_shade(base, 1.16), P([(-0.44, 0.86), (-0.32, 0.97),
                                     (-0.12, 0.94), (0.06, 0.80),
                                     (0.00, 0.70), (-0.30, 0.80)]))
    d.polygon(_shade(base, 0.70), P([(0.22, 0.64), (0.42, 0.52),
                                     (0.54, 0.38), (0.50, 0.30),
                                     (0.30, 0.44), (0.16, 0.54)]))
    d.polygon(_shade(base, 0.52), P(TENIS_CABEDAL), 1)

    # o detalhe do modelo, varrendo do calcanhar até a biqueira
    risco = P([(-0.40, 0.62), (-0.14, 0.42), (0.20, 0.34), (0.44, 0.36),
               (0.30, 0.26), (0.06, 0.24), (-0.22, 0.34), (-0.44, 0.48)])
    d.polygon(detalhe, risco)

    # cadarços, atravessando o peito do pé
    for i in range(3):
        t = 0.18 + i * 0.16
        d.line(_shade(base, 0.58),
               (x + f * (-0.22 + t) * L, y - (0.92 - t * 0.85) * H),
               (x + f * (-0.06 + t) * L, y - (0.74 - t * 0.85) * H), 1)


def _pts(cx, cy, f, r, lista):
    """Converte pontos em frações do raio pra coordenadas da tela."""
    return [(cx + f * x * r, cy + y * r) for x, y in lista]


# Silhueta da cabeça de perfil, em frações do raio. É a linha contínua da
# testa até a mandíbula — o que o olho usa pra reconhecer um rosto de lado.
# Os pontos marcados com `Q` são esticados pela largura de queixo do perfil.
PERFIL_TOPO = [(-0.88, -0.44), (-0.74, -0.74), (-0.48, -0.93),
               (-0.16, -1.02), (0.18, -1.00), (0.48, -0.90), (0.70, -0.72),
               (0.83, -0.48)]
PERFIL_FRENTE = [(0.80, -0.26), (0.78, -0.13), (0.99, 0.07), (0.83, 0.16),
                 (0.86, 0.27), (0.77, 0.38)]
PERFIL_QUEIXO = [(0.83, 0.58), (0.68, 0.78), (0.42, 0.88)]
PERFIL_TRAS = [(0.04, 0.86), (-0.32, 0.74), (-0.60, 0.52), (-0.80, 0.26),
               (-0.92, -0.06), (-0.93, -0.26)]


def pontos_cabeca(queixo, cranio=1.0):
    """A silhueta em frações do raio, com queixo e formato de crânio do perfil.

    `cranio` estica na vertical e ENCOLHE na horizontal na mesma proporção: o
    que muda é a forma, não o tamanho. Só esticar daria uma cabeça maior, que é
    outra coisa — e a cabeça já tem o tamanho certo.
    """
    pts = list(PERFIL_TOPO) + list(PERFIL_FRENTE)
    pts += [(x * queixo, y * queixo) for x, y in PERFIL_QUEIXO]
    pts += list(PERFIL_TRAS)
    if cranio != 1.0:
        larg = 1.0 / cranio
        pts = [(x * larg, y * cranio) for x, y in pts]
    return pts


def silhueta_cabeca(cx, cy, f, r, queixo, cranio=1.0):
    return _pts(cx, cy, f, r, pontos_cabeca(queixo, cranio))


def frente_cabeca(cx, cy, f, r, queixo, corte=-0.30, cranio=1.0):
    """A metade da frente da MESMA silhueta. Usar a silhueta em vez de uma
    elipse é o que faz a borda da luz acompanhar testa, nariz e queixo — de
    elipse, ela terminava num oval no meio da bochecha e lia como mancha."""
    frente = [p for p in pontos_cabeca(queixo, cranio) if p[0] > corte]
    return _pts(cx, cy, f, r, frente)


def draw_head(d, cx, cy, f, brow=0.0, mouth=0, pele=SKIN,
              cabelo="careca", cor_cabelo=(26, 20, 18), barba="nao",
              queixo=1.0, faixa=None, oculos=False, e=1.0, lingua=False,
              cranio=1.0):
    """Cabeça de perfil. `brow` (0..1) fecha a sobrancelha conforme a jogada
    exige esforço e `mouth` abre a boca (0 fechada, 1 entreaberta, 2
    escancarada). Pele, cabelo, barba e largura de queixo vêm do perfil — é o
    que dá um rosto próprio a cada um do elenco."""
    r = BODY_HEAD_R * e
    q = queixo

    def P(lista):
        return _pts(cx, cy, f, r, lista)

    # pescoço, saindo de dentro da mandíbula
    # pescoço: mais estreito que a mandíbula, senão vira uma laje sob a cabeça
    # O pescoço desce EXATAMENTE até a gola: nem curto (abre um vão entre a
    # cabeça e o tronco), nem comprido (a cabeça é desenhada depois do moletom,
    # então sobra como uma coluna de pele sobre o peito). Por isso o
    # comprimento sai de BODY_NECK, não de um número fixo.
    nl = (BODY_NECK - 3.0) / BODY_HEAD_R
    d.polygon(_shade(pele, 0.70),
              P([(-0.32, 0.48), (0.30, 0.56), (0.28, nl), (-0.36, nl)]))
    d.polygon(_shade(pele, 0.86),
              P([(0.02, 0.52), (0.30, 0.56), (0.28, nl), (0.00, nl)]))
    # SOMBRA DA MANDIBULA na garganta. A cabeça é desenhada depois e cobre o
    # alto do pescoço, então o que sobra desta faixa é exatamente a sombra que
    # o queixo projeta — e é ela que separa cabeça de pescoço. Sem isso os dois
    # ficam no mesmo tom e leem como uma peça só.
    d.polygon(_shade(pele, 0.50),
              P([(-0.36, 0.46), (0.32, 0.54), (0.30, 1.04), (-0.34, 0.96)]))

    # o afro é VOLUME de cabelo: vem antes do crânio pra sobrar por trás e por
    # cima, em vez de tapar o rosto
    if cabelo == "afro":
        d.ellipse(cor_cabelo, (cx - f * 1.30 * r, cy - 1.42 * r,
                               2.40 * r, 2.10 * r))
        d.ellipse(_shade(cor_cabelo, 1.3), (cx - f * 0.95 * r, cy - 1.30 * r,
                                            1.50 * r, 1.10 * r))

    sil = silhueta_cabeca(cx, cy, f, r, q, cranio)
    # base no tom de sombra; a luz entra depois, só na frente
    d.polygon(_shade(pele, 0.78), sil)
    d.polygon(pele, frente_cabeca(cx, cy, f, r, q, -0.34, cranio))
    d.polygon(_shade(pele, 1.10), frente_cabeca(cx, cy, f, r, q, 0.28, cranio))
    # maçã do rosto: uma sombra rasa separando a face da mandíbula
    d.ellipse(_shade(pele, 0.92), (cx + f * 0.16 * r, cy + 0.22 * r,
                                   0.62 * r, 0.40 * r))

    # --- cabelo, acompanhando a mesma silhueta do crânio ---
    if cabelo in ("curto", "loiro", "trancas"):
        fundo = 0.30 if cabelo == "loiro" else 0.18
        calota = list(PERFIL_TOPO) + [
            (0.72, -0.46 + fundo), (0.30, -0.70 + fundo),
            (-0.20, -0.78 + fundo), (-0.66, -0.56 + fundo)]
        d.polygon(cor_cabelo, P(calota))
        if cabelo == "loiro":
            # franja curta caindo na testa, o traço que separa Bird e Dirk
            # a franja SAI da calota em vez de ser uma cunha solta na testa
            d.polygon(cor_cabelo, P([(0.48, -0.90), (0.83, -0.48),
                                     (0.78, -0.26), (0.62, -0.36),
                                     (0.40, -0.72)]))
        elif cabelo == "trancas":
            for i, y in enumerate((-0.86, -0.70, -0.54)):
                d.line(_shade(cor_cabelo, 1.8),
                       (cx - f * 0.62 * r, cy + (y + 0.18) * r),
                       (cx + f * (0.40 - i * 0.10) * r, cy + y * r), 0.09 * r)
    d.polygon(_shade(pele, 0.46), sil, 1)
    # o mesmo fio de luz da roupa, na testa e no nariz: é a borda que encara a
    # luz da arena, e sem ela a cabeça também some no fundo
    luz = _pts(cx, cy, f, r, PERFIL_TOPO[-3:] + PERFIL_FRENTE[:3])
    for a, b in zip(luz, luz[1:]):
        d.line(_shade(pele, 1.28), a, b, 1)

    if faixa is not None:
        # banda atravessando a testa, por cima do cabelo. Em arco, contornava o
        # crânio inteiro e virava capacete.
        d.polygon(faixa, P([(-0.80, -0.52), (0.84, -0.46),
                            (0.82, -0.24), (-0.78, -0.30)]))
        d.polygon(_shade(faixa, 0.68), P([(-0.80, -0.52), (0.84, -0.46),
                                          (0.82, -0.24), (-0.78, -0.30)]), 1)

    if barba != "nao":
        # cavanhaque: a mancha do queixo acompanhando a curva da mandíbula.
        # Em quadrado, virava um adesivo preto colado embaixo da boca.
        # a barba nasce dos PONTOS do queixo, então acompanha a largura de
        # mandíbula do perfil em vez de flutuar perto dela
        d.polygon(cor_cabelo, P([(0.66, 0.36), (0.83 * q, 0.58 * q),
                                 (0.68 * q, 0.78 * q), (0.42 * q, 0.88 * q),
                                 (0.30, 0.64)]))
        if barba == "cheia":
            d.polygon(cor_cabelo, P([(-0.32, 0.74), (0.04, 0.86),
                                     (0.42 * q, 0.88 * q), (0.46 * q, 0.66 * q),
                                     (-0.10, 0.60), (-0.30, 0.52)]))

    # orelha, encaixada na borda de trás. Antes ela era 12% mais escura que a
    # pele — nesta escala, invisível. Com a cabeça maior ela cabe inteira, então
    # ganha concha, contorno e lóbulo.
    d.ellipse(_shade(pele, 0.94), (cx - f * 0.44 * r, cy - 0.10 * r,
                                   0.34 * r, 0.50 * r))
    d.ellipse(_shade(pele, 0.62), (cx - f * 0.38 * r, cy - 0.02 * r,
                                   0.22 * r, 0.30 * r))
    d.arc(_shade(pele, 0.44), (cx - f * 0.44 * r, cy - 0.10 * r,
                               0.34 * r, 0.50 * r), 1.1, 4.4, 1)

    # narina
    d.line(_shade(pele, 0.60), (cx + f * 0.86 * r, cy + 0.10 * r),
           (cx + f * 0.94 * r, cy + 0.09 * r), 0.08 * r)

    # olho: branco, íris e a linha dos cílios por cima
    ex, ey = cx + f * 0.50 * r, cy - 0.13 * r
    olho = (ex - 0.15 * r, ey - 0.10 * r, 0.30 * r, 0.21 * r)
    d.ellipse((242, 240, 234), olho)
    d.circle((58, 42, 30), (ex + f * 0.05 * r, ey + 0.01 * r), 0.09 * r)
    d.circle(BLACK, (ex + f * 0.05 * r, ey + 0.01 * r), 0.045 * r)
    # cílios: a linha escura em cima, que dá o peso da pálpebra
    d.line(_shade(pele, 0.38), (ex - 0.16 * r, ey - 0.09 * r),
           (ex + 0.15 * r, ey - 0.07 * r), 0.06 * r)

    # sobrancelha: um traço fino seguindo o arco, que desce com o esforço.
    # Em barra de 3 px ela tomava conta do rosto inteiro.
    by0 = ey - 0.26 * r + brow * 0.12 * r
    by1 = ey - 0.31 * r + brow * 0.20 * r
    cor_sobr = tuple((a + b) // 2 for a, b in zip(cor_cabelo, _shade(pele, 0.42)))
    d.line(cor_sobr, (cx + f * 0.26 * r, by0), (cx + f * 0.76 * r, by1), 0.09 * r)

    if oculos:
        # óculos de proteção: só o aro e o elástico — preenchida, a lente
        # cobria justamente o olho que ela emoldura
        d.ellipse((28, 30, 38), (ex - 0.24 * r, ey - 0.19 * r,
                                 0.48 * r, 0.38 * r), 0.07 * r)
        d.line((28, 30, 38), (ex - f * 0.24 * r, ey),
               (cx - f * 0.40 * r, cy - 0.02 * r), 0.07 * r)

    # boca
    if mouth == 0:
        d.line(_shade(pele, 0.52), (cx + f * 0.52 * r, cy + 0.36 * r),
               (cx + f * 0.80 * r, cy + 0.30 * r), 0.09 * r)
    else:
        alt = 0.22 if mouth == 1 else 0.40
        d.ellipse((78, 34, 38), (cx + f * 0.52 * r, cy + 0.30 * r - alt * r / 2,
                                 0.34 * r, alt * r))
        if lingua:
            # PRA FORA e pendendo pro lado, que é como ela era. O ponto antigo
            # era uma bolinha DENTRO da boca aberta — e valia pra todo mundo,
            # o que tirava do Jordan justamente o traço que leva o nome dela.
            d.polygon(TONGUE_COLOR,
                      [(cx + f * 0.58 * r, cy + 0.34 * r),
                       (cx + f * 0.86 * r, cy + 0.40 * r),
                       (cx + f * 1.02 * r, cy + 0.66 * r),
                       (cx + f * 0.82 * r, cy + 0.74 * r),
                       (cx + f * 0.62 * r, cy + 0.52 * r)])
            d.polygon(_shade(TONGUE_COLOR, 0.80),
                      [(cx + f * 0.86 * r, cy + 0.40 * r),
                       (cx + f * 1.02 * r, cy + 0.66 * r),
                       (cx + f * 0.90 * r, cy + 0.70 * r),
                       (cx + f * 0.80 * r, cy + 0.48 * r)])


SHOE_SOLE = (40, 42, 48)
BAND_COLOR = (235, 235, 240)   # munhequeira branca
TONGUE_COLOR = (214, 108, 118)  # a língua de fora na hora de cravar
STRIPE_COLOR = (235, 235, 240)
# --- FIM DOS HELPERS ---


class Player:
    SPEED = 5
    WIDTH = 40
    HEIGHT = 90
    SHOOT_FRAMES = 22
    DUNK_FRAMES = 34
    DUNK_WINDUP_FRAC = 0.31  # fim do preparo: a mão chega no aro e crava
    LAND_SQUASH_FRAMES = 14  # duração do "estalo" de aterrissagem (ease-out)
    DRIBBLE_PERIOD = 38      # frames por quique
    DRIBBLE_HAND_DIP = 14    # quanto a mão desce empurrando a bola
    DRIBBLE_SNAP = 0.6       # <1 = a bola sai da mão com velocidade, sem "grudar"

    def __init__(self):
        self.x = 150
        self.y = FLOOR_Y  # posição dos pés
        self.facing = 1
        self.state = "idle"
        self.anim_t = 0.0
        self.jump_vel = 0.0
        self.jumping = False
        self.jump_offset = 0.0
        self.number = "23"
        self.action = None       # None | "shoot" | "dunk"
        self.action_timer = 0
        self.dribbling = False
        self.shot_angle = -math.pi / 3
        self.land_timer = 0      # frames restantes do "estalo" de aterrissagem
        self.suspended = False   # True enquanto está pendurado no aro (física pausada)
        self.dunk_start_x = 0.0  # de onde saltou para cravar
        self.dunk_target_x = 0.0 # onde precisa chegar para a mão cair sobre o aro
        self.aiming = False      # armando o arremesso
        self.fade = 0.0          # recuo do fadeaway, enquanto o arremesso corre
        self.dunk_style = 0      # índice em DUNK_NAMES
        self.dunk_voo = False    # cravada de longe: o gesto sai ampliado
        # uniforme por jogador: no x1 o adversário precisa ser outra cor
        self.jersey = JERSEY
        self.jersey_dark = JERSEY_DARK
        self.shorts = SHORTS
        # o preparo da cravada estica conforme a distancia, entao a duracao e
        # decidida por jogada -- estes sao so os valores iniciais
        self.dunk_frames = self.DUNK_FRAMES
        self.dunk_windup_frac = self.DUNK_WINDUP_FRAC
        self.turbo = 0           # quadros restantes de contra-ataque (SHOWTIME)
        self.vx = 0.0            # velocidade horizontal (o corpo tem inércia)
        self.sprint = 0          # quadros restantes de pique
        self.sprint_estalo = False   # arrancou AGORA (o jogo faz a poeira)
        self._tecla = {-1: False, 1: False}    # direção estava apertada?
        self._toque = {-1: -999, 1: -999}      # quando foi o último toque
        self.k_baixo = (pygame.K_s, pygame.K_DOWN)
        self.k_cima = (pygame.K_w, pygame.K_UP)
        self.k_super = (pygame.K_q, pygame.K_RSHIFT)
        self.super_carga = 0.0    # medidor do MODO, de 0 a 1
        self.super_frames = 0     # quadros restantes com o MODO ligado
        self.folego = 1.0        # 1 = inteiro, 0 = exausto
        # --- o que era do Game e agora é DE CADA UM: com dois humanos no mesmo
        # teclado, um conjunto só faria a carga de um zerar a do outro ---
        self.charging = False          # carregando a força do arremesso
        self.charge = 0.0              # quadros segurando o botão
        self.last_action_frame = -999  # pra detectar o duplo-toque
        self.pending_shot = None       # arremesso à espera da 2ª batida
        self.pending_shot_timer = 0
        self.botao = False             # botão de ação segurado agora
        # teclas de movimento, por jogador: lendo A/D *e* as setas, os dois
        # humanos andariam juntos
        self.k_esq = (pygame.K_a, pygame.K_LEFT)
        self.k_dir = (pygame.K_d, pygame.K_RIGHT)
        self.vestir(ROSTER[0])

    # Roupa de TODOS os jogadores. É de classe e não de instância porque é
    # uma escolha do jogo, não do personagem — e assim o boneco da tela de
    # escolha veste o mesmo que os dois em quadra, sem ninguém precisar
    # lembrar de repassar o valor.
    roupa = "uniforme"

    def vestir(self, perfil):
        """Aplica um perfil do ROSTER: roupa, corpo, rosto e habilidade."""
        p = perfil
        self.perfil = p
        self.nome, self.number = p["nome"], p["num"]
        # a cor do time continua no perfil, mas agora só aparece nos detalhes
        self.time_cor, self.time_cor2 = p["cam"], p["cam_esc"]
        # ROUPA: uniforme do time ou moletom all black. Tudo o que o desenho
        # do tronco usa sai daqui — inclusive as luzes e sombras, que antes
        # citavam MOLETOM direto e por isso não sabiam trocar de roupa.
        if self.roupa == "uniforme":
            self.pano, self.pano_esc = p["cam"], p["cam_esc"]
            self.jersey, self.jersey_dark = p["cam"], p["cam_esc"]
            self.shorts = p["cam"]
            self.manga_longa = False
        else:
            self.pano, self.pano_esc = MOLETOM, MOLETOM_ESC
            self.jersey, self.jersey_dark = MOLETOM, MOLETOM_ESC
            self.shorts = MOLETOM_CALCA
            self.manga_longa = True
        # paleta do tecido escuro, por SOMA de luz (ver _lift)
        # a faixa inteira continua escura: numa roupa preta um cinza de 60
        # não lê como luz, lê como outra peça de roupa colada por cima
        # -13 num tecido quase preto virava um risco de ponta a ponta na
        # cintura, e o contorno de 1 px passava no mesmo lugar somando com ele
        self.pano_som = _lift(self.pano, -5)
        self.pano_luz = _lift(self.pano, 15)
        self.pano_brilho = _lift(self.pano, 27)
        self.calca_luz = _lift(self.shorts, 11)
        self.pele = p["pele"]
        self.pele_esc = _shade(p["pele"], 0.74)
        self.cabelo, self.cor_cabelo = p["cabelo"], p["cor_cabelo"]
        self.barba, self.queixo = p["barba"], p["queixo"]
        # só quem tem isso no perfil bota a língua pra fora
        self.lingua = p.get("lingua", False)
        self.cranio = p.get("cranio", 1.0)
        self.altura_cm, self.peso_kg = p["altura"], p["peso"]
        self.atr_arremesso, self.atr_forca, self.atr_defesa = p["arr"], p["forca"], p["defe"]
        self.speed = 3.6 + p["vel"] * 0.32          # 1 -> 3.9 px/quadro, 10 -> 6.8
        self.DRIBBLE_PERIOD = p["drible"]
        self.DRIBBLE_HAND_DIP = p["dip"]
        self.cross = p["cross"]
        self.tiro = p["tiro"]
        self.set_point = p["set_point"]
        self.shoot_ext_frac = p["ext"]
        self.shoot_hop = p["hop"]
        self.shoot_arm = p["arm"]
        self.dunk_pool = list(p["dunks"])
        self.hab, self.traco = p["hab"], p["traco"]
        self.tenis, self.trim = p["tenis"], p["trim"]
        self.faixa, self.manga = p["faixa"], p["manga"]
        self.joelheira, self.meia, self.oculos = p["joelheira"], p["meia"], p["oculos"]
        # o moletom tem manga comprida (o antebraço é tecido); a regata não
        # tem manga nenhuma, então o braço é pele
        if self.manga_longa:
            self.cor_braco, self.cor_braco_esc = MOLETOM, MOLETOM_ESC
        else:
            self.cor_braco = self.pele
            self.cor_braco_esc = _shade(self.pele, 0.74)
        # ESCALA: 198 cm e o corpo de referencia. Mexe no desenho E no alcance.
        # peso vira INÉRCIA: o mais pesado demora mais pra arrancar e pra
        # parar, e ganha o encontrão no contato corpo a corpo
        self.massa = p["peso"] / 98.0
        self.acel = ACEL_BASE * (1.34 - p["peso"] / 250.0)
        self.esc = p["altura"] / 198.0
        self.largura = 1.0 + (p["peso"] - 98) / 380.0
        self.ombros = p.get("ombros", 1.0)
        # o alcance do braço é do JOGADOR, não da constante: ele alimenta a
        # altura da mão, o salto da cravada e a origem do arremesso, então
        # braço comprido tem que valer no jogo e não só no desenho
        self.alcance = BODY_REACH * p.get("envergadura", 1.0)
        self.pilha = BODY_HIP + BODY_TORSO + self.alcance
        self.HEIGHT = int(round(Player.HEIGHT * self.esc))

    @property
    def grab_offset(self):
        """Salto necessario pra mao pousar sobre o aro. Como o corpo inteiro
        escala com a altura, quem e mais alto precisa saltar MENOS -- e a conta
        sai das mesmas medidas usadas pra desenhar, nao de um numero solto."""
        return DUNK_HAND_ABOVE_FEET - self.pilha * self.esc

    @property
    def shot_span(self):
        """Largura do medidor. MENOR = mais perdoante, porque cada quadro mexe
        menos na força. Por isso bons arremessadores têm span menor."""
        return CHARGE_SPAN * (1.45 - 0.07 * self.atr_arremesso)

    @property
    def alcance_dunk(self):
        """Força estica a zona de cravada pra trás."""
        return DUNK_ZONE[0] - (self.atr_forca - 5) * 14

    def dribble_push(self):
        """Altura da bola no quique: 1 = na mão, 0 = tocando o chão.

        É um trecho de parábola de queda livre, então a bola passa RÁPIDO pelo
        chão e desacelera ao subir — nada do vaivém simétrico de uma senoide, que
        era o que deixava o quique mecânico. O corte em DRIBBLE_SNAP (<1) faz a
        bola SAIR da mão já em movimento: com a parábola inteira o ápice cairia
        exatamente na mão, com velocidade zero, e a bola parecia grudada nela."""
        s = abs(2 * ((self.anim_t % self.DRIBBLE_PERIOD) / self.DRIBBLE_PERIOD) - 1)
        k = self.DRIBBLE_SNAP
        return s * (2 - k * s) / (2 - k)

    def ball_pos(self):
        """Onde a bola aparece. Quicando, ela desce SOZINHA até o chão e sobe de
        volta pra mão — por isso não acompanha hand_pos()."""
        hx, hy = self.hand_pos()
        if not self.dribbling:
            return hx, hy
        chao = FLOOR_Y - Ball.RADIUS      # altura da bola encostando no chão
        return hx + self.facing * 5, chao - (chao - hy) * self.dribble_push()

    def hand_pos(self):
        bounce = math.sin(self.anim_t * 0.15) * 2 if self.state == "run" else 0
        if self.dribbling:
            bounce += self.DRIBBLE_HAND_DIP * self.dribble_push()
        if self.action == "finta":
            # a bola sobe até o ponto de soltura e volta, sem sair da mão
            ft = 1 - (self.action_timer / FINTA_FRAMES)
            bounce -= self.set_point * math.sin(math.pi * min(1.0, ft / 0.85))
        if self.aiming and self.action is None:
            # PONTO DE SOLTURA: armando, a bola sobe pra junto da cabeça, com o
            # cotovelo por baixo. Solta-se de lá, mais alto — e como a força
            # ideal é calculada a partir da mão, a mira se ajusta sozinha.
            bounce -= self.set_point
        desloca_x = 0.0
        if self.state == "block":
            # a mão do toco é a que está LÁ EM CIMA — e ela SOBE: durante a
            # antecipação o alcance tem que ser o de quem ainda está agachado
            bounce -= 68 * self.block_ext()
            desloca_x = -18 * self.facing * self.block_ext()
        if self.dribbling and self.cross:
            # CROSSOVER: a bola ATRAVESSA o corpo — sai de uma mão, toca o chão
            # embaixo do peito e sobe do outro lado. O cosseno tem exatamente o
            # período do quique, então a troca de lado cai no ponto mais baixo.
            # O (cos-1) ancora um extremo na posição normal da mão e joga o
            # outro pra além do corpo, em vez de balançar em torno dela.
            fase = math.cos(math.pi * self.anim_t / self.DRIBBLE_PERIOD)
            desloca_x = self.cross * self.facing * (fase - 1)
        if self.state == "dunk":
            t = 1 - (self.action_timer / self.dunk_frames)
            wt = min(1.0, t / self.dunk_windup_frac)
            desloca_x, dy = self.dunk_ball_offset(wt)
            bounce += dy
        ombro = (BODY_HIP + BODY_TORSO) * self.esc
        hy = self.y - ombro + BODY_BALL_DROP - self.jump_offset + bounce
        hx = self.x + self.facing * 26 + desloca_x
        return hx, hy

    def update(self, keys, ball_held, aiming=False):
        self.aiming = aiming     # armando o arremesso: muda a pose e sobe a bola
        # SHOWTIME: os quadros de contra-ataque logo depois de um roubo
        if self.turbo > 0:
            self.turbo -= 1
        # ARRANQUE: dois toques na mesma direção disparam um pique curto
        for lado, teclas in ((-1, self.k_esq), (1, self.k_dir)):
            apertada = any(keys[k] for k in teclas)
            if apertada and not self._tecla[lado]:
                if (self.anim_t - self._toque[lado] <= DOUBLE_TAP_FRAMES
                        and self.folego > 0.28 and not self.suspended):
                    self.sprint = SPRINT_FRAMES
                    # empurrão IMEDIATO, além do teto mais alto: é o que
                    # separa uma arrancada de começar a andar mais rápido
                    self.vx = lado * max(abs(self.vx),
                                         self.speed * SPRINT_IMPULSO)
                    self.sprint_estalo = True   # o jogo lê isto pra soltar poeira
                    SOM.toca("tenis", 0.55)
                    self.folego = max(0.0, self.folego - SPRINT_CUSTO)
                self._toque[lado] = self.anim_t
            self._tecla[lado] = apertada
        if self.sprint > 0:
            self.sprint -= 1

        vel = self.speed * (1.28 if self.turbo > 0 else 1.0)
        if self.sprint > 0:
            vel *= SPRINT_BOOST
        if self.super_frames > 0 and self.hab == "showtime":
            vel *= 1.30          # SHOWTIME: no modo ele voa pela quadra
        # cansado, a velocidade máxima cai — é o que dá ritmo ao 1x1
        vel *= FOLEGO_MIN_VEL + (1 - FOLEGO_MIN_VEL) * self.folego

        # A tecla define uma velocidade ALVO; o corpo acelera até ela e
        # desacelera por atrito. Antes `x += vel` direto: o jogador arrancava e
        # parava no mesmo quadro, e o peso do elenco não significava nada.
        alvo = 0.0
        if self.action == "caido":
            pass                     # no chão ninguém anda
        elif not self.suspended and self.action != "dunk":
            if any(keys[k] for k in self.k_esq):
                alvo -= vel
            if any(keys[k] for k in self.k_dir):
                alvo += vel
        if self.action == "dunk":
            self.vx = 0.0            # o salto da cravada conduz o x sozinho
        elif alvo != 0.0:
            passo = self.acel
            self.vx += max(-passo, min(passo, alvo - self.vx))
            self.facing = 1 if alvo > 0 else -1
        else:
            self.vx *= ATRITO
            if abs(self.vx) < PARADO:
                self.vx = 0.0
        if not self.suspended and self.action != "dunk":
            self.x += self.vx
            self.x = max(30, min(WIDTH - 35, self.x))   # corre a quadra inteira
            if self.x <= 30 or self.x >= WIDTH - 35:
                self.vx = 0.0        # bateu na borda: perde o embalo
        moving = abs(self.vx) > 0.35

        # fôlego: corrida e salto gastam, parado recupera
        if moving:
            if not (self.super_frames > 0 and self.hab == "showtime"):
                # SHOWTIME: no modo o fôlego não cai — é o que permite sprintar
                # a corrida inteira em vez de uma arrancada só
                self.folego -= FOLEGO_GASTO * (0.7 + 0.6 * self.massa)
        else:
            self.folego += FOLEGO_VOLTA
        self.folego = max(0.0, min(1.0, self.folego))

        if self.action == "shoot" and self.fade:
            self.x = max(30, min(WIDTH - 35, self.x + self.fade))

        if self.action == "dunk":
            # o salto é EM DIREÇÃO à cesta: sem isso, cravando de longe o jogador
            # ficava pendurado no ar, com a mão a dezenas de pixels do aro
            t = 1 - (self.action_timer / self.dunk_frames)
            approach = ease_in_out(min(1.0, t / self.dunk_windup_frac))
            self.x = self.dunk_start_x + (self.dunk_target_x - self.dunk_start_x) * approach

        was_jumping = self.jumping
        if self.jumping and not self.suspended:
            self.jump_vel -= GRAVITY * 0.7
            self.jump_offset += self.jump_vel
            if self.jump_offset <= 0:
                self.jump_offset = 0
                self.jumping = False
                self.jump_vel = 0
        if was_jumping and not self.jumping:
            # acabou de aterrissar: dispara o "estalo" de impacto (ease-out)
            self.land_timer = self.LAND_SQUASH_FRAMES
        if self.land_timer > 0:
            self.land_timer -= 1

        if self.action_timer > 0:
            self.action_timer -= 1
            if self.action_timer <= 0:
                self.action = None

        if self.action == "dunk":
            self.state = "dunk"
        elif self.action == "shoot":
            self.state = "shoot"
        elif self.action == "steal":
            self.state = "steal"
        elif self.action == "block":
            self.state = "block"
        elif self.action == "caido":
            self.state = "caido"
        elif self.action == "finta":
            self.state = "finta"
        elif self.suspended:
            self.state = "hang"
        elif self.jumping:
            self.state = "jump"
        elif moving:
            self.state = "run"
        else:
            self.state = "idle"

        self.dribbling = ball_held and (not aiming) and self.state in ("idle", "run")

        self.anim_t += 1

    def start_jump(self, vel=13.0):
        if not self.jumping:
            self.jumping = True
            # cansado salta mais baixo: o fôlego aparece no gesto, não só num
            # número escondido
            self.jump_vel = vel * (0.88 + 0.12 * self.folego)
            self.folego = max(0.0, self.folego - FOLEGO_SALTO)

    def trigger_shoot(self, angle, fade=True):
        """`fade=False` para quem só está levantando o braço (o toco), que
        reaproveita esta pose mas não pode sair andando pra trás."""
        self.action = "shoot"
        self.action_timer = self.SHOOT_FRAMES
        self.shot_angle = angle
        self.start_jump(self.shoot_hop)   # jump shot de verdade, não um pulinho
        # FADEAWAY: o corpo foge pra trás enquanto a bola já está no ar. Como o
        # lançamento já saiu, isso não mexe na trajetória — só tira o corpo do
        # alcance de quem ia tocar.
        self.fade = (-self.facing * (2.2 if self.hab == "flamingo" else 1.5)
                     if fade and self.tiro == "fadeaway" else 0.0)

    STEAL_FRAMES = 20        # duração do bote de roubo
    BLOCK_FRAMES = 24        # duração da subida do toco

    def trigger_steal(self):
        """Bote de roubo: o braço VARRE num arco de trás pra frente, cruzando a
        linha da bola, sem sair do chão. Tem gesto próprio porque reaproveitar
        o arremesso faria o jogador pular."""
        self.action = "steal"
        SOM.toca("tenis", 0.42)     # o pé trava no chão pra dar o bote
        self.action_timer = self.STEAL_FRAMES

    def trigger_finta(self):
        """Finge o arremesso: sobe a bola e desce sem soltar."""
        self.action = "finta"
        self.action_timer = FINTA_FRAMES

    def derrubar(self):
        """Levou um poster: cai sentado e levanta sozinho."""
        self.action = "caido"
        self.action_timer = POSTER_FRAMES
        self.jumping = False
        self.jump_vel = 0.0
        self.jump_offset = 0.0
        self.vx *= 0.2
        self.folego = max(0.0, self.folego - 0.18)

    def block_ext(self):
        """Quanto o braço do toco já subiu, de 0 a 1, com antecipação.

        Uma função só, usada pelo DESENHO e pelo ALCANCE. Com dois valores
        separados, durante o agachamento a mão já media como se estivesse lá
        em cima — a física media uma coisa e a tela mostrava outra."""
        if self.action != "block":
            return 0.0
        t = 1 - (self.action_timer / self.BLOCK_FRAMES)
        return max(0.0, ease_antecipa(min(1.0, t / 0.55)))

    def trigger_block(self):
        """Toco: os dois braços sobem formando uma parede. Antes isto era o
        gesto de ARREMESSO reaproveitado — o defensor fazia a pose de
        arremessar, e não havia o que ler na tela."""
        self.action = "block"
        SOM.toca("tenis", 0.48)     # a arrancada pra cima range o solado
        self.action_timer = self.BLOCK_FRAMES

    def trigger_dunk(self, target_x):
        """Prepara a cravada. O preparo DURA conforme a distância até a cesta e a
        força do salto é resolvida pra que a mão chegue no aro exatamente no fim
        dele. Sem isso, cravar do lance livre viraria um teleporte de 300px em
        11 quadros; e um salto fixo poria o jogador na altura errada."""
        self.action = "dunk"
        self.facing = 1
        self.dunk_start_x = self.x
        self.dunk_target_x = target_x

        dist = abs(target_x - self.x)
        n = max(11, min(30, int(round(11 + dist / 13.0))))     # quadros de preparo
        self.dunk_frames = n + DUNK_SLAM_FRAMES
        self.dunk_windup_frac = n / self.dunk_frames
        self.action_timer = self.dunk_frames

        # altura a ganhar em n quadros, com a gravidade do pulo comendo a subida:
        # offset(n) = v*n - a*n*(n+1)/2  =>  v = (alvo + a*n*(n+1)/2) / n
        a = GRAVITY * 0.7
        subir = self.grab_offset - self.jump_offset
        self.jumping = True
        self.jump_vel = (subir + a * n * (n + 1) / 2) / n
        # A distância não escolhe mais O QUE ele crava — escolhe COMO. De longe
        # o gesto vira a versão em voo (tesoura aberta, arco ampliado), mas
        # continua sendo a cravada DELE. Antes a distância impunha o Jumpman a
        # todo mundo, e do lance livre os doze faziam a mesma coisa.
        limite = DUNK_JUMPMAN_DIST - (46 if self.hab == "jumpman" else 0)
        self.dunk_voo = dist >= limite
        opcoes = [d for d in self.dunk_pool if d != self.dunk_style]
        self.dunk_style = random.choice(opcoes or self.dunk_pool)

    # Entrada do braço por estilo: (cotovelo, mão) em deslocamento do ombro.
    # É esta tabela que faz cada cravada COMEÇAR diferente — antes só quatro
    # estilos tinham entrada própria e o resto já nascia na pose de pegada,
    # o que deixava o braço parado e todas as cravadas parecidas.
    DUNK_COCK = {
        0:  ((4, 8), (2, -14)),        # MARTELO: carrega embaixo e martela
        1:  ((-8, -14), (-20, -32)),   # TOMAHAWK: vem de trás, arco largo
        2:  ((2, -28), (-6, -54)),     # MOLINETE: sai do alto, girando
        3:  ((6, -26), (6, -54)),      # DUAS MÃOS: bem no alto, de frente
        4:  ((-2, 2), (4, -10)),       # BERÇO: colado ao peito
        5:  ((8, -24), (10, -48)),     # BOMBA DUPLA: já sobe alto
        6:  ((8, -30), (12, -62)),     # JUMPMAN: braço esticado lá em cima
        7:  ((-14, 8), (-26, -4)),     # TREM-BALA: carregado lá atrás, baixo
        8:  ((8, -18), (8, -40)),      # QUEBRA-TABELA: curto e tenso
        9:  ((-18, -2), (-30, -20)),   # GANCHO: braço reto varrendo a lateral
        10: ((-6, 10), (-10, -6)),     # BALANÇO: baixo, embalando
        11: ((-12, -26), (-24, -46)),  # REVERSA: por trás do ombro
        12: ((10, -34), (14, -58)),    # TORRE: praticamente já na pegada
    }

    # Silhueta das pernas por estilo: (abertura, tesoura, quanto agacha).
    # `tesoura` abre uma perna à frente e outra atrás em vez de mantê-las juntas.
    DUNK_PERNAS = {
        0:  (12, False, 1.0),
        1:  (18, True, 0.8),
        2:  (24, True, 0.6),
        3:  (6, False, 1.2),
        4:  (8, False, 1.4),
        5:  (12, False, 1.1),
        6:  (60, True, 0.25),
        7:  (36, True, 0.5),
        8:  (4, False, 1.5),
        9:  (14, False, 0.9),
        10: (10, True, 1.6),
        11: (22, True, 0.7),
        12: (6, False, 0.6),
    }

    # quem crava com as DUAS mãos: muda a pose do braço livre
    DUNK_DUAS_MAOS = (3, 4, 5, 7, 8, 12)

    def dunk_ball_offset(self, wt):
        """Onde a bola fica durante o preparo. De longe o MESMO caminho sai
        ampliado: há tempo de ar pra um gesto maior, e é isso que faz a versão
        do lance livre parecer outra cravada sem precisar de uma animação
        separada por jogador."""
        dx, dy = self.caminho_da_bola(wt)
        if not self.dunk_voo:
            return dx, dy
        return dx * 1.35, dy * 1.15 - 8

    def caminho_da_bola(self, wt):
        """Para onde a bola vai durante o preparo, por estilo. `wt` vai de 0 a 1
        ao longo do preparo. Junto com DUNK_COCK (o braço) e DUNK_PERNAS (a
        silhueta), é o que separa uma cravada da outra — o resto da animação
        converge pra mesma pegada no aro, senão a emenda com o pendurado
        daria um salto."""
        f = self.facing
        ec = ease_out_cubic(wt)
        eq = ease_out_quad(wt)
        d = self.dunk_style
        if d == 1:          # TOMAHAWK: leva a bola pra trás da cabeça
            return -30 * eq * f, -58 * ec
        if d == 2:          # MOLINETE: a bola dá a volta completa
            a = -math.pi / 2 + 2 * math.pi * ease_in_out(wt)
            r = 18 + 22 * wt
            return math.cos(a) * r * f, math.sin(a) * r - 30 * wt
        if d == 3:          # DUAS MÃOS: sobe reto e mais alto
            return 0.0, -60 * ec
        if d == 4:          # BERÇO: embala junto ao peito e sobe
            if wt < 0.5:
                k = wt / 0.5
                return -8 * k * f, 8 * k
            k = (wt - 0.5) / 0.5
            return (-8 + 8 * k) * f, 8 - 66 * ease_out_cubic(k)
        if d == 5:          # BOMBA DUPLA: sobe, recolhe e sobe de novo
            if wt < 0.45:
                return 0.0, -52 * ease_out_cubic(wt / 0.45)
            if wt < 0.70:
                return 0.0, -52 + 26 * ease_in_out((wt - 0.45) / 0.25)
            return 0.0, -26 - 40 * ease_out_cubic((wt - 0.70) / 0.30)
        if d == DUNK_JUMPMAN:
            # bola numa mão só, braço quase reto lá no alto
            return 5 * eq * f, -70 * eq
        if d == 7:          # TREM-BALA: recua pra carregar e dispara
            if wt < 0.35:
                k = wt / 0.35
                return -18 * k * f, 14 * k
            k = ease_out_cubic((wt - 0.35) / 0.65)
            return (-18 + 20 * k) * f, 14 - 78 * k
        if d == 8:          # QUEBRA-TABELA: curto e brutal, colado ao corpo
            return 0.0, -64 * eq
        if d == 9:          # GANCHO CRAVADO: varre de trás por cima da cabeça
            a = math.pi - 1.5 * math.pi * ease_in_out(wt)
            r = 22 + 14 * wt
            return math.cos(a) * r * f, math.sin(a) * r - 26 * wt
        if d == 10:         # BALANÇO: pêndulo curto embaixo do aro
            return (math.sin(2 * math.pi * wt) * 15 * f,
                    -60 * ec + math.sin(math.pi * wt) * 12)
        if d == 11:         # REVERSA: entra pela frente e sai por trás do ombro
            if wt < 0.45:
                k = wt / 0.45
                return 12 * k * f, -14 * k
            k = ease_out_cubic((wt - 0.45) / 0.55)
            return (12 - 40 * k) * f, -14 - 48 * k
        if d == 12:         # TORRE: sobe reto e devagar — é só altura, sem arco
            return 2 * wt * f, -74 * wt
        return 12 * (1 - eq) * f, 16 - 72 * ec    # MARTELO (o clássico)

    def draw_emblema(self, d, cx, cy, lw, e):
        """O brasão do time estampado no peito do moletom.

        Redondo, do tamanho de uma estampa: em escudo pontudo e grande ele lia
        como gravata, não como logo. É ele que identifica o jogador agora que a
        roupa inteira é preta — e é por isso que a cor do time não sumiu do
        desenho junto com o uniforme."""
        r = 5.4 * min(lw, e)
        d.circle(self.time_cor2, (cx, cy), r + 1)
        d.circle(self.time_cor, (cx, cy), r)
        # faixa diagonal, o traço que dá cara de emblema
        d.polygon(self.trim, [(cx - r * 0.95, cy + r * 0.30),
                              (cx + r * 0.60, cy - r * 0.85),
                              (cx + r * 0.95, cy - r * 0.30),
                              (cx - r * 0.60, cy + r * 0.85)])
        d.circle(_lift(self.time_cor2, -20), (cx, cy), r, 1)
        num = FONT_TINY.render(self.number, True, WHITE)
        alvo = max(5, int(r * 1.15))
        num = pygame.transform.smoothscale(
            num, (max(4, int(num.get_width() * alvo / num.get_height())), alvo))
        d.blit(num, (cx - num.get_width() / 2, cy - num.get_height() / 2))

    def dunk_arm(self, sl, punch, cx, shoulder_y):
        """Cotovelo e mão no estouro. Cada estilo ENTRA de um jeito, mas todos
        terminam na mesma pose de agarrar o aro — senão a emenda com o
        pendurado daria um salto."""
        f = self.facing
        grip_e = (cx + 10 * f, shoulder_y - 20 * self.esc)
        grip_h = (cx + 14 * f, shoulder_y - self.alcance * self.esc)
        (ex, ey), (hx, hy) = self.DUNK_COCK.get(self.dunk_style,
                                                ((10, -20), (14, -46)))
        cock_e = (cx + ex * f, shoulder_y + ey * self.esc)
        cock_h = (cx + hx * f, shoulder_y + hy * self.esc)
        entra = max(0.0, 1 - sl / 0.45)           # some conforme assenta na pegada
        def mistura(c, g, extra_x, extra_y):
            return (c[0] + (g[0] - c[0]) * (1 - entra) + extra_x,
                    c[1] + (g[1] - c[1]) * (1 - entra) + extra_y)
        return (mistura(cock_e, grip_e, 6 * f * punch, 28 * punch),
                mistura(cock_h, grip_h, 12 * f * punch, 56 * punch))

    def in_dunk_zone(self):
        if self.super_frames > 0 and self.hab == "jumpman":
            # DO LANCE LIVRE: no modo a zona começa onde ele estiver. O limite
            # da direita continua: passado do aro não existe cravada pra frente.
            return self.x <= DUNK_ZONE[1]
        return self.alcance_dunk <= self.x <= DUNK_ZONE[1]

    @property
    def rect(self):
        return pygame.Rect(self.x - self.WIDTH // 2, self.y - self.HEIGHT - self.jump_offset,
                            self.WIDTH, self.HEIGHT)

    # Quantas vezes o personagem é montado maior do que aparece na tela. A
    # redução final com smoothscale é o antisserrilhado — sai de graça em TODO
    # traço, o que nenhuma primitiva do pygame oferece sozinha.
    # Quantas vezes o personagem e montado maior do que aparece. No navegador
    # vai em 1x: e o item mais caro do quadro (~5,4 ms de 11), e la o orcamento
    # nao cabe. Perde o antisserrilhado, ganha os 60 quadros.
    SUPER = 1 if NO_NAVEGADOR else 2
    # Caixa que precisa caber o boneco inteiro: a tesoura da cravada joga o pé
    # a ~83 px do centro e a mão no aro sobe a ~178 px dos pés. A sombra fica
    # ABAIXO dos pés, por isso a borda de baixo é positiva.
    CAIXA = (-78, -205, 155, 10)
    # Sem braço levantado o boneco ocupa bem menos altura, e o custo do
    # supersampling é proporcional à ÁREA da camada — não vale pagar pela
    # caixa da cravada em cada quadro de caminhada.
    CAIXA_TOPO_BAIXO = -147

    # De quantos em quantos quadros a camada do personagem e refeita no
    # navegador. So la: no PC o caminho supersampleado cabe no orcamento.
    PASSO_CAMADA = 3

    def pose_chave(self, holding_ball, dy, alt):
        """O que, mudando, exige redesenhar a camada na hora.

        Sao as mudancas de NATUREZA da pose. O avanco continuo da animacao nao
        entra: e justamente ele que pode esperar alguns quadros. Sem isto, o
        personagem arremessaria com a pose de quem esta parado."""
        return (self.state, self.action, self.facing, bool(holding_ball),
                self.dribbling, self.suspended, self.aiming, self.charging,
                self.sprint > 0, self.super_frames > 0, dy, alt)

    def draw(self, surface, holding_ball):
        """Monta o personagem numa camada ampliada e a reduz sobre a tela."""
        if self.SUPER <= 1:
            self.draw_camada(surface, holding_ball)
            return
        dx, dy, larg, sobra = self.CAIXA
        if not (self.action or self.jumping or self.suspended or self.aiming):
            dy = self.CAIXA_TOPO_BAIXO
        x0 = int(self.x + dx)
        y0 = int(self.y - self.jump_offset + dy)
        alt = int(self.y + sobra) - y0
        k = self.SUPER
        camada = pygame.Surface((larg * k, alt * k), pygame.SRCALPHA)
        self.montar(Pincel(camada, k, x0, y0), holding_ball)
        surface.blit(pygame.transform.smoothscale(camada, (larg, alt)), (x0, y0))

    def draw_camada(self, surface, holding_ball):
        """Desenha o personagem numa camada 1x e a reaproveita por alguns
        quadros. A camada e colada na posicao ATUAL a cada quadro, entao o
        movimento continua liso -- o que roda mais devagar e so a animacao dos
        membros."""
        dx, dy, larg, sobra = self.CAIXA
        if not (self.action or self.jumping or self.suspended or self.aiming):
            dy = self.CAIXA_TOPO_BAIXO
        x0 = int(self.x + dx)
        y0 = int(self.y - self.jump_offset + dy)
        alt = int(self.y + sobra) - y0
        chave = self.pose_chave(holding_ball, dy, alt)
        idade = self.anim_t - getattr(self, "_camada_t", -999)
        if (getattr(self, "_camada", None) is None
                or getattr(self, "_camada_chave", None) != chave
                or idade >= self.PASSO_CAMADA):
            if (getattr(self, "_camada", None) is None
                    or self._camada.get_size() != (larg, alt)):
                self._camada = pygame.Surface((larg, alt), pygame.SRCALPHA)
            self._camada.fill((0, 0, 0, 0))
            # a camada e desenhada com o Pincel deslocado, entao tudo dentro
            # dela fica RELATIVO a (x0, y0) -- e por isso ela pode ser colada
            # noutra posicao no quadro seguinte sem distorcer a pose
            self.montar(Pincel(self._camada, 1, x0, y0), holding_ball)
            self._camada_chave = chave
            self._camada_t = self.anim_t
        surface.blit(self._camada, (x0, y0))

    def montar(self, d, holding_ball):
        f = self.facing
        base_y = self.y - self.jump_offset
        cx = self.x
        # o corpo inteiro sai destas duas escalas: `e` vem da altura e `w` do
        # peso. É o mesmo `e` que entra no cálculo do salto da cravada, então
        # desenho e alcance não têm como divergir.
        e = self.esc
        w = self.largura

        run_cycle = math.sin(self.anim_t * 0.35)
        idle_bob = math.sin(self.anim_t * 0.08) * 2

        shoot_lin = 1 - (self.action_timer / self.SHOOT_FRAMES) if self.state == "shoot" else 0
        shoot_t = ease_out_cubic(shoot_lin)
        # o arremesso é um ESTALO curto seguido de um acompanhamento longo: o
        # braço estende nos primeiros frames e depois fica segurando a pose,
        # com o punho quebrando pra baixo (o "gooseneck")
        shoot_ext = ease_out_cubic(min(1.0, shoot_lin / self.shoot_ext_frac))
        wrist_snap = ease_out_quad(max(0.0, (shoot_lin - 0.20) / 0.28))
        dunk_lin = 1 - (self.action_timer / self.dunk_frames) if self.state == "dunk" else 0

        # "estalo" de aterrissagem: agachada que começa forte (ease-out) e
        # relaxa suavemente até sumir — em vez de um retorno linear/uniforme.
        land_p = 1 - (self.land_timer / self.LAND_SQUASH_FRAMES) if self.land_timer > 0 else 1.0
        land_squash = (1 - land_p) ** 3  # ~1 logo na aterrissagem -> 0 suavemente

        # pendurado no aro: as pernas balançam como um pêndulo
        hang_sway = math.sin(self.anim_t * 0.1) * 7 if self.suspended else 0
        dunk_tesoura = False     # estilos que abrem uma perna à frente

        # quicando: 1 quando empurra a bola pra baixo, 0 quando ela está no chão.
        # o corpo inteiro acompanha, senão só a mão se mexe e a pose fica dura.
        dribble_dip = self.dribble_push() if self.dribbling else 0.0

        if self.state == "run":
            leg_swing = run_cycle * 16
            arm_swing = -run_cycle * 14
            torso_tilt = 4
            # no pique o corpo se joga pra frente. Custa zero — é um parâmetro
            # que o desenho já usa — e é o sinal mais forte de que ele arrancou
            if self.sprint > 0:
                torso_tilt = 13
            knee_bend = 12 + abs(run_cycle) * 14
        elif self.state == "jump":
            leg_swing = 4
            arm_swing = -18
            torso_tilt = -4
            knee_bend = 22
        elif self.state == "shoot":
            # pernas RECOLHIDAS no ar (joelhos sobem) e o corpo se estica: é a
            # silhueta do jump shot, não a de alguém em pé empurrando a bola
            leg_swing = 4
            arm_swing = -10 - 45 * shoot_ext
            torso_tilt = -5 - 5 * shoot_ext
            knee_bend = 16 + 24 * shoot_ext
        elif self.state == "dunk":
            # cada estilo tem a sua silhueta de pernas: o Jumpman abre a
            # tesoura, o Quebra-Tabela crava plantado, o Balanço recolhe
            abert, dunk_tesoura, agacha = self.DUNK_PERNAS.get(
                self.dunk_style, (10, False, 1.0))
            if self.dunk_voo:
                # em voo TODO estilo abre a tesoura e estica: é o corpo de quem
                # saltou de longe, não de quem cravou parado embaixo do aro.
                # O teto evita que o Jumpman (que já abre 60) vire um espacate.
                abert = min(66, abert * 2.3)
                dunk_tesoura = True
                agacha *= 0.45
            if dunk_lin < self.dunk_windup_frac:
                wt = ease_out_quad(dunk_lin / self.dunk_windup_frac)
                leg_swing = 6 + (abert - 6) * wt
                arm_swing = -20 - 20 * wt
                torso_tilt = -4 - 4 * wt
                knee_bend = (8 + 20 * wt) * agacha
            else:
                st = ease_out_cubic((dunk_lin - self.dunk_windup_frac) / (1 - self.dunk_windup_frac))
                # a abertura vai FECHANDO, em vez de sumir de uma vez
                leg_swing = abert - (abert - 10) * st
                arm_swing = -40 - 30 * st
                torso_tilt = -8 - 6 * st
                knee_bend = (24 - 12 * st) * agacha
        elif self.state == "finta":
            # mesma leitura do arremesso, mas SEM sair do chão: é isso que faz
            # o defensor comprar
            ft = math.sin(math.pi * min(1.0, (1 - self.action_timer /
                                              FINTA_FRAMES) / 0.85))
            leg_swing = 4
            arm_swing = -10 - 34 * ft
            torso_tilt = -3 - 4 * ft
            knee_bend = 18 - 8 * ft
        elif self.state == "steal":
            # bote: agacha, avança e volta — o corpo acompanha a varrida do braço
            steal_t = 1 - (self.action_timer / self.STEAL_FRAMES)
            avanco = math.sin(math.pi * min(1.0, steal_t / 0.75))
            leg_swing = 10 + 14 * avanco
            arm_swing = -18
            torso_tilt = 8 + 16 * avanco
            knee_bend = 22 + 14 * avanco
        elif self.state == "block":
            # toco: o corpo ESTICA. Pernas juntas e estendidas, peito aberto,
            # nada de agachar — é o oposto da pose de arremesso, que recolhe.
            bloq_t = self.block_ext()
            # o agachamento da antecipação: joelho dobra ANTES de estender
            agacha = max(0.0, -bloq_t) * 3.4
            leg_swing = 4
            arm_swing = -70 * max(0.0, bloq_t)
            torso_tilt = -4 - 6 * bloq_t + 10 * agacha
            knee_bend = 8 - 4 * bloq_t + 26 * agacha
        elif self.state == "caido":
            # três fases no mesmo timer: desaba, fica no chão, levanta. Em uma
            # fase só o corpo teleportaria pro chão e de volta.
            ct = 1 - (self.action_timer / POSTER_FRAMES)
            if ct < 0.18:
                queda = ease_out_cubic(ct / 0.18)
            elif ct < 0.74:
                queda = 1.0
            else:
                queda = 1.0 - ease_in_out((ct - 0.74) / 0.26)
            self.queda = queda
            leg_swing = 30 * queda
            arm_swing = 30 * queda
            torso_tilt = 26 * queda
            knee_bend = 10 + 34 * queda
        elif self.state == "hang":
            leg_swing = 8
            arm_swing = -60
            torso_tilt = -10
            knee_bend = 12
        else:
            leg_swing = 0
            arm_swing = 0
            torso_tilt = 0
            knee_bend = 10 + land_squash * 12  # agacha mais logo após aterrissar

        if self.dribbling:
            knee_bend += 9 * dribble_dip     # agacha na batida
            torso_tilt += 3 * dribble_dip    # e inclina pra frente
        if self.aiming and holding_ball and self.action is None:
            knee_bend += 18                  # agacha pra armar (a "carga")
            torso_tilt += 5

        hip_drop = land_squash * 8 if self.state in ("idle", "jump") else 0
        # pernas mais longas: antes eram 36px contra 56px de tronco+cabeça, o que
        # deixava o personagem atarracado
        hip_y = (base_y - BODY_HIP * e + (idle_bob if self.state == "idle" else 0)
                 + hip_drop + 5 * dribble_dip)
        if self.state == "caido":
            # o quadril desce quase até o chão: é a queda propriamente dita
            hip_y += (base_y - 8 - hip_y) * getattr(self, "queda", 0.0)
        shoulder_y = hip_y - BODY_TORSO * e - torso_tilt * 0.2
        head_y = shoulder_y - BODY_NECK * e

        # --- riscos de velocidade, enquanto o pique dura ---
        # em LINHA e não em cópia fantasma do personagem: redesenhar o boneco
        # custa 4,5 ms por cópia, e três cópias estourariam o quadro por um
        # efeito de meio segundo
        if self.sprint > 0:
            forca = min(1.0, self.sprint / (SPRINT_FRAMES * 0.6))
            atras = -f
            # na altura do CORPO, nao das pernas: em -52/-34/-14 eles saiam
            # na linha do joelho pra baixo e liam como marcacao da quadra
            for i, (dy, comp) in enumerate(((-104, 32), (-80, 46), (-58, 28))):
                x0 = cx + atras * (10 + i * 4)
                # na cor do time: sempre contrasta com a quadra, e amarra o
                # efeito ao jogador em vez de virar um risco genérico
                d.line(_shade(self.trim, 0.45 + 0.40 * forca),
                       (x0, base_y + dy * e),
                       (x0 + atras * comp * forca, base_y + dy * e),
                       max(1.0, 2.0 * e))

        # --- sombra no chão (desenhada antes, pra ficar sob os pés) ---
        shadow_w = 34 * w - self.jump_offset * 0.16
        if shadow_w > 4:
            # o salto tira densidade além de largura: no alto, o jogador projeta
            # uma mancha larga e fraca; no chão, uma sombra curta e fechada
            perto = max(0.0, 1.0 - self.jump_offset / 150.0)
            shadow = pygame.Surface((int(shadow_w * 2), 12), pygame.SRCALPHA)
            r_ext = shadow.get_rect()
            pygame.draw.ellipse(shadow, (0, 0, 0, int(40 + 34 * perto)), r_ext)
            r_int = r_ext.inflate(-int(shadow_w * 0.8), -4)
            pygame.draw.ellipse(shadow, (0, 0, 0, int(50 + 70 * perto)), r_int)
            d.blit(shadow, (cx - shadow_w, self.y - 6))

        # --- pernas: coxa (calção) + panturrilha (pele), com quebra no joelho ---
        for side, sign in ((0, 1), (1, -1)):
            if self.state == "dunk" and dunk_tesoura:
                # TESOURA: uma perna à frente, outra atrás. Sem o amortecimento
                # de 0.55 usado nas outras poses, senão a abertura some.
                swing = leg_swing * sign * 1.8
            elif self.state in ("jump", "dunk"):
                swing = leg_swing            # as duas juntas
            else:
                swing = leg_swing * sign
            # a perna de TRÁS (side 0) recua e escurece: é o que separa uma
            # da outra numa vista de perfil, onde as duas caem quase no mesmo x
            atras = side == 0
            recuo = -7 * f if atras else 7 * f
            pano_perna = _lift(self.shorts, -12) if atras else self.shorts
            hip_pt = (cx - 4 * w * sign + recuo, hip_y)
            # no arremesso os pés sobem um pouco: sem isso eles ficam presos na
            # linha do chão e a perna nunca recolhe, que é o que fazia a pose no
            # ar parecer alguém em pé
            foot_lift = 9 * shoot_ext if self.state == "shoot" else 0.0
            # o pe de tras fica um pouco mais alto: numa quadra em
            # perspectiva, o que esta mais longe sobe na tela
            foot = (cx + swing * f * 0.55 + hang_sway + recuo,
                    base_y - foot_lift - (2.0 if atras else 0.0))
            # o joelho fica bem acima do calcanhar (calção curto, panturrilha
            # comprida à mostra) e ganha um deslocamento horizontal próprio
            # pra criar uma quebra visível em relação à linha quadril->pé
            knee_forward = 3 * f + 4 * f * sign * 0.4 + swing * f * 0.3
            knee = (cx + knee_forward + recuo, hip_y + 29 * e + knee_bend * 0.3)
            # coxa: grossa no quadril, joelho estreito. Engrossada porque o
            # meio dela media 56% da largura do peito -- a perna sumia embaixo
            # do tronco e o corpo lia como caixa sobre coluna.
            draw_limb(d, hip_pt, knee, 8.8 * w, 4.9 * w, pano_perna,
                      w_meio=7.4 * w, t_meio=0.34)
            # a calça do moletom vai até o tornozelo (panturrilha é tecido);
            # de calção, a perna abaixo do joelho é pele
            pano_panturrilha = pano_perna if self.manga_longa else (
                self.pele if not atras else _shade(self.pele, 0.82))
            # panturrilha: incha logo abaixo do joelho, tornozelo fino
            draw_limb(d, knee, foot, 5.2 * w, 3.1 * w, pano_panturrilha,
                      w_meio=5.6 * w, t_meio=0.26)
            # a junta no MESMO tom do membro DE BAIXO: de calção o joelho
            # está descoberto, e saindo da cor da coxa ele virava uma bolinha
            # vermelha no meio da perna nua
            draw_joint(d, knee, 3.9 * w, pano_panturrilha)
            if side == 1:
                # faixa lateral do conjunto, do quadril ao tornozelo — num
                # calção ela cabia no quadril, numa calça comprida não
                d.line(self.trim,
                       (hip_pt[0] + 6 * w * f, hip_pt[1] + 2),
                       (knee[0] + 3.5 * w * f, knee[1]), 1.6)
                d.line(self.trim, (knee[0] + 3.5 * w * f, knee[1]),
                       (foot[0] + 3 * w * f, foot[1] - 12 * e), 1.6)
            d.line(self.trim if not atras else _lift(self.trim, -60),
                   (foot[0] - 4.5 * w, foot[1] - 11 * e),
                   (foot[0] + 4.5 * w, foot[1] - 11 * e), 2.4)
            draw_shoe(d, foot, f, e, self.tenis, self.meia, atras)
            if side == 1 and self.joelheira:
                # joelheira, só em quem usa
                d.line(BAND_COLOR, (knee[0] - 6, knee[1] - 2),
                                  (knee[0] + 6, knee[1] - 2), 3)

        # --- quadril: a peça curta que liga o tronco às pernas ---
        # Em trapézio próprio, mais claro que a coxa e com contorno, ele lia
        # como um cinto atravessado na cintura. No mesmo tom da coxa, some
        # dentro da calça — que é o que uma calça inteiriça faz.
        # o quadril e a EMENDA entre o moletom e a perna: ele desce um pouco
        # mais e fica quase da largura da barra, pra nao sobrar degrau
        hip_w = 10.2 * w
        incl = torso_tilt * f * 0.1
        d.polygon(self.shorts, [(cx - hip_w + incl, hip_y - 7),
                                (cx + hip_w + incl, hip_y - 7),
                                (cx + hip_w * 0.94, hip_y + 17 * e),
                                (cx - hip_w * 0.94, hip_y + 17 * e)])
        d.polygon(self.calca_luz, [(cx + f * 1.5, hip_y - 7),
                                   (cx + f * hip_w + incl, hip_y - 7),
                                   (cx + f * hip_w * 0.94, hip_y + 17 * e),
                                   (cx + f * 1.5, hip_y + 17 * e)])

        # --- moletom (parte de cima) ---
        ty = shoulder_y
        by = hip_y - 2
        desl = torso_tilt * f * 0.6
        lw = w * 1.06                       # moletom é folgado, mas não inflado

        # PERFIL de meia-largura do tronco: (quanto sai do eixo, em que altura).
        # A silhueta, a metade iluminada e o fio de luz saem todos daqui — em
        # três listas escritas à mão elas divergiam a cada ajuste.
        alt_tronco = max(1.0, by - ty)
        # a cintura fica em 0,67 da largura do ombro: é o V que separa um atleta
        # de um barril. Antes a barra tinha quase a largura dos ombros.
        # a CINTURA não acompanha o ombro de propósito: é a razão entre os
        # dois que o olho lê como porte, não a largura absoluta. Alargando os
        # dois juntos, o Shaq viraria só um Curry grande.
        om = self.ombros
        perfil = [(7.6 * (1 + (om - 1) * 0.45), ty - 7),   # base do pescoço
                  (16.0 * om, ty + 4),             # queda do ombro
                  (16.5 * om, ty + 16 * e),        # cava do braço
                  (11.0, ty + alt_tronco * 0.62),  # cintura
                  # a barra NAO volta a alargar: antes ela ia a 12,0 contra
                  # 11,0 da cintura, e o moletom terminava numa sacola pousada
                  # em cima das pernas
                  (10.6, by - 1), (10.0, by + 3)]  # barra

        def lado(sgn):
            """Um lado do tronco. `desl` entra proporcional à altura, então o
            corpo inclina em vez de deslocar em bloco."""
            return [(cx + sgn * dx * lw + desl * ((y - ty) / alt_tronco), y)
                    for dx, y in perfil]

        tras, frente_lado = lado(-f), lado(f)
        eixo = [(cx + desl * ((y - ty) / alt_tronco), y) for _, y in perfil]
        contorno = tras + frente_lado[::-1]

        # CAPUZ caído nas costas: uma massa arredondada atrás da nuca, com o
        # forro do time por dentro. Em quadrilátero lia como bandeira no ombro.
        # Só existe de moletom — regata não tem capuz.
        if self.manga_longa:
            cap = pygame.Rect(0, 0, max(6, int(21 * lw)), max(6, int(19 * e)))
            cap.center = (int(cx - f * 9 * lw), int(ty + 3 * e))
            d.ellipse(self.pano_som, cap)
            forro = cap.inflate(-max(2, int(8 * lw)), -max(2, int(8 * e)))
            forro.centery = cap.centery - max(1, int(2 * e))
            d.ellipse(self.time_cor2, forro)
            d.ellipse(_lift(self.pano, -22), cap, 1)

        d.polygon(self.jersey, contorno)
        # a frente pega a luz — SOMADA, senão não existe diferença nenhuma
        # dois passos de luz em vez de um degrau só: com um corte único, a
        # divisão virava uma costura reta descendo o meio do peito
        meio_luz = [(e_[0] + (p[0] - e_[0]) * 0.30, p[1])
                    for p, e_ in zip(frente_lado, eixo)]
        d.polygon(_lift(self.pano, 7), frente_lado + eixo[::-1])
        d.polygon(self.pano_luz, frente_lado + meio_luz[::-1])
        # um brilho estreito seguindo a curva do ombro e do peito: o bastante
        # pra dizer que há um corpo embaixo do tecido
        brilho = [0.62, 0.90]
        # peito: a luz não desce reta — infla na caixa torácica e apaga abaixo
        # dela. É essa dupla que diz que há um corpo dentro do moletom.
        peito_y = ty + alt_tronco * 0.26
        d.ellipse(_lift(self.pano, 30),
                  (cx + f * 2 * lw, peito_y - 9 * e, 15 * lw, 18 * e))
        d.ellipse(_lift(self.pano, 4),
                  (cx + f * 3 * lw, peito_y + 8 * e, 12 * lw, 9 * e))
        d.polygon(self.pano_brilho,
                  [(e_[0] + (p[0] - e_[0]) * brilho[0], p[1])
                   for p, e_ in zip(frente_lado[:4], eixo[:4])] +
                  [(e_[0] + (p[0] - e_[0]) * brilho[1], p[1])
                   for p, e_ in zip(frente_lado[:4], eixo[:4])][::-1])
        # sombra rasa na barra, onde o tecido sobra
        d.polygon(self.pano_som, [tras[-2], frente_lado[-2],
                                  frente_lado[-1], tras[-1]])
        d.polygon(_lift(self.pano, -20), contorno, 1)
        # fio de luz na borda da frente: é o que tira o moletom preto de dentro
        # do fundo escuro da arquibancada sem clarear a roupa
        for a, b in zip(frente_lado, frente_lado[1:]):
            d.line(_lift(self.pano, 48), a, b, 1)

        # vincos do tecido: duas dobras curtas saindo do quadril
        # gola redonda do moletom (não o V da regata) e os cordões
        d.arc(_lift(self.pano, 24), (cx - 8 * lw, ty - 7, 16 * lw, 15 * e), 3.4, 6.0, 2)
        d.arc(self.trim, (cx - 7 * lw, ty - 5, 14 * lw, 13 * e), 3.5, 5.9, 1)
        # `lado` agora é a função que gera um lado do tronco: o laço dos
        # cordões usava a mesma palavra e a tapava
        for sgn in (-1, 1):
            d.line(_lift(self.pano, 30), (cx + sgn * 3, ty + 4),
                   (cx + sgn * 4, ty + 12 * e), 1)

        # bolso canguru: uma boca de cada lado, na altura da barriga. Regata
        # não tem bolso.
        bolso_y = by - 13 * e
        for sgn in ((-1, 1) if self.manga_longa else ()):
            d.line(self.pano_som,
                   (cx + sgn * 10.5 * lw + desl * 0.6, bolso_y),
                   (cx + sgn * 5.5 * lw + desl * 0.6, bolso_y + 7 * e), 2)
            d.line(_lift(self.pano, 14),
                   (cx + sgn * 10.5 * lw + desl * 0.6, bolso_y + 1),
                   (cx + sgn * 5.5 * lw + desl * 0.6, bolso_y + 8 * e), 1)

        # --- o emblema do time, estampado no peito ---
        self.draw_emblema(d, cx + f * 5 * lw + desl * 0.4, ty + 18 * e, lw, e)

        # friso da barra, tirado do TECIDO e não da cor do time. Escurecer a
        # cor do time não protege de nada quando ela pode ser branca: 26% de
        # branco dá (61,61,62) sobre um moletom de (30,30,35) — o dobro do
        # brilho, atravessado na cintura. Partindo do tecido, o friso fica
        # sempre um degrau acima dele, vista a camisa que for.
        d.line(_lift(self.pano, 13), tras[-1], frente_lado[-1], 1)

        # --- braço de trás (bíceps + antebraço) ---
        back_shoulder = (cx - 15 * w * self.ombros * f, shoulder_y + 5)
        if self.suspended:
            # pendurado: o outro braço também sobe pra agarrar o aro
            back_elbow = (cx - 6 * f, shoulder_y - 26)
            back_hand = (cx - 1 * f, shoulder_y - 48)
        elif self.state == "dunk" and self.dunk_style == DUNK_JUMPMAN:
            # UMA MÃO SÓ: o outro braço estica pra baixo e pra trás, aberto
            back_elbow = (cx - 16 * f, shoulder_y + 16)
            back_hand = (cx - 26 * f, shoulder_y + 30)
        elif self.state == "dunk" and self.dunk_style in self.DUNK_DUAS_MAOS:
            # DUAS MÃOS: o outro braço acompanha a bola / o aro
            alvo = self.hand_pos() if holding_ball else (cx + 6 * f, shoulder_y - 40)
            back_elbow = ((cx - 9 * f + alvo[0]) / 2, (shoulder_y + 6 + alvo[1]) / 2)
            back_hand = (alvo[0] - f * 11, alvo[1] + 4)
        elif self.state == "dunk":
            # cravada de UMA mão: o braço livre abre pro lado, equilibrando —
            # antes ele caía na pose de quique e ficava largado ao longo do corpo
            back_elbow = (cx - 15 * f, shoulder_y + 4)
            back_hand = (cx - 24 * f, shoulder_y + 13)
        elif self.aiming and holding_ball and self.action is None:
            # MÃO-GUIA: ao armar, a outra mão sobe e apoia a bola de lado
            hxp0, hyp0 = self.hand_pos()
            back_elbow = (cx - 9 * f, shoulder_y + 12)
            back_hand = (hxp0 - f * 9, hyp0 + 3)
        elif self.state == "block":
            # o SEGUNDO braço também sobe: é a parede do toco, e é ela que
            # diferencia o gesto de um arremesso à primeira vista
            # o braço de trás sobe um tico DEPOIS do da frente: subir
            # exatamente junto lê como boneco, não como pessoa
            bq = max(0.0, ease_antecipa(min(1.0, (1 - self.action_timer /
                                                  self.BLOCK_FRAMES) / 0.62)))
            back_elbow = (cx - 12 * f, shoulder_y + 6 - 30 * bq)
            back_hand = (cx - 14 * f, shoulder_y + 18 - 62 * bq)
        elif self.state == "shoot":
            # depois de soltar, a mão-guia cai fora do caminho
            back_elbow = (cx - 12 * f, shoulder_y + 10 - 6 * shoot_ext)
            back_hand = (cx - 17 * f, shoulder_y + 20 - 14 * shoot_ext)
        else:
            # quicando, o braço de proteção sobe e abre um pouco a cada batida
            back_elbow = (cx - 17 * f - 3 * dribble_dip,
                          shoulder_y + 19 - arm_swing * 0.25 - 7 * dribble_dip)
            back_hand = (cx - 18 * f - 5 * dribble_dip,
                         shoulder_y + 38 - arm_swing * 0.35 - 12 * dribble_dip)
        draw_deltoide(d, back_shoulder, back_elbow, 4.8 * w, self.pano_som)
        draw_limb(d, back_shoulder, back_elbow, 5.0 * w, 3.5 * w,
                  self.jersey_dark, w_meio=4.6 * w)
        draw_limb(d, back_elbow, back_hand, 3.9 * w, 2.6 * w,
                  self.cor_braco_esc, w_meio=3.5 * w, t_meio=0.30)
        draw_joint(d, back_elbow, 2.9 * w, self.cor_braco_esc)
        draw_hand(d, back_hand, -f, pele=self.pele, e=e)
        # munhequeira: uma FAIXA atravessada no punho (como círculo virava uma
        # bola branca solta no meio do braço)
        wx = back_elbow[0] + (back_hand[0] - back_elbow[0]) * 0.72
        wy = back_elbow[1] + (back_hand[1] - back_elbow[1]) * 0.72
        dx, dy = back_hand[0] - back_elbow[0], back_hand[1] - back_elbow[1]
        comp = max(1e-3, math.hypot(dx, dy))
        px, py = -dy / comp * 3.6, dx / comp * 3.6
        # punho do moletom: fino e rebaixado. Branco e com 3 px ele cruzava o
        # quadril e lia como cinto.
        d.line(_shade(self.trim, 0.62), (wx - px, wy - py), (wx + px, wy + py), 2)

        # --- cabeça (sobrancelha e boca leves, além do olho) ---
        # a expressão acompanha a jogada: concentrado no arremesso, feroz na cravada
        if self.state in ("dunk", "hang"):
            brow, mouth = 1.0, 2
        elif self.state == "shoot":
            brow, mouth = 0.75, 1
        elif self.state == "run":
            brow, mouth = 0.35, 1
        else:
            brow, mouth = 0.15, 0
        # a língua sai quando ele ATACA — cravando, saltando ou em
        # velocidade. Era aí que ela aparecia, e não só na cravada.
        pondo_lingua = self.lingua and (mouth >= 1 or self.state in ("jump", "hang"))
        draw_head(d, cx + 2 * f, head_y, f, brow, mouth,
                  pele=self.pele, cabelo=self.cabelo, cor_cabelo=self.cor_cabelo,
                  barba=self.barba, queixo=self.queixo,
                  faixa=self.faixa, oculos=self.oculos, e=e,
                  lingua=pondo_lingua, cranio=self.cranio)

        # --- braço da frente (segura a bola / arremessa / crava) ---
        front_shoulder = (cx + 15 * w * self.ombros * f, shoulder_y + 5)
        if holding_ball:
            hxp, hyp = self.hand_pos()
            if self.state == "dunk":
                # o cotovelo segue a bola onde quer que ela esteja: com os
                # estilos novos ela pode ir pra trás da cabeça ou dar a volta,
                # então uma posição fixa deixaria o braço desconectado
                elbow = ((front_shoulder[0] + hxp) / 2 - f * 4,
                         (front_shoulder[1] + hyp) / 2 + 5)
            elif self.aiming:
                # ARMANDO: cotovelo alinhado POR BAIXO da bola, que é o que dá
                # a leitura de forma de arremesso em vez de um empurrão
                elbow = (hxp - f * 2, hyp + 17)
            else:
                # o cotovelo bombeia junto com o quique
                elbow = (cx + 13 * f, shoulder_y + 18 + 7 * dribble_dip)
            draw_deltoide(d, front_shoulder, elbow, 4.8 * w, self.pano_luz)
            draw_limb(d, front_shoulder, elbow, 5.0 * w, 3.5 * w,
                      self.jersey, w_meio=4.6 * w)
            draw_limb(d, elbow, (hxp, hyp), 3.9 * w, 2.6 * w,
                      self.cor_braco, w_meio=3.5 * w, t_meio=0.30)
            draw_joint(d, elbow, 2.9 * w, self.cor_braco)
            draw_hand(d, (hxp, hyp), f, pele=self.pele, e=e)
        elif self.state == "shoot":
            if self.tiro == "gancho":
                # GANCHO: o braço vem ESTICADO pela lateral e varre por cima da
                # cabeça. Não é o arremesso de frente com o cotovelo por baixo —
                # é o arco inteiro, e por isso a bola sai lá em cima.
                ang = math.radians(24) + math.radians(-128) * shoot_ext
                bend = 2 * (1 - shoot_ext)
            else:
                ang = self.shot_angle
                bend = 11 * (1 - shoot_ext)      # dobra que desaparece ao estender
            # braços mais compridos alcançam mais: vem do porte de cada um
            ext = (self.shoot_arm - 14) + (self.shoot_arm - 2) * shoot_ext
            dirx, diry = math.cos(ang), math.sin(ang)
            perpx, perpy = -diry, dirx
            elbow = (front_shoulder[0] + dirx * ext * 0.55 + perpx * bend,
                     front_shoulder[1] + diry * ext * 0.55 + perpy * bend)
            front_hand = (front_shoulder[0] + dirx * ext, front_shoulder[1] + diry * ext)
            draw_deltoide(d, front_shoulder, elbow, 4.8 * w, self.pano_luz)
            draw_limb(d, front_shoulder, elbow, 5.0 * w, 3.5 * w,
                      self.jersey, w_meio=4.6 * w)
            draw_limb(d, elbow, front_hand, 3.9 * w, 2.6 * w,
                      self.cor_braco, w_meio=3.5 * w, t_meio=0.30)
            draw_joint(d, elbow, 2.9 * w, self.cor_braco)
            draw_hand(d, front_hand, f, snap=wrist_snap, pele=self.pele, e=e)
        elif self.state == "dunk":
            if dunk_lin < self.dunk_windup_frac:
                wt = ease_out_quad(dunk_lin / self.dunk_windup_frac)
                elbow = (cx + 7 * f, shoulder_y - 12 - 14 * wt)
                front_hand = (cx + 3 * f, shoulder_y - 28 - 24 * wt)
            else:
                sl = (dunk_lin - self.dunk_windup_frac) / (1 - self.dunk_windup_frac)
                # soco rápido pra baixo (a cravada) e volta pra posição de
                # agarrar o aro, emendando sem salto na pose de pendurado
                if sl < 0.4:
                    punch = ease_out_cubic(sl / 0.4)
                else:
                    punch = 1 - ease_out_quad((sl - 0.4) / 0.6)
                elbow, front_hand = self.dunk_arm(sl, punch, cx, shoulder_y)
            draw_deltoide(d, front_shoulder, elbow, 4.8 * w, self.pano_luz)
            draw_limb(d, front_shoulder, elbow, 5.0 * w, 3.5 * w,
                      self.jersey, w_meio=4.6 * w)
            draw_limb(d, elbow, front_hand, 3.9 * w, 2.6 * w,
                      self.cor_braco, w_meio=3.5 * w, t_meio=0.30)
            draw_joint(d, elbow, 2.9 * w, self.cor_braco)
            draw_hand(d, front_hand, f,
                      aberta=self.state in ("shoot", "dunk", "hang"),
                      pele=self.pele, e=e)
        elif self.state == "steal":
            # BOTE: a mão percorre um ARCO em volta do ombro, de trás pra frente,
            # passando pela linha da bola. Esticar e recolher no mesmo eixo lia
            # como cutucada; o que diz "roubo" é a varrida.
            st = 1 - (self.action_timer / self.STEAL_FRAMES)
            # o braço SAI do descanso, recua pra armar e só então varre — antes
            # ele nascia já na posição armada, o que lia como teleporte
            varre = ease_antecipa(min(1.0, st / 0.58), recuo=0.30)
            volta = 0.0 if st < 0.58 else ease_in_out((st - 0.58) / 0.42)
            ang = math.radians(96 - 96 * varre + 70 * volta)
            raio = (20 + 24 * math.sin(math.pi * min(1.0, st / 0.72))) * (1 - 0.22 * volta)

            def mao_em(a, r):
                return (front_shoulder[0] + math.cos(a) * r * f,
                        front_shoulder[1] + math.sin(a) * r)

            front_hand = mao_em(ang, raio)
            elbow = mao_em(ang + 0.30 * f, raio * 0.52)
            # rastro: onde a mão ACABOU de passar. É o que torna a varrida
            # legível num gesto que dura um terço de segundo.
            if 0.14 < st < 0.80:
                # rastro: um RISCO que afina e apaga ao longo do arco. Em
                # bolinhas ele lia como três bolotas grudadas no braço — era a
                # parte "grossa" do gesto.
                pontos = [mao_em(ang + math.radians(96 * k), raio * (1 - 0.04 * i))
                          for i, k in enumerate((0.06, 0.14, 0.24, 0.36))]
                for i, (a2, b2) in enumerate(zip(pontos, pontos[1:])):
                    d.line(_lift(self.pele, 48 - 15 * i), a2, b2,
                           max(1.0, (2.4 - 0.7 * i) * e))
            draw_deltoide(d, front_shoulder, elbow, 4.8 * w, self.pano_luz)
            draw_limb(d, front_shoulder, elbow, 5.0 * w, 3.5 * w,
                      self.jersey, w_meio=4.6 * w)
            draw_limb(d, elbow, front_hand, 3.9 * w, 2.6 * w,
                      self.cor_braco, w_meio=3.5 * w, t_meio=0.30)
            draw_joint(d, elbow, 2.9 * w, self.cor_braco)
            draw_hand(d, front_hand, f, aberta=True, pele=self.pele, e=e)
        elif self.state == "block":
            # braço da frente esticado no alto, palma aberta
            bq = self.block_ext()
            elbow = (cx + 12 * f, shoulder_y + 4 - 30 * bq)
            front_hand = (cx + 8 * f, shoulder_y + 14 - 68 * bq)
            draw_deltoide(d, front_shoulder, elbow, 4.8 * w, self.pano_luz)
            draw_limb(d, front_shoulder, elbow, 5.0 * w, 3.5 * w,
                      self.jersey, w_meio=4.6 * w)
            draw_limb(d, elbow, front_hand, 3.9 * w, 2.6 * w,
                      self.cor_braco, w_meio=3.5 * w, t_meio=0.30)
            draw_joint(d, elbow, 2.9 * w, self.cor_braco)
            draw_hand(d, front_hand, f, aberta=True, pele=self.pele, e=e)
        elif self.state == "hang":
            # pendurado: braço esticado agarrando o aro
            elbow = (cx + 10 * f, shoulder_y - 20 * e)
            front_hand = (cx + 14 * f, shoulder_y - self.alcance * e)
            draw_deltoide(d, front_shoulder, elbow, 4.8 * w, self.pano_luz)
            draw_limb(d, front_shoulder, elbow, 5.0 * w, 3.5 * w,
                      self.jersey, w_meio=4.6 * w)
            draw_limb(d, elbow, front_hand, 3.9 * w, 2.6 * w,
                      self.cor_braco, w_meio=3.5 * w, t_meio=0.30)
            draw_joint(d, elbow, 2.9 * w, self.cor_braco)
            draw_hand(d, front_hand, f,
                      aberta=self.state in ("shoot", "dunk", "hang"),
                      pele=self.pele, e=e)
        else:
            elbow = (cx + 17 * f, shoulder_y + 19 + arm_swing * 0.3)
            front_hand = (cx + 17 * f, shoulder_y + 38 + arm_swing * 0.5)
            draw_deltoide(d, front_shoulder, elbow, 4.8 * w, self.pano_luz)
            draw_limb(d, front_shoulder, elbow, 5.0 * w, 3.5 * w,
                      self.jersey, w_meio=4.6 * w)
            draw_limb(d, elbow, front_hand, 3.9 * w, 2.6 * w,
                      self.cor_braco, w_meio=3.5 * w, t_meio=0.30)
            draw_joint(d, elbow, 2.9 * w, self.cor_braco)
            draw_hand(d, front_hand, f,
                      aberta=self.state in ("shoot", "dunk", "hang"),
                      pele=self.pele, e=e)


# --------------------------------------------------------------------------
# JOGO
# --------------------------------------------------------------------------
class TeclasToque:
    """O teclado de verdade SOMADO às teclas seguradas por dedo.

    O jogo pergunta `keys[K_a]` em uma dúzia de lugares. Em vez de ensinar cada
    um deles a também olhar o toque, o toque entra por aqui: quem pergunta não
    descobre a diferença, e as duas entradas não têm como divergir.
    """

    __slots__ = ("reais", "dedos")

    def __init__(self, reais, dedos):
        self.reais = reais
        self.dedos = dedos

    def __getitem__(self, k):
        return bool(self.reais[k]) or k in self.dedos


class Toque:
    """Controles na tela, pro jogo funcionar em celular e tablet.

    Cada botão é um círculo que finge uma tecla. Em círculo e não em retângulo
    porque o dedo erra: um alvo redondo perdoa o erro igual em toda direção, e
    o polegar chega nele torto por natureza.

    Aparece sozinho no primeiro toque na tela — quem está no teclado nunca vê
    os botões, e quem está no celular não precisa achar um menu de opções pra
    conseguir jogar.
    """

    R_GRANDE, R_MEDIO, R_PEQUENO = 54, 40, 34

    def __init__(self):
        # No navegador começa LIGADO porque pode ser celular, e quem está no
        # celular precisa ver os botões pra descobrir que dá pra jogar. Mas
        # quem tem teclado se identifica sozinho na primeira tecla, e aí eles
        # somem (ver `evento_toque`) — não dá pra adivinhar o aparelho na
        # abertura, e não precisa: o jogador responde a pergunta usando o jogo.
        self.ativo = NO_NAVEGADOR
        self.dedos = {}          # id do dedo/botão do mouse -> tecla
        self.seguradas = set()   # teclas seguradas agora

    def layout(self, tela):
        """Os botões desta tela: (x, y, raio, rótulo, tecla).

        O rótulo muda com a tela porque a tecla muda de sentido: ESPAÇO confirma
        no menu e arremessa em quadra. Botão que mente sobre o que faz é pior
        que botão sem rótulo.
        """
        if tela == TELA_JOGO:
            return ((70, 470, self.R_MEDIO, "<", pygame.K_a),
                    (172, 470, self.R_MEDIO, ">", pygame.K_d),
                    (906, 486, self.R_GRANDE, "AÇÃO", pygame.K_SPACE),
                    (806, 396, self.R_MEDIO, "CIMA", pygame.K_w),
                    (796, 516, self.R_PEQUENO, "S", pygame.K_s),
                    (930, 300, self.R_PEQUENO, "MODO", pygame.K_q))
        if tela == TELA_QUADRA:
            return ((70, 470, self.R_MEDIO, "<", pygame.K_a),
                    (172, 470, self.R_MEDIO, ">", pygame.K_d),
                    (906, 486, self.R_GRANDE, "OK", pygame.K_SPACE),
                    (806, 396, self.R_MEDIO, "+", pygame.K_w),
                    (806, 516, self.R_MEDIO, "\u2212", pygame.K_s),
                    (930, 300, self.R_PEQUENO, "ROUPA", pygame.K_e))
        if tela == TELA_ESCOLHA:
            return ((70, 470, self.R_MEDIO, "<", pygame.K_a),
                    (172, 470, self.R_MEDIO, ">", pygame.K_d),
                    (906, 486, self.R_GRANDE, "OK", pygame.K_SPACE),
                    (806, 396, self.R_MEDIO, "+", pygame.K_w),
                    (806, 516, self.R_MEDIO, "\u2212", pygame.K_s))
        # tela de início
        return ((906, 486, self.R_GRANDE, "OK", pygame.K_SPACE),
                (806, 396, self.R_MEDIO, "^", pygame.K_w),
                (806, 516, self.R_MEDIO, "v", pygame.K_s))

    def em(self, tela, x, y):
        """Qual tecla está sob o ponto (x, y)? None se for fora dos botões."""
        for bx, by, r, _, k in self.layout(tela):
            if (x - bx) ** 2 + (y - by) ** 2 <= r * r:
                return k
        return None

    def desenhar(self, surface, tela):
        if not self.ativo:
            return
        for bx, by, r, rot, k in self.layout(tela):
            premido = k in self.seguradas
            camada = pygame.Surface((r * 2 + 4, r * 2 + 4), pygame.SRCALPHA)
            c = (r + 2, r + 2)
            pygame.draw.circle(camada, (250, 250, 255, 70) if premido
                               else (14, 16, 26, 120), c, r)
            pygame.draw.circle(camada, (255, 255, 255, 190) if premido
                               else (210, 212, 228, 110), c, r, 2)
            surface.blit(camada, (bx - r - 2, by - r - 2))
            cor = WHITE if premido else (218, 220, 234)
            seta = {"<": (-1, 0), ">": (1, 0), "^": (0, -1), "v": (0, 1)}.get(rot)
            if seta is not None:
                # triângulo DESENHADO, não caractere: num botão de direção a
                # seta é a informação, e uma fonte sem o glifo a transforma num
                # quadrado vazio — que foi exatamente o que apareceu na tela
                dx, dy = seta
                p = r * 0.44
                pygame.draw.polygon(surface, cor, [
                    (bx + dx * p, by + dy * p),
                    (bx - dx * p * 0.6 - dy * p * 0.9,
                     by - dy * p * 0.6 - dx * p * 0.9),
                    (bx - dx * p * 0.6 + dy * p * 0.9,
                     by - dy * p * 0.6 + dx * p * 0.9)])
            else:
                t = FONT_SMALL.render(rot, True, cor)
                surface.blit(t, (bx - t.get_width() // 2, by - t.get_height() // 2))


class Game:
    def __init__(self):
        self.player = Player()
        self.ball = Ball()
        self.net = Net()
        # a quadra vem ANTES da torcida: e ela que diz quantas fileiras existem
        # e se o publico senta ou fica em pe
        self.quadra_i = getattr(self, "quadra_i", 0)
        self.crowd = Crowd(self.quadra)
        self.particles = []
        self.texts = []
        self.score = 0
        self.combo = 0
        self.best_combo = 0
        self.time_left = GAME_SECONDS
        self.frame_count = 0
        self.aiming = False
        self.drag_start = None
        self.drag_current = None
        self.shake = 0.0
        self.game_over = False
        self.started = False
        self.missed_shown = False
        self.high_score = self.load_high_score()
        self.new_record = False
        self.dunk_phase = None   # None | "windup" | "hang"
        self.release_grace = 0
        self.rim_flex = 0.0          # quanto o aro está afundado
        self.rim_flex_vel = 0.0
        self.hang_offset = 0.0       # altura em que o jogador agarrou o aro
        self.hang_frames = 0         # há quantos quadros está pendurado
        self.dunk_saida = None       # resultado da disputa da cravada em curso
        self.aro_quebrado = False    # o Shaq arrebentou a tabela
        # --- x1 ---
        self.player.x = 250
        self.rival = Player()
        self.rival.x = 620
        self.rival.facing = -1
        self.rival.number = "33"
        self.rival.jersey = RIVAL_JERSEY
        self.rival.jersey_dark = RIVAL_JERSEY_DARK
        self.rival.shorts = RIVAL_SHORTS
        self.holder = self.player    # quem está com a bola (None = solta)
        self.shooter = self.player   # quem soltou o último arremesso
        self.dunker = self.player    # quem está cravando
        self.rival_score = 0
        self.winner = None
        self.needs_clear = False     # precisa levar a bola além da linha de 3
        self.steal_cd = 0
        self.rival_cd = 0
        self.block_timer = 0
        self.blocker = None
        self.rival_charge = 0.0
        self.rival_aiming = False
        self.rival_plan = "drive"   # "drive" (vai cravar) ou "shoot" (para e arremessa)
        self.rival_hold = 0         # há quantos quadros a IA segura a bola
        self.encerrar = False        # o laço principal observa isto
        self.tela = TELA_INICIO
        self.modo = getattr(self, "modo", 1)   # quantos humanos
        # a quadra sobrevive ao R, como o nível de dificuldade
        self.quadra_i = getattr(self, "quadra_i", 0)
        # e o alvo de pontos também: quem pediu partida de 21 não quer voltar
        # pra 11 a cada revanche
        self.alvo = getattr(self, "alvo", MATCH_POINTS)
        self.menu_pick = 0
        self._fase_drible = 0.0   # fase do quique no quadro anterior
        self.flash_medidor = None   # (quem, posicao, resultado, quadros)
        self.pausado = False
        # o toque sobrevive ao R: quem está no celular não quer que os
        # botões sumam ao recomeçar a partida
        self.toque = getattr(self, "toque", None) or Toque()
        self.picks = [0, 1]          # personagem escolhido por cada jogador
        self.quem_escolhe = 0
        # o nível escolhido sobrevive ao R: quem pediu FÁCIL não quer voltar
        # pro NORMAL a cada partida nova
        self.nivel = getattr(self, "nivel", DIFICULDADE_PADRAO)
        # cada humano tem as SUAS teclas de movimento
        self.player.k_esq, self.player.k_dir = (pygame.K_a,), (pygame.K_d,)
        self.player.k_baixo = (pygame.K_s,)
        self.player.k_cima = (pygame.K_w,)
        self.player.k_super = (pygame.K_q,)
        self.rival.k_esq, self.rival.k_dir = (pygame.K_LEFT,), (pygame.K_RIGHT,)
        self.rival.k_baixo = (pygame.K_DOWN,)
        self.rival.k_cima = (pygame.K_UP,)
        self.rival.k_super = (pygame.K_RSHIFT,)
        self.player.vestir(ROSTER[0])
        self.rival.vestir(ROSTER[1])
        self.aplicar_quadra()
        # custo medido do desenho e o mostrador do F3: ver `main`
        self.custo_ms = 0.0
        self.mostrar_fps = False

    # ---------------- persistência ----------------
    def load_high_score(self):
        try:
            with open(HIGHSCORE_FILE, "r") as f:
                return json.load(f).get("best", 0)
        except Exception:
            return 0

    def save_high_score(self):
        try:
            with open(HIGHSCORE_FILE, "w") as f:
                json.dump({"best": self.high_score}, f)
        except Exception:
            pass

    # ---------------- utilitários ----------------
    def spawn_burst(self, x, y, color, n=18):
        for _ in range(n):
            self.particles.append(Particle(x, y, color, life=random.randint(30, 55)))

    def add_text(self, x, y, text, color, size=30):
        self.texts.append(FloatingText(x, y, text, color, size))

    def reset_round(self):
        self.player = Player()
        self.ball = Ball()
        self.net = Net()
        # a quadra vem ANTES da torcida: e ela que diz quantas fileiras existem
        # e se o publico senta ou fica em pe
        self.quadra_i = getattr(self, "quadra_i", 0)
        self.crowd = Crowd(self.quadra)
        self.particles.clear()
        self.texts.clear()
        self.score = 0
        self.combo = 0
        self.best_combo = 0
        self.time_left = GAME_SECONDS
        self.frame_count = 0
        self.aiming = False
        self.game_over = False
        self.started = False
        self.missed_shown = False
        self.new_record = False
        self.dunk_phase = None   # None | "windup" | "hang"
        self.release_grace = 0
        self.rim_flex = 0.0          # quanto o aro está afundado
        self.rim_flex_vel = 0.0
        self.hang_offset = 0.0       # altura em que o jogador agarrou o aro
        self.hang_frames = 0         # há quantos quadros está pendurado
        self.dunk_saida = None       # resultado da disputa da cravada em curso
        self.aro_quebrado = False    # o Shaq arrebentou a tabela
        # --- x1 ---
        self.player.x = 250
        self.rival = Player()
        self.rival.x = 620
        self.rival.facing = -1
        self.rival.number = "33"
        self.rival.jersey = RIVAL_JERSEY
        self.rival.jersey_dark = RIVAL_JERSEY_DARK
        self.rival.shorts = RIVAL_SHORTS
        self.holder = self.player    # quem está com a bola (None = solta)
        self.shooter = self.player   # quem soltou o último arremesso
        self.dunker = self.player    # quem está cravando
        self.rival_score = 0
        self.winner = None
        self.needs_clear = False     # precisa levar a bola além da linha de 3
        self.steal_cd = 0
        self.rival_cd = 0
        self.block_timer = 0
        self.blocker = None
        self.rival_charge = 0.0
        self.rival_aiming = False
        self.rival_plan = "drive"   # "drive" (vai cravar) ou "shoot" (para e arremessa)
        self.rival_hold = 0         # há quantos quadros a IA segura a bola
        self.encerrar = False        # o laço principal observa isto
        self.tela = TELA_INICIO
        self.modo = getattr(self, "modo", 1)   # quantos humanos
        # a quadra sobrevive ao R, como o nível de dificuldade
        self.quadra_i = getattr(self, "quadra_i", 0)
        # e o alvo de pontos também: quem pediu partida de 21 não quer voltar
        # pra 11 a cada revanche
        self.alvo = getattr(self, "alvo", MATCH_POINTS)
        self.menu_pick = 0
        self._fase_drible = 0.0   # fase do quique no quadro anterior
        self.flash_medidor = None   # (quem, posicao, resultado, quadros)
        self.pausado = False
        # o toque sobrevive ao R: quem está no celular não quer que os
        # botões sumam ao recomeçar a partida
        self.toque = getattr(self, "toque", None) or Toque()
        self.picks = [0, 1]          # personagem escolhido por cada jogador
        self.quem_escolhe = 0
        # o nível escolhido sobrevive ao R: quem pediu FÁCIL não quer voltar
        # pro NORMAL a cada partida nova
        self.nivel = getattr(self, "nivel", DIFICULDADE_PADRAO)
        # cada humano tem as SUAS teclas de movimento
        self.player.k_esq, self.player.k_dir = (pygame.K_a,), (pygame.K_d,)
        self.player.k_baixo = (pygame.K_s,)
        self.player.k_cima = (pygame.K_w,)
        self.player.k_super = (pygame.K_q,)
        self.rival.k_esq, self.rival.k_dir = (pygame.K_LEFT,), (pygame.K_RIGHT,)
        self.rival.k_baixo = (pygame.K_DOWN,)
        self.rival.k_cima = (pygame.K_UP,)
        self.rival.k_super = (pygame.K_RSHIFT,)
        self.player.vestir(ROSTER[0])
        self.rival.vestir(ROSTER[1])
        self.aplicar_quadra()

    # ---------------- eventos ----------------
    def teclas(self, reais):
        """O teclado de verdade somado ao que está sob o dedo."""
        return TeclasToque(reais, self.toque.seguradas)

    def toque_aperta(self, dedo, x, y):
        """Um dedo pousou em (x, y): se caiu num botão, segura a tecla dele."""
        k = self.toque.em(self.tela, x, y)
        if k is None:
            return False
        self.toque.dedos[dedo] = k
        self.toque.seguradas.add(k)
        # o MESMO evento que a tecla geraria: assim o toque duplo, a carga do
        # arremesso e o modificador saem de graça, sem uma segunda via de
        # entrada pra divergir da primeira
        self.handle_event(pygame.event.Event(pygame.KEYDOWN, key=k,
                                             _do_toque=True))
        return True

    def toque_solta(self, dedo):
        k = self.toque.dedos.pop(dedo, None)
        if k is None:
            return
        self.toque.seguradas.discard(k)
        self.handle_event(pygame.event.Event(pygame.KEYUP, key=k,
                                             _do_toque=True))

    def toque_arrasta(self, dedo, x, y):
        """O dedo escorregou. Trocar de botão sem levantar o polegar é o que
        permite mudar de direção no meio de uma jogada."""
        if dedo not in self.toque.dedos:
            return
        novo = self.toque.em(self.tela, x, y)
        if novo == self.toque.dedos[dedo]:
            return
        self.toque_solta(dedo)
        if novo is not None:
            self.toque_aperta(dedo, x, y)

    def teclado_usado(self):
        """Apertou uma tecla: quem tem teclado não precisa dos botões.

        Some só no navegador porque é lá que eles começam ligados sem ninguém
        ter pedido. E some soltando o que estiver segurado, senão uma tecla
        virtual ficaria presa pra sempre — o jogador andaria sozinho.
        """
        if not self.toque.ativo:
            return
        for dedo in list(self.toque.dedos):
            self.toque_solta(dedo)
        self.toque.ativo = False

    def evento_toque(self, ev):
        """Traduz dedo e mouse em teclas. Devolve True se consumiu o evento.

        Trata FINGER* e MOUSE* porque nem todo navegador entrega toque como
        dedo: parte deles manda o toque como clique de mouse, e um jogo que só
        escutasse FINGER ficaria mudo justamente onde precisa funcionar.
        """
        t = ev.type
        if t in (pygame.FINGERDOWN, pygame.FINGERUP, pygame.FINGERMOTION):
            self.toque.ativo = True          # tocou: os botões aparecem
            dedo = ("d", getattr(ev, "finger_id", 0))
            x, y = ev.x * WIDTH, ev.y * HEIGHT
            if t == pygame.FINGERDOWN:
                self.toque_aperta(dedo, x, y)
            elif t == pygame.FINGERUP:
                self.toque_solta(dedo)
            else:
                self.toque_arrasta(dedo, x, y)
            return True
        if not self.toque.ativo:
            return False
        if t == pygame.MOUSEBUTTONDOWN:
            return self.toque_aperta(("m", ev.button), *ev.pos)
        if t == pygame.MOUSEBUTTONUP:
            dedo = ("m", ev.button)
            if dedo in self.toque.dedos:
                self.toque_solta(dedo)
                return True
        if t == pygame.MOUSEMOTION and self.toque.dedos:
            for dedo in list(self.toque.dedos):
                if dedo[0] == "m":
                    self.toque_arrasta(dedo, *ev.pos)
            return True
        return False

    def handle_event(self, ev):
        if ev.type == pygame.QUIT:
            self.encerrar = True
            return
        if self.evento_toque(ev):
            return
        if ev.type == pygame.KEYDOWN and not getattr(ev, "_do_toque", False):
            # tecla DE VERDADE (as que os botões geram vêm marcadas): quem tem
            # teclado não precisa dos botões na tela
            self.teclado_usado()

        if ev.type == pygame.KEYDOWN:
            if ev.key == pygame.K_ESCAPE and self.tela == TELA_INICIO:
                # ESC só encerra no menu: em jogo ele volta pra tela anterior,
                # e no navegador encerrar mataria a aba sem aviso
                self.encerrar = True
                return
            if ev.key == pygame.K_ESCAPE:
                self.tela = TELA_INICIO
                return
            if ev.key == pygame.K_r:
                # dentro de uma partida (ou no fim dela) R é revanche; no menu
                # não há o que repetir, então volta a ser recomeço
                if self.started or self.game_over:
                    self.revanche()
                else:
                    self.reset_round()
                return
            if ev.key == pygame.K_p and self.tela == TELA_JOGO and not self.game_over:
                self.pausado = not self.pausado
                return
            if ev.key == pygame.K_m:
                SOM.alternar_mudo()
                return
            if ev.key == pygame.K_F3:
                self.mostrar_fps = not self.mostrar_fps
                return
            if ev.key in (pygame.K_F11, pygame.K_f):
                # o estado não é guardado no Game: o R recria o Game inteiro, e
                # uma cópia da flag dessincronizaria da janela de verdade
                alternar_tela_cheia()
                return
            if self.tela == TELA_INICIO:
                if ev.key in (pygame.K_w, pygame.K_UP, pygame.K_s, pygame.K_DOWN):
                    self.menu_pick = 1 - self.menu_pick
                elif ev.key in (pygame.K_SPACE, pygame.K_RETURN):
                    self.modo = self.menu_pick + 1
                    self.quem_escolhe = 0
                    self.tela = TELA_QUADRA
                return
            if self.tela == TELA_QUADRA:
                if ev.key in (pygame.K_a, pygame.K_LEFT):
                    self.quadra_i = (self.quadra_i - 1) % len(QUADRAS)
                elif ev.key in (pygame.K_d, pygame.K_RIGHT):
                    self.quadra_i = (self.quadra_i + 1) % len(QUADRAS)
                elif ev.key in (pygame.K_w, pygame.K_UP):
                    i = PONTOS_OPCOES.index(self.alvo) if self.alvo in PONTOS_OPCOES else 1
                    self.alvo = PONTOS_OPCOES[(i + 1) % len(PONTOS_OPCOES)]
                elif ev.key in (pygame.K_s, pygame.K_DOWN):
                    i = PONTOS_OPCOES.index(self.alvo) if self.alvo in PONTOS_OPCOES else 1
                    self.alvo = PONTOS_OPCOES[(i - 1) % len(PONTOS_OPCOES)]
                elif ev.key == pygame.K_e:
                    atual = [v for _, v in ROUPA_OPCOES].index(Player.roupa)
                    Player.roupa = ROUPA_OPCOES[(atual + 1) % len(ROUPA_OPCOES)][1]
                    # já vestidos precisam trocar de roupa: os dois em quadra e
                    # o boneco da ficha, que é outro Player
                    for quem in (self.player, self.rival, getattr(self, "_modelo", None)):
                        if quem is not None and getattr(quem, "perfil", None):
                            quem.vestir(quem.perfil)
                elif ev.key in (pygame.K_SPACE, pygame.K_RETURN):
                    self.aplicar_quadra()
                    self.tela = TELA_ESCOLHA
                return
            if self.tela == TELA_ESCOLHA:
                self.teclas_escolha(ev.key)
                return
            # --- em jogo: cada humano no seu botão ---
            if ev.key == pygame.K_SPACE and not self.game_over:
                self.acao_press(self.player)
            elif (ev.key == pygame.K_RETURN and self.modo == 2
                    and not self.game_over):
                self.acao_press(self.rival)
            elif ev.key in self.player.k_cima and not self.game_over:
                self.cima_press(self.player)
            elif (ev.key in self.rival.k_cima and self.modo == 2
                    and not self.game_over):
                self.cima_press(self.rival)
            elif ev.key in self.player.k_super and not self.game_over:
                self.ativar_super(self.player)
            elif (ev.key in self.rival.k_super and self.modo == 2
                    and not self.game_over):
                self.ativar_super(self.rival)

        if ev.type == pygame.KEYUP and not self.selecting:
            if ev.key == pygame.K_SPACE:
                self.acao_release(self.player)
            elif ev.key == pygame.K_RETURN and self.modo == 2:
                self.acao_release(self.rival)

        if self.toque.ativo:
            # com botões na tela, um toque na quadra é só um toque — não o
            # começo de um arrasto de mira
            return
        if not self.started and ev.type in (pygame.MOUSEBUTTONDOWN,):
            self.started = True

        if self.game_over:
            return

        if ev.type == pygame.MOUSEBUTTONDOWN and self.ball.held:
            mx, my = ev.pos
            hx, hy = self.player.hand_pos()
            bx, by = self.player.ball_pos()   # clica na bola, que quicando desce
            if math.hypot(mx - bx, my - by) < 70:
                self.aiming = True
                self.charging = False    # a mira do mouse cancela a carga do espaço
                self.drag_start = (hx, hy)
                self.drag_current = (mx, my)

        elif ev.type == pygame.MOUSEMOTION and self.aiming:
            self.drag_current = ev.pos

        elif ev.type == pygame.MOUSEBUTTONUP and self.aiming:
            self.release_shot()
            self.aiming = False

    # --- fachada de um jogador só: no modo de 1 humano o "jogador" é sempre
    # self.player, e o resto do código pergunta por ele sem qualificar ---
    @property
    def quadra(self):
        return QUADRAS[self.quadra_i]

    def aplicar_quadra(self):
        """Troca o cenário: fundo, alambrado e o público que combina com ele."""
        self.bg, self.grade, _ = cenario(self.quadra)
        self.crowd = Crowd(self.quadra)
        # a imagem composta é do cenário ANTIGO: jogar fora, não remendar
        self._cenario = None
        self._cenario_t = -999

    # De quantos em quantos quadros o cenário é recomposto no navegador. Só
    # lá: no PC o gargalo é pixel, e recompor custa mais do que desenhar a
    # torcida direto na tela.
    PASSO_CENARIO = 8

    def _fundo_composto(self):
        """Fundo, torcida, alambrado e refletor numa imagem OPACA só.

        Eram quatro blits de tela cheia por quadro, três delas com alfa, mais
        ~400 blits de gente. Viram uma blit sem alfa, e o repinte da torcida
        passa a valer vários quadros — o que se perde é a oscilação de 1,2 px
        de quem está a 400 px de distância, atrás de um alambrado."""
        passo = 2 if self.crowd._festa > 0 else self.PASSO_CENARIO
        if self._cenario is None or self.crowd.t - self._cenario_t >= passo:
            if self._cenario is None:
                self._cenario = pygame.Surface((WIDTH, HEIGHT))
            self._cenario.blit(self.bg, (0, 0))
            self.crowd.draw(self._cenario)
            if self.grade is not None:
                self._cenario.blit(self.grade, (0, 0))
            if self.quadra["refletor"]:
                self._cenario.blit(HOOP_GLOW,
                                   (RIM_CX - HOOP_GLOW.get_width() // 2,
                                    RIM_Y - HOOP_GLOW.get_height() // 2))
            self._cenario_t = self.crowd.t
        return self._cenario

    @property
    def selecting(self):
        return self.tela != TELA_JOGO

    @selecting.setter
    def selecting(self, v):
        self.tela = TELA_ESCOLHA if v else TELA_JOGO

    @property
    def pick(self):
        return self.picks[self.quem_escolhe]

    @pick.setter
    def pick(self, v):
        self.picks[self.quem_escolhe] = v

    @property
    def charging(self):
        return self.player.charging

    @charging.setter
    def charging(self, v):
        self.player.charging = v

    @property
    def charge(self):
        return self.player.charge

    @charge.setter
    def charge(self, v):
        self.player.charge = v

    def on_space_press(self):
        self.acao_press(self.player)

    def on_space_release(self):
        self.acao_release(self.player)

    @property
    def dif(self):
        """Os multiplicadores do nível escolhido."""
        return DIFICULDADES[self.nivel]

    def draw_quadras(self, surface):
        """Escolha da quadra. Cada cartão mostra o CENÁRIO reduzido — a prévia
        é o próprio fundo do jogo, então não tem como ela mentir sobre o que
        você vai ver quando a bola subir."""
        veu = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        veu.fill((6, 6, 16, 232))
        surface.blit(veu, (0, 0))

        tit = FONT_BIG.render("ESCOLHA A QUADRA", True, GOLD)
        surface.blit(tit, (WIDTH // 2 - tit.get_width() // 2, 34))

        larg, alt = 280, 168
        vao = 20
        total = len(QUADRAS) * larg + (len(QUADRAS) - 1) * vao
        x0 = WIDTH // 2 - total // 2
        for i, q in enumerate(QUADRAS):
            sel = i == self.quadra_i
            cartao = pygame.Rect(x0 + i * (larg + vao), 140, larg, alt)
            fundo_q = cenario(q)[2]
            mini = pygame.transform.smoothscale(fundo_q, (larg - 8, alt - 8))
            if not sel:
                escurece = pygame.Surface(mini.get_size(), pygame.SRCALPHA)
                escurece.fill((0, 0, 0, 130))
                mini.blit(escurece, (0, 0))
            surface.blit(mini, (cartao.x + 4, cartao.y + 4))
            pygame.draw.rect(surface, GOLD if sel else (74, 76, 92), cartao,
                             4 if sel else 2, border_radius=8)

            nome = FONT_SMALL.render(q["nome"], True,
                                     WHITE if sel else (140, 142, 158))
            surface.blit(nome, (cartao.centerx - nome.get_width() // 2,
                                cartao.bottom + 12))
            if sel:
                desc = FONT_TINY.render(q["desc"], True, (200, 200, 216))
                surface.blit(desc, (WIDTH // 2 - desc.get_width() // 2, 368))

        # --- até quantos pontos vai a partida ---
        rot = FONT_SMALL.render("PARTIDA ATÉ", True, (206, 206, 216))
        larg = rot.get_width() + 18 + len(PONTOS_OPCOES) * 62
        x = WIDTH // 2 - larg // 2
        surface.blit(rot, (x, 402))
        x += rot.get_width() + 18
        for pts in PONTOS_OPCOES:
            sel = pts == self.alvo
            caixa = pygame.Rect(x, 398, 50, 30)
            fundo = pygame.Surface(caixa.size, pygame.SRCALPHA)
            pygame.draw.rect(fundo, (30, 30, 48, 230) if sel else (16, 16, 26, 200),
                             fundo.get_rect(), border_radius=6)
            surface.blit(fundo, caixa)
            pygame.draw.rect(surface, GOLD if sel else (92, 94, 110), caixa,
                             2 if sel else 1, border_radius=6)
            t = FONT_SMALL.render(str(pts), True, WHITE if sel else (142, 144, 158))
            surface.blit(t, (caixa.centerx - t.get_width() // 2, caixa.y + 4))
            x += 62

        # --- uniforme do time ou moletom ---
        rot2 = FONT_SMALL.render("ROUPA", True, (206, 206, 216))
        larg2 = rot2.get_width() + 18 + len(ROUPA_OPCOES) * 126
        x = WIDTH // 2 - larg2 // 2
        surface.blit(rot2, (x, 438))
        x += rot2.get_width() + 18
        for label, valor in ROUPA_OPCOES:
            sel = valor == Player.roupa
            # 98 px nao cabiam "UNIFORME" e o texto vazava pela borda
            caixa = pygame.Rect(x, 434, 116, 30)
            fundo = pygame.Surface(caixa.size, pygame.SRCALPHA)
            pygame.draw.rect(fundo, (30, 30, 48, 230) if sel else (16, 16, 26, 200),
                             fundo.get_rect(), border_radius=6)
            surface.blit(fundo, caixa)
            pygame.draw.rect(surface, GOLD if sel else (92, 94, 110), caixa,
                             2 if sel else 1, border_radius=6)
            t = FONT_SMALL.render(label, True, WHITE if sel else (142, 144, 158))
            surface.blit(t, (caixa.centerx - t.get_width() // 2, caixa.y + 4))
            x += 126

        dica = FONT_SMALL.render(
            "A / D  quadra     W / S  pontos     E  roupa     ESPAÇO confirma",
            True, (214, 214, 224))
        surface.blit(dica, (WIDTH // 2 - dica.get_width() // 2, 476))
        nota = FONT_TINY.render(
            "o público muda com o lugar: arquibancada cheia na arena, "
            "galera em pé atrás do alambrado na rua", True, (140, 142, 158))
        surface.blit(nota, (WIDTH // 2 - nota.get_width() // 2, 508))

    def draw_inicio(self, surface):
        """Tela de título: o nome do jogo, a escolha de modo e os controles."""
        # véu mais leve no alto que embaixo: a quadra viva aparece atrás sem
        # brigar com o texto, e a torcida em movimento dá vida à tela
        veu = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        for y in range(0, HEIGHT, 4):
            a = 186 + int(52 * (y / HEIGHT))
            pygame.draw.rect(veu, (6, 6, 16, a), (0, y, WIDTH, 4))
        surface.blit(veu, (0, 0))

        # ---------------- título ----------------
        tit = FONT_BIG.render("HOOP STARS", True, GOLD)
        sombra = FONT_BIG.render("HOOP STARS", True, (86, 56, 8))
        tx = WIDTH // 2 - tit.get_width() // 2
        surface.blit(sombra, (tx + 4, 58))
        surface.blit(tit, (tx, 54))
        sub = FONT_SMALL.render("B A S Q U E T E   1   C O N T R A   1",
                                True, (196, 198, 212))
        surface.blit(sub, (WIDTH // 2 - sub.get_width() // 2, 134))
        pygame.draw.line(surface, (110, 92, 44), (WIDTH // 2 - 190, 172),
                         (WIDTH // 2 + 190, 172), 2)

        # ---------------- modos ----------------
        opcoes = [("1 JOGADOR", "você contra a IA"),
                  ("2 JOGADORES", "dois no mesmo teclado")]
        for i, (rot, desc) in enumerate(opcoes):
            sel = i == self.menu_pick
            caixa = pygame.Rect(WIDTH // 2 - 196, 196 + i * 86, 392, 74)
            fundo = pygame.Surface(caixa.size, pygame.SRCALPHA)
            pygame.draw.rect(fundo, (34, 32, 54, 240) if sel else (16, 16, 28, 205),
                             fundo.get_rect(), border_radius=10)
            surface.blit(fundo, caixa)
            pygame.draw.rect(surface, GOLD if sel else (66, 68, 86), caixa,
                             3 if sel else 1, border_radius=10)
            t = FONT_MED.render(rot, True, WHITE if sel else (146, 148, 162))
            surface.blit(t, (caixa.centerx - t.get_width() // 2, caixa.y + 6))
            dt = FONT_TINY.render(desc, True,
                                  (206, 206, 220) if sel else (106, 108, 122))
            surface.blit(dt, (caixa.centerx - dt.get_width() // 2, caixa.y + 50))
            if sel:
                # a bola marca a opção escolhida
                bx, by = caixa.x - 30, caixa.centery
                pygame.draw.circle(surface, (216, 106, 36), (bx, by), 13)
                pygame.draw.circle(surface, (236, 140, 62), (bx - 4, by - 5), 5)
                pygame.draw.circle(surface, (26, 18, 14), (bx, by), 13, 2)
                pygame.draw.line(surface, (26, 18, 14), (bx - 13, by), (bx + 13, by), 2)
                pygame.draw.line(surface, (26, 18, 14), (bx, by - 13),
                                 (bx, by + 13), 2)

        dica = FONT_SMALL.render("W / S escolhe      ESPAÇO confirma", True,
                                 (220, 220, 230))
        surface.blit(dica, (WIDTH // 2 - dica.get_width() // 2, 370))

        # ---------------- controles, por situação ----------------
        quadro = pygame.Rect(96, 400, WIDTH - 192, 142)
        fundo = pygame.Surface(quadro.size, pygame.SRCALPHA)
        pygame.draw.rect(fundo, (12, 12, 24, 226), fundo.get_rect(), border_radius=10)
        surface.blit(fundo, quadro)
        pygame.draw.rect(surface, (58, 60, 78), quadro, 1, border_radius=10)

        cab = FONT_TINY.render("P1:  A D  mover  ·  W  cima  ·  ESPAÇO  ação  ·  S  modificador"
                               "        P2:  ← →  ·  ↑  ·  ENTER  ·  ↓",
                               True, (170, 172, 188))
        surface.blit(cab, (quadro.centerx - cab.get_width() // 2, quadro.y + 10))
        pygame.draw.line(surface, (52, 54, 70), (quadro.x + 20, quadro.y + 32),
                         (quadro.right - 20, quadro.y + 32), 1)

        linhas = [
            ("COM A BOLA", [("segure a ação", "arremesso"),
                            ("2x ação perto do aro", "enterrada"),
                            ("modificador + ação", "finta / bandeja")]),
            ("MODO", [("Q   (P2: SHIFT dir.)", "liga o MODO"),
                      ("enche jogando", "cesta, roubo, toco"),
                      ("cada um tem o seu", "veja na escolha")]),
            ("SEM A BOLA", [("cima", "toco / pulo"),
                            ("1x ação", "bote de roubo"),
                            ("2x a mesma direção", "arranque")]),
        ]
        for c, (titulo, itens) in enumerate(linhas):
            cx = quadro.x + 22 + c * (quadro.w // 3)
            th = FONT_TINY.render(titulo, True, GOLD)
            surface.blit(th, (cx, quadro.y + 44))
            for i, (tecla, efeito) in enumerate(itens):
                y = quadro.y + 68 + i * 22
                a = FONT_TINY.render(tecla, True, (198, 200, 214))
                b = FONT_TINY.render(efeito, True, (140, 142, 158))
                surface.blit(a, (cx, y))
                surface.blit(b, (cx + 140, y))

        reg = FONT_TINY.render(
            "errou a cesta? quem pegar o rebote leva a bola pra trás da linha de 3",
            True, (120, 122, 136))
        surface.blit(reg, (WIDTH // 2 - reg.get_width() // 2, quadro.bottom + 10))
        atalhos = FONT_TINY.render(
            "F11  tela cheia        P  pausa        M  som        "
            "R  revanche        ESC  volta",
            True, (116, 118, 132))
        surface.blit(atalhos,
                     (WIDTH // 2 - atalhos.get_width() // 2, quadro.bottom + 30))

    def teclas_escolha(self, tecla):
        """Navegação da tela de escolha. Cada jogador usa as próprias teclas —
        no modo de dois, quem não está na vez não mexe na escolha do outro."""
        eu = self.quem_escolhe
        if self.modo == 2:
            # com dois humanos cada um fica só com o seu par de teclas: senão
            # o P2, mexendo nas setas enquanto espera, muda a escolha do P1
            esq, dir_ = ((pygame.K_a,), (pygame.K_d,)) if eu == 0 else                         ((pygame.K_LEFT,), (pygame.K_RIGHT,))
        else:
            esq, dir_ = (pygame.K_a, pygame.K_LEFT), (pygame.K_d, pygame.K_RIGHT)
        passo = 0
        if tecla in esq:
            passo = -1
        elif tecla in dir_:
            passo = 1
        if passo:
            novo = (self.picks[eu] + passo) % len(ROSTER)
            # no modo de dois, o personagem do outro fica fora: dois iguais
            # ficariam indistinguíveis em quadra, os dois de preto
            while self.modo == 2 and novo == self.picks[1 - eu]:
                novo = (novo + passo) % len(ROSTER)
            self.picks[eu] = novo
            return
        if self.modo == 1 and tecla in (pygame.K_w, pygame.K_UP):
            self.nivel = (self.nivel + 1) % len(DIFICULDADES)
        elif self.modo == 1 and tecla in (pygame.K_s, pygame.K_DOWN):
            self.nivel = (self.nivel - 1) % len(DIFICULDADES)
        elif tecla in (pygame.K_SPACE, pygame.K_RETURN):
            self.confirmar_escolha()

    def confirmar_escolha(self):
        """Fecha a escolha. Com dois humanos, passa a vez pro segundo antes de
        começar; com um, a IA sorteia um adversário diferente do seu."""
        if self.modo == 2 and self.quem_escolhe == 0:
            self.quem_escolhe = 1
            if self.picks[1] == self.picks[0]:
                self.picks[1] = (self.picks[0] + 1) % len(ROSTER)
            return
        self.player.vestir(ROSTER[self.picks[0]])
        if self.modo == 2:
            self.rival.vestir(ROSTER[self.picks[1]])
        else:
            outros = [i for i in range(len(ROSTER)) if i != self.picks[0]]
            self.rival.vestir(ROSTER[random.choice(outros)])
        self.tela = TELA_JOGO
        self.started = True
        self.zerar_estatisticas()
        SOM.toca("apito", 0.8)

    def revanche(self):
        """Mesma dupla, mesma quadra, mesma dificuldade, placar zerado.

        `reset_round` não serve aqui: ele devolve o jogo pra tela de início e
        zera as escolhas. E em modo de um jogador o adversário é SORTEADO em
        `confirmar_escolha`, então nem repetir a dupla de propósito daria — por
        isso os dois perfis são guardados e recolocados à mão.
        """
        eu, ele = self.player.perfil, self.rival.perfil
        escolhas = list(self.picks)
        self.reset_round()
        self.picks = escolhas
        self.player.vestir(eu)
        self.rival.vestir(ele)
        self.quem_escolhe = 0
        self.tela = TELA_JOGO
        self.started = True
        self.pausado = False
        self.zerar_estatisticas()
        SOM.toca("apito", 0.8)

    def retrato(self, perfil, alt_px=None):
        """O personagem do perfil, desenhado grande.

        É o MESMO Player.draw do jogo, só ampliado — um retrato desenhado à
        parte poderia divergir do que aparece em quadra. Ele quica a bola: uma
        figura parada num menu lê como imagem, uma que se mexe lê como
        personagem."""
        if alt_px is None:
            # a altura em pixel sai da altura em cm: dois bonecos do mesmo
            # tamanho desmentiriam a linha "2.18 m" logo ao lado
            baixo = min(q["altura"] for q in ROSTER)
            alto = max(q["altura"] for q in ROSTER)
            t = (perfil["altura"] - baixo) / float(alto - baixo)
            alt_px = int(round(196 + 58 * t))
        if not hasattr(self, "_modelo"):
            self._modelo = Player()
            self._bola_retrato = Ball()
            self._tela_retrato = pygame.Surface((170, 260), pygame.SRCALPHA)
        p = self._modelo
        # compara a ROUPA também: só o perfil não basta, porque trocar de
        # uniforme pra moletom não troca o perfil — e o boneco ficaria vestido
        # com a roupa anterior enquanto o jogo usa a nova
        if (getattr(p, "perfil", None) is not perfil
                or getattr(p, "manga_longa", None) != (Player.roupa == "moletom")):
            p.vestir(perfil)
        p.x, p.y = 85, 244
        p.state = "idle"
        # sem quique no retrato: ball_pos() manda a bola pro FLOOR_Y GLOBAL da
        # quadra, que cai fora da superficie do retrato e some. Com a bola na
        # mao ela aparece, e o balanco do idle ja da vida a figura.
        p.dribbling = False
        p.facing = 1
        p.anim_t = self.frame_count * 0.9
        self._tela_retrato.fill((0, 0, 0, 0))
        p.draw(self._tela_retrato, True)
        # bola PROPRIA do retrato: usar a do jogo teleportaria a bola de
        # verdade pra dentro do menu
        b = self._bola_retrato
        b.x, b.y = p.ball_pos()
        b.held = False
        b.rotation = self.frame_count * 0.05
        b.draw(self._tela_retrato)
        # recorta pelo retangulo REAL do desenho e escala isso: com a
        # superficie inteira, o boneco (126 px num quadro de 260) ficava
        # pequeno no meio de um painel vazio
        r = self._tela_retrato.get_bounding_rect()
        if r.width < 4 or r.height < 4:
            return self._tela_retrato
        recorte = self._tela_retrato.subsurface(r).copy()
        esc = alt_px / float(r.height)
        return pygame.transform.smoothscale(
            recorte, (max(1, int(r.width * esc)), alt_px))

    def draw_select(self, surface):
        """Tela de escolha: o personagem desenhado, a ficha dele e os
        atributos. Com dois jogadores ela diz de quem é a vez e mantém a
        escolha já travada do primeiro à vista."""
        # veu quase opaco: aqui o assunto e o personagem, e a silhueta dos
        # jogadores da quadra viva atras vazava por baixo do painel
        veu = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        veu.fill((8, 8, 18, 240))
        surface.blit(veu, (0, 0))

        eu = self.quem_escolhe
        if self.modo == 2:
            titulo = "JOGADOR %d, ESCOLHA" % (eu + 1)
            cor_tit = (120, 200, 255) if eu == 0 else (255, 150, 120)
        else:
            titulo = "ESCOLHA SEU JOGADOR"
            cor_tit = GOLD
        tit = FONT_MED.render(titulo, True, cor_tit)
        surface.blit(tit, (WIDTH // 2 - tit.get_width() // 2, 16))

        # ---------------- fila de nomes ----------------
        n = len(ROSTER)
        col = WIDTH / n
        for i, perfil in enumerate(ROSTER):
            cam = perfil["cam"]
            sel = i == self.picks[eu]
            do_outro = self.modo == 2 and i == self.picks[1 - eu] and eu == 1
            cx = int(col * (i + 0.5))
            caixa = pygame.Rect(cx - 27, 58, 54, 30)
            pygame.draw.rect(surface, cam if sel else tuple(int(c * 0.40) for c in cam),
                             caixa, border_radius=5)
            if sel:
                pygame.draw.rect(surface, WHITE, caixa.inflate(5, 5), 2, border_radius=6)
            elif do_outro:
                pygame.draw.rect(surface, (120, 200, 255), caixa.inflate(5, 5),
                                 2, border_radius=6)
                p1 = FONT_TINY.render("P1", True, (120, 200, 255))
                surface.blit(p1, (cx - p1.get_width() // 2, 40))
            txt = FONT_TINY.render(perfil["nome"], True,
                                   WHITE if sel else (142, 142, 156))
            surface.blit(txt, (cx - txt.get_width() // 2, 91))

        perfil = ROSTER[self.picks[eu]]

        # ---------------- painel do personagem ----------------
        painel = pygame.Rect(56, 122, 240, 300)
        fundo = pygame.Surface(painel.size, pygame.SRCALPHA)
        pygame.draw.rect(fundo, (18, 18, 32, 235), fundo.get_rect(), border_radius=12)
        surface.blit(fundo, painel)
        # um facho atrás do jogador, na cor do time
        facho = pygame.Surface(painel.size, pygame.SRCALPHA)
        pygame.draw.ellipse(facho, (*perfil["cam"], 46),
                            (24, 150, painel.w - 48, 130))
        surface.blit(facho, painel)
        pygame.draw.rect(surface, perfil["cam"], painel, 2, border_radius=12)

        boneco = self.retrato(perfil)
        surface.blit(boneco, (painel.centerx - boneco.get_width() // 2,
                              painel.bottom - boneco.get_height() - 16))

        # ---------------- ficha ----------------
        x0 = 330
        nome = FONT_BIG.render(perfil["nome"], True, WHITE)
        surface.blit(nome, (x0, 112))
        fis = FONT_SMALL.render("%.2f m   ·   %d kg   ·   nº %s" % (
            perfil["altura"] / 100.0, perfil["peso"], perfil["num"]),
            True, (198, 200, 212))
        surface.blit(fis, (x0 + 4, 190))

        gestos = {"normal": "ARREMESSO CLÁSSICO", "rapido": "SOLTURA RELÂMPAGO",
                  "fadeaway": "FADEAWAY", "gancho": "GANCHO"}
        cartao = pygame.Rect(x0, 222, 610, 94)
        fundo = pygame.Surface(cartao.size, pygame.SRCALPHA)
        pygame.draw.rect(fundo, (24, 24, 40, 230), fundo.get_rect(), border_radius=8)
        surface.blit(fundo, cartao)
        pygame.draw.rect(surface, (70, 66, 44), cartao, 1, border_radius=8)
        hab = FONT_SMALL.render(perfil["traco"], True, GOLD)
        surface.blit(hab, (x0 + 14, 228))
        desc = FONT_TINY.render(perfil["traco_desc"], True, (190, 192, 204))
        surface.blit(desc, (x0 + 14, 254))
        # o que antes só se descobria jogando
        assinatura = DUNK_NAMES[perfil["dunks"][0]].rstrip("!")
        extra = FONT_TINY.render("%s   ·   cravada: %s"
                                 % (gestos[perfil["tiro"]], assinatura),
                                 True, (150, 152, 168))
        surface.blit(extra, (x0 + 14, 274))
        # o MODO é a maior diferença entre escolher um e outro; escondê-lo
        # atrás da primeira partida seria escolher no escuro
        modo = FONT_TINY.render(
            "MODO:  %s" % SUPER_DESC.get(perfil["hab"], perfil["traco_desc"]),
            True, (206, 178, 96))
        surface.blit(modo, (x0 + 14, 294))

        # ---------------- barras ----------------
        rotulos = ("ARREMESSO", "VELOCIDADE", "FORÇA", "DEFESA")
        valores = [perfil["arr"], perfil["vel"], perfil["forca"], perfil["defe"]]
        for i, (rot, val) in enumerate(zip(rotulos, valores)):
            y = 330 + i * 30
            lb = FONT_SMALL.render(rot, True, (206, 206, 216))
            surface.blit(lb, (x0, y))
            trilho = pygame.Rect(x0 + 152, y + 3, 380, 14)
            pygame.draw.rect(surface, (34, 36, 50), trilho, border_radius=7)
            cor = GOLD if val >= 9 else (perfil["cam"] if val >= 7 else (150, 152, 166))
            pygame.draw.rect(surface, cor, (trilho.x, trilho.y, int(38 * val), 14),
                             border_radius=7)
            vt = FONT_SMALL.render(str(val), True, WHITE)
            surface.blit(vt, (trilho.right + 12, y))

        # ---------------- rodapé ----------------
        if self.modo == 1:
            niv = FONT_SMALL.render("DIFICULDADE", True, (206, 206, 216))
            surface.blit(niv, (x0, 452))
            for i, d in enumerate(DIFICULDADES):
                sel = i == self.nivel
                txt = FONT_SMALL.render(d["nome"], True,
                                        WHITE if sel else (140, 142, 156))
                cx = x0 + 152 + i * 132
                caixa = pygame.Rect(cx - 6, 448, txt.get_width() + 20, 28)
                pygame.draw.rect(surface, (26, 26, 40), caixa, border_radius=6)
                pygame.draw.rect(surface, GOLD if sel else (108, 110, 124),
                                 caixa, 2, border_radius=6)
                surface.blit(txt, (cx + 4, 452))
            dica = ("A / D escolhe     W / S muda a dificuldade     ESPAÇO começa")
        elif eu == 0:
            dica = "JOGADOR 1:  A / D escolhe     ESPAÇO confirma"
        else:
            dica = "JOGADOR 2:  ← / → escolhe     ENTER começa"
        dt = FONT_SMALL.render(dica, True, (214, 214, 224))
        surface.blit(dt, (WIDTH // 2 - dt.get_width() // 2, 500))

    # ---------------- a IA ----------------
    def update_rival(self):
        """Decide o que o adversário faz e o move. Ele ataca a MESMA cesta, então
        atacar é avançar pra direita e defender é ficar entre você e o aro."""
        r = self.rival
        if self.game_over or not self.started:
            r.update(RivalKeys(), self.holder is r, False)
            return

        atacando = self.holder is r
        mirando = False
        dif = self.dif
        # sem isto, no modo de um jogador só o humano teria MODO: a IA encheria
        # o medidor a partida inteira e nunca usaria
        if r.super_carga >= 1.0 and not self.super_ativo(r):
            perto = abs(self.player.x - r.x) < CONTESTE_RANGE
            if atacando or perto:
                self.ativar_super(r)
        if atacando:
            self.rival_hold += 1
            if self.needs_clear:
                alvo = THREE_POINT_X - 40         # tem que limpar primeiro
            elif self.rival_plan == "shoot":
                alvo = 430                        # para atrás e arremessa
            else:
                # ponto de onde DÁ pra cravar. Antes o alvo virava "onde já
                # estou", e passado do aro ela ficava presa: longe demais pra
                # cravar e perto demais pra arremessar.
                alvo = min(DUNK_ZONE[1] - 30, max(r.alcance_dunk + 20, 745))
        elif self.holder is self.player:
            # DEFESA: fica entre o atacante e a cesta, do lado do aro — e
            # perto o bastante pra o bote alcançar (MARK_DIST < MARK_RANGE)
            alvo = min(RIM_CX - 55, self.player.x + MARK_DIST)
        else:
            alvo = self.ball.x                    # bola solta: corre atrás

        # quanto ela AINDA desliza se soltar a tecla agora: v*a + v*a^2 + ...
        # Sem descontar isso, a inércia faz a IA passar do alvo, voltar e
        # oscilar pra sempre em torno dele, sem nunca parar pra arremessar.
        freio = abs(r.vx) * ATRITO / (1.0 - ATRITO)
        margem = 6
        falta = alvo - r.x
        if abs(falta) <= max(margem, freio):
            keys = RivalKeys()               # deixa o atrito encostar no alvo
        else:
            keys = RivalKeys(esq=falta < 0, dir=falta > 0)
        # o nível mexe no passo da IA sem tocar no perfil do jogador: assim
        # trocar de nível não reescreve os atributos do elenco
        r.speed = (3.6 + r.perfil["vel"] * 0.32) * dif["vel"]

        if atacando and not self.needs_clear and r.action is None:
            # segurou demais? arremessa de onde estiver, pra nunca travar a partida
            if self.rival_hold > 70 and self.ball.held:
                ideal = self.ideal_shot_power(self.space_shot_angle(r), r)
                self.fire_shot_for(r, ideal * random.uniform(0.9, 1.1))
            elif (self.rival_plan == "drive" and r.in_dunk_zone()
                    and self.dunk_phase is None
                    and random.random() < 0.12 * dif["cravada"]):
                self.begin_dunk(r)
            elif abs(self.rim_offset(r)) > 150:
                # arremessa com a força ideal mais um erro: a IA não é perfeita
                self.rival_charge += 1
                if self.rival_charge > 26:
                    self.rival_charge = 0.0
                    ideal = self.ideal_shot_power(self.space_shot_angle(r), r)
                    # quanto melhor o arremesso, menor o erro da IA — e a
                    # habilidade dele encolhe o erro na mesma proporção em que
                    # alargaria a janela de um humano
                    err = ((0.12 - 0.008 * r.atr_arremesso)
                           * (self.janela(r) / r.shot_span) * dif["erro"])
                    self.fire_shot_for(r, ideal * random.uniform(1 - err, 1 + err))
                else:
                    mirando = True
        elif not atacando and self.holder is self.player:
            # defendendo: tenta roubar quando está colado, e tocar quando você
            # está armando o arremesso
            perto = abs(r.x - self.player.x) < MARK_RANGE
            if perto and self.player.charging and random.random() < 0.05 * dif["toco"]:
                self.tentar_toco(r)
            elif perto and random.random() < 0.035 * dif["roubo"]:
                self.tentar_roubo(r)

        r.update(keys, self.ball.held and atacando, mirando)

    # ---------------- posse de bola ----------------
    def rival_de(self, p):
        return self.rival if p is self.player else self.player

    def dar_bola(self, p, clear=True):
        """Passa a posse. `clear` liga a regra de levar a bola pra fora da
        linha de 3 antes de poder atacar."""
        self.ball.snap_to_hand(p.hand_pos())
        self.holder = p
        self.needs_clear = clear
        for quem in (self.player, self.rival):
            quem.charging = False
            quem.pending_shot = None
            quem.pending_shot_timer = 0
        self.rival_charge = 0.0
        self.aiming = False
        # uma cravada EM CURSO morre com a troca de posse, mas quem já está
        # PENDURADO continua pendurado: ele acabou de cravar, a bola ir pro
        # adversário é consequência disso, e quem solta o aro é o botão dele.
        # Zerar aqui deixava `suspended` ligado sem ninguém pra desligar.
        if self.dunk_phase != "hang":
            self.dunk_phase = None
        self.missed_shown = False
        p.suspended = False
        if p is self.rival:
            # decide o plano da posse: quanto melhor o arremesso, mais ela para
            # e arremessa em vez de ir pra cima
            self.rival_plan = ("shoot"
                               if random.random() < p.atr_arremesso / 15.0
                               else "drive")
            self.rival_hold = 0

    def tentar_roubo(self, ladrao):
        """Roubo: só pega se a mão estiver perto da bola, e tem recarga pra não
        virar martelar o botão."""
        vitima = self.rival_de(ladrao)
        if self.holder is not vitima or ladrao.action == "caido":
            return
        if self.super_ativo(vitima) and vitima.hab == "trem":
            # NINGUÉM SEGURA: no modo, a bola não sai da mão dele
            self.add_text(vitima.x, vitima.y - 140, "NÃO SAI!", (235, 200, 120),
                          size=17)
            return
        cd = "steal_cd" if ladrao is self.player else "rival_cd"
        if getattr(self, cd) > 0:
            return
        # CROSSOVER: quem tem a mão mais rápida tenta de novo na metade do tempo
        recarga = (STEAL_COOLDOWN // 2 if ladrao.hab == "crossover"
                   else STEAL_COOLDOWN)
        if self.super_ativo(ladrao) and ladrao.hab in SUPER_DONO_DA_BOLA:
            recarga //= 3           # no modo ele tenta de novo quase na hora
        setattr(self, cd, recarga)
        ladrao.trigger_steal()      # bote no chão, sem pular
        hx, hy = ladrao.hand_pos()
        # defesa do ladrão contra força de quem protege a bola
        chance = STEAL_CHANCE * (0.55 + 0.09 * ladrao.atr_defesa) \
            * (1.35 - 0.07 * vitima.atr_forca)
        if vitima.hab == "trem":
            chance *= 0.45          # TREM DESGOVERNADO: quase não perde a bola
        alcance = STEAL_RANGE * (1.5 if ladrao.hab == "alicate" else 1.0)
        if self.super_ativo(ladrao) and ladrao.hab in SUPER_DONO_DA_BOLA:
            # DONO DA BOLA: o bote alcança de longe e não falha — o que faltava
            # é chegar na bola, e no modo ele chega
            alcance *= 1.8
            chance = 1.0
        if (math.hypot(self.ball.x - hx, self.ball.y - hy) <= alcance
                and random.random() < chance):
            self.dar_bola(ladrao)
            if ladrao.hab == "showtime":
                ladrao.turbo = 90   # SHOWTIME: dispara em contra-ataque
                self.add_text(ladrao.x, ladrao.y - 150, "SHOWTIME!", GOLD, size=18)
            SOM.toca("tapa", 0.95)
            self.carregar_super(ladrao, SUPER_ROUBO)
            self.marcar(ladrao, "roubo")
            self.add_text(self.ball.x, self.ball.y - 34, "ROUBOU!", GOLD, size=20)
            self.shake = max(self.shake, 6)
        else:
            # errou o bote: o corpo foi junto com o braço e ele fica pra trás.
            # Sem esse custo, o defensor cola no atacante (a colisão para os
            # dois a 35 px, dentro do alcance) e rouba sem risco nenhum.
            ladrao.vx -= ladrao.facing * 3.4
            # a penalidade sai da recarga DELE: fixa na global, ela
            # apagava a recarga pela metade do CROSSOVER
            setattr(self, cd, int(recarga * 1.6))

    def tentar_toco(self, defensor):
        """Toco: pula com o braço esticado e abre uma janela em que a bola em
        voo pode ser tocada."""
        if self.holder is defensor:
            return
        defensor.start_jump(12.0)
        defensor.trigger_block()
        self.block_timer = BLOCK_WINDOW
        self.blocker = defensor

    def checar_toco(self):
        if self.block_timer <= 0 or self.blocker is None:
            return
        self.block_timer -= 1
        b = self.ball
        if b.held or b.scored_this_flight:
            return
        if self.shooter is not None and self.shooter.hab == "gancho":
            return                  # GANCHO CÉU: sai alto demais pra ser tocado
        if self.super_ativo(self.shooter) and self.shooter.hab in SUPER_INTOCAVEL:
            return                  # INTOCÁVEL: não há como alcançar
        hx, hy = self.blocker.hand_pos()
        alcance = BLOCK_RANGE * (0.7 + 0.06 * self.blocker.atr_defesa)
        if math.hypot(b.x - hx, b.y - hy) < alcance:
            b.vx = -abs(b.vx) * 0.5 - 2.0
            b.vy = 3.0
            b.scored_this_flight = True     # tocada não vale mais
            self.block_timer = 0
            SOM.toca("tapa", 1.0)
            self.carregar_super(self.blocker, SUPER_TOCO)
            self.marcar(self.blocker, "toco")
            # bola tocada não chega ao chão como erro (scored_this_flight já
            # foi marcada), então a tentativa perdida é contada aqui
            self.marcar(self.shooter, "erro")
            if self.shooter is not None and hasattr(self.shooter, "est"):
                self.shooter.est["seq_atual"] = 0
            self.add_text(hx, hy - 24, "TOCO!", GOLD, size=20)
            self.shake = max(self.shake, 10)
            self.spawn_burst(hx, hy, WHITE, n=12)

    # ---------------- controles do espaço ----------------
    def quer_manso(self, quem):
        """A tecla BAIXO está apertada? É o modificador das jogadas mansas —
        finta longe do aro, bandeja perto dele."""
        keys = getattr(self, "keys_atuais", None)
        if keys is None:
            return False
        try:
            return any(keys[k] for k in quem.k_baixo)
        except Exception:
            return False

    def fintar(self, quem):
        """Finta: o defensor perto pode COMPRAR e saltar."""
        quem.trigger_finta()
        d = self.rival_de(quem)
        if (abs(d.x - quem.x) < FINTA_RANGE and not d.jumping
                and d.action is None and not d.suspended):
            # defensor ruim compra mais: quem lê jogada fica no chão
            if random.random() < 0.72 - 0.045 * d.atr_defesa:
                d.start_jump(11.0)
                d.trigger_block()
                self.add_text(d.x, d.y - 150, "COMPROU!", GOLD, size=18)

    def bandeja(self, quem):
        """Bandeja: sobe a bola mansa em vez de cravar.

        Não dá poster e vale 2, mas é bem mais difícil de afundar que a
        cravada — a saída de quem é baixo demais pra passar por cima."""
        if not self.ball.held or self.holder is not quem:
            return
        quem.trigger_shoot(math.radians(-72), fade=False)
        quem.start_jump(9.5)
        alvo_x = (RIM_LEFT + RIM_RIGHT) / 2
        hx, hy = quem.hand_pos()
        dist = alvo_x - hx
        # Arco alto e curto, resolvido a partir da altura que falta: o apice
        # fica 30 px acima do aro e o tempo e o do cruzamento DESCENDO.
        subir = max(1.0, hy - RIM_Y)
        vy = -math.sqrt(2 * GRAVITY * (subir + 30))
        n = max(6.0, (-vy + math.sqrt(max(0.0, vy * vy - 2 * GRAVITY * subir)))
                / GRAVITY)
        vx = dist / n
        # a contestacao pesa na bandeja tambem, so que menos que na cravada:
        # ser mais dificil de afundar e justamente a razao de ela existir
        c = self.conteste(quem)
        erro = random.uniform(-1.0, 1.0) * c * c
        # 20% de erro deslocava a queda em ~12 px e a boca do aro tolera 23:
        # o erro precisa ser MAIOR que a tolerancia pra significar alguma coisa
        vx *= 1.0 + erro * 0.52
        vy *= 1.0 + erro * 0.10
        self.ball.launch(vx, vy, quem.x)
        # sobe por fora do aro: so passa a respeita-lo quando comeca a cair
        self.ball.ignore_rim = True
        self.ball.so_na_descida = True
        self.shooter = quem
        self.holder = None
        self.release_grace = 10
        self.add_text(quem.x, quem.y - 150, "BANDEJA", (210, 220, 240), size=17)

    def super_ativo(self, quem):
        """O MODO de `quem` está ligado agora?"""
        return quem is not None and getattr(quem, "super_frames", 0) > 0

    def carregar_super(self, quem, quanto):
        """Enche o medidor. Não passa de 1: acumular além disso guardaria
        ativações em estoque, e o modo deixaria de ser uma decisão de momento."""
        if quem is None or self.super_ativo(quem):
            return
        quem.super_carga = min(1.0, getattr(quem, "super_carga", 0.0) + quanto)

    def ativar_super(self, quem):
        """Liga o MODO, se estiver cheio."""
        if self.super_ativo(quem) or getattr(quem, "super_carga", 0.0) < 1.0:
            return
        quem.super_carga = 0.0
        quem.super_frames = SUPER_FRAMES
        grito = SUPER_GRITO.get(quem.hab, quem.traco)
        self.add_text(quem.x, quem.y - 170, grito, GOLD, size=26)
        self.spawn_burst(quem.x, quem.y - 60, GOLD, n=26)
        self.shake = max(self.shake, 7)
        SOM.toca("torcida_forte", 0.8)

    def cima_press(self, quem):
        """Tecla PRA CIMA: sem a bola é toco, com a bola é só pular.

        O toco continua saindo no toque duplo do botão de ação — nada foi
        removido. Mas toque duplo é um gesto que se descobre por acaso, e um
        lance de defesa dura poucos quadros: quem está defendendo precisa de um
        botão que faça a coisa na primeira vez.
        """
        if quem.suspended or quem.action == "caido":
            return
        if self.holder is not quem:
            self.tentar_toco(quem)
        elif not quem.jumping and quem.action is None:
            quem.start_jump()

    def acao_press(self, quem):
        """Botão de ação de `quem`. O mesmo botão faz tudo — o que ele faz
        depende de ter ou não a bola, e de ser toque simples ou duplo."""
        double_tap = (self.frame_count - quem.last_action_frame) <= DOUBLE_TAP_FRAMES
        quem.last_action_frame = self.frame_count
        quem.botao = True

        if self.holder is not quem:
            # SEM A BOLA: botão sozinho é bote de roubo (no chão);
            # 2x botão pula pro toco
            if double_tap:
                self.tentar_toco(quem)
            else:
                self.tentar_roubo(quem)
            return

        if self.needs_clear:
            # tem que sair da linha de 3 antes de atacar
            self.add_text(quem.x, quem.y - 130,
                          "SAIA DA LINHA DE 3", (235, 225, 200), size=20)
            return

        if self.quer_manso(quem) and quem.action is None:
            # BAIXO + ação: perto do aro é bandeja, longe é finta
            if abs(self.rim_offset(quem)) < BANDEJA_RANGE and self.dunk_phase is None:
                self.bandeja(quem)
            else:
                self.fintar(quem)
            return

        if (double_tap and self.ball.held and quem.in_dunk_zone()
                and self.dunk_phase is None):
            # 2ª batida perto do aro: ENTERRA (descarta o arremesso em espera)
            quem.pending_shot = None
            quem.pending_shot_timer = 0
            quem.charging = False
            self.begin_dunk(quem)
        elif self.ball.held and self.dunk_phase is None:
            quem.charging = True     # começa a carregar a força
            quem.charge = 0.0
        elif not self.ball.held:
            quem.start_jump()

    def acao_release(self, quem):
        quem.botao = False
        if quem.suspended:
            # soltou o aro: o gatilho é `suspended`, o mesmo estado que congela
            # o jogador, então não há como um soltar sem o outro
            self.release_hang()
            return
        if not quem.charging:
            return
        quem.charging = False
        pos = self.charge_meter(quem)
        # guarda ONDE soltou, pra barra congelar mostrando o resultado. Sem
        # devolutiva o jogador erra e nao sabe se errou por muito ou por pouco,
        # que e a unica informacao com a qual ele aprenderia o tempo.
        self.flash_medidor = [quem, pos, self.resultado_medidor(quem, pos),
                              MEDIDOR_FLASH]
        power = self.charge_power(quem)
        if (quem.charge <= QUICK_TAP_FRAMES and self.ball.held
                and quem.in_dunk_zone()):
            # perto do aro, um toque curto pode ser a 1ª batida de uma enterrada:
            # segura o arremesso até a janela do duplo-toque fechar
            quem.pending_shot = power
            quem.pending_shot_timer = DOUBLE_TAP_FRAMES
        else:
            self.fire_shot_for(quem, power)

    # Quanto cada traco de arremessador estica o alcance confortavel, em px.
    # Entra AQUI e nao na largura da janela porque quem arremessa bem de longe
    # nao tem so a mao mais firme -- tem o alcance maior. Estreitar a janela
    # era um efeito que a penalidade de distancia engolia inteiro.
    ALCANCE_TRACO = {"chuva3": 155.0, "sanguefrio": 85.0,
                     "mentalidade": 70.0, "gancho": 60.0, "flamingo": 55.0}

    def alcance_confortavel(self, quem):
        """Até onde o arremesso dele ainda é arremesso, e não chute.

        Sai da pontaria — quem tem 10 se sente em casa além da linha de 3, quem
        tem 3 só perto da cesta — mais o que o traço dele estica. É o número
        que impede o pivô de acertar de longe como o melhor arremessador do
        elenco, e o que devolve ao Curry a linha de 3 como território dele.

        (140 + 38: com 170 + 52 o melhor arremessador ficava confortável a
        690 px, ou seja, a quadra inteira, e meia quadra não penalizava
        ninguém.)
        """
        base = 140.0 + 38.0 * quem.atr_arremesso
        return base + self.ALCANCE_TRACO.get(quem.hab, 0.0)

    def zona_verde(self, quem):
        """Meia-largura da zona verde, em fração do medidor.

        Sai da mesma conta que decide o arremesso: a força solta é
        `ideal * (1 - span + 2*span*medidor)`, então o erro relativo é
        `2*span*(medidor - 0.5)`. Soltar dentro de SHOT_TOL da ideal é soltar a
        menos de `SHOT_TOL / (2*span)` do meio. Com isso a barra não pode
        divergir do que o jogo faz — as duas leem o mesmo `span`.

        Sobre essa base entram as duas coisas que decidem um arremesso de
        verdade e antes não entravam em lugar nenhum: a DISTÂNCIA e o
        DEFENSOR. Passado o alcance confortável a janela fecha, e fecha até
        ZERO — sem zona verde não existe soltura garantida, e o arremesso vira
        aposta. É assim que a barra para de prometer onde a promessa não se
        sustenta, em vez de prometer e não cumprir.
        """
        # a DISTÂNCIA não aparece aqui: ela já entrou no `span`, e a zona sai
        # do span. Escrevê-la nos dois lugares cobraria duas vezes pela mesma
        # coisa e desencontraria na primeira mexida em um dos dois.
        span = max(0.02, self.janela(quem))
        base = SHOT_TOL / (2.0 * span)
        # o DEFENSOR, ao contrário, fica só aqui: o espalhamento por
        # contestação já existe em `fire_shot_for`, depois da soltura. O que
        # falta é a zona verde parar de PROMETER cesta com alguém na cara — e
        # como ela é desenhada todo quadro, ela encolhe na tela enquanto o
        # defensor se aproxima.
        base *= max(0.12, 1.0 - 0.6 * self.conteste(quem))
        # PISO: janela mais estreita que um quadro do medidor não é zona, é
        # ruído — e ruído CENTRADO no meio da barra é acertado por quem mira no
        # meio, que é todo mundo com boa mão. Abaixo disso não existe soltura
        # garantida, e a barra para de mostrar verde onde não há promessa.
        if base < 1.0 / CHARGE_FRAMES:
            return 0.0
        return max(0.0, min(0.46, base))

    def resultado_medidor(self, quem, pos):
        """Como foi a soltura: "verde", "quase" ou "fora"."""
        d = abs(pos - 0.5)
        verde = self.zona_verde(quem)
        # janela FECHADA (longe demais pra pontaria dele, ou defensor na cara)
        # não tem soltura garantida: com `d <= verde` e os dois em zero, o
        # arremesso perfeito continuava caindo num lugar onde a barra não
        # mostrava verde nenhum
        if verde > 1e-6 and d <= verde:
            return "verde"
        return "quase" if d <= verde * SHOT_TOL_QUASE else "fora"

    def charge_meter(self, quem=None):
        """Posição do medidor, de 0 a 1. O ponto certo fica em 0.5."""
        return min(1.0, (quem or self.player).charge / CHARGE_FRAMES)

    def cruzamento_no_aro(self, x0, y0, vx, vy):
        """Onde a trajetória cruza o plano do aro, já descendo. None se não cruza.

        Integra EXATAMENTE como `Ball.update` — `vy += g`, depois a posição. A
        parábola contínua e este integrador divergem uns 15 px ao longo de um
        arremesso longo, e 15 px é a diferença entre entrar e raspar o poste.
        """
        for _ in range(400):
            vy += GRAVITY
            nx, ny = x0 + vx, y0 + vy
            if vy > 0 and y0 < RIM_Y <= ny:
                return x0 + vx * (RIM_Y - y0) / (ny - y0)
            x0, y0 = nx, ny
            if y0 > FLOOR_Y:
                return None
        return None

    def ideal_shot_power(self, angle, quem=None):
        """Força que faz a bola cair no centro da cesta.

        A fórmula da parábola entra só como CHUTE INICIAL; o valor devolvido é
        refinado por bisseção contra o integrador de verdade. Corrigir a fórmula
        com um fator resolveria hoje e voltaria a divergir na próxima mexida na
        física da bola — resolver contra o simulador não tem como divergir dele.
        """
        quem = quem or self.player
        hx, hy = quem.hand_pos()
        dist = abs(self.rim_offset(quem))
        rise = hy - RIM_Y
        th = -angle                       # ângulo positivo acima da horizontal
        denom = math.cos(th) ** 2 * (dist * math.tan(th) - rise)
        if dist <= 0 or denom <= 0:
            return SHOT_MAX_POWER * 0.5
        chute = dist * math.sqrt(0.5 * GRAVITY / denom) / SHOT_POWER

        lado = 1.0 if self.rim_offset(quem) >= 0 else -1.0
        alvo = (RIM_LEFT + RIM_RIGHT) / 2.0

        def erro(p):
            v = p * SHOT_POWER
            onde = self.cruzamento_no_aro(hx, hy, math.cos(th) * v * lado,
                                          -math.sin(th) * v)
            # não cruza descendo: conta como "curto demais" pra bisseção andar
            # pro lado certo em vez de parar
            return -1e6 if onde is None else (onde - alvo) * lado

        lo, hi = chute * 0.45, chute * 2.2
        if erro(hi) < 0:
            return min(SHOT_MAX_POWER, hi)
        if erro(lo) > 0:
            return max(SHOT_MIN_POWER, lo)
        for _ in range(26):
            meio = (lo + hi) / 2.0
            if erro(meio) < 0:
                lo = meio
            else:
                hi = meio
        return (lo + hi) / 2.0

    def janela(self, quem):
        """Largura do medidor já com a habilidade dele. MENOR = mais perdoante,
        porque cada quadro do medidor mexe menos na força."""
        span = quem.shot_span
        if quem.hab == "sanguefrio":
            span *= 0.80            # SANGUE FRIO: a janela dele é sempre maior
        elif quem.hab == "chuva3" and quem.x < THREE_POINT_X:
            span *= 0.65            # CHUVA DE 3: de fora da linha quase não erra
        elif quem.hab == "mentalidade":
            meu = self.score if quem is self.player else self.rival_score
            dele = self.rival_score if quem is self.player else self.score
            if meu < dele:
                span *= 0.72        # MENTALIDADE: perdendo, ele cresce
        if self.super_ativo(quem):
            # TIRO CERTO: a janela vira quase o medidor inteiro — errar passa a
            # exigir soltar no extremo da barra. Os outros também ganham, menos.
            span *= 0.22 if quem.hab in SUPER_TIRO_CERTO else 0.62
        # DISTÂNCIA: passado o alcance confortável dele, a força ESPALHA. Tem
        # que ser aqui e não na zona verde: fora do verde a força sai deste
        # span, e com ele apertado uma soltura torta ainda caía dentro da
        # tolerância da cesta — o medidor separava bem de mal e a bola entrava
        # igual. Mexendo aqui, a zona verde encolhe sozinha, porque ela é
        # derivada deste mesmo número.
        sobra = abs(self.rim_offset(quem)) - self.alcance_confortavel(quem)
        if sobra > 0:
            span *= 1.0 + min(3.4, sobra / 92.0)
        return span

    def charge_power(self, quem=None):
        quem = quem or self.player
        ideal = self.ideal_shot_power(self.space_shot_angle(quem), quem)
        medidor = self.charge_meter(quem)
        # SOLTURA VERDE: sai com a força ideal, não com a que o medidor
        # computaria. A zona verde é uma promessa desenhada na tela; cumpri-la
        # calibrando uma tolerância seria frágil — a janela real muda com a
        # distância e com o arco, e nenhuma constante casa em toda a quadra.
        # Assim acertar o tempo É acertar o arremesso, que é o que a barra diz.
        if self.resultado_medidor(quem, medidor) == "verde":
            return max(SHOT_MIN_POWER, min(SHOT_MAX_POWER, ideal))
        span = self.janela(quem)
        power = ideal * (1 - span + 2 * span * medidor)
        return max(SHOT_MIN_POWER, min(SHOT_MAX_POWER, power))

    def space_shot_angle(self, quem=None):
        """Arco do arremesso: quase vertical de perto, mais aberto de longe.

        O arco tem um PISO vindo da geometria. Cesta só conta com a bola
        descendo, e para um ângulo fixo a bola cruza o alvo descendo apenas se
        `dist * tan(ângulo) > 2 * subida`. A 59 px do aro, 80 graus dão 283
        contra os 336 necessários — a bola chegava no aro ainda subindo e
        nenhuma força acertava. O piso sai da própria desigualdade, com margem.
        """
        quem = quem or self.player
        dist = abs(self.rim_offset(quem))
        t = min(1.0, dist / 760.0)
        graus = SPACE_ANGLE_NEAR - (SPACE_ANGLE_NEAR - SPACE_ANGLE_FAR) * t
        subida = quem.hand_pos()[1] - RIM_Y
        if dist > 1.0 and subida > 0.0:
            piso = math.degrees(math.atan(2.4 * subida / dist))
            # o teto era 86 graus e o piso pedia 87,4 a 19 px do aro: com o
            # teto abaixo do piso, nao existe forca que faca a bola descer no
            # aro, e a promessa do verde falhava debaixo da cesta
            graus = max(graus, min(88.0, piso))
        return math.radians(-graus)

    def rim_offset(self, quem=None):
        """Distância horizontal da mão até o centro da cesta, com sinal
        (positivo = a cesta está à direita do jogador)."""
        quem = quem or self.player
        return (RIM_LEFT + RIM_RIGHT) / 2 - quem.hand_pos()[0]

    def space_shot_velocity(self, power, quem=None):
        """Velocidade do arremesso pelo teclado, já apontada para a cesta —
        funciona dos dois lados dela, já que o jogador percorre a quadra toda."""
        quem = quem or self.player
        angle = self.space_shot_angle(quem) + getattr(self, "shot_erro", 0.0)
        speed = power * SHOT_POWER
        direction = 1 if self.rim_offset(quem) >= 0 else -1
        return math.cos(angle) * speed * direction, math.sin(angle) * speed

    def fire_space_shot(self, power):
        if not self.ball.held or self.dunk_phase is not None:
            return
        self.fire_shot_for(self.player, power)

    def vantagem_aerea(self, alto, baixo):
        """Quanto `alto` leva a melhor sobre `baixo` numa disputa de bola no ar.

        Sai da ALTURA (mão mais alta chega antes na bola) e da FORÇA (quem
        segura o corpo no contato termina a jogada). 1.0 é equilíbrio. É a
        mesma conta pro arremesso contestado e pra disputa da cravada — as
        duas disputas são a mesma coisa, e ficariam incoerentes se cada uma
        tivesse a sua fórmula."""
        dh = (alto.altura_cm - baixo.altura_cm) / 100.0      # metros de diferença
        df = (alto.atr_forca - baixo.atr_forca) / 10.0
        return max(0.35, min(2.2, 1.0 + dh * 1.7 + df * 0.55))

    def conteste(self, quem):
        """Quanto o defensor atrapalha o arremesso de `quem`, de 0 a 1.

        Conta a distância, se ele está NO AR (mão levantada incomoda muito mais
        que corpo parado) e a defesa dele. É o que separa um arremesso aberto de
        um arremesso na cara — antes os dois davam exatamente o mesmo."""
        d = self.rival_de(quem)
        if d.suspended:
            return 0.0
        if self.super_ativo(quem) and quem.hab in (SUPER_INTOCAVEL
                                                   + SUPER_TIRO_CERTO):
            return 0.0      # arremessa como se estivesse sozinho na quadra
        dist = abs(d.x - quem.x)
        if dist >= CONTESTE_RANGE:
            return 0.0
        perto = 1.0 - dist / CONTESTE_RANGE
        no_ar = 1.0 if (d.jumping or d.action == "block") else 0.55
        return min(1.0, perto * no_ar * (0.55 + 0.05 * d.atr_defesa)
                   * self.vantagem_aerea(d, quem))

    def fire_shot_for(self, quem, power):
        """Solta o arremesso de `quem`. Guarda o autor pra creditar o ponto."""
        if not self.ball.held or self.holder is not quem or self.dunk_phase is not None:
            return
        # um defensor em cima suja a força e o ângulo: arremesso aberto
        # continua sendo do medidor, contestado vira aposta
        c = self.conteste(quem)
        if c > 0.01:
            # o erro cresce com o QUADRADO da pressão: contestação leve quase
            # não muda nada, na cara erra feio. Linear, o arremesso muito
            # contestado ainda caía com frequência demais.
            peso = c * c
            power *= 1.0 + random.uniform(-1.0, 1.0) * CONTESTE_FORCA * peso
            self.shot_erro = random.uniform(-1.0, 1.0) * CONTESTE_ANGULO * peso
            if c > 0.45:
                self.add_text(quem.x, quem.y - 150, "NA CARA!",
                              (235, 170, 80), size=17)
        else:
            self.shot_erro = 0.0
        vx, vy = self.space_shot_velocity(power, quem)
        quem.facing = 1 if vx >= 0 else -1
        quem.trigger_shoot(math.atan2(vy, vx))
        self.ball.launch(vx, vy, quem.x)
        # SOBE POR FORA DO ARO, como a bandeja: de perto, o arco passa raspando
        # o poste pelo lado de baixo e a bola batia nele ainda subindo. O aro
        # volta a valer no instante em que ela começa a cair.
        self.ball.ignore_rim = True
        self.ball.so_na_descida = True
        self.shooter = quem
        self.holder = None
        self.release_grace = 10

    def begin_dunk(self, quem):
        # o jogador salta até a posição em que a mão pousa em cima do aro
        self.dunker = quem
        self.dunk_saida = None      # o resultado da disputa, sorteado uma vez
        quem.trigger_dunk(RIM_LEFT + RIM_GRAB_INSET - 26)
        self.dunk_phase = "windup"

    def release_hang(self):
        """Soltou o aro: a gravidade volta e o jogador cai (a bola já foi
        cravada). Solta QUEM estiver pendurado, em vez de um jogador fixo."""
        self.dunk_phase = None
        self.hang_frames = 0
        for quem in (self.player, self.rival):
            quem.suspended = False

    def execute_dunk_slam(self):
        hx, hy = self.dunker.hand_pos()
        # a mão agora alcança o aro por cima, então a cravada empurra a bola
        # PARA BAIXO, na direção do centro da cesta (e não pra cima como antes)
        rim_cx = (RIM_LEFT + RIM_RIGHT) / 2
        dx, dy = rim_cx - hx, (RIM_Y + 26) - hy
        dist = max(1.0, math.hypot(dx, dy))
        speed = 11.0
        self.ball.held = False
        self.ball.x, self.ball.y = hx, hy
        self.ball.vx = dx / dist * speed
        self.ball.vy = dy / dist * speed
        self.ball.shot_origin_x = self.dunker.x
        self.ball.touched_rim = False
        self.ball.in_air = True
        self.ball.ignore_rim = True
        self.ball.scored_this_flight = "DUNK"  # marcador especial: pontuação garantida
        self.shooter = self.dunker
        self.holder = None
        self.shake = max(self.shake, 14)
        self.rim_flex_vel += RIM_SLAM_IMPULSE   # tranco no aro no instante da cravada
        if self.super_ativo(self.dunker) and self.dunker.hab == "quebra":
            self.quebrar_tabela()
        # POSTER: quem estava embaixo tentando impedir vai ao chão
        vitima = self.rival_de(self.dunker)
        if (abs(vitima.x - self.dunker.x) < POSTER_RANGE
                and not vitima.suspended and vitima.action != "caido"
                and self.ball.scored_this_flight == "DUNK"):
            vitima.derrubar()
            self.add_text(vitima.x, vitima.y - 120, "POSTER!", (255, 120, 90), size=30)
            self.shake = max(self.shake, 22)
            self.spawn_burst(vitima.x, vitima.y - 40, (255, 150, 110), n=18)
            self.crowd.cheer(vitima.x, 1.6)
        self.release_grace = 10
        self.spawn_burst(hx, hy, GOLD, n=10)

    def release_shot(self):
        hx, hy = self.drag_start
        mx, my = self.drag_current
        dx, dy = hx - mx, hy - my
        power = min(math.hypot(dx, dy), SHOT_MAX_POWER)
        if power < 8:
            return
        angle = math.atan2(dy, dx)
        speed = power * SHOT_POWER
        vx = math.cos(angle) * speed
        vy = math.sin(angle) * speed
        self.player.trigger_shoot(angle)
        self.ball.launch(vx, vy, self.player.x)
        self.release_grace = 10

    def zerar_estatisticas(self):
        """Ficha em branco pros dois. Chamado no começo de cada partida."""
        for quem in (self.player, self.rival):
            quem.est = dict(pontos=0, cesta=0, erro=0, cravada=0,
                            toco=0, roubo=0, seq=0, seq_atual=0)

    def marcar(self, quem, campo, quanto=1):
        """Soma um evento na ficha do jogador.

        Tolera ficha inexistente porque `Player` é criado antes da partida (a
        tela de escolha desenha um), e um teste pode chamar a lógica sem passar
        por `confirmar_escolha`."""
        if quem is None:
            return
        if not hasattr(quem, "est"):
            quem.est = dict(pontos=0, cesta=0, erro=0, cravada=0,
                            toco=0, roubo=0, seq=0, seq_atual=0)
        quem.est[campo] = quem.est.get(campo, 0) + quanto

    def som_do_drible(self):
        """O quique do drible, no instante em que a bola toca o chão.

        A bola do drible não é simulada — a altura dela é uma parábola em
        função da fase (ver `dribble_push`), e o chão é a fase 0,5. Por isso o
        som sai no CRUZAMENTO da fase por 0,5, e não num contador próprio: som
        fora de sincronia com a bola na tela o ouvido percebe muito antes de
        perceber um som errado.
        """
        quem = self.holder
        if quem is None or not quem.dribbling:
            self._fase_drible = 0.0
            return
        fase = (quem.anim_t % quem.DRIBBLE_PERIOD) / quem.DRIBBLE_PERIOD
        if fase >= 0.5 > self._fase_drible:
            SOM.toca("quique", 0.42)
        self._fase_drible = fase

    # ---------------- lógica principal ----------------
    def update(self, keys):
        if self.pausado and self.tela == TELA_JOGO:
            return          # nada anda: nem bola, nem torcida, nem relógio
        self.frame_count += 1
        self.net.update(self.ball)   # a rede reage à bola atravessando
        self.som_do_drible()
        for quem in (self.player, self.rival):
            if quem.super_frames > 0:
                quem.super_frames -= 1
            if quem.sprint_estalo:
                # poeira nos pés no instante da arrancada. Sai daqui e não do
                # jogador porque as partículas são do JOGO — o jogador não tem
                # como alcançá-las, e passar o mundo inteiro pra ele só pra
                # isso seria pior que a bandeira.
                quem.sprint_estalo = False
                for _ in range(9):
                    self.particles.append(Particle(
                        quem.x - quem.facing * 12, quem.y - 4,
                        (188, 176, 150),
                        vx=-quem.facing * random.uniform(0.8, 3.2),
                        vy=random.uniform(-1.8, -0.2),
                        life=random.randint(14, 26), size=3, gravity=0.06))
        if self.flash_medidor is not None:
            self.flash_medidor[3] -= 1
            if self.flash_medidor[3] <= 0:
                self.flash_medidor = None
        self.crowd.update()
        # carregando conta como "mirando": o jogador segura a bola parada, senão o
        # quique mudaria a altura de lançamento e a prévia mentiria sobre o arco
        self.keys_atuais = keys      # a finta/bandeja precisam saber do BAIXO
        self.player.update(keys, self.ball.held and self.holder is self.player,
                           self.aiming or self.player.charging)
        if self.modo == 2:
            # o adversário é um humano: lê o teclado como o primeiro
            self.rival.update(keys, self.ball.held and self.holder is self.rival,
                              self.rival.charging)
        else:
            self.update_rival()
        # Os corpos se ATRAVESSAM. A física de contato existia pra dar peso
        # ao elenco (o Shaq tirando o Iverson do garrafão), mas num 1 contra
        # 1 o defensor termina plantado no caminho o tempo todo: o que se
        # ganhava em peso se perdia em fluidez, e quem joga sente a trava
        # muito mais do que sente o peso.
        for cd in ("steal_cd", "rival_cd"):
            if getattr(self, cd) > 0:
                setattr(self, cd, getattr(self, cd) - 1)
        # levou a bola pra fora da linha de 3: pode atacar
        if self.needs_clear and self.holder and self.holder.x < THREE_POINT_X:
            self.needs_clear = False
        self.checar_toco()

        # aro de mola: afunda com o peso de quem está pendurado e volta ao soltar
        # o repouso da mola é 0 com o aro inteiro e fica torto depois da
        # DEMOLIÇÃO — e como a rede é desenhada a partir da mesma flexão, ela
        # entorta junto sem nenhum desenho novo
        repouso = 13.0 if self.aro_quebrado else 0.0
        alvo = RIM_FLEX_HANG if self.dunk_phase == "hang" else repouso
        self.rim_flex_vel += (alvo - self.rim_flex) * RIM_FLEX_SPRING
        self.rim_flex_vel *= RIM_FLEX_DAMP
        self.rim_flex += self.rim_flex_vel
        if self.dunk_phase == "hang":
            # desce junto com o aro, senão as mãos descolam dele
            self.dunker.jump_offset = self.hang_offset - self.rim_flex

        # rede de segurança: se o KEYUP do espaço se perder (o jogador troca de
        # janela com o botão apertado, por exemplo) o jogador não pode ficar
        # dependurado pra sempre — a física dele está pausada nesse estado
        if self.player.suspended or self.rival.suspended:
            self.hang_frames += 1
            if self.hang_frames > HANG_MAX_FRAMES:
                self.release_hang()
        else:
            self.hang_frames = 0

        # FUNDAMENTO: o erro dele morre no aro em vez de espirrar pra longe,
        # então ele mesmo pega o rebote
        b = self.ball
        if (not b.held and b.touched_rim and not b.scored_this_flight
                and self.shooter is not None and self.shooter.hab == "fundamento"):
            b.vx *= 0.88

        for quem in (self.player, self.rival):
            if quem.charging:
                quem.charge += 1
            if quem.pending_shot_timer > 0:
                quem.pending_shot_timer -= 1
                if quem.pending_shot_timer == 0 and quem.pending_shot is not None:
                    self.fire_shot_for(quem, quem.pending_shot)
                    quem.pending_shot = None

        if self.dunk_phase == "windup":
            p = self.dunker
            if p.action == "dunk":
                # compara CONTAGEM DE QUADROS, não frações: `1 - 23/34` não é
                # exatamente `11/34` em ponto flutuante, e por esse fio o agarre
                # escorregava um quadro e o jogador subia alto demais
                d = self.rival_de(p)
                disputa = (p.action_timer <= DUNK_SLAM_FRAMES + 6 and d.jumping
                           and not d.suspended and abs(d.x - p.x) < AFUNDA_RANGE
                           and self.shooter is not d)
                if disputa and self.dunk_saida is None:
                    # TRES saidas, e nao tudo-ou-nada: quanto mais alto e mais
                    # forte o defensor, mais o sorteio pende pro afundar.
                    # Sorteado UMA VEZ: a janela dura ~7 quadros, e refazer o
                    # sorteio a cada um fazia a cravada precisar sobreviver a
                    # sete moedas seguidas -- 92% delas morriam no ferro.
                    perto = 1.0 - abs(d.x - p.x) / AFUNDA_RANGE
                    placar = min(0.92, (0.26 + 0.34 * perto)
                                 * self.vantagem_aerea(d, p))
                    if self.super_ativo(p) and p.hab in SUPER_VOO:
                        # VOO: no modo ninguém tira a cravada da mão dele
                        placar = 0.0
                    sorte = random.random()
                    if sorte < placar * 0.55:
                        self.dunk_saida = "afundou"
                    elif sorte < placar:
                        self.dunk_saida = "errou"
                    else:
                        self.dunk_saida = "passou"
                saida = self.dunk_saida or "passou"
                if disputa and saida == "errou":
                    # a cravada saiu torta: bate no aro e vira bola viva
                    self.execute_dunk_slam()
                    self.ball.scored_this_flight = False
                    self.ball.ignore_rim = False
                    self.ball.vx *= 0.45
                    self.ball.vy = -3.0
                    self.add_text(p.x, p.y - 150, "NO FERRO!", (235, 170, 80), size=20)
                elif disputa and saida == "afundou":
                    # AFUNDOU: defensor no ar, junto da mão — a cravada não é
                    # mais ponto garantido. Antes o estouro marcava o ponto por
                    # construção e não havia defesa possível.
                    self.dunk_phase = None
                    p.action = None
                    p.action_timer = 0
                    self.ball.held = False
                    self.holder = None
                    hx, hy = p.hand_pos()
                    self.ball.x, self.ball.y = hx, hy
                    self.ball.vx = -abs(self.ball.vx) - 4.5
                    self.ball.vy = -2.0
                    self.ball.in_air = True
                    self.ball.ignore_rim = False
                    self.ball.scored_this_flight = True   # não vale mais
                    self.release_grace = 10
                    self.shake = max(self.shake, 12)
                    self.add_text(hx, hy - 26, "AFUNDOU!", GOLD, size=22)
                    self.spawn_burst(hx, hy, WHITE, n=14)
                elif p.action_timer <= DUNK_SLAM_FRAMES:
                    # a mão chegou no aro: CRAVA
                    self.execute_dunk_slam()
                    if p.botao:
                        # segurando o botão: a mão fica no aro e o corpo pendura
                        self.dunk_phase = "hang"
                        p.suspended = True
                        p.jump_vel = 0
                        self.hang_offset = p.jump_offset
                    else:
                        self.dunk_phase = None
            else:
                self.dunk_phase = None

        if self.release_grace > 0:
            self.release_grace -= 1

        if self.ball.held and self.holder:
            dono = self.holder
            tx, ty = dono.ball_pos()
            if dono.dribbling or self.dunk_phase is not None:
                self.ball.x, self.ball.y = tx, ty
                if dono.dribbling:
                    self.ball.rotation += 0.14   # gira enquanto quica
            else:
                # quique parou (mirando/carregando): a bola sobe suave até a mão
                # em vez de teleportar do chão pra ela
                self.ball.x += (tx - self.ball.x) * 0.35
                self.ball.y += (ty - self.ball.y) * 0.35

        if getattr(self.ball, "so_na_descida", False) and self.ball.vy > 0:
            # comecou a cair: o aro volta a valer
            self.ball.ignore_rim = False
            self.ball.so_na_descida = False

        if self.started and not self.game_over:
            self.ball.update()
            self.check_scoring()
            self.check_pickup()

            # sem cronômetro: o x1 termina em MATCH_POINTS pontos, e não no tempo.
            # (o relógio antigo ainda encerrava a partida no meio do jogo)

        self.particles = [p for p in self.particles if p.alive]
        for p in self.particles:
            p.update()
        self.texts = [t for t in self.texts if t.alive]
        for t in self.texts:
            t.update()

        if self.shake > 0:
            self.shake *= 0.85
            if self.shake < 0.3:
                self.shake = 0

    def check_scoring(self):
        b = self.ball
        if b.held:
            return
        prev_y = b.y - b.vy
        crossing = prev_y < RIM_Y <= b.y
        inside = (RIM_LEFT + 10) < b.x < (RIM_RIGHT - 10)
        moving_down = b.vy > 0

        dunk_score = b.scored_this_flight == "DUNK" and b.y >= RIM_Y - 4
        normal_score = (not b.scored_this_flight) and crossing and inside and moving_down

        if dunk_score:
            self.commit_score(3 if False else 2, swish=False, dunk=True)
            b.scored_this_flight = True
            b.ignore_rim = False  # passou pela cesta: física normal de volta
        elif normal_score:
            swish = not b.touched_rim
            three = (b.shot_origin_x is not None and b.shot_origin_x < THREE_POINT_X)
            pts = (3 if three else 2) + (1 if swish else 0)
            self.commit_score(pts, swish=swish, dunk=False)
            b.scored_this_flight = True

        # detectar erro (bateu no chão sem pontuar)
        if (not b.held and b.in_air and not b.scored_this_flight
                and not self.missed_shown and b.y + b.RADIUS >= FLOOR_Y - 1):
            self.combo = 0
            self.marcar(self.shooter, "erro")
            if self.shooter is not None and hasattr(self.shooter, "est"):
                self.shooter.est["seq_atual"] = 0
            self.add_text(b.x, b.y - 30, "ERROU", (200, 200, 210), size=20)
            self.missed_shown = True

    def commit_score(self, pts, swish, dunk):
        de_quem = self.shooter
        if dunk and de_quem.hab == "quebra":
            pts += 1                # QUEBRA-TABELA: a cravada dele vale 3
        if de_quem is self.rival:
            self.rival_score += pts
        else:
            self.score += pts
        self.combo += 1
        self.best_combo = max(self.best_combo, self.combo)
        self.marcar(de_quem, "pontos", pts)
        self.marcar(de_quem, "cesta")
        if dunk:
            self.marcar(de_quem, "cravada")
        # sequência POR JOGADOR: self.combo é global e some com o erro do
        # adversário, o que não diz nada sobre quem estava quente
        self.marcar(de_quem, "seq_atual")
        de_quem.est["seq"] = max(de_quem.est["seq"], de_quem.est["seq_atual"])
        self.carregar_super(de_quem, SUPER_CRAVADA if dunk else SUPER_CESTA)
        # tomar cesta também enche, menos: sem isso quem abre vantagem ativa o
        # modo primeiro e a partida vira bola de neve
        self.carregar_super(self.rival_de(de_quem), SUPER_SOFREU)
        self.missed_shown = True  # evita contar de novo até a próxima bola
        # a rede leva a onda que desce, não a chacoalhada aleatória: a
        # cravada bate mais forte, e a bola que raspou o aro menos que a limpa
        self.net.swish(1.30 if dunk else (1.05 if swish else 0.85))
        if dunk:
            self.net.wiggle(5)       # o aro treme junto na cravada
            SOM.toca("cravada", 1.0)
        SOM.toca("rede", 1.0 if swish else 0.75)
        SOM.toca("torcida_forte" if (dunk or swish) else "torcida",
                 1.0 if dunk else 0.85)
        self.shake = max(self.shake, 10 if dunk else 6)
        color = GOLD if swish or dunk else WHITE
        if dunk:
            nomes = DUNK_NAMES_VOO if de_quem.dunk_voo else DUNK_NAMES
            label = nomes[de_quem.dunk_style]
        else:
            label = "SWISH!" if swish else "CESTA!"
        self.add_text(RIM_LEFT + 30, RIM_Y - 10, f"+{pts} {label}", color, size=30)
        if self.combo > 1:
            self.add_text(RIM_LEFT + 30, RIM_Y + 40, f"COMBO x{self.combo}", ORANGE, size=20)
        self.spawn_burst(RIM_LEFT + 30, RIM_Y, GOLD if swish else WHITE, n=24 if dunk else 16)
        # a torcida vibra mais em enterrada e em bola limpa
        self.crowd.cheer(RIM_CX, 1.35 if dunk else (1.15 if swish else 1.0))
        # marcou: a bola vai pro outro, que precisa limpar antes de atacar
        if self.score >= self.alvo or self.rival_score >= self.alvo:
            self.winner = self.player if self.score > self.rival_score else self.rival
            self.game_over = True
            SOM.toca("apito", 0.9)
            if self.score > self.high_score:
                self.high_score = self.score
                self.new_record = True
                self.save_high_score()
        else:
            self.dar_bola(self.rival_de(de_quem))

    def quebrar_tabela(self):
        """DEMOLIÇÃO: a tabela estilhaça e o aro fica torto até o fim da partida.

        Não há desenho novo pro aro entortado: `rim_edge_y` já recebe a flexão
        e a rede já sai dela, então basta mudar o repouso da mola e os dois
        entortam juntos.
        """
        if self.aro_quebrado:
            # já está quebrada: só o tranco, senão a segunda cravada "quebraria"
            # de novo uma tabela que não existe mais
            self.shake = max(self.shake, 16)
            return
        self.aro_quebrado = True
        self.shake = max(self.shake, 26)
        self.rim_flex_vel += 9.0
        # o vidro cai da tabela, não do aro
        for _ in range(46):
            self.particles.append(Particle(
                BACKBOARD_X + random.uniform(-6, 10),
                BACKBOARD_TOP + random.uniform(0, BACKBOARD_H),
                random.choice(((226, 236, 244), (198, 214, 228), (250, 250, 255))),
                vx=random.uniform(-3.4, 1.2), vy=random.uniform(-4.0, 1.5),
                life=random.randint(26, 58), size=3, gravity=0.34))
        self.add_text(RIM_LEFT - 40, RIM_Y - 40, "DEMOLIÇÃO!", GOLD, size=32)
        SOM.toca("tabela", 1.0)
        SOM.toca("cravada", 1.0)
        self.crowd.cheer(RIM_CX, 1.6)

    def check_pickup(self):
        """Bola solta: quem chegar primeiro pega. Todo ressalto obriga a levar a
        bola pra fora da linha de 3 antes de atacar."""
        if self.release_grace > 0:
            return
        b = self.ball
        if b.held:
            return
        for quem in (self.player, self.rival):
            if quem.suspended or quem.action == "caido":
                continue
            if quem.rect.inflate(22, 22).collidepoint(b.x, b.y):
                # rebote do PRÓPRIO arremesso não precisa limpar — o ataque
                # continua. Só a bola vinda do erro do adversário (ou seja,
                # troca de posse) obriga a sair da linha de 3.
                self.dar_bola(quem, clear=quem is not self.shooter)
                return

    def end_game(self):
        self.game_over = True
        if self.score > self.high_score:
            self.high_score = self.score
            self.new_record = True
            self.save_high_score()

    # ---------------- desenho ----------------
    def draw_hoop(self, surface):
        # poste de sustentação
        pygame.draw.rect(surface, (70, 70, 78), (POLE_X, RIM_Y + 10, 10, HEIGHT - RIM_Y - 10))
        # tabela
        board_rect = pygame.Rect(BACKBOARD_X, BACKBOARD_TOP, 14, BACKBOARD_H)
        pygame.draw.rect(surface, (235, 235, 240), board_rect)
        pygame.draw.rect(surface, (150, 150, 158), board_rect, 2)
        inner = pygame.Rect(BACKBOARD_X - 4, BACKBOARD_TOP + BACKBOARD_H // 2 - 18, 4, 36)
        pygame.draw.rect(surface, RED, inner)
        if self.aro_quebrado:
            # rachaduras fixas (semente própria): sorteadas a cada quadro elas
            # cintilariam, e leriam como chuvisco em vez de vidro trincado
            rng = random.Random(4242)
            topo = BACKBOARD_TOP
            for _ in range(9):
                y0 = topo + rng.uniform(6, BACKBOARD_H - 6)
                pontos = [(BACKBOARD_X + rng.uniform(0, 14), y0)]
                for _ in range(3):
                    px, py = pontos[-1]
                    pontos.append((max(BACKBOARD_X, min(BACKBOARD_X + 14,
                                                        px + rng.uniform(-6, 6))),
                                   py + rng.uniform(-11, 11)))
                pygame.draw.lines(surface, (126, 132, 146), False, pontos, 1)

        # rede (atrás do aro), acompanhando a flexão
        self.net.draw(surface, self.rim_flex)

        # aro — inclina para a frente quando afunda, como um aro de mola
        left_y, right_y = rim_edge_y(self.rim_flex)
        pygame.draw.line(surface, ORANGE, (RIM_LEFT, left_y), (RIM_RIGHT, right_y), 5)
        pygame.draw.circle(surface, ORANGE_DARK, (RIM_LEFT, int(left_y)), 5)
        pygame.draw.circle(surface, ORANGE_DARK, (RIM_RIGHT, int(right_y)), 5)

        if self.aiming:
            self.draw_dunk_hint(surface)

    def draw_dunk_hint(self, surface):
        pass

    # Cores do resultado da soltura. Verde/amarelo/vermelho porque e a leitura
    # que todo mundo ja tem pronta -- nao ha nada a ensinar sobre o que elas
    # significam.
    CORES_MEDIDOR = {"verde": (66, 224, 118), "quase": (244, 196, 72),
                     "fora": (226, 86, 74)}
    ROTULO_MEDIDOR = {"verde": "PERFEITO!", "quase": "QUASE", "fora": "FORA"}

    # O arco vai da esquerda pra direita passando por cima. A posicao 0,5 --
    # o verde -- cai no ALTO, que e pra onde o olho vai sozinho.
    ARCO_A0 = math.radians(158)
    ARCO_A1 = math.radians(22)

    def draw_medidor(self, surface, quem, pos, congelado=None):
        """O medidor de arremesso, em arco sobre a cabeça de `quem`.

        `pos` é onde o marcador está, de 0 a 1, medido ao longo do arco. Em
        arco e não em barra reta por dois motivos: é o formato que o jogador
        reconhece de outros jogos de basquete, e ele fica FORA da linha do
        corpo — a barra reta caía justamente onde a mão do defensor aparece no
        toco, e as duas se sobrepunham no lance mais tenso do jogo.

        A zona verde continua saindo de `zona_verde`, que sai da mesma conta que
        decide o arremesso. Só a forma mudou.
        """
        crescer = 0.0
        if congelado is not None:
            crescer = (congelado[1] / float(MEDIDOR_FLASH)) ** 2
        # o alto do arco fica 10 px acima do crânio. `HEIGHT` é a caixa de
        # colisão (90 px no padrão), não a altura desenhada (126): a diferença
        # entre as duas é a cabeça, e ignorá-la deixava o arco boiando.
        topo_cranio = (BODY_HIP + BODY_TORSO + BODY_NECK + BODY_HEAD_R) * quem.esc
        raio = (34 + 8 * crescer) * (0.88 + 0.12 * quem.esc)
        grossura = 6 + 3 * crescer
        cx = quem.x
        cy = quem.y - quem.jump_offset - (topo_cranio + 10 - raio)
        ri, re_ = raio - grossura, raio
        a0, a1 = self.ARCO_A0, self.ARCO_A1

        def em(t):
            return a0 + (a1 - a0) * max(0.0, min(1.0, t))

        cores = self.CORES_MEDIDOR
        faixa_arco(surface, (12, 14, 22), cx, cy, ri - 1, re_ + 1, a0, a1)

        verde = self.zona_verde(quem)
        quase = verde * SHOT_TOL_QUASE
        faixa_arco(surface, _shade(cores["quase"], 0.82), cx, cy, ri, re_,
                   em(0.5 - quase), em(0.5 + quase))
        faixa_arco(surface, _shade(cores["verde"], 0.92), cx, cy, ri, re_,
                   em(0.5 - verde), em(0.5 + verde))

        if congelado is None:
            # marcador vivo: um risco radial atravessando a espessura do arco
            a = em(pos)
            pygame.draw.line(surface, WHITE,
                             (cx + math.cos(a) * (ri - 3), cy - math.sin(a) * (ri - 3)),
                             (cx + math.cos(a) * (re_ + 3), cy - math.sin(a) * (re_ + 3)), 3)
        else:
            res, frames = congelado
            cor = cores[res]
            if (frames // 3) % 2:
                cor = _lift(cor, 40)
            faixa_arco(surface, _shade(cor, 0.45), cx, cy, ri, re_, a0, a1)
            a = em(pos)
            pygame.draw.line(surface, cor,
                             (cx + math.cos(a) * (ri - 5), cy - math.sin(a) * (ri - 5)),
                             (cx + math.cos(a) * (re_ + 5), cy - math.sin(a) * (re_ + 5)), 4)
            rot = FONT_TINY.render(self.ROTULO_MEDIDOR[res], True, cor)
            surface.blit(rot, (cx - rot.get_width() // 2,
                               cy - raio - rot.get_height() - 4))

    def draw_trajectory_preview(self, surface):
        for quem in (self.player, self.rival):
            # no modo de dois, quem está carregando vê o PRÓPRIO medidor
            if quem.charging and self.ball.held and self.holder is quem:
                self.draw_medidor(surface, quem, self.charge_meter(quem))
        # soltou: o medidor congela na posição da soltura mostrando o resultado
        if self.flash_medidor is not None:
            quem, pos, res, frames = self.flash_medidor
            self.draw_medidor(surface, quem, pos, congelado=(res, frames))
        if self.player.charging or not (self.aiming and self.drag_start
                                        and self.drag_current):
            return
        hx, hy = self.drag_start
        mx, my = self.drag_current
        if math.hypot(hx - mx, hy - my) < 8:
            return
        # a linha do estilingue fica (é o controle do mouse), mas o arco da
        # trajetória não: era ele que entregava o arremesso antes da soltura
        pygame.draw.line(surface, GOLD, (hx, hy), (mx, my), 3)
        pygame.draw.circle(surface, GOLD, (mx, my), 6)

    def draw_hud(self, surface):
        # no fim de partida a HUD não tem função: o placar final já é a
        # manchete da tela. Desenhá-la e cobrir com véu deixava o placar de
        # jogo fantasma atrás do resultado, bem em cima do título.
        if self.game_over:
            self.draw_game_over(surface)
            return
        # placar superior
        panel = pygame.Rect(WIDTH // 2 - 160, 14, 320, 60)
        panel_s = pygame.Surface((panel.w, panel.h), pygame.SRCALPHA)
        pygame.draw.rect(panel_s, (10, 12, 20, 190), panel_s.get_rect(), border_radius=12)
        surface.blit(panel_s, panel)
        pygame.draw.rect(surface, GOLD, panel, 2, border_radius=12)

        # placar do x1: VOCÊ x RIVAL, com a posse destacada
        vc = FONT_MED.render(str(self.score), True, WHITE)
        ri = FONT_MED.render(str(self.rival_score), True, WHITE)
        x_surf = FONT_SMALL.render("x", True, (170, 170, 185))
        surface.blit(vc, (panel.centerx - 40 - vc.get_width(), panel.y + 4))
        surface.blit(x_surf, (panel.centerx - x_surf.get_width() // 2, panel.y + 14))
        surface.blit(ri, (panel.centerx + 40, panel.y + 4))
        # a camisa agora é preta: quem marca a posse é a cor do time
        l1 = FONT_TINY.render(self.player.nome, True,
                              self.player.time_cor if self.holder is self.player
                              else (170, 170, 185))
        l2 = FONT_TINY.render(self.rival.nome, True,
                              self.rival.time_cor if self.holder is self.rival
                              else (170, 170, 185))
        surface.blit(l1, (panel.centerx - 40 - vc.get_width() // 2 - l1.get_width() // 2,
                          panel.y + 40))
        surface.blit(l2, (panel.centerx + 40 + ri.get_width() // 2 - l2.get_width() // 2,
                          panel.y + 40))

        # medidor do MODO, ABAIXO do painel e centrado no nome de cada um.
        # Habilidade que o jogador não vê carregando não existe pra ele.
        for quem, meio in ((self.player, panel.centerx - 40 - vc.get_width() // 2),
                           (self.rival, panel.centerx + 40 + ri.get_width() // 2)):
            self.barra_modo(surface, quem, meio, panel.bottom + 6)

        alvo_surf = FONT_SMALL.render(f"ATÉ {self.alvo}", True, GOLD)
        surface.blit(alvo_surf, (panel.right + 16, panel.y + 8))
        niv_surf = FONT_TINY.render(self.dif["nome"], True, (190, 192, 206))
        surface.blit(niv_surf, (panel.right + 16, panel.y + 34))
        if self.needs_clear and self.holder is self.player:
            aviso = FONT_SMALL.render("LEVE A BOLA PRA FORA DA LINHA DE 3", True, GOLD)
            surface.blit(aviso, (WIDTH // 2 - aviso.get_width() // 2, panel.bottom + 14))

        if not self.started and not self.game_over:
            self.draw_center_message(
                surface, f"X1 ATÉ {self.alvo} PONTOS",
                "COM a bola: segure = arremesso | 2x = enterrada | S + ação = finta e bandeja"
                "     SEM a bola: ação = roubo | W = toco")

        if self.pausado:
            self.draw_pausa(surface)

    def barra_modo(self, surface, quem, meio, y):
        """A barrinha do MODO, centrada em `meio`.

        Cheia, pulsa; ligada, esvazia mostrando o tempo que resta."""
        larg, alt = 66, 6
        x = meio - larg // 2
        pygame.draw.rect(surface, (14, 16, 24), (x, y, larg, alt), border_radius=3)
        if self.super_ativo(quem):
            # ligado: a barra passa a mostrar o tempo que SOBRA
            f = quem.super_frames / float(SUPER_FRAMES)
            cor = GOLD if (self.frame_count // 4) % 2 else (255, 240, 170)
        else:
            f = getattr(quem, "super_carga", 0.0)
            cheio = f >= 1.0
            # cheio pulsa: é o aviso de que dá pra usar agora
            cor = ((GOLD if (self.frame_count // 6) % 2 else (255, 255, 220))
                   if cheio else quem.time_cor)
        if f > 0:
            pygame.draw.rect(surface, cor, (x + 1, y + 1, int((larg - 2) * f), alt - 2),
                             border_radius=3)
        pygame.draw.rect(surface, (96, 98, 116), (x, y, larg, alt), 1, border_radius=3)
        if not self.super_ativo(quem) and getattr(quem, "super_carga", 0.0) >= 1.0:
            tecla = "Q" if quem is self.player else "SH"
            t = FONT_TINY.render(tecla, True, GOLD)
            surface.blit(t, (x + larg + 4, y - 5))

    def draw_center_message(self, surface, title, subtitle):
        s1 = FONT_MED.render(title, True, WHITE)
        s2 = FONT_SMALL.render(subtitle, True, (210, 210, 220))
        surface.blit(s1, (WIDTH // 2 - s1.get_width() // 2, HEIGHT // 2 - 10))
        surface.blit(s2, (WIDTH // 2 - s2.get_width() // 2, HEIGHT // 2 + 30))

    def draw_game_over(self, surface):
        """Fim de partida: quem venceu, por quanto, e COMO.

        A versão antiga dava placar e melhor sequência. Tudo o que a partida
        produziu — arremessos tentados, cravadas, tocos, roubos — passava pelo
        código e não chegava a lugar nenhum. Esta é a única tela em que o
        jogador para e lê; é onde a partida vira história.
        """
        veu = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        veu.fill((6, 7, 16, 240))
        surface.blit(veu, (0, 0))

        venceu_p1 = self.winner is self.player
        perfil = getattr(self.winner, "perfil", None) or ROSTER[0]
        cor = perfil["cam"]

        # ---------------- o vencedor, desenhado ----------------
        painel = pygame.Rect(56, 104, 232, 338)
        fundo = pygame.Surface(painel.size, pygame.SRCALPHA)
        pygame.draw.rect(fundo, (18, 18, 32, 235), fundo.get_rect(), border_radius=12)
        surface.blit(fundo, painel)
        facho = pygame.Surface(painel.size, pygame.SRCALPHA)
        pygame.draw.ellipse(facho, (*cor, 52), (22, 176, painel.w - 44, 140))
        surface.blit(facho, painel)
        pygame.draw.rect(surface, cor, painel, 2, border_radius=12)
        boneco = self.retrato(perfil, alt_px=248)
        surface.blit(boneco, (painel.centerx - boneco.get_width() // 2,
                              painel.bottom - boneco.get_height() - 30))
        nome = FONT_SMALL.render(perfil["nome"], True, WHITE)
        surface.blit(nome, (painel.centerx - nome.get_width() // 2, painel.bottom - 26))

        # ---------------- veredito e placar ----------------
        x0 = 320
        if self.modo == 2:
            texto = "JOGADOR %d VENCEU" % (1 if venceu_p1 else 2)
            cor_tit = (120, 200, 255) if venceu_p1 else (255, 150, 120)
        else:
            texto = "VOCÊ VENCEU" if venceu_p1 else "VOCÊ PERDEU"
            cor_tit = GOLD if venceu_p1 else (214, 206, 210)
        tit = FONT_MED.render(texto, True, cor_tit)
        surface.blit(tit, (x0, 44))

        placar = FONT_BIG.render("%d  x  %d" % (self.score, self.rival_score),
                                 True, WHITE)
        surface.blit(placar, (x0, 84))
        if self.new_record:
            rec = FONT_SMALL.render("NOVO RECORDE", True, GOLD)
            surface.blit(rec, (x0 + placar.get_width() + 26, 118))

        pygame.draw.line(surface, (62, 64, 82), (x0, 176), (WIDTH - 56, 176), 1)

        # ---------------- a ficha da partida ----------------
        col1, col2 = x0 + 330, x0 + 508
        if self.modo == 2:
            n1, n2 = "JOGADOR 1", "JOGADOR 2"
        else:
            n1, n2 = "VOCÊ", self.rival.nome
        for rot, cx, c in ((n1, col1, (150, 200, 250)), (n2, col2, (250, 176, 150))):
            t = FONT_TINY.render(rot, True, c)
            surface.blit(t, (cx - t.get_width() // 2, 190))

        ep, er = self.ficha(self.player), self.ficha(self.rival)

        def tentativas(e):
            return e["cesta"] + e["erro"]

        def aproveita(e):
            t = tentativas(e)
            # sem tentativa nenhuma, "0%" seria uma afirmação falsa sobre a
            # pontaria de alguém que nunca arremessou
            return "%d%%" % round(100.0 * e["cesta"] / t) if t else "—"

        linhas = (
            ("PONTOS", str(self.score), str(self.rival_score)),
            ("ARREMESSOS", "%d/%d" % (ep["cesta"], tentativas(ep)),
             "%d/%d" % (er["cesta"], tentativas(er))),
            ("APROVEITAMENTO", aproveita(ep), aproveita(er)),
            ("CRAVADAS", str(ep["cravada"]), str(er["cravada"])),
            ("TOCOS", str(ep["toco"]), str(er["toco"])),
            ("ROUBOS", str(ep["roubo"]), str(er["roubo"])),
            ("MELHOR SEQUÊNCIA", "x%d" % ep["seq"], "x%d" % er["seq"]),
        )
        for i, (rot, v1, v2) in enumerate(linhas):
            y = 216 + i * 30
            if i % 2 == 0:
                faixa = pygame.Surface((WIDTH - 56 - x0 + 10, 26), pygame.SRCALPHA)
                faixa.fill((255, 255, 255, 10))
                surface.blit(faixa, (x0 - 8, y - 4))
            lb = FONT_SMALL.render(rot, True, (196, 198, 210))
            surface.blit(lb, (x0, y))
            # quem está melhor na linha vem em branco, o outro em cinza
            melhor = self.melhor_na_linha(v1, v2)
            for k, (v, cx) in enumerate(((v1, col1), (v2, col2))):
                c = WHITE if melhor == k else (138, 140, 154)
                t = FONT_SMALL.render(v, True, c)
                surface.blit(t, (cx - t.get_width() // 2, y))

        # ---------------- saídas ----------------
        dica = FONT_SMALL.render("R  revanche        ESC  menu        M  som",
                                 True, (216, 216, 228))
        surface.blit(dica, (WIDTH // 2 - dica.get_width() // 2, 500))
        detalhe = FONT_TINY.render(
            "revanche mantém a mesma dupla, a mesma quadra e a mesma dificuldade",
            True, (124, 126, 140))
        surface.blit(detalhe, (WIDTH // 2 - detalhe.get_width() // 2, 532))

    def ficha(self, quem):
        """A ficha do jogador, ou uma zerada se a partida nem começou."""
        return getattr(quem, "est", None) or dict(
            pontos=0, cesta=0, erro=0, cravada=0, toco=0, roubo=0,
            seq=0, seq_atual=0)

    def melhor_na_linha(self, v1, v2):
        """Qual coluna destacar: 0, 1, ou -1 quando empatam.

        Compara pelo PRIMEIRO número do texto. Por texto, "x9" venceria "x10".
        Juntando todos os dígitos, "5/9" viraria 59 e perderia de "3/12" — e o
        primeiro número é justamente o que interessa comparar nessa linha (as
        cestas feitas)."""
        def n(v):
            d = ""
            for c in v:
                if c.isdigit():
                    d += c
                elif d:
                    break
            return int(d) if d else -1
        a, b = n(v1), n(v2)
        if a == b:
            return -1
        return 0 if a > b else 1

    def draw_pausa(self, surface):
        """Véu de pausa. Deixa a quadra à vista de propósito: a pausa é pra
        levantar da cadeira, não pra esconder a posição da bola."""
        veu = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        veu.fill((6, 6, 16, 176))
        surface.blit(veu, (0, 0))
        tit = FONT_BIG.render("PAUSA", True, GOLD)
        surface.blit(tit, (WIDTH // 2 - tit.get_width() // 2, 212))
        dica = FONT_SMALL.render("P  continua        R  revanche        "
                                 "ESC  menu        M  som        F11  tela cheia",
                                 True, (216, 216, 228))
        surface.blit(dica, (WIDTH // 2 - dica.get_width() // 2, 310))
        if SOM.mudo:
            m = FONT_TINY.render("som desligado", True, (150, 152, 166))
            surface.blit(m, (WIDTH // 2 - m.get_width() // 2, 344))

    def draw(self, surface):
        offset = (0, 0)
        if self.shake > 0.2:
            offset = (random.uniform(-self.shake, self.shake), random.uniform(-self.shake, self.shake))

        if NO_NAVEGADOR:
            # uma blit opaca no lugar de quatro (três delas com alfa): ver
            # `_fundo_composto`. O tremor passa a sacudir o cenário inteiro.
            surface.blit(self._fundo_composto(), offset)
            self.crowd._flashes(surface)
        else:
            surface.blit(self.bg, offset)
            self.crowd.draw(surface)
            if self.grade is not None:
                # a tela do alambrado vem DEPOIS do público: é o que põe a
                # galera atrás da grade em vez de na frente dela
                surface.blit(self.grade, (0, 0))
            if self.quadra["refletor"]:
                surface.blit(HOOP_GLOW, (RIM_CX - HOOP_GLOW.get_width() // 2,
                                         RIM_Y - HOOP_GLOW.get_height() // 2))
        draw_three_point_label(surface)
        self.draw_hoop(surface)

        # quem está mais à esquerda desenha primeiro, pra sobreposição correta
        for quem in sorted((self.player, self.rival), key=lambda q: q.x):
            quem.draw(surface, self.ball.held and self.holder is quem)
        self.ball.draw(surface)

        for p in self.particles:
            p.draw(surface)
        for t in self.texts:
            t.draw(surface)

        self.draw_trajectory_preview(surface)
        # nada de HUD nas telas de menu: o placar ainda nem existe, e ele
        # atravessava o véu
        if self.tela == TELA_INICIO:
            self.draw_inicio(surface)
        elif self.tela == TELA_QUADRA:
            self.draw_quadras(surface)
        elif self.tela == TELA_ESCOLHA:
            self.draw_select(surface)
        else:
            self.draw_hud(surface)
        # por último: os botões ficam por cima de tudo, inclusive do véu das
        # telas de menu
        self.toque.desenhar(surface, self.tela)
        if self.mostrar_fps:
            self.draw_fps(surface)

    def draw_fps(self, surface):
        """Custo do desenho e quadros por segundo, no F3.

        Existe por causa do navegador: lá o jogo roda numa máquina que eu não
        alcanço com cronômetro nenhum, e sem número na tela a conversa sobre
        desempenho vira adivinhação."""
        ms = max(0.01, self.custo_ms)
        txt = "%.1f ms  ~%d fps" % (ms, min(60, int(1000.0 / ms)))
        img = FONT_TINY.render(txt, True, (220, 226, 240))
        cx = WIDTH - img.get_width() - 10
        fundo = pygame.Surface((img.get_width() + 10, img.get_height() + 6),
                               pygame.SRCALPHA)
        fundo.fill((0, 0, 0, 140))
        surface.blit(fundo, (cx - 5, 5))
        surface.blit(img, (cx, 8))


# --------------------------------------------------------------------------
# LOOP PRINCIPAL
# --------------------------------------------------------------------------
# Acima disto o quadro já não cabe em 60 fps (16,7 ms), com folga pro resto
# do laço. É o gatilho do desenho alternado — ver `main`.
LIMITE_PULO_MS = 24.0


def pula_desenho(custo_ms, mirando, navegador=None):
    """O próximo quadro pode sair sem ser desenhado?

    Três guardas, e nenhuma é detalhe:

      - só no navegador, que é onde o orçamento aperta. Numa máquina que
        aguenta, nada disso existe;
      - só acima do custo MEDIDO: alternar o desenho num jogo que já roda a 60
        fps só tiraria metade dos quadros de graça;
      - nunca durante a carga do arremesso. A zona verde da barra pode ter UM
        quadro de largura: desenhar de dois em dois justamente ali
        transformaria a mira, que é o coração do jogo, em sorteio.

    Está aqui fora, e não numa linha do `while` do `main`, porque o laço
    principal é a única parte do jogo que a suíte não roda — e uma regra que
    ninguém consegue interrogar é uma regra que vai apodrecer."""
    if navegador is None:
        navegador = NO_NAVEGADOR
    return bool(navegador) and custo_ms > LIMITE_PULO_MS and not mirando


async def main():
    """Laço principal.

    É assíncrono porque o jogo também roda no navegador (pygbag/WebAssembly),
    e lá um `while` comum seguraria a thread e congelaria a página. O
    `await asyncio.sleep(0)` devolve o controle ao navegador a cada quadro.
    Nativamente o efeito é nenhum: asyncio.run() só executa a corrotina — uma
    fonte de código só para os dois destinos.

    No navegador, se o desenho não couber em 60 fps, a IMAGEM passa a sair de
    dois em dois quadros e a SIMULAÇÃO continua a 60. A diferença não é
    detalhe: desenhar a 30 deixa o jogo com menos quadros; simular a 30 deixa
    ele com outra física — pulo mais curto, bola mais lenta, janela de
    arremesso mais larga. A primeira perda o jogador aceita, a segunda ele
    sente como jogo quebrado."""
    game = Game()
    custo = 0.0          # média móvel do custo do desenho, em ms
    pulou = False
    while not game.encerrar:
        for ev in pygame.event.get():
            game.handle_event(ev)

        keys = game.teclas(pygame.key.get_pressed())
        game.update(keys)

        # a zona verde da barra pode ter UM quadro de largura: desenhar de dois
        # em dois justamente durante a carga transformaria a mira em sorteio
        mirando = game.player.charging or game.rival.charging
        if pulou and not mirando:
            pulou = False
        else:
            t0 = time.perf_counter()
            game.draw(screen)
            pygame.display.flip()
            ms = (time.perf_counter() - t0) * 1000.0
            # média móvel: a troca de quadra e a primeira cesta custam um quadro
            # caro sozinhas, e isso não é motivo pra passar a partida inteira a 30
            custo = ms if custo <= 0.0 else custo + (ms - custo) * 0.12
            pulou = pula_desenho(custo, mirando)
        game.custo_ms = custo
        # o banco de sons nasce aqui, um por quadro, escondido atrás do menu
        SOM.preparar()

        await asyncio.sleep(0)
        clock.tick(FPS)

    pygame.quit()


if __name__ == "__main__":
    asyncio.run(main())
