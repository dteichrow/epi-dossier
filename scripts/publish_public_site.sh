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

push_commit_with_generated_docs_rebase() {
  local repo_root="$1"
  local remote_name="$2"
  local branch_name="$3"
  local success_message="$4"
  local remote_ref="${remote_name}/${branch_name}"

  if GIT_SSH_COMMAND="$PUSH_SSH_COMMAND" "$GIT_BIN" -C "$repo_root" push "$remote_name" "$branch_name"; then
    echo "$success_message"
    return 0
  fi

  echo "Push rejected for $repo_root; fetching and rebasing generated docs onto $remote_ref."
  GIT_SSH_COMMAND="$PUSH_SSH_COMMAND" "$GIT_BIN" -C "$repo_root" fetch "$remote_name" "$branch_name"
  "$GIT_BIN" -C "$repo_root" rebase "$remote_ref"
  GIT_SSH_COMMAND="$PUSH_SSH_COMMAND" "$GIT_BIN" -C "$repo_root" push "$remote_name" "$branch_name"
  echo "$success_message"
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
  push_commit_with_generated_docs_rebase \
    "$EDGE_REPO_ROOT" \
    origin \
    main \
    "Published umbrella-site Newsdesk refresh."
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
push_commit_with_generated_docs_rebase \
  "$REPO_ROOT" \
  origin \
  main \
  "Published public site refresh."
publish_umbrella_site
