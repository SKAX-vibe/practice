'use strict';

/*
 * 실습 결과 대시보드
 * - 화면은 data/dashboard.json(공개용 집계)만 읽는다. 각 트랙의 원문 파일은 읽지 않는다.
 * - data/dashboard.json은 tools/build_data.py가 report/ 결과물에서 생성한다.
 */

const DATA_URL = 'data/dashboard.json';

/* ---------- Utilities ---------- */

const $ = (sel, el = document) => el.querySelector(sel);
const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

/* ---------- Charts (HTML 막대) ---------- */

const STATUS = {
  '일치': { tone: 'good', icon: '✓', color: 'var(--good)' },
  '금액 차이': { tone: 'serious', icon: '!', color: 'var(--serious)' },
  '계산서 없음': { tone: 'critical', icon: '✕', color: 'var(--critical)' },
};
const statusPill = (v) => {
  const s = STATUS[v];
  return s ? `<span class="pill pill-${s.tone}">${s.icon} ${esc(v)}</span>` : esc(v);
};

const axisHtml = (ticks) => (ticks
  ? `<div class="bar-axis"><span></span><div class="bar-axis-ticks">${ticks.map((t) => `<span>${esc(t)}</span>`).join('')}</div></div>`
  : '');

const barLine = (value, max, color, tip, display, grid) => `
  <div class="bar-line">
    <div class="bar-track${grid ? ' has-grid' : ''}">
      <div class="bar-fill" style="width:${Math.max(0, (value / max) * 100)}%;background:${color}" data-tip="${esc(tip)}"></div>
    </div>
    <span class="bar-value">${esc(display)}</span>
  </div>`;

/** 단일 계열 가로 막대 */
function barChart(c, max) {
  const top = max ?? Math.max(...c.items.map((d) => d.value)) * 1.08;
  const rows = c.items.map((d) => `
    <div class="bar-row">
      <div class="bar-label" title="${esc(d.label)}">${esc(d.label)}</div>
      ${barLine(d.value, top, 'var(--series-1)', `<strong>${esc(d.label)}</strong>${esc(d.tip ?? d.display)}`, d.display, c.ticks)}
    </div>`).join('');
  const label = c.items.map((d) => `${d.label} ${d.display}`).join(', ');
  return `<div class="bars" role="img" aria-label="${esc(`${c.title}: ${label}`)}">${rows}</div>${axisHtml(c.ticks)}`;
}

/** 그룹 가로 막대 (계열 2개 이하) */
function groupedBarChart(c) {
  const color = (s) => `var(--series-${c.series.indexOf(s) + 1})`;
  const legend = `<div class="legend">${c.series.map((s) => `<span class="legend-item"><span class="swatch" style="background:${color(s)}"></span>${esc(s)}</span>`).join('')}</div>`;
  const rows = c.groups.map((g) => `
    <div class="bar-row">
      <div class="bar-label" title="${esc(g.label)}">${esc(g.label)}</div>
      <div class="bar-stack">
        ${g.values.map((v) => barLine(v.value, c.max, color(v.series), `<strong>${esc(g.label)} · ${esc(v.series)}</strong>${esc(v.tip ?? v.display)}`, v.display, c.ticks)).join('')}
      </div>
    </div>`).join('');
  return `${legend}<div class="bars">${rows}</div>${axisHtml(c.ticks)}`;
}

/** 상태 구성 막대 + 아이콘 · 라벨 범례 */
function statusChart(c) {
  const total = c.items.reduce((a, b) => a + b.count, 0);
  const segs = c.items.filter((d) => d.count > 0).map((d) => `<div class="stack-seg" style="flex:${d.count};background:${STATUS[d.name].color}"
      data-tip="<strong>${esc(d.name)}</strong>${d.count}건 (${((d.count / total) * 100).toFixed(1)}%)"></div>`).join('');
  const legend = c.items.map((d) => `
    <div class="status-item">
      <div class="status-name"><span class="status-icon" style="background:${STATUS[d.name].color}" aria-hidden="true">${STATUS[d.name].icon}</span>${esc(d.name)}</div>
      <div class="status-count">${d.count}건</div>
    </div>`).join('');
  return `<div class="stack-bar" role="img" aria-label="${esc(c.items.map((d) => `${d.name} ${d.count}건`).join(', '))}">${segs}</div><div class="status-list">${legend}</div>`;
}

