#!/bin/bash
cd "$(dirname "$(readlink -f "$0")")" || exit 1
echo "Running SolarTracker console in $PWD"
if [ -x .venv/bin/python3 ]; then PY=.venv/bin/python3; else PY=python3; fi
"$PY" console.py "$@"
status=$?
echo
echo "console.py exited with code $status. Press Enter to close."
read -r
exit "$status"
