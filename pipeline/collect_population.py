"""1단계 수집(보조): KOSIS 「행정구역(시군구)별 성별 인구수」(DT_1B040A3)에서 천안시 연도별 총인구를 받는다.

인증키는 환경변수 KOSIS_API_KEY 에서 읽는다. 결과: data/population.csv
"""
from __future__ import annotations

import csv
import os
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "population.csv"
URL = "https://kosis.kr/openapi/Param/statisticsParameterData.do"


def main(start=2019, end=2026):
    key = os.environ.get("KOSIS_API_KEY", "").strip()
    if not key:
        raise SystemExit("환경변수 KOSIS_API_KEY 가 없습니다.")
    params = {"method": "getList", "apiKey": key, "itmId": "T20", "objL1": "44130", "objL2": "",
              "format": "json", "jsonVD": "Y", "prdSe": "Y", "startPrdDe": start, "endPrdDe": end,
              "orgId": "101", "tblId": "DT_1B040A3"}
    for attempt in range(10):
        try:
            r = requests.get(URL, params=params, timeout=60)
            data = r.json()
            if isinstance(data, list):
                break
            raise SystemExit(f"KOSIS 오류: {data}")
        except (requests.RequestException, ValueError):
            time.sleep(min(2 ** attempt, 30))
    else:
        raise SystemExit("KOSIS 호출이 계속 실패했습니다.")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["year", "population", "source"])
        for d in sorted(data, key=lambda d: d["PRD_DE"]):
            if d.get("C1_NM") == "천안시":
                w.writerow([d["PRD_DE"], d["DT"], f"KOSIS {d['TBL_ID']} ({d['TBL_NM']}), 최종수정 {d['LST_CHN_DE']}"])
    print(OUT.read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
