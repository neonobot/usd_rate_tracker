import time
from datetime import datetime

import numpy as np
from fastapi import FastAPI, Depends, Request, Query
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.database import get_db, engine
from app.func import (
    get_current_usd_rate,
    predict_rate_change,
    get_prediction_icon,
    format_change,
    calculate_statistics,
    generate_html_response
)
from app.logger_service import RequestLogger
from app.tables import USDRate, Base, RequestLog

# Создание таблицы логов в БД (если ее нет)
Base.metadata.create_all(bind=engine, tables=[
    RequestLog.__table__
])

app = FastAPI(
    title="USD Tracker API",
    description="API для отслеживания курса USD/RUB с логированием",
    version="2.0"
)


# ========== MIDDLEWARE ДЛЯ ЛОГИРОВАНИЯ ==========
@app.middleware("http")
async def log_requests_middleware(request: Request, call_next):
    start_time = time.time()

    # Проверяем Accept header перед обработкой
    wants_json = "application/json" in request.headers.get("accept", "").lower()

    try:
        response = await call_next(request)
        # Логируем ВСЕ запросы, но для HTML - только метаданные
        db = next(get_db())
        RequestLogger.log_request(
            db=db,
            request=request,
            endpoint=request.url.path,
            start_time=datetime.fromtimestamp(start_time),
            status_code=response.status_code
        )

        return response

    except Exception as e:

        try:
            db = next(get_db())
            RequestLogger.log_request(
                db=db,
                request=request,
                endpoint=request.url.path,
                start_time=datetime.fromtimestamp(start_time),
                status_code=500,
                error=str(e)
            )
        except Exception as log_error:
            print(f"Ошибка логирования исключения: {log_error}")

        raise


# ========== ГЛАВНАЯ СТРАНИЦА ==========
@app.get("/", response_class=HTMLResponse)
def root():
    """Главная страница"""
    content = """
    <div class="text-center mb-8">
        <h2 class="text-3xl font-bold text-gray-800 mb-4">Добро пожаловать в USD Tracker!</h2>
        <p class="text-gray-600 mb-6">Отслеживайте курс USD к RUB в реальном времени с прогнозированием изменений</p>
    </div>

    <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 mb-8">
        <div class="bg-white rounded-xl shadow-md p-6 card-hover">
            <div class="text-blue-500 text-3xl mb-4">
                <i class="fas fa-chart-line"></i>
            </div>
            <h3 class="text-xl font-bold text-gray-800 mb-2">Текущий курс</h3>
            <p class="text-gray-600 mb-4">Получите актуальный курс USD с сайта ЦБ РФ</p>
            <a href="/now" class="inline-block bg-blue-500 text-white px-4 py-2 rounded-lg hover:bg-blue-600 transition">
                <i class="fas fa-arrow-right mr-2"></i> Перейти
            </a>
        </div>

        <div class="bg-white rounded-xl shadow-md p-6 card-hover">
            <div class="text-green-500 text-3xl mb-4">
                <i class="fas fa-sync-alt"></i>
            </div>
            <h3 class="text-xl font-bold text-gray-800 mb-2">Обновить курс</h3>
            <p class="text-gray-600 mb-4">Загрузите и сохраните текущий курс в базу данных</p>
            <a href="/update" class="inline-block bg-green-500 text-white px-4 py-2 rounded-lg hover:bg-green-600 transition">
                <i class="fas fa-download mr-2"></i> Обновить
            </a>
        </div>

        <div class="bg-white rounded-xl shadow-md p-6 card-hover">
            <div class="text-purple-500 text-3xl mb-4">
                <i class="fas fa-crystal-ball"></i>
            </div>
            <h3 class="text-xl font-bold text-gray-800 mb-2">Прогноз</h3>
            <p class="text-gray-600 mb-4">Предскажите следующее изменение курса на основе истории</p>
            <a href="/predict" class="inline-block bg-purple-500 text-white px-4 py-2 rounded-lg hover:bg-purple-600 transition">
                <i class="fas fa-magic mr-2"></i> Предсказать
            </a>
        </div>

        <div class="bg-white rounded-xl shadow-md p-6 card-hover">
            <div class="text-orange-500 text-3xl mb-4">
                <i class="fas fa-history"></i>
            </div>
            <h3 class="text-xl font-bold text-gray-800 mb-2">История</h3>
            <p class="text-gray-600 mb-4">Просмотрите историю сохраненных курсов</p>
            <a href="/history" class="inline-block bg-orange-500 text-white px-4 py-2 rounded-lg hover:bg-orange-600 transition">
                <i class="fas fa-list mr-2"></i> Посмотреть
            </a>
        </div>

        <div class="bg-white rounded-xl shadow-md p-6 card-hover">
            <div class="text-red-500 text-3xl mb-4">
                <i class="fas fa-chart-bar"></i>
            </div>
            <h3 class="text-xl font-bold text-gray-800 mb-2">Статистика</h3>
            <p class="text-gray-600 mb-4">Детальная статистика и графики по курсам</p>
            <a href="/stats" class="inline-block bg-red-500 text-white px-4 py-2 rounded-lg hover:bg-red-600 transition">
                <i class="fas fa-chart-pie mr-2"></i> Анализ
            </a>
        </div>

        <div class="bg-white rounded-xl shadow-md p-6 card-hover">
            <div class="text-gray-500 text-3xl mb-4">
                <i class="fas fa-clipboard-list"></i>
            </div>
            <h3 class="text-xl font-bold text-gray-800 mb-2">Логи</h3>
            <p class="text-gray-600 mb-4">Просмотр логов всех запросов к API</p>
            <a href="/logs" class="inline-block bg-gray-500 text-white px-4 py-2 rounded-lg hover:bg-gray-600 transition">
                <i class="fas fa-file-alt mr-2"></i> Открыть
            </a>
        </div>
    </div>

    <div class="bg-white rounded-xl shadow-lg p-6">
        <h3 class="text-2xl font-bold text-gray-800 mb-4">📈 Быстрый старт</h3>
        <ol class="list-decimal list-inside space-y-3 text-gray-700">
            <li>Нажмите <a href="/update" class="text-blue-500 font-medium">"Обновить курс"</a> чтобы загрузить текущий курс</li>
            <li>Перейдите в <a href="/last" class="text-blue-500 font-medium">"Последний курс"</a> для просмотра результата</li>
            <li>Используйте <a href="/predict" class="text-blue-500 font-medium">"Прогноз"</a> для предсказания изменения</li>
            <li>Анализируйте данные в <a href="/stats" class="text-blue-500 font-medium">"Статистике"</a></li>
        </ol>
    </div>
    """

    html = generate_html_response("home", content=content)
    return HTMLResponse(content=html)


