/**
 * alerts.js - Audio synthesis, speech feedback, and ergonomic break timers
 * Digital Wellness Monitor Major Project
 */

class AlertManager {
  constructor() {
    this.audioContext = null;
    this.audioEnabled = true;
    this.voiceEnabled = true;
    this.desktopNotifEnabled = false;

    // Last alert timestamps to debounce
    this.lastSlouchAlertTime = 0;
    this.slouchAlertCooldown = 6000; // 6 seconds between voice reminders

    // Timer configs (in seconds)
    this.break202020Interval = 20 * 60; // 20 minutes
    this.break202020Remaining = this.break202020Interval;
    this.breakActive = false;
    this.breakCountdown = 20; // 20 seconds duration

    this.sedentaryInterval = 45 * 60; // 45 minutes
    this.sedentaryElapsed = 0;

    // Slouch duration tracker
    this.consecutivePoorPostureSeconds = 0;
    this.poorPostureAlertThreshold = 4; // alert after 4 continuous seconds

    // Callbacks
    this.onBreakTriggered = null;
    this.onBreakCompleted = null;
    this.onSedentaryAlert = null;
    this.onPostureAlert = null;

    this.initAudioContext();
  }

  initAudioContext() {
    // AudioContext must be unlocked via user gesture
    const unlock = () => {
      if (!this.audioContext) {
        const AudioContextClass = window.AudioContext || window.webkitAudioContext;
        if (AudioContextClass) {
          this.audioContext = new AudioContextClass();
        }
      }
      if (this.audioContext && this.audioContext.state === 'suspended') {
        this.audioContext.resume();
      }
      document.removeEventListener('click', unlock);
      document.removeEventListener('keydown', unlock);
    };
    document.addEventListener('click', unlock);
    document.addEventListener('keydown', unlock);
  }

  // Pure Web Audio tone synthesis
  playTone(freq = 440, type = 'sine', duration = 0.25, gainVal = 0.2) {
    if (!this.audioEnabled || !this.audioContext) return;
    try {
      if (this.audioContext.state === 'suspended') {
        this.audioContext.resume();
      }
      const osc = this.audioContext.createOscillator();
      const gainNode = this.audioContext.createGain();

      osc.type = type;
      osc.frequency.setValueAtTime(freq, this.audioContext.currentTime);

      gainNode.gain.setValueAtTime(gainVal, this.audioContext.currentTime);
      gainNode.gain.exponentialRampToValueAtTime(0.001, this.audioContext.currentTime + duration);

      osc.connect(gainNode);
      gainNode.connect(this.audioContext.destination);

      osc.start();
      osc.stop(this.audioContext.currentTime + duration);
    } catch (e) {
      console.warn("Audio playback error:", e);
    }
  }

  // Play pleasant chord on successful action (e.g. calibration or break done)
  playSuccessChime() {
    if (!this.audioEnabled) return;
    setTimeout(() => this.playTone(523.25, 'sine', 0.2, 0.18), 0);   // C5
    setTimeout(() => this.playTone(659.25, 'sine', 0.2, 0.18), 120); // E5
    setTimeout(() => this.playTone(783.99, 'sine', 0.35, 0.22), 240); // G5
  }

  // Play attention chime on poor posture warning
  playPostureWarningChime() {
    if (!this.audioEnabled) return;
    this.playTone(400, 'triangle', 0.18, 0.25);
    setTimeout(() => this.playTone(320, 'triangle', 0.28, 0.25), 180);
  }

  // Play gentle alert for 20-20-20 break
  playBreakAlarm() {
    if (!this.audioEnabled) return;
    this.playTone(587.33, 'sine', 0.25, 0.2); // D5
    setTimeout(() => this.playTone(880.00, 'sine', 0.4, 0.25), 250); // A5
  }

  // Speech synthesis for ergonomic prompts
  speak(text) {
    if (!this.voiceEnabled || !('speechSynthesis' in window)) return;
    window.speechSynthesis.cancel(); // Stop any pending utterances
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.rate = 1.05;
    utterance.pitch = 1.0;
    utterance.volume = 0.85;
    window.speechSynthesis.speak(utterance);
  }

