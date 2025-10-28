from pydantic import BaseModel, Field

class Question(BaseModel):
    question: str = Field(..., description="The open-ended question text")