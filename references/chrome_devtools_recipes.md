# chrome-devtools MCP 操作配方

本文给出从 URL 到 `collected.json + 3 张截图` 的精确调用步骤，
所有工具均以 `mcp__chrome-devtools__*` 前缀提供。

最终产物目录：

```
output/<hostname>/design.md
output/<hostname>/shot1.jpg
output/<hostname>/shot2.jpg
output/<hostname>/shot3.jpg
```

`<hostname>` 即 URL 的 host（例如 `platform.moonshot.cn`）。

## 步骤 0：准备工作目录
```bash
mkdir -p output/<hostname>
mkdir -p /tmp/get-web-design/<run-id>     # 仅用于存放中间产物 collected.json
```
- 截图直接落到 `output/<hostname>/`（最终结果之一）。
- `collected.json` 是中间产物，放 `/tmp/...` 即可。

## 步骤 1：打开页面

```
mcp__chrome-devtools__new_page({ url: "<目标 URL>" })
```

等待页面就绪：
```
mcp__chrome-devtools__wait_for({ text: "<页面上出现的关键字>" })
# 或退而求其次：sleep 2 秒
```

## 步骤 2：截 3 张截图

> Chrome 限制每秒 ≤2 次截图，所以每次截图后需要 ≥600ms 间隔。

```
# 截图 1：顶部
mcp__chrome-devtools__evaluate_script({
  function: "() => window.scrollTo({ top: 0, behavior: 'instant' })"
})
mcp__chrome-devtools__take_screenshot({
  format: "jpeg", quality: 70,
  filePath: "output/<hostname>/shot1.jpg"
})

# 截图 2：35%
mcp__chrome-devtools__evaluate_script({
  function: "() => window.scrollTo({ top: Math.round((document.body.scrollHeight - window.innerHeight) * 0.35), behavior: 'instant' })"
})
# 等 ~600ms（多数 MCP 实现自带；否则插一个空 evaluate_script 占用时间）
mcp__chrome-devtools__take_screenshot({
  format: "jpeg", quality: 70,
  filePath: "output/<hostname>/shot2.jpg"
})

# 截图 3：70%
mcp__chrome-devtools__evaluate_script({
  function: "() => window.scrollTo({ top: Math.round((document.body.scrollHeight - window.innerHeight) * 0.70), behavior: 'instant' })"
})
mcp__chrome-devtools__take_screenshot({
  format: "jpeg", quality: 70,
  filePath: "output/<hostname>/shot3.jpg"
})

# 复位
mcp__chrome-devtools__evaluate_script({
  function: "() => window.scrollTo({ top: 0, behavior: 'instant' })"
})
```

> 若 `take_screenshot` 不支持 `filePath` 参数，使用 base64 返回值由 Bash `echo ... | base64 -d > shot1.jpg` 落盘。

## 步骤 3：注入采集脚本

读取 `assets/collect_design_data.js` 全文，将其包装成立即执行函数：

```
const SCRIPT = readFile('<skill_root>/assets/collect_design_data.js');
mcp__chrome-devtools__evaluate_script({
  function: `() => { ${SCRIPT} }`
})
```

`collect_design_data.js` 末尾自带 `return collectDesignData({ includeCss: true });`，
所以包装层只需 `() => { …全部… }` 即可拿到结构化返回值。

将返回值写入：
```bash
/tmp/get-web-design/<run-id>/collected.json
```

> 若返回的 JSON 字符串极大（>1MB），可在 evaluate_script 内自行
> `JSON.stringify(result).slice(0, MAX)` 截断，或省略 bodyTextSample。

## 步骤 4：交给 Python 脚本

```bash
python3 <skill_root>/scripts/generate_design_md.py \
  --collected /tmp/get-web-design/<run-id>/collected.json \
  --screenshots output/<hostname>/shot1.jpg \
                output/<hostname>/shot2.jpg \
                output/<hostname>/shot3.jpg \
  --hostname "<hostname>"
```

默认输出目录是 **当前工作目录下的 `output/<hostname>/`**：

```
output/<hostname>/design.md
output/<hostname>/shot1.jpg   # 截图复制/直接落盘到此处
output/<hostname>/shot2.jpg
output/<hostname>/shot3.jpg
```

如需自定义可加 `--output-dir <dir>` 整体改目录，或 `--output <path>` 仅改 markdown 路径。
脚本会自动把传入的截图复制到输出目录（截图本身已在该目录时则跳过）。

语言固定为英文（默认 `--language en`），请勿改为 `zh`，以确保整个 DESIGN.md 为英文。

## 故障兜底

| 现象 | 处置 |
|------|-----|
| `take_screenshot` 失败 with rate limit | sleep 1s 后重试一次 |
| `evaluate_script` 返回 `[object Object]` | 改用 `JSON.stringify(...)` 包装返回值 |
| 页面是 SPA 且首屏 loading | navigate_page 后 `wait_for` 一个稳定文本，再开始截图 |
| 长滚动页面（10k+ px） | 仍按 0/35/70 百分比截，覆盖率足够；若需要更多张，留意速率限制 |
