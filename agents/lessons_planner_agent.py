from langchain_core.prompts import ChatPromptTemplate
from langchain_groq import ChatGroq
from pydantic import BaseModel, Field
from typing import List
from dotenv import load_dotenv

load_dotenv()

class Lesson(BaseModel):
    title: str = Field(description="Clear, descriptive lesson title")
    description: str = Field(description="Brief explanation of lesson content in one sentence.")
    learning_objectives: List[str] = Field(description="Specific things students will learn")

class LessonList(BaseModel):
    lessons: List[Lesson]

system_prompt = """
    You are an exper curriculum planner for an adaptive learning app. 
    
    **Input:** You will receive:
    - Topic (broad subject area)
    - Section (subtopic within the topic) 
    - Concept (specific concept within the section)
    
    **Your Task:** Generate a structured list of lessons that comprehensively cover the given concept.
    
    **Requirements:**
    1. Create 1 - 10 focused lessons that build upon each other logically
    2. Each lesson should cover one specific aspect of the concept
    3. Lessons should progress from foundational to advanced understanding
    4. Focus on creating lessons that are actionable and teachable in 15-30 minutes each
    6. Some concepts can have only a small number of lessons, sometimes even one
    
    **Output Format:**
    For each lesson, provide:
    - title: Clear, descriptive lesson title
    - description: Brief explanation of lesson content in one sentence.
    - learning_objectives: Specific things the student will learn in the lesson
    
    **Important Considerations:**
    - Some concepts are introductory overviews or wrap-up summaries - these may only need 1-2 lessons
    - Some concepts are deep and complex - these may need many detailed lessons
    - Adjust the number of lessons based on the concept's complexity and depth
    - For simple or introductory concepts, a single comprehensive lesson is perfectly acceptable
    - For wrap-up/conclusion concepts, focus on synthesis and review rather than new content
"""

user_prompt_template = ChatPromptTemplate.from_messages(
    [
        ('system', system_prompt),
        ('human', """Topic: {topic}\n\nSection: {section}\n\nConcept: {concept}""")
    ]
)


lessons_planner_agent = ChatGroq(
        model='llama-3.3-70b-versatile',
        temperature=0.1,
    ).with_structured_output(LessonList)


def plan_lessons(topic: str, section: str, concept: str):
    try:
        prompt = user_prompt_template.invoke({'topic': topic, 'section': section, 'concept': concept})
        print('Planning lessons...')
        lessons = lessons_planner_agent.invoke(prompt)
        print(lessons.lessons)
        return lessons.lessons
    except Exception as e:
        print(f"Error generating lessons: {e}")
        raise


