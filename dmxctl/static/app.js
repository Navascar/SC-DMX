"use strict";

const $ = (s, root = document) => root.querySelector(s);
const el = (tag, props = {}, ...kids) => {
  const n = Object.assign(document.createElement(tag), props);
  for (const k of kids) n.append(k);
  return n;
};
const hex2 = (v) => v.toString(16).padStart(2, "0");
const toHex = (r, g, b) => "#" + hex2(r) + hex2(g) + hex2(b);
const fromHex = (h) => [1, 3, 5].map((i) => parseInt(h.slice(i, i + 2), 16));

let S = null;                 // повний стан від сервера
const selected = new Set();
let lastColor = "#ff0000";
let effColors = null;         // локальна палітра ефекту
let ws = null;
let activeSlider = null;
let serverVersion = null;     // якщо після перезапуску версія інша — перезавантажуємо сторінку
let updateInfo = null;
let quitting = false;

// ------------------------------------------------------------- зв'язок ----
function connect() {
  ws = new WebSocket(`${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/ws`);
  ws.onopen = () => ($("#offline").hidden = true);
  ws.onmessage = (e) => onMessage(JSON.parse(e.data));
  ws.onclose = () => {
    setOutput({ ok: false, status: "немає з'єднання з сервером" });
    const restarting = updateInfo && updateInfo.status === "restarting";
    $("#offline").hidden = false;
    $("#offlineText").textContent = quitting ? "Програму вимкнено. Це вікно можна закрити."
      : restarting ? "Встановлюється оновлення, програма перезапускається…" : "Підключення…";
    if (!quitting) setTimeout(connect, 1500);
  };
}

function send(msg) {
  if (ws && ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify(msg));
}

// Повідомлення від слайдерів зливаються і відправляються не частіше ніж раз на 33 мс
const pending = new Map();
let flushTimer = null;
function sendThrottled(key, msg) {
  const prev = pending.get(key);
  pending.set(key, prev ? { ...prev, ...msg } : msg);
  if (!flushTimer) flushTimer = setTimeout(flush, 33);
}
function flush() {
  flushTimer = null;
  for (const m of pending.values()) send(m);
  pending.clear();
}

function onMessage(m) {
  if (m.type === "state" && pendingUndo) {
    toast(pendingUndo === "undo" ? "Дію скасовано" : "Дію повторено", true);
    pendingUndo = null;
  }
  if (m.type === "state") {
    if (serverVersion && m.state.version !== serverVersion) return location.reload();
    serverVersion = m.state.version;
    S = m.state;
    for (const id of [...selected]) if (!S.fixtures.some((f) => f.id === id)) selected.delete(id);
    if (effColors === null) effColors = [...S.effect.colors];
    renderAll();
    afterState();
  } else if (m.type === "patch" && S) {
    S.fixtures = m.fixtures;
    S.master = m.master;
    syncSliders();
    syncMaster();
  } else if (m.type === "live") {
    updateLive(m);
  } else if (m.type === "ports") {
    const dl = $("#portList");
    dl.replaceChildren(...m.ports.map((p) => el("option", { value: p.device, label: `${p.device} — ${p.description}` })));
    toast(m.ports.length ? `Знайдено портів: ${m.ports.length}` : "Послідовні порти не знайдено", true);
  } else if (m.type === "udmx") {
    const sel = $("#udmxIndex");
    const cur = S.output_cfg.index || 0;
    sel.replaceChildren(...(m.devices.length ? m.devices : [{ product: "uDMX не знайдено" }]).map((d, i) =>
      el("option", { value: i, textContent: d.bus !== undefined
        ? `${d.product}${d.serial ? " #" + d.serial : ""} — USB ${d.bus}:${d.address}` : d.product })));
    sel.value = cur;
    toast(m.devices.length ? `Знайдено uDMX: ${m.devices.length}` : "uDMX не знайдено — перевірте підключення і драйвер", true);
  } else if (m.type === "update") {
    updateInfo = m.update;
    renderUpdate();
  } else if (m.type === "bye") {
    quitting = true;
  } else if (m.type === "error") {
    pendingUndo = null;
    if (addPending !== null) addPending = null;
    toast(m.message);
  }
}

let toastTimer;
// усі написи — з великої літери
const cap = (s) => (s ? String(s).charAt(0).toUpperCase() + String(s).slice(1) : s);

function toast(text, info = false) {
  const t = $("#toast");
  t.textContent = cap(text);
  t.className = "toast" + (info ? " info" : "");
  hostLayer(t);
  try { t.hidePopover(); t.showPopover(); } catch { /* ignore */ }
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { try { t.hidePopover(); } catch { /* ignore */ } }, 3500);
}

// Коли відкрите модальне вікно, усе поза ним неактивне. Тому меню та сповіщення
// переносимо всередину верхнього відкритого вікна (або назад у <body>).
function hostLayer(node) {
  const open = [...document.querySelectorAll("dialog[open]")].filter((d) => d.matches(":modal"));
  const host = open[open.length - 1] || document.body;
  if (node.parentElement !== host) {
    try { node.hidePopover(); } catch { /* ignore */ }
    host.append(node);
  }
}

// ------------------------------------------------ власні вікна (замість браузерних) ---
function uiDialog({ title = "SC DMX", text = "", input = null, ok = "OK", cancel = "Скасувати", danger = false }) {
  return new Promise((resolve) => {
    const dlg = $("#uiDlg");
    $("#uiTitle").textContent = title;
    $("#uiText").textContent = text;
    $("#uiText").hidden = !text;
    const inp = $("#uiInput");
    inp.hidden = input === null;
    inp.value = input ?? "";
    $("#uiOk").textContent = ok;
    $("#uiCancel").textContent = cancel;
    $("#uiCancel").hidden = cancel === null;
    dlg.classList.toggle("danger", danger);
    let result = null;
    const finish = (value) => { result = value; dlg.close(); };
    $("#uiOk").onclick = () => finish(input === null ? true : inp.value);
    $("#uiCancel").onclick = () => finish(input === null ? false : null);
    inp.onkeydown = (e) => { if (e.key === "Enter") { e.preventDefault(); finish(inp.value); } };
    dlg.addEventListener("close", () => resolve(result ?? (input === null ? false : null)), { once: true });
    dlg.showModal();
    if (input !== null) { inp.focus(); inp.select(); } else $("#uiOk").focus();
  });
}
const uiConfirm = (text, opts = {}) => uiDialog({ title: opts.title || "Підтвердження", text, ok: opts.ok || "Так", danger: !!opts.danger });
const uiPrompt = (title, value = "") => uiDialog({ title, input: value, ok: "Зберегти" });

// ------------------------------------------------------------- рендер -----
function renderAll() {
  renderFixtures();
  syncSliders();
  syncMaster();
  renderStatic();
  renderEffects();
  renderScenes();
  renderSettings();
  setOutput(S.output);
}

function setOutput(o) {
  const pill = $("#outputPill");
  pill.classList.toggle("ok", !!o.ok);
  pill.classList.toggle("err", !o.ok);
  const names = { udmx: "uDMX", none: "Симулятор", enttec_pro: "DMX USB Pro", open_dmx: "Open DMX", artnet: "Art-Net", sacn: "sACN" };
  $("#outputText").textContent = (o.type ? names[o.type] + " · " : "") + cap(o.status);
  pill.title = o.status;
  $("#outStatus").textContent = cap(o.status);
}

function syncMaster() {
  if (activeSlider !== "master") $("#master").value = S.master;
  $("#masterVal").textContent = Math.round((S.master / 255) * 100) + "%";
  $("#blackout").classList.toggle("active", S.blackout);
}

function renderFixtures() {
  const grid = $("#fixtureGrid");
  grid.replaceChildren();
  if (!S.fixtures.length) {
    grid.append(el("div", { className: "empty-state" },
      el("div", { textContent: "Приладів ще немає." }),
      el("button", { className: "btn primary", textContent: "＋ Додати прилад", onclick: openAdd })));
  }
  const effIds = new Set(S.effect.type !== "none" ? S.effect.ids : []);
  for (const f of S.fixtures) {
    const n = segCount(f);
    let lamp;
    if (n > 1) {
      lamp = el("div", { className: "lamp bar" });
      for (let k = 0; k < n; k++) {
        const cell = el("span", { title: `Сегмент ${k + 1}` });
        cell.className = selected.has(`${f.id}#${k}`) ? "sel" : "";
        cell.onclick = (e) => {
          e.stopPropagation();
          pick(`${f.id}#${k}`, e.shiftKey);
        };
        cell.ondblclick = (e) => { e.stopPropagation(); openProps(f.id); };
        lamp.append(cell);
      }
    } else {
      lamp = el("div", { className: "lamp" });
    }
    const tile = el("div", { className: "fx" + (selected.has(f.id) ? " sel" : "") + (n > 1 ? " wide" : ""),
                             title: f.profile + (n > 1 ? "\nКлік по сегменту — вибрати окремий сегмент" : "") },
      lamp,
      el("div", { className: "name", textContent: f.name }),
      el("div", { className: "addr", textContent: `DMX ${f.address}–${f.address + S.profiles[f.profile].length - 1}` }),
      el("div", { className: "fx-badge", textContent: f.preset ? `● ${programName(f.preset)}`
        : effIds.has(f.id) ? "● " + S.effects[S.effect.type] : "" }));
    tile.dataset.id = f.id;
    tile.onclick = (e) => pick(f.id, e.shiftKey);
    tile.ondblclick = (e) => {
      e.preventDefault();
      selected.clear();
      selected.add(f.id);
      refreshSelection();
      syncSliders();
      openProps(f.id);
    };
    grid.append(tile);
  }
}

