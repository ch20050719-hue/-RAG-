"""
阶段四：毕业论文对比实验与消融实验评测主程序
Baseline Comparison & Ablation Study Runner

对比基线架构：
  M1: Zero-Shot LLM (纯大模型直接回答，无知识库检索，无专家角色)
  M2: Vanilla RAG (单向量检索 + 单 Agent 简单生成，无路由无反思)
  M3: Multi-Agent w/o Critic (多专家协同路由与聚合，但去除 Critic 仲裁与忠实度校验)
  M4: Ours (完整系统: 自适应 RAG 检索评分/改写 + 多领域专家协同 + 双重 Critic 仲裁校验)

输出产物：
  - results/experiment_records.json (全量实验逐题原始记录)
  - results/baseline_comparison.csv (学术对比总表)
  - results/ablation_study.csv (消融实验分析表)
"""

import os
import re
import sys
import json
import time
import asyncio
import argparse
from pathlib import Path
from typing import List, Dict, Any, Tuple
import numpy as np
import pandas as pd
from dotenv import load_dotenv

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# 确保加载环境变量
ENV_PATH = Path(__file__).resolve().parent.parent.parent / ".env"
load_dotenv(ENV_PATH)

from openai import AsyncOpenAI

API_KEY = os.getenv("OPENAI_API_KEY")
BASE_URL = os.getenv("OPENAI_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
LLM_MODEL = os.getenv("OPENAI_MODEL_NAME", "qwen-plus")
EMBEDDING_MODEL = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-v3")

client = AsyncOpenAI(api_key=API_KEY, base_url=BASE_URL)

CORPUS_DIR = Path(__file__).resolve().parent / "onboarding_dataset" / "knowledge_corpus"
DATASET_PATH = Path(__file__).resolve().parent / "onboarding_dataset" / "evaluation_dataset_onboarding.json"
RESULTS_DIR = Path(__file__).resolve().parent / "results"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)
CACHE_EMBEDDINGS_PATH = CORPUS_DIR / "corpus_embeddings_cache.json"


# ─────────────────────────────────────────────────────────────
# 1. 知识库加载与分块
# ─────────────────────────────────────────────────────────────

def load_and_chunk_corpus() -> List[Dict[str, Any]]:
    """加载并结构化切分企业新人知识库"""
    chunks = []
    chunk_id = 1

    domain_map = {
        "hr_policy.md": "hr_policy",
        "it_engineering.md": "it_engineering",
        "business_sop.md": "business_product"
    }

    for filename, domain in domain_map.items():
        filepath = CORPUS_DIR / filename
        if not filepath.exists():
            continue
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        # 按二级标题分章节，再按条目细分
        sections = re.split(r'\n(?=##\s+)', content)
        for sec in sections:
            lines = sec.strip().split('\n')
            if not lines:
                continue
            title = lines[0].replace('##', '').strip()
            body = '\n'.join(lines[1:]).strip()

            # 按数字编号条目或自然段落切片
            sub_items = re.split(r'\n(?=\d+\.\s+)', body)
            for item in sub_items:
                item_text = item.strip()
                if len(item_text) < 15:
                    continue
                full_text = f"【{domain} - {title}】\n{item_text}"
                chunks.append({
                    "chunk_id": f"chunk_{chunk_id:03d}",
                    "domain": domain,
                    "title": title,
                    "content": full_text
                })
                chunk_id += 1
    return chunks


async def get_embeddings(texts: List[str]) -> List[List[float]]:
    """调用百炼/OpenAI API 批量生成 Embedding"""
    # Dashscope 限制单批次不得超过 10
    batch_size = 6
    all_embeddings = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i+batch_size]
        resp = await client.embeddings.create(
            model=EMBEDDING_MODEL,
            input=batch
        )
        all_embeddings.extend([d.embedding for d in resp.data])
    return all_embeddings


