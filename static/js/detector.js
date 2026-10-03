/**
 * detector.js - MediaPipe Pose & FaceMesh Client-Side Ergonomic Detection Engine
 * Digital Wellness Monitor Major Project
 */

// FaceMesh Landmark Indices for Eye Aspect Ratio (EAR)
const LEFT_EYE_INDICES = [33, 160, 158, 133, 153, 144];
const RIGHT_EYE_INDICES = [362, 385, 387, 263, 373, 380];

class ErgonomicDetector {
  constructor(videoElement, canvasElement, alertManager) {
    this.video = videoElement;
    this.canvas = canvasElement;
    this.ctx = canvasElement.getContext('2d');
    this.alerts = alertManager;

    // Detection settings & thresholds (loadable from localStorage)
    this.shoulderTiltThreshold = 4.5; // degrees
    this.headTiltThreshold = 6.0;     // degrees
    this.slouchTolerance = 0.15;      // 15% drop from baseline
    this.earThreshold = 0.21;         // below this is a blink

    // Calibration
    this.baselineSlouchRatio = parseFloat(localStorage.getItem('baselineSlouchRatio')) || 0.50;
    this.isCalibrated = localStorage.getItem('baselineSlouchRatio') !== null;
    this.isCalibrating = false;
    this.calibrationSamples = [];

    // Tracking state
    this.isTracking = false;
    this.isMirrored = true;
    this.showOverlay = true;

    // Current metrics
    this.currentShoulderTilt = 0;
    this.currentHeadTilt = 0;
    this.currentSlouchRatio = 0.50;
    this.currentEar = 0.28;
    this.postureScore = 100;
    this.postureStatus = "GOOD"; // "GOOD", "SLOUCH", "TILT"

    // Blink counter & rolling BPM
    this.blinkCount = 0;
    this.eyeClosed = false;
    this.eyeClosedStartTime = null;
    this.blinkTimestamps = [];
    this.bpm = 16;

    // FPS calculation
    this.frameCount = 0;
    this.lastFpsUpdate = performance.now();
    this.fps = 30;

    // MediaPipe instances
    this.pose = null;
    this.faceMesh = null;
    this.camera = null;

    // Cached landmarks from latest frames
    this.latestPoseLandmarks = null;
    this.latestFaceLandmarks = null;

    this.initMediaPipe();
  }

  initMediaPipe() {
    // 1. Initialize Pose
    this.pose = new Pose({
      locateFile: (file) => `https://cdn.jsdelivr.net/npm/@mediapipe/pose/${file}`
    });
    this.pose.setOptions({
      modelComplexity: 1,
      smoothLandmarks: true,
      enableSegmentation: false,
      minDetectionConfidence: 0.5,
      minTrackingConfidence: 0.5
    });
    this.pose.onResults((results) => {
      this.latestPoseLandmarks = results.poseLandmarks;
    });

    // 2. Initialize FaceMesh
    this.faceMesh = new FaceMesh({
      locateFile: (file) => `https://cdn.jsdelivr.net/npm/@mediapipe/face_mesh/${file}`
    });
    this.faceMesh.setOptions({
      maxNumFaces: 1,
      refineLandmarks: true,
      minDetectionConfidence: 0.5,
      minTrackingConfidence: 0.5
    });
    this.faceMesh.onResults((results) => {
      if (results.multiFaceLandmarks && results.multiFaceLandmarks.length > 0) {
        this.latestFaceLandmarks = results.multiFaceLandmarks[0];
      } else {
        this.latestFaceLandmarks = null;
      }
    });
  }

  async startCamera() {
    if (this.camera) {
      await this.camera.start();
      this.isTracking = true;
      return;
    }

    this.camera = new Camera(this.video, {
      onFrame: async () => {
        if (!this.isTracking) return;
        
        // Feed frame to detectors
        await this.pose.send({ image: this.video });
        await this.faceMesh.send({ image: this.video });

        // Process combined analytics and draw overlay
        this.processFrame();
      },
      width: 1280,
      height: 720
    });

    await this.camera.start();
    this.isTracking = true;
  }

  stopCamera() {
    if (this.camera) {
      this.camera.stop();
      this.isTracking = false;
    }
  }

  // Calculate Euclidean distance between two 2D points
  dist(p1, p2) {
    return Math.hypot(p2.x - p1.x, p2.y - p1.y);
  }

  // Calculate angle of line relative to horizontal in degrees
  calculateAngle(p1, p2) {
    const dx = p2.x - p1.x;
    const dy = p2.y - p1.y;
    let angle = Math.abs(Math.atan2(dy, dx) * (180 / Math.PI));
    if (angle > 90) angle = 180 - angle;
    return angle;
  }

