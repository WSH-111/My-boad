#!/usr/bin/env python3
"""
NH투자증권 Namuh PLUG OpenAPI 진단 스크립트.

잔고조회(/krstock/inquiry/v1/balance) 응답을 있는 그대로 출력해서
'매입금액'에 해당하는 실제 필드명이 무엇인지, 그리고 byn_amt 필드가
실제로 존재/정상 값인지 확인하기 위한 용도.

실행 방법 (update_data-1.py와 동일한 환경변수 필요):
  NH_APPKEY=... NH_APPSECRETKEY=... NH_ACCOUNT_NO=... python3 check_balance_fields.py

동작:
  1. 토큰 발급
  2. 잔고조회 1회(첫 페이지) 실행
  3. Output_1(종목 리스트) 중 첫 번째 종목의 전체 raw JSON을 예쁘게 출력
  4. 모든 종목에 대해 '금액'류로 보이는 필드(키에 amt/byn/pch 등이 들어간 것)만
     골라서 표로 요약 출력 → byn_amt 값이 실제로 몇 개 종목에서 비어있는지 한눈에 확인
"""

import json
import os
import sys
import urllib.request
import urllib.parse
import urllib.error

DOMAIN = "https://api.nhplug.com:8443"


def http_post(url, data=None, headers=None, json_body=None, timeout=15):
    headers = headers or {}
    if json_body is not None:
        body = json.dumps(json_body).encode("utf-8")
        headers.setdefault("Content-Type", "application/json;charset=UTF-8")
    else:
        body = urllib.parse.urlencode(data or {}).encode("utf-8")
        headers.setdefault("Content-Type", "application/x-www-form-urlencoded")
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            resp_body = resp.read().decode("utf-8")
            resp_headers = dict(resp.info())
            return json.loads(resp_body), resp_headers
    except urllib.error.HTTPError as e:
        print(f"HTTP {e.code} 오류: {e.read().decode('utf-8', 'ignore')}", file=sys.stderr)
        raise


def get_access_token(appkey, appsecretkey):
    result, _ = http_post(
        f"{DOMAIN}/oauth2/token",
        data={
            "appkey": appkey,
            "appsecretkey": appsecretkey,
            "grant_type": "client_credentials",
            "scope": "oob",
        },
    )
    token = result.get("access_token")
    if not token:
        raise RuntimeError(f"토큰 발급 실패: {result}")
    return token


def main():
    appkey = os.environ.get("NH_APPKEY")
    appsecretkey = os.environ.get("NH_APPSECRETKEY")
    account_no = os.environ.get("NH_ACCOUNT_NO")

    if not (appkey and appsecretkey and account_no):
        print("환경변수 NH_APPKEY / NH_APPSECRETKEY / NH_ACCOUNT_NO 가 필요합니다.", file=sys.stderr)
        sys.exit(1)

    token = get_access_token(appkey, appsecretkey)

    headers = {
        "Authorization": f"Bearer {token}",
        "cts_flag": "N",
        "cts": "",
    }
    json_body = {
        "Input_0": {
            "act_no": account_no,
            "bnc_bse_cd": "1",
            "ltg_aot_dit_cd": "9",
            "aet_bse": "2",
            "qut_dit_cd": "KRX",
        }
    }

    result, resp_headers = http_post(
        f"{DOMAIN}/krstock/inquiry/v1/balance",
        headers=headers,
        json_body=json_body,
    )

    output1 = result.get("Output_1", [])
    if not output1:
        print("Output_1이 비어 있습니다. 응답 전체:")
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    print("=" * 70)
    print(f"총 {len(output1)}개 종목 수신. 첫 번째 종목의 전체 raw 필드:")
    print("=" * 70)
    print(json.dumps(output1[0], ensure_ascii=False, indent=2))

    print()
    print("=" * 70)
    print("모든 종목의 '금액/매입' 관련 필드 요약 (키에 amt/byn/pch/avg 포함된 것만)")
    print("=" * 70)
    interesting_keys = [
        k for k in output1[0].keys()
        if any(tag in k.lower() for tag in ("amt", "byn", "pch", "avg", "qty"))
    ]
    print(f"후보 필드명: {interesting_keys}\n")

    header = ["iem_nm"] + interesting_keys
    print(" | ".join(header))
    for item in output1:
        row = [str(item.get("iem_nm", ""))] + [str(item.get(k, "")) for k in interesting_keys]
        print(" | ".join(row))

    print()
    zero_or_missing = [
        item.get("iem_nm") for item in output1
        if not item.get("byn_amt") or str(item.get("byn_amt")).strip() in ("", "0")
    ]
    print(f"byn_amt가 비어있거나 0인 종목 ({len(zero_or_missing)}개): {zero_or_missing}")


if __name__ == "__main__":
    main()
