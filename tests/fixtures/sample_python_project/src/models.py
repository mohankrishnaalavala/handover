"""DB models for the sample project."""

from .database import Base


class User(Base):
    """Application user account."""

    name: str = ""
    email: str = ""


class Goal(Base):
    """User-defined goal."""

    title: str = ""
    target: int = 0
