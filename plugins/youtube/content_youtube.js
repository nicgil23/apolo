// Apolo Content Script for YouTube (youtube.com)
(function () {
  console.log("[Apolo] Content script loaded on YouTube");
  const APOLO_SERVER = "http://127.0.0.1:4533";

  const SVG_ICONS = {
    download: `<svg viewBox="0 0 24 24"><path d="M17 18v2H7v-2h10ZM12 4.5v8.67l3.3-3.3 1.4 1.4-5.7 5.7-5.7-5.7 1.4-1.4 3.3 3.3V4.5h2Z"/></svg>`,
    spinner: `<svg viewBox="0 0 24 24" class="apolo-spin"><circle cx="12" cy="12" r="9" stroke="currentColor" stroke-width="2.5" stroke-dasharray="40" stroke-linecap="round" fill="none"/></svg>`,
    check: `<svg viewBox="0 0 24 24"><path d="M9.55 18 3.85 12.3l1.42-1.42 4.28 4.3 9.3-9.3 1.42 1.42z"/></svg>`,
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

  function getPageTitle(isPlaylist = false) {
    try {
      if (isPlaylist) {
        const plTitle = document.querySelector("ytd-playlist-header-renderer .title, yt-dynamic-sizing-formatted-string.ytd-playlist-header-renderer, .page-header-view-model-wiz__title span, #container h1");
        if (plTitle && plTitle.textContent.trim()) {
          return plTitle.textContent.trim();
        }
      } else {
        const watchTitle = document.querySelector("ytd-watch-metadata #title h1, h1.ytd-watch-metadata, #container > h1 > yt-formatted-string");
        if (watchTitle && watchTitle.textContent.trim()) {
          return watchTitle.textContent.trim();
        }
      }
    } catch {}
    return (document.title || "").replace(/ - YouTube$/, "").trim();
  }

  async function triggerApoloDownload(url, buttonEl, isPlaylist = false) {
    const cleanUrl = cleanMediaUrl(url || window.location.href, isPlaylist);
    const suggestedTitle = getPageTitle(isPlaylist);
    const originalHTML = buttonEl.innerHTML;
    buttonEl.className = "apolo-btn apolo-loading";
    buttonEl.innerHTML = `${SVG_ICONS.spinner}<span>Enviando...</span>`;

    try {
      const response = await fetch(`${APOLO_SERVER}/api/download`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          url: cleanUrl,
          origin: "youtube",
          title: suggestedTitle
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

  function syncButtonHeight(btn, referenceEl) {
    if (!referenceEl) return;
    const rect = referenceEl.getBoundingClientRect();
    if (rect.height > 20) {
      btn.style.height = `${Math.round(rect.height)}px`;
      btn.style.minHeight = `${Math.round(rect.height)}px`;
      btn.style.borderRadius = `${Math.round(rect.height / 2)}px`;
    }
  }

  function injectWatchButton() {
    if (!window.location.pathname.startsWith("/watch")) return;
    
    const actionsContainer =
      document.querySelector("ytd-watch-metadata #actions #top-level-buttons-computed") ||
      document.querySelector("#actions-inner #top-level-buttons-computed") ||
      document.querySelector("ytd-watch-metadata #actions-inner") ||
      document.querySelector("ytd-menu-renderer #top-level-buttons-computed") ||
      document.querySelector("#top-level-buttons-computed") ||
      document.querySelector("ytd-watch-metadata #actions");

    if (!actionsContainer) return;

    let btn = document.getElementById("apolo-yt-watch-btn");
    const likeBtn = actionsContainer.querySelector("segmented-like-dislike-button-view-model, ytd-segmented-like-dislike-button-renderer, ytd-toggle-button-renderer");

    if (btn) {
      syncButtonHeight(btn, likeBtn);
      return;
    }

    btn = document.createElement("button");
    btn.id = "apolo-yt-watch-btn";
    btn.className = "apolo-btn yt-spec-button-shape-next yt-spec-button-shape-next--tonal yt-spec-button-shape-next--mono yt-spec-button-shape-next--size-m yt-spec-button-shape-next--icon-leading";
    btn.setAttribute("type", "button");
    btn.setAttribute("title", "Descargar con Apolo");
    btn.innerHTML = `${SVG_ICONS.download}<span>Apolo</span>`;

    btn.addEventListener("click", (e) => {
      e.preventDefault();
      e.stopPropagation();
      triggerApoloDownload(window.location.href, btn, false);
    });

    // Place it naturally after the segmented like/dislike button
    if (likeBtn && likeBtn.nextSibling) {
      actionsContainer.insertBefore(btn, likeBtn.nextSibling);
    } else {
      actionsContainer.appendChild(btn);
    }

    syncButtonHeight(btn, likeBtn);
  }

  function injectPlaylistButton() {
    if (!window.location.pathname.startsWith("/playlist")) return;
    
    const actionContainer =
      document.querySelector("ytd-playlist-header-renderer .metadata-action-bar") ||
      document.querySelector("ytd-playlist-header-renderer #buttons") ||
      document.querySelector(".page-header-view-model-wiz__page-header-actions") ||
      document.querySelector("ytd-playlist-byline-renderer");

    if (!actionContainer) return;

    let btn = document.getElementById("apolo-yt-playlist-btn");
    const refBtn = actionContainer.querySelector("yt-button-shape, ytd-button-renderer, button");

    if (btn) {
      syncButtonHeight(btn, refBtn);
      return;
    }

    btn = document.createElement("button");
    btn.id = "apolo-yt-playlist-btn";
    btn.className = "apolo-btn yt-spec-button-shape-next yt-spec-button-shape-next--tonal yt-spec-button-shape-next--mono yt-spec-button-shape-next--size-m yt-spec-button-shape-next--icon-leading";
    btn.setAttribute("type", "button");
    btn.setAttribute("title", "Descargar playlist con Apolo");
    btn.innerHTML = `${SVG_ICONS.download}<span>Apolo</span>`;

    btn.addEventListener("click", (e) => {
      e.preventDefault();
      e.stopPropagation();
      triggerApoloDownload(window.location.href, btn, true);
    });

    actionContainer.appendChild(btn);
    syncButtonHeight(btn, refBtn);
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
