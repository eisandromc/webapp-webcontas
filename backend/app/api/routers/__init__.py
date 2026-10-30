from fastapi import APIRouter

from app.api.routers import backup, categories, imports, invoices, months, people, records, reports, settings, system


router = APIRouter(prefix="/api")
for module in (system, backup, people, months, records, categories, reports, settings, invoices, imports):
    router.include_router(module.router)
