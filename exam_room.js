/**
 * Exam room: webcam capture and AI monitoring.
 * Frames are sent to the server where malpractice.exam_monitor runs detection.
 */

// Config
const FRAME_ANALYZE_INTERVAL = 500;    // Send frame every 500ms for responsive detection (matches your script logic)
const HEARTBEAT_INTERVAL = 5000;       // 5 seconds
const SNAPSHOT_INTERVAL = 5000;        // Staff snapshot every 5s
const EVENT_THROTTLE_MS = 5000;        // Tab switch/copy-paste throttle

// State
let videoEl, overlayEl;
let faceDetectionRunning = false;
let eventLastSent = {};
let analyzeTimer, heartbeatTimer, countdownTimer, snapshotTimer;
let lastResult = { faceCount: 0, lookingAway: false };

function getCsrfToken() {
    const input = document.querySelector('input[name="csrfmiddlewaretoken"]');
    return input ? input.value : document.cookie.match(/csrftoken=([^;]+)/)?.[1]?.trim();
}

function getAttemptId() {
    return document.getElementById('attempt-id')?.value;
}

var MALPRACTICE_THRESHOLD = 50;
var liveCounts = {
    multiple_faces: 0,
    no_face: 0,
    tab_switch: 0,
    looking_away: 0,
    phone_usage: 0
};

function updateLiveCountDisplay(counts) {
    if (!counts) return;
    liveCounts.multiple_faces = Number(counts.multiple_faces || 0);
    liveCounts.no_face = Number(counts.no_face || 0);
    liveCounts.tab_switch = Number(counts.tab_switch || 0);
    liveCounts.looking_away = Number(counts.looking_away || 0);
    liveCounts.phone_usage = Number(counts.phone_usage || 0);

    var multiEl = document.getElementById('disp-multi-count');
    var noFaceEl = document.getElementById('disp-noface-count');
    var tabEl = document.getElementById('disp-tab-count');
    var awayEl = document.getElementById('disp-away-count');
    var phoneEl = document.getElementById('disp-phone-count');

    if (multiEl) multiEl.textContent = String(liveCounts.multiple_faces);
    if (noFaceEl) noFaceEl.textContent = String(liveCounts.no_face);
    if (tabEl) tabEl.textContent = String(liveCounts.tab_switch);
    if (awayEl) awayEl.textContent = String(liveCounts.looking_away);
    if (phoneEl) phoneEl.textContent = String(liveCounts.phone_usage);
}

function sendHeartbeat(faceCount, lookingAway) {
    const attemptId = getAttemptId();
    if (!attemptId) return;

    fetch('/malpractice/heartbeat/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCsrfToken(),
            'X-Requested-With': 'XMLHttpRequest'
        },
        credentials: 'same-origin',
        body: JSON.stringify({
            attempt_id: parseInt(attemptId),
            face_count: faceCount,
            looking_away: lookingAway
        })
    }).then(function(r) { return r.json(); }).then(function(data) {
        if (data && data.success && data.counts) {
            updateLiveCountDisplay(data.counts);
        }
        if (data.success && data.malpractice_score >= MALPRACTICE_THRESHOLD) {
            submitExam(true);
        }
    }).catch(function() {});
}

function captureFrameBlob(callback) {
    if (!videoEl || videoEl.readyState < 2) {
        callback(null);
        return;
    }
    var canvas = document.createElement('canvas');
    canvas.width = 640;
    canvas.height = 480;
    var ctx = canvas.getContext('2d');
    ctx.drawImage(videoEl, 0, 0, 640, 480);
    canvas.toBlob(function(blob) {
        callback(blob);
    }, 'image/jpeg', 0.9);
}

function sendMalpracticeEvent(eventType, details) {
    const now = Date.now();
    if (eventLastSent[eventType] && (now - eventLastSent[eventType]) < EVENT_THROTTLE_MS) {
        return;
    }
    eventLastSent[eventType] = now;

    const attemptId = getAttemptId();
    if (!attemptId) return;

    // Tab-switch events are browser-focus signals; attaching webcam snapshots
    // makes reports look misleading (it cannot show the switched tab/app).
    if (eventType === 'tab_switch') {
        var fdNoSnapshot = new FormData();
        fdNoSnapshot.append('csrfmiddlewaretoken', getCsrfToken());
        fdNoSnapshot.append('attempt_id', attemptId);
        fdNoSnapshot.append('event_type', eventType);
        fdNoSnapshot.append('details', JSON.stringify(details || {}));
        fetch('/malpractice/event/', {
            method: 'POST',
            headers: { 'X-Requested-With': 'XMLHttpRequest' },
            credentials: 'same-origin',
            body: fdNoSnapshot
        }).catch(function() {});
        return;
    }

    captureFrameBlob(function(blob) {
        var fd = new FormData();
        fd.append('csrfmiddlewaretoken', getCsrfToken());
        fd.append('attempt_id', attemptId);
        fd.append('event_type', eventType);
        fd.append('details', JSON.stringify(details || {}));
        if (blob) fd.append('snapshot', blob, 'evidence.jpg');
        fetch('/malpractice/event/', {
            method: 'POST',
            headers: { 'X-Requested-With': 'XMLHttpRequest' },
            credentials: 'same-origin',
            body: fd
        }).catch(function() {});
    });
}

