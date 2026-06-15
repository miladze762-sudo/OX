# Telegram Podcast Digest

## Краткое описание
Нужно создать локальную CLI-программу на Python 3.11+ для Windows, которая автоматизирует цепочку:

аудио из Telegram-канала -> конвертация в MP3 -> отдельный блокнот NotebookLM для каждого аудио -> русское текстовое резюме + MP3 аудиообзора из NotebookLM -> отправка через Telegram-бота.

Первая версия использует:
- пользовательский API Telethon для чтения и скачивания медиа из исходного канала;
- `ffmpeg` для нормализации MP3;
- неофициальный Python API `notebooklm-py` для NotebookLM;
- Telegram Bot API только для отправки итоговых материалов;
- SQLite для идемпотентного состояния и повторных попыток;
- Windows Task Scheduler для ежедневных запусков.

## Основные изменения
- Создать пакет `telegram_podcast_digest` с CLI-командой `tg-podcast-digest`.
- CLI-команды:
  - `doctor`: проверить `.env`, ffmpeg, Telegram-сессию, хранилище NotebookLM и конфигурацию бота для вывода.
  - `setup-telegram`: интерактивный вход через Telethon, сохранение `data/telegram.session`.
  - `run-once --dry-run --max-messages N`: найти и обработать новые аудио из канала.
  - `cleanup`: опциональная очистка старых локальных файлов; блокноты NotebookLM по умолчанию сохраняются.
- `.env.example` включает:
  - `TG_API_ID`, `TG_API_HASH`, `TG_SOURCE_CHAT`, `TG_SESSION_PATH`
  - `NOTEBOOKLM_STORAGE_PATH`
  - `TELEGRAM_BOT_TOKEN`, `TELEGRAM_OUTPUT_CHAT_ID`
  - `DATABASE_PATH`, `DOWNLOAD_DIR`, `CONVERTED_DIR`, `EXPORT_DIR`
  - `MAX_MESSAGES_PER_RUN`, `NOTEBOOK_RETENTION_DAYS=0`
- SQLite отслеживает каждое сообщение Telegram по `(chat_id, message_id)`: статус, путь к исходному файлу, путь к MP3, id блокнота, id источника, резюме, путь к сгенерированному подкасту, id отправленных сообщений в Telegram, ошибку и временные метки.

## Пайплайн
- Загрузка из Telegram:
  - Использовать Telethon `iter_messages` для `TG_SOURCE_CHAT`.
  - Фильтровать сообщения с audio/document media по аудиорасширениям или MIME-типам.
  - Скачивать каждый новый файл в `downloads/` с детерминированными именами.
- Конвертация аудио:
  - Конвертировать каждый исходный файл в MP3 через ffmpeg:
    `ffmpeg -y -i INPUT -vn -codec:a libmp3lame -b:a 96k -ar 44100 OUTPUT.mp3`
  - Хранить оригиналы и сконвертированные MP3 локально; все медиа-папки остаются в Git ignore.
- NotebookLM:
  - Использовать `NotebookLMClient.from_storage(NOTEBOOKLM_STORAGE_PATH)`.
  - Создавать один блокнот для каждого сконвертированного MP3.
  - Загружать MP3 как источник через `client.sources.add_file(..., wait=True, upload_timeout=600.0)`.
  - Запрашивать у NotebookLM структурированное текстовое резюме на русском.
  - Генерировать аудиообзор NotebookLM с русской инструкцией на подкаст в формате подробного разбора примерно на 20 минут.
  - Ждать до 30 минут и скачивать сгенерированный MP3 в `exports/`.
- Вывод в Telegram:
  - Отправлять сгенерированный MP3-подкаст через `sendAudio`.
  - Отправлять короткую подпись и полное текстовое резюме частями через `sendMessage`, если это нужно из-за лимитов.
  - Помечать сообщение обработанным только после успешной отправки в Telegram.

## План тестирования
- Юнит-тесты:
  - парсинг `.env` и валидация `doctor`;
  - фильтрация сообщений Telegram и детерминированные имена файлов;
  - идемпотентность SQLite: отсутствие повторной обработки, повтор неудачных сообщений, переиспользование существующих id блокнотов;
  - сборка команды ffmpeg с замоканным subprocess;
  - адаптер NotebookLM с фейковым async-клиентом;
  - разбиение сообщений отправителя Telegram и защита от выходного файла больше 50 МБ.
- Ручная приемка:
  - `tg-podcast-digest doctor` проходит успешно.
  - `tg-podcast-digest run-once --dry-run` показывает ожидаемые аудио из канала.
  - Один реальный запуск создает локальный MP3, отдельный блокнот NotebookLM, текстовое резюме, сгенерированный MP3 аудиообзора и отправляет резюме и аудио в Telegram.
  - Повторный запуск не дублирует то же самое сообщение Telegram.

## Допущения
- Используется Python-пайплайн, а не CLI-обертка.
- Для входа используется пользовательский API Telegram, для выхода - Bot API.
- В качестве подкаста используется аудиообзор NotebookLM; длительность приблизительная и не гарантируется ровно 20:00.
- Блокноты NotebookLM по умолчанию сохраняются, потому что для каждого MP3 нужен отдельный блокнот.
- `notebooklm-py` - неофициальная библиотека, она может сломаться, если Google изменит внутренние API.
- Использованные источники: `notebooklm-py` https://github.com/teng-lin/notebooklm-py, NoteDoom https://github.com/miladze762-sudo/NoteDoom, документация Telethon https://docs.telethon.dev/, документация FFmpeg https://ffmpeg.org/ffmpeg.html, Telegram Bot API https://core.telegram.org/bots/api.