# ========== ТЕКУЩИЙ КУРС ==========
@app.get("/now", response_class=HTMLResponse)
def get_current_rate_page():
    """Страница текущего курса"""
    try:
        rate = get_current_usd_rate()

        content = f"""
        <div class="max-w-4xl mx-auto">
            <div class="text-center mb-8">
                <h2 class="text-3xl font-bold text-gray-800 mb-4">📈 Текущий курс USD/RUB</h2>
                <p class="text-gray-600">Актуальный курс с сайта Центрального банка РФ</p>
            </div>

            <div class="bg-white rounded-xl shadow-lg p-8 mb-8">
                <div class="text-center">
                    <div class="text-6xl font-bold text-blue-500 mb-4">
                        {rate:.2f} ₽
                    </div>
                    <p class="text-gray-600 mb-6">1 USD = {rate:.4f} RUB</p>

                    <div class="inline-flex items-center bg-blue-100 text-blue-800 px-4 py-2 rounded-full">
                        <i class="fas fa-clock mr-2"></i>
                        {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
                    </div>
                </div>
            </div>

            <div class="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
                <div class="bg-white rounded-xl shadow-md p-6">
                    <h3 class="text-xl font-bold text-gray-800 mb-4">💡 Что делать дальше?</h3>
                    <ul class="space-y-3 text-gray-700">
                        <li class="flex items-center">
                            <i class="fas fa-save text-green-500 mr-3"></i>
                            <span>Сохраните курс в базу данных</span>
                        </li>
                        <li class="flex items-center">
                            <i class="fas fa-chart-line text-blue-500 mr-3"></i>
                            <span>Просмотрите историю курсов</span>
                        </li>
                        <li class="flex items-center">
                            <i class="fas fa-crystal-ball text-purple-500 mr-3"></i>
                            <span>Получите прогноз изменения</span>
                        </li>
                    </ul>
                </div>

                <div class="bg-white rounded-xl shadow-md p-6">
                    <h3 class="text-xl font-bold text-gray-800 mb-4">⚡ Быстрые действия</h3>
                    <div class="space-y-3">
                        <a href="/update" class="block w-full bg-green-500 text-white text-center py-3 rounded-lg hover:bg-green-600 transition">
                            <i class="fas fa-save mr-2"></i> Сохранить этот курс
                        </a>
                        <a href="/history" class="block w-full bg-blue-500 text-white text-center py-3 rounded-lg hover:bg-blue-600 transition">
                            <i class="fas fa-history mr-2"></i> Смотреть историю
                        </a>
                    </div>
                </div>
            </div>
        </div>
        """

        html = generate_html_response("custom", content=content)
        return HTMLResponse(content=html)

    except Exception as e:
        error_html = generate_html_response(
            "error",
            content=f"Не удалось получить курс: {str(e)}"
        )
        return HTMLResponse(content=error_html, status_code=500)


