import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# Загружаем переменные окружения
load_dotenv()

# Получаем URL базы данных из .env файла
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./usd_tracker.db")

print(f"Using database: {DATABASE_URL}")  # Добавьте эту строку для отладки

# Всегда используем SQLite для простоты
if "clickhouse" in DATABASE_URL:
    # Принудительно меняем на SQLite если ClickHouse не работает
    DATABASE_URL = "sqlite:///./usd_tracker.db"
    print(f"Switched to SQLite: {DATABASE_URL}")

# Создаем движок
if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False}
    )
else:
    engine = create_engine(DATABASE_URL)

# Создаем фабрику сессий
SessionLocal = sessionmaker(
    autocommit=False, 
    autoflush=False, 
    bind=engine
)

# Базовый класс для моделей
Base = declarative_base()


# Функция для получения сессии БД
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()