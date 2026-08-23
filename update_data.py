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
  3. 종목별실현손익현황조회 (POST /krstock/inquiry/v1/tradingPnl) — 보유 시작일부터
     오늘까지 기간을 지정해 실제 매도 체결 기반 실현손익을 조회. 현재 잔고에 없는
     종목만 골라 "수익실현 종목" 데이터로 사용.
  4. 기존 portfolio_data.json을 읽어서 오늘 날짜 항목을 추가/갱신
     - NH 데이터는 API로 받은 실시간 값 사용
     - 미래에셋/KB(삼성전자)는 API로 조회가 안 되므로, NH가 알려준 삼성전자
       "현재가"에 고정 보유수량(298주/59주)을 곱해 매번 시가로 재계산
  5. portfolio_data.json 덮어쓰기
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


def get_trading_pnl(token, account_no, start_date, end_date):
    """
    국내_주식_조회_종목별실현손익 API — 지정한 기간(iqr_sta_dt~iqr_end_dt) 동안의
    매수/매도 체결을 기준으로 종목별 실제 실현손익(pls_amt)을 계산해 돌려준다.
    현재 보유 중인 종목도 그 기간에 매매가 있었으면 같이 나오지만, 우리는
    "지금 잔고에 없는 종목"에 대해서만 이 값을 실제 실현손익으로 사용한다.
    """
    cts_flag = "N"
    cts = ""
    all_output1 = []

    while True:
        headers = {
            "Authorization": f"Bearer {token}",
            "cts_flag": cts_flag,
            "cts": cts,
        }
        json_body = {
            "Input_0": {
                "act_no": account_no,
                "iqr_sta_dt": start_date,  # YYYYMMDD
                "iqr_end_dt": end_date,    # YYYYMMDD
            }
        }
        result, resp_headers = http_post(
            f"{DOMAIN}/krstock/inquiry/v1/tradingPnl",
            headers=headers,
            json_body=json_body,
        )

        rsp_cd = result.get("rsp_cd")
        if rsp_cd not in (None, "00166", "00218"):
            print(f"경고: 종목별실현손익조회 응답코드 {rsp_cd} - {result.get('rsp_msg')}", file=sys.stderr)

        output1 = result.get("Output_1", [])
        if output1:
            all_output1.extend(output1)

        next_cts_flag = resp_headers.get("cts_flag") or result.get("cts_flag", "N")
        next_cts = resp_headers.get("cts") or result.get("cts", "")
        if next_cts_flag == "Y" and next_cts:
            cts_flag = "Y"
            cts = next_cts
        else:
            break

    return all_output1


# 2026년 KRX 휴장일 (주말 제외, 평일 중 시장이 쉬는 날).
# 출처: 한국거래소 공지 기준. 연도가 바뀌면 이 목록을 갱신해야 합니다.
KRX_HOLIDAYS_2026 = {
    "2026-01-01",  # 신정
    "2026-02-16", "2026-02-17", "2026-02-18",  # 설 연휴
    "2026-03-02",  # 삼일절 대체공휴일
    "2026-05-01",  # 근로자의 날
    "2026-05-05",  # 어린이날
    "2026-05-25",  # 부처님오신날 대체공휴일
    "2026-06-03",  # 전국동시지방선거
    "2026-07-17",  # 제헌절
    "2026-08-17",  # 광복절 대체공휴일
    "2026-09-24", "2026-09-25", "2026-09-28",  # 추석 연휴 + 대체공휴일
    "2026-10-05",  # 개천절 대체공휴일
    "2026-10-09",  # 한글날
    "2026-12-25",  # 성탄절
    "2026-12-31",  # 연말 휴장
}


def num(v, default=0):
    """API가 숫자를 문자열로 내려줄 수도 있어 방어적으로 변환."""
    if v is None:
        return default
    if isinstance(v, str):
        v = v.strip().replace(",", "")
        if v == "":
            return default
        try:
            return float(v)
        except ValueError:
            return default
    return v


NAME_CANON = {
    "KODEX K방산TOP10": "KODEX 방산TOP10",
    "TIGER 글로벌AI플랫폼": "TIGER 글로벌AI플랫폼액티브",
    # 사용자가 원본 엑셀에 오기입했던 이름들 → 실제 정확한 종목명으로 통일
    "KODEX 미국나스닥100테크액티브": "KODEX 미국나스닥AI테크액티브",
    "KODEX 미국나스닥100텍액티브": "KODEX 미국나스닥AI테크액티브",
    "KODEX 미국나스닥100": "KODEX 미국나스닥AI테크액티브",
    "KODEX 미국나스닥100...": "KODEX 미국나스닥AI테크액티브",
    "KODEX 미국나스닥AI액티브": "KODEX 미국나스닥AI테크액티브",
    "KODEX 미국나스닥시테크액티브": "KODEX 미국나스닥AI테크액티브",
}

# 미래에셋/KB 계좌의 삼성전자 보유 수량 (고정값 — 최초 엑셀 기준).
# 이 두 계좌는 API로 조회가 안 되므로, NH API가 돌려주는 "현재가(now_pr)"에
# 이 수량을 곱해 매번 시가로 재계산한다. (이전 버전은 마지막 저장값을 그대로
# 복사해 써서 시세에 따라 갱신되지 않는 문제가 있었음)
MIRAE_SHARES = 298
MIRAE_INV = 19922100
KB_SHARES = 59
KB_INV = 9858900


def canon(name):
    return NAME_CANON.get(name, name)


