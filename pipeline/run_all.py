"""전체 파이프라인 실행: 수집 → 검증·정제 → 1차 분석.

실행: python pipeline/run_all.py
필요한 환경변수: DATA_GO_KR_KEY(공공데이터포털), KOSIS_API_KEY(KOSIS)
"""
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
STEPS = [
    ("1-1 구조동물 수집(공공데이터포털)", "collect.py"),
    ("1-2 인구 수집(KOSIS)", "collect_population.py"),
    ("2~3 검증·정제", "process.py"),
    ("4 1차 분석", "analyze.py"),
]

for name, script in STEPS:
    print(f"\n=== {name} ===", flush=True)
    r = subprocess.run([sys.executable, "-u", str(HERE / script)], cwd=HERE)
    if r.returncode != 0:
        sys.exit(f"'{name}' 단계에서 멈췄어요. 위의 메시지를 확인하고 다시 실행하세요(이미 받은 달은 건너뜁니다).")
print("\n완료: analysis/REPORT.md 를 확인하세요.")
