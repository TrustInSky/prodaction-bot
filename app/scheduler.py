import asyncio
import logging
from datetime import datetime, time
from typing import NoReturn, Dict, Any
from aiogram import Bot
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

from .services.auto_events_service import AutoEventsService
from .repositories.auto_events_repository import AutoEventsRepository
from .config import Config

logger = logging.getLogger(__name__)


class AutoEventsScheduler:
    """Планировщик для автоматических событий системы"""
    
    def __init__(self, session_factory: async_sessionmaker[AsyncSession], bot: Bot):
        self.session_factory = session_factory
        self.bot = bot
        self.running = False
    
    async def start(self):
        """Запустить планировщик"""
        if self.running:
            logger.warning("Scheduler is already running")
            return
        
        self.running = True
        logger.info("AutoEvents scheduler started")
        
        # Запускаем основной цикл планировщика
        asyncio.create_task(self._run_scheduler())
    
    async def stop(self):
        """Остановить планировщик"""
        self.running = False
        logger.info("AutoEvents scheduler stopped")
    
    async def _run_scheduler(self):
        """Основной цикл планировщика"""
        last_check_dates = {
            'birthday': None,
            'anniversary': None,
            'stock_low': None
        }
        
        while self.running:
            try:
                now = datetime.now()
                current_date = now.date()
                current_time = now.time()
                
                # Получаем настройки всех событий
                async with self.session_factory() as session:
                    repository = AutoEventsRepository(session)
                    all_settings = await repository.get_all_event_settings()
                
                # Проверяем каждый тип события
                for settings in all_settings:
                    if not settings.is_enabled:
                        continue
                    
                    event_type = settings.event_type
                    notification_time = self._parse_time(settings.notification_time)
                    
                    # Проверяем наступил ли новый день и подходящее ли время
                    if (last_check_dates[event_type] != current_date and 
                            self._is_notification_time(current_time, notification_time)):
                        
                        logger.info(f"Running {event_type} check for {current_date}")
                        await self._run_event_check(event_type)
                        last_check_dates[event_type] = current_date
                
                # Спим 30 минут перед следующей проверкой
                await asyncio.sleep(1800)  # 30 минут
                
            except Exception as e:
                logger.error(f"Error in scheduler loop: {e}")
                # В случае ошибки спим 10 минут и продолжаем
                await asyncio.sleep(600)
    
    def _parse_time(self, time_str: str) -> time:
        """Парсить время из строки"""
        try:
            hour, minute = map(int, time_str.split(':'))
            return time(hour, minute)
        except (ValueError, AttributeError):
            # По умолчанию 9:00
            return time(9, 0)
    
    def _is_notification_time(self, current_time: time, target_time: time) -> bool:
        """Проверить, подходящее ли время для отправки уведомлений"""
        # Проверяем в течение 30 минут после целевого времени
        from datetime import timedelta, datetime
        
        today = datetime.now().date()
        current_datetime = datetime.combine(today, current_time)
        target_datetime = datetime.combine(today, target_time)
        
        # Время подходит если прошло не больше 30 минут с целевого времени
        time_diff = current_datetime - target_datetime
        return timedelta(0) <= time_diff <= timedelta(minutes=30)
    
    async def _run_event_check(self, event_type: str) -> Dict[str, Any]:
        """Запустить проверку определенного типа события"""
        async with self.session_factory() as session:
            try:
                auto_events_service = AutoEventsService(session, self.bot)
                
                if event_type == 'birthday':
                    results = await auto_events_service.check_birthdays()
                elif event_type == 'anniversary':
                    results = await auto_events_service.check_anniversaries()
                elif event_type == 'stock_low':
                    results = await auto_events_service.check_low_stock()
                else:
                    logger.warning(f"Unknown event type: {event_type}")
                    return {'errors': [f'Unknown event type: {event_type}']}
                
                # Коммитим изменения в базе данных
                await session.commit()
                
                logger.info(f"{event_type.capitalize()} check completed: {results}")
                
                if results.get('errors'):
                    logger.warning(f"{event_type.capitalize()} check errors: {results['errors']}")
                
                return results
                
            except Exception as e:
                logger.error(f"Error running {event_type} check: {e}")
                await session.rollback()
                return {'errors': [str(e)]}
    
    async def run_manual_check(self, event_type: str = None) -> Dict[str, Any]:
        """Запустить проверку событий вручную (для тестирования)"""
        async with self.session_factory() as session:
            try:
                auto_events_service = AutoEventsService(session, self.bot)
                
                if event_type == 'birthday':
                    results = await auto_events_service.check_birthdays()
                elif event_type == 'anniversary':
                    results = await auto_events_service.check_anniversaries()
                elif event_type == 'stock_low':
                    results = await auto_events_service.check_low_stock()
                elif event_type is None:
                    # Запускаем все проверки
                    birthday_results = await auto_events_service.check_birthdays()
                    anniversary_results = await auto_events_service.check_anniversaries()
                    stock_results = await auto_events_service.check_low_stock()
                    
                    results = {
                        'birthday': birthday_results,
                        'anniversary': anniversary_results,
                        'stock': stock_results
                    }
                else:
                    return {'errors': [f'Unknown event type: {event_type}']}
                
                await session.commit()
                return results
                
            except Exception as e:
                await session.rollback()
                logger.error(f"Error in manual check: {e}")
                return {'errors': [str(e)]}


# Глобальная переменная для планировщика
scheduler: AutoEventsScheduler = None


async def setup_scheduler(session_factory: async_sessionmaker[AsyncSession], bot: Bot):
    """Настроить и запустить планировщик"""
    global scheduler
    
    try:
        scheduler = AutoEventsScheduler(session_factory, bot)
        await scheduler.start()
        logger.info("AutoEvents scheduler setup completed")
    
    except Exception as e:
        logger.error(f"Error setting up scheduler: {e}")
        raise


async def shutdown_scheduler():
    """Остановить планировщик"""
    global scheduler
    
    if scheduler:
        await scheduler.stop()
        logger.info("AutoEvents scheduler shutdown completed")


async def manual_events_check(event_type: str = None) -> Dict[str, Any]:
    """Запустить проверку событий вручную"""
    global scheduler
    
    if scheduler:
        return await scheduler.run_manual_check(event_type)
    else:
        return {'errors': ['Scheduler not initialized']}


# Обратная совместимость
async def manual_birthday_check() -> Dict[str, Any]:
    """Запустить проверку дней рождения вручную (обратная совместимость)"""
    return await manual_events_check('birthday') 