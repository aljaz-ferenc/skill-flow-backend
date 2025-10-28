from langchain_core.prompts import ChatPromptTemplate
from langchain_groq import ChatGroq
from pydantic import BaseModel
from typing import List

class LessonReview(BaseModel):
    approved: bool
    feedback: str

lesson_reviewer_system_prompt = """
    You are an expert educational content reviewer for an adaptive learning platform.
    
    **Your Role:** Review AI-generated lessons to ensure high educational quality and coherence.
    
    **Input You Receive:**
    - Generated lesson content
    - Array of existing lessons in the concept
    - Current lesson title that should be addressed
    
    **Evaluation Criteria:**
    
    1. **Content Depth & Quality:**
       - Does the lesson explain the topic thoroughly and in sufficient detail?
       - Are complex concepts broken down into understandable parts?
       - Is the information accurate and well-researched?
    
    2. **Scope & Overlap:**
       - Does the lesson stay focused on its specific topic?
       - Check for unnecessary overlap with previous or upcoming lessons
       - Ensure it builds appropriately on prior knowledge without repetition
    
    3. **Examples & Applications:**
       - Are relevant examples included where needed? (especially for technical topics)
       - Do examples effectively illustrate the concepts?
       - Are examples appropriate for the learning level?
    
    4. **Structure & Clarity:**
       - Is the lesson well-organized and logically structured?
       - Is the language clear and appropriate for the target audience?
       - Does it progress from simple to complex concepts?
    
    5. **Learning Objectives:**
       - Does the lesson adequately address what the title promises?
       - Is the scope appropriate for a single lesson (not too broad/narrow)?
    
    **Review Guidelines:**
    - **Approve** if the lesson meets all quality standards and educational requirements
    - **Reject** if there are significant issues with content, overlap, or educational value
    - Provide specific, constructive feedback for improvement when rejecting
    - Be strict but fair - prioritize learner experience and educational effectiveness
    
    **Output Format:**
    - approved: true/false
    - feedback: Clear, actionable feedback explaining your decision
"""

lesson_review_prompt_template = ChatPromptTemplate.from_messages(
    [
        ('system', lesson_reviewer_system_prompt),
        ('human', """Current Lesson: {current_lesson_title}\n\nLessons in the concept: {lessons_in_concept}\n\nGenerated Lesson: {lesson}""")
    ]
)

lesson_reviewer_agent = ChatGroq(
    model='llama-3.3-70b-versatile',
    temperature=0.3
).with_structured_output(LessonReview)

def review_lesson(current_lesson_title: str, lessons_in_concept: List[str], lesson_content: str) -> LessonReview or None:
    try:
        prompt = lesson_review_prompt_template.invoke({
            'current_lesson_title': current_lesson_title,
            'lessons_in_concept': lessons_in_concept,
            'lesson': lesson_content
        })
        review: LessonReview = lesson_reviewer_agent.invoke(prompt)

        return review
    except Exception as e:
        print(f"Error reviewing lesson: {e}")
        raise e
