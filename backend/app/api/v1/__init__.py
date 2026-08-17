"""API v1 router assembly."""

from fastapi import APIRouter

from app.api.v1 import admin, analytics, auth, groups, links, media, public, qr

api_router = APIRouter()

# Public routes first so `/public/...` can never be shadowed by an authenticated
# path with a matching shape.
api_router.include_router(public.router)
api_router.include_router(auth.router)
api_router.include_router(groups.router)
api_router.include_router(links.router)
api_router.include_router(qr.router)
api_router.include_router(analytics.router)
api_router.include_router(media.router)
api_router.include_router(admin.router)

__all__ = ["api_router"]
