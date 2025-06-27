# 🚀 Развертывание в продакшене

## 📋 Предварительные требования

### Системные требования
- **ОС**: Ubuntu 20.04+ / CentOS 8+ / Debian 11+
- **Python**: 3.12+
- **RAM**: минимум 2GB (рекомендуется 4GB для 100 пользователей)
- **CPU**: 2+ ядра
- **Диск**: 10GB свободного места
- **Интернет**: стабильное соединение для Telegram API

### Необходимые данные
- **BOT_TOKEN** - токен бота от @BotFather
- **GROUP_ID** - ID закрытой группы сотрудников
- **ADMIN_IDS** - список ID администраторов через запятую

---

## 📦 Установка и настройка

### 1. Подготовка сервера

```bash
# Обновление системы
sudo apt update && sudo apt upgrade -y

# Установка Python 3.12 и зависимостей
sudo apt install python3.12 python3.12-venv python3.12-dev git nginx supervisor -y

# Создание пользователя для бота
sudo useradd -m -s /bin/bash botuser
sudo su - botuser
```

### 2. Клонирование проекта

```bash
# Клонирование в домашнюю папку
cd /home/botuser
git clone <YOUR_REPOSITORY_URL> prodaction-bot
cd prodaction-bot

# Создание виртуального окружения
python3.12 -m venv venv
source venv/bin/activate

# Установка зависимостей
pip install --upgrade pip
pip install -r requirements.txt
```

### 3. Настройка конфигурации

```bash
# Создание файла окружения
cp .env.example .env
nano .env
```

**Содержимое .env:**
```env
# Основные настройки бота
BOT_TOKEN=your_bot_token_here
GROUP_ID=-1001234567890
ADMIN_IDS=123456789,987654321

# Настройки базы данных
DATABASE_URL=sqlite+aiosqlite:///data/shop.db

# Настройки логирования
LOG_LEVEL=INFO
LOG_FILE=logs/bot.log

# Настройки для продакшена
ENVIRONMENT=production
DEBUG=False
```

### 4. Инициализация базы данных

```bash
# Создание папок
mkdir -p data logs temp

# Инициализация Alembic (если первый запуск)
alembic init migrations

# Создание первой миграции
alembic revision --autogenerate -m "Initial migration"

# Применение миграций
alembic upgrade head

# Инициализация данных системы
python migrations/create_auto_events_system.py
```

### 5. Тестирование запуска

```bash
# Тестовый запуск бота
python main.py

# Если всё работает, останавливаем (Ctrl+C)
```

---

## 🔧 Настройка автозапуска

### 1. Создание systemd сервиса

```bash
sudo nano /etc/systemd/system/prodaction-bot.service
```

**Содержимое сервиса:**
```ini
[Unit]
Description=Prodaction Telegram Bot
After=network.target

[Service]
Type=simple
User=botuser
Group=botuser
WorkingDirectory=/home/botuser/prodaction-bot
Environment=PATH=/home/botuser/prodaction-bot/venv/bin
ExecStart=/home/botuser/prodaction-bot/venv/bin/python main.py
Restart=always
RestartSec=10

# Переменные окружения
EnvironmentFile=/home/botuser/prodaction-bot/.env

# Логирование
StandardOutput=journal
StandardError=journal
SyslogIdentifier=prodaction-bot

[Install]
WantedBy=multi-user.target
```

### 2. Запуск сервиса

```bash
# Обновление systemd
sudo systemctl daemon-reload

# Включение автозапуска
sudo systemctl enable prodaction-bot

# Запуск сервиса
sudo systemctl start prodaction-bot

# Проверка статуса
sudo systemctl status prodaction-bot

# Просмотр логов
sudo journalctl -u prodaction-bot -f
```

---

## 📊 Мониторинг и обслуживание

### Команды управления

```bash
# Перезапуск бота
sudo systemctl restart prodaction-bot

# Остановка бота
sudo systemctl stop prodaction-bot

# Просмотр логов в реальном времени
sudo journalctl -u prodaction-bot -f

# Просмотр последних 100 строк логов
sudo journalctl -u prodaction-bot -n 100

# Проверка использования ресурсов
htop
df -h
free -h
```

### Ротация логов

```bash
# Создание конфигурации logrotate
sudo nano /etc/logrotate.d/prodaction-bot
```

```
/home/botuser/prodaction-bot/logs/*.log {
    daily
    missingok
    rotate 30
    compress
    delaycompress
    notifempty
    sharedscripts
    postrotate
        systemctl reload prodaction-bot
    endscript
}
```

### Мониторинг базы данных

```bash
# Размер базы данных
ls -lh data/shop.db

# Бэкап базы данных
cp data/shop.db data/shop_backup_$(date +%Y%m%d_%H%M%S).db

# Автоматический бэкап (добавить в crontab)
crontab -e
# Добавить строку:
# 0 2 * * * cp /home/botuser/prodaction-bot/data/shop.db /home/botuser/prodaction-bot/data/shop_backup_$(date +\%Y\%m\%d).db
```

