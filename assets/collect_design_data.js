/**
 * collect_design_data.js
 *
 * 注入到目标页面运行（通过 chrome-devtools 的 evaluate_script）。
 * 返回 { meta, domSnapshot, engineeredCssEvidence } JSON-serializable 对象。
 *
 * 使用方式（在 chrome-devtools MCP 中）：
 *   将此文件内容包装成 IIFE，作为 function 字符串传入 evaluate_script:
 *     `() => { ...本文件全部内容... ; return collectDesignData({ includeCss: true }); }`
 *   也可使用 generate_design_md.py 中的 build_evaluate_script() 自动包装。
 *
 * 注意：此脚本不依赖任何外部库，全部使用浏览器原生 API。
 */

function collectDesignData({ includeCss = true } = {}) {
  const result = {
    meta: collectPageMeta(),
    domSnapshot: collectDomSnapshot(),
  };
  if (includeCss) {
    result.engineeredCssEvidence = collectCssEvidence();
  }
  return result;
}

function collectPageMeta() {
  const metaByName = (name) => document.querySelector(`meta[name="${name}"]`)?.content || '';
  const metaByProperty = (property) => document.querySelector(`meta[property="${property}"]`)?.content || '';
  return {
    title: document.title,
    hostname: window.location.hostname,
    description: metaByName('description'),
    keywords: metaByName('keywords'),
    ogType: metaByProperty('og:type'),
    ogSiteName: metaByProperty('og:site_name'),
    applicationName: metaByName('application-name'),
    url: window.location.href,
  };
}

function collectDomSnapshot() {
  const textOf = (el, limit = 120) =>
    (el?.textContent || '').replace(/\s+/g, ' ').trim().slice(0, limit);
  const allText = textOf(document.body, 14000);
  const ctaSelector = [
    'button',
    'a[role="button"]',
    'a[href]',
    '[class*="btn" i]',
    '[class*="button" i]',
    '[data-testid*="button" i]',
  ].join(',');

  const headings = Array.from(document.querySelectorAll('h1,h2,h3,h4,h5,h6'))
    .filter(isVisibleForEvidence)
    .slice(0, 24)
    .map((el) => ({ level: el.tagName.toLowerCase(), text: textOf(el, 140) }))
    .filter((item) => item.text);

  const navigation = Array.from(
    document.querySelectorAll('nav a, header a, [role="navigation"] a')
  )
    .filter(isVisibleForEvidence)
    .slice(0, 32)
    .map((el) => textOf(el, 60))
    .filter(Boolean);

  const ctas = Array.from(document.querySelectorAll(ctaSelector))
    .filter(isVisibleForEvidence)
    .slice(0, 36)
    .map((el) => ({
      tag: el.tagName.toLowerCase(),
      text: textOf(el, 80),
      href: el.getAttribute('href') || '',
      ariaLabel: el.getAttribute('aria-label') || '',
    }))
    .filter((item) => item.text || item.ariaLabel);

  const landmarks = Array.from(
    document.querySelectorAll('header,nav,main,section,article,aside,footer,[role]')
  )
    .filter(isVisibleForEvidence)
    .slice(0, 40)
    .map((el) => ({
      tag: el.tagName.toLowerCase(),
      role: el.getAttribute('role') || '',
      id: el.id || '',
      className: stringifyClassName(el.className).split(/\s+/).slice(0, 6).join(' '),
      text: textOf(el, 180),
    }));

  return {
    headings,
    navigation,
    ctas,
    landmarks,
    bodyTextSample: allText,
    counts: {
      forms: document.querySelectorAll('form').length,
      inputs: document.querySelectorAll('input,textarea,select').length,
      tables: document.querySelectorAll('table').length,
      codeBlocks: document.querySelectorAll('pre,code').length,
      articleContainers: document.querySelectorAll(
        'article,[class*="article" i],[class*="post" i],[class*="blog" i]'
      ).length,
      pricingSections: document.querySelectorAll(
        '[class*="pricing" i],[id*="pricing" i],[class*="plans" i],[id*="plans" i]'
      ).length,
    },
  };
}

const CSS_EVIDENCE_LIMIT = 280;

function collectCssEvidence() {
  const diagnostics = [];
  try {
    const totalElements = document.querySelectorAll('*').length;
    const sampled = collectSampledElements(CSS_EVIDENCE_LIMIT);
    const rows = collectComputedStyleRows(sampled);

    if (sampled.length < 30) {
      diagnostics.push('Low sample size: fewer than 30 visible elements were extracted.');
    }
    if (!document.fonts) {
      diagnostics.push('document.fonts is unavailable in this browser context.');
    }

    return {
      source: {
        url: window.location.href,
        title: document.title,
        hostname: window.location.hostname,
      },
      sampledAt: new Date().toISOString(),
      totalElements,
      sampledElements: rows.length,
      rows,
      diagnostics,
    };
  } catch (e) {
    return {
      source: {
        url: window.location.href,
        title: document.title,
        hostname: window.location.hostname,
      },
      sampledAt: new Date().toISOString(),
      totalElements: 0,
      sampledElements: 0,
      rows: [],
      error: e.message,
      diagnostics: [`Engineering CSS evidence extraction failed: ${e.message}`],
    };
  }
}

