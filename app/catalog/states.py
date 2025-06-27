from aiogram.fsm.state import State, StatesGroup

class CartStates(StatesGroup):
    """Состояния корзины"""
    selecting_size = State()  # Выбор размера
    editing_quantity = State()  # Изменение количества
    confirming_order = State()  # Подтверждение заказа
    
class CartItemData:
    """Данные о товаре в корзине для FSM"""
    def __init__(
        self,
        product_id: int,
        current_size: str | None = None,
        current_quantity: int = 1
    ):
        self.product_id = product_id
        self.current_size = current_size
        self.current_quantity = current_quantity 