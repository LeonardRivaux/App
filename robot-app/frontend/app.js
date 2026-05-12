const form         = document.getElementById("missionForm");
const output       = document.getElementById("output");
const missionsList = document.getElementById("missionsList");
const robotsList   = document.getElementById("robotsList");
const canvas       = document.getElementById("mapCanvas");
const ctx          = canvas.getContext("2d");

const API = "http://127.0.0.1:8000";

// ── Coordonnées des salles sur la carte (pixels) ──────────────────────
// À ajuster quand tu auras les vraies coordonnées
const LOCATIONS = {
  "Salle A": { x: 100, y: 100 },
  "Salle B": { x: 300, y: 350 },
  "Salle C": { x: 500, y: 80  },
};

const LOCATION_COLORS = {
  "Salle A": "#3b82f6",
  "Salle B": "#8b5cf6",
  "Salle C": "#f59e0b",
};

// IDs de missions avec une action réseau en cours (évite le spam click)
const pendingActions = new Set();
let isFormSubmitting = false;

// ── Couleurs status ───────────────────────────────────────────────────
const STATUS_COLORS = {
  pending:     "#f59e0b",
  assigned:    "#3b82f6",
  in_recovery: "#f97316",
  completed:   "#10b981",
  cancelled:   "#6b7280",
  available:   "#10b981",
  busy:        "#ef4444",
};

function badge(status) {
  const color = STATUS_COLORS[status] ?? "#999";
  return `<span style="background:${color};color:#fff;padding:2px 8px;
    border-radius:12px;font-size:12px;font-weight:600;">${status}</span>`;
}

// ── Carte ─────────────────────────────────────────────────────────────
const mapImage = new Image();
mapImage.src = "map_placeholder.png";

// offset d'animation pour les pointillés
let dashOffset = 0;

function drawMap(activeMissions) {
  ctx.clearRect(0, 0, canvas.width, canvas.height);

  // fond gris si image non chargée
  if (mapImage.complete && mapImage.naturalWidth > 0) {
    ctx.drawImage(mapImage, 0, 0, canvas.width, canvas.height);
  } else {
    ctx.fillStyle = "#ccc";
    ctx.fillRect(0, 0, canvas.width, canvas.height);
  }

  // Trajets des missions en cours (assigned ou in_recovery)
  activeMissions.forEach((m, i) => {
    const from = LOCATIONS[m.start];
    const to   = LOCATIONS[m.end];
    if (!from || !to) return;

    const colors = ["#ef4444", "#3b82f6", "#f97316", "#8b5cf6"];
    const color  = colors[i % colors.length];

    ctx.save();
    ctx.setLineDash([12, 8]);
    ctx.lineDashOffset = -dashOffset;
    ctx.strokeStyle    = color;
    ctx.lineWidth      = 3;
    ctx.shadowColor    = color;
    ctx.shadowBlur     = 6;
    ctx.beginPath();
    ctx.moveTo(from.x, from.y);
    ctx.lineTo(to.x, to.y);
    ctx.stroke();
    ctx.restore();

    // Flèche au milieu du trajet
    const mx = (from.x + to.x) / 2;
    const my = (from.y + to.y) / 2;
    const angle = Math.atan2(to.y - from.y, to.x - from.x);
    ctx.save();
    ctx.translate(mx, my);
    ctx.rotate(angle);
    ctx.fillStyle = color;
    ctx.beginPath();
    ctx.moveTo(8, 0);
    ctx.lineTo(-6, -5);
    ctx.lineTo(-6, 5);
    ctx.closePath();
    ctx.fill();
    ctx.restore();

    // Label robot
    if (m.robot_id) {
      ctx.fillStyle = color;
      ctx.font      = "bold 11px monospace";
      ctx.fillText(`Robot #${m.robot_id}`, mx + 10, my - 6);
    }
  });

  // Points des salles
  Object.entries(LOCATIONS).forEach(([name, pos]) => {
    const color = LOCATION_COLORS[name] ?? "#555";

    // Halo
    ctx.save();
    ctx.shadowColor = color;
    ctx.shadowBlur  = 12;
    ctx.beginPath();
    ctx.arc(pos.x, pos.y, 10, 0, Math.PI * 2);
    ctx.fillStyle = color;
    ctx.fill();
    ctx.restore();

    // Anneau blanc
    ctx.beginPath();
    ctx.arc(pos.x, pos.y, 10, 0, Math.PI * 2);
    ctx.strokeStyle = "#fff";
    ctx.lineWidth   = 2;
    ctx.stroke();

    // Label
    ctx.fillStyle = "#1e293b";
    ctx.font      = "bold 13px monospace";
    ctx.fillText(name, pos.x + 14, pos.y + 5);
  });
}

