---
name: cnki-advanced-search
description: Perform advanced search on CNKI with field filters like author, title, journal, date range, source category (SCI/EI/CSSCI/北大核心). Use when user needs precise filtered search beyond simple keywords.
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



# CNKI Advanced Search (高级检索)

Perform a filtered search on CNKI using the **old-style** advanced search interface (only interface with source category checkboxes).

## Arguments

`$ARGUMENTS` describes the search criteria in natural language. Parse it to identify:
- **Subject keywords** (主题) — default field
- **Title keywords** (篇名)
- **Keywords** (关键词)
- **Author name** (作者) — separate field `#au_1_value1`
- **Journal/source** (文献来源) — separate field `#magazine_value1`
- **Date range** (时间范围) — `#startYear` / `#endYear`
- **Source category** (来源类别：SCI, EI, 北大核心, CSSCI, CSCD)

## Steps

### 1. Navigate

Use `mcp__chrome_devtools__navigate_page` → `https://kns.cnki.net/kns/AdvSearch?classid=7NS01R8M`

### 2. Search + get results (single async evaluate_script)

Replace placeholder values with actual search criteria:

```javascript
async () => {
  // --- Config: fill in actual values ---
  const query = "KEYWORDS";          // row 1 search keywords
  const fieldType = "SU";           // SU=主题, TI=篇名, KY=关键词, TKA=篇关摘, AB=摘要
  const query2 = "";                // row 2 keywords (optional, "" to skip)
  const fieldType2 = "KY";          // row 2 field type
  const rowLogic = "AND";           // AND=并且, OR=或者, NOT=不含 (between row 1 and 2)
  const sourceTypes = [];    // any of: "SCI", "EI", "hx", "CSSCI", "CSCD" ([] = all)
  const startYear = "";             // e.g. "2020" or "" for no limit
  const endYear = "";               // e.g. "2025" or "" for no limit
  const author = "";                // author name or ""
  const journal = "";               // journal name or ""

  // --- Wait for form ---
  await new Promise((r, j) => {
    let n = 0;
    const c = () => { if (document.querySelector('#txt_1_value1')) r(); else if (n++ > 30) j('timeout'); else setTimeout(c, 500); };
    c();
  });

  // Captcha check
  const cap = document.querySelector('#tcaptcha_transform_dy');
  if (cap && cap.getBoundingClientRect().top >= 0) return { error: 'captcha' };

  const selects = Array.from(document.querySelectorAll('select')).filter(s => s.offsetParent !== null);

  // --- Source type: uncheck 全部, check targets ---
  if (sourceTypes.length > 0) {
    const gjAll = document.querySelector('#gjAll');
    if (gjAll && gjAll.checked) gjAll.click();
    for (const st of sourceTypes) {
      const cb = document.querySelector('#' + st);
      if (cb && !cb.checked) cb.click();
    }
  }

  // --- Row 1: field type + keyword ---
  selects[0].value = fieldType;
  selects[0].dispatchEvent(new Event('change', { bubbles: true }));
  const input = document.querySelector('#txt_1_value1');
  input.value = query;
  input.dispatchEvent(new Event('input', { bubbles: true }));

  // --- Row 2: field type + keyword (optional) ---
  if (query2) {
    selects[5].value = rowLogic; // row logic: AND/OR/NOT
    selects[5].dispatchEvent(new Event('change', { bubbles: true }));
    selects[6].value = fieldType2;
    selects[6].dispatchEvent(new Event('change', { bubbles: true }));
    const input2 = document.querySelector('#txt_2_value1');
    input2.value = query2;
    input2.dispatchEvent(new Event('input', { bubbles: true }));
  }

  // --- Author (optional) ---
  if (author) {
    const auInput = document.querySelector('#au_1_value1');
    if (auInput) { auInput.value = author; auInput.dispatchEvent(new Event('input', { bubbles: true })); }
  }

  // --- Journal (optional) ---
  if (journal) {
    const magInput = document.querySelector('#magazine_value1');
    if (magInput) { magInput.value = journal; magInput.dispatchEvent(new Event('input', { bubbles: true })); }
  }

  // --- Date range (optional) ---
  if (startYear) { selects[14].value = startYear; selects[14].dispatchEvent(new Event('change', { bubbles: true })); }
  if (endYear) { selects[15].value = endYear; selects[15].dispatchEvent(new Event('change', { bubbles: true })); }

  // --- Submit ---
  document.querySelector('div.search')?.click();

  // Wait for results
  await new Promise((r, j) => {
    let n = 0;
    const c = () => {
      if (document.body.innerText.includes('条结果')) r();
      else if (n++ > 40) j('timeout');
      else setTimeout(c, 500);
    };
    setTimeout(c, 2000);
  });

  // Captcha check again
  const cap2 = document.querySelector('#tcaptcha_transform_dy');
  if (cap2 && cap2.getBoundingClientRect().top >= 0) return { error: 'captcha' };

  return {
    query, fieldType, query2, fieldType2, rowLogic,
    sourceTypes, startYear, endYear, author, journal,
    total: document.querySelector('.pagerTitleCell')?.innerText?.match(/([\d,]+)/)?.[1] || '0',
    page: document.querySelector('.countPageMark')?.innerText || '1/1',
    url: location.href
  };
}
```

