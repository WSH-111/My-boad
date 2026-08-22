#!/usr/bin/env python3
"""
NH투자증권 Namuh PLUG OpenAPI로 국내주식 잔고를 조회해
portfolio_data.json을 최신 값으로 갱신하는 스크립트.

필요한 환경변수 (GitHub Actions Secrets로 주입):
  NH_APPKEY        - 발급받은 AppKey
  NH_APPSECRETKEY  - 발급받은 AppSecretKey
  NH_ACCOUNT_NO    - NH 계좌번호 (하이픈 없이 숫자만, 11자리)

동작:
  1. 접근토큰 발급 (POST /oauth2/token)
  2. 주식잔고조회 연속조회 반복 수행 (POST /krstock/inquiry/v1/balance)
  3. 기존 portfolio_data.json을 읽어서 오늘 날짜 항목을 추가/갱신
     - NH 데이터는 API로 받은 실시간 값 사용
     - 미래에셋/KB(삼성전자) 데이터는 가장 최근 저장된 값을 이어씀
  4. portfolio_data.json 덮어쓰기
"""

import json
import os
import sys
import urllib.request
import urllib.parse
import urllib.error
from datetime import datetime, timezone, timedelta

DOMAIN = "https://api.nhplug.com:8443"
DATA_FILE = os.path.join(os.path.dirname(__file__), "portfolio_data.json")

KST = timezone(timedelta(hours=9))


def http_post(url, data=None, headers=None, json_body=None):
    headers = headers or {}
    if json_body is not None:
        body = json.dumps(json_body).encode("utf-8")
        headers.setdefault("Content-Type", "application/json;charset=UTF-8")
    else:
        body = urllib.parse.urlencode(data or {}).encode("utf-8")
        headers.setdefault("Content-Type", "application/x-www-form-urlencoded")
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
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


def get_all_balances(token, account_no):
    """
    cts, cts_flag를 이용해 모든 페이지를 조회하고
    Output_0(최종 합계 정보) 및 Output_1(종목 목록)을 누적하여 반환.
    """
    cts_flag = "N"
    cts = ""
    
    all_output1 = []
    final_output0 = {}

    while True:
        headers = {
            "Authorization": f"Bearer {token}",
            "cts_flag": cts_flag,
            "cts": cts
        }
        json_body = {
            "Input_0": {
                "act_no": account_no,
                "bnc_bse_cd": "1",       # 1: 주식관련 총 평가(체결기준)
                "ltg_aot_dit_cd": "9",   # 9: 전체
                "aet_bse": "2",          # 2: 총자산
                "qut_dit_cd": "KRX",     # KRX: KRX 정규장 시세만 (UNT=통합, NXT=NXT시세)
            }
        }

        result, resp_headers = http_post(
            f"{DOMAIN}/krstock/inquiry/v1/balance",
            headers=headers,
            json_body=json_body
        )

        rsp_cd = result.get("rsp_cd")
        if rsp_cd not in (None, "00166", "00218"):
            print(f"경고: 잔고조회 응답코드 {rsp_cd} - {result.get('rsp_msg')}", file=sys.stderr)

        output1 = result.get("Output_1", [])
        if output1:
            all_output1.extend(output1)

        if result.get("Output_0"):
            final_output0 = result.get("Output_0")

        next_cts_flag = resp_headers.get("cts_flag") or result.get("cts_flag", "N")
        next_cts = resp_headers.get("cts") or result.get("cts", "")

        if next_cts_flag == "Y" and next_cts:
            cts_flag = "Y"
            cts = next_cts
        else:
            break

    return final_output0, all_output1


NAME_CANON = {
    "KODEX K방산TOP10": "KODEX 방산TOP10",
    "TIGER 글로벌AI플랫폼": "TIGER 글로벌AI플랫폼액티브",
}


def canon(name):
    return NAME_CANON.get(name, name)


