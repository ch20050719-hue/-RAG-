from fastapi import FastAPI
from starlette.requests import Request
from contextlib import asynccontextmanager
import logging
import os
from pathlib import Path
from sqlalchemy import text
from app.core.config import settings
from app.db.session import engine
from fastapi.middleware.cors import CORSMiddleware
from app.utils.logging_config import setup_logging, get_logger, LogFormat

from app.core.background_tasks import BackgroundTaskManager
from app.core.resource_manager import make_resource_manager, RedisConnectionPool

# ➕ 2. 必须导入 models 里的文件！
# 只有导入了 document，SQLAlchemy 才知道 "哦，原来有一个叫 Document 的子类要建表"
# 如果不导入这行，Base.metadata 里面是空的，就不会建表。
from app.models import tenant_settings, agent_task, custom_tool, system_settings, multi_agent_session, multi_agent_report
from app.api.v1.endpoints import document as document_router, search, chat, auth, session, knowledge, agent_trace, tool_trace, prompt_optimization, memory, knowledge_graph, logs, chat_logs, human_review, multi_agent, group_chat, tenant_settings, rate_limit, streaming, snapshot, suggestion, task_manager, agent_llm_config, agent_discovery, workflow_events, security, custom_tools, feedback, multimodal_config, home_devices
from app.api.v1.endpoints import agent_task as agent_task_endpoint
from app.api.v1.endpoints.circuit_breaker_api import router as circuit_breaker_router
from app.observability.router import router as observability_router

# 🆕 Skills 系统
from app.api.v1.endpoints.skills import router as skills_router

# 🔒 导入租户中间件
from app.middleware.tenant_middleware import TenantContextMiddleware
# 🔒 导入日志中间件
from app.middleware.logging_middleware import LoggingMiddleware
# 🔒 导入限流中间件
from app.middleware.rate_limit_middleware import RateLimitMiddleware
from app.security.interaction_safety import interaction_guard
from app.security.rule_repository import load_rules
from app.services.tenant_security_service import tenant_security

