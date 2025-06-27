# 📁 Настройка Git для передачи проекта

## 🔐 Безопасная передача кода

### 1. Инициализация репозитория

```bash
# В папке проекта
git init
git add .gitignore
git commit -m "Initial: Add gitignore"

# Добавляем код (без секретных данных)
git add .
git commit -m "feat: Initial project setup - Corporate Telegram Bot"
```

### 2. Создание удаленного репозитория

#### Вариант A: GitHub
```bash
# Создайте репозиторий на GitHub, затем:
git remote add origin https://github.com/your-username/prodaction-bot.git
git branch -M main
git push -u origin main
```

#### Вариант B: GitLab
```bash
# Создайте репозиторий на GitLab, затем:
git remote add origin https://gitlab.com/your-username/prodaction-bot.git
git branch -M main
git push -u origin main
```

#### Вариант C: Корпоративный Git
```bash
# Используйте адрес вашего корпоративного сервера
git remote add origin https://git.company.com/your-username/prodaction-bot.git
git branch -M main
git push -u origin main
```

### 3. Проверка перед отправкой

```bash
# Убедитесь, что секретные файлы исключены
git status

# Не должно быть в списке:
# - .env
# - data/
# - logs/
# - venv/
# - __pycache__/
```

## 📋 Чек-лист для коллег

### ✅ Что включено в репозиторий:

- **Код приложения** (`app/`)
- **Конфигурация** (`main.py`, `requirements.txt`, `alembic.ini`)
- **Миграции** (`migrations/`)  
- **Документация** (`README.md`, `PROJECT_ANALYSIS.md`, `DEPLOYMENT.md`)
- **Пример настроек** (`env.example`)

### ❌ Что НЕ включено (в .gitignore):

- **Токены и пароли** (`.env`)
- **База данных** (`data/`)
- **Логи** (`logs/`)
- **Виртуальное окружение** (`venv/`)
- **Временные файлы** (`temp/`, `__pycache__/`)

## 🚀 Инструкция для коллег

### 1. Клонирование проекта

```bash
git clone <URL_РЕПОЗИТОРИЯ>
cd prodaction-bot
```

### 2. Настройка окружения

```bash
# Создание виртуального окружения
python3.12 -m venv venv
source venv/bin/activate  # Linux/Mac
# или
venv\Scripts\activate     # Windows

# Установка зависимостей
pip install -r requirements.txt
```

### 3. Конфигурация

```bash
# Копируйте пример настроек
cp env.example .env

# Отредактируйте .env:
nano .env
```

**Нужно настроить:**
- `BOT_TOKEN` - получить у @BotFather
- `GROUP_ID` - ID закрытой группы сотрудников
- `ADMIN_IDS` - ID администраторов

### 4. Инициализация базы данных

```bash
# Создание папок
mkdir -p data logs temp

# Применение миграций
alembic upgrade head

# Инициализация системных данных
python migrations/create_auto_events_system.py
```

### 5. Запуск

```bash
python main.py
```

## ⚠️ Важные замечания

### 🔒 Безопасность
- **НИКОГДА** не коммитьте файл `.env` в Git
- **НИКОГДА** не коммитьте реальную базу данных
- Используйте разные токены для разработки и продакшена

### 🐛 Известные проблемы
- **Модуль аналитики не работает** (`app/orders/analytics.py`)
- Требует исправления перед использованием в продакшене

### 📱 Тестирование
1. Создайте тестового бота в @BotFather
2. Создайте тестовую группу
3. Добавьте бота в группу как администратора
4. Протестируйте основные функции

## 🔄 Обновление проекта

### Получение обновлений

```bash
# Получить последние изменения
git pull origin main

# Обновить зависимости (если изменились)
pip install -r requirements.txt

# Применить новые миграции
alembic upgrade head

# Перезапустить бота
```

### Отправка изменений

```bash
# Добавить изменения
git add .

# Создать коммит
git commit -m "feat: описание изменений"

# Отправить в репозиторий
git push origin main
```

## 📞 Поддержка

При проблемах с настройкой:

1. **Проверьте логи**: `logs/bot.log`
2. **Проверьте .env**: все ли переменные заданы
3. **Проверьте права бота**: администратор ли он в группе
4. **Проверьте токен**: валиден ли BOT_TOKEN

## 🎯 Готовые команды для быстрого старта

```bash
# Полная установка с нуля
git clone <URL_РЕПОЗИТОРИЯ>
cd prodaction-bot
python3.12 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp env.example .env
# ОТРЕДАКТИРОВАТЬ .env ФАЙЛ!
mkdir -p data logs temp
alembic upgrade head
python migrations/create_auto_events_system.py
python main.py
```

---

**🎉 Готово! Проект настроен и готов к работе.** 