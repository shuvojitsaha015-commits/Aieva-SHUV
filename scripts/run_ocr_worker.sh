#!/usr/bin/env bash
# Start the Aieva background OCR service.
#
# The service watches a folder and reads every new image in the background -
# the result (LaTeX + the SymPy parsable text) is written as JSON into the
# outbox. It is the piece the instructor asked for: an application that runs
# in the background and performs the OCR.
#
#   ./scripts/run_ocr_worker.sh                       # watch ./ocr_inbox
#   ./scripts/run_ocr_worker.sh --inbox /tmp/shots --outbox /tmp/results
#   ./scripts/run_ocr_worker.sh --mock --once         # read what is there and exit
#
# With a running Aieva server the worker uses it; without a key it uses the
# mock engine so that the pipeline can be demonstrated offline.
set -euo pipefail

cd "$(dirname "$0")/.."

INBOX="${AIEVA_OCR_INBOX:-ocr_inbox}"
OUTBOX="${AIEVA_OCR_OUTBOX:-ocr_outbox}"
POLL="${AIEVA_OCR_POLL:-2}"

if [ -f .env ]; then
  set -a
  # shellcheck disable=SC1091
  . ./.env
  set +a
fi

if [ -z "${GEMINI_API_KEY:-}" ] && [ "${AIEVA_MOCK_LLM:-false}" != "true" ]; then
  echo "[aieva] No GEMINI_API_KEY found -> the OCR worker uses the mock engine."
  MOCK="--mock"
else
  MOCK=""
fi

mkdir -p "$INBOX" "$OUTBOX"
echo "[aieva] OCR worker watching ${INBOX} -> ${OUTBOX} (poll ${POLL}s)"
exec python3 -m aieva.core.ocr.worker --inbox "$INBOX" --outbox "$OUTBOX" --poll "$POLL" $MOCK "$@"
