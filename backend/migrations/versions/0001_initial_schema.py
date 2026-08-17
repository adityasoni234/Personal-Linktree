"""Initial schema

Revision ID: 0001_initial
Revises: 
Created: 2026-08-17 12:28:28.229916
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '0001_initial'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.create_table('organizations',
    sa.Column('name', sa.String(length=120), nullable=False),
    sa.Column('slug', sa.String(length=64), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('logo_url', sa.String(length=512), nullable=True),
    sa.Column('website_url', sa.String(length=512), nullable=True),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('settings', sa.JSON(), server_default='{}', nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_organizations'))
    )
    op.create_index(op.f('ix_organizations_slug'), 'organizations', ['slug'], unique=True)

    op.create_table('users',
    sa.Column('email', sa.String(length=320), nullable=False),
    sa.Column('full_name', sa.String(length=120), nullable=False),
    sa.Column('password_hash', sa.Text(), nullable=False),
    sa.Column('avatar_url', sa.String(length=512), nullable=True),
    sa.Column('system_role', sa.Enum('SUPER_ADMIN', 'ADMIN', 'EDITOR', 'USER', name='role', native_enum=False, length=32), nullable=False),
    sa.Column('status', sa.Enum('ACTIVE', 'SUSPENDED', 'PENDING', 'DELETED', name='user_status', native_enum=False, length=32), nullable=False),
    sa.Column('email_verified', sa.Boolean(), nullable=False),
    sa.Column('last_login_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('tokens_valid_after', sa.DateTime(timezone=True), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_users'))
    )
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)
    op.create_index('ix_users_status_created_at', 'users', ['status', 'created_at'], unique=False)

    op.create_table('audit_logs',
    sa.Column('organization_id', sa.Uuid(), nullable=True),
    sa.Column('actor_id', sa.Uuid(), nullable=True),
    sa.Column('actor_email', sa.String(length=320), nullable=True),
    sa.Column('action', sa.Enum('USER_REGISTERED', 'LOGIN_SUCCEEDED', 'LOGIN_FAILED', 'LOGOUT', 'TOKEN_REFRESHED', 'TOKEN_REUSE_DETECTED', 'PASSWORD_CHANGED', 'PASSWORD_RESET_REQUESTED', 'PASSWORD_RESET_COMPLETED', 'SESSION_REVOKED', 'GROUP_CREATED', 'GROUP_UPDATED', 'GROUP_DELETED', 'GROUP_ARCHIVED', 'GROUP_RESTORED', 'GROUP_PUBLISHED', 'GROUP_UNPUBLISHED', 'GROUP_DUPLICATED', 'GROUP_SLUG_CHANGED', 'GROUP_REORDERED', 'LINK_CREATED', 'LINK_UPDATED', 'LINK_DELETED', 'LINK_REORDERED', 'QR_CONFIG_UPDATED', 'MEDIA_UPLOADED', 'MEDIA_DELETED', 'ROLE_CHANGED', 'USER_SUSPENDED', 'USER_REACTIVATED', 'USER_DELETED', 'MEMBER_ADDED', 'MEMBER_REMOVED', 'ORG_SETTINGS_UPDATED', name='audit_action', native_enum=False, length=32), nullable=False),
    sa.Column('resource_type', sa.Enum('USER', 'ORGANIZATION', 'MEMBERSHIP', 'GROUP', 'LINK', 'QR_CONFIGURATION', 'MEDIA', 'SESSION', name='resource_type', native_enum=False, length=32), nullable=True),
    sa.Column('resource_id', sa.String(length=64), nullable=True),
    sa.Column('event_metadata', sa.JSON(), server_default='{}', nullable=False),
    sa.Column('ip_hash', sa.String(length=64), nullable=True),
    sa.Column('user_agent_label', sa.String(length=120), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.ForeignKeyConstraint(['actor_id'], ['users.id'], name=op.f('fk_audit_logs_actor_id_users'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], name=op.f('fk_audit_logs_organization_id_organizations'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_audit_logs'))
    )
    op.create_index('ix_audit_actor_created', 'audit_logs', ['actor_id', 'created_at'], unique=False)
    op.create_index(op.f('ix_audit_logs_action'), 'audit_logs', ['action'], unique=False)
    op.create_index(op.f('ix_audit_logs_actor_id'), 'audit_logs', ['actor_id'], unique=False)
    op.create_index(op.f('ix_audit_logs_created_at'), 'audit_logs', ['created_at'], unique=False)
    op.create_index(op.f('ix_audit_logs_organization_id'), 'audit_logs', ['organization_id'], unique=False)
    op.create_index('ix_audit_org_created', 'audit_logs', ['organization_id', 'created_at'], unique=False)
    op.create_index('ix_audit_resource', 'audit_logs', ['resource_type', 'resource_id'], unique=False)

    op.create_table('groups',
    sa.Column('organization_id', sa.Uuid(), nullable=False),
    sa.Column('owner_id', sa.Uuid(), nullable=True),
    sa.Column('name', sa.String(length=120), nullable=False),
    sa.Column('slug', sa.String(length=64), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('logo_url', sa.String(length=512), nullable=True),
    sa.Column('theme', sa.JSON(), server_default='{}', nullable=False),
    sa.Column('seo', sa.JSON(), server_default='{}', nullable=False),
    sa.Column('is_published', sa.Boolean(), nullable=False),
    sa.Column('is_archived', sa.Boolean(), nullable=False),
    sa.Column('position', sa.Integer(), nullable=False),
    sa.Column('published_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], name=op.f('fk_groups_organization_id_organizations'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['owner_id'], ['users.id'], name=op.f('fk_groups_owner_id_users'), ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_groups'))
    )
    op.create_index('ix_groups_org_position', 'groups', ['organization_id', 'position'], unique=False)
    op.create_index(op.f('ix_groups_organization_id'), 'groups', ['organization_id'], unique=False)
    op.create_index(op.f('ix_groups_owner_id'), 'groups', ['owner_id'], unique=False)
    op.create_index('ix_groups_public_lookup', 'groups', ['slug', 'is_published', 'is_archived'], unique=False)
    op.create_index(op.f('ix_groups_slug'), 'groups', ['slug'], unique=True)

    op.create_table('media',
    sa.Column('organization_id', sa.Uuid(), nullable=False),
    sa.Column('uploaded_by_id', sa.Uuid(), nullable=True),
    sa.Column('kind', sa.Enum('GROUP_LOGO', 'QR_LOGO', 'AVATAR', 'ORG_LOGO', name='media_kind', native_enum=False, length=32), nullable=False),
    sa.Column('storage_key', sa.String(length=512), nullable=False),
    sa.Column('public_url', sa.String(length=1024), nullable=False),
    sa.Column('original_filename', sa.String(length=255), nullable=True),
    sa.Column('content_type', sa.String(length=100), nullable=False),
    sa.Column('size_bytes', sa.BigInteger(), nullable=False),
    sa.Column('width', sa.Integer(), nullable=True),
    sa.Column('height', sa.Integer(), nullable=True),
    sa.Column('checksum_sha256', sa.String(length=64), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], name=op.f('fk_media_organization_id_organizations'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['uploaded_by_id'], ['users.id'], name=op.f('fk_media_uploaded_by_id_users'), ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_media')),
    sa.UniqueConstraint('storage_key', name=op.f('uq_media_storage_key'))
    )
    op.create_index(op.f('ix_media_checksum_sha256'), 'media', ['checksum_sha256'], unique=False)
    op.create_index('ix_media_org_kind', 'media', ['organization_id', 'kind'], unique=False)
    op.create_index(op.f('ix_media_organization_id'), 'media', ['organization_id'], unique=False)

    op.create_table('memberships',
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('organization_id', sa.Uuid(), nullable=False),
    sa.Column('role', sa.Enum('SUPER_ADMIN', 'ADMIN', 'EDITOR', 'USER', name='role', native_enum=False, length=32), nullable=False),
    sa.Column('is_default', sa.Boolean(), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], name=op.f('fk_memberships_organization_id_organizations'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_memberships_user_id_users'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_memberships')),
    sa.UniqueConstraint('user_id', 'organization_id', name='uq_memberships_user_org')
    )
    op.create_index('ix_memberships_org_role', 'memberships', ['organization_id', 'role'], unique=False)
    op.create_index(op.f('ix_memberships_organization_id'), 'memberships', ['organization_id'], unique=False)
    op.create_index(op.f('ix_memberships_user_id'), 'memberships', ['user_id'], unique=False)

    op.create_table('password_reset_tokens',
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('token_hash', sa.String(length=64), nullable=False),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('used_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('invalidated', sa.Boolean(), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_password_reset_tokens_user_id_users'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_password_reset_tokens'))
    )
    op.create_index(op.f('ix_password_reset_tokens_token_hash'), 'password_reset_tokens', ['token_hash'], unique=True)
    op.create_index(op.f('ix_password_reset_tokens_user_id'), 'password_reset_tokens', ['user_id'], unique=False)

    op.create_table('user_sessions',
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('token_hash', sa.String(length=64), nullable=False),
    sa.Column('previous_token_hash', sa.String(length=64), nullable=True),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('last_used_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('revoked_reason', sa.String(length=64), nullable=True),
    sa.Column('user_agent_label', sa.String(length=120), nullable=True),
    sa.Column('ip_hash', sa.String(length=64), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_user_sessions_user_id_users'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_user_sessions'))
    )
    op.create_index(op.f('ix_user_sessions_previous_token_hash'), 'user_sessions', ['previous_token_hash'], unique=False)
    op.create_index(op.f('ix_user_sessions_token_hash'), 'user_sessions', ['token_hash'], unique=True)
    op.create_index(op.f('ix_user_sessions_user_id'), 'user_sessions', ['user_id'], unique=False)
    op.create_index('ix_user_sessions_user_revoked', 'user_sessions', ['user_id', 'revoked_at'], unique=False)

    op.create_table('links',
    sa.Column('group_id', sa.Uuid(), nullable=False),
    sa.Column('title', sa.String(length=120), nullable=False),
    sa.Column('url', sa.String(length=2048), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('icon', sa.String(length=64), nullable=True),
    sa.Column('style', sa.JSON(), server_default='{}', nullable=False),
    sa.Column('position', sa.Integer(), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['group_id'], ['groups.id'], name=op.f('fk_links_group_id_groups'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_links'))
    )
    op.create_index('ix_links_group_active', 'links', ['group_id', 'is_active'], unique=False)
    op.create_index(op.f('ix_links_group_id'), 'links', ['group_id'], unique=False)
    op.create_index('ix_links_group_position', 'links', ['group_id', 'position'], unique=False)

    op.create_table('qr_configurations',
    sa.Column('group_id', sa.Uuid(), nullable=False),
    sa.Column('preset', sa.String(length=32), nullable=True),
    sa.Column('foreground_color', sa.String(length=9), nullable=False),
    sa.Column('background_color', sa.String(length=9), nullable=False),
    sa.Column('transparent_background', sa.Boolean(), nullable=False),
    sa.Column('gradient_type', sa.Enum('none', 'linear', 'radial', name='gradient_type', native_enum=False, length=32), nullable=False),
    sa.Column('gradient_start_color', sa.String(length=9), nullable=True),
    sa.Column('gradient_end_color', sa.String(length=9), nullable=True),
    sa.Column('gradient_angle', sa.Integer(), nullable=False),
    sa.Column('dot_style', sa.Enum('square', 'rounded', 'dot', 'classy', 'diamond', 'vertical', 'horizontal', name='dot_style', native_enum=False, length=32), nullable=False),
    sa.Column('eye_frame_style', sa.Enum('square', 'rounded', 'circle', 'leaf', 'shield', name='eye_frame_style', native_enum=False, length=32), nullable=False),
    sa.Column('eye_ball_style', sa.Enum('square', 'rounded', 'circle', 'diamond', name='eye_ball_style', native_enum=False, length=32), nullable=False),
    sa.Column('eye_color', sa.String(length=9), nullable=True),
    sa.Column('eye_ball_color', sa.String(length=9), nullable=True),
    sa.Column('margin', sa.Integer(), nullable=False),
    sa.Column('error_correction', sa.Enum('L', 'M', 'Q', 'H', name='error_correction', native_enum=False, length=32), nullable=False),
    sa.Column('logo_media_id', sa.Uuid(), nullable=True),
    sa.Column('logo_size', sa.Float(), nullable=False),
    sa.Column('logo_padding', sa.Float(), nullable=False),
    sa.Column('logo_shape', sa.Enum('square', 'rounded', 'circle', name='logo_shape', native_enum=False, length=32), nullable=False),
    sa.Column('logo_background', sa.Boolean(), nullable=False),
    sa.Column('frame_style', sa.Enum('none', 'simple', 'rounded', 'banner_bottom', 'banner_top', 'ticket', name='frame_style', native_enum=False, length=32), nullable=False),
    sa.Column('frame_color', sa.String(length=9), nullable=False),
    sa.Column('frame_text_color', sa.String(length=9), nullable=False),
    sa.Column('caption', sa.String(length=48), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['group_id'], ['groups.id'], name=op.f('fk_qr_configurations_group_id_groups'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['logo_media_id'], ['media.id'], name=op.f('fk_qr_configurations_logo_media_id_media'), ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_qr_configurations'))
    )
    op.create_index(op.f('ix_qr_configurations_group_id'), 'qr_configurations', ['group_id'], unique=True)

    op.create_table('analytics_events',
    sa.Column('organization_id', sa.Uuid(), nullable=False),
    sa.Column('group_id', sa.Uuid(), nullable=False),
    sa.Column('link_id', sa.Uuid(), nullable=True),
    sa.Column('event_type', sa.Enum('PAGE_VIEW', 'QR_SCAN', 'LINK_CLICK', 'SHARE', name='analytics_event_type', native_enum=False, length=32), nullable=False),
    sa.Column('occurred_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('device_type', sa.Enum('MOBILE', 'TABLET', 'DESKTOP', 'BOT', 'UNKNOWN', name='device_type', native_enum=False, length=32), nullable=False),
    sa.Column('browser', sa.String(length=40), nullable=True),
    sa.Column('os', sa.String(length=40), nullable=True),
    sa.Column('referrer_domain', sa.String(length=255), nullable=True),
    sa.Column('country', sa.String(length=2), nullable=True),
    sa.Column('visitor_hash', sa.String(length=64), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.ForeignKeyConstraint(['group_id'], ['groups.id'], name=op.f('fk_analytics_events_group_id_groups'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['link_id'], ['links.id'], name=op.f('fk_analytics_events_link_id_links'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], name=op.f('fk_analytics_events_organization_id_organizations'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_analytics_events'))
    )
    op.create_index(op.f('ix_analytics_events_group_id'), 'analytics_events', ['group_id'], unique=False)
    op.create_index(op.f('ix_analytics_events_link_id'), 'analytics_events', ['link_id'], unique=False)
    op.create_index(op.f('ix_analytics_events_occurred_at'), 'analytics_events', ['occurred_at'], unique=False)
    op.create_index(op.f('ix_analytics_events_organization_id'), 'analytics_events', ['organization_id'], unique=False)
    op.create_index(op.f('ix_analytics_events_visitor_hash'), 'analytics_events', ['visitor_hash'], unique=False)
    op.create_index('ix_analytics_group_type_time', 'analytics_events', ['group_id', 'event_type', 'occurred_at'], unique=False)
    op.create_index('ix_analytics_link_time', 'analytics_events', ['link_id', 'occurred_at'], unique=False)
    op.create_index('ix_analytics_org_time', 'analytics_events', ['organization_id', 'occurred_at'], unique=False)

def downgrade() -> None:
    op.drop_index('ix_analytics_org_time', table_name='analytics_events')
    op.drop_index('ix_analytics_link_time', table_name='analytics_events')
    op.drop_index('ix_analytics_group_type_time', table_name='analytics_events')
    op.drop_index(op.f('ix_analytics_events_visitor_hash'), table_name='analytics_events')
    op.drop_index(op.f('ix_analytics_events_organization_id'), table_name='analytics_events')
    op.drop_index(op.f('ix_analytics_events_occurred_at'), table_name='analytics_events')
    op.drop_index(op.f('ix_analytics_events_link_id'), table_name='analytics_events')
    op.drop_index(op.f('ix_analytics_events_group_id'), table_name='analytics_events')

    op.drop_table('analytics_events')
    op.drop_index(op.f('ix_qr_configurations_group_id'), table_name='qr_configurations')

    op.drop_table('qr_configurations')
    op.drop_index('ix_links_group_position', table_name='links')
    op.drop_index(op.f('ix_links_group_id'), table_name='links')
    op.drop_index('ix_links_group_active', table_name='links')

    op.drop_table('links')
    op.drop_index('ix_user_sessions_user_revoked', table_name='user_sessions')
    op.drop_index(op.f('ix_user_sessions_user_id'), table_name='user_sessions')
    op.drop_index(op.f('ix_user_sessions_token_hash'), table_name='user_sessions')
    op.drop_index(op.f('ix_user_sessions_previous_token_hash'), table_name='user_sessions')

    op.drop_table('user_sessions')
    op.drop_index(op.f('ix_password_reset_tokens_user_id'), table_name='password_reset_tokens')
    op.drop_index(op.f('ix_password_reset_tokens_token_hash'), table_name='password_reset_tokens')

    op.drop_table('password_reset_tokens')
    op.drop_index(op.f('ix_memberships_user_id'), table_name='memberships')
    op.drop_index(op.f('ix_memberships_organization_id'), table_name='memberships')
    op.drop_index('ix_memberships_org_role', table_name='memberships')

    op.drop_table('memberships')
    op.drop_index(op.f('ix_media_organization_id'), table_name='media')
    op.drop_index('ix_media_org_kind', table_name='media')
    op.drop_index(op.f('ix_media_checksum_sha256'), table_name='media')

    op.drop_table('media')
    op.drop_index(op.f('ix_groups_slug'), table_name='groups')
    op.drop_index('ix_groups_public_lookup', table_name='groups')
    op.drop_index(op.f('ix_groups_owner_id'), table_name='groups')
    op.drop_index(op.f('ix_groups_organization_id'), table_name='groups')
    op.drop_index('ix_groups_org_position', table_name='groups')

    op.drop_table('groups')
    op.drop_index('ix_audit_resource', table_name='audit_logs')
    op.drop_index('ix_audit_org_created', table_name='audit_logs')
    op.drop_index(op.f('ix_audit_logs_organization_id'), table_name='audit_logs')
    op.drop_index(op.f('ix_audit_logs_created_at'), table_name='audit_logs')
    op.drop_index(op.f('ix_audit_logs_actor_id'), table_name='audit_logs')
    op.drop_index(op.f('ix_audit_logs_action'), table_name='audit_logs')
    op.drop_index('ix_audit_actor_created', table_name='audit_logs')

    op.drop_table('audit_logs')
    op.drop_index('ix_users_status_created_at', table_name='users')
    op.drop_index(op.f('ix_users_email'), table_name='users')

    op.drop_table('users')
    op.drop_index(op.f('ix_organizations_slug'), table_name='organizations')

    op.drop_table('organizations')
