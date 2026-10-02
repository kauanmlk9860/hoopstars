/* Guarda o que e NOSSO pra abertura seguinte ser rapida.
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
const COFRE = "hoopstars-103685";
const NOSSOS = ["./", "index.html", "browserfs.min.js", "manifest.json", "icone-192.png", "icone-512.png", "hoopstars_web.apk", "hoopstars_web.tar.gz", "favicon.png"];

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