# ========== ОБНОВИТЬ И СОХРАНИТЬ КУРС ==========
@app.get("/update", response_class=HTMLResponse)
def update_and_save_rate_page(db: Session = Depends(get_db)):
    """Страница обновления курса"""
    try:
        # Получаем текущий курс
        current_rate = get_current_usd_rate()
        print(current_rate)

        # Делаем предсказание
        prediction, previous_rate = predict_rate_change(current_rate, db)

        # Сохраняем в БД
        new_rate = USDRate(
            rate=current_rate,
            prediction=prediction,
            previous_rate=previous_rate
        )
        print(f'new rate - {new_rate}')
        db.add(new_rate)
        db.commit()

        # Получаем иконку и стили для предсказания
        icon, text_color, bg_color, border_color = get_prediction_icon(prediction)

        # Рассчитываем изменение
        change = None
        change_percent = None
        if previous_rate:
            change = current_rate - previous_rate
            change_percent = (change / previous_rate) * 100

        change_formatted, change_color = format_change(change)
        change_percent_formatted, change_percent_color = format_change(change_percent, True)
        print(get_prediction_description(prediction))

        predict = get_prediction_description(prediction)
        content = f"""
        <div class="max-w-4xl mx-auto">
            <div class="text-center mb-8">
                <h2 class="text-3xl font-bold text-gray-800 mb-4">✅ Курс успешно сохранен!</h2>
                <p class="text-gray-600">Данные сохранены в базу данных</p>
            </div>

            <div class="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
                <!-- Текущий курс -->
                <div class="bg-white rounded-xl shadow-lg p-6">
                    <h3 class="text-xl font-bold text-gray-800 mb-4">📊 Текущий курс</h3>
                    <div class="text-center py-6">
                        <div class="text-5xl font-bold text-blue-500 mb-2">
                            {current_rate:.4f} ₽
                        </div>
                        <p class="text-gray-600">1 USD = {current_rate:.4f} RUB</p>
                    </div>
                </div>

                <!-- Предсказание -->
                <div class="bg-white rounded-xl shadow-lg p-6">
                    <h3 class="text-xl font-bold text-gray-800 mb-4">🔮 Прогноз</h3>
                    <div class="text-center py-6">
                        <div class="text-4xl {text_color} mb-2">
                            {icon}
                        </div>
                        <div class="text-2xl font-bold {text_color} mb-2">
                            {prediction}
                        </div>
                        <div class="{bg_color} {border_color} border rounded-lg p-3 inline-block">
                            <i class="fas fa-info-circle mr-2"></i>
                            {predict}
                        </div>
                    </div>
                </div>
            </div>

            <!-- Изменения -->
            <div class="bg-white rounded-xl shadow-lg p-6 mb-8">
                <h3 class="text-xl font-bold text-gray-800 mb-6">📈 Изменения курса</h3>
                <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
                    <div class="text-center">
                        <div class="text-gray-600 mb-2">Предыдущий курс</div>
                        <div class="text-2xl font-bold">
                            {previous_rate:.4f} ₽
                        </div>
                    </div>

                    <div class="text-center">
                        <div class="text-gray-600 mb-2">Изменение</div>
                        <div class="text-2xl font-bold {change_color}">
                            {change_formatted}
                        </div>
                    </div>

                    <div class="text-center">
                        <div class="text-gray-600 mb-2">Изменение %</div>
                        <div class="text-2xl font-bold {change_percent_color}">
                            {change_percent_formatted}
                        </div>
                    </div>
                </div>
            </div>

            <!-- Действия -->
            <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
                <a href="/last" class="bg-blue-500 text-white text-center py-3 rounded-lg hover:bg-blue-600 transition">
                    <i class="fas fa-eye mr-2"></i> Просмотреть
                </a>
                <a href="/predict" class="bg-purple-500 text-white text-center py-3 rounded-lg hover:bg-purple-600 transition">
                    <i class="fas fa-crystal-ball mr-2"></i> Новый прогноз
                </a>
                <a href="/stats" class="bg-green-500 text-white text-center py-3 rounded-lg hover:bg-green-600 transition">
                    <i class="fas fa-chart-bar mr-2"></i> Статистика
                </a>
            </div>
        </div>
        """

        html = generate_html_response("custom", content=content)
        return HTMLResponse(content=html)

    except Exception as e:
        db.rollback()
        error_html = generate_html_response(
            "error",
            content=f"Не удалось сохранить курс: {str(e)}"
        )
        return HTMLResponse(content=error_html, status_code=500)


