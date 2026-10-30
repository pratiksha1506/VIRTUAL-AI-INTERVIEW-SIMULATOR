from fastapi import APIRouter, Request, HTTPException
from typing import Dict, Any, List
from .auth import get_current_user_from_request
from ..database import get_interviews_for_candidate, get_report_by_interview_id

router = APIRouter(prefix="/api/candidate", tags=["candidate"])

def require_candidate(request: Request) -> Dict[str, Any]:
    user = get_current_user_from_request(request)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required.")
    return user

@router.get("/dashboard")
async def get_candidate_dashboard(request: Request):
    user = require_candidate(request)
    all_interviews = get_interviews_for_candidate(user["id"])

    scheduled = [i for i in all_interviews if i["status"] == "scheduled"]
    in_progress = [i for i in all_interviews if i["status"] == "in_progress"]
    completed = [i for i in all_interviews if i["status"] == "completed"]
    cancelled = [i for i in all_interviews if i["status"] == "cancelled"]
    missed = [i for i in all_interviews if i["status"] == "missed"]

    # Calculate average scores from completed reports
    total_scores = []
    comm_scores = []
    tech_scores = []

    for item in completed:
        report = get_report_by_interview_id(item["id"])
        if report:
            item["report"] = report
            total_scores.append(report["overall_score"])
            comm_scores.append(report["communication_score"])
            tech_scores.append(report["technical_score"])

    avg_overall = int(sum(total_scores) / len(total_scores)) if total_scores else 0
    avg_comm = int(sum(comm_scores) / len(comm_scores)) if comm_scores else 0
    avg_tech = int(sum(tech_scores) / len(tech_scores)) if tech_scores else 0

    return {
        "user": user,
        "metrics": {
            "total_interviews": len(all_interviews),
            "completed_count": len(completed),
            "scheduled_count": len(scheduled),
            "in_progress_count": len(in_progress),
            "avg_overall": avg_overall,
            "avg_communication": avg_comm,
            "avg_technical": avg_tech
        },
        "upcoming": scheduled + in_progress,
        "scheduled": scheduled,
        "active_sessions": in_progress,
        "recent_completed": completed[:5],
        "cancelled": cancelled,
        "missed": missed
    }

@router.get("/history")
async def get_candidate_history(request: Request):
    user = require_candidate(request)
    all_interviews = get_interviews_for_candidate(user["id"])
    for item in all_interviews:
        if item["status"] == "completed":
            item["report"] = get_report_by_interview_id(item["id"])
            item["overall_score"] = item["report"]["overall_score"] if item["report"] else None
    return {"interviews": all_interviews, "history": all_interviews}
