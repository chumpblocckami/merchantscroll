const CACHE_VERSION = "ms-v3";
const SHELL_CACHE = `${CACHE_VERSION}-shell`;

const SHELL_ASSETS = [
  "/",
  "/index.html",
  "/player.html",
  "/style.css",
  "/manifest.webmanifest",
  "/assets/icons/icon-192.png",
  "/assets/icons/icon-512.png",
  "/assets/icons/icon-512-maskable.png",
  "/assets/icons/apple-touch-icon.png",
  "/assets/favicon.ico",
];

const BYPASS_HOSTS = new Set([
  "cards.scryfall.io",
  "api.scryfall.com",
  "www.clarity.ms",
  "www.googletagmanager.com",
  "www.google-analytics.com",
  "gc.zgo.at",
]);

function isDataPath(pathname) {
  return (
    pathname.startsWith("/assets/pauper/") ||
    pathname.startsWith("/archetypes/") ||
    pathname === "/info.json"
  );
}

function isShellPath(pathname) {
  return (
    pathname === "/" ||
    pathname === "/index.html" ||
    pathname === "/player.html" ||
    pathname === "/style.css" ||
    pathname === "/manifest.webmanifest" ||
    pathname === "/assets/favicon.ico" ||
    pathname.startsWith("/assets/icons/")
  );
}

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches
      .open(SHELL_CACHE)
      .then((cache) =>
        Promise.allSettled(SHELL_ASSETS.map((url) => cache.add(url))),
      )
      .then(() => self.skipWaiting()),
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) =>
        Promise.all(
          keys
            .filter((key) => !key.startsWith(CACHE_VERSION))
            .map((key) => caches.delete(key)),
        ),
      )
      .then(() => self.clients.claim()),
  );
});

async function cacheFirstShell(request) {
  const cached = await caches.match(request);
  if (cached) return cached;

  try {
    const response = await fetch(request);
    if (response.ok) {
      const cache = await caches.open(SHELL_CACHE);
      cache.put(request, response.clone());
    }
    return response;
  } catch {
    return caches.match("/index.html");
  }
}

async function networkFirstData(request) {
  try {
    return await fetch(request);
  } catch {
    return new Response(JSON.stringify({ error: "offline" }), {
      status: 503,
      headers: { "Content-Type": "application/json" },
    });
  }
}

async function navigationHandler(request) {
  try {
    return await fetch(request);
  } catch {
    const pathname = new URL(request.url).pathname;
    if (pathname.includes("player")) {
      return (
        (await caches.match("/player.html")) ||
        (await caches.match("/index.html"))
      );
    }
    return (await caches.match("/index.html")) || (await caches.match("/"));
  }
}

self.addEventListener("fetch", (event) => {
  if (event.request.method !== "GET") return;

  const url = new URL(event.request.url);
  if (url.origin !== self.location.origin) {
    if (BYPASS_HOSTS.has(url.hostname)) return;
    return;
  }

  if (isDataPath(url.pathname)) {
    event.respondWith(networkFirstData(event.request));
    return;
  }

  if (event.request.mode === "navigate") {
    event.respondWith(navigationHandler(event.request));
    return;
  }

  if (isShellPath(url.pathname)) {
    event.respondWith(cacheFirstShell(event.request));
  }
});
