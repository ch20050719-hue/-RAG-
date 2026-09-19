<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { use } from 'echarts/core'
import { LineChart } from 'echarts/charts'
import { CanvasRenderer } from 'echarts/renderers'
import { GridComponent, MarkLineComponent, TooltipComponent } from 'echarts/components'
import type { EChartsOption } from 'echarts'
import VChart from 'vue-echarts'
import { ElMessage } from 'element-plus'
import {
  AlertTriangle,
  DoorClosed,
  DoorOpen,
  Home,
  Lock,
  Power,
  RefreshCw,
  ShieldCheck,
  Thermometer,
  Unlock,
  Wind,
  Wifi,
  WifiOff
} from 'lucide-vue-next'
import {
  homeApi,
  type DoorLockCommandResult,
  type DoorLockState,
  type EnvironmentLevel,
  type EnvironmentReading,
  type EnvironmentSnapshot,
  type HomeAlert,
  type HomeDevice,
  type HomeMode
} from '@/api/home'

use([CanvasRenderer, LineChart, GridComponent, MarkLineComponent, TooltipComponent])

const room = 'study'
const devices = ref<HomeDevice[]>([])
const environment = ref<EnvironmentSnapshot | null>(null)
const history = ref<{ samples: EnvironmentSnapshot[] }>({ samples: [] })
const alerts = ref<HomeAlert[]>([])
const doorLock = ref<DoorLockState | null>(null)
const mode = ref<HomeMode>('normal')
const loading = ref(false)
const refreshing = ref(false)
const busyDeviceId = ref<string | null>(null)
const busyMode = ref(false)
const busyDoorAction = ref<string | null>(null)
const notifiedAlertIds = new Set<string>()
let pollTimer: number | undefined

const metrics = [
  { kind: 'temperature', label: '温度', color: '#f97316', unit: '°C', dangerLine: 35 },
  { kind: 'humidity', label: '湿度', color: '#0ea5e9', unit: '%', dangerLine: 80 },
  { kind: 'illuminance', label: '光照', color: '#eab308', unit: 'lux', dangerLine: 50 },
  { kind: 'smoke', label: '实验烟雾', color: '#8b5cf6', unit: 'raw', dangerLine: 800 }
] as const

const sensorSummary = computed(() => environment.value?.readings ?? [])
const modeLabels: Record<HomeMode, string> = { normal: '正常模式', sleep: '睡眠模式', away: '离家模式' }

function readingFor(kind: string): EnvironmentReading | undefined {
  return sensorSummary.value.find((reading) => reading.kind === kind)
}

function levelLabel(level: EnvironmentLevel | undefined): string {
  return { normal: '正常', attention: '需关注', danger: '危险', fault: '故障' }[level ?? 'fault']
}

function levelClass(level: EnvironmentLevel | undefined): string {
  return {
    normal: 'bg-emerald-50 text-emerald-700',
    attention: 'bg-amber-50 text-amber-700',
    danger: 'bg-rose-50 text-rose-700',
    fault: 'bg-slate-100 text-slate-600'
  }[level ?? 'fault']
}

function formatNumber(value: number | undefined): string {
  return value === undefined ? '--' : value.toFixed(value >= 100 ? 0 : 1)
}

function chartOption(kind: string, label: string, color: string, unit: string, dangerLine: number): EChartsOption {
  const points = history.value.samples.map((sample) => {
    const reading = sample.readings.find((item) => item.kind === kind)
    return {
      time: new Date(sample.generated_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }),
      value: reading?.quality === 'valid' ? reading.value : null
    }
  })
  return {
    animation: false,
    grid: { left: 48, right: 20, top: 24, bottom: 32 },
    tooltip: { trigger: 'axis' },
    xAxis: { type: 'category', data: points.map((point) => point.time), boundaryGap: false },
    yAxis: { type: 'value', name: unit, nameTextStyle: { color: '#94a3b8' } },
    series: [
      {
        name: label,
        type: 'line',
        smooth: true,
        showSymbol: false,
        data: points.map((point) => point.value),
        lineStyle: { color, width: 2 },
        itemStyle: { color },
        markLine: {
          silent: true,
          symbol: 'none',
          lineStyle: { color: '#f43f5e', type: 'dashed' },
          data: [{ yAxis: dangerLine, name: '危险阈值' }]
        }
      }
    ]
  }
}

function notifyNewAlerts(alertList: HomeAlert[]) {
  for (const alert of alertList) {
    if (alert.state !== 'active' || notifiedAlertIds.has(alert.alert_id)) continue
    notifiedAlertIds.add(alert.alert_id)
    ElMessage.error(`${alert.sensor_id} 已确认报警：${alert.current_value}，阈值 ${alert.threshold ?? '--'}`)
  }
}

