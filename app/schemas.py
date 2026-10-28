from typing import Literal

from pydantic import BaseModel, Field

Category = Literal["animal", "vehicle", "food", "landscape", "building", "other"]


class ImageTags(BaseModel):
    """The shape every Gemini answer must have. Anything else is rejected."""

    subject: str = Field(min_length=1, max_length=80)
    category: Category
    attributes: list[str] = Field(max_length=10)
    caption: str = Field(min_length=1, max_length=300)
    confidence: float = Field(ge=0.0, le=1.0)
