"""4단계 1차 분석: data/processed/cheonan_rescues.csv → analysis/ (그림, 표, REPORT.md)

보고서의 숫자는 모두 이 스크립트가 데이터에서 계산해 넣는다(손으로 적은 수치 없음).
관련 선행연구는 review/output/included_library.json(서지 검증 98건)에서만 고른다.
"""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
OUT = ROOT / "analysis"
FIG = OUT / "figures"
TAB = OUT / "tables"

# 한글 글꼴
for name in ["NanumGothic", "Noto Sans CJK KR", "Malgun Gothic", "AppleGothic", "WenQuanYi Zen Hei"]:
    if any(f.name == name for f in font_manager.fontManager.ttflist):
        plt.rcParams["font.family"] = name
        break
plt.rcParams["axes.unicode_minus"] = False
plt.rcParams["figure.dpi"] = 110
INK, MUTED, ACCENT, ACCENT2, GRID = "#1f2937", "#6b7280", "#2563eb", "#f59e0b", "#e5e7eb"
OUTCOME_ORDER = ["반환", "입양", "자연사", "안락사", "방사", "기증", "기타", "보호중"]
OUTCOME_COLOR = {"반환": "#2563eb", "입양": "#16a34a", "자연사": "#9ca3af", "안락사": "#dc2626",
                 "방사": "#a855f7", "기증": "#0891b2", "기타": "#d1d5db", "보호중": "#f59e0b"}
WEEKDAYS = ["월", "화", "수", "목", "금", "토", "일"]


def style(ax, title, ylabel=""):
    ax.set_title(title, loc="left", fontsize=12, color=INK, pad=10)
    ax.set_ylabel(ylabel, color=MUTED)
    ax.spines[["top", "right"]].set_visible(False)
    ax.spines[["left", "bottom"]].set_color(GRID)
    ax.tick_params(colors=MUTED)
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)


def save(fig, name):
    fig.tight_layout()
    fig.savefig(FIG / name, bbox_inches="tight")
    plt.close(fig)
    return f"figures/{name}"


def pct(a, b):
    return 0.0 if not b else 100.0 * a / b


def papers(tag: str, n=3):
    """검증된 선행연구 목록에서 해당 주제 범주 논문을 인용수 순으로 n건."""
    lib = json.loads((ROOT / "review/output/included_library.json").read_text(encoding="utf-8"))
    hit = sorted([x for x in lib if any(tag in t for t in x["tags"])], key=lambda x: -x.get("cites", 0))[:n]
    out = []
    for x in hit:
        au = x["authors"][0].split()[-1] + (" 외" if len(x["authors"]) > 1 else "")
        out.append(f"- {au} ({x['year']}). {x['title']}. *{x['venue']}*. {x['url']}")
    return "\n".join(out)


