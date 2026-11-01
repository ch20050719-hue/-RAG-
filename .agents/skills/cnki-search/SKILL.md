---
name: cnki-search
description: Search CNKI (中国知网) for papers by keyword. Use when the user wants to find academic papers on a topic.
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



# CNKI Basic Search

Search CNKI for papers using keyword(s). Returns result count and structured result list (titles, URLs, authors, journal, date) in a single call.

## Arguments

$ARGUMENTS contains the search keyword(s) in Chinese or English.

## Steps

### 1. Navigate

Use `mcp__chrome_devtools__navigate_page` → `https://kns.cnki.net/kns8s/search`

### 2. Search + extract results (single evaluate_script, NO wait_for)

Replace `YOUR_KEYWORDS` with actual search terms:

```javascript
async () => {
  const query = "YOUR_KEYWORDS";

  // Wait for search input (replaces wait_for)
  await new Promise((r, j) => {
    let n = 0;
    const c = () => { if (document.querySelector('input.search-input')) r(); else if (++n > 30) j('timeout'); else setTimeout(c, 500); };
    c();
  });

  // Check captcha (only if visible on screen, not hidden SDK at top:-1000000)
  const outer = document.querySelector('#tcaptcha_transform_dy');
  if (outer && outer.getBoundingClientRect().top >= 0) return { error: 'captcha' };

  // Fill and submit (verified selectors: input.search-input, input.search-btn)
  const input = document.querySelector('input.search-input');
  input.value = query;
  input.dispatchEvent(new Event('input', { bubbles: true }));
  document.querySelector('input.search-btn')?.click();

  // Wait for results
  await new Promise((r, j) => {
    let n = 0;
    const c = () => { if (document.body.innerText.includes('条结果')) r(); else if (++n > 30) j('timeout'); else setTimeout(c, 500); };
    c();
  });

  // Check captcha again
  const outer2 = document.querySelector('#tcaptcha_transform_dy');
  if (outer2 && outer2.getBoundingClientRect().top >= 0) return { error: 'captcha' };

  // Extract current page results (merged parse-results)
  const rows = document.querySelectorAll('.result-table-list tbody tr');
  const checkboxes = document.querySelectorAll('.result-table-list tbody input.cbItem');
  const results = Array.from(rows).map((row, i) => {
    const titleLink = row.querySelector('td.name a.fz14');
    const authors = Array.from(row.querySelectorAll('td.author a.KnowledgeNetLink') || []).map(a => a.innerText?.trim());
    const journal = row.querySelector('td.source a')?.innerText?.trim() || '';
    const date = row.querySelector('td.date')?.innerText?.trim() || '';
    const citations = row.querySelector('td.quote')?.innerText?.trim() || '';
    const downloads = row.querySelector('td.download')?.innerText?.trim() || '';
    return {
      n: i + 1,
      title: titleLink?.innerText?.trim() || '',
      href: titleLink?.href || '',
      exportId: checkboxes[i]?.value || '',
      authors: authors.join('; '),
      journal,
      date,
      citations,
      downloads
    };
  });

  return {
    query,
    total: document.querySelector('.pagerTitleCell')?.innerText?.match(/([\d,]+)/)?.[1] || '0',
    page: document.querySelector('.countPageMark')?.innerText || '1/1',
    results
  };
}
```

### 3. Report

Present results as a numbered list:

```
Searched CNKI for "$ARGUMENTS": found {total} results (page {page}).

1. {title}
   Authors: {authors} | Journal: {journal} | Date: {date}
   Citations: {citations} | Downloads: {downloads}

2. ...
```

### 4. Follow-up: navigate to a paper

When the user wants to open or download a specific paper, use `navigate_page` with the result's `href` URL directly — do NOT click the link (clicking opens a new tab and wastes 3 extra tool calls for tab management).

## Captcha detection

Check `#tcaptcha_transform_dy` element's `getBoundingClientRect().top >= 0`.
Tencent captcha SDK preloads DOM at `top: -1000000px` (off-screen, not active).
Only return `error: 'captcha'` when `top >= 0` (actually visible to user).

## Verified selectors

| Element | Selector | Notes |
|---------|----------|-------|
| Search input | `input.search-input` | id=`txt_search`, placeholder "中文文献、外文文献" |
| Search button | `input.search-btn` | type="button" |
| Result count | `.pagerTitleCell` | text "共找到 X 条结果" |
| Page indicator | `.countPageMark` | text "1/300" |
| Result rows | `.result-table-list tbody tr` | Each row = one paper |
| Title link | `td.name a.fz14` | Paper title with href |
| Authors | `td.author a.KnowledgeNetLink` | Author name links |
| Journal | `td.source a` | Journal/source link |
| Date | `td.date` | Publication date text |
| Citations | `td.quote` | Citation count |
| Downloads | `td.download` | Download count |

## Batch export to Zotero

When user wants to save results to Zotero, use batch export directly from the results page — **do NOT navigate to each detail page**. The `exportId` in results equals the detail page's `#export-id`. Call `cnki-export` skill with batch mode (Step 1B). See cnki-export SKILL.md for details.

## Tool calls: 2 (navigate + evaluate_script)
