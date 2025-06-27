"""
Единый сервис для управления автоматическими событиями системы:
- Дни рождения
- Юбилеи работы  
- Остатки товаров
"""
import logging
from datetime import datetime, date, timedelta
from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.models import (
    AutoEventSettings, AdminNotificationPreferences, 
    User, Product, TPointsTransaction
)
from ..services.transaction_service import TransactionService
from ..repositories.auto_events_repository import AutoEventsRepository

logger = logging.getLogger(__name__)


class AutoEventsService:
    """Единый сервис для автоматических событий"""
    
    def __init__(self, session: AsyncSession, bot=None):
        self.session = session
        self.bot = bot
        self.transaction_service = TransactionService(session)
        self.repository = AutoEventsRepository(session)
    
    # =============================================================================
    # УПРАВЛЕНИЕ НАСТРОЙКАМИ СОБЫТИЙ
    # =============================================================================
    
    async def get_event_settings(self, event_type: str) -> Optional[AutoEventSettings]:
        """Получить настройки события по типу"""
        return await self.repository.get_event_settings(event_type)
    
    async def get_all_event_settings(self) -> List[AutoEventSettings]:
        """Получить все настройки событий"""
        return await self.repository.get_all_event_settings()
    
    async def update_event_settings(self, event_type: str, **kwargs) -> bool:
        """Обновить настройки события"""
        try:
            settings = await self.get_event_settings(event_type)
            if not settings:
                # Создаём новые настройки если их нет
                settings = await self.repository.create_event_settings(event_type, **kwargs)
            else:
                # Обновляем существующие настройки
                settings = await self.repository.update_event_settings(settings, **kwargs)
            
            # ИСПРАВЛЕНО: Убрана прямая работа с session - это делает middleware
            logger.info(f"Updated {event_type} settings: {kwargs}")
            return True
            
        except Exception as e:
            logger.error(f"Error updating {event_type} settings: {e}")
            # ИСПРАВЛЕНО: Убран rollback - это делает middleware при ошибке
            return False
    
    # =============================================================================
    # УПРАВЛЕНИЕ ПЕРСОНАЛЬНЫМИ НАСТРОЙКАМИ АДМИНОВ
    # =============================================================================
    
    async def get_admin_preferences(self, user_id: int) -> AdminNotificationPreferences:
        """Получить персональные настройки админа (создать если нет)"""
        preferences = await self.repository.get_admin_preferences(user_id)
        
        if not preferences:
            # Создаём настройки по умолчанию для нового админа
            preferences = await self.repository.create_admin_preferences(user_id)
            # ИСПРАВЛЕНО: Убран commit - это делает middleware
        
        return preferences
    
    async def update_admin_preferences(self, user_id: int, **kwargs) -> bool:
        """Обновить персональные настройки админа"""
        try:
            preferences = await self.get_admin_preferences(user_id)
            preferences = await self.repository.update_admin_preferences(preferences, **kwargs)
            
            # ИСПРАВЛЕНО: Убран commit - это делает middleware
            logger.info(f"Updated admin {user_id} preferences: {kwargs}")
            return True
            
        except Exception as e:
            logger.error(f"Error updating admin {user_id} preferences: {e}")
            # ИСПРАВЛЕНО: Убран rollback - это делает middleware
            return False
    
    async def get_all_hr_users(self) -> List[User]:
        """Получить всех активных HR пользователей"""
        return await self.repository.get_all_hr_users()
    
    # =============================================================================
    # ПРОВЕРКА И ОБРАБОТКА ДНЕЙ РОЖДЕНИЯ
    # =============================================================================
    
    async def check_birthdays(self) -> Dict[str, Any]:
        """Проверить дни рождения и отправить уведомления"""
        results = {
            'birthday_notifications_sent': 0,
            'tpoints_awarded': 0,
            'errors': []
        }
        
        try:
            # Получаем настройки дней рождения
            birthday_settings = await self.get_event_settings('birthday')
            if not birthday_settings or not birthday_settings.is_enabled:
                logger.info("Birthday notifications are disabled")
                return results
            
            # Парсим дни уведомлений
            notification_days = self._parse_notification_days(birthday_settings.notification_days)
            today = date.today()
            
            # Получаем всех активных пользователей с днями рождения
            users = await self.repository.get_users_with_birthdays()
            
            for user in users:
                if not user.birth_date:
                    continue
                
                # Проверяем, сколько дней до дня рождения
                days_until_birthday = self._days_until_birthday(user.birth_date, today)
                
                if days_until_birthday in notification_days:
                    # Отправляем уведомление
                    if await self._send_birthday_notification(user, days_until_birthday, birthday_settings):
                        results['birthday_notifications_sent'] += 1
                    
                    # Начисляем T-Points в день рождения
                    if days_until_birthday == 0 and birthday_settings.tpoints_amount > 0:
                        # Проверяем, не начисляли ли уже в этом году
                        if not await self.repository.check_birthday_transaction_exists(user.telegram_id, today.year):
                            if await self._award_birthday_points(user, birthday_settings.tpoints_amount):
                                results['tpoints_awarded'] += birthday_settings.tpoints_amount
            
            logger.info(f"Birthday check completed: {results}")
            return results
            
        except Exception as e:
            error_msg = f"Error in birthday check: {e}"
            logger.error(error_msg)
            results['errors'].append(error_msg)
            return results
    
    async def _send_birthday_notification(self, user: User, days_until: int, settings: AutoEventSettings) -> bool:
        """Отправить уведомление о дне рождения"""
        try:
            if not self.bot:
                return False
            
            # Получаем HR пользователей с включенными уведомлениями
            hr_users = await self._get_hr_users_for_notifications('birthday')
            
            # Формируем сообщение для HR
            username = f"@{user.username}" if user.username else user.fullname
            
            if days_until == 0:
                message = f"🎂 <b>Сегодня день рождения!</b>\n\n👤 {username}\n🎉 Не забудьте отправить поздравление в общую группу!"
                button_text = "Спасибо"
                callback_data = f"birthday_hr_thanks_{user.telegram_id}"
            else:
                message = f"🎂 <b>Скоро день рождения</b>\n\n👤 {username}\n📅 Через {days_until} дн.\n\n💡 Не забудьте поздравить {'сегодня' if days_until == 1 else f'через {days_until} дней'}!"
                button_text = "Спасибо"
                callback_data = f"birthday_hr_thanks_{user.telegram_id}_{days_until}"
            
            # Создаем кнопку для HR
            from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text=button_text, callback_data=callback_data)]
            ])
            
            # Отправляем уведомления всем HR
            for hr_user in hr_users:
                try:
                    await self.bot.send_message(
                        hr_user.telegram_id, 
                        message, 
                        parse_mode="HTML",
                        reply_markup=keyboard
                    )
                except Exception as e:
                    logger.error(f"Failed to send birthday notification to HR {hr_user.telegram_id}: {e}")
            
            # Отправляем поздравление самому пользователю в день рождения
            if days_until == 0:
                try:
                    # Извлекаем имя (второе слово из fullname, в надежде что это имя в ФИО)
                    name_parts = user.fullname.split() if user.fullname else []
                    first_name = name_parts[1] if len(name_parts) > 1 else (name_parts[0] if name_parts else "Коллега")
                    
                    birthday_message = f"🎂 <b>{first_name}, поздравляем Вас с Днём Рождения!</b>\n\n🎉 Желаем счастья, здоровья и успехов!"
                    if settings.tpoints_amount > 0:
                        birthday_message += f"\n\n💎 Вам начислено {settings.tpoints_amount} T-Points в подарок!"
                    
                    # Создаем кнопку "Спасибо"
                    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
                    keyboard = InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="Спасибо", callback_data=f"birthday_thanks_{user.telegram_id}")]
                    ])
                    
                    await self.bot.send_message(
                        user.telegram_id, 
                        birthday_message, 
                        parse_mode="HTML",
                        reply_markup=keyboard
                    )
                except Exception as e:
                    logger.error(f"Failed to send birthday greeting to user {user.telegram_id}: {e}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error sending birthday notification for user {user.telegram_id}: {e}")
            return False
    
    async def _award_birthday_points(self, user: User, points: int) -> bool:
        """Начислить T-Points за день рождения"""
        try:
            # Начисляем T-Points
            success = await self.transaction_service.add_points(
                user_id=user.telegram_id,
                points=points,
                description=f"День рождения {date.today().year}"
            )
            
            if success:
                logger.info(f"Awarded {points} T-Points to user {user.telegram_id} for birthday")
            
            return success
            
        except Exception as e:
            logger.error(f"Error awarding birthday points to user {user.telegram_id}: {e}")
            return False
    
    # =============================================================================
    # ПРОВЕРКА И ОБРАБОТКА ЮБИЛЕЕВ РАБОТЫ
    # =============================================================================
    
    async def check_anniversaries(self) -> Dict[str, Any]:
        """Проверить юбилеи работы и отправить уведомления"""
        results = {
            'anniversary_notifications_sent': 0,
            'tpoints_awarded': 0,
            'errors': []
        }
        
        try:
            # Получаем настройки юбилеев
            anniversary_settings = await self.get_event_settings('anniversary')
            if not anniversary_settings or not anniversary_settings.is_enabled:
                logger.info("Anniversary notifications are disabled")
                return results
            
            # Парсим дни уведомлений
            notification_days = self._parse_notification_days(anniversary_settings.notification_days)
            today = date.today()
            
            # Получаем всех активных пользователей с датами найма
            users = await self.repository.get_users_with_hire_dates()
            
            for user in users:
                if not user.hire_date:
                    continue
                
                # Вычисляем годы работы и дни до юбилея
                years_worked, days_until_anniversary = self._calculate_anniversary(user.hire_date, today)
                
                # Учитываем юбилеи только с первого года работы
                if years_worked >= 1 and days_until_anniversary in notification_days:
                    # Отправляем уведомление
                    if await self._send_anniversary_notification(user, years_worked, days_until_anniversary, anniversary_settings):
                        results['anniversary_notifications_sent'] += 1
                    
                    # Начисляем T-Points в день юбилея
                    if days_until_anniversary == 0:
                        points_to_award = anniversary_settings.tpoints_amount + (years_worked * anniversary_settings.tpoints_multiplier)
                        if points_to_award > 0:
                            # Проверяем, не начисляли ли уже за этот юбилей
                            if not await self.repository.check_anniversary_transaction_exists(user.telegram_id, years_worked):
                                if await self._award_anniversary_points(user, years_worked, points_to_award):
                                    results['tpoints_awarded'] += points_to_award
            
            logger.info(f"Anniversary check completed: {results}")
            return results
            
        except Exception as e:
            error_msg = f"Error in anniversary check: {e}"
            logger.error(error_msg)
            results['errors'].append(error_msg)
            return results
    
    async def _send_anniversary_notification(self, user: User, years: int, days_until: int, settings: AutoEventSettings) -> bool:
        """Отправить уведомление о юбилее работы"""
        try:
            if not self.bot:
                return False
            
            # Получаем HR пользователей с включенными уведомлениями
            hr_users = await self._get_hr_users_for_notifications('anniversary')
            
            if days_until == 0:
                message = f"🏆 <b>Сегодня юбилей работы!</b>\n\n👤 {user.fullname}\n🎯 {years} лет в компании\n🎉 Поздравляем!"
            else:
                message = f"🏆 <b>Скоро юбилей работы</b>\n\n👤 {user.fullname}\n🎯 {years} лет в компании\n📅 Через {days_until} дн."
            
            # Отправляем уведомления всем HR
            for hr_user in hr_users:
                try:
                    await self.bot.send_message(hr_user.telegram_id, message)
                except Exception as e:
                    logger.error(f"Failed to send anniversary notification to HR {hr_user.telegram_id}: {e}")
            
            # Отправляем поздравление самому пользователю в день юбилея
            if days_until == 0:
                try:
                    points_to_award = settings.tpoints_amount + (years * settings.tpoints_multiplier)
                    anniversary_message = f"🏆 <b>С Юбилеем работы!</b>\n\n🎉 Поздравляем с {years} годами в нашей компании!\nСпасибо за Ваш вклад и преданность!"
                    if points_to_award > 0:
                        anniversary_message += f"\n\n💎 Вам начислено {points_to_award} T-Points в честь юбилея!"
                    
                    await self.bot.send_message(user.telegram_id, anniversary_message)
                except Exception as e:
                    logger.error(f"Failed to send anniversary greeting to user {user.telegram_id}: {e}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error sending anniversary notification for user {user.telegram_id}: {e}")
            return False
    
    async def _award_anniversary_points(self, user: User, years: int, points: int) -> bool:
        """Начислить T-Points за юбилей работы"""
        try:
            # Начисляем T-Points
            success = await self.transaction_service.add_points(
                user_id=user.telegram_id,
                points=points,
                description=f"Юбилей - {years} лет работы"
            )
            
            if success:
                logger.info(f"Awarded {points} T-Points to user {user.telegram_id} for {years} years anniversary")
            
            return success
            
        except Exception as e:
            logger.error(f"Error awarding anniversary points to user {user.telegram_id}: {e}")
            return False
    
    # =============================================================================
    # ПРОВЕРКА ОСТАТКОВ ТОВАРОВ
    # =============================================================================
    
    async def check_low_stock(self) -> Dict[str, Any]:
        """Проверить остатки товаров и отправить уведомления"""
        results = {
            'stock_notifications_sent': 0,
            'low_stock_products': 0,
            'errors': []
        }
        
        try:
            # Получаем настройки остатков
            stock_settings = await self.get_event_settings('stock_low')
            if not stock_settings or not stock_settings.is_enabled:
                logger.info("Stock notifications are disabled")
                return results
            
            # Получаем HR пользователей с включенными уведомлениями
            hr_users = await self._get_hr_users_for_notifications('stock')
            if not hr_users:
                logger.info("No HR users enabled for stock notifications")
                return results
            
            # Получаем все активные товары
            products = await self.repository.get_all_active_products()
            
            low_stock_items = []
            
            for product in products:
                total_stock = product.total_stock
                
                if total_stock <= stock_settings.stock_threshold:
                    low_stock_items.append({
                        'name': product.name,
                        'stock': total_stock,
                        'id': product.id
                    })
                    results['low_stock_products'] += 1
            
            if low_stock_items:
                # Отправляем сводное уведомление HR
                message = self._format_stock_notification(low_stock_items, stock_settings.stock_threshold)
                
                for hr_user in hr_users:
                    try:
                        await self.bot.send_message(hr_user.telegram_id, message)
                        results['stock_notifications_sent'] += 1
                    except Exception as e:
                        logger.error(f"Failed to send stock notification to HR {hr_user.telegram_id}: {e}")
            
            logger.info(f"Stock check completed: {results}")
            return results
            
        except Exception as e:
            error_msg = f"Error in stock check: {e}"
            logger.error(error_msg)
            results['errors'].append(error_msg)
            return results
    
    def _format_stock_notification(self, low_stock_items: List[Dict], threshold: int) -> str:
        """Форматировать уведомление об остатках"""
        message = f"📦 <b>Уведомление об остатках товаров</b>\n\n"
        message += f"⚠️ Товары с остатком ≤ {threshold} шт.:\n\n"
        
        for i, item in enumerate(low_stock_items[:10], 1):  # Ограничиваем до 10 товаров
            message += f"{i}. <b>{item['name']}</b>\n   📊 Остаток: {item['stock']} шт.\n\n"
        
        if len(low_stock_items) > 10:
            message += f"... и ещё {len(low_stock_items) - 10} товаров\n\n"
        
        message += "💡 Рекомендуется пополнить запасы"
        
        return message
    
    # =============================================================================
    # ВСПОМОГАТЕЛЬНЫЕ МЕТОДЫ
    # =============================================================================
    
    async def _get_hr_users_for_notifications(self, event_type: str) -> List[User]:
        """Получить HR пользователей с включенными уведомлениями для типа события"""
        # Получаем всех HR пользователей
        hr_users = await self.get_all_hr_users()
        
        if event_type == 'birthday':
            enabled_field = 'birthday_enabled'
        elif event_type == 'anniversary':
            enabled_field = 'anniversary_enabled'
        elif event_type == 'stock':
            enabled_field = 'stock_enabled'
        else:
            return hr_users  # Если тип неизвестен, возвращаем всех HR
        
        # Фильтруем HR по их персональным настройкам
        enabled_hr_users = []
        for hr_user in hr_users:
            preferences = await self.get_admin_preferences(hr_user.telegram_id)
            # По умолчанию уведомления ВЫКЛЮЧЕНЫ для безопасности
            if getattr(preferences, enabled_field, False):
                enabled_hr_users.append(hr_user)
        
        return enabled_hr_users
    
    def _parse_notification_days(self, days_string: str) -> List[int]:
        """Парсить строку дней уведомлений в список чисел"""
        try:
            return [int(day.strip()) for day in days_string.split(',') if day.strip()]
        except (ValueError, AttributeError):
            return [0]  # По умолчанию только в день события
    
    def _days_until_birthday(self, birth_date: date, today: date) -> int:
        """Вычислить количество дней до дня рождения"""
        # Создаём дату дня рождения в этом году
        this_year_birthday = birth_date.replace(year=today.year)
        
        # Если день рождения уже прошёл в этом году, берём следующий год
        if this_year_birthday < today:
            this_year_birthday = birth_date.replace(year=today.year + 1)
        
        return (this_year_birthday - today).days
    
    def _calculate_anniversary(self, hire_date: date, today: date) -> tuple[int, int]:
        """Вычислить годы работы и дни до юбилея"""
        # Вычисляем полные годы работы 
        years_worked = today.year - hire_date.year
        
        # Создаём дату юбилея в этом году
        try:
            this_year_anniversary = hire_date.replace(year=today.year)
        except ValueError:
            # Обрабатываем случай 29 февраля
            this_year_anniversary = hire_date.replace(year=today.year, day=28)
        
        # Определяем точные годы работы учитывая дату и месяц
        if this_year_anniversary <= today:
            # Юбилей уже наступил в этом году
            current_years = years_worked
            days_until = 0 if this_year_anniversary == today else 0
            
            # Если сегодня не день юбилея, считаем дни до следующего
            if this_year_anniversary < today:
                try:
                    next_anniversary = hire_date.replace(year=today.year + 1)
                except ValueError:
                    next_anniversary = hire_date.replace(year=today.year + 1, day=28)
                days_until = (next_anniversary - today).days
        else:
            # Юбилей ещё не наступил в этом году
            current_years = years_worked - 1 if years_worked > 0 else 0
            days_until = (this_year_anniversary - today).days
        
        return current_years, days_until
    
    # =============================================================================
    # МЕТОДЫ ДЛЯ ТЕСТИРОВАНИЯ
    # =============================================================================
    
    async def test_birthday_notification(self, user_id: int) -> bool:
        """Отправить тестовое уведомление о дне рождения"""
        try:
            user = await self.repository.get_user_by_id(user_id)
            if not user:
                return False
            
            settings = await self.get_event_settings('birthday')
            if not settings:
                return False
            
            return await self._send_birthday_notification(user, 0, settings)
            
        except Exception as e:
            logger.error(f"Error sending test birthday notification: {e}")
            return False
    
    async def test_anniversary_notification(self, user_id: int, years: int = 1) -> bool:
        """Отправить тестовое уведомление о юбилее"""
        try:
            user = await self.repository.get_user_by_id(user_id)
            if not user:
                return False
            
            settings = await self.get_event_settings('anniversary')
            if not settings:
                return False
            
            return await self._send_anniversary_notification(user, years, 0, settings)
            
        except Exception as e:
            logger.error(f"Error sending test anniversary notification: {e}")
            return False
    
    async def test_stock_notification(self) -> bool:
        """Отправить тестовое уведомление об остатках"""
        try:
            test_items = [
                {'name': 'Тестовый товар 1', 'stock': 2, 'id': 999},
                {'name': 'Тестовый товар 2', 'stock': 1, 'id': 998}
            ]
            
            settings = await self.get_event_settings('stock_low')
            if not settings:
                return False
            
            hr_users = await self._get_hr_users_for_notifications('stock')
            if not hr_users:
                return False
            
            message = self._format_stock_notification(test_items, settings.stock_threshold)
            message = f"🧪 <b>ТЕСТОВОЕ УВЕДОМЛЕНИЕ</b>\n\n{message}"
            
            for hr_user in hr_users:
                try:
                    await self.bot.send_message(hr_user.telegram_id, message)
                except Exception as e:
                    logger.error(f"Failed to send test stock notification to HR {hr_user.telegram_id}: {e}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error sending test stock notification: {e}")
            return False
    
    # =============================================================================
    # ОТЧЕТЫ ДЛЯ HR
    # =============================================================================
    
    async def get_birthdays_report(self) -> Dict[str, Any]:
        """Получить отчет о ближайших днях рождения"""
        try:
            users = await self.repository.get_users_with_birthdays()
            today = date.today()
            upcoming_birthdays = []
            
            for user in users:
                if not user.birth_date:
                    continue
                    
                days_until = self._days_until_birthday(user.birth_date, today)
                
                if days_until <= 30:  # Показываем на ближайшие 30 дней
                    upcoming_birthdays.append((user, days_until))
            
            # Сортируем по количеству дней
            upcoming_birthdays.sort(key=lambda x: x[1])
            
            return {'upcoming_birthdays': upcoming_birthdays}
            
        except Exception as e:
            logger.error(f"Error getting birthdays report: {e}")
            return {'upcoming_birthdays': [], 'errors': [str(e)]}
    
    async def get_anniversaries_report(self) -> Dict[str, Any]:
        """Получить отчет о ближайших годовщинах"""
        try:
            users = await self.repository.get_users_with_hire_dates()
            today = date.today()
            upcoming_anniversaries = []
            
            for user in users:
                if not user.hire_date:
                    continue
                    
                years_worked, days_until = self._calculate_anniversary(user.hire_date, today)
                
                # Показываем годовщины за последние 30 дней и на ближайшие 30 дней
                # Если days_until > 300, значит годовщина была недавно (прошедший год)
                if years_worked >= 1:
                    if days_until <= 30:  # Ближайшие 30 дней
                        upcoming_anniversaries.append((user, years_worked, days_until))
                    elif days_until > 335:  # Была в последние 30 дней (прошедший год: 365-30=335)
                        # Пересчитываем как "дней назад"
                        days_ago = 365 - days_until
                        upcoming_anniversaries.append((user, years_worked, -days_ago))
            
            # Сортируем: сначала прошедшие (отрицательные), потом будущие (положительные)
            upcoming_anniversaries.sort(key=lambda x: x[2])
            
            return {'upcoming_anniversaries': upcoming_anniversaries}
            
        except Exception as e:
            logger.error(f"Error getting anniversaries report: {e}")
            return {'upcoming_anniversaries': [], 'errors': [str(e)]} 