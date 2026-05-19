
/* ═══════════════════════════════════════════════════════════════
   ASK_tech — Frontend Logic (AIScript.js)
   ═══════════════════════════════════════════════════════════════ */

const ASKtech = {
    API_BASE: '',
    getToken() { return localStorage.getItem('asktech_token'); },
    setToken(t) { localStorage.setItem('asktech_token', t); },
    getUser() { try { return JSON.parse(localStorage.getItem('asktech_user')); } catch { return null; } },
    setUser(u) { localStorage.setItem('asktech_user', JSON.stringify(u)); },
    clearAuth() { localStorage.removeItem('asktech_token'); localStorage.removeItem('asktech_user'); },
    isLoggedIn() { return !!this.getToken(); },

    async api(endpoint, options = {}) {
        const headers = { 'Content-Type': 'application/json', ...options.headers };
        const token = this.getToken();
        if (token) headers['Authorization'] = 'Bearer ' + token;
        try {
            const resp = await fetch(this.API_BASE + endpoint, { ...options, headers });
            const data = options.raw ? resp : await resp.json();
            if (!resp.ok) throw { status: resp.status, ...(typeof data === 'object' ? data : { error: 'خطأ في الخادم' }) };
            return data;
        } catch (err) {
            if (err.status === 401) { this.clearAuth(); window.location.href = '/login'; }
            throw err;
        }
    },

    toast(msg, type = 'info') {
        let container = document.querySelector('.toast-container');
        if (!container) { container = document.createElement('div'); container.className = 'toast-container'; document.body.appendChild(container); }
        const t = document.createElement('div');
        t.className = 'toast ' + type;
        t.textContent = msg;
        container.appendChild(t);
        setTimeout(() => t.remove(), 3000);
    },

    showLoading() {
        if (document.querySelector('.loading-overlay')) return;
        const el = document.createElement('div');
        el.className = 'loading-overlay';
        el.innerHTML = '<div class="loading-spinner"></div>';
        document.body.appendChild(el);
    },
    hideLoading() { document.querySelectorAll('.loading-overlay').forEach(e => e.remove()); },

    requireAuth() {
        if (!this.isLoggedIn()) { window.location.href = '/login'; return false; }
        return true;
    },

    /* ═══════ AUTH MODULE ═══════ */
    Auth: {
        init() {
            const loginForm = document.getElementById('loginForm');
            const registerForm = document.getElementById('registerForm');
            const loginTab = document.getElementById('loginTab');
            const registerTab = document.getElementById('registerTab');
            if (!loginForm) return;

            loginTab.addEventListener('click', () => {
                loginTab.classList.add('active'); registerTab.classList.remove('active');
                loginForm.classList.add('active'); registerForm.classList.remove('active');
                document.getElementById('tabIndicator').classList.remove('register');
            });
            registerTab.addEventListener('click', () => {
                registerTab.classList.add('active'); loginTab.classList.remove('active');
                registerForm.classList.add('active'); loginForm.classList.remove('active');
                document.getElementById('tabIndicator').classList.add('register');
            });

            loginForm.addEventListener('submit', async (e) => {
                e.preventDefault();
                const btn = document.getElementById('loginBtn');
                btn.querySelector('.btn-text').style.display = 'none';
                btn.querySelector('.btn-loader').style.display = 'inline';
                try {
                    const data = await ASKtech.api('/api/auth/login', {
                        method: 'POST',
                        body: JSON.stringify({
                            email: document.getElementById('loginEmail').value,
                            password: document.getElementById('loginPassword').value
                        })
                    });
                    ASKtech.setToken(data.token);
                    ASKtech.setUser(data.user);
                    ASKtech.toast('تم تسجيل الدخول بنجاح!', 'success');
                    setTimeout(() => window.location.href = '/dashboard', 500);
                } catch (err) {
                    ASKtech.showAuthMessage(err.error || 'خطأ في تسجيل الدخول', 'error');
                } finally {
                    btn.querySelector('.btn-text').style.display = 'inline';
                    btn.querySelector('.btn-loader').style.display = 'none';
                }
            });

            registerForm.addEventListener('submit', async (e) => {
                e.preventDefault();
                const btn = document.getElementById('regBtn');
                btn.querySelector('.btn-text').style.display = 'none';
                btn.querySelector('.btn-loader').style.display = 'inline';
                try {
                    const data = await ASKtech.api('/api/auth/register', {
                        method: 'POST',
                        body: JSON.stringify({
                            name: document.getElementById('regName').value,
                            email: document.getElementById('regEmail').value,
                            password: document.getElementById('regPassword').value
                        })
                    });
                    ASKtech.setToken(data.token);
                    ASKtech.setUser(data.user);
                    ASKtech.toast('تم إنشاء الحساب بنجاح!', 'success');
                    setTimeout(() => window.location.href = '/dashboard', 500);
                } catch (err) {
                    ASKtech.showAuthMessage(err.error || 'خطأ في إنشاء الحساب', 'error');
                } finally {
                    btn.querySelector('.btn-text').style.display = 'inline';
                    btn.querySelector('.btn-loader').style.display = 'none';
                }
            });

            document.querySelectorAll('.password-toggle').forEach(btn => {
                btn.addEventListener('click', () => {
                    const input = document.getElementById(btn.dataset.target);
                    const isPassword = input.type === 'password';
                    input.type = isPassword ? 'text' : 'password';
                    btn.querySelector('i').className = isPassword ? 'fas fa-eye-slash' : 'fas fa-eye';
                });
            });
        }
    },

    showAuthMessage(msg, type) {
        const el = document.getElementById('authMessage');
        if (el) { el.textContent = msg; el.className = 'auth-message ' + type; setTimeout(() => { el.textContent = ''; el.className = 'auth-message'; }, 4000); }
    },

    /* ═══════ DASHBOARD MODULE ═══════ */
    Dashboard: {
        init() {
            if (!ASKtech.requireAuth()) return;
            const user = ASKtech.getUser();
            const nameEl = document.getElementById('userName');
            if (nameEl && user) nameEl.textContent = user.name;
            const dateEl = document.getElementById('currentDate');
            if (dateEl) dateEl.textContent = new Date().toLocaleDateString('ar-EG', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' });
            this.loadStats();
        },
        async loadStats() {
            try {
                const data = await ASKtech.api('/api/dashboard/stats');
                document.getElementById('kpiAssessments').textContent = data.stats.assessments;
                document.getElementById('kpiInterviews').textContent = data.stats.interviews;
                document.getElementById('kpiResumes').textContent = data.stats.resumes;
                document.getElementById('kpiCareers').textContent = data.stats.careers;
                const feed = document.getElementById('activityFeed');
                if (data.activities && data.activities.length > 0) {
                    feed.innerHTML = data.activities.map(a => `
                        <div class="activity-item">
                            <div class="activity-icon ${a.type}"><i class="fas fa-${a.type === 'skills' ? 'chart-line' : a.type === 'interview' ? 'microphone-lines' : a.type === 'resume' ? 'file-lines' : a.type === 'career' ? 'route' : 'user'}"></i></div>
                            <div class="activity-info"><span>${a.title}</span><span class="activity-date">${a.date}</span></div>
                        </div>`).join('');
                }
            } catch (err) { console.error(err); }
        }
    },

    /* ═══════ SKILLS MODULE ═══════ */
    Skills: {
        selectedSkills: [],
        init() {
            if (!ASKtech.requireAuth()) return;
            document.querySelectorAll('.skill-chip').forEach(chip => {
                chip.addEventListener('click', () => {
                    chip.classList.toggle('selected');
                    const skill = chip.dataset.skill;
                    if (chip.classList.contains('selected')) {
                        if (!this.selectedSkills.includes(skill)) this.selectedSkills.push(skill);
                    } else {
                        this.selectedSkills = this.selectedSkills.filter(s => s !== skill);
                    }
                    this.renderSelected();
                });
            });
            const addBtn = document.getElementById('addCustomSkill');
            const customInput = document.getElementById('customSkill');
            if (addBtn) {
                const addCustom = () => {
                    const val = customInput.value.trim();
                    if (val && !this.selectedSkills.includes(val)) {
                        this.selectedSkills.push(val);
                        this.renderSelected();
                        customInput.value = '';
                    }
                };
                addBtn.addEventListener('click', addCustom);
                customInput.addEventListener('keypress', e => { if (e.key === 'Enter') { e.preventDefault(); addCustom(); } });
            }
            const assessBtn = document.getElementById('assessBtn');
            if (assessBtn) assessBtn.addEventListener('click', () => this.assess());
            const resetBtn = document.getElementById('resetSkills');
            if (resetBtn) resetBtn.addEventListener('click', () => this.reset());
        },
        renderSelected() {
            const container = document.getElementById('selectedChips');
            const wrapper = document.getElementById('selectedSkills');
            if (!container) return;
            container.innerHTML = this.selectedSkills.map(s => `<span class="selected-chip">${s} <span class="remove-chip" data-skill="${s}">&times;</span></span>`).join('');
            wrapper.className = this.selectedSkills.length ? 'selected-skills has-skills' : 'selected-skills';
            container.querySelectorAll('.remove-chip').forEach(btn => {
                btn.addEventListener('click', () => {
                    this.selectedSkills = this.selectedSkills.filter(s => s !== btn.dataset.skill);
                    document.querySelectorAll('.skill-chip').forEach(c => { if (c.dataset.skill === btn.dataset.skill) c.classList.remove('selected'); });
                    this.renderSelected();
                });
            });
        },
        async assess() {
            if (this.selectedSkills.length === 0) { ASKtech.toast('يرجى اختيار مهارة واحدة على الأقل', 'error'); return; }
            const targetRole = document.getElementById('targetRole').value.trim() || 'مطور برمجيات';
            ASKtech.showLoading();
            try {
                const result = await ASKtech.api('/api/skills/assess', {
                    method: 'POST',
                    body: JSON.stringify({ skills: this.selectedSkills, target_role: targetRole })
                });
                this.showResults(result);
            } catch (err) {
                ASKtech.toast(err.error || 'حدث خطأ', 'error');
            } finally { ASKtech.hideLoading(); }
        },
        showResults(data) {
            document.getElementById('skillsInputSection').style.display = 'none';
            const results = document.getElementById('skillsResults');
            results.style.display = 'block';
            // Score
            const score = data.score || 0;
            document.getElementById('scoreText').textContent = score + '%';
            const fill = document.getElementById('scoreFill');
            if (fill) { const offset = 339.3 - (339.3 * score / 100); fill.style.strokeDashoffset = offset; }
            // Analysis
            document.getElementById('analysisText').textContent = data.analysis || '';
            // Strengths
            const sList = document.getElementById('strengthsList');
            sList.innerHTML = (data.strengths || []).map(s => `<li>${s}</li>`).join('');
            // Gaps
            const gList = document.getElementById('gapsList');
            gList.innerHTML = (data.gaps || []).map(g => {
                const imp = g.importance === 'عالية' ? 'high' : g.importance === 'متوسطة' ? 'medium' : 'low';
                return `<div class="gap-item"><h4>${g.skill}</h4><span class="gap-importance ${imp}">${g.importance}</span><p>${g.recommendation}</p></div>`;
            }).join('');
            // Roadmap
            const rList = document.getElementById('roadmapList');
            rList.innerHTML = (data.roadmap || []).map(r => `<div class="roadmap-item">${r}</div>`).join('');
        },
        reset() {
            document.getElementById('skillsInputSection').style.display = 'block';
            document.getElementById('skillsResults').style.display = 'none';
            this.selectedSkills = [];
            document.querySelectorAll('.skill-chip').forEach(c => c.classList.remove('selected'));
            this.renderSelected();
        }
    },

    /* ═══════ INTERVIEW MODULE ═══════ */
    Interview: {
        sessionId: null,
        questionCount: 0,
        init() {
            if (!ASKtech.requireAuth()) return;
            const startBtn = document.getElementById('startInterviewBtn');
            if (startBtn) startBtn.addEventListener('click', () => this.start());
            const sendBtn = document.getElementById('sendAnswerBtn');
            if (sendBtn) sendBtn.addEventListener('click', () => this.sendAnswer());
            const endBtn = document.getElementById('endInterviewBtn');
            if (endBtn) endBtn.addEventListener('click', () => this.end());
            const closeModal = document.getElementById('closeSummaryModal');
            if (closeModal) closeModal.addEventListener('click', () => { document.getElementById('interviewSummaryModal').style.display = 'none'; });
            const chatInput = document.getElementById('chatInput');
            if (chatInput) chatInput.addEventListener('keydown', e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); this.sendAnswer(); } });
        },
        async start() {
            const role = document.getElementById('interviewRole').value.trim();
            const field = document.getElementById('interviewField').value;
            if (!role) { ASKtech.toast('يرجى إدخال الوظيفة المستهدفة', 'error'); return; }
            ASKtech.showLoading();
            try {
                const data = await ASKtech.api('/api/interview/start', {
                    method: 'POST', body: JSON.stringify({ role, field })
                });
                this.sessionId = data.session_id;
                this.questionCount = 1;
                document.getElementById('interviewSetup').style.display = 'none';
                document.getElementById('interviewChat').style.display = 'block';
                document.getElementById('questionCounter').textContent = 'السؤال ' + this.questionCount;
                this.addMessage(data.question, 'ai');
            } catch (err) { ASKtech.toast(err.error || 'خطأ في بدء المقابلة', 'error'); }
            finally { ASKtech.hideLoading(); }
        },
        addMessage(text, type, feedback, score) {
            const container = document.getElementById('chatMessages');
            const msg = document.createElement('div');
            msg.className = 'chat-message ' + type;
            let html = text;
            if (feedback) html += '<div class="feedback">' + feedback + '</div>';
            if (score) html += '<span class="score-badge">' + score + '/10</span>';
            msg.innerHTML = html;
            container.appendChild(msg);
            container.scrollTop = container.scrollHeight;
        },
        showTyping() {
            const container = document.getElementById('chatMessages');
            const el = document.createElement('div');
            el.className = 'typing-indicator';
            el.id = 'typingIndicator';
            el.innerHTML = '<span></span><span></span><span></span>';
            container.appendChild(el);
            container.scrollTop = container.scrollHeight;
        },
        hideTyping() { const el = document.getElementById('typingIndicator'); if (el) el.remove(); },
        async sendAnswer() {
            const input = document.getElementById('chatInput');
            const answer = input.value.trim();
            if (!answer || !this.sessionId) return;
            input.value = '';
            this.addMessage(answer, 'user');
            this.showTyping();
            document.getElementById('sendAnswerBtn').disabled = true;
            try {
                const data = await ASKtech.api('/api/interview/respond', {
                    method: 'POST', body: JSON.stringify({ session_id: this.sessionId, answer })
                });
                this.hideTyping();
                this.questionCount++;
                document.getElementById('questionCounter').textContent = 'السؤال ' + this.questionCount;
                this.addMessage(data.question, 'ai', data.feedback, data.score);
            } catch (err) {
                this.hideTyping();
                ASKtech.toast(err.error || 'خطأ', 'error');
            } finally { document.getElementById('sendAnswerBtn').disabled = false; }
        },
        async end() {
            if (!this.sessionId) return;
            ASKtech.showLoading();
            try {
                const data = await ASKtech.api('/api/interview/end', {
                    method: 'POST', body: JSON.stringify({ session_id: this.sessionId })
                });
                this.sessionId = null;
                // Show summary modal
                const modal = document.getElementById('interviewSummaryModal');
                modal.style.display = 'flex';
                document.getElementById('summaryScoreText').textContent = data.overall_score;
                const fill = document.getElementById('summaryScoreFill');
                if (fill) { const offset = 339.3 - (339.3 * data.overall_score / 10); fill.style.strokeDashoffset = offset; }
                document.getElementById('summaryText').textContent = data.summary || '';
                document.getElementById('summaryStrengths').innerHTML = (data.strengths || []).map(s => '<li>' + s + '</li>').join('');
                document.getElementById('summaryImprovements').innerHTML = (data.improvements || []).map(s => '<li>' + s + '</li>').join('');
                document.getElementById('summaryTips').innerHTML = (data.tips || []).map(s => '<li>' + s + '</li>').join('');
            } catch (err) { ASKtech.toast(err.error || 'خطأ', 'error'); }
            finally { ASKtech.hideLoading(); }
        }
    },

    /* ═══════ RESUME MODULE ═══════ */
    Resume: {
        currentStep: 1,
        init() {
            if (!ASKtech.requireAuth()) return;
            const addExp = document.getElementById('addExperience');
            if (addExp) addExp.addEventListener('click', () => this.addEntry('experience'));
            const addEdu = document.getElementById('addEducation');
            if (addEdu) addEdu.addEventListener('click', () => this.addEntry('education'));
            const genBtn = document.getElementById('generateResumeBtn');
            if (genBtn) genBtn.addEventListener('click', () => this.generate());
            const expBtn = document.getElementById('exportPdfBtn');
            if (expBtn) expBtn.addEventListener('click', () => this.exportPdf());
            // Live preview on input
            document.querySelectorAll('.resume-input').forEach(inp => {
                inp.addEventListener('input', () => this.updatePreview());
            });
        },
        goToStep(n) {
            this.currentStep = n;
            document.querySelectorAll('.resume-step').forEach(s => s.classList.remove('active'));
            const step = document.getElementById('resumeStep' + n);
            if (step) step.classList.add('active');
            document.querySelectorAll('.step-ind').forEach(ind => {
                const s = parseInt(ind.dataset.step);
                ind.classList.remove('active', 'completed');
                if (s === n) ind.classList.add('active');
                else if (s < n) ind.classList.add('completed');
            });
            this.updatePreview();
        },
        addEntry(type) {
            const container = document.getElementById(type + 'Entries');
            if (!container) return;
            const template = container.querySelector('.' + type + '-entry');
            if (!template) return;
            const clone = template.cloneNode(true);
            clone.querySelectorAll('input, textarea').forEach(inp => { inp.value = ''; inp.addEventListener('input', () => this.updatePreview()); });
            container.appendChild(clone);
        },
        getData() {
            const data = {
                name: document.getElementById('resName')?.value || '',
                email: document.getElementById('resEmail')?.value || '',
                phone: document.getElementById('resPhone')?.value || '',
                title: document.getElementById('resTitle')?.value || '',
                summary: document.getElementById('resSummary')?.value || '',
                experience: [], education: [],
                skills_tech: document.getElementById('resSkillsTech')?.value || '',
                skills_soft: document.getElementById('resSkillsSoft')?.value || '',
                languages: document.getElementById('resLanguages')?.value || ''
            };
            document.querySelectorAll('.experience-entry').forEach(entry => {
                const t = entry.querySelector('.exp-title')?.value;
                if (t) data.experience.push({
                    title: t, company: entry.querySelector('.exp-company')?.value || '',
                    from: entry.querySelector('.exp-from')?.value || '', to: entry.querySelector('.exp-to')?.value || '',
                    description: entry.querySelector('.exp-desc')?.value || ''
                });
            });
            document.querySelectorAll('.education-entry').forEach(entry => {
                const d = entry.querySelector('.edu-degree')?.value;
                if (d) data.education.push({
                    degree: d, school: entry.querySelector('.edu-school')?.value || '',
                    year: entry.querySelector('.edu-year')?.value || ''
                });
            });
            return data;
        },
        updatePreview() {
            const d = this.getData();
            const preview = document.getElementById('resumePreview');
            if (!d.name && !d.email) {
                preview.innerHTML = '<div class="preview-placeholder"><i class="fas fa-file-lines"></i><p>ابدأ بملء البيانات لرؤية المعاينة</p></div>';
                return;
            }
            let html = '<div class="preview-name">' + (d.name || '') + '</div>';
            html += '<div class="preview-contact">' + [d.title, d.email, d.phone].filter(Boolean).join(' | ') + '</div>';
            if (d.summary) html += '<div class="preview-section"><h2>الملخص المهني</h2><p>' + d.summary + '</p></div>';
            if (d.experience.length) {
                html += '<div class="preview-section"><h2>الخبرات العملية</h2>';
                d.experience.forEach(e => { html += '<h3>' + e.title + ' - ' + e.company + '</h3><p style="color:#999;font-size:.75rem">' + e.from + ' - ' + e.to + '</p><p>' + e.description + '</p>'; });
                html += '</div>';
            }
            if (d.education.length) {
                html += '<div class="preview-section"><h2>التعليم</h2>';
                d.education.forEach(e => { html += '<h3>' + e.degree + '</h3><p>' + e.school + ' - ' + e.year + '</p>'; });
                html += '</div>';
            }
            if (d.skills_tech) html += '<div class="preview-section"><h2>المهارات التقنية</h2><p>' + d.skills_tech + '</p></div>';
            if (d.skills_soft) html += '<div class="preview-section"><h2>المهارات الشخصية</h2><p>' + d.skills_soft + '</p></div>';
            if (d.languages) html += '<div class="preview-section"><h2>اللغات</h2><p>' + d.languages + '</p></div>';
            preview.innerHTML = html;
        },
        async generate() {
            const data = this.getData();
            if (!data.name) { ASKtech.toast('يرجى إدخال الاسم على الأقل', 'error'); return; }
            ASKtech.showLoading();
            try {
                const result = await ASKtech.api('/api/resume/generate', { method: 'POST', body: JSON.stringify(data) });
                if (result.enhancements?.professional_summary) {
                    document.getElementById('resSummary').value = result.enhancements.professional_summary;
                }
                this.updatePreview();
                document.getElementById('exportPdfBtn').style.display = 'inline-flex';
                ASKtech.toast('تم تحسين السيرة الذاتية بنجاح!', 'success');
            } catch (err) { ASKtech.toast(err.error || 'خطأ', 'error'); }
            finally { ASKtech.hideLoading(); }
        },
        async exportPdf() {
            const data = this.getData();
            data.summary = document.getElementById('resSummary')?.value || '';
            ASKtech.showLoading();
            try {
                const resp = await fetch('/api/resume/export-pdf', {
                    method: 'POST', headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + ASKtech.getToken() },
                    body: JSON.stringify(data)
                });
                if (!resp.ok) throw new Error('Export failed');
                const blob = await resp.blob();
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a'); a.href = url; a.download = 'resume.pdf'; a.click();
                URL.revokeObjectURL(url);
                ASKtech.toast('تم تصدير السيرة الذاتية!', 'success');
            } catch (err) { ASKtech.toast('خطأ في التصدير', 'error'); }
            finally { ASKtech.hideLoading(); }
        }
    },

    /* ═══════ CAREER MODULE ═══════ */
    Career: {
        init() {
            if (!ASKtech.requireAuth()) return;
            const recBtn = document.getElementById('careerRecommendBtn');
            if (recBtn) recBtn.addEventListener('click', () => this.recommend());
            const resetBtn = document.getElementById('resetCareer');
            if (resetBtn) resetBtn.addEventListener('click', () => {
                document.getElementById('careerInput').style.display = 'block';
                document.getElementById('careerResults').style.display = 'none';
            });
        },
        async recommend() {
            const skills = document.getElementById('careerSkills').value.trim().split(/[,،]+/).map(s => s.trim()).filter(Boolean);
            const interests = document.getElementById('careerInterests').value.trim();
            const experience = parseInt(document.getElementById('careerExperience').value) || 0;
            if (skills.length === 0) { ASKtech.toast('يرجى إدخال مهاراتك', 'error'); return; }
            ASKtech.showLoading();
            try {
                const result = await ASKtech.api('/api/career/recommend', {
                    method: 'POST', body: JSON.stringify({ skills, interests, experience_years: experience })
                });
                this.showResults(result);
            } catch (err) { ASKtech.toast(err.error || 'خطأ', 'error'); }
            finally { ASKtech.hideLoading(); }
        },
        showResults(data) {
            document.getElementById('careerInput').style.display = 'none';
            document.getElementById('careerResults').style.display = 'block';
            document.getElementById('careerAdvice').textContent = data.general_advice || '';
            const grid = document.getElementById('careerPathsGrid');
            grid.innerHTML = (data.paths || []).map(p => `
                <div class="career-card">
                    <div class="career-card-header">
                        <h3>${p.title}</h3>
                        <span class="match-badge">${p.match_percentage}%</span>
                    </div>
                    <p>${p.description}</p>
                    <div class="career-detail"><i class="fas fa-money-bill-wave"></i> ${p.salary_range || 'غير محدد'}</div>
                    <div class="career-detail"><i class="fas fa-chart-line"></i> ${p.growth_outlook || 'غير محدد'}</div>
                    <div class="career-skills">${(p.required_skills || []).map(s => '<span>' + s + '</span>').join('')}</div>
                </div>
            `).join('');
        }
    }
};

