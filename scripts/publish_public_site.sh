#!/bin/zsh

set -euo pipefail

REPO_ROOT="${0:A:h:h}"
LOCAL_REPO_ROOT="${EPI_DOSSIER_LOCAL_REPO_ROOT:-$REPO_ROOT}"
EDGE_REPO_ROOT="${EPI_DOSSIER_EDGE_REPO_ROOT:-$LOCAL_REPO_ROOT/../edge-of-epidemiology-site}"
DEFAULT_TEMP_ROOT="/tmp"
if [[ -d "/private/tmp" ]]; then
  DEFAULT_TEMP_ROOT="/private/tmp"
fi
PUBLIC_PUBLISH_TEMP_ROOT="${EPI_DOSSIER_PUBLIC_PUBLISH_TEMP_ROOT:-$DEFAULT_TEMP_ROOT}"
LOCK_DIR="${EPI_DOSSIER_PUBLIC_PUBLISH_LOCK_DIR:-$PUBLIC_PUBLISH_TEMP_ROOT/epi-dossier-public-publish.lock}"
PYTHON_BIN="${EPI_DOSSIER_PYTHON_BIN:-$REPO_ROOT/.venv/bin/python}"
EDGE_PYTHON_BIN="$EDGE_REPO_ROOT/.venv/bin/python"
SSH_KEY="$HOME/.ssh/id_ed25519_epi_dossier"
GIT_BIN="/usr/bin/git"
SSH_BIN="/usr/bin/ssh"
DATE_BIN="/bin/date"
MKDIR_BIN="/bin/mkdir"
RMDIR_BIN="/bin/rmdir"
MKTEMP_BIN="/usr/bin/mktemp"
RM_BIN="/bin/rm"
RSYNC_BIN="/usr/bin/rsync"
PUSH_SSH_COMMAND="${EPI_DOSSIER_GIT_SSH_COMMAND:-}"
NEWS_DESK_ROOT_EXPORTS=(archive.json atlas.json health.json latest.json manifest.json)
if [[ -z "$PUSH_SSH_COMMAND" && -f "$SSH_KEY" ]]; then
  PUSH_SSH_COMMAND="$SSH_BIN -o StrictHostKeyChecking=accept-new -i $SSH_KEY"
fi

cleanup() {
  "$RMDIR_BIN" "$LOCK_DIR" 2>/dev/null || true
}

cleanup_worktree() {
  local repo_root="$1"
  local temp_worktree="$2"
  "$GIT_BIN" -C "$repo_root" worktree remove --force "$temp_worktree" >/dev/null 2>&1 || true
  "$RM_BIN" -rf "$temp_worktree" >/dev/null 2>&1 || true
}

git_with_publish_auth() {
  if [[ -n "$PUSH_SSH_COMMAND" ]]; then
    GIT_SSH_COMMAND="$PUSH_SSH_COMMAND" "$GIT_BIN" "$@"
  else
    "$GIT_BIN" "$@"
  fi
}

skip_umbrella_publish() {
  [[ "${EPI_DOSSIER_SKIP_UMBRELLA_PUBLISH:-}" == "1" || "${EPI_DOSSIER_SKIP_UMBRELLA_PUBLISH:-}" == "true" ]]
}

newsdesk_mirror_paths() {
  local -a paths
  local export_name
  paths=(docs/newsdesk)
  for export_name in "${NEWS_DESK_ROOT_EXPORTS[@]}"; do
    paths+=("docs/app_exports/$export_name")
  done
  printf '%s\n' "${paths[@]}"
}

copy_newsdesk_mirror_files() {
  local source_root="$1"
  local target_root="$2"
  local export_name

  "$MKDIR_BIN" -p "$target_root/docs/newsdesk" "$target_root/docs/app_exports"
  "$RSYNC_BIN" -a --delete "$source_root/docs/" "$target_root/docs/newsdesk/"
  for export_name in "${NEWS_DESK_ROOT_EXPORTS[@]}"; do
    if [[ -f "$source_root/docs/app_exports/$export_name" ]]; then
      "$RSYNC_BIN" -a "$source_root/docs/app_exports/$export_name" "$target_root/docs/app_exports/$export_name"
    fi
  done
}

