# RAG 安全规则数据

本目录存放当前项目的安全规则知识与红队评测数据。

## 数据分层

- `rules/`：人工审核后的规范化规则卡，可进入安全规则检索索引。
- `red_team/`：红队数据集的清单、许可证和导入约束；原始攻击样本只用于离线评测，不进入普通业务 RAG。
- `sources/`：官方标准和公开数据集的原始副本或浅克隆。

## 建议索引策略

1. 生产安全规则只索引 `rules/*.jsonl`。
2. `red_team/` 仅供测试流水线读取，使用独立 collection、只读账号和隔离网络。
3. 每条规则保留 `source_url`、`source_version` 和 `license`，更新时重新审核。
4. 原始样本可能包含攻击性提示、代码或外部指令，禁止直接展示给普通用户，也禁止作为系统提示词拼接。

## 已纳入来源

- OWASP Top 10 for LLM Applications 2025：LLM 应用风险与缓解建议。
- OWASP API Security：API 认证、授权、资源限制和业务流程风险。
- NIST AI RMF Generative AI Profile：生成式 AI 风险管理与治理建议。
- ETSI EN 303 645 V3.1.3：消费级 IoT 安全基线，供未来 MQTT/ESP32 链路使用。
- Microsoft BIPIA：多模态/多任务间接提示注入评测基准，MIT License。
- S-Labs prompt-injection-dataset：提示注入分类数据，按仓库许可证执行。
- iNLP-Lab multilingual-safety：多语言安全分类数据，CC BY-NC-4.0，仅研究/非商业使用。
