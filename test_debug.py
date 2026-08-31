import os
import requests
import json

# 1. API URL 설정
url = "https://www.nhplug.com/apiservice?group_id=5ebbc5cb-8234-41c4-bc95-86a51e42116a&api_id=b44fe112-508f-4e96-b7b8-bd88dffef94d"

# 2. update_data.py에서 사용 중인 헤더/파라미터 설정 (필요시 작성)
# 예: headers = {"Authorization": os.environ.get("NH_API_TOKEN")}
headers = {}
params = {}

print("=== [STEP 1] API 호출 시도 ===")
try:
    response = requests.get(url, headers=headers, params=params, timeout=10)
    print(f"응답 상태 코드 (Status Code): {response.status_code}")
    
    # 3. 응답 원본 확인
    data = response.json()
    print("=== [STEP 2] API 원본 JSON 응답 결과 ===")
    print(json.dumps(data, indent=2, ensure_ascii=False))
    
except Exception as e:
    print(f"=== [ERROR] API 호출 또는 JSON 변환 실패: {e} ===")