// Клік — вибрати лише цей прилад/сегмент (повторний клік знімає вибір).
// Shift + клік — додати до вибору або прибрати з нього.
function pick(id, multi) {
  const fid = id.split("#")[0];
  if (multi) {
    if (selected.has(id)) {
      selected.delete(id);
    } else {
      // прилад цілком і його сегменти взаємовиключні
      for (const x of [...selected]) if (x !== id && x.split("#")[0] === fid && (!id.includes("#") || !x.includes("#"))) selected.delete(x);
      selected.add(id);
    }
  } else {
    const only = selected.size === 1 && selected.has(id);
    selected.clear();
    if (!only) selected.add(id);
  }
  refreshSelection();
  syncSliders();
  // клік по бару відкриває вікно пресетів (знято вибір — вікно закриється саме)
  if (selected.has(id) && (S.preset_fixtures || []).includes(fid)) openPresets();
}

// оновлює підсвітку вибору, не перебудовуючи плитки
function refreshSelection() {
  for (const tile of document.querySelectorAll(".fx")) {
    tile.classList.toggle("sel", selected.has(tile.dataset.id));
    const bar = tile.querySelector(".lamp.bar");
    if (bar) [...bar.children].forEach((c, k) => c.classList.toggle("sel", selected.has(`${tile.dataset.id}#${k}`)));
  }
}

let lastDmx = new Array(512).fill(0);

function updateLive(m) {
  lastDmx = m.dmx;
  const paint = (node, [r, g, b, w], glow) => {
    const rr = Math.min(255, r + w), gg = Math.min(255, g + w), bb = Math.min(255, b + w);
    node.style.background = `rgb(${rr},${gg},${bb})`;
    node.style.boxShadow = `0 0 ${glow + (rr + gg + bb) / 30}px rgba(${rr},${gg},${bb},.7)`;
  };
  for (const tile of document.querySelectorAll(".fx")) {
    const segs = m.live[tile.dataset.id];
    if (!segs) continue;
    const lamp = tile.firstChild;
    if (lamp.classList.contains("bar")) {
      [...lamp.children].forEach((cell, k) => segs[k] && paint(cell, segs[k], 2));
    } else {
      paint(lamp, segs[0], 6);
    }
  }
  if (m.output) setOutput(m.output);
  const det = $(".monitor-panel details");
  $("#frameCounter").textContent = `· Відправлено кадрів: ${m.frames}`;
  if (det.open) {
    const cells = $("#monitor").children;
    for (let i = 0; i < 512; i++) {
      const v = m.dmx[i];
      const c = cells[i];
      if (c._v === v) continue;
      c._v = v;
      c.lastChild.textContent = v;
      c.firstChild.style.height = (v / 255) * 100 + "%";
    }
  }
}

// ------------------------------------------------------- колір/слайдери ---
const SLIDERS = [
  ["r", "Червоний", "#ff4d4d"], ["g", "Зелений", "#3ecf5e"], ["b", "Синій", "#4f8cff"],
  ["w", "Білий", "#ffffff"], ["a", "Бурштин", "#ffb000"], ["uv", "УФ", "#9b5cff"],
  ["dimmer", "Яскравість", "#cccccc"], ["strobe", "Строб (кан.)", "#888888"],
];

function buildSliders() {
  const box = $("#sliders");
  for (const [key, label, color] of SLIDERS) {
    const input = el("input", { type: "range", min: 0, max: 255, value: 0, id: "sl_" + key });
    input.style.setProperty("--fill", color);
    const out = el("output", { textContent: "0" });
    input.addEventListener("pointerdown", () => (activeSlider = key));
    input.addEventListener("pointerup", () => (activeSlider = null));
    input.addEventListener("input", () => {
      out.textContent = input.value;
      if (!selected.size) return toast("Спершу виберіть прилади");
      sendThrottled("color", { cmd: "set_color", ids: [...selected], [key]: +input.value });
    });
    const row = el("div", { className: "slider" }, el("label", { textContent: label, htmlFor: input.id }), input, out);
    row.dataset.key = key;
    box.append(row);
  }
}

function segCount(f) {
  const ch = S.profiles[f.profile] || [];
  return Math.max(1, ...["r", "g", "b", "w", "a", "uv"].map((c) => ch.filter((x) => x === c).length));
}

// вибрані елементи: [{f, seg}] — seg = null для приладу цілком
function selItems() {
  const out = [];
  for (const id of selected) {
    const [fid, k] = id.split("#");
    const f = S.fixtures.find((x) => x.id === fid);
    if (f) out.push({ f, seg: k === undefined ? null : +k });
  }
  return out;
}

function itemColor({ f, seg }) {
  const c = { ...f };
  if (seg !== null && f.segs && f.segs[seg]) [c.r, c.g, c.b] = f.segs[seg];
  return c;
}

function selDescription(items) {
  const whole = items.filter((i) => i.seg === null).length;
  const segs = items.length - whole;
  return [whole && `приладів: ${whole}`, segs && `сегментів: ${segs}`].filter(Boolean).join(", ");
}

function syncSliders() {
  const items = selItems();
  const sel = [...new Set(items.map((i) => i.f))];
  const desc = selDescription(items);
  $("#selInfo").textContent = desc ? `Вибрано ${desc}` : "Нічого не вибрано";
  $("#staticTarget").textContent = desc ? `Для вибраних (${desc})` : "Для всіх приладів";
  renderPresets();
  $("#clearLabel").textContent = desc ? "Очистити вибрані" : "Очистити все";
  // показувати лише ті канали, що є у вибраних приладів (або всі, якщо не вибрано)
  const roles = new Set();
  for (const f of sel.length ? sel : S.fixtures) for (const r of S.profiles[f.profile] || []) roles.add(r);
  const first = items[0] && itemColor(items[0]);
  for (const row of $("#sliders").children) {
    const key = row.dataset.key;
    const always = ["r", "g", "b", "w", "dimmer"].includes(key);
    row.hidden = !always && !roles.has(key);
    if (first && activeSlider !== key) {
      row.children[1].value = first[key];
      row.children[2].textContent = first[key];
    }
  }
}

function buildSwatches() {
  const colors = ["#ff0000", "#ff6a00", "#ffc400", "#ffff00", "#80ff00", "#00ff00", "#00ffaa", "#00ffff",
                  "#0080ff", "#0000ff", "#8000ff", "#ff00ff", "#ff0080", "#ffffff", "#ffb070", "#000000"];
  const box = $("#swatches");
  for (const c of colors) {
    const b = el("button", { title: c });
    b.style.background = c;
    b.onclick = () => pickColor(c);
    box.append(b);
  }
}

function pickColor(hex) {
  lastColor = hex;
  if (!selected.size) return toast("Спершу виберіть прилади");
  sendThrottled("color", { cmd: "set_color", ids: [...selected], hex });
}

function buildWheel() {
  const cv = $("#wheel");
  const ctx = cv.getContext("2d");
  const R = cv.width / 2;
  const img = ctx.createImageData(cv.width, cv.height);
  for (let y = 0; y < cv.height; y++) {
    for (let x = 0; x < cv.width; x++) {
      const dx = x - R, dy = y - R, d = Math.hypot(dx, dy);
      const i = (y * cv.width + x) * 4;
      if (d > R) { img.data[i + 3] = 0; continue; }
      const [r, g, b] = hsv((Math.atan2(dy, dx) / (2 * Math.PI) + 1) % 1, d / R, 1);
      img.data.set([r, g, b, d > R - 1 ? 128 : 255], i);
    }
  }
  ctx.putImageData(img, 0, 0);
  const pick = (e) => {
    const rect = cv.getBoundingClientRect();
    const x = ((e.clientX - rect.left) / rect.width) * cv.width - R;
    const y = ((e.clientY - rect.top) / rect.height) * cv.height - R;
    const s = Math.min(1, Math.hypot(x, y) / R);
    const [r, g, b] = hsv((Math.atan2(y, x) / (2 * Math.PI) + 1) % 1, s, 1);
    pickColor(toHex(r, g, b));
  };
  let down = false;
  cv.addEventListener("pointerdown", (e) => { down = true; cv.setPointerCapture(e.pointerId); pick(e); });
  cv.addEventListener("pointermove", (e) => down && pick(e));
  cv.addEventListener("pointerup", () => (down = false));
}

function hsv(h, s, v) {
  const i = Math.floor(h * 6), f = h * 6 - i;
  const p = v * (1 - s), q = v * (1 - f * s), t = v * (1 - (1 - f) * s);
  const [r, g, b] = [[v, t, p], [q, v, p], [p, v, t], [p, q, v], [t, p, v], [v, p, q]][i % 6];
  return [r, g, b].map((x) => Math.round(x * 255));
}

