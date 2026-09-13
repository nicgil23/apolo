const APOLO_SERVER = "http://127.0.0.1:4533";

function cleanMediaUrl(rawUrl) {
  if (!rawUrl) return "";
  try {
    const parsed = new URL(rawUrl.trim());
    const host = parsed.hostname.toLowerCase();

    if (host.includes("youtube.com") || host.includes("youtu.be")) {
      const v = parsed.searchParams.get("v");
      if (v) {
        return `${parsed.protocol}//${parsed.hostname}${parsed.pathname}?v=${v}`;
      }
      if (host.includes("youtu.be")) {
        const id = parsed.pathname.replace(/^\//, "").split("/")[0];
        if (id) return `https://youtu.be/${id}`;
      }
      if (parsed.pathname.includes("/playlist")) {
        const list = parsed.searchParams.get("list");
        if (list) return `${parsed.protocol}//${parsed.hostname}/playlist?list=${list}`;
      }
    }
  } catch {
    // If URL parsing fails, fallback
  }
  return rawUrl.trim();
}

async function checkStatus() {
  const indicator = document.getElementById("status-indicator");
  try {
    const res = await fetch(`${APOLO_SERVER}/api/status`, { signal: AbortSignal.timeout(1500) });
    if (res.ok) {
      indicator.className = "status-indicator online";
      indicator.title = "Servidor Apolo activo";
      loadTasks();
    } else {
      throw new Error();
    }
  } catch {
    indicator.className = "status-indicator";
    indicator.title = "Servidor Apolo desconectado";
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
      listEl.innerHTML = `<div class="empty-state">Sin descargas activas</div>`;
      return;
    }

    listEl.innerHTML = tasks
      .slice(0, 10)
      .map((t) => {
        let title = t.url;
        if (t.results && t.results.length > 0) {
          title = `${t.results[0].artist} - ${t.results[0].title}`;
        }

        const isRunning = t.status === "downloading" || t.status === "queued";
        const progressPct = t.progress ? Math.round(t.progress) : 0;
        const statusText = isRunning && progressPct > 0 ? `${progressPct}%` : t.status;

        const progressBarHtml = isRunning
          ? `<div class="progress-bar-container"><div class="progress-bar-fill" style="width: ${progressPct > 0 ? progressPct : 15}%;"></div></div>`
          : "";

        const cancelBtnHtml = isRunning
          ? `<button class="btn-cancel-task" data-id="${t.id}">Cancelar</button>`
          : "";

        return `
        <div class="task-card">
          <div class="task-top-row">
            <span class="task-title" title="${escapeHtml(title)}">${escapeHtml(title)}</span>
            <div class="task-actions">
              <span class="task-badge ${t.status}">${escapeHtml(statusText)}</span>
              ${cancelBtnHtml}
            </div>
          </div>
          ${progressBarHtml}
          <div class="task-url-row">
            <span class="task-full-url" title="${escapeHtml(t.url)}">${escapeHtml(t.url)}</span>
            <button class="btn-copy-url" data-url="${escapeHtml(t.url)}" title="Copiar enlace">
              <svg viewBox="0 0 24 24"><path d="M16 1H4c-1.1 0-2 .9-2 2v14h2V3h12V1zm3 4H8c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h11c1.1 0 2-.9 2-2V7c0-1.1-.9-2-2-2zm0 16H8V7h11v14z"/></svg>
            </button>
          </div>
        </div>
      `;
      })
      .join("");

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
          btn.style.color = "#10b981";
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

document.getElementById("download-tab-btn").addEventListener("click", async () => {
  const btn = document.getElementById("download-tab-btn");
  const label = document.getElementById("btn-label");
  const originalText = "Descargar pestaña";
  btn.disabled = true;
  label.textContent = "Enviando...";

  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (!tab || !tab.url) {
      throw new Error("No tab URL");
    }

    const cleanUrl = cleanMediaUrl(tab.url);

    const res = await fetch(`${APOLO_SERVER}/api/download`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url: cleanUrl, origin: "browser" })
    });

    if (res.ok) {
      label.textContent = "Enviado";
      setTimeout(() => {
        btn.disabled = false;
        label.textContent = originalText;
        loadTasks();
      }, 1500);
    } else {
      throw new Error(`HTTP ${res.status}`);
    }
  } catch (err) {
    label.textContent = "Error";
    setTimeout(() => {
      btn.disabled = false;
      label.textContent = originalText;
    }, 2000);
  }
});

checkStatus();
setInterval(checkStatus, 2000);
