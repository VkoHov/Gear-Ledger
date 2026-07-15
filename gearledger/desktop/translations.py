# -*- coding: utf-8 -*-
"""
Translation system for Gear Ledger.
Supports English and Russian languages.
"""
from __future__ import annotations

# Available languages
LANGUAGES = {
    "en": "English",
    "ru": "Русский",
}

# Translation dictionary
TRANSLATIONS = {
    # ============ Main Window ============
    "settings_button": {
        "en": "⚙️ Settings",
        "ru": "⚙️ Настройки",
    },
    "ready": {
        "en": "Ready.",
        "ru": "Готово.",
    },
    # ============ Weight Input (Scale Widget) ============
    "weight_input": {
        "en": "Weight Input",
        "ru": "Ввод веса",
    },
    "scale": {
        "en": "⚖️ Scale",
        "ru": "⚖️ Весы",
    },
    "manual": {
        "en": "✏️ Manual",
        "ru": "✏️ Вручную",
    },
    "weight_kg": {
        "en": "-- kg",
        "ru": "-- кг",
    },
    "disconnected": {
        "en": "Disconnected",
        "ru": "Отключено",
    },
    "connecting": {
        "en": "Connecting...",
        "ru": "Подключение...",
    },
    "connected": {
        "en": "Connected",
        "ru": "Подключено",
    },
    "connection_lost": {
        "en": "Connection Lost",
        "ru": "Соединение потеряно",
    },
    "changing": {
        "en": "Changing...",
        "ru": "Изменение...",
    },
    "stabilizing": {
        "en": "Stabilizing...",
        "ru": "Стабилизация...",
    },
    "connect": {
        "en": "Connect",
        "ru": "Подключить",
    },
    "disconnect": {
        "en": "Disconnect",
        "ru": "Отключить",
    },
    "tare": {
        "en": "Tare",
        "ru": "Тара",
    },
    "auto_capture_note": {
        "en": "⚡ Auto-capture on stable weight",
        "ru": "⚡ Авто-захват при стабильном весе",
    },
    "enter_weight_kg": {
        "en": "Enter weight (kg)",
        "ru": "Введите вес (кг)",
    },
    "weight_display": {
        "en": "Weight: -- kg",
        "ru": "Вес: -- кг",
    },
    "set_weight": {
        "en": "Set Weight",
        "ru": "Установить вес",
    },
    "invalid_weight": {
        "en": "Invalid Weight",
        "ru": "Неверный вес",
    },
    "weight_must_be_positive": {
        "en": "Weight must be greater than 0.",
        "ru": "Вес должен быть больше 0.",
    },
    "enter_valid_number": {
        "en": "Please enter a valid number.",
        "ru": "Пожалуйста, введите корректное число.",
    },
    "scale_connection": {
        "en": "Scale Connection",
        "ru": "Подключение весов",
    },
    "configure_scale_port": {
        "en": "Please configure the scale port in Settings.",
        "ru": "Пожалуйста, настройте порт весов в Настройках.",
    },
    # ============ Item Input (Camera Widget) ============
    "item_input": {
        "en": "Item Input",
        "ru": "Ввод товара",
    },
    "camera": {
        "en": "📷 Camera",
        "ru": "📷 Камера",
    },
    "camera_preview": {
        "en": "Camera preview",
        "ru": "Превью камеры",
    },
    "opening_camera": {
        "en": "Opening camera...\nPlease wait",
        "ru": "Открытие камеры...\nПодождите",
    },
    "processing": {
        "en": "⏳ Processing...\nPlease wait",
        "ru": "⏳ Обработка...\nПодождите",
    },
    "start_camera": {
        "en": "Start camera",
        "ru": "Включить камеру",
    },
    "capture_run": {
        "en": "Capture & Run",
        "ru": "Сканировать",
    },
    "stop_cancel": {
        "en": "Stop / Cancel",
        "ru": "Стоп / Отмена",
    },
    "enter_part_code": {
        "en": "Enter Part Code Manually",
        "ru": "Введите артикул вручную",
    },
    "part_code_placeholder": {
        "en": "Enter part code (e.g., PK-5396)",
        "ru": "Введите артикул (напр., PK-5396)",
    },
    "search_add": {
        "en": "🔍 Search & Add",
        "ru": "🔍 Найти и добавить",
    },
    "out_of_stock": {
        "en": "Out of Stock",
        "ru": "Нет в наличии",
    },
    "out_of_stock_msg": {
        "en": "Cannot add {artikul}: only {total} in catalog, {added} already recorded.",
        "ru": "Невозможно добавить {artikul}: в каталоге {total} шт., уже записано {added} шт.",
    },
    "out_of_stock_detail": {
        "en": "This item cannot be added — stock limit reached.",
        "ru": "Этот товар нельзя добавить — лимит склада исчерпан.",
    },
    "in_catalog": {
        "en": "In catalog",
        "ru": "В каталоге",
    },
    "already_added": {
        "en": "Already added",
        "ru": "Уже добавлено",
    },
    "in_stock_label": {
        "en": "Available: {count} pcs",
        "ru": "Доступно: {count} шт.",
    },
    "combined_stock_label": {
        "en": "ⓘ Combined from {count} order lines ({breakdown})",
        "ru": "ⓘ Объединено из {count} строк заказа ({breakdown})",
    },
    "searching": {
        "en": "Searching...",
        "ru": "Поиск...",
    },
    "please_enter_code": {
        "en": "Please enter a part code",
        "ru": "Пожалуйста, введите артикул",
    },
    "no_frame_yet": {
        "en": "No frame yet. Try again.",
        "ru": "Нет кадра. Попробуйте снова.",
    },
    "camera_error": {
        "en": "Camera",
        "ru": "Камера",
    },
    "camera_open_failed": {
        "en": "Failed to open camera (index {index}).\n\nPlease check:\n1. Camera is connected and not in use by another application\n2. Camera index is correct (open Settings ⚙️ to change it)\n3. Camera permissions are granted\n\nError: {error}",
        "ru": "Не удалось открыть камеру (индекс {index}).\n\nПроверьте:\n1. Камера подключена и не используется другим приложением\n2. Индекс камеры правильный (откройте Настройки ⚙️ для изменения)\n3. Разрешения камеры предоставлены\n\nОшибка: {error}",
    },
    # ============ Settings Page ============
    "settings_title": {
        "en": "Gear Ledger - Settings",
        "ru": "Gear Ledger - Настройки",
    },
    "language": {
        "en": "Language",
        "ru": "Язык",
    },
    "api_settings": {
        "en": "API Settings",
        "ru": "Настройки API",
    },
    "openai_api_key": {
        "en": "OpenAI API Key:",
        "ru": "Ключ API OpenAI:",
    },
    "vision_backend": {
        "en": "Vision Backend:",
        "ru": "Движок распознавания:",
    },
    "openai_model": {
        "en": "OpenAI Model:",
        "ru": "Модель OpenAI:",
    },
    "camera_settings": {
        "en": "Camera Settings",
        "ru": "Настройки камеры",
    },
    "camera_index": {
        "en": "Camera Index:",
        "ru": "Индекс камеры:",
    },
    "resolution": {
        "en": "Resolution:",
        "ru": "Разрешение:",
    },
    "scale_settings": {
        "en": "Scale Settings",
        "ru": "Настройки весов",
    },
    "scale_port": {
        "en": "Scale Port:",
        "ru": "Порт весов:",
    },
    "baudrate": {
        "en": "Baudrate:",
        "ru": "Скорость:",
    },
    "weight_threshold": {
        "en": "Weight Threshold (kg):",
        "ru": "Порог веса (кг):",
    },
    "stable_time": {
        "en": "Stable Time (sec):",
        "ru": "Время стабилизации (сек):",
    },
    "advanced_settings": {
        "en": "Advanced",
        "ru": "Дополнительно",
    },
    "pricing": {
        "en": "Pricing",
        "ru": "Цены",
    },
    "price_per_kg": {
        "en": "Price per kg:",
        "ru": "Цена за кг:",
    },
    "interface": {
        "en": "Interface",
        "ru": "Интерфейс",
    },
    "show_logs": {
        "en": "Show Logs",
        "ru": "Показать логи",
    },
    "save_settings": {
        "en": "Save Settings",
        "ru": "Сохранить настройки",
    },
    "cancel": {
        "en": "Cancel",
        "ru": "Отмена",
    },
    "settings_saved": {
        "en": "Settings Saved",
        "ru": "Настройки сохранены",
    },
    "settings_saved_msg": {
        "en": "Settings have been saved successfully.",
        "ru": "Настройки успешно сохранены.",
    },
    # ============ Settings Widget (File Selection) ============
    "settings_group": {
        "en": "Settings",
        "ru": "Настройки",
    },
    "files": {
        "en": "Files",
        "ru": "Файлы",
    },
    "catalog_excel_lookup": {
        "en": "Catalog Excel (lookup):",
        "ru": "Каталог Excel (поиск):",
    },
    "results_excel_ledger": {
        "en": "Results Excel (ledger):",
        "ru": "Результаты Excel (журнал):",
    },
    "catalog_status_from_server": {
        "en": "Catalog from server",
        "ru": "Каталог с сервера",
    },
    "catalog_status_not_on_server": {
        "en": "No catalog on server. Please upload on server.",
        "ru": "Нет каталога на сервере. Загрузите на сервере.",
    },
    "catalog_status_not_connected": {
        "en": "Not connected to server",
        "ru": "Не подключено к серверу",
    },
    "results_status_available": {
        "en": "Results: Available from server",
        "ru": "Результаты: Доступны с сервера",
    },
    "results_status_database": {
        "en": "Results are stored in the database",
        "ru": "Результаты хранятся в базе данных",
    },
    "results_status_not_connected": {
        "en": "Results: Not connected",
        "ru": "Результаты: Не подключено",
    },
    "catalog": {
        "en": "Catalog:",
        "ru": "Каталог:",
    },
    "results": {
        "en": "Results:",
        "ru": "Результаты:",
    },
    "browse": {
        "en": "Browse…",
        "ru": "Обзор…",
    },
    "import_results": {
        "en": "Import…",
        "ru": "Импорт…",
    },
    "import_results_tooltip": {
        "en": "Import an external Excel file's rows into the database",
        "ru": "Импортировать строки из внешнего файла Excel в базу данных",
    },
    "import_results_title": {
        "en": "Import Results Excel",
        "ru": "Импорт файла результатов Excel",
    },
    "import_invalid_title": {
        "en": "Invalid File",
        "ru": "Неверный файл",
    },
    "import_invalid_msg": {
        "en": "This file doesn't match the expected format — missing column(s): {columns}",
        "ru": "Этот файл не соответствует ожидаемому формату — отсутствуют столбцы: {columns}",
    },
    "import_confirm_title": {
        "en": "Import Results",
        "ru": "Импорт результатов",
    },
    "import_confirm_msg": {
        "en": "Import this file into the database? The current data will be archived as a new version first, so nothing is lost.",
        "ru": "Импортировать этот файл в базу данных? Текущие данные будут сначала сохранены как новая версия, поэтому ничего не потеряется.",
    },
    "import_complete_title": {
        "en": "Import Complete",
        "ru": "Импорт завершён",
    },
    "import_complete_msg": {
        "en": "Imported {count} rows into the database.",
        "ru": "В базу данных импортировано строк: {count}.",
    },
    "import_failed": {
        "en": "Import Failed",
        "ru": "Ошибка импорта",
    },
    "import_failed_msg": {
        "en": "Could not import this file:\n{error}",
        "ru": "Не удалось импортировать этот файл:\n{error}",
    },
    "reset": {
        "en": "Reset",
        "ru": "Сброс",
    },
    "versions": {
        "en": "Versions",
        "ru": "Версии",
    },
    "versions_tooltip": {
        "en": "View and export previous result-file versions saved by Reset",
        "ru": "Просмотр и экспорт предыдущих версий файла результатов, сохранённых при сбросе",
    },
    "previous_versions_title": {
        "en": "Previous Versions",
        "ru": "Предыдущие версии",
    },
    "no_previous_versions": {
        "en": "No previous versions yet — they appear here after you use Reset.",
        "ru": "Пока нет предыдущих версий — они появятся здесь после сброса.",
    },
    "version_row_label": {
        "en": "{date} ({count} items)",
        "ru": "{date} ({count} поз.)",
    },
    "open_version": {
        "en": "Open",
        "ru": "Открыть",
    },
    "export_version": {
        "en": "Export",
        "ru": "Экспорт",
    },
    "restore_version": {
        "en": "Restore",
        "ru": "Восстановить",
    },
    "delete_version": {
        "en": "Delete",
        "ru": "Удалить",
    },
    "delete_version_confirm_title": {
        "en": "Delete Version",
        "ru": "Удалить версию",
    },
    "delete_version_confirm_msg": {
        "en": "Delete version {version}? This cannot be undone.",
        "ru": "Удалить версию {version}? Это действие необратимо.",
    },
    "restore_version_title": {
        "en": "Restore Version",
        "ru": "Восстановить версию",
    },
    "restore_version_confirm": {
        "en": "Make this version the active results file? The current file will be archived as a new version first, so nothing is lost.",
        "ru": "Сделать эту версию активным файлом результатов? Текущий файл будет сначала сохранён как новая версия, поэтому ничего не потеряется.",
    },
    "restore_version_confirm_server": {
        "en": "Restore this version? This changes results for everyone currently connected — the current data will be archived as a new version first, so nothing is lost.",
        "ru": "Восстановить эту версию? Это изменит результаты для всех, кто сейчас подключён — текущие данные будут сначала сохранены как новая версия, поэтому ничего не потеряется.",
    },
    "restore_complete": {
        "en": "Restore Complete",
        "ru": "Восстановление завершено",
    },
    "restore_complete_msg": {
        "en": "Restored version is now the active results file:\n{path}",
        "ru": "Восстановленная версия теперь является активным файлом результатов:\n{path}",
    },
    "restore_failed": {
        "en": "Restore Failed",
        "ru": "Ошибка восстановления",
    },
    "last_action_reset": {
        "en": "Last action: reset ({detail}) at {time}",
        "ru": "Последнее действие: сброс ({detail}) в {time}",
    },
    "last_action_restore": {
        "en": "Last action: restored from {detail} at {time}",
        "ru": "Последнее действие: восстановлено из {detail} в {time}",
    },
    "last_action_import": {
        "en": "Last action: imported from {detail} at {time}",
        "ru": "Последнее действие: импортировано из {detail} в {time}",
    },
    "restore_failed_msg": {
        "en": "Could not restore this version:\n{error}",
        "ru": "Не удалось восстановить эту версию:\n{error}",
    },
    "close": {
        "en": "Close",
        "ru": "Закрыть",
    },
    "download": {
        "en": "Download",
        "ru": "Скачать",
    },
    "weight_price": {
        "en": "Weight Price:",
        "ru": "Цена за вес:",
    },
    "select_catalog": {
        "en": "Select Catalog Excel File",
        "ru": "Выберите файл каталога Excel",
    },
    "select_results": {
        "en": "Select Results Excel File",
        "ru": "Выберите файл результатов Excel",
    },
    "generate_invoice": {
        "en": "Generate Invoice",
        "ru": "Создать накладную",
    },
    "check_completeness": {
        "en": "Check Order",
        "ru": "Проверить заказ",
    },
    "check_completeness_tooltip": {
        "en": "Compare recorded results against the catalog and show anything not fully scanned",
        "ru": "Сравнить записанные результаты с каталогом и показать то, что отсканировано не полностью",
    },
    "no_quantity_column_msg": {
        "en": "The catalog has no quantity column, so there's nothing to compare recorded results against.",
        "ru": "В каталоге нет столбца с количеством, поэтому не с чем сравнивать записанные результаты.",
    },
    "completeness_summary": {
        "en": "{complete} of {total} items fully recorded",
        "ru": "{complete} из {total} позиций полностью записано",
    },
    "completeness_all_done": {
        "en": "Everything in the catalog has been fully recorded. ✓",
        "ru": "Всё в каталоге полностью записано. ✓",
    },
    "not_started_section": {
        "en": "Not Started ({count})",
        "ru": "Не начато ({count})",
    },
    "partial_section": {
        "en": "Partial ({count})",
        "ru": "Частично ({count})",
    },
    "completeness_not_started_detail": {
        "en": "Ordered: {ordered}, Recorded: 0",
        "ru": "Заказано: {ordered}, Записано: 0",
    },
    "completeness_partial_detail": {
        "en": "Ordered: {ordered}, Recorded: {recorded}, Missing: {missing}",
        "ru": "Заказано: {ordered}, Записано: {recorded}, Не хватает: {missing}",
    },
    "over_recorded_section": {
        "en": "Over-Recorded ({count})",
        "ru": "Записано больше ({count})",
    },
    "completeness_over_recorded_detail": {
        "en": "Ordered: {ordered}, Recorded: {recorded}, Excess: {excess}",
        "ru": "Заказано: {ordered}, Записано: {recorded}, Излишек: {excess}",
    },
    "over_recorded_status": {
        "en": "Over-Recorded",
        "ru": "Записано больше",
    },
    "adjust_quantity": {
        "en": "Adjust",
        "ru": "Исправить",
    },
    "adjust_quantity_title": {
        "en": "Adjust Quantity",
        "ru": "Исправить количество",
    },
    "adjust_quantity_prompt": {
        "en": "New quantity for {artikul} — {client}:",
        "ru": "Новое количество для {artikul} — {client}:",
    },
    "adjust_quantity_failed": {
        "en": "Could not adjust this item's quantity.",
        "ru": "Не удалось изменить количество для этого элемента.",
    },
    "col_status": {
        "en": "Status",
        "ru": "Статус",
    },
    "col_client": {
        "en": "Client",
        "ru": "Клиент",
    },
    "col_artikul": {
        "en": "Artikul",
        "ru": "Артикул",
    },
    "col_ordered": {
        "en": "Ordered",
        "ru": "Заказано",
    },
    "col_recorded": {
        "en": "Recorded",
        "ru": "Записано",
    },
    "col_missing": {
        "en": "Missing",
        "ru": "Не хватает",
    },
    "col_excess": {
        "en": "Excess",
        "ru": "Излишек",
    },
    "not_started_status": {
        "en": "Not Started",
        "ru": "Не начато",
    },
    "partial_status": {
        "en": "Partial",
        "ru": "Частично",
    },
    "not_in_catalog_section": {
        "en": "Not in Catalog ({count})",
        "ru": "Нет в каталоге ({count})",
    },
    "not_in_catalog_detail": {
        "en": "Recorded: {recorded} — this code/client isn't in the catalog",
        "ru": "Записано: {recorded} — этого кода/клиента нет в каталоге",
    },
    "not_in_catalog_status": {
        "en": "Not in Catalog",
        "ru": "Нет в каталоге",
    },
    "delete_item": {
        "en": "Delete",
        "ru": "Удалить",
    },
    "delete_item_confirm_title": {
        "en": "Delete Result",
        "ru": "Удалить результат",
    },
    "delete_item_confirm_msg": {
        "en": "Delete {artikul} — {client} from results? This cannot be undone.",
        "ru": "Удалить {artikul} — {client} из результатов? Это действие необратимо.",
    },
    "delete_item_failed": {
        "en": "Could not delete this item.",
        "ru": "Не удалось удалить этот элемент.",
    },
    "delete_items_confirm_msg": {
        "en": "Delete {count} selected rows from results? This cannot be undone.",
        "ru": "Удалить {count} выбранных строк из результатов? Это действие необратимо.",
    },
    "delete_items_partial_failed": {
        "en": "Deleted {deleted} of {total} selected rows. {failed} could not be deleted.",
        "ru": "Удалено {deleted} из {total} выбранных строк. {failed} не удалось удалить.",
    },
    "choose_catalog_excel": {
        "en": "Choose Catalog Excel (lookup)",
        "ru": "Выберите каталог Excel (поиск)",
    },
    "choose_results_excel": {
        "en": "Choose Results Excel (ledger)",
        "ru": "Выберите результаты Excel (журнал)",
    },
    # ============ Results Pane ============
    "results_excel": {
        "en": "Results (Excel):",
        "ru": "Результаты (Excel):",
    },
    "refresh_server_data": {
        "en": "🔄 Refresh",
        "ru": "🔄 Обновить",
    },
    # ============ Catalog Required Dialog ============
    "catalog_required_title": {
        "en": "Gear Ledger - Catalog Required",
        "ru": "Gear Ledger - Требуется каталог",
    },
    "catalog_file_required": {
        "en": "Catalog File Required",
        "ru": "Требуется файл каталога",
    },
    "catalog_required_message": {
        "en": "Please select a Catalog Excel file to continue.\n\nThe catalog file contains the part codes and client information\nneeded for matching scanned items.",
        "ru": "Пожалуйста, выберите файл каталога Excel для продолжения.\n\nФайл каталога содержит артикулы и информацию о клиентах,\nнеобходимую для сопоставления отсканированных товаров.",
    },
    "select_catalog_file": {
        "en": "Select Catalog File",
        "ru": "Выбрать файл каталога",
    },
    # ============ Results Widget ============
    "result_summary": {
        "en": "Result summary",
        "ru": "Результат",
    },
    "ocr_results": {
        "en": "OCR Results",
        "ru": "Результаты OCR",
    },
    "best_visible": {
        "en": "Best (visible):",
        "ru": "Лучший (видимый):",
    },
    "best_normalized": {
        "en": "Best (normalized):",
        "ru": "Лучший (нормализованный):",
    },
    "excel_match": {
        "en": "Excel match:",
        "ru": "Совпадение в Excel:",
    },
    "est_gpt_cost": {
        "en": "Est. GPT cost:",
        "ru": "Прибл. стоимость GPT:",
    },
    "no_api_key": {
        "en": "— (no API key)",
        "ru": "— (нет API ключа)",
    },
    "match_result": {
        "en": "Match:",
        "ru": "Совпадение:",
    },
    "gpt_cost": {
        "en": "GPT cost:",
        "ru": "Стоимость GPT:",
    },
    "not_found": {
        "en": "not found",
        "ru": "не найдено",
    },
    "canceled": {
        "en": "canceled",
        "ru": "отменено",
    },
    "no_exact_match_fuzzy": {
        "en": "No exact match — try fuzzy?",
        "ru": "Нет точного совпадения — попробовать нечёткий поиск?",
    },
    "likely_candidates": {
        "en": "Likely candidates (from GPT/local ranking):",
        "ru": "Вероятные кандидаты (от GPT/локального ранжирования):",
    },
    "limit_fuzzy_to_shown": {
        "en": "Limit fuzzy to shown candidates",
        "ru": "Ограничить поиск показанными кандидатами",
    },
    "run_fuzzy_match": {
        "en": "Run fuzzy match",
        "ru": "Запустить нечёткий поиск",
    },
    "no_match_manual": {
        "en": "No match found — enter code manually?",
        "ru": "Совпадение не найдено — ввести код вручную?",
    },
    "enter_code_search": {
        "en": "Enter part code to search in invoice:",
        "ru": "Введите артикул для поиска в каталоге:",
    },
    "search": {
        "en": "Search",
        "ru": "Поиск",
    },
    "start_fuzzy_matching": {
        "en": "Start fuzzy matching?",
        "ru": "Запустить нечёткий поиск?",
    },
    "no_exact_match_msg": {
        "en": "No exact match found.\n\nTop candidates to try with fuzzy matching:\n{preview}\n\nStart fuzzy matching now?",
        "ru": "Точное совпадение не найдено.\n\nЛучшие кандидаты для нечёткого поиска:\n{preview}\n\nЗапустить нечёткий поиск сейчас?",
    },
    "no_fuzzy_match_found": {
        "en": "No fuzzy match found.",
        "ru": "Нечёткое совпадение не найдено.",
    },
    "fuzzy": {
        "en": "Fuzzy",
        "ru": "Нечёткий поиск",
    },
    "manual_search": {
        "en": "Manual Search",
        "ru": "Ручной поиск",
    },
    "enter_code_to_search": {
        "en": "Please enter a part code to search.",
        "ru": "Пожалуйста, введите артикул для поиска.",
    },
    "no_match_for_code": {
        "en": "No match found for the entered code.",
        "ru": "Совпадение для введённого кода не найдено.",
    },
    # ============ Logs Widget ============
    "logs": {
        "en": "Logs",
        "ru": "Логи",
    },
    "part_code_placeholder": {
        "en": "Enter part code (e.g., PK-5396, A 221 501 26 91)",
        "ru": "Введите артикул (напр., PK-5396, A 221 501 26 91)",
    },
    # ============ Settings Page ============
    "application_settings": {
        "en": "Application Settings",
        "ru": "Настройки приложения",
    },
    "openai_api_configuration": {
        "en": "OpenAI API Configuration",
        "ru": "Конфигурация OpenAI API",
    },
    "openai_api_key_label": {
        "en": "OpenAI API Key (required for GPT vision):",
        "ru": "Ключ OpenAI API (требуется для GPT vision):",
    },
    "show": {
        "en": "Show",
        "ru": "Показать",
    },
    "hide": {
        "en": "Hide",
        "ru": "Скрыть",
    },
    "vision_backend": {
        "en": "Vision Backend:",
        "ru": "Бэкенд распознавания:",
    },
    "model": {
        "en": "Model:",
        "ru": "Модель:",
    },
    "camera_configuration": {
        "en": "Camera Configuration",
        "ru": "Конфигурация камеры",
    },
    "camera_index": {
        "en": "Camera Index:",
        "ru": "Индекс камеры:",
    },
    "width": {
        "en": "Width:",
        "ru": "Ширина:",
    },
    "height": {
        "en": "Height:",
        "ru": "Высота:",
    },
    "test_camera": {
        "en": "Test Camera",
        "ru": "Проверить камеру",
    },
    "scale_configuration": {
        "en": "Scale Configuration",
        "ru": "Конфигурация весов",
    },
    "scale_port": {
        "en": "Scale Port:",
        "ru": "Порт весов:",
    },
    "scale_port_placeholder": {
        "en": "COM3, /dev/ttyUSB0, etc.",
        "ru": "COM3, /dev/ttyUSB0 и т.д.",
    },
    "baudrate": {
        "en": "Baudrate:",
        "ru": "Скорость передачи:",
    },
    "weight_threshold": {
        "en": "Weight Threshold (kg):",
        "ru": "Порог веса (кг):",
    },
    "stable_time": {
        "en": "Stable Time (seconds):",
        "ru": "Время стабилизации (сек):",
    },
    "advanced_settings": {
        "en": "Advanced",
        "ru": "Дополнительно",
    },
    "test_scale_connection": {
        "en": "Test Scale Connection",
        "ru": "Проверить подключение весов",
    },
    "multiple_matches_title": {
        "en": "Multiple Matches Found",
        "ru": "Найдено несколько совпадений",
    },
    "multiple_matches_msg": {
        "en": "The code matches multiple catalog entries. Select the correct one:",
        "ru": "Код соответствует нескольким записям в каталоге. Выберите нужную:",
    },
    "processing_configuration": {
        "en": "Processing Configuration",
        "ru": "Конфигурация обработки",
    },
    "default_target": {
        "en": "Default Target:",
        "ru": "Цель по умолчанию:",
    },
    "min_fuzzy_score": {
        "en": "Min Fuzzy Score:",
        "ru": "Мин. балл нечёткого поиска:",
    },
    "ui_configuration": {
        "en": "UI Configuration",
        "ru": "Конфигурация интерфейса",
    },
    "language_label": {
        "en": "Language / Язык:",
        "ru": "Язык / Language:",
    },
    "show_logs_widget": {
        "en": "Show Logs Widget",
        "ru": "Показывать виджет логов",
    },
    "show_logs_tooltip": {
        "en": "Show or hide the logs widget in both Automated and Manual tabs",
        "ru": "Показывать или скрывать виджет логов",
    },
    "use_openai_tts": {
        "en": "Use OpenAI TTS (premium)",
        "ru": "Использовать OpenAI TTS (премиум)",
    },
    "use_openai_tts_tooltip": {
        "en": "Requires OPENAI_API_KEY. May incur API costs. Disabled by default for free OS voices.",
        "ru": "Требуется OPENAI_API_KEY. Могут взиматься расходы на API. По умолчанию отключено для бесплатных системных голосов.",
    },
    "voice_support": {
        "en": "Voice Support",
        "ru": "Голосовая поддержка",
    },
    "speech_engine_label": {
        "en": "Speech Engine:",
        "ru": "Движок озвучивания:",
    },
    "speech_engine_os": {
        "en": "OS (free)",
        "ru": "Системный (бесплатно)",
    },
    "speech_engine_openai": {
        "en": "OpenAI (premium)",
        "ru": "OpenAI (премиум)",
    },
    "speech_engine_piper": {
        "en": "Piper (offline)",
        "ru": "Piper (офлайн)",
    },
    "piper_voice_label": {
        "en": "Piper voice model id:",
        "ru": "Модель голоса Piper:",
    },
    "piper_voice_help": {
        "en": "Armenian local voice model (Piper). Requires one-time model download.",
        "ru": "Армянский локальный голос (Piper). Требуется одноразовая загрузка модели.",
    },
    "piper_binary_path_label": {
        "en": "Piper binary path (optional):",
        "ru": "Путь к исполняемому файлу Piper (необязательно):",
    },
    "download_armenian_voice": {
        "en": "Download Armenian Voice",
        "ru": "Скачать армянский голос",
    },
    "test_voice": {
        "en": "Test voice",
        "ru": "Тест голоса",
    },
    "piper_download_title": {
        "en": "Piper Voice Download",
        "ru": "Загрузка голоса Piper",
    },
    "piper_download_started": {
        "en": "Downloading Armenian Piper voice model...\nThis may take a minute depending on your connection.",
        "ru": "Загружается армянская голосовая модель Piper...\nЭто может занять некоторое время в зависимости от соединения.",
    },
    "piper_download_success": {
        "en": "Armenian Piper voice model downloaded successfully.",
        "ru": "Армянская голосовая модель Piper успешно загружена.",
    },
    "piper_download_failed": {
        "en": "Failed to download Armenian Piper voice model:\n{error}",
        "ru": "Не удалось загрузить армянскую голосовую модель Piper:\n{error}",
    },
    "piper_missing_model_fallback": {
        "en": "Piper engine selected, but the voice model was not found.\nFalling back to OS speech engine.",
        "ru": "Выбран движок Piper, но модель голоса не найдена.\nИспользуется системный движок озвучивания.",
    },
    "openai_tts_requires_key": {
        "en": "OpenAI API Key Required",
        "ru": "Требуется ключ OpenAI API",
    },
    "openai_tts_requires_key_msg": {
        "en": "OpenAI TTS requires an API key to be set.\n\nPlease enter your OpenAI API key in the OpenAI API Configuration section above.",
        "ru": "OpenAI TTS требует наличия ключа API.\n\nПожалуйста, введите ваш ключ OpenAI API в разделе конфигурации OpenAI API выше.",
    },
    "pricing_configuration": {
        "en": "Pricing Configuration",
        "ru": "Конфигурация цен",
    },
    "weight_price_per_kg": {
        "en": "Weight Price (per kg):",
        "ru": "Цена за кг:",
    },
    "default_result_file": {
        "en": "Default Result File",
        "ru": "Файл результатов по умолчанию",
    },
    "default_result_file_label": {
        "en": "Default result file (used when no file is selected):",
        "ru": "Файл результатов по умолчанию (используется, если не выбран другой):",
    },
    "leave_empty_auto_generate": {
        "en": "Leave empty to auto-generate in app data directory",
        "ru": "Оставьте пустым для автоматической генерации",
    },
    "browse": {
        "en": "Browse…",
        "ru": "Обзор…",
    },
    "use_default": {
        "en": "Use Default",
        "ru": "По умолчанию",
    },
    "use_default_tooltip": {
        "en": "Set to default location in app data directory",
        "ru": "Установить местоположение по умолчанию",
    },
    "if_empty_files_auto_generated": {
        "en": "If empty, files will be auto-generated in:\n{path}",
        "ru": "Если пусто, файлы будут созданы в:\n{path}",
    },
    "reset_to_defaults": {
        "en": "Reset to Defaults",
        "ru": "Сбросить настройки",
    },
    "cancel": {
        "en": "Cancel",
        "ru": "Отмена",
    },
    "save_settings": {
        "en": "Save Settings",
        "ru": "Сохранить настройки",
    },
    "camera_test": {
        "en": "Camera Test",
        "ru": "Тест камеры",
    },
    "camera_working": {
        "en": "Camera {index} is working!\nFrame size: {width}x{height}",
        "ru": "Камера {index} работает!\nРазмер кадра: {width}x{height}",
    },
    "camera_no_frame": {
        "en": "Camera {index} opened but couldn't read frame.",
        "ru": "Камера {index} открыта, но не удалось прочитать кадр.",
    },
    "camera_failed_open": {
        "en": "Failed to open camera {index}.",
        "ru": "Не удалось открыть камеру {index}.",
    },
    "camera_test_error": {
        "en": "Error testing camera: {error}",
        "ru": "Ошибка тестирования камеры: {error}",
    },
    "choose_default_result_file": {
        "en": "Choose Default Result File",
        "ru": "Выбор файла результатов по умолчанию",
    },
    "excel_filter": {
        "en": "Excel (*.xlsx);;All files (*)",
        "ru": "Excel (*.xlsx);;Все файлы (*)",
    },
    "scale_test": {
        "en": "Scale Test",
        "ru": "Тест весов",
    },
    "enter_scale_port": {
        "en": "Please enter a scale port.",
        "ru": "Пожалуйста, введите порт весов.",
    },
    "scale_connection_success": {
        "en": "Scale connection successful!\nPort: {port}\nBaudrate: {baudrate}\nWeight: {weight}",
        "ru": "Подключение к весам успешно!\nПорт: {port}\nСкорость: {baudrate}\nВес: {weight}",
    },
    "scale_connected_no_data": {
        "en": "Connected to {port} but no weight data received.\nThis is normal if the scale is empty.",
        "ru": "Подключено к {port}, но данные о весе не получены.\nЭто нормально, если весы пусты.",
    },
    "scale_connection_failed": {
        "en": "Failed to connect to scale:\n{error}",
        "ru": "Не удалось подключиться к весам:\n{error}",
    },
    "missing_api_key": {
        "en": "Missing API Key",
        "ru": "Отсутствует ключ API",
    },
    "missing_api_key_msg": {
        "en": "OpenAI API key is empty. You won't be able to use GPT vision.\nContinue anyway?",
        "ru": "Ключ OpenAI API пуст. Вы не сможете использовать GPT vision.\nПродолжить?",
    },
    "validating_api_key": {
        "en": "Validating API key...",
        "ru": "Проверка ключа API...",
    },
    "validating_api_key_title": {
        "en": "Validating API Key",
        "ru": "Проверка ключа API",
    },
    "invalid_api_key": {
        "en": "Invalid API Key",
        "ru": "Неверный ключ API",
    },
    "invalid_api_key_msg": {
        "en": "Failed to validate OpenAI API key:\n\n{error}\n\nPlease check your API key and try again.\n\nYou can get your API key from: https://platform.openai.com/api-keys",
        "ru": "Не удалось проверить ключ OpenAI API:\n\n{error}\n\nПожалуйста, проверьте ключ и попробуйте снова.\n\nВы можете получить ключ: https://platform.openai.com/api-keys",
    },
    "api_key_validation_warning": {
        "en": "API Key Validation Warning",
        "ru": "Предупреждение проверки ключа API",
    },
    "api_key_warning_msg": {
        "en": "API key validation completed with a warning:\n\n{error}\n\nThe key may be valid, but verification failed.\nContinue anyway?",
        "ru": "Проверка ключа API завершена с предупреждением:\n\n{error}\n\nКлюч может быть действительным, но проверка не удалась.\nПродолжить?",
    },
    "api_key_valid": {
        "en": "API Key Valid",
        "ru": "Ключ API действителен",
    },
    "api_key_valid_msg": {
        "en": "OpenAI API key validated successfully!",
        "ru": "Ключ OpenAI API успешно проверен!",
    },
    "settings_saved": {
        "en": "Settings Saved",
        "ru": "Настройки сохранены",
    },
    "settings_saved_msg": {
        "en": "Settings have been saved successfully.\nLanguage changes require restarting the application.\n\nНастройки сохранены.\nДля изменения языка требуется перезапуск приложения.",
        "ru": "Настройки сохранены.\nДля изменения языка требуется перезапуск приложения.\n\nSettings saved.\nLanguage changes require restarting the application.",
    },
    "reset_settings": {
        "en": "Reset Settings",
        "ru": "Сбросить настройки",
    },
    "reset_settings_msg": {
        "en": "Are you sure you want to reset all settings to their default values?\n\nThis will clear your API key and all custom configurations.\nThis action cannot be undone.",
        "ru": "Вы уверены, что хотите сбросить все настройки?\n\nЭто очистит ваш ключ API и все пользовательские настройки.\nЭто действие нельзя отменить.",
    },
    "settings_reset_title": {
        "en": "Settings Reset",
        "ru": "Настройки сброшены",
    },
    "settings_reset_msg": {
        "en": "All settings have been reset to default values.\n\nRemember to configure your API key and other settings before using the application.",
        "ru": "Все настройки сброшены на значения по умолчанию.\n\nНе забудьте настроить ключ API и другие параметры перед использованием приложения.",
    },
    # ============ Settings Widget ============
    "manual_entry_without_scanning": {
        "en": "Manual Entry (without scanning)",
        "ru": "Ручной ввод (без сканирования)",
    },
    "part_code_label": {
        "en": "Part Code:",
        "ru": "Артикул:",
    },
    "part_code_placeholder_short": {
        "en": "Enter part code (e.g., PK-5396)",
        "ru": "Введите артикул (напр., PK-5396)",
    },
    "weight_kg_label": {
        "en": "Weight (kg):",
        "ru": "Вес (кг):",
    },
    "enter_weight": {
        "en": "Enter weight",
        "ru": "Введите вес",
    },
    "add_to_results": {
        "en": "Add to Results",
        "ru": "Добавить в результаты",
    },
    "quantity_label": {
        "en": "Quantity:",
        "ru": "Количество:",
    },
    "qty_min": {
        "en": "Min",
        "ru": "Мин",
    },
    "qty_max": {
        "en": "Max",
        "ru": "Макс",
    },
    "enter_quantity": {
        "en": "Please enter a quantity",
        "ru": "Пожалуйста, введите количество",
    },
    "reset_tooltip": {
        "en": "Clear selection and start with new empty results file",
        "ru": "Очистить выбор и начать с нового пустого файла результатов",
    },
    "excel_file_problem": {
        "en": "Excel File Problem",
        "ru": "Проблема с файлом Excel",
    },
    "catalog_cannot_open": {
        "en": "The catalog file cannot be opened",
        "ru": "Файл каталога не может быть открыт",
    },
    "catalog_corrupted_msg": {
        "en": "The file '{file}' appears to be corrupted or in an unsupported format.\n\nTo fix this:\n\n1. Open the file in Microsoft Excel or LibreOffice\n2. If it opens, click File → Save As\n3. Choose 'Excel Workbook (.xlsx)' as the format\n4. Save the file\n5. Select the new .xlsx file as Catalog",
        "ru": "Файл '{file}' поврежден или в неподдерживаемом формате.\n\nДля исправления:\n\n1. Откройте файл в Microsoft Excel или LibreOffice\n2. Если он открывается, нажмите Файл → Сохранить как\n3. Выберите формат 'Книга Excel (.xlsx)'\n4. Сохраните файл\n5. Выберите новый файл .xlsx в качестве каталога",
    },
    "empty_catalog_file": {
        "en": "Empty Catalog File",
        "ru": "Пустой файл каталога",
    },
    "catalog_empty": {
        "en": "The catalog file is empty",
        "ru": "Файл каталога пуст",
    },
    "catalog_empty_msg": {
        "en": "The file '{file}' does not contain any data rows.\n\nPlease ensure your Excel file has:\n• Column headers in the first row\n• At least one data row with part codes\n\nThe file appears to be empty or only contains headers.",
        "ru": "Файл '{file}' не содержит данных.\n\nУбедитесь, что ваш файл Excel содержит:\n• Заголовки столбцов в первой строке\n• Хотя бы одну строку данных с артикулами\n\nФайл пуст или содержит только заголовки.",
    },
    "invalid_catalog_file": {
        "en": "Invalid Catalog File",
        "ru": "Неверный файл каталога",
    },
    "catalog_missing_columns": {
        "en": "The catalog file is missing required columns",
        "ru": "В файле каталога отсутствуют обязательные столбцы",
    },
    "catalog_missing_columns_msg": {
        "en": "The file '{file}' does not contain a part code column.\n\nRequired column (one of):\n• Номер / Артикул\n• номер / арт / artikul / article / part / sku / code / number\n\nOptional column:\n• Клиент / client / name / buyer / vendor / customer\n\nPlease check your Excel file and ensure it has the correct column headers.",
        "ru": "Файл '{file}' не содержит столбца с артикулами.\n\nОбязательный столбец (один из):\n• Номер / Артикул\n• номер / арт / artikul / article / part / sku / code / number\n\nНеобязательный столбец:\n• Клиент / client / name / buyer / vendor / customer\n\nПроверьте файл Excel и убедитесь, что заголовки столбцов указаны правильно.",
    },
    "reset_results_file": {
        "en": "Reset Results File",
        "ru": "Сбросить файл результатов",
    },
    "reset_results_confirm": {
        "en": "This will clear the current results file selection and create a new empty file.\nContinue?",
        "ru": "Это очистит выбор текущего файла результатов и создаст новый пустой файл.\nПродолжить?",
    },
    "reset_complete": {
        "en": "Reset Complete",
        "ru": "Сброс завершен",
    },
    "reset_complete_msg": {
        "en": "New empty results file created:\n{path}",
        "ru": "Создан новый пустой файл результатов:\n{path}",
    },
    "reset_failed": {
        "en": "Reset Failed",
        "ru": "Сбой сброса",
    },
    "reset_failed_msg": {
        "en": "Failed to create new results file:\n{error}",
        "ru": "Не удалось создать новый файл результатов:\n{error}",
    },
    "download_results": {
        "en": "Download Results",
        "ru": "Скачать результаты",
    },
    "no_results_file": {
        "en": "No results file found. Please run some OCR operations first to generate results.",
        "ru": "Файл результатов не найден. Сначала выполните операции OCR для генерации результатов.",
    },
    "save_results_excel": {
        "en": "Save Results Excel File",
        "ru": "Сохранить файл результатов Excel",
    },
    "download_complete": {
        "en": "Download Complete",
        "ru": "Загрузка завершена",
    },
    "download_complete_msg": {
        "en": "Results file saved successfully to:\n{path}",
        "ru": "Файл результатов успешно сохранен:\n{path}",
    },
    "download_failed": {
        "en": "Download Failed",
        "ru": "Ошибка загрузки",
    },
    "download_failed_msg": {
        "en": "Failed to save results file:\n{error}",
        "ru": "Не удалось сохранить файл результатов:\n{error}",
    },
    "manual_entry": {
        "en": "Manual Entry",
        "ru": "Ручной ввод",
    },
    "enter_part_code": {
        "en": "Please enter a part code.",
        "ru": "Пожалуйста, введите артикул.",
    },
    "enter_the_weight": {
        "en": "Please enter the weight.",
        "ru": "Пожалуйста, введите вес.",
    },
    "weight_greater_than_zero": {
        "en": "Weight must be greater than 0.",
        "ru": "Вес должен быть больше 0.",
    },
    "enter_valid_weight": {
        "en": "Please enter a valid weight number.",
        "ru": "Пожалуйста, введите корректное числовое значение веса.",
    },
    "weight_price_error": {
        "en": "Weight Price must be greater than 0. Please configure it in Settings.",
        "ru": "Цена за кг должна быть больше 0. Пожалуйста, настройте её в Настройках.",
    },
    # ============ Error Messages - Main Window ============
    "error": {
        "en": "Error",
        "ru": "Ошибка",
    },
    "choose_valid_catalog": {
        "en": "Please choose a valid Catalog Excel file.",
        "ru": "Пожалуйста, выберите действительный файл каталога Excel.",
    },
    "run_failed": {
        "en": "Run failed",
        "ru": "Сбой выполнения",
    },
    "weight_price_required": {
        "en": "Weight Price Required",
        "ru": "Требуется цена за кг",
    },
    "cannot_record_match": {
        "en": "Cannot record match without valid weight price:\n{error}",
        "ru": "Невозможно записать совпадение без действительной цены за кг:\n{error}",
    },
    "search_failed": {
        "en": "Search Failed",
        "ru": "Ошибка поиска",
    },
    "unable_search_catalog": {
        "en": "Unable to search the catalog. Please check your settings.",
        "ru": "Не удалось выполнить поиск в каталоге. Проверьте настройки.",
    },
    "cannot_record_manual_search": {
        "en": "Cannot record manual search without valid weight price:\n{error}",
        "ru": "Невозможно записать ручной поиск без действительной цены за кг:\n{error}",
    },
    "cannot_record_manual_entry": {
        "en": "Cannot record manual entry without valid weight price:\n{error}",
        "ru": "Невозможно записать ручной ввод без действительной цены за кг:\n{error}",
    },
    "manual_entry_success": {
        "en": "Manual Entry Success",
        "ru": "Ручной ввод успешен",
    },
    "manual_entry_success_msg": {
        "en": "Successfully added:\n{artikul} → {client}\nWeight: {weight} kg",
        "ru": "Успешно добавлено:\n{artikul} → {client}\nВес: {weight} кг",
    },
    "entry_saved_confirmation": {
        "en": "Saved successfully. You can continue.",
        "ru": "Успешно сохранено. Можно продолжать.",
    },
    "copy_name": {
        "en": "Copy Name",
        "ru": "Копировать имя",
    },
    "manual_entry_failed": {
        "en": "Manual Entry Failed",
        "ru": "Ошибка ручного ввода",
    },
    "manual_entry_failed_msg": {
        "en": "Failed to log entry: {error}",
        "ru": "Не удалось записать: {error}",
    },
    "no_match_found": {
        "en": "No Match Found",
        "ru": "Совпадение не найдено",
    },
    "no_match_for_part_code": {
        "en": "No match found for part code: {code}\n\nYou can still add it manually to your inventory.",
        "ru": "Совпадение для артикула: {code} не найдено.\n\nВы все еще можете добавить его вручную в инвентарь.",
    },
    "unable_search_part_code": {
        "en": "Unable to search for part code '{code}'.\n\nPlease check that your catalog file is set up correctly in Settings.",
        "ru": "Не удалось найти артикул '{code}'.\n\nПроверьте, что файл каталога правильно настроен в Настройках.",
    },
    "manual_entry_error": {
        "en": "Manual Entry Error",
        "ru": "Ошибка ручного ввода",
    },
    "error_occurred": {
        "en": "An error occurred: {error}",
        "ru": "Произошла ошибка: {error}",
    },
    "generate_invoice_title": {
        "en": "Generate Invoice",
        "ru": "Генерация счёта",
    },
    "no_results_file_invoice": {
        "en": "No results file found. Please run some OCR operations first to generate results.",
        "ru": "Файл результатов не найден. Сначала выполните операции OCR для генерации результатов.",
    },
    "choose_valid_catalog_first": {
        "en": "Please choose a valid Catalog Excel file first.",
        "ru": "Сначала выберите действительный файл каталога Excel.",
    },
    "weight_price_validation_failed": {
        "en": "Weight Price validation failed:\n{error}",
        "ru": "Проверка цены за кг не удалась:\n{error}",
    },
    "save_invoice_as": {
        "en": "Save Invoice As",
        "ru": "Сохранить счёт как",
    },
    "invoice_generated": {
        "en": "Invoice Generated",
        "ru": "Счёт сгенерирован",
    },
    "invoice_generated_msg": {
        "en": "Invoice generated successfully!\n\nFile: {path}\nClients: {clients}",
        "ru": "Счёт успешно сгенерирован!\n\nФайл: {path}\nКлиентов: {clients}",
    },
    "invoice_generation_failed": {
        "en": "Invoice Generation Failed",
        "ru": "Ошибка генерации счёта",
    },
    "invoice_generation_failed_msg": {
        "en": "Failed to generate invoice:\n\n{error}",
        "ru": "Не удалось сгенерировать счёт:\n\n{error}",
    },
    # ============ Error Messages - Camera Widget ============
    "camera_title": {
        "en": "Camera",
        "ru": "Камера",
    },
    "camera_failed_open_msg": {
        "en": "Failed to open camera (index {index}).\n\nPlease check:\n1. Camera is connected and not in use by another application\n2. Camera index is correct (open Settings ⚙️ to change it)\n3. Camera permissions are granted\n\nError: {error}",
        "ru": "Не удалось открыть камеру (индекс {index}).\n\nПожалуйста, проверьте:\n1. Камера подключена и не используется другим приложением\n2. Индекс камеры верен (откройте Настройки ⚙️ для изменения)\n3. Разрешения камеры предоставлены\n\nОшибка: {error}",
    },
    "no_frame_yet": {
        "en": "No frame yet. Try again.",
        "ru": "Кадр ещё не получен. Попробуйте снова.",
    },
    "failed_save_capture": {
        "en": "Failed to save capture: {error}",
        "ru": "Не удалось сохранить снимок: {error}",
    },
    # ============ Error Messages - Scale Widget ============
    "invalid_weight": {
        "en": "Invalid Weight",
        "ru": "Неверный вес",
    },
    "weight_must_be_positive": {
        "en": "Weight must be greater than 0.",
        "ru": "Вес должен быть больше 0.",
    },
    "enter_valid_number": {
        "en": "Please enter a valid number.",
        "ru": "Пожалуйста, введите корректное число.",
    },
    "scale_connection_title": {
        "en": "Scale Connection",
        "ru": "Подключение весов",
    },
    "configure_scale_port": {
        "en": "Please configure the scale port in Settings.",
        "ru": "Пожалуйста, настройте порт весов в Настройках.",
    },
    "scale_connected_title": {
        "en": "Scale Connected",
        "ru": "Весы подключены",
    },
    "scale_connected_msg": {
        "en": "Successfully connected to scale on {port}.\nCurrent weight: {weight}",
        "ru": "Успешно подключено к весам на {port}.\nТекущий вес: {weight}",
    },
    "scale_connected_no_weight": {
        "en": "Successfully connected to scale on {port}, but no weight data was received yet.\n\nThis is normal if the scale is empty or only sends data when weight changes.",
        "ru": "Успешно подключено к весам на {port}, но данные о весе еще не получены.\n\nЭто нормально, если весы пусты или отправляют данные только при изменении веса.",
    },
    "failed_persistent_connection": {
        "en": "Failed to open persistent connection: {error}",
        "ru": "Не удалось открыть постоянное соединение: {error}",
    },
    "failed_open_port": {
        "en": "Failed to open port {port}.\n\nError: {error}",
        "ru": "Не удалось открыть порт {port}.\n\nОшибка: {error}",
    },
    # ============ Log Messages ============
    "log_running": {
        "en": "Running…",
        "ru": "Выполнение…",
    },
    "log_using_scale_weight": {
        "en": "Using scale weight: {weight:.3f} kg",
        "ru": "Использование веса весов: {weight:.3f} кг",
    },
    "log_scale_detected": {
        "en": "[INFO] Scale detected weight: {weight:.3f} kg - auto-starting camera",
        "ru": "[ИНФО] Весы обнаружили вес: {weight:.3f} кг - автозапуск камеры",
    },
    "log_camera_started": {
        "en": "[INFO] Camera started automatically",
        "ru": "[ИНФО] Камера запущена автоматически",
    },
    "log_failed_autostart_camera": {
        "en": "[ERROR] Failed to auto-start camera: {error}",
        "ru": "[ОШИБКА] Не удалось автоматически запустить камеру: {error}",
    },
    "log_job_canceled": {
        "en": "[INFO] Job was canceled.",
        "ru": "[ИНФО] Задание отменено.",
    },
    "log_fuzzy_canceled": {
        "en": "[INFO] Fuzzy job was canceled.",
        "ru": "[ИНФО] Нечёткое задание отменено.",
    },
    "log_logged_to_results": {
        "en": "[INFO] Logged to results: {action} → {path}",
        "ru": "[ИНФО] Записано в результаты: {action} → {path}",
    },
    "log_results_log_failed": {
        "en": "[WARN] Results log failed: {error}",
        "ru": "[ПРЕДУПРЕЖДЕНИЕ] Запись результатов не удалась: {error}",
    },
    "log_searching_manual_code": {
        "en": "Searching for manual code: {code}",
        "ru": "Поиск кода: {code}",
    },
    "log_manual_entry": {
        "en": "Manual entry: {code} (weight: {weight} kg)",
        "ru": "Ручной ввод: {code} (вес: {weight} кг)",
    },
    "log_manual_entry_logged": {
        "en": "[INFO] Manual entry logged: {artikul} → {client} (weight: {weight} kg)",
        "ru": "[ИНФО] Ручной ввод записан: {artikul} → {client} (вес: {weight} кг)",
    },
    "log_no_match_manual_code": {
        "en": "[INFO] No match found for manual code: {code}",
        "ru": "[ИНФО] Совпадение для кода: {code} не найдено",
    },
    "log_manual_search_failed": {
        "en": "[ERROR] Manual search failed: {error}",
        "ru": "[ОШИБКА] Ручной поиск не удался: {error}",
    },
    "log_manual_search_error": {
        "en": "[ERROR] Manual search error: {error}",
        "ru": "[ОШИБКА] Ошибка ручного поиска: {error}",
    },
    "log_manual_entry_failed": {
        "en": "[WARN] Manual entry log failed: {error}",
        "ru": "[ПРЕДУПРЕЖДЕНИЕ] Запись ручного ввода не удалась: {error}",
    },
    "log_manual_entry_search_failed": {
        "en": "[ERROR] Manual entry search failed: {error}",
        "ru": "[ОШИБКА] Поиск ручного ввода не удался: {error}",
    },
    "log_manual_entry_error": {
        "en": "[ERROR] Manual entry error: {error}",
        "ru": "[ОШИБКА] Ошибка ручного ввода: {error}",
    },
    "log_generating_invoice": {
        "en": "[INFO] Generating invoice...",
        "ru": "[ИНФО] Генерация счёта...",
    },
    "log_invoice_success": {
        "en": "[INFO] Invoice generated successfully!",
        "ru": "[ИНФО] Счёт успешно сгенерирован!",
    },
    "log_invoice_output": {
        "en": "[INFO] Output: {path}",
        "ru": "[ИНФО] Файл: {path}",
    },
    "log_invoice_clients": {
        "en": "[INFO] Clients processed: {clients}",
        "ru": "[ИНФО] Обработано клиентов: {clients}",
    },
    "log_invoice_failed": {
        "en": "[ERROR] Invoice generation failed: {error}",
        "ru": "[ОШИБКА] Генерация счёта не удалась: {error}",
    },
    "log_failed_start_camera": {
        "en": "[ERROR] Failed to start camera: {error}",
        "ru": "[ОШИБКА] Не удалось запустить камеру: {error}",
    },
    "log_failed_capture": {
        "en": "[ERROR] Failed to capture: {error}",
        "ru": "[ОШИБКА] Не удалось захватить: {error}",
    },
    "log_camera_not_ready": {
        "en": "[WARNING] Camera not ready for capture - waiting longer...",
        "ru": "[ВНИМАНИЕ] Камера не готова к захвату - ожидание...",
    },
    "log_camera_init_failed": {
        "en": "[ERROR] Camera failed to initialize after multiple attempts",
        "ru": "[ОШИБКА] Камера не инициализировалась после нескольких попыток",
    },
    "log_failed_capture_delay": {
        "en": "[ERROR] Failed to capture after delay: {error}",
        "ru": "[ОШИБКА] Не удалось захватить после задержки: {error}",
    },
    "log_scale_connection_lost": {
        "en": "[WARNING] Scale connection lost.",
        "ru": "[ВНИМАНИЕ] Соединение с весами потеряно.",
    },
    # ============ Speech Messages ============
    "speak_no_match_best_guess": {
        "en": "No match found. Best guess code: {code}.",
        "ru": "Совпадение не найдено. Лучший код: {code}.",
    },
    "speak_no_match": {
        "en": "No match found.",
        "ru": "Совпадение не найдено.",
    },
    "speak_no_match_for_code": {
        "en": "No match found for code: {code}.",
        "ru": "Совпадение для кода: {code} не найдено.",
    },
    # ============ Result Status ============
    "status_not_found": {
        "en": "not found",
        "ru": "не найдено",
    },
    "canceled": {
        "en": "canceled",
        "ru": "отменено",
    },
    # ============ Additional Log Messages ============
    "log_manual_weight_set": {
        "en": "[INFO] Manual weight set: {weight:.3f} kg",
        "ru": "[ИНФО] Ручной вес установлен: {weight:.3f} кг",
    },
    "log_select_catalog_first": {
        "en": "Please select a catalog file first",
        "ru": "Сначала выберите файл каталога",
    },
    "log_set_weight_first": {
        "en": "Please set a weight first (scale or manual)",
        "ru": "Сначала установите вес (весы или вручную)",
    },
    "log_manual_code_submitted": {
        "en": "[INFO] Manual code submitted: {code} (weight: {weight:.3f} kg)",
        "ru": "[ИНФО] Код введён вручную: {code} (вес: {weight:.3f} кг)",
    },
    "log_processing_code": {
        "en": "Processing: {code}",
        "ru": "Обработка: {code}",
    },
    "log_weight_ready_debug": {
        "en": "[DEBUG] Weight ready signal received: {weight:.3f} kg",
        "ru": "[ОТЛАДКА] Получен сигнал о готовности веса: {weight:.3f} кг",
    },
    "log_weight_stabilized_manual_mode": {
        "en": "[INFO] Weight stabilized: {weight:.3f} kg (camera in manual mode)",
        "ru": "[ИНФО] Вес стабилизировался: {weight:.3f} кг (камера в ручном режиме)",
    },
    "log_weight_stabilized_no_catalog": {
        "en": "[INFO] Weight stabilized: {weight:.3f} kg, but no catalog file selected",
        "ru": "[ИНФО] Вес стабилизировался: {weight:.3f} кг, но файл каталога не выбран",
    },
    "log_weight_stabilized_starting_camera": {
        "en": "[INFO] Weight stabilized: {weight:.3f} kg - starting camera...",
        "ru": "[ИНФО] Вес стабилизировался: {weight:.3f} кг - запуск камеры...",
    },
    "log_weight_stabilized_waiting_frame": {
        "en": "[INFO] Weight stabilized: {weight:.3f} kg - waiting for camera frame...",
        "ru": "[ИНФО] Вес стабилизировался: {weight:.3f} кг - ожидание кадра камеры...",
    },
    "log_weight_stabilized_capturing": {
        "en": "[INFO] Weight stabilized: {weight:.3f} kg - capturing image and running OCR",
        "ru": "[ИНФО] Вес стабилизировался: {weight:.3f} кг - захват изображения и запуск OCR",
    },
    "log_waiting_camera_frame": {
        "en": "[INFO] Waiting for camera frame...",
        "ru": "[ИНФО] Ожидание кадра камеры...",
    },
    "log_camera_ready_capturing": {
        "en": "[INFO] Camera ready - capturing image for weight: {weight:.3f} kg",
        "ru": "[ИНФО] Камера готова - захват изображения для веса: {weight:.3f} кг",
    },
    # ============ Results Pane ============
    "results_table": {
        "en": "Results Table",
        "ru": "Таблица результатов",
    },
    "refresh": {
        "en": "Refresh",
        "ru": "Обновить",
    },
    "open_file": {
        "en": "Open File",
        "ru": "Открыть файл",
    },
    # ============ Logs Widget ============
    "logs": {
        "en": "Logs",
        "ru": "Логи",
    },
    "clear": {
        "en": "Clear",
        "ru": "Очистить",
    },
    # ============ Messages ============
    "running": {
        "en": "Running…",
        "ru": "Выполняется…",
    },
    "using_scale_weight": {
        "en": "Using scale weight: {weight:.3f} kg",
        "ru": "Используется вес с весов: {weight:.3f} кг",
    },
    "no_match_found": {
        "en": "No match found.",
        "ru": "Совпадение не найдено.",
    },
    "catalog_required": {
        "en": "Catalog File Required",
        "ru": "Требуется файл каталога",
    },
    "select_catalog_msg": {
        "en": "Please select a Catalog Excel file to continue.\n\nThe catalog file contains the part codes and client information\nneeded for matching scanned items.",
        "ru": "Пожалуйста, выберите файл каталога Excel для продолжения.\n\nФайл каталога содержит артикулы и информацию о клиентах,\nнеобходимую для сопоставления отсканированных товаров.",
    },
    "select_catalog_file": {
        "en": "Select Catalog File",
        "ru": "Выберите файл каталога",
    },
    "error": {
        "en": "Error",
        "ru": "Ошибка",
    },
    "please_select_catalog": {
        "en": "Please select a catalog file first",
        "ru": "Сначала выберите файл каталога",
    },
    "please_set_weight": {
        "en": "Please set a weight first (scale or manual)",
        "ru": "Сначала установите вес (весы или вручную)",
    },
    # ============ Network Configuration ============
    "network": {
        "en": "Network",
        "ru": "Сеть",
    },
    "network_configuration": {
        "en": "Network Configuration (Multi-Device)",
        "ru": "Сетевая конфигурация (Многопользовательский режим)",
    },
    "network_mode_label": {
        "en": "Select mode:",
        "ru": "Выберите режим:",
    },
    "standalone_mode": {
        "en": "📱 Standalone",
        "ru": "📱 Автономный",
    },
    "server_mode": {
        "en": "🖥️ Server",
        "ru": "🖥️ Сервер",
    },
    "client_mode": {
        "en": "💻 Client",
        "ru": "💻 Клиент",
    },
    "standalone_tooltip": {
        "en": "Work independently without network connection",
        "ru": "Работать независимо без сетевого подключения",
    },
    "server_tooltip": {
        "en": "Run as server - other computers can connect to this one",
        "ru": "Запустить как сервер - другие компьютеры могут подключаться к этому",
    },
    "client_tooltip": {
        "en": "Connect to another computer running as server",
        "ru": "Подключиться к другому компьютеру, работающему как сервер",
    },
    "server_port_label": {
        "en": "Port:",
        "ru": "Порт:",
    },
    "start_server": {
        "en": "▶️ Start Server",
        "ru": "▶️ Запустить сервер",
    },
    "stop_server": {
        "en": "⏹️ Stop Server",
        "ru": "⏹️ Остановить сервер",
    },
    "reconnect_sse": {
        "en": "🔄 Reconnect",
        "ru": "🔄 Переподключить",
    },
    "server_status_stopped": {
        "en": "Server is not running",
        "ru": "Сервер не запущен",
    },
    "server_status_running": {
        "en": "✅ Server running at: {url}",
        "ru": "✅ Сервер запущен: {url}",
    },
    "server_status_running_with_clients": {
        "en": "✅ Server running at: {url} | {count} device(s) connected",
        "ru": "✅ Сервер запущен: {url} | Подключено устройств: {count}",
    },
    "server_address_label": {
        "en": "Server Address:",
        "ru": "Адрес сервера:",
    },
    "connect": {
        "en": "🔗 Connect",
        "ru": "🔗 Подключить",
    },
    "disconnect": {
        "en": "🔌 Disconnect",
        "ru": "🔌 Отключить",
    },
    "connection_status_disconnected": {
        "en": "Not connected to any server",
        "ru": "Не подключено ни к одному серверу",
    },
    "connection_status_connected": {
        "en": "✅ Connected to: {address}",
        "ru": "✅ Подключено к: {address}",
    },
    "server": {
        "en": "Server",
        "ru": "Сервер",
    },
    "server_started_msg": {
        "en": "Server started successfully!\n\nOther computers can connect using:\n{url}\n\nShare this address with other devices.",
        "ru": "Сервер успешно запущен!\n\nДругие компьютеры могут подключиться по адресу:\n{url}\n\nПоделитесь этим адресом с другими устройствами.",
    },
    "server_stopped_msg": {
        "en": "Server has been stopped.",
        "ru": "Сервер остановлен.",
    },
    "server_start_failed": {
        "en": "Failed to start server. Please check the port is not in use.",
        "ru": "Не удалось запустить сервер. Проверьте, что порт не занят.",
    },
    "server_error": {
        "en": "Server error: {error}",
        "ru": "Ошибка сервера: {error}",
    },
    "connection": {
        "en": "Connection",
        "ru": "Подключение",
    },
    "enter_server_address": {
        "en": "Please enter the server address (e.g., 192.168.1.100:8080)",
        "ru": "Введите адрес сервера (например, 192.168.1.100:8080)",
    },
    "discovering_servers": {
        "en": "🔍 Discovering servers on network...",
        "ru": "🔍 Поиск серверов в сети...",
    },
    "servers_found": {
        "en": "✅ Found {count} server(s)",
        "ru": "✅ Найдено серверов: {count}",
    },
    "no_servers_found": {
        "en": "No servers found. You can enter address manually.",
        "ru": "Серверы не найдены. Вы можете ввести адрес вручную.",
    },
    "refresh_server_discovery": {
        "en": "Search for servers on network (click to start/stop)",
        "ru": "Поиск серверов в сети (нажмите для запуска/остановки)",
    },
    "connected_msg": {
        "en": "Successfully connected to server at:\n{address}\n\nYou can now work together with other devices.",
        "ru": "Успешно подключено к серверу:\n{address}\n\nТеперь вы можете работать вместе с другими устройствами.",
    },
    "disconnected_msg": {
        "en": "Disconnected from server.",
        "ru": "Отключено от сервера.",
    },
    "connection_failed": {
        "en": "Failed to connect to server at:\n{address}\n\nPlease check:\n1. Server is running\n2. Address is correct\n3. Firewall allows connection",
        "ru": "Не удалось подключиться к серверу:\n{address}\n\nПроверьте:\n1. Сервер запущен\n2. Адрес правильный\n3. Брандмауэр разрешает подключение",
    },
    "connection_error": {
        "en": "Connection error: {error}",
        "ru": "Ошибка подключения: {error}",
    },
}


