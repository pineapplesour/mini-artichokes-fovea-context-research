#!/usr/bin/env bash
# Cron 설정 헬퍼. AWS 원본에서 `sudo -u ubuntu bash install_cron.sh` 로 실행.
# 매일 새벽 3시에 통합 ingest 파이프라인 실행.

set -euo pipefail

CRON_ENTRY="0 3 * * * /srv/lawkey/current/scripts/ingest/run_all_ingest.sh >> /srv/lawkey/runs/logs/cron.log 2>&1"

# 기존 crontab 유지 + 중복 제거 후 추가
(crontab -l 2>/dev/null | grep -vF "run_all_ingest.sh" ; echo "$CRON_ENTRY") | crontab -
echo "installed cron entry:"
crontab -l | grep "run_all_ingest.sh"
