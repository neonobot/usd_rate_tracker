"""
Сервис для логирования запросов в ClickHouse
"""
import json
from datetime import datetime
from typing import Dict, Optional

from fastapi import Request
from sqlalchemy.orm import Session

from app.tables import RequestLog


class RequestLogger:
    @staticmethod
    def log_request(
            db: Session,
            request: Request,
            endpoint: str,
            start_time: datetime,
            response_data: Optional[Dict] = None,
            status_code: int = 200,
            error: Optional[str] = None
    ):
        """Логирование запроса в ClickHouse"""
        try:
            end_time = datetime.utcnow()
            processing_time = int((end_time - start_time).total_seconds() * 1000)

            # Получаем IP клиента
            client_ip = request.client.host if request.client else None

            # Получаем User-Agent
            user_agent = request.headers.get("user-agent")

            # Преобразуем response_data в JSON строку
            response_json = json.dumps(response_data) if response_data else None

            # Создаем запись лога
            log_entry = RequestLog(
                endpoint=endpoint,
                method=request.method,
                client_ip=client_ip,
                user_agent=user_agent,
                request_time=start_time,
                response_time=end_time,
                status_code=status_code,
                response_data=response_json,
                error_message=error,
                processing_time_ms=processing_time
            )

            db.add(log_entry)
            db.commit()

        except Exception as e:
            print(f"Ошибка логирования: {e}")
            try:
                db.rollback()
            except:
                pass

    @staticmethod
    def get_recent_logs(db: Session, limit: int = 100):
        """Получение последних логов"""
        return db.query(RequestLog) \
            .order_by(RequestLog.request_time.desc()) \
            .limit(limit) \
            .all()

    @staticmethod
    def get_stats(db: Session):
        """Статистика по логам для ClickHouse"""
        from sqlalchemy import func

        total = db.query(func.count(RequestLog.id)).scalar()
        errors = db.query(func.count(RequestLog.id)) \
            .filter(RequestLog.status_code >= 400) \
            .scalar()

        # Самые популярные эндпоинты
        popular = db.query(
            RequestLog.endpoint,
            func.count(RequestLog.id).label('count')
        ).group_by(RequestLog.endpoint) \
            .order_by(func.count(RequestLog.id).desc()) \
            .limit(5) \
            .all()

        # Среднее время обработки
        avg_time = db.query(func.avg(RequestLog.processing_time_ms)).scalar()

        return {
            "total_requests": total or 0,
            "error_requests": errors or 0,
            "success_rate": ((total - errors) / total * 100) if total > 0 else 100,
            "average_processing_time_ms": round(avg_time, 2) if avg_time else 0,
            "most_popular_endpoints": [
                {"endpoint": e[0], "count": e[1]} for e in popular
            ]
        }