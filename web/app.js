const $ = (id) => document.getElementById(id);
let currentId = null;
let manualCheckItems = [];
let allMaterials = [];
let metaCache = null;

async function api(path, body) {
  const res = await fetch(path, body ? {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  } : {});
  const data = await res.json();
  if (!res.ok) throw new Error(data.error || res.statusText);
  return data;
}
function showError(err) { $("error").textContent = err ? String(err.message || err) : ""; }

// --- tabs -------------------------------------------------------------------
document.querySelectorAll(".tab").forEach(btn => btn.addEventListener("click", () => {
  document.querySelectorAll(".tab").forEach(b => b.classList.remove("active"));
  btn.classList.add("active");
  ["make", "board", "sourcing", "analytics", "settings"].forEach(t =>
    $("tab-" + t).hidden = t !== btn.dataset.tab);
  if (btn.dataset.tab === "board") { renderBoard(); loadQueue(); }
  if (btn.dataset.tab === "analytics") loadAnalytics();
}));

// --- meta / settings ----------------------------------------------------------
async function loadMeta() {
  const meta = await api("/api/meta");
  metaCache = meta;
  $("provider-badge").textContent = "provider: " + meta.provider +
    (meta.provider === "stub" ? " (데모용 자리표시자)" : "");
  const opts = meta.topics.map(t => `<option>${t}</option>`).join("");
  $("topic").innerHTML = opts; $("src-topic").innerHTML = opts;
  manualCheckItems = meta.manual_checks;
  $("manual-checks").innerHTML = manualCheckItems.map(item =>
    `<label><input type="checkbox" class="mcheck" value="${item}"> ${item}</label><br>`).join("");
  $("loc-buttons").innerHTML = meta.targets.map(lang =>
    `<button class="loc-btn" data-lang="${lang}">${lang} 버전</button>`).join("");
  document.querySelectorAll(".loc-btn").forEach(b => b.addEventListener("click", async () => {
    try { const m = await api(`/api/materials/${currentId}/localize`, { lang: b.dataset.lang }); renderRenders(m); }
    catch (e) { showError(e); }
  }));
  // settings form
  const settings = await api("/api/settings");
  const langs = settings.languages.targets || [];
  $("set-langs").innerHTML = Object.entries(meta.languages)
    .filter(([code]) => code !== "ko")
    .map(([code, [name]]) => `<label><input type="checkbox" class="lang-check" value="${code}" ${langs.includes(code) ? "checked" : ""}> ${code} (${name})</label> `).join("");
  $("set-accent").value = settings.render.accent_color || "#FFE600";
  $("set-fontsize").value = settings.render.font_size || 64;
  $("set-count").value = settings.copy.candidate_count || 5;
  $("set-min").value = settings.copy.min_chars || 15;
  $("set-max").value = settings.copy.max_chars || 28;
  const th = meta.region_monthly_min_views || {};
  $("threshold-note").textContent =
    "참고: 사진 보너스 월 최소 조회수 (Meta 공개 규칙) — 한국 " +
    (th.KR || 0).toLocaleString() + " / 미국 " + (th.US || 0).toLocaleString() +
    " / 일본 " + (th.JP || 0).toLocaleString() + ". 초대 보장 조건이 아니라 후보군 기준입니다.";
}

$("btn-settings-save").addEventListener("click", async () => {
  try {
    const targets = [...document.querySelectorAll(".lang-check")].filter(c => c.checked).map(c => c.value);
    const r = await api("/api/settings", {
      languages: { base: "ko", targets },
      render: { accent_color: $("set-accent").value, font_size: Number($("set-fontsize").value) },
      copy: { candidate_count: Number($("set-count").value),
              min_chars: Number($("set-min").value), max_chars: Number($("set-max").value),
              max_lines: 2 },
    });
    $("settings-result").textContent = r.note;
    await loadMeta();
  } catch (e) { showError(e); }
});

// --- materials ----------------------------------------------------------------
async function loadMaterials() {
  allMaterials = await api("/api/materials");
  $("materials").innerHTML = allMaterials.map(m => `
    <div class="mat" data-id="${m.id}">
      <img src="/api/files/${m.image_rel}">
      <div>${m.topic || "-"}<br><span class="status">${m.status}</span></div>
      <div>${m.fact || ""}</div>
    </div>`).join("") || "<p>아직 소재가 없습니다.</p>";
  document.querySelectorAll(".mat").forEach(el =>
    el.addEventListener("click", () => openWorkbench(el.dataset.id)));
}

function openWorkbench(id) {
  currentId = id;
  const m = allMaterials.find(x => x.id === id);
  if (!m) return;
  $("workbench").hidden = false;
  $("wb-title").textContent = `${m.topic} / ${m.status}`;
  $("wb-image").src = "/api/files/" + m.image_rel;
  $("fact").value = m.fact || "";
  renderCopies(m); renderRenders(m);
}

