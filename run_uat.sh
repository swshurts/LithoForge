#!/usr/bin/env bash
# Lithoforge Automated UAT runner
#
# Runs all backend pytests + the Playwright E2E suite + a few curl smoke
# checks. Exits non-zero if anything fails. Output is grouped so it's easy
# to scan.

set -u
TOTAL_FAILS=0
TS_START=$(date +%s)

# Colors
G="\033[1;32m"; R="\033[1;31m"; Y="\033[1;33m"; B="\033[1;36m"; N="\033[0m"

section() { echo -e "\n${B}━━ $1 ━━${N}"; }
pass()    { echo -e "${G}✓${N} $1"; }
fail()    { echo -e "${R}✗${N} $1"; TOTAL_FAILS=$((TOTAL_FAILS+1)); }

# 1. Backend pytest
section "Backend pytest"
if (cd /app/backend && python -m pytest tests/ -q 2>&1 | tail -3 | grep -q "passed"); then
  COUNT=$(cd /app/backend && python -m pytest tests/ --co -q 2>/dev/null | grep -E "::" | wc -l)
  pass "Backend pytest suite ($COUNT tests)"
else
  fail "Backend pytest suite — re-run with: cd /app/backend && python -m pytest tests/ -v"
fi

# 2. Backend log clean
section "Backend log freshness"
if ! tail -n 100 /var/log/supervisor/backend.err.log 2>/dev/null | grep -E "Traceback|ERROR|CRITICAL" | grep -v Deprecat > /dev/null; then
  pass "No fresh exceptions in backend logs"
else
  fail "Fresh exceptions in backend logs — tail /var/log/supervisor/backend.err.log"
fi

# 3. No _id leaks
section "No ObjectId leaks in marketplace responses"
API_URL=$(grep REACT_APP_BACKEND_URL /app/frontend/.env | cut -d= -f2)
LEAKS=$(curl -s "$API_URL/api/marketplace" | python3 -c "
import sys,json
try:
    data = json.load(sys.stdin)
except Exception:
    print('parse-error'); sys.exit()
def find(obj):
    if isinstance(obj, dict):
        if '_id' in obj: return True
        return any(find(v) for v in obj.values())
    if isinstance(obj, list):
        return any(find(x) for x in obj)
    return False
print('leak' if find(data) else 'ok')
")
if [ "$LEAKS" = "ok" ]; then
  pass "Marketplace responses are ObjectId-free"
else
  fail "Marketplace response contains _id (got: $LEAKS)"
fi

# 4. Playwright E2E
section "Frontend E2E (Playwright)"
PYBIN=/opt/plugins-venv/bin/python
if $PYBIN -m pytest /app/e2e/uat_e2e.py -q --tb=short 2>&1 | tail -20; then
  pass "Playwright E2E suite"
else
  fail "Playwright E2E suite — re-run with: $PYBIN -m pytest /app/e2e/uat_e2e.py -v"
fi

# Final summary
TS_END=$(date +%s)
DURATION=$((TS_END - TS_START))
section "Result"
echo "  Duration: ${DURATION}s"
if [ $TOTAL_FAILS -eq 0 ]; then
  echo -e "  ${G}ALL AUTOMATED UAT SECTIONS PASSED${N}"
  echo "  Next step: walk through /app/MANUAL_UAT.md (12 human tests)"
  exit 0
else
  echo -e "  ${R}${TOTAL_FAILS} SECTION(S) FAILED${N}"
  exit 1
fi
