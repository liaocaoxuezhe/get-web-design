"""
css_evidence.py — 将原始 computed-style 行压缩为 design tokens 并渲染为 Markdown。

输入：collect_design_data.js 返回的 engineeredCssEvidence 对象（dict）。
输出：
  - normalize_css_evidence(raw)  -> 归一化后的 tokens 字典
  - format_css_evidence_markdown(evidence, language='zh') -> Markdown 字符串

核心思路：保留高频 token，舍弃噪声值；按角色（text/surface/accent/border 等）归类。
"""

from __future__ import annotations

import re
from collections import Counter
from typing import Any, Callable, Dict, Iterable, List, Optional

EMPTY_LABEL_EN = "Not enough evidence"
EMPTY_LABEL_ZH = "证据不足"

LABELS = {
    "en": {
        "title": "Engineering CSS Evidence",
        "intro": (
            "Compressed from live DOM computed styles. This section keeps "
            "high-frequency tokens and intent, not raw CSS dumps."
        ),
        "tokens": "Compressed Design Tokens",
        "colors": "Color Roles",
        "typography": "Typography Roles",
        "spacing": "Spacing Rhythm",
        "radius": "Radius Roles",
        "shadow": "Shadow Intent",
        "motion": "Motion Intent",
        "distinction": "Distinctive Implementation Signals",
        "diagnostics": "Extraction Diagnostics",
        "sampled": "Sampled {sampled} visible elements from {total} total DOM elements.",
        "confidence": "Confidence",
        "empty": EMPTY_LABEL_EN,
    },
    "zh": {
        "title": "工程 CSS 证据",
        "intro": "由实时 DOM computed styles 压缩生成。这里只保留高频 token 与设计意图，不输出原始 CSS 清单。",
        "tokens": "压缩设计 Token",
        "colors": "色彩角色",
        "typography": "字体角色",
        "spacing": "间距节奏",
        "radius": "圆角角色",
        "shadow": "阴影意图",
        "motion": "动效意图",
        "distinction": "差异化实现信号",
        "diagnostics": "采集诊断",
        "sampled": "从 {total} 个 DOM 元素中采样了 {sampled} 个可见元素。",
        "confidence": "置信度",
        "empty": EMPTY_LABEL_ZH,
    },
}

NOISE_VALUES = {
    "none", "normal", "auto", "initial", "inherit", "unset",
    "0", "0px", "0s", "0ms",
    "rgba(0, 0, 0, 0)", "rgba(0,0,0,0)", "transparent",
}

PX_RE = re.compile(r"-?\d*\.?\d+px")
RGBA_RE = re.compile(r"rgba?\(([^)]+)\)")
HEX_RE = re.compile(r"^#[0-9a-f]{3,8}$", re.IGNORECASE)


# ── 通用工具 ─────────────────────────────────────────────────────


def labels_for(language: str) -> Dict[str, str]:
    return LABELS.get(language, LABELS["en"])


def empty_label(language: str) -> str:
    return labels_for(language)["empty"]


def is_informative(value: Any) -> bool:
    if value is None:
        return False
    s = str(value).strip().lower()
    if not s:
        return False
    return s not in NOISE_VALUES


def count_values(
    values: Iterable[Any], transform: Callable[[Any], Any] = lambda v: v
) -> List[Dict[str, Any]]:
    counter: Counter = Counter()
    for raw in values:
        v = transform(raw)
        if not is_informative(v):
            continue
        counter[str(v).strip()] += 1
    items = sorted(counter.items(), key=lambda kv: (-kv[1], kv[0]))
    return [{"value": v, "count": c} for v, c in items]


def top_rows(
    values: Iterable[Any], limit: int = 3, transform: Callable[[Any], Any] = lambda v: v
) -> List[Dict[str, Any]]:
    return count_values(values, transform)[:limit]


def px_number(value: Any) -> Optional[float]:
    if value is None:
        return None
    m = PX_RE.search(str(value))
    if not m:
        return None
    try:
        return float(m.group(0)[:-2])
    except ValueError:
        return None


def px_numbers(value: Any) -> List[float]:
    if value is None:
        return []
    nums = []
    for m in PX_RE.findall(str(value)):
        try:
            n = float(m[:-2])
            if n > 0:
                nums.append(n)
        except ValueError:
            pass
    return nums


def format_px(num: Optional[float]) -> Optional[str]:
    if num is None or num != num:  # NaN check
        return None
    if float(num).is_integer():
        return f"{int(num)}px"
    return f"{round(num, 2)}px"