function renderCopies(m) {
  $("copies").innerHTML = (m.copies || []).map(c => `
    <div class="copy ${c.valid ? "" : "invalid"}" data-text="${c.text.replace(/"/g, "&quot;")}">
      ${c.text}<span class="note">[${c.lang}] ${c.note}${c.valid ? "" : " / " + (c.issues || []).join(", ")}</span>
    </div>`).join("");
  document.querySelectorAll(".copy").forEach(el =>
    el.addEventListener("click", () => { $("chosen").value = el.dataset.text; }));
}

function renderRenders(m) {
  $("renders").innerHTML = Object.entries(m.renders || {}).map(([lang, rel]) =>
    `<figure style="display:inline-block;margin:4px"><img src="/api/files/${rel}"><figcaption>${lang}</figcaption></figure>`).join("");
  $("slide-renders").innerHTML = (m.slide_renders || []).map((rel, i) =>
    `<figure style="display:inline-block;margin:4px"><img src="/api/files/${rel}"><figcaption>슬라이드 ${i + 1}</figcaption></figure>`).join("");
  if ((m.slides || []).length && !$("slides-input").value) {
    $("slides-input").value = m.slides.map(s =>
      s.text + (s.prompt ? "\n> " + s.prompt : "")).join("\n\n");
  }
}

function parseSlidesInput() {
  return $("slides-input").value.split(/\n\s*\n/).map(block => {
    const lines = block.split("\n").map(l => l.trim()).filter(Boolean);
    const promptLine = lines.find(l => l.startsWith(">"));
    return {
      text: lines.filter(l => !l.startsWith(">")).join("\n"),
      prompt: promptLine ? promptLine.slice(1).trim() : "",
    };
  }).filter(s => s.text);
}

$("btn-slides").addEventListener("click", async () => {
  try {
    const m = await api(`/api/materials/${currentId}/slides`, { slides: parseSlidesInput() });
    $("slides-result").textContent = `슬라이드 ${m.slides.length}장 설정됨`;
  } catch (e) { showError(e); }
});
$("btn-slides-gen").addEventListener("click", async () => {
  try {
    const count = parseSlidesInput().length;
    for (let i = 0; i < count; i++) {
      await api(`/api/materials/${currentId}/slides/${i}`, {});
    }
    $("slides-result").textContent = "이미지 생성 완료 — 합성을 누르세요";
  } catch (e) { showError(e); }
});

async function refresh() { await loadMaterials(); if (currentId) openWorkbench(currentId); }

// --- board / batch --------------------------------------------------------------
function renderBoard() {
  const groups = {};
  allMaterials.forEach(m => { (groups[m.status] = groups[m.status] || []).push(m); });
  $("board").innerHTML = Object.entries(groups).map(([status, items]) => `
    <h3>${status} (${items.length})</h3>
    ${items.map(m => `<div class="mat">
      <label><input type="checkbox" class="batch-check" value="${m.id}"></label>
      <img src="/api/files/${m.image_rel}">
      <div>${m.topic}<br><span class="status">${m.fact || ""}</span></div>
      ${m.views != null ? `<div>조회 ${m.views.toLocaleString()}</div>` : ""}
    </div>`).join("")}`).join("") || "<p>소재가 없습니다.</p>";
}

async function runBatch(action) {
  try {
    const ids = [...document.querySelectorAll(".batch-check")].filter(c => c.checked).map(c => c.value);
    if (!ids.length) throw new Error("선택된 소재가 없습니다");
    const results = await api("/api/batch", { ids, action });
    $("batch-result").textContent = results.map(r =>
      `${r.id}: ${r.ok ? "OK" : "실패 - " + r.error}`).join("\n");
    await loadMaterials(); renderBoard();
  } catch (e) { showError(e); }
}
$("btn-batch-copies").addEventListener("click", () => runBatch("copies"));
$("btn-batch-render").addEventListener("click", () => runBatch("render"));
$("btn-batch-loc").addEventListener("click", () => runBatch("localize"));

// --- sourcing -------------------------------------------------------------------
$("btn-queries").addEventListener("click", () => {
  const topicEn = { "동물": "animals", "운동": "sports", "우주": "space", "음식·요리": "food",
    "건강": "health", "가족": "family", "직장": "work life", "돈·경제": "money",
    "여행": "travel", "결혼": "wedding", "학교·학창시절": "school life", "소비·생활": "shopping",
    "연예·남녀관계": "dating", "자동차·교통": "cars traffic", "군대·남자공감": "military life" };
  const t = $("src-topic").value; const en = topicEn[t] || t;
  const queries = [`${en} viral story most shared`, `${en} unbelievable true story photo`,
    `${t} 話題 写真`, `site:reddit.com ${en} story`, `${en} news oddity viral`];
  $("queries").innerHTML = queries.map(q =>
    `<div class="copy"><a target="_blank" href="https://www.google.com/search?q=${encodeURIComponent(q)}">${q}</a></div>`).join("");
});

