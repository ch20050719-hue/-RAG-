import { request } from '@/utils/request'

export type DeviceState = 'on' | 'off'

export interface HomeDevice {
  device_id: string
  room: string
  device_type: 'light' | 'fan' | string
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
  readings: Array<{
    sensor_id: string
    kind: string
    value: number
    unit: string
    online: boolean
    recorded_at: string
    source: string
  }>
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
  runScenario: (scenario: 'sleep' | 'away' | 'movie'): Promise<Record<string, unknown>> =>
    request('/home/scenarios', { method: 'POST', data: { scenario } })
}
