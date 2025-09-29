#!/usr/bin/env sh

# Simplified helper to regenerate requirements.txt
# Assumes pip-tools is already installed in the environment.

set -e

pip-compile --upgrade --output-file=requirements.txt requirements.in

printf '%s\n' "✅ requirements.txt updated. Commit the changes and rebuild the image."
