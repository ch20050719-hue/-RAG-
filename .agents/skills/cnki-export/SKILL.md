---
name: cnki-export
description: Export paper from CNKI and push to Zotero, or save as RIS file. Use when user wants to save a paper to Zotero or export citation data.
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



# CNKI Export & Zotero Integration

Export paper citation data from CNKI and push directly to Zotero, or save as RIS file.

## Arguments

- `zotero` (only when explicitly requested) — push to Zotero desktop via local API
- `ris` — save as .ris file
- `gb` (default) — output GB/T 7714 citation text
- Optionally include a paper URL

## Mode Selection

Choose the right mode based on context:

| Context | Mode | Tool calls |
|---------|------|-----------|
| On a paper detail page | Single export (Step 1A) | gb: 1 evaluate; explicit zotero: evaluate + Python |
| On a search results page, export selected citations | **Batch export (Step 1B)** | gb: 1 evaluate; explicit zotero: evaluate + Python |
| Need to search then export citations | Use cnki-search first, then batch export | gb: search plus citation read |

**Always prefer batch export (1B) when multiple papers need saving.** It avoids navigating to each detail page (saves ~3 calls per paper).

## Steps

### 1A. Single export: from paper detail page

Use `mcp__chrome_devtools__evaluate_script`:

```javascript
async () => {
  const url = document.querySelector('#export-url')?.value;
  const params = document.querySelector('#export-id')?.value;
  const uniplatform = new URLSearchParams(window.location.search).get('uniplatform') || 'NZKPT';
  if (!url || !params) return { error: 'Not on a paper detail page' };

  const resp = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: new URLSearchParams({ filename: params, displaymode: 'GBTREFER,elearning,EndNote', uniplatform })
  });
  const data = await resp.json();
  if (data.code !== 1) return { error: data.msg };

  const result = {};
  for (const item of data.data) {
    result[item.mode] = item.value[0];
  }

  const body = document.body.innerText;
  result.pageUrl = window.location.href;
  result.issn = body.match(/ISSN[：:]\s*(\S+)/)?.[1] || '';
  result.dbcode = document.querySelector('#paramdbcode')?.value || '';
  result.dbname = document.querySelector('#paramdbname')?.value || '';
  result.filename = document.querySelector('#paramfilename')?.value || '';

  return result;
}
```

### 1B. Batch export: from search results page (PREFERRED for multiple papers)

On any CNKI search results page, extract checkbox values and call the export API directly — **no need to navigate to detail pages**.

Key discovery: `input.cbItem` checkbox `value` === detail page `#export-id` (same encrypted ID).

Use `mcp__chrome_devtools__evaluate_script`:

```javascript
async () => {
  const API_URL = 'https://kns.cnki.net/dm8/API/GetExport';

  // Get all checkbox values (= export encrypted IDs)
  const checkboxes = document.querySelectorAll('.result-table-list tbody input.cbItem');
  const rows = document.querySelectorAll('.result-table-list tbody tr');

  if (checkboxes.length === 0) return { error: 'No results on page' };

  const allPapers = [];
  for (let i = 0; i < checkboxes.length; i++) {
    const exportId = checkboxes[i].value;
    const paperUrl = rows[i]?.querySelector('td.name a.fz14')?.href || '';

    const resp = await fetch(API_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: new URLSearchParams({ filename: exportId, displaymode: 'GBTREFER,elearning,EndNote', uniplatform: 'NZKPT' })
    });
    const data = await resp.json();
    if (data.code === 1) {
      const result = {};
      for (const item of data.data) { result[item.mode] = item.value[0]; }
      result.pageUrl = paperUrl;
      // Extract ISSN from ENDNOTE %@ field
      const issnMatch = result.ENDNOTE?.match(/%@\s*([^\s<]+)/);
      result.issn = issnMatch ? issnMatch[1] : '';
      result.dbcode = 'CJFQ';
      result.dbname = '';
      result.filename = '';
      allPapers.push(result);
    } else {
      allPapers.push({pageUrl:paperUrl,error:data.msg || "Citation export failed"});
    }
  }

  return allPapers; // JSON array, directly writable to file for Python script
}
```

**To export only specific papers** (e.g. #1, #3, #5), filter by index:

```javascript
// Replace the for loop condition:
const indices = [0, 2, 4]; // 0-indexed: papers #1, #3, #5
for (let i = 0; i < checkboxes.length; i++) {
  if (!indices.includes(i)) continue;
  // ... rest same
}
```

### 2. Output citations or push to Zotero

For default `gb` mode, return the `GBTREFER` citation text and stop here. For `ris` mode, save the returned EndNote/RIS citation data in the user-approved directory. Run the following Zotero script only when the user explicitly requests Zotero.

Save the export data (single object or JSON array) to a temp file, then run the Python script:

```bash
python "E:/codes/.agents/skills/cnki-export/scripts/push_to_zotero.py" F:/论文方向/大模型+RAG知识库/.local/tmp/cnki-setup/papers.json
```

The Python script handles both single paper `{}` and batch `[{}, {}, ...]` JSON input.

- UTF-8 encoding (avoids Windows encoding issues)
- Parsing ELEARNING format into Zotero item fields
- Calling `POST http://127.0.0.1:23119/connector/saveItems`
- Returns: 201 = success, 500 = error, 0 = Zotero not running

### 3. Report result

For `gb`, output the paper title, authors, publication year, verified detail URL and the returned GB/T 7714 citation. Report any failed citation reads per paper. The following Zotero success templates apply only after an explicitly requested Zotero write has succeeded.

Single:
```
已将论文添加到 Zotero:
  标题: {title}
  作者: {authors}
  期刊: {journal}

GB/T 7714 引用: {gbt_citation}
```

Batch:
```
已批量添加 {count} 篇论文到 Zotero:
  1. {title1} ({journal1})
  2. {title2} ({journal2})
  ...
```

## Export API Reference

| Parameter | Value | Source |
|-----------|-------|--------|
| API URL | `https://kns.cnki.net/dm8/API/GetExport` | Fixed, works from any page |
| filename | Encrypted ID | Detail page: `#export-id`; Results page: `input.cbItem` value |
| displaymode | `GBTREFER,elearning,EndNote` | Comma-separated modes |
| uniplatform | `NZKPT` | Required |

## Verified selectors

| Element | Selector | Page |
|---------|----------|------|
| Export URL | `#export-url` | Detail page only |
| Export ID | `#export-id` | Detail page only |
| Checkbox (= export ID) | `input.cbItem` | Search results page |
| Result rows | `.result-table-list tbody tr` | Search results page |
| Title link | `td.name a.fz14` | Search results page |

## Zotero API Reference

```
POST http://127.0.0.1:23119/connector/saveItems
Content-Type: application/json
X-Zotero-Connector-API-Version: 3
```

**Response:** 201 = created, 500 = error
**Collection:** Saves to Zotero's currently selected collection.

Query collections:
```bash
python "E:/codes/.agents/skills/cnki-export/scripts/push_to_zotero.py" --list
```

## Important Notes

- **Windows encoding in zotero mode:** Use the Python helper for Chinese JSON; gb mode returns citation text directly without a Python or Zotero requirement
- **In explicitly requested zotero mode, Zotero must be running:** `localhost:23119` requires Zotero desktop in background
- **Chinese authors:** Use `name` field (single field, not split), `creatorType: "author"`
- **Batch export saves ~90% tool calls:** 9 papers: 33 calls → 3 calls
- **CNKI Export API:** `filename` must be encrypted ID (`#export-id` or `input.cbItem` value), NOT `#paramfilename`
