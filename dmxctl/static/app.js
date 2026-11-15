"use strict";

const $ = (s, root = document) => root.querySelector(s);
const el = (tag, props = {}, ...kids) => {
  const n = Object.assign(document.createElement(tag), props);
  for (const k of kids) n.append(k);
  return n;
};
// Єдиний набір іконок: 24×24, лінія 2 px, заокруглені кінці (стиль Lucide, ISC).
const ICONS = {
  plus: "M12 5v14M5 12h14",
  x: "M6 6l12 12M18 6L6 18",
  eraser: "M20 20H9L4 15a2 2 0 0 1 0-2.8L13.2 3a2 2 0 0 1 2.8 0l4.9 4.9a2 2 0 0 1 0 2.8L12 19.6M8 10.5l6.5 6.5",
  bulbOff: "M9 18h6M10 21h4M12 3a6 6 0 0 0-3.5 10.9c.6.5 1 1.2 1 2V16h5v-.1c0-.8.4-1.5 1-2A6 6 0 0 0 12 3zM3 3l18 18",
  settings: "M12.2 2h-.4a2 2 0 0 0-2 2v.2a2 2 0 0 1-1 1.7l-.4.3a2 2 0 0 1-2 0l-.2-.1a2 2 0 0 0-2.7.7l-.2.4a2 2 0 0 0 .7 2.7l.2.1a2 2 0 0 1 1 1.7v.5a2 2 0 0 1-1 1.7l-.2.1a2 2 0 0 0-.7 2.7l.2.4a2 2 0 0 0 2.7.7l.2-.1a2 2 0 0 1 2 0l.4.3a2 2 0 0 1 1 1.7v.2a2 2 0 0 0 2 2h.4a2 2 0 0 0 2-2v-.2a2 2 0 0 1 1-1.7l.4-.3a2 2 0 0 1 2 0l.2.1a2 2 0 0 0 2.7-.7l.2-.4a2 2 0 0 0-.7-2.7l-.2-.1a2 2 0 0 1-1-1.7v-.5a2 2 0 0 1 1-1.7l.2-.1a2 2 0 0 0 .7-2.7l-.2-.4a2 2 0 0 0-2.7-.7l-.2.1a2 2 0 0 1-2 0l-.4-.3a2 2 0 0 1-1-1.7V4a2 2 0 0 0-2-2zM12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6z",
  trash: "M3 6h18M8 6V4h8v2M19 6l-1 14H6L5 6M10 11v6M14 11v6",
  copy: "M9 9h11v11H9zM5 15H4V4h11v1",
  clipboard: "M9 3h6v4H9zM8 5H6v16h12V5h-2",
  scissors: "M6 9a3 3 0 1 0 0-6 3 3 0 0 0 0 6zM6 21a3 3 0 1 0 0-6 3 3 0 0 0 0 6zM20 4L8.1 15.9M14.5 14.5L20 20M8.1 8.1L12 12",
  selectAll: "M4 4h16v16H4zM8 12l3 3 5-6",
  play: "M8 5v14l11-7z",
  stop: "M7 7h10v10H7z",
  undo: "M9 14L4 9l5-5M4 9h11a5 5 0 0 1 0 10h-3",
  redo: "M15 14l5-5-5-5M20 9H9a5 5 0 0 0 0 10h3",
  star: "M12 3l2.8 5.7 6.2.9-4.5 4.4 1.1 6.2L12 17.3l-5.6 2.9 1.1-6.2L3 9.6l6.2-.9z",
  edit: "M4 20h4L19 9l-4-4L4 16zM14 6l4 4",
  reset: "M3 12a9 9 0 1 0 3-6.7L3 8M3 3v5h5",
  sun: "M12 16a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4",
  half: "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18zM12 3v18",
  grid: "M4 4h7v7H4zM13 4h7v7h-7zM4 13h7v7H4zM13 13h7v7h-7z",
  layers: "M12 3l9 5-9 5-9-5zM3 13l9 5 9-5",
  list: "M9 6h12M9 12h12M9 18h12M4 6h.01M4 12h.01M4 18h.01",
  circle: "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18z",
  dot: "M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6z",
  swap: "M7 4L3 8l4 4M3 8h14M17 20l4-4-4-4M21 16H7",
  refresh: "M21 12a9 9 0 1 1-3-6.7L21 8M21 3v5h-5",
  arrowUp: "M12 19V5M5 12l7-7 7 7",
  arrowDown: "M12 5v14M19 12l-7 7-7-7",
  download: "M12 3v12M7 10l5 5 5-5M5 21h14",
  wrench: "M14.7 6.3a4 4 0 0 0-5.4 5.4L3 18l3 3 6.3-6.3a4 4 0 0 0 5.4-5.4l-2.5 2.5-2.4-.6-.6-2.4z",
  bolt: "M13 2L4 14h7l-1 8 9-12h-7z",
  power: "M12 2v10M18.4 6.6a9 9 0 1 1-12.8 0",
  check: "M5 12l5 5 9-10",
  alert: "M12 9v4M12 17h.01M10.3 3.9L2 18a2 2 0 0 0 1.7 3h16.6a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z",
};
function icon(name) {
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("viewBox", "0 0 24 24");
  svg.setAttribute("class", "ico");
  svg.setAttribute("aria-hidden", "true");
  const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
  path.setAttribute("d", ICONS[name] || "");
  for (const [k, v] of [["fill", "none"], ["stroke", "currentColor"], ["stroke-width", "2"],
                        ["stroke-linecap", "round"], ["stroke-linejoin", "round"]]) path.setAttribute(k, v);
  svg.append(path);
  return svg;
}
// кнопка з іконкою й текстом (без тексту — квадратна кнопка-іконка)
const ibtn = (name, text, props = {}) => {
  const b = el("button", { type: "button", className: "btn small", ...props }, icon(name));
  if (text) b.append(el("span", { textContent: text }));
  else b.classList.add("icon-btn");
  if (!text && props.title) b.setAttribute("aria-label", props.title);
  return b;
};
function hydrateIcons(root = document) {
  for (const n of root.querySelectorAll("[data-icon]")) {
    if (n.querySelector(":scope > svg.ico")) continue;
    n.prepend(icon(n.dataset.icon));
  }
}
// підтвердження дії: кнопка ненадовго показує «✓ Готово»
function flash(btn, text) {
  if (!btn || btn._flash) return;
  const old = [...btn.childNodes];
  btn._flash = true;
  btn.classList.add("done");
  btn.replaceChildren(icon("check"), el("span", { textContent: text }));
  setTimeout(() => { btn.replaceChildren(...old); btn.classList.remove("done"); btn._flash = false; }, 1400);
}
// колір тексту на кольоровій кнопці — той, що дає більший контраст (WCAG)
function readableText(hex) {
  const lum = fromHex(hex).map((v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4; });
  const L = 0.2126 * lum[0] + 0.7152 * lum[1] + 0.0722 * lum[2];
  return (L + 0.05) / 0.05 >= 1.05 / (L + 0.05) ? "#0b0d10" : "#ffffff";
}
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
    if (quitting) document.title = "__SCDMX_CLOSE__";
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
  } else if (m.type === "open_here") {
    window.open(m.url, "_blank", "noopener");  // інший пристрій у мережі — відкриваємо в ньому самому
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
  $("#effApply").classList.toggle("primary", S.fixtures.length > 0);
  grid.replaceChildren();
  if (!S.fixtures.length) {
    grid.append(el("div", { className: "empty-state" },
      el("div", { textContent: "Приладів ще немає." }),
      Object.assign(ibtn("plus", "Додати прилад", { className: "btn primary" }), { onclick: openAdd })));
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
      el("div", { className: "fx-badge", textContent: f.preset ? programName(f.preset)
        : effIds.has(f.id) ? S.effects[S.effect.type] : "" }));
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
    node.style.boxShadow = glow ? `0 0 ${Math.round((rr + gg + bb) / 90)}px rgba(${rr},${gg},${bb},.5)` : "none";
  };
  for (const tile of document.querySelectorAll(".fx")) {
    const segs = m.live[tile.dataset.id];
    if (!segs) continue;
    const lamp = tile.firstChild;
    if (lamp.classList.contains("bar")) {
      [...lamp.children].forEach((cell, k) => segs[k] && paint(cell, segs[k], false));
    } else {
      paint(lamp, segs[0], true);
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
    row.hidden = !["r", "g", "b", "w", "dimmer"].includes(key);  // решта — лише для приладів з такими каналами
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
  btn.replaceChildren(icon(busy ? "refresh" : failed ? "alert" : "download"), el("span", {
    textContent: busy ? (u.progress || "Оновлення…") : failed ? "Оновлення не вдалося" : `Оновити до ${u.latest}` }));
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
  $("#staticEdit").replaceChildren(icon(staticEditing ? "check" : "edit"),
    el("span", { textContent: staticEditing ? "Готово" : "Редагувати" }));
  $("#staticReset").hidden = !staticEditing;
  grid.replaceChildren(...S.static_colors.map((c, index) => {
    const b = el("button", { className: "static-btn" + (c.w ? " w" : ""), title: c.name, textContent: c.name });
    b.dataset.index = index;
    b.style.background = c.hex;
    if (c.w) b.style.background = `linear-gradient(135deg, ${c.hex} 60%, #fff)`;
    // темний текст на світлих кольорах
    const [r, g, bl] = fromHex(c.hex);
    b.style.color = readableText(c.hex);
    b.onclick = () => {
      if (staticEditing) return;
      lastColor = c.hex;
      send({ cmd: "static_color", index, ids: [...selected] });
    };
    const del = el("span", { className: "del", title: "Видалити" }, icon("x"));
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
  $("#effectState").textContent = e.type !== "none" ? `${S.effects[e.type]} · ${e.ids.length} прил.` : "";
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
    flash($("#effApply"), "Запущено");
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
      Object.assign(ibtn("play", name, { className: "btn" }), {
        onclick: () => send({ cmd: "recall_scene", name, fade: +$("#sceneFade").value || 0 }) }),
      Object.assign(ibtn("trash", "", { title: "Видалити сцену" }), {
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
    flash($("#sceneSave"), "Збережено");
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
        Object.assign(ibtn("arrowUp", "", { title: "Вище" }), { onclick: () => send({ cmd: "move_fixture", id: f.id, delta: -1 }) }),
        Object.assign(ibtn("arrowDown", "", { title: "Нижче" }), { onclick: () => send({ cmd: "move_fixture", id: f.id, delta: 1 }) }),
        Object.assign(ibtn("trash", "", { title: "Видалити прилад" }), {
          onclick: () => deleteFixtures([f.id]) })));
    return tr;
  }));
  const warn = $("#overlapWarn");
  warn.hidden = !S.overlaps.length;
  const nameOf = (id) => S.fixtures.find((f) => f.id === id)?.name;
  warn.textContent = "Перетин адрес: " + S.overlaps.map(([a, b]) => `${nameOf(a)} ↔ ${nameOf(b)}`).join(", ");

  // профілі
  $("#profileList").replaceChildren(...profNames.map((p) => el("li", {},
    el("strong", { textContent: p }),
    el("span", { className: "chs", textContent: S.profiles[p].join(", ") }),
    el("button", { className: "btn small", textContent: "Змінити", onclick: () => {
      $("#profName").value = p; $("#profChannels").value = S.profiles[p].join(", ");
    } }),
    Object.assign(ibtn("trash", "", { title: "Видалити профіль" }), { onclick: () => send({ cmd: "delete_profile", name: p }) }))));
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
  $("#propWarn").textContent = warn;
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
// пункти меню описано символами; показуються вони іконками єдиного набору
const GLYPH_ICON = {
  "⌫": "eraser", "＋": "plus", "▶": "play", "⧉": "copy", "✕": "trash", "☰": "selectAll", "■": "stop",
  "📋": "clipboard", "⟳": "refresh", "✎": "edit", "⚙": "settings", "★": "star", "○": "circle", "⬆": "download",
  "✂": "scissors", "⚡": "bolt", "☀": "sun", "◐": "bulbOff", "●": "dot", "◎": "circle", "▭": "selectAll",
  "▦": "grid", "▤": "layers", "≡": "list", "⇄": "swap", "↺": "reset", "↷": "redo", "↶": "undo", "½": "half",
};

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
      it.icon && GLYPH_ICON[it.icon] ? icon(GLYPH_ICON[it.icon]) : el("span", { className: "ico-slot" }),
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

// Зовнішні посилання відкриваються браузером користувача за замовчуванням (через програму),
// а не у вікні програми чи в Edge.
// Закриття вікна програми (хрестик, Alt+F4) — лише після підтвердження.
// Викликається з вікна Qt; "asked" — питання показано тут, інакше вікно спитає саме.
window.scdmxRequestClose = () => {
  if (!ws || ws.readyState !== WebSocket.OPEN || quitting) return "none";
  if ($("#uiDlg").open) return "asked";
  hideMenu();
  uiConfirm("Прожектори згаснуть.", { title: "Закрити SC DMX?", ok: "Закрити", danger: true })
    .then((ok) => { if (ok) { quitting = true; send({ cmd: "quit" }); } });
  return "asked";
};

function bindExternalLinks() {
  const handler = (e) => {
    const a = e.target instanceof Element && e.target.closest("a[href]");
    if (!a) return;
    const url = new URL(a.href, location.href);
    if (url.origin === location.origin || !/^https?:$/.test(url.protocol)) return;
    if (e.type === "auxclick" && e.button !== 1) return;
    e.preventDefault();
    send({ cmd: "open_url", url: url.href });
    toast("Відкриваю в браузері…", true);
  };
  document.addEventListener("click", handler, true);
  document.addEventListener("auxclick", handler, true);
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

// ------------------------------------------------- бібліотека приладів -----
const LIB_TYPES = [
  ["", "Усі моделі"], ["bar", "LED-бари"], ["par", "Прожектори PAR і заливка"], ["head", "Голови"],
  ["strobe", "Стробоскопи і блайндери"], ["matrix", "Матриці й панелі"], ["effect", "Ефекти"], ["other", "Інше"],
];
const LED = { r: "#ff4a4a", g: "#3ddc6b", b: "#4f7dff", w: "#f4f1e8", a: "#ffb02e", uv: "#a066ff" };
const LED_NAME = { r: "R", g: "G", b: "B", w: "W", a: "A", uv: "UV" };
const lib = { type: "", q: "", offset: 0, seq: 0, timer: null };
let pendingProfile = null;
let chosenModel = null;

function libProfileName(fx, mode) {
  return mode[2] || `${fx.m} ${fx.n} · ${mode[0]} (${mode[1].length} кан.)`;
}

function fxColors(fx) {
  const set = new Set();
  for (const m of fx.modes) for (const r of m[1]) if (LED[r]) set.add(r);
  return ["r", "g", "b", "w", "a", "uv"].filter((c) => set.has(c));
}
const fxSegments = (fx) => Math.max(1, ...fx.modes.map((m) => Math.max(...["r", "g", "b", "w"].map((c) => m[1].filter((x) => x === c).length))));

// Схематичне зображення приладу: форма за типом, світлодіоди — його кольори, у барів — його сегменти
function fixtureArt(fx) {
  const cols = fxColors(fx).map((c) => LED[c]);
  const pal = cols.length ? cols : [LED.w];
  const body = 'fill="#1b1f27" stroke="#4a5160" stroke-width="2"';
  const led = (cx, cy, r, i) => `<circle cx="${cx}" cy="${cy}" r="${r}" fill="${pal[i % pal.length]}" opacity=".9"/>`;
  let g = "";
  switch (fx.t) {
    case "bar": {
      const n = Math.min(16, fxSegments(fx));
      const w = 200, x0 = 20, cw = (w - 8) / Math.max(n, 1);
      g = `<rect x="${x0}" y="34" width="${w}" height="28" rx="6" ${body}/>` +
          `<path d="M${x0 + 20} 62 l-8 14 h16 z M${x0 + w - 20} 62 l-8 14 h16 z" fill="#2a2f3a"/>`;
      for (let i = 0; i < n; i++) g += `<rect x="${x0 + 4 + i * cw + 1.5}" y="38" width="${cw - 3}" height="20" rx="3" fill="${pal[i % pal.length]}" opacity=".9"/>`;
      break;
    }
    case "head":
      g = `<rect x="95" y="70" width="50" height="16" rx="4" ${body}/>` +
          `<path d="M100 70 V44 M140 70 V44" stroke="#4a5160" stroke-width="6" stroke-linecap="round"/>` +
          `<circle cx="120" cy="40" r="26" ${body}/>` + [0, 1, 2, 3, 4, 5].map((i) =>
            led(120 + 13 * Math.cos(i * Math.PI / 3), 40 + 13 * Math.sin(i * Math.PI / 3), 5, i)).join("") + led(120, 40, 5, 6);
      break;
    case "strobe":
      g = `<rect x="45" y="22" width="150" height="54" rx="8" ${body}/>` +
          `<rect x="57" y="40" width="126" height="18" rx="9" fill="${pal.includes(LED.w) ? LED.w : pal[0]}" opacity=".95"/>`;
      break;
    case "matrix":
      g = `<rect x="70" y="8" width="100" height="80" rx="8" ${body}/>`;
      for (let y = 0; y < 4; y++) for (let x = 0; x < 5; x++) g += led(84 + x * 18, 22 + y * 18, 6, x + y);
      break;
    case "effect":
      g = `<circle cx="120" cy="48" r="34" ${body}/>` + [...Array(8)].map((_, i) =>
        `<path d="M120 48 L${120 + 30 * Math.cos(i * Math.PI / 4)} ${48 + 30 * Math.sin(i * Math.PI / 4)}" stroke="${pal[i % pal.length]}" stroke-width="3" stroke-linecap="round" opacity=".85"/>`).join("");
      break;
    default: {  // PAR / заливка / інше: корпус-«банка» з LED-матрицею
      g = `<path d="M96 80 l-10 10 h68 l-10 -10" fill="#2a2f3a"/><circle cx="120" cy="46" r="38" ${body}/><circle cx="120" cy="46" r="30" fill="#0f1217"/>`;
      const pts = [[0, 0], ...[0, 1, 2, 3, 4, 5].map((i) => [16 * Math.cos(i * Math.PI / 3), 16 * Math.sin(i * Math.PI / 3)])];
      pts.forEach(([dx, dy], i) => (g += led(120 + dx, 46 + dy, 6, i)));
    }
  }
  return `<svg viewBox="0 0 240 96" role="img" aria-label="${fx.t}">${g}</svg>`;
}

function libCard(fx) {
  const card = el("div", { className: "lib-card" });
  const img = el("div", { className: "lib-img", innerHTML: fixtureArt(fx) });
  const colors = el("div", { className: "lib-colors" }, ...fxColors(fx).map((c) => {
    const i = el("i"); i.style.background = LED[c];
    return el("span", {}, i, LED_NAME[c]);
  }));
  const modes = el("div", { className: "lib-modes" }, ...fx.modes.map((mode) => {
    const b = el("button", { type: "button", className: "btn small", title: mode[1].join(" "),
                             textContent: `${mode[0]} · ${mode[1].length} кан.` });
    b.onclick = () => importProfile(fx, mode, b);
    return b;
  }));
  card.append(img, el("div", { className: "lib-maker", textContent: fx.m }),
              el("div", { className: "lib-model", textContent: fx.n }), colors, modes);
  return card;
}

async function loadLibrary(append = false) {
  const seq = ++lib.seq;
  if (!append) lib.offset = 0;
  const params = new URLSearchParams({ q: lib.q, type: lib.type, offset: lib.offset, limit: 60 });
  let data = { results: [], counts: {}, more: false, total: 0 };
  try { data = await (await fetch(`/api/library?${params}`)).json(); } catch { /* сервер недоступний */ }
  if (seq !== lib.seq) return;  // відповідь на застарілий запит
  // розділи з кількістю моделей для поточного пошуку
  const all = Object.values(data.counts).reduce((x, y) => x + y, 0);
  $("#libTypes").replaceChildren(...LIB_TYPES.map(([key, label]) => {
    const n = key ? data.counts[key] || 0 : all;
    const b = el("button", { type: "button", className: lib.type === key ? "active" : "", disabled: !n && lib.type !== key },
      el("span", { textContent: label }), el("span", { className: "n", textContent: n }));
    b.onclick = () => { lib.type = key; loadLibrary(); };
    return b;
  }));
  const grid = $("#libGrid");
  if (!append) { grid.replaceChildren(); grid.scrollTop = 0; }
  for (const fx of data.results) grid.append(libCard(fx));
  if (!grid.children.length) grid.append(el("div", { className: "lib-empty",
    textContent: "Нічого не знайдено. Спробуйте коротший запит або інший розділ." }));
  lib.offset += data.results.length;
  $("#libMore").hidden = !data.more;
}

function openLibrary() {
  lib.q = $("#libSearch").value.trim();
  $("#libDlg").showModal();
  loadLibrary();
  $("#libSearch").focus();
}

function pickProfile(name) {
  $("#addProfile").value = name;
  updateAddInfo();
}

function importProfile(fx, mode, btn) {
  const name = libProfileName(fx, mode);
  if (!$("#addName").value.trim()) $("#addName").value = fx.n;
  document.querySelectorAll(".lib-modes .btn.picked").forEach((b) => b.classList.remove("picked"));
  btn.classList.add("picked");
  chosenModel = fx;
  $("#libChosen").replaceChildren(el("b", { textContent: `${fx.m} ${fx.n}` }), el("br"), `Режим: ${mode[0]} · ${mode[1].length} кан.`);
  $("#libDlg").close();
  if (S.profiles[name]) return pickProfile(name);
  pendingProfile = name;
  send({ cmd: "save_profile", name, channels: mode[1] });
}

function nextFreeAddress() {
  const end = Math.max(0, ...S.fixtures.map((f) => f.address + S.profiles[f.profile].length - 1));
  return Math.min(512, end + 1);
}

function openAdd() {
  renderSettings();
  $("#addAddress").value = nextFreeAddress();
  $("#addCount").value = 1;
  $("#addName").value = "";
  $("#libSearch").value = "";
  chosenModel = null;
  $("#libChosen").textContent = "Модель не вибрано — виберіть з бібліотеки або профіль вручну";
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
  if (pendingProfile && S.profiles[pendingProfile]) {
    renderSettings();
    pickProfile(pendingProfile);
    pendingProfile = null;
  }
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
    flash($("#outApply"), "Застосовано");
  };
  $("#openAdd").onclick = openAdd;
  for (const b of document.querySelectorAll("[data-open-add]")) b.onclick = openAdd;
  $("#addCount").addEventListener("input", updateAddInfo);
  $("#libSearch").addEventListener("input", () => {
    clearTimeout(lib.timer);
    lib.timer = setTimeout(() => { lib.q = $("#libSearch").value.trim(); loadLibrary(); }, 150);
  });
  $("#libMore").onclick = () => loadLibrary(true);
  $("#openLibrary").onclick = openLibrary;
  $("#addProfile").addEventListener("change", () => {
    chosenModel = null;
    $("#libChosen").textContent = "Профіль вибрано вручну";
  });
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
  hydrateIcons();
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
  bindExternalLinks();
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