def parse_duration_ms(value: Any) -> Optional[int]:
    if value is None:
        return None
    raw = str(value).strip()
    if not raw or raw in ("0s", "0ms"):
        return None
    parts = [p.strip() for p in raw.split(",")]
    ms_values = []
    for part in parts:
        try:
            if part.endswith("ms"):
                ms_values.append(float(part[:-2]))
            elif part.endswith("s"):
                ms_values.append(float(part[:-1]) * 1000)
        except ValueError:
            continue
    ms_values = [m for m in ms_values if m > 0]
    return round(max(ms_values)) if ms_values else None


def canonical_color(value: Any) -> Optional[str]:
    if not is_informative(value):
        return None
    raw = str(value).strip().lower()
    if raw == "transparent":
        return None
    if HEX_RE.match(raw):
        if len(raw) == 4:
            return f"#{raw[1]*2}{raw[2]*2}{raw[3]*2}"
        return raw[:7]
    m = RGBA_RE.match(raw)
    if not m:
        return raw
    parts = [p.strip() for p in m.group(1).split(",")]
    if len(parts) < 3:
        return raw
    try:
        alpha = float(parts[3]) if len(parts) >= 4 else 1.0
    except ValueError:
        alpha = 1.0
    if alpha == 0:
        return None
    try:
        channels = [max(0, min(255, round(float(p)))) for p in parts[:3]]
    except ValueError:
        return raw
    return "#" + "".join(f"{c:02x}" for c in channels)


def first_font_family(font_family: Any) -> Optional[str]:
    if font_family is None:
        return None
    for item in str(font_family).split(","):
        cleaned = item.strip().strip("'\"")
        if cleaned:
            return cleaned
    return None


def color_brightness(hex_value: str) -> Optional[float]:
    if not hex_value:
        return None
    pairs = re.findall(r"[0-9a-f]{2}", hex_value, re.IGNORECASE)[:3]
    if len(pairs) < 3:
        return None
    try:
        nums = [int(p, 16) for p in pairs]
    except ValueError:
        return None
    return sum(nums) / 3


# ── Token 推断 ───────────────────────────────────────────────────


def pick_color_role(rows: List[Dict], getter: Callable, limit: int = 1):
    values = top_rows([getter(r) for r in rows], limit, canonical_color)
    formatted = [{"value": r["value"], "usage": r["count"]} for r in values]
    if limit == 1:
        return formatted[0] if formatted else None
    return formatted


def infer_color_tokens(rows: List[Dict], body_rows: List[Dict]) -> Dict[str, Any]:
    button_rows = [r for r in rows if r.get("componentType") in ("button", "link")]
    pool_rows = button_rows or rows
    accent_pool = []
    for r in pool_rows:
        c = r.get("color") or {}
        accent_pool.extend([c.get("backgroundColor"), c.get("color"), c.get("borderColor")])

    text_primary = pick_color_role(rows, lambda r: (r.get("color") or {}).get("color"))
    text_secondary = pick_color_role(
        body_rows or rows, lambda r: (r.get("color") or {}).get("color")
    )
    background = pick_color_role(rows, lambda r: (r.get("color") or {}).get("backgroundColor"))
    border = pick_color_role(rows, lambda r: (r.get("color") or {}).get("borderColor"))
    focus = pick_color_role(rows, lambda r: (r.get("color") or {}).get("outlineColor"))
    accent_top = top_rows(accent_pool, 1, canonical_color)
    accent = (
        {"value": accent_top[0]["value"], "usage": accent_top[0]["count"]} if accent_top else None
    )

    return {
        "color.text.primary": text_primary,
        "color.text.secondary": text_secondary,
        "color.surface.base": background,
        "color.accent": accent,
        "color.border.default": border,
        "color.focus.ring": focus,
    }


def infer_mode_from_colors(colors: Iterable[Any]) -> str:
    brightness = [
        b for b in (color_brightness(canonical_color(c) or "") for c in colors) if b is not None
    ]
    if not brightness:
        return "unknown"
    dark = sum(1 for b in brightness if b < 90)
    light = sum(1 for b in brightness if b > 180)
    if dark and light:
        return "mixed"
    if dark > light:
        return "dark"
    if light > dark:
        return "light"
    return "mixed"


