<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { CalendarClock, Play, Pause, Trash2, Plus, RefreshCw } from 'lucide-vue-next'
import { taskManagerApi, type ScheduledTask } from '@/api/task-manager'

const tasks = ref<ScheduledTask[]>([])
const loading = ref(false)
const showCreate = ref(false)
const form = ref({ name: '晚间回家场景', description: '按计划执行智能家居场景', task_type: 'home_scenario' as ScheduledTask['task_type'], frequency: 'once' as ScheduledTask['frequency'], next_run_time: '', scenario: 'home' })

async function loadTasks() {
  loading.value = true
  try { tasks.value = (await taskManagerApi.listTasks({ page_size: 100 })).tasks }
  catch (error) { console.error(error); ElMessage.error('加载定时任务失败') }
  finally { loading.value = false }
}

async function createTask() {
  if (!form.value.next_run_time) return ElMessage.warning('请选择执行时间')
  try {
    await taskManagerApi.createTask({ ...form.value, params: { scenario: form.value.scenario } })
    showCreate.value = false
    await loadTasks()
    ElMessage.success('场景任务已创建')
  } catch (error) { console.error(error); ElMessage.error('创建场景任务失败') }
}

async function toggle(task: ScheduledTask) {
  try { await taskManagerApi.toggleTask(task.id, !task.enabled); await loadTasks() }
  catch (error) { console.error(error); ElMessage.error('更新任务状态失败') }
}

async function run(task: ScheduledTask) {
  try { await taskManagerApi.runTaskNow(task.id); ElMessage.success('场景任务已触发') }
  catch (error) { console.error(error); ElMessage.error('触发任务失败') }
}

async function remove(task: ScheduledTask) {
  try { await taskManagerApi.deleteTask(task.id); tasks.value = tasks.value.filter(item => item.id !== task.id); ElMessage.success('任务已删除') }
  catch (error) { console.error(error); ElMessage.error('删除任务失败') }
}

onMounted(loadTasks)
</script>

<template>
  <div class="min-h-full bg-slate-50 p-6">
    <div class="mx-auto max-w-5xl">
      <div class="mb-6 flex items-center justify-between">
        <div><h1 class="text-2xl font-bold text-slate-900">智能家居定时任务</h1><p class="mt-1 text-sm text-slate-500">安排场景执行并查看设备状态巡检任务。</p></div>
        <div class="flex gap-2"><el-button :icon="RefreshCw" @click="loadTasks">刷新</el-button><el-button type="primary" :icon="Plus" @click="showCreate = true">新建场景任务</el-button></div>
      </div>
      <el-card v-loading="loading" shadow="never"><el-table :data="tasks" empty-text="暂无智能家居定时任务">
        <el-table-column prop="name" label="任务" min-width="220" /><el-table-column prop="task_type" label="类型" width="160"><template #default="{ row }">{{ row.task_type === 'home_scenario' ? '场景执行' : '设备状态检查' }}</template></el-table-column>
        <el-table-column prop="next_run_time" label="下次执行" width="210" /><el-table-column prop="status" label="状态" width="110" /><el-table-column label="操作" width="190"><template #default="{ row }"><el-button link type="primary" :icon="row.enabled ? Pause : Play" @click="toggle(row)">{{ row.enabled ? '暂停' : '启用' }}</el-button><el-button link type="success" :icon="Play" @click="run(row)">执行</el-button><el-button link type="danger" :icon="Trash2" @click="remove(row)">删除</el-button></template></el-table-column>
      </el-table></el-card>
    </div>
    <el-dialog v-model="showCreate" title="新建智能家居场景任务" width="520px"><el-form label-position="top"><el-form-item label="任务名称"><el-input v-model="form.name" /></el-form-item><el-form-item label="说明"><el-input v-model="form.description" /></el-form-item><el-form-item label="场景"><el-select v-model="form.scenario" class="w-full"><el-option label="回家" value="home" /><el-option label="离家" value="away" /><el-option label="睡眠" value="sleep" /></el-select></el-form-item><el-form-item label="执行时间"><el-date-picker v-model="form.next_run_time" type="datetime" value-format="YYYY-MM-DDTHH:mm:ss" class="w-full" /></el-form-item></el-form><template #footer><el-button @click="showCreate = false">取消</el-button><el-button type="primary" @click="createTask">创建</el-button></template></el-dialog>
  </div>
</template>
