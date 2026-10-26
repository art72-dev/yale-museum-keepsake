#!/bin/bash
# Approved full harvest (option A, 2026-10-25): wait until LUX answers, finish the samples, then harvest
# everything on view + Musical Instruments and Campus Art with images, at 1 request every 2 seconds.
# Every step resumes where it stopped, so if LUX blocks again we just wait and run the steps again.
# Log: data/lux/full/option_a.log      Stop: kill this script's process (Ctrl-C if run in a terminal).

cd "$(dirname "$0")/.." || exit 1
PY=.venv/bin/python
H=harvest/lux_harvest.py
UA="YaleMuseumKeepsake/0.1 (Yale SOM MGT 409 student project; polite harvester, 1 request/second)"
CHECK_URL="https://lux.collections.yale.edu/api/search-estimate/item?q=%7B%22text%22%3A%22teapot%22%7D"
STOP_WAITING_AT="${STOP_WAITING_AT:-2026-10-26 12:00}"   # stop waiting for LUX after this (local time)
LOG=data/lux/full/option_a.log
mkdir -p data/lux/full

log() { echo "$(date '+%Y-%m-%d %H:%M:%S') $*" | tee -a "$LOG"; }

wait_for_lux() {     # one request every 15 minutes until LUX answers 200
  local stop_at code
  stop_at=$(date -j -f "%Y-%m-%d %H:%M" "$STOP_WAITING_AT" +%s)
  while true; do
    code=$(curl -s -o /dev/null -m 30 -w "%{http_code}" -A "$UA" "$CHECK_URL")
    if [ "$code" = "200" ]; then log "LUX is answering (HTTP 200)"; return 0; fi
    if [ "$(date +%s)" -ge "$stop_at" ]; then log "LUX still answers HTTP $code at $STOP_WAITING_AT: giving up"; return 1; fi
    log "LUX answers HTTP $code; next check in 15 min"
    sleep 900
  done
}

step() {             # exit code 0 = done, 2 = LUX blocked us again (wait, then rerun), other = error
  log "RUN: $*"
  "$PY" -u "$H" --interval 2 "$@" >> "$LOG" 2>&1
  local rc=$?
  log "EXIT $rc: $*"
  return $rc
}

while true; do
  wait_for_lux || exit 1
  step sample --n 20 --resume; rc=$?
  [ $rc = 2 ] && continue; [ $rc != 0 ] && exit $rc
  "$PY" "$H" report data/lux/samples --output output/lux_report_samples.md \
      --title "LUX samples: 20 records per museum" --html output/lux_samples_preview.html >> "$LOG" 2>&1
  step harvest --scope on_view --museum yuag ycba peabody yale_library paul_mellon_centre \
      babylonian_collection lewis_walpole_library; rc=$?
  [ $rc = 2 ] && continue; [ $rc != 0 ] && exit $rc
  step harvest --scope images --museum musical_instruments campus_art; rc=$?
  [ $rc = 2 ] && continue; [ $rc != 0 ] && exit $rc
  "$PY" "$H" report data/lux/full --output output/lux_report_full.md \
      --title "LUX full harvest: option A" --html output/lux_full_preview.html >> "$LOG" 2>&1
  log "DONE"
  exit 0
done
