/**
 * Types mirroring the backend's Pydantic schemas.
 *
 * These are the contract between the two halves of the app; when a backend
 * schema changes, this file changes with it.
 */

export type Role = 'SUPER_ADMIN' | 'ADMIN' | 'EDITOR' | 'USER';
export type UserStatus = 'ACTIVE' | 'SUSPENDED' | 'PENDING' | 'DELETED';

export interface ApiSuccess<T> {
  success: true;
  data: T;
}

export interface ApiMessage {
  success: true;
  message: string;
}

export interface ApiErrorBody {
  success: false;
  error: {
    code: string;
    message: string;
    details?: unknown;
    request_id?: string;
  };
}

export interface PageMeta {
  page: number;
  limit: number;
  total: number;
  pages: number;
  has_next: boolean;
  has_previous: boolean;
}

export interface Paginated<T> {
  success: true;
  data: T[];
  meta: PageMeta;
}

export interface FieldError {
  field: string;
  message: string;
  type?: string;
}

/* -------------------------------------------------------------------------- */
/* Auth                                                                        */
/* -------------------------------------------------------------------------- */

export interface UserProfile {
  id: string;
  email: string;
  full_name: string;
  avatar_url: string | null;
  system_role: Role;
  status: UserStatus;
  email_verified: boolean;
  created_at: string;
  last_login_at: string | null;
  organization_id: string | null;
  organization_name: string | null;
  organization_role: Role | null;
  effective_role: Role;
  permissions: string[];
}

export interface AuthSession {
  access_token: string;
  token_type: string;
  expires_in: number;
  expires_at: string;
  csrf_token: string;
  user: UserProfile;
}

export interface SessionInfo {
  id: string;
  created_at: string;
  last_used_at: string | null;
  expires_at: string;
  user_agent_label: string | null;
  is_current: boolean;
}

/* -------------------------------------------------------------------------- */
/* Groups                                                                      */
/* -------------------------------------------------------------------------- */

export type ThemePreset =
  | 'ieee-classic'
  | 'minimal-white'
  | 'dark'
  | 'corporate'
  | 'gradient'
  | 'event';
export type ButtonStyle = 'solid' | 'outline' | 'soft' | 'glass';
export type ButtonRadius = 'none' | 'sm' | 'md' | 'lg' | 'full';
export type FontFamily = 'inter' | 'dm-sans' | 'space-grotesk' | 'source-serif' | 'system';
export type BackgroundStyle = 'solid' | 'gradient' | 'pattern';

export interface Theme {
  preset: ThemePreset;
  primary_color: string;
  secondary_color: string;
  background_color: string;
  background_end_color: string | null;
  background_style: BackgroundStyle;
  text_color: string | null;
  button_style: ButtonStyle;
  button_radius: ButtonRadius;
  font: FontFamily;
}

export interface SEO {
  title: string | null;
  description: string | null;
  og_image_url: string | null;
}

export interface GroupStats {
  link_count: number;
  page_views: number;
  qr_scans: number;
  link_clicks: number;
}

export interface GroupSummary {
  id: string;
  organization_id: string;
  owner_id: string | null;
  name: string;
  slug: string;
  description: string | null;
  logo_url: string | null;
  is_published: boolean;
  is_archived: boolean;
  position: number;
  created_at: string;
  updated_at: string;
  public_url: string;
  stats: GroupStats;
}

export interface GroupDetail extends GroupSummary {
  theme: Theme;
  seo: SEO;
  published_at: string | null;
  owner_name: string | null;
}

export interface GroupCreatePayload {
  name: string;
  slug?: string | null;
  description?: string | null;
  logo_url?: string | null;
  theme?: Theme;
  seo?: SEO;
  is_published?: boolean;
}

export type GroupUpdatePayload = Partial<
  Pick<GroupCreatePayload, 'name' | 'slug' | 'description' | 'logo_url' | 'theme' | 'seo'>
>;

export interface SlugAvailability {
  available: boolean;
  slug: string;
  reason: string | null;
}

/* -------------------------------------------------------------------------- */
/* Links                                                                       */
/* -------------------------------------------------------------------------- */

export type LinkVariant = 'default' | 'solid' | 'outline' | 'soft' | 'minimal' | 'featured';

export interface LinkStyle {
  variant: LinkVariant;
  background_color: string | null;
  text_color: string | null;
  border_radius: ButtonRadius | null;
}

export interface LinkItem {
  id: string;
  group_id: string;
  title: string;
  url: string;
  description: string | null;
  icon: string | null;
  style: LinkStyle;
  position: number;
  is_active: boolean;
  created_at: string;
  updated_at: string;
  click_count: number;
}

export interface LinkPayload {
  title: string;
  url: string;
  description?: string | null;
  icon?: string | null;
  style?: Partial<LinkStyle>;
  is_active?: boolean;
  position?: number | null;
}

/* -------------------------------------------------------------------------- */
/* QR                                                                          */
/* -------------------------------------------------------------------------- */

export type DotStyle =
  | 'square'
  | 'rounded'
  | 'dot'
  | 'classy'
  | 'diamond'
  | 'vertical'
  | 'horizontal';
export type EyeFrameStyle = 'square' | 'rounded' | 'circle' | 'leaf' | 'shield';
export type EyeBallStyle = 'square' | 'rounded' | 'circle' | 'diamond';
export type GradientType = 'none' | 'linear' | 'radial';
export type ErrorCorrection = 'L' | 'M' | 'Q' | 'H';
export type LogoShape = 'square' | 'rounded' | 'circle';
export type FrameStyle =
  | 'none'
  | 'simple'
  | 'rounded'
  | 'banner_bottom'
  | 'banner_top'
  | 'ticket';

