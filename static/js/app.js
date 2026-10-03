/**
 * app.js - Main Application Orchestrator & User Interface Controller
 * Digital Wellness Monitor Major Project
 */

document.addEventListener('DOMContentLoaded', async () => {
  console.log("Initializing Digital Wellness Monitor...");

  // 1. Initialize Managers
  const alertManager = new AlertManager();
  const videoEl = document.getElementById('webcam');
  const canvasEl = document.getElementById('overlay-canvas');
  const detector = new ErgonomicDetector(videoEl, canvasEl, alertManager);
  const analytics = new AnalyticsManager();

  // Wire up alert callbacks
  alertManager.onPostureAlert = (reason) => {
    analytics.recordSlouchAlert();
  };

  alertManager.onBreakTriggered = () => {
    openModal('modal-break');
    startBreakCountdown();
  };

  // 2. Start Camera and Detection Pipeline
  try {
    await detector.startCamera();
    console.log("Webcam and MediaPipe pipeline initialized successfully.");
  } catch (err) {
    console.error("Camera initialization error:", err);
    const hudStatus = document.getElementById('hud-posture-text');
    if (hudStatus) {
      hudStatus.textContent = "CAMERA ERROR: Please allow webcam access in browser.";
      hudStatus.className = "hud-posture-badge bad";
    }
  }

  // 3. Start 1-Second Analytics & Timers Heartbeat
  setInterval(() => {
    if (detector.isTracking) {
      alertManager.tick();
      analytics.update(detector);
    }
  }, 1000);

  // ==========================================
  // Modal Management Helpers
  // ==========================================
  function openModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) modal.classList.add('active');
  }

  function closeModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) modal.classList.remove('active');
  }

  function closeAllModals() {
    document.querySelectorAll('.modal-backdrop').forEach(m => m.classList.remove('active'));
  }

  // ==========================================
  // 20-20-20 Eye Break Modal Controller
  // ==========================================
  let breakIntervalTimer = null;
  function startBreakCountdown() {
    let count = 20;
    const numEl = document.getElementById('break-countdown-number');
    const instructionEl = document.getElementById('breathing-instruction');
    if (numEl) numEl.textContent = count;
    if (instructionEl) instructionEl.textContent = "Breathe In & Focus Far";

    if (breakIntervalTimer) clearInterval(breakIntervalTimer);

    breakIntervalTimer = setInterval(() => {
      count--;
      if (numEl) numEl.textContent = count;

      if (instructionEl) {
        if (count % 4 >= 2) {
          instructionEl.textContent = "Breathe Out & Relax Shoulders";
        } else {
          instructionEl.textContent = "Breathe In & Look 20ft Away";
        }
      }

      if (count <= 0) {
        clearInterval(breakIntervalTimer);
        finishBreak();
      }
    }, 1000);
  }

  function finishBreak() {
    if (breakIntervalTimer) clearInterval(breakIntervalTimer);
    closeModal('modal-break');
    analytics.recordBreakCompleted();
    alertManager.reset202020Timer();
    alertManager.playSuccessChime();
    alertManager.speak("Break completed! Excellent job resting your eyes.");
    
    // Confetti celebration
    if (window.confetti) {
      window.confetti({ particleCount: 80, spread: 70, origin: { y: 0.6 } });
    }
  }

  document.getElementById('btn-complete-break')?.addEventListener('click', finishBreak);
  document.getElementById('btn-skip-break')?.addEventListener('click', () => {
    if (breakIntervalTimer) clearInterval(breakIntervalTimer);
    closeModal('modal-break');
    alertManager.reset202020Timer();
  });

  // ==========================================
  // Header Action Buttons
  // ==========================================
  
  // Calibrate button [C]
  const btnCalibrate = document.getElementById('btn-calibrate-quick');
  btnCalibrate?.addEventListener('click', () => {
    detector.startCalibration(null, (newBase) => {
      alertManager.playSuccessChime();
    });
  });

  // Take Break button [B]
  document.getElementById('btn-break-now')?.addEventListener('click', () => {
    openModal('modal-break');
    startBreakCountdown();
  });

  document.getElementById('btn-quick-eye-break')?.addEventListener('click', () => {
    openModal('modal-break');
    startBreakCountdown();
  });

  // Guided Stretches button
  document.getElementById('btn-stretches')?.addEventListener('click', () => {
    openModal('modal-stretches');
  });
  document.getElementById('btn-close-stretches')?.addEventListener('click', () => {
    closeModal('modal-stretches');
  });
  document.getElementById('btn-done-stretches')?.addEventListener('click', () => {
    closeModal('modal-stretches');
    alertManager.playSuccessChime();
  });

  // Sound Toggle button
  const btnSound = document.getElementById('btn-sound-toggle');
  btnSound?.addEventListener('click', () => {
    alertManager.audioEnabled = !alertManager.audioEnabled;
    alertManager.voiceEnabled = alertManager.audioEnabled;
    btnSound.classList.toggle('active', alertManager.audioEnabled);
    btnSound.innerHTML = alertManager.audioEnabled 
      ? '<i class="fa-solid fa-volume-high"></i>' 
      : '<i class="fa-solid fa-volume-xmark"></i>';
    
    if (alertManager.audioEnabled) {
      alertManager.playTone(550, 'sine', 0.15, 0.2);
    }
  });

  // Settings button
  document.getElementById('btn-settings')?.addEventListener('click', () => {
    loadSettingsIntoModal();
    openModal('modal-settings');
  });
  document.getElementById('btn-close-settings')?.addEventListener('click', () => {
    closeModal('modal-settings');
  });

  // Viva Report button
  document.getElementById('btn-export-report')?.addEventListener('click', () => {
    analytics.prepareReportModal(detector);
    openModal('modal-report');
  });
  document.getElementById('btn-close-report')?.addEventListener('click', () => {
    closeModal('modal-report');
  });

  // Print Report
  document.getElementById('btn-print-report')?.addEventListener('click', () => {
    window.print();
  });

  // Export CSV
  document.getElementById('btn-export-csv')?.addEventListener('click', () => {
    analytics.exportCSV(detector);
  });

  // Save Session to Database
  document.getElementById('btn-save-session-db')?.addEventListener('click', async () => {
    const btn = document.getElementById('btn-save-session-db');
    btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Saving...';
    const result = await analytics.saveToBackend(detector);
    if (result && result.status === 'success') {
      btn.innerHTML = '<i class="fa-solid fa-check"></i> Saved!';
      btn.classList.add('btn-accent');
      setTimeout(() => {
        btn.innerHTML = '<i class="fa-solid fa-cloud-arrow-up"></i> Save to Database';
        btn.classList.remove('btn-accent');
      }, 2500);
    } else {
      btn.innerHTML = '<i class="fa-solid fa-circle-exclamation"></i> Save Failed';
      setTimeout(() => {
        btn.innerHTML = '<i class="fa-solid fa-cloud-arrow-up"></i> Save to Database';
      }, 2000);
    }
  });

  // ==========================================
  // Camera Toolbar Controls
  // ==========================================
  
  // Pause / Resume Camera
  const btnToggleCam = document.getElementById('btn-toggle-camera');
  btnToggleCam?.addEventListener('click', async () => {
    if (detector.isTracking) {
      detector.stopCamera();
      btnToggleCam.innerHTML = '<i class="fa-solid fa-video"></i> <span>Resume Camera</span>';
      btnToggleCam.classList.remove('active');
    } else {
      await detector.startCamera();
      btnToggleCam.innerHTML = '<i class="fa-solid fa-video-slash"></i> <span>Pause Camera</span>';
      btnToggleCam.classList.add('active');
    }
  });

  // Flip Mirror
  const btnFlip = document.getElementById('btn-flip-camera');
  btnFlip?.addEventListener('click', () => {
    detector.isMirrored = !detector.isMirrored;
    btnFlip.classList.toggle('active', detector.isMirrored);
  });

  // Toggle HUD Overlay
  const btnMesh = document.getElementById('btn-toggle-mesh');
  btnMesh?.addEventListener('click', () => {
    detector.showOverlay = !detector.showOverlay;
    btnMesh.classList.toggle('active', detector.showOverlay);
  });

  // ==========================================
  // Settings Form Bindings
  // ==========================================
  function loadSettingsIntoModal() {
    const sTilt = document.getElementById('setting-shoulder-tilt');
    const hTilt = document.getElementById('setting-head-tilt');
    const slouchSens = document.getElementById('setting-slouch-sens');
    const earThresh = document.getElementById('setting-ear-thresh');
    const brkInt = document.getElementById('setting-break-interval');
    const sedInt = document.getElementById('setting-sedentary-interval');
    const togAudio = document.getElementById('toggle-audio-alerts');
    const togVoice = document.getElementById('toggle-voice-alerts');

    if (sTilt) {
      sTilt.value = detector.shoulderTiltThreshold;
      document.getElementById('disp-shoulder-tilt').textContent = `${detector.shoulderTiltThreshold}°`;
    }
    if (hTilt) {
      hTilt.value = detector.headTiltThreshold;
      document.getElementById('disp-head-tilt').textContent = `${detector.headTiltThreshold}°`;
    }
    if (slouchSens) {
      slouchSens.value = detector.slouchTolerance;
      document.getElementById('disp-slouch-sens').textContent = `${Math.round(detector.slouchTolerance * 100)}%`;
    }
    if (earThresh) {
      earThresh.value = detector.earThreshold;
      document.getElementById('disp-ear-thresh').textContent = `${detector.earThreshold}`;
    }
    if (brkInt) brkInt.value = Math.floor(alertManager.break202020Interval / 60);
    if (sedInt) sedInt.value = Math.floor(alertManager.sedentaryInterval / 60);
    if (togAudio) togAudio.checked = alertManager.audioEnabled;
    if (togVoice) togVoice.checked = alertManager.voiceEnabled;
  }

  // Live slider display updates
  document.getElementById('setting-shoulder-tilt')?.addEventListener('input', (e) => {
    document.getElementById('disp-shoulder-tilt').textContent = `${e.target.value}°`;
  });
  document.getElementById('setting-head-tilt')?.addEventListener('input', (e) => {
    document.getElementById('disp-head-tilt').textContent = `${e.target.value}°`;
  });
  document.getElementById('setting-slouch-sens')?.addEventListener('input', (e) => {
    document.getElementById('disp-slouch-sens').textContent = `${Math.round(e.target.value * 100)}%`;
  });
  document.getElementById('setting-ear-thresh')?.addEventListener('input', (e) => {
    document.getElementById('disp-ear-thresh').textContent = `${e.target.value}`;
  });

  // Save Settings button
  document.getElementById('btn-save-settings')?.addEventListener('click', async () => {
    detector.shoulderTiltThreshold = parseFloat(document.getElementById('setting-shoulder-tilt').value);
    detector.headTiltThreshold = parseFloat(document.getElementById('setting-head-tilt').value);
    detector.slouchTolerance = parseFloat(document.getElementById('setting-slouch-sens').value);
    detector.earThreshold = parseFloat(document.getElementById('setting-ear-thresh').value);
    
    alertManager.break202020Interval = parseInt(document.getElementById('setting-break-interval').value) * 60;
    alertManager.sedentaryInterval = parseInt(document.getElementById('setting-sedentary-interval').value) * 60;
    alertManager.audioEnabled = document.getElementById('toggle-audio-alerts').checked;
    alertManager.voiceEnabled = document.getElementById('toggle-voice-alerts').checked;

    closeModal('modal-settings');
    alertManager.playSuccessChime();

    // Persist to backend
    try {
      await fetch('/api/settings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          shoulder_tilt_thresh: detector.shoulderTiltThreshold,
          head_tilt_thresh: detector.headTiltThreshold,
          slouch_ratio_thresh: detector.slouchTolerance,
          ear_thresh: detector.earThreshold,
          audio_enabled: alertManager.audioEnabled,
          voice_enabled: alertManager.voiceEnabled
        })
      });
    } catch (e) {
      console.warn("Could not save settings to server:", e);
    }
  });

  // Test sound button
  document.getElementById('btn-test-sound')?.addEventListener('click', () => {
    alertManager.playPostureWarningChime();
    alertManager.speak("Testing posture voice synthesizer audio output.");
  });

  // Reset defaults
  document.getElementById('btn-reset-defaults')?.addEventListener('click', () => {
    detector.shoulderTiltThreshold = 4.5;
    detector.headTiltThreshold = 6.0;
    detector.slouchTolerance = 0.15;
    detector.earThreshold = 0.21;
    alertManager.break202020Interval = 20 * 60;
    alertManager.sedentaryInterval = 45 * 60;
    alertManager.audioEnabled = true;
    alertManager.voiceEnabled = true;
    loadSettingsIntoModal();
  });

  // ==========================================
  // Keyboard Shortcuts (Matches Reference Image!)
  // ==========================================
  document.addEventListener('keydown', (e) => {
    // If typing in an input, ignore shortcuts
    if (['INPUT', 'TEXTAREA', 'SELECT'].includes(document.activeElement.tagName)) return;

    const key = e.key.toUpperCase();
    if (key === 'C') {
      e.preventDefault();
      detector.startCalibration();
    } else if (key === 'B') {
      e.preventDefault();
      openModal('modal-break');
      startBreakCountdown();
    } else if (key === ' ' || e.code === 'Space') {
      e.preventDefault();
      btnToggleCam?.click();
    } else if (key === 'ESCAPE') {
      closeAllModals();
    }
  });

  console.log("Digital Wellness Monitor fully ready.");
});
