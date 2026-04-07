const form = document.getElementById("missionForm");
const output = document.getElementById("output");
const missionsList = document.getElementById("missionsList");
const robotsList = document.getElementById("robotsList");

const API = "http://127.0.0.1:8000";

// ── Status badge colors ───────────────────────────────────────────────
const STATUS_COLORS = {
  pending:   "#f59e0b",
  assigned:  "#3b82f6",
  completed: "#10b981",
  cancelled: "#6b7280",
  available: "#10b981",
  busy:      "#ef4444",
};

function badge(status) {
  const color = STATUS_COLORS[status] ?? "#999";
  return `<span style="
    background:${color};color:#fff;padding:2px 8px;
    border-radius:12px;font-size:12px;font-weight:600;
  ">${status}</span>`;
}

// ── Load robots ───────────────────────────────────────────────────────
async function loadRobots() {
  try {
    const res  = await fetch(`${API}/robots`);
    const data = await res.json();
    robotsList.innerHTML = data.map(r => `
      <div class="card">
        <strong>${r.name}</strong> &nbsp;${badge(r.status)}
        <span style="color:#888;font-size:13px;margin-left:8px">${r.ip_address ?? ""}</span>
      </div>
    `).join("");
  } catch (e) {
    robotsList.textContent = "Erreur : " + e.message;
  }
}

// ── Load missions ─────────────────────────────────────────────────────
async function loadMissions() {
  try {
    const res  = await fetch(`${API}/missions`);
    const data = await res.json();

    if (data.length === 0) {
      missionsList.innerHTML = "<p style='color:#888'>Aucune mission.</p>";
      return;
    }

    missionsList.innerHTML = data.map(m => `
      <div class="card">
        <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap">
          <strong>#${m.id}</strong>
          ${badge(m.status)}
          <span>${m.start} → ${m.end}</span>
          ${m.robot_id ? `<span style="color:#888;font-size:13px">Robot #${m.robot_id}</span>` : ""}
        </div>
        <div style="margin-top:8px;display:flex;gap:8px;flex-wrap:wrap">
          ${m.status === "assigned" ? `
            <button class="btn-success" onclick="completemission(${m.id})">✔ Compléter</button>
          ` : ""}
          ${["pending","assigned"].includes(m.status) ? `
            <button class="btn-danger" onclick="cancelMission(${m.id})">✖ Annuler</button>
          ` : ""}
          <button class="btn-delete" onclick="deleteMission(${m.id})">🗑 Supprimer</button>
        </div>
      </div>
    `).join("");
  } catch (e) {
    missionsList.innerHTML = "Erreur : " + e.message;
  }
}

function refresh() {
  loadRobots();
  loadMissions();
}

// ── Create mission ────────────────────────────────────────────────────
form.addEventListener("submit", async (e) => {
  e.preventDefault();
  const start = document.getElementById("start").value;
  const end   = document.getElementById("end").value;

  try {
    const res  = await fetch(`${API}/missions`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ start, end }),
    });
    const data = await res.json();
    output.innerHTML = `<span style="color:#10b981">✔ Mission créée</span><br><pre>${JSON.stringify(data, null, 2)}</pre>`;
    form.reset();
    refresh();
  } catch (err) {
    output.textContent = "Erreur : " + err.message;
  }
});

// ── Complete mission ──────────────────────────────────────────────────
async function completemission(id) {
  try {
    const res  = await fetch(`${API}/missions/${id}/complete`, { method: "POST" });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail);
    output.innerHTML = `<span style="color:#10b981">✔ Mission #${id} complétée</span>`;
    refresh();
  } catch (err) {
    output.innerHTML = `<span style="color:#ef4444">Erreur : ${err.message}</span>`;
  }
}

// ── Cancel mission ────────────────────────────────────────────────────
async function cancelMission(id) {
  try {
    const res  = await fetch(`${API}/missions/${id}/cancel`, { method: "POST" });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail);
    output.innerHTML = `<span style="color:#f59e0b">⚠ Mission #${id} annulée</span>`;
    refresh();
  } catch (err) {
    output.innerHTML = `<span style="color:#ef4444">Erreur : ${err.message}</span>`;
  }
}

// ── Delete mission ────────────────────────────────────────────────────
async function deleteMission(id) {
  if (!confirm(`Supprimer la mission #${id} ?`)) return;
  try {
    const res  = await fetch(`${API}/missions/${id}`, { method: "DELETE" });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail);
    output.innerHTML = `<span style="color:#6b7280">🗑 Mission #${id} supprimée</span>`;
    refresh();
  } catch (err) {
    output.innerHTML = `<span style="color:#ef4444">Erreur : ${err.message}</span>`;
  }
}

// ── Auto-refresh every 5 s ────────────────────────────────────────────
refresh();
setInterval(refresh, 5000);