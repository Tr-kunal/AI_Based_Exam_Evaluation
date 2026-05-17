// Backend API base URL
const API_BASE = 'http://127.0.0.1:8000';

// ==================== LOGIN ====================
document.getElementById('loginForm')?.addEventListener('submit', async function(e) {
  e.preventDefault();

  const email = document.getElementById('email').value.trim();
  const password = document.getElementById('password').value;
  const role = document.querySelector('input[name="role"]:checked').value;

  try {
    const res = await fetch(`${API_BASE}/api/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password, role })
    });

    const data = await res.json();

    if (!res.ok) {
      alert(data.detail || data.error || 'Login failed');
      return;
    }

    // Store user info
    localStorage.setItem('userRole', role);
    localStorage.setItem('userEmail', email);
    if (data.user) {
      localStorage.setItem('userName', data.user.fullname || '');
    }

    alert(data.message || 'Login successful!');

    // Redirect based on role
    if (role === 'teacher') {
      window.location.href = 'teacher-dashboard.html';
    } else {
      window.location.href = 'student-dashboard.html';
    }
  } catch (err) {
    console.error('Login error:', err);
    alert('Could not connect to server. Make sure the backend is running.');
  }
});

// ==================== SIGNUP ====================
document.getElementById('signupForm')?.addEventListener('submit', async function(e) {
  e.preventDefault();

  const fullname = document.getElementById('fullname').value.trim();
  const email = document.getElementById('email').value.trim();
  const password = document.getElementById('password').value;
  const role = document.querySelector('input[name="role"]:checked').value;

  try {
    const res = await fetch(`${API_BASE}/api/signup`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ fullname, email, password, role })
    });

    const data = await res.json();

    if (!res.ok) {
      alert(data.detail || data.error || 'Signup failed');
      return;
    }

    // Store user info
    localStorage.setItem('userRole', role);
    localStorage.setItem('userEmail', email);
    localStorage.setItem('userName', fullname);

    alert(data.message || 'Signup successful!');

    // Redirect to login
    window.location.href = 'login.html';
  } catch (err) {
    console.error('Signup error:', err);
    alert('Could not connect to server. Make sure the backend is running.');
  }
});
