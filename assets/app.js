const CLASSES = window.CLASSES || [];
const store = {
  get(k){ try{ return JSON.parse(localStorage.getItem(k)); }catch(e){ return null; } },
  set(k,v){ try{ localStorage.setItem(k, JSON.stringify(v)); }catch(e){} },
};
const PLUS_REASONS  = ["回答問題","表現優異","主動幫忙","小組合作","作業完成"];
const MINUS_REASONS = ["上課講話","不專心","遲到","未帶課本","作業未交"];
const AMOUNTS = [1,2,5];
const HAIR = ["#3b2a20","#2a201b","#5a3a26","#1f1a17","#4a2f22","#6b4428"];
const SHIRTS = ["#a9d8f5","#ff6f61","#a9d8f5","#ffd166","#a9d8f5","#ff6f61"];
const $ = id => document.getElementById(id);
const pad = n => String(n).padStart(2,"0");
const esc = t => String(t ?? "").replace(/[&<>"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));

let cls, KEY, state, selected = null, amount = 1, editMode = false;
let muted = store.get("classroom:muted") || false;
const save = () => store.set(KEY, state);
const sig = c => JSON.stringify([c.rows, c.cols, c.seats]);

/* ---------- 班級載入 ---------- */
const newSessionId = () => Date.now().toString(36) + Math.random().toString(36).slice(2, 7);
function fresh(c){
  return { className: c.className, rows: c.rows, cols: c.cols, seats: c.seats.map(s => ({...s})),
           sig: sig(c), events: [], startedAt: Date.now(), sessionId: newSessionId(), view: "chart" };
}
function loadClass(id){
  cls = CLASSES.find(c => c.id === id) || CLASSES[0];
  KEY = "classroom:v2:" + cls.id;
  state = store.get(KEY);
  if (!state) state = fresh(cls);
  else if (!state.manual && state.sig !== sig(cls)) {
    // 照片重新辨識過：換上新座位，保留已經記錄的分數（依座號對應）
    Object.assign(state, { rows: cls.rows, cols: cls.cols, seats: cls.seats.map(s => ({...s})), sig: sig(cls) });
  }
  state.sessionId = state.sessionId || newSessionId();
  selected = null;
  $("classSel").value = cls.id;
  store.set("classroom:last", cls.id);
  save(); renderRoom();
}

/* ---------- 由事件推算每位學生的分數與出席 ---------- */
function compute(){
  const r = {};
  for (const s of state.seats) r[s.no] = { plus:0, minus:0, plusN:0, minusN:0, status:"none", plusR:[], minusR:[] };
  for (const e of state.events){
    const x = r[e.no]; if (!x) continue;
    if (e.type === "status") x.status = e.status;
    else if (e.delta > 0){ x.plus += e.delta; x.plusN++; x.plusR.push(`${e.reason||"加分"}+${e.delta}`); }
    else { x.minus += -e.delta; x.minusN++; x.minusR.push(`${e.reason||"扣分"}${e.delta}`); }
  }
  for (const k in r) r[k].net = r[k].plus - r[k].minus;
  return r;
}
const seatByNo = no => state.seats.find(s => s.no === no);
const seatEl = no => $("grid").querySelector(`.seat[data-no="${no}"]`);

/* ---------- 教室繪製 ----------
   座位座標以紙本座位表為準：row 1 = 紙上最上排（離講台最遠），col 1 = 紙上最左。
   「chart」視角 = 跟紙本一樣（講台在下方、看得到臉）；「back」= 從教室後面看（講台在上方）。 */
function gridPos(s){
  const back = state.view === "back";
  return { r: back ? state.rows - s.row + 1 : s.row, c: back ? state.cols - s.col + 1 : s.col };
}
function renderRoom(){
  const room = $("room"), grid = $("grid");
  room.classList.toggle("back", state.view === "back");
  room.classList.toggle("edit-mode", editMode);
  grid.style.gridTemplateColumns = `repeat(${state.cols}, minmax(86px, 1fr))`;
  grid.innerHTML = "";
  const taken = new Set(state.seats.map(s => s.row + "-" + s.col));
  const cells = [...state.seats];
  for (let row = 1; row <= state.rows; row++)
    for (let col = 1; col <= state.cols; col++)
      if (!taken.has(row + "-" + col)) cells.push({ row, col, empty: true });
  for (const s of cells){
    const el = document.createElement("button");
    el.className = "seat" + (s.empty ? " empty" : "");
    const p = gridPos(s);
    el.style.gridRow = p.r; el.style.gridColumn = p.c;
    const n = s.no || 0;
    const lead = /班長/.test(s.role || "");
    el.innerHTML = `
      ${s.empty ? "" : `<div class="score">0</div><div class="tier"></div><div class="dot"></div><div class="stamp">缺席</div>`}
      <div class="chair"></div>
      <div class="kid${n % 3 === 1 ? " bun" : ""}" style="--shirt:${SHIRTS[n % SHIRTS.length]};--hair:${HAIR[n % HAIR.length]};--d:${((n * 0.37) % 2.6).toFixed(2)}s">
        <div class="body"></div><div class="head"><i class="eye l"></i><i class="eye r"></i><i class="cheek l"></i><i class="cheek r"></i><i class="mouth"></i></div>
      </div>
      <div class="desk"><span class="plate">${s.empty ? "空位" : pad(s.no)}</span></div>
      <div class="name">${s.empty ? "—" : esc(s.name)}</div>
      <div class="role${lead ? " lead" : ""}">${esc(s.role || "")}</div>`;
    if (!s.empty) el.dataset.no = s.no;
    el.addEventListener("click", () => editMode ? editSeat(s) : select(s.no));
    grid.appendChild(el);
  }
  refresh();
}

function refresh(){
  const R = compute();
  for (const s of state.seats){
    const el = seatEl(s.no); if (!el) continue;
    const x = R[s.no];
    const sc = el.querySelector(".score");
    sc.textContent = x.net > 0 ? "+" + x.net : x.net;
    sc.className = "score" + (x.net > 0 ? " pos" : x.net < 0 ? " neg" : "");
    el.querySelector(".tier").textContent = x.net >= 10 ? "👑" : x.net >= 5 ? "⭐" : x.net <= -3 ? "⚠️" : "";
    el.querySelector(".dot").className = "dot " + x.status;
    el.classList.toggle("absent", x.status === "absent");
    el.classList.toggle("sel", s.no === selected);
  }
  const vals = state.seats.map(s => R[s.no]);
  $("sAtt").textContent = `${vals.filter(v => v.status === "present").length}/${state.seats.length}`;
  $("sPlus").textContent = "+" + vals.reduce((a,v) => a + v.plus, 0);
  $("sMinus").textContent = "-" + vals.reduce((a,v) => a + v.minus, 0);
  $("boardTitle").textContent = state.className + " 班";
  const ranked = state.seats.map(s => ({ s, x: R[s.no] })).filter(o => o.x.net > 0).sort((a,b) => b.x.net - a.x.net);
  $("boardStar").textContent = ranked.length ? `🌟 今日之星：${ranked[0].s.name}（+${ranked[0].x.net}）`
    : new Date().toLocaleDateString("zh-TW",{month:"long",day:"numeric",weekday:"long"});
  const medals = ["🥇","🥈","🥉","4","5"];
  $("lb").innerHTML = ranked.length ? ranked.slice(0,5).map((o,i) =>
    `<li data-no="${o.s.no}"><span class="rk">${medals[i]}</span><span class="n">${pad(o.s.no)} ${esc(o.s.name)}</span><span class="v">+${o.x.net}</span></li>`).join("")
    : `<li style="cursor:default;color:var(--muted)">還沒有人得分，快來加分吧！✨</li>`;
  const evs = state.events.slice(-40).reverse();
  $("log").innerHTML = evs.length ? evs.map(e => {
    const s = seatByNo(e.no); const t = new Date(e.t);
    const label = e.type === "status" ? ({present:"到課",absent:"缺席",none:"取消點名"})[e.status] : (e.reason || (e.delta > 0 ? "加分" : "扣分"));
    const d = e.type === "status" ? "" : `<span class="d ${e.delta>0?"p":"m"}">${e.delta>0?"+":""}${e.delta}</span>`;
    return `<li><time>${pad(t.getHours())}:${pad(t.getMinutes())}</time><span>${s ? esc(s.name) : "#"+e.no}・${label}</span>${d}</li>`;
  }).join("") : `<li style="color:var(--muted)">尚無紀錄</li>`;
  renderAction(R);
  $("viewBtn").textContent = state.view === "back" ? "🔄 座位表視角" : "🔄 教室後方視角";
  $("editBtn").classList.toggle("on", editMode);
  $("muteBtn").textContent = muted ? "🔇" : "🔊";
  const synced = state.syncedSig && state.syncedSig === eventsSig();
  $("syncBtn").textContent = synced ? "✓ 已上傳" : "☁️ 下課上傳";
  $("syncBtn").classList.toggle("done", !!synced);
  $("syncBtn").classList.toggle("primary", !synced);
}

function renderAction(R){
  const box = $("action");
  const s = selected != null && seatByNo(selected);
  if (!s){
    box.innerHTML = `<h3>🎯 目前選擇</h3><div class="empty-sel"><span class="big">👆</span>點教室裡的同學開始加分吧！</div>`;
    return;
  }
  const x = R[s.no];
  const color = x.net > 0 ? "var(--plus-d)" : x.net < 0 ? "var(--minus-d)" : "var(--ink)";
  box.innerHTML = `
    <h3>🎯 目前選擇 <span style="font-size:12px;color:var(--muted)">${esc(s.role || "")}</span></h3>
    <div class="who"><div class="av">${pad(s.no)}</div>
      <div><div class="nm">${esc(s.name)}</div><div class="sub">加 ${x.plus}・扣 ${x.minus}</div></div>
      <div class="big" style="color:${color}">${x.net > 0 ? "+" : ""}${x.net}</div></div>
    <div class="pm"><button class="p" data-act="plus">＋ 加 ${amount} 分</button><button class="m" data-act="minus">－ 扣 ${amount} 分</button></div>
    <div class="amt">分數 ${AMOUNTS.map(a => `<button data-amt="${a}" class="${a===amount?"on":""}">${a}</button>`).join("")}</div>
    <div class="chips">${PLUS_REASONS.map(r => `<button class="chip p" data-reason="${r}" data-sign="1">${r} +${amount}</button>`).join("")}</div>
    <div class="chips">${MINUS_REASONS.map(r => `<button class="chip m" data-reason="${r}" data-sign="-1">${r} -${amount}</button>`).join("")}</div>
    <div class="att">
      <button class="present ${x.status==="present"?"on":""}" data-st="present">✅ 到課</button>
      <button class="absent ${x.status==="absent"?"on":""}" data-st="absent">❌ 缺席</button>
      <button class="none ${x.status==="none"?"on":""}" data-st="none">⏺ 未點名</button>
    </div>`;
}

/* ---------- 動作 ---------- */
function select(no){ selected = selected === no ? null : no; refresh(); }
function score(no, delta, reason){
  state.events.push({ type:"score", no, delta, reason: reason || "", t: Date.now() });
  save(); refresh(); fx(no, delta);
}
function setStatus(no, status){
  state.events.push({ type:"status", no, status, t: Date.now() });
  save(); refresh();
}
function undo(){
  const e = state.events.pop();
  if (!e) return toast("沒有可以復原的紀錄");
  if (e.batch){
    while (state.events.length && state.events[state.events.length-1].batch === e.batch) state.events.pop();
    save(); refresh(); return toast("已復原：" + e.batch);
  }
  save(); refresh();
  const s = seatByNo(e.no);
  toast(`已復原：${s ? s.name : ""} ${e.type === "status" ? "點名" : (e.delta>0?"+":"") + e.delta}`);
}

function fx(no, delta, quiet){
  const el = seatEl(no); if (!el) return;
  el.classList.remove("bump","shake"); void el.offsetWidth;
  el.classList.add(delta > 0 ? "bump" : "shake");
  const kid = el.querySelector(".kid");
  kid.classList.remove("happy","sad"); kid.classList.add(delta > 0 ? "happy" : "sad");
  clearTimeout(kid._t); kid._t = setTimeout(() => kid.classList.remove("happy","sad"), 1600);
  const f = document.createElement("span");
  f.className = "float " + (delta > 0 ? "p" : "m");
  f.textContent = (delta > 0 ? "+" : "") + delta;
  el.appendChild(f); setTimeout(() => f.remove(), 1000);
  if (delta >= 5) confetti(el);
  if (!quiet) sound(delta > 0, Math.abs(delta) >= 5);
}
function confetti(el){
  if (!el) return;
  const colors = ["#ffc93c","#3fc77b","#5aa9ff","#ff8fb1","#a98bff"];
  for (let i = 0; i < 20; i++){
    const c = document.createElement("span"); c.className = "confetti";
    c.style.background = colors[i % colors.length];
    c.style.setProperty("--dx", (Math.random()*150-75) + "px");
    c.style.setProperty("--dy", (Math.random()*-120-10) + "px");
    el.appendChild(c); setTimeout(() => c.remove(), 900);
  }
}

let actx;
function tone(freqs, type, vol, step){
  if (muted) return;
  try{
    actx = actx || new (window.AudioContext || window.webkitAudioContext)();
    freqs.forEach((f,i) => {
      const o = actx.createOscillator(), g = actx.createGain(), t = actx.currentTime + i*step;
      o.type = type; o.frequency.value = f;
      g.gain.setValueAtTime(0.0001, t); g.gain.exponentialRampToValueAtTime(vol, t + 0.01);
      g.gain.exponentialRampToValueAtTime(0.0001, t + 0.18);
      o.connect(g).connect(actx.destination); o.start(t); o.stop(t + 0.2);
    });
  }catch(e){}
}
const sound = (up, big) => up ? tone(big ? [523,659,784,1047] : [660,990], "triangle", .18, .08) : tone([320,220], "square", .07, .1);

function toast(msg){
  const t = $("toast"); t.textContent = msg; t.classList.add("show");
  clearTimeout(toast.h); toast.h = setTimeout(() => t.classList.remove("show"), 1800);
}

/* ---------- 抽籤 ---------- */
let luckyNo = null, spinning = false;
function lucky(){
  if (spinning) return;
  const R = compute();
  const pool = state.seats.filter(s => R[s.no].status !== "absent");
  if (!pool.length) return;
  $("luckyModal").classList.add("open");
  spinning = true;
  let n = 0; const total = 18 + Math.floor(Math.random()*8);
  (function spin(){
    const s = pool[Math.floor(Math.random()*pool.length)];
    document.querySelectorAll(".seat.spot").forEach(x => x.classList.remove("spot"));
    seatEl(s.no)?.classList.add("spot");
    $("lotteryName").textContent = `${pad(s.no)} ${s.name}`;
    luckyNo = s.no; tone([400 + n*25], "sine", .06, 0);
    if (++n < total) setTimeout(spin, 50 + n*n*0.6);
    else { spinning = false; tone([784,1047,1319], "triangle", .16, .09); confetti(seatEl(s.no)); }
  })();
}
$("luckyBtn").onclick = lucky;
$("luckyAgain").onclick = lucky;
$("luckyPick").onclick = () => {
  if (spinning) return;
  $("luckyModal").classList.remove("open");
  document.querySelectorAll(".seat.spot").forEach(x => x.classList.remove("spot"));
  selected = luckyNo; refresh();
};

/* ---------- 編輯 / 匯入 ---------- */
function editSeat(s){
  const cur = s.empty ? "" : `${s.no} ${s.name} ${s.role || ""}`.trim();
  const v = prompt(`第 ${s.row} 排・第 ${s.col} 列\n輸入「座號 姓名 職稱」，清空則移除此座位：`, cur);
  if (v === null) return;
  const m = v.trim().match(/^(\d+)\s*(\S*)\s*(.*)$/);
  const others = state.seats.filter(x => !(x.row === s.row && x.col === s.col));
  if (m && others.some(x => x.no === +m[1])) return alert(`座號 ${m[1]} 已經有人了`);
  state.seats = others;
  if (m) state.seats.push({ no: +m[1], name: m[2] || `${m[1]} 號`, role: m[3].trim(), row: s.row, col: s.col });
  state.manual = true; save(); renderRoom();
}
function parseGrid(text){
  const lines = text.replace(/\r/g,"").split("\n").filter(l => l.trim() !== "");
  const seats = []; let cols = 0;
  lines.forEach((line, i) => {
    const cells = line.split(/\t|,|，|\||｜/);
    cols = Math.max(cols, cells.length);
    cells.forEach((cell, j) => {
      const m = cell.trim().match(/^(\d+)\s*[.號、:：]?\s*(\S*)\s*(.*)$/);
      if (m) seats.push({ no: +m[1], name: m[2] || `${+m[1]} 號`, role: m[3].trim(), row: i + 1, col: j + 1 });
    });
  });
  return { rows: lines.length, cols, seats };
}
function toGridText(){
  const lines = [];
  for (let r = 1; r <= state.rows; r++){
    const row = [];
    for (let c = 1; c <= state.cols; c++){
      const s = state.seats.find(x => x.row === r && x.col === c);
      row.push(s ? `${s.no} ${s.name} ${s.role || ""}`.trim() : "");
    }
    lines.push(row.join("\t"));
  }
  return lines.join("\n");
}

/* ---------- 匯出 CSV ---------- */
function exportCSV(){
  const R = compute();
  const q = v => { v = String(v); return /[",\n]/.test(v) ? `"${v.replace(/"/g,'""')}"` : v; };
  const head = ["班級","座號","姓名","職稱","座位(排-列)","出席狀態","加分次數","加分總計","扣分次數","扣分總計","淨分","加分明細","扣分明細"];
  const st = { present:"已到", absent:"缺席", none:"未點名" };
  const rows = [...state.seats].sort((a,b) => a.no - b.no).map(s => {
    const x = R[s.no];
    return [state.className, s.no, s.name, s.role || "", `${s.row}-${s.col}`, st[x.status], x.plusN, x.plus, x.minusN, x.minus, x.net, x.plusR.join("、"), x.minusR.join("、")];
  });
  const csv = "﻿" + [head, ...rows].map(r => r.map(q).join(",")).join("\r\n");
  const d = new Date();
  const name = `${state.className}_${d.getFullYear()}${pad(d.getMonth()+1)}${pad(d.getDate())}_${pad(d.getHours())}${pad(d.getMinutes())}.csv`;
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([csv], { type: "text/csv;charset=utf-8" }));
  a.download = name; a.click(); setTimeout(() => URL.revokeObjectURL(a.href), 1000);
  toast("已匯出 " + name);
}

/* ---------- 上傳到 Google Sheet ---------- */
const cloud = () => store.get("classroom:cloud") || {};
const LOCAL = location.protocol.startsWith("http");   // 用 server.py 開啟時，由本機伺服器以服務帳戶寫入，不需要 Apps Script
const eventsSig = () => state.events.length + ":" + (state.events.at(-1)?.t || 0);
const sessionDate = () => { const d = new Date(state.startedAt); return { md: `${d.getMonth()+1}/${d.getDate()}`, iso: `${d.getFullYear()}-${pad(d.getMonth()+1)}-${pad(d.getDate())}` }; };

async function post(body){
  let res;
  if (LOCAL) res = await fetch("/api/" + body.action, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  else {
    const { url, token } = cloud();
    // 用 text/plain 送出，瀏覽器不會先發 CORS 預檢，Apps Script 才收得到
    res = await fetch(url, { method: "POST", body: JSON.stringify({ token, ...body }) });
  }
  const data = await res.json().catch(() => ({ ok: false, error: "伺服器沒有回應，請用 start.command 或 python3 server.py 開啟" }));
  if (!data.ok) throw new Error(data.error || "上傳失敗");
  return data;
}

async function syncSheet(){
  if (!LOCAL && !cloud().url) return openCloud();
  const R = compute();
  const students = [...state.seats].sort((a,b) => a.no - b.no).map(s => {
    const x = R[s.no];
    return { no: s.no, name: s.name, role: s.role || "", status: x.status, plus: x.plus, minus: x.minus, net: x.net,
             plusN: x.plusN, minusN: x.minusN, plusR: x.plusR, minusR: x.minusR };
  });
  const active = students.filter(s => s.plusN || s.minusN).length;
  const { md, iso } = sessionDate();
  if (!confirm(`上傳到 Google Sheet？\n\n分頁：${state.className}\n日期：${md}\n有加扣分的同學：${active} 位\n\n（同一堂課重複上傳只會更新，不會重複加分）`)) return;
  const btn = $("syncBtn"); btn.disabled = true; btn.textContent = "⏳ 上傳中…";
  try{
    const r = await post({ action: "sync", className: state.className, date: md, isoDate: iso, sessionId: state.sessionId, students });
    state.syncedSig = eventsSig(); save();
    tone([523,659,784,1047], "triangle", .16, .08);
    toast(`☁️ 已寫入「${r.sheet}」分頁 ${r.date}，共 ${r.count} 位同學`);
    if (confirm("上傳完成！要開始新課堂（清空這堂課的分數）嗎？\n\n選「取消」可以繼續上這堂課，之後再上傳會更新同一欄。")){
      state.events = []; state.startedAt = Date.now(); state.sessionId = newSessionId(); state.syncedSig = null;
      selected = null; save();
    }
  }catch(e){
    alert("上傳失敗：" + e.message + "\n\n" + (LOCAL ? "請看終端機視窗的錯誤訊息。" : "請檢查網路，或到「⚙️」確認網址和密碼。") + "分數仍保存在這台電腦，可以稍後再上傳。");
  }finally{
    btn.disabled = false; refresh();
  }
}

function openCloud(){
  const c = cloud();
  $("cloudUrl").value = c.url || ""; $("cloudToken").value = c.token || "";
  $("cloudModal").classList.add("open");
}
function readCloudForm(){
  const url = $("cloudUrl").value.trim(), token = $("cloudToken").value;
  if (!/^https:\/\/script\.google(usercontent)?\.com\/.+/.test(url)) { alert("網址應該是 https://script.google.com/macros/s/…/exec"); return null; }
  return { url, token };
}
$("cloudBtn").onclick = LOCAL ? async () => {
  try{ toast("✅ " + (await post({ action: "ping" })).message); }
  catch(e){ alert("連線失敗：" + e.message); }
} : openCloud;
$("syncBtn").onclick = syncSheet;
$("cloudSave").onclick = () => {
  const c = readCloudForm(); if (!c) return;
  store.set("classroom:cloud", c); $("cloudModal").classList.remove("open"); toast("已儲存雲端設定");
};
$("cloudTest").onclick = async () => {
  const c = readCloudForm(); if (!c) return;
  const prev = cloud(); store.set("classroom:cloud", c);
  try{ toast("✅ " + (await post({ action: "ping" })).message); }
  catch(e){ store.set("classroom:cloud", prev); alert("連線失敗：" + e.message); }
};

/* ---------- 綁定 ---------- */
$("action").addEventListener("click", e => {
  const b = e.target.closest("button"); if (!b || selected == null) return;
  if (b.dataset.act) score(selected, b.dataset.act === "plus" ? amount : -amount);
  else if (b.dataset.amt){ amount = +b.dataset.amt; refresh(); }
  else if (b.dataset.reason) score(selected, +b.dataset.sign * amount, b.dataset.reason);
  else if (b.dataset.st) setStatus(selected, b.dataset.st);
});
$("lb").addEventListener("click", e => { const li = e.target.closest("li[data-no]"); if (li) select(+li.dataset.no); });
$("classSel").innerHTML = CLASSES.map(c => `<option value="${esc(c.id)}">${esc(c.className)} 班</option>`).join("");
$("classSel").onchange = e => loadClass(e.target.value);
$("viewBtn").onclick = () => { state.view = state.view === "back" ? "chart" : "back"; save(); renderRoom(); };
$("editBtn").onclick = () => { editMode = !editMode; selected = null; renderRoom(); toast(editMode ? "編輯模式：點座位修改座號／姓名／職稱" : "已離開編輯模式"); };
$("muteBtn").onclick = () => { muted = !muted; store.set("classroom:muted", muted); refresh(); };
$("allPresentBtn").onclick = () => {
  const R = compute(); const t = Date.now();
  state.seats.forEach(s => { if (R[s.no].status === "none") state.events.push({ type:"status", no:s.no, status:"present", t, batch:"全部到齊" }); });
  save(); refresh(); toast("未點名的同學已全部標記為到課 ✅");
};
$("classPlusBtn").onclick = () => {
  const R = compute(); const t = Date.now();
  const list = state.seats.filter(s => R[s.no].status !== "absent");
  list.forEach(s => state.events.push({ type:"score", no:s.no, delta:1, reason:"全班加分", t, batch:"全班 +1" }));
  save(); refresh(); list.forEach(s => fx(s.no, 1, true)); sound(true, true);
};
$("undoBtn").onclick = undo;
$("exportBtn").onclick = exportCSV;
$("resetBtn").onclick = () => {
  if (!state.events.length) return toast("目前沒有任何紀錄");
  if (!confirm(`要開始 ${state.className} 班的新課堂嗎？所有加扣分與點名紀錄會被清空。\n（建議先按「匯出 CSV」保存）`)) return;
  state.events = []; state.startedAt = Date.now(); state.sessionId = newSessionId(); state.syncedSig = null; selected = null; save(); refresh(); toast("新課堂開始！🎉");
};
$("importBtn").onclick = () => { $("importText").value = toGridText(); $("importModal").classList.add("open"); };
document.querySelectorAll("[data-close]").forEach(b => b.onclick = () => b.closest(".modal").classList.remove("open"));
$("importApply").onclick = () => {
  const g = parseGrid($("importText").value);
  if (!g.seats.length) return alert("沒有讀到任何「座號 姓名」，請檢查格式");
  const dup = g.seats.map(s => s.no).filter((n,i,a) => a.indexOf(n) !== i);
  if (dup.length) return alert("座號重複：" + [...new Set(dup)].join(", "));
  Object.assign(state, { rows: g.rows, cols: g.cols, seats: g.seats, manual: true });
  selected = null; save(); renderRoom(); $("importModal").classList.remove("open");
  toast(`已更新 ${g.seats.length} 位學生的座位`);
};
$("restoreBtn").onclick = () => {
  if (!confirm("還原為照片辨識出的名單？（分數紀錄會保留）")) return;
  Object.assign(state, { rows: cls.rows, cols: cls.cols, seats: cls.seats.map(s => ({...s})), sig: sig(cls), manual: false });
  selected = null; save(); renderRoom(); $("importModal").classList.remove("open");
};

document.addEventListener("keydown", e => {
  if (e.target.matches("input,textarea,select") || document.querySelector(".modal.open")) return;
  if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "z"){ e.preventDefault(); return undo(); }
  if (e.key === "Escape"){ selected = null; return refresh(); }
  const i = ["1","2","3"].indexOf(e.key); if (i >= 0){ amount = AMOUNTS[i]; return refresh(); }
  if (selected == null){
    if (e.key.startsWith("Arrow") && state.seats.length){ e.preventDefault(); selected = [...state.seats].sort((a,b)=>a.no-b.no)[0].no; refresh(); }
    return;
  }
  if (e.key === "+" || e.key === "=") return score(selected, amount);
  if (e.key === "-" || e.key === "_") return score(selected, -amount);
  if (e.key.toLowerCase() === "a") return setStatus(selected, "present");
  if (e.key.toLowerCase() === "x") return setStatus(selected, "absent");
  const dir = { ArrowUp:[-1,0], ArrowDown:[1,0], ArrowLeft:[0,-1], ArrowRight:[0,1] }[e.key];
  if (dir){
    e.preventDefault();
    const cur = gridPos(seatByNo(selected));
    const dist = p => dir[0] ? Math.abs(p.r-cur.r) + 2*Math.abs(p.c-cur.c) : Math.abs(p.c-cur.c) + 2*Math.abs(p.r-cur.r);
    const target = state.seats.map(x => ({ x, p: gridPos(x) }))
      .filter(o => dir[0] ? Math.sign(o.p.r - cur.r) === dir[0] : Math.sign(o.p.c - cur.c) === dir[1])
      .sort((a,b) => dist(a.p) - dist(b.p))[0];
    if (target){ selected = target.x.no; refresh(); }
  }
});

setInterval(() => {
  if (!state) return;
  const s = Math.floor((Date.now() - state.startedAt) / 1000);
  $("sTime").textContent = s >= 3600 ? `${Math.floor(s/3600)}:${pad(Math.floor(s/60)%60)}` : `${pad(Math.floor(s/60))}:${pad(s%60)}`;
}, 1000);

if (!CLASSES.length){
  document.querySelector("main").innerHTML = `<div class="card" style="margin:40px auto;max-width:520px;text-align:center">
    <h3 style="justify-content:center">還沒有任何班級 📷</h3><p>把座位表照片放進 <code>images/</code>，再執行 <code>python3 import_seating.py</code>。</p></div>`;
} else {
  const last = store.get("classroom:last");
  $("classSel").value = CLASSES.some(c => c.id === last) ? last : CLASSES[0].id;
  loadClass($("classSel").value);
}
