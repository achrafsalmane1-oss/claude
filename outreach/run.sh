#!/usr/bin/env bash
# Start the local outreach app.
cd "$(dirname "$0")"
exec python3 app.py --open "$@"
