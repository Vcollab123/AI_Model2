from fastapi import FastAPI
from pydantic import BaseModel
import math
import re
import os
from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv()

app = FastAPI()

@app.get("/")
async def health_check():
    return {
        "status": "healthy",
        "service": "opportunity-scoring-api"
    }

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
genai.configure(api_key=GEMINI_API_KEY)

model = genai.GenerativeModel("gemini-pro")

class Opportunity(BaseModel):
    Name: str
    Stage: str
    Notes: str
    Email: int
    Call: int
    Meeting: int
    Days_In_Stage: int

STAGE_BENCHMARKS = {
    "Prospecting": 10,
    "Qualification": 15,
    "Needs Analysis": 10,
    "Proposal": 12,
    "Negotiation": 8,
    "Closed Won": 5,
    "Closed Lost": 5
}

def compute_activity_score(calls, emails, meetings):
    return min((calls * 5 + emails * 3 + meetings * 10), 100)

def compute_sentiment_score(notes):
    if "approved" in notes.lower() or "evaluate" in notes.lower():
        return 85
    elif "not interested" in notes.lower() or "no budget" in notes.lower():
        return 30
    return 60

def compute_stage_duration_score(stage, days):
    benchmark = STAGE_BENCHMARKS.get(stage, 10)
    diff = days - benchmark
    if diff <= 0:
        return 100
    penalty = min(100, math.exp(-0.15 * diff) * 100)
    return round(penalty, 2)

def detect_buying_signals(text):
    keywords = ["send proposal", "ready to buy", "approved budget", "timeline", "implementation",
                "contract", "PO", "quote", "pricing", "final decision", "move forward", "sign off",
                "demo", "evaluation", "trial", "pilot"]
    text = text.lower()
    return any(re.search(rf"\b{re.escape(kw)}\b", text) for kw in keywords)

def compute_confidence_score(activity, sentiment, stage, buying_flag):
    return round(0.3 * activity + 0.3 * sentiment + 0.3 * stage + (10 if buying_flag else 0), 2)

def generate_prompt(data, scores):
    return f"""
You are a B2B sales assistant. Based on this opportunity, suggest the next best action.

Name: {data.Name}
Stage: {data.Stage}
Notes: {data.Notes[:250]}
Activity Score: {scores['activity']}
Sentiment Score: {scores['sentiment']}
Stage Duration Score: {scores['stage']}
Buying Signal: {"Yes" if scores['buying'] else "No"}
Confidence Score: {scores['confidence']}

Suggestion:"""

@app.post("/score")
def score_opportunity(opp: Opportunity):
    try:
        activity = compute_activity_score(opp.Call, opp.Email, opp.Meeting)
        sentiment = compute_sentiment_score(opp.Notes)
        stage = compute_stage_duration_score(opp.Stage, opp.Days_In_Stage)
        buying = detect_buying_signals(opp.Notes)
        confidence = compute_confidence_score(activity, sentiment, stage, buying)

        scores = {
            "activity": activity,
            "sentiment": sentiment,
            "stage": stage,
            "buying": buying,
            "confidence": confidence
        }

        prompt = generate_prompt(opp, scores)
        response = model.generate_content(prompt)

        return {
            "scores": scores,
            "suggestion": response.text.strip()
        }
    
    except Exception as e:
        return {
            "error": str(e)
        }
