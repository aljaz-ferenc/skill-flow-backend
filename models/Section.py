from pydantic import BaseModel, Field
from typing import List, Optional


class ConceptMeta(BaseModel):
    title: str = Field(..., description="Title of the concept")
    description: str = Field(..., description="Description of the concept")


class Section(BaseModel):
    title: str = Field(..., description="The section title")
    description: str = Field(..., description="Brief explanation of what the section covers")
    concepts: List[ConceptMeta] = Field(..., description="List of concepts in this section")
    locked: Optional[str] = 'locked'