async function loadHome(showSpinner = false) {
  if (refreshing.value) return
  refreshing.value = true
  if (showSpinner) loading.value = true
  try {
    const [deviceList, snapshot, historyData, alertList, modeData, lockData] = await Promise.all([
      homeApi.listDevices(),
      homeApi.getEnvironment(room),
      homeApi.getEnvironmentHistory(room, 10),
      homeApi.getAlerts(room, true),
      homeApi.getMode(room),
      homeApi.getDoorLockStatus(room)
    ])
    devices.value = deviceList
    environment.value = snapshot
    history.value = historyData
    notifyNewAlerts(alertList)
    alerts.value = alertList
    mode.value = modeData.mode
    doorLock.value = lockData
  } catch (error) {
    console.error('Failed to load home devices', error)
    if (showSpinner) ElMessage.error('设备数据加载失败，请检查后端或 MQTT 连接')
  } finally {
    loading.value = false
    refreshing.value = false
  }
}

async function toggleDevice(device: HomeDevice) {
  busyDeviceId.value = device.device_id
  const nextState: 'on' | 'off' = device.state === 'on' ? 'off' : 'on'
  try {
    const result = await homeApi.setDeviceState(device.device_id, nextState)
    if (!result.accepted) {
      ElMessage.warning(result.blocked_reason || result.message || '设备操作被安全规则拦截')
      return
    }
    ElMessage.success(`${device.device_id} 已${nextState === 'on' ? '开启' : '关闭'}`)
    await loadHome()
  } catch (error) {
    console.error('Failed to control home device', error)
    ElMessage.error('指令下发失败')
  } finally {
    busyDeviceId.value = null
  }
}

async function toggleWindow(device: HomeDevice) {
  busyDeviceId.value = device.device_id
  try {
    const result = await homeApi.setWindowState(device.state === 'open' ? 'closed' : 'open')
    if (!result.accepted) ElMessage.warning(result.blocked_reason || result.message)
    else ElMessage.success(result.state === 'open' ? '窗户已打开' : '窗户已关闭')
    await loadHome()
  } finally {
    busyDeviceId.value = null
  }
}

async function switchMode(nextMode: HomeMode) {
  if (busyMode.value) return
  busyMode.value = true
  try {
    const result = await homeApi.setMode(nextMode, room)
    if (!result.accepted) ElMessage.warning(result.message || '模式切换未完成')
    else ElMessage.success(`${modeLabels[nextMode]}已生效`)
    await loadHome()
  } catch (error) {
    console.error('Failed to switch home mode', error)
    ElMessage.error('模式切换失败')
  } finally {
    busyMode.value = false
  }
}

async function runDoorAction(action: 'open' | 'close' | 'unlock' | 'lock' | 'engage' | 'release') {
  if (action === 'release' && !window.confirm('确认解除门锁反锁吗？')) return
  busyDoorAction.value = action
  try {
    let result: DoorLockCommandResult
    if (action === 'open') result = await homeApi.openDoor(room)
    else if (action === 'close') result = await homeApi.closeDoor(room)
    else if (action === 'unlock') result = await homeApi.unlockDoor(room)
    else if (action === 'lock') result = await homeApi.lockDoor(room)
    else if (action === 'engage') result = await homeApi.engageDeadbolt(room)
    else result = await homeApi.releaseDeadbolt(room)
    if (!result.accepted) ElMessage.warning(result.blocked_reason || result.message)
    else ElMessage.success(action === 'open' ? '门体已打开' : action === 'close' ? '门体已关闭' : '门锁指令已收到成功 ack')
    await loadHome()
  } catch (error) {
    console.error('Failed to control door lock', error)
    ElMessage.error('门锁指令下发失败')
  } finally {
    busyDoorAction.value = null
  }
}

onMounted(() => {
  void loadHome(true)
  pollTimer = window.setInterval(() => void loadHome(), 5000)
})

onBeforeUnmount(() => {
  if (pollTimer !== undefined) window.clearInterval(pollTimer)
})
</script>