// ----------------------------------------------------------- оновлення ----
function renderUpdate() {
  const u = updateInfo;
  if (!u) return;
  $("#aboutVersion").textContent = "v" + u.current;
  $("#aboutRepo").textContent = "github.com/" + u.repo;
  $("#aboutRepo").href = u.page || `https://github.com/${u.repo}/releases`;
  const busy = u.status === "installing" || u.status === "restarting";
  $("#aboutUpdate").textContent = cap(u.status === "checking" ? "Перевірка…"
    : busy ? u.progress
    : u.error ? u.error
    : u.available ? `Доступна версія ${u.latest}`
    : u.latest ? `Встановлено останню версію (${u.current})` : "");
  $("#checkUpdate").textContent = u.available ? "Оновити до " + u.latest : "Перевірити оновлення";
  $("#checkUpdate").disabled = busy || u.status === "checking";
  $("#aboutNotes").hidden = !(u.available && u.notes);
  $("#aboutNotes").textContent = u.notes;

  // кнопка у шапці: з'являється сама, щойно знайдено нову версію
  const btn = $("#updateBtn");
  const failed = !!u.error && renderUpdate.tried && !busy;
  btn.hidden = !(u.available || busy || failed);
  btn.classList.toggle("busy", busy);
  btn.classList.toggle("err", failed);
  btn.disabled = busy;
  btn.textContent = busy ? `⟳ ${u.progress || "оновлення…"}`
    : failed ? "⚠ Оновлення не вдалося"
    : `⬆ Оновити до ${u.latest}`;
  btn.title = failed ? u.error : `Встановлена версія ${u.current}, доступна ${u.latest}`;

  $("#updTitle").textContent = `SC DMX ${u.latest}`;
  $("#updSubtitle").textContent = `Встановлено: ${u.current}  →  нова версія: ${u.latest}`;
  $("#updNotes").textContent = u.notes || "Опис змін відсутній.";
  $("#updBlocked").hidden = !u.blocked;
  $("#updBlocked").textContent = u.blocked ? "Автооновлення недоступне: " + u.blocked : "";
  $("#updInstall").disabled = !!u.blocked || busy || !u.available;
  if (busy && $("#updDlg").open) $("#updDlg").close();
}

function openUpdateDialog() {
  if (!updateInfo) return;
  if (updateInfo.error && renderUpdate.tried && !updateInfo.available) return toast(updateInfo.error);
  $("#updDlg").showModal();
}

function startUpdate() {
  renderUpdate.tried = true;
  send({ cmd: "apply_update" });
  $("#updDlg").close();
}

function bindUpdate() {
  $("#updateBtn").onclick = openUpdateDialog;
  $("#updInstall").onclick = startUpdate;
  $("#checkUpdate").onclick = () => (updateInfo && updateInfo.available && !updateInfo.blocked
    ? ($("#settings").close(), openUpdateDialog()) : send({ cmd: "check_update" }));
  $("#quitApp").onclick = () => {
    uiConfirm("Прожектори згаснуть.", { title: "Вимкнути SC DMX?", ok: "Вимкнути", danger: true })
      .then((ok) => { if (ok) { quitting = true; send({ cmd: "quit" }); } });
  };
}

// --------------------------------------------------------------- пресети ---
// вибрані прилади, що мають вбудовані пресети (LED-бари)
function presetTargets() {
  const bars = new Set(S.preset_fixtures || []);
  const ids = [...new Set(selItems().map((i) => i.f.id))];
  return S.fixtures.filter((f) => ids.includes(f.id) && bars.has(f.id));
}

// Панель «Колір»: для вибраного LED-бару її місце займають пресети (перемикач «Пресети / Колір»)
let colorPane = "color";

function setPane(pane) {
  colorPane = pane;
  const bars = presetTargets().length > 0;
  const showPresets = bars && pane === "presets";
  $("#presetPane").hidden = !showPresets;
  $("#colorPane").hidden = showPresets;
  $("#paneTabs").hidden = !bars;
  $("#colorTitle").hidden = bars;
  for (const b of $("#paneTabs").children) b.classList.toggle("active", b.dataset.pane === (showPresets ? "presets" : "color"));
}

function openPresets() {
  if (!presetTargets().length) return toast("Виберіть LED-бар");
  renderPresets();
  setPane("presets");
}

const PROGRAM_GROUPS = [["color", "Кольори"], ["effect", "Ефекти"], ["gradient", "Градієнти"], ["sound", "Звук"]];
const PROGRAM_SWATCH = { "Червоний": "#ff2020", "Зелений": "#20e040", "Синій": "#2050ff", "Жовтий": "#ffc800",
                         "Фіолетовий": "#a020ff", "Блакитний": "#00d0ff", "Білий": "#ffffff", "Круговий": "conic-gradient(#f22,#fc0,#2e4,#25f,#a2f,#f22)" };
const programName = (n) => (S.programs || [])[n - 1]?.name || `Пресет ${n}`;

function programSwatch(p) {
  const key = Object.keys(PROGRAM_SWATCH).find((k) => p.name.startsWith(k));
  if (!key) return null;
  const c = PROGRAM_SWATCH[key];
  return p.group === "gradient" && key !== "Круговий" ? `linear-gradient(90deg, #000, ${c})` : c;
}

function buildPresets() {
  const grid = $("#presetGrid");
  if (grid.dataset.built === String(S.preset_count)) return;
  grid.dataset.built = S.preset_count;
  grid.replaceChildren();
  for (const [group, title] of PROGRAM_GROUPS) {
    const progs = (S.programs || []).filter((p) => p.group === group);
    if (!progs.length) continue;
    grid.append(el("div", { className: "prog-title", textContent: title }));
    const box = el("div", { className: "prog-row prog-" + group });
    for (const p of progs) {
      const label = group === "effect" ? p.name.replace("Ефект ", "") : group === "gradient" ? p.name.replace(" градієнт", "") : p.name;
      const b = el("button", { type: "button", title: `${p.name} · DMX ${p.range[0]}–${p.range[1]}` });
      const sw = programSwatch(p);
      if (sw) b.append(el("i", { className: "sw" }));
      if (sw) b.lastChild.style.background = sw;
      b.append(el("span", { textContent: label }));
      b.dataset.n = p.n;
      b.onclick = () => send({ cmd: "preset", ids: presetTargets().map((f) => f.id), n: p.n });
      box.append(b);
    }
    grid.append(box);
  }
}

function renderPresets() {
  if (!S) return;
  buildPresets();
  const targets = presetTargets();
  setPane(colorPane);
  if (!targets.length) return;
  const used = new Map();
  for (const f of targets) if (f.preset) used.set(f.preset, (used.get(f.preset) || 0) + 1);
  $("#presetGrid").querySelectorAll("button[data-n]").forEach((b) => {
    const c = used.get(+b.dataset.n) || 0;
    b.classList.toggle("on", c > 0 && c === targets.length);
    b.classList.toggle("part", c > 0 && c < targets.length);
  });
  $("#presetOff").disabled = !targets.some((f) => f.preset);
  if (activeSlider !== "presetSpeed") {
    $("#presetSpeed").value = targets[0].speed ?? 128;
    $("#presetSpeedVal").textContent = Math.round(($("#presetSpeed").value / 255) * 100) + "%";
  }
}

// ---------------------------------------------------- статичні кольори ---
let staticEditing = false;

function renderStatic() {
  const grid = $("#staticGrid");
  grid.classList.toggle("editing", staticEditing);
  $("#staticEdit").textContent = staticEditing ? "Готово" : "Редагувати";
  $("#staticReset").hidden = !staticEditing;
  grid.replaceChildren(...S.static_colors.map((c, index) => {
    const b = el("button", { className: "static-btn" + (c.w ? " w" : ""), title: c.name, textContent: c.name });
    b.dataset.index = index;
    b.style.background = c.hex;
    if (c.w) b.style.background = `linear-gradient(135deg, ${c.hex} 60%, #fff)`;
    // темний текст на світлих кольорах
    const [r, g, bl] = fromHex(c.hex);
    if (0.299 * r + 0.587 * g + 0.114 * bl > 170) { b.style.color = "#111"; b.style.textShadow = "none"; }
    b.onclick = () => {
      if (staticEditing) return;
      lastColor = c.hex;
      send({ cmd: "static_color", index, ids: [...selected] });
    };
    const del = el("span", { className: "del", textContent: "×", title: "Видалити" });
    del.onclick = (e) => { e.stopPropagation(); send({ cmd: "delete_static_color", index }); };
    b.append(del);
    return b;
  }));
}

function clearColors() {
  send({ cmd: "clear", ids: [...selected] });
}