import asyncio
from app.services.group_chat_service import group_chat_ws_manager
from app.services.redis_service import get_redis_service


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger = get_logger(__name__)
    background_tasks = BackgroundTaskManager()
    app.state.background_tasks = background_tasks
    task_scheduler = None
    
    setup_logging(
        log_level="INFO",
        log_dir="logs",
        log_file="app.log",
        max_bytes=10 * 1024 * 1024,
        backup_count=5,
        enable_console=True,
        enable_file=True,
        format_type=LogFormat.DETAILED
    )
    
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    
    logger.info(f"🚀 {settings.PROJECT_NAME} 正在启动...")

    # 规则必须在接受请求前加载；失败时保持 fail-closed，避免空规则集放行高危请求。
    rules_root = Path(settings.SECURITY_RULES_DIR)
    if not rules_root.is_absolute():
        rules_root = Path(__file__).resolve().parent.parent / rules_root
    try:
        rule_snapshot = load_rules(rules_root, version=settings.SECURITY_RULES_VERSION)
        interaction_guard.configure_rules(
            rule_snapshot.rules,
            version=rule_snapshot.version,
            sha256=rule_snapshot.sha256,
        )
        app.state.security_rules = rule_snapshot
        logger.info("✅ 安全规则加载完成: version=%s files=%d rules=%d regex=%d sha256=%s",
                    rule_snapshot.version, rule_snapshot.file_count, rule_snapshot.rule_count,
                    rule_snapshot.regex_rule_count, rule_snapshot.sha256)
    except Exception:
        logger.exception("❌ 安全规则加载失败: %s", rules_root)
        if settings.SECURITY_RULES_FAIL_CLOSED:
            raise

    logger.info("正在尝试连接数据库...")
    try:
        async with engine.begin() as conn:
            await conn.execute(text("SELECT 1"))
        logger.info(f"✅ 数据库连接成功！地址: {settings.POSTGRES_SERVER}")
    except ConnectionError as e:
        logger.error(f"❌ 数据库连接失败: {e}")
        raise
    except OSError as e:
        logger.error(f"❌ 数据库网络错误: {e}")
        raise
    except Exception as e:
        logger.error(f"❌ 数据库连接未知错误: {e}")
        raise

    async with make_resource_manager() as resource_manager:
        app.state.resource_manager = resource_manager
        logger.info("✅ ResourceManager 初始化完成")
        
        await background_tasks.start("cleanup_expired_presence", cleanup_expired_presence_task())
        logger.info("✅ 在线状态清理任务已启动")

        from app.services.task_scheduler import task_scheduler
        await task_scheduler.start()
        logger.info("✅ 定时任务调度器已启动")
        
        try:
            from app.db.session import AsyncSessionLocal
            from app.services.custom_tool_service import custom_tool_service

            async with AsyncSessionLocal() as session:
                loaded_tools = await custom_tool_service.load_published_tools(session)
            logger.info(f"Loaded published custom tools: {loaded_tools}")
        except Exception as e:
            logger.warning(f"Custom tool bootstrap skipped: {e}")

        try:
            from app.a2a_protocol.initializer import initialize_a2a_protocol
            initializer, registry = await initialize_a2a_protocol()
            app.state.a2a_initializer = initializer
            app.state.a2a_registry = registry
            app.state.a2a_dispatcher = initializer.get_dispatcher()
            logger.info("✅ A2A 协议初始化完成")
        except ImportError as e:
            logger.warning(f"⚠️ A2A 协议导入失败: {e}")
        except RuntimeError as e:
            logger.warning(f"⚠️ A2A 协议运行时错误: {e}")
        except Exception as e:
            logger.warning(f"⚠️ A2A 协议初始化失败: {e}")
        
        try:
            from app.a2a_protocol import get_transport_manager
            transport_manager = await get_transport_manager()
            app.state.transport_manager = transport_manager
            logger.info("✅ A2A Transport Manager 初始化完成")
        except ImportError as e:
            logger.warning(f"⚠️ A2A Transport Manager 导入失败: {e}")
        except RuntimeError as e:
            logger.warning(f"⚠️ A2A Transport Manager 运行时错误: {e}")
        except Exception as e:
            logger.warning(f"⚠️ A2A Transport Manager 初始化失败: {e}")
        
        try:
            from app.memory_system.model_context_manager import model_context_manager
            init_success = await model_context_manager.initialize()
            if init_success:
                logger.info("✅ ModelContextManager 初始化成功 - 从 API 加载")
            else:
                cached_count = len(model_context_manager.get_all_context_limits())
                logger.info(f"✅ ModelContextManager 初始化完成 - 使用缓存 ({cached_count} 个模型)")
        except ImportError as e:
            logger.warning(f"⚠️ ModelContextManager 导入失败: {e}")
        except RuntimeError as e:
            logger.warning(f"⚠️ ModelContextManager 运行时错误: {e}")
        except Exception as e:
            logger.warning(f"⚠️ ModelContextManager 初始化失败: {e}")
        
        try:
            from app.langgraph.circuit_breaker_integration import initialize_circuit_breaker_manager
            await initialize_circuit_breaker_manager()
            logger.info("✅ CircuitBreaker Manager 初始化完成")
        except ImportError as e:
            logger.warning(f"⚠️ CircuitBreaker Manager 导入失败: {e}")
        except RuntimeError as e:
            logger.warning(f"⚠️ CircuitBreaker Manager 运行时错误: {e}")
        except Exception as e:
            logger.warning(f"⚠️ CircuitBreaker Manager 初始化失败: {e}")
        
        try:
            from app.tasks.arq_worker import ARQWorker
            worker = ARQWorker()
            await worker.initialize()
            await background_tasks.start("arq_worker", worker.run())
            app.state.arq_worker = worker
            logger.info("✅ ARQ Worker 已启动（后台任务队列）")
        except ImportError as e:
            logger.warning(f"⚠️ ARQ Worker 导入失败: {e}")
        except RuntimeError as e:
            logger.warning(f"⚠️ ARQ Worker 运行时错误: {e}")
        except Exception as e:
            logger.warning(f"⚠️ ARQ Worker 启动失败: {e}")

        # 🆕 初始化技能系统
        try:
            from app.skills.skill_registry import SkillRegistry
            skills_dir = Path(__file__).resolve().parent.parent / "skills"
            count = await SkillRegistry.initialize(scan_paths=[skills_dir])
            app.state.skill_registry = SkillRegistry
            logger.info(f"✅ 技能系统初始化完成: {count} 个技能")
        except ImportError as e:
            logger.warning(f"⚠️ 技能系统导入失败: {e}")
        except RuntimeError as e:
            logger.warning(f"⚠️ 技能系统运行时错误: {e}")
        except Exception as e:
            logger.warning(f"⚠️ 技能系统初始化失败: {e}")

        # 设备适配器默认使用模拟实现；显式选择 MQTT 时，连接失败应阻止
        # 应用以“看似在线”的状态启动，避免控制请求被静默丢失。
        try:
            from app.home_automation.device_tools import initialize_device_service

            app.state.home_device_service = initialize_device_service()
            logger.info("✅ 智能家居设备服务已初始化: adapter=%s", os.getenv("HOME_DEVICE_ADAPTER", "simulated"))
        except Exception:
            logger.exception("❌ 智能家居设备服务初始化失败")
            if os.getenv("HOME_DEVICE_ADAPTER", "simulated").strip().lower() == "mqtt":
                raise

        yield

        logger.info(f"🛑 {settings.PROJECT_NAME} 正在关闭...")
        try:
            from app.home_automation.device_tools import close_device_service

            close_device_service()
            logger.info("✅ 智能家居设备服务已关闭")
        except Exception:
            logger.exception("⚠️ 智能家居设备服务关闭失败")
        arq_worker = getattr(app.state, "arq_worker", None)
        if arq_worker is not None:
            arq_worker.stop()
        await background_tasks.shutdown()

    if task_scheduler is not None:
        await task_scheduler.stop()
        logger.info("✅ 定时任务调度器已停止")
    await RedisConnectionPool.close()
    await engine.dispose()
    
    logger.info("✅ 应用已成功关闭")



