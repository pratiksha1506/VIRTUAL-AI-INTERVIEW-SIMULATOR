import json
import logging
import random
from typing import List, Dict, Any, Optional
import httpx
from ..config import GEMINI_API_KEY, OPENAI_API_KEY, LLM_MODEL

logger = logging.getLogger("ai_service")

# Static role question bank for intelligent local fallback & grounding
ROLE_QUESTION_BANKS = {
    "Software Developer": {
        "Technical": [
            {
                "topic": "Data Structures & Algorithms",
                "question": "Can you explain the trade-offs between an array and a linked list in terms of memory layout and runtime complexity for lookup, insertion, and deletion?",
                "expected": "array contiguous memory cache locality o1 lookup linked list pointers insertion deletion o1 at head"
            },
            {
                "topic": "System Architecture",
                "question": "What principles define a RESTful API, and how do you decide between REST and GraphQL for a high-traffic microservices architecture?",
                "expected": "stateless resource url http verbs over-fetching under-fetching client server caching graphql payload"
            },
            {
                "topic": "Concurrency & Databases",
                "question": "Explain ACID properties in relational databases and how connection pooling prevents resource exhaustion under sudden request spikes.",
                "expected": "atomicity consistency isolation durability transactions connection pool limit socket leak concurrency"
            },
            {
                "topic": "Web Performance",
                "question": "How does the browser event loop handle asynchronous tasks, microtasks (like Promises), and rendering updates?",
                "expected": "call stack event loop task queue microtask promise macrotask requestanimationframe non-blocking"
            }
        ],
        "Behavioral": [
            {
                "topic": "Problem Solving",
                "question": "Tell me about a challenging bug that was difficult to reproduce in development but occurred frequently in production. What was your diagnosis methodology?",
                "expected": "logs monitoring metrics reproduction race condition root cause postmortem regression testing"
            },
            {
                "topic": "Team Collaboration",
                "question": "Describe a scenario where you strongly disagreed with a peer or lead on a technical implementation choice. How did you advocate your perspective and reach consensus?",
                "expected": "respectful discussion benchmarks data trade-offs team alignment compromise objective criteria"
            }
        ],
        "Situational": [
            {
                "topic": "Production Incidents",
                "question": "A deployment passes all automated unit and integration tests, but 10 minutes after releasing to production, error rates spike and latency degrades. Walk me through your response protocol step by step.",
                "expected": "triage rollback incident communication investigate logs metrics isolate canary deployment fix"
            }
        ],
        "HR": [
            {
                "topic": "Career Goals",
                "question": "What attracted you to this software engineering role, and what technical domains or leadership skills do you want to master over the next 2-3 years?",
                "expected": "growth motivation impact technical depth mentorship engineering culture alignment"
            }
        ]
    },
    "Frontend Developer": {
        "Technical": [
            {
                "topic": "Core Web Vitals & Performance",
                "question": "How do you optimize Core Web Vitals such as Largest Contentful Paint (LCP) and Cumulative Layout Shift (CLS) on a content-heavy web application?",
                "expected": "lcp cls fid inp image optimization lazy loading font-display cdn critical css aspect-ratio layout stability"
            },
            {
                "topic": "State Management & Reactivity",
                "question": "Compare client-side global state management approaches (e.g., Redux, Zustand, Context API). What criteria do you use to choose between them?",
                "expected": "re-renders boilerplate selectors unidirectional data flow server cache zustand recoil context performance"
            },
            {
                "topic": "CSS Architecture & Accessibility",
                "question": "What techniques do you employ to guarantee WCAG 2.1 AA accessibility standards, keyboard navigation, and responsive typography across diverse viewports?",
                "expected": "aria labels semantic html contrast ratio focus management screen readers rem units responsive design"
            }
        ],
        "Behavioral": [
            {
                "topic": "Design Collaboration",
                "question": "How do you work with UI/UX designers when a requested animation or interaction pattern poses severe accessibility or performance degradation?",
                "expected": "collaboration alternatives user experience frame rate aria fallback graceful degradation empathy"
            }
        ]
    },
    "Backend Developer": {
        "Technical": [
            {
                "topic": "Distributed Systems",
                "question": "How do you handle data consistency and idempotency in distributed event-driven systems using message brokers like Kafka or RabbitMQ?",
                "expected": "idempotency keys outbox pattern eventual consistency deduplication saga pattern dead letter queue"
            },
            {
                "topic": "Database Optimization",
                "question": "Explain how database indexing works internally (such as B-Trees vs. Hash indices) and how you diagnose slow queries using EXPLAIN plans.",
                "expected": "b-tree index composite index table scan index seek query planner cardinality explain analyze"
            },
            {
                "topic": "Security & Authentication",
                "question": "Describe the architecture of a secure authentication and authorization pipeline using JWTs, refresh tokens, and rate limiting to prevent brute force attacks.",
                "expected": "jwt refresh token rotation http-only cookie csrf cors rate limiting redis expiry salt bcrypt"
            }
        ],
        "Behavioral": [
            {
                "topic": "Technical Debt",
                "question": "Tell me about a legacy backend service you had to refactor while maintaining zero downtime and backward compatibility for existing consumers.",
                "expected": "strangler fig pattern dual writing feature flags integration testing backward compatibility monitoring"
            }
        ]
    },
    "Data Analyst": {
        "Technical": [
            {
                "topic": "SQL & Query Optimization",
                "question": "Explain the behavioral difference between window functions (e.g., ROW_NUMBER, RANK, DENSE_RANK) and GROUP BY aggregations with practical examples.",
                "expected": "window functions partition by order by rank dense_rank group by collapse rows running totals"
            },
            {
                "topic": "Data Cleaning & Strategy",
                "question": "When working with a messy transactional dataset with missing values, outliers, and duplicate records, what is your standard validation and imputation strategy?",
                "expected": "data cleaning mean median imputation z-score iqr deduplication domain knowledge sensitivity analysis"
            }
        ],
        "Behavioral": [
            {
                "topic": "Executive Stakeholder Communication",
                "question": "Describe a scenario where your analytical findings contradicted the intuition of senior business stakeholders. How did you communicate the insights effectively?",
                "expected": "data storytelling visualizations clear charts business impact objective data confidence intervals"
            }
        ]
    },
    "HR Interview": {
        "HR": [
            {
                "topic": "Self Introduction & Alignment",
                "question": "Tell me about your professional background, your proudest engineering accomplishments, and what motivates you to seek this opportunity.",
                "expected": "career summary achievements passion collaboration values alignment impact"
            },
            {
                "topic": "Conflict Resolution",
                "question": "Can you describe a high-stakes team conflict or priority clash you experienced and the steps you took to achieve a constructive resolution?",
                "expected": "active listening communication empathy common goals constructive mediation professionalism"
            },
            {
                "topic": "Work Ethic & Growth",
                "question": "What is an area of development you have actively worked on over the past year, and how did you measure your improvement?",
                "expected": "self-awareness growth mindset feedback deliberate practice measurable progress maturity"
            }
        ],
        "Behavioral": [
            {
                "topic": "Handling Pressure",
                "question": "Describe a time when you were facing conflicting deadlines from multiple stakeholders. How did you prioritize and set realistic expectations?",
                "expected": "prioritization eisenhower matrix stakeholder communication delegation transparency deliverables"
            }
        ]
    }
}

