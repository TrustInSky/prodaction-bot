from sqlalchemy.ext.asyncio import AsyncSession
from ..repositories.catalog_repository import CatalogRepository
from ..models.models import Product
from ..core.base import BaseService
from typing import List, Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)

class CatalogService(BaseService):
    """
    Сервис для работы с каталогом товаров
    ИСПРАВЛЕНО: работает через репозиторий, правильный конструктор
    """
    
    def __init__(self, session: AsyncSession):
        super().__init__(session)
        self.repository = CatalogRepository(session)
        
    async def get_all_products(self) -> List[Product]:
        """Получить все товары"""
        return await self.repository.get_all_products()
        
    async def get_available_products(self) -> List[Product]:
        """Получить доступные товары"""
        return await self.repository.get_available_products()
        
    async def get_product(self, product_id: int) -> Optional[Product]:
        """Получить товар по ID"""
        return await self.repository.get_product_by_id(product_id)
        
        
        
    async def update_product_quantity(self, product_id: int, quantity: int) -> bool:
        """Обновить количество товара"""
        if quantity < 0:
            return False
        return await self.repository.update_product_quantity(product_id, quantity)
        
    async def update_product_sizes(self, product_id: int, sizes: Dict[str, int]) -> bool:
        """Обновить размеры товара"""
        # Проверяем, что все значения неотрицательные
        if any(quantity < 0 for quantity in sizes.values()):
            return False
        return await self.repository.update_product_sizes(product_id, sizes)
        

        
    async def check_product_availability(self, product_id: int, quantity: int = 1, size: Optional[str] = None) -> bool:
        """Проверить доступность товара"""
        product = await self.get_product(product_id)
        if not product:
            return False
            
        if size:
            available_quantity = product.sizes_dict.get(size, 0)
        else:
            available_quantity = product.get_quantity()
            
        return available_quantity >= quantity
        
    async def reserve_product(self, product_id: int, quantity: int = 1, size: Optional[str] = None) -> bool:
        """Зарезервировать товар"""
        product = await self.get_product(product_id)
        if not product:
            return False
            
        if size:
            available_quantity = product.sizes_dict.get(size, 0)
            if available_quantity < quantity:
                return False
            new_sizes = product.sizes_dict.copy()
            new_sizes[size] = available_quantity - quantity
            return await self.update_product_sizes(product_id, new_sizes)
        else:
            current_quantity = product.get_quantity()
            if current_quantity < quantity:
                return False
            return await self.update_product_quantity(product_id, current_quantity - quantity)
            
    async def release_product(self, product_id: int, quantity: int = 1, size: Optional[str] = None) -> bool:
        """Освободить зарезервированный товар"""
        product = await self.get_product(product_id)
        if not product:
            return False
            
        if size:
            current_quantity = product.sizes_dict.get(size, 0)
            new_sizes = product.sizes_dict.copy()
            new_sizes[size] = current_quantity + quantity
            return await self.update_product_sizes(product_id, new_sizes)
        else:
            current_quantity = product.get_quantity()
            return await self.update_product_quantity(product_id, current_quantity + quantity)

    async def bulk_update_products(self, products_data: List[Dict[str, Any]]) -> int:
        """
        Массовое обновление товаров через репозиторий
        ИСПРАВЛЕНО: убран прямой commit
        """
        updated_count = 0
        
        for product_data in products_data:
            try:
                if product_data.get('id'):
                    # Обновляем существующий товар
                    success = await self._update_existing_product(product_data['id'], product_data)
                    if success:
                        updated_count += 1
                else:
                    # Создаем новый товар
                    success = await self._create_new_product(product_data)
                    if success:
                        updated_count += 1
                        
            except Exception as e:
                logger.error(f"Error processing product {product_data.get('name', 'Unknown')}: {e}")
                continue
                    
        # НЕ ДЕЛАЕМ COMMIT - это делает middleware
        logger.info(f"Bulk update completed: {updated_count} products processed")
        return updated_count
    
    async def _update_existing_product(self, product_id: int, product_data: Dict[str, Any]) -> bool:
        """Обновить существующий товар"""
        try:
            product = await self.repository.get_product_by_id(product_id)
            if not product:
                logger.warning(f"Product with ID {product_id} not found")
                return False
            
            # Обновляем поля
            product.name = product_data['name']
            product.description = product_data.get('description', '')
            product.price = product_data['price']
            product.image_url = product_data.get('image_url')
            product.color = product_data.get('color')
            product.is_available = product_data.get('is_available', True)
            
            # Обновляем size_quantities
            if product_data.get('has_sizes'):
                # Устанавливаем как JSON словарь
                product.sizes_dict = product_data['size_quantities']
            else:
                # Устанавливаем как число
                product.quantity_as_number = product_data['size_quantities']
            
            return True
            
        except Exception as e:
            logger.error(f"Error updating product {product_id}: {e}")
            return False
    
    async def _create_new_product(self, product_data: Dict[str, Any]) -> bool:
        """Создать новый товар - ИСПРАВЛЕНО: через репозиторий"""
        try:
            # Создаем через репозиторий
            return await self.repository.create_product(product_data)
            
        except Exception as e:
            logger.error(f"Error creating product {product_data.get('name')}: {e}")
            return False

 