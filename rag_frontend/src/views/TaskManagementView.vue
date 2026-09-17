<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Play, Pause, Trash2, Plus, RefreshCw } from 'lucide-vue-next'
import { taskManagerApi, type ScheduledTask } from '@/api/task-manager'
import { homeApi, type HomeDevice } from '@/api/home'

type Frequency = ScheduledTask['frequency']

interface TaskForm {
  name: string
  description: string
  task_type: ScheduledTask['task_type']
  frequency: Frequency
  next_run_time: string
  scenario: string
  device_id: string
  device_state: 'on' | 'off'
  reminder_enabled: boolean
  reminder_time: string
  reminder_before_minutes: number
  deadline: string
  repeat_until: string
  notification_channels: string[]
}

const emptyForm = (): TaskForm => ({
  name: '晚间回家场景', description: '按计划执行智能家居场景', task_type: 'home_scenario', frequency: 'once',
  next_run_time: '', scenario: 'away', device_id: '', device_state: 'on', reminder_enabled: true, reminder_time: '', reminder_before_minutes: 10,
  deadline: '', repeat_until: '', notification_channels: ['in_app']
})

const tasks = ref<ScheduledTask[]>([])
const devices = ref<HomeDevice[]>([])
const loading = ref(false)
const showCreate = ref(false)
const form = ref<TaskForm>(emptyForm())
const isRecurring = computed(() => form.value.frequency !== 'once')
const isScenarioTask = computed(() => form.value.task_type === 'home_scenario')
const controllableDevices = computed(() => devices.value.filter(device => ['light', 'fan'].includes(device.device_type) && device.online))

const frequencyLabels: Record<Frequency, string> = { once: '一次性', daily: '每天', weekly: '每周', monthly: '每月', quarterly: '每季度', yearly: '每年' }
const statusLabels: Record<ScheduledTask['status'], string> = { pending: '待执行', running: '执行中', completed: '已完成', failed: '失败', cancelled: '已取消', expired: '已过期' }
const deviceTypeLabels: Record<string, string> = { light: '灯', fan: '风扇' }

function formatDate(value?: string | null) {
  if (!value) return '—'
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString('zh-CN', { hour12: false })
}

function toUtcIso(value: string) { return value ? new Date(value).toISOString() : undefined }
function resetForm() { form.value = emptyForm() }

async function loadTasks() {
  loading.value = true
  try {
    const result = await taskManagerApi.listTasks({ page_size: 100 })
    tasks.value = result.tasks
    try {
      devices.value = await homeApi.listDevices()
      if (!form.value.device_id && controllableDevices.value.length) form.value.device_id = controllableDevices.value[0].device_id
    } catch (deviceError) {
      console.error(deviceError)
      ElMessage.warning('设备列表加载失败，暂时无法创建单设备控制任务')
    }
  }
  catch (error) { console.error(error); ElMessage.error('加载定时任务失败') }
  finally { loading.value = false }
}

function validateForm() {
  if (!form.value.name.trim()) return '请输入任务名称'
  if (!form.value.next_run_time) return '请选择执行时间'
  if (!isScenarioTask.value && !form.value.device_id) return '请选择要控制的家居设备'
  if (form.value.reminder_enabled && !isRecurring.value && !form.value.reminder_time) return '请选择提醒时间'
  if (form.value.reminder_enabled && isRecurring.value && !form.value.reminder_before_minutes) return '请输入提前提醒分钟数'
  const execution = new Date(form.value.next_run_time).getTime()
  if (form.value.reminder_time && new Date(form.value.reminder_time).getTime() >= execution) return '提醒时间必须早于执行时间'
  if (form.value.deadline && new Date(form.value.deadline).getTime() < execution) return '截止时间不能早于首次执行时间'
  if (isRecurring.value && form.value.repeat_until && new Date(form.value.repeat_until).getTime() < execution) return '重复结束时间不能早于首次执行时间'
  if (!form.value.notification_channels.length) return '至少选择一种通知方式'
  return ''
}

