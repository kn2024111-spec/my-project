"""공공데이터포털 '농림축산식품부 농림축산검역본부_국가동물보호정보시스템 구조동물 조회 서비스' 클라이언트.

인증키는 코드에 적지 않고 환경변수 DATA_GO_KR_KEY 에서 읽는다.
연결이 자주 끊기는 환경을 고려해 지수 백오프로 재시도한다.
"""
from __future__ import annotations

import os
import sys
import time

import requests

BASE = "https://apis.data.go.kr/1543061/abandonmentPublicService_v2"


class ApiError(RuntimeError):
    pass


def _key() -> str:
    key = os.environ.get("DATA_GO_KR_KEY", "").strip()
    if not key:
        raise ApiError(
            "환경변수 DATA_GO_KR_KEY 가 없습니다. 공공데이터포털에서 발급받은 '일반 인증키(Decoding)'를 "
            "설정한 뒤 다시 실행하세요. 예) export DATA_GO_KR_KEY='발급받은키'"
        )
    return key


def call(endpoint: str, retries: int = 10, **params) -> dict:
    """API를 호출해 response.body 를 돌려준다. 실패 시 재시도, 끝내 실패하면 ApiError."""
    params = {"_type": "json", **params}
    last = None
    for attempt in range(retries):
        try:
            r = requests.get(f"{BASE}/{endpoint}", params={"serviceKey": _key(), **params}, timeout=(15, 60))
            if r.status_code == 200 and r.text.strip().startswith("{"):
                data = r.json()
                header = data.get("response", {}).get("header", {})
                if header.get("resultCode") not in ("00", "0"):
                    raise ApiError(f"API 오류 {header.get('resultCode')}: {header.get('resultMsg')}")
                return data["response"]["body"]
            # 인증 오류 등은 XML/텍스트로 오므로 재시도 의미 없음
            if r.status_code in (401, 403) or "SERVICE_KEY" in r.text:
                raise ApiError(f"인증 실패(HTTP {r.status_code}). 인증키나 활용신청 승인 상태를 확인하세요.")
            last = f"HTTP {r.status_code}: {r.text[:120]}"
        except ApiError:
            raise
        except (requests.RequestException, ValueError) as e:
            last = type(e).__name__
        print(f"  재시도 {attempt + 1}/{retries} ({endpoint}): {last}", file=sys.stderr, flush=True)
        time.sleep(min(2 ** attempt, 30))
    raise ApiError(f"{endpoint} 호출이 {retries}회 모두 실패했습니다({last}).")


def items(body: dict) -> list[dict]:
    it = (body.get("items") or {}) if isinstance(body.get("items"), dict) else {}
    it = it.get("item", [])
    return it if isinstance(it, list) else [it]
