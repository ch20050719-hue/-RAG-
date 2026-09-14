"""文档领域标识。

新人培训领域先复用通用 Auto-Merging 分块器，保留领域标签供路由和检索过滤使用。
"""

SMART_HOME_DOMAINS = ("smart_home",)
SUPPORTED_DOCUMENT_DOMAINS = (*SMART_HOME_DOMAINS, "general")
