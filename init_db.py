import asyncio
import json
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.models.models import Base, Product
from app.config import Config

async def init_db():
    """Инициализация базы данных"""
    config = Config()
    
    # Создаем движок базы данных
    engine = create_async_engine(
        config.DATABASE_URL,
        echo=False
    )
    
    # Создаем все таблицы
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # Создаем фабрику сессий
    async_session = async_sessionmaker(engine, expire_on_commit=False)
    
    # Добавляем тестовые товары
    async with async_session() as session:
        # Проверяем, есть ли уже товары
        products = await session.execute("SELECT COUNT(*) FROM products")
        count = products.scalar()
        
        if count == 0:
            # Худи
            hoodie = Product(
                name="Худи с логотипом компании",
                description="Теплое и стильное худи с вышитым логотипом компании. Состав: 80% хлопок, 20% полиэстер",
                price=2500.0,
                image_url="https://example.com/hoodie.jpg",
                is_available=True,
                size_quantities=json.dumps({"S": 5, "M": 10, "L": 8, "XL": 6}),
                color="Черный"
            )
            session.add(hoodie)
            
            # Свитшот
            sweatshirt = Product(
                name="Свитшот базовый",
                description="Базовый свитшот с круглым вырезом. Состав: 100% хлопок",
                price=2000.0,
                image_url="https://example.com/sweatshirt.jpg",
                is_available=True,
                size_quantities=json.dumps({"S": 3, "M": 7, "L": 5, "XL": 4}),
                color="Серый"
            )
            session.add(sweatshirt)
            
            await session.commit()
    
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(init_db()) 