  // Calculate Eye Aspect Ratio (EAR) for blinking
  calculateEAR(landmarks, indices, width, height) {
    const pts = indices.map(idx => ({
      x: landmarks[idx].x * width,
      y: landmarks[idx].y * height
    }));
    const v1 = this.dist(pts[1], pts[5]);
    const v2 = this.dist(pts[2], pts[4]);
    const h = this.dist(pts[0], pts[3]);
    if (h === 0) return 0.25;
    return (v1 + v2) / (2.0 * h);
  }

  // Calibrate user's upright posture baseline
  startCalibration(onProgress, onDone) {
    this.isCalibrating = true;
    this.calibrationSamples = [];
    const overlay = document.getElementById('calibration-overlay');
    const countdownEl = document.getElementById('calib-countdown');
    if (overlay) overlay.classList.add('active');

    let secondsLeft = 3;
    if (countdownEl) countdownEl.textContent = secondsLeft;

    const timer = setInterval(() => {
      secondsLeft -= 1;
      if (countdownEl) countdownEl.textContent = secondsLeft;
      if (onProgress) onProgress(secondsLeft);

      if (secondsLeft <= 0) {
        clearInterval(timer);
        this.finalizeCalibration();
        if (overlay) overlay.classList.remove('active');
        if (onDone) onDone(this.baselineSlouchRatio);
      }
    }, 1000);
  }

  finalizeCalibration() {
    this.isCalibrating = false;
    if (this.calibrationSamples.length > 5) {
      const sum = this.calibrationSamples.reduce((a, b) => a + b, 0);
      this.baselineSlouchRatio = parseFloat((sum / this.calibrationSamples.length).toFixed(2));
    } else {
      this.baselineSlouchRatio = parseFloat(this.currentSlouchRatio.toFixed(2));
    }
    this.isCalibrated = true;
    localStorage.setItem('baselineSlouchRatio', this.baselineSlouchRatio);

    // Update UI badge
    const badge = document.getElementById('calib-status-badge');
    if (badge) {
      badge.innerHTML = `<i class="fa-solid fa-circle-check"></i> Calibrated (Base: ${this.baselineSlouchRatio.toFixed(2)})`;
    }

    this.alerts.playSuccessChime();
    this.alerts.speak("Baseline calibrated successfully.");
  }

