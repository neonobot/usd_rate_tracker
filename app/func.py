"""
Вспомогательные функции для USD Tracker
"""
from datetime import datetime

import matplotlib
import numpy as np
import pandas as pd
import requests
from sqlalchemy.orm import Session

from app.tables import USDRate

matplotlib.use('Agg')
import matplotlib.pyplot as plt
import io
import base64


def get_current_usd_rate() -> float:
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
        # Возвращаем тестовое значение для разработки
        return 91.5


def predict_rate_change(current_rate: float, db: Session):
    """
    Простое предсказание: сравниваем с предыдущим курсом
    """
    try:
        # Получаем последнюю запись из БД
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
    except Exception as e:
        print(f"Ошибка в predict_rate_change: {e}")
        return "ERROR", None


def get_prediction_icon(prediction: str) -> tuple:
    """
    Возвращает иконку и цвет для предсказания
    """
    icons = {
        "UP": ("📈", "text-green-500", "bg-green-100", "border-green-300"),
        "DOWN": ("📉", "text-red-500", "bg-red-100", "border-red-300"),
        "SAME": ("➡️", "text-blue-500", "bg-blue-100", "border-blue-300"),
        "FIRST": ("✨", "text-purple-500", "bg-purple-100", "border-purple-300"),
        "ERROR": ("❌", "text-gray-500", "bg-gray-100", "border-gray-300"),
    }
    return icons.get(prediction, ("❓", "text-gray-500", "bg-gray-100", "border-gray-300"))


def format_change(change: float, is_percent: bool = False) -> tuple:
    """
    Форматирование изменения курса
    Возвращает (форматированная строка, цвет)
    """
    if change is None:
        return "N/A", "text-gray-500"

    try:
        if is_percent:
            formatted = f"{change:+.2f}%"
        else:
            formatted = f"{change:+.4f}"

        if change > 0:
            return formatted, "text-green-500"
        elif change < 0:
            return formatted, "text-red-500"
        else:
            return formatted, "text-blue-500"
    except:
        return "ERR", "text-gray-500"


def calculate_statistics(records):
    """
    Расчет статистики для графиков
    Возвращает (статистика, изображение_графика_в_base64)
    """
    if not records or len(records) < 2:
        return None, None

    try:
        # Создаем DataFrame
        df = pd.DataFrame([{
            'date': r.date,
            'rate': r.rate,
            'prediction': r.prediction
        } for r in records])

        rates = df['rate'].values

        # Основная статистика
        stats = {
            "total_records": len(records),
            "current_rate": float(rates[-1]) if len(rates) > 0 else 0,
            "minimum_rate": float(np.min(rates)) if len(rates) > 0 else 0,
            "maximum_rate": float(np.max(rates)) if len(rates) > 0 else 0,
            "average_rate": float(np.mean(rates)) if len(rates) > 0 else 0,
            "std_deviation": float(np.std(rates)) if len(rates) > 1 else 0,
            "first_record": records[0].date if records else None,
            "last_record": records[-1].date if records else None,
            "total_change": float(((rates[-1] - rates[0]) / rates[0] * 100)) if len(rates) > 1 and rates[0] != 0 else 0,
            "avg_daily_change": float(np.mean(np.diff(rates))) if len(rates) > 1 else 0,
        }

        # Создаем график
        plt.figure(figsize=(12, 6))

        # График 1: История курса
        plt.subplot(2, 2, 1)
        plt.plot(df['date'], df['rate'], 'b-', linewidth=2, label='Курс USD/RUB')
        plt.xlabel('Дата')
        plt.ylabel('Курс')
        plt.title('История курса USD/RUB')
        plt.grid(True, alpha=0.3)
        plt.xticks(rotation=45)
        plt.legend()

        # График 2: Изменения по дням
        plt.subplot(2, 2, 2)
        if len(rates) > 1:
            changes = np.diff(rates)
            colors = ['green' if x > 0 else 'red' for x in changes]
            plt.bar(range(len(changes)), changes, color=colors, alpha=0.7)
        plt.xlabel('День')
        plt.ylabel('Изменение')
        plt.title('Ежедневные изменения')
        plt.grid(True, alpha=0.3)

        # График 3: Распределение
        plt.subplot(2, 2, 3)
        plt.hist(rates, bins=min(15, len(rates)), edgecolor='black', alpha=0.7, color='skyblue')
        plt.xlabel('Курс')
        plt.ylabel('Частота')
        plt.title('Распределение курсов')
        plt.grid(True, alpha=0.3)

        # График 4: Скользящее среднее
        plt.subplot(2, 2, 4)
        if len(rates) >= 7:
            window = min(7, len(rates))
            ma = pd.Series(rates).rolling(window=window).mean()
            plt.plot(df['date'], rates, 'b-', alpha=0.5, label='Факт')
            plt.plot(df['date'], ma, 'r-', linewidth=2, label=f'Среднее ({window}д)')
            plt.xlabel('Дата')
            plt.ylabel('Курс')
            plt.title(f'Скользящее среднее ({window} дней)')
            plt.grid(True, alpha=0.3)
            plt.legend()
            plt.xticks(rotation=45)

        plt.tight_layout()

        # Сохраняем график в байты
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=100)
        plt.close()
        buf.seek(0)

        # Кодируем в base64 для HTML
        chart_image = base64.b64encode(buf.getvalue()).decode('utf-8')

        return stats, chart_image

    except Exception as e:
        print(f"Ошибка при расчете статистики: {e}")
        return None, None


