from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from langgraph.constants import START, END
from langgraph.graph import StateGraph
from pydantic import BaseModel
from typing import List
from agents.roadmap_generator_agent import roadmap_generator_agent, generator_system_prompt
from agents.roadmap_reviewer_agent import roadmap_reviewer_agent, review_system_prompt
from models.Roadmap import Roadmap

class RoadmapStatus(BaseModel):
    roadmap: Roadmap = None
    approved: bool = False
    feedback: str = ''

class RoadmapGenerationAgentState(BaseModel):
    messages: List[BaseMessage]
    roadmap_status: RoadmapStatus
    topic: str
    iteration: int = 0
    next_node: str = None

MAX_ITERATIONS = 1

def roadmap_supervisor_node(state: RoadmapGenerationAgentState) -> RoadmapGenerationAgentState:
    """Decides which node to run next based on roadmap state"""
    if state.iteration >= MAX_ITERATIONS:
        print("⚠️ Max iterations reached. Ending loop.")
        state.next_node = "__end__"

    elif not state.roadmap_status.roadmap:
        state.next_node = "roadmap_generator"

    elif not state.roadmap_status.approved:
        last_msg = state.messages[-1] if state.messages else None
        if isinstance(last_msg, AIMessage):
            state.next_node = "roadmap_reviewer"
        else:
            state.next_node = "roadmap_generator"

    else:
        print("✅ Roadmap approved!")
        state.next_node = "__end__"

    return state


def roadmap_generation_node(state: RoadmapGenerationAgentState) -> RoadmapGenerationAgentState:
    """Uses roadmap_generator_agent to generate or refine a roadmap."""
    print("🧩 Generating roadmap...")
    state.iteration += 1

    messages_for_gen = [
        SystemMessage(content=generator_system_prompt),
        HumanMessage(content=state.topic),
    ]

    if state.roadmap_status.feedback:
        messages_for_gen.append(
            HumanMessage(content=f"Please improve the roadmap based on this feedback:\n{state.roadmap_status.feedback}")
        )

    roadmap_result = roadmap_generator_agent.invoke(messages_for_gen)
    state.roadmap_status.roadmap = roadmap_result

    state.messages.append(AIMessage(content=roadmap_result.model_dump_json(indent=2)))

    return state


def roadmap_review_node(state: RoadmapGenerationAgentState) -> RoadmapGenerationAgentState:
    print('Reviewing roadmap...')

    review_result = roadmap_reviewer_agent.invoke(
        [SystemMessage(review_system_prompt), *state.messages]
    )

    state.roadmap_status.approved = review_result.approved
    state.roadmap_status.feedback = review_result.feedback

    if review_result.feedback:
        state.messages.append(HumanMessage(content=review_result.model_dump_json(indent=2)))

    return state


graph_builder = StateGraph(RoadmapGenerationAgentState)

graph_builder.add_node('roadmap_generator', roadmap_generation_node)
graph_builder.add_node('roadmap_supervisor', roadmap_supervisor_node)
graph_builder.add_node('roadmap_reviewer', roadmap_review_node)

graph_builder.add_edge(START, 'roadmap_supervisor')
graph_builder.add_edge('roadmap_generator', 'roadmap_supervisor')
graph_builder.add_edge('roadmap_reviewer', 'roadmap_supervisor')

graph_builder.add_conditional_edges(
    'roadmap_supervisor',
    lambda state, result = None: state.next_node,
    {
        'roadmap_generator': 'roadmap_generator',
        'roadmap_reviewer': 'roadmap_reviewer',
        '__end__': END
    }
)

roadmap_generation_graph = graph_builder.compile()


