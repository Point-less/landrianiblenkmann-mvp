#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

coverage run --rcfile=.coveragerc manage.py test "$@"
coverage report
