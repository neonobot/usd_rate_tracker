from sqlalchemy import Column, Integer, String, Float, DateTime, Text
from sqlalchemy.sql import func
from clickhouse_sqlalchemy import engines
from datetime import datetime
from app.database import Base


class USDRate(Base):
    """
    Таблица с информацией о курсе
    """
    __tablename__ = "usd_rates"
    
    __table_args__ = (
        engines.MergeTree(
            order_by=['date'],
            partition_by=func.toYYYYMM('date'),
            primary_key=['date']
        ),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
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
    
    __table_args__ = (
        engines.MergeTree(
            order_by=['request_time'],
            partition_by=func.toYYYYMMDD('request_time'),
            primary_key=['request_time'],
            ttl=func.date_add(func.now(), func.toIntervalDay(30))  # Хранить 30 дней
        ),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    endpoint = Column(String(100), nullable=False)
    method = Column(String(10), nullable=False)
    client_ip = Column(String(50), nullable=True)
    user_agent = Column(String(500), nullable=True)
    request_time = Column(DateTime, default=datetime.utcnow)
    response_time = Column(DateTime, nullable=True)
    status_code = Column(Integer, nullable=True)
    response_data = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)
    processing_time_ms = Column(Integer, nullable=True)

    def __repr__(self):
        return f"<RequestLog(endpoint={self.endpoint}, status={self.status_code})>"