function bindStatic() {
  $("#clearColors").onclick = clearColors;
  $("#staticEdit").onclick = () => { staticEditing = !staticEditing; renderStatic(); };
  $("#staticReset").onclick = () => uiConfirm("Власні кольори буде видалено.", { title: "Повернути стандартний набір кольорів?", ok: "Повернути" })
    .then((ok) => ok && send({ cmd: "reset_static_colors" }));
  $("#staticAdd").onclick = () => {
    const f = selItems()[0] && itemColor(selItems()[0]);
    if (!f) return toast("Виберіть прилад і налаштуйте колір, який хочете зберегти");
    uiPrompt("Назва кольору", "Мій колір").then((name) => {
      if (name === null) return;
      send({ cmd: "add_static_color", name, hex: toHex(f.r, f.g, f.b), w: f.w });
    });
  };
}

// ------------------------------------------------------------- ефекти -----
const speedFromSlider = (x) => 0.05 * Math.pow(10, x / 40);
const sliderFromSpeed = (s) => Math.round(40 * Math.log10(s / 0.05));

function renderEffects() {
  const sel = $("#effType");
  if (!sel.options.length) {
    for (const [k, v] of Object.entries(S.effects)) if (k !== "none") sel.append(el("option", { value: k, textContent: v }));
  }
  const e = S.effect;
  if (e.type !== "none") sel.value = e.type;
  // поки ефект не запущено, повзунки належать користувачу — не скидаємо їх оновленнями стану
  if (e.type !== "none" || !renderEffects.synced) {
    $("#effSpeed").value = sliderFromSpeed(e.speed);
    $("#effSpread").value = Math.round(e.spread * 100);
    $("#effBySeg").checked = e.by_segment !== false;
    renderEffects.synced = true;
  }
  updateEffLabels();
  $("#effectState").textContent = e.type !== "none" ? `▶ ${S.effects[e.type]} · ${e.ids.length} прил.` : "";
  renderEffColors();
}

function updateEffLabels() {
  const hz = speedFromSlider(+$("#effSpeed").value);
  $("#effSpeedVal").textContent = $("#effSpeed").value + "%";
  const hzText = `${hz.toFixed(2)} Гц — ${hz >= 1 ? hz.toFixed(1) + " циклів за секунду" : "один цикл за " + (1 / hz).toFixed(1) + " с"}`;
  $("#effSpeedVal").title = hzText;
  $("#effSpeed").title = hzText;
  $("#effSpreadVal").textContent = $("#effSpread").value + "%";
}

function renderEffColors() {
  $("#effColors").replaceChildren(...effColors.map((c, i) => {
    const s = el("span", { title: `${c} — клік, щоб прибрати` });
    s.style.background = c;
    s.onclick = () => { effColors.splice(i, 1); renderEffColors(); liveEffectUpdate(); };
    return s;
  }));
}

function effectParams() {
  return {
    speed: +speedFromSlider(+$("#effSpeed").value).toFixed(3),
    spread: +$("#effSpread").value / 100,
    colors: effColors,
    by_segment: $("#effBySeg").checked,
  };
}

function liveEffectUpdate() {
  if (S.effect.type !== "none") sendThrottled("effect", { cmd: "set_effect", ...effectParams() });
}

function bindEffects() {
  $("#effBySeg").addEventListener("change", liveEffectUpdate);
  for (const id of ["#effSpeed", "#effSpread"]) {
    $(id).addEventListener("input", () => { updateEffLabels(); liveEffectUpdate(); });
  }
  $("#effAddColor").onclick = () => {
    const f = selItems()[0] && itemColor(selItems()[0]);
    effColors.push(f && (f.r || f.g || f.b) ? toHex(f.r, f.g, f.b) : lastColor);
    renderEffColors();
    liveEffectUpdate();
  };
  $("#effApply").onclick = () => {
    const picked = [...new Set(selItems().map((i) => i.f.id))];
    const ids = picked.length ? picked : S.fixtures.map((f) => f.id);
    send({ cmd: "set_effect", type: $("#effType").value, ids, ...effectParams() });
  };
  $("#effStop").onclick = () => send({ cmd: "set_effect", type: "none" });
}

// -------------------------------------------------------------- сцени -----
function renderScenes() {
  const list = $("#sceneList");
  const names = Object.keys(S.scenes);
  if (!names.length) return list.replaceChildren(el("li", { className: "info", textContent: "Збережених сцен немає" }));
  list.replaceChildren(...names.map((name) => {
    const li = el("li", {},
      el("button", { className: "btn", textContent: "▶ " + name,
        onclick: () => send({ cmd: "recall_scene", name, fade: +$("#sceneFade").value || 0 }) }),
      el("button", { className: "btn small", textContent: "✕", title: "Видалити",
        onclick: () => uiConfirm("", { title: `Видалити сцену «${name}»?`, ok: "Видалити", danger: true })
          .then((ok) => ok && send({ cmd: "delete_scene", name })) }));
    li.dataset.name = name;
    return li;
  }));
}

function bindScenes() {
  $("#sceneSave").onclick = () => {
    const name = $("#sceneName").value.trim();
    if (!name) return toast("Вкажіть назву сцени");
    send({ cmd: "save_scene", name, with_effect: $("#sceneWithEffect").checked });
    $("#sceneName").value = "";
  };
}

// --------------------------------------------------------- налаштування ---
function renderSettings() {
  // вихід
  const o = S.output_cfg;
  if (!$("#settings").open || !renderSettings.outputTouched) {
    $("#outType").value = o.type || "udmx";
    $("#outPort").value = o.port || "";
    $("#outHost").value = o.host || "";
    $("#outUniverse").value = o.universe ?? (o.type === "sacn" ? 1 : 0);
    toggleOutFields();
  }
  // профілі в селектах
  const profNames = Object.keys(S.profiles);
  const addSel = $("#addProfile");
  const keep = addSel.value;
  addSel.replaceChildren(...profNames.map((p) => el("option", { value: p, textContent: p })));
  if (profNames.includes(keep)) addSel.value = keep;
  // наступна вільна адреса
  const end = Math.max(0, ...S.fixtures.map((f) => f.address + S.profiles[f.profile].length - 1));
  addSel.onchange = updateAddInfo;

  // патч
  const overlapIds = new Set(S.overlaps.flat());
  $("#patchBody").replaceChildren(...S.fixtures.map((f) => {
    const name = el("input", { value: f.name });
    name.onchange = () => send({ cmd: "update_fixture", id: f.id, name: name.value });
    const addr = el("input", { type: "number", min: 1, max: 512, value: f.address });
    addr.onchange = () => send({ cmd: "update_fixture", id: f.id, address: +addr.value });
    const prof = el("select", {}, ...profNames.map((p) => el("option", { value: p, textContent: p })));
    prof.value = f.profile;
    prof.onchange = () => send({ cmd: "update_fixture", id: f.id, profile: prof.value });
    const tr = el("tr", { className: overlapIds.has(f.id) ? "overlap" : "" },
      el("td", {}, name), el("td", {}, addr), el("td", {}, prof),
      el("td", { className: "muted", textContent: S.profiles[f.profile].join(" ") }),
      el("td", { className: "ops" },
        el("button", { className: "btn small", textContent: "↑", onclick: () => send({ cmd: "move_fixture", id: f.id, delta: -1 }) }),
        el("button", { className: "btn small", textContent: "↓", onclick: () => send({ cmd: "move_fixture", id: f.id, delta: 1 }) }),
        el("button", { className: "btn small", textContent: "✕", title: "Видалити",
          onclick: () => deleteFixtures([f.id]) })));
    return tr;
  }));
  const warn = $("#overlapWarn");
  warn.hidden = !S.overlaps.length;
  const nameOf = (id) => S.fixtures.find((f) => f.id === id)?.name;
  warn.textContent = "⚠ Перетин адрес: " + S.overlaps.map(([a, b]) => `${nameOf(a)} ↔ ${nameOf(b)}`).join(", ");

  // профілі
  $("#profileList").replaceChildren(...profNames.map((p) => el("li", {},
    el("strong", { textContent: p }),
    el("span", { className: "chs", textContent: S.profiles[p].join(", ") }),
    el("button", { className: "btn small", textContent: "Змінити", onclick: () => {
      $("#profName").value = p; $("#profChannels").value = S.profiles[p].join(", ");
    } }),
    el("button", { className: "btn small", textContent: "✕", onclick: () => send({ cmd: "delete_profile", name: p }) }))));
}

// --------------------------------------------------- властивості приладу ---
let propId = null;

function openProps(id) {
  const f = S.fixtures.find((x) => x.id === id);
  if (!f) return;
  propId = id;
  renderSettings();
  const sel = $("#propProfile");
  sel.replaceChildren(...Object.keys(S.profiles).map((p) => el("option", { value: p, textContent: p })));
  sel.value = f.profile;
  $("#propName").value = f.name;
  $("#propAddress").value = f.address;
  $("#propDimmer").value = f.dimmer;
  $("#propPresets").checked = (S.preset_fixtures || []).includes(f.id);
  updatePropInfo();
  $("#propDlg").showModal();
}

