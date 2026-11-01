---
name: cnki-paper-detail
description: Extract full paper details from a CNKI paper page including title, authors, affiliations, abstract, keywords, fund, classification. Use when the user needs detailed information about a specific paper.
---

## Codex 使用约定

- 来源：https://github.com/cookjohn/cnki-skills ，本地浏览器服务器为 `chrome_devtools`。示例中的工具名以当前实际工具清单为准，先核对工具和参数；缺少服务器时报告未连接，不能把安装成功当作检索成功。
- `$ARGUMENTS` 指用户当前给出的检索条件或论文链接；在 Codex 中可用 `$cnki-search` 等技能名称调用。
- 只操作本次检索创建的浏览器页面；按工具返回的页面 ID 或选中页执行，不访问用户其他浏览器资料。
- 遇到验证码或需要登录时，等待用户在专用浏览器中完成；不绕过验证，也不读取或导出密码、Cookie 和访问令牌。
- 论文题名、作者、刊名、年份、页码和详情链接以实际页面或引用导出结果为准；无法核验时标明未核验，不根据 DOI 拼出链接后宣称已验证。
- 页面布局或选择器变化时，先查看实际页面，再调整解析；没有返回结果不等于不存在该论文。
- 下载、缓存和临时文件沿用用户非 C 盘配置。引用导出默认输出 GB/T 7714 文本；只有用户明确要求写入 Zotero 时才调用 Zotero 写入脚本。
- 本机安装检索、高级检索、论文详情和引用导出四项；需要解析搜索列表时复用 cnki-search 的解析段落，需要翻页时检查当前分页控件，不假定其他技能已经安装。



# CNKI Paper Detail Extraction

Extract complete metadata from a CNKI paper detail page. Cross-check year, volume, issue and pages against actual publication information and cnki-export citation data; search-list dates alone do not establish complete bibliographic metadata. Return the actual page URL and mark fields that could not be verified.

## Arguments

`$ARGUMENTS` is optionally a CNKI paper detail URL (containing `kcms2/article/abstract`). If not provided, assumes the current page is already a paper detail page.

## Steps

### 1. Navigate to the paper page (if URL provided)

If `$ARGUMENTS` contains a URL:
- Use `mcp__chrome_devtools__navigate_page` with the URL.
- Use `mcp__chrome_devtools__wait_for` with text `["摘要"]` and timeout 15000.

### 2. Check for captcha

Use `mcp__chrome_devtools__take_snapshot`. If "拖动下方拼图完成验证" found, notify user:

> CNKI 正在显示滑块验证码。请在 Chrome 浏览器中手动完成拼图验证，完成后告诉我继续。

### 3. Extract paper metadata via JavaScript

Use `mcp__chrome_devtools__evaluate_script` with this function:

