from datetime import datetime

from sqlalchemy import Column, Integer, Float, String, DateTime

from app.database import Base


class USDRate(Base):

    __tablename__ = "usd_rates"  # Имя таблицы в БД

    # Колонки таблицы:

    # 1. ID - первичный ключ, auto-increment
    id = Column(Integer, primary_key=True, index=True)
    # primary_key=True - уникальный идентификатор
    # index=True - создает индекс для быстрого поиска

    # 2. Курс USD/RUB (число с плавающей точкой)
    rate = Column(Float, nullable=False)
    # nullable=False - поле обязательно для заполнения

    # 3. Дата и время сохранения
    date = Column(DateTime, default=datetime.utcnow)
    # default=datetime.utcnow - текущее время UTC

    # 4. Предсказание (строка): "UP", "DOWN", "SAME", "FIRST"
    prediction = Column(String, nullable=True)
    # nullable=True - поле может быть пустым

    # 5. Предыдущий курс для сравнения
    previous_rate = Column(Float, nullable=True)

    # Метод для красивого вывода (необязательно)
    def __repr__(self):
        return f"<USDRate(rate={self.rate}, date={self.date})>"
