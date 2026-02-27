# art_scopus

PDF 논문에서 초록(abstract)을 추출하고, Scopus 초록과 비교 평가하는 도구입니다.

이 프로젝트는 아래 작업을 수행합니다.
- Google Vision OCR로 PDF 앞부분 텍스트 추출
- OpenAI로 초록 본문 추출 및 신뢰도 확인
- Scopus 초록과 유사도/단어 지표 비교
- 파일별 JSON 캐시와 배치 CSV 로그 생성

## 1) 사전 준비

- Python 3.10 이상
- Poppler 설치 (`pdf2image` 실행에 필요)
- Google Vision 서비스 계정 JSON 키
- OpenAI API 키

## 2) 설치

```bash
pip install -r requirements.txt
```

## 3) Google Cloud 설정 (필수)

OCR 실행 전, 사용자 본인 Google Cloud 프로젝트에서 아래를 설정해야 합니다.

1. Cloud Vision API 활성화
2. 결제(Billing) 활성화
3. Vision API 사용 가능한 서비스 계정 생성
4. 서비스 계정 JSON 키 파일 발급 및 로컬 저장
5. `GOOGLE_APPLICATION_CREDENTIALS` 환경변수에 JSON 경로 지정

결제가 비활성화된 경우 OCR 호출은 `403 BILLING_DISABLED` 오류로 실패합니다.

서비스 계정 JSON 파일은 GitHub에 업로드하면 안 됩니다.

## 4) 환경변수

공개 저장소에서는 키를 파일에 넣지 말고 환경변수로 설정하세요.

### Windows PowerShell

```powershell
$env:OPENAI_API_KEY="<OpenAI API 키>"
$env:GOOGLE_APPLICATION_CREDENTIALS="C:\경로\service-account.json"
```

### macOS/Linux

```bash
export OPENAI_API_KEY="<OpenAI API 키>"
export GOOGLE_APPLICATION_CREDENTIALS="/경로/service-account.json"
```

`.env.example` 파일을 템플릿으로 참고할 수 있습니다.

## 5) 입력 파일

기본 경로는 아래와 같습니다.
- PDF 폴더: `./PDF`
- Scopus CSV: `./scopus_eng_20250325.csv`

Scopus CSV에는 아래 칼럼이 반드시 있어야 합니다.
- `art_id` (파일 식별자 또는 파일명)
- `abstr` (비교용 초록)

## 6) 실행

### 파일 1개 처리

```bash
python art_scopus.py --file 12345.pdf
```

### 앞에서 N개 처리

```bash
python art_scopus.py --count 20
```

### 인터랙티브 모드

```bash
python art_scopus.py --interactive
```

### 자주 쓰는 옵션 예시

```bash
python art_scopus.py --count 10 --max-workers 6 --dpi 250 --page-start 0 --page-end 1
```

## 7) 출력 결과

- OCR 캐시: `OCR_vision/<file_id>.json` (실행 시 자동 생성)
- 추출 캐시: `EXT_vision/<file_id>.json` (실행 시 자동 생성)
- 실행 로그: `logs/abstract_extraction_YYYYMMDD_HHMMSS.csv` (실행 시 자동 생성)

## 8) 보안 주의사항

- 서비스 계정 JSON, `.env` 파일을 커밋하지 마세요.
- Google 자격증명 JSON은 로컬에만 보관하세요.
- API 키는 반드시 환경변수로 관리하세요.
- 키가 노출된 적이 있으면 즉시 재발급(rotate) 하세요.
- `.gitignore`에 민감파일/산출물 제외 규칙이 포함되어 있습니다.

## 9) 프로젝트 구조

```text
art_scopus.py                # CLI 진입점
art_scopus_lib/
  cli.py                     # 인자 파싱 및 실행 흐름
  config.py                  # 설정 로딩 및 유효성 검증
  ocr.py                     # Google Vision OCR
  llm.py                     # OpenAI 추출/검증
  metrics.py                 # 유사도/단어 지표 계산
  pipeline.py                # 병렬 처리 파이프라인
  retry_utils.py             # 재시도 유틸리티
  storage.py                 # CSV/JSON 입출력
.env.example
PDF/                         # 입력 PDF 폴더
scopus_eng_20250325.csv      # 입력 CSV
requirements.txt
README.md
```
