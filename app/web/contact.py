from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field


class ContactMember(BaseModel):
    model_config = ConfigDict(extra='forbid',hide_input_in_errors=True)
    name: str = Field(min_length=1,max_length=100)
    student_id: str | None = Field(default=None,max_length=32)
    role: str | None = Field(default=None,max_length=200)
    email: str | None = Field(default=None,max_length=200)


class ContactRoster(BaseModel):
    model_config = ConfigDict(extra='forbid',hide_input_in_errors=True)
    verified: bool = False
    members: list[ContactMember] = Field(default_factory=list,max_length=20)

    @classmethod
    def from_path(cls,path: Path):
        if not path.exists():return cls()
        try:
            if path.stat().st_size>65536:raise ValueError
            return cls.model_validate_json(path.read_text())
        except Exception:
            raise RuntimeError('The configured contact roster is invalid') from None