  // Main frame processing and drawing loop
  processFrame() {
    const w = this.canvas.width = this.video.videoWidth || 1280;
    const h = this.canvas.height = this.video.videoHeight || 720;
    const ctx = this.ctx;

    // Calculate FPS
    this.frameCount++;
    const now = performance.now();
    if (now - this.lastFpsUpdate >= 1000) {
      this.fps = Math.round((this.frameCount * 1000) / (now - this.lastFpsUpdate));
      this.frameCount = 0;
      this.lastFpsUpdate = now;
      const fpsBadge = document.getElementById('hud-fps');
      if (fpsBadge) fpsBadge.textContent = `${this.fps} FPS`;
    }

    // Clear canvas
    ctx.clearRect(0, 0, w, h);
    ctx.save();

    // Mirror video feed if enabled
    if (this.isMirrored) {
      ctx.translate(w, 0);
      ctx.scale(-1, 1);
    }

    // Draw live webcam frame onto canvas
    ctx.drawImage(this.video, 0, 0, w, h);

    // ==========================================
    // 1. Process Face & Eye Blinking
    // ==========================================
    if (this.latestFaceLandmarks) {
      const leftEar = this.calculateEAR(this.latestFaceLandmarks, LEFT_EYE_INDICES, w, h);
      const rightEar = this.calculateEAR(this.latestFaceLandmarks, RIGHT_EYE_INDICES, w, h);
      this.currentEar = parseFloat(((leftEar + rightEar) / 2.0).toFixed(3));

      const currentTimeSec = performance.now() / 1000;

      // Blink detection state machine
      if (this.currentEar < this.earThreshold) {
        if (!this.eyeClosed) {
          this.eyeClosed = true;
          this.eyeClosedStartTime = currentTimeSec;
        } else if (currentTimeSec - this.eyeClosedStartTime > 2.5) {
          // Eyes closed for > 2.5 seconds indicates microsleep or drowsiness
          this.alerts.speak("Drowsiness alert: eyes closed for extended period.");
        }
      } else {
        if (this.eyeClosed) {
          this.blinkCount++;
          this.blinkTimestamps.push(currentTimeSec);
          this.eyeClosed = false;
        }
      }

      // Update rolling 60-second Blink Rate (BPM)
      this.blinkTimestamps = this.blinkTimestamps.filter(t => currentTimeSec - t <= 60);
      this.bpm = this.blinkTimestamps.length;

      // Draw Eye Contours if HUD overlay is enabled
      if (this.showOverlay) {
        this.drawEyeContour(ctx, this.latestFaceLandmarks, LEFT_EYE_INDICES, w, h);
        this.drawEyeContour(ctx, this.latestFaceLandmarks, RIGHT_EYE_INDICES, w, h);
      }
    }

    // ==========================================
    // 2. Process Posture (Pose Landmarks)
    // ==========================================
    let isGoodPosture = true;
    let postureReasons = [];

    if (this.latestPoseLandmarks) {
      const lm = this.latestPoseLandmarks;

      // Points: 2: left_eye, 5: right_eye, 11: left_shoulder, 12: right_shoulder
      const leftEye = { x: lm[2].x * w, y: lm[2].y * h };
      const rightEye = { x: lm[5].x * w, y: lm[5].y * h };
      const leftShoulder = { x: lm[11].x * w, y: lm[11].y * h };
      const rightShoulder = { x: lm[12].x * w, y: lm[12].y * h };

      // Calculate angles
      this.currentShoulderTilt = parseFloat(this.calculateAngle(leftShoulder, rightShoulder).toFixed(1));
      this.currentHeadTilt = parseFloat(this.calculateAngle(leftEye, rightEye).toFixed(1));

      // Calculate Slouch Ratio (normalized vertical head-to-shoulder distance over shoulder width)
      const headMid = { x: (leftEye.x + rightEye.x) / 2, y: (leftEye.y + rightEye.y) / 2 };
      const shoulderMid = { x: (leftShoulder.x + rightShoulder.x) / 2, y: (leftShoulder.y + rightShoulder.y) / 2 };
      const shoulderWidth = this.dist(leftShoulder, rightShoulder);

      if (shoulderWidth > 30) {
        const verticalDist = shoulderMid.y - headMid.y;
        this.currentSlouchRatio = parseFloat((verticalDist / shoulderWidth).toFixed(2));
      }

      // Auto collect sample if calibrating
      if (this.isCalibrating && this.currentSlouchRatio > 0.15) {
        this.calibrationSamples.push(this.currentSlouchRatio);
      }

      // Posture Evaluation logic
      if (this.currentShoulderTilt > this.shoulderTiltThreshold) {
        isGoodPosture = false;
        postureReasons.push("Shoulder Tilt");
      }

      if (this.currentHeadTilt > this.headTiltThreshold) {
        isGoodPosture = false;
        postureReasons.push("Head Tilt");
      }

      const slouchLimit = this.baselineSlouchRatio * (1.0 - this.slouchTolerance);
      if (this.currentSlouchRatio < slouchLimit) {
        isGoodPosture = false;
        postureReasons.push("Slouching / Forward Head");
      }

      // Posture Health Score calculation (0 - 100)
      let scoreDeductions = 0;
      if (this.currentShoulderTilt > this.shoulderTiltThreshold) {
        scoreDeductions += Math.min(25, (this.currentShoulderTilt - this.shoulderTiltThreshold) * 4);
      }
      if (this.currentHeadTilt > this.headTiltThreshold) {
        scoreDeductions += Math.min(25, (this.currentHeadTilt - this.headTiltThreshold) * 3);
      }
      if (this.currentSlouchRatio < slouchLimit) {
        const dropPct = (this.baselineSlouchRatio - this.currentSlouchRatio) / this.baselineSlouchRatio;
        scoreDeductions += Math.min(35, dropPct * 80);
      }
      if (this.bpm < 8 && this.frameCount % 90 === 0) {
        scoreDeductions += 10; // dry eye risk deduction
      }

      const targetScore = Math.max(20, Math.round(100 - scoreDeductions));
      this.postureScore = Math.round(this.postureScore * 0.9 + targetScore * 0.1); // smooth EMA

      // Update Posture Status
      if (isGoodPosture) {
        this.postureStatus = "GOOD (Upright & Aligned)";
      } else {
        this.postureStatus = "POOR (" + postureReasons.join(" & ") + ")";
      }

      // Trigger audio & visual alerts via AlertManager
      this.alerts.handlePostureState(isGoodPosture, postureReasons.join(", "));

      // Draw skeleton overlays on canvas matching reference image
      if (this.showOverlay) {
        this.drawPostureHUD(ctx, leftShoulder, rightShoulder, leftEye, rightEye, headMid, shoulderMid, isGoodPosture);
      }
    }

    ctx.restore();

    // Update HTML HUD and Telemetry cards
    this.updateUI(isGoodPosture);
  }

