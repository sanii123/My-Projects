#!/usr/bin/env bash
# Automated restore drill. docs/architecture.md section 9:
# "A backup you haven't test-restored is a hypothesis, not a backup."
#
# This is a TEMPLATE, not a working script yet - it assumes Barman is set up
# per section 9 (recommended tool, not yet provisioned in this repo). Fill in
# the TODOs once Barman is deployed against the agent's Postgres instance and
# wire this into cron / CI on a weekly schedule, feeding results into
# Prometheus per the "Monitoring hook" in section 9.
#
# Exit non-zero on ANY failure - this script's whole job is to be the thing
# that pages someone before a real restore is needed, not after.

set -euo pipefail

BARMAN_SERVER_NAME="${BARMAN_SERVER_NAME:-ipam-agent-pg}"
DRILL_CONTAINER_NAME="restore-drill-$(date +%s 2>/dev/null || echo pending)"
EXPECTED_MIN_SESSIONS_ROWCOUNT="${EXPECTED_MIN_SESSIONS_ROWCOUNT:-0}"

echo "== Restore drill starting for ${BARMAN_SERVER_NAME} =="

# 1. Restore the latest backup to a throwaway location/container.
#    TODO: barman restore ${BARMAN_SERVER_NAME} latest /tmp/restore_drill_data
echo "TODO: barman restore step not yet implemented"

# 2. Start a disposable Postgres instance against the restored data directory.
#    TODO: docker run --rm -d --name "${DRILL_CONTAINER_NAME}" \
#            -v /tmp/restore_drill_data:/var/lib/postgresql/data postgres:16-alpine
echo "TODO: throwaway Postgres instance not yet implemented"

# 3. Sanity check: row counts / checksums against known tables.
#    Compare against the primary - a restore that "succeeds" but is missing
#    rows is worse than an honest failure.
#    TODO: psql ... -c "SELECT count(*) FROM sessions;" and compare
echo "TODO: sanity check not yet implemented"

# 4. Tear down the throwaway instance.
#    TODO: docker rm -f "${DRILL_CONTAINER_NAME}"

# 5. Report result to monitoring (section 9's "Monitoring hook").
#    TODO: push a restore_drill_success{server="..."} 1|0 metric, e.g. via a
#    Prometheus Pushgateway, so a failed/skipped drill alerts like any other
#    monitoring signal rather than being discovered by reading a log file.
echo "TODO: metrics push not yet implemented"

echo "== Restore drill template ran (no real work done yet - see TODOs above) =="
