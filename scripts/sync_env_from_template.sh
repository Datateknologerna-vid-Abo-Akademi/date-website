#!/usr/bin/env bash
set -euo pipefail

usage() {
    cat <<'EOF'
Usage: scripts/sync_env_from_template.sh [--dry-run] [--no-backup] [template-env-file] [target-env-file]

Rebuild an env file using the template file's comments/order while preserving
values already present in the target env file. Keys that exist only in the
target file are appended at the bottom under a local-only section.
Before writing, the current target file is copied to
<target-directory>/.env-backups/<target-basename>.bak.<timestamp> unless
--no-backup is passed.

Defaults:
  template-env-file  .env.prod.example
  target-env-file    .env
EOF
}

dry_run=false
backup=true

while [[ "${1:-}" == -* ]]; do
    case "$1" in
        --dry-run|-n)
            dry_run=true
            shift
            ;;
        --no-backup)
            backup=false
            shift
            ;;
        --help|-h)
            usage
            exit 0
            ;;
        --)
            shift
            break
            ;;
        *)
            echo "Unknown option: $1" >&2
            usage >&2
            exit 1
            ;;
    esac
done

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
    usage
    exit 0
fi

template_file="${1:-.env.prod.example}"
target_file="${2:-.env}"

if [[ "$#" -gt 2 ]]; then
    usage >&2
    exit 1
fi

if [[ ! -f "$template_file" ]]; then
    echo "Template file not found: $template_file" >&2
    exit 1
fi

if [[ ! -f "$target_file" ]]; then
    echo "Target file not found: $target_file" >&2
    exit 1
fi

tmp_file="$(mktemp)"
cleanup() {
    rm -f "$tmp_file"
}
trap cleanup EXIT

declare -A target_values=()
declare -A target_lines=()
declare -A target_seen=()
declare -a target_order=()
declare -A template_seen=()

parse_assignment() {
    local line="$1"
    local trimmed

    trimmed="${line#"${line%%[![:space:]]*}"}"

    [[ -z "$trimmed" ]] && return 1
    [[ "$trimmed" == \#* ]] && return 1

    if [[ "$trimmed" == export[[:space:]]* ]]; then
        trimmed="${trimmed#export}"
        trimmed="${trimmed#"${trimmed%%[![:space:]]*}"}"
    fi

    [[ "$trimmed" =~ ^([A-Za-z_][A-Za-z0-9_]*)=(.*)$ ]]
}

while IFS= read -r line || [[ -n "$line" ]]; do
    if parse_assignment "$line"; then
        key="${BASH_REMATCH[1]}"
        value="${BASH_REMATCH[2]}"

        if [[ -z "${target_seen[$key]+x}" ]]; then
            target_order+=("$key")
        fi

        target_seen["$key"]=1
        target_values["$key"]="$value"
        target_lines["$key"]="$key=$value"
    fi
done < "$target_file"

while IFS= read -r line || [[ -n "$line" ]]; do
    if parse_assignment "$line"; then
        key="${BASH_REMATCH[1]}"
        template_seen["$key"]=1

        if [[ -n "${target_values[$key]+x}" ]]; then
            printf '%s=%s\n' "$key" "${target_values[$key]}" >> "$tmp_file"
            continue
        fi
    fi

    printf '%s\n' "$line" >> "$tmp_file"
done < "$template_file"

extra_count=0
for key in "${target_order[@]}"; do
    if [[ -z "${template_seen[$key]+x}" ]]; then
        if [[ "$extra_count" -eq 0 ]]; then
            {
                printf '\n'
                printf '# [Local-only values preserved from previous env]\n'
                printf '# These keys were not present in %s when this file was synced.\n' "$template_file"
                printf '\n'
            } >> "$tmp_file"
        fi

        printf '%s\n' "${target_lines[$key]}" >> "$tmp_file"
        extra_count=$((extra_count + 1))
    fi
done

if [[ "$dry_run" == true ]]; then
    cat "$tmp_file"
else
    if [[ ! -s "$tmp_file" ]]; then
        echo "Refusing to replace $target_file with an empty generated file" >&2
        exit 1
    fi

    if chmod --reference="$target_file" "$tmp_file" 2>/dev/null; then
        :
    else
        chmod 600 "$tmp_file"
    fi

    backup_file=""
    if [[ "$backup" == true ]]; then
        backup_dir="$(dirname "$target_file")/.env-backups"
        backup_file="$backup_dir/$(basename "$target_file").bak.$(date +%Y%m%d%H%M%S)"
        mkdir -p "$backup_dir"
        cp -p "$target_file" "$backup_file"
    fi

    mv "$tmp_file" "$target_file"
    trap - EXIT
    echo "Synced $target_file from $template_file"
    if [[ -n "$backup_file" ]]; then
        echo "Backup written to $backup_file"
    fi
    if [[ "$extra_count" -gt 0 ]]; then
        echo "Preserved $extra_count target-only key(s) at the bottom"
    fi
fi
