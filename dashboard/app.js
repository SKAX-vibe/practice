'use strict';

/*
 * 실습 결과 대시보드
 * - 화면은 data/dashboard.json 한 파일만 읽는다 (내부: 실제 집계 / 공개: 가상 데모).
 * - 화면 구성: 개요(#overview) + 트랙 상세(#A ~ #D). 트랙 상세는 업무별로 구성이 다르다.
 * - 수치는 모두 {value, unit} 로 받아 단위를 붙여 표시한다. 화면에서 새 수치를 만들지 않고,
 *   비율 · 합계처럼 데이터 안의 값으로 계산되는 것만 계산한다.
 */

const DATA_URL = 'data/dashboard.json';

/* ---------- Utilities ---------- */

const $ = (sel, el = document) => el.querySelector(sel);
const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

/** {value, unit} → 표시 문자열. signed: 금액 차이처럼 부호를 붙인다. */
function fmt(q, { signed = false } = {}) {
  if (!q) return '-';
  const { value, unit } = q;
  if (unit === '%') return `${Number(value).toFixed(1)}%`;
  const abs = Math.abs(value).toLocaleString('ko-KR');
  const sign = signed ? (value > 0 ? '+' : value < 0 ? '−' : '') : (value < 0 ? '−' : '');
  return `${sign}${abs}${unit}`;
}
const ratio = (a, b) => `${Number(a.value).toLocaleString('ko-KR')} / ${fmt(b)}`;
const share = (part, whole) => (whole ? `${((part / whole) * 100).toFixed(1)}%` : '-');

let DATA = null;
const isDemo = () => DATA?.mode === 'demo';
const trackById = (id) => DATA.tracks.find((t) => t.id === id);

/* ---------- Shared pieces ---------- */

const STATUS = {
  '일치': { icon: '✓', color: 'var(--good)' },
  '금액 차이': { icon: '!', color: 'var(--serious)' },
  '계산서 없음': { icon: '✕', color: 'var(--critical)' },
  '조치 완료': { icon: '✓', color: 'var(--good)' },
  '조치 중': { icon: '…', color: 'var(--neutral)' },
  '조치 미기재': { icon: '!', color: 'var(--critical)' },
};

const meter = (value, max, tip) => `
  <div class="meter" role="presentation"><div class="meter-fill" style="width:${max ? Math.max(0, (value / max) * 100) : 0}%"${tip ? ` data-tip="${esc(tip)}"` : ''}></div></div>`;

const section = (title, body, note = '') => `
  <section class="section">
    <div class="section-head"><h2 class="section-title">${esc(title)}</h2>${note ? `<p class="section-note">${note}</p>` : ''}</div>
    ${body}
  </section>`;

function flowStrip(flow) {
  const step = (cls, label, items) => `
    <div class="flow-step ${cls}">
      <p class="flow-label">${label}</p>
      <ul class="flow-items">${items.map((i) => `
        <li class="flow-item"><span class="flow-value num">${esc(fmt(i))}</span><span class="flow-name">${esc(i.label)}</span></li>`).join('')}
      </ul>
    </div>`;
  return `<div class="flow" aria-label="업무 흐름">
    ${step('input', '입력', flow.input)}
    ${step('output', '자동 산출', flow.output)}
    ${step('review', '사람 확인 필요', flow.review)}
  </div>`;
}

function verdictHtml(v) {
  if (v.final === 'DEMO') return '<span class="verdict demo">예시</span>';
  if (v.final === 'PASS') return '<span class="verdict pass">✓ PASS</span>';
  return `<span class="verdict fail">✕ ${esc(v.final || '결과 없음')}</span>`;
}

function verifyLine(v) {
  if (v.final === 'DEMO') {
    return `<div class="verify-line"><span class="label">검증</span>${verdictHtml(v)}</div>`;
  }
  const parts = [];
  if (v.script) parts.push(`자동 검증 ${ratio(v.script.passed, v.script.total)}`);
  if (v.factual) parts.push(`사실성 검토 ${esc(v.factual)}`);
  return `<div class="verify-line">
    <span class="label">검증</span>${verdictHtml(v)}
    <span>${parts.map(esc).join(' · ')}</span>
    <span class="meta">실행일 ${esc(v.run_date || '-')} · 기준일 ${esc(v.base_date || '-')}</span>
  </div>`;
}

