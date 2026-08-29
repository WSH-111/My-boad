#!/usr/bin/env python3
"""
API 호출 없이 portfolio_data.json만 수동으로 업데이트하는 스크립트
"""
import json
import os
from datetime import datetime, timezone, timedelta

KST = timezone(timedelta(hours=9))
DATA_FILE = "portfolio_data.json"

def update_with_input():
    today = datetime.now(KST).date().isoformat()
    
    print(f"\n📊 포트폴리오 데이터 업데이트 ({today})")
    print("=" * 50)
    
    # 사용자 입력
    eval_amt = int(input("👉 평가금액 입력 (예: 170000000): "))
    invested_amt = int(input("👉 매수금액 입력 (예: 100000000): "))
    
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
    overall = store["overall"]
    if overall and overall[-1]["date"] == today:
        overall[-1] = overall_entry
        print(f"♻️  오늘 데이터 갱신됨")
    else:
        overall.append(overall_entry)
        print(f"✨ 새로운 날짜 데이터 추가됨")
    
    # 날짜 목록에 추가
    if today not in store["dates"]:
        store["dates"].append(today)
        store["dates"].sort()
    
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