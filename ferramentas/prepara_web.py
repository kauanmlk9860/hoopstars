# -*- coding: utf-8 -*-
"""Deixa o build do pygbag publicavel: conserta o que ele erra e vira app.

Roda DEPOIS de cada `pygbag --build`, porque o `index.html` e gerado toda vez e
tudo o que se escreve nele se perde no build seguinte.

Faz quatro coisas:

1. BROWSERFS. O index gerado carrega
       https://pygame-web.github.io/cdn/0.9.3//browserfs.min.js
   -- com barra dupla, e o arquivo nao esta la: da 404. Como entra por
   `<script src>`, a falha e dura e o jogo nao sobe. O arquivo existe em
   `archives/0.9/` e e BAIXADO pra junto do jogo: um link de portfolio que
   depende de um CDN de terceiro para de funcionar no dia em que o terceiro
   reorganiza as pastas -- que foi exatamente o que aconteceu.

2. SERVICE WORKER. O index gerado faz
       navigator.serviceWorker.register("https://pygame-web.github.io/.../pygbag0.9.3.js")
   e isso esta errado em duas frentes: o arquivo da 404, e service worker tem
   que ser do MESMO dominio -- o navegador recusa de outro dominio por
   principio. Ou seja, hoje nao existe service worker nenhum, so um erro no
   console. Entra um nosso, local, que guarda o jogo pra segunda abertura ser
   instantanea e pra ele abrir sem rede.

3. MANIFESTO. Sem ele o Chrome nao oferece "Instalar". Com ele o jogo vira
   aplicativo de verdade no Chromebook: icone na prateleira, janela propria
   sem barra de endereco, tela cheia deitada.

4. TITULO. O pygbag poe o nome da PASTA ("hoopstars_web"), que e o que
   apareceria na aba, no atalho e embaixo do icone.

O icone e desenhado com a arte do proprio jogo -- a mesma funcao que desenha a
bola em quadra --, pra ele nao ser um desenho avulso que envelhece sozinho.
"""
import io
import json
import os
import sys
import importlib.util
import urllib.request

FONTE_BFS = "https://pygame-web.github.io/archives/0.9/browserfs.min.js"
QUEBRADO = "https://pygame-web.github.io/cdn/0.9.3//browserfs.min.js"
QUEBRADO2 = "https://pygame-web.github.io/cdn/0.9.3/browserfs.min.js"
JOGO = r"c:\Users\kauan.rodrigues\Downloads\hoopstars (1).py"

NOME = "Hoop Stars"
TEMA = "#1a1430"        # o roxo do fundo da quadra
FUNDO = "#0f0b1e"

SW = """/* Guarda o que e NOSSO pra abertura seguinte ser rapida.
 *
 * O pygbag registrava um service worker de OUTRO dominio, o que o navegador
 * recusa por principio -- e o arquivo ainda por cima dava 404. Ou seja, nao
 * havia service worker nenhum, so um erro no console. Este e local, e e
 * tambem o que faz o Chrome oferecer "Instalar".
 *
 * O que entra no cofre e o que mora aqui: a pagina, o pacote do jogo, o
 * manifesto e os icones. O interpretador Python -- 13 MB de WebAssembly --
 * vem do CDN do pygbag e NAO entra: resposta de outro dominio chega opaca, e
 * guardar opaco e guardar sem saber se e o arquivo ou uma pagina de erro.
 * Melhor nao guardar do que servir erro pra sempre.
 *
 * Entao isto nao e jogo offline de verdade: sem rede, o navegador ainda
 * precisa ter o interpretador no cache normal dele. Offline garantido so
 * trazendo os 13 MB pra ca, que e outra conversa.
 */
const COFRE = "hoopstars-%(versao)s";
const NOSSOS = %(arquivos)s;

self.addEventListener("install", (ev) => {
  ev.waitUntil(caches.open(COFRE).then((c) => c.addAll(NOSSOS))
               .then(() => self.skipWaiting()));
});

self.addEventListener("activate", (ev) => {
  // some com os cofres de versoes antigas, senao cada publicacao deixa um
  // jogo velho inteiro ocupando disco do jogador pra sempre
  ev.waitUntil(caches.keys().then((nomes) => Promise.all(
    nomes.filter((n) => n.startsWith("hoopstars-") && n !== COFRE)
         .map((n) => caches.delete(n))
  )).then(() => self.clients.claim()));
});

self.addEventListener("fetch", (ev) => {
  // cache.put so aceita GET, e um POST aqui derrubaria o fetch inteiro
  if (ev.request.method !== "GET") return;
  const url = new URL(ev.request.url);
  if (url.origin !== self.location.origin) return;   // CDN: deixa passar
  ev.respondWith(
    // rede primeiro, cofre como rede de seguranca: assim quem abre online
    // sempre pega a versao nova, e quem esta sem rede ainda joga
    fetch(ev.request).then((r) => {
      if (r && r.ok) {
        const copia = r.clone();
        caches.open(COFRE).then((c) => c.put(ev.request, copia));
      }
      return r;
    }).catch(() => caches.match(ev.request))
  );
});
"""

