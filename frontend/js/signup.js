var API = (location.protocol === 'file:' || !location.origin || location.origin === 'null')
  ? 'http://localhost:5000' : location.origin;
var HOME_URL = 'index.html'; // where to go after a successful sign-up

function $(id) { return document.getElementById(id); }
function isValidEmail(v) { return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v); }

function setFieldError(field, message) {
  var input = $(field), err = $(field + '-error');
  input.classList.toggle('invalid', !!message);
  err.hidden = !message;
  err.textContent = message || '';
}

function setBanner(message, type) {
  var b = $('banner');
  b.hidden = !message;
  b.textContent = message || '';
  b.className = 'banner ' + (type || 'error');
}

function clearErrors() {
  ['name', 'email', 'password', 'confirm'].forEach(function (f) { setFieldError(f, ''); });
  setBanner('');
}

function setLoading(loading) {
  $('submit-btn').disabled = loading;
  $('spinner').hidden = !loading;
  $('submit-label').textContent = loading ? 'Creating account…' : 'Create Account';
}

// POST { name, email, password } -> 200/201 { user }, 409 = email already registered
function register(name, email, password) {
  var controller = new AbortController();
  var t = setTimeout(function () { controller.abort(); }, 2500);
  return fetch(API + '/api/signup', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name: name, email: email, password: password }),
    signal: controller.signal
  }).finally(function () { clearTimeout(t); });
}

$('signup-form').addEventListener('submit', function (e) {
  e.preventDefault();
  clearErrors();

  var name = $('name').value.trim();
  var email = $('email').value.trim();
  var password = $('password').value;
  var confirm = $('confirm').value;
  var bad = false;
  function fail(f, m) { setFieldError(f, m); bad = true; }

  if (!name) fail('name', 'Full name is required.');
  if (!email) fail('email', 'Email address is required.');
  else if (!isValidEmail(email)) fail('email', 'Enter a valid email address.');
  if (!password) fail('password', 'Password is required.');
  else if (password.length < 6) fail('password', 'Password must be at least 6 characters.');
  if (!confirm) fail('confirm', 'Please confirm your password.');
  else if (confirm !== password) fail('confirm', 'Passwords do not match.');
  if (bad) return;

  // Seeds the Profile page (app.js reads this key).
  function saveProfile() {
    try {
      localStorage.setItem('denguesenseqc_profile_v1', JSON.stringify({
        name: name, title: 'Public User', email: email, organization: '',
        location: 'Quezon City, Philippines', username: email.split('@')[0],
        password: '', avatar: null, access: 'Public User',
        memberSince: new Date().toISOString()
      }));
    } catch (err) {}
  }

  function goHome() { setTimeout(function () { location.href = HOME_URL; }, 900); }

  function demoFallback() {
    try {
      localStorage.setItem('denguesense_current_user', JSON.stringify({ email: email, role: 'user' }));
    } catch (err) {}
    saveProfile();
    setBanner('Sign-up service isn\u2019t connected yet — continuing in demo mode.', 'info');
    goHome();
  }

  setLoading(true);
  register(name, email, password)
    .then(function (res) {
      if (res.ok) {
        return res.json().then(function (data) {
          if (data && data.user) localStorage.setItem('denguesense_current_user', JSON.stringify(data.user));
          saveProfile();
          setBanner('Account created. Taking you to the dashboard…', 'success');
          goHome();
        }).catch(function () { saveProfile(); goHome(); });
      }
      if (res.status === 409) setFieldError('email', 'An account with this email already exists.');
      else if (res.status === 400 || res.status === 422) setBanner('Please check your details and try again.', 'error');
      else demoFallback();
    })
    .catch(demoFallback)
    .finally(function () { setLoading(false); });
});