```javascript
() => {
  const brief = document.querySelector('.brief');
  if (!brief) return { error: 'Paper detail section (.brief) not found' };

  // Title
  const title = brief.querySelector('h1')?.innerText?.trim()
    ?.replace(/\s*附视频\s*$/, '')  // remove "附视频" suffix
    ?.replace(/\s*网络首发\s*$/, ''); // remove "网络首发" suffix

  // Authors - first h3.author contains author links with sup tags
  const authorH3s = brief.querySelectorAll('h3.author');
  const authorSection = authorH3s[0];
  const authors = [];
  if (authorSection) {
    const authorLinks = authorSection.querySelectorAll('a');
    authorLinks.forEach(a => {
      const name = a.innerText?.replace(/\d+$/, '').trim();
      const supMatch = a.innerText?.match(/(\d+)$/);
      const affiliationNum = supMatch ? supMatch[1] : '';
      authors.push({ name, affiliationNum });
    });
  }

  // Affiliations - second h3.author contains org links
  const affiliations = [];
  if (authorH3s.length > 1) {
    const orgLinks = authorH3s[1].querySelectorAll('a');
    orgLinks.forEach(a => {
      affiliations.push(a.innerText?.trim());
    });
  }

  // Abstract
  const abstractEl = document.querySelector('.abstract-text');
  const abstract = abstractEl?.innerText?.trim() || '';

  // Keywords
  const keywordsP = document.querySelector('p.keywords');
  const keywords = keywordsP
    ? Array.from(keywordsP.querySelectorAll('a')).map(a => a.innerText?.replace(/;$/, '').trim())
    : [];

  // Fund
  const fundsP = document.querySelector('p.funds');
  const fund = fundsP?.innerText?.trim() || '';

  // Classification code
  const clcCode = document.querySelector('.clc-code');
  const classification = clcCode?.innerText?.trim() || '';

  // Journal/source
  const docTop = document.querySelector('.doc-top');
  const journal = docTop?.querySelector('a')?.innerText?.trim() || '';

  // Online first / publication info
  const headTime = document.querySelector('.head-time');
  const pubInfo = headTime?.innerText?.trim() || '';

  // Is online first?
  const isOnlineFirst = !!brief.querySelector('.icon-shoufa');

  // Article outline/TOC
  const catalogList = document.querySelector('.catalog-list, .catalog-listDiv');
  const toc = catalogList?.innerText?.trim() || '';

  // Citation network counts
  const citationTabs = document.querySelectorAll('ul.module-tab.tpl_lieteratures li');
  const citationInfo = {};
  citationTabs.forEach(li => {
    const id = li.getAttribute('data-id');
    const text = li.innerText?.trim();
    const countMatch = text.match(/(\d+)/);
    if (id) {
      citationInfo[id] = {
        label: text.replace(/\d+/, '').trim(),
        count: countMatch ? parseInt(countMatch[1]) : 0
      };
    }
  });

  return {
    pageUrl: window.location.href,
    title,
    authors,
    affiliations,
    abstract,
    keywords,
    fund,
    classification,
    journal,
    pubInfo,
    isOnlineFirst,
    toc,
    citationInfo
  };
}
```

### 4. Format and present the output

```
## {title} {isOnlineFirst ? "[网络首发]" : ""}

**Authors:**
{For each author: "- {name} ({affiliation})"}

**Affiliations:**
{For each affiliation: "- {affiliation}"}

**Journal:** {journal}
**Publication Info:** {pubInfo}

**Abstract:**
{abstract}

**Keywords:** {keywords joined by ", "}

**Fund:** {fund}
**Classification:** {classification}

**Citation Network:**
{For each citation type: "- {label}: {count}"}
```

### 5. Fallback: snapshot-based parsing

If JS extraction fails, use `mcp__chrome_devtools__take_snapshot` and parse the accessibility tree:
- **Title**: `heading` level 1 element
- **Authors**: `link` elements whose URLs contain `kcms2/author/detail`
- **Affiliations**: `link` elements whose URLs contain `kcms2/organ/detail`
- **Abstract**: `StaticText` following "摘要："
- **Keywords**: `link` elements whose URLs contain `kcms2/keyword/detail`
- **Fund**: `link` elements following "基金资助："
- **Classification**: `StaticText` following "分类号："

## Verified DOM Selectors

| Data           | Selector                                   | Notes                                    |
|----------------|--------------------------------------------|------------------------------------------|
| Paper section  | `.brief`                                    | Main paper info container                |
| Title          | `.brief h1`                                 | May contain icons, clean text needed     |
| Authors        | `.brief h3.author:first-of-type a`          | Text has superscript numbers (e.g., "张三1") |
| Affiliations   | `.brief h3.author:nth-of-type(2) a`         | Text starts with "N." (e.g., "1.北京大学") |
| Abstract       | `.abstract-text`                            | Full abstract text                       |
| Keywords       | `p.keywords a`                              | Semicolon-separated keyword links        |
| Fund           | `p.funds`                                   | Fund information text                    |
| Classification | `.clc-code`                                 | CLC classification codes                |
| Journal        | `.doc-top a`                                | Source journal link                      |
| Online first   | `.brief .icon-shoufa`                       | Present if paper is online first         |
| Citation tabs  | `ul.module-tab.tpl_lieteratures li`         | data-id attr identifies type             |