stage_newsdesk_mirror_files() {
  local repo_root="$1"
  local export_name

  "$GIT_BIN" -C "$repo_root" add docs/newsdesk
  for export_name in "${NEWS_DESK_ROOT_EXPORTS[@]}"; do
    if [[ -f "$repo_root/docs/app_exports/$export_name" ]]; then
      "$GIT_BIN" -C "$repo_root" add "docs/app_exports/$export_name"
    fi
  done
}

newsdesk_mirror_staged_diff_is_empty() {
  local repo_root="$1"
  local -a paths
  paths=("${(@f)$(newsdesk_mirror_paths)}")
  "$GIT_BIN" -C "$repo_root" diff --cached --quiet -- "${paths[@]}"
}

repo_has_local_changes() {
  local repo_root="$1"
  [[ -n "$("$GIT_BIN" -C "$repo_root" status --porcelain --untracked-files=no)" ]]
}

push_from_clean_temp_worktree() {
  local repo_root="$1"
  local remote_name="$2"
  local branch_name="$3"
  local success_message="$4"
  local remote_ref="${remote_name}/${branch_name}"
  local temp_worktree current_ref commit_subject

  temp_worktree="$("$MKTEMP_BIN" -d "$PUBLIC_PUBLISH_TEMP_ROOT/epi-dossier-publish-rebase.XXXXXX")"
  current_ref="$("$GIT_BIN" -C "$repo_root" rev-parse HEAD)"
  commit_subject="$("$GIT_BIN" -C "$repo_root" log -1 --format=%s HEAD)"

  "$GIT_BIN" -C "$repo_root" worktree add --detach "$temp_worktree" "$current_ref" >/dev/null
  if ! git_with_publish_auth -C "$temp_worktree" fetch "$remote_name" "$branch_name"; then
    cleanup_worktree "$repo_root" "$temp_worktree"
    return 1
  fi
  if ! "$GIT_BIN" -C "$temp_worktree" reset --hard "$remote_ref" >/dev/null; then
    cleanup_worktree "$repo_root" "$temp_worktree"
    return 1
  fi
  # Generated site trees conflict frequently. Do not rebase them line-by-line;
  # overlay this run's generated snapshot onto the latest remote branch.
  if ! "$RSYNC_BIN" -a --delete "$repo_root/docs/" "$temp_worktree/docs/"; then
    cleanup_worktree "$repo_root" "$temp_worktree"
    return 1
  fi
  if [[ -f "$repo_root/content/posts.yml" ]]; then
    "$MKDIR_BIN" -p "$temp_worktree/content"
    "$RSYNC_BIN" -a "$repo_root/content/posts.yml" "$temp_worktree/content/posts.yml"
  fi
  "$GIT_BIN" -C "$temp_worktree" add docs
  if [[ -f "$temp_worktree/content/posts.yml" ]]; then
    "$GIT_BIN" -C "$temp_worktree" add content/posts.yml
  fi
  if "$GIT_BIN" -C "$temp_worktree" diff --cached --quiet -- docs content/posts.yml 2>/dev/null; then
    cleanup_worktree "$repo_root" "$temp_worktree"
    echo "$success_message"
    return 0
  fi
  if ! "$GIT_BIN" -C "$temp_worktree" commit -m "$commit_subject" >/dev/null; then
    cleanup_worktree "$repo_root" "$temp_worktree"
    return 1
  fi
  if ! git_with_publish_auth -C "$temp_worktree" push "$remote_name" HEAD:"$branch_name"; then
    cleanup_worktree "$repo_root" "$temp_worktree"
    return 1
  fi

  cleanup_worktree "$repo_root" "$temp_worktree"
  echo "$success_message"
}

fetch_remote_branch() {
  local repo_root="$1"
  local remote_name="$2"
  local branch_name="$3"
  git_with_publish_auth -C "$repo_root" fetch "$remote_name" "$branch_name" >/dev/null
}

local_branch_is_ahead() {
  local repo_root="$1"
  local remote_name="$2"
  local branch_name="$3"
  local remote_ref="${remote_name}/${branch_name}"
  [[ -n "$("$GIT_BIN" -C "$repo_root" rev-list "${remote_ref}..HEAD")" ]]
}

