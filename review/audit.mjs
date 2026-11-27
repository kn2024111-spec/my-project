// 독립 재검토: run_review.mjs 결과(included_library.json)를 처음부터 다시 조회해 대조한다.
// 실행: node review/audit.mjs
// 하나라도 불일치하면 해당 논문을 최종 목록에서 제외하고 사유를 남긴다.
import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const OUT = path.join(path.dirname(fileURLToPath(import.meta.url)), 'output');
const UA = 'prior-research-tool/1.0 (literature review audit)';
const sleep = ms => new Promise(r => setTimeout(r, ms));
async function getJSON(url, tries = 4) {
  for (let i = 0; i < tries; i++) {
    try {
      const res = await fetch(url, { headers: { 'User-Agent': UA, Accept: 'application/json' } });
      if (res.status === 404) return { __status: 404 };
      if (res.ok) return await res.json();
      await sleep(1500 * (i + 1));
    } catch { await sleep(1500 * (i + 1)); }
  }
  return { __status: 'network' };
}
const ENT = { amp: '&', lt: '<', gt: '>', quot: '"', apos: "'", nbsp: ' ' };
const cleanText = s => String(s || '').replace(/<[^>]+>/g, '')
  .replace(/&(#x[0-9a-f]+|#\d+|\w+);/gi, (m, e) => e[0] === '#' ? String.fromCodePoint(e[1].toLowerCase() === 'x' ? parseInt(e.slice(2), 16) : +e.slice(1)) : (ENT[e.toLowerCase()] ?? m))
  .replace(/\s+/g, ' ').trim();
function abstractFromIndex(idx) {
  if (!idx) return '';
  const w = []; for (const [t, ps] of Object.entries(idx)) for (const p of ps) w[p] = t;
  return w.filter(Boolean).join(' ');
}

const lib = JSON.parse(await fs.readFile(path.join(OUT, 'included_library.json'), 'utf8'));
const checks = ['DOI 실존(doi.org)', '제목 일치(Crossref)', '저자 일치(Crossref)', '연도 일치(Crossref)', '학술지 일치(Crossref)', '동일 논문 재조회(OpenAlex)', '초록 재현(OpenAlex)', '발췌문이 초록 원문에 그대로 있음', 'HTML 기호 잔존 없음'];
const results = [];
for (const x of lib) {
  const doi = x.url.replace('https://doi.org/', '');
  const fail = [];
  const h = await getJSON(`https://doi.org/api/handles/${encodeURIComponent(doi)}`);
  if (h.responseCode !== 1) fail.push(checks[0]);
  const cr = await getJSON(`https://api.crossref.org/works/${encodeURIComponent(doi)}`);
  if (cr.__status) fail.push(checks[1], checks[2], checks[3], checks[4]);
  else {
    const m = cr.message;
    if (cleanText((m.title || [])[0]) !== x.title) fail.push(checks[1]);
    const au = (m.author || []).filter(a => a.family || a.name).map(a => cleanText(a.family ? [a.given, a.family].filter(Boolean).join(' ') : a.name));
    if (JSON.stringify(au) !== JSON.stringify(x.authors)) fail.push(checks[2]);
    const y = m.issued?.['date-parts']?.[0]?.[0] || m.published?.['date-parts']?.[0]?.[0];
    if (y !== x.year) fail.push(checks[3]);
    if (cleanText((m['container-title'] || [])[0]) !== x.venue) fail.push(checks[4]);
  }
  const oa = await getJSON(`https://api.openalex.org/works/doi:${encodeURIComponent(doi)}?select=id,abstract_inverted_index`);
  if (oa.__status || oa.id !== x.id) fail.push(checks[5]);
  else if (abstractFromIndex(oa.abstract_inverted_index) !== x.abstract) fail.push(checks[6]);
  for (const k of ['purpose', 'method', 'result']) {
    const s = (x[k] || '').replace(/^\[초록 원문\] /, '');
    if (s && !x.abstract.includes(s)) { fail.push(`${checks[7]}(${k})`); }
  }
  if (/&(amp|lt|gt|quot|#\d+);|<\/?[a-z]/i.test(x.title + x.venue + x.authors.join(' '))) fail.push(checks[8]);
  results.push({ id: x.id, doi, title: x.title, pass: fail.length === 0, fail });
  process.stdout.write(fail.length ? 'x' : '.');
  await sleep(120);
}
console.log();

const passed = lib.filter(x => results.find(r => r.id === x.id).pass);
const failed = results.filter(r => !r.pass);
await fs.writeFile(path.join(OUT, 'audit.json'), JSON.stringify({ auditedAt: new Date().toISOString(), checks, audited: lib.length, passed: passed.length, failed }, null, 2));
if (failed.length) {
  // 불일치 논문은 최종 목록에서 제외
  await fs.writeFile(path.join(OUT, 'included_library.json'), JSON.stringify(passed, null, 2));
  const q = v => `"${String(v ?? '').replace(/"/g, '""')}"`;
  await fs.appendFile(path.join(OUT, 'excluded.csv'), failed.map(f => '\r\n' + ['독립 재검토', f.fail.join('; '), f.title, '', f.doi, f.id].map(q).join(',')).join(''));
}
console.log({ audited: lib.length, passed: passed.length, failed: failed.length });
for (const f of failed) console.log(' -', f.title.slice(0, 80), '→', f.fail.join(', '));
