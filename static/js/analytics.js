/**
 * analytics.js - Telemetry graphs, session tracking, and Viva report generation
 * Digital Wellness Monitor Major Project
 */

class AnalyticsManager {
  constructor() {
    this.sessionStartTime = Date.now();
    this.durationSeconds = 0;
    this.goodPostureSeconds = 0;
    this.slouchSeconds = 0;
    this.tiltSeconds = 0;
    this.breaksCompleted = 0;
    this.slouchAlertsCount = 0;

    this.scoreSamples = [];
    this.bpmSamples = [];

    this.chart = null;
    this.chartLabels = [];
    this.chartScoreData = [];
    this.chartBpmData = [];
    this.maxDataPoints = 30; // Rolling 30 intervals

    this.initChart();
  }

  initChart() {
    const ctx = document.getElementById('telemetryChart');
    if (!ctx) return;

    // Pre-populate empty labels
    for (let i = 0; i < this.maxDataPoints; i++) {
      this.chartLabels.push('');
      this.chartScoreData.push(100);
      this.chartBpmData.push(16);
    }

    this.chart = new Chart(ctx, {
      type: 'line',
      data: {
        labels: this.chartLabels,
        datasets: [
          {
            label: 'Posture Score (%)',
            data: this.chartScoreData,
            borderColor: '#00ff88',
            backgroundColor: 'rgba(0, 255, 136, 0.08)',
            borderWidth: 2.2,
            tension: 0.35,
            fill: true,
            pointRadius: 0,
            yAxisID: 'y'
          },
          {
            label: 'Blink Rate (BPM)',
            data: this.chartBpmData,
            borderColor: '#00d2ff',
            borderWidth: 2,
            borderDash: [4, 4],
            tension: 0.3,
            fill: false,
            pointRadius: 0,
            yAxisID: 'y1'
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        animation: { duration: 400 },
        plugins: {
          legend: { display: false },
          tooltip: {
            mode: 'index',
            intersect: false,
            backgroundColor: 'rgba(15, 21, 35, 0.9)',
            titleColor: '#00d2ff',
            bodyColor: '#f0f4fc',
            borderColor: 'rgba(255, 255, 255, 0.1)',
            borderWidth: 1
          }
        },
        scales: {
          x: {
            display: false,
            grid: { display: false }
          },
          y: {
            min: 0,
            max: 100,
            grid: { color: 'rgba(255, 255, 255, 0.05)' },
            ticks: {
              color: '#8e9bb5',
              font: { size: 10 },
              stepSize: 25
            }
          },
          y1: {
            position: 'right',
            min: 0,
            max: 40,
            display: false,
            grid: { display: false }
          }
        }
      }
    });
  }

  // Update telemetry graph and session tallies each second
  update(detector) {
    this.durationSeconds++;
    
    const isGood = detector.postureStatus.includes("GOOD");
    if (isGood) {
      this.goodPostureSeconds++;
    } else if (detector.postureStatus.includes("Slouch")) {
      this.slouchSeconds++;
    } else {
      this.tiltSeconds++;
    }

    this.scoreSamples.push(detector.postureScore);
    this.bpmSamples.push(detector.bpm);

    // Update Chart
    if (this.chart) {
      this.chartScoreData.push(detector.postureScore);
      this.chartBpmData.push(detector.bpm);

      if (this.chartScoreData.length > this.maxDataPoints) {
        this.chartScoreData.shift();
        this.chartBpmData.shift();
      }
      this.chart.update('none'); // fast update without full redraw
    }

    // Update percentages in UI
    const total = Math.max(1, this.durationSeconds);
    const goodPct = Math.round((this.goodPostureSeconds / total) * 100);
    const badPct = 100 - goodPct;

    const goodEl = document.getElementById('good-time-pct');
    const badEl = document.getElementById('bad-time-pct');
    const barGood = document.getElementById('bar-good-pct');
    const barBad = document.getElementById('bar-bad-pct');

    if (goodEl) goodEl.textContent = `${goodPct}%`;
    if (badEl) badEl.textContent = `${badPct}%`;
    if (barGood) barGood.style.width = `${goodPct}%`;
    if (barBad) barBad.style.width = `${badPct}%`;

    // Update Session Timer in header
    const hrs = String(Math.floor(this.durationSeconds / 3600)).padStart(2, '0');
    const mins = String(Math.floor((this.durationSeconds % 3600) / 60)).padStart(2, '0');
    const secs = String(this.durationSeconds % 60).padStart(2, '0');
    const timerEl = document.getElementById('session-timer');
    if (timerEl) timerEl.textContent = `${hrs}:${mins}:${secs}`;
  }

  recordBreakCompleted() {
    this.breaksCompleted++;
  }

  recordSlouchAlert() {
    this.slouchAlertsCount++;
  }

  // Calculate Ergonomic Grade for Viva Evaluation
  calculateGrade() {
    const total = Math.max(1, this.durationSeconds);
    const goodPct = (this.goodPostureSeconds / total) * 100;
    const avgScore = this.scoreSamples.length > 0 
      ? this.scoreSamples.reduce((a, b) => a + b, 0) / this.scoreSamples.length 
      : 100;

    let grade = 'A';
    let title = 'Excellent Ergonomics';
    let desc = 'Balanced spinal alignment, good gaze elevation, and healthy blink frequency.';

    if (goodPct >= 90 && avgScore >= 90) {
      grade = 'A+';
      title = 'Exceptional Alignment';
      desc = 'Near-perfect upright habit with high break adherence and relaxed cervical spine.';
    } else if (goodPct >= 80 && avgScore >= 80) {
      grade = 'A';
      title = 'Good Ergonomic Health';
      desc = 'Occasional minor deviation quickly corrected. Minimal muscle fatigue risk.';
    } else if (goodPct >= 65 && avgScore >= 65) {
      grade = 'B';
      title = 'Moderate Postural Strain';
      desc = 'Noticeable forward head tilt or shoulder slump. Perform desk stretches regularly.';
    } else if (goodPct >= 50) {
      grade = 'C';
      title = 'High Musculoskeletal Risk';
      desc = 'Frequent prolonged slouching detected. Elevate your laptop screen to eye level.';
    } else {
      grade = 'D';
      title = 'Severe Text-Neck & Strain';
      desc = 'Persistent chronic slouching. Immediate ergonomic workstation adjustment needed.';
    }

    return { grade, title, desc, avgScore: Math.round(avgScore), goodPct: Math.round(goodPct) };
  }

  // Render Viva Report Modal with live data
  prepareReportModal(detector) {
    const total = Math.max(1, this.durationSeconds);
    const goodPct = Math.round((this.goodPostureSeconds / total) * 100);
    const slouchPct = Math.round((this.slouchSeconds / total) * 100);
    const tiltPct = Math.max(0, 100 - goodPct - slouchPct);
    const avgBpm = this.bpmSamples.length > 0 
      ? (this.bpmSamples.reduce((a, b) => a + b, 0) / this.bpmSamples.length).toFixed(1)
      : detector.bpm;

    const evaluation = this.calculateGrade();

    const hrs = String(Math.floor(this.durationSeconds / 3600)).padStart(2, '0');
    const mins = String(Math.floor((this.durationSeconds % 3600) / 60)).padStart(2, '0');
    const secs = String(this.durationSeconds % 60).padStart(2, '0');

    // Populate Report Modal elements
    document.getElementById('rep-date-time').textContent = new Date().toLocaleString();
    document.getElementById('rep-duration').textContent = `${hrs}:${mins}:${secs}`;
    document.getElementById('rep-grade').textContent = evaluation.grade;
    document.getElementById('rep-grade-title').textContent = evaluation.title;
    document.getElementById('rep-grade-comment').textContent = evaluation.desc;
    document.getElementById('rep-avg-score').textContent = `${evaluation.avgScore}%`;
    document.getElementById('rep-good-pct').textContent = `${goodPct}%`;
    document.getElementById('rep-slouch-pct').textContent = `${slouchPct}%`;
    document.getElementById('rep-tilt-pct').textContent = `${tiltPct}%`;
    document.getElementById('rep-total-blinks').textContent = detector.blinkCount;
    document.getElementById('rep-avg-bpm').textContent = `${avgBpm} BPM`;
    document.getElementById('rep-breaks-count').textContent = this.breaksCompleted;
  }

  // Export session data as CSV file
  exportCSV(detector) {
    const evaluation = this.calculateGrade();
    const total = Math.max(1, this.durationSeconds);
    const goodPct = Math.round((this.goodPostureSeconds / total) * 100);
    const slouchPct = Math.round((this.slouchSeconds / total) * 100);
    const tiltPct = Math.max(0, 100 - goodPct - slouchPct);

    const rows = [
      ["Metric", "Value", "Unit / Status"],
      ["Date & Time", new Date().toISOString(), "ISO-8601"],
      ["Session Duration", this.durationSeconds, "Seconds"],
      ["Ergonomic Grade", evaluation.grade, evaluation.title],
      ["Average Health Score", evaluation.avgScore, "%"],
      ["Good Posture Duration", `${goodPct}% (${this.goodPostureSeconds}s)`, "Optimal"],
      ["Slouched / Forward Head", `${slouchPct}% (${this.slouchSeconds}s)`, "Sub-optimal"],
      ["Asymmetric Lateral Tilt", `${tiltPct}% (${this.tiltSeconds}s)`, "Deviation"],
      ["Total Eye Blinks", detector.blinkCount, "Blinks"],
      ["Baseline Slouch Ratio", detector.baselineSlouchRatio, "Calibrated Ratio"],
      ["20-20-20 Breaks Taken", this.breaksCompleted, "Count"],
      ["Slouch Audio Warnings", this.slouchAlertsCount, "Count"]
    ];

    const csvContent = "data:text/csv;charset=utf-8," + rows.map(e => e.join(",")).join("\n");
    const encodedUri = encodeURI(csvContent);
    const link = document.createElement("a");
    link.setAttribute("href", encodedUri);
    link.setAttribute("download", `wellness_session_${Date.now()}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  }

  // Persist session to FastAPI backend SQLite database
  async saveToBackend(detector) {
    const evaluation = this.calculateGrade();
    const total = Math.max(1, this.durationSeconds);
    const goodPct = Math.round((this.goodPostureSeconds / total) * 100);
    const slouchPct = Math.round((this.slouchSeconds / total) * 100);
    const tiltPct = Math.max(0, 100 - goodPct - slouchPct);
    const avgBpm = this.bpmSamples.length > 0 
      ? parseFloat((this.bpmSamples.reduce((a, b) => a + b, 0) / this.bpmSamples.length).toFixed(1))
      : detector.bpm;

    const payload = {
      timestamp: new Date().toISOString(),
      duration_seconds: this.durationSeconds,
      avg_posture_score: evaluation.avgScore,
      good_posture_pct: goodPct,
      slouch_pct: slouchPct,
      tilt_pct: tiltPct,
      total_blinks: detector.blinkCount,
      avg_blink_rate: avgBpm,
      breaks_completed: this.breaksCompleted,
      slouch_alerts_count: this.slouchAlertsCount,
      ergonomic_grade: evaluation.grade
    };

    try {
      const resp = await fetch('/api/sessions/save', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      const data = await resp.json();
      return data;
    } catch (err) {
      console.warn("Could not save to backend database:", err);
      return null;
    }
  }
}

window.AnalyticsManager = AnalyticsManager;