---

## 🔄 Обновление проекта

### Стандартная процедура обновления

```bash
# Переход в директорию проекта
cd /home/botuser/prodaction-bot

# Активация виртуального окружения
source venv/bin/activate

# Создание бэкапа базы данных
cp data/shop.db data/shop_backup_$(date +%Y%m%d_%H%M%S).db

# Остановка сервиса
sudo systemctl stop prodaction-bot

# Получение обновлений
git pull origin main

# Обновление зависимостей (если изменились)
pip install -r requirements.txt

# Применение миграций (если есть новые)
alembic upgrade head

# Запуск сервиса
sudo systemctl start prodaction-bot

# Проверка статуса
sudo systemctl status prodaction-bot
```

---

## 🛡️ Безопасность

### Настройка firewall

```bash
# Базовая настройка ufw
sudo ufw enable
sudo ufw default deny incoming
sudo ufw default allow outgoing

# Разрешение SSH (если нужен)
sudo ufw allow 22/tcp

# Проверка статуса
sudo ufw status
```

### Права доступа

```bash
# Настройка прав на файлы
chmod 600 .env
chmod +x main.py
chmod -R 755 app/
chmod 644 data/shop.db
```

### Бэкапы

```bash
# Создание скрипта бэкапа
nano backup.sh
```

```bash
#!/bin/bash
BACKUP_DIR="/home/botuser/backups"
DATE=$(date +%Y%m%d_%H%M%S)

mkdir -p $BACKUP_DIR

# Бэкап базы данных
cp data/shop.db $BACKUP_DIR/shop_$DATE.db

# Бэкап конфигурации
cp .env $BACKUP_DIR/env_$DATE.txt

# Удаление старых бэкапов (старше 30 дней)
find $BACKUP_DIR -name "*.db" -mtime +30 -delete
find $BACKUP_DIR -name "*.txt" -mtime +30 -delete

echo "Backup completed: $DATE"
```

```bash
chmod +x backup.sh

# Добавление в crontab для ежедневного бэкапа
crontab -e
# 0 1 * * * /home/botuser/prodaction-bot/backup.sh
```

---

## 📈 Производительность

### Оптимизация для 100 пользователей

**Рекомендации по конфигурации:**

1. **Пул соединений SQLAlchemy:**
```python
# В app/database.py
engine = create_async_engine(
    database_url,
    pool_size=20,
    max_overflow=30,
    pool_timeout=30,
    pool_recycle=3600
)
```

2. **Настройка логирования:**
```python
# Установка уровня INFO для продакшена
logging.basicConfig(level=logging.INFO)
```

3. **Мониторинг ресурсов:**
```bash
# Установка мониторинга
sudo apt install htop iotop nethogs -y

# Просмотр процессов бота
ps aux | grep python
```

### Тестирование нагрузки

```bash
# Тестирование отклика бота
time curl -s "https://api.telegram.org/bot$BOT_TOKEN/getMe"

# Мониторинг использования памяти
watch 'ps -p $(pgrep -f "python main.py") -o pid,rss,vsz,pcpu,pmem,cmd'
```

---

## ❗ Устранение неполадок

### Частые проблемы

1. **Бот не отвечает**
```bash
sudo systemctl status prodaction-bot
sudo journalctl -u prodaction-bot -n 50
```

2. **Ошибки базы данных**
```bash
# Проверка целостности SQLite
sqlite3 data/shop.db "PRAGMA integrity_check;"
```

3. **Проблемы с памятью**
```bash
# Проверка использования памяти
free -h
ps aux --sort=-%mem | head
```

4. **Проблемы с правами доступа**
```bash
# Восстановление прав
sudo chown -R botuser:botuser /home/botuser/prodaction-bot
chmod 600 .env
```

### Контакты поддержки

При критических проблемах:
1. Сохраните логи: `sudo journalctl -u prodaction-bot > problem_logs.txt`
2. Создайте бэкап БД: `cp data/shop.db emergency_backup.db`
3. Опишите проблему и приложите логи

---

## ✅ Чек-лист развертывания

- [ ] Сервер подготовлен и обновлен
- [ ] Python 3.12+ установлен
- [ ] Пользователь `botuser` создан
- [ ] Проект склонирован и настроен
- [ ] Файл `.env` создан и заполнен
- [ ] Виртуальное окружение активировано
- [ ] Зависимости установлены
- [ ] База данных инициализирована
- [ ] Миграции применены
- [ ] Системные данные загружены
- [ ] Systemd сервис настроен
- [ ] Автозапуск включен
- [ ] Логирование настроено
- [ ] Бэкапы настроены
- [ ] Мониторинг настроен
- [ ] Firewall настроен
- [ ] Тестирование проведено

**🎉 Бот готов к работе в продакшене!** 