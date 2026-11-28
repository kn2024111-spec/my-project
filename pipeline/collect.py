"""1단계 수집: 천안시 구조동물 공고를 월 단위로 받아 원본(JSON)으로 보관한다.

- 이미 받은 달은 건너뛰고(이어받기), 최근 2개월은 상태가 바뀌므로 항상 다시 받는다.
- 달마다 API가 알려준 총건수(totalCount)와 실제로 받은 건수가 같아야 '완료'로 기록한다.
- 담당자 이름(chargeNm)·사무실 전화(officetel)는 개인정보라 저장하지 않는다.

실행: python pipeline/collect.py [--from 2019-01] [--to 2026-11]
"""
from __future__ import annotations

import argparse
import calendar
import datetime as dt
import json
from pathlib import Path

import api

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
LOG = ROOT / "data" / "collection_log.json"
SIDO_CODE = "6440000"  # 충청남도
SIGUNGU_NAME = "천안시"
DROP_FIELDS = {"chargeNm", "officetel"}
PAGE = 1000
# 원천(API) 결함으로 총건수(totalCount)보다 실제로 돌려주는 건수가 적은 달.
# 2026-11-28 확인: 페이지 크기(50·1000)와 축종별(개·고양이·기타) 조회를 모두 바꿔도
# 두 달 모두 '개' 1건이 총건수에는 잡히지만 목록으로는 끝내 오지 않음 → 재수집으로 복구 불가.
# 이 달은 '총건수 - 누락 건수'만큼 받으면 완료로 보고, 누락 건수를 기록에 남긴다.
KNOWN_SOURCE_GAPS = {"2021-05": 1, "2023-02": 1}


def find_org_code() -> str:
    for s in api.items(api.call("sigungu_v2", upr_cd=SIDO_CODE, numOfRows=100)):
        if s["orgdownNm"] == SIGUNGU_NAME:
            return s["orgCd"]
    raise SystemExit(f"{SIGUNGU_NAME} 코드를 찾지 못했습니다.")


def months(start: str, end: str):
    y, m = map(int, start.split("-"))
    ey, em = map(int, end.split("-"))
    while (y, m) <= (ey, em):
        yield y, m
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)


def fetch_month(org: str, y: int, m: int, until: dt.date) -> dict:
    first = dt.date(y, m, 1)
    last = min(dt.date(y, m, calendar.monthrange(y, m)[1]), until)
    rows, page, total = [], 1, None
    while True:
        body = api.call("abandonmentPublic_v2", upr_cd=SIDO_CODE, org_cd=org,
                        bgnde=first.strftime("%Y%m%d"), endde=last.strftime("%Y%m%d"),
                        numOfRows=PAGE, pageNo=page)
        total = int(body.get("totalCount") or 0)
        batch = [{k: v for k, v in r.items() if k not in DROP_FIELDS} for r in api.items(body)]
        rows += batch
        if len(rows) >= total or not batch:
            break
        page += 1
    month = f"{y}-{m:02d}"
    gap = KNOWN_SOURCE_GAPS.get(month, 0)
    return {"month": month, "from": first.isoformat(), "to": last.isoformat(),
            "totalCount": total, "fetched": len(rows), "sourceGap": gap,
            "complete": len(rows) == total - gap,
            "fetchedAt": dt.datetime.now().isoformat(timespec="seconds"), "items": rows}


def main():
    yesterday = dt.date.today() - dt.timedelta(days=1)
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="start", default="2019-01")
    ap.add_argument("--to", dest="end", default=yesterday.strftime("%Y-%m"))
    a = ap.parse_args()

    RAW.mkdir(parents=True, exist_ok=True)
    org = find_org_code()
    print(f"{SIGUNGU_NAME} 기관코드 {org}")
    recent = {(yesterday.year, yesterday.month)}
    prev = yesterday.replace(day=1) - dt.timedelta(days=1)
    recent.add((prev.year, prev.month))

    log = {}
    for y, m in months(a.start, a.end):
        f = RAW / f"{y}-{m:02d}.json"
        if f.exists() and (y, m) not in recent:
            old = json.loads(f.read_text(encoding="utf-8"))
            if old.get("complete"):
                log[old["month"]] = {k: old.get(k, 0) for k in ("totalCount", "fetched", "sourceGap", "complete", "fetchedAt")}
                continue
        res = fetch_month(org, y, m, yesterday)
        f.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
        log[res["month"]] = {k: res[k] for k in ("totalCount", "fetched", "sourceGap", "complete", "fetchedAt")}
        print(f"{res['month']}: {res['fetched']}/{res['totalCount']} {'완료' if res['complete'] else '불완전'}"
              + (f" (원천 누락 {res['sourceGap']}건)" if res["sourceGap"] else ""))

    LOG.write_text(json.dumps({"orgCode": org, "sigungu": SIGUNGU_NAME, "months": log}, ensure_ascii=False, indent=1), encoding="utf-8")
    bad = [k for k, v in log.items() if not v["complete"]]
    gaps = {k: v["sourceGap"] for k, v in log.items() if v.get("sourceGap")}
    print(f"총 {sum(v['fetched'] for v in log.values())}건, 불완전한 달 {len(bad)}개 {bad if bad else ''}"
          + (f", 원천 누락 {sum(gaps.values())}건 {gaps}" if gaps else ""))
    if bad:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
