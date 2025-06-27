"""
Константы для системы заказов
"""

# Настройки пагинации
ORDERS_PER_PAGE = 5

# Маппинг статусов для callback_data клавиатур админки (совместимость с UI)
ADMIN_STATUS_MAPPING = {
    "new": 'new',
    "ready": 'ready_for_pickup',  # Совместимость старых кнопок
    "completed": 'delivered',  # Совместимость старых кнопок
    "processing": 'processing',
    "cancelled": 'cancelled',
    "all": "all"
}

def normalize_admin_status(status: str) -> str:
    """Нормализует статус из админки для совместимости с кнопками"""
    return ADMIN_STATUS_MAPPING.get(status, status) 