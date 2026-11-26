import os
import tempfile
import unittest
from datetime import datetime, timedelta

from models.entry import ChecklistTask, Note, Task
from models.subtask import Subtask
from services.controller import AppController
from services.indexer_service import InvertedIndexBuilder
from storage.json_repository import DataStorageError, JsonXmlRepository


class TestNotesTasksApp(unittest.TestCase):
    def setUp(self) -> None:
        self.ctrl = AppController(num_workers=4)
        self.ctrl.create_tag("ООП", "#2E7D32")
        self.ctrl.create_tag("Навчання", "#2B7DE9")

    def test_validation_empty_title_and_duplicate_tag(self) -> None:
        with self.assertRaises(ValueError):
            Note(title="   ", text="Текст")
        with self.assertRaises(ValueError):
            self.ctrl.create_tag("ооп", "#111111")

    def test_overdue_task_detection(self) -> None:
        past = datetime.now() - timedelta(hours=5)
        t = Task(title="Здати КР", deadline=past, status="В роботі", tags=["ООП"])
        self.assertTrue(t.is_overdue())
        t.status = "Виконано"
        self.assertFalse(t.is_overdue())

    def test_checklist_completion_ratio(self) -> None:
        ct = ChecklistTask(
            title="Чек-лист",
            subtasks=[Subtask("Пункт 1", True), Subtask("Пункт 2", False)],
            tags=["ООП"],
        )
        self.assertEqual(ct.completion_ratio(), (1, 2))
        self.assertIn("1/2", ct.summary())

    def test_update_tag_propagates_to_entries(self) -> None:
        n = Note(title="Конспект", text="Поліморфізм", tags=["ООП"])
        self.ctrl.add_entry(n)
        self.ctrl.update_tag("ООП", "Python-ООП", "#1565C0")
        self.assertIn("Python-ООП", n.get_tags())
        self.assertNotIn("ООП", self.ctrl.tags)

    def test_delete_used_tag_protection(self) -> None:
        n = Note(title="Нотатка", text="Перевірка тегу", tags=["ООП"])
        self.ctrl.add_entry(n)
        with self.assertRaises(ValueError):
            self.ctrl.delete_tag("ООП", force=False)
        detached = self.ctrl.delete_tag("ООП", force=True)
        self.assertEqual(detached, 1)
        self.assertEqual(n.get_tags(), [])

    def test_multi_tag_and_search_filtering(self) -> None:
        n1 = Note(title="Лекція 1", text="Інкапсуляція", tags=["ООП", "Навчання"])
        n2 = Note(title="Лекція 2", text="Спадкування", tags=["ООП"])
        self.ctrl.add_entry(n1)
        self.ctrl.add_entry(n2)
        res = self.ctrl.query_entries(search_text="інкапс", required_tags=["ООП", "Навчання"])
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0].id, n1.id)

    def test_multithreaded_index_matches_single_threaded(self) -> None:
        entries = [
            Note(title=f"Запис {i}", text=f"Тестовий контент слово{i % 10}", tags=["ООП"])
            for i in range(100)
        ]
        builder = InvertedIndexBuilder(num_workers=4)
        idx1, _ = builder.build_single_threaded(entries)
        idx4, _ = builder.build_multithreaded(entries)
        self.assertEqual(idx1, idx4)

    def test_corrupted_json_import(self) -> None:
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as tmp:
            tmp.write("{ broken json: [1, 2")
            tmp_path = tmp.name
        try:
            with self.assertRaises(DataStorageError):
                JsonXmlRepository.load_from_json(tmp_path)
        finally:
            os.remove(tmp_path)

    def test_xml_report_export(self) -> None:
        t1 = ChecklistTask(
            title="Підготовка",
            status="Виконано",
            subtasks=[Subtask("Крок 1", True)],
            tags=["Навчання"],
        )
        self.ctrl.add_entry(t1)
        with tempfile.NamedTemporaryFile("w", suffix=".xml", delete=False, encoding="utf-8") as tmp:
            xml_path = tmp.name
        try:
            count = self.ctrl.export_xml_report(xml_path, "Навчання")
            self.assertEqual(count, 1)
            with open(xml_path, encoding="utf-8") as f:
                content = f.read()
            self.assertIn("<TotalTasks>1</TotalTasks>", content)
            self.assertIn("<CompletedTasks>1</CompletedTasks>", content)
        finally:
            os.remove(xml_path)


if __name__ == "__main__":
    unittest.main()
