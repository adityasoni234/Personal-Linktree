/**
 * Typed wrappers for every API endpoint the app uses.
 *
 * Grouping them here keeps URL strings out of components and gives one place to
 * change when the API version moves.
 */

import { apiBlob, apiDelete, apiGet, apiMessage, apiPatch, apiPost, request } from './client';
import type {
  AdminUserRow,
  ApiSuccess,
  AuditLogRow,
  AuthSession,
  DashboardOverview,
  GroupAnalytics,
  GroupCreatePayload,
  GroupDetail,
  GroupSummary,
  GroupUpdatePayload,
  LinkItem,
  LinkPayload,
  MediaItem,
  MediaKind,
  Organization,
  OrganizationAnalytics,
  OrganizationSettings,
  Paginated,
  PublicGroup,
  QRConfig,
  QRConfigResponse,
  QRPreset,
  Role,
  SessionInfo,
  SlugAvailability,
  SystemStats,
  TimeRange,
  UserProfile,
  UserStatus,
} from './types';

/* -------------------------------------------------------------------------- */
/* Auth                                                                        */
/* -------------------------------------------------------------------------- */

export const authApi = {
  register: (payload: {
    email: string;
    full_name: string;
    password: string;
    organization_slug?: string;
  }) => apiPost<AuthSession>('/auth/register', payload, { skipAuthRetry: true }),

  login: (payload: { email: string; password: string; remember_me?: boolean }) =>
    apiPost<AuthSession>('/auth/login', payload, { skipAuthRetry: true }),

  /** Uses the HttpOnly refresh cookie; never send a token in the body. */
  refresh: () => apiPost<AuthSession>('/auth/refresh', undefined, { skipAuthRetry: true }),

  logout: () => apiMessage('/auth/logout'),
  logoutAll: () => apiMessage('/auth/logout-all'),

  me: () => apiGet<UserProfile>('/auth/me'),
  updateProfile: (payload: { full_name?: string; avatar_url?: string | null }) =>
    apiPatch<UserProfile>('/auth/me', payload),

  forgotPassword: (email: string) =>
    apiMessage('/auth/forgot-password', 'POST', { email }),

  resetPassword: (token: string, newPassword: string) =>
    apiMessage('/auth/reset-password', 'POST', { token, new_password: newPassword }),

  changePassword: (payload: {
    current_password: string;
    new_password: string;
    revoke_other_sessions: boolean;
  }) => apiMessage('/auth/change-password', 'POST', payload),

  sessions: () => apiGet<SessionInfo[]>('/auth/sessions'),
  revokeSession: (id: string) => apiDelete(`/auth/sessions/${id}`),
};

/* -------------------------------------------------------------------------- */
/* Groups                                                                      */
/* -------------------------------------------------------------------------- */

export interface GroupListParams {
  page?: number;
  limit?: number;
  search?: string;
  status?: 'all' | 'published' | 'draft' | 'archived' | 'mine';
  sort?: 'position' | 'name' | 'created_at' | 'updated_at';
}

export const groupsApi = {
  list: (params: GroupListParams = {}) =>
    request<Paginated<GroupSummary>>('/groups', { method: 'GET', query: { ...params } }),

  get: (id: string) => apiGet<GroupDetail>(`/groups/${id}`),

  create: (payload: GroupCreatePayload) => apiPost<GroupDetail>('/groups', payload),

  update: (id: string, payload: GroupUpdatePayload) =>
    apiPatch<GroupDetail>(`/groups/${id}`, payload),

  remove: (id: string) => apiDelete(`/groups/${id}`),

  setPublished: (id: string, isPublished: boolean) =>
    apiPost<GroupDetail>(`/groups/${id}/publish`, { is_published: isPublished }),

  archive: (id: string) => apiPost<GroupDetail>(`/groups/${id}/archive`),
  restore: (id: string) => apiPost<GroupDetail>(`/groups/${id}/restore`),

  duplicate: (
    id: string,
    payload: { name?: string; include_links?: boolean; include_qr_design?: boolean } = {},
  ) => apiPost<GroupDetail>(`/groups/${id}/duplicate`, payload),

  reorder: (items: { id: string; position: number }[]) =>
    apiMessage('/groups/reorder', 'POST', { items }),

  checkSlug: (slug: string, excludeId?: string) =>
    request<ApiSuccess<SlugAvailability>>(`/groups/slug-available/${slug}`, {
      method: 'GET',
      query: excludeId ? { exclude: excludeId } : undefined,
    }).then((body) => body.data),
};

/* -------------------------------------------------------------------------- */
/* Links                                                                       */
/* -------------------------------------------------------------------------- */