function chartHtml(c, sharedMax) {
  if (c.type === 'grouped') return groupedBarChart(c);
  if (c.type === 'status') return statusChart(c);
  return barChart(c, sharedMax);
}

/* ---------- View pieces ---------- */

function tableHtml(t) {
  const cls = (i) => (t.align?.[i] === 'right' ? ' class="num"' : '');
  const totals = new Set(t.total_rows ?? []);
  const rows = [...t.rows.map((r, i) => [r, totals.has(i)]), ...(t.total ? [[t.total, true]] : [])];
  const head = t.headers.map((h, i) => `<th${cls(i)} scope="col">${esc(h)}</th>`).join('');
  const body = rows.map(([r, isTotal]) => `<tr${isTotal ? ' class="total"' : ''}>${r.map((v, i) =>
    `<td${cls(i)}>${i === t.status_col && !isTotal ? statusPill(v) : esc(v)}</td>`).join('')}</tr>`).join('');
  return `<div class="table-wrap"><table><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table></div>`;
}

const kpiHtml = (k) => `
  <div class="kpi${k.tone ? ` is-${k.tone}` : ''}">
    <div class="kpi-label">${esc(k.label)}</div>
    <div class="kpi-value">${esc(k.value)}</div>
    ${k.sub ? `<div class="kpi-sub">${esc(k.sub)}</div>` : ''}
  </div>`;

const card = (title, body, extra = '') => `
  <section class="card">
    <div class="card-head"><h3>${esc(title)}</h3>${extra}</div>
    <div class="card-body">${body}</div>
  </section>`;

const verdictBadge = (v) => (v === 'PASS'
  ? '<span class="badge badge-pass">✓ PASS</span>'
  : v ? `<span class="badge badge-fail">✕ ${esc(v)}</span>` : '<span class="badge badge-unknown">확인 불가</span>');

function verifyCard(v) {
  const pass = v.final === 'PASS';
  const rows = v.checks.map((c) => `
    <tr>
      <td>${esc(c.method)}</td>
      <td>${c.result === 'PASS' ? '<span class="pill pill-good">✓ PASS</span>' : `<span class="pill pill-critical">✕ ${esc(c.result)}</span>`}</td>
      <td class="num">${c.total ? `${c.passed} / ${c.total} 항목` : '-'}</td>
    </tr>`).join('');
  return card('검증 결과', `
    <div class="verify-summary ${pass ? 'pass' : 'fail'}">
      <div class="verify-big">${pass ? '✓ PASS' : `✕ ${esc(v.final || '결과 없음')}`}</div>
      <div class="verify-meta">최종 결과 · 실행일 ${esc(v.run_date || '-')} · 기준일 ${esc(v.base_date || '-')}</div>
    </div>
    <div class="table-wrap"><table>
      <thead><tr><th scope="col">검증 방법</th><th scope="col">결과</th><th class="num" scope="col">통과 항목</th></tr></thead>
      <tbody>${rows}</tbody>
    </table></div>`);
}

/* ---------- Track view ---------- */

let DATA = null;

function renderTrack(id) {
  const t = DATA.tracks.find((x) => x.id === id) || DATA.tracks[0];
  document.querySelectorAll('.track-tab').forEach((b) => {
    const on = b.dataset.id === t.id;
    b.setAttribute('aria-selected', String(on));
    b.tabIndex = on ? 0 : -1;
  });
  const bars = t.charts.filter((c) => c.type === 'bar');
  const sharedMax = bars.length > 1 ? Math.max(...bars.flatMap((c) => c.items.map((d) => d.value))) * 1.08 : undefined;
  const charts = t.charts.map((c, i) => `${i ? '<div class="chart-gap"></div>' : ''}<h4 class="chart-title">${esc(c.title)}</h4>${chartHtml(c, sharedMax)}`).join('');
  const chartTitle = t.charts.length > 1 ? '현황 차트' : t.charts[0].title;

  $('#trackView').innerHTML = `
    <div class="track-head">
      <div>
        <h2>${esc(t.id)} · ${esc(t.name)} — ${esc(t.desc)}</h2>
        <div class="track-meta"><span>기준일 ${esc(t.verify.base_date || '-')}</span><span>검증 실행일 ${esc(t.verify.run_date || '-')}</span></div>
      </div>
      ${verdictBadge(t.verify.final)}
    </div>
    ${t.note ? `<p class="info" role="note"><span class="info-icon" aria-hidden="true">i</span>${esc(t.note)}</p>` : ''}
    <div class="kpis">${t.kpis.map(kpiHtml).join('')}</div>
    <div class="grid-2">
      ${card(chartTitle, t.charts.length > 1 ? charts : chartHtml(t.charts[0]))}
      ${verifyCard(t.verify)}
    </div>
    ${t.tables.map((tb) => card(tb.title, tableHtml(tb))).join('')}
    <p class="sources">집계 출처: ${t.sources.map((s) => `<code>${esc(s)}</code>`).join(' ')}</p>`;
}

