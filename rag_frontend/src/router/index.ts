import { createRouter, createWebHistory } from 'vue-router'
import type { RouteRecordRaw } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const routes: RouteRecordRaw[] = [
  {
    path: '/login',
    name: 'login',
    component: () => import('@/views/ModernLoginView.vue'),
    meta: { requiresAuth: false },
  },
  {
    path: '/register',
    name: 'register',
    component: () => import('@/views/ModernRegisterView.vue'),
    meta: { requiresAuth: false },
  },
  {
    path: '/',
    name: 'chat',
    component: () => import('@/views/MultiAgentChatView.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/multi-agent',
    redirect: '/',
    meta: { requiresAuth: true },
  },
  {
    path: '/home-devices',
    name: 'home-devices',
    component: () => import('@/views/HomeDevicesView.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/search',
    name: 'search',
    component: () => import('@/views/ModernSearchView.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/documents',
    name: 'documents',
    component: () => import('@/views/ModernDocumentsView.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/knowledge',
    name: 'knowledge',
    component: () => import('@/views/KnowledgeManagementView.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/knowledge/:id',
    name: 'knowledge-detail',
    component: () => import('@/views/ModernKnowledgeDetailView.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/knowledge-graph',
    name: 'knowledge-graph',
    component: () => import('@/views/KnowledgeGraphView.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/logs',
    name: 'logs',
    component: () => import('@/views/LogsView.vue'),
    meta: { requiresAuth: true, requiresAdmin: true },
  },
  {
    path: '/chat-logs',
    name: 'chat-logs',
    component: () => import('@/views/ChatLogsView.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/profile',
    name: 'profile',
    component: () => import('@/views/ModernProfileView.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/group-chat',
    name: 'group-chat',
    component: () => import('@/views/GroupChatView.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/analytics',
    name: 'analytics',
    component: () => import('@/views/AnalyticsDashboard.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/agent-center',
    name: 'agent-center',
    component: () => import('@/views/AgentCenterView.vue'),
    meta: { requiresAuth: true, requiresAdmin: true },
  },
  {
    path: '/custom-tools',
    name: 'custom-tools',
    component: () => import('@/views/CustomToolsView.vue'),
    meta: { requiresAuth: true, requiresAdmin: true },
  },
  {
    path: '/agent-monitor',
    redirect: '/agent-center',
    name: 'agent-monitor',
    meta: { requiresAuth: true, requiresAdmin: true },
  },
  {
    path: '/agent-trace',
    redirect: '/agent-center',
    name: 'agent-trace',
    meta: { requiresAuth: true, requiresAdmin: true },
  },
  {
    path: '/intent-debug',
    name: 'intent-debug',
    component: () => import('@/views/IntentClassifierDebugView.vue'),
    meta: { requiresAuth: true, requiresAdmin: true },
  },
  {
    path: '/security-audit',
    name: 'security-audit',
    component: () => import('@/views/SecurityAuditView.vue'),
    meta: { requiresAuth: true, requiresAdmin: true },
  },
  {
    path: '/knowledge-graph-editor',
    name: 'knowledge-graph-editor',
    component: () => import('@/views/KnowledgeGraphEditorView.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/task-management',
    name: 'task-management',
    component: () => import('@/views/TaskManagementView.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/notifications',
    name: 'notifications',
    component: () => import('@/views/NotificationCenterView.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/animation-demo',
    name: 'animation-demo',
    component: () => import('@/views/AnimationDemoView.vue'),
    meta: { requiresAuth: true },
  },
  // === 模型配置中心（对话/向量/重排）· 管理员 ===
  {
    path: '/settings/models',
    name: 'model-settings',
    component: () => import('@/views/ModelSettingsView.vue'),
    meta: { requiresAuth: true, requiresAdmin: true },
  },
  // === P0 新增: 多模态配置 + 用量 ===
  {
    path: '/settings/multimodal',
    name: 'multimodal-settings',
    component: () => import('@/views/MultiModalSettingsView.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/multimodal-usage',
    name: 'multimodal-usage',
    component: () => import('@/views/MultiModalUsageView.vue'),
    meta: { requiresAuth: true },
  },
  // === P1 反馈管理后台 ===
  {
    path: '/feedback-management',
    name: 'feedback-management',
    component: () => import('@/views/FeedbackManagementView.vue'),
    meta: { requiresAuth: true, requiresAdmin: true },
  },
  {
    path: '/failure-analysis',
    name: 'failure-analysis',
    component: () => import('@/views/FailureAnalysisView.vue'),
    meta: { requiresAuth: true, requiresAdmin: true },
  },
  {
    path: '/:pathMatch(.*)*',
    name: 'not-found',
    redirect: '/',
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

// Navigation guard for authentication
router.beforeEach((to, from, next) => {
  try {
    const authStore = useAuthStore()
    const isAdmin = authStore.isAdmin || localStorage.getItem('rag_user_role') === 'admin'

    if (to.meta.requiresAuth && !authStore.isLoggedIn) {
      next('/login')
    } else if (to.name === 'login' && authStore.isLoggedIn) {
      next('/')
    } else if (to.meta.requiresAdmin && !isAdmin) {
      next('/')
    } else {
      next()
    }
  } catch (error) {
    console.error('Navigation guard error:', error)
    next('/login')
  }
})

router.onError((error) => {
  console.error('Router error:', error)
})

export default router
