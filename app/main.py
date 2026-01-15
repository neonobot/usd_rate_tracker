from datetime import datetime

import matplotlib
from fastapi import FastAPI, Depends
from sqlalchemy.orm import Session

from app.database import get_db, engine
from app.func import get_current_usd_rate, predict_rate_change
from app.tables import USDRate, Base

matplotlib.use('Agg')  # Важно для серверного использования
import matplotlib.pyplot as plt
import io
import base64
import pandas as pd
import numpy as np

# Создание таблицы в БД
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="USD Tracker API",
    description="API для отслеживания курса USD/RUB"
)

# ========== API ENDPOINTS ==========
from fastapi.responses import HTMLResponse


@app.get("/", response_class=HTMLResponse)
def root():
    """
    Главная страница с кликабельными ссылками
    """
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>USD Tracker API</title>
        <style>
            body {
                font-family: Arial, sans-serif;
                max-width: 800px;
                margin: 40px auto;
                padding: 20px;
                background-color: #f5f5f5;
            }
            .container {
                background: white;
                padding: 30px;
                border-radius: 10px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            }
            h1 {
                color: #333;
                border-bottom: 2px solid #4CAF50;
                padding-bottom: 10px;
            }
            .endpoint {
                background: #f8f9fa;
                margin: 10px 0;
                padding: 15px;
                border-left: 4px solid #4CAF50;
                border-radius: 5px;
            }
            a {
                color: #4CAF50;
                text-decoration: none;
                font-weight: bold;
            }
            a:hover {
                text-decoration: underline;
            }
            .method {
                display: inline-block;
                background: #4CAF50;
                color: white;
                padding: 3px 8px;
                border-radius: 3px;
                font-size: 12px;
                margin-right: 10px;
            }
            .docs-link {
                display: inline-block;
                background: #2196F3;
                color: white;
                padding: 10px 20px;
                border-radius: 5px;
                text-decoration: none;
                margin-top: 20px;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>💰 USD/RUB Tracker API</h1>
            <p>API для отслеживания курса USD к RUB с сайта ЦБ РФ</p>

            <h2>📋 Доступные эндпоинты:</h2>

            <div class="endpoint">
                <span class="method">GET</span>
                <a href="/docs" target="_blank">/docs</a>
                <p>📖 Документация Swagger UI (интерактивная)</p>
            </div>

            <div class="endpoint">
                <span class="method">GET</span>
                <a href="/now" target="_blank">/now</a>
                <p>📈 Текущий курс USD (без сохранения в БД)</p>
            </div>

            <div class="endpoint">
                <span class="method">GET</span>
                <a href="/update" target="_blank">/update</a>
                <p>💾 Получить текущий курс и сохранить в БД</p>
            </div>

            <div class="endpoint">
                <span class="method">GET</span>
                <a href="/last" target="_blank">/last</a>
                <p>📊 Последний сохраненный курс из БД</p>
            </div>

            <div class="endpoint">
                <span class="method">GET</span>
                <a href="/history" target="_blank">/history</a>
                <p>📅 История курсов (по умолчанию 10 последних)</p>
            </div>

            <div class="endpoint">
                <span class="method">GET</span>
                <a href="/predict" target="_blank">/predict</a>
                <p>🔮 Предсказать следующее изменение курса</p>
            </div>

            <div class="endpoint">
                <span class="method">GET</span>
                <a href="/stats" target="_blank">/stats</a>
                <p>📊 Статистика по сохраненным курсам</p>
            </div>

            <h2>🚀 Быстрый старт:</h2>
            <ol>
                <li>Нажмите <a href="/update">/update</a> чтобы получить и сохранить текущий курс</li>
                <li>Нажмите <a href="/last">/last</a> чтобы увидеть результат</li>
                <li>Используйте <a href="/predict">/predict</a> для предсказания</li>
            </ol>

            <a href="/docs" class="docs-link" target="_blank">📖 Открыть Swagger документацию</a>
        </div>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)


@app.get("/now")
def get_current_rate():
    """
    Получение текущего курса USD с сайта ЦБ
    """
    rate = get_current_usd_rate()
    return {
        "rate": rate,
        "currency": "USD/RUB",
        "timestamp": datetime.utcnow().isoformat()
    }


@app.get("/update")
def update_and_save_rate(db: Session = Depends(get_db)):
    """
    Получить текущий курс и сохранить в БД
    """
    # Получаем текущий курс
    current_rate = get_current_usd_rate()

    # Делаем предсказание
    prediction, previous_rate = predict_rate_change(current_rate, db)

    # Сохраняем в БД
    new_rate = USDRate(
        rate=current_rate,
        prediction=prediction,
        previous_rate=previous_rate
    )

    db.add(new_rate)
    db.commit()

    return {
        "status": "success",
        "message": "Курс сохранен в БД",
        "data": {
            "rate": current_rate,
            "prediction": prediction,
            "previous_rate": previous_rate,
            "saved_at": datetime.utcnow().isoformat()
        }
    }


