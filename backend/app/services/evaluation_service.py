import re
import json
import logging
from typing import List, Dict, Any, Optional
from .ai_service import call_gemini, call_openai
from ..config import GEMINI_API_KEY, OPENAI_API_KEY, LLM_MODEL

logger = logging.getLogger("evaluation_service")

FILLER_WORDS = ["um", "uh", "umm", "uhh", "like", "you know", "actually", "basically", "i mean", "sort of", "kind of"]

def calculate_wpm(text: str, duration_sec: float) -> int:
    if duration_sec <= 0:
        return 0
    words = len(re.findall(r"\b\w+\b", text))
    return int((words / max(duration_sec, 1.0)) * 60)

def count_fillers(text: str) -> int:
    lower = f" {text.lower()} "
    count = 0
    for fw in FILLER_WORDS:
        pattern = r"\b" + re.escape(fw) + r"\b"
        count += len(re.findall(pattern, lower))
    return count

def _safe_json_parse(text: str) -> Optional[Dict[str, Any]]:
    if not text:
        return None
    cleaned = text.strip()
    if cleaned.startswith("```json"):
        cleaned = cleaned[7:]
    elif cleaned.startswith("```"):
        cleaned = cleaned[3:]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    cleaned = cleaned.strip()

    try:
        return json.loads(cleaned)
    except Exception:
        pass

    first_brace = cleaned.find("{")
    last_brace = cleaned.rfind("}")
    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
        try:
            return json.loads(cleaned[first_brace:last_brace + 1])
        except Exception:
            pass
    return None

def calculate_keyword_overlap(transcript: str, expected_keywords: str) -> int:
    if not expected_keywords:
        return 65
    t_words = set(re.findall(r"[a-z0-9]+", transcript.lower()))
    k_words = set(re.findall(r"[a-z0-9]+", expected_keywords.lower()))
    if not k_words:
        return 60
    hits = len(t_words.intersection(k_words))
    ratio = hits / len(k_words)
    return min(100, int(ratio * 120))

