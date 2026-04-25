#!/usr/bin/env bash
set -e

SKILL_REPO="https://raw.githubusercontent.com/liaocaoxuezhe/get-web-design/main"
SKILL_NAME="get-web-design"

# ── 检测目标平台 ──────────────────────────────
detect_target() {
  if [[ "$1" != "" ]]; then echo "$1"; return; fi
  if command -v claude &>/dev/null; then echo "claude-code"; return; fi
  if [[ -d "$HOME/.cursor" ]]; then echo "cursor"; return; fi
  if command -v codex &>/dev/null; then echo "codex"; return; fi
  if command -v gemini &>/dev/null; then echo "gemini-cli"; return; fi
  echo "unknown"
}

TARGET=$(detect_target "${1:-}")

# ── 下载核心文件 ──────────────────────────────
TMP=$(mktemp -d)
FILES=(
  SKILL.md
  skill.yaml
  assets/core_principles.md
  assets/design_thinking.md
  assets/system_prompt_en.txt
  assets/system_prompt_zh.txt
  assets/collect_design_data.js
  scripts/generate_design_md.py
  scripts/css_evidence.py
  references/setup.md
  references/workflow.md
  references/chrome_devtools_recipes.md
)

for f in "${FILES[@]}"; do
  mkdir -p "$TMP/$(dirname "$f")"
  curl -fsSL "$SKILL_REPO/$f" -o "$TMP/$f"
done

# ── 按平台安装 ────────────────────────────────
case "$TARGET" in
  claude-code)
    DEST="$HOME/.claude/skills/$SKILL_NAME"
    mkdir -p "$DEST"
    cp -r "$TMP/"* "$DEST/"
    # 注入 CLAUDE.md
    CLAUDE_MD="$HOME/.claude/CLAUDE.md"
    if [[ -f "$CLAUDE_MD" ]]; then
      echo -e "\n## Skill: $SKILL_NAME\n@$DEST/SKILL.md" >> "$CLAUDE_MD"
    fi
    echo "✓ Installed to Claude Code: $DEST"
    echo "  Skill context files are available in agent conversations."
    ;;

  cursor)
    DEST="$HOME/.cursor/skills/$SKILL_NAME"
    mkdir -p "$DEST"
    cp -r "$TMP/"* "$DEST/"
    # 注入 .cursorrules
    RULES_DIR="$HOME/.cursor/rules"
    mkdir -p "$RULES_DIR"
    RULES="$RULES_DIR/${SKILL_NAME}.mdc"
    cp "$DEST/SKILL.md" "$RULES"
    echo "✓ Installed to Cursor: $RULES"
    ;;

  codex)
    DEST="$HOME/.codex/skills/$SKILL_NAME"
    mkdir -p "$DEST"
    cp -r "$TMP/"* "$DEST/"
    echo "✓ Installed to Codex: $DEST"
    echo "  Add to your AGENTS.md: @$DEST/SKILL.md"
    ;;

  gemini-cli)
    DEST="$HOME/.gemini/skills/$SKILL_NAME"
    mkdir -p "$DEST"
    cp -r "$TMP/"* "$DEST/"
    # GEMINI.md 注入
    GEMINI_MD="$HOME/.gemini/GEMINI.md"
    if [[ -f "$GEMINI_MD" ]]; then
      echo -e "\n## Skill: $SKILL_NAME\n@$DEST/SKILL.md" >> "$GEMINI_MD"
    fi
    echo "✓ Installed to Gemini CLI: $DEST"
    ;;

  *)
    echo "⚠ Could not detect target AI agent."
    echo "  Files downloaded to: $TMP"
    echo "  Manually copy SKILL.md into your agent's context."
    echo ""
    echo "  Supported targets: claude-code, cursor, codex, gemini-cli"
    echo "  Try: bash install.sh <target>"
    exit 1
    ;;
esac

rm -rf "$TMP"
echo ""
echo "🎉 $SKILL_NAME installed successfully!"