# ... 下面的代码保持不变 ...
app = FastAPI(title=settings.PROJECT_NAME, lifespan=lifespan)


async def _persist_interaction_security_event(payload: dict) -> None:
    """只把阻断/终止事件写入租户审计表，正常请求保留在本地结构化日志。"""
    if payload.get("event") not in {"blocked", "terminated"}:
        return
    await tenant_security.log_security_event(
        event_type=f"interaction_safety_{payload['event']}",
        details=payload,
        severity="critical" if payload.get("risk_level") == "critical" else "high",
        user_id=payload.get("principal_id"),
        tenant_id=payload.get("tenant_id"),
    )


interaction_guard.audit_sink = _persist_interaction_security_event

# 🔧 测试端点 - 用于诊断请求是否到达
from fastapi import UploadFile, File

@app.post("/debug/test-upload")
async def test_upload_debug(file: UploadFile = File(...)):
    """测试端点 - 验证请求是否到达"""
    import time
    logger.info(f"🔧 [TEST-UPLOAD] 收到请求! 文件: {file.filename}, 大小: {file.size}")
    return {
        "status": "ok",
        "filename": file.filename,
        "size": file.size,
        "timestamp": time.time()
    }

@app.get("/debug/ping")
async def ping():
    """简单的 ping 端点"""
    import time
    return {"pong": True, "timestamp": time.time()}

# 添加租户上下文中间件
# 注意：中间件按注册顺序反向执行，所以 TenantContextMiddleware 在 CORSMiddleware 之前
app.add_middleware(TenantContextMiddleware)

# 👇 添加日志中间件（记录所有API请求）
app.add_middleware(LoggingMiddleware)

# 👇 添加限流中间件（API限流保护）
app.add_middleware(RateLimitMiddleware)

# 👇 配置 CORS 中间件（必须在最后添加，使其最先执行）
_cors_origins = [origin.strip() for origin in settings.CORS_ALLOWED_ORIGINS.split(",") if origin.strip()]
if not _cors_origins or "*" in _cors_origins:
    raise RuntimeError("CORS_ALLOWED_ORIGINS must contain explicit origins; wildcard is forbidden")
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept", "X-API-Key", "Last-Event-ID"],
)


app.include_router(auth.router, prefix="/api/v1/auth", tags=["Auth"]) # 👈 注册
app.include_router(rate_limit.router, prefix="/api/v1", tags=["Rate Limit Management"])
app.include_router(streaming.router, prefix="/api/v1", tags=["Streaming Enhancement"])
app.include_router(snapshot.router, prefix="/api/v1", tags=["Session Snapshots"])
app.include_router(suggestion.router, prefix="/api/v1", tags=["Suggestion"])

app.include_router(document_router.router, prefix="/api/v1/documents", tags=["Documents"])
app.include_router(search.router, prefix="/api/v1/search", tags=["Search"])
#挂载聊天接口
app.include_router(chat.router, prefix="/api/v1/chat", tags=["Chat"])
app.include_router(home_devices.router, prefix="/api/v1/home", tags=["Home Automation"])

# app.router.include_router(auth.router, prefix="/auth", tags=["Auth"]) # 👈 新增这行

