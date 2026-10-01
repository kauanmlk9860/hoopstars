# Hoop Stars

Jogo de basquete 1 contra 1, em Python e pygame, num arquivo só.

**▶ [Jogar no navegador](https://kauanmlk9860.github.io/hoopstars/)** — funciona
em PC, Chromebook, celular e tablet. Nada para instalar.

No **Chromebook** (ou em qualquer Chrome) dá para instalar como aplicativo: abra
o link e clique no ícone de instalar na barra de endereço, ou menu ⋮ →
*Transmitir, salvar e compartilhar* → *Instalar página como aplicativo*. Ele
ganha ícone na prateleira e abre em janela própria, em tela cheia, sem barra de
endereço.

![Python](https://img.shields.io/badge/Python-3.12-blue)
![pygame](https://img.shields.io/badge/pygame-2.6-green)
![WebAssembly](https://img.shields.io/badge/roda%20no-navegador-orange)

---

## O que tem

**Doze jogadores, cada um diferente de verdade.** Altura, peso, envergadura e
largura de ombro saem do perfil e alimentam o desenho *e* a física — o braço
mais comprido do Pippen não é enfeite, ele alcança mais longe no roubo e precisa
saltar menos para cravar. Cada um tem drible, gesto de arremesso, cravada
assinada e um traço próprio.

**Medidor de arremesso que não mente.** Segure a ação e um arco aparece sobre a
cabeça. Soltar no verde é cesta — e a zona verde sai da *mesma conta* que decide
se a bola entra, então ela não tem como divergir do jogo. Ela encolhe com a
distância e com o defensor em cima: um pivô chutando de três não tem zona verde
nenhuma, e é assim que a barra avisa que dali não existe arremesso garantido.

**MODO.** Um medidor enche jogando (cesta, roubo, toco — e um pouco quando você
*leva* cesta, para quem está perdendo ter chance de reagir). Cheio, ele liga o
traço do jogador no exagero por alguns segundos. O do Shaq arrebenta a tabela, e
o aro fica torto até o fim da partida.

**Três quadras** com o público se adaptando ao lugar: arquibancada cheia na
arena, galera em pé atrás do alambrado na quadra de rua.

**Dois jogadores** no mesmo teclado, uniforme do time ou moletom, partida até 7,
11, 15 ou 21 pontos, três níveis de dificuldade.

**Som** sintetizado no próprio código — nenhum arquivo de áudio no projeto. O
ferro do aro usa parciais inarmônicas (438, 772, 1245 Hz) porque parcial
harmônica sairia como nota de instrumento, não como metal.

## Controles

|                     | Jogador 1 | Jogador 2   |
| ------------------- | --------- | ----------- |
| mover               | `A` `D`   | `←` `→`     |
| pular / dar toco    | `W`       | `↑`         |
| ação                | `ESPAÇO`  | `ENTER`     |
| modificador         | `S`       | `↓`         |
| MODO                | `Q`       | `SHIFT` dir |

**Com a bola:** segure a ação para arremessar · 2× ação perto do aro para
enterrar · modificador + ação para finta (longe) ou bandeja (perto) · 2× a mesma
direção para arrancar.

**Sem a bola:** cima dá toco · 1× ação é bote de roubo.

`F11` tela cheia · `F3` custo do quadro · `P` pausa · `M` som · `R` revanche · `ESC` volta.

No celular os botões aparecem na tela; eles somem sozinhos assim que você
apertar uma tecla.

## Rodar local

```bash
pip install pygame
python hoopstars.py
```

## Publicar a versão web

```bash
pygbag --build --ume_block 0 --template default.tmpl hoopstars_web
python ferramentas/prepara_web.py hoopstars_web/build/web
```

O segundo passo não é opcional e precisa rodar **depois de cada build**: o
pygbag regenera o `index.html` toda vez, e é nele que estão o conserto do
`browserfs.min.js` (o CDN dele aponta para um arquivo que dá 404), o service
worker próprio (o que vinha era de outro domínio, o que o navegador recusa) e o
manifesto que faz o Chrome oferecer "Instalar". O ícone é desenhado com a arte
do próprio jogo — a mesma função que desenha a bola em quadra.

## Como foi feito

Um arquivo, ~6.600 linhas, sem imagens nem sons externos: personagens, quadra,
público e efeitos são todos desenhados por código, e o áudio é sintetizado na
abertura. Isso é o que permite o mesmo arquivo virar executável, página web e
jogo de celular sem nenhuma pasta de recursos junto.

A simulação anda pelo **relógio**, não por quadro desenhado: um passo é sempre
1/60 de segundo e o laço simula quantos couberem no tempo que passou de verdade.
Num aparelho fraco isso é a diferença entre um jogo com menos quadros e um jogo
em câmera lenta — pulo durando três vezes mais, bola subindo devagar. O primeiro
o jogador perdoa; o segundo ele sente como jogo quebrado.

No navegador o custo é por *chamada* ao pygame, não por pixel: cada uma atravessa
a ponte Python→WebAssembly. Por isso o que roda lá guarda desenho em vez de
baixar resolução — a torcida parada é uma imagem só, a rede imóvel reaproveita o
próprio desenho, e os bonecos viram camadas recoladas a cada quadro na posição
atual. São 1189 chamadas por quadro na primeira versão web contra ~110 hoje.

O projeto tem uma suíte de 18 testes de regressão que mede o jogo em vez de
inspecionar o código — taxas de acerto por distância e por jogador, partidas
completas contra a IA, custo por quadro, alcance da mão no aro, e o laço
principal rodando contra o relógio de parede. Foi ela que pegou, por exemplo,
que a habilidade do Curry tinha parado de valer depois de uma mudança na conta
do arremesso.

---

Projeto de fã, sem fins comerciais e sem qualquer vínculo com a NBA ou com os
jogadores citados.