async function createTask() {
  const validationMessage = validateForm()
  if (validationMessage) return ElMessage.warning(validationMessage)
  try {
    await taskManagerApi.createTask({
      name: form.value.name, description: form.value.description, task_type: form.value.task_type,
      frequency: form.value.frequency, next_run_time: toUtcIso(form.value.next_run_time)!,
      params: isScenarioTask.value
        ? { scenario: form.value.scenario }
        : { device_id: form.value.device_id, state: form.value.device_state },
      reminder_enabled: form.value.reminder_enabled,
      reminder_time: !isRecurring.value ? toUtcIso(form.value.reminder_time) : undefined,
      reminder_before_minutes: isRecurring.value && form.value.reminder_enabled ? form.value.reminder_before_minutes : undefined,
      deadline: toUtcIso(form.value.deadline), repeat_until: isRecurring.value ? toUtcIso(form.value.repeat_until) : undefined,
      notification_channels: form.value.notification_channels
    })
    showCreate.value = false; resetForm(); await loadTasks(); ElMessage.success('定时任务已创建')
  } catch (error) { console.error(error); ElMessage.error('创建定时任务失败') }
}

async function toggle(task: ScheduledTask) {
  try { await taskManagerApi.toggleTask(task.id, !task.enabled); await loadTasks() }
  catch (error) { console.error(error); ElMessage.error('更新任务状态失败') }
}
async function run(task: ScheduledTask) {
  try { await taskManagerApi.runTaskNow(task.id); ElMessage.success('任务已触发') }
  catch (error) { console.error(error); ElMessage.error('触发任务失败') }
}
async function remove(task: ScheduledTask) {
  try { await taskManagerApi.deleteTask(task.id); tasks.value = tasks.value.filter(item => item.id !== task.id); ElMessage.success('任务已删除') }
  catch (error) { console.error(error); ElMessage.error('删除任务失败') }
}
function openCreate() { resetForm(); showCreate.value = true }
onMounted(loadTasks)
</script>

