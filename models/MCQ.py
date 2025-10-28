from pydantic import BaseModel, Field
from typing import List

class MCQ(BaseModel):
    """Multiple-choice question"""
    question: str = Field(..., description="The multiple-choice question text")
    answer_options: List[str] = Field(..., description="The available answer options")
    answer_index: int = Field(..., description="The index of the correct answer in answer_options")