  // Notify user when poor posture is detected
  handlePostureState(isGoodPosture, reason = "") {
    const now = Date.now();
    const banner = document.getElementById('posture-warning-banner');

    if (isGoodPosture) {
      this.consecutivePoorPostureSeconds = 0;
      if (banner) banner.classList.remove('active');
    } else {
      this.consecutivePoorPostureSeconds += 1;
      
      // If poor posture persists past threshold
      if (this.consecutivePoorPostureSeconds >= this.poorPostureAlertThreshold) {
        if (banner) banner.classList.add('active');

        if (now - this.lastSlouchAlertTime > this.slouchAlertCooldown) {
          this.playPostureWarningChime();
          this.speak("Posture alert: please sit upright and align your shoulders.");
          this.lastSlouchAlertTime = now;
          if (this.onPostureAlert) this.onPostureAlert(reason);
        }
      }
    }
  }

  // Notify user for prolonged low blink rate (eye strain)
  handleEyeStrainAlert() {
    const now = Date.now();
    if (now - this.lastSlouchAlertTime > 20000) {
      this.playTone(480, 'sine', 0.25, 0.18);
      this.speak("Low blink rate detected. Remember to blink gently to rest your eyes.");
      this.lastSlouchAlertTime = now;
    }
  }

  // Update break timers each second
  tick() {
    // 1. Sedentary Timer
    this.sedentaryElapsed += 1;
    const sedMin = Math.floor(this.sedentaryElapsed / 60);
    const sedSec = this.sedentaryElapsed % 60;
    const sedDisplay = document.getElementById('timer-sedentary-display');
    if (sedDisplay) {
      sedDisplay.textContent = `${String(sedMin).padStart(2, '0')}:${String(sedSec).padStart(2, '0')}`;
    }

    if (this.sedentaryElapsed >= this.sedentaryInterval) {
      this.playBreakAlarm();
      this.speak("Sedentary reminder. You have been sitting for 45 minutes. Please stand up, walk, and stretch.");
      if (this.onSedentaryAlert) this.onSedentaryAlert();
      this.sedentaryElapsed = 0; // reset
    }

    // 2. 20-20-20 Eye Break Timer
    if (!this.breakActive) {
      this.break202020Remaining -= 1;
      if (this.break202020Remaining <= 0) {
        this.trigger202020Break();
      } else {
        const bMin = Math.floor(this.break202020Remaining / 60);
        const bSec = this.break202020Remaining % 60;
        const bDisplay = document.getElementById('timer-202020-display');
        if (bDisplay) {
          bDisplay.textContent = `${String(bMin).padStart(2, '0')}:${String(bSec).padStart(2, '0')}`;
        }
      }
    }
  }

  trigger202020Break() {
    this.breakActive = true;
    this.playBreakAlarm();
    this.speak("Time for your 20-20-20 eye break! Look at an object 20 feet away for 20 seconds.");
    if (this.onBreakTriggered) this.onBreakTriggered();
  }

  reset202020Timer() {
    this.breakActive = false;
    this.break202020Remaining = this.break202020Interval;
    this.breakCountdown = 20;
    const bDisplay = document.getElementById('timer-202020-display');
    if (bDisplay) {
      const bMin = Math.floor(this.break202020Interval / 60);
      bDisplay.textContent = `${String(bMin).padStart(2, '0')}:00`;
    }
  }

  requestDesktopPermission() {
    if ('Notification' in window && Notification.permission !== 'granted') {
      Notification.requestPermission().then(permission => {
        this.desktopNotifEnabled = (permission === 'granted');
      });
    }
  }

  showDesktopNotification(title, body) {
    if (this.desktopNotifEnabled && 'Notification' in window && Notification.permission === 'granted') {
      try {
        new Notification(title, { body, icon: '/static/assets/icon.png' });
      } catch (e) {
        console.warn("Desktop notification failed:", e);
      }
    }
  }
}

window.AlertManager = AlertManager;
