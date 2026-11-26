class Subtask:
    """Підзадача для контрольного списку ChecklistTask."""

    def __init__(self, title: str, completed: bool = False) -> None:
        self.title = title
        self.completed = completed

    @property
    def title(self) -> str:
        return self._title

    @title.setter
    def title(self, value: str) -> None:
        cleaned = value.strip() if isinstance(value, str) else ""
        if not cleaned:
            raise ValueError("Назва підзадачі не може бути порожньою.")
        self._title = cleaned

    @property
    def completed(self) -> bool:
        return self._completed

    @completed.setter
    def completed(self, value: bool) -> None:
        self._completed = bool(value)

    def toggle(self) -> None:
        self._completed = not self._completed

    def to_dict(self) -> dict:
        return {"title": self._title, "completed": self._completed}

    @classmethod
    def from_dict(cls, data: dict) -> "Subtask":
        return cls(
            title=data.get("title", ""),
            completed=bool(data.get("completed", False)),
        )
