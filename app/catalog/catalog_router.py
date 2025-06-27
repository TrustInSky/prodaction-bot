from aiogram import Router, F
from aiogram.filters import Command
from .navigation_handlers import router as navigation_router
from .product_handlers import router as product_router
from .cart import router as cart_router
from .checkout_handlers import router as checkout_router
from .catalog_management import catalog_management_router as catalog_management

router = Router(name="catalog")

# Подключаем все роутеры каталога

router.include_router(navigation_router)
router.include_router(product_router)
router.include_router(cart_router) 
router.include_router(checkout_router)
router.include_router(catalog_management)