function updatePropInfo() {
  const f = S.fixtures.find((x) => x.id === propId);
  if (!f) return;
  const ch = S.profiles[$("#propProfile").value] || [];
  const start = +$("#propAddress").value || 1;
  const end = start + ch.length - 1;
  const n = Math.max(1, ...["r", "g", "b"].map((c) => ch.filter((x) => x === c).length));
  $("#propDimmerVal").textContent = Math.round((+$("#propDimmer").value / 255) * 100) + "%";
  $("#propInfo").textContent = `Адреси ${start}–${end} · ${ch.length} кан.${n > 1 ? ` · ${n} сегм.` : ""} · ${ch.join(" ")}`;
  const clash = S.fixtures.filter((o) => o.id !== f.id).filter((o) => {
    const oe = o.address + S.profiles[o.profile].length - 1;
    return start <= oe && o.address <= end;
  });
  const warn = end > 512 ? "Прилад виходить за межі 512 каналів."
    : clash.length ? "Адреси перетинаються з: " + clash.map((o) => o.name).join(", ") : "";
  $("#propWarn").hidden = !warn;
  $("#propWarn").textContent = warn ? "⚠ " + warn : "";
}

// ------------------------------------------------------------ тест каналів ---
const TEST_ROLES = [
  ["r", "Червоний"], ["g", "Зелений"], ["b", "Синій"], ["w", "Білий"], ["a", "Бурштин"], ["uv", "УФ"],
  ["dim", "Диммер"], ["strobe", "Строб"], ["macro", "Програма (пресет)"], ["speed", "Швидкість програми"],
  ["zero", "Не використ. (0)"], ["full", "Завжди 255"],
  ["fixed", "Фіксоване значення"],
];
const tested = new Set();   // адреси, якими зараз керує тест

function buildTestRows() {
  const f = S.fixtures.find((x) => x.id === propId);
  if (!f) return;
  const prof = S.profiles[$("#propProfile").value] || [];
  const start = +$("#propAddress").value || f.address;
  const count = Math.max(1, Math.min(64, +$("#testCount").value || prof.length));
  const prev = [...$("#testRows").children].map((r) => ({ role: r.querySelector("select").value, v: r.querySelector("input").value }));
  $("#testRows").replaceChildren();
  for (let i = 0; i < count; i++) {
    const addr = start + i;
    if (addr > 512) break;
    let role = prev[i]?.role ?? (prof[i] || "zero");
    let value = prev[i]?.v ?? lastDmx[addr - 1] ?? 0;
    if (!prev[i] && role.startsWith("=")) { value = +role.slice(1); role = "fixed"; }
    const sel = el("select", {}, ...TEST_ROLES.map(([k, t]) => el("option", { value: k, textContent: t })));
    sel.value = TEST_ROLES.some(([k]) => k === role) ? role : "zero";
    const range = el("input", { type: "range", min: 0, max: 255, value });
    const out = el("output", { textContent: value });
    const row = el("div", { className: "test-row" + (tested.has(addr) ? " live" : "") },
      el("span", { className: "ch", innerHTML: `<b>CH${i + 1}</b> · DMX ${addr}` }), sel, range, out);
    range.addEventListener("input", () => {
      out.textContent = range.value;
      tested.add(addr);
      row.classList.add("live");
      sendThrottled("raw" + addr, { cmd: "raw_set", address: addr, value: +range.value });
    });
    $("#testRows").append(row);
  }
}

function releaseTest() {
  if (tested.size) send({ cmd: "raw_clear", addresses: [...tested] });
  tested.clear();
  for (const r of $("#testRows").children) r.classList.remove("live");
}

function bindTest() {
  $("#propTest").addEventListener("toggle", () => {
    if ($("#propTest").open) {
      const prof = S.profiles[$("#propProfile").value] || [];
      if (!$("#testCount").value) $("#testCount").value = prof.length;
      if (!$("#testProfName").value) {
        const f = S.fixtures.find((x) => x.id === propId);
        $("#testProfName").value = `${f ? f.name : "Прилад"} (власний)`;
      }
      buildTestRows();
    }
  });
  $("#testCount").addEventListener("change", buildTestRows);
  $("#propProfile").addEventListener("change", () => {
    $("#testCount").value = (S.profiles[$("#propProfile").value] || []).length;
    $("#testRows").replaceChildren();
    if ($("#propTest").open) buildTestRows();
  });
  $("#testZero").onclick = () => {
    for (const r of $("#testRows").children) {
      const range = r.querySelector("input");
      range.value = 0;
      range.dispatchEvent(new Event("input"));
    }
  };
  $("#testRelease").onclick = releaseTest;
  $("#testSave").onclick = () => {
    const rows = [...$("#testRows").children];
    if (!rows.length) return toast("Немає каналів для збереження");
    const channels = rows.map((r) => {
      const role = r.querySelector("select").value;
      return role === "fixed" ? "=" + r.querySelector("input").value : role;
    });
    const name = $("#testProfName").value.trim();
    if (!name) return toast("Вкажіть назву профілю");
    send({ cmd: "update_fixture", id: propId, address: +$("#propAddress").value });
    send({ cmd: "save_profile", name, channels, assign_to: propId });
    releaseTest();
    $("#propDlg").close();
    toast(`Профіль «${name}» збережено і призначено: ${channels.join(" ")}`, true);
  };
  // закриття вікна властивостей повертає канали програмі
  $("#propDlg").addEventListener("close", () => {
    releaseTest();
    $("#propTest").open = false;
    $("#testRows").replaceChildren();
    $("#testCount").value = "";
    $("#testProfName").value = "";
  });
}

function duplicateFixture(id) {
  const f = S.fixtures.find((x) => x.id === id);
  if (!f) return;
  addPending = S.fixtures.length;
  send({ cmd: "add_fixture", name: f.name + " (копія)", profile: f.profile, address: nextFreeAddress(), count: 1 });
}

function deleteFixtures(ids) {
  const names = S.fixtures.filter((f) => ids.includes(f.id)).map((f) => f.name);
  if (!names.length) return Promise.resolve(false);
  return uiConfirm(names.join(", "), { title: names.length > 1 ? `Видалити прилади (${names.length})?` : "Видалити прилад?",
                                        ok: "Видалити", danger: true }).then((ok) => {
    if (!ok) return false;
    for (const id of ids) send({ cmd: "delete_fixture", id });
    ids.forEach((id) => selected.delete(id));
    return true;
  });
}

function bindProps() {
  for (const id of ["#propProfile", "#propAddress", "#propDimmer"]) $(id).addEventListener("input", updatePropInfo);
  $("#propDimmer").addEventListener("input", () =>
    sendThrottled("color", { cmd: "set_color", ids: [propId], dimmer: +$("#propDimmer").value }));
  $("#propSave").onclick = () => {
    send({ cmd: "update_fixture", id: propId, name: $("#propName").value.trim() || "Прилад",
           address: +$("#propAddress").value, profile: $("#propProfile").value,
           presets: $("#propPresets").checked });
    $("#propDlg").close();
  };
  $("#propDup").onclick = () => { $("#propDlg").close(); duplicateFixture(propId); };
  $("#propDelete").onclick = () => deleteFixtures([propId]).then((ok) => ok && $("#propDlg").close());
}

// ---------------------------------------------------- контекстне меню -----
function showMenu(x, y, items) {
  const menu = $("#ctxMenu");
  menu.replaceChildren();
  for (const it of items) {
    if (!it) continue;
    if (it.sep) { menu.append(el("div", { className: "sep" })); continue; }
    if (it.title) { menu.append(el("div", { className: "title", textContent: it.title })); continue; }
    if (it.colors) {
      const box = el("div", { className: "chips" });
      for (const [i, c] of S.static_colors.entries()) {
        const b = el("button", { title: c.name });
        b.style.background = c.w ? `linear-gradient(135deg, ${c.hex} 55%, #fff)` : c.hex;
        b.onclick = () => { hideMenu(); it.colors(i); };
        box.append(b);
      }
      menu.append(box);
      continue;
    }
    const btn = el("button", { className: "item" + (it.danger ? " danger" : ""), disabled: !!it.disabled },
      el("span", { className: "ico", textContent: it.icon || "" }),
      el("span", { textContent: it.label }),
      el("span", { className: "key", textContent: it.key || "" }));
    btn.setAttribute("role", "menuitem");
    btn.onclick = () => { hideMenu(); it.action(); };
    menu.append(btn);
  }
  hostLayer(menu);
  try { menu.hidePopover(); menu.showPopover(); } catch { /* ignore */ }
  // не виходити за межі вікна
  const r = menu.getBoundingClientRect();
  menu.style.left = Math.max(4, Math.min(x, innerWidth - r.width - 4)) + "px";
  menu.style.top = Math.max(4, Math.min(y, innerHeight - r.height - 4)) + "px";
  menu.querySelector(".item:not(:disabled)")?.focus({ preventScroll: true });
}

function menuOpen() { return $("#ctxMenu").matches(":popover-open"); }
function hideMenu() { try { $("#ctxMenu").hidePopover(); } catch { /* ignore */ } }