async def evaluate_single_response(question_text: str, expected_keywords: str,
                                   transcript: str, duration_sec: float,
                                   job_role: str = "Software Developer",
                                   experience_level: str = "Mid-Level",
                                   interview_type: str = "Technical",
                                   difficulty: str = "Medium",
                                   framing_info: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Evaluates an individual answer turn using real Gemini model with intelligent fallback.
    """
    words = len(re.findall(r"\b\w+\b", transcript))
    wpm = calculate_wpm(transcript, duration_sec)
    fillers = count_fillers(transcript)

    # Presentation visual score (local positioning aid only)
    facial_score = None
    visual_feedback = "Webcam mode disabled."
    if framing_info:
        is_centered = framing_info.get("is_centered", True)
        lighting = framing_info.get("lighting", "Good")
        f_score = 85
        if not is_centered:
            f_score -= 15
        if lighting != "Good":
            f_score -= 10
        facial_score = max(50, min(100, f_score))
        visual_feedback = f"Framing: {'Centered' if is_centered else 'Slightly off-center'}; Lighting: {lighting}."

    # Speech delivery heuristic summary
    speech_summary = f"{wpm} WPM, {fillers} filler words."

    # 1. Attempt Real Gemini Evaluation
    eval_prompt = f"""You are an expert hiring committee interviewer evaluating a candidate's answer during a mock interview.
Target Job Role: {job_role}
Experience Level: {experience_level}
Interview Type: {interview_type}
Difficulty: {difficulty}

Question Asked:
"{question_text}"

Candidate's Actual Answer:
"{transcript}"

Expected Concepts:
"{expected_keywords}"

Instructions:
Evaluate the candidate's answer rigorously, constructively, and objectively.
- Content score (0-100): How relevant and complete is the answer?
- Technical score (0-100): How accurate, deep, and architecturally sound is the technical understanding?
- Communication score (0-100): How structured, articulate, and clear is the delivery?
- Problem solving score (0-100): How effective is their reasoning and trade-off analysis?
- Overall score (0-100): Weighted synthesis of the above.
- Strengths: 2-3 specific bullet points explicitly citing what they explained well.
- Points to Refine: 2-3 specific bullet points detailing what they missed, inaccuracies, or how to reach staff/senior level.
- Speech feedback: 1 concise sentence about technical delivery and clarity.

Return strictly valid JSON with this exact schema:
{{
  "content_score": int,
  "technical_score": int,
  "communication_score": int,
  "problem_solving_score": int,
  "overall_score": int,
  "strengths": [str, str],
  "improvements": [str, str],
  "speech_feedback": str
}}
"""
    gemini_res = await call_gemini(eval_prompt)
    if gemini_res:
        text, used_model = gemini_res
        try:
            ai_data = json.loads(text)
            content_score = int(ai_data.get("content_score", 75))
            technical_score = int(ai_data.get("technical_score", 75))
            communication_score = int(ai_data.get("communication_score", 80))
            problem_solving_score = int(ai_data.get("problem_solving_score", 75))
            overall_score = int(ai_data.get("overall_score", 75))
            strengths = ai_data.get("strengths") or ["Provided relevant domain explanation."]
            improvements = ai_data.get("improvements") or ["Continue elaborating on practical edge cases."]
            speech_feedback = ai_data.get("speech_feedback") or speech_summary

            # Compute speech confidence from cadence and fillers
            pace_penalty = min(30, abs(wpm - 130) * 0.4) if wpm > 0 else 20
            filler_ratio = fillers / max(words, 1)
            speech_confidence = max(40, min(96, int(100 - (filler_ratio * 400) - (pace_penalty * 0.7))))

            return {
                "analysis": {
                    "content_score": content_score,
                    "technical_score": technical_score,
                    "communication_score": communication_score,
                    "problem_solving_score": problem_solving_score,
                    "speech_confidence": speech_confidence,
                    "facial_score": facial_score,
                    "overall_score": overall_score,
                    "engine": f"Google Gemini ({used_model})"
                },
                "feedback": {
                    "strengths": strengths,
                    "improvements": improvements,
                    "speech_feedback": f"{speech_feedback} ({wpm} WPM)",
                    "visual_feedback": visual_feedback
                }
            }
        except Exception as e:
            logger.warning(f"Error parsing Gemini turn evaluation: {e}")

    # 2. Local Heuristic Fallback
    overlap = calculate_keyword_overlap(transcript, expected_keywords)
    if words < 8:
        content_score = 35
        technical_score = 30
    elif words < 25:
        content_score = max(45, min(80, 45 + int(overlap * 0.4)))
        technical_score = max(40, min(82, 40 + int(overlap * 0.45)))
    else:
        content_score = max(55, min(96, 55 + int(overlap * 0.45)))
        technical_score = max(50, min(95, 52 + int(overlap * 0.48)))

    filler_ratio = fillers / max(words, 1)
    pace_penalty = min(35, abs(wpm - 130) * 0.4) if wpm > 0 else 25
    fluency = max(30, int(100 - (filler_ratio * 350) - pace_penalty))
    communication_score = max(35, min(95, fluency))
    problem_solving_score = max(40, min(94, int((content_score * 0.6) + (communication_score * 0.4))))
    speech_confidence = max(40, min(96, int(100 - (filler_ratio * 400) - (pace_penalty * 0.7))))
    overall_score = int(content_score * 0.40 + technical_score * 0.35 + communication_score * 0.25)

    strengths = []
    improvements = []
    if words >= 30:
        strengths.append("Provided an elaborated and detailed explanation.")
    if overlap >= 50:
        strengths.append("Addressed fundamental domain concepts accurately.")
    if 110 <= wpm <= 160:
        strengths.append(f"Good speaking cadence ({wpm} WPM).")
    if not strengths:
        strengths.append("Communicated clearly and directly.")

    if words < 20:
        improvements.append("Expand on your reasoning with concrete examples or architectural trade-offs.")
    if fillers > 2:
        improvements.append(f"Noticed {fillers} filler words ({', '.join(FILLER_WORDS[:3])}) — pause silently instead.")
    if wpm > 170:
        improvements.append(f"Speaking rate was brisk ({wpm} WPM) — slow down slightly for technical clarity.")
    elif wpm < 90 and words > 0:
        improvements.append(f"Speaking rate was slow ({wpm} WPM) — aim for continuous delivery.")
    if not improvements:
        improvements.append("Solid answer. Continue reinforcing with industry best practices.")

    return {
        "analysis": {
            "content_score": content_score,
            "technical_score": technical_score,
            "communication_score": communication_score,
            "problem_solving_score": problem_solving_score,
            "speech_confidence": speech_confidence,
            "facial_score": facial_score,
            "overall_score": overall_score,
            "engine": "[Local Heuristic Engine: Add GEMINI_API_KEY in .env for live LLM]"
        },
        "feedback": {
            "strengths": strengths,
            "improvements": improvements,
            "speech_feedback": f"{wpm} words/min, {fillers} filler words, {words} total words.",
            "visual_feedback": visual_feedback
        }
    }

async def generate_final_report(job_role: str, experience_level: str, interview_type: str,
                                difficulty: str, responses: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Generates a full comprehensive report when the interview concludes.
    Uses Gemini / OpenAI if available, or rich local heuristic synthesis.
    """
    if not responses:
        return {
            "overall_score": 0,
            "content_score": 0,
            "technical_score": 0,
            "communication_score": 0,
            "problem_solving_score": 0,
            "scoring_engine": "[No responses recorded]",
            "strengths": [],
            "weaknesses": ["No answers recorded during the session."],
            "recommendations": ["Complete at least one full question."],
            "practice_exercises": [],
            "model_answers": [],
            "presentation_observations": {},
            "overall_feedback": "The interview was concluded without recording candidate responses."
        }

    # Aggregate turn scores
    avg_content = int(sum(r["content_score"] for r in responses) / len(responses))
    avg_tech = int(sum(r["technical_score"] for r in responses) / len(responses))
    avg_comm = int(sum(r["communication_score"] for r in responses) / len(responses))
    avg_prob = int(sum(r["problem_solving_score"] for r in responses) / len(responses))
    overall_score = int(avg_content * 0.35 + avg_tech * 0.35 + avg_comm * 0.15 + avg_prob * 0.15)

    # Prepare turns for LLM
    turns_for_prompt = []
    for i, r in enumerate(responses, 1):
        turns_for_prompt.append({
            "number": i,
            "question": r.get("question_text", ""),
            "answer": r.get("transcript", ""),
            "duration": r.get("duration_seconds", 0)
        })

    prompt = f"""
You are a Lead Hiring Committee Chair conducting an evaluation of a candidate's completed interview.
Job Role: {job_role}
Level: {experience_level}
Type: {interview_type}
Difficulty: {difficulty}

Candidate Responses:
{json.dumps(turns_for_prompt, indent=2)}

Generate a thorough, rigorous, and constructive final evaluation report.
Requirements:
1. Provide overall score (0-100) and transparent sub-scores for Content, Technical Depth, Communication, and Problem Solving.
2. For each question, provide:
   - "question_number": int
   - "critique": constructive 2-3 sentence review of their specific response
   - "score": score for this question (0-100)
   - "model_answer": A high-quality, professional 3-5 sentence model answer demonstrating how a top candidate would answer this.
3. "strengths": 3-4 bullet points highlighting specific technical or behavioral strengths shown in these answers.
4. "weaknesses": 3-4 bullet points outlining specific technical gaps, missed edge cases, or communication weaknesses.
5. "recommendations": 3-4 practical study topics to review.
6. "practice_exercises": 2-3 concrete coding, architectural, or behavioral exercises to prepare for next rounds.
7. "overall_feedback": A comprehensive 3-paragraph summary of their performance, readiness for the role, and roadmap to improve.

Return strictly valid JSON in this schema:
{{
  "overall_score": int,
  "content_score": int,
  "technical_score": int,
  "communication_score": int,
  "problem_solving_score": int,
  "model_answers": [
    {{"question_number": int, "question": str, "critique": str, "score": int, "model_answer": str}}
  ],
  "strengths": [str],
  "weaknesses": [str],
  "recommendations": [str],
  "practice_exercises": [str],
  "overall_feedback": str
}}
"""

    # 1. Try Gemini
    gemini_res = await call_gemini(prompt, max_tokens=4000)
    if gemini_res:
        text, used_model = gemini_res
        report_data = _safe_json_parse(text)
        if report_data and isinstance(report_data, dict) and "overall_score" in report_data:
            report_data["scoring_engine"] = f"Google Gemini ({used_model})"
            avg_wpm = int(sum(calculate_wpm(r.get("transcript", ""), r.get("duration_seconds", 30)) for r in responses) / max(len(responses), 1))
            filler_count = sum(count_fillers(r.get("transcript", "")) for r in responses)
            report_data["presentation_observations"] = {
                "disclaimer": "Presentation telemetry is an approximate positioning aid only. It does not measure personality or hireability.",
                "avg_wpm": avg_wpm,
                "filler_word_total": filler_count
            }
            if not isinstance(report_data.get("model_answers"), list):
                report_data["model_answers"] = []
            if not isinstance(report_data.get("strengths"), list):
                report_data["strengths"] = ["Demonstrated clear technical domain concepts."]
            if not isinstance(report_data.get("weaknesses"), list):
                report_data["weaknesses"] = ["Continue deepening distributed systems experience."]
            if not isinstance(report_data.get("recommendations"), list):
                report_data["recommendations"] = ["Review edge-case fault-tolerance and latency budgets."]
            if not isinstance(report_data.get("practice_exercises"), list):
                report_data["practice_exercises"] = ["Simulate live database partitioning scenarios."]
            if not report_data.get("overall_feedback"):
                report_data["overall_feedback"] = "Solid performance throughout the mock interview session."
            return report_data
        else:
            logger.warning(f"Could not parse valid Gemini report JSON: {text[:150] if text else 'None'}")

    # 2. Try OpenAI
    openai_resp = await call_openai([
        {"role": "system", "content": "You are a Lead Hiring Committee Chair. Output valid JSON."},
        {"role": "user", "content": prompt}
    ])
    if openai_resp:
        report_data = _safe_json_parse(openai_resp)
        if report_data and isinstance(report_data, dict) and "overall_score" in report_data:
            report_data["scoring_engine"] = "OpenAI (GPT-4o-mini)"
            avg_wpm = int(sum(calculate_wpm(r.get("transcript", ""), r.get("duration_seconds", 30)) for r in responses) / max(len(responses), 1))
            filler_count = sum(count_fillers(r.get("transcript", "")) for r in responses)
            report_data["presentation_observations"] = {
                "disclaimer": "Presentation telemetry is an approximate positioning aid only. It does not measure personality or hireability.",
                "avg_wpm": avg_wpm,
                "filler_word_total": filler_count
            }
            return report_data
        else:
            logger.warning("Could not parse valid OpenAI report JSON.")

    # 3. Local Heuristic Synthesis
    model_answers = []
    for i, r in enumerate(responses, 1):
        q_text = r.get("question_text", f"Question {i}")
        transcript = r.get("transcript", "")
        q_score = r.get("overall_score", 70)

        # Generate custom model answer
        model_answers.append({
            "question_number": i,
            "question": q_text,
            "critique": f"Candidate gave a {len(transcript.split())}-word response covering core ideas with {q_score}% relevance.",
            "score": q_score,
            "model_answer": f"When addressing {q_text[:70]}..., an ideal response defines core architecture, details practical trade-offs (e.g. latency vs. consistency), mentions monitoring/logging, and shares a real-world edge-case mitigation."
        })

    strengths = [
        f"Demonstrated good baseline domain knowledge in {job_role}.",
        "Maintained consistent engagement across all interview prompts.",
        "Clear articulation of technical concepts without excessive pauses."
    ]
    weaknesses = [
        "Could articulate deeper trade-offs regarding system scale and edge cases.",
        "Include more quantifiable metrics and real-world outcomes in situational answers.",
        "Structure responses using the STAR methodology (Situation, Task, Action, Result) for behavioral questions."
    ]
    recommendations = [
        f"Deepen knowledge in {job_role} core architecture and performance patterns.",
        "Practice mock interview answers under a 2-minute timer to tighten delivery conciseness.",
        "Review failure modes, incident post-mortems, and distributed systems principles."
    ]
    practice_exercises = [
        "Exercise 1: Design a high-concurrency rate-limiter and articulate memory vs. consistency trade-offs.",
        "Exercise 2: Write out 3 STAR-format stories highlighting technical leadership under pressure."
    ]
    overall_feedback = (
        f"The candidate completed {len(responses)} questions for the {experience_level} {job_role} interview, "
        f"achieving an overall score of {overall_score}/100. "
        f"Technical responses demonstrated a strong foundational understanding ({avg_tech}/100) with solid communication clarity ({avg_comm}/100). "
        "To reach higher seniority levels, prioritize explaining system resilience, edge-case mitigation, and end-to-end impact."
    )

    return {
        "overall_score": overall_score,
        "content_score": avg_content,
        "technical_score": avg_tech,
        "communication_score": avg_comm,
        "problem_solving_score": avg_prob,
        "scoring_engine": "[Local Heuristic Engine: Add GEMINI_API_KEY in .env for live LLM]",
        "strengths": strengths,
        "weaknesses": weaknesses,
        "recommendations": recommendations,
        "practice_exercises": practice_exercises,
        "model_answers": model_answers,
        "presentation_observations": {
            "disclaimer": "Presentation telemetry is an approximate positioning aid only. It does not measure personality or hireability.",
            "avg_wpm": int(sum(calculate_wpm(r["transcript"], r["duration_seconds"]) for r in responses) / len(responses)),
            "filler_word_total": sum(count_fillers(r["transcript"]) for r in responses)
        },
        "overall_feedback": overall_feedback
    }
