"""Analytics reporting endpoints (dashboard-facing, authenticated)."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.deps import CurrentPrincipal, DbSession
from app.core.rate_limit import Policies, rate_limit
from app.schemas.analytics import (
    DashboardOverview,
    GroupAnalytics,
    OrganizationAnalytics,
    TimeRange,
)
from app.schemas.common import Success
from app.services import analytics_service, group_service

router = APIRouter(tags=["Analytics"])

RangeQuery = Annotated[TimeRange, Query(description="Reporting window")]
LimitQuery = Annotated[int, Query(ge=1, le=50)]


@router.get(
    "/analytics/overview",
    response_model=Success[DashboardOverview],
    dependencies=[Depends(rate_limit(Policies.ANALYTICS_READ))],
    summary="Dashboard overview",
)
async def overview(
    principal: CurrentPrincipal, db: DbSession, range: RangeQuery = "30d"
) -> Success[DashboardOverview]:
    return Success(
        data=await analytics_service.dashboard_overview(db, principal, time_range=range)
    )


@router.get(
    "/analytics/organization",
    response_model=Success[OrganizationAnalytics],
    dependencies=[Depends(rate_limit(Policies.ANALYTICS_READ))],
    summary="Organization-wide analytics",
)
async def organization_analytics(
    principal: CurrentPrincipal,
    db: DbSession,
    range: RangeQuery = "30d",
    limit: LimitQuery = 10,
) -> Success[OrganizationAnalytics]:
    return Success(
        data=await analytics_service.organization_analytics(
            db, principal, time_range=range, limit=limit
        )
    )


@router.get(
    "/groups/{group_id}/analytics",
    response_model=Success[GroupAnalytics],
    dependencies=[Depends(rate_limit(Policies.ANALYTICS_READ))],
    summary="Analytics for one group",
)
async def group_analytics(
    group_id: uuid.UUID,
    principal: CurrentPrincipal,
    db: DbSession,
    range: RangeQuery = "30d",
    limit: LimitQuery = 10,
) -> Success[GroupAnalytics]:
    group = await group_service.get_group_or_404(db, group_id, principal)
    return Success(
        data=await analytics_service.group_analytics(
            db, group, principal, time_range=range, limit=limit
        )
    )