function fixtureMenu(id) {
  const [fid, seg] = id.split("#");
  const f = S.fixtures.find((x) => x.id === fid);
  if (!f) return [];
  // правий клік по невибраному елементу вибирає лише його (як у провіднику)
  if (!selected.has(id)) { selected.clear(); selected.add(id); refreshSelection(); syncSliders(); }
  const ids = [...selected];
  const items = selItems();
  const whole = [...new Set(items.filter((i) => i.seg === null).map((i) => i.f.id))];
  const fixturesInSel = [...new Set(items.map((i) => i.f.id))];
  const inEffect = fixturesInSel.some((x) => S.effect.type !== "none" && S.effect.ids.includes(x));
  const effName = S.effects[$("#effType").value];
  const head = items.length > 1 ? `Вибрано: ${selDescription(items)}`
    : seg !== undefined ? `${f.name} · сегмент ${+seg + 1}` : f.name;
  return [
    { title: head },
    { colors: (index) => send({ cmd: "static_color", index, ids }) },
    { icon: "⌫", label: "Очистити колір", key: "Del", action: () => send({ cmd: "clear", ids }) },
    { sep: true },
    { icon: "▶", label: `Запустити ефект «${effName}»`, action: () =>
        send({ cmd: "set_effect", type: $("#effType").value, ids: fixturesInSel, ...effectParams() }) },
    inEffect && { icon: "■", label: "Зупинити ефект", action: () => {
        const rest = S.effect.ids.filter((x) => !fixturesInSel.includes(x));
        send(rest.length ? { cmd: "set_effect", ids: rest } : { cmd: "set_effect", type: "none" });
      } },
    { sep: true },
    seg !== undefined && items.length === 1 && { icon: "▭", label: "Вибрати весь прилад", action: () => pick(fid, false) },
    { icon: "≡", label: "Вибрати всі такі самі прилади", action: () => {
        selected.clear();
        S.fixtures.filter((x) => x.profile === f.profile).forEach((x) => selected.add(x.id));
        refreshSelection(); syncSliders();
      } },
    (S.preset_fixtures || []).some((x) => fixturesInSel.includes(x)) && { icon: "▦", label: "Пресети", action: openPresets },
    fixturesInSel.length === 1 && { icon: "⚙", label: "Властивості…", key: "2×клік", action: () => openProps(fid) },
    fixturesInSel.length === 1 && { icon: "⧉", label: "Дублювати", action: () => duplicateFixture(fid) },
    whole.length > 0 && { sep: true },
    whole.length > 0 && { icon: "✕", label: whole.length > 1 ? `Видалити прилади (${whole.length})` : "Видалити прилад",
      danger: true, action: () => deleteFixtures(whole) },
  ];
}

let colorClipboard = null;

function firstSelColor() {
  const it = selItems()[0];
  if (!it) return null;
  const c = itemColor(it);
  return { hex: toHex(c.r, c.g, c.b), w: c.w || 0 };
}

function colorMenu() {
  const has = selected.size > 0;
  const ids = [...selected];
  const cur = firstSelColor();
  return [
    { title: has ? `Колір · вибрано ${selDescription(selItems())}` : "Колір · нічого не вибрано" },
    has && { colors: (index) => send({ cmd: "static_color", index, ids }) },
    { icon: "⧉", label: "Копіювати колір", disabled: !cur, action: () => {
        colorClipboard = cur; toast(`Скопійовано ${cur.hex}`, true);
      } },
    { icon: "📋", label: colorClipboard ? `Вставити колір ${colorClipboard.hex}` : "Вставити колір",
      disabled: !colorClipboard || !has,
      action: () => send({ cmd: "set_color", ids, hex: colorClipboard.hex, w: colorClipboard.w }) },
    { sep: true },
    { icon: "☀", label: "Яскравість 100%", disabled: !has, action: () => send({ cmd: "set_color", ids, dimmer: 255 }) },
    { icon: "½", label: "Яскравість 50%", disabled: !has, action: () => send({ cmd: "set_color", ids, dimmer: 128 }) },
    { sep: true },
    { icon: "★", label: "Зберегти як статичний колір…", disabled: !cur, action: () => $("#staticAdd").click() },
    { icon: "⌫", label: has ? "Очистити вибрані" : "Очистити все", key: "Del", action: clearColors },
  ];
}

function staticMenu(index) {
  const ids = [...selected];
  const c = index !== null ? S.static_colors[index] : null;
  return [
    c ? { title: `Статичний колір · ${c.name}` } : { title: "Статичні кольори" },
    c && { icon: "●", label: selected.size ? "Застосувати до вибраних" : "Застосувати до всіх",
      key: index < 9 ? String(index + 1) : "", action: () => send({ cmd: "static_color", index, ids }) },
    c && selected.size > 0 && { icon: "◎", label: "Застосувати до всіх приладів",
      action: () => send({ cmd: "static_color", index, ids: [] }) },
    c && { icon: "✎", label: "Перейменувати…", action: () => {
        uiPrompt("Нова назва кольору", c.name).then((name) => {
          if (name && name.trim()) send({ cmd: "rename_static_color", index, name: name.trim() });
        });
      } },
    c && { icon: "✕", label: "Видалити колір", danger: true, action: () =>
        uiConfirm("", { title: `Видалити колір «${c.name}»?`, ok: "Видалити", danger: true })
          .then((ok) => ok && send({ cmd: "delete_static_color", index })) },
    c && { sep: true },
    { icon: "★", label: "Зберегти поточний колір…", disabled: !firstSelColor(), action: () => $("#staticAdd").click() },
    { icon: "✎", label: staticEditing ? "Завершити редагування" : "Редагувати набір", action: () => $("#staticEdit").click() },
    { icon: "↺", label: "Скинути до стандартних", action: () =>
        uiConfirm("Власні кольори буде видалено.", { title: "Повернути стандартний набір кольорів?", ok: "Повернути" })
          .then((ok) => ok && send({ cmd: "reset_static_colors" })) },
    { sep: true },
    { icon: "⌫", label: selected.size ? "Очистити вибрані прилади" : "Очистити всі прилади", key: "Del", action: clearColors },
  ];
}

function effectMenu() {
  const running = S.effect.type !== "none";
  const effName = S.effects[$("#effType").value];
  const picked = [...new Set(selItems().map((i) => i.f.id))];
  return [
    { title: running ? `Ефект · ${S.effects[S.effect.type]} (${S.effect.ids.length} прил.)` : "Ефекти" },
    picked.length > 0 && { icon: "▶", label: `«${effName}» на вибраних`, action: () => $("#effApply").click() },
    { icon: "▶", label: `«${effName}» на всіх приладах`, disabled: !S.fixtures.length, action: () =>
        send({ cmd: "set_effect", type: $("#effType").value, ids: S.fixtures.map((f) => f.id), ...effectParams() }) },
    running && { icon: "■", label: "Зупинити ефект", action: () => send({ cmd: "set_effect", type: "none" }) },
    { sep: true },
    { icon: "＋", label: "Додати поточний колір у палітру", action: () => $("#effAddColor").click() },
    effColors.length > 0 && { icon: "⌫", label: "Очистити палітру", action: () => {
        effColors.length = 0; renderEffColors(); liveEffectUpdate();
      } },
  ];
}

function sceneMenu(name) {
  const fade = +$("#sceneFade").value || 0;
  return [
    { title: name ? `Сцена · ${name}` : "Сцени" },
    name && { icon: "▶", label: fade ? `Викликати (перехід ${fade} с)` : "Викликати", action: () => send({ cmd: "recall_scene", name, fade }) },
    name && fade > 0 && { icon: "⚡", label: "Викликати миттєво", action: () => send({ cmd: "recall_scene", name, fade: 0 }) },
    name && { icon: "⟳", label: "Перезаписати поточним станом", action: () =>
        uiConfirm("", { title: `Перезаписати сцену «${name}» поточними кольорами?`, ok: "Перезаписати" })
          .then((ok) => ok && send({ cmd: "save_scene", name, with_effect: $("#sceneWithEffect").checked })) },
    name && { icon: "✕", label: "Видалити сцену", danger: true, action: () =>
        uiConfirm("", { title: `Видалити сцену «${name}»?`, ok: "Видалити", danger: true })
          .then((ok) => ok && send({ cmd: "delete_scene", name })) },
    name && { sep: true },
    { icon: "＋", label: "Зберегти нову сцену…", action: () => {
        uiPrompt("Назва сцени", "").then((n) => {
          if (n && n.trim()) send({ cmd: "save_scene", name: n.trim(), with_effect: $("#sceneWithEffect").checked });
        });
      } },
  ];
}

// меню для текстових полів: вирізати / копіювати / вставити / виділити все
function inputMenu(inp) {
  const hasSel = inp.selectionStart !== inp.selectionEnd && inp.type !== "number";
  const editable = !inp.readOnly && !inp.disabled;
  const selText = () => inp.value.slice(inp.selectionStart ?? 0, inp.selectionEnd ?? 0);
  const insert = (text) => {
    inp.focus();
    if (inp.type === "number") inp.value = text.trim();
    else inp.setRangeText(text, inp.selectionStart, inp.selectionEnd, "end");
    inp.dispatchEvent(new Event("input", { bubbles: true }));
  };
  return [
    { icon: "✂", label: "Вирізати", key: "Ctrl+X", disabled: !hasSel || !editable, action: () => {
        navigator.clipboard?.writeText(selText()); insert("");
      } },
    { icon: "⧉", label: "Копіювати", key: "Ctrl+C", disabled: !hasSel && inp.type !== "number",
      action: () => navigator.clipboard?.writeText(inp.type === "number" ? inp.value : selText()) },
    { icon: "📋", label: "Вставити", key: "Ctrl+V", disabled: !editable, action: () =>
        navigator.clipboard?.readText().then(insert).catch(() => toast("Немає доступу до буфера обміну")) },
    { sep: true },
    { icon: "☰", label: "Виділити все", key: "Ctrl+A", action: () => { inp.focus(); inp.select(); } },
  ];
}

