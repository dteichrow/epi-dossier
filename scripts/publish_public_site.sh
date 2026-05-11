#!/bin/zsh

set -euo pipefail

REPO_ROOT="${0:A:h:h}"
EDGE_REPO_ROOT="$REPO_ROOT/../edge-of-epidemiology-site"
LOCK_DIR="/private/tmp/epi-dossier-public-publish.lock"
PYTHON_BIN="$REPO_ROOT/.venv/bin/python"
EDGE_PYTHON_BIN="$EDGE_REPO_ROOT/.venv/bin/python"
SSH_KEY="$HOME/.ssh/id_ed25519_epi_dossier"
GIT_BIN="/usr/bin/git"
SSH_BIN="/usr/bin/ssh"
DATE_BIN="/bin/date"
MKDIR_BIN="/bin/mkdir"
RMDIR_BIN="/bin/rmdir"
PUSH_SSH_COMMAND="$SSH_BIN -o StrictHostKeyChecking=accept-new -i $SSH_KEY"

cleanup() {
  "$RMDIR_BIN" "$LOCK_DIR" 2>/dev/null || true
}

publish_umbrella_site() {
  if [[ ! -d "$EDGE_REPO_ROOT/.git" ]]; then
    echo "Skipping umbrella site refresh because edge-of-epidemiology-site was not found."
    return 0
  fi
  if [[ ! -x "$EDGE_PYTHON_BIN" ]]; then
    echo "Skipping umbrella site refresh because its virtualenv Python was not found."
    return 0
  fi

  cd "$EDGE_REPO_ROOT"
  "$EDGE_PYTHON_BIN" -m src.build_site --site-base-url /
  "$GIT_BIN" -C "$EDGE_REPO_ROOT" add docs

  if "$GIT_BIN" -C "$EDGE_REPO_ROOT" diff --cached --quiet -- docs; then
    echo "No umbrella-site Newsdesk changes to publish."
    cd "$REPO_ROOT"
    return 0
  fi

  local umbrella_commit_message
  umbrella_commit_message="Automated Newsdesk refresh $("$DATE_BIN" '+%Y-%m-%d %H:%M %Z')"
  "$GIT_BIN" -C "$EDGE_REPO_ROOT" commit -m "$umbrella_commit_message"
  GIT_SSH_COMMAND="$PUSH_SSH_COMMAND" "$GIT_BIN" -C "$EDGE_REPO_ROOT" push origin main
  echo "Published umbrella-site Newsdesk refresh."
  cd "$REPO_ROOT"
}

if ! "$MKDIR_BIN" "$LOCK_DIR" 2>/dev/null; then
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
  done <<< "$("$GIT_BIN" -C "$REPO_ROOT" status --porcelain)"
  if (( ${#blocking[@]} > 0 )); then
    printf '%s\n' "${blocking[@]}"
  fi
}

report_blocking_and_exit_if_needed() {
  local -a blocking
  blocking=("${(@f)$(collect_blocking_changes)}")
  blocking=("${(@)blocking:#}")
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

"$GIT_BIN" add docs

if "$GIT_BIN" diff --cached --quiet -- docs; then
  echo "No public-site changes to publish."
  publish_umbrella_site
  exit 0
fi

commit_message="Automated public refresh $("$DATE_BIN" '+%Y-%m-%d %H:%M %Z')"
"$GIT_BIN" commit -m "$commit_message"
GIT_SSH_COMMAND="$PUSH_SSH_COMMAND" "$GIT_BIN" push origin main
echo "Published public site refresh."
publish_umbrella_site