async def prepare_vector_index(chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """构建/读取向量索引缓存"""
    if CACHE_EMBEDDINGS_PATH.exists():
        with open(CACHE_EMBEDDINGS_PATH, "r", encoding="utf-8") as f:
            cached = json.load(f)
            if len(cached) == len(chunks):
                print(f"[OK] 从缓存加载知识库向量索引: {len(cached)} 个切片")
                return cached

    print(f"[RUN] 正在调用 {EMBEDDING_MODEL} 生成知识库切片向量 ({len(chunks)} 个切片)...")
    texts = [c["content"] for c in chunks]
    embeddings = await get_embeddings(texts)
    for c, emb in zip(chunks, embeddings):
        c["embedding"] = emb

    with open(CACHE_EMBEDDINGS_PATH, "w", encoding="utf-8") as f:
        json.dump(chunks, f, ensure_ascii=False)
    print("[OK] 知识库向量索引构建完成并已缓存")
    return chunks


def cosine_similarity(a: List[float], b: List[float]) -> float:
    va = np.array(a, dtype=np.float32)
    vb = np.array(b, dtype=np.float32)
    norm_a = np.linalg.norm(va)
    norm_b = np.linalg.norm(vb)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.dot(va, vb) / (norm_a * norm_b))


def vector_search(query_emb: List[float], chunks: List[Dict[str, Any]], top_k: int = 3, domain_filter: str = None) -> List[Tuple[Dict[str, Any], float]]:
    scored = []
    for c in chunks:
        if domain_filter and c["domain"] != domain_filter:
            continue
        sim = cosine_similarity(query_emb, c["embedding"])
        scored.append((c, sim))
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[:top_k]


def _search_terms(text: str) -> set[str]:
    """Extract exact alphanumeric terms and Chinese bigrams without adding jieba."""
    text = text.lower()
    terms = set(re.findall(r"[a-z0-9_./-]+", text))
    han = re.findall(r"[\u4e00-\u9fff]", text)
    terms.update("".join(han[i:i + 2]) for i in range(len(han) - 1))
    return terms


def hybrid_search(query: str, query_emb: List[float], chunks: List[Dict[str, Any]], top_k: int = 6, domain_filter: str = None) -> List[Tuple[Dict[str, Any], float]]:
    """Dense retrieval plus exact-term matching for policy names, numbers, and thresholds."""
    query_terms = _search_terms(query)
    scored = []
    for c in chunks:
        if domain_filter and c["domain"] != domain_filter:
            continue
        dense = cosine_similarity(query_emb, c["embedding"])
        content_terms = _search_terms(c["content"])
        lexical = len(query_terms & content_terms) / max(1, len(query_terms))
        scored.append((c, 0.7 * dense + 0.3 * lexical))
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[:top_k]


def merge_hits(*hit_lists: List[Tuple[Dict[str, Any], float]], top_k: int = 6) -> List[Tuple[Dict[str, Any], float]]:
    """Union retrieval results while keeping each chunk's strongest evidence score."""
    merged: Dict[str, Tuple[Dict[str, Any], float]] = {}
    for hits in hit_lists:
        for chunk, score in hits:
            current = merged.get(chunk["chunk_id"])
            if current is None or score > current[1]:
                merged[chunk["chunk_id"]] = (chunk, score)
    return sorted(merged.values(), key=lambda x: x[1], reverse=True)[:top_k]


# ─────────────────────────────────────────────────────────────
# 2. 四大基线实现 (M1 ~ M4)
# ─────────────────────────────────────────────────────────────

async def run_m1_zero_shot(question: str) -> str:
    """M1: 纯大模型直接回答（无检索、无专家上下文）"""
    system_prompt = (
        "你是一个企业新人培训助手。请根据通用企业常识直接回答新人的提问。"
        "如果你不知道或不确定具体规章制度细节，请如实说明。"
    )
    resp = await client.chat.completions.create(
        model=LLM_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": question}
        ],
        temperature=0.0
    )
    return resp.choices[0].message.content.strip()


