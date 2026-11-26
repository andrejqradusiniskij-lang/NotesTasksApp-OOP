from abc import ABC, abstractmethod
from datetime import datetime
from typing import List, Optional


class Taggable(ABC):
    """Інтерфейс для сутностей, які підтримують прикріплення тегів."""

    @abstractmethod
    def add_tag(self, tag_name: str) -> None:
        pass

    @abstractmethod
    def remove_tag(self, tag_name: str) -> None:
        pass

    @abstractmethod
    def get_tags(self) -> List[str]:
        pass


class Deadlined(ABC):
    """Інтерфейс для сутностей, які мають кінцевий термін виконання."""

    @abstractmethod
    def set_deadline(self, deadline: Optional[datetime]) -> None:
        pass

    @abstractmethod
    def get_deadline(self) -> Optional[datetime]:
        pass

    @abstractmethod
    def is_overdue(self) -> bool:
        pass
