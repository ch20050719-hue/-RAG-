# 红队数据集导入约束

## 数据源

| 数据集 | 本地位置 | 用途 | 许可证/限制 |
|---|---|---|---|
| Microsoft BIPIA | `sources/BIPIA` | 间接提示注入评测，含 text/code/email/qa/table | MIT |
| S-Labs prompt injection dataset | `sources/S-Labs-prompt-injection-dataset` | 提示注入二分类与鲁棒性评测 | 以仓库许可证为准，导入前复核 |
| iNLP-Lab multilingual-safety | `sources/iNLP-Lab-multilingual-safety` | 多语言安全分类与中文回归 | CC BY-NC-4.0，仅研究/非商业 |

## 安全边界

- 这些样本不是业务知识，不得写入普通 RAG collection。
- 测试运行使用独立数据库、只读凭据、无外网副作用工具和固定预算。
- 测试报告只保存样本 ID、标签、规则命中、耗时和终止结果；原文按最小必要原则保留。
- 任何包含真实密钥、个人信息或可直接执行破坏动作的样本，先脱敏再进入评测。

## 建议统一字段

`sample_id, source, language, task, label, risk_category, expected_action, split, license, content_hash`

`expected_action` 仅允许：`allow`、`refuse`、`terminate`、`review`。
