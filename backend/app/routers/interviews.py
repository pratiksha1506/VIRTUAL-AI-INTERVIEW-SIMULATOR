from fastapi import APIRouter, Request, HTTPException, UploadFile, File, Form, Depends
from typing import Optional, List, Dict, Any
import json
from datetime import datetime

from ..models import CreateInterviewRequest, SubmitResponseResult, QuestionOut
from ..database import (
    create_interview, get_interview_by_id, update_interview_status,
    add_question, get_questions_for_interview, get_question_by_id,
    add_response, get_responses_for_interview,
    save_report, get_report_by_interview_id,
    get_configured_question_count
)
from .auth import get_current_user_from_request
from ..services.ai_service import generate_question
from ..services.evaluation_service import evaluate_single_response, generate_final_report
from ..services.resume_service import extract_text_from_file

router = APIRouter(prefix="/api/interviews", tags=["interviews"])

def require_auth_user(request: Request) -> Dict[str, Any]:
    user = get_current_user_from_request(request)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required.")
    return user

@router.post("/upload-resume")
async def upload_resume(file: UploadFile = File(...)):
    """Extracts text from uploaded resume file for personalization."""
    content = await file.read()
    if len(content) > 10 * 1024 * 1024:  # 10MB limit
        raise HTTPException(status_code=400, detail="File too large (maximum 10MB).")
    extracted_text = extract_text_from_file(content, file.filename or "resume.pdf")
    return {"filename": file.filename, "extracted_text": extracted_text}

@router.post("")
async def start_interview(payload: CreateInterviewRequest, request: Request):
    user = require_auth_user(request)
    q_count = payload.questionCount if payload.questionCount is not None else get_configured_question_count(payload.jobRole)
    interview = create_interview(
        candidate_id=user["id"],
        job_role=payload.jobRole,
        experience_level=payload.experienceLevel or "Mid-Level",
        interview_type=payload.interviewType,
        difficulty=payload.difficulty,
        question_count=q_count,
        duration_minutes=payload.durationMinutes or 15,
        camera_enabled=bool(payload.cameraEnabled),
        resume_text=payload.resumeText,
        status="in_progress"
    )

    # Generate First Question
    q_data = await generate_question(
        interview_id=interview["id"],
        job_role=interview["job_role"],
        experience_level=interview["experience_level"],
        interview_type=interview["interview_type"],
        difficulty=interview["difficulty"],
        sequence_num=1,
        total_questions=interview["question_count"],
        resume_text=interview.get("resume_text"),
        previous_qa=[]
    )

    q = add_question(
        interview_id=interview["id"],
        sequence_num=1,
        question_text=q_data["question_text"],
        question_type=q_data.get("question_type", interview["interview_type"]),
        topic=q_data.get("topic", "Introduction"),
        difficulty=q_data.get("difficulty", interview["difficulty"]),
        expected_keywords=q_data.get("expected_keywords", ""),
        context_notes=q_data.get("context_notes", "")
    )

    return {
        "interview": interview,
        "first_question": q
    }

