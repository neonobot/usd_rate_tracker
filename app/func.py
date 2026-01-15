import requests
from sqlalchemy.orm import Session

from app.tables import USDRate


def get_current_usd_rate():
    """
    Получить текущий курс USD с сайта ЦБ РФ
    """
    try:
        response = requests.get(
            "https://www.cbr-xml-daily.ru/daily_json.js",
            timeout=5
        )
        data = response.json()
        usd_rate = data["Valute"]["USD"]["Value"]
        return usd_rate
    except Exception as e:
        print(f"Ошибка при получении курса: {e}")
        # Возвращаем тестовое значение
        return 91.5


def predict_rate_change(current_rate: float, db: Session):
    """
    Простое предсказание: сравниваем с предыдущим курсом
    """
    # Последняя запись из БД
    last_record = db.query(USDRate).order_by(USDRate.date.desc()).first()

    if not last_record:
        return "FIRST", None

    previous_rate = last_record.rate
    change = current_rate - previous_rate

    if change > 0.01:
        return "UP", previous_rate
    elif change < -0.01:
        return "DOWN", previous_rate
    else:
        return "SAME", previous_rate
