export default {
  common: { version: '智能家居 RAG v1.0.0', ready: '就绪', newSession: '新会话', settings: '设置' },
  auth: {
    username: '用户名', email: '邮箱', password: '密码', fullName: '姓名', login: '登录', logout: '退出', register: '注册',
    loggingIn: '登录中...', registering: '注册中...', usernamePlaceholder: '输入用户名', emailPlaceholder: '输入邮箱地址',
    passwordPlaceholder: '输入密码', fullNamePlaceholder: '输入真实姓名', passwordHint: '密码至少6个字符',
    noAccount: '还没有账号？立即注册', hasAccount: '已有账号？立即登录',
    errors: { required: '所有字段都是必填的', loginFailed: '登录失败，请检查用户名和密码', registerFailed: '注册失败，请稍后重试', passwordTooShort: '密码至少6个字符' },
  },
  sidebar: {
    logo: '> 智能家居 RAG', newChat: '新会话', database: '数据库', connected: '已连接', disconnected: '已断开', model: '模型', latency: '延迟',
    recentChats: '最近对话', knowledgeBase: '知识库', selectKnowledgeBase: '选择知识库', selectKnowledgeBases: '选择知识库', knowledgeBaseName: '知识库名称',
    description: '描述', createKnowledgeBase: '创建知识库', create: '创建', cancel: '取消', selectAll: '全选', deselectAll: '取消全选',
    knowledgeBasesSelected: '已选择 {count} 个知识库', close: '收起', noKnowledgeBases: '暂无知识库', documents: '文档', totalStorage: '总存储', chunks: '分块',
    vectorDB: '向量数据库', systemMetrics: '系统指标', uptime: '运行时间', sessionId: '会话 ID', waitingForInput: '等待输入', memoryUsage: '内存使用',
  },
  chat: {
    emptyState: { title: '智能家居 RAG', subtitle: '可查询设备、读取环境或执行安全场景' },
    input: { placeholder: '输入家居指令...', disclaimer: '设备控制将经过安全校验。', status: '系统就绪', pressEnter: '按 Enter 发送' },
    loading: { scanning: '扫描设备...', querying: '检索家居知识...', generating: '生成响应...' },
    messages: { user: '[用户指令]', assistant: '[智能家居助手]', sources: '【知识来源】', doc: '文档', confidence: '置信度' },
    error: { failedToConnect: '错误：无法连接到服务器', noResponse: '错误：无法生成响应，请检查服务器连接。' },
  },
  upload: {
    title: '上传家居知识', dropzone: '拖拽文件到此处或点击选择', supportedFormats: '支持的文件格式：', clear: '清除', button: '上传文档', uploading: '上传中', pleaseSelectKB: '请先选择一个知识库',
    status: { completed: '已完成', failed: '上传失败', pending: '等待处理', parsing: '解析中', processing: '处理中' },
    info: { title: '知识处理流程：', parsing: '提取设备与场景知识', chunking: '按语义切分知识', embedding: '生成向量嵌入' },
  },
  search: {
    title: '家居知识搜索', queryLabel: '搜索查询', placeholder: '输入设备、环境或安全规则...', button: '搜索', topKLabel: '返回结果数量 (Top-K)', results: '搜索结果', score: '相似度', page: '页码', noResults: '未找到匹配结果',
    initial: { title: '家居知识搜索', subtitle: '搜索设备手册、传感器指南、场景定义和安全规则' },
  },
  documents: {
    title: '知识文档管理', refresh: '刷新', loading: '加载中', fetchError: '获取文档列表失败', size: '文件大小', type: '文件类型', uploaded: '上传时间', error: '错误信息',
    status: { completed: '已完成', failed: '处理失败', pending: '等待处理', parsing: '解析中' }, noDocuments: '暂无文档', noDocumentsSub: '请先上传家居知识文档', confirmDelete: '确认要删除这个文档吗？', delete: '删除',
  },
  nav: { chat: '对话', upload: '上传', search: '搜索', documents: '文档', editProfile: '编辑个人信息' },
  date: { justNow: '刚刚', minutesAgo: '{count} 分钟前', hoursAgo: '{count} 小时前', daysAgo: '{count} 天前' },
}