app.include_router(session.router, prefix="/api/v1/sessions", tags=["Session"]) # 🆕
app.include_router(knowledge.router, prefix="/api/v1/knowledge", tags=["Knowledge Base"]) # 🆕
app.include_router(agent_trace.router, prefix="/api/v1/agent_trace", tags=["Agent Trace"]) # 🆕 Agent 追踪
app.include_router(agent_trace.router, prefix="/api/v1/agent-trace", tags=["Agent Trace"]) # 兼容前端 hyphen 路径
app.include_router(agent_discovery.router, prefix="/api/v1/agent-discovery", tags=["Agent Discovery"]) # 🆕 Agent 发现与追踪
app.include_router(custom_tools.router, prefix="/api/v1/custom-tools", tags=["Custom Tools"])
app.include_router(tool_trace.router, prefix="/api/v1/tool_trace", tags=["Tool Trace"]) # 🆕 工具追踪
app.include_router(tool_trace.router, prefix="/api/v1/tool-trace", tags=["Tool Trace"]) # 兼容前端 hyphen 路径
app.include_router(prompt_optimization.router, prefix="/api/v1/prompt", tags=["Prompt Optimization"]) # 🆕 Prompt 优化
app.include_router(memory.router, prefix="/api/v1/memory", tags=["Memory System"]) # 🆕 记忆系统
app.include_router(knowledge_graph.router, prefix="/api/v1/knowledge_graph", tags=["Knowledge Graph"]) # 🆕 知识图谱
app.include_router(logs.router, prefix="/api/v1/logs", tags=["Logging System"]) # 🆕 日志系统
app.include_router(chat_logs.router, prefix="/api/v1/chat-logs", tags=["Chat Logs"]) # 🆕 对话日志
app.include_router(human_review.router, prefix="/api/v1/human-review", tags=["Human Review"]) # 🆕 人工审核
app.include_router(multi_agent.router, prefix="/api/v1/multi-agent", tags=["Multi-Agent System"]) # 🆕 多智能体系统
app.include_router(security.router, prefix="/api/v1", tags=["Security Monitor"]) # 🆕 安全监控

# 用户反馈与失败案例
app.include_router(feedback.router, prefix="/api/v1", tags=["User Feedback"]) # 🆕 反馈系统 (P1)

# 多模态配置
app.include_router(multimodal_config.router, prefix="/api/v1/multimodal", tags=["Multimodal Config"]) # 🆕 多模态配置 (P0)

# 可观测性 API
app.include_router(observability_router, prefix="/api/v1", tags=["Observability"]) # 🆕 可观测性

try:
    from app.api.v1.endpoints.langsmith_api import router as langsmith_router
    app.include_router(langsmith_router, prefix="/api/v1/langsmith", tags=["LangSmith Integration"])
except ImportError as e:
    logger = get_logger(__name__)
    logger.warning(f"LangSmith API 路由未注册: {e}")

try:
    from app.api.v1.endpoints.a2a_protocol import router as a2a_router
    app.include_router(a2a_router, prefix="/api/v1", tags=["A2A Protocol"])
except ImportError as e:
    logger = get_logger(__name__)
    logger.warning(f"A2A Protocol 路由未注册: {e}")

try:
    from app.api.v1.endpoints.a2a_v1 import router as a2a_v1_router
    app.include_router(a2a_v1_router, prefix="/api/v1", tags=["A2A Protocol v1"])
    logger = get_logger(__name__)
    logger.info("✅ A2A Protocol v1 路由已注册")
except ImportError as e:
    logger = get_logger(__name__)
    logger.warning(f"A2A Protocol v1 路由未注册: {e}")

# 群聊相关路由
app.include_router(group_chat.router, prefix="/api/v1/groups", tags=["Group Chat"]) # 🆕 群聊
app.include_router(group_chat.invitation_router, prefix="/api/v1/invitations", tags=["Group Invitations"]) # 🆕 群聊邀请
app.include_router(group_chat.notification_router, prefix="/api/v1/notifications", tags=["Notifications"]) # 🆕 通知
app.include_router(group_chat.ws_router, prefix="/api/v1/ws/groups", tags=["Group Chat WebSocket"]) # 🆕 群聊 WebSocket

# 租户设置
app.include_router(tenant_settings.router, prefix="/api/v1", tags=["Tenant Settings"]) # 🆕 租户设置

# 智能体LLM配置
app.include_router(agent_llm_config.router, prefix="/api/v1/agents", tags=["Agent LLM Config"]) # 🆕 智能体LLM配置

# 任务管理
app.include_router(task_manager.router, prefix="/api/v1/task-manager", tags=["Task Manager"]) # 🆕 定时任务管理

# 工作流事件 SSE 推送
app.include_router(workflow_events.router, prefix="/api/v1", tags=["Workflow Events"]) # 🆕 工作流事件实时推送

