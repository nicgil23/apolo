const APOLO_SERVER = "http://127.0.0.1:4533";

const ICONS = {
  spinner: `<svg viewBox="0 0 24 24" class="task-icon downloading"><circle cx="12" cy="12" r="9" stroke="currentColor" stroke-width="2.5" stroke-dasharray="40" stroke-linecap="round" fill="none"/></svg>`,
  retrying: `<svg viewBox="0 0 24 24" class="task-icon retrying"><path d="M12 5V1L7 6l5 5V7c3.31 0 6 2.69 6 6 0 1.01-.25 1.97-.7 2.8l1.46 1.46A7.93 7.93 0 0 0 20 13c0-4.42-3.58-8-8-8zm-6 8c0-1.01.25-1.97.7-2.8L5.24 8.74A7.93 7.93 0 0 0 4 13c0 4.42 3.58 8 8 8v4l5-5-5-5v4c-3.31 0-6-2.69-6-6z"/></svg>`,
  playlist: `<svg viewBox="0 0 24 24" class="task-icon"><path d="M15 6H3v2h12V6zm0 4H3v2h12v-2zM3 16h8v-2H3v2zM17 6v8.18c-.31-.11-.65-.18-1-.18-1.66 0-3 1.34-3 3s1.34 3 3 3 3-1.34 3-3V8h3V6h-5z"/></svg>`,
  completed: `<svg viewBox="0 0 24 24" class="task-icon completed"><path d="M9.55 18 3.85 12.3l1.42-1.42 4.28 4.3 9.3-9.3 1.42 1.42z"/></svg>`,
  failed: `<svg viewBox="0 0 24 24" class="task-icon failed"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-2h2v2zm0-4h-2V7h2v6z"/></svg>`,
  cancelled: `<svg viewBox="0 0 24 24" class="task-icon cancelled"><path d="M12 2C6.47 2 2 6.47 2 12s4.47 10 10 10 10-4.47 10-10S17.53 2 12 2zm0 18c-4.41 0-8-3.59-8-8s3.59-8 8-8 8 3.59 8 8-3.59 8-8 8zm3.59-13L12 10.59 8.41 7 7 8.41 10.59 12 7 15.59 8.41 17 12 13.41 15.59 17 17 15.59 13.41 12 17 8.41z"/></svg>`,
  close: `<svg viewBox="0 0 24 24"><path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/></svg>`,
  copy: `<svg viewBox="0 0 24 24"><path d="M16 1H4c-1.1 0-2 .9-2 2v14h2V3h12V1zm3 4H8c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h11c1.1 0 2-.9 2-2V7c0-1.1-.9-2-2-2zm0 16H8V7h11v14z"/></svg>`,
  chevron: `<svg viewBox="0 0 24 24" class="accordion-chevron"><path d="M7.41 8.59L12 13.17l4.59-4.58L18 10l-6 6-6-6 1.41-1.41z"/></svg>`
};

const expandedPlaylists = new Set();

