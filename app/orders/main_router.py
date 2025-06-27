from aiogram import Router
import logging

from .management import management_router
from .analytics import analytics_router  
from .notifications import notifications_router
from .user_orders import user_orders_router

logger = logging.getLogger(__name__)
orders_router = Router(name="orders_main")

# Подключаем под-роутеры
logger.info("Registering user_orders_router to orders_router")
orders_router.include_router(user_orders_router)

logger.info("Registering management_router to orders_router")
orders_router.include_router(management_router)

logger.info("Registering analytics_router to orders_router")
orders_router.include_router(analytics_router)

logger.info("Registering notifications_router to orders_router")
orders_router.include_router(notifications_router)

__all__ = ["orders_router"]