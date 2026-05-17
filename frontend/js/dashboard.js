// Backend API base URL
const API_BASE = 'http://127.0.0.1:8000';

// ==================== NAVIGATION ====================
function showSection(sectionId, evt) {
  const sections = document.querySelectorAll('.content-section');
  sections.forEach(section => section.classList.remove('active'));

  const targetSection = document.getElementById(sectionId);
  if (targetSection) {
    targetSection.classList.add('active');
  }

  const navItems = document.querySelectorAll('.nav-item');
  navItems.forEach(item => item.classList.remove('active'));

  // Use the passed event or window.event fallback
  const e = evt || window.event;
  if (e && e.target) {
    e.target.closest('.nav-item')?.classList.add('active');
  }

  const titles = {
    'overview': 'Dashboard Overview',
    'upload-key': 'Upload Answer Key',
    'submissions': 'Student Submissions',
    'evaluate': 'Evaluate Answer Sheets',
    'review': 'Review Results',
    'upload': 'Upload Answer Sheet',
    'results': 'Exam Results',
    'performance': 'Performance Analytics'
  };

  const titleElement = document.getElementById('section-title');
  if (titleElement && titles[sectionId]) {
    titleElement.textContent = titles[sectionId];
  }

  // Load data for certain sections
  if (sectionId === 'overview') loadDashboardStats();
  if (sectionId === 'submissions') loadSubmissions();
  if (sectionId === 'evaluate') loadPendingAnswers();
}

// ==================== DASHBOARD STATS ====================
async function loadDashboardStats() {
  try {
    const res = await fetch(`${API_BASE}/api/dashboard-stats`);
    const data = await res.json();

    const statCards = document.querySelectorAll('.stat-info h3');
    if (statCards.length >= 4) {
      statCards[0].textContent = data.total_exams ?? 0;
      statCards[1].textContent = data.total_submissions ?? 0;
      statCards[2].textContent = data.evaluated ?? 0;
      statCards[3].textContent = data.pending ?? 0;
    }
  } catch (err) {
    console.error('Failed to load dashboard stats:', err);
  }
}

// ==================== LOAD SUBMISSIONS (TEACHER) ====================
async function loadSubmissions() {
  try {
    const res = await fetch(`${API_BASE}/api/student-submissions`);
    const data = await res.json();

    const grid = document.querySelector('#submissions .submissions-grid');
    if (!grid || !data.submissions) return;

    grid.innerHTML = data.submissions.map(sub => `
      <div class="submission-card card">
        <div class="submission-header">
          <h4>${sub.exam_name || 'Untitled Exam'}</h4>
          <span class="badge badge-${sub.status === 'evaluated' ? 'evaluated' : 'pending'}">${sub.status || 'pending'}</span>
        </div>
        <p class="submission-info">Student: ${sub.student || sub.roll_number || 'Unknown'}</p>
        <p class="submission-info">Roll No: ${sub.roll_number || 'N/A'}</p>
        <p class="submission-info">Subject: ${sub.subject || 'N/A'}</p>
        <p class="submission-info">Submitted: ${sub.timestamp || 'N/A'}</p>
        ${sub.status === 'pending' ?
          `<button class="btn btn-primary" onclick="startAIEvaluation('${sub.roll_number}')">AI Evaluate</button>` :
          `<button class="btn btn-secondary" onclick="viewReport('${sub.roll_number}')">View Results</button>`
        }
      </div>
    `).join('');
  } catch (err) {
    console.error('Failed to load submissions:', err);
  }
}

// ==================== LOAD PENDING ANSWERS ====================
async function loadPendingAnswers() {
  try {
    const res = await fetch(`${API_BASE}/api/pending-answers`);
    const data = await res.json();

    const container = document.querySelector('#evaluate .evaluate-content');
    if (!container || !data.pending) return;

    if (data.pending.length === 0) {
      container.innerHTML = '<p style="text-align:center;color:#64748b;">No pending submissions to evaluate.</p>';
      return;
    }

    container.innerHTML = data.pending.map(sub => `
      <div class="submission-card card" style="margin-bottom:16px;">
        <div class="submission-header">
          <h4>${sub.exam_name || 'Untitled'} — ${sub.subject || ''}</h4>
        </div>
        <p class="submission-info">Roll No: ${sub.roll_number}</p>
        <p class="submission-info">Type: ${sub.answer_sheet_type || 'descriptive'}</p>
        <button class="btn btn-primary" onclick="startAIEvaluation('${sub.roll_number}')">🤖 Start AI Evaluation</button>
        <button class="btn btn-secondary" onclick="startMockEvaluation('${sub.roll_number}')">⚡ Quick Evaluate</button>
      </div>
    `).join('');
  } catch (err) {
    console.error('Failed to load pending answers:', err);
  }
}

