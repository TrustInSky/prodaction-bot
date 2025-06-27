import asyncio
import logging
import os
import sys
from typing import NoReturn
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine, AsyncSession
from contextlib import asynccontextmanager
from aiogram3_di import setup_di

from app.config import Config
from app.middlewares.database import DatabaseMiddleware, set_database_middleware
from app.middlewares.group_membership import GroupMembershipMiddleware
from app.scheduler import setup_scheduler, shutdown_scheduler
from app.catalog.catalog_router import router as catalog_router
from app.handlers.main_menu import router as main_menu_router
from app.handlers.simple_admin import router as admin_router
from app.handlers.questions import router as questions_router
from app.handlers.hr_questions import hr_questions_router
from app.handlers.user_management import user_management_router
# Удален старый импорт notification_handlers - теперь обработчики в orders/notifications.py
from app.handlers.tpoints_activity import tpoints_activity_router
from app.handlers.auto_events_handlers import router as auto_events_router
from app.handlers.events_management import router as events_management_router
from app.orders.main_router import orders_router
from app.models.models import Base
from app.filters.chat_type import PrivateChatOnly

logger = logging.getLogger(__name__)

def setup_logging() -> None:
    """Настройка логирования"""
    os.makedirs('logs', exist_ok=True)
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('logs/bot.log'),
            logging.StreamHandler()
        ]
    )

async def setup_database(config: Config) -> tuple[async_sessionmaker[AsyncSession], create_async_engine]:
    """Настройка базы данных"""
    try:
        engine = create_async_engine(
            config.DATABASE_URL,
            echo=False,
            pool_pre_ping=True  # Проверка соединения перед использованием
        )
        
        # Создаем таблицы в базе данных
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        
        # Создаем фабрику сессий
        async_session = async_sessionmaker(engine, expire_on_commit=False)
        
        return async_session, engine
    except Exception as e:
        logger.error(f"Failed to setup database: {e}")
        raise

def setup_routers(dp: Dispatcher) -> None:
    """Настройка роутеров"""
    routers = [
        user_management_router,
        catalog_router,  # Включает все роутеры каталога
        orders_router,
        # notification_router удален - теперь обработчики в orders_router
        admin_router,  # Новая упрощенная админка
        questions_router,
        hr_questions_router,  # HR управление вопросами
        tpoints_activity_router,  # Обработчики T-Points активностей
        auto_events_router,  # Обработчики кнопок автоуведомлений
        events_management_router,  # Ручная проверка событий для HR
        main_menu_router,  # Главное меню ПОСЛЕДНИМ - чтобы заглушки не перехватывали события
    ]
    
    # ИСПРАВЛЕНО: Добавляем фильтр для работы только в личных чатах
    private_chat_filter = PrivateChatOnly()
    
    for router in routers:
        # Применяем фильтр ко всем обработчикам роутера
        router.message.filter(private_chat_filter)
        router.callback_query.filter(private_chat_filter)
        
        dp.include_router(router)
        logger.info(f"✅ Router registered with private chat filter: {router.name}")

def setup_middlewares(dp: Dispatcher, async_session: async_sessionmaker, config: Config, bot: Bot) -> None:
    """Настройка middleware"""
    # Создаем экземпляр DatabaseMiddleware
    database_middleware = DatabaseMiddleware(async_session, bot)
    
    # Устанавливаем ссылку на middleware для фильтров
    set_database_middleware(database_middleware)
    
    # Регистрируем middleware для сообщений
    dp.message.middleware(database_middleware)
    dp.message.middleware(GroupMembershipMiddleware(config.GROUP_ID))
    
    # Регистрируем middleware для callback_query
    dp.callback_query.middleware(database_middleware)
    dp.callback_query.middleware(GroupMembershipMiddleware(config.GROUP_ID))

async def cleanup(bot: Bot, engine: create_async_engine) -> None:
    """Очистка ресурсов при завершении"""
    try:
        logger.info("Stopping scheduler...")
        await shutdown_scheduler()
        
        logger.info("Closing bot session...")
        await bot.session.close()
        
        logger.info("Closing database connections...")
        await engine.dispose()
        
    except Exception as e:
        logger.error(f"Error during cleanup: {e}")

async def main() -> NoReturn:
    """Основная функция запуска бота"""
    try:
        # Настраиваем логирование
        setup_logging()
        logger.info("Starting bot...")
        
        # Загружаем конфигурацию
        config = Config()
        
        # Проверяем наличие необходимых переменных окружения
        if not config.BOT_TOKEN:
            logger.error("BOT_TOKEN is not set!")
            sys.exit(1)
        
        if not config.GROUP_ID:
            logger.error("GROUP_ID is not set!")
            sys.exit(1)
        
        # Настраиваем базу данных
        async_session, engine = await setup_database(config)
        
        # Создаем бота и диспетчер
        bot = Bot(
            token=config.BOT_TOKEN,
            default=DefaultBotProperties(parse_mode=ParseMode.HTML)
        )
        storage = MemoryStorage()
        dp = Dispatcher(storage=storage)
        
        # Настраиваем aiogram3-di ПЕРЕД middleware
        setup_di(dp)
        
        # Настраиваем middleware
        setup_middlewares(dp, async_session, config, bot)
        
        # Регистрируем обработчики
        setup_routers(dp)
        
        # Запускаем планировщик уведомлений
        await setup_scheduler(async_session, bot)
        
        # Запускаем бота
        logger.info(f"🚀 Bot started! Will only respond in PRIVATE chats, not in groups")
        logger.info(f"📊 All routers registered with private chat filter")
        logger.info(f"👥 Group monitoring enabled for GROUP_ID: {config.GROUP_ID}")
        
        try:
            await dp.start_polling(bot)
        except Exception as e:
            logger.error(f"Error during bot polling: {e}")
            raise
        finally:
            await cleanup(bot, engine)
            
    except Exception as e:
        logger.critical(f"Critical error occurred: {e}")
        sys.exit(1)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped!")
    except Exception as e:
        logger.critical(f"Unexpected error occurred: {e}")
        sys.exit(1)