async def call_gemini(prompt: str, system_instruction: str = "", max_tokens: int = 3500) -> Optional[tuple[str, str]]:
    """
    Call Google Gemini API using httpx with automatic model fallback.
    Returns tuple (clean_json_text, model_name) or None.
    """
    if not GEMINI_API_KEY:
        return None

    # Preferred candidate models in priority order
    candidate_models = []
    for m in [LLM_MODEL, "gemini-3.8-flash", "gemini-flash-latest", "gemini-3-flash-preview"]:
        if m and m not in candidate_models:
            candidate_models.append(m)

    payload = {
        "contents": [
            {
                "parts": [{"text": prompt}]
            }
        ],
        "generationConfig": {
            "temperature": 0.6,
            "maxOutputTokens": max_tokens,
            "responseMimeType": "application/json"
        }
    }
    if system_instruction:
        payload["systemInstruction"] = {
            "parts": [{"text": system_instruction}]
        }

    async with httpx.AsyncClient(timeout=12.0) as client:
        for model in candidate_models:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={GEMINI_API_KEY}"
            try:
                resp = await client.post(url, json=payload)
                if resp.status_code == 200:
                    data = resp.json()
                    candidates = data.get("candidates", [])
                    if candidates and "content" in candidates[0]:
                        parts = candidates[0]["content"].get("parts", [])
                        if parts and "text" in parts[0]:
                            text = parts[0]["text"].strip()
                            # Strip markdown formatting if returned
                            if text.startswith("```json"):
                                text = text[7:]
                            elif text.startswith("```"):
                                text = text[3:]
                            if text.endswith("```"):
                                text = text[:-3]
                            return text.strip(), model
                else:
                    logger.warning(f"Gemini API ({model}) returned status {resp.status_code}: {resp.text[:120]}")
            except Exception as e:
                logger.error(f"Gemini API call failed for {model}: {e}")
    return None

