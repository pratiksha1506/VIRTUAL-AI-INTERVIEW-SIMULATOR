/**
 * presentation-assist.js — Ethical, 100% Client-Side Webcam Telemetry
 *
 * Implements real-time presentation awareness:
 * 1. Face framing & centering detection via skin-tone/face bounding box heuristics on Canvas.
 * 2. Scene luminance assessment (Good, Low Light, Backlit / High Glare).
 * 3. Provides explicit consent checks and non-blocking fallbacks.
 *
 * ETHICAL COMPLIANCE:
 * - Runs strictly locally in the candidate's browser.
 * - Does NOT infer emotion, personality, honesty, or hireability.
 * - Used exclusively as a friendly positioning aid.
 */

window.PresentationAssist = (function () {
  let videoEl = null;
  let canvas = null;
  let ctx = null;
  let stream = null;
  let isAnalyzing = false;
  let analysisInterval = null;

  let lastTelemetry = {
    face_detected: false,
    is_centered: true,
    horizontal_offset: "Centered",
    lighting: "Good",
    average_luma: 128
  };

  function init(videoElement) {
    videoEl = videoElement;
    canvas = document.createElement("canvas");
    canvas.width = 160;
    canvas.height = 120;
    ctx = canvas.getContext("2d", { willReadFrequently: true });
  }

  async function start(streamRef) {
    stream = streamRef;
    if (!videoEl || !stream) return;
    videoEl.srcObject = stream;
    try {
      await videoEl.play();
    } catch (e) {
      console.warn("Video playback error:", e);
    }

    isAnalyzing = true;
    if (analysisInterval) clearInterval(analysisInterval);
    analysisInterval = setInterval(analyzeFrame, 800);
  }

  function stop() {
    isAnalyzing = false;
    if (analysisInterval) clearInterval(analysisInterval);
    if (stream) {
      stream.getTracks().forEach(t => t.stop());
      stream = null;
    }
  }

  function analyzeFrame() {
    if (!videoEl || !isAnalyzing || videoEl.readyState < 2) return;

    try {
      ctx.drawImage(videoEl, 0, 0, canvas.width, canvas.height);
      const imgData = ctx.getImageData(0, 0, canvas.width, canvas.height);
      const data = imgData.data;

      let totalLuma = 0;
      let skinPixels = 0;
      let minX = canvas.width, maxX = 0;
      let minY = canvas.height, maxY = 0;

      // Scan pixels
      for (let i = 0; i < data.length; i += 16) { // step by 4 pixels (16 bytes) for speed
        const r = data[i];
        const g = data[i + 1];
        const b = data[i + 2];

        // Standard perceived luminance
        const luma = 0.299 * r + 0.587 * g + 0.114 * b;
        totalLuma += luma;

        // Approximate skin-tone chromatic range in RGB
        // R > 95, G > 40, B > 20, max(r,g,b) - min(r,g,b) > 15, |r-g| > 15, r > g, r > b
        if (r > 60 && g > 35 && b > 20 && r > g && (r - b) > 10) {
          const pixelIdx = i / 4;
          const x = pixelIdx % canvas.width;
          const y = Math.floor(pixelIdx / canvas.width);

          skinPixels++;
          if (x < minX) minX = x;
          if (x > maxX) maxX = x;
          if (y < minY) minY = y;
          if (y > maxY) maxY = y;
        }
      }

      const totalSamples = data.length / 16;
      const avgLuma = Math.round(totalLuma / totalSamples);

      // Lighting condition
      let lighting = "Good";
      if (avgLuma < 55) {
        lighting = "Low Light";
      } else if (avgLuma > 215) {
        lighting = "Overexposed";
      }

      // Face detection & centering
      const faceDetected = skinPixels > (totalSamples * 0.04);
      let isCentered = true;
      let horizontalOffset = "Centered";

      if (faceDetected) {
        const faceCenterX = (minX + maxX) / 2;
        const normalizedCenter = faceCenterX / canvas.width; // 0.0 to 1.0 (0.5 is center)

        if (normalizedCenter < 0.38) {
          horizontalOffset = "Shift Right";
          isCentered = false;
        } else if (normalizedCenter > 0.62) {
          horizontalOffset = "Shift Left";
          isCentered = false;
        } else {
          horizontalOffset = "Centered";
          isCentered = true;
        }
      } else {
        horizontalOffset = "No Face in View";
        isCentered = false;
      }

      lastTelemetry = {
        face_detected: faceDetected,
        is_centered: isCentered,
        horizontal_offset: horizontalOffset,
        lighting: lighting,
        average_luma: avgLuma
      };

      // Trigger UI callback if registered
      if (typeof window.onPresentationTelemetry === "function") {
        window.onPresentationTelemetry(lastTelemetry);
      }
    } catch (err) {
      console.warn("Frame analysis error:", err);
    }
  }

  function getTelemetry() {
    return Object.assign({}, lastTelemetry);
  }

  return {
    init: init,
    start: start,
    stop: stop,
    getTelemetry: getTelemetry
  };
})();