def get_text(key: str, lang: str = "en", **kwargs) -> str:
    """
    Get translated text for a key.

    Args:
        key: Translation key
        lang: Language code ("en" or "ru")
        **kwargs: Format arguments for the string

    Returns:
        Translated string, or key if not found
    """
    if key not in TRANSLATIONS:
        return key

    trans = TRANSLATIONS[key]
    if lang not in trans:
        lang = "en"  # Fallback to English

    text = trans.get(lang, key)

    # Apply format arguments if any
    if kwargs:
        try:
            text = text.format(**kwargs)
        except KeyError:
            pass

    return text


# Global language state
_current_language = "en"


def get_current_language() -> str:
    """Get the current language code."""
    return _current_language


def set_current_language(lang: str):
    """Set the current language code."""
    global _current_language
    if lang in LANGUAGES:
        _current_language = lang


def tr(key: str, **kwargs) -> str:
    """
    Shorthand for get_text with current language.

    Args:
        key: Translation key
        **kwargs: Format arguments for the string

    Returns:
        Translated string
    """
    return get_text(key, _current_language, **kwargs)


def load_language_from_settings():
    """Load and set language from settings."""
    try:
        from gearledger.desktop.settings_manager import load_settings

        settings = load_settings()
        if hasattr(settings, "language") and settings.language:
            set_current_language(settings.language)
    except Exception:
        pass  # Keep default English
