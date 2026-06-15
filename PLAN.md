# План реализации Telegram Podcast Digest

> **Для агентных исполнителей:** ОБЯЗАТЕЛЬНЫЙ ПОДНАВЫК: используйте superpowers:subagent-driven-development (рекомендуется) или superpowers:executing-plans, чтобы выполнять этот план по задачам. Шаги используют чекбоксы (`- [ ]`) для отслеживания.

**Цель:** довести локальную Python CLI `tg-podcast-digest` до надежной версии для ежедневной обработки аудио из Telegram: скачать, конвертировать в MP3, прогнать через NotebookLM, отправить результат в Telegram и отдать машинно-читаемый результат для автоматизации.

**Архитектура:** ядро остается в `PodcastPipeline`, а Telegram, ffmpeg, NotebookLM и Telegram Bot API остаются адаптерами за маленькими портами. SQLite хранит идемпотентное состояние по `(chat_id, message_id)`, CLI и HTTP-слой только запускают пайплайн и сериализуют `RunResult`.

**Стек:** Python 3.11+, `unittest`, `argparse`, `sqlite3`, `Telethon`, `requests`, `notebooklm-py`, `ffmpeg`, `http.server` из стандартной библиотеки.

---

## Текущая База

- Рабочая папка: `C:\Users\Admin\Desktop\сжатие подкастов из телеги`.
- Текущая проверка: `python -m unittest discover -s tests -v`.
- На 15 июня 2026 команда проходит: 18 тестов, `OK`.
- `pytest` в текущем окружении не установлен, поэтому все шаги ниже используют `unittest`.
- `PLAN.md` не отслеживается git (`?? PLAN.md`), поэтому при исполнении не смешивать его коммит с кодом, если план не нужен в истории.

## Структура Файлов

- Изменить: `src/tg_podcast_digest/models.py`  
  Ответственность: общие DTO `AudioItem`, `NotebookResult`, `RunResult`, сериализация результата запуска в JSON-совместимый `dict`.
- Изменить: `src/tg_podcast_digest/pipeline.py`  
  Ответственность: оркестрация одного запуска, расчет статуса, сбор обработанных сообщений и ошибок.
- Изменить: `src/tg_podcast_digest/cli.py`  
  Ответственность: команды `doctor`, `setup-telegram`, `run-once`, `cleanup`, `serve`; текстовый и JSON-вывод.
- Изменить: `src/tg_podcast_digest/config.py`  
  Ответственность: чтение `.env`, включая HTTP-настройки для n8n/внешнего запуска.
- Изменить: `src/tg_podcast_digest/notebooklm_client.py`  
  Ответственность: генерация заголовков, промптов и адаптер NotebookLM с тестируемой фабрикой клиента.
- Создать: `src/tg_podcast_digest/http_server.py`  
  Ответственность: минимальный HTTP API `GET /health`, `POST /run-once`, `GET /runs/{run_id}` с авторизацией по Bearer-токену.
- Создать: `tests/test_cli.py`  
  Ответственность: CLI-контракт `run-once --json`, коды выхода и отсутствие внешних сетевых вызовов через подмену билдеров.
- Создать: `tests/test_notebooklm_client.py`  
  Ответственность: чистые функции NotebookLM и асинхронный сценарий через фейковый клиент.
- Создать: `tests/test_http_server.py`  
  Ответственность: чистая логика HTTP-запросов без поднятия реального порта.
- Создать: `tests/test_cleanup.py`  
  Ответственность: удаление старых файлов и сохранение свежих файлов.
- Изменить: `.env.example`  
  Ответственность: полный список переменных конфигурации, включая HTTP.
- Изменить: `README.md`  
  Ответственность: установка, ручной запуск, JSON-вывод, Планировщик заданий Windows, сценарий HTTP/n8n, чеклист приемки.

## Правила Выполнения

- Каждое изменение рабочего кода начинается с красной фазы: написать один минимальный тест и увидеть ожидаемое падение.
- После зеленой фазы запускать точечный тест, затем весь набор тестов: `python -m unittest discover -s tests -v`.
- Коммитить после каждой задачи, когда весь набор тестов зеленый.
- Не использовать реальные Telegram, NotebookLM или Telegram Bot API в модульных тестах.
- Ручная приемка с реальными учетными данными выполняется только после зеленого набора модульных тестов.

---

### Задача 1: Машинно-Читаемый `run-once --json`

**Файлы:**
- Создать: `tests/test_cli.py`
- Изменить: `src/tg_podcast_digest/models.py`
- Изменить: `src/tg_podcast_digest/pipeline.py`
- Изменить: `src/tg_podcast_digest/cli.py`

- [ ] **Шаг 1: Написать падающие тесты CLI JSON**

Создать `tests/test_cli.py`:

