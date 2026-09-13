// Apolo Content Script for YouTube Music (music.youtube.com)
(function () {
  console.log("[Apolo] Content script loaded on YouTube Music");
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
        // If it's explicitly a playlist download action on a playlist/browse page
        if (isPlaylist && (parsed.pathname.includes("/playlist") || parsed.pathname.includes("/browse"))) {
          const list = parsed.searchParams.get("list");
          if (list) return `${parsed.protocol}//${parsed.hostname}/playlist?list=${list}`;
        }

        // Single track: ALWAYS strip list/radio mix parameters (list=RD...)
        const v = parsed.searchParams.get("v");
        if (v) {
          return `${parsed.protocol}//${parsed.hostname}/watch?v=${v}`;
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

  async function triggerApoloDownload(url, buttonEl, isBar = false, isPlaylist = false) {
    const cleanUrl = cleanMediaUrl(url || window.location.href, isPlaylist);
    const originalHTML = buttonEl.innerHTML;
    buttonEl.classList.add("apolo-loading");
    if (!isBar) {
      buttonEl.innerHTML = `${SVG_ICONS.spinner}<span>Enviando...</span>`;
    } else {
      buttonEl.innerHTML = SVG_ICONS.spinner;
    }

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

      buttonEl.classList.remove("apolo-loading");
      buttonEl.classList.add("apolo-success");
      if (!isBar) {
        buttonEl.innerHTML = `${SVG_ICONS.check}<span>En Apolo</span>`;
      } else {
        buttonEl.innerHTML = SVG_ICONS.check;
      }
      showToast("Descarga iniciada en Apolo", "success");

      setTimeout(() => {
        buttonEl.classList.remove("apolo-success");
        buttonEl.innerHTML = originalHTML;
      }, 3500);
    } catch (err) {
      console.error("[Apolo YTMusic] Connection failed:", err);
      buttonEl.classList.remove("apolo-loading");
      buttonEl.classList.add("apolo-error");
      if (!isBar) {
        buttonEl.innerHTML = `${SVG_ICONS.error}<span>Error</span>`;
      } else {
        buttonEl.innerHTML = SVG_ICONS.error;
      }
      showToast("No se pudo conectar con el servidor de Apolo", "error", 5000);

      setTimeout(() => {
        buttonEl.classList.remove("apolo-error");
        buttonEl.innerHTML = originalHTML;
      }, 3500);
    }
  }

  function injectPlayerBarButton() {
    if (document.getElementById("apolo-ytmusic-bar-btn")) return;

    const playerBarRight =
      document.querySelector("ytmusic-player-bar .middle-controls") ||
      document.querySelector("ytmusic-player-bar .right-controls-buttons") ||
      document.querySelector("#right-controls-buttons") ||
      document.querySelector("ytmusic-player-bar");

    if (!playerBarRight) return;

    const btn = document.createElement("button");
    btn.id = "apolo-ytmusic-bar-btn";
    btn.className = "apolo-ytmusic-bar-btn";
    btn.setAttribute("type", "button");
    btn.setAttribute("title", "Descargar canción con Apolo");
    btn.innerHTML = SVG_ICONS.download;

    btn.addEventListener("click", (e) => {
      e.preventDefault();
      e.stopPropagation();

      const currentTrackLink = document.querySelector("ytmusic-player-bar .title.ytmusic-player-bar a")?.href;
      const targetUrl = currentTrackLink || window.location.href;

      // Always download single track (never radio mix playlist)
      triggerApoloDownload(targetUrl, btn, true, false);
    });

    playerBarRight.appendChild(btn);
  }

  function injectHeaderButton() {
    const isAlbumOrPlaylist =
      window.location.pathname.startsWith("/playlist") ||
      window.location.pathname.startsWith("/browse");

    if (!isAlbumOrPlaylist) return;
    if (document.getElementById("apolo-ytmusic-header-btn")) return;

    const actionContainer =
      document.querySelector("ytmusic-header-renderer .detail-page-action-bar") ||
      document.querySelector("ytmusic-responsive-header-renderer .actions") ||
      document.querySelector("ytmusic-responsive-header-renderer #actions") ||
      document.querySelector("ytmusic-detail-header-renderer .actions");

    if (!actionContainer) return;

    const btn = document.createElement("button");
    btn.id = "apolo-ytmusic-header-btn";
    btn.className = "apolo-btn";
    btn.setAttribute("type", "button");
    btn.setAttribute("title", "Descargar con Apolo");
    btn.innerHTML = `${SVG_ICONS.download}<span>Descargar con Apolo</span>`;

    btn.addEventListener("click", (e) => {
      e.preventDefault();
      e.stopPropagation();
      triggerApoloDownload(window.location.href, btn, false, true);
    });

    actionContainer.appendChild(btn);
  }

  function tryInject() {
    injectPlayerBarButton();
    injectHeaderButton();
  }

  tryInject();
  setInterval(tryInject, 1500);

  window.addEventListener("yt-page-data-updated", () => {
    setTimeout(tryInject, 400);
  });
  window.addEventListener("yt-navigate-finish", () => {
    setTimeout(tryInject, 400);
  });

  const observer = new MutationObserver(() => {
    tryInject();
  });

  observer.observe(document.body, {
    childList: true,
    subtree: true
  });
})();