def main():
    appkey = os.environ.get("NH_APPKEY")
    appsecretkey = os.environ.get("NH_APPSECRETKEY")
    account_no = os.environ.get("NH_ACCOUNT_NO")

    if not (appkey and appsecretkey and account_no):
        print("환경변수 NH_APPKEY / NH_APPSECRETKEY / NH_ACCOUNT_NO 가 필요합니다.", file=sys.stderr)
        sys.exit(1)

    now_kst = datetime.now(KST)
    today_iso = now_kst.date().isoformat()
    if now_kst.weekday() >= 5:  # 5=토요일, 6=일요일
        print(f"{today_iso}은(는) 주말이라 KRX 휴장일 — 갱신을 건너뜁니다.")
        return
    if today_iso in KRX_HOLIDAYS_2026:
        print(f"{today_iso}은(는) KRX 휴장일 — 갱신을 건너뜁니다.")
        return

    token = get_access_token(appkey, appsecretkey)
    output0, output1 = get_all_balances(token, account_no)

    today = today_iso

    with open(DATA_FILE, "r", encoding="utf-8") as f:
        store = json.load(f)

    # 실현손익 조회 기간: 우리가 갖고 있는 가장 이른 날짜부터 오늘까지
    trading_pnl_start = (store["dates"][0] if store.get("dates") else today).replace("-", "")
    trading_pnl_end = today.replace("-", "")
    trading_output1 = get_trading_pnl(token, account_no, trading_pnl_start, trading_pnl_end)
    print(f"[진단] tradingPnl 조회기간 {trading_pnl_start}~{trading_pnl_end}, 받은 종목 수: {len(trading_output1)}")
    for it in trading_output1:
        print(f"[진단]   {it.get('iem_nm')!r} pls_amt={it.get('pls_amt')} sll_abk_amt={it.get('sll_abk_amt')} pft_rt={it.get('pft_rt')}")

    # ---- 종목별 갱신 ----
    for item in output1:
        name = canon(item.get("iem_nm", "").strip())
        if not name:
            continue
        qty = num(item.get("itg_bnc_qty"))
        phs_pr = num(item.get("phs_pr"))
        invested = round(qty * phs_pr)
        eval_amt = round(num(item.get("eal_amt")))
        pnl = round(num(item.get("eal_pls_amt")))
        pct = item.get("pft_rt")
        pct = round(num(pct), 2) if pct not in (None, "") else (
            round(pnl / invested * 100, 2) if invested else None
        )

        series = store["stocks"].setdefault(name, [])
        entry = {"date": today, "invested": invested, "eval": eval_amt, "pnl": pnl, "pct": pct}

        if name == "삼성전자":
            now_pr = num(item.get("now_pr"))
            mirae_eval = round(MIRAE_SHARES * now_pr)
            kb_eval = round(KB_SHARES * now_pr)
            mirae_pnl = mirae_eval - MIRAE_INV
            kb_pnl = kb_eval - KB_INV
            entry["nh"] = {"invested": invested, "eval": eval_amt, "pnl": pnl, "pct": pct}
            entry["mirae"] = {
                "invested": MIRAE_INV, "eval": mirae_eval, "pnl": mirae_pnl,
                "pct": round(mirae_pnl / MIRAE_INV * 100, 2) if MIRAE_INV else None,
            }
            entry["kb"] = {
                "invested": KB_INV, "eval": kb_eval, "pnl": kb_pnl,
                "pct": round(kb_pnl / KB_INV * 100, 2) if KB_INV else None,
            }
            total_inv = invested + MIRAE_INV + KB_INV
            total_eval = eval_amt + mirae_eval + kb_eval
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

    # ---- 실현손익(매도 완료 종목) 갱신 ----
    held_names = {canon((it.get("iem_nm") or "").strip()) for it in output1 if it.get("iem_nm")}
    print(f"[진단] 현재 보유중 종목명: {sorted(held_names)}")
    realized_stocks = {}
    for item in trading_output1:
        raw_name = (item.get("iem_nm") or "").strip()
        if not raw_name or raw_name.startswith("<"):
            continue
        name = canon(raw_name)
        if name in held_names:
            print(f"[진단]   건너뜀(보유중): {name}")
            continue  # 현재도 보유 중인 종목은 02번 섹션에서 이미 다룸
        pnl = round(num(item.get("pls_amt")))
        principal = round(num(item.get("sll_abk_amt")))
        pct_raw = item.get("pft_rt")
        pct = round(num(pct_raw), 2) if pct_raw not in (None, "") else (
            round(pnl / principal * 100, 2) if principal else None
        )
        prev = realized_stocks.get(name)
        if prev:
            # 같은 종목이 여러 건(분할매도 등)으로 나뉘어 나올 수 있어 합산
            prev["pnl"] += pnl
            prev["principal"] += principal
            prev["pct"] = round(prev["pnl"] / prev["principal"] * 100, 2) if prev["principal"] else None
        else:
            realized_stocks[name] = {"pnl": pnl, "principal": principal, "pct": pct}

    if realized_stocks:
        store["realizedStocks"] = realized_stocks
        store["realizedAsOf"] = today
        store["realizedFrom"] = store["dates"][0] if store.get("dates") else today
        print(f"[진단] realizedStocks 저장: {list(realized_stocks.keys())}")
    else:
        print("[진단] realizedStocks 없음 — trading_output1이 비었거나 전부 보유중 종목으로 필터링됨")

    # ---- 전체 요약 갱신 (NH 계좌 기준) ----
    nh_eval = round(num(output0.get("tot_eal_amt")))
    nh_invested = round(num(output0.get("tot_byn_amt")))
    nh_pnl = round(num(output0.get("tot_eal_pls")))
    nh_pct = output0.get("pft_rt")
    nh_pct = round(num(nh_pct), 2) if nh_pct not in (None, "") else (
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