export interface QRConfig {
  preset: string | null;
  foreground_color: string;
  background_color: string;
  transparent_background: boolean;
  gradient_type: GradientType;
  gradient_start_color: string | null;
  gradient_end_color: string | null;
  gradient_angle: number;
  dot_style: DotStyle;
  eye_frame_style: EyeFrameStyle;
  eye_ball_style: EyeBallStyle;
  eye_color: string | null;
  eye_ball_color: string | null;
  margin: number;
  error_correction: ErrorCorrection;
  logo_media_id: string | null;
  logo_size: number;
  logo_padding: number;
  logo_shape: LogoShape;
  logo_background: boolean;
  frame_style: FrameStyle;
  frame_color: string;
  frame_text_color: string;
  caption: string | null;
}

export interface QRConfigOut extends QRConfig {
  id: string;
  group_id: string;
  logo_url: string | null;
  updated_at: string;
}

export interface QRWarning {
  field: string;
  severity: 'info' | 'warning' | 'error';
  message: string;
}

export interface QRRenderInfo {
  target_url: string;
  contrast_ratio: number;
  is_scannable: boolean;
  warnings: QRWarning[];
  preview_data_uri: string | null;
  png_url: string;
  svg_url: string;
}

export interface QRConfigResponse {
  config: QRConfigOut;
  render: QRRenderInfo;
}

export interface QRPreset {
  id: string;
  label: string;
  description: string;
  config: Partial<QRConfig>;
}

/* -------------------------------------------------------------------------- */
/* Analytics                                                                   */
/* -------------------------------------------------------------------------- */

export type TimeRange = '24h' | '7d' | '30d' | '90d' | '12m';

export interface MetricPoint {
  date: string;
  page_views: number;
  qr_scans: number;
  link_clicks: number;
}

export interface NamedCount {
  id: string | null;
  label: string;
  count: number;
  share: number;
}

export interface AnalyticsTotals {
  page_views: number;
  qr_scans: number;
  link_clicks: number;
  unique_visitors: number;
  click_through_rate: number;
}

export interface GroupAnalytics {
  group_id: string;
  group_name: string;
  range: TimeRange;
  starts_at: string;
  ends_at: string;
  totals: AnalyticsTotals;
  timeseries: MetricPoint[];
  top_links: NamedCount[];
  devices: NamedCount[];
  browsers: NamedCount[];
  referrers: NamedCount[];
}

export interface OrganizationAnalytics {
  range: TimeRange;
  starts_at: string;
  ends_at: string;
  totals: AnalyticsTotals;
  timeseries: MetricPoint[];
  top_groups: NamedCount[];
  top_links: NamedCount[];
  devices: NamedCount[];
}

export interface DashboardActivity {
  id: string;
  action: string;
  description: string;
  actor_name: string | null;
  resource_type: string | null;
  resource_id: string | null;
  created_at: string;
}

export interface DashboardGroupRow {
  id: string;
  name: string;
  slug: string;
  links: number;
  page_views: number;
  qr_scans: number;
  status: 'published' | 'draft' | 'archived';
  updated_at: string;
}

export interface DashboardOverview {
  total_groups: number;
  published_groups: number;
  total_links: number;
  total_page_views: number;
  total_qr_scans: number;
  total_link_clicks: number;
  totals_range: TimeRange;
  timeseries: MetricPoint[];
  recent_activity: DashboardActivity[];
  groups: DashboardGroupRow[];
}

/* -------------------------------------------------------------------------- */
/* Media                                                                       */
/* -------------------------------------------------------------------------- */

export type MediaKind = 'GROUP_LOGO' | 'QR_LOGO' | 'AVATAR' | 'ORG_LOGO';

export interface MediaItem {
  id: string;
  kind: MediaKind;
  public_url: string;
  content_type: string;
  size_bytes: number;
  width: number | null;
  height: number | null;
  original_filename: string | null;
  created_at: string;
}

/* -------------------------------------------------------------------------- */
/* Administration                                                              */
/* -------------------------------------------------------------------------- */

export interface AdminUserRow {
  id: string;
  email: string;
  full_name: string;
  avatar_url: string | null;
  system_role: Role;
  status: UserStatus;
  email_verified: boolean;
  created_at: string;
  last_login_at: string | null;
  organization_role: Role | null;
  organization_name: string | null;
  group_count: number;
}

export interface AuditLogRow {
  id: string;
  action: string;
  actor_id: string | null;
  actor_email: string | null;
  resource_type: string | null;
  resource_id: string | null;
  event_metadata: Record<string, unknown>;
  created_at: string;
}

export interface OrganizationSettings {
  allow_public_registration: boolean;
  default_member_role: Role;
  max_groups_per_user: number;
  require_group_approval: boolean;
}

export interface Organization {
  id: string;
  name: string;
  slug: string;
  description: string | null;
  logo_url: string | null;
  website_url: string | null;
  is_active: boolean;
  settings: OrganizationSettings;
  created_at: string;
  member_count: number;
  group_count: number;
}

export interface SystemStats {
  users: number;
  organizations: number;
  groups: number;
  links: number;
  events_last_30d: number;
  published_groups: number;
}

/* -------------------------------------------------------------------------- */
/* Public page                                                                 */
/* -------------------------------------------------------------------------- */

export interface PublicLink {
  id: string;
  title: string;
  url: string;
  description: string | null;
  icon: string | null;
  style: LinkStyle;
}

export interface PublicGroup {
  name: string;
  slug: string;
  description: string | null;
  logo_url: string | null;
  theme: Theme;
  seo: SEO;
  public_url: string;
  organization: { name: string; slug: string; logo_url: string | null };
  links: PublicLink[];
  qr_png_url: string;
  qr_svg_url: string;
}