def generate_html_response(title: str, content: str) -> str:
    """
    Генерация HTML ответа с базовым шаблоном
    """
    current_year = datetime.now().year

    html = f"""<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>USD Tracker - {title}</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        .gradient-bg {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        }}
    </style>
</head>
<body class="bg-gray-50 min-h-screen">
    <!-- Навигация -->
    <nav class="gradient-bg text-white shadow-lg">
        <div class="container mx-auto px-4 py-4">
            <div class="flex flex-col md:flex-row justify-between items-center">
                <div class="flex items-center space-x-3 mb-4 md:mb-0">
                    <i class="fas fa-dollar-sign text-2xl"></i>
                    <h1 class="text-2xl font-bold">USD/RUB Tracker</h1>
                </div>
                <div class="flex flex-wrap justify-center gap-2 md:gap-4">
                    <a href="/" class="px-3 py-2 rounded hover:bg-white hover:bg-opacity-20 transition">
                        <i class="fas fa-home mr-1"></i> Главная
                    </a>
                    <a href="/now" class="px-3 py-2 rounded hover:bg-white hover:bg-opacity-20 transition">
                        <i class="fas fa-chart-line mr-1"></i> Текущий курс
                    </a>
                    <a href="/update" class="px-3 py-2 rounded hover:bg-white hover:bg-opacity-20 transition">
                        <i class="fas fa-sync-alt mr-1"></i> Обновить
                    </a>
                    <a href="/last" class="px-3 py-2 rounded hover:bg-white hover:bg-opacity-20 transition">
                        <i class="fas fa-database mr-1"></i> Последний
                    </a>
                    <a href="/history" class="px-3 py-2 rounded hover:bg-white hover:bg-opacity-20 transition">
                        <i class="fas fa-history mr-1"></i> История
                    </a>
                    <a href="/predict" class="px-3 py-2 rounded hover:bg-white hover:bg-opacity-20 transition">
                        <i class="fas fa-crystal-ball mr-1"></i> Предсказание
                    </a>
                    <a href="/stats" class="px-3 py-2 rounded hover:bg-white hover:bg-opacity-20 transition">
                        <i class="fas fa-chart-bar mr-1"></i> Статистика
                    </a>
                </div>
            </div>
        </div>
    </nav>

    <!-- Основной контент -->
    <main class="container mx-auto px-4 py-8">
        {content}
    </main>

    <!-- Футер -->
    <footer class="bg-gray-800 text-white py-6 mt-8">
        <div class="container mx-auto px-4 text-center">
            <p>USD/RUB Tracker • Данные предоставлены ЦБ РФ • {current_year}</p>
        </div>
    </footer>
</body>
</html>"""

    return html


def get_error_html(error_message: str) -> str:
    """Генерация HTML для страницы ошибки"""
    content = f"""
    <div class="max-w-2xl mx-auto">
        <div class="bg-white rounded-xl shadow-lg p-8 text-center">
            <div class="text-red-500 text-5xl mb-6">
                <i class="fas fa-exclamation-triangle"></i>
            </div>
            <h2 class="text-3xl font-bold text-gray-800 mb-4">Ошибка</h2>
            <p class="text-gray-600 mb-8">{error_message}</p>
            <div class="space-x-4">
                <a href="/" class="inline-block bg-blue-500 text-white px-6 py-3 rounded-lg hover:bg-blue-600 transition">
                    <i class="fas fa-home mr-2"></i> На главную
                </a>
                <a href="/now" class="inline-block bg-green-500 text-white px-6 py-3 rounded-lg hover:bg-green-600 transition">
                    <i class="fas fa-chart-line mr-2"></i> Текущий курс
                </a>
            </div>
        </div>
    </div>
    """
    return generate_html_response("Ошибка", content)
