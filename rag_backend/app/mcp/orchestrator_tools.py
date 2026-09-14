"""智能家居编排工具。

保留编排工具接口，底层任务只允许落到智能家居专家与场景汇总。
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from app.mcp.decorators import local_tool


@local_tool(
    description="将智能家居目标拆解为环境读取、设备控制、安全校验和场景汇总任务。",
    name="breakdown_task_to_blackboard",
    tags=["orchestrator", "smart_home", "blackboard"],
    timeout=60,
)
async def breakdown_task_to_blackboard(
    user_goal: str,
    session_id: str,
    tenant_id: str,
    required_expertise: Optional[List[str]] = None,
    priority_tasks: Optional[List[str]] = None,
    context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """创建智能家居任务 DAG。"""
    try:
        from app.multi_agent_system.task_blackboard import TaskBlackboard, TaskPriority

        allowed = {"home_butler", "environment", "device_control", "comfort", "safety"}
        requested = [item for item in (required_expertise or []) if item in allowed]
        task_types = requested or ["environment", "device_control", "safety"]
        blackboard = TaskBlackboard(session_id=session_id)
        created = []
        for index, specialty in enumerate(task_types):
            task = await blackboard.create_task(
                task_type=f"home_{specialty}",
                description=f"[{session_id}] {specialty}：{user_goal[:80]}",
                priority=TaskPriority.CRITICAL if f"home_{specialty}" in (priority_tasks or []) else TaskPriority.NORMAL,
                created_by="home_orchestrator",
                input_data={"user_goal": user_goal, "tenant_id": tenant_id, "context": context or {}},
                dependencies=[created[-1].task_id] if created else [],
                metadata={"specialty": specialty, "dag_position": index},
                tags={"smart_home", specialty},
            )
            created.append(task)
        await blackboard.write_shared_data(key="dag_root_goal", value=user_goal)
        return {
            "status": "success",
            "task_graph": {"nodes": [{"id": t.task_id, "type": t.task_type} for t in created]},
            "created_tasks": [t.to_dict() for t in created],
            "execution_order": list(range(len(created))),
            "summary": {"total_tasks": len(created), "domain": "smart_home"},
        }
    except Exception as exc:  # noqa: BLE001 - tool boundary
        return {"status": "error", "error": str(exc), "message": "智能家居任务拆解失败"}


@local_tool(
    description="收集智能家居任务结论，生成设备状态、场景执行和安全结果摘要。",
    name="summarize_final_report",
    tags=["orchestrator", "smart_home", "summary"],
    timeout=120,
)
async def summarize_final_report(
    session_id: str,
    tenant_id: str,
    user_query: str,
    report_title: Optional[str] = None,
    include_executive_summary: bool = True,
    include_recommendations: bool = True,
    format: str = "markdown",
) -> Dict[str, Any]:
    """汇总智能家居黑板结果。"""
    try:
        from app.multi_agent_system.task_blackboard import TaskBlackboard, TaskStatus

        blackboard = TaskBlackboard(session_id=session_id)
        completed = await blackboard.get_tasks_by_status(TaskStatus.COMPLETED)
        sections = []
        if include_executive_summary:
            sections.append({"section": "summary", "title": "智能家居执行摘要", "content": f"已完成 {len(completed)} 个家居任务。"})
        for task in completed:
            content = (task.output_data or {}).get("content") or (task.output_data or {}).get("response") or "无返回内容"
            sections.append({"section": task.task_type, "title": task.description, "content": content})
        if include_recommendations:
            sections.append({"section": "recommendations", "title": "安全建议", "content": "持续关注设备在线状态、执行回执和安全规则命中情况。"})
        metadata = {"title": report_title or f"智能家居任务报告：{user_query[:30]}", "generated_at": datetime.now().isoformat(), "session_id": session_id, "tenant_id": tenant_id, "format": format}
        report_text = "\n\n".join(f"## {s['title']}\n{s['content']}" for s in sections)
        return {"status": "success", "metadata": metadata, "sections": sections, "report_text": report_text, "report_content": report_text, "raw_results": {"domain": "smart_home", "task_count": len(completed)}}
    except Exception as exc:  # noqa: BLE001 - tool boundary
        return {"status": "error", "error": str(exc), "message": "智能家居结果汇总失败"}


def get_orchestrator_tools():
    return [breakdown_task_to_blackboard, summarize_final_report]