<template>
  <div class="min-h-full bg-slate-100 p-6 text-slate-900">
    <div class="mx-auto max-w-7xl space-y-6">
      <header class="flex flex-wrap items-start justify-between gap-4">
        <div>
          <div class="mb-2 flex items-center gap-2 text-sm font-medium text-indigo-600"><Home :size="16" /> 智能家居控制台</div>
          <div class="flex flex-wrap items-center gap-3">
            <h1 class="text-2xl font-semibold tracking-tight">设备与环境</h1>
            <span class="rounded-full bg-indigo-50 px-3 py-1 text-xs font-semibold text-indigo-700">当前：{{ modeLabels[mode] }}</span>
          </div>
          <p class="mt-1 text-sm text-slate-500">单房间实验控制台 · 数据每 5 秒刷新 · 所有动作均等待后端 ack。</p>
        </div>
        <button class="inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-medium shadow-sm hover:bg-slate-50" :disabled="loading" @click="loadHome(true)">
          <RefreshCw :size="16" :class="loading ? 'animate-spin' : ''" /> 刷新
        </button>
      </header>

      <section class="grid gap-4 md:grid-cols-3">
        <article v-for="metric in metrics" :key="metric.kind" class="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <div class="flex items-start justify-between">
            <div><p class="text-xs font-semibold uppercase tracking-wider text-slate-400">{{ metric.label }}</p><p class="mt-3 text-3xl font-semibold">{{ formatNumber(readingFor(metric.kind)?.value) }} <span class="text-sm font-normal text-slate-400">{{ readingFor(metric.kind)?.unit || metric.unit }}</span></p></div>
            <Thermometer :size="20" :style="{ color: metric.color }" />
          </div>
          <div class="mt-4 flex items-center justify-between text-xs text-slate-400">
            <span>质量：{{ readingFor(metric.kind)?.quality || 'unknown' }}</span>
            <span class="rounded-full px-2 py-1 font-semibold" :class="levelClass(readingFor(metric.kind)?.level)">{{ levelLabel(readingFor(metric.kind)?.level) }}</span>
          </div>
        </article>
      </section>

      <section class="grid gap-4 lg:grid-cols-[1.25fr_0.75fr]">
        <article class="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <div class="flex items-center justify-between"><div class="flex items-center gap-2"><ShieldCheck :size="18" class="text-indigo-600" /><h2 class="font-semibold">运行模式</h2></div><span class="text-xs text-slate-400">{{ room }}</span></div>
          <div class="mt-4 grid gap-3 sm:grid-cols-3">
            <button v-for="item in (['normal', 'sleep', 'away'] as HomeMode[])" :key="item" class="rounded-lg px-4 py-3 text-sm font-semibold transition" :class="mode === item ? 'bg-indigo-600 text-white' : 'bg-slate-100 text-slate-700 hover:bg-slate-200'" :disabled="busyMode" @click="switchMode(item)">{{ modeLabels[item] }}</button>
          </div>
          <p class="mt-4 text-xs text-slate-500">睡眠模式：关闭 LED 后反锁；离家模式：关闭 LED/风扇后锁门。任何失败都会保留逐步结果。</p>
        </article>
        <article class="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <div class="flex items-center justify-between"><div class="flex items-center gap-2"><Lock :size="18" class="text-indigo-600" /><h2 class="font-semibold">门锁状态</h2></div><component :is="doorLock?.online ? Wifi : WifiOff" :size="18" :class="doorLock?.online ? 'text-emerald-500' : 'text-slate-300'" /></div>
          <div class="mt-4 grid grid-cols-2 gap-3 text-sm">
            <div><p class="text-xs text-slate-400">门磁</p><p class="mt-1 font-semibold">{{ doorLock?.door_state === 'closed' ? '已关闭' : '已打开' }}</p></div>
            <div><p class="text-xs text-slate-400">门舌</p><p class="mt-1 font-semibold">{{ doorLock?.latch_state === 'locked' ? '已锁定' : '已解锁' }}</p></div>
            <div><p class="text-xs text-slate-400">反锁</p><p class="mt-1 font-semibold">{{ doorLock?.deadbolt_state === 'engaged' ? '已反锁' : '已释放' }}</p></div>
            <div><p class="text-xs text-slate-400">电量</p><p class="mt-1 font-semibold">{{ doorLock?.battery_level ?? '--' }}%</p></div>
          </div>
          <div class="mt-4 flex flex-wrap gap-2">
            <button class="inline-flex items-center gap-1 rounded-lg bg-emerald-100 px-3 py-2 text-xs font-semibold text-emerald-800 disabled:cursor-not-allowed disabled:opacity-50" :disabled="busyDoorAction !== null || !doorLock?.online || doorLock?.door_state !== 'closed' || doorLock?.latch_state !== 'unlocked' || doorLock?.deadbolt_state !== 'released'" @click="runDoorAction('open')"><DoorOpen :size="14" /> 自动开门</button>
            <button class="inline-flex items-center gap-1 rounded-lg bg-sky-100 px-3 py-2 text-xs font-semibold text-sky-800 disabled:cursor-not-allowed disabled:opacity-50" :disabled="busyDoorAction !== null || !doorLock?.online || doorLock?.door_state !== 'open' || doorLock?.latch_state !== 'unlocked' || doorLock?.deadbolt_state !== 'released'" @click="runDoorAction('close')"><DoorClosed :size="14" /> 自动关门</button>
            <button class="inline-flex items-center gap-1 rounded-lg bg-amber-100 px-3 py-2 text-xs font-semibold text-amber-800 disabled:cursor-not-allowed disabled:opacity-50" :disabled="busyDoorAction !== null || !doorLock?.online" @click="runDoorAction('unlock')"><Unlock :size="14" /> 解锁</button>
            <button class="inline-flex items-center gap-1 rounded-lg bg-slate-100 px-3 py-2 text-xs font-semibold text-slate-700 disabled:cursor-not-allowed disabled:opacity-50" :disabled="busyDoorAction !== null || !doorLock?.online || doorLock?.door_state !== 'closed'" @click="runDoorAction('lock')"><Lock :size="14" /> 锁门</button>
            <button class="inline-flex items-center gap-1 rounded-lg bg-indigo-100 px-3 py-2 text-xs font-semibold text-indigo-800 disabled:cursor-not-allowed disabled:opacity-50" :disabled="busyDoorAction !== null || !doorLock?.online || doorLock?.door_state !== 'closed'" @click="runDoorAction('engage')"><ShieldCheck :size="14" /> 反锁</button>
            <button class="inline-flex items-center gap-1 rounded-lg bg-rose-100 px-3 py-2 text-xs font-semibold text-rose-800 disabled:cursor-not-allowed disabled:opacity-50" :disabled="busyDoorAction !== null || !doorLock?.online" @click="runDoorAction('release')"><Unlock :size="14" /> 解除反锁</button>
          </div>
        </article>
      </section>

      <section class="grid gap-4 lg:grid-cols-3">
        <article v-for="metric in metrics" :key="`${metric.kind}-chart`" class="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <div class="flex items-center justify-between"><h2 class="font-semibold">{{ metric.label }}趋势</h2><span class="text-xs text-slate-400">最近 10 分钟</span></div>
          <VChart class="mt-3 h-56 w-full" :option="chartOption(metric.kind, metric.label, metric.color, metric.unit, metric.dangerLine)" autoresize />
        </article>
      </section>

      <section class="grid gap-4 lg:grid-cols-[1fr_1fr]">
        <article class="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <div class="flex items-center gap-2"><Wind :size="18" class="text-indigo-600" /><h2 class="font-semibold">设备控制</h2></div>
          <div class="mt-4 grid gap-3 sm:grid-cols-2">
            <div v-for="device in devices.filter((item) => item.device_type !== 'door_lock')" :key="device.device_id" class="rounded-xl bg-slate-50 p-4">
              <div class="flex items-center justify-between"><div><p class="text-xs text-slate-400">{{ device.device_type }}</p><p class="mt-1 font-semibold">{{ device.device_id }}</p></div><component :is="device.online ? Wifi : WifiOff" :size="16" :class="device.online ? 'text-emerald-500' : 'text-slate-300'" /></div>
              <button v-if="device.device_type === 'window'" class="mt-4 inline-flex w-full items-center justify-center gap-2 rounded-lg bg-sky-600 px-3 py-2 text-sm font-semibold text-white disabled:opacity-50" :disabled="!device.online || busyDeviceId === device.device_id" @click="toggleWindow(device)">{{ device.state === 'open' ? '关闭窗户' : '打开窗户' }}</button>
              <button v-else class="mt-4 inline-flex w-full items-center justify-center gap-2 rounded-lg px-3 py-2 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:opacity-50" :class="device.state === 'on' ? 'bg-slate-700' : 'bg-indigo-600'" :disabled="!device.online || busyDeviceId === device.device_id" @click="toggleDevice(device)"><Power :size="15" /> {{ device.state === 'on' ? '关闭' : '开启' }}</button>
            </div>
          </div>
        </article>
        <article class="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <div class="flex items-center justify-between"><div class="flex items-center gap-2"><AlertTriangle :size="18" class="text-rose-500" /><h2 class="font-semibold">应用内报警</h2></div><span class="text-xs text-slate-400">{{ alerts.length }} 条当前记录</span></div>
          <div v-if="alerts.length" class="mt-4 space-y-3">
            <div v-for="alert in alerts.slice().reverse().slice(0, 6)" :key="`${alert.alert_id}-${alert.last_updated_at}`" class="rounded-xl border border-rose-100 bg-rose-50 p-3">
              <div class="flex items-center justify-between gap-3"><p class="text-sm font-semibold text-rose-800">{{ alert.sensor_id }} · {{ alert.metric }}</p><span class="text-xs font-semibold text-rose-700">{{ alert.state }}</span></div>
              <p class="mt-1 text-xs text-rose-700">{{ alert.current_value }} / 阈值 {{ alert.threshold ?? '--' }} · {{ alert.reason }}</p>
            </div>
          </div>
          <p v-else class="mt-6 rounded-xl bg-emerald-50 p-4 text-sm text-emerald-700">当前无 active 报警，传感器数据正常。</p>
        </article>
      </section>
    </div>
  </div>
</template>