# 工作流监控 API

# 熔断器管理 API
app.include_router(circuit_breaker_router, prefix="/api/v1", tags=["Circuit Breaker Management"]) # 🆕 熔断器管理

# Agent 任务状态 API（用于前端水合）
app.include_router(agent_task_endpoint.router, prefix="/api/v1", tags=["Agent Task Status"]) # 🆕 任务状态持久化与恢复

# 🆕 Skills 系统 API
app.include_router(skills_router)

@app.get("/")
def root():
    return {"message": "RAG Backend is Running", "docs": "/docs"}

@app.get("/health")
async def health_check(request: Request):
    """健康检查端点（增强版）"""
    from app.services.health_service import health_service
    
    # 执行健康检查
    report = await health_service.check_all(use_cache=True)
    
    # 返回健康报告
    return report.to_dict()


@app.get("/health/quick")
async def health_check_quick(request: Request):
    """快速健康检查端点（只检查关键组件）"""
    from app.services.health_service import health_service
    
    report = await health_service.check_quick()
    
    return report


@app.get("/health/{component}")
async def health_check_component(
    request: Request,
    component: str
):
    """单个组件健康检查"""
    from app.services.health_service import health_service
    
    # 检查指定的组件
    report = await health_service.check_all(
        use_cache=True,
        components=[component]
    )
    
    if not report.components:
        return {
            "status": "unknown",
            "message": f"Unknown component: {component}",
            "component": component
        }
    
    component_health = report.components[0]
    return component_health.to_dict()

@app.get("/api/health")
def api_health_check():
    """API健康检查端点"""
    return {"status": "healthy", "message": "API is running", "version": settings.VERSION if hasattr(settings, "VERSION") else "1.0.0"}

@app.get("/personal-page")
def personal_page():
    """个人页面入口"""
    from fastapi.responses import FileResponse
    from pathlib import Path
    static_path = Path(__file__).parent / "static" / "personal_page.html"
    if static_path.exists():
        return FileResponse(str(static_path))
    else:
        return {"error": "个人页面未找到"}


async def cleanup_expired_presence_task():
    """后台任务：定期清理过期的在线状态"""
    logger = get_logger(__name__)
    
    while True:
        try:
            await asyncio.sleep(60)
            
            redis_service = get_redis_service()
            if not redis_service or not redis_service.client:
                continue
            
            try:
                presence_keys = redis_service.client.keys("group:presence:*")
                
                for key in presence_keys:
                    group_id = key.split(":")[-1]
                    
                    members_data = redis_service.client.hgetall(key)
                    now = asyncio.get_event_loop().time()
                    removed_count = 0
                    
                    for user_id, data_str in members_data.items():
                        try:
                            import json
                            from datetime import datetime
                            data = json.loads(data_str)
                            last_heartbeat = data.get("timestamp", 0)
                            
                            if now - last_heartbeat > 90:
                                redis_service.client.hdel(key, user_id)
                                removed_count += 1
                                
                                await group_chat_ws_manager.broadcast_to_group(
                                    group_id,
                                    {
                                        "event": "member_offline",
                                        "data": {
                                            "user_id": user_id,
                                            "reason": "timeout",
                                            "timestamp": datetime.fromtimestamp(last_heartbeat).isoformat()
                                        }
                                    }
                                )
                        except json.JSONDecodeError:
                            logger.warning(f"无法解析用户在线状态数据: {user_id}")
                            continue
                        except (ValueError, KeyError) as e:
                            logger.warning(f"用户在线状态数据格式错误: {user_id}, {e}")
                            continue
                        except (OSError, IOError) as e:
                            logger.warning(f"处理用户在线状态IO错误: {user_id}, {e}")
                            continue
                        except Exception:
                            logger.warning(f"处理用户在线状态时发生未知错误: {user_id}")
                            continue
                    
                    if removed_count > 0:
                        logger.debug(f"清理群组 {group_id} 中 {removed_count} 个过期在线成员")
                        
            except OSError as e:
                logger.error(f"清理在线状态任务 Redis 连接错误: {e}")
                await asyncio.sleep(5)
            except RuntimeError as e:
                logger.error(f"清理在线状态任务运行时错误: {e}")
                await asyncio.sleep(5)
            except Exception as e:
                logger.error(f"清理在线状态任务出错: {e}")
                await asyncio.sleep(5)
                
        except asyncio.CancelledError:
            logger.info("在线状态清理任务已停止")
            break
        except Exception as e:
            logger.error(f"在线状态清理任务异常: {e}")
            await asyncio.sleep(60)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=False)
