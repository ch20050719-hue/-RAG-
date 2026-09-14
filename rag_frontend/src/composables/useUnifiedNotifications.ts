import { ref, computed, readonly } from 'vue'
import { notificationsApi, type Notification as GeneralNotification } from '@/api/notifications'
import { groupChatApi } from '@/api/group-chat'
import { ElMessage } from 'element-plus'

export type NotificationCategory = 'all' | 'system' | 'task' | 'chat'

export interface UnifiedNotification {
  id: string
  category: NotificationCategory
  title: string
  message: string
  icon: string
  iconColor: string
  bgColor: string
  isRead: boolean
  isArchived?: boolean
  priority: 'low' | 'medium' | 'high' | 'urgent'
  actionUrl?: string
  metadata?: Record<string, any>
  createdAt: string
  sourceId?: string
}

export interface UnifiedStats {
  total: number
  unread: number
  today: number
  byCategory: Record<NotificationCategory, number>
  byPriority: Record<string, number>
}

const notifications = ref<UnifiedNotification[]>([])
const stats = ref<UnifiedStats>({
  total: 0,
  unread: 0,
  today: 0,
  byCategory: { all: 0, system: 0, task: 0, chat: 0 },
  byPriority: { low: 0, medium: 0, high: 0, urgent: 0 },
})
const isLoading = ref(false)
const isInitialized = ref(false)

interface LoadNotificationOptions { isArchived?: boolean }

const priorityConfig: Record<string, { iconColor: string; bgColor: string }> = {
  urgent: { iconColor: 'text-red-600', bgColor: 'bg-red-100' },
  high: { iconColor: 'text-orange-600', bgColor: 'bg-orange-100' },
  medium: { iconColor: 'text-blue-600', bgColor: 'bg-blue-100' },
  low: { iconColor: 'text-gray-600', bgColor: 'bg-gray-100' },
}

