#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

PYTHON="${PYTHON:-python3}"
log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }

log "=== Visa Bulletin update started ==="

YEAR=$(date +%Y)
MONTH=$(date +%-m)
NEXT_MONTH=$(( MONTH + 1 )); NEXT_YEAR=$YEAR
if [ $NEXT_MONTH -gt 12 ]; then NEXT_MONTH=1; NEXT_YEAR=$(( YEAR + 1 )); fi

log "Fetching ${MONTH}/${YEAR} ..."
$PYTHON scraper/scrape.py --year "$YEAR" --month "$MONTH" \
  && log "Saved: data/${YEAR}-$(printf '%02d' $MONTH).json" \
  || log "WARN: current month fetch failed"

log "Fetching ${NEXT_MONTH}/${NEXT_YEAR} (advance preview) ..."
$PYTHON scraper/scrape.py --year "$NEXT_YEAR" --month "$NEXT_MONTH" \
  && log "Saved: data/${NEXT_YEAR}-$(printf '%02d' $NEXT_MONTH).json" \
  || log "INFO: next month not yet published (normal before the 8th)"

log "Building frontend (embedding data into HTML) ..."
$PYTHON build.py && log "Build complete"

log "=== Update complete. Open frontend/index.html ==="

# Optional Slack webhook — uncomment and set SLACK_WEBHOOK to enable:
# SLACK_WEBHOOK="${SLACK_WEBHOOK:-}"
# if [ -n "$SLACK_WEBHOOK" ]; then
#   curl -s -X POST "$SLACK_WEBHOOK" -H 'Content-type: application/json' \
#     --data "{\"text\":\"Visa Bulletin updated: ${YEAR}-$(printf '%02d' $MONTH) dashboard refreshed.\"}" \
#     > /dev/null && log "Slack notified"
# fi