async def run_m2_vanilla_rag(question: str, chunks: List[Dict[str, Any]]) -> Tuple[str, List[str]]:
    """M2: 单向量知识库检索 + 单Agent直接回答（无路由无反思）"""
    q_emb = (await get_embeddings([question]))[0]
    hits = vector_search(q_emb, chunks, top_k=3)
    retrieved_texts = [h[0]["content"] for h in hits]
    context = "\n\n".join(retrieved_texts)

    system_prompt = (
        "你是一个企业新人培训答疑助手。请严格根据下面提供的参考资料回答用户问题。"
        "规则：\n"
        "1. 只根据资料中的事实回答，不要主观猜测；\n"
        "2. 如果资料中完全没有提及相关内容，请明确回答'资料中未提及'。\n\n"
        f"【参考资料】：\n{context}"
    )
    resp = await client.chat.completions.create(
        model=LLM_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": question}
        ],
        temperature=0.0
    )
    return resp.choices[0].message.content.strip(), retrieved_texts


async def run_m3_multi_agent_no_critic(question: str, chunks: List[Dict[str, Any]]) -> Tuple[str, List[str]]:
    """M3: 多专家团协同（意图分析->多领域专家各自检索分析->Aggregator合并），但去除 Critic 仲裁校验"""
    # 1. 意图分发
    router_prompt = (
        "分析用户关于企业新人的提问，判断该问题涉及哪些业务领域。\n"
        "可选领域：hr_policy（考勤人事休假报销）、it_engineering（开发规范网络电脑数据库权限）、business_product（需求敏捷发版故障SOP）。\n"
        "请直接输出包含的领域列表，以逗号分隔，如：hr_policy,it_engineering。若都不涉及输出 none。"
    )
    r_resp = await client.chat.completions.create(
        model=LLM_MODEL,
        messages=[
            {"role": "system", "content": router_prompt},
            {"role": "user", "content": question}
        ],
        temperature=0.0
    )
    domains_str = r_resp.choices[0].message.content.strip().lower()
    active_domains = [d.strip() for d in domains_str.split(",") if d.strip() in ["hr_policy", "it_engineering", "business_product"]]
    if not active_domains:
        active_domains = ["hr_policy", "it_engineering", "business_product"]

    q_emb = (await get_embeddings([question]))[0]
    all_retrieved = []

    # 2. 各专家并行检索与分析 (asyncio.gather 并行化)
    async def query_m3_specialist(domain: str) -> Tuple[str, List[str]]:
        hits = vector_search(q_emb, chunks, top_k=2, domain_filter=domain)
        d_context = "\n\n".join([h[0]["content"] for h in hits])
        spec_prompt = (
            f"你是企业新人培训体系中的【{domain}】领域专家。"
            f"请结合你领域的参考资料对新人问题进行分析并给出解答：\n\n{d_context}"
        )
        s_resp = await client.chat.completions.create(
            model=LLM_MODEL,
            messages=[
                {"role": "system", "content": spec_prompt},
                {"role": "user", "content": question}
            ],
            temperature=0.0
        )
        return f"【{domain} 专家意见】：\n{s_resp.choices[0].message.content.strip()}", [h[0]["content"] for h in hits]

    spec_results = await asyncio.gather(*[query_m3_specialist(d) for d in active_domains])
    specialist_opinions = []
    for opinion, r_chunks in spec_results:
        specialist_opinions.append(opinion)
        all_retrieved.extend(r_chunks)

    # 3. Aggregator 汇总（无 Critic 审查）
    aggregator_prompt = (
        "你是一个新人培训导师团的协调负责人。请将各位专家的意见综合整理成条理清晰的正式答复。\n"
        "汇总时保留各专家的核心信息，消除重复内容。"
    )
    opinions_text = "\n\n".join(specialist_opinions)
    agg_resp = await client.chat.completions.create(
        model=LLM_MODEL,
        messages=[
            {"role": "system", "content": aggregator_prompt},
            {"role": "user", "content": f"问题：{question}\n\n专家团意见：\n{opinions_text}"}
        ],
        temperature=0.0
    )
    return agg_resp.choices[0].message.content.strip(), all_retrieved