def infer_typography_tokens(
    rows: List[Dict], heading_rows: List[Dict], body_rows: List[Dict]
) -> Dict[str, Any]:
    family_rows = top_rows([(r.get("typography") or {}).get("fontFamily") for r in rows], 2)
    families = []
    for row in family_rows:
        primary = first_font_family(row["value"])
        if primary:
            families.append({"value": primary, "stack": row["value"], "usage": row["count"]})

    def to_px_label(value):
        n = px_number(value)
        return format_px(n) if n is not None else None

    size_counts = count_values(
        [(r.get("typography") or {}).get("fontSize") for r in rows], to_px_label
    )

    body_size_top = top_rows(
        [(r.get("typography") or {}).get("fontSize") for r in body_rows], 1, to_px_label
    )
    body_size = body_size_top[0] if body_size_top else (size_counts[0] if size_counts else None)

    body_size_px = px_number(body_size["value"]) if body_size else None
    heading_sizes = []
    for r in heading_rows:
        n = px_number((r.get("typography") or {}).get("fontSize"))
        if n is not None and (body_size_px is None or n >= body_size_px):
            heading_sizes.append(n)

    if heading_sizes:
        display_size = {"value": format_px(max(heading_sizes)), "count": len(heading_sizes)}
    else:
        display_size = next(
            (s for s in size_counts if (px_number(s["value"]) or 0) >= 24), None
        ) or (size_counts[0] if size_counts else None)

    label_candidates = [
        s for s in size_counts if not body_size_px or (px_number(s["value"]) or 0) <= body_size_px
    ]
    label_size = (
        label_candidates[-1] if label_candidates else (size_counts[0] if size_counts else None)
    )

    display_px = px_number(display_size["value"]) if display_size else None

    def wrap(token):
        if not token:
            return None
        return {"value": token["value"], "usage": token["count"]}

    return {
        "font.family.primary": families[0] if families else None,
        "font.family.secondary": families[1] if len(families) > 1 else None,
        "font.size.display": wrap(display_size),
        "font.size.body": wrap(body_size),
        "font.size.label": wrap(label_size),
        "ratio": (
            f"display is {round(display_px / body_size_px, 2)}x body"
            if body_size_px and display_px
            else EMPTY_LABEL_EN
        ),
    }


def infer_base_unit(numbers: List[float]) -> Optional[str]:
    if not numbers:
        return None
    candidates = [4, 5, 6, 8]
    best, best_score = candidates[0], -1
    for c in candidates:
        score = sum(
            1
            for n in numbers
            if abs(n % c) < 0.1 or abs((n % c) - c) < 0.1
        )
        if score > best_score:
            best, best_score = c, score
    return f"{best}px"


def infer_spacing_tokens(rows: List[Dict]) -> Dict[str, Any]:
    keys = [
        "margin", "padding",
        "marginTop", "marginRight", "marginBottom", "marginLeft",
        "paddingTop", "paddingRight", "paddingBottom", "paddingLeft",
    ]
    numbers: List[float] = []
    for r in rows:
        box = r.get("box") or {}
        for k in keys:
            numbers.extend(px_numbers(box.get(k)))
    numbers = [n for n in numbers if 0 < n <= 160]
    common = top_rows([format_px(n) for n in numbers], 5)
    return {
        "baseUnit": infer_base_unit(numbers) or EMPTY_LABEL_EN,
        "scale": [
            {"name": f"space.{i + 1}", "value": row["value"], "usage": row["count"]}
            for i, row in enumerate(common)
        ],
    }


def infer_radius_tokens(rows: List[Dict]) -> List[Dict[str, Any]]:
    radii: List[float] = []
    for r in rows:
        radii.extend(px_numbers((r.get("box") or {}).get("borderRadius")))
    buckets = {
        "sharp": [n for n in radii if n <= 4],
        "medium": [n for n in radii if 4 < n <= 16],
        "pill": [n for n in radii if n > 16],
    }

    def token_for(name: str, values: List[float]):
        if not values:
            return None
        top = top_rows([format_px(n) for n in values], 1)
        if not top:
            return None
        return {"name": f"radius.{name}", "value": top[0]["value"], "usage": top[0]["count"]}

    return [t for t in (token_for(k, v) for k, v in buckets.items()) if t]


def infer_shadow_intent(rows: List[Dict]) -> Dict[str, Any]:
    shadows = [
        s for s in ((r.get("box") or {}).get("boxShadow") for r in rows) if is_informative(s)
    ]
    if not shadows:
        return {"level": "none", "usage": 0, "note": "flat surfaces dominate"}
    ratio = len(shadows) / max(len(rows), 1)
    unique_count = len(count_values(shadows))
    if ratio > 0.25 or unique_count > 4:
        level = "layered"
    elif ratio > 0.08:
        level = "subtle elevation"
    else:
        level = "rare accent"
    note = (
        f"{unique_count} recurring shadow treatments, compressed to intent"
        if unique_count > 1
        else "single recurring elevation treatment"
    )
    return {"level": level, "usage": len(shadows), "note": note}