```python
import io
import json
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from tg_podcast_digest import cli


class FakePipeline:
    def __init__(self, result):
        self.result = result
        self.calls = []

    async def run_once(self, dry_run=False, max_messages=10):
        self.calls.append((dry_run, max_messages))
        return self.result


def fake_settings():
    return SimpleNamespace(max_messages_per_run=10)


class CliTests(unittest.TestCase):
    def test_run_once_json_outputs_stable_machine_readable_result(self):
        result = SimpleNamespace(
            run_id="run-123",
            status="success",
            processed_count=1,
            skipped_count=0,
            failed_count=0,
            processed_messages=[
                {
                    "chat_id": "chat",
                    "message_id": 7,
                    "title": "Episode",
                    "status": "processed",
                    "notebook_url": "https://notebook/7",
                    "error": None,
                }
            ],
            errors=[],
            dry_run_items=[],
            started_at="2026-06-15T10:00:00+00:00",
            finished_at="2026-06-15T10:00:01+00:00",
        )
        pipeline = FakePipeline(result)
        stdout = io.StringIO()

        with patch.object(cli, "load_settings", return_value=fake_settings()):
            with patch.object(cli, "_build_pipeline", return_value=pipeline):
                with redirect_stdout(stdout):
                    exit_code = cli.main(["--env", "ignored.env", "run-once", "--json", "--max-messages", "3"])

        payload = json.loads(stdout.getvalue())
        self.assertEqual(0, exit_code)
        self.assertEqual("run-123", payload["run_id"])
        self.assertEqual("success", payload["status"])
        self.assertEqual(1, payload["processed_count"])
        self.assertEqual(0, payload["failed_count"])
        self.assertEqual("Episode", payload["processed_messages"][0]["title"])
        self.assertEqual([(False, 3)], pipeline.calls)

    def test_run_once_json_returns_nonzero_when_errors_exist(self):
        result = SimpleNamespace(
            run_id="run-456",
            status="failed",
            processed_count=0,
            skipped_count=0,
            failed_count=1,
            processed_messages=[],
            errors=["chat/8: NotebookLM failed"],
            dry_run_items=[],
            started_at="2026-06-15T10:00:00+00:00",
            finished_at="2026-06-15T10:00:01+00:00",
        )
        pipeline = FakePipeline(result)
        stdout = io.StringIO()

        with patch.object(cli, "load_settings", return_value=fake_settings()):
            with patch.object(cli, "_build_pipeline", return_value=pipeline):
                with redirect_stdout(stdout):
                    exit_code = cli.main(["--env", "ignored.env", "run-once", "--json"])

        payload = json.loads(stdout.getvalue())
        self.assertEqual(1, exit_code)
        self.assertEqual("failed", payload["status"])
        self.assertEqual(["chat/8: NotebookLM failed"], payload["errors"])
        self.assertEqual([(False, 10)], pipeline.calls)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Шаг 2: Запустить новый тест и проверить красную фазу**

Запустить:

```powershell
python -m unittest tests.test_cli -v
```

Ожидается: FAIL или ERROR, потому что `run-once` еще не принимает `--json`.

- [ ] **Шаг 3: Расширить общие модели запуска**

Изменить `src/tg_podcast_digest/models.py`:

```python
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class AudioItem:
    chat_id: str
    message_id: int
    title: str
    message_date: str | None
    file_name: str | None
    mime_type: str | None


@dataclass(frozen=True)
class NotebookResult:
    notebook_id: str
    notebook_url: str
    summary: str
    podcast_path: Path


@dataclass(frozen=True)
class ProcessedMessage:
    chat_id: str
    message_id: int
    title: str
    status: str
    notebook_url: str | None = None
    error: str | None = None


@dataclass(frozen=True)
class RunResult:
    run_id: str = ""
    status: str = "success"
    processed_count: int = 0
    skipped_count: int = 0
    failed_count: int = 0
    processed_messages: list[ProcessedMessage] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    dry_run_items: list[AudioItem] = field(default_factory=list)
    started_at: str | None = None
    finished_at: str | None = None


def run_result_to_dict(result: RunResult) -> dict[str, object]:
    return {
        "run_id": result.run_id,
        "status": result.status,
        "processed_count": result.processed_count,
        "skipped_count": result.skipped_count,
        "failed_count": result.failed_count,
        "processed_messages": [
            asdict(message) if not isinstance(message, dict) else message
            for message in result.processed_messages
        ],
        "errors": result.errors,
        "dry_run_items": [
            asdict(item) if not isinstance(item, dict) else item
            for item in result.dry_run_items
        ],
        "started_at": result.started_at,
        "finished_at": result.finished_at,
    }
```

- [ ] **Шаг 4: Добавить метаданные запуска в пайплайн**

Изменить импорты и `run_once` в `src/tg_podcast_digest/pipeline.py`:

```python
from datetime import datetime, timezone
from uuid import uuid4