function fixturesPanelMenu() {
  return [
    { title: "Прилади" },
    { icon: "＋", label: "Додати прилад…", action: openAdd },
    S.fixtures.length > 0 && { icon: "☰", label: "Вибрати всі прилади", key: "Ctrl+A", action: () => $("#selAll").click() },
    selected.size > 0 && { icon: "○", label: "Зняти вибір", key: "Esc", action: () => $("#selNone").click() },
    S.fixtures.length > 0 && { icon: "⇄", label: "Інвертувати вибір", action: () => $("#selInvert").click() },
    { sep: true },
    { icon: "⌫", label: selected.size ? "Очистити вибрані" : "Очистити всі кольори", key: "Del", action: clearColors },
    { icon: "▤", label: "Патч приладів…", action: () => {
        $("#openSettings").click(); document.querySelector(".tabs button[data-tab=tabPatch]").click();
      } },
  ];
}

const UNDO_NAMES = {
  set_color: "зміну кольору", static_color: "статичний колір", clear: "очищення", preset: "пресет",
  set_master: "майстер", blackout: "Blackout", set_effect: "зміну ефекту", add_fixture: "додавання приладу",
  update_fixture: "зміну приладу", delete_fixture: "видалення приладу", move_fixture: "переміщення приладу",
  save_scene: "збереження сцени", recall_scene: "виклик сцени", delete_scene: "видалення сцени",
  save_profile: "збереження профілю", delete_profile: "видалення профілю", add_static_color: "новий колір",
  delete_static_color: "видалення кольору", rename_static_color: "перейменування кольору",
  reset_static_colors: "скидання кольорів",
};
const undoName = (c) => UNDO_NAMES[c] || "дію";

let pendingUndo = null;
function undo() { pendingUndo = "undo"; send({ cmd: "undo" }); }
function redo() { pendingUndo = "redo"; send({ cmd: "redo" }); }

function generalMenu() {
  const u = updateInfo || {};
  return [
    { icon: "↶", label: S.undo ? `Скасувати ${undoName(S.undo)}` : "Скасувати", key: "Ctrl+Z", disabled: !S.undo, action: undo },
    { icon: "↷", label: S.redo ? `Повторити ${undoName(S.redo)}` : "Повторити", key: "Ctrl+Y", disabled: !S.redo, action: redo },
    { sep: true },
    { icon: "＋", label: "Додати прилад…", action: openAdd },
    S.fixtures.length > 0 && { icon: "☰", label: "Вибрати всі прилади", key: "Ctrl+A", action: () => $("#selAll").click() },
    selected.size > 0 && { icon: "○", label: "Зняти вибір", key: "Esc", action: () => $("#selNone").click() },
    { sep: true },
    { icon: "⌫", label: "Очистити всі кольори", action: () => send({ cmd: "clear", ids: [] }) },
    S.effect.type !== "none" && { icon: "■", label: "Зупинити всі ефекти", action: () => send({ cmd: "set_effect", type: "none" }) },
    { icon: "◐", label: S.blackout ? "Вимкнути Blackout" : "Blackout", key: "B", action: () => send({ cmd: "blackout" }) },
    { sep: true },
    u.available && !u.blocked && { icon: "⬆", label: `Оновити до ${u.latest}…`, action: openUpdateDialog },
    !(u.available && !u.blocked) && { icon: "⟳", label: "Перевірити оновлення", action: () => send({ cmd: "check_update" }) },
    { icon: "⚙", label: "Налаштування", action: () => $("#openSettings").click() },
  ];
}

function bindContextMenu() {
  // заборона виділення тексту поза полями введення (і міні-меню браузера разом з ним)
  document.addEventListener("selectstart", (e) => {
    const t = e.target instanceof Element ? e.target : e.target.parentElement;
    if (!t || !t.closest("input, textarea, [contenteditable]")) e.preventDefault();
  });
  document.addEventListener("contextmenu", (e) => {
    e.preventDefault();  // меню браузера не показуємо ніде
    const target = e.target instanceof Element ? e.target : document.body;
    if (target.matches("input:not([type=range]):not([type=checkbox]), textarea")) {
      return showMenu(e.clientX, e.clientY, inputMenu(target));
    }
    if (!S || document.querySelector("dialog:modal")) return hideMenu();
    const cell = e.target.closest(".lamp.bar span");
    const tile = e.target.closest(".fx");
    const zone = e.target.closest("[data-zone]")?.dataset.zone;
    let items;
    if (cell && tile) {
      const k = [...cell.parentNode.children].indexOf(cell);
      items = fixtureMenu(`${tile.dataset.id}#${k}`);
    } else if (tile) {
      items = fixtureMenu(tile.dataset.id);
    } else if (zone === "fixtures") {
      items = fixturesPanelMenu();
    } else if (zone === "color") {
      const sc = target.closest("#sceneList li[data-name]");
      if (sc) items = sceneMenu(sc.dataset.name);
      else if (target.closest("[data-block=scenes]")) items = sceneMenu(null);
      else items = colorMenu();
    } else if (zone === "side") {
      // права колонка містить три блоки: статичні кольори, ефекти, сцени
      const st = e.target.closest(".static-btn");
      const sc = e.target.closest("#sceneList li[data-name]");
      const block = e.target.closest("[data-block]")?.dataset.block;
      if (st) items = staticMenu(+st.dataset.index);
      else if (sc) items = sceneMenu(sc.dataset.name);
      else if (block === "effects") items = effectMenu();
      else items = staticMenu(null);
    } else {
      items = generalMenu();
    }
    showMenu(e.clientX, e.clientY, items);
  });
  document.addEventListener("pointerdown", (e) => {
    if (!(e.target instanceof Element && e.target.closest("#ctxMenu"))) hideMenu();
  }, true);
  // Esc при відкритому меню закриває лише меню, а не вікно під ним
  document.addEventListener("cancel", (e) => { if (menuOpen()) { e.preventDefault(); hideMenu(); } }, true);
  addEventListener("blur", hideMenu);
  addEventListener("resize", hideMenu);
  document.addEventListener("scroll", hideMenu, true);
  $("#ctxMenu").addEventListener("keydown", (e) => {
    const items = [...$("#ctxMenu").querySelectorAll(".item:not(:disabled)")];
    const i = items.indexOf(document.activeElement);
    if (e.key === "Escape") { hideMenu(); e.preventDefault(); e.stopPropagation(); }
    if (e.key === "ArrowDown") { e.preventDefault(); items[(i + 1) % items.length]?.focus(); }
    if (e.key === "ArrowUp") { e.preventDefault(); items[(i - 1 + items.length) % items.length]?.focus(); }
  });
}

let addPending = null;

function nextFreeAddress() {
  const end = Math.max(0, ...S.fixtures.map((f) => f.address + S.profiles[f.profile].length - 1));
  return Math.min(512, end + 1);
}

function openAdd() {
  renderSettings();
  $("#addAddress").value = nextFreeAddress();
  $("#addCount").value = 1;
  $("#addName").value = "";
  updateAddInfo();
  $("#addDlg").showModal();
}

function updateAddInfo() {
  const ch = S.profiles[$("#addProfile").value] || [];
  const n = Math.max(1, ...["r", "g", "b"].map((c) => ch.filter((x) => x === c).length));
  const count = Math.max(1, +$("#addCount").value || 1);
  const start = +$("#addAddress").value || 1;
  const last = start + ch.length * count - 1;
  $("#addInfo").textContent = `${ch.length} кан.${n > 1 ? ` · ${n} сегм.` : ""} · канали: ${ch.join(" ")}` +
    ` · займе адреси ${start}–${last}${last > 512 ? " (за межами 512!)" : ""}`;
}

// після успішного додавання — закрити вікно і вибрати новий прилад
function afterState() {
  if (addPending !== null && S.fixtures.length > addPending) {
    const added = S.fixtures.slice(addPending);
    addPending = null;
    $("#addDlg").close();
    selected.clear();
    selected.add(added[0].id);
    renderFixtures();
    syncSliders();
  }
}

function toggleOutFields() {
  const t = $("#outType").value;
  for (const n of document.querySelectorAll("[data-for]")) n.hidden = !n.dataset.for.split(" ").includes(t);
}