def infer_motion_intent(rows: List[Dict]) -> Dict[str, Any]:
    durations = []
    for r in rows:
        m = r.get("motion") or {}
        for v in (m.get("transitionDuration"), m.get("animationDuration")):
            d = parse_duration_ms(v)
            if d:
                durations.append(d)

    easing_pool = []
    for r in rows:
        m = r.get("motion") or {}
        easing_pool.extend([m.get("transitionTimingFunction"), m.get("animationTimingFunction")])
    easings = top_rows(easing_pool, 3, lambda v: None if str(v or "").strip() == "ease" else v)

    if not durations:
        return {
            "level": "none",
            "range": EMPTY_LABEL_EN,
            "durations": [],
            "easingStyle": EMPTY_LABEL_EN,
        }

    mn, mx = min(durations), max(durations)
    common = top_rows([f"{d}ms" for d in durations], 3)
    if mx >= 700:
        level = "expressive"
    elif mx >= 300:
        level = "moderate"
    else:
        level = "subtle"
    return {
        "level": level,
        "range": f"{mn}-{mx}ms",
        "durations": [{"value": r["value"], "usage": r["count"]} for r in common],
        "easingStyle": ", ".join(f"{r['value']} ({r['count']})" for r in easings)
        or "mostly default easing",
    }


def infer_distinctive_signals(tokens: Dict[str, Any]) -> List[str]:
    signals = []
    pill = next((t for t in tokens["radius"] if t["name"] == "radius.pill"), None)
    if pill:
        signals.append(
            f"Frequent pill radius ({pill['value']}) creates a soft/capsule interaction language."
        )
    if tokens["shadow"]["level"] == "none":
        signals.append("Flat surfaces are preferred over decorative depth.")
    if tokens["shadow"]["level"] == "layered":
        signals.append(
            "Elevation appears as a recurring material cue, not a one-off decoration."
        )
    if tokens["motion"]["level"] != "none":
        signals.append(
            f"Motion is {tokens['motion']['level']}, centered around {tokens['motion']['range']}."
        )
    ratio = tokens["typography"].get("ratio")
    if ratio and ratio != EMPTY_LABEL_EN:
        signals.append(f"Type hierarchy is ratio-driven: {ratio}.")
    return signals[:4]


# ── 主入口 ────────────────────────────────────────────────────────


