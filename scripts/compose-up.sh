#!/usr/bin/env bash
# Build and start the stack with the current commit baked into the image.
#
# The container has no repository, so git_sha() cannot resolve the commit at
# runtime; it reads the GIT_SHA env var instead. This computes that value the
# same way git_sha() would on a working tree -- short SHA, plus a "-dirty"
# suffix when the tree carries uncommitted changes -- and hands it to compose.
set -euo pipefail

sha="$(git rev-parse --short HEAD)"
if [ -n "$(git status --porcelain)" ]; then
  sha="${sha}-dirty"
fi

# With no arguments Compose picks up compose.override.yaml and runs the dev
# stack. --prod names the files explicitly, which is what excludes the
# override; see compose.prod.yaml.
files=()
if [ "${1:-}" = "--prod" ]; then
  shift
  files=(-f compose.yaml -f compose.prod.yaml)
fi

export GIT_SHA="$sha"
exec docker compose "${files[@]}" up --build "$@"