// ==================== FILE PREVIEW HANDLERS ====================
document.getElementById('answerKeyFile')?.addEventListener('change', function(e) {
  const file = e.target.files[0];
  if (file) {
    const reader = new FileReader();
    reader.onload = function(event) {
      document.querySelector('.upload-placeholder').style.display = 'none';
      document.getElementById('answerKeyPreview').style.display = 'block';

      if (file.type.startsWith('image/')) {
        document.getElementById('answerKeyImage').src = event.target.result;
        document.getElementById('answerKeyImage').style.display = 'block';
      }
      document.getElementById('answerKeyFileName').textContent = file.name;
    };
    reader.readAsDataURL(file);
  }
});

document.getElementById('answerSheetFile')?.addEventListener('change', function(e) {
  const files = e.target.files;
  if (files.length > 0) {
    document.querySelector('#answerSheetUpload .upload-placeholder').style.display = 'none';
    document.getElementById('answerSheetPreview').style.display = 'block';

    const gallery = document.getElementById('imageGallery');
    gallery.innerHTML = '';

    Array.from(files).forEach(file => {
      if (file.type.startsWith('image/')) {
        const reader = new FileReader();
        reader.onload = function(event) {
          const img = document.createElement('img');
          img.src = event.target.result;
          gallery.appendChild(img);
        };
        reader.readAsDataURL(file);
      } else {
        const p = document.createElement('p');
        p.textContent = `📄 ${file.name}`;
        p.style.color = '#64748b';
        gallery.appendChild(p);
      }
    });
  }
});

// ==================== UPLOAD ANSWER KEY (TEACHER) ====================
document.getElementById('answerKeyForm')?.addEventListener('submit', async function(e) {
  e.preventDefault();

  const fileInput = document.getElementById('answerKeyFile');
  if (!fileInput.files.length) {
    alert('Please select an answer key file.');
    return;
  }

  const formData = new FormData();
  formData.append('file', fileInput.files[0]);
  formData.append('exam_name', document.getElementById('examName').value);
  formData.append('subject', document.getElementById('subject').value);
  formData.append('total_marks', document.getElementById('totalMarks').value);
  formData.append('key_type', document.getElementById('keyType').value);
  formData.append('teacher', localStorage.getItem('userEmail') || 'Unknown Teacher');

  try {
    const res = await fetch(`${API_BASE}/api/upload-key`, {
      method: 'POST',
      body: formData
    });

    const data = await res.json();
    if (!res.ok) {
      alert(data.detail || 'Upload failed');
      return;
    }

    alert(data.message || 'Answer key uploaded!');
    this.reset();
    const placeholder = document.querySelector('.upload-placeholder');
    if (placeholder) placeholder.style.display = 'block';
    const preview = document.getElementById('answerKeyPreview');
    if (preview) preview.style.display = 'none';
  } catch (err) {
    console.error('Upload error:', err);
    alert('Failed to upload. Check if server is running.');
  }
});

// ==================== UPLOAD ANSWER SHEET (STUDENT) ====================
document.getElementById('answerSheetForm')?.addEventListener('submit', async function(e) {
  e.preventDefault();

  const fileInput = document.getElementById('answerSheetFile');
  if (!fileInput.files.length) {
    alert('Please select answer sheet files.');
    return;
  }

  const formData = new FormData();
  for (const file of fileInput.files) {
    formData.append('files', file);
  }
  formData.append('exam_name', document.getElementById('examName').value);
  formData.append('subject', document.getElementById('subject').value);
  formData.append('roll_number', document.getElementById('rollNumber').value);
  formData.append('notes', document.getElementById('notes')?.value || '');
  formData.append('answer_sheet_type', 'Descriptive');
  formData.append('student', localStorage.getItem('userEmail') || 'Unknown Student');

  try {
    const res = await fetch(`${API_BASE}/api/upload-answer`, {
      method: 'POST',
      body: formData
    });

    const data = await res.json();
    if (!res.ok) {
      alert(data.detail || 'Upload failed');
      return;
    }

    alert(data.message || 'Answer sheet submitted!');
    this.reset();
    const placeholder = document.querySelector('#answerSheetUpload .upload-placeholder');
    if (placeholder) placeholder.style.display = 'block';
    const preview = document.getElementById('answerSheetPreview');
    if (preview) preview.style.display = 'none';
  } catch (err) {
    console.error('Upload error:', err);
    alert('Failed to upload. Check if server is running.');
  }
});