# ========== ПОСЛЕДНИЙ КУРС ==========
@app.get("/last", response_class=HTMLResponse)
def get_last_saved_rate_page(db: Session = Depends(get_db)):
    """Страница последнего курса"""
    try:
        last_record = db.query(USDRate).order_by(USDRate.date.desc()).first()

        if not last_record:
            error_html = generate_html_response(
                "error",
                content="В базе данных нет сохраненных курсов. Используйте /update для получения первого курса."
            )
            return HTMLResponse(content=error_html, status_code=404)

        # Получаем предпоследнюю запись
        prev_record = db.query(USDRate) \
            .filter(USDRate.id != last_record.id) \
            .order_by(USDRate.date.desc()) \
            .first()

        # Получаем иконку предсказания
        icon, text_color, bg_color, border_color = get_prediction_icon(last_record.prediction or "SAME")

        # Рассчитываем изменение
        change = None
        change_percent = None
        if prev_record:
            change = last_record.rate - prev_record.rate
            change_percent = (change / prev_record.rate) * 100

        change_formatted, change_color = format_change(change)
        change_percent_formatted, change_percent_color = format_change(change_percent, True)

        content = f"""
        <div class="max-w-4xl mx-auto">
            <div class="text-center mb-8">
                <h2 class="text-3xl font-bold text-gray-800 mb-4">💾 Последний сохраненный курс</h2>
                <p class="text-gray-600">Курс сохранен в базе данных</p>
            </div>

            <div class="bg-white rounded-xl shadow-lg p-8 mb-8">
                <div class="grid grid-cols-1 md:grid-cols-2 gap-8">
                    <!-- Основная информация -->
                    <div>
                        <h3 class="text-xl font-bold text-gray-800 mb-4">📊 Информация о курсе</h3>
                        <div class="space-y-4">
                            <div>
                                <div class="text-gray-600">Курс USD/RUB</div>
                                <div class="text-3xl font-bold text-blue-500">
                                    {last_record.rate:.4f} ₽
                                </div>
                            </div>

                            <div>
                                <div class="text-gray-600">Дата сохранения</div>
                                <div class="text-xl font-semibold">
                                    {last_record.date.strftime("%Y-%m-%d %H:%M:%S")}
                                </div>
                            </div>

                            <div>
                                <div class="text-gray-600">Прогноз</div>
                                <div class="flex items-center">
                                    <span class="text-2xl {text_color} mr-2">{icon}</span>
                                    <span class="text-xl font-bold {text_color}">{last_record.prediction or "N/A"}</span>
                                </div>
                            </div>
                        </div>
                    </div>

                    <!-- Изменения -->
                    <div>
                        <h3 class="text-xl font-bold text-gray-800 mb-4">📈 Сравнение</h3>
                        <div class="space-y-4">
                            <div>
                                <div class="text-gray-600">Предыдущий курс</div>
                                <div class="text-xl font-semibold">
                                    {prev_record.rate:.4f} ₽
                                </div>
                            </div>

                            <div>
                                <div class="text-gray-600">Изменение курса</div>
                                <div class="text-2xl font-bold {change_color}">
                                    {change_formatted}
                                </div>
                            </div>

                            <div>
                                <div class="text-gray-600">Изменение в %</div>
                                <div class="text-2xl font-bold {change_percent_color}">
                                    {change_percent_formatted}
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Действия -->
            <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
                <a href="/update" class="bg-green-500 text-white text-center py-3 rounded-lg hover:bg-green-600 transition">
                    <i class="fas fa-sync-alt mr-2"></i> Обновить курс
                </a>
                <a href="/history" class="bg-blue-500 text-white text-center py-3 rounded-lg hover:bg-blue-600 transition">
                    <i class="fas fa-history mr-2"></i> Вся история
                </a>
                <a href="/predict" class="bg-purple-500 text-white text-center py-3 rounded-lg hover:bg-purple-600 transition">
                    <i class="fas fa-crystal-ball mr-2"></i> Прогноз
                </a>
            </div>
        </div>
        """

        html = generate_html_response("custom", content=content)
        return HTMLResponse(content=html)

    except Exception as e:
        error_html = generate_html_response(
            "error",
            content=f"Не удалось получить последний курс: {str(e)}"
        )
        return HTMLResponse(content=error_html, status_code=500)


# ========== ИСТОРИЯ КУРСОВ ==========
@app.get("/history", response_class=HTMLResponse)
def get_rate_history_page(
        limit: int = Query(20, ge=1, le=100),
        db: Session = Depends(get_db)
):
    """Страница истории курсов"""
    try:
        records = db.query(USDRate) \
            .order_by(USDRate.date.desc()) \
            .limit(limit) \
            .all()

        if not records:
            error_html = generate_html_response(
                "error",
                content="В базе данных нет сохраненных курсов."
            )
            return HTMLResponse(content=error_html, status_code=404)

        # Подготавливаем данные для таблицы
        table_rows = ""
        for i, record in enumerate(records):
            # Находим предыдущий курс для расчета изменения
            if i < len(records) - 1:
                prev_record = records[i + 1]
                change = record.rate - prev_record.rate
                change_percent = (change / prev_record.rate) * 100 if prev_record.rate else 0
            else:
                change = None
                change_percent = None

            # Форматируем изменение
            change_formatted, change_color = format_change(change)
            change_percent_formatted, change_percent_color = format_change(change_percent, True)

            # Получаем иконку предсказания
            icon, text_color, _, _ = get_prediction_icon(record.prediction or "SAME")

            # Цвет строки
            row_color = "bg-white" if i % 2 == 0 else "bg-gray-50"

            table_rows += f"""
            <tr class="{row_color} hover:bg-gray-100 transition">
                <td class="py-3 px-4 border-b">
                    {record.date.strftime("%Y-%m-%d %H:%M:%S")}
                </td>
                <td class="py-3 px-4 border-b font-bold">
                    {record.rate:.4f} ₽
                </td>
                <td class="py-3 px-4 border-b">
                    <span class="{change_color} font-medium">{change_formatted}</span>
                </td>
                <td class="py-3 px-4 border-b">
                    <span class="{change_percent_color} font-medium">{change_percent_formatted}</span>
                </td>
                <td class="py-3 px-4 border-b">
                    <span class="{text_color}">
                        {icon} {record.prediction or "N/A"}
                    </span>
                </td>
            </tr>
            """

        content = f"""
        <div class="max-w-6xl mx-auto">
            <div class="text-center mb-8">
                <h2 class="text-3xl font-bold text-gray-800 mb-4">📊 История курсов USD/RUB</h2>
                <p class="text-gray-600 mb-2">Показано последних {len(records)} записей</p>
                <div class="inline-flex items-center bg-blue-100 text-blue-800 px-4 py-2 rounded-full">
                    <i class="fas fa-info-circle mr-2"></i>
                    Всего записей в базе: {db.query(USDRate).count()}
                </div>
            </div>

            <!-- Таблица -->
            <div class="bg-white rounded-xl shadow-lg overflow-hidden mb-8">
                <div class="overflow-x-auto">
                    <table class="w-full">
                        <thead class="bg-gray-800 text-white">
                            <tr>
                                <th class="py-3 px-4 text-left">Дата и время</th>
                                <th class="py-3 px-4 text-left">Курс USD/RUB</th>
                                <th class="py-3 px-4 text-left">Изменение</th>
                                <th class="py-3 px-4 text-left">Изменение %</th>
                                <th class="py-3 px-4 text-left">Прогноз</th>
                            </tr>
                        </thead>
                        <tbody>
                            {table_rows}
                        </tbody>
                    </table>
                </div>
            </div>

            <!-- Фильтры и действия -->
            <div class="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
                <div class="bg-white rounded-xl shadow-md p-6">
                    <h3 class="text-xl font-bold text-gray-800 mb-4">🔍 Фильтры</h3>
                    <form method="get" class="space-y-4">
                        <div>
                            <label class="block text-gray-700 mb-2">Количество записей</label>
                            <select name="limit" class="w-full p-2 border rounded-lg">
                                <option value="10" {'selected' if limit == 10 else ''}>10</option>
                                <option value="20" {'selected' if limit == 20 else ''}>20</option>
                                <option value="50" {'selected' if limit == 50 else ''}>50</option>
                                <option value="100" {'selected' if limit == 100 else ''}>100</option>
                            </select>
                        </div>
                        <button type="submit" class="w-full bg-blue-500 text-white py-2 rounded-lg hover:bg-blue-600 transition">
                            <i class="fas fa-filter mr-2"></i> Применить фильтр
                        </button>
                    </form>
                </div>

                <div class="bg-white rounded-xl shadow-md p-6">
                    <h3 class="text-xl font-bold text-gray-800 mb-4">⚡ Быстрые действия</h3>
                    <div class="space-y-3">
                        <a href="/update" class="block w-full bg-green-500 text-white text-center py-3 rounded-lg hover:bg-green-600 transition">
                            <i class="fas fa-plus-circle mr-2"></i> Добавить новый курс
                        </a>
                        <a href="/stats" class="block w-full bg-purple-500 text-white text-center py-3 rounded-lg hover:bg-purple-600 transition">
                            <i class="fas fa-chart-bar mr-2"></i> Подробная статистика
                        </a>
                    </div>
                </div>
            </div>
        </div>
        """

        html = generate_html_response("custom", content=content)
        return HTMLResponse(content=html)

    except Exception as e:
        error_html = generate_html_response(
            "error",
            content=f"Не удалось получить историю курсов: {str(e)}"
        )
        return HTMLResponse(content=error_html, status_code=500)


