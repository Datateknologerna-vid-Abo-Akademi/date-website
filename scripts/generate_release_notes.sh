#!/bin/bash
# Generate GitHub release notes from the conventional-commit titles of
# squash-merged pull requests between two release tags.
#
# Requires a checkout with the full tag history (actions/checkout with
# fetch-depth: 0), the gh CLI authenticated for the repository, and jq.
#
# Every squash merge lands on main as one commit whose subject is the PR
# title at merge time. That subject drives the release notes: its
# conventional-commit prefix (feat, fix, docs, dependency scopes,
# maintenance types) decides the section, mirroring the previous
# label-based release notes, so PRs do not need category labels. PRs
# labeled "ignore-for-release" are skipped. Each commit is matched to its
# pull request through the GitHub API for the number, author, and labels;
# the PR title itself is not used, so titles edited after the merge do not
# rewrite the release history. Commits that cannot be matched to a pull
# request (for example direct pushes) fall back to their commit subject.
#
# Usage: scripts/generate_release_notes.sh <last-tag|none> [<next-ref>]
#
#   <last-tag>  previous release tag, or "none" for the full history
#   <next-ref>  git ref to release (tag name or commit); defaults to HEAD
#
# Prints the release notes markdown to stdout. Run from anywhere inside
# the repository.

set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${SCRIPT_DIR}/.."

LAST_TAG="${1:?usage: generate_release_notes.sh <last-tag|none> [<next-ref>]}"
NEXT_REF="${2:-HEAD}"

REPO="${GITHUB_REPOSITORY:-}"
if [ -z "${REPO}" ]; then
    REPO="$(git remote get-url origin | sed -E 's#.*github\.com[:/]([^/:]+/[^/.]+)(\.git)?$#\1#')"
fi

if [ "${LAST_TAG}" = "none" ]; then
    mapfile -t COMMITS < <(git log --first-parent --format='%H')
else
    mapfile -t COMMITS < <(git log --first-parent --format='%H' "${LAST_TAG}..${NEXT_REF}")
fi

ADDED=()
FIXED=()
DOCUMENTATION=()
DEPENDENCIES=()
MAINTENANCE=()
OTHER=()

for SHA in "${COMMITS[@]}"; do
    [ -n "${SHA}" ] || continue

    SUBJECT="$(git log -1 --format='%s' "${SHA}")"

    NUMBER=""
    AUTHOR=""
    LABELS=""

    PR_JSON="$(gh api "repos/${REPO}/commits/${SHA}/pulls" 2>/dev/null || true)"
    if [ -n "${PR_JSON}" ]; then
        COUNT="$(jq -r 'if type == "array" then length else 0 end' <<<"${PR_JSON}")"
        if [ "${COUNT}" -gt 0 ]; then
            NUMBER="$(jq -r '.[0].number' <<<"${PR_JSON}")"
            AUTHOR="$(jq -r '.[0].user.login // empty' <<<"${PR_JSON}")"
            LABELS="$(jq -r '[.[0].labels[].name] | join(",")' <<<"${PR_JSON}")"
        fi
    fi

    if [[ ",${LABELS}," == *",ignore-for-release,"* ]]; then
        continue
    fi

    TITLE="${SUBJECT}"
    if [ -n "${NUMBER}" ]; then
        TITLE="$(sed -E 's/[[:space:]]+\(#[0-9]+\)$//' <<<"${SUBJECT}")"
    fi

    if [ -n "${NUMBER}" ]; then
        if [ -n "${AUTHOR}" ]; then
            ITEM="* ${TITLE} by @${AUTHOR} in https://github.com/${REPO}/pull/${NUMBER}"
        else
            ITEM="* ${TITLE} in https://github.com/${REPO}/pull/${NUMBER}"
        fi
    else
        ITEM="* ${TITLE}"
    fi

    TYPE=""
    SCOPE=""
    if [[ "${TITLE}" =~ ^([A-Za-z][A-Za-z0-9-]*)(\(([A-Za-z0-9_.-]+)\))?(!)?:[[:space:]]*(.*)$ ]]; then
        TYPE="${BASH_REMATCH[1],,}"
        SCOPE="${BASH_REMATCH[3],,}"
    fi

    if [ "${SCOPE}" = "deps" ] || [ "${SCOPE}" = "deps-dev" ] || [ "${TYPE}" = "deps" ]; then
        DEPENDENCIES+=("${ITEM}")
    elif [ "${TYPE}" = "feat" ] || [ "${TYPE}" = "feature" ]; then
        ADDED+=("${ITEM}")
    elif [ "${TYPE}" = "fix" ]; then
        FIXED+=("${ITEM}")
    elif [ "${TYPE}" = "docs" ]; then
        DOCUMENTATION+=("${ITEM}")
    elif [[ "${TYPE}" =~ ^(build|chart|chore|ci|devx|docker|k8s|perf|refactor|revert|security|style|test)$ ]]; then
        MAINTENANCE+=("${ITEM}")
    else
        OTHER+=("${ITEM}")
    fi
done

section() {
    local heading="$1"
    shift
    if [ "$#" -gt 0 ]; then
        echo "### ${heading}"
        printf '%s\n' "$@"
        echo ""
    fi
}

echo "## What's Changed"
echo ""
section "Added" "${ADDED[@]}"
section "Fixed" "${FIXED[@]}"
section "Documentation" "${DOCUMENTATION[@]}"
section "Dependencies" "${DEPENDENCIES[@]}"
section "Maintenance" "${MAINTENANCE[@]}"
section "Other Changes" "${OTHER[@]}"

if [ "${LAST_TAG}" != "none" ]; then
    echo "**Full Changelog**: https://github.com/${REPO}/compare/${LAST_TAG}...${NEXT_REF}"
fi
