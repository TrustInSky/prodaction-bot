"""
Миграция для создания новой системы автоматических событий
Создает таблицы auto_event_settings и admin_notification_preferences
"""
import asyncio
import os
import sys

# Добавляем путь к корню проекта
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from app.models.models import Base, AutoEventSettings, AdminNotificationPreferences
from app.config import Config

async def create_auto_events_tables():
    """Создаёт таблицы для новой системы автоматических событий"""
    config = Config()
    
    # Создаём async engine
    engine = create_async_engine(
        config.DATABASE_URL,
        echo=True
    )
    
    try:
        async with engine.begin() as conn:
            # Создаём только новые таблицы
            await conn.run_sync(AutoEventSettings.__table__.create, checkfirst=True)
            await conn.run_sync(AdminNotificationPreferences.__table__.create, checkfirst=True)
            
        print("✅ Таблицы auto_event_settings и admin_notification_preferences созданы успешно!")
        
        # Создаём сессию для заполнения начальными данными
        async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        
        async with async_session() as session:
            # Создаём базовые настройки для автоматических событий
            default_events = [
                {
                    'event_type': 'birthday',
                    'is_enabled': True,
                    'notification_days': '3,1,0',
                    'notification_time': '09:00',
                    'tpoints_amount': 1000,
                    'tpoints_multiplier': 0,
                    'stock_threshold': 0
                },
                {
                    'event_type': 'anniversary',
                    'is_enabled': True,
                    'notification_days': '3,0',
                    'notification_time': '09:00',
                    'tpoints_amount': 500,
                    'tpoints_multiplier': 100,
                    'stock_threshold': 0
                },
                {
                    'event_type': 'stock_low',
                    'is_enabled': True,
                    'notification_days': '0',
                    'notification_time': '10:00',
                    'tpoints_amount': 0,
                    'tpoints_multiplier': 0,
                    'stock_threshold': 5
                }
            ]
            
            for event_data in default_events:
                # Проверяем, нет ли уже такого события
                existing = await session.get(AutoEventSettings, event_data['event_type'])
                if not existing:
                    event = AutoEventSettings(**event_data)
                    session.add(event)
            
            await session.commit()
            print("✅ Начальные настройки автоматических событий созданы!")
            
    except Exception as e:
        print(f"❌ Ошибка при создании таблиц: {e}")
        raise
    finally:
        await engine.dispose()

if __name__ == "__main__":
    asyncio.run(create_auto_events_tables()) 