# ========== ПРЕДСКАЗАНИЕ ==========
@app.get("/predict", response_class=HTMLResponse)
def predict_future_rate_page(db: Session = Depends(get_db)):
    """Страница предсказания"""
    try:
        # Получаем последние записи для анализа
        records = db.query(USDRate) \
            .order_by(USDRate.date.desc()) \
            .limit(10) \
            .all()

        if len(records) < 2:
            error_html = generate_html_response(
                "error",
                content="Для предсказания нужно минимум 2 записи в базе. Используйте /update несколько раз."
            )
            return HTMLResponse(content=error_html, status_code=400)

        # Анализируем данные
        rates = [r.rate for r in records[::-1]]  # В хронологическом порядке

        # Рассчитываем изменения
        changes = []
        for i in range(1, len(rates)):
            change_percent = ((rates[i] - rates[i - 1]) / rates[i - 1]) * 100
            changes.append(change_percent)

        avg_change = sum(changes) / len(changes) if changes else 0

        # Определяем предсказание
        if avg_change > 0.1:
            prediction = "UP"
            confidence = min(0.95, avg_change / 10)
            reason = f"Средний рост за период: {avg_change:.2f}%"
            icon, text_color, bg_color, border_color = get_prediction_icon("UP")
        elif avg_change < -0.1:
            prediction = "DOWN"
            confidence = min(0.95, abs(avg_change) / 10)
            reason = f"Среднее падение за период: {avg_change:.2f}%"
            icon, text_color, bg_color, border_color = get_prediction_icon("DOWN")
        else:
            prediction = "STABLE"
            confidence = 0.7
            reason = "Колебания в пределах нормы (±0.1%)"
            icon, text_color, bg_color, border_color = get_prediction_icon("SAME")

        # Рассчитываем дополнительные метрики
        volatility = np.std(changes) if len(changes) > 1 else 0
        min_change = min(changes) if changes else 0
        max_change = max(changes) if changes else 0

        content = f"""
        <div class="max-w-4xl mx-auto">
            <div class="text-center mb-8">
                <h2 class="text-3xl font-bold text-gray-800 mb-4">🔮 Прогноз курса USD/RUB</h2>
                <p class="text-gray-600">Анализ на основе последних {len(records)} записей</p>
            </div>

            <!-- Результат предсказания -->
            <div class="bg-white rounded-xl shadow-lg p-8 mb-8">
                <div class="text-center mb-8">
                    <div class="text-6xl {text_color} mb-4">
                        {icon}
                    </div>
                    <div class="text-4xl font-bold {text_color} mb-2">
                        {prediction}
                    </div>
                    <div class="text-gray-600 mb-6">{reason}</div>

                    <!-- Уверенность -->
                    <div class="inline-block {bg_color} {border_color} border rounded-full px-6 py-3">
                        <div class="flex items-center">
                            <i class="fas fa-bullseye mr-2"></i>
                            <span class="font-bold">Уверенность: {confidence * 100:.0f}%</span>
                        </div>
                    </div>
                </div>

                <!-- Текущий курс -->
                <div class="text-center border-t pt-6">
                    <div class="text-gray-600 mb-2">Текущий курс</div>
                    <div class="text-3xl font-bold text-blue-500">
                        {rates[-1]:.4f} ₽
                    </div>
                </div>
            </div>

            <!-- Анализ данных -->
            <div class="bg-white rounded-xl shadow-lg p-6 mb-8">
                <h3 class="text-xl font-bold text-gray-800 mb-6">📊 Анализ данных</h3>
                <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
                    <div class="text-center p-4 bg-blue-50 rounded-lg">
                        <div class="text-gray-600 mb-1">Среднее изменение</div>
                        <div class="text-2xl font-bold {'text-green-500' if avg_change > 0 else 'text-red-500' if avg_change < 0 else 'text-blue-500'}">
                            {avg_change:+.2f}%
                        </div>
                    </div>

                    <div class="text-center p-4 bg-purple-50 rounded-lg">
                        <div class="text-gray-600 mb-1">Волатильность</div>
                        <div class="text-2xl font-bold text-purple-500">
                            {volatility:.2f}%
                        </div>
                    </div>

                    <div class="text-center p-4 bg-green-50 rounded-lg">
                        <div class="text-gray-600 mb-1">Макс. рост</div>
                        <div class="text-2xl font-bold text-green-500">
                            {max_change:+.2f}%
                        </div>
                    </div>

                    <div class="text-center p-4 bg-red-50 rounded-lg">
                        <div class="text-gray-600 mb-1">Макс. падение</div>
                        <div class="text-2xl font-bold text-red-500">
                            {min_change:+.2f}%
                        </div>
                    </div>
                </div>
            </div>

            <!-- Действия -->
            <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                <a href="/update" class="bg-green-500 text-white text-center py-3 rounded-lg hover:bg-green-600 transition">
                    <i class="fas fa-sync-alt mr-2"></i> Обновить данные
                </a>
                <a href="/stats" class="bg-blue-500 text-white text-center py-3 rounded-lg hover:bg-blue-600 transition">
                    <i class="fas fa-chart-bar mr-2"></i> Подробный анализ
                </a>
            </div>
        </div>
        """

        html = generate_html_response("custom", content=content)
        return HTMLResponse(content=html)

    except Exception as e:
        error_html = generate_html_response(
            "error",
            content=f"Не удалось сделать предсказание: {str(e)}"
        )
        return HTMLResponse(content=error_html, status_code=500)