/* ---------- Tabs ---------- */

function buildTabs() {
  const nav = $('#trackTabs');
  nav.innerHTML = DATA.tracks.map((t) => `
    <button type="button" class="track-tab" role="tab" data-id="${esc(t.id)}" aria-selected="false" aria-controls="trackView">
      <span class="tab-top"><span class="tab-letter">TRACK ${esc(t.id)}</span>${verdictBadge(t.verify.final)}</span>
      <span class="tab-name">${esc(t.name)}</span>
      <span class="tab-desc">${esc(t.desc)}</span>
    </button>`).join('');
  nav.addEventListener('click', (e) => {
    const b = e.target.closest('.track-tab');
    if (b) location.hash = b.dataset.id;
  });
  nav.addEventListener('keydown', (e) => {
    if (!['ArrowLeft', 'ArrowRight'].includes(e.key)) return;
    const tabs = [...nav.querySelectorAll('.track-tab')];
    const i = tabs.indexOf(document.activeElement);
    if (i < 0) return;
    const next = tabs[(i + (e.key === 'ArrowRight' ? 1 : tabs.length - 1)) % tabs.length];
    next.focus();
    location.hash = next.dataset.id;
  });
}

/* ---------- Tooltip ---------- */

function initTooltip() {
  const tip = $('#tip');
  document.addEventListener('mouseover', (e) => {
    const el = e.target.closest('[data-tip]');
    if (!el) { tip.hidden = true; return; }
    tip.innerHTML = el.dataset.tip;
    tip.hidden = false;
  });
  document.addEventListener('mousemove', (e) => {
    if (tip.hidden) return;
    const w = tip.offsetWidth, h = tip.offsetHeight;
    tip.style.left = `${Math.min(e.clientX + 12, window.innerWidth - w - 8)}px`;
    tip.style.top = `${e.clientY - h - 10 < 8 ? e.clientY + 16 : e.clientY - h - 10}px`;
  });
}

/* ---------- Theme ---------- */

function initTheme() {
  const root = document.documentElement;
  try { const saved = localStorage.getItem('dash-theme'); if (saved) root.dataset.theme = saved; } catch { /* 저장소 사용 불가 */ }
  $('#themeToggle').addEventListener('click', () => {
    const dark = root.dataset.theme ? root.dataset.theme === 'dark' : matchMedia('(prefers-color-scheme: dark)').matches;
    root.dataset.theme = dark ? 'light' : 'dark';
    try { localStorage.setItem('dash-theme', root.dataset.theme); } catch { /* 무시 */ }
  });
}

/* ---------- Boot ---------- */

async function boot() {
  initTheme();
  initTooltip();
  try {
    const res = await fetch(DATA_URL, { cache: 'no-cache' });
    if (!res.ok) throw new Error(`${DATA_URL} (HTTP ${res.status})`);
    DATA = await res.json();
  } catch (e) {
    const n = $('#notice');
    n.hidden = false;
    n.innerHTML = `데이터를 불러오지 못했습니다: ${esc(e.message)}<br>파일을 직접 열면(file://) 브라우저가 읽기를 막습니다. <code>dashboard</code> 폴더에서 <code>python -m http.server 8000</code> 실행 후 <code>http://localhost:8000/</code>으로 여세요.`;
    $('#trackView').innerHTML = '';
    return;
  }
  buildTabs();
  const route = () => renderTrack((location.hash.slice(1) || 'A').toUpperCase());
  window.addEventListener('hashchange', route);
  route();
}

boot();
