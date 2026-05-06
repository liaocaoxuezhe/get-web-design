# get-web-design

将任意线上网站的设计风格提取为一份结构化 `DESIGN.md`。本 skill 是 design-extractor Chrome 扩展的命令行 / AI Agent 移植版。

## 功能

- 从任意 URL 生成可用于 AI 编程提示词的 `DESIGN.md`
- 提取站点的设计 token（颜色 / 字体 / 间距 / 圆角 / 阴影 / 动效）
- 使用多模态 LLM 分析站点的视觉风格、组件规范与整体氛围
- 识别网页中特别值得复刻的主要元素，并输出 few-shot 模块规范
- 通过 chrome-devtools MCP 采集 DOM、Computed CSS 与 3 视口截图
- 输出包含 frontmatter + design thinking + AI 风格分析 + CSS 证据 + negative constraints 的完整文档

## 触发场景

- "生成 https://stripe.com 的 DESIGN.md"
- "分析 linear.app 的设计风格并保存"
- "extract design from <url>"

## 前置依赖

1. **chrome-devtools MCP** —— 通过 `/mcp` 验证是否有 `chrome-devtools` 服务
2. **多模态 LLM 配置**（环境变量）：
   - `WEB_DESIGN_API_KEY`
   - `WEB_DESIGN_BASE_URL`
   - `WEB_DESIGN_MODEL`（必须支持 vision）

详见 `references/setup.md`。

## 安装

### 一行命令（自动检测你的 AI 工具）

```bash
curl -fsSL https://raw.githubusercontent.com/liaocaoxuezhe/get-web-design/main/install.sh | bash
```

### 通过 npx skills 安装（推荐）

如果你已经安装了 [`skill.sh`](https://skill.sh) 生态，可以直接用以下命令安装：

```bash
npx skills add liaocaoxuezhe/get-web-design
```

安装完成后，skill 会自动注入到当前 AI Agent 的 context 中，无需手动复制文件。

### 指定平台安装

```bash
# Claude Code
curl -fsSL https://raw.githubusercontent.com/liaocaoxuezhe/get-web-design/main/install.sh | bash -s -- claude-code

# Cursor
curl -fsSL https://raw.githubusercontent.com/liaocaoxuezhe/get-web-design/main/install.sh | bash -s -- cursor

# OpenAI Codex CLI
curl -fsSL https://raw.githubusercontent.com/liaocaoxuezhe/get-web-design/main/install.sh | bash -s -- codex

# Gemini CLI
curl -fsSL https://raw.githubusercontent.com/liaocaoxuezhe/get-web-design/main/install.sh | bash -s -- gemini-cli
```

### 手动安装

将 `SKILL.md` 复制到你的项目根目录或 agent context 目录即可。

## 工作流

```
URL → [chrome-devtools] 3 截图 + collected.json
    → [Python] CSS 压缩 + LLM 调用 + 拼装
    → output/<hostname>/design.md
      output/<hostname>/shot1.jpg
      output/<hostname>/shot2.jpg
      output/<hostname>/shot3.jpg
```

每次抽取的所有产物都收敛到一个 `output/<hostname>/` 文件夹，便于归档和复用。

详细步骤见 `references/workflow.md`。chrome-devtools MCP 调用配方见 `references/chrome_devtools_recipes.md`。

## 文件结构

| 路径 | 用途 |
|------|------|
| `SKILL.md` | Skill 核心定义与使用指南 |
| `assets/collect_design_data.js` | 注入目标页面的 DOM + CSS 采集脚本 |
| `assets/system_prompt_en.txt` / `system_prompt_zh.txt` | 多模态 LLM system prompt |
| `assets/design_thinking.md` / `core_principles.md` | DESIGN.md 固定头尾段落 |
| `scripts/generate_design_md.py` | 主入口 CLI：调 LLM 与最终拼装 |
| `scripts/css_evidence.py` | CSS computed-style → 设计 token 压缩 |
| `references/setup.md` | chrome-devtools MCP + LLM 凭据配置 |
| `references/workflow.md` | 完整数据流详解 |
| `references/chrome_devtools_recipes.md` | MCP 精确调用顺序与故障兜底 |

## License

MIT
