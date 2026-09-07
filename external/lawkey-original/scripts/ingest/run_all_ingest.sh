#!/usr/bin/env bash
# 매일/매주 돌아가는 통합 ingest 파이프라인.
# 크론에서 이걸 호출하면 아래 순서로 진행:
#   1) 법제처 OPEN API 신규 판례 수집 (LAWGOKR_OC 필요)
#   2) staging → 메인 DB 병합
#   3) decision_date 정제
#   4) judges DB 재구축
#
# 전제: LAWGOKR_OC 환경변수가 /etc/environment 또는 systemd env 파일에 설정되어 있어야 함.

set -euo pipefail

ROOT="/srv/lawkey/current"
LOG_DIR="/srv/lawkey/runs/logs"
mkdir -p "$LOG_DIR"

cd "$ROOT"
if [ ! -d ".venv" ]; then
  echo "ERROR: $ROOT/.venv not found" >&2
  exit 1
fi
. .venv/bin/activate

ts() { date '+%Y-%m-%d %H:%M:%S'; }
log() { echo "[$(ts)] $*" | tee -a "$LOG_DIR/ingest.log"; }

# 1. lawgokr DRF ----------
if [ -n "${LAWGOKR_OC:-}" ]; then
  log "=== law.go.kr DRF (OC=${LAWGOKR_OC:0:2}..) ==="
  MAX="${LAWGOKR_MAX:-500}"
  python3 scripts/ingest/lawgokr_drf.py --max "$MAX" \
      >>"$LOG_DIR/ingest.log" 2>&1 || log "  lawgokr failed (continuing)"
else
  log "SKIP lawgokr (LAWGOKR_OC not set)"
fi

# 2. Wikipedia justices master (weekly is enough but safe to run daily) ----
log "=== wiki justices ==="
python3 scripts/ingest/scourt_justices_wiki.py \
    >>"$LOG_DIR/ingest.log" 2>&1 || log "  wiki failed (continuing)"

# 3. Merge staging → main DB ----
log "=== merge staging into precedents.sqlite3 ==="
python3 scripts/ingest/merge_into_main_db.py \
    >>"$LOG_DIR/ingest.log" 2>&1 || log "  merge failed"

# 4. Clean invalid decision_date (idempotent) ----
log "=== clean invalid decision_date ==="
python3 scripts/ingest/clean_decision_dates.py --apply \
    >>"$LOG_DIR/ingest.log" 2>&1 || log "  clean failed"

# 5. Rebuild judges DB ----
log "=== rebuild judges.sqlite3 ==="
python3 scripts/build_judges_db.py \
    --precedents "/srv/lawkey/work16/저장파일/unified_precedent_db_2026-04-10_run3/precedents.sqlite3" \
    --out /srv/lawkey/shared/judges.sqlite3 \
    >>"$LOG_DIR/ingest.log" 2>&1 || log "  judges rebuild failed"

log "=== done ==="