from .models import AudioItem, NotebookResult, ProcessedMessage, RunResult
```

Заменить `run_once` на:

```python
    async def run_once(self, dry_run: bool = False, max_messages: int = 10) -> RunResult:
        self._state.initialize()
        started_at = _utcnow()
        run_id = f"run-{uuid4().hex}"
        items = await self._source.list_audio(max_messages)
        if dry_run:
            return RunResult(
                run_id=run_id,
                status="dry_run" if items else "nothing_to_do",
                dry_run_items=items,
                started_at=started_at,
                finished_at=_utcnow(),
            )

        processed = 0
        skipped = 0
        processed_messages: list[ProcessedMessage] = []
        errors: list[str] = []
        for audio in items:
            if not self._state.claim_message(audio.chat_id, audio.message_id, audio.title, audio.message_date):
                skipped += 1
                processed_messages.append(
                    ProcessedMessage(
                        chat_id=audio.chat_id,
                        message_id=audio.message_id,
                        title=audio.title,
                        status="skipped",
                    )
                )
                continue
            try:
                source_path = await self._source.download_audio(audio, self._download_dir)
                self._state.mark_downloaded(audio.chat_id, audio.message_id, source_path)

                mp3_path = self._converter.convert_to_mp3(source_path, self._converted_dir)
                self._state.mark_converted(audio.chat_id, audio.message_id, mp3_path)

                notebook_result = await self._notebook.create_summary_and_podcast(
                    audio,
                    mp3_path,
                    self._export_dir,
                )
                self._state.mark_notebook_ready(
                    audio.chat_id,
                    audio.message_id,
                    notebook_result.notebook_id,
                    notebook_result.notebook_url,
                )
                self._state.mark_summary_ready(audio.chat_id, audio.message_id, notebook_result.summary)
                self._state.mark_podcast_ready(audio.chat_id, audio.message_id, notebook_result.podcast_path)

                sent_ids = self._sender.send_podcast(
                    audio.title,
                    notebook_result.summary,
                    notebook_result.podcast_path,
                    notebook_result.notebook_url,
                )
                self._state.mark_sent(audio.chat_id, audio.message_id, sent_ids)
                processed += 1
                processed_messages.append(
                    ProcessedMessage(
                        chat_id=audio.chat_id,
                        message_id=audio.message_id,
                        title=audio.title,
                        status="processed",
                        notebook_url=notebook_result.notebook_url,
                    )
                )
            except Exception as exc:  # noqa: BLE001 - keep one bad audio from stopping the batch.
                message = f"{audio.chat_id}/{audio.message_id}: {exc}"
                errors.append(message)
                processed_messages.append(
                    ProcessedMessage(
                        chat_id=audio.chat_id,
                        message_id=audio.message_id,
                        title=audio.title,
                        status="failed",
                        error=message,
                    )
                )
                self._state.mark_failed(audio.chat_id, audio.message_id, message)

        failed_count = len(errors)
        return RunResult(
            run_id=run_id,
            status=_run_status(processed, skipped, failed_count, len(items)),
            processed_count=processed,
            skipped_count=skipped,
            failed_count=failed_count,
            processed_messages=processed_messages,
            errors=errors,
            started_at=started_at,
            finished_at=_utcnow(),
        )
```

Добавить вспомогательные функции в конец `pipeline.py`:

```python
def _run_status(processed: int, skipped: int, failed: int, total: int) -> str:
    if total == 0:
        return "nothing_to_do"
    if failed and processed:
        return "partial_success"
    if failed:
        return "failed"
    if processed == 0 and skipped > 0:
        return "nothing_to_do"
    return "success"


def _utcnow() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
```

- [ ] **Шаг 5: Добавить `--json` в вывод CLI**

Изменить импорты в `src/tg_podcast_digest/cli.py`:

```python
import json
```

Добавить:

```python
from .models import run_result_to_dict
```

В `_build_parser` добавить аргумент:

```python
    run_once.add_argument("--json", action="store_true", dest="json_output")
```

В `main` заменить блок вывода `run-once` на:

```python
        if args.command == "run-once":
            pipeline = _build_pipeline(settings)
            max_messages = args.max_messages or settings.max_messages_per_run
            result = asyncio.run(pipeline.run_once(dry_run=args.dry_run, max_messages=max_messages))
            if args.json_output:
                print(json.dumps(run_result_to_dict(result), ensure_ascii=False))
            elif args.dry_run:
                for item in result.dry_run_items:
                    print(f"DRY RUN: {item.chat_id}/{item.message_id} | {item.title}")
                print(f"dry_run_count={len(result.dry_run_items)}")
            else:
                print(
                    f"processed={result.processed_count} "
                    f"skipped={result.skipped_count} errors={len(result.errors)}"
                )
                for error in result.errors:
                    print(f"ERROR: {error}")
            return 1 if result.errors else 0
```

- [ ] **Шаг 6: Проверить зеленую фазу**

Запустить:

```powershell
python -m unittest tests.test_cli -v
python -m unittest discover -s tests -v
```

Ожидается: все тесты проходят, включая 18 существующих тестов.

- [ ] **Шаг 7: Сделать коммит**

Запустить:

```powershell
git add src/tg_podcast_digest/models.py src/tg_podcast_digest/pipeline.py src/tg_podcast_digest/cli.py tests/test_cli.py
git commit -m "feat: add json run result output"
```

---

### Задача 2: Тестируемый Шов Адаптера NotebookLM

**Файлы:**
- Создать: `tests/test_notebooklm_client.py`
- Изменить: `src/tg_podcast_digest/notebooklm_client.py`

- [ ] **Шаг 1: Написать падающие тесты NotebookLM**

Создать `tests/test_notebooklm_client.py`:

```python
import asyncio
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from tg_podcast_digest.models import AudioItem
from tg_podcast_digest.notebooklm_client import (
    NotebookLMProcessor,
    build_notebook_title,
    build_podcast_prompt,
    build_summary_prompt,
)


