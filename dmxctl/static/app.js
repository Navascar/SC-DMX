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
    if (addPending !== null) addPending = null;
    toast(m.message);
  }
}

let toastTimer;
function toast(text, info = false) {
  const t = $("#toast");
  t.textContent = text;
  t.className = "toast" + (info ? " info" : "");
  t.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => (t.hidden = true), 3500);
}

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
  $("#outputText").textContent = (o.type ? names[o.type] + " · " : "") + o.status;
  pill.title = o.status;
  $("#outStatus").textContent = o.status;
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
      el("div", { className: "fx-badge", textContent: effIds.has(f.id) ? "● " + S.effects[S.effect.type] : "" }));
    tile.dataset.id = f.id;
    tile.onclick = (e) => pick(f.id, e.shiftKey);
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
  renderFixtures();
  syncSliders();
}

function updateLive(m) {
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
  $("#frameCounter").textContent = `· відправлено кадрів: ${m.frames}`;
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
    input.style.accentColor = color;
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
  $("#selInfo").textContent = desc ? `вибрано ${desc}` : "нічого не вибрано";
  $("#staticTarget").textContent = desc ? `для вибраних (${desc})` : "для всіх приладів";
  $("#clearColors").textContent = desc ? "⌫ Очистити вибрані" : "⌫ Очистити все";
  // показувати лише ті канали, що є у вибраних приладів (або всі, якщо не вибрано)
  const roles = new Set();
  for (const f of sel.length ? sel : S.fixtures) for (const r of S.profiles[f.profile] || []) roles.add(r);
  const first = items[0] && itemColor(items[0]);
  for (const row of $("#sliders").children) {
    const key = row.dataset.key;
    const always = ["r", "g", "b", "dimmer"].includes(key);
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
  let about = u.status === "checking" ? "перевірка…"
    : busy ? u.progress
    : u.error ? u.error
    : u.available ? `доступна версія ${u.latest}`
    : u.latest ? `встановлено останню версію (${u.current})` : "";
  $("#aboutUpdate").textContent = about;
  $("#checkUpdate").textContent = u.available ? "Оновити до " + u.latest : "Перевірити оновлення";
  $("#checkUpdate").disabled = busy || u.status === "checking";
  $("#aboutNotes").hidden = !(u.available && u.notes);
  $("#aboutNotes").textContent = u.notes;

  const banner = $("#updateBanner");
  const dismissed = sessionStorageGet("dismissed") === u.latest;
  banner.hidden = !(busy || (u.available && !dismissed) || (u.error && u.status === "idle" && renderUpdate.tried));
  banner.classList.toggle("err", !!u.error && !busy);
  $("#updateText").textContent = busy ? `Оновлення до ${u.latest}: ${u.progress}`
    : u.error && renderUpdate.tried ? u.error
    : u.blocked ? `Доступна версія ${u.latest} (у вас ${u.current}). Автооновлення недоступне: ${u.blocked}`
    : `Доступна нова версія SC DMX ${u.latest} (у вас ${u.current}).`;
  $("#updateNow").hidden = busy || !u.available || !!u.blocked;
  $("#updateNotesBtn").hidden = busy || !u.notes;
  $("#updateLater").hidden = busy;
}

function sessionStorageGet(k) { try { return sessionStorage.getItem(k); } catch { return null; } }
function sessionStorageSet(k, v) { try { sessionStorage.setItem(k, v); } catch { /* ignore */ } }

function startUpdate() {
  if (!confirm(`Оновити SC DMX до версії ${updateInfo.latest}?\nПрограма перезапуститься (~10 с), світло залишиться увімкненим.`)) return;
  renderUpdate.tried = true;
  send({ cmd: "apply_update" });
}

function bindUpdate() {
  $("#updateNow").onclick = startUpdate;
  $("#updateLater").onclick = () => { sessionStorageSet("dismissed", updateInfo.latest); renderUpdate.tried = false; renderUpdate(); };
  $("#updateNotesBtn").onclick = () => {
    $("#openSettings").click();
    document.querySelector(".tabs button[data-tab=tabAbout]").click();
  };
  $("#checkUpdate").onclick = () => (updateInfo && updateInfo.available && !updateInfo.blocked ? startUpdate() : send({ cmd: "check_update" }));
  $("#quitApp").onclick = () => {
    if (confirm("Вимкнути SC DMX? Прожектори згаснуть.")) { quitting = true; send({ cmd: "quit" }); }
  };
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
  $("#staticClear").onclick = clearColors;
  $("#staticEdit").onclick = () => { staticEditing = !staticEditing; renderStatic(); };
  $("#staticReset").onclick = () => confirm("Повернути стандартний набір кольорів?") && send({ cmd: "reset_static_colors" });
  $("#staticAdd").onclick = () => {
    const f = selItems()[0] && itemColor(selItems()[0]);
    if (!f) return toast("Виберіть прилад і налаштуйте колір, який хочете зберегти");
    const name = prompt("Назва кольору:", "Мій колір");
    if (name === null) return;
    send({ cmd: "add_static_color", name, hex: toHex(f.r, f.g, f.b), w: f.w });
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
  $("#effSpeed").value = sliderFromSpeed(e.speed);
  $("#effSpread").value = Math.round(e.spread * 100);
  $("#effBySeg").checked = e.by_segment !== false;
  updateEffLabels();
  $("#effectState").textContent = e.type !== "none" ? `▶ ${S.effects[e.type]} · ${e.ids.length} прил.` : "";
  renderEffColors();
}

function updateEffLabels() {
  $("#effSpeedVal").textContent = speedFromSlider(+$("#effSpeed").value).toFixed(2) + " Гц";
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
  if (!names.length) return list.replaceChildren(el("li", { className: "hint", textContent: "Збережених сцен немає" }));
  list.replaceChildren(...names.map((name) => el("li", {},
    el("button", { className: "btn", textContent: "▶ " + name,
      onclick: () => send({ cmd: "recall_scene", name, fade: +$("#sceneFade").value || 0 }) }),
    el("button", { className: "btn small", textContent: "✕", title: "Видалити",
      onclick: () => confirm(`Видалити сцену «${name}»?`) && send({ cmd: "delete_scene", name }) }))));
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
          onclick: () => confirm(`Видалити «${f.name}»?`) && send({ cmd: "delete_fixture", id: f.id }) })));
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

// ------------------------------------------------------------- старт ------
function init() {
  buildSliders();
  buildSwatches();
  buildWheel();
  bindStatic();
  bindUpdate();
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
    if (e.target.matches("input, select, textarea") || $("#settings").open || $("#addDlg").open) return;
    if (e.key === "b" || e.key === "B" || e.key === "и" || e.key === "И") send({ cmd: "blackout" });
    if ((e.ctrlKey || e.metaKey) && e.key === "a") { e.preventDefault(); $("#selAll").click(); }
    if (e.key === "Escape") $("#selNone").click();
    if (e.key === "Delete" || e.key === "Backspace" || e.key === "0") { e.preventDefault(); clearColors(); }
    // 1..9 — швидкий вибір статичного кольору
    if (/^[1-9]$/.test(e.key) && S.static_colors[+e.key - 1]) {
      send({ cmd: "static_color", index: +e.key - 1, ids: [...selected] });
    }
  });
  connect();
}

init();
