// Apolo Content Script for YouTube (youtube.com)
(function () {
  console.log("[Apolo] Content script loaded on YouTube");
  const APOLO_SERVER = "http://127.0.0.1:4533";

  const SVG_ICONS = {
    download: `<svg viewBox="0 0 24 24"><path d="M19 9h-4V3H9v6H5l7 7 7-7zM5 18v2h14v-2H5z"/></svg>`,
    spinner: `<svg viewBox="0 0 24 24"><path d="M12 4V2A10 10 0 0 0 2 12h2a8 8 0 0 1 8-8z"/></svg>`,
    check: `<svg viewBox="0 0 24 24"><path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/></svg>`,
    error: `<svg viewBox="0 0 24 24"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-2h2v2zm0-4h-2V7h2v6z"/></svg>`
  };

  function cleanMediaUrl(rawUrl, isPlaylist = false) {
    if (!rawUrl) return "";
    try {
      const parsed = new URL(rawUrl.trim());
      const host = parsed.hostname.toLowerCase();

      if (host.includes("youtube.com") || host.includes("youtu.be")) {
        // If it's a playlist action on an explicit playlist page
        if (isPlaylist && parsed.pathname.includes("/playlist")) {
          const list = parsed.searchParams.get("list");
          if (list) return `${parsed.protocol}//${parsed.hostname}/playlist?list=${list}`;
        }

        // Single video: strip list/radio params
        const v = parsed.searchParams.get("v");
        if (v) {
          return `${parsed.protocol}//${parsed.hostname}${parsed.pathname}?v=${v}`;
        }
        if (host.includes("youtu.be")) {
          const id = parsed.pathname.replace(/^\//, "").split("/")[0];
          if (id) return `https://youtu.be/${id}`;
        }
      }
    } catch {
      // Fallback
    }
    return rawUrl.trim();
  }

  function showToast(message, type = "info", duration = 3500) {
    let toast = document.getElementById("apolo-toast-notification");
    if (!toast) {
      toast = document.createElement("div");
      toast.id = "apolo-toast-notification";
      document.body.appendChild(toast);
    }

    const icon = type === "success" ? SVG_ICONS.check : (type === "error" ? SVG_ICONS.error : SVG_ICONS.download);
    toast.className = `apolo-toast apolo-toast-${type} show`;
    toast.innerHTML = `${icon}<span>${message}</span>`;

    setTimeout(() => {
      toast.classList.remove("show");
    }, duration);
  }

  async function triggerApoloDownload(url, buttonEl, isPlaylist = false) {
    const cleanUrl = cleanMediaUrl(url || window.location.href, isPlaylist);
    const originalHTML = buttonEl.innerHTML;
    buttonEl.className = "apolo-btn apolo-loading";
    buttonEl.innerHTML = `${SVG_ICONS.spinner}<span>Enviando...</span>`;

    try {
      const response = await fetch(`${APOLO_SERVER}/api/download`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          url: cleanUrl,
          origin: "youtube"
        })
      });

      if (!response.ok) {
        throw new Error(`HTTP Error ${response.status}`);
      }

      buttonEl.className = "apolo-btn apolo-success";
      buttonEl.innerHTML = `${SVG_ICONS.check}<span>En Apolo</span>`;
      showToast("Descarga iniciada en Apolo", "success");

      setTimeout(() => {
        buttonEl.className = "apolo-btn";
        buttonEl.innerHTML = originalHTML;
      }, 3500);
    } catch (err) {
      console.error("[Apolo] Connection failed:", err);
      buttonEl.className = "apolo-btn apolo-error";
      buttonEl.innerHTML = `${SVG_ICONS.error}<span>Error</span>`;
      showToast("No se pudo conectar con el servidor de Apolo", "error", 5000);

      setTimeout(() => {
        buttonEl.className = "apolo-btn";
        buttonEl.innerHTML = originalHTML;
      }, 3500);
    }
  }

  function injectWatchButton() {
    if (!window.location.pathname.startsWith("/watch")) return;
    if (document.getElementById("apolo-yt-watch-btn")) return;

    const actionsContainer =
      document.querySelector("ytd-watch-metadata #actions #top-level-buttons-computed") ||
      document.querySelector("#actions-inner #top-level-buttons-computed") ||
      document.querySelector("ytd-watch-metadata #actions-inner") ||
      document.querySelector("ytd-menu-renderer #top-level-buttons-computed") ||
      document.querySelector("#top-level-buttons-computed") ||
      document.querySelector("ytd-watch-metadata #actions");

    if (!actionsContainer) return;

    const btn = document.createElement("button");
    btn.id = "apolo-yt-watch-btn";
    btn.className = "apolo-btn";
    btn.setAttribute("type", "button");
    btn.setAttribute("title", "Descargar con Apolo");
    btn.innerHTML = `${SVG_ICONS.download}<span>Apolo</span>`;

    btn.addEventListener("click", (e) => {
      e.preventDefault();
      e.stopPropagation();
      triggerApoloDownload(window.location.href, btn, false);
    });

    actionsContainer.appendChild(btn);
  }

  function injectPlaylistButton() {
    if (!window.location.pathname.startsWith("/playlist")) return;
    if (document.getElementById("apolo-yt-playlist-btn")) return;

    const actionContainer =
      document.querySelector("ytd-playlist-header-renderer .metadata-action-bar") ||
      document.querySelector("ytd-playlist-header-renderer #buttons") ||
      document.querySelector(".page-header-view-model-wiz__page-header-actions") ||
      document.querySelector("ytd-playlist-byline-renderer");

    if (!actionContainer) return;

    const btn = document.createElement("button");
    btn.id = "apolo-yt-playlist-btn";
    btn.className = "apolo-btn";
    btn.setAttribute("type", "button");
    btn.setAttribute("title", "Descargar playlist con Apolo");
    btn.innerHTML = `${SVG_ICONS.download}<span>Descargar Playlist</span>`;

    btn.addEventListener("click", (e) => {
      e.preventDefault();
      e.stopPropagation();
      triggerApoloDownload(window.location.href, btn, true);
    });

    actionContainer.appendChild(btn);
  }

  function tryInject() {
    injectWatchButton();
    injectPlaylistButton();
  }

  tryInject();
  setInterval(tryInject, 1500);

  window.addEventListener("yt-navigate-finish", () => {
    setTimeout(tryInject, 300);
    setTimeout(tryInject, 1000);
  });
  window.addEventListener("spfdone", () => {
    setTimeout(tryInject, 300);
  });

  const observer = new MutationObserver(() => {
    tryInject();
  });

  observer.observe(document.body, {
    childList: true,
    subtree: true
  });
})();
