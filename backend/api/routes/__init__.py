from backend.api.routes.health import router as health_router
from backend.api.routes.query import router as query_router
from backend.api.routes.admin import router as admin_router

__all__ = ["health_router", "query_router", "admin_router"]