function updateWebcamStatus(text, isOk) {
    const el = document.getElementById('webcam-status');
    if (!el) return;
    el.innerHTML = isOk 
        ? '<i class="fas fa-video"></i> <span>Camera active</span>' 
        : '<i class="fas fa-video-slash"></i> <span>' + text + '</span>';
    el.className = 'webcam-status ' + (isOk ? 'status-ok' : 'status-warn');
}

function updateFaceStatus(result) {
    var el = document.getElementById('face-status');
    if (el) {
        var faceCount = result.faceCount || 0;
        var lookingAway = result.lookingAway || false;
        var phoneDetected = result.phone_detected || false;

        if (faceCount === 0) {
            el.innerHTML = '<i class="fas fa-user-slash"></i> <span>No face detected</span>';
            el.className = 'face-status status-warn';
        } else if (phoneDetected) {
            el.innerHTML = '<i class="fas fa-mobile-alt"></i> <span>Phone detected!</span>';
            el.className = 'face-status status-danger';
        } else if (lookingAway) {
            el.innerHTML = '<i class="fas fa-eye-slash"></i> <span>Look at screen</span>';
            el.className = 'face-status status-warn';
        } else {
            el.innerHTML = '<i class="fas fa-user-check"></i> <span>Face detected</span>';
            el.className = 'face-status status-ok';
        }
    }

    var faceDisp = document.getElementById('disp-face');
    var eyesDisp = document.getElementById('disp-eyes');
    var phoneDisp = document.getElementById('disp-phone');
    var timerDisp = document.getElementById('disp-timer');
    if (faceDisp) faceDisp.textContent = result.face_direction || '--';
    if (eyesDisp) eyesDisp.textContent = result.eye_direction || '--';
    if (phoneDisp) {
        phoneDisp.textContent = result.phone_detected ? 'DETECTED' : 'NOT DETECTED';
        phoneDisp.className = result.phone_detected ? 'status-danger' : 'status-ok';
    }
    if (timerDisp) {
        var et = result.elapsed_time !== undefined ? result.elapsed_time : 0;
        timerDisp.textContent = et.toFixed(1) + 's / 15s';
        timerDisp.className = et >= 15 ? 'status-danger' : 'status-ok';
    }
}

function sendFrameForAnalysis() {
    const attemptId = getAttemptId();
    if (!attemptId || !videoEl || videoEl.readyState < 2) return;

    var canvas = document.createElement('canvas');
    canvas.width = 640;
    canvas.height = 480;
    var ctx = canvas.getContext('2d');
    ctx.drawImage(videoEl, 0, 0, 640, 480);

    canvas.toBlob(function(blob) {
        if (!blob) return;
        var fd = new FormData();
        fd.append('frame', blob, 'frame.jpg');
        fd.append('csrfmiddlewaretoken', getCsrfToken());

        fetch('/malpractice/analyze-frame/' + attemptId + '/', {
            method: 'POST',
            body: fd,
            credentials: 'same-origin',
            headers: { 'X-Requested-With': 'XMLHttpRequest' }
        }).then(function(r) { return r.json();         }).then(function(data) {
            if (data.success) {
                lastResult = {
                    faceCount: data.face_count || 0,
                    lookingAway: data.looking_away || false,
                    phone_detected: data.phone_detected || false,
                    face_direction: data.face_direction,
                    eye_direction: data.eye_direction,
                    elapsed_time: data.elapsed_time
                };
                updateFaceStatus(lastResult);
            }
        }).catch(function() {});
    }, 'image/jpeg', 0.95);
}

