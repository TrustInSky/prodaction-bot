"""
Сервис онбординга пользователей
Вся бизнес-логика регистрации новых сотрудников
"""
from typing import Optional, Dict, Any, List
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, date
import re
import logging

from ..models.models import User
from ..core.base import BaseService
from ..services.user import UserService
from ..constants.departments import get_departments_list, format_fullname

logger = logging.getLogger(__name__)

class OnboardingService(BaseService):
    """Сервис для онбординга новых пользователей"""

    def __init__(self, session: AsyncSession):
        super().__init__(session)
        self.user_service = UserService(session)

    async def validate_fullname(self, fullname: str) -> Dict[str, Any]:
        """
        Валидация и форматирование ФИО (ОБЯЗАТЕЛЬНОЕ ПОЛЕ)
        
        Returns:
            Dict с ключами: valid (bool), message (str), first_name (str), formatted_fullname (str)
        """
        try:
            # ФИО - ОБЯЗАТЕЛЬНОЕ поле
            if not fullname or fullname.strip() == "":
                return {
                    'valid': False,
                    'message': "❌ ФИО обязательно для заполнения!\nПожалуйста, введите ваше полное имя",
                    'first_name': None,
                    'formatted_fullname': None,
                    'skipped': False
                }
            
            if len(fullname.strip()) < 3:
                return {
                    'valid': False,
                    'message': "❌ Пожалуйста, введите полное имя (минимум 3 символа)",
                    'first_name': None,
                    'formatted_fullname': None,
                    'skipped': False
                }
            
            if len(fullname.strip()) > 200:
                return {
                    'valid': False,
                    'message': "❌ Слишком длинное имя (максимум 200 символов)",
                    'first_name': None,
                    'formatted_fullname': None,
                    'skipped': False
                }
            
            # Проверяем, что есть буквы
            if not re.search(r'[а-яёА-ЯЁa-zA-Z]', fullname):
                return {
                    'valid': False,
                    'message': "❌ Имя должно содержать буквы",
                    'first_name': None,
                    'formatted_fullname': None,
                    'skipped': False
                }
            
            # Форматируем ФИО (первая буква заглавная в каждом слове)
            formatted_fullname = format_fullname(fullname)
            
            # Извлекаем имя (первое слово после фамилии)
            first_name = self._extract_first_name(formatted_fullname)
            
            return {
                'valid': True,
                'message': f"✅ ФИО принято: {formatted_fullname}",
                'first_name': first_name,
                'formatted_fullname': formatted_fullname,
                'skipped': False
            }
        except Exception as e:
            logger.error(f"Error validating fullname: {e}")
            return {
                'valid': False,
                'message': "❌ Ошибка валидации имени",
                'first_name': None,
                'formatted_fullname': None,
                'skipped': False
            }

    async def validate_birth_date(self, date_string: str) -> Dict[str, Any]:
        """
        Валидация даты рождения (можно пропустить)
        
        Returns:
            Dict с ключами: valid (bool), message (str), birth_date (date), age (int), skipped (bool)
        """
        try:
            # Разрешаем пропустить поле
            if not date_string or date_string.strip() == "" or date_string.strip().lower() in ["пропустить", "skip", "-"]:
                return {
                    'valid': True,
                    'message': "⏭️ Дата рождения пропущена (HR получит уведомление)",
                    'birth_date': None,
                    'age': None,
                    'skipped': True
                }
            
            # Парсим дату в формате ДД.ММ.ГГГГ
            birth_date = datetime.strptime(date_string.strip(), '%d.%m.%Y').date()
            
            # Проверяем разумность даты
            today = datetime.now().date()
            age = (today - birth_date).days // 365
            
            if age < 16:
                return {
                    'valid': False,
                    'message': "❌ Возраст должен быть не менее 16 лет или введите 'пропустить'",
                    'birth_date': None,
                    'age': age,
                    'skipped': False
                }
            
            if age > 80:
                return {
                    'valid': False,
                    'message': "❌ Пожалуйста, проверьте дату рождения (возраст не может быть больше 80 лет)",
                    'birth_date': None,
                    'age': age,
                    'skipped': False
                }
            
            # Проверяем, что дата не в будущем
            if birth_date > today:
                return {
                    'valid': False,
                    'message': "❌ Дата рождения не может быть в будущем",
                    'birth_date': None,
                    'age': 0,
                    'skipped': False
                }
            
            return {
                'valid': True,
                'message': f"✅ Дата рождения принята (возраст: {age} лет)",
                'birth_date': birth_date,
                'age': age,
                'skipped': False
            }
        except ValueError:
            return {
                'valid': False,
                'message': "❌ Неверный формат даты. Введите дату в формате ДД.ММ.ГГГГ\n💡 Пример: 15.03.1990\n⏭️ Или введите 'пропустить'",
                'birth_date': None,
                'age': 0,
                'skipped': False
            }
        except Exception as e:
            logger.error(f"Error validating birth date: {e}")
            return {
                'valid': False,
                'message': "❌ Ошибка валидации даты рождения",
                'birth_date': None,
                'age': 0,
                'skipped': False
            }

    async def validate_hire_date(self, date_string: str) -> Dict[str, Any]:
        """
        Валидация даты трудоустройства
        
        Returns:
            Dict с ключами: valid (bool), message (str), hire_date (date)
        """
        try:
            # Парсим дату в формате ДД.ММ.ГГГГ
            hire_date = datetime.strptime(date_string.strip(), '%d.%m.%Y').date()
            
            # Проверяем, что дата не в будущем
            today = datetime.now().date()
            if hire_date > today:
                return {
                    'valid': False,
                    'message': "❌ Дата трудоустройства не может быть в будущем",
                    'hire_date': None
                }
            
            # Проверяем разумность (не более 50 лет назад)
            max_past_date = today.replace(year=today.year - 50)
            if hire_date < max_past_date:
                return {
                    'valid': False,
                    'message': "❌ Дата трудоустройства слишком далеко в прошлом",
                    'hire_date': None
                }
            
            return {
                'valid': True,
                'message': "✅ Дата трудоустройства принята",
                'hire_date': hire_date
            }
        except ValueError:
            return {
                'valid': False,
                'message': "❌ Неверный формат даты. Пожалуйста, введите дату в формате ДД.ММ.ГГГГ\n💡 Пример: 01.09.2023",
                'hire_date': None
            }
        except Exception as e:
            logger.error(f"Error validating hire date: {e}")
            return {
                'valid': False,
                'message': "❌ Ошибка валидации даты трудоустройства",
                'hire_date': None
            }

    async def process_department_selection(self, callback_data: str) -> Dict[str, Any]:
        """
        Обработка выбора отдела через кнопки (ТОЛЬКО кнопки, никакого ввода!)
        
        Args:
            callback_data: данные из callback (например: "dept:Купер" или "dept:skip")
        
        Returns:
            Dict с ключами: valid (bool), message (str), department (str), skipped (bool)
        """
        try:
            if not callback_data or not callback_data.startswith("dept:"):
                return {
                    'valid': False,
                    'message': "❌ Некорректные данные выбора отдела",
                    'department': None,
                    'skipped': False
                }
            
            department_value = callback_data[5:]  # Убираем "dept:" префикс
            
            # Обработка пропуска
            if department_value == "skip":
                return {
                    'valid': True,
                    'message': "⏭️ Отдел пропущен (HR получит уведомление и уточнит)",
                    'department': "",
                    'skipped': True
                }
            
            # Проверяем что выбранный отдел есть в списке
            active_departments = get_departments_list()
            if department_value in active_departments:
                return {
                    'valid': True,
                    'message': f"✅ Выбран отдел: {department_value}",
                    'department': department_value,
                    'skipped': False
                }
            else:
                return {
                    'valid': False,
                    'message': f"❌ Отдел '{department_value}' не найден в списке",
                    'department': None,
                    'skipped': False
                }
                
        except Exception as e:
            logger.error(f"Error processing department selection: {e}")
            return {
                'valid': False,
                'message': "❌ Ошибка обработки выбора отдела",
                'department': None,
                'skipped': False
            }

    async def complete_onboarding(self, telegram_id: int, username: str, onboarding_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Завершить онбординг пользователя
        
        Args:
            telegram_id: ID пользователя в Telegram
            username: Username в Telegram
            onboarding_data: Данные из процесса онбординга
            
        Returns:
            Dict с результатом: success (bool), user (User), message (str)
        """
        try:
            # Создаем пользователя
            user = await self.user_service.get_or_create_user(
                telegram_id=telegram_id,
                username=username or "",
                fullname=onboarding_data['fullname']
            )
            
            if not user:
                return {
                    'success': False,
                    'user': None,
                    'message': "❌ Ошибка при создании пользователя"
                }
            
            # Обновляем дополнительные данные
            success = await self.user_service.repository.update_user_data(user.telegram_id, {
                'birth_date': onboarding_data['birth_date'],
                'hire_date': onboarding_data['hire_date'],
                'department': onboarding_data['department']
            })
            
            if not success:
                return {
                    'success': False,
                    'user': user,
                    'message': "❌ Ошибка при обновлении данных пользователя"
                }
            
            # Уведомляем HR о новом сотруднике
            try:
                await self.user_service.notify_hr_about_new_employee(None, user)  # bot передадим позже
            except Exception as e:
                logger.error(f"Error notifying HR about new employee: {e}")
                # Не критично, продолжаем
            
            return {
                'success': True,
                'user': user,
                'message': "✅ Регистрация завершена успешно!"
            }
        except Exception as e:
            logger.error(f"Error completing onboarding: {e}")
            return {
                'success': False,
                'user': None,
                'message': "❌ Ошибка при завершении регистрации"
            }

    def get_available_departments(self) -> List[str]:
        """Получить список доступных отделов"""
        return get_departments_list()

    def _extract_first_name(self, fullname: str) -> str:
        """Извлекает имя из полного ФИО"""
        try:
            parts = fullname.strip().split()
            if len(parts) >= 2:
                return parts[1]  # Второе слово (имя)
            elif len(parts) == 1:
                return parts[0]  # Если только одно слово
            else:
                return "Пользователь"
        except (AttributeError, IndexError):
            return "Пользователь"

    async def get_onboarding_welcome_text(self) -> str:
        """Получить приветственный текст для онбординга"""
        return (
            f"👋 Добро пожаловать в HR Support Bot!\n\n"
            f"🎉 Поздравляем с присоединением к нашей команде!\n\n"
            f"📝 Для завершения регистрации, пожалуйста, укажите ваше полное имя (ФИО):\n\n"
            f"💡 Пример: Иванов Иван Иванович"
        )

    async def format_completion_message(self, user_data: Dict[str, Any], first_name: str, user_balance: int) -> str:
        """Форматирует сообщение о завершении онбординга"""
        return (
            f"🎉 <b>Регистрация завершена!</b>\n\n"
            f"👤 ФИО: {user_data['fullname']}\n"
            f"📅 Дата рождения: {user_data['birth_date'].strftime('%d.%m.%Y')}\n"
            f"💼 Дата трудоустройства: {user_data['hire_date'].strftime('%d.%m.%Y')}\n"
            f"🏢 Отдел: {user_data['department']}\n\n"
            f"💎 Ваш стартовый баланс: {user_balance:,} T-Points\n\n"
            f"🚀 Добро пожаловать в команду, {first_name}!\n\n"
            f"🏠 Можете ознакомиться с функционалом бота:"
        ) 