### 3. Report

> Advanced search: "{query}" ({fieldType}) + source: {sourceTypes} → {total} results.

## Tool calls: 2 (navigate + evaluate_script)

## Verified selectors (old-style interface)

### Form fields

| Element | Selector / Select index | Notes |
|---------|------------------------|-------|
| 行1 字段类型 | `selects[0]` | SU=主题, TI=篇名, KY=关键词, TKA=篇关摘, AB=摘要 |
| 行1 关键词 | `#txt_1_value1` | main keyword input |
| 行1 行内第二词 | `#txt_1_value2` | same-row AND/OR/NOT with first keyword |
| 行1 行内逻辑 | `selects[2]` | AND=并含, OR=或含, NOT=不含 |
| **行间逻辑** | `selects[5]` | **AND=并且, OR=或者, NOT=不含** |
| 行2 字段类型 | `selects[6]` | same options as row 1 |
| 行2 关键词 | `#txt_2_value1` | second row keyword |
| 行2 行内第二词 | `#txt_2_value2` | |
| 作者 | `#au_1_value1` | placeholder "中文名/英文名/拼音" |
| 作者单位 | `#au_1_value2` | placeholder "全称/简称/曾用名" |
| 文献来源 | `#magazine_value1` | placeholder "期刊名称/ISSN/CN" |
| 基金 | `#base_value1` | |
| 起始年 | `selects[14]` / `#startYear` | `<select>` 1915-2026 |
| 结束年 | `selects[15]` / `#endYear` | `<select>` 2026-1915 |
| 检索按钮 | `div.search` | NOT input/button |

### Source type checkboxes (来源类型)

| 来源 | Checkbox ID | Notes |
|------|-------------|-------|
| 全部期刊 | `#gjAll` | 默认勾选，选其他前需取消 |
| SCI来源期刊 | `#SCI` | value="Y" |
| EI来源期刊 | `#EI` | value="Y" |
| 北大核心期刊 | `#hx` | value="Y" |
| CSSCI | `#CSSCI` | value="Y" |
| CSCD | `#CSCD` | value="Y" |

Multiple source types can be checked simultaneously (OR logic).

### Results

| Element | Selector | Notes |
|---------|----------|-------|
| Result count | `.pagerTitleCell` | text "共找到 X 条结果" |
| Page indicator | `.countPageMark` | text "1/300" |

## Captcha detection

Check `#tcaptcha_transform_dy` element's `getBoundingClientRect().top >= 0`.

## Important Notes

- **Must use old-style URL** (`kns.cnki.net/kns/AdvSearch`). New interface (`kns8s/AdvSearch`) has NO source category checkboxes.
- The `classid=7NS01R8M` parameter ensures the correct form layout loads.
- Parse results using the installed cnki-search result extraction section; inspect the current pagination controls when more pages are needed.