async def call_openai(messages: List[Dict[str, str]]) -> Optional[str]:
    """Call OpenAI API using httpx."""
    if not OPENAI_API_KEY:
        return None
    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "gpt-4o-mini",
        "messages": messages,
        "temperature": 0.7,
        "response_format": {"type": "json_object"}
    }
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.post(url, headers=headers, json=payload)
            if resp.status_code == 200:
                data = resp.json()
                return data["choices"][0]["message"]["content"]
            else:
                logger.warning(f"OpenAI API returned error {resp.status_code}: {resp.text}")
    except Exception as e:
        logger.error(f"OpenAI API call failed: {e}")
    return None

def local_heuristic_question(job_role: str, experience_level: str, interview_type: str,
                             difficulty: str, sequence_num: int, resume_text: Optional[str] = None,
                             previous_qa: Optional[List[Dict[str, str]]] = None) -> Dict[str, Any]:
    """
    Intelligent local heuristic question generator with context-awareness and adaptive follow-ups.
    Tagged explicitly as [LOCAL HEURISTIC ENGINE].
    """
    bank = ROLE_QUESTION_BANKS.get(job_role) or ROLE_QUESTION_BANKS["Software Developer"]
    type_pool = bank.get(interview_type)
    if not type_pool:
        # Flatten available categories
        flat = []
        for cat_list in bank.values():
            flat.extend(cat_list)
        type_pool = flat if flat else ROLE_QUESTION_BANKS["Software Developer"]["Technical"]

    asked_texts = [qa.get("question", "") for qa in (previous_qa or [])]

    # Check if we should ask an adaptive follow-up based on the previous answer
    if previous_qa and len(previous_qa) > 0 and sequence_num > 1:
        last_turn = previous_qa[-1]
        last_q = last_turn.get("question", "")
        last_a = last_turn.get("transcript", "").strip()

        # Follow-up reasoning
        if len(last_a.split()) < 18:
            return {
                "question_text": f"In your last response, you gave a concise summary. Could you dive deeper into the architectural implications, trade-offs, and how you would practically implement that in a production codebase?",
                "question_type": interview_type,
                "topic": "In-Depth Elaboration & Trade-offs",
                "difficulty": difficulty,
                "expected_keywords": "trade-offs edge cases practical implementation scaling reliability",
                "context_notes": "[Adaptive Follow-up: probing for architectural depth due to brief response]"
            }
        elif "scale" in last_a.lower() or "database" in last_a.lower() or "api" in last_a.lower():
            return {
                "question_text": f"You noted the importance of backend systems and scaling. If your traffic suddenly surged by 50x during a peak marketing event, what specific caching layers, rate limiting, and failure containment strategies would you enforce?",
                "expected_keywords": "caching redis cdn rate-limiting circuit breaker bulkhead queue degradation",
                "question_type": interview_type,
                "topic": "High-Load Scalability & Resilience",
                "difficulty": difficulty,
                "context_notes": "[Adaptive Follow-up: probing on mentioned scaling concepts]"
            }

    # If resume is provided and sequence == 1, tailor first question to resume
    if resume_text and len(resume_text) > 40 and sequence_num == 1:
        # Extract keywords from resume
        snippet = resume_text[:180].strip()
        return {
            "question_text": f"I see from your background experience in your profile: \"{snippet}...\". Could you walk me through the most technically complex architectural decision you owned in that work and how you validated its success?",
            "question_type": interview_type,
            "topic": "Resume Project Deep-Dive",
            "difficulty": difficulty,
            "expected_keywords": "architecture decision impact metrics validation lessons learned",
            "context_notes": "[Resume-Personalized Initial Question]"
        }

    # Unused question from pool
    unused = [q for q in type_pool if q["question"] not in asked_texts]
    selected = random.choice(unused) if unused else random.choice(type_pool)

    return {
        "question_text": selected["question"],
        "question_type": interview_type,
        "topic": selected.get("topic", "Core Competencies"),
        "difficulty": difficulty,
        "expected_keywords": selected.get("expected", ""),
        "context_notes": "[Curated Role Bank Question]"
    }