REGISTRO = """
    // service worker NOSSO, deste mesmo endereço. O que o pygbag registrava
    // aqui era um arquivo de outro domínio (que o navegador recusa) e que
    // ainda por cima dava 404 — ou seja, não havia service worker nenhum.
    if (navigator.serviceWorker)
        navigator.serviceWorker.register("sw.js")
"""


def carrega_jogo():
    spec = importlib.util.spec_from_file_location("hoopicone", JOGO)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["hoopicone"] = mod
    spec.loader.exec_module(mod)
    return mod


def desenha_icone(h, lado):
    """O ícone, com a arte do próprio jogo.

    A bola sai da mesma função que a desenha em quadra, então o dia em que o
    couro mudar de cor o ícone muda junto — em vez de virar um desenho avulso
    que ninguém lembra de atualizar.

    Desenhada no TAMANHO do ícone, não ampliada: a bola em quadra tem 30 px, e
    esticar isso pra 512 dá uma mancha borrada. A função aceita o raio pelo
    `Ball.RADIUS`, então basta pedir o raio grande — a arte é vetorial o
    caminho inteiro, o único motivo de ela ser pequena é a quadra."""
    import pygame
    icone = pygame.Surface((lado, lado), pygame.SRCALPHA)
    # fundo arredondado na cor da quadra: no Chromebook o ícone aparece sobre
    # fundo claro e sobre fundo escuro, e um PNG transparente some num dos dois
    raio = int(lado * 0.22)
    pygame.draw.rect(icone, (26, 20, 48), (0, 0, lado, lado), border_radius=raio)

    # o aro visto de frente: é o que diz "basquete" antes mesmo de o olho achar
    # a bola
    aro_y = int(lado * 0.34)
    larg = int(lado * 0.62)
    pygame.draw.ellipse(icone, (236, 120, 40),
                        (lado // 2 - larg // 2, aro_y - int(lado * 0.05),
                         larg, int(lado * 0.10)), max(3, int(lado * 0.035)))

    # a bola, desenhada no tamanho certo em vez de ampliada
    r = int(lado * 0.21)
    h.Ball.RADIUS = r
    bola = h._build_ball_surface(0.6)

    # recortada no círculo dela: o brilho especular da arte passa um fio de
    # fora da silhueta, o que nos 30 px da quadra não se vê e em 512 vira uma
    # mancha cinza no canto de cima. Recortar é melhor que mexer na arte — o
    # problema não é dela, é de usá-la oito vezes maior do que ela existe pra ser.
    meio = bola.get_width() // 2
    molde = pygame.Surface(bola.get_size(), pygame.SRCALPHA)
    pygame.draw.circle(molde, (255, 255, 255, 255), (meio, meio), r)
    bola = bola.copy()
    bola.blit(molde, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)

    # encostando no aro por dentro: bola e aro separados viram dois desenhos
    # soltos, sobrepostos viram uma cesta
    icone.blit(bola, (lado // 2 - meio, aro_y - int(r * 0.30)))
    return icone


def emenda(html, velho, novo, nome):
    """Troca `velho` por `novo`, e aceita que a troca já tenha sido feita.

    Este script roda depois de cada build, mas também roda de novo quando eu
    estou mexendo nele — e na segunda passada o `velho` já não existe. Sem
    isto, a segunda passada quebra com "o registro mudou de forma", que é a
    mensagem de um problema de VERDADE (o pygbag ter mudado o template) sendo
    gritada por um não-problema. Alarme que toca sozinho é alarme que se
    aprende a ignorar.

    O que não se aceita é nenhum dos dois estar lá: aí o template mudou mesmo,
    e seguir em frente publicaria uma página sem o conserto."""
    if velho in html:
        return html.replace(velho, novo)
    if novo in html:
        print("  (%s: já estava feito)" % nome)
        return html
    raise AssertionError(
        "%s: não achei nem a forma antiga nem a nova no index.html — "
        "o template do pygbag mudou e este script precisa ser revisto" % nome)


def prepara(pasta):
    idx = os.path.join(pasta, "index.html")
    if not os.path.exists(idx):
        print("nao achei index.html em", pasta)
        return False

    # ---------------------------------------------------------- 1. browserfs
    destino = os.path.join(pasta, "browserfs.min.js")
    if not os.path.exists(destino):
        print("baixando browserfs.min.js")
        dados = urllib.request.urlopen(FONTE_BFS, timeout=60).read()
        assert len(dados) > 100000, "arquivo pequeno demais: %d bytes" % len(dados)
        open(destino, "wb").write(dados)
    html = io.open(idx, encoding="utf-8").read()
    n = html.count(QUEBRADO) + html.count(QUEBRADO2)
    html = html.replace(QUEBRADO, "browserfs.min.js")
    html = html.replace(QUEBRADO2, "browserfs.min.js")
    print("browserfs: %d referência(s) apontadas pro arquivo local" % n)

    # ------------------------------------------------------------- 2. ícones
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
    import pygame
    h = carrega_jogo()
    for lado in (192, 512):
        pygame.image.save(desenha_icone(h, lado),
                          os.path.join(pasta, "icone-%d.png" % lado))
    print("ícones: icone-192.png, icone-512.png")

    # --------------------------------------------------------- 3. manifesto
    manifesto = {
        "name": NOME,
        "short_name": NOME,
        "description": "Basquete 1 contra 1, dois jogadores no mesmo teclado.",
        # tudo relativo: o jogo mora num subcaminho no GitHub Pages e dentro de
        # um iframe no itch.io, e caminho absoluto quebraria nos dois
        "start_url": "./",
        "scope": "./",
        "display": "fullscreen",
        "display_override": ["fullscreen", "standalone"],
        "orientation": "landscape",
        "background_color": FUNDO,
        "theme_color": TEMA,
        "icons": [
            {"src": "icone-192.png", "sizes": "192x192", "type": "image/png",
             "purpose": "any"},
            {"src": "icone-512.png", "sizes": "512x512", "type": "image/png",
             "purpose": "any"},
            {"src": "icone-512.png", "sizes": "512x512", "type": "image/png",
             "purpose": "maskable"},
        ],
    }
    io.open(os.path.join(pasta, "manifest.json"), "w", encoding="utf-8").write(
        json.dumps(manifesto, indent=2, ensure_ascii=False) + "\n")
    print("manifesto: manifest.json")

    # ---------------------------------------------------- 4. service worker
    nossos = ["./", "index.html", "browserfs.min.js", "manifest.json",
              "icone-192.png", "icone-512.png"]
    for extra in ("hoopstars_web.apk", "hoopstars_web.tar.gz", "favicon.png"):
        if os.path.exists(os.path.join(pasta, extra)):
            nossos.append(extra)
    # a versão sai do tamanho do pacote do jogo: muda quando o jogo muda, e é
    # isso que faz o cofre antigo ser jogado fora na publicação seguinte
    apk = os.path.join(pasta, "hoopstars_web.apk")
    versao = str(os.path.getsize(apk)) if os.path.exists(apk) else "1"
    io.open(os.path.join(pasta, "sw.js"), "w", encoding="utf-8").write(
        SW % {"versao": versao, "arquivos": json.dumps(nossos)})
    print("service worker: sw.js (cofre hoopstars-%s)" % versao)

    # ------------------------------------------------------- 5. o index.html
    velho_sw = ('        if (navigator.serviceWorker)\n'
                '            navigator.serviceWorker.register('
                '"https://pygame-web.github.io/cdn/0.9.3/pygbag0.9.3.js")')
    html = emenda(html, velho_sw, REGISTRO.rstrip(), "service worker")

    velho_titulo = "<title>hoopstars_web</title>"
    novo_titulo = (
        "<title>%s</title>\n"
        '    <link rel="manifest" href="manifest.json">\n'
        '    <meta name="theme-color" content="%s">\n'
        '    <meta name="mobile-web-app-capable" content="yes">\n'
        '    <link rel="apple-touch-icon" href="icone-192.png">' % (NOME, TEMA))
    html = emenda(html, velho_titulo, novo_titulo, "título e manifesto")

    io.open(idx, "w", encoding="utf-8").write(html)
    print("index.html: título, manifesto e service worker no lugar")
    return True


if __name__ == "__main__":
    pasta = sys.argv[1] if len(sys.argv) > 1 else (
        r"c:\Users\kauan.rodrigues\Downloads\hoopstars_web\build\web")
    sys.exit(0 if prepara(pasta) else 1)
