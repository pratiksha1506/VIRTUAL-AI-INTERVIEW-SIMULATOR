/*
 * storage.js — client-side data layer standing in for the Flask+SQLite
 * backend. Mirrors the real schema (users, interviews, responses/results)
 * so the data model matches the full Python version. Uses localStorage,
 * which is appropriate here since these are real files running in your
 * own browser (not a sandboxed preview).
 *
 * SECURITY NOTE: passwords are stored in plain text for demo simplicity.
 * The real backend (Phase 2 of the Python project) uses proper salted
 * password hashing — never do this in a real deployment.
 */
const DB_KEY = "ai_interview_sim_db_v1";
const SESSION_KEY = "ai_interview_sim_session_v1";

function _loadDb() {
  const raw = localStorage.getItem(DB_KEY);
  if (raw) return JSON.parse(raw);
  const fresh = { users: [], interviews: [], nextUserId: 1, nextInterviewId: 1 };
  localStorage.setItem(DB_KEY, JSON.stringify(fresh));
  return fresh;
}
function _saveDb(db) { localStorage.setItem(DB_KEY, JSON.stringify(db)); }

const Storage = {
  // ---------- Users ----------
  getUsers() { return _loadDb().users; },

  findUserByEmail(email) {
    return _loadDb().users.find(u => u.email.toLowerCase() === email.toLowerCase());
  },

  registerJobSeeker(name, email, password) {
    const db = _loadDb();
    if (db.users.find(u => u.email.toLowerCase() === email.toLowerCase())) {
      return { error: "An account with this email already exists." };
    }
    const user = { id: db.nextUserId++, name, email: email.toLowerCase(), password, role: "job_seeker", createdAt: new Date().toISOString() };
    db.users.push(user);
    _saveDb(db);
    return { user };
  },

  ensureDemoAdmin() {
    const db = _loadDb();
    if (!db.users.find(u => u.role === "admin")) {
      db.users.push({ id: db.nextUserId++, name: "Administrator", email: "admin@organization.com", role: "admin", createdAt: new Date().toISOString() });
      _saveDb(db);
    }
  },

  login(email, password, expectedRole) {
    const user = this.findUserByEmail(email);
    if (!user || user.password !== password || user.role !== expectedRole) {
      return { error: "Invalid email or password." };
    }
    sessionStorage.setItem(SESSION_KEY, String(user.id));
    return { user };
  },

  logout() { sessionStorage.removeItem(SESSION_KEY); },

  currentUser() {
    const id = sessionStorage.getItem(SESSION_KEY);
    if (!id) return null;
    return _loadDb().users.find(u => u.id === Number(id)) || null;
  },

  requireAuth(role) {
    const user = this.currentUser();
    if (!user) { window.location.href = "index.html"; return null; }
    if (role && user.role !== role) { window.location.href = "index.html"; return null; }
    return user;
  },

  // ---------- Interviews ----------
  createInterview(data) {
    const db = _loadDb();
    const interview = Object.assign({
      id: db.nextInterviewId++, status: "in_progress", createdAt: new Date().toISOString(),
      responses: [], report: null,
    }, data);
    db.interviews.push(interview);
    _saveDb(db);
    return interview;
  },

  getInterview(id) { return _loadDb().interviews.find(i => i.id === Number(id)); },

  updateInterview(id, patch) {
    const db = _loadDb();
    const idx = db.interviews.findIndex(i => i.id === Number(id));
    if (idx === -1) return null;
    db.interviews[idx] = Object.assign({}, db.interviews[idx], patch);
    _saveDb(db);
    return db.interviews[idx];
  },

  addResponse(interviewId, response) {
    const db = _loadDb();
    const interview = db.interviews.find(i => i.id === Number(interviewId));
    if (!interview) return null;
    interview.responses.push(response);
    _saveDb(db);
    return interview;
  },

  interviewsForCandidate(candidateId, status) {
    return _loadDb().interviews.filter(i => i.candidateId === candidateId && (!status || i.status === status));
  },

  allInterviews() { return _loadDb().interviews; },

  cancelInterview(id) { return this.updateInterview(id, { status: "cancelled" }); },
};
