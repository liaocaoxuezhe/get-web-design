# 环境准备 / Setup

本 skill 有 **2 项硬性外部依赖**，必须在使用前由用户完成配置。

## 1. chrome-devtools MCP（硬依赖）

本 skill 通过 chrome-devtools MCP 完成截图与脚本注入。**没有它无法工作。**

### 安装步骤
在 Claude Code 中：

```bash
claude mcp add chrome-devtools npx chrome-devtools-mcp@latest
```

或编辑 `~/.claude.json` 添加：

```json
{
  "mcpServers": {
    "chrome-devtools": {
      "command": "npx",
      "args": ["chrome-devtools-mcp@latest"]
    }
  }
}
```

### 验证
启动一个新的 Claude Code 会话，输入 `/mcp` 应能看到 `chrome-devtools` 已连接，
并能调用 `mcp__chrome-devtools__new_page` / `take_screenshot` / `evaluate_script`。

### 备选 MCP
若没有 chrome-devtools，本 skill **也可以**改用以下任一替代（需修改调用细节）：
- `mcp__local-browser__*`
- `mcp__Claude_in_Chrome__*`

但本文档与示例命令默认使用 chrome-devtools。

---

## 2. 多模态 LLM 凭据（硬依赖）

本 skill 自身不内置任何 API Key —— 用户必须自行准备一个 **支持多模态视觉输入** 的 OpenAI 兼容接口。

### 必填 3 项配置

| 环境变量 | 含义 | 示例 |
|---------|-----|------|
| `WEB_DESIGN_API_KEY` | API Key | `sk-xxxxxxxxxxxx` |
| `WEB_DESIGN_BASE_URL` | OpenAI 兼容根路径（**包含 `/v1`**） | `https://api.moonshot.cn/v1` |
| `WEB_DESIGN_MODEL` | 模型名（必须支持视觉） | `kimi-latest` |

### 设置方式

**方式 A — Shell 环境变量（推荐）：**
```bash
export WEB_DESIGN_API_KEY="sk-..."
export WEB_DESIGN_BASE_URL="https://api.moonshot.cn/v1"
export WEB_DESIGN_MODEL="kimi-latest"
```

**方式 B — CLI 参数（覆盖环境变量）：**
```bash
python scripts/generate_design_md.py \
  --api-key "sk-..." --base-url "https://..." --model "..." \
  --collected ... --screenshots ... --output DESIGN.md
```

### 已知可用的多模态模型

| Provider | base_url | model 示例 |
|---------|----------|-----------|
| Moonshot Kimi | `https://api.moonshot.cn/v1` | `kimi-latest`, `moonshot-v1-32k-vision-preview` |
| OpenAI | `https://api.openai.com/v1` | `gpt-4o`, `gpt-4o-mini`, `gpt-4-turbo` |
| Anthropic（兼容代理） | OpenAI-compat 网关 | `claude-3-5-sonnet-20241022`, `claude-opus-4-...` |
| 阿里云 DashScope | `https://dashscope.aliyuncs.com/compatible-mode/v1` | `qwen-vl-max`, `qwen-vl-plus` |
| 智谱 GLM | `https://open.bigmodel.cn/api/paas/v4` | `glm-4v`, `glm-4v-plus` |
| 火山方舟 | `https://ark.cn-beijing.volces.com/api/v3` | `doubao-vision-pro-32k` |

> ⚠️ 纯文本模型（如 `gpt-3.5-turbo`、`deepseek-chat`、`kimi-k2`）**不可用** —— skill 会调用失败或得到无视觉理解的低质量结果。

---

## Python 环境

skill 仅使用标准库（`urllib`, `json`, `base64`, `argparse` 等），**不依赖任何第三方包**。

- Python ≥ 3.9
- 用户全局 Python（`python3`）即可，不需要虚拟环境。