async function loadCandidates() {
  const list = await api("/api/candidates");
  $("candidates").innerHTML = list.map(c => `
    <div class="mat">
      <div><a href="${c.url}" target="_blank">${c.url}</a><br>
      <span class="status">${c.topic} / ${c.status}</span> ${c.note || ""}</div>
      <button class="cand-adopt" data-id="${c.id}">채택</button>
      <button class="cand-drop" data-id="${c.id}">버림</button>
      <button class="cand-use" data-id="${c.id}" data-url="${c.url}">소재 등록에 사용</button>
      <button class="cand-regen" data-url="${c.url}" data-note="${(c.note || "").replace(/"/g, "&quot;")}">이 스토리로 AI 재생성</button>
    </div>`).join("") || "<p>후보가 없습니다.</p>";
  document.querySelectorAll(".cand-adopt").forEach(b => b.addEventListener("click", async () => {
    await api(`/api/candidates/${b.dataset.id}`, { status: "채택" }); loadCandidates(); }));
  document.querySelectorAll(".cand-drop").forEach(b => b.addEventListener("click", async () => {
    await api(`/api/candidates/${b.dataset.id}`, { status: "버림" }); loadCandidates(); }));
  document.querySelectorAll(".cand-use").forEach(b => b.addEventListener("click", () => {
    $("source").value = b.dataset.url;
    document.querySelector('[data-tab="make"]').click();
    window.scrollTo(0, 0);
  }));
  document.querySelectorAll(".cand-regen").forEach(b => b.addEventListener("click", () => {
    $("regen-url").value = b.dataset.url;
    window.scrollTo(0, 0);
    $("regen-prompt").focus();
  }));
}
$("btn-regen").addEventListener("click", async () => {
  try {
    const m = await api("/api/materials/regenerate", {
      story_url: $("regen-url").value, prompt: $("regen-prompt").value,
      topic: $("src-topic").value, fact: $("regen-fact").value });
    $("regen-result").textContent = `소재 등록됨: ${m.id} (제작 탭에서 계속)`;
    currentId = m.id; await refresh();
  } catch (e) { showError(e); }
});

$("btn-cand-add").addEventListener("click", async () => {
  try {
    await api("/api/candidates", { topic: $("src-topic").value,
      url: $("cand-url").value, note: $("cand-note").value });
    $("cand-url").value = ""; $("cand-note").value = ""; loadCandidates();
  } catch (e) { showError(e); }
});

// --- analytics --------------------------------------------------------------------
async function loadAnalytics() {
  try {
    const a = await api("/api/analytics");
    const topics = Object.entries(a.by_topic).map(([t, b]) =>
      `<div class="copy">${t}: ${b.count}건, 총 ${b.views.toLocaleString()}, 평균 ${b.avg_views.toLocaleString()}</div>`).join("");
    const top = a.top.map(m =>
      `<div class="copy">${(m.views || 0).toLocaleString()} — ${m.copy || m.fact} <span class="note">${m.topic}</span></div>`).join("");
    $("analytics").innerHTML =
      `<p>전체 소재 ${a.total_materials} / 게시 ${a.posted} / 총 조회 ${(a.total_views || 0).toLocaleString()} ` +
      `(한국 월 최소 기준 ${a.kr_monthly_min_views.toLocaleString()})</p><h3>주제별</h3>${topics || "<p>기록 없음</p>"}<h3>상위 게시물</h3>${top || "<p>기록 없음</p>"}`;
    const patterns = await api("/api/patterns");
    $("patterns").innerHTML = patterns.map(p =>
      `<div class="copy">${p.text}<span class="note">${p.topic}</span></div>`).join("") || "<p>아직 승인 패턴이 없습니다. 카피를 확정하면 쌓입니다.</p>";
  } catch (e) { showError(e); }
}
$("btn-analytics").addEventListener("click", loadAnalytics);