// ==================== AI EVALUATION ====================
async function startAIEvaluation(rollNumber) {
  if (!confirm(`Start AI evaluation for Roll No ${rollNumber}?`)) return;

  try {
    const res = await fetch(`${API_BASE}/api/ai-evaluate/${rollNumber}`, {
      method: 'POST'
    });
    const data = await res.json();

    if (!res.ok) {
      alert(data.detail || 'Evaluation failed');
      return;
    }

    alert(`${data.message}\nMarks: ${data.marks_obtained}/${data.total_marks}\n${data.feedback || ''}`);
    loadSubmissions();
    loadPendingAnswers();
  } catch (err) {
    console.error('AI Evaluation error:', err);
    alert('Evaluation failed. Check server logs.');
  }
}

async function startMockEvaluation(rollNumber) {
  if (!confirm(`Start quick evaluation for Roll No ${rollNumber}?`)) return;

  try {
    const res = await fetch(`${API_BASE}/api/start-evaluation/${rollNumber}`, {
      method: 'POST'
    });
    const data = await res.json();

    if (!res.ok) {
      alert(data.detail || 'Evaluation failed');
      return;
    }

    alert(`${data.message}\nMarks: ${data.marks_obtained}/100\n${data.feedback || ''}`);
    loadSubmissions();
    loadPendingAnswers();
  } catch (err) {
    console.error('Evaluation error:', err);
    alert('Evaluation failed. Check server logs.');
  }
}

// ==================== EVALUATION PROGRESS (legacy UI) ====================
function startEvaluation() {
  const progressDiv = document.getElementById('evaluationProgress');
  const resultDiv = document.getElementById('evaluationResult');
  const progressFill = document.getElementById('progressFill');
  const progressText = document.getElementById('progressText');

  if (!progressDiv) return;

  progressDiv.style.display = 'block';
  if (resultDiv) resultDiv.style.display = 'none';

  let progress = 0;
  const interval = setInterval(() => {
    progress += 10;
    progressFill.style.width = progress + '%';
    progressText.textContent = `Processing... ${progress}%`;

    if (progress >= 100) {
      clearInterval(interval);
      setTimeout(() => {
        progressDiv.style.display = 'none';
        if (resultDiv) resultDiv.style.display = 'block';
      }, 500);
    }
  }, 300);
}

// ==================== REPORT VIEWING ====================
async function viewReport(rollNumber) {
  try {
    const res = await fetch(`${API_BASE}/api/evaluation-report/${rollNumber}`);
    const data = await res.json();

    if (!res.ok) {
      alert(data.detail || 'Could not load report');
      return;
    }

    const msg = [
      `Roll No: ${data.roll_number || rollNumber}`,
      `Exam: ${data.exam_name || 'N/A'}`,
      `Marks: ${data.marks_obtained}/${data.total_marks}`,
      `Percentage: ${data.percentage || 'N/A'}%`,
      `Method: ${data.evaluation_method || 'N/A'}`,
      `\nFeedback: ${data.feedback || 'No feedback'}`
    ].join('\n');

    alert(msg);
  } catch (err) {
    console.error('Report error:', err);
    alert('Failed to load report.');
  }
}

// ==================== MODAL ====================
function showDetailedResult() {
  const modal = document.getElementById('resultModal');
  if (modal) modal.classList.add('active');
}

function closeModal() {
  const modal = document.getElementById('resultModal');
  if (modal) modal.classList.remove('active');
}

window.onclick = function(event) {
  const modal = document.getElementById('resultModal');
  if (event.target === modal) {
    modal.classList.remove('active');
  }
};

// ==================== AUTO-LOAD ON PAGE LOAD ====================
document.addEventListener('DOMContentLoaded', () => {
  loadDashboardStats();
});