// Animation des pointillés
let activeMissionsCache = [];
function animateMap() {
  dashOffset = (dashOffset + 0.5) % 20;
  drawMap(activeMissionsCache);
  requestAnimationFrame(animateMap);
}
mapImage.onload = () => animateMap();
// Démarre même si l'image tarde
setTimeout(() => { if (!mapImage.complete) animateMap(); }, 500);

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

    // Met à jour le cache pour la carte
    activeMissionsCache = data.filter(m =>
      m.status === "assigned" || m.status === "in_recovery"
    );

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
          ${["assigned","in_recovery"].includes(m.status) ? `
            <button class="btn-success" onclick="completeMission(${m.id}, this)">✔ Compléter</button>
          ` : ""}
          ${["pending","assigned"].includes(m.status) ? `
            <button class="btn-danger" onclick="cancelMission(${m.id}, this)">✖ Annuler</button>
          ` : ""}
          <button class="btn-delete" onclick="deleteMission(${m.id}, this)">🗑 Supprimer</button>
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
  if (isFormSubmitting) return;

  const start     = document.getElementById("start").value;
  const end       = document.getElementById("end").value;
  const submitBtn = form.querySelector('button[type="submit"]');

  if (start === end) {
    output.innerHTML = `<span style="color:#ef4444">⚠ Le départ et l'arrivée doivent être différents.</span>`;
    return;
  }

  isFormSubmitting = true;
  if (submitBtn) { submitBtn.disabled = true; submitBtn.textContent = "Envoi…"; }

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
  } finally {
    isFormSubmitting = false;
    if (submitBtn) { submitBtn.disabled = false; submitBtn.textContent = "Envoyer la mission"; }
  }
});

// ── Complete mission ──────────────────────────────────────────────────
async function completeMission(id, btn) {
  if (pendingActions.has(id)) return;
  pendingActions.add(id);
  if (btn) { btn.disabled = true; btn.textContent = "…"; }
  try {
    const res  = await fetch(`${API}/missions/${id}/complete`, { method: "POST" });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail);
    output.innerHTML = `<span style="color:#10b981">✔ Mission #${id} complétée</span>`;
    refresh();
  } catch (err) {
    output.innerHTML = `<span style="color:#ef4444">Erreur : ${err.message}</span>`;
    if (btn) { btn.disabled = false; btn.textContent = "✔ Compléter"; }
  } finally {
    pendingActions.delete(id);
  }
}

// ── Cancel mission ────────────────────────────────────────────────────
async function cancelMission(id, btn) {
  if (pendingActions.has(id)) return;
  pendingActions.add(id);
  if (btn) { btn.disabled = true; btn.textContent = "…"; }
  try {
    const res  = await fetch(`${API}/missions/${id}/cancel`, { method: "POST" });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail);
    output.innerHTML = `<span style="color:#f59e0b">⚠ Mission #${id} annulée</span>`;
    refresh();
  } catch (err) {
    output.innerHTML = `<span style="color:#ef4444">Erreur : ${err.message}</span>`;
    if (btn) { btn.disabled = false; btn.textContent = "✖ Annuler"; }
  } finally {
    pendingActions.delete(id);
  }
}

// ── Delete mission ────────────────────────────────────────────────────
async function deleteMission(id, btn) {
  if (!confirm(`Supprimer la mission #${id} ?`)) return;
  if (pendingActions.has(id)) return;
  pendingActions.add(id);
  if (btn) { btn.disabled = true; btn.textContent = "…"; }
  try {
    const res  = await fetch(`${API}/missions/${id}`, { method: "DELETE" });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail);
    output.innerHTML = `<span style="color:#6b7280">🗑 Mission #${id} supprimée</span>`;
    refresh();
  } catch (err) {
    output.innerHTML = `<span style="color:#ef4444">Erreur : ${err.message}</span>`;
    if (btn) { btn.disabled = false; btn.textContent = "🗑 Supprimer"; }
  } finally {
    pendingActions.delete(id);
  }
}

// ── Auto-refresh every 5 s ────────────────────────────────────────────
refresh();
setInterval(refresh, 5000);