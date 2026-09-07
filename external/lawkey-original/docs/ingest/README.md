# 판례·판사 데이터 수집 인프라

## 디렉토리 구조

```
/srv/lawkey/ingest/
  08_lawgokr_drf/
    raw/                # OPEN API 원본 (HTML)
    staging.jsonl       # 정규화된 row
  09_aihub_legal_qa/
    raw/                # AI Hub 다운로드 압축 해제본
    staging.jsonl
  10_scourt_judges/
    raw/
    staging.jsonl
  11_gwanbo_personnel/
    raw/                # 관보 PDF
    staging.jsonl
```

## 수집 → 정규화 → 메인 DB 병합 파이프라인

```
[source crawl]  →  raw/  →  [normalize]  →  staging.jsonl  →  [merge_into_main_db.py]  →  precedents.sqlite3
                                                                                       ↓
                                                                                   [build_judges_db.py]
                                                                                       ↓
                                                                                   judges.sqlite3
```

## 1. 법제처 OPEN API (08_lawgokr_drf)

가장 안정적이고 합법적인 자동 수집 경로. 약 80만 건의 판례 보유 (대법원 + 하급심).

### 사전 작업
1. https://open.law.go.kr/openLawPortal/cooperation/cooperationList.do 접속
2. 회원가입 (내국인)
3. "OPEN API 활용신청" → 도메인 또는 IP 등록
   - 운영: `lawkey.ai.kr` 또는 `43.200.191.87`
4. 발급받은 사용자ID(영문 4자) 복사

### 실행
AWS 서버에서:
```bash
sudo -u ubuntu -i
cd /srv/lawkey/current
. .venv/bin/activate
LAWGOKR_OC=발급받은ID python3 scripts/ingest/lawgokr_drf.py --query '*' --max 5000
```

`raw/` 캐시 + `staging.jsonl` 생성. 재실행하면 캐시 활용해 빠르게 재개.

### 자동화 (매일 새벽 3시 신규 판례 수집)
```bash
sudo crontab -u ubuntu -e
# 추가:
0 3 * * * cd /srv/lawkey/current && . .venv/bin/activate && LAWGOKR_OC=xxxx python3 scripts/ingest/lawgokr_drf.py --max 500 >> /srv/lawkey/runs/logs/lawgokr.log 2>&1
30 3 * * * cd /srv/lawkey/current && . .venv/bin/activate && python3 scripts/ingest/merge_into_main_db.py --source 08_lawgokr_drf >> /srv/lawkey/runs/logs/merge.log 2>&1
```

## 2. AI Hub 법률 판례 데이터셋 (09_aihub_legal_qa)

원문 약 25만 건 + QA 66k. 2024.10 신규 개방.

### 사전 작업 (사용자 직접)
1. https://www.aihub.or.kr/aihubdata/data/view.do?dataSetSn=71723
2. 로그인 → "데이터 신청"
3. 활용 목적·기간 적고 제출. 평일 1~3일 내 승인.
4. API 다운로드 (분할 압축) 또는 K-ICT 안심구역 사용
5. 압축 해제

### 업로드 + 정규화
```bash
# 로컬 → AWS
scp -i ~/.ssh/buylow-prod-seoul-20260330.pem aihub_files.zip ubuntu@43.200.191.87:/tmp/
ssh -i ~/.ssh/buylow-prod-seoul-20260330.pem ubuntu@43.200.191.87 '
  mkdir -p /srv/lawkey/ingest/09_aihub_legal_qa/raw
  unzip /tmp/aihub_files.zip -d /srv/lawkey/ingest/09_aihub_legal_qa/raw/
  cd /srv/lawkey/current && . .venv/bin/activate
  python3 scripts/ingest/aihub_normalize.py
  python3 scripts/ingest/merge_into_main_db.py --source 09_aihub_legal_qa
'
```

## 3. 메인 DB 병합

```bash
python3 scripts/ingest/merge_into_main_db.py            # 모든 source 병합
python3 scripts/ingest/merge_into_main_db.py --source 08_lawgokr_drf
```

`precedents.sqlite3`의 `canonical_id` 기준으로 UPSERT (중복 시 업데이트).

## 4. 판사 DB 재구축

판례 신규 추가 후:
```bash
python3 scripts/build_judges_db.py \
  --precedents "/srv/lawkey/work16/저장파일/unified_precedent_db_2026-04-10_run3/precedents.sqlite3" \
  --out /srv/lawkey/shared/judges.sqlite3
```

## 5. 향후 추가 source (스켈레톤만)

- **10_scourt_judges**: scourt.go.kr 대법관·고등부장 명단 (HTML 스크레이핑). 약 300명 마스터.
- **11_gwanbo_personnel**: 관보 법관 인사 공시 PDF 파서. 매년 2월/8월 정기인사. 누적 임명·전보 기록 → 판사 disambiguation 마스터.

이 두 source는 다음 세션에 구현 예정.