def item():
    return AudioItem(
        chat_id="chat",
        message_id=42,
        title="Episode about AI",
        message_date="2026-06-15",
        file_name='My: "Episode"?.mp3',
        mime_type="audio/mpeg",
    )


class FakeNotebook:
    id = "nb-42"


class FakeSource:
    id = "source-42"


class FakeAnswer:
    answer = "summary text"


class FakeNotebooks:
    def __init__(self):
        self.created_titles = []

    async def create(self, title):
        self.created_titles.append(title)
        return FakeNotebook()


class FakeSources:
    def __init__(self):
        self.uploads = []

    async def add_file(self, notebook_id, mp3_path, title, wait, wait_timeout, upload_timeout):
        self.uploads.append((notebook_id, mp3_path, title, wait, wait_timeout, upload_timeout))
        return FakeSource()


class FakeChat:
    def __init__(self):
        self.questions = []

    async def ask(self, notebook_id, prompt, source_ids=None):
        self.questions.append((notebook_id, prompt, source_ids))
        return FakeAnswer()


class FakeStatus:
    task_id = "task-42"


class FakeArtifacts:
    def __init__(self):
        self.generated = []
        self.waited = []
        self.downloads = []

    async def generate_audio(self, notebook_id, instructions):
        self.generated.append((notebook_id, instructions))
        return FakeStatus()

    async def wait_for_completion(self, notebook_id, task_id, timeout):
        self.waited.append((notebook_id, task_id, timeout))

    async def download_audio(self, notebook_id, output_path):
        self.downloads.append((notebook_id, output_path))
        path = Path(output_path)
        path.write_bytes(b"podcast")
        return path


class FakeClient:
    def __init__(self):
        self.notebooks = FakeNotebooks()
        self.sources = FakeSources()
        self.chat = FakeChat()
        self.artifacts = FakeArtifacts()


class FakeContext:
    def __init__(self, client):
        self.client = client

    async def __aenter__(self):
        return self.client

    async def __aexit__(self, exc_type, exc, tb):
        return False


class NotebookLMClientTests(unittest.TestCase):
    def test_build_notebook_title_is_safe_and_deterministic(self):
        title = build_notebook_title(item())

        self.assertEqual("Telegram Podcast - 2026-06-15 - 42 - My - Episode - .mp3", title)
        self.assertLessEqual(len(title), 120)

    def test_prompts_are_russian_and_reference_title(self):
        summary_prompt = build_summary_prompt(item())
        podcast_prompt = build_podcast_prompt(item())

        self.assertIn("Episode about AI", summary_prompt)
        self.assertIn("по-русски", summary_prompt)
        self.assertIn("20 минут", podcast_prompt)
        self.assertIn("не выдумывай", podcast_prompt)

    def test_processor_uses_injected_client_and_exports_audio(self):
        with tempfile.TemporaryDirectory() as tmp:
            client = FakeClient()
            storage_calls = []

            def client_factory(path, keepalive):
                storage_calls.append((path, keepalive))
                return FakeContext(client)

            mp3_path = Path(tmp) / "episode.mp3"
            mp3_path.write_bytes(b"mp3")
            processor = NotebookLMProcessor(
                storage_path=Path("data/notebooklm.json"),
                wait_timeout=12.0,
                client_factory=client_factory,
            )

            result = asyncio.run(processor.create_summary_and_podcast(item(), mp3_path, Path(tmp) / "exports"))

        self.assertEqual([("data/notebooklm.json", 300.0)], storage_calls)
        self.assertEqual("nb-42", result.notebook_id)
        self.assertEqual("https://notebooklm.google.com/notebook/nb-42", result.notebook_url)
        self.assertEqual("summary text", result.summary)
        self.assertEqual(Path(tmp) / "exports" / "chat_42_notebooklm.mp3", result.podcast_path)
        self.assertEqual([("nb-42", mp3_path, 'My: "Episode"?.mp3', True, 600.0, 600.0)], client.sources.uploads)
        self.assertEqual("source-42", client.chat.questions[0][2][0])
        self.assertEqual([("nb-42", "task-42", 12.0)], client.artifacts.waited)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Шаг 2: Запустить новый тест и проверить красную фазу**

Запустить:

```powershell
python -m unittest tests.test_notebooklm_client -v
```

Ожидается: ERROR, потому что `NotebookLMProcessor.__init__` еще не принимает `client_factory`.

- [ ] **Шаг 3: Добавить внедряемую фабрику клиента NotebookLM**

Изменить импорты и инициализацию класса в `src/tg_podcast_digest/notebooklm_client.py`:

```python
from typing import Any, Callable
```

Добавить ближе к началу файла:

```python
NotebookClientFactory = Callable[[str | None, float], Any]
```

Заменить `build_notebook_title` на:

```python
def build_notebook_title(item: AudioItem) -> str:
    date_part = item.message_date or "no-date"
    name_part = item.file_name or item.title or "audio"
    title = f"Telegram Podcast - {date_part} - {item.message_id} - {name_part}"
    title = re.sub(r'[\\/:*?"<>|]+', " - ", title)
    title = re.sub(r"\s+", " ", title)
    title = re.sub(r"\s*-\s*(?:-\s*)+", " - ", title)
    return title.strip(" -")[:120]
```