def main():
    appkey = os.environ.get("NH_APPKEY")
    appsecretkey = os.environ.get("NH_APPSECRETKEY")
    account_no = os.environ.get("NH_ACCOUNT_NO")

    if not (appkey and appsecretkey and account_no):
        print("환경변수 NH_APPKEY / NH_APPSECRETKEY / NH_ACCOUNT_NO 가 필요합니다.", file=sys.stderr)
        sys.exit(1)

    token = get_access_token(appkey, appsecretkey)
    output0, output1 = get_all_balances(token, account_no)

    today = datetime.now(KST).date().isoformat()

    with open(DATA_FILE, "r", encoding="utf-8") as f:
        store = json.load(f)

    # ---- 종목별 갱신 ----
    for item in output1:
        name = canon(item.get("iem_nm", "").strip())
        if not name:
            continue
        qty = item.get("itg_bnc_qty") or 0
        phs_pr = item.get("phs_pr") or 0
        invested = round(qty * phs_pr)
        eval_amt = round(item.get("eal_amt") or 0)
        pnl = round(item.get("eal_pls_amt") or 0)
        pct = item.get("pft_rt")
        pct = round(pct, 2) if pct is not None else (
            round(pnl / invested * 100, 2) if invested else None
        )

        series = store["stocks"].setdefault(name, [])
        entry = {"date": today, "invested": invested, "eval": eval_amt, "pnl": pnl, "pct": pct}

        if name == "삼성전자":
            prev = series[-1] if series else {}
            mirae = prev.get("mirae")
            kb = prev.get("kb")
            entry["nh"] = {"invested": invested, "eval": eval_amt, "pnl": pnl, "pct": pct}
            entry["mirae"] = mirae
            entry["kb"] = kb
            add_inv = (mirae or {}).get("invested") or 0
            add_eval = (mirae or {}).get("eval") or 0
            add_inv += (kb or {}).get("invested") or 0
            add_eval += (kb or {}).get("eval") or 0
            total_inv = invested + add_inv
            total_eval = eval_amt + add_eval
            total_pnl = total_eval - total_inv
            entry["total"] = {
                "invested": total_inv, "eval": total_eval, "pnl": total_pnl,
                "pct": round(total_pnl / total_inv * 100, 2) if total_inv else None,
            }
            entry["invested"] = entry["total"]["invested"]
            entry["eval"] = entry["total"]["eval"]
            entry["pnl"] = entry["total"]["pnl"]
            entry["pct"] = entry["total"]["pct"]

        if series and series[-1]["date"] == today:
            series[-1] = entry
        else:
            series.append(entry)

    if today not in store["dates"]:
        store["dates"].append(today)
        store["dates"].sort()

    # ---- 전체 요약 갱신 (NH 계좌 기준) ----
    nh_eval = round(output0.get("tot_eal_amt") or 0)
    nh_invested = round(output0.get("tot_byn_amt") or 0)
    nh_pnl = round(output0.get("tot_eal_pls") or 0)
    nh_pct = output0.get("pft_rt")
    nh_pct = round(nh_pct, 2) if nh_pct is not None else (
        round(nh_pnl / nh_invested * 100, 2) if nh_invested else None
    )

    # 삼성전자의 미래에셋/KB 몫을 더해 "진짜 합계"도 함께 갱신 (근사치)
    ss_series = store["stocks"].get("삼성전자", [])
    ss_latest = ss_series[-1] if ss_series else {}
    add_inv = ((ss_latest.get("mirae") or {}).get("invested") or 0) + \
              ((ss_latest.get("kb") or {}).get("invested") or 0)
    add_eval = ((ss_latest.get("mirae") or {}).get("eval") or 0) + \
               ((ss_latest.get("kb") or {}).get("eval") or 0)
    true_eval = nh_eval + add_eval
    true_invested = nh_invested + add_inv
    true_pnl = true_eval - true_invested

    overall_entry = {
        "date": today,
        "eval": nh_eval, "invested": nh_invested, "pnl": nh_pnl, "pct": nh_pct,
        "trueEval": round(true_eval), "trueInvested": round(true_invested),
        "truePnl": round(true_pnl),
        "truePct": round(true_pnl / true_invested * 100, 2) if true_invested else None,
    }

    overall = store["overall"]
    if overall and overall[-1]["date"] == today:
        overall[-1] = overall_entry
    else:
        overall.append(overall_entry)

    store["lastUpdated"] = datetime.now(KST).strftime("%Y-%m-%d %H:%M")

    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(store, f, ensure_ascii=False, indent=2)

    print(f"갱신 완료: {today} / 평가금액 {nh_eval:,}원 / 수익률 {nh_pct}%")


if __name__ == "__main__":
    main()
