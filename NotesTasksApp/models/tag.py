import re


class Tag:
    """Модель тегу з назвою та HEX-кольором."""

    HEX_PATTERN = re.compile(r"^#[0-9A-Fa-f]{6}$")

    def __init__(self, name: str, color: str = "#3B8ED0") -> None:
        self.name = name
        self.color = color

    @property
    def name(self) -> str:
        return self._name

    @name.setter
    def name(self, value: str) -> None:
        cleaned = value.strip() if isinstance(value, str) else ""
        if not cleaned:
            raise ValueError("Назва тегу не може бути порожньою.")
        self._name = cleaned

    @property
    def color(self) -> str:
        return self._color

    @color.setter
    def color(self, value: str) -> None:
        if not isinstance(value, str) or not self.HEX_PATTERN.match(value.strip()):
            raise ValueError(f"Некоректний формат HEX-кольору тегу: {value}")
        self._color = value.strip().upper()

    def to_dict(self) -> dict:
        return {"name": self._name, "color": self._color}

    @classmethod
    def from_dict(cls, data: dict) -> "Tag":
        return cls(
            name=data.get("name", ""),
            color=data.get("color", "#3B8ED0"),
        )

    def __repr__(self) -> str:
        return f"Tag(name={self._name!r}, color={self._color!r})"
