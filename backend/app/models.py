from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any

class RegisterRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    email: str = Field(..., pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    password: str = Field(..., min_length=8)

class LoginRequest(BaseModel):
    email: str = Field(..., pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    password: str

class CreateInterviewRequest(BaseModel):
    jobRole: str
    experienceLevel: Optional[str] = "Mid-Level"
    interviewType: str = "Technical"
    difficulty: str = "Medium"
    questionCount: Optional[int] = Field(None, ge=1, le=50)
    durationMinutes: Optional[int] = Field(15, ge=3, le=60)
    cameraEnabled: Optional[bool] = False
    resumeText: Optional[str] = None

class ScheduleInterviewRequest(BaseModel):
    candidateId: int
    jobRole: str
    interviewType: str = "Technical"
    difficulty: str = "Medium"
    questionCount: Optional[int] = Field(None, ge=1, le=50)
    scheduledDate: Optional[str] = None
    scheduledTime: Optional[str] = None

class SettingsUpdateRequest(BaseModel):
    defaultQuestionCount: Optional[int] = Field(None, ge=1, le=50)
    key: Optional[str] = None
    value: Optional[Any] = None
    roleOverrides: Optional[Dict[str, int]] = None

class QuestionOut(BaseModel):
    id: int
    sequence_num: int
    question_text: str
    question_type: str
    topic: Optional[str]
    difficulty: str
    expected_keywords: Optional[str] = None
    context_notes: Optional[str] = None

class ResponseFeedback(BaseModel):
    strengths: List[str]
    improvements: List[str]
    speech_feedback: Optional[str] = None
    visual_feedback: Optional[str] = None

class ResponseAnalysis(BaseModel):
    content_score: int
    technical_score: int
    communication_score: int
    problem_solving_score: int
    speech_confidence: int
    facial_score: Optional[int] = None
    overall_score: int

class SubmitResponseResult(BaseModel):
    analysis: ResponseAnalysis
    feedback: ResponseFeedback
    interview_completed: bool
    next_question: Optional[QuestionOut] = None
    remaining_time_seconds: Optional[int] = None
