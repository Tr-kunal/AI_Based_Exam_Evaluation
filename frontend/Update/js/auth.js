// ============================
// 🔹 ROLE SELECTION HANDLER
// ============================
function selectRole(card) {
    // Remove "selected" from all role cards
    document.querySelectorAll(".role-card").forEach(c => c.classList.remove("selected"));
    // Add "selected" to the clicked one
    card.classList.add("selected");
}

// Attach role selection globally
window.selectRole = selectRole;

// Helper: show toast or alert
function showAlert(message, success = true) {
    const color = success ? "#28a745" : "#dc3545";
    const toast = document.createElement("div");
    toast.textContent = message;
    toast.style.position = "fixed";
    toast.style.bottom = "25px";
    toast.style.left = "50%";
    toast.style.transform = "translateX(-50%)";
    toast.style.background = color;
    toast.style.color = "white";
    toast.style.padding = "10px 20px";
    toast.style.borderRadius = "6px";
    toast.style.zIndex = "1000";
    toast.style.boxShadow = "0 4px 8px rgba(0,0,0,0.2)";
    document.body.appendChild(toast);
    setTimeout(() => toast.remove(), 2500);
}

// ============================
// 🔹 SIGNUP FORM HANDLER
// ============================
const signupForm = document.getElementById("signupForm");

if (signupForm) {
    signupForm.addEventListener("submit", async function (event) {
        event.preventDefault();

        const fullname = document.getElementById("fullname").value.trim();
        const email = document.getElementById("email").value.trim();
        const password = document.getElementById("password").value.trim();
        const selectedRole = document.querySelector(".role-card.selected")?.dataset.role;

        if (!fullname || !email || !password || !selectedRole) {
            showAlert("⚠️ Please fill all fields and select a role.", false);
            return;
        }

        try {
            const response = await fetch("http://127.0.0.1:5000/api/signup", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ fullname, email, password, role: selectedRole }),
            });

            const data = await response.json();

            if (response.ok) {
                showAlert(data.message || "✅ Signup successful!");
                // Store user data for future use
                localStorage.setItem("userEmail", email);
                localStorage.setItem("userRole", selectedRole);
                // Redirect to login page after delay
                setTimeout(() => (window.location.href = "login.html"), 1000);
            } else {
                showAlert(data.error || "❌ Signup failed.", false);
            }
        } catch (error) {
            console.error("Error:", error);
            showAlert("🚫 Server not reachable. Please ensure Flask is running on port 5000.", false);
        }
    });
}

// ============================
// 🔹 LOGIN FORM HANDLER
// ============================
const loginForm = document.getElementById("loginForm");

if (loginForm) {
    loginForm.addEventListener("submit", async function (event) {
        event.preventDefault();

        const email = document.getElementById("email").value.trim();
        const password = document.getElementById("password").value.trim();
        const selectedRole = document.querySelector(".role-card.selected")?.dataset.role;

        if (!email || !password || !selectedRole) {
            showAlert("⚠️ Please fill in all fields and select your role.", false);
            return;
        }

        try {
            const response = await fetch("http://127.0.0.1:5000/api/login", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ email, password, role: selectedRole }),
            });

            const data = await response.json();

            if (response.ok) {
                showAlert(data.message || "✅ Login successful!");
                // Store login info locally
                localStorage.setItem("userEmail", email);
                localStorage.setItem("userRole", selectedRole);

                if (data.redirect) {
                    setTimeout(() => (window.location.href = data.redirect), 1000);
                } else {
                    showAlert("⚠️ No redirect URL provided by server.", false);
                }
            } else {
                showAlert(data.error || "❌ Login failed. Please check your credentials.", false);
            }
        } catch (error) {
            console.error("Error:", error);
            showAlert("🚫 Server not reachable. Please ensure Flask is running on port 5000.", false);
        }
    });
}
