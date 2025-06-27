"""
Создает таблицы notification_types и status_transitions для системы уведомлений
"""

import asyncio
import sys
import os

# Добавляем путь к корневой папке проекта
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.models.models import Base, NotificationType, StatusTransition, OrderStatus
from app.database import get_async_engine
from sqlalchemy import text
import logging

logger = logging.getLogger(__name__)

async def create_notification_system():
    """Создать систему типов уведомлений"""
    try:
        engine = get_async_engine()
        
        async with engine.begin() as conn:
            # Создаем таблицы
            await conn.run_sync(NotificationType.__table__.create, checkfirst=True)
            await conn.run_sync(StatusTransition.__table__.create, checkfirst=True)
            
            print("✅ Таблицы notification_types и status_transitions созданы успешно!")
            
            # Заполняем типы уведомлений
            notifications_data = [
                ('order_created', 'Заказ создан', 'Уведомление о создании нового заказа'),
                ('order_taken', 'Заказ взят в работу', 'Уведомление о взятии заказа в работу'),
                ('order_ready', 'Заказ готов к выдаче', 'Уведомление о готовности заказа к выдаче'),
                ('order_completed', 'Заказ выполнен', 'Уведомление о выполнении заказа'),
                ('order_cancelled', 'Заказ отменен', 'Уведомление об отмене заказа'),
                ('order_cancelled_by_user', 'Заказ отменен пользователем', 'Уведомление об отмене заказа пользователем')
            ]
            
            # Вставляем типы уведомлений
            for code, name, description in notifications_data:
                await conn.execute(
                    text("""
                        INSERT INTO notification_types (code, name, description, is_active, created_at)
                        VALUES (:code, :name, :description, :is_active, CURRENT_TIMESTAMP)
                        ON CONFLICT (code) DO NOTHING
                    """),
                    {
                        'code': code,
                        'name': name, 
                        'description': description,
                        'is_active': True
                    }
                )
            
            print("✅ Типы уведомлений добавлены успешно!")
            
            # Создаем переходы между статусами
            # Сначала получаем ID статусов и типов уведомлений
            result = await conn.execute(text("SELECT id, code FROM order_statuses"))
            statuses = {row[1]: row[0] for row in result}
            
            result = await conn.execute(text("SELECT id, code FROM notification_types"))
            notifications = {row[1]: row[0] for row in result}
            
            # Определяем переходы
            transitions = [
                # from_status, to_status, notification_type
                (None, 'new', 'order_created'),  # Создание заказа
                ('new', 'processing', 'order_taken'),  # Взятие в работу
                ('processing', 'ready_for_pickup', 'order_ready'),  # Готов к выдаче
                ('ready_for_pickup', 'delivered', 'order_completed'),  # Выполнен
                ('new', 'cancelled', 'order_cancelled'),  # Отменен из нового
                ('processing', 'cancelled', 'order_cancelled'),  # Отменен из обработки
                ('new', 'cancelled', 'order_cancelled_by_user'),  # Отменен пользователем
            ]
            
            # Вставляем переходы
            for from_status, to_status, notification_type in transitions:
                from_status_id = statuses.get(from_status) if from_status else None
                to_status_id = statuses.get(to_status)
                notification_type_id = notifications.get(notification_type)
                
                if to_status_id and notification_type_id:
                    await conn.execute(
                        text("""
                            INSERT INTO status_transitions (from_status_id, to_status_id, notification_type_id, is_active, created_at)
                            VALUES (:from_status_id, :to_status_id, :notification_type_id, :is_active, CURRENT_TIMESTAMP)
                            ON CONFLICT DO NOTHING
                        """),
                        {
                            'from_status_id': from_status_id,
                            'to_status_id': to_status_id,
                            'notification_type_id': notification_type_id,
                            'is_active': True
                        }
                    )
            
            print("✅ Переходы статусов настроены успешно!")
            print("🎉 Система уведомлений полностью настроена!")
            
    except Exception as e:
        print(f"❌ Ошибка при создании системы уведомлений: {e}")
        logger.error(f"Migration error: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(create_notification_system()) 