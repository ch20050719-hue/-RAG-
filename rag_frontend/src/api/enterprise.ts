import { request } from '@/utils/request'

export interface EnterpriseUser {
  id: string
  email: string
  full_name: string
  nickname?: string
  phone?: string
  company_position?: string
  avatar_url?: string
  is_active: boolean
  is_admin: boolean
  created_at: string
}

export interface EnterpriseResponse { id: string; name: string; tenant_id: string; created_at: string; member_count: number }
export interface InviteCode { code: string; created_by: string; created_at: string; expires_at: string; max_uses: number; used_count: number; is_active: boolean }
export interface CreateInviteCodeRequest { max_uses?: number; expires_in_days?: number }

export const enterpriseApi = {
  getEnterprise: () => request<EnterpriseResponse>('/enterprise/info'),
  getUsers: () => request<EnterpriseUser[]>('/enterprise/users'),
  getTenantUsers: () => request<EnterpriseUser[]>('/enterprise/users/list'),
  updateUserStatus: (userId: string, is_active: boolean) => request<void>(`/enterprise/users/${userId}/status`, { method: 'PUT', data: JSON.stringify({ is_active }) }),
  deleteUser: (userId: string) => request<void>(`/enterprise/users/${userId}`, { method: 'DELETE' }),
  createInviteCode: (data: CreateInviteCodeRequest = {}) => request<InviteCode>('/invite-codes', { method: 'POST', data: JSON.stringify(data) }),
  getInviteCodes: () => request<InviteCode[]>('/invite-codes'),
  deactivateInviteCode: (code: string) => request<void>(`/invite-codes/${code}`, { method: 'DELETE' }),
}
