from typing import Optional, List
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langgraph.graph import StateGraph
from pydantic import BaseModel, Field
from langgraph.constants import START, END
from agents.lesson_generator_agent import lesson_generator_agent, lesson_generator_system_prompt
from agents.lesson_reviewer_agent import  review_lesson, LessonReview
from models.Lesson import Lesson
from models.Roadmap import Roadmap

MAX_ITERATIONS = 1

class LessonAgentState(BaseModel):
    roadmap: Roadmap = Field(..., description="The overall roadmap to see the scope of the roadmap")
    learned_summary: str = Field(..., description="A summary of what the user has learned so far, to know the next lesson.")
    lesson: Optional[Lesson] = None
    current_section_title: str = Field(..., description="The title of the section to which the lesson belongs to")
    current_concept_title: str = Field(..., description="The title of the concept to which the lesson belongs to")
    lesson_title: str = Field(..., description="Title of the lesson to generate")
    learning_objectives: List[str] = Field(..., description="Learning objectives")
    lessons_in_concept: List[str] = Field(..., description="All lessons in current concept for scope orientation")
    review: Optional[LessonReview] = None
    iteration: int = 0
    last_node: Optional[str] = None


def lesson_supervisor_node(state: LessonAgentState) -> str:
    is_approved = state.review and state.review.approved
    print(f"Supervisor - Iteration: {state.iteration}, Approved: {is_approved}, Last node: {state.last_node}")

    if state.iteration >= MAX_ITERATIONS or is_approved:
        print("Routing to END")
        return END

    # If we just generated a lesson and no review exists, go to reviewer
    if state.last_node == 'lesson_generator_node' and not state.review:
        print('Routing to lesson reviewer (first review)')
        return 'lesson_reviewer_node'

    # If we have a review but it's not approved, go back to generator
    if state.review and not state.review.approved:
        print("Routing to lesson generator (needs improvement)")
        return 'lesson_generator_node'

    # If we just reviewed and it's approved, we're done
    if state.last_node == 'lesson_reviewer_node' and state.review and state.review.approved:
        print("Routing to END (approved)")
        return END

    # Default to generator for first run
    print("Routing to lesson generator (first run)")
    return 'lesson_generator_node'


def lesson_generator_node(state: LessonAgentState) -> LessonAgentState:
    print("Generating lesson...")
    generator_messages: list[SystemMessage | HumanMessage | AIMessage] = [
        SystemMessage(content=lesson_generator_system_prompt),
        HumanMessage(content=f"""
                Roadmap: {state.roadmap.model_dump_json(indent=2)}\n\n
                Current Section: {state.current_section_title}\n\n
                Current Concept: {state.current_concept_title}\n\n
                Lesson Title: {state.lesson_title}\n\n
                Learning Objectives: {"\n".join(state.learning_objectives)} 
                Summary of what the user learned so far: "{state.learned_summary}"
            """)
    ]

    feedback = getattr(state.review, 'feedback', None)
    approved = getattr(state.review, 'approved', False)

    if feedback and not approved:
        generator_messages.extend([
            AIMessage(content=state.lesson.content),
            HumanMessage(content=f"Please improve the lesson based on this feedback:\n{feedback}")
        ])

    result = lesson_generator_agent.invoke(generator_messages)
    state.iteration += 1
    state.last_node = 'lesson_generator_node'
    state.lesson = result

    return state

def lesson_reviewer_node(state: LessonAgentState) -> LessonAgentState:
    print('Reviewing lesson...')

    result = review_lesson(
        lesson_content=state.lesson.model_dump()['content'],
        lessons_in_concept=state.lessons_in_concept,
        current_lesson_title=state.lesson_title
    )

    state.review = result
    state.last_node = 'lesson_reviewer_node'
    return state


graph_builder = StateGraph(LessonAgentState)

graph_builder.add_node('lesson_generator_node', lesson_generator_node)
graph_builder.add_node('lesson_reviewer_node', lesson_reviewer_node)

graph_builder.add_edge(START, 'lesson_generator_node')

graph_builder.add_conditional_edges('lesson_generator_node', lesson_supervisor_node)
graph_builder.add_conditional_edges('lesson_reviewer_node', lesson_supervisor_node)

lesson_generation_graph = graph_builder.compile()

