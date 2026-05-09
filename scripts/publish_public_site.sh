#!/bin/zsh

set -euo pipefail

REPO_ROOT="${0:A:h:h}"
LOCK_DIR="/private/tmp/epi-dossier-public-publish.lock"
PYTHON_BIN="$REPO_ROOT/.venv/bin/python"
SSH_KEY="$HOME/.ssh/id_ed25519_epi_dossier"
PUSH_SSH_COMMAND="ssh -o StrictHostKeyChecking=accept-new -i $SSH_KEY"

cleanup() {
  rmdir "$LOCK_DIR" 2>/dev/null || true
}

if ! mkdir "$LOCK_DIR" 2>/dev/null; then
  echo "Public publish already running; exiting."
  exit 0
fi
trap cleanup EXIT

collect_blocking_changes() {
  local -a blocking=()
  local line path
  while IFS= read -r line; do
    [[ -z "$line" ]] && continue
    path="${line#?? }"
    [[ "$path" == docs/* ]] && continue
    blocking+=("$path")
  done < <(git -C "$REPO_ROOT" status --porcelain)
  print -r -- "${blocking[@]}"
}

report_blocking_and_exit_if_needed() {
  local -a blocking
  blocking=("${(@f)$(collect_blocking_changes)}")
  if (( ${#blocking[@]} > 0 )); then
    echo "Skipping automated public publish because the repo has non-generated changes:"
    printf ' - %s\n' "${blocking[@]}"
    exit 0
  fi
}

report_blocking_and_exit_if_needed

cd "$REPO_ROOT"
"$PYTHON_BIN" -m src.site_build --days 7 --output-mode both --deploy-dir docs

report_blocking_and_exit_if_needed

git add docs

if git diff --cached --quiet -- docs; then
  echo "No public-site changes to publish."
  exit 0
fi

commit_message="Automated public refresh $(date '+%Y-%m-%d %H:%M %Z')"
git commit -m "$commit_message"
GIT_SSH_COMMAND="$PUSH_SSH_COMMAND" git push origin main
echo "Published public site refresh."