export function useUnifiedNotifications() {
  const unreadCount = computed(() => notifications.value.filter(item => !item.isRead).length)

  async function loadNotifications(category: NotificationCategory = 'all', force = false, options: LoadNotificationOptions = {}) {
    if (isLoading.value || (isInitialized.value && !force)) return
    isLoading.value = true
    try {
      const source = category === 'chat' || category === 'task' || category === 'system' ? category : undefined
      const response = await notificationsApi.listNotifications({
        page_size: 100,
        source,
        is_archived: options.isArchived ?? false,
      })
      const next = (response.notifications || [])
        .map(transformGeneralNotification)
        .sort((left, right) => new Date(right.createdAt).getTime() - new Date(left.createdAt).getTime())
      notifications.value = next
      calculateStats(next)
      isInitialized.value = true
    } catch (error: any) {
      if (error?.response?.status === 401 || error?.response?.status === 403) throw error
      console.error('Failed to load notifications:', error)
      ElMessage.error('加载通知失败')
    } finally {
      isLoading.value = false
    }
  }

  function transformGeneralNotification(item: GeneralNotification): UnifiedNotification {
    const priority = ['low', 'medium', 'high', 'urgent'].includes(item.priority || '') ? item.priority as UnifiedNotification['priority'] : 'medium'
    const source = item.source || 'system'
    const category: NotificationCategory = source === 'chat' ? 'chat' : source === 'task' ? 'task' : 'system'
    const config = priorityConfig[priority]
    const rawId = item.id || `${source}-${item.timestamp || item.created_at || Date.now()}`
    return {
      id: `general-${rawId}`,
      category,
      title: item.title,
      message: item.message || item.content || '',
      icon: item.notification_type === 'warning' ? 'AlertTriangle' : item.notification_type === 'error' ? 'XCircle' : 'Bell',
      iconColor: config.iconColor,
      bgColor: config.bgColor,
      isRead: item.is_read ?? item.read ?? false,
      isArchived: item.is_archived ?? false,
      priority,
      actionUrl: item.action_url,
      metadata: item.metadata,
      createdAt: item.created_at || item.timestamp || new Date().toISOString(),
      sourceId: rawId,
    }
  }

  function calculateStats(items = notifications.value) {
    const today = new Date().toDateString()
    stats.value = {
      total: items.length,
      unread: items.filter(item => !item.isRead).length,
      today: items.filter(item => new Date(item.createdAt).toDateString() === today).length,
      byCategory: {
        all: items.length,
        system: items.filter(item => item.category === 'system').length,
        task: items.filter(item => item.category === 'task').length,
        chat: items.filter(item => item.category === 'chat').length,
      },
      byPriority: {
        urgent: items.filter(item => item.priority === 'urgent').length,
        high: items.filter(item => item.priority === 'high').length,
        medium: items.filter(item => item.priority === 'medium').length,
        low: items.filter(item => item.priority === 'low').length,
      },
    }
  }

  function splitId(id: string): [string, string] {
    const index = id.indexOf('-')
    return index < 0 ? [id, ''] : [id.slice(0, index), id.slice(index + 1)]
  }

  async function markAsRead(id: string) {
    const item = notifications.value.find(notification => notification.id === id)
    if (!item || item.isRead) return
    const [, sourceId] = splitId(id)
    try {
      if (item.category === 'chat') await groupChatApi.markNotificationRead(sourceId)
      else await notificationsApi.markAsRead(sourceId)
      notifications.value = notifications.value.map(notification => notification.id === id ? { ...notification, isRead: true } : notification)
      calculateStats()
    } catch (error) { console.error('Failed to mark notification as read:', error) }
  }

  async function markAllAsRead(category: NotificationCategory = 'all') {
    try {
      await notificationsApi.markAllAsRead()
      notifications.value = notifications.value.map(item => category === 'all' || item.category === category ? { ...item, isRead: true } : item)
      calculateStats()
      ElMessage.success('已全部标为已读')
    } catch (error) { console.error('Failed to mark all notifications as read:', error); ElMessage.error('操作失败') }
  }

  async function deleteNotification(id: string) {
    const item = notifications.value.find(notification => notification.id === id)
    if (!item) return
    const [, sourceId] = splitId(id)
    try {
      if (item.category === 'chat') await groupChatApi.deleteNotification(sourceId)
      else await notificationsApi.deleteNotification(sourceId)
      notifications.value = notifications.value.filter(notification => notification.id !== id)
      calculateStats()
      ElMessage.success('删除成功')
    } catch (error) { console.error('Failed to delete notification:', error); ElMessage.error('删除失败') }
  }

  async function archiveNotification(id: string) {
    const [, sourceId] = splitId(id)
    try {
      await notificationsApi.archiveNotification(sourceId)
      notifications.value = notifications.value.filter(notification => notification.id !== id)
      calculateStats()
      ElMessage.success('归档成功')
    } catch (error) { console.error('Failed to archive notification:', error); ElMessage.error('归档失败') }
  }

  async function acceptInvitation(id: string) {
    try { await groupChatApi.acceptInvitation(id); notifications.value = notifications.value.filter(item => item.id !== `chat-${id}`); calculateStats(); return true }
    catch (error) { console.error('Failed to accept invitation:', error); return false }
  }

  async function declineInvitation(id: string) {
    try { await groupChatApi.declineInvitation(id); notifications.value = notifications.value.filter(item => item.id !== `chat-${id}`); calculateStats(); return true }
    catch (error) { console.error('Failed to decline invitation:', error); return false }
  }

  return {
    notifications: readonly(notifications), stats: readonly(stats), isLoading: readonly(isLoading), unreadCount,
    loadNotifications, markAsRead, markAllAsRead, archiveNotification, deleteNotification,
    acceptInvitation, declineInvitation,
    filterByCategory: (category: NotificationCategory) => category === 'all' ? notifications.value : notifications.value.filter(item => item.category === category),
    filterUnread: () => notifications.value.filter(item => !item.isRead),
    refresh: () => { isInitialized.value = false; void loadNotifications('all', true) },
  }
}
