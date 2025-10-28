from typing import Literal, Union
from pydantic import BaseModel
from models.Question import Question
from models.MCQ import MCQ

class Exercise(BaseModel):
    type: Literal['mcq', 'question']
    exercise: Union[Question, MCQ]