#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

detect_shell_config() {
    local shell_name
    shell_name="$(basename "${SHELL:-}")"

    case "$shell_name" in
        zsh)
            echo "${ZDOTDIR:-$HOME}/.zshrc"
            ;;
        bash)
            if [ -f "$HOME/.bashrc" ] || [ ! -f "$HOME/.bash_profile" ]; then
                echo "$HOME/.bashrc"
            else
                echo "$HOME/.bash_profile"
            fi
            ;;
        *)
            echo "$HOME/.profile"
            ;;
    esac
}

target_file="${1:-$(detect_shell_config)}"
target_dir="$(dirname "$target_file")"
mkdir -p "$target_dir"
touch "$target_file"

start_marker="# >>> date-website aliases >>>"
end_marker="# <<< date-website aliases <<<"
block="$(mktemp)"
tmp_target="$(mktemp)"

cat > "$block" <<EOF
$start_marker
export DATE_WEBSITE_DIR="$PROJECT_DIR"
source "\$DATE_WEBSITE_DIR/env.sh"
$end_marker
EOF

awk -v start="$start_marker" -v end="$end_marker" '
    $0 == start { skip = 1; next }
    $0 == end { skip = 0; next }
    !skip { print }
' "$target_file" > "$tmp_target"

if [ -s "$tmp_target" ] && [ "$(tail -c 1 "$tmp_target")" != "" ]; then
    printf '\n' >> "$tmp_target"
fi

cat "$block" >> "$tmp_target"
mv "$tmp_target" "$target_file"
rm -f "$block"

echo "Installed date-website aliases in $target_file"
echo "Open a new shell or run: source \"$target_file\""
