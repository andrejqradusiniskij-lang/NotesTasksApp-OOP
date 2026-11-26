import logging
import queue
import re
import threading
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Set, Tuple

from models.entry import Entry
from storage.json_repository import JsonXmlRepository

logger = logging.getLogger(__name__)
TOKEN_RE = re.compile(r"[a-zA-Zа-яА-ЯіІїЇєЄґҐ0-9_]{2,}")


class InvertedIndexBuilder:
    """Побудова інвертованого індексу слів у одно- та багатопотоковому режимах."""

    def __init__(self, num_workers: int = 4) -> None:
        self.num_workers = max(1, num_workers)
        self._lock = threading.Lock()

    @staticmethod
    def tokenize(text: str) -> Set[str]:
        return set(TOKEN_RE.findall(text.lower()))

    def _build_chunk_index(self, chunk: List[Entry]) -> Dict[str, Set[str]]:
        partial: Dict[str, Set[str]] = defaultdict(set)
        for entry in chunk:
            for token in self.tokenize(entry.get_searchable_text()):
                partial[token].add(entry.id)
        return partial

    def _build_and_merge_chunk(
        self,
        chunk: List[Entry],
        global_index: Dict[str, Set[str]],
    ) -> None:
        partial = self._build_chunk_index(chunk)
        # Потокобезпечне об'єднання часткового індексу під threading.Lock
        with self._lock:
            for token, ids in partial.items():
                global_index[token].update(ids)

    def build_single_threaded(self, entries: List[Entry]) -> Tuple[Dict[str, Set[str]], float]:
        start = time.perf_counter()
        index = self._build_chunk_index(entries)
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        return dict(index), elapsed_ms

    def build_multithreaded(
        self,
        entries: List[Entry],
        progress_queue: queue.Queue | None = None,
    ) -> Tuple[Dict[str, Set[str]], float]:
        start = time.perf_counter()
        global_index: Dict[str, Set[str]] = defaultdict(set)
        total = len(entries)
        if total == 0:
            if progress_queue:
                progress_queue.put(("progress", 1.0, "Файл порожній"))
            return {}, 0.0

        chunk_size = max(1, (total + self.num_workers - 1) // self.num_workers)
        chunks = [entries[i : i + chunk_size] for i in range(0, total, chunk_size)]
        completed_chunks = 0

        with ThreadPoolExecutor(max_workers=self.num_workers) as executor:
            futures = [
                executor.submit(self._build_and_merge_chunk, ch, global_index)
                for ch in chunks
            ]
            for future in as_completed(futures):
                future.result()
                completed_chunks += 1
                if progress_queue is not None:
                    ratio = 0.35 + 0.65 * (completed_chunks / len(chunks))
                    progress_queue.put((
                        "progress",
                        ratio,
                        f"Індексація: блок {completed_chunks}/{len(chunks)}",
                    ))

        elapsed_ms = (time.perf_counter() - start) * 1000.0
        return dict(global_index), elapsed_ms

    def load_and_index_background(
        self,
        filepath: str,
        progress_queue: queue.Queue,
    ) -> None:
        """Фонова задача: читання JSON, вимір T1/Tn та надсилання прогресу в чергу."""
        try:
            progress_queue.put(("progress", 0.1, "Читання JSON-файлу з диска..."))
            entries, tags = JsonXmlRepository.load_from_json(filepath)
            progress_queue.put(("progress", 0.35, f"Завантажено {len(entries)} записів. Індексація..."))

            _, t1_ms = self.build_single_threaded(entries)
            index, tn_ms = self.build_multithreaded(entries, progress_queue=progress_queue)
            speedup = (t1_ms / tn_ms) if tn_ms > 0 else 1.0

            logger.info(
                "Індексацію завершено (%d записів): T1=%.2f мс, T%d=%.2f мс, S=%.2f",
                len(entries), t1_ms, self.num_workers, tn_ms, speedup,
            )
            progress_queue.put((
                "done",
                {
                    "entries": entries,
                    "tags": tags,
                    "index": index,
                    "t1_ms": t1_ms,
                    "tn_ms": tn_ms,
                    "speedup": speedup,
                    "workers": self.num_workers,
                },
            ))
        except Exception as exc:
            logger.exception("Помилка фонового імпорту %s", filepath)
            progress_queue.put(("error", str(exc)))
