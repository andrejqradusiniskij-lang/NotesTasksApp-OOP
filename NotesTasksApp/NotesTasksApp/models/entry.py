import uuid
from abc import ABC, abstractmethod
from datetime import datetime
from typing import List, Optional

from models.interfaces import Deadlined, Taggable
from models.subtask import Subtask


class Entry(Taggable, ABC):
    """Абстрактний базовий клас для всіх записів у системі."""

    DATE_FORMAT = "%Y-%m-%d %H:%M"

    def __init__(
        self,
        title: str,
        created_at: Optional[datetime] = None,
        tags: Optional[List[str]] = None,
        entry_id: Optional[str] = None,
    ) -> None:
        self._id: str = entry_id or str(uuid.uuid4())
        self.title = title
        self._created_at: datetime = created_at or datetime.now()
        self._tags: List[str] = []
        if tags:
            for t in tags:
                self.add_tag(t)

    @property
    def id(self) -> str:
        return self._id

    @property
    def title(self) -> str:
        return self._title

    @title.setter
    def title(self, value: str) -> None:
        cleaned = value.strip() if isinstance(value, str) else ""
        if not cleaned:
            raise ValueError("Заголовок запису не може бути порожнім.")
        self._title = cleaned

    @property
    def created_at(self) -> datetime:
        return self._created_at

    def add_tag(self, tag_name: str) -> None:
        cleaned = tag_name.strip()
        if cleaned and cleaned not in self._tags:
            self._tags.append(cleaned)

    def remove_tag(self, tag_name: str) -> None:
        if tag_name in self._tags:
            self._tags.remove(tag_name)

    def get_tags(self) -> List[str]:
        return list(self._tags)

    def set_tags(self, tags: List[str]) -> None:
        self._tags.clear()
        for t in tags:
            self.add_tag(t)

    @abstractmethod
    def summary(self) -> str:
        """Повертає стислий опис запису для відображення у таблиці."""
        pass

    @abstractmethod
    def get_searchable_text(self) -> str:
        """Повертає повний текст запису для повнотекстового пошуку."""
        pass

    @abstractmethod
    def to_dict(self) -> dict:
        pass

    @classmethod
    def parse_datetime(cls, value: Optional[str]) -> Optional[datetime]:
        if not value:
            return None
        for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
            try:
                return datetime.strptime(value.strip(), fmt)
            except ValueError:
                continue
        raise ValueError(f"Хибний формат дати: {value}")


