import logging
import queue
import threading
from datetime import datetime
from typing import Dict, List, Optional, Set

from models.entry import Entry, Task
from models.tag import Tag
from services.indexer_service import InvertedIndexBuilder
from storage.json_repository import JsonXmlRepository

logger = logging.getLogger(__name__)


class AppController:
    """Контролер шаблону MVC: керує моделлю, пошуком, фільтрацією та потоками."""

    def __init__(self, num_workers: int = 4) -> None:
        self._entries: List[Entry] = []
        self._tags: Dict[str, Tag] = {}
        self._word_index: Dict[str, Set[str]] = {}
        self._indexer = InvertedIndexBuilder(num_workers=num_workers)
        self.progress_queue: queue.Queue = queue.Queue()
        self.last_benchmark: Optional[dict] = None

    @property
    def entries(self) -> List[Entry]:
        return list(self._entries)

    @property
    def tags(self) -> Dict[str, Tag]:
        return dict(self._tags)

    def rebuild_index(self) -> None:
        self._word_index, _ = self._indexer.build_single_threaded(self._entries)

    # --- CRUD для тегів ---
    def create_tag(self, name: str, color: str) -> Tag:
        cleaned = name.strip()
        if any(existing.lower() == cleaned.lower() for existing in self._tags):
            raise ValueError(f"Тег із назвою '{cleaned}' вже існує.")
        tag = Tag(name=cleaned, color=color)
        self._tags[tag.name] = tag
        logger.info("Створено тег '%s' (%s)", tag.name, tag.color)
        return tag

    def update_tag(self, old_name: str, new_name: str, new_color: str) -> Tag:
        if old_name not in self._tags:
            raise KeyError(f"Тег '{old_name}' не знайдено.")
        cleaned = new_name.strip()
        if cleaned.lower() != old_name.lower() and any(
            k.lower() == cleaned.lower() for k in self._tags
        ):
            raise ValueError(f"Тег із назвою '{cleaned}' вже існує.")
        updated = Tag(name=cleaned, color=new_color)
        del self._tags[old_name]
        self._tags[updated.name] = updated
        if old_name != updated.name:
            for entry in self._entries:
                if old_name in entry.get_tags():
                    entry.remove_tag(old_name)
                    entry.add_tag(updated.name)
        self.rebuild_index()
        logger.info("Оновлено тег '%s' -> '%s'", old_name, updated.name)
        return updated

    def delete_tag(self, name: str, force: bool = False) -> int:
        """Видаляє тег. Якщо тег задіяний і force=False, генерує ValueError."""
        if name not in self._tags:
            raise KeyError(f"Тег '{name}' не знайдено.")
        used_in = [e for e in self._entries if name in e.get_tags()]
        if used_in and not force:
            raise ValueError(
                f"Тег '{name}' використовується у {len(used_in)} записах. Підтвердьте відкріплення."
            )
        for entry in used_in:
            entry.remove_tag(name)
        del self._tags[name]
        self.rebuild_index()
        logger.info("Видалено тег '%s' (відкріплено від %d записів)", name, len(used_in))
        return len(used_in)

    # --- CRUD для записів ---
    def _validate_entry_tags(self, entry: Entry) -> None:
        for t in entry.get_tags():
            if t not in self._tags:
                raise ValueError(f"Неіснуючий тег: '{t}'")

    def add_entry(self, entry: Entry) -> None:
        self._validate_entry_tags(entry)
        self._entries.append(entry)
        self.rebuild_index()
        logger.info("Додано запис '%s' (%s)", entry.title, entry.__class__.__name__)

    def update_entry(self, updated_entry: Entry) -> None:
        self._validate_entry_tags(updated_entry)
        for i, existing in enumerate(self._entries):
            if existing.id == updated_entry.id:
                self._entries[i] = updated_entry
                self.rebuild_index()
                logger.info("Оновлено запис '%s'", updated_entry.title)
                return
        raise KeyError(f"Запис із ID '{updated_entry.id}' не знайдено.")

    def delete_entry(self, entry_id: str) -> None:
        before = len(self._entries)
        self._entries = [e for e in self._entries if e.id != entry_id]
        if len(self._entries) == before:
            raise KeyError(f"Запис із ID '{entry_id}' не знайдено.")
        self.rebuild_index()
        logger.info("Видалено запис ID=%s", entry_id)

    def get_entry_by_id(self, entry_id: str) -> Optional[Entry]:
        for e in self._entries:
            if e.id == entry_id:
                return e
        return None

    # --- Пошук, фільтрація та сортування ---
    def query_entries(
        self,
        search_text: str = "",
        required_tags: Optional[List[str]] = None,
        priority_filter: str = "Усі",
        status_filter: str = "Усі",
        sort_by: str = "created_desc",
    ) -> List[Entry]:
        candidate_ids: Optional[Set[str]] = None
        tokens = InvertedIndexBuilder.tokenize(search_text) if search_text.strip() else set()

        if tokens:
            for tok in tokens:
                matched_for_tok: Set[str] = set()
                for idx_word, ids in self._word_index.items():
                    if tok in idx_word:
                        matched_for_tok.update(ids)
                candidate_ids = (
                    matched_for_tok
                    if candidate_ids is None
                    else (candidate_ids & matched_for_tok)
                )

        req_tags_set = set(required_tags) if required_tags else set()
        result: List[Entry] = []

        for entry in self._entries:
            if candidate_ids is not None and entry.id not in candidate_ids:
                continue
            if req_tags_set and not req_tags_set.issubset(set(entry.get_tags())):
                continue
            if priority_filter != "Усі":
                if not isinstance(entry, Task) or entry.priority != priority_filter:
                    continue
            if status_filter != "Усі":
                if status_filter == "Прострочені":
                    if not isinstance(entry, Task) or not entry.is_overdue():
                        continue
                elif not isinstance(entry, Task) or entry.status != status_filter:
                    continue
            result.append(entry)

        if sort_by == "created_asc":
            result.sort(key=lambda e: e.created_at)
        elif sort_by == "created_desc":
            result.sort(key=lambda e: e.created_at, reverse=True)
        elif sort_by == "deadline_asc":
            result.sort(
                key=lambda e: (
                    0,
                    e.get_deadline(),
                )
                if isinstance(e, Task) and e.get_deadline() is not None
                else (1, datetime.max)
            )
        elif sort_by == "deadline_desc":
            result.sort(
                key=lambda e: (
                    0,
                    e.get_deadline(),
                )
                if isinstance(e, Task) and e.get_deadline() is not None
                else (1, datetime.min),
                reverse=True,
            )
        return result

    # --- Фоновий імпорт і експорт ---
    def start_background_import(self, filepath: str) -> None:
        worker = threading.Thread(
            target=self._indexer.load_and_index_background,
            args=(filepath, self.progress_queue),
            daemon=True,
        )
        worker.start()

    def apply_imported_data(self, payload: dict) -> None:
        self._entries = payload["entries"]
        self._tags = payload["tags"]
        self._word_index = payload["index"]
        self.last_benchmark = {
            "count": len(self._entries),
            "t1_ms": payload["t1_ms"],
            "tn_ms": payload["tn_ms"],
            "speedup": payload["speedup"],
            "workers": payload["workers"],
        }

    def export_json(self, filepath: str) -> None:
        JsonXmlRepository.save_to_json(filepath, self._entries, self._tags)

    def export_xml_report(self, filepath: str, tag_name: str) -> int:
        if tag_name not in self._tags:
            raise ValueError(f"Неіснуючий тег для звіту: '{tag_name}'")
        return JsonXmlRepository.export_tag_report_xml(filepath, tag_name, self._entries)
