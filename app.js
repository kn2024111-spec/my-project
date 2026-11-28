// 선행 연구 정리 도구 — 논문 검색(OpenAlex) + 내 목록 + 정리표
(() => {
  'use strict';

  const API = 'https://api.openalex.org/works';
  const PER_PAGE = 20;
  const STORE_KEY = 'prior-research-library-v1';
  const $ = (s, el = document) => el.querySelector(s);

  // ---------- 저장소 ----------
  let library = load();
  function load() {
    try { return JSON.parse(localStorage.getItem(STORE_KEY)) || []; }
    catch { return []; }
  }
  function save() {
    try { localStorage.setItem(STORE_KEY, JSON.stringify(library)); }
    catch { toast('저장에 실패했어요. 백업 저장을 이용하세요.'); }
    $('#libCount').textContent = library.length;
  }
  const inLibrary = id => library.some(x => x.id === id);

  // ---------- 유틸 ----------
  const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const splitList = s => String(s || '').split(',').map(t => t.trim()).filter(Boolean);
  function toast(msg) {
    const t = $('#toast'); t.textContent = msg; t.hidden = false;
    clearTimeout(toast.timer); toast.timer = setTimeout(() => (t.hidden = true), 2200);
  }
  function abstractFromIndex(idx) {
    if (!idx) return '';
    const words = [];
    for (const [w, positions] of Object.entries(idx)) for (const p of positions) words[p] = w;
    return words.filter(Boolean).join(' ');
  }
  function shortAuthors(a) {
    if (!a.length) return '저자 미상';
    return a.length > 3 ? `${a.slice(0, 3).join(', ')} 외 ${a.length - 3}명` : a.join(', ');
  }
  function linkOf(item) {
    if (!item.url) return '';
    if (/^https?:\/\//.test(item.url)) return item.url;
    if (/^10\./.test(item.url)) return 'https://doi.org/' + item.url;
    return '';
  }

  function fromOpenAlex(w) {
    return {
      id: w.id,
      title: w.display_name || '(제목 없음)',
      authors: (w.authorships || []).map(a => a.author?.display_name).filter(Boolean),
      year: w.publication_year || '',
      venue: w.primary_location?.source?.display_name || '',
      url: w.doi || w.open_access?.oa_url || w.id,
      oaUrl: w.open_access?.oa_url || '',
      cites: w.cited_by_count || 0,
      abstract: abstractFromIndex(w.abstract_inverted_index),
    };
  }

  // ---------- 탭 ----------
  document.querySelectorAll('.tab').forEach(btn => btn.addEventListener('click', () => showTab(btn.dataset.tab)));
  function showTab(name) {
    document.querySelectorAll('.tab').forEach(b => b.classList.toggle('active', b.dataset.tab === name));
    document.querySelectorAll('.panel').forEach(p => p.classList.toggle('active', p.id === 'tab-' + name));
    if (name === 'library') renderLibrary();
    if (name === 'matrix') renderMatrix();
  }

  // ---------- 검색 ----------
  let page = 1, lastResults = [], total = 0;
  $('#searchForm').addEventListener('submit', e => { e.preventDefault(); page = 1; search(); });
  $('#prevPage').addEventListener('click', () => { page--; search(); });
  $('#nextPage').addEventListener('click', () => { page++; search(); });

  async function search() {
    const q = $('#q').value.trim();
    if (!q) return;
    const filters = [];
    const yf = $('#yearFrom').value, yt = $('#yearTo').value;
    if (yf) filters.push(`from_publication_date:${yf}-01-01`);
    if (yt) filters.push(`to_publication_date:${yt}-12-31`);
    if ($('#oaOnly').checked) filters.push('is_oa:true');
    const params = new URLSearchParams({
      search: q, page, 'per-page': PER_PAGE, sort: $('#sort').value,
      select: 'id,display_name,publication_year,authorships,primary_location,cited_by_count,doi,abstract_inverted_index,open_access',
    });
    if (filters.length) params.set('filter', filters.join(','));

    $('#searchInfo').textContent = '검색 중…';
    $('#results').innerHTML = '';
    try {
      const res = await fetch(`${API}?${params}`);
      if (!res.ok) throw new Error('HTTP ' + res.status);
      const data = await res.json();
      total = data.meta?.count || 0;
      lastResults = (data.results || []).map(fromOpenAlex);
      $('#searchInfo').textContent = `총 ${total.toLocaleString()}건의 논문을 찾았어요.`;
      renderResults();
    } catch (err) {
      $('#searchInfo').textContent = '검색에 실패했어요. 인터넷 연결을 확인하고 다시 시도해 주세요. (' + err.message + ')';
      lastResults = []; total = 0; renderResults();
    }
  }

  function renderResults() {
    const box = $('#results');
    if (!lastResults.length) { box.innerHTML = total === 0 && $('#q').value ? '<p class="empty">결과가 없어요.</p>' : ''; }
    else box.innerHTML = lastResults.map((r, i) => `
      <article class="card">
        <h3>${linkOf(r) ? `<a href="${esc(linkOf(r))}" target="_blank" rel="noopener">${esc(r.title)}</a>` : esc(r.title)}</h3>
        <div class="meta">${esc(shortAuthors(r.authors))} · ${esc(r.year)}${r.venue ? ' · ' + esc(r.venue) : ''} · 인용 ${r.cites.toLocaleString()}회</div>
        ${r.abstract ? `<p class="abstract clamp">${esc(r.abstract)}</p>` : '<p class="abstract muted">초록 정보가 없어요.</p>'}
        <div class="actions">
          <button data-add="${i}" ${inLibrary(r.id) ? 'disabled' : ''}>${inLibrary(r.id) ? '✓ 담김' : '+ 내 목록에 담기'}</button>
          ${r.abstract ? `<button data-more="${i}">초록 펼치기</button>` : ''}
          ${r.oaUrl ? `<a href="${esc(r.oaUrl)}" target="_blank" rel="noopener">무료 원문</a>` : ''}
        </div>
      </article>`).join('');
    const pages = Math.ceil(total / PER_PAGE);
    $('#pageInfo').textContent = total ? `${page} / ${Math.min(pages, 500).toLocaleString()} 페이지` : '';
    $('#prevPage').disabled = page <= 1;
    $('#nextPage').disabled = page >= pages || page >= 500;
  }

  $('#results').addEventListener('click', e => {
    const add = e.target.closest('[data-add]');
    if (add) {
      const r = lastResults[add.dataset.add];
      if (!inLibrary(r.id)) {
        library.unshift({ ...r, status: '읽을 예정', tags: [], purpose: '', method: '', result: '', note: '', addedAt: Date.now() });
        save(); add.disabled = true; add.textContent = '✓ 담김'; toast('내 목록에 담았어요');
      }
    }
    const more = e.target.closest('[data-more]');
    if (more) {
      const p = more.closest('.card').querySelector('.abstract');
      p.classList.toggle('clamp');
      more.textContent = p.classList.contains('clamp') ? '초록 펼치기' : '초록 접기';
    }
  });

  // ---------- 내 목록 ----------
  $('#libFilter').addEventListener('input', renderLibrary);
  $('#statusFilter').addEventListener('change', renderLibrary);
  $('#addManual').addEventListener('click', () => openEditor(null));

  function renderLibrary() {
    const q = $('#libFilter').value.trim().toLowerCase();
    const st = $('#statusFilter').value;
    const items = library.filter(x => {
      if (st && x.status !== st) return false;
      if (!q) return true;
      return [x.title, x.authors.join(' '), x.tags.join(' '), x.note, x.purpose, x.method, x.result, x.venue]
        .join(' ').toLowerCase().includes(q);
    });
    const box = $('#library');
    if (!library.length) { box.innerHTML = '<p class="empty">아직 담은 논문이 없어요.<br>‘논문 검색’ 탭에서 찾아서 담거나 ‘+ 직접 추가’를 눌러 주세요.</p>'; return; }
    if (!items.length) { box.innerHTML = '<p class="empty">조건에 맞는 논문이 없어요.</p>'; return; }
    box.innerHTML = items.map(x => `
      <article class="card">
        <span class="status ${esc(x.status)}">${x.status === '핵심' ? '⭐ ' : ''}${esc(x.status)}</span>
        <h3>${linkOf(x) ? `<a href="${esc(linkOf(x))}" target="_blank" rel="noopener">${esc(x.title)}</a>` : esc(x.title)}</h3>
        <div class="meta">${esc(shortAuthors(x.authors))} · ${esc(x.year)}${x.venue ? ' · ' + esc(x.venue) : ''}</div>
        ${x.tags.length ? `<div style="margin-top:6px">${x.tags.map(t => `<span class="tag">#${esc(t)}</span>`).join('')}</div>` : ''}
        ${x.note ? `<div class="notes">${esc(x.note)}</div>` : ''}
        <div class="actions">
          <button data-edit="${esc(x.id)}">✏️ 정리하기</button>
          <button data-cite="${esc(x.id)}">📄 APA 인용 복사</button>
          <button data-del="${esc(x.id)}">🗑 삭제</button>
        </div>
      </article>`).join('');
  }

  $('#library').addEventListener('click', e => {
    const id = e.target.closest('button')?.dataset;
    if (!id) return;
    if (id.edit) openEditor(library.find(x => x.id === id.edit));
    if (id.cite) {
      const x = library.find(y => y.id === id.cite);
      copy(apa(x)).then(() => toast('인용문을 복사했어요'));
    }
    if (id.del && confirm('이 논문을 목록에서 삭제할까요?')) {
      library = library.filter(x => x.id !== id.del); save(); renderLibrary();
    }
  });

  function copy(text) {
    if (navigator.clipboard?.writeText) return navigator.clipboard.writeText(text).catch(() => fallback());
    return Promise.resolve(fallback());
    function fallback() { const t = document.createElement('textarea'); t.value = text; document.body.append(t); t.select(); document.execCommand('copy'); t.remove(); }
  }

  function apa(x) {
    const names = x.authors.map(n => {
      const parts = n.trim().split(/\s+/);
      if (parts.length < 2 || /[가-힣]/.test(n)) return n;
      const last = parts.pop();
      return `${last}, ${parts.map(p => p[0] + '.').join(' ')}`;
    });
    let au = names.length <= 2 ? names.join(', & ') : names.length <= 20 ? names.slice(0, -1).join(', ') + ', & ' + names.at(-1) : names.slice(0, 19).join(', ') + ', ... ' + names.at(-1);
    if (!au) au = '저자 미상';
    const doi = /doi\.org/.test(x.url || '') || /^10\./.test(x.url || '') ? ' ' + linkOf(x) : '';
    return `${au} (${x.year || 'n.d.'}). ${x.title}.${x.venue ? ' ' + x.venue + '.' : ''}${doi}`;
  }

  // ---------- 편집기 ----------
  function openEditor(item) {
    const dlg = $('#tplEdit').content.firstElementChild.cloneNode(true);
    document.body.append(dlg);
    const f = dlg.querySelector('form');
    const v = item || { title: '', authors: [], year: '', venue: '', url: '', status: '읽을 예정', tags: [], purpose: '', method: '', result: '', note: '', abstract: '' };
    for (const k of ['title', 'year', 'venue', 'url', 'status', 'purpose', 'method', 'result', 'note', 'abstract']) f.elements[k].value = v[k] ?? '';
    f.elements.authors.value = v.authors.join(', ');
    f.elements.tags.value = v.tags.join(', ');
    dlg.addEventListener('close', () => {
      if (dlg.returnValue === 'save') {
        const data = {
          title: f.elements.title.value.trim(), authors: splitList(f.elements.authors.value),
          year: f.elements.year.value, venue: f.elements.venue.value.trim(), url: f.elements.url.value.trim(),
          status: f.elements.status.value, tags: splitList(f.elements.tags.value),
          purpose: f.elements.purpose.value, method: f.elements.method.value, result: f.elements.result.value,
          note: f.elements.note.value, abstract: f.elements.abstract.value,
        };
        if (item) Object.assign(item, data);
        else library.unshift({ id: 'manual-' + Date.now(), cites: 0, addedAt: Date.now(), ...data });
        save(); renderLibrary(); toast('저장했어요');
      }
      dlg.remove();
    });
    dlg.showModal();
  }

  // ---------- 정리표 ----------
  const COLS = [
    ['year', '연도'], ['authors', '저자'], ['title', '제목'], ['purpose', '연구 목적'],
    ['method', '연구 방법'], ['result', '주요 결과'], ['note', '시사점'], ['tags', '태그'],
  ];
  function cellText(x, k) { return Array.isArray(x[k]) ? x[k].join(', ') : (x[k] ?? ''); }
  function renderMatrix() {
    const t = $('#matrix');
    if (!library.length) { t.innerHTML = '<tr><td class="empty">내 목록에 논문을 담으면 여기에 정리표가 만들어져요.</td></tr>'; return; }
    const rows = [...library].sort((a, b) => (a.year || 9999) - (b.year || 9999));
    t.innerHTML = `<thead><tr><th>#</th>${COLS.map(c => `<th>${c[1]}</th>`).join('')}</tr></thead><tbody>` +
      rows.map((x, i) => `<tr data-id="${esc(x.id)}"><td>${i + 1}</td>${COLS.map(([k]) =>
        `<td contenteditable="plaintext-only" data-k="${k}" class="${k === 'title' ? 'title-cell' : ''}">${esc(cellText(x, k))}</td>`).join('')}</tr>`).join('') + '</tbody>';
  }
  $('#matrix').addEventListener('focusout', e => {
    const td = e.target.closest('td[data-k]'); if (!td) return;
    const x = library.find(y => y.id === td.parentElement.dataset.id); if (!x) return;
    const k = td.dataset.k, val = td.innerText.trim();
    const next = (k === 'authors' || k === 'tags') ? splitList(val) : val;
    if (JSON.stringify(next) !== JSON.stringify(x[k])) { x[k] = next; save(); toast('저장했어요'); }
  });

  // ---------- 내보내기 / 가져오기 ----------
  function download(name, text, type) {
    const a = document.createElement('a');
    a.href = URL.createObjectURL(new Blob([text], { type }));
    a.download = name; a.click(); setTimeout(() => URL.revokeObjectURL(a.href), 1000);
  }
  const today = () => new Date().toISOString().slice(0, 10);
  $('#exportCsv').addEventListener('click', () => {
    if (!library.length) return toast('내보낼 논문이 없어요');
    const head = [...COLS.map(c => c[1]), '학술지', '링크', '상태', '인용수'];
    const q = v => `"${String(v ?? '').replace(/"/g, '""')}"`;
    const lines = [head.map(q).join(',')].concat(library.map(x =>
      [...COLS.map(([k]) => cellText(x, k)), x.venue, linkOf(x), x.status, x.cites].map(q).join(',')));
    download(`선행연구_${today()}.csv`, '﻿' + lines.join('\r\n'), 'text/csv;charset=utf-8');
  });
  $('#exportBib').addEventListener('click', () => {
    if (!library.length) return toast('내보낼 논문이 없어요');
    const used = {};
    const bib = library.map(x => {
      const first = (x.authors[0] || 'anon').split(/\s+/).pop().replace(/[^\w가-힣]/g, '').toLowerCase() || 'anon';
      let key = first + (x.year || ''); used[key] = (used[key] || 0) + 1; if (used[key] > 1) key += String.fromCharCode(95 + used[key]);
      const doi = (x.url || '').replace(/^https?:\/\/doi\.org\//, '');
      const f = [`  title = {${x.title}}`, `  author = {${x.authors.join(' and ')}}`];
      if (x.year) f.push(`  year = {${x.year}}`);
      if (x.venue) f.push(`  journal = {${x.venue}}`);
      if (/^10\./.test(doi)) f.push(`  doi = {${doi}}`); else if (x.url) f.push(`  url = {${x.url}}`);
      return `@article{${key},\n${f.join(',\n')}\n}`;
    }).join('\n\n');
    download(`선행연구_${today()}.bib`, bib, 'text/plain;charset=utf-8');
  });
  $('#exportJson').addEventListener('click', () => download(`선행연구_백업_${today()}.json`, JSON.stringify(library, null, 2), 'application/json'));
  $('#importJson').addEventListener('change', async e => {
    const file = e.target.files[0]; if (!file) return;
    try {
      const data = JSON.parse(await file.text());
      if (!Array.isArray(data)) throw new Error();
      let added = 0;
      for (const x of data) if (x && x.id && x.title && !inLibrary(x.id)) {
        library.push({ authors: [], tags: [], status: '읽을 예정', purpose: '', method: '', result: '', note: '', ...x }); added++;
      }
      save(); renderMatrix(); toast(`${added}건을 불러왔어요`);
    } catch { toast('백업 파일을 읽을 수 없어요'); }
    e.target.value = '';
  });

  save();
})();