# ========== СТАТИСТИКА ==========
@app.get("/stats", response_class=HTMLResponse)
def get_statistics_page(db: Session = Depends(get_db)):
    """Страница статистики"""
    try:
        records = db.query(USDRate).order_by(USDRate.date.asc()).all()

        if len(records) < 2:
            error_html = generate_html_response(
                "error",
                content="Для статистики нужно минимум 2 записи. Используйте /update несколько раз."
            )
            return HTMLResponse(content=error_html, status_code=400)

        # Рассчитываем статистику
        stats, chart_image = calculate_statistics(records)

        if not stats:
            error_html = generate_html_response(
                "error",
                content="Не удалось рассчитать статистику."
            )
            return HTMLResponse(content=error_html, status_code=500)

        # Форматируем даты
        first_date = stats['first_record'].strftime("%Y-%m-%d %H:%M") if stats['first_record'] else "N/A"
        last_date = stats['last_record'].strftime("%Y-%m-%d %H:%M") if stats['last_record'] else "N/A"

        # Цвет для общего изменения
        total_change_color = "text-green-500" if stats['total_change'] > 0 else "text-red-500" if stats[
                                                                                                      'total_change'] < 0 else "text-blue-500"
        total_change_icon = "📈" if stats['total_change'] > 0 else "📉" if stats['total_change'] < 0 else "➡️"

        # Получаем последние записи для таблицы
        recent_records = records[-10:] if len(records) >= 10 else records

        # Генерируем строки таблицы
        table_rows = ""
        for i, record in enumerate(reversed(recent_records)):
            if i < len(recent_records) - 1:
                prev_rate = recent_records[-(i + 2)].rate
                change = record.rate - prev_rate
                change_percent = (change / prev_rate) * 100
            else:
                change = None
                change_percent = None

            change_formatted, change_color = format_change(change)
            change_percent_formatted, change_percent_color = format_change(change_percent, True)
            icon, text_color, _, _ = get_prediction_icon(record.prediction or "SAME")

            table_rows += f"""
            <tr class="{'bg-white' if i % 2 == 0 else 'bg-gray-50'} hover:bg-gray-100">
                <td class="py-2 px-4 border-b">{record.date.strftime("%Y-%m-%d %H:%M")}</td>
                <td class="py-2 px-4 border-b font-bold">{record.rate:.4f} ₽</td>
                <td class="py-2 px-4 border-b"><span class="{change_color}">{change_formatted}</span></td>
                <td class="py-2 px-4 border-b"><span class="{change_percent_color}">{change_percent_formatted}</span></td>
                <td class="py-2 px-4 border-b"><span class="{text_color}">{icon} {record.prediction or 'N/A'}</span></td>
            </tr>
            """

        content = f"""
        <div class="max-w-6xl mx-auto">
            <div class="text-center mb-8">
                <h2 class="text-3xl font-bold text-gray-800 mb-4">📊 Статистика курса USD/RUB</h2>
                <p class="text-gray-600">Детальный анализ исторических данных</p>
            </div>

            <!-- Основная статистика -->
            <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
                <div class="bg-white rounded-xl shadow-md p-6 text-center">
                    <div class="text-gray-600 mb-2">Всего записей</div>
                    <div class="text-3xl font-bold text-blue-500">{stats['total_records']}</div>
                </div>

                <div class="bg-white rounded-xl shadow-md p-6 text-center">
                    <div class="text-gray-600 mb-2">Текущий курс</div>
                    <div class="text-3xl font-bold text-green-500">{stats['current_rate']:.2f} ₽</div>
                </div>

                <div class="bg-white rounded-xl shadow-md p-6 text-center">
                    <div class="text-gray-600 mb-2">Средний курс</div>
                    <div class="text-3xl font-bold text-purple-500">{stats['average_rate']:.2f} ₽</div>
                </div>

                <div class="bg-white rounded-xl shadow-md p-6 text-center">
                    <div class="text-gray-600 mb-2">Общее изменение</div>
                    <div class="text-3xl font-bold {total_change_color}">
                        {total_change_icon} {stats['total_change']:+.2f}%
                    </div>
                </div>
            </div>

            <!-- График -->
            {f'''
            <div class="bg-white rounded-xl shadow-lg p-6 mb-8">
                <h3 class="text-xl font-bold text-gray-800 mb-6">📊 Визуализация данных</h3>
                <img src="data:image/png;base64,{chart_image}" alt="График статистики" class="w-full rounded-lg">
            </div>
            ''' if chart_image else ''}

            <!-- Последние записи -->
            <div class="bg-white rounded-xl shadow-lg p-6 mb-8">
                <h3 class="text-xl font-bold text-gray-800 mb-6">📋 Последние 10 записей</h3>
                <div class="overflow-x-auto">
                    <table class="w-full">
                        <thead class="bg-gray-800 text-white">
                            <tr>
                                <th class="py-2 px-4 text-left">Дата</th>
                                <th class="py-2 px-4 text-left">Курс</th>
                                <th class="py-2 px-4 text-left">Изменение</th>
                                <th class="py-2 px-4 text-left">Изменение %</th>
                                <th class="py-2 px-4 text-left">Прогноз</th>
                            </tr>
                        </thead>
                        <tbody>
                            {table_rows}
                        </tbody>
                    </table>
                </div>
            </div>

            <!-- Действия -->
            <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
                <a href="/history" class="bg-blue-500 text-white text-center py-3 rounded-lg hover:bg-blue-600 transition">
                    <i class="fas fa-history mr-2"></i> Вся история
                </a>
                <a href="/predict" class="bg-purple-500 text-white text-center py-3 rounded-lg hover:bg-purple-600 transition">
                    <i class="fas fa-crystal-ball mr-2"></i> Новый прогноз
                </a>
                <a href="/update" class="bg-green-500 text-white text-center py-3 rounded-lg hover:bg-green-600 transition">
                    <i class="fas fa-plus-circle mr-2"></i> Добавить данные
                </a>
            </div>
        </div>
        """

        html = generate_html_response("custom", content=content)
        return HTMLResponse(content=html)

    except Exception as e:
        error_html = generate_html_response(
            "error",
            content=f"Не удалось рассчитать статистику: {str(e)}"
        )
        return HTMLResponse(content=error_html, status_code=500)


