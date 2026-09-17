import { request } from '@/utils/request'

export type DeviceState = 'on' | 'off'
export type HomeMode = 'normal' | 'sleep' | 'away'
export type EnvironmentLevel = 'normal' | 'attention' | 'danger' | 'fault'
export type SensorQuality = 'valid' | 'stale' | 'invalid' | 'offline'

export interface HomeDevice {
  device_id: string
  room: string
  device_type: 'light' | 'fan' | 'door_lock' | string
  state: DeviceState
  online: boolean
  updated_at: string
}

export interface DeviceCommandResult {
  request_id: string
  device_id: string
  accepted: boolean
  state: DeviceState
  message: string
  blocked_reason?: string | null
  acknowledged_at: string
}

export interface EnvironmentSnapshot {
  room: string
  generated_at: string
  readings: EnvironmentReading[]
}

export interface EnvironmentReading {
  sensor_id: string
  kind: string
  value: number
  unit: string
  online: boolean
  recorded_at: string
  source: string
  quality: SensorQuality
  level: EnvironmentLevel
}

export interface EnvironmentHistory {
  room: string
  minutes: number
  samples: EnvironmentSnapshot[]
}

export interface HomeAlert {
  alert_id: string
  room: string
  sensor_id: string
  metric: string
  current_value: number
  threshold: number | null
  consecutive_count: number
  state: 'suspected' | 'active' | 'fault' | 'recovered' | 'normal'
  source: string
  reason: string
  related_action?: string | null
  occurred_at?: string | null
  last_updated_at: string
}

export interface ModeActionResult {
  name: string
  accepted: boolean
  message: string
  device_id?: string | null
  command_result?: DeviceCommandResult | null
  lock_result?: DoorLockCommandResult | null
}

export interface ModeExecutionResult {
  room: string
  mode: HomeMode
  previous_mode: HomeMode
  accepted: boolean
  overall_status: 'success' | 'partial_failed' | 'failed'
  message: string
  actions: ModeActionResult[]
}

export interface DoorLockState {
  device_id: string
  room: string
  door_state: 'open' | 'closed'
  latch_state: 'locked' | 'unlocked'
  lock_state: 'locked' | 'unlocked'
  deadbolt_state: 'engaged' | 'released'
  online: boolean
  battery_level: number
  battery_state: 'normal' | 'low'
  jammed: boolean
  tampered: boolean
  last_command: string | null
  ack_status: 'accepted' | 'success' | 'failed'
  updated_at: string
}

export interface DoorLockCommandResult {
  request_id: string
  device_id: string
  room: string
  action: string
  accepted: boolean
  ack_status: 'accepted' | 'success' | 'failed'
  message: string
  blocked_reason?: string | null
  door_state: 'open' | 'closed'
  latch_state: 'locked' | 'unlocked'
  deadbolt_state: 'engaged' | 'released'
  battery_level: number
  expires_at?: string | null
  acknowledged_at: string
}

export const homeApi = {
  listDevices: (): Promise<HomeDevice[]> => request('/home/devices', { method: 'GET' }),
  setDeviceState: (deviceId: string, state: DeviceState): Promise<DeviceCommandResult> =>
    request(`/home/devices/${encodeURIComponent(deviceId)}/state`, {
      method: 'POST',
      data: { state }
    }),
  getEnvironment: (room = 'study'): Promise<EnvironmentSnapshot> =>
    request('/home/environment', { method: 'GET', params: { room } }),
  getEnvironmentHistory: (room = 'study', minutes = 10): Promise<EnvironmentHistory> =>
    request('/home/environment/history', { method: 'GET', params: { room, minutes } }),
  getAlerts: (room = 'study', activeOnly = false): Promise<HomeAlert[]> =>
    request('/home/alerts', { method: 'GET', params: { room, active_only: activeOnly } }),
  getMode: (room = 'study'): Promise<{ room: string; mode: HomeMode }> =>
    request('/home/mode', { method: 'GET', params: { room } }),
  setMode: (mode: HomeMode, room = 'study'): Promise<ModeExecutionResult> =>
    request('/home/mode', { method: 'POST', data: { mode }, params: { room } }),
  getDoorLockStatus: (room = 'study'): Promise<DoorLockState> =>
    request('/home/lock/status', { method: 'GET', params: { room } }),
  unlockDoor: (room = 'study'): Promise<DoorLockCommandResult> =>
    request('/home/lock/unlock', { method: 'POST', data: {}, params: { room } }),
  lockDoor: (room = 'study'): Promise<DoorLockCommandResult> =>
    request('/home/lock/lock', { method: 'POST', data: {}, params: { room } }),
  engageDeadbolt: (room = 'study'): Promise<DoorLockCommandResult> =>
    request('/home/lock/deadbolt/engage', { method: 'POST', data: {}, params: { room } }),
  releaseDeadbolt: (room = 'study'): Promise<DoorLockCommandResult> =>
    request('/home/lock/deadbolt/release', { method: 'POST', data: { confirmed: true }, params: { room } }),
  runScenario: (scenario: 'sleep' | 'away' | 'movie'): Promise<Record<string, unknown>> =>
    request('/home/scenarios', { method: 'POST', data: { scenario } })
}
