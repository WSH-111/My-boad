# 내 주식 계좌 대시보드 (자동 갱신)

## 파일 구성
- `index.html` — 대시보드 (React 전체 포함, 외부 CDN 의존 없음)
- `portfolio_data.json` — 대시보드가 읽어오는 데이터. `update_data.py`가 갱신함
- `update_data.py` — NH나무증권 Namuh PLUG API를 호출해 `portfolio_data.json`을 최신화
- `.github/workflows/update.yml` — 정해진 시간마다 `update_data.py`를 자동 실행

## 모바일에서 설정하는 방법 (GitHub 웹/앱 사용)

1. **저장소 만들기**: GitHub에서 새 Repository 생성 (Public 또는 Private 둘 다 가능)
2. **이 4개 파일을 그대로 업로드**: 저장소 화면에서 "Add file → Upload files"로
   `index.html`, `portfolio_data.json`, `update_data.py`,
   `.github/workflows/update.yml` (폴더 경로 그대로 유지) 업로드 후 커밋
3. **비밀키 등록**: 저장소 → Settings → Secrets and variables → Actions →
   "New repository secret" 3개 등록
   - `NH_APPKEY` : 발급받은 AppKey
   - `NH_APPSECRETKEY` : 발급받은 AppSecretKey
   - `NH_ACCOUNT_NO` : NH 계좌번호 (하이픈 없이 숫자만)
4. **GitHub Pages 켜기**: Settings → Pages → Source를
   "Deploy from a branch" → Branch: `main` (또는 `master`) / `/ (root)` 선택 후 저장
   → 몇 분 뒤 `https://<계정명>.github.io/<저장소명>/` 주소로 대시보드 접속 가능
5. **자동 실행 확인**: 저장소 → Actions 탭에서 "주식 데이터 자동 갱신" 워크플로우가
   보이면 성공. 기다리지 않고 바로 테스트하려면 그 화면에서
   "Run workflow" 버튼으로 수동 실행 가능

## 실행 주기 바꾸기
`.github/workflows/update.yml`의 `cron` 값을 수정하세요.
(cron은 UTC 기준이라 한국시간(KST)보다 9시간 느립니다)

## 참고
- 미래에셋·KB증권의 삼성전자 잔고는 NH API로 조회가 안 되기 때문에
  자동으로 갱신되지 않고, 마지막으로 저장된 값을 그대로 이어씁니다.
  이 부분을 갱신하려면 `portfolio_data.json`의 해당 값을 수동으로 고치면 됩니다.
- API 접근토큰은 24시간 유효하며, 스크립트가 실행될 때마다 새로 발급받으므로
  별도 관리가 필요 없습니다.
