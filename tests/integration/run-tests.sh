#!/bin/bash
# Integration test script for Osiris backup management CLI.
# Runs inside the controller container against real PostgreSQL and MinIO.
set -uo pipefail

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

PASS_COUNT=0
FAIL_COUNT=0
SKIP_COUNT=0

pass_test() {
    echo -e "  ${GREEN}PASS${NC} $1"
    PASS_COUNT=$((PASS_COUNT + 1))
}

fail_test() {
    echo -e "  ${RED}FAIL${NC} $1"
    if [ -n "${2:-}" ]; then
        echo -e "       ${RED}$2${NC}"
    fi
    FAIL_COUNT=$((FAIL_COUNT + 1))
}

skip_test() {
    echo -e "  ${YELLOW}SKIP${NC} $1"
    SKIP_COUNT=$((SKIP_COUNT + 1))
}

section() {
    echo ""
    echo -e "${CYAN}=== $1 ===${NC}"
}

# Shorthand: run osiris in non-interactive mode
osiris() {
    command osiris --config /etc/osiris/config.yaml --non-interactive "$@"
}

# ---------------------------------------------------------------------------
# Phase 1: Validation
# ---------------------------------------------------------------------------
section "Phase 1: Validation"

# SSH connectivity to postgres
if ssh -o BatchMode=yes -o ConnectTimeout=5 -i /etc/osiris/ssh/id_ed25519 osiris@postgres "echo ok" >/dev/null 2>&1; then
    pass_test "SSH to postgres"
else
    fail_test "SSH to postgres"
fi

# SSH connectivity to minio
if ssh -o BatchMode=yes -o ConnectTimeout=5 -i /etc/osiris/ssh/id_ed25519 osiris@minio "echo ok" >/dev/null 2>&1; then
    pass_test "SSH to minio"
else
    fail_test "SSH to minio"
fi

# pg_dump available on postgres host
if ssh -o BatchMode=yes -i /etc/osiris/ssh/id_ed25519 osiris@postgres "which pg_dump" >/dev/null 2>&1; then
    pass_test "pg_dump available on postgres"
else
    fail_test "pg_dump available on postgres"
fi

# Restic repo is initialized
if restic --repo /var/backups/osiris/repo --password-file /etc/osiris/repo-password snapshots --json >/dev/null 2>&1; then
    pass_test "Restic repo initialized"
else
    fail_test "Restic repo initialized"
fi

# osiris validate
OUTPUT=$(osiris validate 2>&1) && RC=$? || RC=$?
if [ "$RC" -eq 0 ]; then
    pass_test "osiris validate"
else
    fail_test "osiris validate" "$OUTPUT"
fi

# ---------------------------------------------------------------------------
# Phase 2: Full Backup
# ---------------------------------------------------------------------------
section "Phase 2: Full Backup"

OUTPUT=$(osiris backup --force 2>&1) && RC=$? || RC=$?
if [ "$RC" -eq 0 ]; then
    pass_test "osiris backup --force"
else
    fail_test "osiris backup --force" "$OUTPUT"
fi

# Verify snapshots appear in list
OUTPUT=$(osiris list 2>&1) && RC=$? || RC=$?
if [ "$RC" -eq 0 ] && echo "$OUTPUT" | grep -q "OK"; then
    pass_test "osiris list shows backup with OK status"
else
    fail_test "osiris list shows backup with OK status" "$OUTPUT"
fi

# Extract batch ID from list output (first column of first data row)
# The batch ID format is YYYYMMDD-HHMMSS
BATCH_ID=$(osiris list 2>&1 | grep -oE '[0-9]{8}-[0-9]{6}' | head -1)
if [ -n "$BATCH_ID" ]; then
    pass_test "Extracted batch ID: $BATCH_ID"