  // Draw eye landmarks
  drawEyeContour(ctx, landmarks, indices, w, h) {
    ctx.beginPath();
    ctx.strokeStyle = '#00d2ff';
    ctx.lineWidth = 1.5;
    for (let i = 0; i < indices.length; i++) {
      const pt = landmarks[indices[i]];
      const x = pt.x * w;
      const y = pt.y * h;
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    }
    ctx.closePath();
    ctx.stroke();
  }

  // Draw overlay lines matching user reference photo exactly
  drawPostureHUD(ctx, leftShoulder, rightShoulder, leftEye, rightEye, headMid, shoulderMid, isGood) {
    const lineColor = isGood ? '#00ff88' : '#ff3860';
    const pinColor = '#ffd000';

    // 1. Shoulder Alignment Line
    ctx.beginPath();
    ctx.moveTo(leftShoulder.x, leftShoulder.y);
    ctx.lineTo(rightShoulder.x, rightShoulder.y);
    ctx.strokeStyle = lineColor;
    ctx.lineWidth = 4;
    ctx.stroke();

    // Shoulder endpoints (circle pins)
    this.drawPin(ctx, leftShoulder.x, leftShoulder.y, pinColor);
    this.drawPin(ctx, rightShoulder.x, rightShoulder.y, pinColor);

    // Shoulder Angle Text
    ctx.fillStyle = '#00ffff';
    ctx.font = 'bold 15px JetBrains Mono, monospace';
    ctx.fillText(`${this.currentShoulderTilt}°`, (leftShoulder.x + rightShoulder.x) / 2 - 20, leftShoulder.y - 12);

    // 2. Head / Eye Alignment Line
    ctx.beginPath();
    ctx.moveTo(leftEye.x, leftEye.y);
    ctx.lineTo(rightEye.x, rightEye.y);
    ctx.strokeStyle = lineColor;
    ctx.lineWidth = 4;
    ctx.stroke();

    // Eye endpoints
    this.drawPin(ctx, leftEye.x, leftEye.y, pinColor);
    this.drawPin(ctx, rightEye.x, rightEye.y, pinColor);

    // Head Angle Text
    ctx.fillText(`${this.currentHeadTilt}°`, (leftEye.x + rightEye.x) / 2 - 20, leftEye.y - 12);

    // 3. Spinal Vertical Alignment Line (Head midpoint down to shoulder midpoint)
    ctx.beginPath();
    ctx.moveTo(headMid.x, headMid.y);
    ctx.lineTo(shoulderMid.x, shoulderMid.y);
    ctx.strokeStyle = '#00d2ff';
    ctx.lineWidth = 3;
    ctx.setLineDash([4, 4]); // dashed spine line
    ctx.stroke();
    ctx.setLineDash([]); // reset line dash

    this.drawPin(ctx, headMid.x, headMid.y, '#00ff88', 4);
    this.drawPin(ctx, shoulderMid.x, shoulderMid.y, '#00ff88', 4);
  }

  drawPin(ctx, x, y, color, radius = 7) {
    ctx.beginPath();
    ctx.arc(x, y, radius, 0, 2 * Math.PI);
    ctx.fillStyle = color;
    ctx.fill();
    ctx.strokeStyle = '#ffffff';
    ctx.lineWidth = 2;
    ctx.stroke();
  }

