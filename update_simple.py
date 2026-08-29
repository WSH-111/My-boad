#!/usr/bin/env python3
"""
API 호출 없이 portfolio_data.json만 수동으로 업데이트하는 스크립트
- 사용법:
  - interactive: python update_simple.py
  - cli args:   python update_simple.py 170000000 100000000
  - env vars:   EVAL_AMT, INVESTED_AMT 환경변수 사용 가능
"""
import json
import os
import sys
from datetime import datetime, timezone, timedelta

KST = timezone(timedelta(hours=9))
DATA_FILE = "portfolio_data.json"

def get_inputs():
    # 1) 명령행 인수 우선
    if len(sys.argv) >= 3:
        return int(sys.argv[1]), int(sys.argv[2])
    # 2) 환경변수
    eval_env = os.getenv("EVAL_AMT")
    invested_env = os.getenv("INVESTED_AMT")
    if eval_env and invested_env:
        return int(eval_env), int(invested_env)
    # 3) 대화형(기본 동작) - 로컬 수동 실행용
    try:
        eval_amt = int(input("👉 평가금액 입력 (예: 170000000): "))
        invested_amt = int(input("👉 매수금액 입력 (예: 100000000): "))
        return eval_amt, invested_amt
    except EOFError:
        # 비대화형 환경에서 실수로 호출된 경우 명확한 에러
        raise RuntimeError("입력이 제공되지 않았습니다. CI 환경에서는 명령행 인수 또는 환경변수(EVAL_AMT, INVESTED_AMT)를 사용하세요.")

def update_with_input():
    today = datetime.now(KST).date().isoformat()
    print(f"\n📊 포트폴리오 데이터 업데이트 ({today})")
    print("=" * 50)

    eval_amt, invested_amt = get_inputs()

    pnl = eval_amt - invested_amt
    pct = round(pnl / invested_amt * 100, 2) if invested_amt else 0

    # 기존 파일 로드
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        store = json.load(f)

    # 새 데이터 항목
    overall_entry = {
        "date": today,
        "eval": eval_amt,
        "invested": invested_amt,
        "pnl": pnl,
        "pct": pct,
        "trueEval": eval_amt,
        "trueInvested": invested_amt,
        "truePnl": pnl,
        "truePct": pct,
    }

    # 기존 데이터에 추가/갱신
    overall = store.get("overall", [])
    if overall and overall[-1].get("date") == today:
        overall[-1] = overall_entry
        print(f"♻️  오늘 데이터 갱신됨")
    else:
        overall.append(overall_entry)
        store["overall"] = overall
        print(f"✨ 새로운 날짜 데이터 추가됨")

    # 날짜 목록에 추가
    dates = store.get("dates", [])
    if today not in dates:
        dates.append(today)
        dates.sort()
        store["dates"] = dates

    # 마지막 업데이트 시간
    store["lastUpdated"] = datetime.now(KST).strftime("%Y-%m-%d %H:%M")

    # 파일에 저장
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(store, f, ensure_ascii=False, indent=2)

    print("\n" + "=" * 50)
    print(f"✅ JSON 업데이트 완료!")
    print(f"   📅 날짜: {today}")
    print(f"   💰 평가금액: {eval_amt:,}원")
    print(f"   📈 매수금액: {invested_amt:,}원")
    print(f"   🎯 수익금액: {pnl:,}원")
    print(f"   📊 수익률: {pct}%")
    print("=" * 50)

if __name__ == "__main__":
    update_with_input()