export const linksApi = {
  list: (groupId: string) => apiGet<LinkItem[]>(`/groups/${groupId}/links`),
  create: (groupId: string, payload: LinkPayload) =>
    apiPost<LinkItem>(`/groups/${groupId}/links`, payload),
  update: (linkId: string, payload: Partial<LinkPayload>) =>
    apiPatch<LinkItem>(`/links/${linkId}`, payload),
  remove: (linkId: string) => apiDelete(`/links/${linkId}`),
  duplicate: (linkId: string) => apiPost<LinkItem>(`/links/${linkId}/duplicate`),
  reorder: (groupId: string, items: { id: string; position: number }[]) =>
    apiMessage(`/groups/${groupId}/links/reorder`, 'POST', { items }),
};

/* -------------------------------------------------------------------------- */
/* QR                                                                          */
/* -------------------------------------------------------------------------- */

export const qrApi = {
  presets: () => apiGet<QRPreset[]>('/qr/presets'),
  get: (groupId: string) => apiGet<QRConfigResponse>(`/groups/${groupId}/qr`),
  save: (groupId: string, config: QRConfig) =>
    apiPost<QRConfigResponse>(`/groups/${groupId}/qr`, config),
  applyPreset: (groupId: string, preset: string) =>
    apiPost<QRConfigResponse>(`/groups/${groupId}/qr/preset/${preset}`),
  preview: (groupId: string, config: QRConfig & { size?: number }) =>
    apiPost<import('./types').QRRenderInfo>(`/groups/${groupId}/qr/preview`, config),
  download: (groupId: string, format: 'png' | 'svg', size = 1024) =>
    apiBlob(`/groups/${groupId}/qr.${format}`, { size, download: true }),
};

/* -------------------------------------------------------------------------- */
/* Analytics                                                                   */
/* -------------------------------------------------------------------------- */

export const analyticsApi = {
  overview: (range: TimeRange = '30d') =>
    apiGet<DashboardOverview>('/analytics/overview', { range }),
  organization: (range: TimeRange = '30d', limit = 10) =>
    apiGet<OrganizationAnalytics>('/analytics/organization', { range, limit }),
  group: (groupId: string, range: TimeRange = '30d', limit = 10) =>
    apiGet<GroupAnalytics>(`/groups/${groupId}/analytics`, { range, limit }),
};

/* -------------------------------------------------------------------------- */
/* Media                                                                       */
/* -------------------------------------------------------------------------- */

export const mediaApi = {
  upload: (file: File, kind: MediaKind) => {
    const form = new FormData();
    form.append('file', file);
    return apiPost<MediaItem>('/media', form, { query: { kind } });
  },
  list: (kind?: MediaKind, limit = 50) =>
    apiGet<MediaItem[]>('/media', { kind: kind ?? '', limit }),
  remove: (id: string) => apiDelete(`/media/${id}`),
};

/* -------------------------------------------------------------------------- */
/* Administration                                                              */
/* -------------------------------------------------------------------------- */

export const adminApi = {
  users: (params: {
    page?: number;
    limit?: number;
    search?: string;
    role?: Role;
    status?: UserStatus;
  } = {}) =>
    request<Paginated<AdminUserRow>>('/admin/users', { method: 'GET', query: { ...params } }),

  changeRole: (userId: string, role: Role) =>
    apiMessage(`/admin/users/${userId}/role`, 'POST', { role }),

  changeStatus: (userId: string, status: UserStatus, reason?: string) =>
    apiMessage(`/admin/users/${userId}/status`, 'POST', { status, reason }),

  addMember: (email: string, role: Role) =>
    apiMessage('/admin/members', 'POST', { email, role }),

  removeMember: (userId: string) => apiDelete(`/admin/members/${userId}`),

  organization: () => apiGet<Organization>('/admin/organization'),
  updateOrganization: (payload: {
    name?: string;
    description?: string | null;
    logo_url?: string | null;
    website_url?: string | null;
    settings?: OrganizationSettings;
  }) => apiPatch<Organization>('/admin/organization', payload),

  auditLogs: (params: { page?: number; limit?: number; action?: string } = {}) =>
    request<Paginated<AuditLogRow>>('/admin/audit-logs', {
      method: 'GET',
      query: { ...params },
    }),

  systemStats: () => apiGet<SystemStats>('/admin/system'),
};

/* -------------------------------------------------------------------------- */
/* Public                                                                      */
/* -------------------------------------------------------------------------- */

export const publicApi = {
  group: (slug: string, source: 'direct' | 'qr' | 'share' = 'direct') =>
    apiGet<PublicGroup>(`/public/groups/${slug}`, { src: source }),

  /** Absolute URL of the click-tracking redirect for a link. */
  linkHref: (slug: string, linkId: string) => {
    const base = (import.meta.env.VITE_API_BASE_URL ?? '/api/v1').replace(/\/$/, '');
    return `${base}/public/groups/${slug}/links/${linkId}`;
  },

  trackShare: (slug: string) => apiMessage(`/public/groups/${slug}/events`, 'POST'),

  qrUrl: (slug: string, format: 'png' | 'svg' = 'png', size = 512) => {
    const base = (import.meta.env.VITE_API_BASE_URL ?? '/api/v1').replace(/\/$/, '');
    return `${base}/public/groups/${slug}/qr.${format}?size=${size}`;
  },
};