/* ═══════ GLOBAL INIT ═══════ */
document.addEventListener('DOMContentLoaded', () => {
    const path = window.location.pathname;

    // Navbar scroll effect
    window.addEventListener('scroll', () => {
        const nav = document.getElementById('navbar');
        if (nav) nav.classList.toggle('scrolled', window.scrollY > 50);
    });

    // Mobile menu
    const mobileBtn = document.getElementById('mobileMenuBtn');
    if (mobileBtn) {
        mobileBtn.addEventListener('click', () => {
            document.getElementById('navLinks').classList.toggle('open');
        });
    }

    // Logout
    const logoutBtn = document.getElementById('logoutBtn');
    if (logoutBtn) {
        logoutBtn.addEventListener('click', async () => {
            try { await ASKtech.api('/api/auth/logout', { method: 'POST' }); } catch (e) {}
            ASKtech.clearAuth();
            window.location.href = '/login';
        });
    }

    // Hero counter animation
    document.querySelectorAll('.hero-stat-number').forEach(el => {
        const target = parseInt(el.dataset.count) || 0;
        let current = 0;
        const increment = target / 60;
        const timer = setInterval(() => {
            current += increment;
            if (current >= target) { current = target; clearInterval(timer); }
            el.textContent = Math.floor(current).toLocaleString('ar-EG');
        }, 30);
    });

    // Page-specific init
    if (path === '/login') ASKtech.Auth.init();
    else if (path === '/dashboard') ASKtech.Dashboard.init();
    else if (path === '/skills') ASKtech.Skills.init();
    else if (path === '/interview') ASKtech.Interview.init();
    else if (path === '/resume') ASKtech.Resume.init();
    else if (path === '/career') ASKtech.Career.init();
});