ahead_commits_only_touch_generated_site() {
  local repo_root="$1"
  local remote_name="$2"
  local branch_name="$3"
  local remote_ref="${remote_name}/${branch_name}"
  local changed_paths
  changed_paths="$("$GIT_BIN" -C "$repo_root" diff --name-only "${remote_ref}..HEAD")"
  [[ -n "$changed_paths" ]] || return 1
  while IFS= read -r path; do
    [[ -z "$path" ]] && continue
    [[ "$path" == docs/* || "$path" == "content/posts.yml" ]] || return 1
  done <<< "$changed_paths"
}

push_commit_with_generated_docs_rebase() {
  local repo_root="$1"
  local remote_name="$2"
  local branch_name="$3"
  local success_message="$4"
  local remote_ref="${remote_name}/${branch_name}"

  if git_with_publish_auth -C "$repo_root" push "$remote_name" HEAD:"$branch_name"; then
    echo "$success_message"
    return 0
  fi

  echo "Push rejected for $repo_root; overlaying generated docs onto latest $remote_ref in a temporary worktree."
  push_from_clean_temp_worktree "$repo_root" "$remote_name" "$branch_name" "$success_message"
}

push_newsdesk_mirror_from_clean_temp_worktree() {
  local repo_root="$1"
  local remote_name="$2"
  local branch_name="$3"
  local success_message="$4"
  local remote_ref="${remote_name}/${branch_name}"
  local temp_worktree current_ref commit_subject

  temp_worktree="$("$MKTEMP_BIN" -d "$PUBLIC_PUBLISH_TEMP_ROOT/newsdesk-mirror-rebase.XXXXXX")"
  current_ref="$("$GIT_BIN" -C "$repo_root" rev-parse HEAD)"
  commit_subject="$("$GIT_BIN" -C "$repo_root" log -1 --format=%s HEAD)"

  "$GIT_BIN" -C "$repo_root" worktree add --detach "$temp_worktree" "$current_ref" >/dev/null
  if ! git_with_publish_auth -C "$temp_worktree" fetch "$remote_name" "$branch_name"; then
    cleanup_worktree "$repo_root" "$temp_worktree"
    return 1
  fi
  if ! "$GIT_BIN" -C "$temp_worktree" reset --hard "$remote_ref" >/dev/null; then
    cleanup_worktree "$repo_root" "$temp_worktree"
    return 1
  fi

  copy_newsdesk_mirror_files "$repo_root" "$temp_worktree"
  stage_newsdesk_mirror_files "$temp_worktree"
  if newsdesk_mirror_staged_diff_is_empty "$temp_worktree"; then
    cleanup_worktree "$repo_root" "$temp_worktree"
    echo "$success_message"
    return 0
  fi
  if ! "$GIT_BIN" -C "$temp_worktree" commit -m "$commit_subject" >/dev/null; then
    cleanup_worktree "$repo_root" "$temp_worktree"
    return 1
  fi
  if ! git_with_publish_auth -C "$temp_worktree" push "$remote_name" HEAD:"$branch_name"; then
    cleanup_worktree "$repo_root" "$temp_worktree"
    return 1
  fi

  cleanup_worktree "$repo_root" "$temp_worktree"
  echo "$success_message"
}

push_newsdesk_mirror_commit() {
  local repo_root="$1"
  local remote_name="$2"
  local branch_name="$3"
  local success_message="$4"
  local remote_ref="${remote_name}/${branch_name}"

  if git_with_publish_auth -C "$repo_root" push "$remote_name" HEAD:"$branch_name"; then
    echo "$success_message"
    return 0
  fi

  echo "Push rejected for $repo_root; overlaying Newsdesk mirror onto latest $remote_ref in a temporary worktree."
  push_newsdesk_mirror_from_clean_temp_worktree "$repo_root" "$remote_name" "$branch_name" "$success_message"
}

publish_umbrella_newsdesk_mirror() {
  if [[ ! -d "$EDGE_REPO_ROOT/.git" ]]; then
    echo "No local umbrella-site checkout found; dteichrow.github.io owns the scheduled and dispatched Newsdesk import."
    return 0
  fi

  local temp_worktree mirror_commit_message
  fetch_remote_branch "$EDGE_REPO_ROOT" origin main
  temp_worktree="$("$MKTEMP_BIN" -d "$PUBLIC_PUBLISH_TEMP_ROOT/newsdesk-mirror.XXXXXX")"
  "$GIT_BIN" -C "$EDGE_REPO_ROOT" worktree add --detach "$temp_worktree" origin/main >/dev/null

  copy_newsdesk_mirror_files "$REPO_ROOT" "$temp_worktree"
  stage_newsdesk_mirror_files "$temp_worktree"
  if newsdesk_mirror_staged_diff_is_empty "$temp_worktree"; then
    cleanup_worktree "$EDGE_REPO_ROOT" "$temp_worktree"
    echo "No umbrella-site Newsdesk mirror changes to publish."
    return 0
  fi

  mirror_commit_message="Mirror Newsdesk refresh $("$DATE_BIN" '+%Y-%m-%d %H:%M %Z')"
  "$GIT_BIN" -C "$temp_worktree" commit -m "$mirror_commit_message"
  if ! push_newsdesk_mirror_commit \
    "$temp_worktree" \
    origin \
    main \
    "Published umbrella-site Newsdesk mirror refresh."; then
    cleanup_worktree "$EDGE_REPO_ROOT" "$temp_worktree"
    return 1
  fi
  cleanup_worktree "$EDGE_REPO_ROOT" "$temp_worktree"
}

publish_umbrella_site() {
  if [[ "$REPO_ROOT" != "$LOCAL_REPO_ROOT" && -d "$LOCAL_REPO_ROOT/docs" ]]; then
    "$RSYNC_BIN" -a --delete "$REPO_ROOT/docs/" "$LOCAL_REPO_ROOT/docs/"
  fi

  if [[ ! -d "$EDGE_REPO_ROOT/.git" ]]; then
    echo "Skipping umbrella site refresh because edge-of-epidemiology-site was not found."
    return 0
  fi
  if [[ ! -x "$EDGE_PYTHON_BIN" ]]; then
    echo "Skipping umbrella site refresh because its virtualenv Python was not found."
    return 0
  fi

  cd "$EDGE_REPO_ROOT"
  "$EDGE_PYTHON_BIN" -m src.substack_sync --mode incremental
  "$EDGE_PYTHON_BIN" -m src.build_site --site-base-url /
  "$GIT_BIN" -C "$EDGE_REPO_ROOT" add docs
  "$GIT_BIN" -C "$EDGE_REPO_ROOT" add content/posts.yml
  fetch_remote_branch "$EDGE_REPO_ROOT" origin main

  if "$GIT_BIN" -C "$EDGE_REPO_ROOT" diff --cached --quiet -- docs content/posts.yml; then
    if local_branch_is_ahead "$EDGE_REPO_ROOT" origin main && ahead_commits_only_touch_generated_site "$EDGE_REPO_ROOT" origin main; then
      push_commit_with_generated_docs_rebase \
        "$EDGE_REPO_ROOT" \
        origin \
        main \
        "Published umbrella-site Newsdesk refresh."
      cd "$REPO_ROOT"
      return 0
    fi
    echo "No umbrella-site Newsdesk changes to publish."
    cd "$REPO_ROOT"
    return 0
  fi

  local umbrella_commit_message
  umbrella_commit_message="Automated site refresh $("$DATE_BIN" '+%Y-%m-%d %H:%M %Z')"
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
"$PYTHON_BIN" -m src.outbreak_dashboard_quality

report_blocking_and_exit_if_needed

"$GIT_BIN" add docs

if "$GIT_BIN" diff --cached --quiet -- docs; then
  echo "No public-site changes to publish."
  if skip_umbrella_publish; then
    echo "Skipping full umbrella-site refresh by configuration; publishing Newsdesk mirror only."
    publish_umbrella_newsdesk_mirror
    exit 0
  fi
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
if skip_umbrella_publish; then
  echo "Skipping full umbrella-site refresh by configuration; publishing Newsdesk mirror only."
  publish_umbrella_newsdesk_mirror
  exit 0
fi
publish_umbrella_site