@router.post("/{interview_id}/start")
async def start_scheduled_interview(interview_id: int, request: Request):
    """Initializes or resumes a scheduled interview session, generating Question 1 if needed."""
    user = require_auth_user(request)
    interview = get_interview_by_id(interview_id)
    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found.")

    if user["role"] != "admin" and interview["candidate_id"] != user["id"]:
        raise HTTPException(status_code=403, detail="Access denied. This interview is not assigned to your account.")

    if interview["status"] == "cancelled":
        raise HTTPException(status_code=400, detail="This interview has been cancelled by an administrator.")
    if interview["status"] == "missed":
        raise HTTPException(status_code=400, detail="This interview was missed and can no longer be attended.")
    if interview["status"] == "completed":
        return {
            "interview": interview,
            "status": "completed",
            "message": "This interview has already been completed."
        }

    # Transition scheduled to in_progress
    if interview["status"] == "scheduled":
        update_interview_status(interview_id, status="in_progress")
        interview["status"] = "in_progress"

    questions = get_questions_for_interview(interview_id)
    responses = get_responses_for_interview(interview_id)
    current_q = None

    if len(questions) == 0:
        # Generate First Question
        q_data = await generate_question(
            interview_id=interview["id"],
            job_role=interview["job_role"],
            experience_level=interview["experience_level"],
            interview_type=interview["interview_type"],
            difficulty=interview["difficulty"],
            sequence_num=1,
            total_questions=interview["question_count"],
            resume_text=interview.get("resume_text"),
            previous_qa=[]
        )

        current_q = add_question(
            interview_id=interview["id"],
            sequence_num=1,
            question_text=q_data["question_text"],
            question_type=q_data.get("question_type", interview["interview_type"]),
            topic=q_data.get("topic", "Introduction"),
            difficulty=q_data.get("difficulty", interview["difficulty"]),
            expected_keywords=q_data.get("expected_keywords", ""),
            context_notes=q_data.get("context_notes", "")
        )
        questions = [current_q]
    else:
        question_index = len(responses)
        if question_index < len(questions):
            current_q = questions[question_index]
        elif question_index < interview["question_count"]:
            prev_qa = [{"question": r.get("question_text", ""), "transcript": r.get("transcript", "")} for r in responses]
            next_seq = question_index + 1
            q_data = await generate_question(
                interview_id=interview["id"],
                job_role=interview["job_role"],
                experience_level=interview["experience_level"],
                interview_type=interview["interview_type"],
                difficulty=interview["difficulty"],
                sequence_num=next_seq,
                total_questions=interview["question_count"],
                resume_text=interview.get("resume_text"),
                previous_qa=prev_qa
            )
            current_q = add_question(
                interview_id=interview["id"],
                sequence_num=next_seq,
                question_text=q_data["question_text"],
                question_type=q_data.get("question_type", interview["interview_type"]),
                topic=q_data.get("topic", "Competency"),
                difficulty=q_data.get("difficulty", interview["difficulty"]),
                expected_keywords=q_data.get("expected_keywords", ""),
                context_notes=q_data.get("context_notes", "")
            )
            questions.append(current_q)

    total_q = interview["question_count"]
    interview_view = dict(interview)
    interview_view["total_questions"] = total_q

    return {
        "interview": interview_view,
        "questions": questions,
        "responses": responses,
        "current_question": current_q,
        "first_question": current_q,
        "question_index": len(responses)
    }

@router.get("/{interview_id}")
async def get_interview_details(interview_id: int, request: Request):
    user = require_auth_user(request)
    interview = get_interview_by_id(interview_id)
    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found.")

    if user["role"] != "admin" and interview["candidate_id"] != user["id"]:
        raise HTTPException(status_code=403, detail="Access denied. This interview is not assigned to your account.")

    # If the assigned candidate accesses a scheduled interview, transition it to in_progress
    if interview["status"] == "scheduled" and (user["role"] == "admin" or interview["candidate_id"] == user["id"]):
        update_interview_status(interview_id, status="in_progress")
        interview["status"] = "in_progress"

    questions = get_questions_for_interview(interview_id)
    responses = get_responses_for_interview(interview_id)

    # Determine current question
    current_q = None
    question_index = len(responses)
    if question_index < len(questions):
        current_q = questions[question_index]
    elif question_index < interview["question_count"] and interview["status"] == "in_progress":
        # Need to generate next question (or Question 1 if len(questions) == 0)
        prev_qa = [{"question": r.get("question_text", ""), "transcript": r.get("transcript", "")} for r in responses]
        next_seq = question_index + 1
        q_data = await generate_question(
            interview_id=interview["id"],
            job_role=interview["job_role"],
            experience_level=interview["experience_level"],
            interview_type=interview["interview_type"],
            difficulty=interview["difficulty"],
            sequence_num=next_seq,
            total_questions=interview["question_count"],
            resume_text=interview.get("resume_text"),
            previous_qa=prev_qa
        )
        current_q = add_question(
            interview_id=interview["id"],
            sequence_num=next_seq,
            question_text=q_data["question_text"],
            question_type=q_data.get("question_type", interview["interview_type"]),
            topic=q_data.get("topic", "Introduction" if next_seq == 1 else "Competency"),
            difficulty=q_data.get("difficulty", interview["difficulty"]),
            expected_keywords=q_data.get("expected_keywords", ""),
            context_notes=q_data.get("context_notes", "")
        )
        questions.append(current_q)

    # Format interview object for frontend compatibility
    total_q = interview["question_count"]
    interview_view = dict(interview)
    interview_view["total_questions"] = total_q

    return {
        "interview": interview_view,
        "questions": questions,
        "responses": responses,
        "current_question": current_q,
        "question_index": question_index
    }

