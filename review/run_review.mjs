// 선행연구 검토 파이프라인 (PRISMA 2020 절차 + 서지 검증)
// 실행: node review/run_review.mjs
// 원칙: AI가 만든 문장은 결과에 넣지 않는다. 모든 서지정보는 Crossref(출판사 등록 정보)에서,
//       초록 발췌는 원문 문장을 그대로 가져온다. 검증 단계를 하나라도 통과하지 못하면 제외한다.
import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const DIR = path.dirname(fileURLToPath(import.meta.url));
const OUT = path.join(DIR, 'output');
const UA = 'prior-research-tool/1.0 (literature review script)';
const YEAR_FROM = 2010, YEAR_TO = 2026;

// ---------- 1. 검색어 (과업지시서 1.1, 2.1, 제3조, 제6조, 제7조, 제16조에서 도출) ----------
const QUERIES = [
  'stray dog capture',
  'stray animal rescue',
  'animal control officer',
  'animal shelter intake outcomes',
  'animal shelter management dogs cats',
  'shelter length of stay dogs',
  'return to owner lost dogs microchip',
  'animal shelter capacity',
  'animal shelter staff occupational injury',
  'stray dogs Korea',
  '유기동물',
  '동물보호센터',
  '유기견',
];

// ---------- 3. 선별 기준 (제목+초록, 규칙 기반이라 누가 돌려도 같은 결과) ----------
const A = /\b(stray|abandon\w*|free[- ]roaming|lost (dog|cat|pet)s?|shelter\w*|rescue\w*|animal control|impound\w*|pound)\b|유기|유실|보호센터|보호소|구조/i;
const B = /\b(dogs?|cats?|canine|feline|puppies|kittens|companion animals?|pets?)\b|(?<![가-힣])개(?=[는가를의와도\s,.)])|고양이|반려|유기견|유기묘/i;
const C = /\b(captur\w*|catch\w*|rescu\w*|intake|outcomes?|euthan\w*|adopt\w*|return(ed)? to owner|reclaim\w*|manag\w*|polic\w*|welfare|capacity|length of stay|microchip\w*|population|control|bit(e|es|ing)|occupational|staff|workers?|response|legislation|law)\b|구조|포획|입양|반환|안락사|관리|정책|복지|보호/i;
const CLINICAL = /\b(prevalence|seroprevalence|infection|parasit\w*|virus|viral|bacteri\w*|genom\w*|antimicrobial|resistance|tumou?r|surgery|surgical|vaccine efficacy|pharmacokinetic\w*|molecular|serolog\w*|strain|isolates?)\b/i;
const OPS_IN_TITLE = /\b(manag\w*|polic\w*|intake|outcomes?|capture|rescue|control program\w*|welfare|adoption|length of stay)\b/i;

