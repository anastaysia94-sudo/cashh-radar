#!/usr/bin/env bash
# Backup committed Git refs + Git LFS + live Actions artifacts to a configured
# rclone destination. Delete ONLY old, unprotected artifacts AFTER verified backups.
set -Eeuo pipefail
IFS=$'\n\t'
umask 077

say() { printf '%s\n' "$*"; }
fail() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }
summary() {
  say "$*"
  if [[ -n "${GITHUB_STEP_SUMMARY:-}" ]]; then printf '%s\n' "$*" >> "$GITHUB_STEP_SUMMARY"; fi
}
need() { command -v "$1" >/dev/null || fail "Required program missing: $1"; }
for x in git gh rclone jq curl unzip tar sha256sum date; do need "$x"; done
[[ -n "${GITHUB_REPOSITORY:-}" && "$GITHUB_REPOSITORY" == */* ]] || fail 'GITHUB_REPOSITORY must be OWNER/REPO'
[[ -n "${GH_TOKEN:-}" ]] || fail 'GH_TOKEN is required (GITHUB_TOKEN on Actions).'
[[ -n "${DRIVE_DESTINATION:-}" && "$DRIVE_DESTINATION" == *:* ]] || fail 'DRIVE_DESTINATION must be an rclone remote, e.g. gdrive:Backups'
[[ "${MIN_AGE_DAYS:-7}" =~ ^[0-9]+$ ]] || fail 'MIN_AGE_DAYS must be a nonnegative integer'
[[ "${DELETE_AFTER_BACKUP:-false}" == 'true' || "${DELETE_AFTER_BACKUP:-false}" == 'false' ]] || fail 'DELETE_AFTER_BACKUP must be true or false'
[[ "${BACKUP_LFS:-true}" == 'true' || "${BACKUP_LFS:-true}" == 'false' ]] || fail 'BACKUP_LFS must be true or false'
[[ "${BACKUP_LFS:-true}" == 'true' ]] || fail 'This safe profile requires BACKUP_LFS=true'

# Deliberately do not change or delete any tracked/untracked Git source files,
# GitHub releases, caches, workflow runs, secrets, or repository settings.
repo="$GITHUB_REPOSITORY"
base="${DRIVE_DESTINATION%/}/$repo"
min_age_days="${MIN_AGE_DAYS:-7}"
delete="${DELETE_AFTER_BACKUP:-false}"
protected_regex="${PROTECTED_NAMES_REGEX:-(^|[-_])(release|deploy|production|acceptance|evidence)([-_]|$)}"
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
archive="$work/repository-mirror.tar.gz"
refs="$work/refs.txt"

verify_upload() {
  local local_file="$1" remote_file="$2" local_hash remote_hash
  local_hash="$(sha256sum "$local_file" | awk '{print $1}')"
  rclone copyto "$local_file" "$remote_file" --retries 3 --low-level-retries 5
  # Read back every byte via Drive rather than trusting upload success alone.
  remote_hash="$(rclone cat "$remote_file" --retries 3 --low-level-retries 5 | sha256sum | awk '{print $1}')"
  [[ "$local_hash" == "$remote_hash" ]] || fail "Google Drive hash mismatch: $remote_file"
  say "VERIFIED: $remote_file ($local_hash)"
}

summary "### Drive backup — $repo"
summary "Mode: $(if [[ "$delete" == true ]]; then echo 'backup, verify, then delete eligible artifacts'; else echo 'backup + verify ONLY (safe default)'; fi)"

# 1. Mirror clone contains Git history, refs, branches, tags (not GitHub settings).
# Using gh avoids embedding access tokens in the repository URL / tarball.
say 'Mirroring Git repository...'
gh auth setup-git >/dev/null
gh repo clone "$repo" "$work/repository.git" --no-upstream -- --mirror --no-local
[[ -d "$work/repository.git/objects" ]] || fail 'Mirror clone failed'
git -C "$work/repository.git" fsck --full >/dev/null

# Backup actual LFS objects, not just pointer files. Stops safely if unavailable.
if ! git -C "$work/repository.git" lfs version >/dev/null 2>&1; then
  fail 'Git LFS is not installed; refusing to call this a complete Git backup.'
fi
lfs_count="$(git -C "$work/repository.git" lfs ls-files --all --name-only | awk 'END{print NR+0}')"
if (( lfs_count > 0 )); then
  say "Fetching all historical Git LFS objects ($lfs_count paths)..."
  git -C "$work/repository.git" lfs fetch --all origin
fi
# Remove any stored remote auth configuration from the recoverable mirror.
git -C "$work/repository.git" remote set-url origin "https://github.com/$repo.git"
git -C "$work/repository.git" config --local --unset-all credential.helper >/dev/null 2>&1 || true
git -C "$work/repository.git" show-ref > "$refs" || fail 'Git repository has no refs to archive'
# tar includes downloaded LFS files inside bare repository's lfs/objects directory.
tar -czf "$archive" -C "$work" repository.git
tar -tzf "$archive" >/dev/null
verify_upload "$archive" "$base/repository/latest-mirror.tar.gz"
verify_upload "$refs" "$base/repository/latest-refs.txt"
rm -rf "$work/repository.git" "$archive"
summary '- Git mirror, refs and any tracked Git LFS objects: verified on Drive'

# 2. One complete inventory of live artifacts; fail-closed if GitHub API errors.
say 'Getting Actions artifact inventory...'
gh api --paginate "repos/$repo/actions/artifacts?per_page=100" > "$work/pages.json"
jq -s '[ .[] | .artifacts[] | select(.expired != true) ]' "$work/pages.json" > "$work/artifacts.json"
verify_upload "$work/artifacts.json" "$base/artifacts/latest-inventory.json"
artifact_count="$(jq 'length' "$work/artifacts.json")"
summary "- Live Actions artifacts inventoried: $artifact_count"

# 3. Download + verify ALL live artifacts first. Do not delete a single file
# until the whole reachable artifact set has safely reached Google Drive.
# Do not buffer the whole set on runner disk: upload one archive at a time.
: > "$work/delete-candidates.tsv"
now_epoch="$(date -u +%s)"
cutoff_epoch="$((now_epoch - min_age_days * 86400))"
backed=0
while IFS= read -r item; do
  id="$(jq -r '.id' <<<"$item")"
  name="$(jq -r '.name' <<<"$item")"
  created="$(jq -r '.created_at' <<<"$item")"
  [[ "$id" =~ ^[0-9]+$ ]] || fail 'Invalid artifact id in GitHub API response'
  [[ -n "$created" && "$created" != null ]] || fail "Missing date for artifact $id"
  created_epoch="$(date -u -d "$created" +%s)" || fail "Invalid artifact date $id"
  local_zip="$work/artifact-$id.zip"
  local_meta="$work/artifact-$id.json"
  remote_zip="$base/artifacts/$id.zip"
  remote_meta="$base/artifacts/$id.json"

  say "Backing up artifact $id: $name"
  curl --fail --location --silent --show-error --retry 3 --retry-all-errors \
    --proto '=https' --proto-redir '=https' \
    -H "Accept: application/vnd.github+json" \
    -H "Authorization: Bearer $GH_TOKEN" \
    "https://api.github.com/repos/$repo/actions/artifacts/$id/zip" -o "$local_zip"
  [[ -s "$local_zip" ]] || fail "Empty download for artifact $id"
  unzip -tqq "$local_zip" >/dev/null || fail "Invalid zip for artifact $id"
  printf '%s\n' "$item" | jq '.' > "$local_meta"
  verify_upload "$local_zip" "$remote_zip"
  verify_upload "$local_meta" "$remote_meta"
  backed=$((backed + 1))
  rm -f "$local_zip" "$local_meta"

  lower="${name,,}"
  if (( created_epoch <= cutoff_epoch )) && [[ ! "$lower" =~ $protected_regex ]]; then
    printf '%s\t%s\n' "$id" "$name" >> "$work/delete-candidates.tsv"
  fi
done < <(jq -c '.[]' "$work/artifacts.json")
summary "- Downloaded, validated and SHA-256 read-back verified: $backed artifacts"

# 4. Only eligible and already VERIFIED artifacts get deleted, after all
# artifact uploads finish successfully. Default is NOT to delete.
candidates="$(wc -l < "$work/delete-candidates.tsv" | tr -d ' ')"
summary "- Eligible artifacts older than or equal to $min_age_days days, excluding protected names: $candidates"
if [[ "$delete" != true ]]; then
  summary '- GitHub deletion: DISABLED; run again with delete_after_backup=true when ready'
  exit 0
fi

removed=0
while IFS=$'\t' read -r id name; do
  [[ -n "$id" ]] || continue
  [[ "$id" =~ ^[0-9]+$ ]] || fail 'Invalid delete candidate id'
  # Listing can change during a run; skip artifacts already gone (404).
  if gh api -X DELETE "repos/$repo/actions/artifacts/$id" >/dev/null; then
    say "DELETED GitHub artifact: $id ($name), verified Drive copy remains"
    removed=$((removed + 1))
  else
    fail "Deletion failed for artifact $id; remaining artifacts untouched"
  fi
done < "$work/delete-candidates.tsv"
summary "- Deleted from GitHub after complete verified backup: $removed artifacts"
summary '- Git source, releases, Actions caches, runs, and repository settings: NOT deleted'