/** 그레이 단색 농도: t(0~1)가 클수록 진하게. 글자색은 배경에 맞춰 바꾼다. */
function heatCell(t, inner, tip) {
  const L = Math.round(96 - Math.max(0, Math.min(1, t)) * 70);
  return `<td class="heat" style="background:hsl(0 0% ${L}%);color:${L < 47 ? '#fff' : '#000'}" data-tip="${esc(tip)}">${inner}</td>`;
}
const heatLegend = (lo, hi, label) => `
  <div class="heat-legend" aria-hidden="true"><span>${esc(label)}</span><span>${esc(lo)}</span><span class="heat-ramp"></span><span>${esc(hi)}</span></div>`;

/** 도넛: 조각 사이 2px 간격, 가운데 합계. 색은 상태 색이며 범례에 아이콘 · 라벨을 함께 둔다. */
function donut(items, total, centerLabel, label) {
  const r = 70, sw = 22, c = 2 * Math.PI * r, gap = 2;
  let offset = 0;
  const segs = items.filter((d) => d.value > 0).map((d) => {
    const len = (d.value / total) * c;
    const draw = Math.max(0, len - gap);
    const seg = `<circle class="donut-seg" data-verdict="${esc(d.name)}" r="${r}" cx="90" cy="90" fill="none" stroke="${STATUS[d.name].color}" stroke-width="${sw}"
      stroke-dasharray="${draw.toFixed(2)} ${(c - draw).toFixed(2)}" stroke-dashoffset="${(-offset).toFixed(2)}"
      data-tip="<strong>${esc(d.name)}</strong>${esc(d.text)} (${share(d.value, total)})"></circle>`;
    offset += len;
    return seg;
  }).join('');
  return `<svg class="donut" viewBox="0 0 180 180" role="img" aria-label="${esc(`${label}: ${items.map((d) => `${d.name} ${d.text}`).join(', ')}`)}">
      <g transform="rotate(-90 90 90)">${segs}</g>
      <text x="90" y="88" text-anchor="middle" class="donut-total">${esc(fmt({ value: total, unit: '건' }))}</text>
      <text x="90" y="112" text-anchor="middle" class="donut-label">${esc(centerLabel)}</text>
    </svg>`;
}