Заменить `NotebookLMProcessor` на:

```python
class NotebookLMProcessor:
    def __init__(
        self,
        storage_path: Path | None = None,
        wait_timeout: float = 1800.0,
        client_factory: NotebookClientFactory | None = None,
    ) -> None:
        self._storage_path = storage_path
        self._wait_timeout = wait_timeout
        self._client_factory = client_factory or _default_client_factory

    async def create_summary_and_podcast(
        self,
        item: AudioItem,
        mp3_path: Path,
        export_dir: Path,
    ) -> NotebookResult:
        export_dir.mkdir(parents=True, exist_ok=True)
        notebook_title = build_notebook_title(item)
        storage = str(self._storage_path) if self._storage_path else None
        async with self._client_factory(storage, 300.0) as client:
            notebook = await client.notebooks.create(notebook_title)
            source = await client.sources.add_file(
                notebook.id,
                mp3_path,
                title=item.file_name or mp3_path.name,
                wait=True,
                wait_timeout=600.0,
                upload_timeout=600.0,
            )
            source_id = getattr(source, "id", None)
            source_ids = [source_id] if source_id else None
            if source_ids:
                answer = await client.chat.ask(notebook.id, build_summary_prompt(item), source_ids=source_ids)
            else:
                answer = await client.chat.ask(notebook.id, build_summary_prompt(item))
            status = await client.artifacts.generate_audio(
                notebook.id,
                instructions=build_podcast_prompt(item),
            )
            await client.artifacts.wait_for_completion(
                notebook.id,
                status.task_id,
                timeout=self._wait_timeout,
            )
            podcast_path = export_dir / f"{item.chat_id}_{item.message_id}_notebooklm.mp3"
            downloaded = await client.artifacts.download_audio(notebook.id, str(podcast_path))
            return NotebookResult(
                notebook_id=notebook.id,
                notebook_url=f"https://notebooklm.google.com/notebook/{notebook.id}",
                summary=answer.answer,
                podcast_path=Path(downloaded),
            )
```

Добавить фабрику по умолчанию после класса:

```python
def _default_client_factory(storage_path: str | None, keepalive: float) -> Any:
    try:
        from notebooklm import NotebookLMClient
    except ImportError as exc:
        raise RuntimeError("notebooklm-py is missing. Run: python -m pip install -e .") from exc
    return NotebookLMClient.from_storage(path=storage_path, keepalive=keepalive)
```

- [ ] **Шаг 4: Проверить зеленую фазу**

Запустить:

```powershell
python -m unittest tests.test_notebooklm_client -v
python -m unittest discover -s tests -v
```

Ожидается: все тесты проходят.

- [ ] **Шаг 5: Сделать коммит**

Запустить:

```powershell
git add src/tg_podcast_digest/notebooklm_client.py tests/test_notebooklm_client.py
git commit -m "test: cover notebooklm adapter flow"
```

---

### Задача 3: HTTP-Запуск Для n8n И Удаленных Триггеров

**Файлы:**
- Создать: `tests/test_http_server.py`
- Создать: `src/tg_podcast_digest/http_server.py`
- Изменить: `src/tg_podcast_digest/config.py`
- Изменить: `src/tg_podcast_digest/cli.py`
- Изменить: `.env.example`

- [ ] **Шаг 1: Написать падающие тесты чистого HTTP-обработчика**

Создать `tests/test_http_server.py`:

```python
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from tg_podcast_digest.models import RunResult
from tg_podcast_digest.http_server import handle_request


class FakeRunner:
    def __init__(self):
        self.calls = []

    def __call__(self, dry_run=False, max_messages=10):
        self.calls.append((dry_run, max_messages))
        return RunResult(
            run_id="run-http",
            status="dry_run",
            dry_run_items=[],
            started_at="2026-06-15T10:00:00+00:00",
            finished_at="2026-06-15T10:00:01+00:00",
        )


class HttpServerTests(unittest.TestCase):
    def test_health_requires_bearer_token(self):
        response = handle_request(
            method="GET",
            path="/health",
            headers={},
            body=b"",
            auth_token="secret",
            run_once=FakeRunner(),
        )

        self.assertEqual(401, response.status_code)
        self.assertEqual({"error": "unauthorized"}, json.loads(response.body.decode("utf-8")))

    def test_health_returns_ok_when_authorized(self):
        response = handle_request(
            method="GET",
            path="/health",
            headers={"authorization": "Bearer secret"},
            body=b"",
            auth_token="secret",
            run_once=FakeRunner(),
        )

        self.assertEqual(200, response.status_code)
        self.assertEqual({"status": "ok"}, json.loads(response.body.decode("utf-8")))

    def test_post_run_once_parses_json_body_and_returns_run_result(self):
        runner = FakeRunner()
        response = handle_request(
            method="POST",
            path="/run-once",
            headers={"authorization": "Bearer secret", "content-type": "application/json"},
            body=json.dumps({"dry_run": True, "max_messages": 2}).encode("utf-8"),
            auth_token="secret",
            run_once=runner,
        )

        payload = json.loads(response.body.decode("utf-8"))
        self.assertEqual(200, response.status_code)
        self.assertEqual("run-http", payload["run_id"])
        self.assertEqual("dry_run", payload["status"])
        self.assertEqual([(True, 2)], runner.calls)

    def test_unknown_route_returns_404(self):
        response = handle_request(
            method="GET",
            path="/missing",
            headers={"authorization": "Bearer secret"},
            body=b"",
            auth_token="secret",
            run_once=FakeRunner(),
        )

        self.assertEqual(404, response.status_code)
        self.assertEqual({"error": "not_found"}, json.loads(response.body.decode("utf-8")))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Шаг 2: Запустить новый тест и проверить красную фазу**

Запустить:

```powershell
python -m unittest tests.test_http_server -v
```

Ожидается: ERROR, потому что `tg_podcast_digest.http_server` еще не существует.

- [ ] **Шаг 3: Реализовать чистую логику HTTP-запросов и обертку сервера из стандартной библиотеки**

Создать `src/tg_podcast_digest/http_server.py`:

```python
from __future__ import annotations