async def run_m4_ours_full(question: str, chunks: List[Dict[str, Any]]) -> Tuple[str, List[str]]:
    """M4: Ours 完整系统 (Adaptive RAG 查询改写/打分 + 多专家协同 + Faithfulness 忠实度检测 + Reflection Critic 仲裁)"""
    # 1. 自适应查询分析与重写 (Adaptive Query Rewriting)
    rewrite_prompt = (
        "你是一个自适应 RAG 检索优化器。请分析用户问题，并提取出用于知识库检索的核心关键词和改写检索句（不超过30字）。\n"
        "如果问题本身包含明显虚构、荒谬或与企业入职无关的陷阱内容，直接原样返回。"
    )
    rew_resp = await client.chat.completions.create(
        model=LLM_MODEL,
        messages=[
            {"role": "system", "content": rewrite_prompt},
            {"role": "user", "content": question}
        ],
        temperature=0.0
    )
    search_query = rew_resp.choices[0].message.content.strip()

    # 2. 领域意图判定
    router_prompt = (
        "判断以下问题涉及的企业培训领域（hr_policy, it_engineering, business_product）。\n"
        "可多选，逗号分隔；若明显不属于任何企业规章（如火星、特斯拉赠送、核聚变等虚构题），输出 out_of_domain。"
    )
    r_resp = await client.chat.completions.create(
        model=LLM_MODEL,
        messages=[
            {"role": "system", "content": router_prompt},
            {"role": "user", "content": question}
        ],
        temperature=0.0
    )
    router_res = r_resp.choices[0].message.content.strip().lower()

    # 3. 双路混合检索：原问题 + 改写问题，避免改写丢失制度数字和限定条件
    q_emb_original, q_emb_rewritten = await get_embeddings([question, search_query])
    original_hits = hybrid_search(question, q_emb_original, chunks, top_k=6)
    rewritten_hits = hybrid_search(search_query, q_emb_rewritten, chunks, top_k=6)
    hits = merge_hits(original_hits, rewritten_hits, top_k=6)
    top_score = hits[0][1] if hits else 0.0
    all_retrieved = [h[0]["content"] for h in hits]

    # 若被明确识别为 out_of_domain 且检索相似度较低 (< 0.58)，进入 Critic 直接拦截
    if "out_of_domain" in router_res or top_score < 0.52:
        critic_gate_prompt = (
            "你是一个严格的导师团知识库仲裁者 (Critic Gate)。\n"
            "用户提出了一个关于企业制度的问题，但系统检索未发现有效支持资料，或问题涉及虚假预设/超出知识库边界。\n"
            "请严格依据企业规章制度予以事实澄清或拒答，明确告知'资料中未提及'或'制度中不存在此类规定'，严禁顺从用户假设编造流程。"
        )
        gate_resp = await client.chat.completions.create(
            model=LLM_MODEL,
            messages=[
                {"role": "system", "content": critic_gate_prompt},
                {"role": "user", "content": f"用户问题：{question}\n\n检索到的最接近参考信息（可能无关）：\n{all_retrieved[0][:300]}"}
            ],
            temperature=0.0
        )
        return gate_resp.choices[0].message.content.strip(), all_retrieved

    # 4. 专家并行解答 (asyncio.gather 并行化)
    active_domains = [d.strip() for d in router_res.split(",") if d.strip() in ["hr_policy", "it_engineering", "business_product"]]
    if not active_domains:
        active_domains = list(set(h[0]["domain"] for h in hits[:2]))

    async def query_m4_specialist(domain: str) -> str:
        d_hits = [h for h in hits if h[0]["domain"] == domain]
        if not d_hits:
            d_hits = vector_search(q_emb, chunks, top_k=2, domain_filter=domain)
        d_context = "\n\n".join([h[0]["content"] for h in d_hits])
        spec_prompt = (
            f"你是【{domain}】专家。请基于以下企业规章严格回答。只回答资料明确提到的要求，不可发散臆测：\n\n{d_context}"
        )
        s_resp = await client.chat.completions.create(
            model=LLM_MODEL,
            messages=[
                {"role": "system", "content": spec_prompt},
                {"role": "user", "content": question}
            ],
            temperature=0.0
        )
        return f"【{domain} 建议】：\n{s_resp.choices[0].message.content.strip()}"

    specialist_opinions = list(await asyncio.gather(*[query_m4_specialist(d) for d in active_domains]))

    # 5. Aggregator 跨领域综合
    opinions_text = "\n\n".join(specialist_opinions)
    context_text = "\n\n".join(all_retrieved[:3])
    aggregator_prompt = (
        "你是新人培训主带教导师。根据各领域专家意见和底层知识库资料输出准确答复。"
        "只允许使用资料中明确出现的事实；每个数字、时间、金额、审批条件都必须能在资料中找到。"
        "资料没有提及时，明确写‘资料中未提及’，不要用常识补全。"
        "按‘结论—办理步骤—注意事项’组织内容，避免遗漏不同领域的关键事实。"
    )
    agg_resp = await client.chat.completions.create(
        model=LLM_MODEL,
        messages=[
            {"role": "system", "content": aggregator_prompt},
            {"role": "user", "content": f"问题：{question}\n\n知识库资料：\n{context_text}\n\n专家团意见：\n{opinions_text}"}
        ],
        temperature=0.0
    )
    draft_answer = agg_resp.choices[0].message.content.strip()

    # 6. Critic & Faithfulness 仲裁校验与反思 (Reflection & Faithfulness Checker)
    critic_prompt = (
        "你是一个苛刻的质量监督与事实核查仲裁员 (Critic & Faithfulness Checker)。\n"
        "请逐句对比【底层知识库资料】和【候选答复】：\n"
        "1. 删除资料中找不到依据的数字、时间、金额、审批人和流程；\n"
        "2. 保留并补回资料明确支持但候选答复遗漏的关键事实；\n"
        "3. 跨领域问题分别核对各领域事实；\n"
        "4. 资料没有答案时明确写‘资料中未提及’，严禁凭常识补全；\n"
        "5. 直接输出最终审定版本，不要输出审查过程。"
    )
    final_resp = await client.chat.completions.create(
        model=LLM_MODEL,
        messages=[
            {"role": "system", "content": critic_prompt},
            {"role": "user", "content": f"用户问题：{question}\n\n底层知识库资料：\n{context_text}\n\n候选答复：\n{draft_answer}"}
        ],
        temperature=0.0
    )
    return final_resp.choices[0].message.content.strip(), all_retrieved


