// ===============================
// DASHBOARD.JS (Student + Teacher)
// ===============================

// SECTION SWITCHING
function showSection(sectionId) {
    document.querySelectorAll(".content-section").forEach(section => section.classList.remove("active"));
    document.getElementById(sectionId)?.classList.add("active");

    const titles = {
        overview: "Dashboard Overview",
        upload: "Upload Answer Sheet",
        results: "View Results",
        performance: "Performance Analytics",
        "upload-key": "Upload Answer Key",
        submissions: "View Submissions"
    };
    document.getElementById("section-title").textContent = titles[sectionId] || "Dashboard Overview";
}

// STATUS DISPLAY
function updateStatus(id, message, success = true) {
    const el = document.getElementById(id);
    if (!el) return;
    el.innerHTML = `<div class="upload-status ${success ? "success" : "error"}">${success ? "✅" : "❌"} ${message}</div>`;
    setTimeout(() => (el.innerHTML = ""), 5000);
}

// ========== TEACHER UPLOAD KEY ==========
const answerKeyForm = document.getElementById("answerKeyForm");
if (answerKeyForm) {
    answerKeyForm.addEventListener("submit", async e => {
        e.preventDefault();
        const file = document.getElementById("answerKeyFile").files[0];
        if (!file) return updateStatus("teacherUploadStatus", "No file selected", false);

        const formData = new FormData();
        formData.append("file", file);
        formData.append("teacher", localStorage.getItem("userEmail") || "Unknown");

        const res = await fetch("http://127.0.0.1:5000/api/upload-key", { method: "POST", body: formData });
        const data = await res.json();
        updateStatus("teacherUploadStatus", res.ok ? data.message : data.error, res.ok);
        if (res.ok) loadStudentSubmissions();
    });
}

// ========== STUDENT UPLOAD ==========
const answerSheetForm = document.getElementById("answerSheetForm");
if (answerSheetForm) {
    const fileInput = document.getElementById("answerSheetFile");
    const previewContainer = document.getElementById("answerSheetPreview");
    const gallery = document.getElementById("imageGallery");

    fileInput.addEventListener("change", () => {
        gallery.innerHTML = "";
        const files = Array.from(fileInput.files);
        if (!files.length) return (previewContainer.style.display = "none");

        previewContainer.style.display = "block";
        files.forEach(f => {
            const div = document.createElement("div");
            div.classList.add("preview-item");
            if (f.type.startsWith("image/")) {
                const img = document.createElement("img");
                img.classList.add("preview-thumb");
                img.src = URL.createObjectURL(f);
                div.appendChild(img);
            } else {
                div.textContent = `📄 ${f.name}`;
                div.classList.add("pdf-preview");
            }
            gallery.appendChild(div);
        });
    });

    answerSheetForm.addEventListener("submit", async e => {
        e.preventDefault();
        const files = Array.from(fileInput.files);
        if (!files.length) return updateStatus("studentUploadStatus", "Please select files", false);

        const formData = new FormData();
        files.forEach(f => formData.append("files", f));
        formData.append("exam_name", document.getElementById("examDropdown").value);
        formData.append("subject", document.getElementById("subjectDropdown").value);
        formData.append("roll_number", document.getElementById("rollNumber").value);
        formData.append("notes", document.getElementById("notes").value);
        formData.append("answer_sheet_type", document.getElementById("answerSheetTypeDropdown").value);
        formData.append("student", localStorage.getItem("userEmail") || "Unknown");

        const res = await fetch("http://127.0.0.1:5000/api/upload-answer", { method: "POST", body: formData });
        const data = await res.json();
        updateStatus("studentUploadStatus", res.ok ? data.message : data.error, res.ok);

        if (res.ok) {
            await loadStudentResults();
            showSection("results");
        }
    });
}

// ========== LOAD STUDENT RESULTS ==========
async function loadStudentResults() {
    const grid = document.querySelector(".results-grid");
    if (!grid) return;
    const studentEmail = localStorage.getItem("userEmail");
    grid.innerHTML = "<p>⏳ Loading submissions...</p>";

    try {
        const res = await fetch(`http://127.0.0.1:5000/api/get-student-submissions?student=${studentEmail}`);
        const data = await res.json();

        if (res.ok && data.submissions.length) {
            grid.innerHTML = data.submissions.map(sub => `
                <div class="exam-result-card card">
                    <h4>${sub.exam_name} - ${sub.subject}</h4>
                    <p><b>Roll No:</b> ${sub.roll_number}</p>
                    <p><b>Type:</b> ${sub.answer_sheet_type}</p>
                    <p><b>Uploaded:</b> ${new Date(sub.timestamp).toLocaleString()}</p>
                    <div>${(sub.file_urls || []).map(u => `<a href="${u}" target="_blank">${u.endsWith(".pdf") ? "📄 PDF" : "🖼️ Image"}</a>`).join("<br>")}</div>
                </div>
            `).join("");
        } else grid.innerHTML = "<p>❌ No submissions found.</p>";
    } catch {
        grid.innerHTML = "<p>⚠️ Failed to load submissions.</p>";
    }
}

// ========== TEACHER VIEW ==========
async function loadStudentSubmissions() {
    const container = document.getElementById("studentSubmissions");
    if (!container) return;
    container.innerHTML = "<p>⏳ Loading submissions...</p>";

    try {
        const res = await fetch("http://127.0.0.1:5000/api/student-submissions");
        const data = await res.json();

        if (res.ok && data.submissions.length) {
            container.innerHTML = data.submissions.map(sub => `
                <div class="submission-card">
                    <h4>${sub.exam_name} - ${sub.subject}</h4>
                    <p><b>Roll:</b> ${sub.roll_number}</p>
                    <div>${(sub.file_urls || []).map(u => `<a href="${u}" target="_blank">${u.endsWith(".pdf") ? "📄" : "🖼️"}</a>`).join(" ")}</div>
                </div>
            `).join("");
        } else container.innerHTML = "<p>No student submissions yet.</p>";
    } catch {
        container.innerHTML = "<p>⚠️ Failed to load submissions.</p>";
    }
}

// INIT
document.addEventListener("DOMContentLoaded", () => {
    if (document.getElementById("studentSubmissions")) loadStudentSubmissions();
    if (document.querySelector(".results-grid")) loadStudentResults();
});
