import os
import random
from datetime import datetime, timedelta
from models.entry import ChecklistTask, Note, Task
from models.subtask import Subtask
from models.tag import Tag
from storage.json_repository import JsonXmlRepository


def generate_dataset(filepath: str, total_entries: int = 60) -> None:
    tags = {
        "Навчання": Tag("Навчання", "#2B7DE9"),
        "ООП": Tag("ООП", "#2E7D32"),
        "Робота": Tag("Робота", "#EF6C00"),
        "Терміново": Tag("Терміново", "#C62828"),
        "Ідеї": Tag("Ідеї", "#6A1B9A"),
    }
    tag_names = list(tags.keys())
    now = datetime(2026, 11, 20, 14, 0)
    entries = []

    for i in range(1, total_entries + 1):
        chosen_tags = random.sample(tag_names, k=random.randint(1, 3))
        created = now - timedelta(days=random.randint(0, 30), hours=random.randint(0, 23))
        kind = i % 3
        if kind == 1:
            entries.append(
                Note(
                    title=f"Конспект лекції №{i}: принципи ООП",
                    text=f"Детальний опис інкапсуляції, поліморфізму та композиції для модуля {i}.",
                    created_at=created,
                    tags=chosen_tags,
                )
            )
        elif kind == 2:
            delta_days = -2 if i % 6 == 0 else random.randint(1, 14)
            status = "Виконано" if i % 4 == 0 else ("В роботі" if i % 2 == 0 else "Нова")
            entries.append(
                Task(
                    title=f"Лабораторна робота №{i}",
                    description=f"Реалізувати ієрархію класів та перевірити обробку винятків (варіант {i}).",
                    priority=random.choice(Task.VALID_PRIORITIES),
                    status=status,
                    deadline=now + timedelta(days=delta_days),
                    created_at=created,
                    tags=chosen_tags,
                )
            )
        else:
            subs = [
                Subtask("Спроєктувати UML-діаграму", completed=True),
                Subtask("Реалізувати модульні тести", completed=(i % 2 == 0)),
                Subtask("Оформити пояснювальну записку", completed=False),
            ]
            entries.append(
                ChecklistTask(
                    title=f"Етап курсового проєкту #{i}",
                    description="Контрольний перелік завдань перед захистом.",
                    priority="Високий" if i % 5 == 0 else "Середній",
                    status="В роботі",
                    deadline=now + timedelta(days=random.randint(2, 20)),
                    subtasks=subs,
                    created_at=created,
                    tags=chosen_tags,
                )
            )

    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    JsonXmlRepository.save_to_json(filepath, entries, tags)


if __name__ == "__main__":
    generate_dataset(os.path.join("data", "notes.json"), total_entries=60)
    generate_dataset(os.path.join("data", "notes_10000.json"), total_entries=10000)