  // Synchronize detected metrics with UI components
  updateUI(isGood) {
    // Top HUD matching reference image
    const hudStatus = document.getElementById('hud-posture-text');
    if (hudStatus) {
      hudStatus.textContent = `POSTURE: ${this.postureStatus}`;
      hudStatus.className = `hud-posture-badge ${isGood ? 'good' : 'bad'}`;
    }

    const hudShoulder = document.getElementById('hud-shoulder');
    if (hudShoulder) hudShoulder.textContent = `${this.currentShoulderTilt} deg`;

    const hudHead = document.getElementById('hud-head');
    if (hudHead) hudHead.textContent = `${this.currentHeadTilt} deg`;

    const hudSlouch = document.getElementById('hud-slouch');
    if (hudSlouch) {
      hudSlouch.textContent = `${this.currentSlouchRatio.toFixed(2)} (Base: ${this.baselineSlouchRatio.toFixed(2)})`;
    }

    // Top Header Pill
    const headerPill = document.getElementById('header-posture-pill');
    const headerText = document.getElementById('header-status-text');
    if (headerPill && headerText) {
      headerText.textContent = isGood ? 'POSTURE: OPTIMAL' : 'POSTURE: POOR';
      headerPill.className = `posture-status-pill ${isGood ? 'good' : 'bad'}`;
    }

    // Health Score Circle
    const scoreNum = document.getElementById('score-number');
    const scoreCircle = document.getElementById('score-circle-bar');
    const ratingBadge = document.getElementById('rating-badge');
    if (scoreNum && scoreCircle) {
      scoreNum.textContent = this.postureScore;
      // Circumference = 2 * PI * 50 = 314
      const offset = 314 - (314 * (this.postureScore / 100));
      scoreCircle.style.strokeDashoffset = offset;
      
      if (this.postureScore >= 85) {
        scoreCircle.style.stroke = 'var(--color-good)';
        if (ratingBadge) {
          ratingBadge.textContent = 'Optimal Alignment';
          ratingBadge.className = 'rating-badge optimal';
        }
      } else if (this.postureScore >= 70) {
        scoreCircle.style.stroke = 'var(--color-warning)';
        if (ratingBadge) {
          ratingBadge.textContent = 'Moderate Strain';
          ratingBadge.className = 'rating-badge warning';
        }
      } else {
        scoreCircle.style.stroke = 'var(--color-danger)';
        if (ratingBadge) {
          ratingBadge.textContent = 'Ergonomic Risk';
          ratingBadge.className = 'rating-badge poor';
        }
      }
    }

    // Telemetry Cards
    const valShoulder = document.getElementById('metric-shoulder-val');
    if (valShoulder) valShoulder.textContent = `${this.currentShoulderTilt}°`;
    const barShoulder = document.getElementById('bar-shoulder');
    if (barShoulder) {
      barShoulder.style.width = `${Math.min(100, (this.currentShoulderTilt / 10) * 100)}%`;
      barShoulder.style.backgroundColor = this.currentShoulderTilt > this.shoulderTiltThreshold ? 'var(--color-danger)' : 'var(--color-cyan)';
    }

    const valHead = document.getElementById('metric-head-val');
    if (valHead) valHead.textContent = `${this.currentHeadTilt}°`;
    const barHead = document.getElementById('bar-head');
    if (barHead) {
      barHead.style.width = `${Math.min(100, (this.currentHeadTilt / 12) * 100)}%`;
      barHead.style.backgroundColor = this.currentHeadTilt > this.headTiltThreshold ? 'var(--color-danger)' : 'var(--color-cyan)';
    }

    const valSlouch = document.getElementById('metric-slouch-val');
    if (valSlouch) valSlouch.textContent = `${this.currentSlouchRatio.toFixed(2)}`;
    const baseSlouch = document.getElementById('metric-slouch-base');
    if (baseSlouch) {
      const diffPct = Math.round(((this.currentSlouchRatio - this.baselineSlouchRatio) / this.baselineSlouchRatio) * 100);
      baseSlouch.textContent = `Base: ${this.baselineSlouchRatio.toFixed(2)} (${diffPct >= 0 ? '+' : ''}${diffPct}%)`;
    }

    const valBpm = document.getElementById('metric-bpm-val');
    if (valBpm) valBpm.innerHTML = `${this.bpm} <small>BPM</small>`;
    const totalBlinks = document.getElementById('metric-total-blinks');
    if (totalBlinks) totalBlinks.textContent = `Total: ${this.blinkCount} blinks`;

    const valEar = document.getElementById('metric-ear-val');
    if (valEar) valEar.textContent = `${this.currentEar.toFixed(2)}`;
    const badgeEar = document.getElementById('badge-ear');
    if (badgeEar) {
      if (this.currentEar < this.earThreshold) {
        badgeEar.textContent = 'Blinking';
        badgeEar.className = 'metric-badge warning';
      } else {
        badgeEar.textContent = 'Eyes Open';
        badgeEar.className = 'metric-badge good';
      }
    }

    const badgeFatigue = document.getElementById('badge-fatigue');
    const valFatigue = document.getElementById('metric-fatigue-val');
    if (badgeFatigue && valFatigue) {
      if (this.bpm < 10) {
        badgeFatigue.textContent = 'Warning';
        badgeFatigue.className = 'metric-badge bad';
        valFatigue.textContent = 'Dry Eyes';
      } else {
        badgeFatigue.textContent = 'Low';
        badgeFatigue.className = 'metric-badge good';
        valFatigue.textContent = 'Alert';
      }
    }
  }
}

window.ErgonomicDetector = ErgonomicDetector;
