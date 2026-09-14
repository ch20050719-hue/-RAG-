<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Home, Power, RefreshCw, ShieldCheck, Thermometer, Wifi, WifiOff } from 'lucide-vue-next'
import { homeApi, type DeviceState, type EnvironmentSnapshot, type HomeDevice } from '@/api/home'

const devices = ref<HomeDevice[]>([])
const environment = ref<EnvironmentSnapshot | null>(null)
const loading = ref(false)
const busyDeviceId = ref<string | null>(null)

const sensorSummary = computed(() => environment.value?.readings ?? [])

async function loadHome() {
  loading.value = true
  try {
    const [deviceList, snapshot] = await Promise.all([homeApi.listDevices(), homeApi.getEnvironment()])
    devices.value = deviceList
    environment.value = snapshot
  } catch (error) {
    console.error('Failed to load home devices', error)
    ElMessage.error('设备数据加载失败，请检查后端或 MQTT 连接')
  } finally {
    loading.value = false
  }
}

async function toggleDevice(device: HomeDevice) {
  busyDeviceId.value = device.device_id
  const nextState: DeviceState = device.state === 'on' ? 'off' : 'on'
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

async function runScenario(scenario: 'sleep' | 'away' | 'movie') {
  try {
    const result = await homeApi.runScenario(scenario)
    if (result.accepted === false) {
      ElMessage.warning(String(result.message || '场景执行被拦截'))
      return
    }
    ElMessage.success('场景指令已执行')
    await loadHome()
  } catch (error) {
    console.error('Failed to run home scenario', error)
    ElMessage.error('场景执行失败')
  }
}

onMounted(loadHome)
</script>

<template>
  <div class="min-h-full bg-slate-100 p-6 text-slate-900">
    <div class="mx-auto max-w-6xl space-y-6">
      <header class="flex flex-wrap items-start justify-between gap-4">
        <div>
          <div class="mb-2 flex items-center gap-2 text-sm font-medium text-indigo-600">
            <Home :size="16" /> 智能家居控制台
          </div>
          <h1 class="text-2xl font-semibold tracking-tight">设备与环境</h1>
          <p class="mt-1 text-sm text-slate-500">所有控制均经过设备白名单、安全校验和回执确认。</p>
        </div>
        <button class="inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-medium shadow-sm hover:bg-slate-50" :disabled="loading" @click="loadHome">
          <RefreshCw :size="16" :class="loading ? 'animate-spin' : ''" /> 刷新
        </button>
      </header>

      <section class="grid gap-4 md:grid-cols-2">
        <article v-for="device in devices" :key="device.device_id" class="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <div class="flex items-start justify-between">
            <div>
              <p class="text-xs uppercase tracking-wider text-slate-400">{{ device.room }} · {{ device.device_type }}</p>
              <h2 class="mt-2 text-lg font-semibold">{{ device.device_id }}</h2>
            </div>
            <component :is="device.online ? Wifi : WifiOff" :size="18" :class="device.online ? 'text-emerald-500' : 'text-slate-300'" />
          </div>
          <div class="mt-8 flex items-end justify-between">
            <div>
              <p class="text-xs text-slate-400">当前状态</p>
              <p class="mt-1 text-2xl font-semibold">{{ device.state === 'on' ? '开启' : '关闭' }}</p>
            </div>
            <button class="inline-flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:opacity-50" :class="device.state === 'on' ? 'bg-slate-700 hover:bg-slate-800' : 'bg-indigo-600 hover:bg-indigo-700'" :disabled="!device.online || busyDeviceId === device.device_id" @click="toggleDevice(device)">
              <Power :size="16" /> {{ device.state === 'on' ? '关闭' : '开启' }}
            </button>
          </div>
        </article>
      </section>

      <section class="grid gap-4 lg:grid-cols-[1.4fr_1fr]">
        <article class="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <div class="flex items-center gap-2"><ShieldCheck :size="18" class="text-indigo-600" /><h2 class="font-semibold">预置场景</h2></div>
          <div class="mt-4 flex flex-wrap gap-3">
            <button class="rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-700" @click="runScenario('sleep')">睡眠模式</button>
            <button class="rounded-lg bg-slate-100 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-200" @click="runScenario('away')">离家模式</button>
            <button class="rounded-lg bg-slate-100 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-200" @click="runScenario('movie')">观影模式</button>
          </div>
        </article>
        <article class="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <div class="flex items-center gap-2"><Thermometer :size="18" class="text-indigo-600" /><h2 class="font-semibold">环境快照</h2></div>
          <div class="mt-4 grid grid-cols-2 gap-3">
            <div v-for="reading in sensorSummary" :key="reading.sensor_id" class="rounded-lg bg-slate-50 p-3">
              <p class="text-xs text-slate-400">{{ reading.kind }}</p><p class="mt-1 font-semibold">{{ reading.value }} {{ reading.unit }}</p>
            </div>
            <p v-if="!sensorSummary.length" class="col-span-2 text-sm text-slate-400">暂无传感器数据</p>
          </div>
        </article>
      </section>
    </div>
  </div>
</template>
