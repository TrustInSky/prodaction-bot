"""
Dependency Injection утилиты для использования с aiogram3-di
"""
from typing import Type, Any, get_type_hints
from functools import wraps
import inspect

def inject(*service_types: Type) -> callable:
    """
    Декоратор для инжекции сервисов через aiogram3-di
    
    Использование:
    @inject(UserService, CartService)
    async def my_handler(message: Message, user_service: UserService, cart_service: CartService):
        pass
    
    aiogram3-di автоматически найдет сервисы по типам параметров
    """
    def decorator(func):
        # aiogram3-di автоматически инжектит зависимости по типам аннотаций
        # Декоратор нужен только для явного указания зависимостей
        return func
    
    return decorator


# Альтернативный подход - функция для получения сервиса
def get_service(service_type: Type, **kwargs) -> Any:
    """
    Получить сервис по типу из kwargs (для случаев когда нужно получить сервис динамически)
    
    Использование:
    async def my_handler(message: Message, **kwargs):
        user_service = get_service(UserService, **kwargs)
    """
    # Ищем по имени типа с суффиксом _service
    service_name = f"{service_type.__name__.lower()}"
    if not service_name.endswith('_service'):
        service_name += '_service'
    
    service = kwargs.get(service_name)
    if service is None:
        raise ValueError(f"Service {service_type.__name__} not found in kwargs. Available: {list(kwargs.keys())}")
    
    return service 