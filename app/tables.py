from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, Text
from datetime import datetime
from app.database import Base


class USDRate(Base):
    """
    Таблица с информацией о курсе
    """
    __tablename__ = "usd_rates"

    id = Column(Integer, primary_key=True, index=True)
    rate = Column(Float, nullable=False)
    date = Column(DateTime, default=datetime.utcnow)
    prediction = Column(String, nullable=True)
    previous_rate = Column(Float, nullable=True)

    def __repr__(self):
        return f"<USDRate(rate={self.rate}, date={self.date})>"


class RequestLog(Base):
    """
    Таблица для логирования всех запросов к API
    """
    __tablename__ = "request_logs"

    id = Column(Integer, primary_key=True, index=True)
    endpoint = Column(String(100), nullable=False)
    method = Column(String(10), nullable=False)
    client_ip = Column(String(50), nullable=True)
    user_agent = Column(String(500), nullable=True)
    request_time = Column(DateTime, default=datetime.utcnow)
    response_time = Column(DateTime, nullable=True)
    status_code = Column(Integer, nullable=True)
    response_data = Column(Text, nullable=True)  # JSON в виде текста
    error_message = Column(Text, nullable=True)
    processing_time_ms = Column(Integer, nullable=True)

    def __repr__(self):
        return f"<RequestLog(endpoint={self.endpoint}, status={self.status_code})>"
