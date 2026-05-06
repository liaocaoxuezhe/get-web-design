# 完整工作流（DESIGN.md 生成流程详解）

本流程移植自 design-extractor Chrome 扩展的 sidepanel + background + content-script 三方协作逻辑，
在 Claude Code 环境中由 chrome-devtools MCP + 本 skill 的 Python 脚本协作完成。

## 总览

```
chrome-devtools MCP                 本地脚本 (skill)
─────────────────────               ─────────────────────────
new_page(url)                       │
take_screenshot(top)         ─┐     │
scroll → 35%, screenshot     ─┼──►  ai_screenshots[3]
scroll → 70%, screenshot     ─┘     │
evaluate_script(collect_design_data.js) ──► collected.json
                                    │   ├─ meta
                                    │   ├─ domSnapshot
                                    │   └─ engineeredCssEvidence
                                    │
                                    ▼
                             generate_design_md.py
                              ├─ normalize_css_evidence(...)
                              ├─ format_css_evidence_markdown(...)
                              ├─ build_messages(dom + 3 screenshots)
                              ├─ call_llm(vision model)
                              └─ assemble: frontmatter + FIXED_1
                                          + AI 分析 + CSS Evidence
                                          + FIXED_2
                                    │
                                    ▼
                output/<hostname>/design.md
                output/<hostname>/shot{1,2,3}.jpg
```

## 各步骤细节

### 1. 截图采集（3 张）
- 顶部（scrollY = 0%）
- 中部偏上（scrollY = 35%）
- 中下部（scrollY = 70%）

设计原则：3 张是 Chrome `captureVisibleTab` 速率限制（每秒 ≤2 次）下的安全上限，且能覆盖 hero、内容主区、footer 上方过渡区。

**chrome-devtools MCP 实现要点：**
- 使用 `mcp__chrome-devtools__navigate_page` 打开 URL；
- 使用 `mcp__chrome-devtools__evaluate_script` 执行 `window.scrollTo({top: docHeight*0.35, behavior:'instant'})`；
- 使用 `mcp__chrome-devtools__take_screenshot` 保存为 PNG/JPEG；
- 每次截图后 sleep ~600ms 以避开速率限制。

### 2. DOM + CSS 采集
通过 `evaluate_script` 执行 `assets/collect_design_data.js`，返回单个 JSON 对象：

```json
{
  "meta":   { "title", "hostname", "description", "url", ... },
  "domSnapshot": {
    "headings":  [{level, text}],
    "navigation": ["...nav text..."],
    "ctas":      [{tag, text, href, ariaLabel}],
    "landmarks": [{tag, role, id, className, text}],
    "bodyTextSample": "<截断到 14k 字>",
    "counts": {forms, inputs, tables, codeBlocks, articleContainers, pricingSections}
  },
  "engineeredCssEvidence": {
    "source": {url, title, hostname},
    "totalElements": <int>,
    "sampledElements": <int>,
    "rows": [
      {
        "selectorHint", "componentType", "tagName", "role", "id", "className",
        "textSample", "rect": {...},
        "typography": {fontFamily, fontSize, fontWeight, lineHeight, letterSpacing},
        "color":      {color, backgroundColor, borderColor, outlineColor},
        "box":        {margin*, padding*, borderRadius, boxShadow},
        "motion":     {transition*, animation*}
      }, ...
    ]
  }
}
```

**采样策略（与原始扩展一致）：**
- 优先级选择器：`body`, 标题, `p`, `a`, `button`, 表单元素, 语义化 landmark, `li`, 表格, `[role=button]`, `[class*=card]`, `[class*=btn]`, `[tabindex]`
- 命中后按 priority 排序、再按可见面积降序
- 上限 280 个元素
- 过滤不可见（display:none / visibility:hidden / 0 尺寸）

**保存到磁盘：** chrome-devtools 的 evaluate_script 返回结构化对象，将其 `JSON.stringify` 后保存为 `collected.json`。

### 3. CSS 处理（高频 token 提取）
由 `scripts/css_evidence.py` 完成，逻辑等价于原扩展 `lib/css-evidence.js`：

| Token 类别 | 推断方法 |
|-----------|---------|
| `color.text.primary` / `secondary` | 全部元素 / body 类元素 `color` 的 top-1 高频值 |
| `color.surface.base` | `backgroundColor` 的 top-1 |
| `color.accent` | button + link 的 bg/color/border 池子 top-1 |
| `color.border.default` | `borderColor` top-1 |
| `mode` | 由 background 颜色亮度判定 light/dark/mixed |
| `font.family.primary/secondary` | `fontFamily` 的 top-2，取栈中第一项 |
| `font.size.display/body/label` | 标题最大值 / body 元素 top-1 / 最小值 |
| `spacing.baseUnit` | 在 4/5/6/8 中选取整除命中率最高者 |
| `spacing.scale` | margin/padding 高频 px 值 top-5 |
| `radius.sharp/medium/pill` | 按 ≤4 / 4-16 / >16 分桶取 top-1 |
| `shadow.level` | 按 boxShadow 出现率分级：layered / subtle elevation / rare accent / none |
| `motion.level` | 由最大 duration 分级：subtle (<300ms) / moderate (≥300) / expressive (≥700) |

**噪声值过滤：** `none / normal / auto / 0 / transparent / rgba(0,0,0,0)` 等被剔除。

输出 Markdown 段落标题为 `## Engineering CSS Evidence`（中文 `## 工程 CSS 证据`），最终拼入 DESIGN.md 第 4 段。

### 4. AI 风格分析（多模态）
- **输入：** system_prompt（中/英文，要求按固定 H1/H2/H3 输出风格分析）+ DOM snapshot JSON + 3 张截图（base64 data URL）+ 收尾指令。
- **关键约束：** 提示词明确要求 *"不要分析 CSS 原始数据"* —— CSS 证据由脚本生成，模型只看截图和 DOM 文本。
- **接口：** OpenAI 兼容 `/v1/chat/completions`；image 通过 `image_url.url = "data:image/...;base64,..."` 传入。
- **模型要求：** 必须支持多模态视觉输入（如 `kimi-latest`、`gpt-4o`、`claude-3-5-sonnet-20241022`、`qwen-vl-max` 等）。

### 5. 最终拼装
顺序固定，**不可调换**：

```
build_frontmatter(hostname)
↓
FIXED_TEXT_1   (Design Thinking 准则)
↓
strip_markdown_fence(ai_analysis)   (AI 风格分析，去掉首尾 ``` 围栏)
↓
formatted CSS Evidence Markdown
↓
FIXED_TEXT_2   (Negative Constraints + Performance)
```

由 `assemble_design_md(...)` 完成，默认写入 `output/<hostname>/design.md`，
并把传入的 3 张截图复制到同一目录（已在目录中的会跳过）。可用
`--output-dir` / `--output` 自定义。

## 失败模式与排查
| 现象 | 排查 |
|------|------|
| `engineeredCssEvidence missing` | evaluate_script 未成功；检查页面是否拦截了脚本注入或返回值过大被截断 |
| AI 输出为空 | 检查 `WEB_DESIGN_BASE_URL` 是否带 `/v1` 后缀；检查模型是否支持 vision |
| 截图全黑 | navigate_page 后未等待页面加载，加 `wait_for` 或 sleep 1-2 秒 |
| `Low sample size` 诊断 | 页面元素少（如登录墙、SPA 未加载完毕），可考虑滚动后重采 |
| HTTP 413 | 截图过大，降低截图质量或减小 viewport（可在 chrome-devtools 中 `resize_page`） |
