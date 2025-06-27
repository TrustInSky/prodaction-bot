"""
Простые константы отделов
Легко редактируемый список отделов для выбора при регистрации
"""

# Список отделов для выбора при регистрации
DEPARTMENTS = [
    "Купер",
    "Отдел сопровождения",
    "Отдел продаж",
    "Отдел разработки",
    "Отдел тестирования",
    "Отдел техподдержки",
    "Бухгалтерия",
    "Администрация",
    "Фарма"
]

def get_departments_list():
    """Получить список отделов"""
    return DEPARTMENTS.copy()

def add_department(department_name: str):
    """Добавить новый отдел"""
    if department_name and department_name.strip() not in DEPARTMENTS:
        DEPARTMENTS.append(department_name.strip())
        return True
    return False

def remove_department(department_name: str):
    """Удалить отдел"""
    if department_name in DEPARTMENTS:
        DEPARTMENTS.remove(department_name)
        return True
    return False

def format_departments_for_display():
    """Форматировать отделы для отображения"""
    if not DEPARTMENTS:
        return "📋 Список отделов пуст"
    
    text = "🏢 <b>Список отделов:</b>\n\n"
    for i, dept in enumerate(DEPARTMENTS, 1):
        text += f"{i}. {dept}\n"
    
    return text

def format_fullname(fullname: str) -> str:
    """
    Приводит ФИО к правильному формату:
    первая буква большая, остальные маленькие в каждом слове
    
    Args:
        fullname: ФИО для форматирования
        
    Returns:
        Отформатированное ФИО
    """
    if not fullname:
        return ""
    
    # Убираем лишние пробелы и приводим к правильному регистру
    words = fullname.strip().split()
    formatted_words = []
    
    for word in words:
        if word:  # Проверяем что слово не пустое
            # Первая буква заглавная, остальные строчные
            formatted_word = word[0].upper() + word[1:].lower()
            formatted_words.append(formatted_word)
    
    return " ".join(formatted_words)

def get_departments_keyboard():
    """
    Создает клавиатуру с отделами для выбора в онбординге
    
    Returns:
        InlineKeyboardMarkup с кнопками отделов
    """
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    
    buttons = []
    
    # Добавляем кнопки по 1 в ряд для лучшей читаемости
    for dept in DEPARTMENTS:
        buttons.append([InlineKeyboardButton(
            text=f"🏢 {dept}",
            callback_data=f"dept:{dept}"
        )])
    
    # Добавляем кнопку "Пропустить" в конце
    buttons.append([InlineKeyboardButton(
        text="⏭️ Не знаю точно / Пропустить",
        callback_data="dept:skip"
    )])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_departments_text():
    """
    Получить текст с предложением выбрать отдел
    
    Returns:
        Форматированный текст для сообщения
    """
    text = "🏢 <b>Выберите ваш отдел:</b>\n\n"
    text += "📋 Нажмите на кнопку с вашим отделом из списка ниже:\n\n"
    
    # Добавляем список отделов в текст для информации
    for i, dept in enumerate(DEPARTMENTS, 1):
        text += f"   {i}. {dept}\n"
    
    text += "\n❓ Если вы не знаете точное название отдела - "
    text += "нажмите 'Пропустить'.\n"
    text += "HR-отдел получит уведомление и уточнит эту информацию с вами."
    
    return text 