else
    fail_test "Could not extract batch ID from list output"
    # Try to continue with a fallback - check restic directly
    BATCH_ID=$(restic --repo /var/backups/osiris/repo --password-file /etc/osiris/repo-password snapshots --json 2>/dev/null \
        | python3 -c "
import json,sys
snaps=json.load(sys.stdin)
for s in snaps:
    for t in s.get('tags',[]):
        if t.startswith('osiris:'):
            print(t.split(':',1)[1])
            sys.exit(0)
" 2>/dev/null || true)
    if [ -n "$BATCH_ID" ]; then
        echo "       (recovered batch ID from restic: $BATCH_ID)"
    fi
fi

# Check osiris status (may exit 1 due to no systemd timer, that's OK)
OUTPUT=$(osiris status 2>&1) || true
if echo "$OUTPUT" | grep -qi "initialized\|accessible"; then
    pass_test "osiris status shows repository info"
else
    fail_test "osiris status shows repository info" "$OUTPUT"
fi

# ---------------------------------------------------------------------------
# Phase 3: Target-Specific Backup
# ---------------------------------------------------------------------------
section "Phase 3: Target-Specific Backup"

OUTPUT=$(osiris backup --target postgres --force 2>&1) && RC=$? || RC=$?
if [ "$RC" -eq 0 ]; then
    pass_test "osiris backup --target postgres"
else
    fail_test "osiris backup --target postgres" "$OUTPUT"
fi

OUTPUT=$(osiris backup --target minio --force 2>&1) && RC=$? || RC=$?
if [ "$RC" -eq 0 ]; then
    pass_test "osiris backup --target minio"
else
    fail_test "osiris backup --target minio" "$OUTPUT"
fi

# Should now have 3 batches in list
BATCH_COUNT=$(osiris list 2>&1 | grep -cE '[0-9]{8}-[0-9]{6}' || true)
if [ "$BATCH_COUNT" -ge 3 ]; then
    pass_test "osiris list shows >= 3 batches ($BATCH_COUNT)"
else
    fail_test "osiris list shows >= 3 batches (got $BATCH_COUNT)"
fi

# ---------------------------------------------------------------------------
# Phase 4: Verification
# ---------------------------------------------------------------------------
section "Phase 4: Verification"

OUTPUT=$(osiris verify 2>&1) && RC=$? || RC=$?
if [ "$RC" -eq 0 ]; then
    pass_test "osiris verify"
else
    fail_test "osiris verify" "$OUTPUT"
fi

# Show details of the full backup batch
if [ -n "$BATCH_ID" ]; then
    OUTPUT=$(osiris show "$BATCH_ID" 2>&1) && RC=$? || RC=$?
    if [ "$RC" -eq 0 ]; then
        pass_test "osiris show $BATCH_ID"

        # Verify it contains both targets
        if echo "$OUTPUT" | grep -q "postgres" && echo "$OUTPUT" | grep -q "minio"; then
            pass_test "show output contains both targets"
        else
            fail_test "show output contains both targets" "$OUTPUT"
        fi
    else
        fail_test "osiris show $BATCH_ID" "$OUTPUT"
        skip_test "show output contains both targets"
    fi
else
    skip_test "osiris show (no batch ID)"
    skip_test "show output contains both targets (no batch ID)"
fi

# ---------------------------------------------------------------------------
# Phase 5: Restore
# ---------------------------------------------------------------------------
section "Phase 5: Restore"

if [ -n "$BATCH_ID" ]; then
    # Drop the users table from osiris_test to verify restore brings it back
    echo "  Dropping users table from osiris_test..."
    ssh -o BatchMode=yes -i /etc/osiris/ssh/id_ed25519 osiris@postgres \
        "psql -U postgres -d osiris_test -c 'DROP TABLE IF EXISTS sessions CASCADE; DROP TABLE IF EXISTS users CASCADE;'" \
        >/dev/null 2>&1

    # Verify the table is gone
    TABLE_CHECK=$(ssh -o BatchMode=yes -i /etc/osiris/ssh/id_ed25519 osiris@postgres \
        "psql -U postgres -d osiris_test -t -c \"SELECT count(*) FROM information_schema.tables WHERE table_name='users'\"" \
        2>/dev/null | tr -d ' \n\r')
    if [ "$TABLE_CHECK" = "0" ]; then
        pass_test "Verified users table was dropped"
    else
        fail_test "Users table still exists after drop (count=$TABLE_CHECK)"
    fi

    # Restore from the full backup
    OUTPUT=$(osiris restore --batch-id "$BATCH_ID" --target postgres --force 2>&1) && RC=$? || RC=$?
    if [ "$RC" -eq 0 ]; then
        pass_test "osiris restore --batch-id $BATCH_ID --target postgres"
    else
        fail_test "osiris restore --batch-id $BATCH_ID --target postgres" "$OUTPUT"
    fi

    # Give PostgreSQL a moment to settle after database recreation
    sleep 2

    # Verify data came back
    USER_COUNT=$(ssh -o BatchMode=yes -i /etc/osiris/ssh/id_ed25519 osiris@postgres \
        "psql -U postgres -d osiris_test -t -c 'SELECT count(*) FROM users'" \
        2>/dev/null | tr -d ' \n\r')
    if [ "$USER_COUNT" = "3" ]; then
        pass_test "Restore recovered 3 users"
    else
        fail_test "Restore recovered users (expected 3, got '$USER_COUNT')"
    fi

    SESSION_COUNT=$(ssh -o BatchMode=yes -i /etc/osiris/ssh/id_ed25519 osiris@postgres \
        "psql -U postgres -d osiris_test -t -c 'SELECT count(*) FROM sessions'" \
        2>/dev/null | tr -d ' \n\r')
    if [ "$SESSION_COUNT" = "2" ]; then
        pass_test "Restore recovered 2 sessions"
    else
        fail_test "Restore recovered sessions (expected 2, got '$SESSION_COUNT')"
    fi

    # -- Minio restore --
    # Delete a seed file to verify restore brings it back
    ssh -o BatchMode=yes -i /etc/osiris/ssh/id_ed25519 osiris@minio \
        "rm -f /var/lib/minio/data/test-bucket/data-001.json" \
        >/dev/null 2>&1

    # Verify the file is gone
    FILE_CHECK=$(ssh -o BatchMode=yes -i /etc/osiris/ssh/id_ed25519 osiris@minio \
        "test -f /var/lib/minio/data/test-bucket/data-001.json && echo exists || echo missing" \
        2>/dev/null | tr -d ' \n\r')
    if [ "$FILE_CHECK" = "missing" ]; then
        pass_test "Verified data-001.json was deleted from minio"
    else
        fail_test "data-001.json still exists after deletion"
    fi

    # Restore minio target
    OUTPUT=$(osiris restore --batch-id "$BATCH_ID" --target minio --force 2>&1) && RC=$? || RC=$?
    if [ "$RC" -eq 0 ]; then
        pass_test "osiris restore --batch-id $BATCH_ID --target minio"
    else
        fail_test "osiris restore --batch-id $BATCH_ID --target minio" "$OUTPUT"
    fi

    # Verify file was restored
    FILE_CHECK=$(ssh -o BatchMode=yes -i /etc/osiris/ssh/id_ed25519 osiris@minio \
        "test -f /var/lib/minio/data/test-bucket/data-001.json && echo exists || echo missing" \
        2>/dev/null | tr -d ' \n\r')
    if [ "$FILE_CHECK" = "exists" ]; then
        pass_test "Restore recovered data-001.json"
    else
        fail_test "Restore did not recover data-001.json"
    fi

    # Verify content matches seed data
    RESTORED_CONTENT=$(ssh -o BatchMode=yes -i /etc/osiris/ssh/id_ed25519 osiris@minio \
        "cat /var/lib/minio/data/test-bucket/data-001.json" 2>/dev/null)
    EXPECTED='{"id": 1, "name": "alpha", "tags": ["test", "seed"], "timestamp": "2026-01-15T10:00:00Z"}'
    if [ "$RESTORED_CONTENT" = "$EXPECTED" ]; then
        pass_test "Restored data-001.json content matches seed data"
    else
        fail_test "Restored data-001.json content mismatch" "got: $RESTORED_CONTENT"
    fi
else
    skip_test "Restore tests (no batch ID available)"
fi

# ---------------------------------------------------------------------------
# Phase 6: Prune (dry-run)
# ---------------------------------------------------------------------------
section "Phase 6: Prune"

OUTPUT=$(osiris prune --dry-run 2>&1) && RC=$? || RC=$?
if [ "$RC" -eq 0 ]; then
    pass_test "osiris prune --dry-run"
else
    fail_test "osiris prune --dry-run" "$OUTPUT"
fi

# Verify dry-run mentions retention policy
if echo "$OUTPUT" | grep -qi "keep"; then
    pass_test "prune output shows retention policy"
else
    fail_test "prune output shows retention policy" "$OUTPUT"
fi

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
echo ""
echo "==========================================="
TOTAL=$((PASS_COUNT + FAIL_COUNT + SKIP_COUNT))
echo -e "  ${GREEN}Passed:  $PASS_COUNT${NC}"
echo -e "  ${RED}Failed:  $FAIL_COUNT${NC}"
if [ "$SKIP_COUNT" -gt 0 ]; then
    echo -e "  ${YELLOW}Skipped: $SKIP_COUNT${NC}"
fi
echo "  Total:   $TOTAL"
echo "==========================================="

if [ "$FAIL_COUNT" -gt 0 ]; then
    echo -e "${RED}INTEGRATION TESTS FAILED${NC}"
    exit 1
else
    echo -e "${GREEN}ALL INTEGRATION TESTS PASSED${NC}"
    exit 0
fi