<template>
  <div class="min-h-full bg-slate-50 p-6"><div class="mx-auto max-w-6xl">
    <div class="mb-6 flex items-center justify-between"><div><h1 class="text-2xl font-bold text-slate-900">智能家居定时任务</h1><p class="mt-1 text-sm text-slate-500">设置场景或具体设备的执行时间、提醒时间、截止时间和重复规则。</p></div><div class="flex gap-2"><el-button :icon="RefreshCw" @click="loadTasks">刷新</el-button><el-button type="primary" :icon="Plus" @click="openCreate">新建定时任务</el-button></div></div>
    <el-card v-loading="loading" shadow="never"><el-table :data="tasks" empty-text="暂无智能家居定时任务">
      <el-table-column prop="name" label="任务" min-width="220" /><el-table-column label="规则" width="120"><template #default="{ row }">{{ frequencyLabels[row.frequency] }}</template></el-table-column>
      <el-table-column label="下次执行" width="190"><template #default="{ row }">{{ formatDate(row.next_run_time) }}</template></el-table-column>
      <el-table-column label="提醒/截止" min-width="210"><template #default="{ row }"><div v-if="row.reminder_enabled" class="text-xs text-slate-600">提醒：{{ row.reminder_time ? formatDate(row.reminder_time) : `提前 ${row.reminder_before_minutes} 分钟` }}</div><div v-if="row.deadline" class="text-xs text-slate-500">截止：{{ formatDate(row.deadline) }}</div><span v-if="!row.reminder_enabled && !row.deadline" class="text-xs text-slate-400">未设置</span></template></el-table-column>
      <el-table-column label="状态" width="100"><template #default="{ row }">{{ statusLabels[row.status] || row.status }}</template></el-table-column>
      <el-table-column label="操作" width="210"><template #default="{ row }"><el-button link type="primary" :icon="row.enabled ? Pause : Play" @click="toggle(row)">{{ row.enabled ? '暂停' : '启用' }}</el-button><el-button link type="success" :icon="Play" @click="run(row)">执行</el-button><el-button link type="danger" :icon="Trash2" @click="remove(row)">删除</el-button></template></el-table-column>
    </el-table></el-card>
  </div>
  <el-dialog v-model="showCreate" title="新建智能家居定时任务" width="640px" destroy-on-close><el-form label-position="top">
    <div class="grid grid-cols-2 gap-4"><el-form-item label="任务名称" required><el-input v-model="form.name" /></el-form-item><el-form-item label="任务类型" required><el-select v-model="form.task_type" class="w-full"><el-option label="场景执行" value="home_scenario" /><el-option label="控制具体设备" value="device_control" /></el-select></el-form-item></div>
    <div v-if="isScenarioTask" class="grid grid-cols-2 gap-4"><el-form-item label="场景" required><el-select v-model="form.scenario" class="w-full"><el-option label="离家" value="away" /><el-option label="睡眠" value="sleep" /><el-option label="观影" value="movie" /></el-select></el-form-item><div /></div>
    <div v-else class="grid grid-cols-2 gap-4"><el-form-item label="家居设备" required><el-select v-model="form.device_id" class="w-full" placeholder="请选择设备"><el-option v-for="device in controllableDevices" :key="device.device_id" :label="`${device.room} · ${device.device_id}（${deviceTypeLabels[device.device_type] || device.device_type}）`" :value="device.device_id" /></el-select></el-form-item><el-form-item label="执行动作" required><el-select v-model="form.device_state" class="w-full"><el-option label="打开" value="on" /><el-option label="关闭" value="off" /></el-select></el-form-item></div>
    <el-form-item label="说明"><el-input v-model="form.description" /></el-form-item><div class="grid grid-cols-2 gap-4"><el-form-item label="重复规则" required><el-select v-model="form.frequency" class="w-full"><el-option v-for="(label, value) in frequencyLabels" :key="value" :label="label" :value="value" /></el-select></el-form-item><el-form-item label="执行时间" required><el-date-picker v-model="form.next_run_time" type="datetime" value-format="YYYY-MM-DDTHH:mm:ss" class="w-full" /></el-form-item></div>
    <el-form-item label="执行前提醒"><el-switch v-model="form.reminder_enabled" active-text="开启站内提醒" /></el-form-item><el-form-item v-if="form.reminder_enabled && !isRecurring" label="提醒时间" required><el-date-picker v-model="form.reminder_time" type="datetime" value-format="YYYY-MM-DDTHH:mm:ss" class="w-full" /></el-form-item><el-form-item v-if="form.reminder_enabled && isRecurring" label="每次执行前提醒"><el-input-number v-model="form.reminder_before_minutes" :min="1" :max="10080" /><span class="ml-2 text-xs text-slate-500">分钟（最多提前7天）</span></el-form-item>
    <div class="grid grid-cols-2 gap-4"><el-form-item label="截止时间（可选）"><el-date-picker v-model="form.deadline" type="datetime" value-format="YYYY-MM-DDTHH:mm:ss" class="w-full" /></el-form-item><el-form-item v-if="isRecurring" label="重复结束时间（可选）"><el-date-picker v-model="form.repeat_until" type="datetime" value-format="YYYY-MM-DDTHH:mm:ss" class="w-full" /></el-form-item></div><el-form-item label="通知方式"><el-checkbox-group v-model="form.notification_channels"><el-checkbox label="in_app">站内通知</el-checkbox></el-checkbox-group></el-form-item>
    <div class="rounded bg-slate-50 px-3 py-2 text-xs leading-5 text-slate-500">到达提醒时间会发送站内提醒；到达执行时间会调用受控的家居场景；到达截止时间仍未执行时，任务会标记为“已过期”并停止后续执行。</div>
  </el-form><template #footer><el-button @click="showCreate = false">取消</el-button><el-button type="primary" @click="createTask">创建</el-button></template></el-dialog>
  </div>
</template>
