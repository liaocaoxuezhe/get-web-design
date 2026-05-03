---
name: get-web-design
description: This skill should be used when the user wants to extract a complete DESIGN.md style guide (frontmatter + design thinking + AI style analysis + compressed CSS evidence + negative constraints) from any live website URL. It captures 3 viewport screenshots, samples DOM and computed CSS via chrome-devtools MCP, asks a user-configured multimodal LLM to analyze the visual style from screenshots+DOM, then merges everything into a single DESIGN.md file. Trigger phrases include "extract design from a url", "生成 DESIGN.md", "分析这个网站的设计风格", "get web design".
---

# get-web-design

将任意线上网站的设计风格提取为一份结构化 `DESIGN.md`。本 skill 是 design-extractor Chrome 扩展的命令行 / Claude Code 移植版。

## 何时使用

调用本 skill 当且仅当用户希望：

- 从一个 URL 生成一份可用于 AI 编程提示词的 `DESIGN.md`
- 提取某站点的设计 token（颜色 / 字体 / 间距 / 圆角 / 阴影 / 动效 token）
- 让 AI 描述某站点的视觉风格、组件规范、整体氛围
- 识别网页里最值得复刻的特殊元素，并输出 few-shot 模块规范

典型触发语句：
- "生成 https://stripe.com 的 DESIGN.md"
- "分析 linear.app 的设计风格并保存"
- "extract design from <url>"

## 硬性前置条件

调用本 skill **前**必须确认：

1. **chrome-devtools MCP 已连接** —— 通过 `/mcp` 验证是否有 `chrome-devtools` 服务，没有则参考 `references/setup.md` 安装。
2. **多模态 LLM 三项配置已就绪**（环境变量或 CLI 参数）：
   - `WEB_DESIGN_API_KEY`
   - `WEB_DESIGN_BASE_URL` （OpenAI 兼容根路径，必须含 `/v1` 或对应路径前缀）
   - `WEB_DESIGN_MODEL` （**必须支持 vision**，纯文本模型会失败）

   若任一项缺失，**必须先向用户询问并由用户自行填写**，不要替用户编造任何 key/url/model。
   详见 `references/setup.md`。

## 总体工作流（5 步）

```
URL → [chrome-devtools] 3 截图 + collected.json → [Python] CSS 压缩 + LLM 调用 + 拼装 → {hostname}_design.md
```

每一步细节见 `references/workflow.md`。chrome-devtools MCP 的精确调用配方见 `references/chrome_devtools_recipes.md`。

### Step 1 — 创建临时工作目录

```bash
mkdir -p /tmp/get-web-design/<run-id>
```

### Step 2 — 用 chrome-devtools 采集

按 `references/chrome_devtools_recipes.md` 顺序：

1. `mcp__chrome-devtools__new_page({ url })`，必要时 `wait_for` 等首屏渲染。
2. 依次滚到 0% / 35% / 70%，每次滚动后 ≥600ms 再 `take_screenshot`，存为 `shot1.jpg / shot2.jpg / shot3.jpg`。
3. 读取 `assets/collect_design_data.js` 全部内容，包成 `() => { …全部代码… }` 传给 `evaluate_script`，把返回值序列化写入 `collected.json`。

> 该 JS 文件最后一行是 `return collectDesignData({ includeCss: true });`，
> 所以包装层只需要把整个文件内容塞进 `() => { ... }` 里就能得到结构化对象。

### Step 3 — 调用编排脚本

```bash
python3 <skill_dir>/scripts/generate_design_md.py \
  --collected /tmp/get-web-design/<run-id>/collected.json \
  --screenshots /tmp/.../shot1.jpg /tmp/.../shot2.jpg /tmp/.../shot3.jpg \
  --hostname "<hostname>"
```

`--output` 可省略，默认输出到当前目录的 `<hostname>_design.md`（如 `platform.moonshot.cn_design.md`）。如需自定义路径可加 `--output <path>`。语言默认英文（`--language en`），不建议改为 `zh`。

脚本内部完成：
- `normalize_css_evidence` —— 用 `scripts/css_evidence.py` 把 280 行 computed-style 压成高频 token；
- `format_css_evidence_markdown` —— 渲染成 `## Engineering CSS Evidence` 段（英文）；
- `build_messages` —— DOM JSON + 3 张截图 base64 + 英文 system prompt（`assets/system_prompt_en.txt`）；
- `call_llm` —— OpenAI 兼容 `/chat/completions` 非流式调用；
- `assemble_design_md` —— 按固定顺序拼装：

```
frontmatter (hostname / version / last_updated)
+ design_thinking   (assets/design_thinking.md，Design Thinking 准则)
+ AI 风格分析      (去掉 ``` 围栏)
+ CSS Evidence Markdown
+ core_principles   (assets/core_principles.md，Negative Constraints + Performance)
```

### Step 4 — 校验输出

打开 `./<hostname>_design.md`，确认：
- 顶部有 `---` frontmatter；
- 包含 `# Design Thinking`、`# Overall Atmosphere`、`## Engineering CSS Evidence`、`## Core Principles` 四个段落；
- 包含 `## Distinctive Element Few-shot Examples`，并为真实页面元素给出 purpose / evidence / visual rules / recreation prompt / structure sketch；
- `## Engineering CSS Evidence` 下的 token 不全是 "Not enough evidence"；
- 全文无中文（frontmatter 及 AI 分析段落均应为英文）。

若 `Engineering CSS Evidence` 大量为 "Not enough evidence"，回到 Step 2 检查 evaluate_script 返回值是否完整。

### Step 5 — 关闭页面（可选）

```
mcp__chrome-devtools__close_page({ pageIdx })
```

## 文件清单

| 路径 | 用途 |
|------|------|
| `assets/collect_design_data.js` | 注入到目标页面的 DOM+CSS 采集脚本（不依赖任何外部库） |
| `assets/system_prompt_zh.txt` / `system_prompt_en.txt` | 多模态 LLM 的 system prompt |
| `assets/design_thinking.md` / `core_principles.md` | DESIGN.md 的固定头尾段，**不要修改顺序或内容** |
| `scripts/css_evidence.py` | CSS computed-style → 设计 token 压缩 + Markdown 渲染（Python 库） |
| `scripts/generate_design_md.py` | 主入口 CLI；负责调 LLM 与最终拼装 |
| `references/setup.md` | 安装 chrome-devtools MCP + 配置 LLM 凭据 |
| `references/workflow.md` | 完整数据流详解（与原 design-extractor 对齐） |
| `references/chrome_devtools_recipes.md` | chrome-devtools MCP 的精确调用顺序与故障兜底 |

## 重要约束

- **不要在 LLM prompt 中加入 CSS 数据。** 原始 CSS 由 Python 单独压缩；prompt 中只提供 DOM 文本+截图。这是为了防止模型编造 CSS 细节。
- **特殊元素 few-shot 必须来自真实证据。** `domSnapshot.distinctiveCandidates` 会提供候选模块，但最终仍需结合截图判断，不要为不存在的页面元素编造模块。
- **拼装顺序固定。** frontmatter → design_thinking → AI 分析 → CSS Evidence → core_principles。任何重排都会破坏下游使用本 DESIGN.md 的提示词链。
- **3 张截图是上限。** 由 Chrome 速率限制决定；不要尝试加到 5 张以上。
- **模型必须支持 vision。** 用纯文本模型会得到无视觉 grounding 的低质量结果。
- **API key/url/model 由用户提供。** 不要为用户填默认值；缺失时用 `AskUserQuestion` 询问，然后让用户用环境变量或 `--api-key` 传入。