async def generate_question(interview_id: int, job_role: str, experience_level: str,
                            interview_type: str, difficulty: str, sequence_num: int,
                            total_questions: int, resume_text: Optional[str] = None,
                            previous_qa: Optional[List[Dict[str, str]]] = None) -> Dict[str, Any]:
    """
    Generate next dynamic question via real Gemini / OpenAI or graceful local heuristic engine.
    """
    system_prompt = (
        "You are an expert AI Technical Interviewer conducting a realistic, interactive mock interview. "
        "Your task is to generate the next interview question tailored to the candidate's target role, "
        "experience level, difficulty, and previous answers. Output ONLY valid JSON."
    )
    resume_section = ""
    if resume_text:
        resume_section = f"Candidate Resume Highlights:\n{resume_text[:1000]}\n"

    history_formatted = ""
    if previous_qa:
        history_formatted = "Previous Interview Turns:\n"
        for i, turn in enumerate(previous_qa, 1):
            history_formatted += f"Q{i}: {turn.get('question')}\nAnswer: {turn.get('transcript')}\n"

    latest_answer_emphasis = ""
    if previous_qa and len(previous_qa) > 0:
        latest = previous_qa[-1]
        latest_answer_emphasis = f"""
CRITICAL ADAPTIVE INSTRUCTION:
The candidate just answered the previous question (Q{len(previous_qa)}):
- Question Asked: "{latest.get('question')}"
- Candidate Answer: "{latest.get('transcript')}"

You MUST generate the next question (Question {sequence_num}) directly building upon, questioning, or advancing from this specific answer:
- If the candidate's answer was technically sound, probe deeper into practical tradeoffs, edge cases, failure scenarios, or architectural scalability related to what they said.
- If the candidate's answer was incomplete or vague, ask a focused question testing the core concept they struggled with or omitted.
- If the candidate mentioned specific technologies, frameworks, or patterns (e.g., caching, databases, indexing, concurrency, async), formulate your next question specifically around those mentioned concepts.
- Do NOT jump to an unrelated generic question. The question must feel like a live, intelligent human conversation.
"""

    user_prompt = f"""
Target Job Role: {job_role}
Experience Level: {experience_level}
Interview Type: {interview_type}
Target Difficulty: {difficulty}
Current Question Number: {sequence_num} of {total_questions}
{resume_section}
{history_formatted}
{latest_answer_emphasis}

Instructions:
1. If this is question 1 and a resume snippet is provided, ask a relevant opening question grounded in their stated experience.
2. If previous answers exist, demonstrate context awareness: ask a natural follow-up probing deeper into any unclear claims, exploring edge cases, or transitioning smoothly to the next essential competency.
3. Match the requested difficulty ({difficulty}) and role ({job_role}).
4. Ensure the question is clear, realistic, and spoken-friendly when read aloud by text-to-speech.
5. Return JSON with format:
{{
  "question_text": "The exact question text to speak aloud",
  "question_type": "{interview_type}",
  "topic": "Specific technical or behavioral topic",
  "difficulty": "{difficulty}",
  "expected_keywords": "comma separated key concepts expected in a strong answer",
  "context_notes": "Brief reason why this question was selected"
}}
"""

    # 1. Attempt Gemini if configured
    gemini_res = await call_gemini(user_prompt, system_instruction=system_prompt)
    if gemini_res:
        text, used_model = gemini_res
        try:
            data = json.loads(text)
            if "question_text" in data:
                data["engine"] = f"Google Gemini ({used_model})"
                return data
        except Exception as e:
            logger.warning(f"Failed to parse Gemini response: {e}")

    # 2. Attempt OpenAI if configured
    openai_resp = await call_openai([
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ])
    if openai_resp:
        try:
            data = json.loads(openai_resp)
            if "question_text" in data:
                data["engine"] = "OpenAI (GPT-4o-mini)"
                return data
        except Exception as e:
            logger.warning(f"Failed to parse OpenAI response: {e}")

    # 3. Fallback to Local Heuristic Engine
    local_data = local_heuristic_question(
        job_role=job_role,
        experience_level=experience_level,
        interview_type=interview_type,
        difficulty=difficulty,
        sequence_num=sequence_num,
        resume_text=resume_text,
        previous_qa=previous_qa
    )
    local_data["engine"] = "[Local Heuristic Engine: Add GEMINI_API_KEY in .env for live LLM]"
    return local_data
