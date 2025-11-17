from langchain_core.messages import SystemMessage, HumanMessage
from agents.exercise_checker_agent import exercise_checker, exercise_checker_system_prompt
from graphs.lesson_generation_graph import LessonAgentState, lesson_generation_graph
from models.Roadmap import Roadmap
from bson import ObjectId
import datetime
from datetime import timezone
from fastapi import FastAPI, HTTPException
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse
import json
from pydantic import BaseModel
from agents.lessons_planner_agent import plan_lessons
from db.mongo import client
from graphs.roadmap_generation_graph import RoadmapGenerationAgentState, RoadmapStatus, roadmap_generation_graph
import uuid

load_dotenv()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://skill-flow-frontend-ashen.vercel.app"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class GenerateRoadmapRequest(BaseModel):
    topic: str

@app.post('/generate-roadmap')
async def generate_roadmap(request: GenerateRoadmapRequest):
    """Generates roadmap, generates lessons meta, adds lessons to concept, inserts lessons to lessons collection"""
    print(request.topic)
    try:
        initial_state = RoadmapGenerationAgentState(
            roadmap_status=RoadmapStatus(),
            topic=request.topic,
            messages=[],
            iteration=0
        )

        roadmap = roadmap_generation_graph.invoke(initial_state)

        print(roadmap)

        database = client.get_database('prod')
        roadmaps_col = database.get_collection('roadmaps')
        lessons_col = database.get_collection('lessons')

        last_message = roadmap['messages'][-1]
        roadmap_content = json.loads(last_message.content)

        sections_with_id = [
            {
                **section,
                "_id": str(uuid.uuid4()),
                'status': 'current' if i == 0 else 'locked',
                'concepts': [
                    {
                        **concept,
                        "_id": str(uuid.uuid4()),
                        'status': 'current' if i == 0 and j == 0 else 'locked',
                        'lessons': []
                    }
                    for j, concept in enumerate(section['concepts'])
                ]
            }
            for i, section in enumerate(roadmap_content["sections"])
        ]

        first_concept_id = sections_with_id[0]['concepts'][0]['_id']

        lessons = plan_lessons(
            topic=roadmap_content['topic'],
            section=sections_with_id[0]['title'],
            concept=sections_with_id[0]['concepts'][0]['title']
        )
        lessons_dicts = [
            {
                **lesson.model_dump(),
                'status': 'current' if i == 0 else 'locked',
                'conceptId': first_concept_id
            } for i, lesson in enumerate(lessons)]

        try:
            lessons_col.insert_many(lessons_dicts)
        except Exception as e:
            print(f'Error saving lessons: {e}')
            raise

        sections_with_id[0]['concepts'][0]['lessons'] = lessons_dicts

        doc = {
            'topic': roadmap_content['topic'],
            'sections': sections_with_id,
            'createdAt': datetime.datetime.now(timezone.utc),
        }

        roadmaps_col.insert_one(doc)
        print("Roadmap saved successfully.")
        return JSONResponse(status_code=201, content={"status": 'success'})
    except Exception as e:
        print("Error saving roadmap:", e)
        return HTTPException(status_code=500, detail=f"Failed to generate roadmap: {e}")


@app.get('/roadmaps')
async def get_roadmaps():
    db = client.get_database('prod')
    collection = db.get_collection('roadmaps')

    roadmaps = list(collection.find())
    print(roadmaps)
    return {'roadmaps': roadmaps}


class LessonRequest(BaseModel):
    roadmapId: str
    roadmapTitle: str
    sectionTitle: str
    conceptTitle: str
    conceptId: str
    lessonId: str

