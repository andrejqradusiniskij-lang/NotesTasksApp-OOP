import os
import tempfile
import unittest
from datetime import datetime, timedelta

from models.entry import ChecklistTask, Note, Task
from models.subtask import Subtask
from services.controller import AppController
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

    def test_delete_used_tag_protection(self) -> None:
        n = Note(title="Нотатка", text="Перевірка тегу", tags=["ООП"])
        self.ctrl.add_entry(n)
        with self.assertRaises(ValueError):
            self.ctrl.delete_tag("ООП", force=False)
        detached = self.ctrl.delete_tag("ООП", force=True)
        self.assertEqual(detached, 1)
        self.assertEqual(n.get_tags(), [])

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
