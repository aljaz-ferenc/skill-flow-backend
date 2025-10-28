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
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
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
        lessons_dicts = [{**lesson.model_dump(), 'status': 'locked', 'conceptId': first_concept_id} for lesson in
                         lessons]

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