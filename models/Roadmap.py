from typing import List, Optional
from bson import ObjectId
from pydantic import BaseModel, Field
from models.Section import Section

class Roadmap(BaseModel):
    sections: List[Section] = Field(..., description="A list of sections in the roadmap")
    _id: Optional[ObjectId] = None
    topic: str = Field(..., description="Main title of the roadmap")