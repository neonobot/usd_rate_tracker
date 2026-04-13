# USD/RUB Tracker

Инструмент для сбора, хранения и анализа исторических данных курса USD/RUB с функциями прогнозирования.

## Данные

**Источник:** ЦБ РФ (cbr-xml-daily.ru)

**Собираемые метрики:**
- `rate` — курс USD/RUB
- `date` — временная метка
- `prediction` — прогноз направления (UP/DOWN/SAME)
- `previous_rate` — предыдущее значение

## Быстрый старт

```bash
git clone https://github.com/neonobot/usd_rate_tracker.git
cd usd_rate_tracker
pip install -r requirements.txt
python run.py
```

Приложение доступно на `http://localhost:8000`

## Аналитические возможности

### Сбор данных
```python
# Ручной сбор
GET /update

# API
GET /api/update
```

### Статистика (`/stats`)
- Временной ряд курса
- Распределение значений
- Скользящее среднее (7 дней)
- Волатильность и дневные изменения

### Прогнозирование (`/predict`)
- Анализ последних N записей
- Среднее изменение за период
- Метрика уверенности прогноза

## Структура данных

```sql
-- usd_rates
id          INTEGER PRIMARY KEY
rate        FLOAT      -- курс
date        DATETIME   -- временная метка
prediction  VARCHAR    -- UP/DOWN/SAME/FIRST
prev_rate   FLOAT      -- предыдущее значение

-- request_logs (для аудита)
endpoint, method, status_code, processing_time_ms, ...
```

## Конфигурация БД

`.env`:
```env
# SQLite (по умолчанию)
DATABASE_URL=sqlite:///./usd_tracker.db

# PostgreSQL
DATABASE_URL=postgresql://user:pass@localhost:5432/usd

# ClickHouse (для больших объемов)
DATABASE_URL=clickhouse://default:@localhost:8123/usd
```

## Зависимости

```txt
fastapi==0.104.1
sqlalchemy==2.0.23
pandas==2.1.4
numpy==1.26.2
matplotlib==3.8.2
```

## 📄 Лицензия

MIT
