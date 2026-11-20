import json
import logging
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Dict, List, Tuple

from models.entry import ChecklistTask, Entry, Note, Task
from models.tag import Tag

logger = logging.getLogger(__name__)


class DataStorageError(Exception):
    """Виняток помилки читання, валідації або запису даних."""


class JsonXmlRepository:
    """Репозиторій для імпорту та експорту даних у форматах JSON та XML."""

    @staticmethod
    def save_to_json(filepath: str, entries: List[Entry], tags: Dict[str, Tag]) -> None:
        payload = {
            "tags": [t.to_dict() for t in tags.values()],
            "entries": [e.to_dict() for e in entries],
        }
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
            logger.info("Експортовано %d записів і %d тегів у %s", len(entries), len(tags), filepath)
        except OSError as exc:
            logger.error("Помилка запису JSON-файлу %s: %s", filepath, exc)
            raise DataStorageError(f"Не вдалося зберегти файл: {exc}") from exc

    @staticmethod
    def load_from_json(filepath: str) -> Tuple[List[Entry], Dict[str, Tag]]:
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                raw = json.load(f)
        except json.JSONDecodeError as exc:
            logger.error("Пошкоджений JSON-файл %s: %s", filepath, exc)
            raise DataStorageError(f"Пошкоджений формат JSON (рядок {exc.lineno}): {exc.msg}") from exc
        except OSError as exc:
            logger.error("Помилка читання файлу %s: %s", filepath, exc)
            raise DataStorageError(f"Не вдалося відкрити файл: {exc}") from exc

        if not isinstance(raw, dict) or "entries" not in raw:
            logger.error("Некоректна структура JSON у файлі %s", filepath)
            raise DataStorageError("Файл JSON не містить обов'язкового поля 'entries'.")

        tags: Dict[str, Tag] = {}
        for t_item in raw.get("tags", []):
            try:
                tag = Tag.from_dict(t_item)
                tags[tag.name] = tag
            except ValueError as exc:
                logger.warning("Пропущено некоректний тег у JSON: %s", exc)

        entries: List[Entry] = []
        for idx, item in enumerate(raw.get("entries", []), start=1):
            try:
                kind = item.get("kind", "note")
                if kind == "note":
                    entry: Entry = Note.from_dict(item)
                elif kind == "task":
                    entry = Task.from_dict(item)
                elif kind == "checklist_task":
                    entry = ChecklistTask.from_dict(item)
                else:
                    raise ValueError(f"Невідомий тип запису: {kind}")

                for t_name in entry.get_tags():
                    if t_name not in tags:
                        raise ValueError(f"Запис посилається на неіснуючий тег '{t_name}'")

                entries.append(entry)
            except (ValueError, TypeError) as exc:
                logger.error("Помилка валідації запису #%d у %s: %s", idx, filepath, exc)
                raise DataStorageError(f"Помилка у записі #{idx}: {exc}") from exc

        logger.info("Імпортовано %d записів і %d тегів із %s", len(entries), len(tags), filepath)
        return entries, tags

    @staticmethod
    def export_tag_report_xml(filepath: str, tag_name: str, entries: List[Entry]) -> int:
        """Експортує XML-звіт про виконання задач за обраним тегом."""
        tagged_tasks = [
            e for e in entries if isinstance(e, Task) and tag_name in e.get_tags()
        ]
        completed_count = sum(1 for t in tagged_tasks if t.status == "Виконано")
        overdue_count = sum(1 for t in tagged_tasks if t.is_overdue())

        root = ET.Element("TagTaskReport", attrib={
            "tag": tag_name,
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        })
        summary_el = ET.SubElement(root, "Summary")
        ET.SubElement(summary_el, "TotalTasks").text = str(len(tagged_tasks))
        ET.SubElement(summary_el, "CompletedTasks").text = str(completed_count)
        ET.SubElement(summary_el, "OverdueTasks").text = str(overdue_count)

        tasks_el = ET.SubElement(root, "Tasks")
        for task in tagged_tasks:
            t_el = ET.SubElement(tasks_el, "Task", attrib={
                "id": task.id,
                "type": "ChecklistTask" if isinstance(task, ChecklistTask) else "Task",
            })
            ET.SubElement(t_el, "Title").text = task.title
            ET.SubElement(t_el, "Priority").text = task.priority
            ET.SubElement(t_el, "Status").text = task.status
            dl = task.get_deadline()
            ET.SubElement(t_el, "Deadline").text = dl.strftime(Entry.DATE_FORMAT) if dl else "none"
            ET.SubElement(t_el, "Overdue").text = "true" if task.is_overdue() else "false"
            if isinstance(task, ChecklistTask):
                done, total = task.completion_ratio()
                ET.SubElement(t_el, "SubtasksProgress").text = f"{done}/{total}"

        ET.indent(root, space="  ")
        tree = ET.ElementTree(root)
        try:
            tree.write(filepath, encoding="utf-8", xml_declaration=True)
            logger.info("Звіт XML за тегом '%s' (%d задач) збережено у %s", tag_name, len(tagged_tasks), filepath)
            return len(tagged_tasks)
        except OSError as exc:
            logger.error("Помилка запису XML-звіту %s: %s", filepath, exc)
            raise DataStorageError(f"Помилка збереження XML: {exc}") from exc