def normalize_css_evidence(raw_evidence: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    raw_evidence = raw_evidence or {}
    raw_rows = raw_evidence.get("rows") or []
    visible_rows = [r for r in raw_rows if not r.get("lowConfidence")]
    rows = visible_rows or raw_rows

    heading_rows = [
        r for r in rows
        if re.match(r"^h[1-6]$", str(r.get("tagName") or ""), re.IGNORECASE)
        or r.get("componentType") == "heading"
    ]
    body_tags = {"p", "span", "li", "label", "blockquote", "body"}
    body_rows = [r for r in rows if str(r.get("tagName") or "").lower() in body_tags]

    diagnostics = list(raw_evidence.get("diagnostics") or [])
    sampled_elements = raw_evidence.get("sampledElements") or len(raw_rows)
    total_elements = raw_evidence.get("totalElements") or 0

    if raw_evidence.get("error"):
        diagnostics.append(f"CSS evidence extraction failed: {raw_evidence['error']}")
    if sampled_elements < 30:
        diagnostics.append(
            "Low sample size: fewer than 30 visible elements were extracted."
        )
    if not rows:
        diagnostics.append("No computed style rows were available for normalization.")

    color = infer_color_tokens(rows, body_rows)
    tokens = {
        "color": color,
        "mode": infer_mode_from_colors([(r.get("color") or {}).get("backgroundColor") for r in rows]),
        "typography": infer_typography_tokens(rows, heading_rows, body_rows),
        "spacing": infer_spacing_tokens(rows),
        "radius": infer_radius_tokens(rows),
        "shadow": infer_shadow_intent(rows),
        "motion": infer_motion_intent(rows),
    }
    tokens["distinctiveSignals"] = infer_distinctive_signals(tokens)

    confidence = (
        "high" if sampled_elements >= 120 else "medium" if sampled_elements >= 30 else "low"
    )

    return {
        "source": raw_evidence.get("source"),
        "sampledAt": raw_evidence.get("sampledAt"),
        "tokens": tokens,
        "evidenceStats": {
            "totalElements": total_elements,
            "sampledElements": sampled_elements,
            "confidence": confidence,
            "diagnostics": diagnostics,
        },
    }


# ── Markdown 渲染 ────────────────────────────────────────────────


def _render_token(token, language: str) -> str:
    if not token:
        return empty_label(language)
    if token.get("value") and "usage" in token:
        return f"{token['value']} ({token['usage']})"
    if token.get("value"):
        return token["value"]
    return empty_label(language)


def _render_color_tokens(color_tokens, language) -> str:
    lines = []
    for name, token in (color_tokens or {}).items():
        if not token:
            continue
        lines.append(f"- **{name}:** {_render_token(token, language)}")
        if len(lines) >= 6:
            break
    return "\n".join(lines) if lines else f"- {empty_label(language)}"


def _render_typography_tokens(typography, language) -> str:
    lines = []
    for name in (
        "font.family.primary",
        "font.family.secondary",
        "font.size.display",
        "font.size.body",
        "font.size.label",
    ):
        token = (typography or {}).get(name)
        if not token:
            continue
        if name.startswith("font.family"):
            lines.append(f"- **{name}:** {token['value']} ({token['usage']})")
        else:
            lines.append(f"- **{name}:** {_render_token(token, language)}")
    ratio = (typography or {}).get("ratio")
    if ratio and ratio != EMPTY_LABEL_EN:
        lines.append(f"- **ratio:** {ratio}")
    return "\n".join(lines) if lines else f"- {empty_label(language)}"


def _render_spacing_tokens(spacing, language) -> str:
    lines = [f"- **base unit:** {(spacing or {}).get('baseUnit') or empty_label(language)}"]
    for token in (spacing or {}).get("scale") or []:
        lines.append(f"- **{token['name']}:** {token['value']} ({token['usage']})")
    return "\n".join(lines)


def _render_radius_tokens(radius, language) -> str:
    if not radius:
        return f"- {empty_label(language)}"
    return "\n".join(f"- **{t['name']}:** {t['value']} ({t['usage']})" for t in radius)


def _render_motion(motion, language) -> str:
    motion = motion or {}
    durations = motion.get("durations") or []
    duration_text = (
        ", ".join(_render_token(d, language) for d in durations) if durations else empty_label(language)
    )
    return "\n".join(
        [
            f"- **level:** {motion.get('level') or empty_label(language)}",
            f"- **range:** {motion.get('range') or empty_label(language)}",
            f"- **common durations:** {duration_text}",
            f"- **easing style:** {motion.get('easingStyle') or empty_label(language)}",
        ]
    )


def format_css_evidence_markdown(evidence: Dict[str, Any], language: str = "zh") -> str:
    labels = labels_for(language)
    tokens = (evidence or {}).get("tokens") or {}
    diagnostics = ((evidence or {}).get("evidenceStats") or {}).get("diagnostics") or []
    signals = tokens.get("distinctiveSignals") or []
    stats = (evidence or {}).get("evidenceStats") or {}

    body = f"""## {labels['title']}

{labels['intro']}

### {labels['tokens']}

**Mode:** {tokens.get('mode') or 'unknown'}

#### {labels['colors']}
{_render_color_tokens(tokens.get('color'), language)}

#### {labels['typography']}
{_render_typography_tokens(tokens.get('typography'), language)}

#### {labels['spacing']}
{_render_spacing_tokens(tokens.get('spacing'), language)}

#### {labels['radius']}
{_render_radius_tokens(tokens.get('radius'), language)}

#### {labels['shadow']}
- **level:** {(tokens.get('shadow') or {}).get('level') or empty_label(language)}
- **usage:** {(tokens.get('shadow') or {}).get('usage') or 0}
- **note:** {(tokens.get('shadow') or {}).get('note') or empty_label(language)}

#### {labels['motion']}
{_render_motion(tokens.get('motion'), language)}

### {labels['distinction']}

{chr(10).join(f'- {s}' for s in signals) if signals else f'- {empty_label(language)}'}

### {labels['diagnostics']}

- {labels['sampled'].replace('{sampled}', str(stats.get('sampledElements') or 0)).replace('{total}', str(stats.get('totalElements') or 0))}
- {labels['confidence']}: {stats.get('confidence') or 'low'}.
{chr(10).join(f'- {d}' for d in diagnostics) if diagnostics else '- No extraction warnings.'}"""

    return body