function bindSettings() {
  const dlg = $("#settings");
  const open = () => {
    renderSettings.outputTouched = false; renderSettings(); dlg.showModal();
    if ($("#outType").value === "udmx") send({ cmd: "find_udmx" });
  };
  $("#openSettings").onclick = open;
  $("#outputPill").onclick = open;
  for (const b of document.querySelectorAll(".tabs button")) {
    b.onclick = () => {
      document.querySelectorAll(".tabs button, .tab").forEach((x) => x.classList.remove("active"));
      b.classList.add("active");
      $("#" + b.dataset.tab).classList.add("active");
    };
  }
  for (const id of ["#outType", "#outPort", "#outHost", "#outUniverse"]) {
    $(id).addEventListener("input", () => { renderSettings.outputTouched = true; toggleOutFields(); });
  }
  $("#refreshPorts").onclick = () => send({ cmd: "list_ports" });
  $("#findUdmx").onclick = () => send({ cmd: "find_udmx" });
  $("#udmxIndex").addEventListener("input", () => (renderSettings.outputTouched = true));
  $("#outApply").onclick = () => {
    const type = $("#outType").value;
    const cfg = { cmd: "set_output", type };
    if (type === "udmx") cfg.index = +$("#udmxIndex").value || 0;
    if (type === "enttec_pro" || type === "open_dmx") cfg.port = $("#outPort").value.trim();
    if (type === "artnet" || type === "sacn") {
      cfg.host = $("#outHost").value.trim();
      cfg.universe = +$("#outUniverse").value;
    }
    renderSettings.outputTouched = false;
    send(cfg);
  };
  $("#openAdd").onclick = openAdd;
  for (const b of document.querySelectorAll("[data-open-add]")) b.onclick = openAdd;
  $("#addCount").addEventListener("input", updateAddInfo);
  $("#addAddress").addEventListener("input", updateAddInfo);
  $("#addFixture").onclick = () => {
    addPending = S.fixtures.length;
    send({
      cmd: "add_fixture", name: $("#addName").value.trim(), address: +$("#addAddress").value,
      profile: $("#addProfile").value, count: +$("#addCount").value || 1,
    });
  };
  $("#profSave").onclick = () => {
    const channels = $("#profChannels").value.split(/[\s,;]+/).filter(Boolean);
    send({ cmd: "save_profile", name: $("#profName").value.trim(), channels });
  };
}

// ------------------------------------------- введення чисел біля повзунків ---
// Клік по значенню біля повзунка відкриває поле: можна вписати число.
// Якщо значення показано у %, а повзунок має інший діапазон (0..255), число перераховується.
function rangeFor(out) {
  const prev = out.previousElementSibling;
  if (prev && prev.matches("input[type=range]")) return prev;
  return out.parentElement && out.parentElement.querySelector("input[type=range]");
}

function bindEditableOutputs() {
  const mark = () => document.querySelectorAll("output").forEach((o) => {
    if (!o.classList.contains("editable") && rangeFor(o)) {
      o.classList.add("editable");
      if (!o.title) o.title = "Клікніть, щоб ввести значення";
    }
  });
  mark();
  new MutationObserver(mark).observe(document.body, { childList: true, subtree: true });

  document.addEventListener("click", (e) => {
    const out = e.target.closest("output.editable");
    if (!out || out.querySelector("input")) return;
    const range = rangeFor(out);
    if (!range) return;
    e.preventDefault();
    e.stopPropagation();
    const min = +range.min, max = +range.max;
    const isPct = out.textContent.trim().endsWith("%") && max !== 100;
    const shown = parseFloat(out.textContent) || 0;
    const old = out.textContent;
    const inp = el("input", { type: "number", className: "num-edit", value: Math.round(shown),
                              min: isPct ? 0 : min, max: isPct ? 100 : max });
    out.replaceChildren(inp);
    inp.focus();
    inp.select();
    let done = false;
    const finish = (apply) => {
      if (done) return;
      done = true;
      const raw = parseFloat(inp.value);
      out.textContent = old;
      if (!apply || Number.isNaN(raw)) return;
      let v = isPct ? Math.round((raw / 100) * max) : Math.round(raw);
      v = Math.max(min, Math.min(max, v));
      range.value = v;
      range.dispatchEvent(new Event("input", { bubbles: true }));
      range.dispatchEvent(new Event("change", { bubbles: true }));
    };
    inp.addEventListener("keydown", (ev) => {
      ev.stopPropagation();
      if (ev.key === "Enter") finish(true);
      if (ev.key === "Escape") finish(false);
    });
    inp.addEventListener("blur", () => finish(true));
    inp.addEventListener("click", (ev) => ev.stopPropagation());
  }, true);
}

// ------------------------------------------------- заливка повзунків -----
// --p (0..1) задає, наскільки заповнена доріжка; при максимумі — до самого кінця.
function paintRange(r) {
  const min = +r.min || 0, max = r.max === "" ? 100 : +r.max;
  const p = max > min ? (+r.value - min) / (max - min) : 0;
  if (r._p !== p) { r._p = p; r.style.setProperty("--p", p); }
}
function paintAllRanges() { document.querySelectorAll("input[type=range]").forEach(paintRange); }
function bindRangePaint() {
  document.addEventListener("input", (e) => { if (e.target.matches?.("input[type=range]")) paintRange(e.target); }, true);
  // значення змінюються й програмно (оновлення стану) — перефарбовуємо регулярно, це дешево
  setInterval(paintAllRanges, 120);
  paintAllRanges();
}

// ------------------------------------------------------------- старт ------
function init() {
  buildSliders();
  buildSwatches();
  buildWheel();
  bindStatic();
  $("#presetOff").onclick = () => send({ cmd: "preset", ids: presetTargets().map((f) => f.id), n: 0 });
  for (const b of $("#paneTabs").children) b.onclick = () => setPane(b.dataset.pane);
  const sp = $("#presetSpeed");
  sp.addEventListener("pointerdown", () => (activeSlider = "presetSpeed"));
  sp.addEventListener("pointerup", () => (activeSlider = null));
  sp.addEventListener("input", () => {
    $("#presetSpeedVal").textContent = Math.round((sp.value / 255) * 100) + "%";
    sendThrottled("presetSpeed", { cmd: "preset", ids: presetTargets().map((f) => f.id), speed: +sp.value });
  });

  bindEditableOutputs();
  bindRangePaint();
  bindUpdate();
  bindProps();
  bindTest();
  bindContextMenu();
  bindEffects();
  bindScenes();
  bindSettings();
  const mon = $("#monitor");
  for (let i = 0; i < 512; i++) mon.append(el("div", {}, el("i"), el("b", { textContent: i + 1 }), el("span", { textContent: "0" })));

  const master = $("#master");
  master.addEventListener("pointerdown", () => (activeSlider = "master"));
  master.addEventListener("pointerup", () => (activeSlider = null));
  master.addEventListener("input", () => {
    $("#masterVal").textContent = Math.round((master.value / 255) * 100) + "%";
    sendThrottled("master", { cmd: "set_master", value: +master.value });
  });
  $("#blackout").onclick = () => send({ cmd: "blackout" });
  $("#selAll").onclick = () => { selected.clear(); S.fixtures.forEach((f) => selected.add(f.id)); renderFixtures(); syncSliders(); };
  $("#selNone").onclick = () => { selected.clear(); renderFixtures(); syncSliders(); };
  $("#selInvert").onclick = () => {
    const had = new Set(selItems().filter((i) => i.seg === null).map((i) => i.f.id));
    selected.clear();
    S.fixtures.forEach((f) => had.has(f.id) || selected.add(f.id));
    renderFixtures(); syncSliders();
  };
  document.addEventListener("keydown", (e) => {
    const ctrlA = (e.ctrlKey || e.metaKey) && e.code === "KeyA";
    const ctrl = e.ctrlKey || e.metaKey;
    const isUndo = ctrl && e.code === "KeyZ" && !e.shiftKey;
    const isRedo = ctrl && (e.code === "KeyY" || (e.code === "KeyZ" && e.shiftKey));
    // у текстовому полі Ctrl+A виділяє лише його текст (стандартна поведінка)
    const t = e.target instanceof Element ? e.target : document.body;
    if (t.matches("input:not([type=range]):not([type=checkbox]), textarea, [contenteditable]")) return;  // у полях — своє скасування
    if (document.querySelector("dialog:modal") || menuOpen()) {
      if (ctrlA || isUndo || isRedo) e.preventDefault();  // не виділяти текст вікна
      return;
    }
    if (isUndo) { e.preventDefault(); undo(); return; }
    if (isRedo) { e.preventDefault(); redo(); return; }
    if (t.matches("select")) return;
    // e.code — фізична клавіша, тож працює і на українській розкладці
    if (ctrlA) { e.preventDefault(); $("#selAll").click(); return; }
    if (e.ctrlKey || e.metaKey || e.altKey) return;
    if (e.code === "KeyB") send({ cmd: "blackout" });
    if (e.key === "Escape") {
      $("#selNone").click();
    }
    if (e.key === "Delete" || e.key === "Backspace" || e.key === "0") { e.preventDefault(); clearColors(); }
    // 1..9 — швидкий вибір статичного кольору
    if (/^[1-9]$/.test(e.key) && S.static_colors[+e.key - 1]) {
      send({ cmd: "static_color", index: +e.key - 1, ids: [...selected] });
    }
  });
  connect();
}

init();