class Note(Entry):
    """Клас текстової нотатки."""

    def __init__(
        self,
        title: str,
        text: str = "",
        created_at: Optional[datetime] = None,
        tags: Optional[List[str]] = None,
        entry_id: Optional[str] = None,
    ) -> None:
        super().__init__(title=title, created_at=created_at, tags=tags, entry_id=entry_id)
        self.text = text

    @property
    def text(self) -> str:
        return self._text

    @text.setter
    def text(self, value: str) -> None:
        self._text = str(value) if value is not None else ""

    def summary(self) -> str:
        preview = self._text.replace("\n", " ").strip()
        if len(preview) > 55:
            preview = preview[:52] + "..."
        return f"Нотатка: {self._title} ({preview})" if preview else f"Нотатка: {self._title}"

    def get_searchable_text(self) -> str:
        return f"{self._title} {self._text} {' '.join(self._tags)}"

    def to_dict(self) -> dict:
        return {
            "id": self._id,
            "kind": "note",
            "title": self._title,
            "text": self._text,
            "created_at": self._created_at.strftime(self.DATE_FORMAT),
            "tags": list(self._tags),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Note":
        created = cls.parse_datetime(data.get("created_at"))
        return cls(
            title=data.get("title", ""),
            text=data.get("text", ""),
            created_at=created,
            tags=data.get("tags", []),
            entry_id=data.get("id"),
        )


class Task(Entry, Deadlined):
    """Клас звичайної задачі з пріоритетом, станом і кінцевим терміном."""

    VALID_PRIORITIES = ("Низький", "Середній", "Високий")
    VALID_STATUSES = ("Нова", "В роботі", "Виконано")

    def __init__(
        self,
        title: str,
        description: str = "",
        priority: str = "Середній",
        status: str = "Нова",
        deadline: Optional[datetime] = None,
        created_at: Optional[datetime] = None,
        tags: Optional[List[str]] = None,
        entry_id: Optional[str] = None,
    ) -> None:
        super().__init__(title=title, created_at=created_at, tags=tags, entry_id=entry_id)
        self.description = description
        self.priority = priority
        self.status = status
        self._deadline: Optional[datetime] = None
        self.set_deadline(deadline)

    @property
    def description(self) -> str:
        return self._description

    @description.setter
    def description(self, value: str) -> None:
        self._description = str(value) if value is not None else ""

    @property
    def priority(self) -> str:
        return self._priority

    @priority.setter
    def priority(self, value: str) -> None:
        if value not in self.VALID_PRIORITIES:
            raise ValueError(f"Невідомий пріоритет задачі: {value}")
        self._priority = value

    @property
    def status(self) -> str:
        return self._status

    @status.setter
    def status(self, value: str) -> None:
        if value not in self.VALID_STATUSES:
            raise ValueError(f"Невідомий стан задачі: {value}")
        self._status = value

    def set_deadline(self, deadline: Optional[datetime]) -> None:
        self._deadline = deadline

    def get_deadline(self) -> Optional[datetime]:
        return self._deadline

    def is_overdue(self) -> bool:
        if self._deadline is None or self._status == "Виконано":
            return False
        return datetime.now() > self._deadline

    def summary(self) -> str:
        dl = self._deadline.strftime(self.DATE_FORMAT) if self._deadline else "без терміну"
        overdue_mark = " [ПРОСТРОЧЕНО]" if self.is_overdue() else ""
        return f"Задача [{self._status} | {self._priority}]: {self._title} (до {dl}){overdue_mark}"

    def get_searchable_text(self) -> str:
        return f"{self._title} {self._description} {self._priority} {self._status} {' '.join(self._tags)}"

    def to_dict(self) -> dict:
        return {
            "id": self._id,
            "kind": "task",
            "title": self._title,
            "description": self._description,
            "priority": self._priority,
            "status": self._status,
            "deadline": self._deadline.strftime(self.DATE_FORMAT) if self._deadline else None,
            "created_at": self._created_at.strftime(self.DATE_FORMAT),
            "tags": list(self._tags),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Task":
        created = cls.parse_datetime(data.get("created_at"))
        deadline = cls.parse_datetime(data.get("deadline"))
        return cls(
            title=data.get("title", ""),
            description=data.get("description", ""),
            priority=data.get("priority", "Середній"),
            status=data.get("status", "Нова"),
            deadline=deadline,
            created_at=created,
            tags=data.get("tags", []),
            entry_id=data.get("id"),
        )


class ChecklistTask(Task):
    """Задача з переліком підзадач (чек-лист)."""

    def __init__(
        self,
        title: str,
        description: str = "",
        priority: str = "Середній",
        status: str = "Нова",
        deadline: Optional[datetime] = None,
        subtasks: Optional[List[Subtask]] = None,
        created_at: Optional[datetime] = None,
        tags: Optional[List[str]] = None,
        entry_id: Optional[str] = None,
    ) -> None:
        super().__init__(
            title=title,
            description=description,
            priority=priority,
            status=status,
            deadline=deadline,
            created_at=created_at,
            tags=tags,
            entry_id=entry_id,
        )
        self._subtasks: List[Subtask] = list(subtasks) if subtasks else []

    @property
    def subtasks(self) -> List[Subtask]:
        return list(self._subtasks)

    def add_subtask(self, subtask: Subtask) -> None:
        self._subtasks.append(subtask)

    def set_subtasks(self, subtasks: List[Subtask]) -> None:
        self._subtasks = list(subtasks)

    def completion_ratio(self) -> tuple[int, int]:
        done = sum(1 for s in self._subtasks if s.completed)
        return done, len(self._subtasks)

    def summary(self) -> str:
        done, total = self.completion_ratio()
        overdue_mark = " [ПРОСТРОЧЕНО]" if self.is_overdue() else ""
        return f"Чек-лист [{self._status} | {done}/{total}]: {self._title}{overdue_mark}"

    def get_searchable_text(self) -> str:
        sub_text = " ".join(s.title for s in self._subtasks)
        return f"{super().get_searchable_text()} {sub_text}"

    def to_dict(self) -> dict:
        base = super().to_dict()
        base["kind"] = "checklist_task"
        base["subtasks"] = [s.to_dict() for s in self._subtasks]
        return base

    @classmethod
    def from_dict(cls, data: dict) -> "ChecklistTask":
        created = cls.parse_datetime(data.get("created_at"))
        deadline = cls.parse_datetime(data.get("deadline"))
        raw_subs = data.get("subtasks", [])
        subtasks = [Subtask.from_dict(s) for s in raw_subs]
        return cls(
            title=data.get("title", ""),
            description=data.get("description", ""),
            priority=data.get("priority", "Середній"),
            status=data.get("status", "Нова"),
            deadline=deadline,
            subtasks=subtasks,
            created_at=created,
            tags=data.get("tags", []),
            entry_id=data.get("id"),
        )