@router.post("/{interview_id}/responses")
async def submit_answer(
    interview_id: int,
    request: Request,
    question_id: int = Form(...),
    response_duration: float = Form(0.0),
    transcript: str = Form(""),
    audio_file: Optional[UploadFile] = File(None),
    frames: Optional[str] = Form(None),
    framing_telemetry: Optional[str] = Form(None)
):
    user = require_auth_user(request)
    interview = get_interview_by_id(interview_id)
    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found.")
    if user["role"] != "admin" and interview["candidate_id"] != user["id"]:
        raise HTTPException(status_code=403, detail="Access denied.")

    question = get_question_by_id(question_id)
    if not question:
        raise HTTPException(status_code=404, detail="Question not found.")

    framing_info = None
    if framing_telemetry:
        try:
            framing_info = json.loads(framing_telemetry)
        except Exception:
            pass

    # Check if question is already answered (duplicate submission guard)
    existing_responses = get_responses_for_interview(interview_id)
    existing_resp = next((r for r in existing_responses if r.get("question_id") == question_id), None)
    if existing_resp:
        answered_count = len(existing_responses)
        total_required = interview["question_count"]
        is_completed = answered_count >= total_required
        questions = get_questions_for_interview(interview_id)
        next_q = next((q for q in questions if q["sequence_num"] == answered_count + 1), None)
        return {
            "analysis": {
                "overall_score": existing_resp.get("overall_score", 75),
                "content_score": existing_resp.get("content_score", 75),
                "technical_score": existing_resp.get("technical_score", 75),
                "communication_score": existing_resp.get("communication_score", 75),
                "problem_solving_score": existing_resp.get("problem_solving_score", 75),
                "facial_score": existing_resp.get("facial_score", 75),
            },
            "feedback": existing_resp.get("feedback", "Response previously recorded."),
            "interview_completed": is_completed,
            "next_question": next_q,
            "answered_count": answered_count,
            "total_questions": total_required
        }

    # Evaluate answer with LLM / fallback
    eval_result = await evaluate_single_response(
        question_text=question["question_text"],
        expected_keywords=question.get("expected_keywords", ""),
        transcript=transcript,
        duration_sec=response_duration,
        framing_info=framing_info,
        job_role=interview.get("job_role", ""),
        experience_level=interview.get("experience_level", ""),
        interview_type=interview.get("interview_type", ""),
        difficulty=interview.get("difficulty", "")
    )

    analysis = eval_result["analysis"]
    feedback = eval_result["feedback"]

    # Save to database
    add_response(
        interview_id=interview_id,
        question_id=question_id,
        transcript=transcript,
        duration_seconds=response_duration,
        content_score=analysis["content_score"],
        technical_score=analysis["technical_score"],
        communication_score=analysis["communication_score"],
        problem_solving_score=analysis["problem_solving_score"],
        facial_score=analysis["facial_score"],
        overall_score=analysis["overall_score"],
        feedback=feedback
    )

    # Check progress & next question
    all_responses = get_responses_for_interview(interview_id)
    answered_count = len(all_responses)
    total_required = interview["question_count"]

    is_completed = answered_count >= total_required

    next_q = None
    if is_completed:
        update_interview_status(interview_id, status="completed", completed_at=datetime.utcnow().isoformat())
    else:
        # Generate next question with context
        prev_qa = [{"question": r.get("question_text", ""), "transcript": r.get("transcript", "")} for r in all_responses]
        next_seq = answered_count + 1
        q_data = await generate_question(
            interview_id=interview_id,
            job_role=interview["job_role"],
            experience_level=interview["experience_level"],
            interview_type=interview["interview_type"],
            difficulty=interview["difficulty"],
            sequence_num=next_seq,
            total_questions=total_required,
            resume_text=interview.get("resume_text"),
            previous_qa=prev_qa
        )
        next_q = add_question(
            interview_id=interview_id,
            sequence_num=next_seq,
            question_text=q_data["question_text"],
            question_type=q_data.get("question_type", interview["interview_type"]),
            topic=q_data.get("topic", "Adaptive Follow-Up"),
            difficulty=q_data.get("difficulty", interview["difficulty"]),
            expected_keywords=q_data.get("expected_keywords", ""),
            context_notes=q_data.get("context_notes", "")
        )

    return {
        "analysis": analysis,
        "feedback": feedback,
        "interview_completed": is_completed,
        "next_question": next_q,
        "answered_count": answered_count,
        "total_questions": total_required
    }