// ---------- 3-2. 과업 관련성 (제목 기준) ----------
// 과업지시서 조항과 연결되는 주제 범주. 제목이 하나 이상에 해당해야 포함한다.
const TOPICS = [
  ['구조·포획 운영(제3조·제7조)', /\b(captur\w*|catch\w*|rescu\w*|impound\w*|pounds?|animal control|reporting)\b|구조|포획|신고/i],
  ['입소·보호기간·처리결과(제3조)', /\b(intake\w*|outcomes?|length[- ]of[- ]stay|live release|euthan\w*|adopt\w*|relinquish\w*|surrender\w*|foster\w*|census|diversion|admission|triage|returns?|returned|treatment methods|processing periods?)\b|입양|안락사|처리/i],
  ['소유자 반환·동물등록(제3조⑤)', /\b(microchip\w*|registration|lost (dogs?|cats?|pets?)|return[- ]to[- ]owner|rto|reunif\w*|resister system)\b|등록|반환/i],
  ['보호센터 운영·인력·안전(제5조·제6조·제16조)', /\b(shelter (management|staff|workers?|work|data|records?|practices|capacity|operations?)|capacity for care|record[- ]keeping|staff|workers?|financial|frontline|occupational|best practices|animal shelters?'? response)\b|인력|운영/i],
  ['정책·법·개체수 관리(제9조)', /\b(polic(y|ies)|laws?|legislation|management (laws|strateg\w*|system)|stray (dogs?|cats?|animals?) (management|population|crisis|issues?)|population (estimat\w*|dynamics)|abandonment|abandoned animals)\b|정책|법|개체수/i],
];
// 과업 범위 밖이 분명한 제목(질병·병원체·임상 사례, 무관한 분야)은 제외한다.
const OFF_TOPIC_TITLE = /\b(dirofilaria|helminth\w*|brucell\w*|parasit\w*|ectoparasit\w*|ticks?|anaplasm\w*|myiasis|leptospir\w*|parvovirus|panleukopenia|dermatophyt\w*|tetanus|heartworm|rabies|vaccin\w*|respiratory|mutant|genes?|pcr|pathogens?|infections?|diseases?|case report|zoono\w*|antibod\w*|animation|students?|celebrit\w*|motorcycle|equine|volunteer\w*|therapy dog|phobia|charity|internet|empathy|biopolitics|emotional behaviors?|circadian|laterality)\b/i;
function topicsOf(title) { return TOPICS.filter(([, re]) => re.test(title)).map(([name]) => name); }

const sleep = ms => new Promise(r => setTimeout(r, ms));
async function getJSON(url, tries = 4) {
  for (let i = 0; i < tries; i++) {
    try {
      const res = await fetch(url, { headers: { 'User-Agent': UA, Accept: 'application/json' } });
      if (res.status === 404) return { __status: 404 };
      if (res.ok) return await res.json();
      if (res.status === 429 || res.status >= 500) { await sleep(1500 * (i + 1)); continue; }
      return { __status: res.status };
    } catch { await sleep(1500 * (i + 1)); }
  }
  return { __status: 'network' };
}

const norm = s => String(s || '').toLowerCase().normalize('NFKC').replace(/<[^>]+>/g, '').replace(/[^\p{L}\p{N}]+/gu, ' ').trim();
function similarity(a, b) { // 문자 bigram Dice 계수
  a = norm(a); b = norm(b); if (!a || !b) return 0; if (a === b) return 1;
  const grams = s => { const m = new Map(); for (let i = 0; i < s.length - 1; i++) { const g = s.slice(i, i + 2); m.set(g, (m.get(g) || 0) + 1); } return m; };
  const ga = grams(a), gb = grams(b); let inter = 0;
  for (const [g, n] of ga) inter += Math.min(n, gb.get(g) || 0);
  return (2 * inter) / (a.length - 1 + b.length - 1);
}
function abstractFromIndex(idx) {
  if (!idx) return '';
  const w = []; for (const [t, ps] of Object.entries(idx)) for (const p of ps) w[p] = t;
  return w.filter(Boolean).join(' ');
}
// Crossref 원문에 섞인 HTML 태그·엔티티를 원래 글자로 되돌림 (내용은 바꾸지 않음)
const ENT = { amp: '&', lt: '<', gt: '>', quot: '"', apos: "'", nbsp: ' ' };
const cleanText = s => String(s || '').replace(/<[^>]+>/g, '')
  .replace(/&(#x[0-9a-f]+|#\d+|\w+);/gi, (m, e) => e[0] === '#' ? String.fromCodePoint(e[1].toLowerCase() === 'x' ? parseInt(e.slice(2), 16) : +e.slice(1)) : (ENT[e.toLowerCase()] ?? m))
  .replace(/\s+/g, ' ').trim();
const bareDoi = d => String(d || '').replace(/^https?:\/\/(dx\.)?doi\.org\//i, '').trim().toLowerCase();

// ---------- 2. 식별 ----------
async function identify() {
  const records = [], perQuery = {};
  for (const q of QUERIES) {
    const p = new URLSearchParams({
      search: q, 'per-page': '50', sort: 'relevance_score:desc',
      filter: `from_publication_date:${YEAR_FROM}-01-01,to_publication_date:${YEAR_TO}-12-31`,
      select: 'id,doi,display_name,publication_year,type,authorships,primary_location,abstract_inverted_index,is_retracted,is_paratext,cited_by_count,language',
    });
    const d = await getJSON(`https://api.openalex.org/works?${p}`);
    const rs = d.results || [];
    perQuery[q] = { hits: d.meta?.count ?? 0, fetched: rs.length };
    for (const r of rs) records.push({ ...r, _query: q });
    await sleep(150);
  }
  return { records, perQuery };
}

// ---------- 5. 인용 검증 ----------
async function verify(rec) {
  const doi = bareDoi(rec.doi);
  const reasons = [];
  const cr = await getJSON(`https://api.crossref.org/works/${encodeURIComponent(doi)}`);
  if (cr.__status) return { ok: false, reasons: [`Crossref에 DOI 등록 정보 없음(${cr.__status})`] };
  const m = cr.message;
  const crTitle = (m.title || [])[0] || '';
  const sim = similarity(crTitle, rec.display_name);
  if (sim < 0.9) reasons.push(`제목 불일치(유사도 ${sim.toFixed(2)})`);
  const crYear = (m.issued?.['date-parts']?.[0]?.[0]) || (m.published?.['date-parts']?.[0]?.[0]);
  if (!crYear) reasons.push('Crossref 출판연도 없음');
  else if (Math.abs(crYear - rec.publication_year) > 1) reasons.push(`연도 불일치(OpenAlex ${rec.publication_year} / Crossref ${crYear})`);
  const crAuthors = (m.author || []).filter(a => a.family || a.name);
  if (!crAuthors.length) reasons.push('Crossref 저자 정보 없음');
  else {
    const oaFirst = norm(rec.authorships?.[0]?.author?.display_name || '');
    const crFirst = norm(crAuthors[0].family || crAuthors[0].name);
    if (!oaFirst || !crFirst.split(' ').some(t => t.length > 1 && oaFirst.includes(t))) reasons.push('제1저자 불일치');
  }
  const venue = (m['container-title'] || [])[0] || '';
  if (!venue) reasons.push('Crossref 학술지명 없음');
  const updates = [...(m['update-to'] || []), ...((m.relation?.['is-retracted-by']) || [])];
  if (updates.some(u => /retract|withdraw/i.test(u.type || u['id-type'] || '') ) || m.relation?.['is-retracted-by']) reasons.push('철회/정정 기록 있음');
  if (/retract|withdrawn/i.test(crTitle)) reasons.push('제목에 철회 표시');
  const h = await getJSON(`https://doi.org/api/handles/${encodeURIComponent(doi)}`);
  if (h.responseCode !== 1) reasons.push('doi.org에서 DOI가 확인되지 않음');
  if (reasons.length) return { ok: false, reasons };
  return {
    ok: true,
    crossref: {
      doi, title: cleanText(crTitle), year: crYear, venue: cleanText(venue),
      authors: crAuthors.map(a => cleanText(a.family ? [a.given, a.family].filter(Boolean).join(' ') : a.name)),
      volume: m.volume || '', issue: m.issue || '', page: m.page || '', type: m.type,
    },
  };
}

// 초록 원문 문장 발췌 (생성 아님, 원문 문장 그대로)
function excerpts(abs) {
  const sents = abs.split(/(?<=[.!?])\s+(?=[A-Z가-힣0-9])/).map(s => s.trim()).filter(s => s.length > 20);
  const used = new Set();
  const pick = (...res) => { // 앞의 규칙(구조화 초록의 표시)부터 시도, 이미 쓴 문장은 다시 쓰지 않음
    for (const re of res) { const s = sents.find(t => !used.has(t) && re.test(t)); if (s) { used.add(s); return s; } }
    return '';
  };
  const purpose = pick(/^(objectives?|aims?|purpose|goal)\b/i,
    /\b(aim(ed|s)? (to|of)|objective|purpose|we (investigated|examined|assessed|evaluated|describe|explored)|this (study|paper|article|research) (aims|examines|investigates|describes|explores|analy[sz]es)|to (measure|determine|evaluate|investigate|assess|examine|identify|compare|explore))\b|목적|목표/i);
  const result = pick(/^(results?|findings?)\b/i,
    /\b(results? (showed|indicated|revealed|suggest)|we found|found that|showed that|indicat\w* that|reveal\w* that|significant\w*|increas\w*|decreas\w*|associated with)\b|결과|나타났|확인되었/i);
  const method = pick(/^(methods?|sample|procedures?|design|animals|materials)\b/i,
    /\b(survey\w*|interview\w*|questionnaire|records? (were|from)|data (were|from|on)|dataset|retrospective|cohort|sample[ds]?|regression|model(l)?ed|observ\w*|collected)\b|조사|분석|설문|자료/i);
  return { purpose, method, result };
}

async function main() {
  await fs.mkdir(OUT, { recursive: true });
  const flow = {};
  const excluded = [];
  const exclude = (r, stage, reason) => excluded.push({ stage, reason, title: r.display_name || '', year: r.publication_year || '', doi: bareDoi(r.doi), openalex: r.id });

  console.log('1) 식별: OpenAlex 검색');
  const { records, perQuery } = await identify();
  flow.identified = records.length;

  console.log('2) 중복 제거');
  const seen = new Set(); const unique = [];
  for (const r of records) {
    const key = bareDoi(r.doi) || norm(r.display_name);
    if (seen.has(key) || seen.has(r.id)) continue;
    seen.add(key); seen.add(r.id); unique.push(r);
  }
  flow.duplicatesRemoved = records.length - unique.length;
  flow.afterDedup = unique.length;

  console.log('3) 기본 자격 확인');
  const eligibleBasic = [];
  for (const r of unique) {
    const abs = abstractFromIndex(r.abstract_inverted_index);
    if (!bareDoi(r.doi)) { exclude(r, '기본 자격', 'DOI 없음(원 출처 확인 불가)'); continue; }
    if (r.is_retracted) { exclude(r, '기본 자격', '철회된 논문'); continue; }
    if (r.is_paratext) { exclude(r, '기본 자격', '논문이 아닌 부속 자료'); continue; }
    if (!['article', 'review'].includes(r.type)) { exclude(r, '기본 자격', `학술논문 아님(${r.type})`); continue; }
    if (!abs || abs.split(' ').length < 40) { exclude(r, '기본 자격', '초록 없음/불충분(내용 확인 불가)'); continue; }
    if (!r.authorships?.length) { exclude(r, '기본 자격', '저자 정보 없음'); continue; }
    eligibleBasic.push({ ...r, _abs: abs });
  }
  flow.afterBasic = eligibleBasic.length;

  console.log('4) 주제 선별');
  const screened = [];
  for (const r of eligibleBasic) {
    const text = `${r.display_name} ${r._abs}`;
    if (!A.test(text)) { exclude(r, '주제 선별', '유기·보호·구조 관련 내용 없음'); continue; }
    if (!B.test(text)) { exclude(r, '주제 선별', '개·고양이(반려동물) 대상 아님'); continue; }
    if (!C.test(text)) { exclude(r, '주제 선별', '구조·관리·정책 관련 내용 없음'); continue; }
    if (CLINICAL.test(r.display_name) && !OPS_IN_TITLE.test(r.display_name)) { exclude(r, '주제 선별', '임상·병원체 연구(운영과 무관)'); continue; }
    if (OFF_TOPIC_TITLE.test(r.display_name)) { exclude(r, '과업 관련성', '질병·임상 또는 과업 범위 밖 주제'); continue; }
    const topics = topicsOf(r.display_name);
    if (!topics.length) { exclude(r, '과업 관련성', '제목이 과업 주제 범주에 해당하지 않음'); continue; }
    screened.push({ ...r, _topics: topics });
  }
  flow.afterScreening = screened.length;

  console.log(`5) 인용 검증 1차 (${screened.length}건)`);
  const pass1 = [];
  for (const r of screened) {
    const v = await verify(r);
    if (!v.ok) exclude(r, '인용 검증 1차', v.reasons.join('; '));
    else pass1.push({ r, v });
    await sleep(120);
  }
  flow.afterVerify1 = pass1.length;

  console.log(`6) 재검증 2차 (${pass1.length}건, 독립 재조회 후 1차와 비교)`);
  const included = [];
  for (const { r, v } of pass1) {
    const v2 = await verify(r);
    if (!v2.ok) { exclude(r, '재검증 2차', v2.reasons.join('; ')); continue; }
    if (JSON.stringify(v2.crossref) !== JSON.stringify(v.crossref)) { exclude(r, '재검증 2차', '1차·2차 조회 결과가 다름(재현 불가)'); continue; }
    const c = v.crossref;
    included.push({
      id: r.id,
      title: c.title, authors: c.authors, year: c.year, venue: c.venue,
      url: 'https://doi.org/' + c.doi, oaUrl: '', cites: r.cited_by_count || 0,
      abstract: r._abs,
      status: '읽을 예정', tags: ['검증완료', ...r._topics],
      ...Object.fromEntries(Object.entries(excerpts(r._abs)).map(([k, s]) => [k, s ? `[초록 원문] ${s}` : ''])),
      note: '',
      verification: { crossrefTitle: c.title, volume: c.volume, issue: c.issue, page: c.page, openalexTitle: r.display_name, checkedAt: new Date().toISOString() },
      addedAt: Date.now(),
    });
    await sleep(120);
  }
  flow.included = included.length;
  flow.excluded = excluded.length;
  included.sort((a, b) => a.year - b.year || a.title.localeCompare(b.title));

  await fs.writeFile(path.join(OUT, 'included_library.json'), JSON.stringify(included, null, 2));
  const q = v => `"${String(v ?? '').replace(/"/g, '""')}"`;
  await fs.writeFile(path.join(OUT, 'excluded.csv'), '﻿' + [['단계', '제외 사유', '제목', '연도', 'DOI', 'OpenAlex'].map(q).join(',')]
    .concat(excluded.map(e => [e.stage, e.reason, e.title, e.year, e.doi, e.openalex].map(q).join(','))).join('\r\n'));
  await fs.writeFile(path.join(OUT, 'flow.json'), JSON.stringify({ runAt: new Date().toISOString(), yearRange: [YEAR_FROM, YEAR_TO], perQuery, flow }, null, 2));
  console.log(flow);
}

main().catch(e => { console.error(e); process.exit(1); });