/** C: 도넛 조각 · 범례 ↔ 불일치 상세 행 연결 (hover · 포커스 강조, 클릭 시 상세로 이동) */
function linkVerdicts(root) {
  const rows = (name) => root.querySelectorAll(`#mismatch-detail tr[data-verdict="${CSS.escape(name)}"]`);
  const set = (name, on) => {
    rows(name).forEach((r) => r.classList.toggle('is-hl', on));
    root.querySelectorAll(`[data-verdict="${CSS.escape(name)}"]`).forEach((el) => el.classList.toggle('is-hl', on));
  };
  // 도넛 조각은 마우스 전용. SVG 요소에 포커스 이벤트를 달면 Chrome이 Tab 정지점으로 만들므로,
  // 키보드 조작은 범례 버튼(포커스 · Enter · Space)이 맡는다.
  const on = (el, name, events) => {
    el.addEventListener(events[0], () => set(name, true));
    el.addEventListener(events[1], () => set(name, false));
  };
  root.querySelectorAll('.donut-seg').forEach((el) => on(el, el.dataset.verdict, ['mouseenter', 'mouseleave']));
  root.querySelectorAll('.legend-col li').forEach((el) => {
    on(el, el.dataset.verdict, ['mouseenter', 'mouseleave']);
    on(el, el.dataset.verdict, ['focusin', 'focusout']);
  });
  root.querySelectorAll('button.legend-link').forEach((b) => b.addEventListener('click', () => {
    const r = rows(b.dataset.target)[0];
    if (!r) return;
    r.scrollIntoView({ behavior: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth', block: 'center' });
    r.focus({ preventScroll: true });
  }));
}

const linkLine = (from, to, ok, okText, gapText) => `
  <div class="link-line">
    <span>${from}</span><span class="arrow" aria-hidden="true">→</span><span>${to}</span>
    <span class="ok">${ok ? `✓ ${esc(okText)}` : esc(gapText)}</span>
  </div>`;

/* ---------- Track views (업무별 구성) ---------- */

const VIEWS = {
  /* A 영업: 문의별 처리 목록 하나가 중심 (금액 · 품목 · 확인 필요 · 초안을 한 표에) */
  quotes(t) {
    const d = t.detail;
    const max = Math.max(...d.inquiries.map((i) => i.amount.value));
    const drafted = d.inquiries.filter((i) => i.draft).length;
    const rows = d.inquiries.map((i) => `
      <tr>
        <td data-label="거래처">${esc(i.name)}</td>
        <td class="num" data-label="품목">${esc(fmt(i.items))}</td>
        <td data-label="견적 금액"><div class="inline-bar">${meter(i.amount.value, max, `${i.name} · ${fmt(i.amount)}`)}<span class="val num">${esc(fmt(i.amount))}</span></div></td>
        <td class="num" data-label="확인 필요 품목">${i.review.value
          ? `<span class="mark"><span class="dot" aria-hidden="true"></span>${esc(fmt(i.review))}</span>`
          : `<span class="mark zero">${esc(fmt(i.review))}</span>`}</td>
        <td data-label="회신 초안">${i.draft ? '작성' : '<strong>미작성</strong>'}</td>
      </tr>`).join('');
    const table = `<div class="block"><div class="table-wrap"><table class="stack-table">
      <thead><tr><th scope="col">거래처</th><th class="num" scope="col">품목</th><th scope="col">견적 금액</th><th class="num" scope="col">확인 필요 품목</th><th scope="col">회신 초안</th></tr></thead>
      <tbody>${rows}</tbody>
      <tfoot><tr>
        <td data-label="">합계</td>
        <td class="num" data-label="품목">${esc(fmt(d.items_total))}</td>
        <td data-label="견적 금액"><div class="inline-bar"><span class="val num" style="margin-left:auto">${esc(fmt(d.amount_total))}</span></div></td>
        <td class="num" data-label="확인 필요 품목">${esc(fmt(d.items_review))}</td>
        <td data-label="회신 초안">${drafted}건</td>
      </tr></tfoot>
    </table></div><p class="note">견적 금액: ${esc(d.amount_note)}</p></div>`;
    return section('문의별 처리 현황', table, `품목 ${esc(fmt(d.items_total))} 중 견적 반영 ${esc(fmt(d.items_quoted))} · 확인 필요 ${esc(fmt(d.items_review))}`);
  },

  /* B 인사: 과정별 이수율 → 부서 × 과정 히트맵 → 지연과 독려 초안 연결 */
  training(t) {
    const d = t.detail;
    const courses = d.courses.map((c) => `
      <div class="course">
        <p class="course-name">${esc(c.course)}</p>
        <p class="course-rate num">${esc(fmt(c.rate))}</p>
        ${meter(c.rate.value, 100, `${c.course} · ${fmt(c.rate)}`)}
        <p class="course-sub">이수 ${esc(fmt(c.done))} / 대상 ${esc(fmt(c.target))} · 미이수 ${esc(fmt({ value: c.target.value - c.done.value, unit: '명' }))}</p>
      </div>`).join('');
    const head = d.courses.map((c) => `<th scope="col">${esc(c.course)}</th>`).join('');
    const rows = d.groups.map((g) => `
      <tr><th scope="row">${esc(g.name)}<span class="heat-sub">대상 ${esc(fmt(g.size))}</span></th>
        ${g.cells.map((c) => heatCell(c.rate.value / 100, `<strong class="num">${esc(fmt(c.rate))}</strong><span class="heat-sub num">${c.done.value}/${esc(fmt(c.target))}</span>`,
          `${g.name} · ${c.course} · ${fmt(c.rate)} (이수 ${fmt(c.done)} / 대상 ${fmt(c.target)})`)).join('')}
      </tr>`).join('');
    const heat = `<div class="block"><div class="table-wrap"><table class="heatmap">
        <thead><tr><th scope="col">부서</th>${head}</tr></thead><tbody>${rows}</tbody>
      </table></div>
      ${heatLegend('0%', '100%', '이수율')}
      ${d.merge_note ? `<p class="note">${esc(d.merge_note)}</p>` : ''}</div>`;
    const ok = d.draft_count.value === d.late_people.value;
    return section('과정별 이수율', `<div class="course-grid">${courses}</div>`)
      + section('부서별 이수율', heat, '칸이 진할수록 이수율이 높음')
      + linkLine(
        `지연 <strong class="num">${esc(fmt(d.late_count))}</strong> (과정 기준) · 실인원 <strong class="num">${esc(fmt(d.late_people))}</strong>`,
        `독려 초안 <strong class="num">${esc(fmt(d.draft_count))}</strong> (1인 1건)`,
        ok, '지연 실인원 전원 초안 작성', '초안 수와 지연 실인원이 다릅니다 — 확인 필요');
  },

  /* C 재무 · 구매: 판정 구성 도넛 → 불일치 상세(판정별 거래처 · 금액) → 확인 요청 연결 */
  reconcile(t) {
    const d = t.detail;
    const total = d.verdicts.reduce((a, v) => a + v.count.value, 0);
    const legend = d.verdicts.map((v) => {
      const mismatch = v.name !== '일치';
      const inner = `
          <span class="icon" style="background:${STATUS[v.name].color}" aria-hidden="true">${STATUS[v.name].icon}</span>
          <span class="name">${esc(v.name)}</span><span class="count num">${esc(fmt(v.count))}</span><span class="share num">${share(v.count.value, total)}</span>
          ${mismatch ? '<span class="go" aria-hidden="true">상세 ↓</span>' : ''}`;
      return `<li data-verdict="${esc(v.name)}">${mismatch
        ? `<button type="button" class="legend-link" data-target="${esc(v.name)}" aria-label="${esc(`${v.name} ${fmt(v.count)} 상세 보기`)}">${inner}</button>`
        : `<span class="legend-link">${inner}</span>`}</li>`;
    }).join('');
    const donutBlock = `<div class="block donut-wrap">
        ${donut(d.verdicts.map((v) => ({ name: v.name, value: v.count.value, text: fmt(v.count) })), total, '발주', '판정 구성')}
        <ul class="legend legend-col">${legend}</ul>
      </div>`;
    const mis = d.verdicts.filter((v) => v.name !== '일치');
    const sum = (k) => ({ value: mis.reduce((a, v) => a + v[k].value, 0), unit: mis[0][k].unit });
    const rows = mis.map((v) => `
      <tr data-verdict="${esc(v.name)}" tabindex="-1">
        <td data-label="판정"><span class="mark"><span class="dot" style="background:${STATUS[v.name].color}" aria-hidden="true"></span>${esc(v.name)}</span></td>
        <td class="num" data-label="거래처">${esc(fmt(v.vendors))}</td>
        <td class="num" data-label="공급가액">${esc(fmt(v.supply))}</td>
        <td class="num" data-label="계산서 금액">${esc(fmt(v.invoice))}</td>
        <td class="num" data-label="차액">${esc(fmt(v.diff, { signed: true }))}</td>
      </tr>`).join('');
    const detail = `<div class="block"><div class="table-wrap"><table class="stack-table">
      <thead><tr><th scope="col">판정</th><th class="num" scope="col">거래처</th><th class="num" scope="col">공급가액</th><th class="num" scope="col">계산서 금액</th><th class="num" scope="col">차액</th></tr></thead>
      <tbody>${rows}</tbody>
      <tfoot><tr><td>불일치 합계</td><td class="num" data-label="거래처">${esc(fmt(d.mismatch_vendors))}</td><td class="num" data-label="공급가액">${esc(fmt(sum('supply')))}</td>
        <td class="num" data-label="계산서 금액">${esc(fmt(sum('invoice')))}</td><td class="num" data-label="차액">${esc(fmt(sum('diff'), { signed: true }))}</td></tr></tfoot>
    </table></div><p class="note">차액 = 계산서 금액 − 공급가액 · 계산서 없음은 차액 계산에서 제외 · 일치 판정은 차액 0원</p></div>`;
    const ok = d.draft_count.value === d.mismatch_vendors.value;
    return `<div class="split">
        ${section('판정 구성', donutBlock)}
        <div id="mismatch-detail">${section('불일치 상세', detail)}</div>
      </div>`
      + linkLine(
        `불일치 <strong class="num">${esc(fmt(d.mismatch))}</strong> · 거래처 <strong class="num">${esc(fmt(d.mismatch_vendors))}</strong>`,
        `확인 요청 초안 <strong class="num">${esc(fmt(d.draft_count))}</strong> (거래처별)`,
        ok, '불일치 거래처 전부 초안 작성', '초안 수와 불일치 거래처 수가 다릅니다 — 확인 필요');
  },

  /* D 품질 · IT: 조치 상태(숫자) → 확인 순서(정렬 기준) → 일별 불량 → 라인 × 유형 히트맵 */
  quality(t) {
    const d = t.detail;
    const order = ['조치 완료', '조치 중', '조치 미기재'];
    const status = [...d.status].sort((a, b) => order.indexOf(a.name) - order.indexOf(b.name)).map((s) => `
      <li class="${s.reports.value ? '' : 'zero'}"><span class="icon" style="background:${STATUS[s.name].color}" aria-hidden="true">${STATUS[s.name].icon}</span>
        <span class="name">${esc(s.name)}</span><strong class="num">${esc(fmt(s.reports))}</strong></li>`).join('');
    const statusLine = `<div class="status-chips" aria-label="조치 상태">
        <span class="label">조치 상태</span><ul>${status}</ul>
        <span class="progress num">완료 ${esc(ratio(d.done, d.reports))}</span>
      </div>`;

    const basis = d.order_basis.map((b, i) => `${i ? '<span class="gt" aria-hidden="true">›</span>' : ''}<span class="chip">${esc(b)}</span>`).join('');
    const items = d.order_groups.map((g) => `
      <li class="order-item">
        <div><p class="order-name">${esc(g.name)}</p><p class="order-count">보고 ${esc(fmt(g.reports))} · 불량 ${esc(fmt(g.qty))}</p></div>
        <div class="order-bar">${meter(g.qty.value, d.qty.value, `${g.name} · 불량 ${fmt(g.qty)} (${share(g.qty.value, d.qty.value)})`)}</div>
      </li>`).join('');
    const orderBlock = `<div class="block">
        <div class="order-basis"><span>정렬 기준</span>${basis}</div>
        <ol class="order-list">${items}</ol>
        <p class="note">확인 필요 보고를 살펴볼 순서입니다. 보고서의 정렬 기준을 따른 것이며, 원인이나 책임을 확정한 판정이 아닙니다.</p>
      </div>`;

    const maxDay = Math.max(...d.daily.map((x) => x.qty.value));
    const cols = d.daily.map((x) => `
      <li><span class="col-val num">${esc(fmt(x.qty))}</span>
        <span class="col-track"><span class="col-bar" style="height:${(x.qty.value / maxDay) * 100}%" data-tip="<strong>${esc(x.date)}</strong>불량 ${esc(fmt(x.qty))} · 보고 ${esc(fmt(x.reports))}"></span></span>
        <span class="col-date num">${esc(x.date)}</span><span class="col-sub num">${esc(fmt(x.reports))}</span></li>`).join('');
    const daily = `<div class="block"><ol class="cols" role="img" aria-label="${esc(`일별 불량 수량: ${d.daily.map((x) => `${x.date} ${fmt(x.qty)}`).join(', ')}`)}">${cols}</ol></div>`;

    const types = d.types.map((x) => x.name);
    const maxCell = Math.max(...d.matrix.map((m) => m.qty.value));
    const cell = (l, ty) => d.matrix.find((m) => m.line === l && m.type === ty);
    const total = (q, r) => `<td class="heat-total num"><strong>${esc(fmt(q))}</strong><span class="heat-sub">${esc(fmt(r))}</span></td>`;
    const rows = d.lines.map((l) => `
      <tr><th scope="row">${esc(l.name)}</th>
        ${types.map((ty) => {
          const m = cell(l.name, ty);
          return m ? heatCell(m.qty.value / maxCell, `<strong class="num">${esc(fmt(m.qty))}</strong><span class="heat-sub num">${esc(fmt(m.reports))}</span>`,
            `${l.name} · ${ty} · 불량 ${fmt(m.qty)} · 보고 ${fmt(m.reports)}`) : '<td class="heat-empty">–<span class="sr-only">없음</span></td>';
        }).join('')}
        ${total(l.qty, l.reports)}
      </tr>`).join('');
    const foot = d.types.map((x) => total(x.qty, x.reports)).join('');
    const matrix = `<div class="block"><div class="table-wrap"><table class="heatmap">
        <thead><tr><th scope="col">라인</th>${types.map((ty) => `<th scope="col">${esc(ty)}</th>`).join('')}<th scope="col">합계</th></tr></thead>
        <tbody>${rows}</tbody>
        <tfoot><tr><th scope="row">합계</th>${foot}${total(d.qty, d.reports)}</tr></tfoot>
      </table></div>${heatLegend('적음', '많음', '불량 수량')}</div>`;

    return statusLine
      + section('확인 순서', orderBlock, '정렬 기준 · 확정 판정 아님')
      + section('일별 불량 수량', daily, '막대: 불량 수량(개) · 아래: 보고 건수')
      + section('라인 × 유형 불량 수량', matrix, '칸: 불량 수량(개) · 아래: 보고 건수');
  },
};

/* ---------- Screens ---------- */

function renderOverview() {
  const tracks = DATA.tracks;
  let status;
  if (isDemo()) {
    status = `<div class="status-line"><span>${esc(DATA.notice)}</span></div>`;
  } else {
    const pass = tracks.filter((t) => t.verify.final === 'PASS').length;
    const scripted = tracks.filter((t) => t.verify.script);
    const passed = scripted.reduce((a, t) => a + t.verify.script.passed.value, 0);
    const total = scripted.reduce((a, t) => a + t.verify.script.total.value, 0);
    const dates = (k) => [...new Set(tracks.map((t) => t.verify[k]).filter(Boolean))].join(', ');
    status = `<div class="status-line">
      <strong>${pass === tracks.length ? '✓ ' : ''}자동 검증 PASS ${pass} / ${tracks.length}개 트랙</strong>
      <span>통과 ${passed.toLocaleString('ko-KR')} / ${total.toLocaleString('ko-KR')}항목</span>
      <span class="sep">기준일 ${esc(dates('base_date'))} · 실행일 ${esc(dates('run_date'))}</span>
    </div>`;
  }
  const cards = tracks.map((t) => {
    const list = (items) => items.map((i) => `<span>${esc(i.label)} ${esc(fmt(i))}</span>`).join('');
    const v = t.verify;
    const verify = v.final === 'DEMO' ? verdictHtml(v)
      : `${verdictHtml(v)}${v.script ? ` <span class="num" style="font-weight:400">${esc(ratio(v.script.passed, v.script.total))}</span>` : ''}`;
    return `<a class="track-card" href="#${esc(t.id)}">
      <div><p class="eyebrow">TRACK ${esc(t.id)} · ${esc(t.name)}</p><h2 class="track-card-title">${esc(t.task)}</h2></div>
      <dl class="facts">
        <dt>입력</dt><dd>${list(t.flow.input)}</dd>
        <dt>자동 산출</dt><dd>${list(t.flow.output)}</dd>
        <dt>사람 확인</dt><dd>${list(t.flow.review)}</dd>
        <dt>검증</dt><dd>${verify}</dd>
      </dl>
      <span class="text-cta">자세히 보기</span>
    </a>`;
  }).join('');
  return `
    <p class="eyebrow">개요</p>
    <h1 class="page-title">업무 자동화 실습 결과</h1>
    <p class="page-lead">4개 업무에서 자동화가 처리한 일과, 사람이 판단해야 할 일을 정리했습니다.</p>
    ${status}
    <div class="track-grid">${cards}</div>
    ${renderComponents()}`;
}

/** 개요 하단: 저장소에 실제로 있는 커맨드 · Skill · 도구 · 기억 파일 (구분 · 항목 · 담당 업무 · 설명) */
function renderComponents() {
  const items = DATA.components || [];
  if (!items.length) return '';
  const label = Object.fromEntries(DATA.tracks.map((t) => [t.key, `${t.id} ${t.name}`]));
  const where = (keys) => (keys.length === DATA.tracks.length ? '4개 업무 공통' : keys.map((k) => label[k] || k).join(' · '));
  const kinds = [...new Set(items.map((i) => i.kind))];
  const groups = kinds.map((kind) => {
    const list = items.filter((i) => i.kind === kind);
    return `<section class="comp-group" aria-labelledby="comp-${esc(kind)}">
      <h3 class="comp-kind" id="comp-${esc(kind)}">${esc(kind)} <span class="comp-count">${list.length}</span></h3>
      <ul class="comp-list">${list.map((i) => `
        <li>
          <p class="comp-head"><span class="comp-name">${esc(i.name)}</span><span class="comp-where">${esc(where(i.tracks))}</span></p>
          <p class="comp-desc">${esc(i.desc)}</p>
        </li>`).join('')}
      </ul>
    </section>`;
  }).join('');
  return `<section class="section components" aria-labelledby="comp-title">
    <div class="section-head"><h2 class="section-title" id="comp-title">자동화 구성 요소</h2>
      <p class="section-note">각 업무 폴더에 있는 도구 · Skill · 커맨드 · Memory</p></div>
    <div class="comp-grid">${groups}</div>
  </section>`;
}

function renderTrack(t) {
  const ids = DATA.tracks.map((x) => x.id);
  const i = ids.indexOf(t.id);
  const prev = i > 0 ? DATA.tracks[i - 1] : null;
  const next = i < ids.length - 1 ? DATA.tracks[i + 1] : null;
  return `
    <p class="eyebrow">TRACK ${esc(t.id)} · ${esc(t.name)}</p>
    <h1 class="page-title">${esc(t.task)}</h1>
    <p class="page-lead">${esc(t.question)}</p>
    ${flowStrip(t.flow)}
    ${VIEWS[t.view](t)}
    ${verifyLine(t.verify)}
    <nav class="pager" aria-label="트랙 이동">
      ${prev ? `<a class="btn-outline" href="#${esc(prev.id)}">← ${esc(prev.id)} ${esc(prev.name)}</a>` : '<a class="btn-outline" href="#overview">← 개요</a>'}
      ${next ? `<a class="btn-outline next" href="#${esc(next.id)}">${esc(next.id)} ${esc(next.name)} →</a>` : '<a class="btn-outline next" href="#overview">개요 →</a>'}
    </nav>`;
}

function renderFooter(t) {
  if (isDemo()) return '정적 페이지 · <code>data/dashboard.json</code> 한 파일만 읽습니다.';
  const src = t ? t.sources.map((s) => `<code>${esc(s)}</code>`).join(' ') : '각 트랙 <code>report/</code> 결과물';
  return `${esc(DATA.notice)}<br>집계 출처: ${src} · 개인 · 거래 단위 내역과 원문 제외${DATA.min_group ? ` · 대상 ${DATA.min_group}명 미만 부서는 합산` : ''}`;
}

/* ---------- Navigation ---------- */

function buildNav() {
  const items = [{ id: 'overview', label: '개요' }, ...DATA.tracks.map((t) => ({ id: t.id, label: `${t.id} ${t.name}` }))];
  $('#gnb').innerHTML = items.map((n) => `<li><a class="gnb-link" href="#${esc(n.id)}" data-route="${esc(n.id)}">${esc(n.label)}</a></li>`).join('');
}

function route(focus) {
  const id = decodeURIComponent(location.hash.slice(1)) || 'overview';
  const t = trackById(id.toUpperCase());
  const current = t ? t.id : 'overview';
  document.querySelectorAll('.gnb-link').forEach((a) => {
    if (a.dataset.route === current) a.setAttribute('aria-current', 'page');
    else a.removeAttribute('aria-current');
  });
  const active = $(`.gnb-link[data-route="${current}"]`);
  if (active) active.scrollIntoView({ block: 'nearest', inline: 'nearest' });
  $('#view').innerHTML = t ? renderTrack(t) : renderOverview();
  if (t && t.view === 'reconcile') linkVerdicts($('#view'));
  $('#footer').innerHTML = renderFooter(t);
  document.title = `${t ? `${t.id} ${t.name} · ` : ''}실습 결과 대시보드${isDemo() ? ' (데모)' : ''}`;
  if (focus) {
    window.scrollTo(0, 0);
    $('#main').focus({ preventScroll: true });
  }
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

/* ---------- Boot ---------- */

async function boot() {
  initTooltip();
  try {
    const res = await fetch(DATA_URL, { cache: 'no-cache' });
    if (!res.ok) throw new Error(`${DATA_URL} (HTTP ${res.status})`);
    DATA = await res.json();
    if (DATA.schema !== 2) throw new Error('데이터 구조 버전이 맞지 않습니다 (schema 2 필요)');
  } catch (e) {
    const n = $('#notice');
    n.hidden = false;
    n.innerHTML = `데이터를 불러오지 못했습니다: ${esc(e.message)}<br>파일을 직접 열면(file://) 브라우저가 읽기를 막습니다. <code>dashboard</code> 폴더에서 <code>python -m http.server 8000</code> 실행 후 <code>http://localhost:8000/</code>으로 여세요.`;
    $('#view').innerHTML = '';
    return;
  }
  const tag = $('#modeTag');
  tag.textContent = isDemo() ? 'DEMO · 예시 데이터' : '내부 확인용';
  tag.classList.toggle('demo', isDemo());
  tag.hidden = false;
  buildNav();
  window.addEventListener('hashchange', () => route(true));
  route(false);
}

boot();