# ========== ЛОГИ ==========
@app.get("/logs", response_class=HTMLResponse)
def get_logs_page(
        limit: int = Query(50, ge=1, le=200),
        db: Session = Depends(get_db)
):
    """Страница логов"""
    try:
        from app.logger_service import RequestLogger

        logs = RequestLogger.get_recent_logs(db, limit)
        stats = RequestLogger.get_stats(db)

        # Подготавливаем таблицу логов
        table_rows = ""
        for i, log in enumerate(logs):
            # Цвет статуса
            if log.status_code and log.status_code >= 500:
                status_color = "bg-red-100 text-red-800"
            elif log.status_code and log.status_code >= 400:
                status_color = "bg-yellow-100 text-yellow-800"
            elif log.status_code:
                status_color = "bg-green-100 text-green-800"
            else:
                status_color = "bg-gray-100 text-gray-800"

            # Цвет строки
            row_color = "bg-white" if i % 2 == 0 else "bg-gray-50"

            table_rows += f"""
            <tr class="{row_color} hover:bg-gray-100">
                <td class="py-3 px-4 border-b">{log.request_time.strftime("%Y-%m-%d %H:%M:%S")}</td>
                <td class="py-3 px-4 border-b">
                    <span class="inline-block px-2 py-1 rounded {status_color} text-xs font-bold">
                        {log.status_code or "N/A"}
                    </span>
                </td>
                <td class="py-3 px-4 border-b">
                    <span class="inline-block px-2 py-1 rounded bg-blue-100 text-blue-800 text-xs font-bold">
                        {log.method}
                    </span>
                </td>
                <td class="py-3 px-4 border-b font-mono text-sm">{log.endpoint}</td>
                <td class="py-3 px-4 border-b">{log.client_ip or "N/A"}</td>
                <td class="py-3 px-4 border-b">
                    <span class="inline-block px-2 py-1 rounded bg-gray-100 text-gray-800 text-xs">
                        {log.processing_time_ms or 0}ms
                    </span>
                </td>
            </tr>
            """

        content = f"""
        <div class="max-w-6xl mx-auto">
            <div class="text-center mb-8">
                <h2 class="text-3xl font-bold text-gray-800 mb-4">📋 Логи запросов API</h2>
                <p class="text-gray-600">Мониторинг всех обращений к API</p>
            </div>

            <!-- Статистика -->
            <div class="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
                <div class="bg-white rounded-xl shadow-md p-6 text-center">
                    <div class="text-gray-600 mb-2">Всего запросов</div>
                    <div class="text-3xl font-bold text-blue-500">{stats.get('total_requests', 0)}</div>
                </div>

                <div class="bg-white rounded-xl shadow-md p-6 text-center">
                    <div class="text-gray-600 mb-2">Ошибочных</div>
                    <div class="text-3xl font-bold text-red-500">{stats.get('error_requests', 0)}</div>
                </div>

                <div class="bg-white rounded-xl shadow-md p-6 text-center">
                    <div class="text-gray-600 mb-2">Успешных</div>
                    <div class="text-3xl font-bold text-green-500">{stats.get('success_rate', 0):.1f}%</div>
                </div>

                <div class="bg-white rounded-xl shadow-md p-6 text-center">
                    <div class="text-gray-600 mb-2">Среднее время</div>
                    <div class="text-3xl font-bold text-purple-500">{stats.get('average_processing_time_ms', 0)}ms</div>
                </div>
            </div>

            <!-- Таблица логов -->
            <div class="bg-white rounded-xl shadow-lg overflow-hidden mb-8">
                <div class="p-6 border-b">
                    <h3 class="text-xl font-bold text-gray-800">Последние {len(logs)} записей</h3>
                </div>

                <div class="overflow-x-auto">
                    <table class="w-full">
                        <thead class="bg-gray-800 text-white">
                            <tr>
                                <th class="py-3 px-4 text-left">Время</th>
                                <th class="py-3 px-4 text-left">Статус</th>
                                <th class="py-3 px-4 text-left">Метод</th>
                                <th class="py-3 px-4 text-left">Эндпоинт</th>
                                <th class="py-3 px-4 text-left">IP</th>
                                <th class="py-3 px-4 text-left">Время</th>
                            </tr>
                        </thead>
                        <tbody>
                            {table_rows}
                        </tbody>
                    </table>
                </div>
            </div>

            <!-- Фильтры -->
            <div class="bg-white rounded-xl shadow-md p-6">
                <h3 class="text-xl font-bold text-gray-800 mb-4">🔍 Фильтры логов</h3>
                <form method="get" class="space-y-4">
                    <div>
                        <label class="block text-gray-700 mb-2">Количество записей</label>
                        <select name="limit" class="w-full p-2 border rounded-lg">
                            <option value="20" {'selected' if limit == 20 else ''}>20</option>
                            <option value="50" {'selected' if limit == 50 else ''}>50</option>
                            <option value="100" {'selected' if limit == 100 else ''}>100</option>
                            <option value="200" {'selected' if limit == 200 else ''}>200</option>
                        </select>
                    </div>
                    <button type="submit" class="w-full bg-blue-500 text-white py-2 rounded-lg hover:bg-blue-600 transition">
                        <i class="fas fa-filter mr-2"></i> Применить фильтр
                    </button>
                </form>
            </div>
        </div>
        """

        html = generate_html_response("custom", content=content)
        return HTMLResponse(content=html)

    except Exception as e:
        error_html = generate_html_response(
            "error",
            content=f"Не удалось получить логи: {str(e)}"
        )
        return HTMLResponse(content=error_html, status_code=500)


# ========== API ДОКУМЕНТАЦИЯ (для совместимости) ==========
@app.get("/api/now")
def get_current_rate_api():
    """API: Текущий курс USD"""
    rate = get_current_usd_rate()
    return {"rate": rate, "timestamp": datetime.utcnow().isoformat()}


@app.get("/api/update")
def update_rate_api(db: Session = Depends(get_db)):
    """API: Обновить и сохранить курс"""
    current_rate = get_current_usd_rate()
    prediction, previous_rate = predict_rate_change(current_rate, db)

    new_rate = USDRate(
        rate=current_rate,
        prediction=prediction,
        previous_rate=previous_rate
    )

    db.add(new_rate)
    db.commit()

    return {
        "rate": current_rate,
        "prediction": prediction,
        "previous_rate": previous_rate,
        "saved_at": datetime.utcnow().isoformat()
    }


# ========== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ==========
def get_prediction_description(prediction: str) -> str:
    """Описание предсказания"""
    descriptions = {
        "UP": "Курс вероятно вырастет",
        "DOWN": "Курс вероятно упадет",
        "SAME": "Курс останется примерно таким же",
        "FIRST": "Это первая запись в базе"
    }
    return descriptions.get(prediction, "Неизвестное предсказание")
