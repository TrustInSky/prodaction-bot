from sqlalchemy import select, update, and_, or_, func, cast, Integer, case
from sqlalchemy.ext.asyncio import AsyncSession
from ..models.models import Product
from ..core.base import BaseRepository
from typing import List, Optional, Dict, Any
import logging
import json

logger = logging.getLogger(__name__)

class CatalogRepository(BaseRepository):
    """Репозиторий для работы с каталогом товаров"""
    
    def __init__(self, session: AsyncSession):
        super().__init__(session)
        
    async def get_all_products(self) -> List[Product]:
        """Получить все товары"""
        query = select(Product).order_by(Product.id)
        result = await self.session.execute(query)
        return list(result.scalars().all())
        
    async def get_available_products(self) -> List[Product]:
        """Получить доступные товары"""
        query = select(Product).where(
            Product.is_available == True
        ).order_by(Product.id)
        result = await self.session.execute(query)
        products = list(result.scalars().all())
        
        # Фильтруем товары с нулевым количеством
        return [p for p in products if p.total_stock > 0]
        
    async def get_product_by_id(self, product_id: int) -> Optional[Product]:
        """Получить товар по ID"""
        query = select(Product).where(Product.id == product_id)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()
            
    async def update_product_quantity(self, product_id: int, quantity: int) -> bool:
        """Обновить количество товара"""
        try:
            query = update(Product).where(Product.id == product_id).values(size_quantities=str(quantity))
            await self.session.execute(query)
            return True
        except Exception as e:
            logger.error(f"Error updating product quantity: {e}")
            return False
            
    async def update_product_sizes(self, product_id: int, sizes: Dict[str, int]) -> bool:
        """Обновить размеры товара"""
        try:
            # Преобразуем dict в JSON строку для сохранения
            sizes_json = json.dumps(sizes)
            
            query = update(Product).where(Product.id == product_id).values(size_quantities=sizes_json)
            await self.session.execute(query)
            return True
        except Exception as e:
            logger.error(f"Error updating product sizes: {e}")
            return False
            
    async def update_product_availability(self, product_id: int, is_available: bool) -> bool:
        """Обновить доступность товара"""
        try:
            query = update(Product).where(Product.id == product_id).values(is_available=is_available)
            await self.session.execute(query)
            return True
        except Exception as e:
            logger.error(f"Error updating product availability: {e}")
            return False

    async def create_product(self, product_data: Dict[str, Any]) -> bool:
        """Создать новый товар"""
        try:
            product = Product(
                name=product_data['name'],
                description=product_data.get('description', ''),
                price=product_data['price'],
                image_url=product_data.get('image_url'),
                color=product_data.get('color'),
                is_available=product_data.get('is_available', True)
            )
            
            # Устанавливаем size_quantities
            if product_data.get('has_sizes'):
                # Устанавливаем как JSON словарь
                product.sizes_dict = product_data['size_quantities']
            else:
                # Устанавливаем как число
                product.quantity_as_number = product_data['size_quantities']
            
            self.session.add(product)
            return True
            
        except Exception as e:
            logger.error(f"Error creating product {product_data.get('name')}: {e}")
            return False