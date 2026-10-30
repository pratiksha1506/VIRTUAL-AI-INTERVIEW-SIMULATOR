# AI-Powered Mock Interview Simulator

A full-stack, AI-powered mock interview platform featuring dynamic, context-aware question generation, interactive voice synthesis (TTS), live speech recognition with editable transcripts (STT), consent-based local camera presentation assistance, and comprehensive hiring-committee feedback reports.

---

## 🌟 Key Features

1. **Adaptive AI Question Engine**:
   - Continuous, multi-turn interview question generation until configured question count or duration is reached.
   - Tailored to target roles (Software Developer, Frontend Developer, Backend Developer, Data Analyst, HR Interview) and seniority levels (Entry, Mid, Senior, Lead).
   - Generates intelligent context-aware follow-up questions probing deeper into trade-offs and concepts mentioned in the candidate's actual answers.
   - Optional resume text extraction (PDF, DOCX, TXT) to personalize initial questions to the candidate's real-world projects.

2. **Real AI Integration & Transparent Fallbacks**:
   - Supports live **Google Gemini API** (`gemini-2.5-flash`, `gemini-1.5-flash`) and **OpenAI API** (`gpt-4o-mini`).
   - If no API key is configured, automatically and smoothly falls back to an intelligent local heuristic engine with role-specific depth.
   - All fallback outputs are clearly labeled in the UI as `[Local Heuristic Engine: Add GEMINI_API_KEY in .env for live LLM]`.

3. **Interactive Voice & Editable Transcripts**:
   - Real Text-to-Speech (TTS) questions with audio controls: Replay, Pause, Resume, and Mute.
   - Real-time Speech-to-Text (STT) using the Web Speech API.
   - **In-place Editable Transcript Box**: Candidates can review, edit, format, or type code directly before submitting.
   - Instant toggle between voice recording and manual text typing anytime.

4. **Consent-Based Local Webcam Guidance**:
   - Optional camera feature with explicit consent toggle (works 100% without camera).
   - Real-time client-side face framing and scene lighting checks (Luminance histogram: Good, Low Light, Overexposed).
   - **Ethical Compliance**: Runs strictly locally on HTML5 Canvas; no video frames are stored or uploaded without consent. Presentation metrics are positioning aids only and never used to infer candidate personality or hiring decisions.

5. **Comprehensive Final Feedback Reports**:
   - Transparent scoring rubrics: Overall Readiness, Technical Depth, Content Relevance, Communication & Fluency, and Problem Solving.
   - Question-by-question breakdown with the candidate's actual spoken transcript vs. senior-level model answer.
   - Actionable strengths, areas for improvement, and concrete practice exercises.
   - Separate presentation observations (speaking WPM, filler words, framing).
   - Clean print / "Save as PDF" styling.

6. **Candidate & Admin Dashboards**:
   - Candidate history, average score tracking, and scheduled session launches.
   - Recruiter/Admin console to schedule interviews, inspect candidate directories, and review performance reports.

---

## 🚀 Setup and Run Instructions

### 1. Prerequisites
- Python 3.10+ (tested on Python 3.13)
- Modern web browser (Chrome, Edge, or Brave recommended for Web Speech STT)

### 2. Install Dependencies
```bash
pip install -r backend/requirements.txt
```

### 3. (Optional) Configure API Credentials
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```
Open `.env` and set your key:
```env
GEMINI_API_KEY=your_gemini_api_key_here
# or
OPENAI_API_KEY=your_openai_api_key_here
```
> **Note**: If left blank, the application will automatically run with the built-in local adaptive heuristic engine and clearly label it in the UI.

### 4. Start the Application
Run the FastAPI backend server:
```bash
python -m uvicorn backend.app.main:app --port 8000 --reload
```
Open your browser and navigate to:
```
http://localhost:8000
```
The FastAPI backend serves both the API endpoints (`/api/...`) and the frontend UI directly.

---

## 🔑 Demo Credentials

- **Admin Login**: `admin@demo.com` / `admin123` (pre-seeded automatically)
- **Candidate Account**: Register any account on `register.html` or sign in with existing credentials.

---

## 🧪 Automated Verification Suite

Run the full end-to-end backend integration tests:
```bash
python backend/test_backend.py
```
This tests:
- Server health and provider status
- Candidate registration and session persistence
- Admin authentication and candidate management
- Interview creation and first question generation
- Context-aware answer evaluation and follow-up generation
- Interview conclusion and comprehensive final report generation