function collectSampledElements(limit) {
  const prioritySelectors = [
    'body',
    'h1,h2,h3,h4,h5,h6',
    'p',
    'a',
    'button',
    'input,textarea,select',
    'label',
    'nav,header,footer,main,section,article,aside',
    'ul li,ol li',
    'table,th,td',
    '[role="button"]',
    '[class*="card" i]',
    '[class*="btn" i]',
    '[tabindex]',
  ];

  const seen = new Set();
  const candidates = [];
  const addElement = (el, priority) => {
    if (!el || seen.has(el) || !isVisibleForEvidence(el)) return;
    seen.add(el);
    candidates.push({ el, priority, area: elementArea(el) });
  };

  prioritySelectors.forEach((selector, index) => {
    try {
      document.querySelectorAll(selector).forEach((el) => addElement(el, index));
    } catch (_) {}
  });

  return candidates
    .sort((a, b) => a.priority - b.priority || b.area - a.area)
    .slice(0, limit)
    .map((item) => item.el);
}

function isVisibleForEvidence(el) {
  if (!(el instanceof Element)) return false;
  const rect = el.getBoundingClientRect();
  if (rect.width <= 0 || rect.height <= 0) return false;
  const cs = getComputedStyle(el);
  if (cs.display === 'none' || cs.visibility === 'hidden') return false;
  return true;
}

function elementArea(el) {
  const rect = el.getBoundingClientRect();
  return Math.round(rect.width * rect.height);
}

function collectComputedStyleRows(elements) {
  const rows = [];
  for (const el of elements) {
    try {
      const cs = getComputedStyle(el);
      const rect = el.getBoundingClientRect();
      const componentType = inferComponentType(el);
      const isLowConfidence = cs.opacity === '0';

      rows.push({
        selectorHint: buildSelectorHint(el),
        componentType,
        lowConfidence: isLowConfidence,
        tagName: el.tagName.toLowerCase(),
        role: el.getAttribute('role'),
        id: el.id || null,
        className: stringifyClassName(el.className),
        textSample: getTextSample(el),
        rect: {
          width: Math.round(rect.width),
          height: Math.round(rect.height),
          top: Math.round(rect.top),
          left: Math.round(rect.left),
        },
        typography: {
          fontFamily: cs.fontFamily,
          fontSize: cs.fontSize,
          fontWeight: cs.fontWeight,
          lineHeight: cs.lineHeight,
          letterSpacing: cs.letterSpacing,
        },
        color: {
          color: cs.color,
          backgroundColor: cs.backgroundColor,
          borderColor: cs.borderColor,
          outlineColor: cs.outlineColor,
        },
        box: {
          margin: cs.margin,
          padding: cs.padding,
          marginTop: cs.marginTop,
          marginRight: cs.marginRight,
          marginBottom: cs.marginBottom,
          marginLeft: cs.marginLeft,
          paddingTop: cs.paddingTop,
          paddingRight: cs.paddingRight,
          paddingBottom: cs.paddingBottom,
          paddingLeft: cs.paddingLeft,
          borderRadius: cs.borderRadius,
          boxShadow: cs.boxShadow,
        },
        motion: {
          transitionDuration: cs.transitionDuration,
          transitionTimingFunction: cs.transitionTimingFunction,
          animationDuration: cs.animationDuration,
          animationTimingFunction: cs.animationTimingFunction,
        },
      });
    } catch (_) {}
  }
  return rows;
}

function inferComponentType(el) {
  const tag = el.tagName.toLowerCase();
  const role = (el.getAttribute('role') || '').toLowerCase();
  const className = stringifyClassName(el.className).toLowerCase();
  const id = (el.id || '').toLowerCase();
  const marker = `${className} ${id}`;

  if (/^h[1-6]$/.test(tag)) return 'heading';
  if (tag === 'button' || role === 'button' || marker.includes('button') || marker.includes('btn'))
    return 'button';
  if (tag === 'a') return 'link';
  if (['input', 'textarea', 'select'].includes(tag)) return 'input';
  if (tag === 'nav' || marker.includes('nav')) return 'navigation';
  if (tag === 'section') return 'section';
  if (tag === 'ul' || tag === 'ol' || tag === 'li') return 'list';
  if (['table', 'thead', 'tbody', 'tr', 'td', 'th'].includes(tag)) return 'table';
  if (marker.includes('card')) return 'card';
  if (marker.includes('hero')) return 'hero';
  if (marker.includes('modal')) return 'modal';
  if (marker.includes('panel')) return 'panel';
  if (marker.includes('grid')) return 'grid';
  if (marker.includes('container')) return 'container';
  return 'content';
}

function buildSelectorHint(el) {
  const tag = el.tagName.toLowerCase();
  if (el.id) return `${tag}#${el.id}`;
  const className = stringifyClassName(el.className);
  if (className) {
    return `${tag}.${className.split(/\s+/).filter(Boolean).slice(0, 3).join('.')}`;
  }
  const role = el.getAttribute('role');
  if (role) return `${tag}[role="${role}"]`;
  return tag;
}

function stringifyClassName(value) {
  if (!value) return '';
  if (typeof value === 'string') return value;
  if (typeof value.baseVal === 'string') return value.baseVal;
  return String(value);
}

function getTextSample(el) {
  if (['INPUT', 'TEXTAREA', 'SELECT'].includes(el.tagName)) return '';
  return (el.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 80);
}

// 直接调用并返回结果（chrome-devtools evaluate_script 会序列化返回值）
return collectDesignData({ includeCss: true });
