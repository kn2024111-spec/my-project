"""2~3단계 검증·정제: data/raw/*.json → data/processed/cheonan_rescues.csv

검증 규칙(하나라도 어기면 해당 행을 제외하고 data/processed/rejected.csv 에 사유를 남김)
- 필수 항목(desertionNo, happenDt, processState, upKindNm) 존재
- 날짜 형식(YYYYMMDD)과 범위(수집 기간 안)
- 공고번호 중복은 최신 수정본(updTm 기준) 하나만 남김

정제 항목
- 처리결과(processState) → outcome(보호중/반환/입양/안락사/자연사/방사/기증/기타)
- 나이 '2024(년생)' → 발견 당시 추정 나이(년), '60일미만' 등은 0
- 체중 '1.8(Kg)' → 숫자
- 발견장소 → 구(동남구/서북구), 읍·면·동(문자열에서 추출, 추정)
- 처리까지 걸린 날(추정) = 최종수정일(updTm) − 발견일. 종료된 건만 계산하며,
  updTm 은 '마지막으로 기록이 수정된 날'이라 실제 처리일과 다를 수 있음(추정치로만 사용)
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "processed"

OUTCOME = [("반환", "반환"), ("입양", "입양"), ("안락사", "안락사"), ("자연사", "자연사"),
           ("방사", "방사"), ("기증", "기증"), ("보호중", "보호중")]
DONG = re.compile(r"([가-힣0-9]{1,6}(?:읍|면|동))(?![가-힣])")
SKIP_DONG = {"동남", "서북"}


def outcome_of(s: str) -> str:
    for key, name in OUTCOME:
        if key in s:
            return name
    return "기타"


def age_years(age: str, year: int):
    if not isinstance(age, str):
        return None
    if "60일미만" in age or "개월" in age or "일미만" in age:
        return 0.0
    m = re.search(r"(\d{4})\s*\(년생\)", age)
    if m:
        v = year - int(m.group(1))
        return float(v) if 0 <= v <= 30 else None
    return None


def weight_kg(w: str):
    m = re.search(r"(\d+(?:\.\d+)?)", str(w or ""))
    if not m:
        return None
    v = float(m.group(1))
    return v if 0 < v < 100 else None


def place_parts(place: str):
    place = str(place or "")
    gu = "동남구" if "동남구" in place else "서북구" if "서북구" in place else ""
    dong = ""
    for cand in DONG.findall(place):
        name = cand[:-1] if cand.endswith("동") else cand
        if cand in ("동남구", "서북구") or name in SKIP_DONG:
            continue
        dong = cand
        break
    return gu, dong


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    rows, rejected = [], []
    period_from = period_to = None
    for f in sorted(RAW.glob("*.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        period_from = min(period_from or d["from"], d["from"])
        period_to = max(period_to or d["to"], d["to"])
        for r in d["items"]:
            r["_month_file"] = d["month"]
            rows.append(r)
    df = pd.DataFrame(rows)
    n_raw = len(df)

    def reject(mask, reason):
        nonlocal df
        bad = df[mask]
        for _, r in bad.iterrows():
            rejected.append({"desertionNo": r.get("desertionNo"), "noticeNo": r.get("noticeNo"), "reason": reason})
        df = df[~mask]

    for col in ["desertionNo", "happenDt", "processState", "upKindNm"]:
        reject(df[col].isna() | (df[col].astype(str).str.strip() == ""), f"필수 항목 없음({col})")
    df["happen_date"] = pd.to_datetime(df["happenDt"], format="%Y%m%d", errors="coerce")
    reject(df["happen_date"].isna(), "발견일 형식 오류")
    reject((df["happen_date"] < pd.Timestamp(period_from)) | (df["happen_date"] > pd.Timestamp(period_to)), "발견일이 수집 기간 밖")

    df["upd_time"] = pd.to_datetime(df["updTm"], errors="coerce")
    before = len(df)
    df = df.sort_values("upd_time").drop_duplicates("desertionNo", keep="last")
    n_dup = before - len(df)

    out = pd.DataFrame({
        "desertion_no": df["desertionNo"].astype(str),
        "notice_no": df["noticeNo"],
        "happen_date": df["happen_date"].dt.date,
        "year": df["happen_date"].dt.year,
        "month": df["happen_date"].dt.month,
        "weekday": df["happen_date"].dt.dayofweek,  # 0=월
        "species": df["upKindNm"],
        "breed": df["kindNm"],
        "sex": df["sexCd"].map({"M": "수컷", "F": "암컷", "Q": "미상"}).fillna("미상"),
        "neutered": df["neuterYn"].map({"Y": "예", "N": "아니오", "U": "미상"}).fillna("미상"),
        "age_years": [age_years(a, y) for a, y in zip(df["age"], df["happen_date"].dt.year)],
        "weight_kg": df["weight"].map(weight_kg),
        "process_state": df["processState"],
        "outcome": df["processState"].map(outcome_of),
        "happen_place": df["happenPlace"],
        "notice_start": pd.to_datetime(df["noticeSdt"], format="%Y%m%d", errors="coerce").dt.date,
        "notice_end": pd.to_datetime(df["noticeEdt"], format="%Y%m%d", errors="coerce").dt.date,
        "updated_at": df["upd_time"],
        "care_name": df["careNm"],
    })
    parts = out["happen_place"].map(place_parts)
    out["gu"] = [p[0] for p in parts]
    out["dong_est"] = [p[1] for p in parts]
    ended = out["outcome"] != "보호중"
    days = (pd.to_datetime(out["updated_at"]).dt.normalize() - pd.to_datetime(out["happen_date"])).dt.days
    out["days_to_update_est"] = days.where(ended & (days >= 0))
    out = out.sort_values(["happen_date", "desertion_no"]).reset_index(drop=True)

    out.to_csv(OUT / "cheonan_rescues.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(rejected, columns=["desertionNo", "noticeNo", "reason"]).to_csv(OUT / "rejected.csv", index=False, encoding="utf-8-sig")
    summary = {"period": [period_from, period_to], "raw_rows": n_raw, "rejected": len(rejected),
               "duplicates_removed": n_dup, "clean_rows": len(out)}
    (OUT / "processing_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
    print(summary)


if __name__ == "__main__":
    main()