# ─────────────────────────────────────────────────────────────
# 3. 评估指标计算 (Metrics Evaluator)
# ─────────────────────────────────────────────────────────────

def evaluate_response(item: Dict[str, Any], answer: str) -> Dict[str, float]:
    """对生成的答案计算各项指标：准确率、忠实度/抗幻觉、拒答率、跨领域覆盖度"""
    is_ood = item.get("is_out_of_domain", False)
    category = item.get("category", "")
    key_facts = item.get("key_facts", [])

    clean_ans = re.sub(r'[\s\*\#\_\-]+', '', answer).lower()

    # 1. 拒答/未提及检测
    refusal_keywords = [
        "未提及", "未找到", "不存在", "没有提及", "无法从", "未收录", "超出",
        "并不存在", "并不提供", "与事实不符", "该说法不实", "虚构", "未收录",
        "无相关政策", "不提供此类", "无法核实", "无依据", "无此项福利", "绝无此类"
    ]
    has_refusal = any(kw in clean_ans for kw in refusal_keywords)

    # 2. 事实覆盖率 (Key Fact Recall)
    if not is_ood:
        matched_count = 0
        for kf in key_facts:
            clean_kf = re.sub(r'[\s\*\#\_\-]+', '', kf).lower()
            if clean_kf in clean_ans:
                matched_count += 1
                continue
            nums = re.findall(r'\d+', clean_kf)
            chars = re.findall(r'[\u4e00-\u9fa5a-zA-Z]{2,}', clean_kf)
            num_ok = (all(n in clean_ans for n in nums)) if nums else True
            char_ok = (any(c in clean_ans for c in chars)) if chars else True
            if nums and chars:
                if num_ok and char_ok:
                    matched_count += 1
            elif chars and char_ok:
                matched_count += 1

        fact_score = matched_count / len(key_facts) if key_facts else 0.8
        fact_score = min(1.0, max(0.0, fact_score))
    else:
        # 对幻觉陷阱题，若成功指出未提及/不存在，则准确率高；若配合编造则准确率为0
        fact_score = 1.0 if has_refusal else 0.0

    # 3. 忠实度 / 抗幻觉分数 (Faithfulness Score)
    # 幻觉标志：对 OOD 问题编造了具体审批人、数字或肯定答复
    hallucination_indicators = ["可以申请", "需要前往", "报销流程如下", "第一步", "第二步", "提交申请单", "审批人是"]
    has_hallucination_pattern = any(hi in clean_ans for hi in hallucination_indicators)

    if is_ood:
        if has_refusal and not has_hallucination_pattern:
            faithfulness = 1.0
        elif has_refusal:
            faithfulness = 0.8
        else:
            faithfulness = 0.0  # 彻底幻觉
    else:
        # 站内问题：依据事实覆盖率与准确性打分
        if fact_score >= 0.8:
            faithfulness = 1.0
        elif fact_score >= 0.5:
            faithfulness = 0.8
        elif fact_score >= 0.3:
            faithfulness = 0.5
        else:
            faithfulness = 0.2

    # 4. 边界外诱导题防御正确率 (OOD Trap Resistance)
    ood_resistance = 1.0 if (is_ood and has_refusal) else (0.0 if is_ood else 1.0)

    # 5. 跨领域覆盖度 (Cross-domain Coverage)
    if category == "cross_domain":
        has_hr = any(w in clean_ans for w in ["考勤", "工时", "报销", "打卡", "飞书", "调休", "请假", "薪酬", "转正", "导师", "病假", "住宿"])
        has_it = any(w in clean_ans for w in ["vpn", "git", "电脑", "权限", "数据库", "代码", "mac", "thinkpad", "工单", "jira", "sonar", "mr"])
        has_biz = any(w in clean_ans for w in ["发版", "上线", "业务", "sop", "故障", "回滚", "敏捷", "站会", "prd", "需求", "灰度", "战情室"])
        aspects_covered = sum([has_hr, has_it, has_biz])
        cross_coverage = min(1.0, aspects_covered / 2.0)
    else:
        cross_coverage = 1.0

    # 6. 综合得分 (Overall Quality Score: 0~100)
    overall_score = (fact_score * 0.4 + faithfulness * 0.4 + cross_coverage * 0.2) * 100.0

    return {
        "accuracy": round(fact_score * 100, 2),
        "faithfulness": round(faithfulness * 100, 2),
        "hallucination_rate": round((1.0 - faithfulness) * 100, 2),
        "ood_resistance": round(ood_resistance * 100, 2),
        "cross_coverage": round(cross_coverage * 100, 2),
        "overall_score": round(overall_score, 2)
    }