function cleanMediaUrl(rawUrl) {
  if (!rawUrl) return "";
  try {
    const parsed = new URL(rawUrl.trim());
    const host = parsed.hostname.toLowerCase();

    if (host.includes("youtube.com") || host.includes("youtu.be")) {
      const v = parsed.searchParams.get("v");
      if (v) {
        return `https://www.youtube.com/watch?v=${v}`;
      }
      if (host.includes("youtu.be")) {
        const id = parsed.pathname.replace(/^\//, "").split("/")[0];
        if (id) return `https://youtu.be/${id}`;
      }
      const list = parsed.searchParams.get("list");
      if (list) {
        return `https://www.youtube.com/playlist?list=${list}`;
      }
    }
  } catch {
    // Fallback
  }
  return rawUrl.trim();
}

async function checkStatus() {
  const chip = document.getElementById("status-chip");
  const statusText = document.getElementById("status-text");

  try {
    const res = await fetch(`${APOLO_SERVER}/api/status`, { signal: AbortSignal.timeout(1500) });
    if (res.ok) {
      chip.className = "status-chip online";
      chip.title = "Servidor Apolo conectado";
      statusText.textContent = "Conectado";
      loadTasks();
    } else {
      throw new Error();
    }
  } catch {
    chip.className = "status-chip offline";
    chip.title = "Servidor Apolo desconectado";
    statusText.textContent = "Desconectado";
  }
}

async function cancelTask(taskId) {
  try {
    const res = await fetch(`${APOLO_SERVER}/api/tasks/${taskId}/cancel`, { method: "POST" });
    if (res.ok) {
      loadTasks();
    }
  } catch (err) {
    console.error("Failed to cancel task:", err);
  }
}

async function clearHistory() {
  const listEl = document.getElementById("task-list");
  const counterEl = document.getElementById("task-counter");
  try {
    await fetch(`${APOLO_SERVER}/api/tasks/clear`, { method: "POST" });
  } catch (err) {
    console.error("Failed to clear history:", err);
  }

  if (counterEl) counterEl.textContent = "0 tareas";
  if (listEl) {
    listEl.innerHTML = `
      <div class="empty-state">
        <svg viewBox="0 0 24 24"><path d="M12 3v10.55c-.59-.34-1.27-.55-2-.55-2.21 0-4 1.79-4 4s1.79 4 4 4 4-1.79 4-4V7h4V3h-6z"/></svg>
        <span>Sin descargas activas</span>
      </div>`;
  }
  await loadTasks();
}

async function loadTasks() {
  const listEl = document.getElementById("task-list");
  const counterEl = document.getElementById("task-counter");

  try {
    const res = await fetch(`${APOLO_SERVER}/api/tasks`);
    if (!res.ok) return;
    const data = await res.json();
    const tasks = data.tasks || [];

    counterEl.textContent = `${tasks.length} ${tasks.length === 1 ? "tarea" : "tareas"}`;

    if (tasks.length === 0) {
      listEl.innerHTML = `
        <div class="empty-state">
          <svg viewBox="0 0 24 24"><path d="M12 3v10.55c-.59-.34-1.27-.55-2-.55-2.21 0-4 1.79-4 4s1.79 4 4 4 4-1.79 4-4V7h4V3h-6z"/></svg>
          <span>Sin descargas activas</span>
        </div>`;
      return;
    }

    listEl.innerHTML = tasks
      .slice(0, 20)
      .map((t) => {
        const isRunning = t.status === "downloading" || t.status === "queued" || t.status === "retrying";
        const progressPct = t.progress ? Math.round(t.progress) : 0;
        const isPlaylist = t.is_playlist || (t.url && t.url.includes("list=")) || (t.subtracks && t.subtracks.length > 0);

        let statusLabel = t.status;
        if (t.status === "downloading") {
          statusLabel = progressPct > 0 ? `${progressPct}%` : "Descargando";
        } else if (t.status === "retrying") {
          statusLabel = "Reintentando...";
        } else if (t.status === "completed") {
          statusLabel = "Listo";
        } else if (t.status === "queued") {
          statusLabel = "En cola";
        } else if (t.status === "failed") {
          statusLabel = "Error";
        } else if (t.status === "cancelled") {
          statusLabel = "Cancelado";
        }

        let statusIcon = ICONS[t.status] || ICONS.spinner;
        if (isPlaylist && t.status === "completed") {
          statusIcon = ICONS.playlist;
        }

        const cancelBtnHtml = isRunning
          ? `<button class="btn-cancel-task" data-id="${t.id}" title="Cancelar descarga">${ICONS.close}</button>`
          : "";

        // Render Playlist / Album Task Card
        if (isPlaylist) {
          const playlistTitle = t.title || "Álbum / Playlist";
          const isExpanded = expandedPlaylists.has(t.id);
          const totalCount = t.total_tracks || (t.subtracks ? t.subtracks.length : 1);
          const completedCount = t.completed_tracks || (t.subtracks ? t.subtracks.filter(s => s.status === "completed").length : 0);

          const playlistStatusBadge = t.status === "completed"
            ? `<span class="task-badge completed">Listo (${completedCount}/${totalCount})</span>`
            : (t.status === "retrying"
                ? `<span class="task-badge retrying">Reintentando...</span>`
                : `<span class="task-badge ${t.status}">${completedCount}/${totalCount} (${progressPct}%)</span>`);

          // 1. Top Total Progress Bar (Progreso Total de la Playlist)
          const totalProgressBarHtml = isRunning || t.status === "completed"
            ? `
              <div class="playlist-total-header">
                <span>Progreso total</span>
                <span>${completedCount} de ${totalCount} (${progressPct}%)</span>
              </div>
              <div class="progress-bar-container total-bar">
                <div class="progress-bar-fill total-fill ${t.status === "retrying" ? "retrying" : ""}" style="width: ${progressPct > 0 ? progressPct : (isRunning ? 6 : 0)}%;"></div>
              </div>`
            : "";

          // 2. Active Song Indicator (Canción que está siendo descargada en ese momento)
          let activeSongHtml = "";
          if (isRunning) {
            const activeSub = (t.subtracks || []).find(s => s.status === "downloading" || s.status === "retrying");
            const activeTitle = t.current_track_title || (activeSub ? activeSub.title : "Descargando canción...");
            const activeIdx = t.current_track_index || (activeSub ? activeSub.track_number : "");
            const activePct = t.current_track_progress !== undefined && t.current_track_progress !== null
              ? Math.round(t.current_track_progress)
              : (activeSub && activeSub.progress ? Math.round(activeSub.progress) : 0);

            activeSongHtml = `
              <div class="active-song-box">
                <div class="active-song-header">
                  <span class="active-song-name">${activeIdx ? '#' + activeIdx + ' ' : ''}${escapeHtml(activeTitle)}</span>
                  <span class="active-song-pct">${activePct > 0 ? activePct + '%' : 'Descargando'}</span>
                </div>
                <div class="progress-bar-container active-song-bar">
                  <div class="progress-bar-fill" style="width: ${activePct > 0 ? activePct : 15}%;"></div>
                </div>
              </div>
            `;
          }

          // 3. Subtracks list for the Accordion
          const subtracksList = t.subtracks || [];
          const subtracksHtml = subtracksList
            .map((st, sIdx) => {
              const stNum = st.track_number || sIdx + 1;
              const stProgress = st.progress ? Math.round(st.progress) : 0;
              let stBadgeText = st.status;
              if (st.status === "completed") stBadgeText = "Listo";
              else if (st.status === "downloading") stBadgeText = stProgress > 0 ? `${stProgress}%` : "Descargando";
              else if (st.status === "retrying") stBadgeText = "Reintentando...";
              else if (st.status === "queued") stBadgeText = "En cola";
              else if (st.status === "failed") stBadgeText = "Error";

              const stBarHtml = st.status === "downloading" || st.status === "retrying"
                ? `<div class="progress-bar-container"><div class="progress-bar-fill ${st.status === "retrying" ? "retrying" : ""}" style="width: ${stProgress > 0 ? stProgress : 15}%;"></div></div>`
                : "";

              return `
                <div class="subtrack-card">
                  <div class="subtrack-top">
                    <div class="subtrack-title-box">
                      <span class="subtrack-num">#${stNum}</span>
                      <span class="subtrack-name" title="${escapeHtml(st.title)}">${escapeHtml(st.title)}</span>
                    </div>
                    <span class="subtrack-badge ${st.status}">${escapeHtml(stBadgeText)}</span>
                  </div>
                  ${stBarHtml}
                </div>
              `;
            })
            .join("");

          const accordionHtml = subtracksList.length > 0
            ? `
              <button class="accordion-toggle-btn ${isExpanded ? "expanded" : ""}" data-id="${t.id}">
                <span>Ver canciones (${subtracksList.length})</span>
                ${ICONS.chevron}
              </button>
              <div class="subtrack-list ${isExpanded ? "expanded" : ""}" id="subtracks-${t.id}">
                ${subtracksHtml}
              </div>`
            : "";

          return `
            <div class="task-card">
              <div class="task-top-row">
                <div class="task-info-left">
                  ${statusIcon}
                  <div class="task-title-group">
                    <span class="task-title" title="${escapeHtml(playlistTitle)}">${escapeHtml(playlistTitle)}</span>
                    <span class="task-subtitle">Playlist • ${totalCount} canciones</span>
                  </div>
                </div>
                <div class="task-actions">
                  ${playlistStatusBadge}
                  ${cancelBtnHtml}
                </div>
              </div>

              ${totalProgressBarHtml}
              ${activeSongHtml}
              ${accordionHtml}

              <div class="task-url-row">
                <span class="task-full-url" title="${escapeHtml(t.url)}">${escapeHtml(t.url)}</span>
                <button class="btn-copy-url" data-url="${escapeHtml(t.url)}" title="Copiar enlace">
                  ${ICONS.copy}
                </button>
              </div>
            </div>
          `;
        }

        // Single Track Card
        let title = t.title || t.url;
        if (!t.title && t.results && t.results.length > 0) {
          title = `${t.results[0].artist} - ${t.results[0].title}`;
        }

        const progressBarHtml = isRunning
          ? `<div class="progress-bar-container"><div class="progress-bar-fill ${t.status === "retrying" ? "retrying" : ""}" style="width: ${progressPct > 0 ? progressPct : 15}%;"></div></div>`
          : "";

        return `
          <div class="task-card">
            <div class="task-top-row">
              <div class="task-info-left">
                ${statusIcon}
                <span class="task-title" title="${escapeHtml(title)}">${escapeHtml(title)}</span>
              </div>
              <div class="task-actions">
                <span class="task-badge ${t.status}">${escapeHtml(statusLabel)}</span>
                ${cancelBtnHtml}
              </div>
            </div>
            ${progressBarHtml}
            <div class="task-url-row">
              <span class="task-full-url" title="${escapeHtml(t.url)}">${escapeHtml(t.url)}</span>
              <button class="btn-copy-url" data-url="${escapeHtml(t.url)}" title="Copiar enlace">
                ${ICONS.copy}
              </button>
            </div>
          </div>
        `;
      })
      .join("");

    // Attach accordion toggle events
    listEl.querySelectorAll(".accordion-toggle-btn").forEach((btn) => {
      btn.addEventListener("click", (e) => {
        e.stopPropagation();
        const taskId = btn.getAttribute("data-id");
        if (expandedPlaylists.has(taskId)) {
          expandedPlaylists.delete(taskId);
        } else {
          expandedPlaylists.add(taskId);
        }
        btn.classList.toggle("expanded");
        const list = document.getElementById(`subtracks-${taskId}`);
        if (list) {
          list.classList.toggle("expanded");
        }
      });
    });

    // Attach cancel events
    listEl.querySelectorAll(".btn-cancel-task").forEach((btn) => {
      btn.addEventListener("click", (e) => {
        e.stopPropagation();
        const taskId = btn.getAttribute("data-id");
        cancelTask(taskId);
      });
    });

    // Attach copy url events
    listEl.querySelectorAll(".btn-copy-url").forEach((btn) => {
      btn.addEventListener("click", (e) => {
        e.stopPropagation();
        const url = btn.getAttribute("data-url");
        if (url) {
          navigator.clipboard.writeText(url);
          btn.style.color = "#3ea6ff";
          setTimeout(() => {
            btn.style.color = "";
          }, 1500);
        }
      });
    });
  } catch (err) {
    console.error(err);
  }
}

function escapeHtml(str) {
  if (!str) return "";
  return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

const clearBtn = document.getElementById("btn-clear-history");
if (clearBtn) {
  clearBtn.addEventListener("click", (e) => {
    e.preventDefault();
    e.stopPropagation();
    clearHistory();
  });
}

document.getElementById("download-tab-btn").addEventListener("click", async () => {
  const btn = document.getElementById("download-tab-btn");
  const label = document.getElementById("btn-label");
  const originalText = "Descargar pestaña activa";
  btn.disabled = true;
  label.textContent = "Enviando...";

  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (!tab || !tab.url) {
      throw new Error("No tab URL");
    }

    let cleanTitle = tab.title ? tab.title.replace(/ - YouTube Music$/, "").replace(/ - YouTube$/, "").trim() : "";
    const cleanUrl = cleanMediaUrl(tab.url);

    const res = await fetch(`${APOLO_SERVER}/api/download`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url: cleanUrl, origin: "browser", title: cleanTitle })
    });

    if (res.ok) {
      label.textContent = "Enviado a Apolo";
      setTimeout(() => {
        btn.disabled = false;
        label.textContent = originalText;
        loadTasks();
      }, 1500);
    } else {
      throw new Error(`HTTP ${res.status}`);
    }
  } catch (err) {
    label.textContent = "Error al conectar";
    setTimeout(() => {
      btn.disabled = false;
      label.textContent = originalText;
    }, 2000);
  }
});

checkStatus();
setInterval(checkStatus, 2000);