function sendSnapshot() {
    var attemptId = getAttemptId();
    if (!attemptId || !videoEl || videoEl.readyState < 2) return;
    var c = document.createElement('canvas');
    c.width = 320;
    c.height = 240;
    var ctx2 = c.getContext('2d');
    ctx2.drawImage(videoEl, 0, 0, c.width, c.height);

    ctx2.fillStyle = 'rgba(0,0,0,0.7)';
    ctx2.fillRect(0, 0, c.width, 70);
    ctx2.fillStyle = '#fff';
    ctx2.font = '12px monospace';
    ctx2.fillText('Face: ' + (lastResult.face_direction || '--'), 10, 20);
    ctx2.fillText('Eyes: ' + (lastResult.eye_direction || '--'), 10, 35);
    ctx2.fillText('Phone: ' + (lastResult.phone_detected ? 'DETECTED' : 'NOT DETECTED'), 10, 50);
    ctx2.fillText('Timer: ' + ((lastResult.elapsed_time || 0).toFixed(1) + 's / 15s'), 10, 65);
    if (lastResult.lookingAway || lastResult.phone_detected) {
        ctx2.strokeStyle = '#ef4444';
        ctx2.lineWidth = 4;
        ctx2.strokeRect(2, 2, c.width - 4, c.height - 4);
    }

    c.toBlob(function(blob) {
        if (!blob) return;
        var fd = new FormData();
        fd.append('snapshot', blob, 'snapshot.jpg');
        fd.append('csrfmiddlewaretoken', getCsrfToken());
        fetch('/malpractice/snapshot/' + attemptId + '/', {
            method: 'POST',
            body: fd,
            credentials: 'same-origin',
            headers: { 'X-Requested-With': 'XMLHttpRequest' }
        }).catch(function() {});
    }, 'image/jpeg', 0.7);
}

function startAnalyzeLoop() {
    sendFrameForAnalysis();
    analyzeTimer = setInterval(sendFrameForAnalysis, FRAME_ANALYZE_INTERVAL);
}

function startHeartbeatTimer() {
    sendHeartbeat(lastResult.faceCount, lastResult.lookingAway);
    heartbeatTimer = setInterval(function() {
        sendHeartbeat(lastResult.faceCount, lastResult.lookingAway);
    }, HEARTBEAT_INTERVAL);
}

function handleVisibilityChange() {
    if (document.hidden) {
        sendMalpracticeEvent('tab_switch', { source: 'visibilitychange' });
    }
}

function handleWindowBlur() {
    sendMalpracticeEvent('tab_switch', { source: 'blur' });
}

function preventCopyPaste(e) {
    if (e.ctrlKey && (e.key === 'c' || e.key === 'v' || e.key === 'x')) {
        e.preventDefault();
        sendMalpracticeEvent('copy_paste', { key: e.key });
    }
}

function startTimer(minutes) {
    var remaining = minutes * 60;
    var display = document.getElementById('timer-display');
    if (!display) return;

    var format = function(s) {
        var m = Math.floor(s / 60);
        var sec = s % 60;
        return (String(m).padStart(2, '0') + ':' + String(sec).padStart(2, '0'));
    };

    display.textContent = format(remaining);
    countdownTimer = setInterval(function() {
        remaining--;
        display.textContent = format(Math.max(0, remaining));
        if (remaining <= 0) {
            clearInterval(countdownTimer);
            submitExam();
        }
    }, 1000);
}

function stopAIMonitor() {
    const attemptId = getAttemptId();
    if (!attemptId) return;
    fetch('/malpractice/stop/' + attemptId + '/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCsrfToken(),
            'X-Requested-With': 'XMLHttpRequest'
        },
        credentials: 'same-origin',
        body: JSON.stringify({}),
        keepalive: true
    }).catch(function() {});
}

function saveAllAnswersBeforeSubmit() {
    const attemptId = getAttemptId();
    if (!attemptId) return Promise.resolve();
    const checked = document.querySelectorAll('.question-options input[type=radio]:checked');
    if (checked.length === 0) return Promise.resolve();
    const answers = Array.from(checked).map(function(r) {
        return { question_id: parseInt(r.getAttribute('data-question-id'), 10), selected_answer: r.value };
    });
    function postAnswers() {
        return fetch('/exams/room/' + attemptId + '/save/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCsrfToken(),
                'X-Requested-With': 'XMLHttpRequest'
            },
            credentials: 'same-origin',
            body: JSON.stringify({ answers: answers })
        }).then(function(r) {
            if (!r.ok) throw new Error('save_failed_status_' + r.status);
            return r.json();
        }).then(function(data) {
            if (!data || data.success !== true) throw new Error('save_failed_payload');
            return data;
        });
    }

    // Try once more on transient failure before final submit.
    return postAnswers().catch(function() { return postAnswers(); });
}