import json
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Callable
from urllib.parse import urlparse

from .models import RunResult, run_result_to_dict


RunOnceCallable = Callable[[bool, int], RunResult]


@dataclass(frozen=True)
class HttpResponse:
    status_code: int
    body: bytes
    content_type: str = "application/json; charset=utf-8"


def handle_request(
    method: str,
    path: str,
    headers: dict[str, str],
    body: bytes,
    auth_token: str,
    run_once: RunOnceCallable,
) -> HttpResponse:
    if not _authorized(headers, auth_token):
        return _json_response(401, {"error": "unauthorized"})

    route = urlparse(path).path
    if method == "GET" and route == "/health":
        return _json_response(200, {"status": "ok"})

    if method == "POST" and route == "/run-once":
        try:
            payload = json.loads(body.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            return _json_response(400, {"error": "invalid_json"})
        dry_run = bool(payload.get("dry_run", False))
        max_messages = int(payload.get("max_messages", 10))
        result = run_once(dry_run, max_messages)
        return _json_response(200, run_result_to_dict(result))

    if method == "GET" and route.startswith("/runs/"):
        return _json_response(200, {"status": "completed", "run_id": route.rsplit("/", 1)[-1]})

    return _json_response(404, {"error": "not_found"})


def serve_http(host: str, port: int, auth_token: str, run_once: RunOnceCallable) -> None:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            self._respond()

        def do_POST(self) -> None:
            self._respond()

        def log_message(self, format: str, *args: object) -> None:
            return

        def _respond(self) -> None:
            length = int(self.headers.get("content-length", "0"))
            body = self.rfile.read(length) if length else b""
            response = handle_request(
                method=self.command,
                path=self.path,
                headers={key.lower(): value for key, value in self.headers.items()},
                body=body,
                auth_token=auth_token,
                run_once=run_once,
            )
            self.send_response(response.status_code)
            self.send_header("Content-Type", response.content_type)
            self.send_header("Content-Length", str(len(response.body)))
            self.end_headers()
            self.wfile.write(response.body)

    server = ThreadingHTTPServer((host, port), Handler)
    server.serve_forever()


def _authorized(headers: dict[str, str], auth_token: str) -> bool:
    if not auth_token:
        return False
    return headers.get("authorization") == f"Bearer {auth_token}"


def _json_response(status_code: int, payload: dict[str, object]) -> HttpResponse:
    return HttpResponse(
        status_code=status_code,
        body=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
    )
```

- [ ] **Шаг 4: Добавить HTTP-настройки**

Изменить `Settings` в `src/tg_podcast_digest/config.py`:

```python
    http_host: str = "127.0.0.1"
    http_port: int = 8787
    http_auth_token: str = ""
```

В `load_settings` добавить:

```python
        http_host=values.get("HTTP_HOST", "127.0.0.1"),
        http_port=int(values.get("HTTP_PORT", "8787")),
        http_auth_token=values.get("HTTP_AUTH_TOKEN", ""),
```

Добавить в `.env.example`:

```dotenv
HTTP_HOST=127.0.0.1
HTTP_PORT=8787
HTTP_AUTH_TOKEN=change-me-local-token
```

- [ ] **Шаг 5: Добавить CLI-команду `serve`**

Изменить импорты в `src/tg_podcast_digest/cli.py`:

```python
from .http_server import serve_http
```

В `_build_parser` добавить:

```python
    subparsers.add_parser("serve", help="Run local HTTP API for n8n or remote triggers")
```

В `main` перед `cleanup` добавить:

```python
        if args.command == "serve":
            if not settings.http_auth_token:
                raise ValueError("HTTP_AUTH_TOKEN is required for serve")
            pipeline = _build_pipeline(settings)

            def run_once(dry_run: bool = False, max_messages: int = 10):
                return asyncio.run(pipeline.run_once(dry_run=dry_run, max_messages=max_messages))

            print(f"serving http://{settings.http_host}:{settings.http_port}")
            serve_http(settings.http_host, settings.http_port, settings.http_auth_token, run_once)
            return 0
```

- [ ] **Шаг 6: Проверить зеленую фазу**

Запустить:

```powershell
python -m unittest tests.test_http_server -v
python -m unittest discover -s tests -v
```

Ожидается: все тесты проходят.

- [ ] **Шаг 7: Сделать коммит**

Запустить:

```powershell
git add src/tg_podcast_digest/http_server.py src/tg_podcast_digest/config.py src/tg_podcast_digest/cli.py tests/test_http_server.py .env.example
git commit -m "feat: add local http runner"
```

---

### Задача 4: Покрытие Очистки И Безопасность Хранения

**Файлы:**
- Создать: `tests/test_cleanup.py`
- Изменить: `src/tg_podcast_digest/cleanup.py`

- [ ] **Шаг 1: Написать падающие тесты очистки**

Создать `tests/test_cleanup.py`:

```python
import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from tg_podcast_digest.cleanup import cleanup_old_files


def set_mtime(path: Path, when: datetime) -> None:
    timestamp = when.timestamp()
    os.utime(path, (timestamp, timestamp))


class CleanupTests(unittest.TestCase):
    def test_cleanup_deletes_old_files_and_keeps_recent_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            old_file = root / "old.mp3"
            recent_file = root / "recent.mp3"
            nested_file = root / "nested" / "old.txt"
            nested_file.parent.mkdir()
            old_file.write_bytes(b"old")
            recent_file.write_bytes(b"recent")
            nested_file.write_bytes(b"nested")

            now = datetime.now(timezone.utc)
            set_mtime(old_file, now - timedelta(days=40))
            set_mtime(recent_file, now - timedelta(days=2))
            set_mtime(nested_file, now - timedelta(days=45))

            deleted = cleanup_old_files([root], retention_days=30)

        self.assertEqual(2, deleted)
        self.assertFalse(old_file.exists())
        self.assertTrue(recent_file.exists())
        self.assertFalse(nested_file.exists())

    def test_cleanup_does_nothing_when_retention_is_zero(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            old_file = root / "old.mp3"
            old_file.write_bytes(b"old")
            set_mtime(old_file, datetime.now(timezone.utc) - timedelta(days=400))

            deleted = cleanup_old_files([root], retention_days=0)

        self.assertEqual(0, deleted)
        self.assertTrue(old_file.exists())


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Шаг 2: Запустить новый тест и проверить красную фазу**

Запустить:

```powershell
python -m unittest tests.test_cleanup -v
```

Ожидается: первый тест может уже проходить; если он сразу проходит, добавьте этот более строгий падающий тест до изменения рабочего кода:

```python
    def test_cleanup_ignores_missing_roots(self):
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / "missing"

            deleted = cleanup_old_files([missing], retention_days=30)

        self.assertEqual(0, deleted)
```

Запустить еще раз:

```powershell
python -m unittest tests.test_cleanup -v
```

Ожидается: тесты документируют существующее поведение. Если все тесты проходят, изменение рабочего кода для этой задачи не требуется.

- [ ] **Шаг 3: Держать рабочий код минимальным**

Если все тесты очистки проходят, оставить `src/tg_podcast_digest/cleanup.py` без изменений.

Если точность файловых меток времени в Windows вызывает пограничное падение, изменить только сравнение в `cleanup_old_files`:

```python
            if modified < cutoff:
                file_path.unlink()
                deleted += 1
```

- [ ] **Шаг 4: Проверить зеленую фазу**

Запустить:

```powershell
python -m unittest tests.test_cleanup -v
python -m unittest discover -s tests -v
```

Ожидается: все тесты проходят.

- [ ] **Шаг 5: Сделать коммит**

Запустить:

```powershell
git add tests/test_cleanup.py src/tg_podcast_digest/cleanup.py
git commit -m "test: cover cleanup retention behavior"
```

---

### Задача 5: Документация И Чеклист Ручной Приемки

**Файлы:**
- Изменить: `README.md`
- Изменить: `.env.example`

- [ ] **Шаг 1: Написать падающую проверку документации**

Создать `tests/test_docs.py`:

```python
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


class DocumentationTests(unittest.TestCase):
    def test_readme_documents_operational_commands(self):
        readme = Path("README.md").read_text(encoding="utf-8")

        self.assertIn("tg-podcast-digest run-once --json", readme)
        self.assertIn("tg-podcast-digest serve", readme)
        self.assertIn("Планировщик заданий Windows", readme)
        self.assertIn("Ручная приемка", readme)

    def test_env_example_contains_http_settings(self):
        env = Path(".env.example").read_text(encoding="utf-8")

        self.assertIn("HTTP_HOST=127.0.0.1", env)
        self.assertIn("HTTP_PORT=8787", env)
        self.assertIn("HTTP_AUTH_TOKEN=", env)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Шаг 2: Запустить новый тест и проверить красную фазу**

Запустить:

```powershell
python -m unittest tests.test_docs -v
```

Ожидается: FAIL, потому что README еще не описывает JSON-вывод, `serve` и ручную приемку.

- [ ] **Шаг 3: Обновить README точным операторским процессом**

Заменить `README.md` на:

````markdown
# Telegram Podcast Digest

Локальная автоматизация под Windows для превращения аудио из Telegram-канала в подкаст-дайджесты NotebookLM.

## Настройка

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e .
```

Установите ffmpeg и убедитесь, что эта команда работает:

```powershell
ffmpeg -version
```

Скопируйте `.env.example` в `.env` и заполните значения Telegram, NotebookLM, бота и HTTP.

Авторизуйте NotebookLM через неофициальную CLI `notebooklm-py`:

```powershell
notebooklm --storage data/notebooklm_storage_state.json login
notebooklm --storage data/notebooklm_storage_state.json auth check --test
```

Авторизуйте пользовательский доступ Telegram:

```powershell
tg-podcast-digest setup-telegram
```

## Запуск

```powershell
tg-podcast-digest doctor
tg-podcast-digest run-once --dry-run
tg-podcast-digest run-once
tg-podcast-digest run-once --json
tg-podcast-digest cleanup
```

`run-once --json` печатает один JSON-объект с `run_id`, `status`, счетчиками, записями обработанных сообщений, ошибками и временными метками. Используйте его из n8n, скриптов или оберток Планировщика заданий Windows.

## HTTP-режим

Запустите локальный HTTP API:

```powershell
tg-podcast-digest serve
```

Проверка доступности:

```powershell
Invoke-RestMethod `
  -Method GET `
  -Uri http://127.0.0.1:8787/health `
  -Headers @{ Authorization = "Bearer $env:HTTP_AUTH_TOKEN" }
```

Запуск одной dry-run проверки:

```powershell
Invoke-RestMethod `
  -Method POST `
  -Uri http://127.0.0.1:8787/run-once `
  -Headers @{ Authorization = "Bearer $env:HTTP_AUTH_TOKEN" } `
  -ContentType "application/json" `
  -Body '{"dry_run":true,"max_messages":3}'
```

Открывайте HTTP-режим только через контролируемую локальную сеть, VPN или туннель с авторизацией. Не публикуйте его напрямую в интернет.

## Планировщик заданий Windows

Настройте Планировщик заданий Windows на запуск этой команды из директории проекта:

```powershell
tg-podcast-digest run-once --json
```

Укажите корень проекта как рабочую директорию задачи, чтобы относительные пути из `.env` разрешались в `data/`, `downloads/` и `output/`.

## Ручная приемка

1. `python -m unittest discover -s tests -v` проходит.
2. `tg-podcast-digest doctor` возвращает код выхода `0`.
3. `tg-podcast-digest run-once --dry-run --max-messages 3` показывает ожидаемые аудио из исходного канала.
4. `tg-podcast-digest run-once --json --max-messages 1` создает локальный исходный файл, сконвертированный MP3, блокнот NotebookLM, текстовое резюме, сгенерированный MP3 и доставку в Telegram.
5. Повторный запуск `tg-podcast-digest run-once --json --max-messages 1` не обрабатывает то же сообщение Telegram второй раз.
````

- [ ] **Шаг 4: Проверить зеленую фазу**

Запустить:

```powershell
python -m unittest tests.test_docs -v
python -m unittest discover -s tests -v
```

Ожидается: все тесты проходят.

- [ ] **Шаг 5: Сделать коммит**

Запустить:

```powershell
git add README.md .env.example tests/test_docs.py
git commit -m "docs: document operation and acceptance"
```

---

### Задача 6: Финальная Проверка

**Файлы:**
- Новых файлов нет.

- [ ] **Шаг 1: Запустить полный набор модульных тестов**

Запустить:

```powershell
python -m unittest discover -s tests -v
```

Ожидается: все тесты проходят.

- [ ] **Шаг 2: Проверить точку входа пакета**

Запустить:

```powershell
python -m tg_podcast_digest --help
```

Ожидается: help-вывод содержит `doctor`, `setup-telegram`, `run-once`, `cleanup` и `serve`.

- [ ] **Шаг 3: Проверить форму CLI JSON без реальных внешних сервисов**

Использовать модульный тест как автоматическое доказательство:

```powershell
python -m unittest tests.test_cli.CliTests.test_run_once_json_outputs_stable_machine_readable_result -v
```

Ожидается: `ok`.

- [ ] **Шаг 4: Проверить git diff перед сдачей**

Запустить:

```powershell
git status --short
git diff --stat
```

Ожидается: изменены только файлы из задач выше.

- [ ] **Шаг 5: При необходимости закоммитить финальные заметки проверки**

Если `PLAN.md` должен версионироваться вместе с проектом, запустить:

```powershell
git add PLAN.md
git commit -m "docs: add implementation plan"
```

Если `PLAN.md` является только локальным рабочим контекстом, оставить его неотслеживаемым.

---

## Самопроверка

- Покрытие спеки: V1-пайплайн, конфигурация, идемпотентность SQLite, адаптеры Telegram/ffmpeg/NotebookLM, вывод в Telegram, JSON-результат, очистка, HTTP/n8n-путь запуска и ручная приемка покрыты задачами.
- Поиск заглушек: шагов с маркерами-заглушками не осталось; каждый шаг, создающий код, содержит конкретный код.
- Согласованность типов: `RunResult`, `ProcessedMessage`, `run_result_to_dict`, `NotebookLMProcessor(client_factory=...)`, `handle_request` и `serve_http` вводятся раньше, чем последующие задачи на них ссылаются.
- Тестовая дисциплина: каждое изменение поведения начинается с падающей команды `unittest`, и только после этого добавляется рабочий код.
