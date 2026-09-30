#!/bin/bash
# Generate GitHub release notes for squash-merged pull requests between
# two release tags.
#
# Requires a checkout with the full tag history (actions/checkout with
# fetch-depth: 0), the gh CLI authenticated for the repository, and jq.
#
# Each merged PR lands on main as one commit whose subject is the PR
# title at merge time. A PR is categorized by its release-category labels
# when it carries them (feature/enhancement -> Added, bug/fix -> Fixed,
# documentation/docs -> Documentation, dependencies -> Dependencies,
# chore/refactor -> Maintenance, mirroring the old label-based notes);
# otherwise the conventional-commit prefix of the merge subject decides
# the section (feat, fix, docs, dependency scopes, maintenance types), so
# unlabeled PRs still land in the right place. PRs labeled
# "ignore-for-release" are skipped. Each commit is matched to its pull
# request through the GitHub API for the number, author, and labels; the
# PR title itself is not used, so titles edited after the merge do not
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
    REMOTE="$(git remote get-url origin)"
    REMOTE="${REMOTE#*github.com}"
    REMOTE="${REMOTE#[:/]}"
    REPO="${REMOTE%.git}"
fi
if [[ ! "${REPO}" =~ ^[^/]+/[^/]+$ ]]; then
    echo "error: could not determine owner/repo (got '${REPO}')" >&2
    exit 1
fi

if [ "${LAST_TAG}" = "none" ]; then
    mapfile -t COMMITS < <(git log --first-parent --format='%H' "${NEXT_REF}")
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

    if ! PR_JSON="$(gh api "repos/${REPO}/commits/${SHA}/pulls")"; then
        echo "error: could not look up the pull request for commit ${SHA} (${SUBJECT})" >&2
        exit 1
    fi
    COUNT="$(jq -r 'if type == "array" then length else 0 end' <<<"${PR_JSON}")"
    if [ "${COUNT}" -gt 0 ]; then
        NUMBER="$(jq -r '.[0].number' <<<"${PR_JSON}")"
        AUTHOR="$(jq -r '.[0].user.login // empty' <<<"${PR_JSON}")"
        LABELS="$(jq -r '[.[0].labels[].name] | join(",")' <<<"${PR_JSON}")"
    fi

    if [[ ",${LABELS}," == *",ignore-for-release,"* ]]; then
        continue
    fi

    SECTION=""
    if [ -n "${LABELS}" ]; then
        IFS=',' read -r -a PR_LABELS <<< "${LABELS}"
        for PR_LABEL in "${PR_LABELS[@]}"; do
            case "${PR_LABEL}" in
                feature|enhancement) SECTION="added" ;;
                bug|fix) SECTION="fixed" ;;
                documentation|docs) SECTION="documentation" ;;
                dependencies) SECTION="dependencies" ;;
                chore|refactor|maintenance) SECTION="maintenance" ;;
            esac
            if [ -n "${SECTION}" ]; then
                break
            fi
        done
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

    if [ -z "${SECTION}" ]; then
        TYPE=""
        SCOPE=""
        if [[ "${TITLE}" =~ ^([A-Za-z][A-Za-z0-9-]*)(\(([A-Za-z0-9_.-]+)\))?(!)?:[[:space:]]*(.*)$ ]]; then
            TYPE="${BASH_REMATCH[1],,}"
            SCOPE="${BASH_REMATCH[3],,}"
        fi

        if [ "${SCOPE}" = "deps" ] || [ "${SCOPE}" = "deps-dev" ] || [ "${TYPE}" = "deps" ]; then
            SECTION="dependencies"
        elif [ "${TYPE}" = "feat" ] || [ "${TYPE}" = "feature" ]; then
            SECTION="added"
        elif [ "${TYPE}" = "fix" ]; then
            SECTION="fixed"
        elif [ "${TYPE}" = "docs" ]; then
            SECTION="documentation"
        elif [[ "${TYPE}" =~ ^(build|chart|chore|ci|devx|docker|k8s|perf|refactor|revert|security|style|test)$ ]]; then
            SECTION="maintenance"
        else
            SECTION="other"
        fi
    fi

    case "${SECTION}" in
        added) ADDED+=("${ITEM}") ;;
        fixed) FIXED+=("${ITEM}") ;;
        documentation) DOCUMENTATION+=("${ITEM}") ;;
        dependencies) DEPENDENCIES+=("${ITEM}") ;;
        maintenance) MAINTENANCE+=("${ITEM}") ;;
        *) OTHER+=("${ITEM}") ;;
    esac
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