// --- workbench actions --------------------------------------------------------------
$("btn-register").addEventListener("click", async () => {
  try {
    showError("");
    const file = $("file").files[0];
    if (!file) throw new Error("이미지 파일을 선택하세요");
    const buf = await file.arrayBuffer();
    let binary = ""; const bytes = new Uint8Array(buf);
    for (let i = 0; i < bytes.length; i += 8192)
      binary += String.fromCharCode.apply(null, bytes.subarray(i, i + 8192));
    const m = await api("/api/materials", {
      filename: file.name, data_base64: btoa(binary),
      source: $("source").value, topic: $("topic").value, rights: $("rights").value });
    currentId = m.id; await refresh(); openWorkbench(m.id);
  } catch (e) { showError(e); }
});
$("btn-analyze").addEventListener("click", async () => {
  try {
    const m = await api(`/api/materials/${currentId}/analyze`, {});
    $("fact-candidates").textContent = "후보: " + (m.fact_candidates || []).join(" | ");
    if (m.fact_candidates && m.fact_candidates[0]) $("fact").value = m.fact_candidates[0];
  } catch (e) { showError(e); }
});
$("btn-fact").addEventListener("click", async () => {
  try { await api(`/api/materials/${currentId}/fact`, { fact: $("fact").value }); await refresh(); }
  catch (e) { showError(e); }
});
$("btn-copies").addEventListener("click", async () => {
  try {
    const m = await api(`/api/materials/${currentId}/copies`, { humor: $("humor").checked });
    renderCopies(m); await loadMaterials();
  } catch (e) { showError(e); }
});
$("btn-choose").addEventListener("click", async () => {
  try {
    await api(`/api/materials/${currentId}/choose`,
      { text: $("chosen").value, highlight: $("highlight").value });
    await refresh();
  } catch (e) { showError(e); }
});
$("btn-render").addEventListener("click", async () => {
  try { const m = await api(`/api/materials/${currentId}/render`, {}); renderRenders(m); await loadMaterials(); }
  catch (e) { showError(e); }
});
$("btn-loc-all").addEventListener("click", async () => {
  try { const m = await api(`/api/materials/${currentId}/localize_all`, {}); renderRenders(m); renderCopies(m); }
  catch (e) { showError(e); }
});
$("btn-review").addEventListener("click", async () => {
  try {
    const checks = [...document.querySelectorAll(".mcheck")].filter(c => c.checked).map(c => c.value);
    const m = await api(`/api/materials/${currentId}/review`, { manual_checks: checks });
    $("review-result").textContent =
      "상태: " + m.status + "\n자동 발견: " + JSON.stringify(m.review.auto_findings) +
      "\n차단 사유: " + JSON.stringify(m.review.blockers);
  } catch (e) { showError(e); }
});
$("btn-export").addEventListener("click", async () => {
  try {
    const r = await api(`/api/materials/${currentId}/export`, {});
    $("export-result").innerHTML = `패키지: <a href="/api/files/${r.zip}">zip 다운로드</a>`;
  } catch (e) { showError(e); }
});
$("btn-enqueue").addEventListener("click", async () => {
  try {
    const q = await api(`/api/materials/${currentId}/enqueue`, {});
    $("enqueue-result").textContent = `큐 등록됨 (${q.langs.join(", ")}) — 운영자가 게시합니다`;
  } catch (e) { showError(e); }
});

async function loadQueue() {
  try {
    const list = await api("/api/queue");
    $("queue").innerHTML = list.map(q => `
      <div class="copy">
        <b>${q.status}</b> — ${q.caption.split("\n")[0]}
        <span class="note">소재 ${q.material_id} / 언어 ${q.langs.join(",")} / 등록 ${q.created_at}${q.scheduled_for ? " / 게시 목표 " + q.scheduled_for : ""}</span>
        ${q.post_url ? `<br><a href="${q.post_url}" target="_blank">${q.post_url}</a>` : ""}
        ${q.error ? `<br>오류: ${q.error}` : ""}
        ${q.status === "대기" ? `<br>
          <input type="text" class="q-url" data-id="${q.id}" placeholder="게시 후 URL (운영자 기록용)" size="36">
          <button class="q-done" data-id="${q.id}">게시완료 기록</button>
          <button class="q-cancel" data-id="${q.id}">취소</button>` : ""}
      </div>`).join("") || "<p>큐가 비어 있습니다.</p>";
    document.querySelectorAll(".q-done").forEach(b => b.addEventListener("click", async () => {
      const url = document.querySelector(`.q-url[data-id="${b.dataset.id}"]`).value;
      await api(`/api/queue/${b.dataset.id}/result`, { status: "게시완료", post_url: url });
      loadQueue(); await loadMaterials(); renderBoard();
    }));
    document.querySelectorAll(".q-cancel").forEach(b => b.addEventListener("click", async () => {
      await api(`/api/queue/${b.dataset.id}/result`, { status: "취소" }); loadQueue();
    }));
  } catch (e) { showError(e); }
}
$("btn-queue-refresh").addEventListener("click", loadQueue);

$("btn-views").addEventListener("click", async () => {
  try {
    await api(`/api/materials/${currentId}/views`, { views: Number($("views").value || 0) });
    await refresh();
  } catch (e) { showError(e); }
});

loadMeta().then(async () => { await loadMaterials(); loadCandidates(); }).catch(showError);