@app.get("/last")
def get_last_saved_rate(db: Session = Depends(get_db)):
    """
    Получить последний сохраненный курс из БД
    """
    last_record = db.query(USDRate).order_by(USDRate.date.desc()).first()

    if not last_record:
        return {
            "status": "error",
            "message": "В БД нет данных. Используйте /update сначала."
        }

    return {
        "status": "success",
        "data": {
            "rate": last_record.rate,
            "prediction": last_record.prediction,
            "previous_rate": last_record.previous_rate,
            "saved_at": last_record.date.isoformat()
        }
    }


@app.get("/history")
def get_rate_history(
        limit: int = 10,
        db: Session = Depends(get_db)
):
    """
    Получить историю сохраненных курсов
    """
    records = db.query(USDRate) \
        .order_by(USDRate.date.desc()) \
        .limit(limit) \
        .all()

    if not records:
        return {
            "status": "error",
            "message": "В БД нет данных"
        }

    history = []
    for record in records:
        history.append({
            "rate": record.rate,
            "prediction": record.prediction,
            "saved_at": record.date.isoformat()
        })

    return {
        "status": "success",
        "count": len(history),
        "data": history
    }


@app.get("/predict")
def predict_future_rate(db: Session = Depends(get_db)):
    """
    Предсказать будущее изменение курса на основе истории
    """
    # Получаем последние 5 записей
    records = db.query(USDRate) \
        .order_by(USDRate.date.desc()) \
        .limit(5) \
        .all()

    if len(records) < 2:
        return {
            "status": "error",
            "message": "Недостаточно данных для предсказания"
        }

    rates = [record.rate for record in records]

    # Вычисляем среднее изменение
    changes = []
    for i in range(len(rates) - 1):
        change_percent = ((rates[i] - rates[i + 1]) / rates[i + 1]) * 100
        changes.append(change_percent)

    avg_change = sum(changes) / len(changes)

    # Делаем предсказание на основе среднего изменения
    if avg_change > 0.1:
        prediction = "UP"
        confidence = min(0.95, avg_change / 10)
    elif avg_change < -0.1:
        prediction = "DOWN"
        confidence = min(0.95, abs(avg_change) / 10)
    else:
        prediction = "STABLE"
        confidence = 0.7

    return {
        "status": "success",
        "prediction": prediction,
        "confidence": round(confidence, 2),
        "avg_daily_change": round(avg_change, 3),
        "based_on_last": len(records),
        "current_rate": rates[0]
    }