@app.post("/lesson")
async def generate_lesson(request: LessonRequest):
    try:
        db = client.get_database("prod")
        roadmaps_col = db.get_collection("roadmaps")
        lessons_col = db.get_collection("lessons")

        roadmap_data = roadmaps_col.find_one({"_id": ObjectId(request.roadmapId)})
        lesson_data = lessons_col.find_one({'_id': ObjectId(request.lessonId)})
        lesson_titles = [lesson['title'] for lesson in lessons_col.find(
            {'conceptId': request.conceptId},
            {'title': 1, '_id': 0}
        )]

        if not roadmap_data:
            return JSONResponse(status_code=404, content={"error": "Roadmap not found."})
        if not lesson_data:
            return JSONResponse(status_code=404, content={"error": "Lesson not found."})

        initial_state = LessonAgentState(
            roadmap=Roadmap(**roadmap_data),
            learned_summary="",
            current_section_title=request.sectionTitle,
            current_concept_title=request.conceptTitle,
            lesson=None,
            lesson_title=lesson_data['title'],
            learning_objectives=lesson_data['learning_objectives'],
            lessons_in_concept=lesson_titles
        )

        result_dict = lesson_generation_graph.invoke(initial_state)
        lesson_state = LessonAgentState(**result_dict)

        if not lesson_state.lesson:
            return JSONResponse(status_code=500, content={"error": "No lesson generated"})

        lesson_dict = lesson_state.lesson.model_dump()

        exercises_data = []
        for exercise in lesson_dict['exercises']:
            exercise_data = {
                'type': exercise['type'],
                'question': exercise['exercise']['question']
            }
            if exercise['type'] == 'mcq':
                exercise_data['answer_options'] = exercise['exercise']['answer_options']
                exercise_data['answer_index'] = exercise['exercise']['answer_index']
            exercises_data.append(exercise_data)

        update_result = lessons_col.update_one(
            {'_id': ObjectId(request.lessonId)},
            {'$set': {
                'content': lesson_dict['content'],
                'exercises': exercises_data,
                'summary': lesson_dict['summary'],
                'is_final': lesson_dict['is_final'],
                'conceptId': request.conceptId,
                'createdAt': datetime.datetime.now(),
                'status': 'current'
            }}
        )

        if update_result.modified_count == 0:
            return JSONResponse(status_code=500, content={"error": "Failed to update lesson"})

        return {"message": "Lesson generated successfully", "lesson_id": request.lessonId}

    except Exception as e:
        print("Error in /lesson endpoint:", e)
        return JSONResponse(status_code=500, content={"error": f"Error generating lesson: {str(e)}"})


class AnswerCheckRequest(BaseModel):
    question: str
    answer: str
    lessonContent: str


@app.post('/check-answer')
async def check_answer(request: AnswerCheckRequest):
    print('Checking answer...')
    try:

        user_prompt = f"""
            Question: {request.question}\n\n
            User's answer: {request.answer}\n\n
            Lesson Content: {request.lessonContent}
        """

        answer = exercise_checker.invoke(
            [
                SystemMessage(content=exercise_checker_system_prompt),
                HumanMessage(content=user_prompt)
            ]
        )
        print(answer)
        return answer.model_dump()

    except Exception as e:
        print(e)
        raise HTTPException(status_code=500, detail=f"Error processing answer: {str(e)}")


class PlanLessonsRequest(BaseModel):
    roadmap_topic: str
    section_title: str
    concept_title: str
    concept_id: str
    roadmap_id: str
    section_id: str


@app.post('/plan-lessons')
async def plan_lessons_for_concept(request: PlanLessonsRequest):
    print('Planning lessons...')
    lessons = plan_lessons(
        topic=request.roadmap_topic,
        section=request.section_title,
        concept=request.concept_title
    )

    db = client.get_database('prod')
    lessons_col = db.get_collection('lessons')
    roadmaps_col = db.get_collection('roadmaps')

    lessons_dicts = [{**lesson.model_dump(),
                      'status': 'locked',
                      'conceptId': request.concept_id} for lesson in
                     lessons]
    lessons_dicts[0]['status'] = 'current'

    try:
        lessons_col.insert_many(lessons_dicts)
        roadmaps_col.find_one_and_update(
            {'_id': ObjectId(request.roadmap_id)},
            {
                '$set': {
                    "sections.$[section].concepts.$[concept].lessons": lessons_dicts
                }
            },
            array_filters=[
                {"section._id": request.section_id},
                {"concept._id": request.concept_id}
            ]
        )
        return {'message': 'Lessons planned successfully'}
    except Exception as e:
        print(f'Error saving lessons: {e}')
        raise
