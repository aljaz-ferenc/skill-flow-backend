from typing import Optional

from pydantic import BaseModel, Field
from models.Exercise import Exercise
from typing import List

class Lesson(BaseModel):
    content: str = Field(..., description="The lesson content in Markdown")
    exercises: List[Exercise] = Field(..., description="A list of exercises at the end of the lesson")
    summary: str = Field(..., description="Short summary of what the learner learned in this lesson to be combined with previous summaries to track the learners knowledge")
    is_final: bool = Field(..., description="Whether this is the final lesson for the current concept")