def table_md(df: pd.DataFrame, floatfmt="{:,.1f}") -> str:
    cols = [str(c) for c in df.columns]
    lines = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for _, r in df.iterrows():
        cells = []
        for v in r:
            if isinstance(v, float):
                cells.append(floatfmt.format(v))
            elif isinstance(v, int):
                cells.append(f"{v:,}")
            else:
                cells.append(str(v))
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def main():
    FIG.mkdir(parents=True, exist_ok=True)
    TAB.mkdir(parents=True, exist_ok=True)
    df = pd.read_csv(DATA / "processed/cheonan_rescues.csv", parse_dates=["happen_date", "updated_at"])
    pop = pd.read_csv(DATA / "population.csv")
    summ = json.loads((DATA / "processed/processing_summary.json").read_text(encoding="utf-8"))
    log = json.loads((DATA / "collection_log.json").read_text(encoding="utf-8"))
    p_from, p_to = pd.Timestamp(summ["period"][0]), pd.Timestamp(summ["period"][1])
    last_year = p_to.year
    full_years = [y for y in sorted(df["year"].unique()) if y < last_year or p_to.month == 12 and p_to.day == 31]
    md = []
    A = md.append

    # ---------- 0. 개요 ----------
    A("# 천안시 유기·유실동물 1차 데이터 분석\n")
    A(f"- 분석 기준: 「2027년 천안시 유기·유실동물 구조(포획) 용역 과업지시서」, 선행연구 검토 결과(`review/`)")
    A(f"- 데이터: 농림축산검역본부 국가동물보호정보시스템 구조동물 조회 API(공공데이터포털), KOSIS 천안시 주민등록인구")
    A(f"- 기간: {p_from:%Y-%m-%d} ~ {p_to:%Y-%m-%d} (발견일 기준) · 생성일: {dt.date.today():%Y-%m-%d}")
    A(f"- 수집 {summ['raw_rows']:,}건 → 형식 오류 {summ['rejected']:,}건·중복 {summ['duplicates_removed']:,}건 제외 → **분석 {summ['clean_rows']:,}건**")
    A(f"- 수집 완결성: {len(log['months'])}개월 모두 API 총건수와 수집 건수 일치 여부 확인 "
      f"(불일치 {sum(1 for v in log['months'].values() if not v['complete'])}개월)\n")
    A("> 이 보고서의 수치는 `pipeline/analyze.py`가 데이터에서 직접 계산한 값이에요. "
      "'추정'이라고 표시한 지표는 API에 해당 항목이 없어 다른 항목으로 근사한 값이라 해석에 주의가 필요해요.\n")

    # ---------- 1. 연도별 규모 ----------
    yr = df.groupby("year").size().rename("구조 건수").reset_index().rename(columns={"year": "연도"})
    yr = yr.merge(pop.rename(columns={"year": "연도", "population": "인구"})[["연도", "인구"]], on="연도", how="left")
    days_in = {y: ((min(p_to, pd.Timestamp(y, 12, 31)) - max(p_from, pd.Timestamp(y, 1, 1))).days + 1) for y in yr["연도"]}
    yr["집계 일수"] = yr["연도"].map(days_in)
    yr["일평균"] = yr["구조 건수"] / yr["집계 일수"]
    yr["인구 1천명당"] = yr["구조 건수"] / yr["인구"] * 1000
    yr.to_csv(TAB / "01_yearly.csv", index=False, encoding="utf-8-sig")
    fig, ax = plt.subplots(figsize=(8, 3.6))
    colors = [ACCENT if days_in[y] >= 365 else "#93c5fd" for y in yr["연도"]]
    ax.bar(yr["연도"].astype(str), yr["구조 건수"], color=colors)
    for x, v in zip(yr["연도"].astype(str), yr["구조 건수"]):
        ax.text(x, v, f"{v:,}", ha="center", va="bottom", fontsize=9, color=INK)
    style(ax, "연도별 구조(공고) 건수", "건")
    if days_in[last_year] < 365:
        ax.text(1, 1.02, f"{last_year}년은 {p_to:%m월 %d일}까지 집계", transform=ax.transAxes, ha="right", fontsize=8, color=MUTED)
    f1 = save(fig, "01_yearly.png")
    fy = yr[yr["연도"].isin(full_years)]
    A("## 1. 구조 규모 (과업지시서 제3조·제6조)\n")
    A(f"![연도별 구조 건수]({f1})\n")
    show = yr.copy()
    show["인구"] = show["인구"].map(lambda v: f"{int(v):,}" if pd.notna(v) else "미공표")
    show["인구 1천명당"] = show["인구 1천명당"].map(lambda v: f"{v:.2f}" if pd.notna(v) else "-")
    A(table_md(show[["연도", "구조 건수", "집계 일수", "일평균", "인구", "인구 1천명당"]]) + "\n")
    peak = fy.loc[fy["구조 건수"].idxmax()]
    recent = fy[fy["연도"] >= fy["연도"].max() - 2]
    A(f"- 전체 연도 중 구조 건수가 가장 많았던 해는 **{int(peak['연도'])}년({int(peak['구조 건수']):,}건)**이에요.")
    A(f"- 최근 3개 완결 연도({int(recent['연도'].min())}~{int(recent['연도'].max())}년)의 일평균은 "
      f"**{recent['구조 건수'].sum() / recent['집계 일수'].sum():.1f}건**이에요. "
      f"과업지시서의 구조 전담 인력 최소 3인·2인 1조(제6조), 신고 후 3시간 이내 포획(제7조) 기준을 검토할 때 기초 수요로 쓸 수 있어요.")
    if days_in[last_year] < 365:
        cur = yr[yr["연도"] == last_year].iloc[0]
        A(f"- {last_year}년은 {int(cur['집계 일수'])}일 동안 {int(cur['구조 건수']):,}건(일평균 {cur['일평균']:.1f}건)이에요.")
    A("\n관련 선행연구(입소 추이·인구 대비 지표):\n" + papers("입소·보호기간·처리결과") + "\n")

    # ---------- 2. 월별·요일별 ----------
    full = df[df["year"].isin(full_years)]
    mon = full.groupby(["year", "month"]).size().unstack(fill_value=0)
    mon_avg = mon.mean(axis=0)
    wk = df.groupby("weekday").size().reindex(range(7), fill_value=0)
    pd.DataFrame({"월": mon_avg.index, "완결 연도 평균 건수": mon_avg.values}).to_csv(TAB / "02_monthly_avg.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame({"요일": WEEKDAYS, "건수": wk.values, "비율(%)": (wk / wk.sum() * 100).round(1).values}).to_csv(TAB / "03_weekday.csv", index=False, encoding="utf-8-sig")
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(10, 3.6), gridspec_kw={"width_ratios": [1.6, 1]})
    a1.plot(mon_avg.index, mon_avg.values, marker="o", color=ACCENT)
    a1.set_xticks(range(1, 13), [f"{m}월" for m in range(1, 13)], fontsize=8)
    style(a1, f"월별 평균 구조 건수 ({min(full_years)}~{max(full_years)}년)", "건/월")
    a2.bar(WEEKDAYS, wk.values, color=[ACCENT] * 5 + [ACCENT2] * 2)
    style(a2, "요일별 구조 건수(발견일 기준)", "건")
    f2 = save(fig, "02_month_weekday.png")
    weekend = pct(wk[5] + wk[6], wk.sum())
    A("## 2. 계절·요일 분포 (과업지시서 제3조⑦ 365일 운영)\n")
    A(f"![월별·요일별]({f2})\n")
    A(f"- 월평균이 가장 많은 달은 **{int(mon_avg.idxmax())}월({mon_avg.max():.1f}건)**, 가장 적은 달은 **{int(mon_avg.idxmin())}월({mon_avg.min():.1f}건)**이에요. "
      f"차이는 약 {mon_avg.max() / mon_avg.min():.1f}배예요.")
    A(f"- 주말(토·일) 발견이 전체의 **{weekend:.1f}%**예요(요일이 고르면 28.6%). "
      "주말에도 구조 수요가 있어 365일 운영(제3조⑦)의 근거가 돼요. 단, 발견일은 공고에 적힌 날짜라 실제 신고 시각과 다를 수 있어요.\n")

    # ---------- 3. 대상 동물 특성 ----------
    sp = df.groupby(["year", "species"]).size().unstack(fill_value=0)
    sp.to_csv(TAB / "04_species_by_year.csv", encoding="utf-8-sig")
    bins = [-0.1, 0.99, 2.99, 7.99, 100]
    labels = ["1세 미만", "1~2세", "3~7세", "8세 이상"]
    df["age_group"] = pd.cut(df["age_years"], bins=bins, labels=labels)
    ag = df.groupby(["species", "age_group"], observed=False).size().unstack(fill_value=0)
    ag.to_csv(TAB / "05_age_by_species.csv", encoding="utf-8-sig")
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(10, 3.6))
    bottom = None
    palette = {"개": ACCENT, "고양이": ACCENT2}
    for col in sp.columns:
        a1.bar(sp.index.astype(str), sp[col], bottom=bottom, label=col, color=palette.get(col, "#9ca3af"))
        bottom = sp[col] if bottom is None else bottom + sp[col]
    a1.legend(frameon=False, fontsize=8)
    style(a1, "축종별 구조 건수", "건")
    for i, s in enumerate([c for c in ["개", "고양이"] if c in ag.index]):
        vals = ag.loc[s] / ag.loc[s].sum() * 100
        a2.barh([f"{s} {l}" for l in labels], vals.values, color=palette[s])
    a2.invert_yaxis()
    a2.set_xlabel("축종 내 비율(%)", color=MUTED)
    style(a2, "축종별 나이 분포(추정 나이)")
    a2.grid(axis="x", color=GRID)
    f3 = save(fig, "03_species_age.png")
    tot_sp = df["species"].value_counts()
    neut = df[df["neutered"] != "미상"]
    A("## 3. 구조 동물 특성\n")
    A(f"![축종·나이]({f3})\n")
    A("- 전체 기간 축종 구성: " + ", ".join(f"{k} {v:,}건({pct(v, len(df)):.1f}%)" for k, v in tot_sp.items()))
    for s in ["개", "고양이"]:
        if s in ag.index:
            young = pct(ag.loc[s, "1세 미만"], ag.loc[s].sum())
            A(f"- {s}의 **{young:.1f}%**가 1세 미만(추정 나이)이에요.")
    A(f"- 중성화 여부가 기록된 {len(neut):,}건 중 중성화된 동물은 **{pct((neut['neutered'] == '예').sum(), len(neut)):.1f}%**예요.\n")

    # ---------- 4. 처리 결과 ----------
    oc = df.groupby(["year", "outcome"]).size().unstack(fill_value=0).reindex(columns=OUTCOME_ORDER, fill_value=0)
    oc = oc.loc[:, oc.sum() > 0]
    ocp = oc.div(oc.sum(axis=1), axis=0) * 100
    ocp.round(1).to_csv(TAB / "06_outcome_share_by_year.csv", encoding="utf-8-sig")
    oc.to_csv(TAB / "06_outcome_count_by_year.csv", encoding="utf-8-sig")
    fig, ax = plt.subplots(figsize=(9, 3.8))
    left = pd.Series(0.0, index=ocp.index)
    for col in ocp.columns:
        ax.barh(ocp.index.astype(str), ocp[col], left=left, color=OUTCOME_COLOR[col], label=col)
        left += ocp[col]
    ax.invert_yaxis()
    ax.set_xlim(0, 100)
    ax.legend(ncol=len(ocp.columns), frameon=False, fontsize=8, loc="upper center", bbox_to_anchor=(0.5, -0.12))
    style(ax, "연도별 처리 결과 구성(%)")
    ax.grid(axis="x", color=GRID)
    f4 = save(fig, "04_outcomes.png")
    ended = df[df["outcome"] != "보호중"]
    endf = ended[ended["year"].isin(full_years)]
    share = endf["outcome"].value_counts()
    A("## 4. 처리 결과 (과업지시서 제3조⑤·⑥)\n")
    A(f"![처리 결과]({f4})\n")
    A(table_md(ocp.round(1).reset_index().rename(columns={"year": "연도"}).astype({"연도": str})) + "\n")
    A(f"- 완결 연도({min(full_years)}~{max(full_years)}년) 종료 건 {len(endf):,}건 기준: "
      + ", ".join(f"{k} {pct(v, len(endf)):.1f}%" for k, v in share.items()) + ".")
    for s in ["개", "고양이"]:
        sub = endf[endf["species"] == s]
        if len(sub):
            A(f"- {s}: 반환 {pct((sub['outcome'] == '반환').sum(), len(sub)):.1f}%, 입양 {pct((sub['outcome'] == '입양').sum(), len(sub)):.1f}%, "
              f"자연사 {pct((sub['outcome'] == '자연사').sum(), len(sub)):.1f}%, 안락사 {pct((sub['outcome'] == '안락사').sum(), len(sub)):.1f}%")
    A(f"- {last_year}년은 아직 '보호중'인 건이 포함돼 있어 다른 연도와 단순 비교하기 어려워요.")
    A("\n관련 선행연구(소유자 반환·동물등록):\n" + papers("소유자 반환·동물등록") + "\n")

    # ---------- 5. 처리 소요일(추정) ----------
    d = ended.dropna(subset=["days_to_update_est"])
    d = d[d["days_to_update_est"] <= 365]
    los = d.groupby("outcome")["days_to_update_est"].describe(percentiles=[0.25, 0.5, 0.75])[["count", "25%", "50%", "75%"]]
    los = los.reindex([o for o in OUTCOME_ORDER if o in los.index])
    los.round(1).to_csv(TAB / "07_days_to_outcome_est.csv", encoding="utf-8-sig")
    fig, ax = plt.subplots(figsize=(8, 3.4))
    order = [o for o in ["반환", "입양", "자연사", "안락사"] if o in d["outcome"].unique()]
    ax.boxplot([d.loc[d["outcome"] == o, "days_to_update_est"] for o in order], tick_labels=order, showfliers=False,
               patch_artist=True, boxprops=dict(facecolor="#dbeafe", color=ACCENT), medianprops=dict(color=INK))
    style(ax, "처리 결과별 소요일(추정: 최종수정일 - 발견일)", "일")
    f5 = save(fig, "05_days_to_outcome.png")
    A("## 5. 처리까지 걸린 기간 — 추정 (선행연구의 보호기간 지표)\n")
    A(f"![처리 소요일]({f5})\n")
    show = los.round(1).reset_index().rename(columns={"outcome": "처리 결과", "count": "건수", "25%": "하위 25%(일)", "50%": "중앙값(일)", "75%": "상위 25%(일)"})
    show["건수"] = show["건수"].astype(int)
    A(table_md(show) + "\n")
    A("- API에는 실제 처리일이 없어서, 기록이 마지막으로 수정된 날(updTm)을 처리일로 근사했어요. "
      "처리 후에 기록이 다시 수정되면 기간이 길게 잡힐 수 있으니 **참고용 추정치**로만 봐 주세요. 365일을 넘는 값은 제외했어요.")
    A("\n관련 선행연구(보호기간):\n" + papers("입소·보호기간·처리결과", 5).split("\n", 3)[-1] + "\n")

    # ---------- 6. 발생 지역 ----------
    gu = df["gu"].fillna("").replace("", "미상").value_counts()
    dong = df[df["dong_est"].notna() & (df["dong_est"] != "")]["dong_est"].value_counts().head(15)
    pd.DataFrame({"구": gu.index, "건수": gu.values}).to_csv(TAB / "08_gu.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame({"읍면동(추정)": dong.index, "건수": dong.values}).to_csv(TAB / "09_dong_top15.csv", index=False, encoding="utf-8-sig")
    fig, ax = plt.subplots(figsize=(8, 4.2))
    ax.barh(dong.index[::-1], dong.values[::-1], color=ACCENT)
    style(ax, "발견 장소 상위 15개 읍·면·동(장소 문자열에서 추출)", "")
    ax.grid(axis="x", color=GRID)
    f6 = save(fig, "06_dong_top15.png")
    has_dong = pct((df["dong_est"].fillna("") != "").sum(), len(df))
    A("## 6. 발생 지역 (과업지시서 제3조② 관내 전 지역)\n")
    A(f"![발생 지역]({f6})\n")
    A("- 구별: " + ", ".join(f"{k} {v:,}건({pct(v, len(df)):.1f}%)" for k, v in gu.items()))
    A(f"- 발견 장소 문자열에서 읍·면·동을 뽑을 수 있었던 건은 {has_dong:.1f}%예요. 장소가 '○○아파트', '○○로' 등으로만 적힌 경우는 빠지므로 분포는 근사치예요.")
    A(f"- 상위 3곳: " + ", ".join(f"{k}({v:,}건)" for k, v in dong.head(3).items()) + ". 출동 거리·3시간 내 포획 기준(제7조)을 검토할 때 거점 배치 참고 자료가 될 수 있어요.\n")

    # ---------- 7. 보호 두수 추정 ----------
    start = max(p_from, p_to - pd.Timedelta(days=3 * 365))
    days = pd.date_range(start, p_to, freq="D")
    occ = pd.Series(0, index=days)
    a = df[["happen_date", "days_to_update_est", "outcome"]].copy()
    a["end"] = a["happen_date"] + pd.to_timedelta(a["days_to_update_est"], unit="D")
    a.loc[a["outcome"] == "보호중", "end"] = p_to + pd.Timedelta(days=1)
    a = a.dropna(subset=["end"])
    for s, e in zip(a["happen_date"], a["end"]):
        if e < start or s > p_to:
            continue
        occ[max(s, start):min(e - pd.Timedelta(days=1), p_to)] += 1
    occ.rename("추정 보호 두수").to_csv(TAB / "10_occupancy_est.csv", encoding="utf-8-sig")
    fig, ax = plt.subplots(figsize=(9, 3.4))
    ax.plot(occ.index, occ.values, color=ACCENT, linewidth=1)
    ax.axhspan(150, 200, color=ACCENT2, alpha=0.15, label="과업지시서 기준 150~200마리")
    ax.legend(frameon=False, fontsize=8, loc="upper left")
    style(ax, "일별 보호 두수 추정(최근 3년)", "마리")
    f7 = save(fig, "07_occupancy_est.png")
    A("## 7. 보호 두수 추정 (과업지시서 2.3 다. 기준 마릿수 150~200마리)\n")
    A(f"![보호 두수 추정]({f7})\n")
    A(f"- 최근 3년 추정 보호 두수: 평균 **{occ.mean():.0f}마리**, 최소 {occ.min():.0f}마리, 최대 {occ.max():.0f}마리"
      f"({occ.idxmax():%Y-%m-%d}).")
    A("- 발견일부터 처리일(추정)까지 보호소에 있었다고 가정해 날마다 더한 값이에요. 처리일이 추정치라서 실제 보호 두수와 차이가 날 수 있어요. "
      "센터 내부의 일일 보호 현황과 맞춰 보정하는 것이 좋아요.\n")

    # ---------- 8. 데이터 공백 ----------
    A("## 8. 과업 요구사항 대비 데이터 공백\n")
    A("| 과업지시서 요구사항 | 공개 API로 확인 가능 여부 | 필요한 추가 자료 |")
    A("|---|---|---|")
    A("| 신고 접수 후 3시간 이내 포획, 긴급 1시간 이내 출동(제7조) | 불가 (신고·출동·포획 시각 없음) | 천안시 신고 접수·출동 일지 |")
    A("| 09:00~22:00 신고 접수, 2인 1조 근무(제6조) | 불가 (시각·인력 정보 없음) | 근무표, 시간대별 신고 기록 |")
    A("| 센터 도착 전 폐사 처리(제3조⑥) | 일부 (자연사 건수만, 도착 전·후 구분 없음) | 사체 처리 대장 |")
    A("| 교통사고 동물 후송·치료(제3조④) | 일부 (특이사항 문구에 의존) | 구조 사유 분류 기록 |")
    A("| 월별 처리실적 보고(제13조) | 가능 (월별 건수·처리 결과) | — |")
    A("\n## 9. 재현 방법\n")
    A("```bash\nexport DATA_GO_KR_KEY='공공데이터포털 인증키'\nexport KOSIS_API_KEY='KOSIS 인증키'\npython pipeline/run_all.py\n```\n")
    A("산출물: `data/processed/cheonan_rescues.csv`(정제 데이터), `analysis/tables/*.csv`(표), `analysis/figures/*.png`(그림)")

    (OUT / "REPORT.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("analysis/REPORT.md 생성 완료")


if __name__ == "__main__":
    main()
