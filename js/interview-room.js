/**
 * interview-room.js — Complete AI Voice & Video Mock Interview Engine
 * Connects to the FastAPI backend, supports real speech recognition & synthesis,
 * editable live transcripts, dynamic context-aware questions, and local presentation assistance.
 */
(function () {
  const params = new URLSearchParams(window.location.search);
  const interviewId = params.get("id");
  if (!interviewId) {
    window.location.href = "candidate-dashboard.html";
    return;
  }

  // DOM Elements
  const qCounter = document.getElementById("qCounter");
  const diffBadge = document.getElementById("diffBadge");
  const timerBadge = document.getElementById("timerBadge");
  const qType = document.getElementById("qType");
  const qTopic = document.getElementById("qTopic");
  const qText = document.getElementById("qText");
  const progressDots = document.getElementById("progressDots");
  const aiEngineText = document.getElementById("aiEngineText");

  // Voice playback controls
  const replayQuestionBtn = document.getElementById("replayQuestionBtn");
  const pauseAudioBtn = document.getElementById("pauseAudioBtn");
  const muteAudioBtn = document.getElementById("muteAudioBtn");
  const aiSpeakerBox = document.getElementById("aiSpeakerBox");
  const speakingWave = document.getElementById("speakingWave");
  const interviewerStateBadge = document.getElementById("interviewerStateBadge");
  const speakingHelp = document.getElementById("speakingHelp");

  // Candidate Answer controls
  const startBtn = document.getElementById("startBtn");
  const stopBtn = document.getElementById("stopBtn");
  const retryBtn = document.getElementById("retryBtn");
  const submitBtn = document.getElementById("submitBtn");
  const toggleInputModeBtn = document.getElementById("toggleInputModeBtn");
  const recordingStatus = document.getElementById("recordingStatus");
  const recordingError = document.getElementById("recordingError");
  const recordingIndicator = document.getElementById("recordingIndicator");
  const answerTimerBadge = document.getElementById("answerTimerBadge");
  const editableTranscript = document.getElementById("editableTranscript");
  const wordCountBadge = document.getElementById("wordCountBadge");
  const endInterviewEarlyBtn = document.getElementById("endInterviewEarlyBtn");

  // Feedback Panel
  const resultPanel = document.getElementById("resultPanel");
  const scoreContent = document.getElementById("scoreContent");
  const scoreTech = document.getElementById("scoreTech");
  const scoreCommunication = document.getElementById("scoreCommunication");
  const scoreOverall = document.getElementById("scoreOverall");
  const strengthsList = document.getElementById("strengthsList");
  const improvementsList = document.getElementById("improvementsList");
  const speechObsText = document.getElementById("speechObsText");
  const visualObsText = document.getElementById("visualObsText");
  const nextQuestionBtn = document.getElementById("nextQuestionBtn");

  // Camera elements
  const cameraPreview = document.getElementById("cameraPreview");
  const cameraBox = document.getElementById("cameraBox");
  const cameraPlaceholder = document.getElementById("cameraPlaceholder");
  const camStatusBadge = document.getElementById("camStatusBadge");
  const toggleCameraBtn = document.getElementById("toggleCameraBtn");
  const guideBox = document.getElementById("guideBox");
  const badgeFace = document.getElementById("badgeFace");
  const badgeLighting = document.getElementById("badgeLighting");
  const telemetryOverlay = document.getElementById("telemetryOverlay");

  // Context fields
  const ctxRole = document.getElementById("ctxRole");
  const ctxLevel = document.getElementById("ctxLevel");
  const ctxType = document.getElementById("ctxType");
  const ctxCount = document.getElementById("ctxCount");

  // State Variables
  let interview = null;
  let currentQuestion = null;
  let currentQIndex = 0;
  let answeredResponsesCount = 0;
  let isInterviewCompleted = false;
  let nextQuestionData = null;

  let isMuted = false;
  let isPausedSpeech = false;
  let currentUtterance = null;

  let mediaStream = null;
  let videoStream = null;
  let mediaRecorder = null;
  let audioChunks = [];
  let recognition = null;
  let isRecording = false;
  let isManualMode = false;
  let cameraActive = false;
  let isSubmitting = false;

  let answerStartTime = null;
  let answerTimerInterval = null;
  let sessionStartTime = Date.now();
  let sessionTimerInterval = null;

  // Format seconds to MM:SS
  function formatTime(seconds) {
    const m = Math.floor(seconds / 60).toString().padStart(2, "0");
    const s = Math.floor(seconds % 60).toString().padStart(2, "0");
    return `⏱ ${m}:${s}`;
  }

  function updateWordCount() {
    const text = editableTranscript.value.trim();
    const words = text ? text.split(/\s+/).filter(Boolean).length : 0;
    wordCountBadge.textContent = `${words} word${words === 1 ? "" : "s"}`;
    if (words > 0 && !isRecording && !isSubmitting) {
      submitBtn.style.display = "inline-flex";
    }
  }
  editableTranscript.addEventListener("input", updateWordCount);

  // State Machine helper
  function setState(state) {
    if (state === "AI_SPEAKING") {
      interviewerStateBadge.className = "state-badge state-speaking";
      interviewerStateBadge.innerHTML = "🔊 AI is speaking...";
      speakingWave.style.display = "flex";
      speakingHelp.textContent = "Listen carefully to the question";
      startBtn.disabled = true;
      recordingStatus.textContent = "AI interviewer is speaking the question aloud…";
    } else if (state === "READY_TO_ANSWER") {
      interviewerStateBadge.className = "state-badge state-ready";
      interviewerStateBadge.innerHTML = "🎤 Ready for response";
      speakingWave.style.display = "none";
      speakingHelp.textContent = "Click 'Start Voice Answer' or type below";
      startBtn.disabled = false;
      recordingStatus.textContent = "Question complete. Record your answer or type into the box below.";
    } else if (state === "RECORDING") {
      interviewerStateBadge.className = "state-badge state-recording";
      interviewerStateBadge.innerHTML = "🔴 Recording in progress...";
      speakingWave.style.display = "none";
      speakingHelp.textContent = "Speak clearly into your microphone";
      recordingStatus.textContent = "Recording your voice answer. Your words appear below and can be edited.";
    } else if (state === "ANALYZING") {
      interviewerStateBadge.className = "state-badge state-analyzing";
      interviewerStateBadge.innerHTML = "⚙️ Evaluating response...";
      speakingWave.style.display = "none";
      speakingHelp.textContent = "Analyzing content, domain depth, and communication delivery";
      recordingStatus.textContent = "Evaluating your response…";
    } else if (state === "FEEDBACK") {
      interviewerStateBadge.className = "state-badge state-ready";
      interviewerStateBadge.innerHTML = "✓ Feedback ready";
      speakingWave.style.display = "none";
      speakingHelp.textContent = "Review question analysis below";
      recordingStatus.textContent = "Review your evaluation before advancing to the next adaptive question.";
    }
  }

  // Real TTS speech
  function speakQuestion(text) {
    if (!("speechSynthesis" in window) || isMuted) {
      setState("READY_TO_ANSWER");
      return;
    }

    try {
      window.speechSynthesis.cancel();
      setState("AI_SPEAKING");

      currentUtterance = new SpeechSynthesisUtterance(text);
      currentUtterance.rate = 0.98;
      currentUtterance.pitch = 1.0;
      currentUtterance.lang = "en-US";

      // Select natural voice if available
      const voices = window.speechSynthesis.getVoices();
      const preferred = voices.find(v => v.lang.startsWith("en") && (v.name.includes("Natural") || v.name.includes("Google") || v.name.includes("Samantha")));
      if (preferred) currentUtterance.voice = preferred;

      currentUtterance.onstart = () => setState("AI_SPEAKING");
      currentUtterance.onend = () => setState("READY_TO_ANSWER");
      currentUtterance.onerror = (err) => {
        console.warn("SpeechSynthesis error:", err);
        setState("READY_TO_ANSWER");
      };

      window.speechSynthesis.speak(currentUtterance);
    } catch (e) {
      console.warn("TTS speak failure:", e);
      setState("READY_TO_ANSWER");
    }
  }

  // Audio Playback Controls
  replayQuestionBtn.addEventListener("click", () => {
    if (currentQuestion) {
      speakQuestion(currentQuestion.question_text || currentQuestion.text);
    }
  });

  pauseAudioBtn.addEventListener("click", () => {
    if (!("speechSynthesis" in window)) return;
    if (window.speechSynthesis.speaking) {
      if (isPausedSpeech) {
        window.speechSynthesis.resume();
        isPausedSpeech = false;
        pauseAudioBtn.textContent = "⏸ Pause";
        speakingWave.style.display = "flex";
      } else {
        window.speechSynthesis.pause();
        isPausedSpeech = true;
        pauseAudioBtn.textContent = "▶ Resume";
        speakingWave.style.display = "none";
      }
    }
  });

  muteAudioBtn.addEventListener("click", () => {
    isMuted = !isMuted;
    if (isMuted) {
      window.speechSynthesis.cancel();
      muteAudioBtn.textContent = "🔊 Unmute";
      muteAudioBtn.className = "btn btn-danger btn-sm";
      setState("READY_TO_ANSWER");
    } else {
      muteAudioBtn.textContent = "🔇 Mute";
      muteAudioBtn.className = "btn btn-outline btn-sm";
      if (currentQuestion) speakQuestion(currentQuestion.question_text || currentQuestion.text);
    }
  });

  // Presentation Assist Setup
  async function initWebcam(enableCamera) {
    PresentationAssist.init(cameraPreview);

    window.onPresentationTelemetry = function (telemetry) {
      if (!cameraActive) return;
      telemetryOverlay.style.display = "flex";

      if (telemetry.face_detected) {
        guideBox.className = telemetry.is_centered ? "camera-guide-box in-frame" : "camera-guide-box";
        badgeFace.textContent = `Face: ${telemetry.horizontal_offset}`;
        badgeFace.className = telemetry.is_centered ? "badge badge-success" : "badge badge-warning";
        document.getElementById("telemetryFraming").textContent = `Framing: ${telemetry.horizontal_offset}`;
      } else {
        guideBox.className = "camera-guide-box";
        badgeFace.textContent = "Face: Not detected";
        badgeFace.className = "badge badge-secondary";
        document.getElementById("telemetryFraming").textContent = "Face: Positioning…";
      }

      badgeLighting.textContent = `Lighting: ${telemetry.lighting}`;
      badgeLighting.className = telemetry.lighting === "Good" ? "badge badge-success" : "badge badge-warning";
      document.getElementById("telemetryLighting").textContent = `Lighting: ${telemetry.lighting}`;
    };

    if (enableCamera) {
      try {
        videoStream = await navigator.mediaDevices.getUserMedia({
          video: { width: 480, height: 360, facingMode: "user" }
        });
        cameraPreview.style.display = "block";
        cameraPlaceholder.style.display = "none";
        camStatusBadge.textContent = "Active";
        camStatusBadge.className = "badge badge-success";
        cameraActive = true;
        toggleCameraBtn.textContent = "Camera: On";
        PresentationAssist.start(videoStream);
      } catch (err) {
        console.warn("Camera access denied/unavailable:", err);
        cameraActive = false;
        cameraPreview.style.display = "none";
        cameraPlaceholder.style.display = "flex";
        camStatusBadge.textContent = "Off";
        camStatusBadge.className = "badge badge-secondary";
        toggleCameraBtn.textContent = "Camera: Off";
      }
    } else {
      cameraActive = false;
      cameraPreview.style.display = "none";
      cameraPlaceholder.style.display = "flex";
      camStatusBadge.textContent = "Off";
      camStatusBadge.className = "badge badge-secondary";
      toggleCameraBtn.textContent = "Camera: Off";
    }
  }

  toggleCameraBtn.addEventListener("click", async () => {
    if (cameraActive) {
      PresentationAssist.stop();
      if (videoStream) {
        videoStream.getTracks().forEach(t => t.stop());
        videoStream = null;
      }
      cameraActive = false;
      cameraPreview.style.display = "none";
      cameraPlaceholder.style.display = "flex";
      camStatusBadge.textContent = "Off";
      camStatusBadge.className = "badge badge-secondary";
      toggleCameraBtn.textContent = "Camera: Off";
      telemetryOverlay.style.display = "none";
    } else {
      await initWebcam(true);
    }
  });

  // Speech Recognition Setup
  function initSpeechRecognition() {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (SR) {
      recognition = new SR();
      recognition.continuous = true;
      recognition.interimResults = true;
      recognition.lang = "en-US";

      recognition.onresult = function (event) {
        let fullTranscript = "";
        for (let i = 0; i < event.results.length; ++i) {
          fullTranscript += event.results[i][0].transcript + " ";
        }
        // Stream text into editable textarea
        editableTranscript.value = fullTranscript.trim();
        updateWordCount();
      };

      recognition.onerror = function (e) {
        console.warn("Speech recognition warning:", e);
      };

      recognition.onend = function () {
        if (isRecording) {
          // Restart if still marked recording (handles browser timeout)
          try { recognition.start(); } catch (e) {}
        }
      };
    } else {
      recordingError.textContent = "Web Speech Recognition is not supported on this browser. You can type your answer directly.";
      recordingError.style.display = "block";
      enableManualMode();
    }
  }

  function enableManualMode() {
    isManualMode = true;
    toggleInputModeBtn.textContent = "🎤 Switch to Voice + Text";
    startBtn.style.display = "none";
    stopBtn.style.display = "none";
    retryBtn.style.display = "none";
    submitBtn.style.display = "inline-flex";
    submitBtn.disabled = false;
    submitBtn.textContent = "🚀 Submit Answer";
    recordingStatus.textContent = "Type your response in the box below and click Submit Answer.";
  }

  function enableVoiceMode() {
    isManualMode = false;
    toggleInputModeBtn.textContent = "⌨ Switch to Text Only";
    startBtn.style.display = "inline-flex";
    stopBtn.style.display = "none";
    retryBtn.style.display = "none";
    submitBtn.disabled = false;
    submitBtn.textContent = "🚀 Submit Answer";
    submitBtn.style.display = editableTranscript.value.trim().length > 0 ? "inline-flex" : "none";
    recordingStatus.textContent = "Click 'Start Voice Answer' to record or type in the box below.";
  }

  toggleInputModeBtn.addEventListener("click", () => {
    if (isManualMode) {
      enableVoiceMode();
    } else {
      if (isRecording) stopRecording();
      enableManualMode();
    }
  });

  // Start Answer Recording
  startBtn.addEventListener("click", async () => {
    window.speechSynthesis.cancel();
    audioChunks = [];
    recordingError.style.display = "none";
    answerStartTime = Date.now();

    answerTimerBadge.textContent = "⏱ 00:00";
    answerTimerBadge.style.display = "inline-block";
    recordingIndicator.style.display = "inline-block";

    setState("RECORDING");
    isRecording = true;

    answerTimerInterval = setInterval(() => {
      const elapsed = (Date.now() - answerStartTime) / 1000;
      answerTimerBadge.textContent = formatTime(elapsed);
    }, 500);

    // Audio stream capture
    try {
      if (!mediaStream) {
        mediaStream = await navigator.mediaDevices.getUserMedia({ audio: true });
      }
      mediaRecorder = new MediaRecorder(mediaStream);
      mediaRecorder.ondataavailable = (e) => {
        if (e.data && e.data.size > 0) audioChunks.push(e.data);
      };
      mediaRecorder.start(250);
    } catch (err) {
      console.warn("Microphone capture warning:", err);
    }

    // Start recognition
    if (recognition) {
      try {
        recognition.start();
      } catch (e) {}
    }

    startBtn.style.display = "none";
    stopBtn.style.display = "inline-flex";
    retryBtn.style.display = "none";
    submitBtn.style.display = "none";
  });

  function stopRecording() {
    isRecording = false;
    clearInterval(answerTimerInterval);
    recordingIndicator.style.display = "none";

    if (recognition) {
      try { recognition.stop(); } catch (e) {}
    }

    if (mediaRecorder && mediaRecorder.state !== "inactive") {
      try { mediaRecorder.stop(); } catch (e) {}
    }

    stopBtn.style.display = "none";
    retryBtn.style.display = "inline-flex";
    submitBtn.style.display = "inline-flex";
    submitBtn.disabled = false;
    submitBtn.textContent = "🚀 Submit Answer";
    recordingStatus.textContent = "Answer recorded. You may edit your transcript below before submitting.";
  }

  stopBtn.addEventListener("click", stopRecording);

  retryBtn.addEventListener("click", () => {
    clearInterval(answerTimerInterval);
    audioChunks = [];
    editableTranscript.value = "";
    updateWordCount();
    answerTimerBadge.style.display = "none";
    recordingIndicator.style.display = "none";

    startBtn.style.display = "inline-flex";
    stopBtn.style.display = "none";
    retryBtn.style.display = "none";
    submitBtn.style.display = "none";
    submitBtn.disabled = false;
    submitBtn.textContent = "🚀 Submit Answer";
    isSubmitting = false;
    setState("READY_TO_ANSWER");
  });

  // Submit Answer
  submitBtn.addEventListener("click", async () => {
    if (isSubmitting) return;

    const textAnswer = editableTranscript.value.trim();

    if (!textAnswer && audioChunks.length === 0) {
      recordingError.textContent = "Please speak or type your answer before submitting.";
      recordingError.style.display = "block";
      return;
    }

    isSubmitting = true;
    setState("ANALYZING");
    submitBtn.disabled = true;
    submitBtn.textContent = "Evaluating response…";
    recordingError.style.display = "none";

    const durationSec = answerStartTime ? Math.max(1.0, (Date.now() - answerStartTime) / 1000) : 10.0;

    const formData = new FormData();
    formData.append("question_id", currentQuestion.id);
    formData.append("response_duration", durationSec);
    formData.append("transcript", textAnswer);

    // Audio file if recorded
    if (audioChunks.length > 0) {
      const blob = new Blob(audioChunks, { type: "audio/webm" });
      formData.append("audio_file", blob, "answer.webm");
    }

    // Presentation telemetry from local assist
    const telemetry = PresentationAssist.getTelemetry();
    formData.append("framing_telemetry", JSON.stringify(telemetry));

    try {
      const res = await Api.submitResponse(interviewId, formData);
      isSubmitting = false;
      displayFeedback(res);
    } catch (err) {
      console.error("Submission error:", err);
      recordingError.textContent = err.message || "Failed to submit answer. Please retry.";
      recordingError.style.display = "block";
      isSubmitting = false;
      submitBtn.disabled = false;
      submitBtn.textContent = "🚀 Submit Answer";
      setState("READY_TO_ANSWER");
    }
  });

  function displayFeedback(data) {
    setState("FEEDBACK");
    submitBtn.style.display = "none";
    retryBtn.style.display = "none";

    answeredResponsesCount = data.answered_count || (answeredResponsesCount + 1);
    const analysis = data.analysis;
    const feedback = data.feedback;
    isInterviewCompleted = data.interview_completed;
    nextQuestionData = data.next_question;

    scoreContent.textContent = analysis.content_score ?? "-";
    scoreTech.textContent = analysis.technical_score ?? "-";
    scoreCommunication.textContent = analysis.communication_score ?? "-";
    scoreOverall.textContent = analysis.overall_score ?? "-";

    // Strengths
    strengthsList.innerHTML = (feedback.strengths || ["Provided solid technical input."])
      .map(s => `<div class="strength-item"><span>✓</span><span>${s}</span></div>`)
      .join("");

    // Improvements
    improvementsList.innerHTML = (feedback.improvements || ["Continue elaborating with concrete architecture examples."])
      .map(imp => `<div class="improve-item"><span>→</span><span>${imp}</span></div>`)
      .join("");

    speechObsText.textContent = feedback.speech_feedback || "Clear speaking delivery.";
    visualObsText.textContent = feedback.visual_feedback || "Camera analysis disabled.";

    if (isInterviewCompleted) {
      nextQuestionBtn.textContent = "View Final Interview Report →";
      nextQuestionBtn.className = "btn btn-success btn-block";
    } else {
      nextQuestionBtn.textContent = "Next Adaptive Question (AI adapts to your answer) →";
      nextQuestionBtn.className = "btn btn-primary btn-block";
    }

    resultPanel.style.display = "block";
    resultPanel.scrollIntoView({ behavior: "smooth" });
  }

  // Next Question or Report
  nextQuestionBtn.addEventListener("click", async () => {
    if (isInterviewCompleted) {
      window.location.href = "report.html?id=" + interviewId;
      return;
    }

    if (nextQuestionData) {
      renderQuestion(nextQuestionData, currentQIndex + 1, interview.total_questions);
      window.scrollTo({ top: 0, behavior: "smooth" });
    } else {
      window.location.href = "report.html?id=" + interviewId;
    }
  });

  // End Interview Early
  endInterviewEarlyBtn.addEventListener("click", async () => {
    if (answeredResponsesCount === 0) {
      const exitConf = confirm("No answers have been recorded yet. Do you want to exit the interview room and return to your dashboard? (No report will be generated)");
      if (exitConf) {
        window.location.href = "candidate-dashboard.html";
      }
      return;
    }

    const conf = confirm("Are you sure you want to conclude this interview session now? Your recorded answers will be evaluated to generate your final feedback report.");
    if (conf) {
      try {
        await Api.finishInterview(interviewId);
      } catch (e) {
        console.warn("Finish interview warning:", e);
      }
      window.location.href = "report.html?id=" + interviewId;
    }
  });

  // Render Question
  function renderQuestion(qData, index, total) {
    currentQuestion = qData;
    currentQIndex = index;

    qCounter.textContent = `Question ${index + 1} / ${total}`;
    qType.textContent = qData.question_type || "Technical";
    qTopic.textContent = qData.topic || "Core Concept";
    qText.textContent = qData.question_text || qData.text;

    const diff = qData.difficulty || "Medium";
    diffBadge.textContent = diff;
    diffBadge.className = `badge badge-${diff.toLowerCase()}`;

    // Update Progress Dots
    progressDots.innerHTML = Array.from({ length: total })
      .map((_, i) => `<span class="progress-dot ${i < index ? "done" : (i === index ? "active" : "")}"></span>`)
      .join("");

    // Reset controls
    resultPanel.style.display = "none";
    recordingError.style.display = "none";
    editableTranscript.value = "";
    audioChunks = [];
    isSubmitting = false;
    submitBtn.disabled = false;
    submitBtn.textContent = "🚀 Submit Answer";
    updateWordCount();
    answerTimerBadge.style.display = "none";
    recordingIndicator.style.display = "none";

    if (isManualMode) {
      enableManualMode();
    } else {
      enableVoiceMode();
    }

    // Speak aloud via TTS
    speakQuestion(qData.question_text || qData.text);
  }

  // Initialize
  async function init() {
    const user = await Api.requireAuth("job_seeker");
    if (!user) return;

    // Load AI Health & Provider status
    try {
      const health = await Api.getHealth();
      aiEngineText.textContent = `⚡ Active Engine: ${health.provider} (${health.model})`;
    } catch (e) {
      aiEngineText.textContent = "⚡ Active Engine: Local Adaptive Heuristic";
    }

    let data;
    try {
      data = await Api.getInterview(interviewId);
    } catch (err) {
      alert("Could not load interview: " + err.message);
      window.location.href = "candidate-dashboard.html";
      return;
    }

    interview = data.interview;
    answeredResponsesCount = (data.responses || []).length;

    // Display context
    ctxRole.textContent = interview.job_role || "Software Developer";
    ctxLevel.textContent = interview.experience_level || "Mid-Level";
    ctxType.textContent = interview.interview_type || "Technical";
    ctxCount.textContent = `${interview.total_questions} Questions`;

    // Session timer
    sessionTimerInterval = setInterval(() => {
      const elapsedSec = (Date.now() - sessionStartTime) / 1000;
      timerBadge.textContent = formatTime(elapsedSec);
    }, 1000);

    if (interview.status === "cancelled") {
      alert("This interview has been cancelled by an administrator.");
      window.location.href = "candidate-dashboard.html";
      return;
    }

    if (interview.status === "missed") {
      alert("This scheduled interview was marked as missed.");
      window.location.href = "candidate-dashboard.html";
      return;
    }

    if (interview.status === "completed") {
      window.location.href = "report.html?id=" + interviewId;
      return;
    }

    // If candidate has completed all required questions, finalize and show report
    if (data.responses && data.responses.length >= interview.total_questions && data.responses.length > 0) {
      try {
        await Api.finishInterview(interviewId);
      } catch (e) {}
      window.location.href = "report.html?id=" + interviewId;
      return;
    }

    // If for any reason current_question is not loaded yet (e.g. freshly started scheduled interview):
    if (!data.current_question) {
      try {
        data = await Api.startInterview(interviewId);
        interview = data.interview;
        answeredResponsesCount = (data.responses || []).length;
      } catch (err) {
        console.warn("Could not start interview:", err);
      }
    }

    if (!data.current_question) {
      alert("Could not load the interview question. Returning to candidate dashboard.");
      window.location.href = "candidate-dashboard.html";
      return;
    }

    initSpeechRecognition();
    await initWebcam(interview.camera_enabled);

    renderQuestion(data.current_question, data.question_index, interview.total_questions);
  }

  init();
})();