@router.post("/{interview_id}/finish")
async def finish_interview(interview_id: int, request: Request):
    user = require_auth_user(request)
    interview = get_interview_by_id(interview_id)
    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found.")
    if user["role"] != "admin" and interview["candidate_id"] != user["id"]:
        raise HTTPException(status_code=403, detail="Access denied.")

    responses = get_responses_for_interview(interview_id)
    if not responses or len(responses) == 0:
        raise HTTPException(
            status_code=400,
            detail="Cannot complete interview without any recorded responses. At least one question must be answered."
        )

    update_interview_status(interview_id, status="completed", completed_at=datetime.utcnow().isoformat())

    # Generate or return cached report
    existing_report = get_report_by_interview_id(interview_id)
    if existing_report:
        return {"report": existing_report}

    report_data = await generate_final_report(
        job_role=interview["job_role"],
        experience_level=interview["experience_level"],
        interview_type=interview["interview_type"],
        difficulty=interview["difficulty"],
        responses=responses
    )

    saved = save_report(
        interview_id=interview_id,
        overall_score=report_data["overall_score"],
        content_score=report_data["content_score"],
        technical_score=report_data["technical_score"],
        communication_score=report_data["communication_score"],
        problem_solving_score=report_data["problem_solving_score"],
        scoring_engine=report_data["scoring_engine"],
        strengths=report_data["strengths"],
        weaknesses=report_data["weaknesses"],
        recommendations=report_data["recommendations"],
        practice_exercises=report_data["practice_exercises"],
        model_answers=report_data["model_answers"],
        presentation_obs=report_data.get("presentation_observations", {}),
        overall_feedback=report_data["overall_feedback"]
    )

    return {"report": saved}

@router.get("/{interview_id}/report")
async def get_interview_report(interview_id: int, request: Request):
    user = require_auth_user(request)
    interview = get_interview_by_id(interview_id)
    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found.")
    if user["role"] != "admin" and interview["candidate_id"] != user["id"]:
        raise HTTPException(status_code=403, detail="Access denied.")

    report = get_report_by_interview_id(interview_id)
    if not report:
        responses = get_responses_for_interview(interview_id)
        if not responses or len(responses) == 0:
            raise HTTPException(status_code=400, detail="No answers recorded for this interview. A report cannot be generated.")
        if interview["status"] != "completed":
            raise HTTPException(status_code=400, detail="Interview is still in progress and has not been completed.")

        report_data = await generate_final_report(
            job_role=interview["job_role"],
            experience_level=interview["experience_level"],
            interview_type=interview["interview_type"],
            difficulty=interview["difficulty"],
            responses=responses
        )
        report = save_report(
            interview_id=interview_id,
            overall_score=report_data["overall_score"],
            content_score=report_data["content_score"],
            technical_score=report_data["technical_score"],
            communication_score=report_data["communication_score"],
            problem_solving_score=report_data["problem_solving_score"],
            scoring_engine=report_data["scoring_engine"],
            strengths=report_data["strengths"],
            weaknesses=report_data["weaknesses"],
            recommendations=report_data["recommendations"],
            practice_exercises=report_data["practice_exercises"],
            model_answers=report_data["model_answers"],
            presentation_obs=report_data.get("presentation_observations", {}),
            overall_feedback=report_data["overall_feedback"]
        )

    responses = get_responses_for_interview(interview_id)
    return {
        "interview": interview,
        "report": report,
        "responses": responses
    }