function stopVideoStream() {
    if (videoEl && videoEl.srcObject) {
        videoEl.srcObject.getTracks().forEach(function(t) { t.stop(); });
        videoEl.srcObject = null;
    }
}

function submitExam(terminated) {
    var submitBtn = document.getElementById('submit-exam-btn');
    if (submitBtn) {
        submitBtn.disabled = true;
        submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Submitting...';
    }
    faceDetectionRunning = false;
    if (heartbeatTimer) clearInterval(heartbeatTimer);
    if (analyzeTimer) clearInterval(analyzeTimer);
    if (countdownTimer) clearInterval(countdownTimer);
    if (snapshotTimer) clearInterval(snapshotTimer);
    stopVideoStream();
    stopAIMonitor();

    const attemptId = getAttemptId();
    if (!attemptId) return;
    function doSubmit() {
        var form = document.createElement('form');
        form.method = 'POST';
        form.action = '/exams/submit/' + attemptId + '/';
        var csrf = document.querySelector('input[name="csrfmiddlewaretoken"]');
        if (csrf) {
            var inp = document.createElement('input');
            inp.type = 'hidden';
            inp.name = 'csrfmiddlewaretoken';
            inp.value = csrf.value;
            form.appendChild(inp);
        }
        if (terminated) {
            var term = document.createElement('input');
            term.type = 'hidden';
            term.name = 'terminated';
            term.value = '1';
            form.appendChild(term);
        }
        document.body.appendChild(form);
        form.submit();
    }
    saveAllAnswersBeforeSubmit()
        .catch(function() {})
        .then(doSubmit);
}

async function init() {
    videoEl = document.getElementById('webcam');
    overlayEl = document.getElementById('overlay');
    if (!videoEl || !overlayEl) return;

    try {
        if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
            updateWebcamStatus('Camera is not available in this browser or context (HTTPS required).', false);
            return;
        }

        var stream;
        try {
            stream = await navigator.mediaDevices.getUserMedia({
                video: { facingMode: 'user', width: { ideal: 640 }, height: { ideal: 480 } },
                audio: false
            });
        } catch (constraintErr) {
            if (constraintErr && (constraintErr.name === 'OverconstrainedError' || constraintErr.name === 'NotFoundError')) {
                stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
            } else {
                throw constraintErr;
            }
        }

        videoEl.srcObject = stream;
        await videoEl.play();

        updateWebcamStatus('Camera active', true);
        faceDetectionRunning = true;

        var attemptId = getAttemptId();
        if (attemptId) {
            var fd = new FormData();
            fd.append('csrfmiddlewaretoken', getCsrfToken());
            fetch('/malpractice/start/' + attemptId + '/', {
                method: 'POST',
                headers: { 'X-Requested-With': 'XMLHttpRequest' },
                credentials: 'same-origin',
                body: fd
            }).catch(function() {});
        }
        startAnalyzeLoop();
        startHeartbeatTimer();

        function scheduleFirstSnapshot() {
            if (videoEl.readyState >= 2) {
                sendSnapshot();
            } else {
                videoEl.addEventListener('canplay', function onCanPlay() {
                    videoEl.removeEventListener('canplay', onCanPlay);
                    sendSnapshot();
                }, { once: true });
            }
        }
        scheduleFirstSnapshot();
        setTimeout(function() { 
            if (videoEl && videoEl.readyState >= 2) sendSnapshot(); 
        }, 1000);
        snapshotTimer = setInterval(sendSnapshot, SNAPSHOT_INTERVAL);

        var submitBtn = document.getElementById('submit-exam-btn');
        if (submitBtn) submitBtn.addEventListener('click', function() {
            if (confirm('Are you sure you want to submit your exam?')) {
                submitExam(false);
            }
        });

        document.addEventListener('visibilitychange', handleVisibilityChange);
        window.addEventListener('blur', handleWindowBlur);
        document.addEventListener('keydown', preventCopyPaste);
        window.addEventListener('beforeunload', function() { stopVideoStream(); stopAIMonitor(); });
        window.addEventListener('pagehide', function() { stopVideoStream(); stopAIMonitor(); });

        var duration = parseInt(document.getElementById('duration-minutes')?.value || '60', 10);
        startTimer(duration);

    } catch (err) {
        console.error('Camera error:', err);
        if (err && (err.name === 'NotAllowedError' || err.name === 'PermissionDeniedError')) {
            updateWebcamStatus('Camera access denied. Please enable your webcam to take the exam.', false);
        } else {
            updateWebcamStatus('Unable to start camera. Please check webcam connection and browser settings.', false);
        }
    }
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
} else {
    init();
}