@app.get("/stats", response_class=HTMLResponse)
def get_statistics(db: Session = Depends(get_db)):
    """
    Получить статистику с графиком
    """
    records = db.query(USDRate).order_by(USDRate.date.asc()).all()

    if not records:
        return HTMLResponse(content="<h3>Нет данных в БД</h3>")

    # Преобразуем в DataFrame для удобства
    df = pd.DataFrame([{
        'date': r.date,
        'rate': r.rate,
        'prediction': r.prediction
    } for r in records])

    # Основная статистика
    rates = df['rate'].values
    stats = {
        "total_records": len(records),
        "current_rate": rates[-1],
        "minimum_rate": float(np.min(rates)),
        "maximum_rate": float(np.max(rates)),
        "average_rate": float(np.mean(rates)),
        "std_deviation": float(np.std(rates)),
        "first_record": records[0].date.isoformat(),
        "last_record": records[-1].date.isoformat(),
        "total_change": float(((rates[-1] - rates[0]) / rates[0]) * 100),
        "avg_daily_change": float(np.mean(np.diff(rates))),
    }

    # Создаем график
    plt.figure(figsize=(12, 6))

    # График курса
    plt.subplot(2, 2, 1)
    plt.plot(df['date'], df['rate'], 'b-', linewidth=2, label='Курс USD/RUB')
    plt.xlabel('Дата')
    plt.ylabel('Курс')
    plt.title('История курса USD/RUB')
    plt.grid(True, alpha=0.3)
    plt.xticks(rotation=45)
    plt.legend()

    # Изменения по дням
    plt.subplot(2, 2, 2)
    changes = np.diff(rates)
    colors = ['green' if x > 0 else 'red' for x in changes]
    plt.bar(range(len(changes)), changes, color=colors, alpha=0.7)
    plt.xlabel('День')
    plt.ylabel('Изменение')
    plt.title('Ежедневные изменения')
    plt.grid(True, alpha=0.3)

    # Распределение
    plt.subplot(2, 2, 3)
    plt.hist(rates, bins=15, edgecolor='black', alpha=0.7, color='skyblue')
    plt.xlabel('Курс')
    plt.ylabel('Частота')
    plt.title('Распределение курсов')
    plt.grid(True, alpha=0.3)

    # Скользящее среднее
    plt.subplot(2, 2, 4)
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
    image_base64 = base64.b64encode(buf.getvalue()).decode('utf-8')

    # Создаем HTML страницу
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Статистика USD/RUB</title>
        <style>
            body {{
                font-family: Arial, sans-serif;
                max-width: 1200px;
                margin: 0 auto;
                padding: 20px;
                background-color: #f8f9fa;
            }}
            .header {{
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                padding: 30px;
                border-radius: 10px;
                margin-bottom: 30px;
                text-align: center;
            }}
            .stats-grid {{
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
                gap: 20px;
                margin-bottom: 30px;
            }}
            .stat-card {{
                background: white;
                padding: 20px;
                border-radius: 10px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                text-align: center;
            }}
            .stat-value {{
                font-size: 2em;
                font-weight: bold;
                color: #667eea;
                margin: 10px 0;
            }}
            .stat-label {{
                color: #666;
                font-size: 0.9em;
            }}
            .chart-container {{
                background: white;
                padding: 20px;
                border-radius: 10px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                margin-bottom: 30px;
                text-align: center;
            }}
            .chart-title {{
                font-size: 1.5em;
                margin-bottom: 20px;
                color: #333;
            }}
            img {{
                max-width: 100%;
                border-radius: 5px;
            }}
            .navigation {{
                text-align: center;
                margin-top: 30px;
            }}
            .btn {{
                display: inline-block;
                background: #667eea;
                color: white;
                padding: 10px 20px;
                text-decoration: none;
                border-radius: 5px;
                margin: 0 5px;
            }}
            .btn:hover {{
                background: #5a67d8;
            }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>📊 Статистика курса USD/RUB</h1>
            <p>Анализ исторических данных курса доллара</p>
        </div>

        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-label">Текущий курс</div>
                <div class="stat-value">{stats['current_rate']:.2f} ₽</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Минимальный</div>
                <div class="stat-value">{stats['minimum_rate']:.2f} ₽</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Максимальный</div>
                <div class="stat-value">{stats['maximum_rate']:.2f} ₽</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Средний</div>
                <div class="stat-value">{stats['average_rate']:.2f} ₽</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Всего записей</div>
                <div class="stat-value">{stats['total_records']}</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Общее изменение</div>
                <div class="stat-value" style="color: {'green' if stats['total_change'] > 0 else 'red'}">
                    {stats['total_change']:+.2f}%
                </div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Станд. отклонение</div>
                <div class="stat-value">{stats['std_deviation']:.4f}</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Период</div>
                <div class="stat-value">
                    {len(records)} дней
                </div>
            </div>
        </div>

        <div class="chart-container">
            <div class="chart-title">📈 Визуализация данных</div>
            <img src="data:image/png;base64,{image_base64}" alt="График курса USD/RUB">
        </div>

        <div class="chart-container">
            <div class="chart-title">📋 Последние 10 записей</div>
            <table style="width: 100%; border-collapse: collapse; margin-top: 20px;">
                <thead>
                    <tr style="background-color: #667eea; color: white;">
                        <th style="padding: 12px; text-align: left;">Дата</th>
                        <th style="padding: 12px; text-align: left;">Курс</th>
                        <th style="padding: 12px; text-align: left;">Изменение</th>
                        <th style="padding: 12px; text-align: left;">Прогноз</th>
                    </tr>
                </thead>
                <tbody>
    """

    # Добавляем последние 10 записей в таблицу
    last_records = records[-10:] if len(records) >= 10 else records
    for i, record in enumerate(reversed(last_records)):
        if i < len(last_records) - 1:
            prev_rate = last_records[-(i + 2)].rate if i < len(last_records) - 1 else None
            change = ((record.rate - prev_rate) / prev_rate * 100) if prev_rate else 0
            change_str = f"{change:+.2f}%" if prev_rate else "N/A"
            change_color = "green" if change > 0 else "red" if change < 0 else "gray"
        else:
            change_str = "N/A"
            change_color = "gray"

        prediction_icon = "📈" if record.prediction == "UP" else "📉" if record.prediction == "DOWN" else "➡️"

        html_content += f"""
                    <tr style="border-bottom: 1px solid #eee; background: {'#f9f9f9' if i % 2 == 0 else 'white'};">
                        <td style="padding: 10px;">{record.date.strftime('%Y-%m-%d %H:%M')}</td>
                        <td style="padding: 10px; font-weight: bold;">{record.rate:.4f} ₽</td>
                        <td style="padding: 10px; color: {change_color};">{change_str}</td>
                        <td style="padding: 10px;">{prediction_icon} {record.prediction or 'N/A'}</td>
                    </tr>
        """

    html_content += """
                </tbody>
            </table>
        </div>

        <div class="navigation">
            <a href="/" class="btn">🏠 На главную</a>
            <a href="/history" class="btn">📅 Вся история</a>
            <a href="/predict" class="btn">🔮 Предсказание</a>
            <a href="/docs" class="btn">📖 Документация</a>
        </div>
    </body>
    </html>
    """

    return HTMLResponse(content=html_content)