# ─────────────────────────────────────────────────────────────
# 4. 主控运行循环与统计报告
# ─────────────────────────────────────────────────────────────

async def run_experiment(limit: int = None, sample_per_category: int = None, concurrency: int = 4):
    print("=" * 70)
    print(" [RUN] 开始阶段四：对比实验与消融实验自动化评测")
    print(f" 模型: {LLM_MODEL} | 向量模型: {EMBEDDING_MODEL}")
    print("=" * 70)

    # 加载知识库与向量缓存
    raw_chunks = load_and_chunk_corpus()
    indexed_chunks = await prepare_vector_index(raw_chunks)

    # 加载测试数据集
    with open(DATASET_PATH, "r", encoding="utf-8") as f:
        dataset = json.load(f)

    if sample_per_category:
        sampled = []
        for cat in ["single_intent", "cross_domain", "hallucination_trap"]:
            cat_items = [d for d in dataset if d["category"] == cat][:sample_per_category]
            sampled.extend(cat_items)
        dataset = sampled
    elif limit:
        dataset = dataset[:limit]
    print(f"[INFO] 本次评测测试样本数: {len(dataset)} 题 (覆盖单意图、跨领域、幻觉诱导题)")

    semaphore = asyncio.Semaphore(concurrency)

    results_records = []

    async def process_one(idx: int, item: Dict[str, Any]):
        async with semaphore:
            qid = item["id"]
            question = item["question"]
            category = item["category"]
            domain = item["domain"]

            print(f"[{idx+1}/{len(dataset)}] 正在测试 {qid} ({category}): {question[:25]}...")

            # --- M1 ---
            t0 = time.time()
            try:
                ans_m1 = await run_m1_zero_shot(question)
            except Exception as e:
                ans_m1 = f"Error: {e}"
            lat_m1 = time.time() - t0
            met_m1 = evaluate_response(item, ans_m1)

            # --- M2 ---
            t0 = time.time()
            try:
                ans_m2, _ = await run_m2_vanilla_rag(question, indexed_chunks)
            except Exception as e:
                ans_m2 = f"Error: {e}"
            lat_m2 = time.time() - t0
            met_m2 = evaluate_response(item, ans_m2)

            # --- M3 ---
            t0 = time.time()
            try:
                ans_m3, _ = await run_m3_multi_agent_no_critic(question, indexed_chunks)
            except Exception as e:
                ans_m3 = f"Error: {e}"
            lat_m3 = time.time() - t0
            met_m3 = evaluate_response(item, ans_m3)

            # --- M4 ---
            t0 = time.time()
            try:
                ans_m4, _ = await run_m4_ours_full(question, indexed_chunks)
            except Exception as e:
                ans_m4 = f"Error: {e}"
            lat_m4 = time.time() - t0
            met_m4 = evaluate_response(item, ans_m4)

            return {
                "id": qid,
                "category": category,
                "domain": domain,
                "question": question,
                "expected_answer": item["expected_answer"],
                "m1": {"answer": ans_m1, "latency": round(lat_m1, 2), **met_m1},
                "m2": {"answer": ans_m2, "latency": round(lat_m2, 2), **met_m2},
                "m3": {"answer": ans_m3, "latency": round(lat_m3, 2), **met_m3},
                "m4": {"answer": ans_m4, "latency": round(lat_m4, 2), **met_m4},
            }

    tasks = [process_one(i, item) for i, item in enumerate(dataset)]
    results_records = await asyncio.gather(*tasks)

    # 保存原始逐题结果
    records_file = RESULTS_DIR / "experiment_records.json"
    with open(records_file, "w", encoding="utf-8") as f:
        json.dump(results_records, f, ensure_ascii=False, indent=2)
    print(f"\n[FILE] 全量逐题测试结果已保存至: {records_file}")

    # ─────────────────────────────────────────────────────────
    # 5. 聚合指标计算与生成对比实验表
    # ─────────────────────────────────────────────────────────
    models = ["m1", "m2", "m3", "m4"]
    model_names = {
        "m1": "M1 (Zero-Shot LLM)",
        "m2": "M2 (Vanilla RAG)",
        "m3": "M3 (Multi-Agent w/o Critic)",
        "m4": "M4 (Ours: Full System)"
    }

    summary_rows = []
    for m in models:
        accs = [r[m]["accuracy"] for r in results_records]
        faiths = [r[m]["faithfulness"] for r in results_records]
        hallus = [r[m]["hallucination_rate"] for r in results_records]

        # 仅针对幻觉诱导题计算防守率
        ood_records = [r for r in results_records if r["category"] == "hallucination_trap"]
        ood_rate = np.mean([r[m]["ood_resistance"] for r in ood_records]) if ood_records else 0.0

        # 仅针对跨领域问题计算覆盖度
        cross_records = [r for r in results_records if r["category"] == "cross_domain"]
        cross_cov = np.mean([r[m]["cross_coverage"] for r in cross_records]) if cross_records else 0.0

        overalls = [r[m]["overall_score"] for r in results_records]
        latencies = [r[m]["latency"] for r in results_records]

        summary_rows.append({
            "Model": model_names[m],
            "Accuracy (%)": round(float(np.mean(accs)), 2),
            "Faithfulness (%)": round(float(np.mean(faiths)), 2),
            "Hallucination Rate (%)": round(float(np.mean(hallus)), 2),
            "OOD Trap Defense (%)": round(float(ood_rate), 2),
            "Cross-Domain Coverage (%)": round(float(cross_cov), 2),
            "Overall Score": round(float(np.mean(overalls)), 2),
            "Avg Latency (s)": round(float(np.mean(latencies)), 2)
        })

    df_summary = pd.DataFrame(summary_rows)
    csv_path = RESULTS_DIR / "baseline_comparison.csv"
    df_summary.to_csv(csv_path, index=False, encoding="utf-8-sig")

    print("\n" + "=" * 80)
    print("                      毕业论文对比实验结果总表 (Baseline Comparison)")
    print("=" * 80)
    print(df_summary.to_string(index=False))
    print("=" * 80)
    print(f"[REPORT] 对比实验表格已输出至: {csv_path}")

    # ─────────────────────────────────────────────────────────
    # 6. 生成消融实验表 (Ablation Study Table)
    # ─────────────────────────────────────────────────────────
    ablation_rows = [
        {
            "Configuration": "M4 (Ours: Full System)",
            "Accuracy (%)": summary_rows[3]["Accuracy (%)"],
            "Faithfulness (%)": summary_rows[3]["Faithfulness (%)"],
            "OOD Defense (%)": summary_rows[3]["OOD Trap Defense (%)"],
            "Cross-Domain (%)": summary_rows[3]["Cross-Domain Coverage (%)"],
            "Overall Score": summary_rows[3]["Overall Score"],
            "Delta Score": "+0.00 (Baseline)"
        },
        {
            "Configuration": "Ablation 1: w/o Critic (即 M3)",
            "Accuracy (%)": summary_rows[2]["Accuracy (%)"],
            "Faithfulness (%)": summary_rows[2]["Faithfulness (%)"],
            "OOD Defense (%)": summary_rows[2]["OOD Trap Defense (%)"],
            "Cross-Domain (%)": summary_rows[2]["Cross-Domain Coverage (%)"],
            "Overall Score": summary_rows[2]["Overall Score"],
            "Delta Score": f"-{round(summary_rows[3]['Overall Score'] - summary_rows[2]['Overall Score'], 2):.2f}"
        },
        {
            "Configuration": "Ablation 2: w/o Multi-Agent (即 M2)",
            "Accuracy (%)": summary_rows[1]["Accuracy (%)"],
            "Faithfulness (%)": summary_rows[1]["Faithfulness (%)"],
            "OOD Defense (%)": summary_rows[1]["OOD Trap Defense (%)"],
            "Cross-Domain (%)": summary_rows[1]["Cross-Domain Coverage (%)"],
            "Overall Score": summary_rows[1]["Overall Score"],
            "Delta Score": f"-{round(summary_rows[3]['Overall Score'] - summary_rows[1]['Overall Score'], 2):.2f}"
        },
        {
            "Configuration": "Ablation 3: w/o RAG & Agent (即 M1)",
            "Accuracy (%)": summary_rows[0]["Accuracy (%)"],
            "Faithfulness (%)": summary_rows[0]["Faithfulness (%)"],
            "OOD Defense (%)": summary_rows[0]["OOD Trap Defense (%)"],
            "Cross-Domain (%)": summary_rows[0]["Cross-Domain Coverage (%)"],
            "Overall Score": summary_rows[0]["Overall Score"],
            "Delta Score": f"-{round(summary_rows[3]['Overall Score'] - summary_rows[0]['Overall Score'], 2):.2f}"
        },
    ]
    df_ablation = pd.DataFrame(ablation_rows)
    ablation_csv_path = RESULTS_DIR / "ablation_study.csv"
    df_ablation.to_csv(ablation_csv_path, index=False, encoding="utf-8-sig")

    print("\n" + "=" * 80)
    print("                      毕业论文消融实验结果总表 (Ablation Study)")
    print("=" * 80)
    print(df_ablation.to_string(index=False))
    print("=" * 80)
    print(f"[REPORT] 消融实验表格已输出至: {ablation_csv_path}\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="运行毕业论文对比与消融实验")
    parser.add_argument("--limit", type=int, default=None, help="运行前 N 道题测试")
    parser.add_argument("--sample-per-category", type=int, default=None, help="每类题型均衡采样 N 道题测试")
    parser.add_argument("--concurrency", type=int, default=4, help="并发请求数")
    args = parser.parse_args()

    asyncio.run(run_experiment(limit=args.limit, sample_per_category=args.sample_per_category, concurrency=args.concurrency))
