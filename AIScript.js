
/* ═══════════════════════════════════════════════════════════════
   Talent Metric — Frontend Logic (AIScript.js)
   ═══════════════════════════════════════════════════════════════ */

const TalentMetric = {
    API_BASE: '',
    getToken() { return localStorage.getItem('talentmetric_token'); },
    setToken(t) { localStorage.setItem('talentmetric_token', t); },
    getUser() { try { return JSON.parse(localStorage.getItem('talentmetric_user')); } catch { return null; } },
    setUser(u) { localStorage.setItem('talentmetric_user', JSON.stringify(u)); },
    clearAuth() { localStorage.removeItem('talentmetric_token'); localStorage.removeItem('talentmetric_user'); },
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

    async loadSiteConfig() {
        try {
            const config = await this.api('/api/site/config');
            if (config) {
                // Update brand name
                if (config.app_name) {
                    document.querySelectorAll('.logo-text').forEach(el => el.textContent = config.app_name);
                    document.title = document.title.replace('Talent Metric', config.app_name);
                }
                
                // Update Interview Fields dropdown if it exists
                const fieldSelect = document.getElementById('interviewField');
                if (fieldSelect && config.interview_fields && config.interview_fields.length > 0) {
                    fieldSelect.innerHTML = config.interview_fields.map(f => `<option value="${f}">${f}</option>`).join('');
                }
                
                // Update default target role inputs
                if (config.default_target_role) {
                    const roleInp = document.getElementById('interviewRole');
                    if (roleInp && !roleInp.value) roleInp.placeholder = `مثال: ${config.default_target_role}`;
                    const targetInp = document.getElementById('targetRole'); // skills
                    if (targetInp && !targetInp.value) targetInp.placeholder = `مثال: ${config.default_target_role}`;
                }
            }
        } catch(e) { console.error('Failed to load site config:', e); }
    },

    /* ═══════ AUTH MODULE ═══════ */
    Auth: {
        adminMode: false,
        init() {
            const loginForm = document.getElementById('loginForm');
            const registerForm = document.getElementById('registerForm');
            const loginTab = document.getElementById('loginTab');
            const registerTab = document.getElementById('registerTab');
            const adminToggle = document.getElementById('adminToggleBtn');
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
                if (this.adminMode) this.toggleAdmin();
            });

            if (adminToggle) {
                adminToggle.addEventListener('click', () => this.toggleAdmin());
            }

            loginForm.addEventListener('submit', async (e) => {
                e.preventDefault();
                const btn = document.getElementById('loginBtn');
                btn.querySelector('.btn-text').style.display = 'none';
                btn.querySelector('.btn-loader').style.display = 'inline';
                try {
                    if (this.adminMode) {
                        const resp = await fetch('/api/admin/login', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ password: document.getElementById('loginPassword').value })
                        });
                        const data = await resp.json();
                        if (!resp.ok) throw new Error(data.error || 'Wrong password');
                        sessionStorage.setItem('talentmetric_admin_token', data.token);
                        window.location.href = '/admin';
                    } else {
                        const data = await TalentMetric.api('/api/auth/login', {
                            method: 'POST',
                            body: JSON.stringify({
                                email: document.getElementById('loginEmail').value,
                                password: document.getElementById('loginPassword').value
                            })
                        });
                        TalentMetric.setToken(data.token);
                        TalentMetric.setUser(data.user);
                        TalentMetric.toast('تم تسجيل الدخول بنجاح!', 'success');
                        setTimeout(() => window.location.href = '/dashboard', 500);
                    }
                } catch (err) {
                    TalentMetric.showAuthMessage(err.error || err.message || 'خطأ في تسجيل الدخول', 'error');
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
                    const data = await TalentMetric.api('/api/auth/register', {
                        method: 'POST',
                        body: JSON.stringify({
                            name: document.getElementById('regName').value,
                            email: document.getElementById('regEmail').value,
                            password: document.getElementById('regPassword').value
                        })
                    });
                    TalentMetric.setToken(data.token);
                    TalentMetric.setUser(data.user);
                    TalentMetric.toast('تم إنشاء الحساب بنجاح!', 'success');
                    setTimeout(() => window.location.href = '/dashboard', 500);
                } catch (err) {
                    TalentMetric.showAuthMessage(err.error || 'خطأ في إنشاء الحساب', 'error');
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
        },
        toggleAdmin() {
            this.adminMode = !this.adminMode;
            const emailGroup = document.getElementById('loginEmailGroup');
            const toggleBtn = document.getElementById('adminToggleBtn');
            const toggleText = document.getElementById('adminToggleText');
            const btnText = document.querySelector('#loginBtn .btn-text');
            const emailInput = document.getElementById('loginEmail');
            if (this.adminMode) {
                emailGroup.style.display = 'none';
                if (emailInput) { emailInput.required = false; emailInput.disabled = true; }
                document.getElementById('registerTab').style.display = 'none';
                document.getElementById('loginPassword').placeholder = 'أدخل كلمة مرور المشرف';
                document.getElementById('loginPassword').required = true;
                toggleText.textContent = 'تسجيل الدخول كمستخدم';
                btnText.innerHTML = '<i class="fas fa-shield-halved"></i> دخول المشرف';
                
                // Force login tab active without triggering event
                document.getElementById('loginTab').classList.add('active');
                document.getElementById('registerTab').classList.remove('active');
                document.getElementById('loginForm').classList.add('active');
                document.getElementById('registerForm').classList.remove('active');
                document.getElementById('tabIndicator').classList.remove('register');
            } else {
                emailGroup.style.display = 'block';
                if (emailInput) { emailInput.required = true; emailInput.disabled = false; }
                document.getElementById('registerTab').style.display = '';
                document.getElementById('loginPassword').placeholder = '••••••••';
                toggleText.textContent = 'دخول المشرف';
                btnText.textContent = 'تسجيل الدخول';
            }
        }
    },

    showAuthMessage(msg, type) {
        const el = document.getElementById('authMessage');
        if (el) { el.textContent = msg; el.className = 'auth-message ' + type; setTimeout(() => { el.textContent = ''; el.className = 'auth-message'; }, 4000); }
    },

    /* ═══════ DASHBOARD MODULE ═══════ */
    Dashboard: {
        init() {
            if (!TalentMetric.requireAuth()) return;
            const user = TalentMetric.getUser();
            const nameEl = document.getElementById('userName');
            if (nameEl && user) nameEl.textContent = user.name;
            const dateEl = document.getElementById('currentDate');
            if (dateEl) dateEl.textContent = new Date().toLocaleDateString('ar-EG', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' });
            this.loadStats();
        },
        async loadStats() {
            try {
                const data = await TalentMetric.api('/api/dashboard/stats');
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
            if (!TalentMetric.requireAuth()) return;
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
            if (this.selectedSkills.length === 0) { TalentMetric.toast('يرجى اختيار مهارة واحدة على الأقل', 'error'); return; }
            const targetRole = document.getElementById('targetRole').value.trim();
            TalentMetric.showLoading();
            try {
                const result = await TalentMetric.api('/api/skills/assess', {
                    method: 'POST',
                    body: JSON.stringify({ skills: this.selectedSkills, target_role: targetRole })
                });
                this.showResults(result);
            } catch (err) {
                TalentMetric.toast(err.error || 'حدث خطأ', 'error');
            } finally { TalentMetric.hideLoading(); }
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
        sessionId: null, questionCount: 0, mode: 'chat',
        stream: null, recognition: null, synth: window.speechSynthesis, ttsEnabled: true,
        timerInt: null, seconds: 0,
        
        init() {
            if (!TalentMetric.requireAuth()) return;
            
            // Mode Selectors
            const modeBtns = document.querySelectorAll('.mode-card');
            modeBtns.forEach(btn => {
                btn.addEventListener('click', () => {
                    modeBtns.forEach(b => b.classList.remove('active'));
                    btn.classList.add('active');
                    this.mode = btn.dataset.mode;
                    if(this.mode === 'video') this.setupPreview();
                    else this.stopPreview();
                });
            });

            // Chat Mode
            document.getElementById('startInterviewBtn')?.addEventListener('click', () => this.start());
            document.getElementById('sendAnswerBtn')?.addEventListener('click', () => this.sendAnswer('chat'));
            document.getElementById('endInterviewBtn')?.addEventListener('click', () => this.end());
            document.getElementById('chatInput')?.addEventListener('keydown', e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); this.sendAnswer('chat'); } });
            
            // Chat TTS/STT
            document.getElementById('toggleTtsBtn')?.addEventListener('click', (e) => {
                this.ttsEnabled = !this.ttsEnabled;
                e.currentTarget.classList.toggle('muted', !this.ttsEnabled);
                e.currentTarget.querySelector('i').className = this.ttsEnabled ? 'fas fa-volume-high' : 'fas fa-volume-xmark';
                if(!this.ttsEnabled) this.synth.cancel();
            });
            document.getElementById('chatMicBtn')?.addEventListener('click', () => this.toggleSTT('chatInput', 'chatMicBtn'));

            // Video Mode
            document.getElementById('videoSendBtn')?.addEventListener('click', () => this.sendAnswer('video'));
            document.getElementById('endVideoInterviewBtn')?.addEventListener('click', () => this.end());
            document.getElementById('endVideoCallBtn')?.addEventListener('click', () => this.end());
            document.getElementById('videoTranscriptInput')?.addEventListener('keydown', e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); this.sendAnswer('video'); } });
            
            document.getElementById('toggleMicBtn')?.addEventListener('click', (e) => {
                if(!this.stream) return;
                const audioTrack = this.stream.getAudioTracks()[0];
                if(audioTrack) {
                    audioTrack.enabled = !audioTrack.enabled;
                    e.currentTarget.classList.toggle('muted', !audioTrack.enabled);
                    e.currentTarget.querySelector('i').className = audioTrack.enabled ? 'fas fa-microphone' : 'fas fa-microphone-slash';
                }
            });
            document.getElementById('toggleCamBtn')?.addEventListener('click', (e) => {
                if(!this.stream) return;
                const videoTrack = this.stream.getVideoTracks()[0];
                if(videoTrack) {
                    videoTrack.enabled = !videoTrack.enabled;
                    e.currentTarget.classList.toggle('muted', !videoTrack.enabled);
                    e.currentTarget.querySelector('i').className = videoTrack.enabled ? 'fas fa-video' : 'fas fa-video-slash';
                }
            });
            document.getElementById('toggleAiVoiceBtn')?.addEventListener('click', (e) => {
                this.ttsEnabled = !this.ttsEnabled;
                e.currentTarget.classList.toggle('active', this.ttsEnabled);
                e.currentTarget.classList.toggle('muted', !this.ttsEnabled);
                e.currentTarget.querySelector('i').className = this.ttsEnabled ? 'fas fa-volume-high' : 'fas fa-volume-xmark';
                if(!this.ttsEnabled) this.synth.cancel();
            });
            document.getElementById('sttMicBtn')?.addEventListener('click', () => this.toggleSTT('videoTranscriptInput', 'sttMicBtn', 'sttWave'));

            document.getElementById('closeSummaryModal')?.addEventListener('click', () => { document.getElementById('interviewSummaryModal').style.display = 'none'; });

            this.initSpeech();
        },
        initSpeech() {
            const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
            if(SpeechRecognition) {
                this.recognition = new SpeechRecognition();
                this.recognition.lang = 'ar-SA';
                this.recognition.continuous = false;
                this.recognition.interimResults = true;
            }
        },
        toggleSTT(inputId, btnId, waveId = null) {
            if(!this.recognition) { TalentMetric.toast('متصفحك لا يدعم إدخال الصوت', 'error'); return; }
            const btn = document.getElementById(btnId);
            const input = document.getElementById(inputId);
            const wave = waveId ? document.getElementById(waveId) : null;
            
            if(btn.classList.contains('listening')) {
                this.recognition.stop();
                btn.classList.remove('listening');
                if(wave) wave.classList.remove('listening');
            } else {
                btn.classList.add('listening');
                if(wave) wave.classList.add('listening');
                
                this.recognition.onresult = (e) => {
                    let text = '';
                    for (let i = 0; i < e.results.length; ++i) text += e.results[i][0].transcript;
                    input.value = text;
                };
                this.recognition.onend = () => {
                    btn.classList.remove('listening');
                    if(wave) wave.classList.remove('listening');
                };
                this.recognition.start();
            }
        },
        speak(text) {
            if(!this.ttsEnabled || !this.synth) return;
            this.synth.cancel();
            const utterance = new SpeechSynthesisUtterance(text);
            utterance.lang = 'ar-SA';
            
            const avatar = document.getElementById('aiSpeakingIndicator');
            utterance.onstart = () => { if(avatar) avatar.classList.add('active'); };
            utterance.onend = () => { if(avatar) avatar.classList.remove('active'); };
            utterance.onerror = () => { if(avatar) avatar.classList.remove('active'); };
            
            this.synth.speak(utterance);
        },
        async setupPreview() {
            const prev = document.getElementById('videoPreviewSetup');
            if(prev) prev.style.display = 'block';
            try {
                const stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: true });
                const video = document.getElementById('previewVideo');
                if(video) video.srcObject = stream;
                document.getElementById('camStatusText').textContent = 'الكاميرا والميكروفون تعملان';
                document.getElementById('camDot').classList.add('active');
            } catch(e) {
                document.getElementById('camStatusText').textContent = 'تعذر الوصول للكاميرا';
                document.getElementById('camDot').classList.remove('active');
                TalentMetric.toast('يرجى السماح بالوصول للكاميرا', 'error');
            }
        },
        stopPreview() {
            const video = document.getElementById('previewVideo');
            if(video && video.srcObject) {
                video.srcObject.getTracks().forEach(t => t.stop());
                video.srcObject = null;
            }
            const prev = document.getElementById('videoPreviewSetup');
            if(prev) prev.style.display = 'none';
        },
        async start() {
            const role = document.getElementById('interviewRole').value.trim();
            const field = document.getElementById('interviewField').value;
            
            TalentMetric.showLoading();
            
            // Move preview stream to main interview video if video mode
            if(this.mode === 'video') {
                const prevVideo = document.getElementById('previewVideo');
                if(prevVideo && prevVideo.srcObject) {
                    this.stream = prevVideo.srcObject;
                    prevVideo.srcObject = null;
                    document.getElementById('interviewVideoFeed').srcObject = this.stream;
                } else {
                    try {
                        this.stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: true });
                        document.getElementById('interviewVideoFeed').srcObject = this.stream;
                    } catch(e) {}
                }
            } else {
                this.stopPreview();
            }

            try {
                const data = await TalentMetric.api('/api/interview/start', {
                    method: 'POST', body: JSON.stringify({ role, field, mode: this.mode })
                });
                this.sessionId = data.session_id;
                this.questionCount = 1;
                
                document.getElementById('interviewSetup').style.display = 'none';
                
                if(this.mode === 'video') {
                    document.getElementById('interviewVideo').style.display = 'block';
                    document.getElementById('videoQuestionCounter').textContent = 'السؤال ' + this.questionCount;
                    this.startTimer();
                } else {
                    document.getElementById('interviewChat').style.display = 'block';
                    document.getElementById('questionCounter').textContent = 'السؤال ' + this.questionCount;
                }
                
                this.addMessage(data.question, 'ai');
                this.speak(data.question);
            } catch (err) { TalentMetric.toast(err.error || 'خطأ في بدء المقابلة', 'error'); }
            finally { TalentMetric.hideLoading(); }
        },
        startTimer() {
            this.seconds = 0;
            if(this.timerInt) clearInterval(this.timerInt);
            this.timerInt = setInterval(() => {
                this.seconds++;
                const m = Math.floor(this.seconds / 60).toString().padStart(2, '0');
                const s = (this.seconds % 60).toString().padStart(2, '0');
                document.getElementById('interviewTimer').textContent = `${m}:${s}`;
            }, 1000);
        },
        addMessage(text, type, feedback, score) {
            const container = this.mode === 'video' ? document.getElementById('videoMessages') : document.getElementById('chatMessages');
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
            const container = this.mode === 'video' ? document.getElementById('videoMessages') : document.getElementById('chatMessages');
            const el = document.createElement('div');
            el.className = 'typing-indicator';
            el.id = 'typingIndicator';
            el.innerHTML = '<span></span><span></span><span></span>';
            container.appendChild(el);
            container.scrollTop = container.scrollHeight;
            if(this.mode === 'video') {
                const av = document.getElementById('aiAvatarEl');
                if(av) av.style.opacity = '0.5';
            }
        },
        hideTyping() { 
            const el = document.getElementById('typingIndicator'); if (el) el.remove(); 
            if(this.mode === 'video') {
                const av = document.getElementById('aiAvatarEl');
                if(av) av.style.opacity = '1';
            }
        },
        async sendAnswer(modeStr) {
            const inputId = modeStr === 'video' ? 'videoTranscriptInput' : 'chatInput';
            const btnId = modeStr === 'video' ? 'videoSendBtn' : 'sendAnswerBtn';
            
            const input = document.getElementById(inputId);
            const answer = input.value.trim();
            if (!answer || !this.sessionId) return;
            
            if(this.synth) this.synth.cancel(); // Stop speaking previous question
            
            input.value = '';
            this.addMessage(answer, 'user');
            this.showTyping();
            document.getElementById(btnId).disabled = true;
            
            try {
                const data = await TalentMetric.api('/api/interview/respond', {
                    method: 'POST', body: JSON.stringify({ session_id: this.sessionId, answer })
                });
                this.hideTyping();
                this.questionCount++;
                if(modeStr === 'video') document.getElementById('videoQuestionCounter').textContent = 'السؤال ' + this.questionCount;
                else document.getElementById('questionCounter').textContent = 'السؤال ' + this.questionCount;
                
                this.addMessage(data.question, 'ai', data.feedback, data.score);
                this.speak(data.question);
            } catch (err) {
                this.hideTyping();
                TalentMetric.toast(err.error || 'خطأ', 'error');
            } finally { document.getElementById(btnId).disabled = false; }
        },
        async end() {
            if (!this.sessionId) return;
            if(this.timerInt) clearInterval(this.timerInt);
            if(this.synth) this.synth.cancel();
            if(this.recognition) this.recognition.stop();
            if(this.stream) {
                this.stream.getTracks().forEach(t => t.stop());
                this.stream = null;
            }
            
            TalentMetric.showLoading();
            try {
                const data = await TalentMetric.api('/api/interview/end', {
                    method: 'POST', body: JSON.stringify({ session_id: this.sessionId })
                });
                this.sessionId = null;
                const modal = document.getElementById('interviewSummaryModal');
                if(modal) modal.style.display = 'flex';
                
                if(document.getElementById('summaryScoreText')) {
                    document.getElementById('summaryScoreText').textContent = data.overall_score;
                    const fill = document.getElementById('summaryScoreFill');
                    if (fill) { const offset = 339.3 - (339.3 * data.overall_score / 10); fill.style.strokeDashoffset = offset; }
                    document.getElementById('summaryText').textContent = data.summary || '';
                    document.getElementById('summaryStrengths').innerHTML = (data.strengths || []).map(s => '<li>' + s + '</li>').join('');
                    document.getElementById('summaryImprovements').innerHTML = (data.improvements || []).map(s => '<li>' + s + '</li>').join('');
                    document.getElementById('summaryTips').innerHTML = (data.tips || []).map(s => '<li>' + s + '</li>').join('');
                }
            } catch (err) { TalentMetric.toast(err.error || 'خطأ', 'error'); }
            finally { TalentMetric.hideLoading(); }
        }
    },

    /* ═══════ RESUME MODULE ═══════ */
    Resume: {
        currentStep: 1,
        init() {
            if (!TalentMetric.requireAuth()) return;
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
            if (!data.name) { TalentMetric.toast('يرجى إدخال الاسم على الأقل', 'error'); return; }
            TalentMetric.showLoading();
            try {
                const result = await TalentMetric.api('/api/resume/generate', { method: 'POST', body: JSON.stringify(data) });
                if (result.enhancements?.professional_summary) {
                    document.getElementById('resSummary').value = result.enhancements.professional_summary;
                }
                this.updatePreview();
                document.getElementById('exportPdfBtn').style.display = 'inline-flex';
                TalentMetric.toast('تم تحسين السيرة الذاتية بنجاح!', 'success');
            } catch (err) { TalentMetric.toast(err.error || 'خطأ', 'error'); }
            finally { TalentMetric.hideLoading(); }
        },
        async exportPdf() {
            const data = this.getData();
            data.summary = document.getElementById('resSummary')?.value || '';
            TalentMetric.showLoading();
            try {
                const resp = await fetch('/api/resume/export-pdf', {
                    method: 'POST', headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + TalentMetric.getToken() },
                    body: JSON.stringify(data)
                });
                if (!resp.ok) throw new Error('Export failed');
                const blob = await resp.blob();
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a'); a.href = url; a.download = 'resume.pdf'; a.click();
                URL.revokeObjectURL(url);
                TalentMetric.toast('تم تصدير السيرة الذاتية!', 'success');
            } catch (err) { TalentMetric.toast('خطأ في التصدير', 'error'); }
            finally { TalentMetric.hideLoading(); }
        }
    },

    /* ═══════ CAREER MODULE ═══════ */
    Career: {
        init() {
            if (!TalentMetric.requireAuth()) return;
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
            if (skills.length === 0) { TalentMetric.toast('يرجى إدخال مهاراتك', 'error'); return; }
            TalentMetric.showLoading();
            try {
                const result = await TalentMetric.api('/api/career/recommend', {
                    method: 'POST', body: JSON.stringify({ skills, interests, experience_years: experience })
                });
                this.showResults(result);
            } catch (err) { TalentMetric.toast(err.error || 'خطأ', 'error'); }
            finally { TalentMetric.hideLoading(); }
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
    },


        /* ═══════ ADMIN MODULE ═══════ */
    Admin: {
        token: null,
        init() {
            const loginScreen = document.getElementById('adminLogin');
            if (!loginScreen) return;

            this.token = sessionStorage.getItem('talentmetric_admin_token');
            if (!this.token) {
                window.location.href = '/login';
                return;
            }

            document.getElementById('adminSaveBtn').addEventListener('click', () => this.saveSettings());
            document.getElementById('adminRefreshBtn')?.addEventListener('click', () => this.refreshStatus());

            document.querySelectorAll('.admin-test-btn').forEach(btn => {
                btn.addEventListener('click', () => this.testProvider(btn.dataset.provider));
            });

            const logoutBtn = document.getElementById('adminLogoutBtn');
            if (logoutBtn) logoutBtn.addEventListener('click', () => {
                this.token = null;
                sessionStorage.removeItem('talentmetric_admin_token');
                window.location.href = '/login';
            });
            
            document.getElementById('fetchOllamaModels')?.addEventListener('click', () => this.fetchLocalModels('ollama'));
            document.getElementById('fetchLMStudioModels')?.addEventListener('click', () => this.fetchLocalModels('lmstudio'));

            // HF + generic model chips — set provider default model input
            document.addEventListener('click', e => {
                const chip = e.target.closest('.model-chip');
                if (!chip) return;
                const provider = chip.dataset.provider;
                const model = chip.dataset.model;
                if (provider) {
                    const inp = document.querySelector(`.admin-provider-input[data-provider="${provider}"][data-field="model"]`);
                    if (inp) inp.value = model;
                }
            });

            this.showPanel();
            this.loadSettings();
        },
        showPanel() {
            document.getElementById('adminLogin').style.display = 'none';
            document.getElementById('adminPanel').style.display = 'block';
            document.getElementById('adminLogoutBtn').style.display = 'inline-flex';
        },
        async fetchLocalModels(provider) {
            try {
                const resp = await fetch('/api/admin/local-models', { headers: { 'Authorization': 'Bearer ' + this.token } });
                const data = await resp.json();
                const list = data[provider] || [];
                const container = document.getElementById(provider + 'ModelsList');
                const chips = document.getElementById(provider + 'ModelsChips');
                if (container && chips) {
                    if (list.length === 0) {
                        chips.innerHTML = '<span style="color:var(--text-muted);font-size:.8rem">No models found. Is the server running?</span>';
                    } else {
                        chips.innerHTML = list.map(m => `<button class="model-chip" data-model="${m.name}" data-provider="${provider}">${m.name}</button>`).join('');
                    }
                    container.classList.add('visible');
                }
            } catch(e) { console.error(e); }
        },
        async loadSettings() {
            try {
                const resp = await fetch('/api/admin/settings', {
                    headers: { 'Authorization': 'Bearer ' + this.token }
                });
                if (resp.status === 401) { sessionStorage.removeItem('talentmetric_admin_token'); window.location.href = '/login'; return; }
                const data = await resp.json();
                this.renderSettings(data);
                this.refreshStatus();
            } catch (err) { console.error(err); }
        },
        renderSettings(data) {
            document.getElementById('adminActiveProvider').value = data.active_provider || 'openrouter';
            document.getElementById('adminFallbackOrder').value = (data.fallback_order || []).join(', ');
            document.getElementById('adminAppName').value = data.site?.app_name || '';
            document.getElementById('adminDefaultRole').value = data.site?.default_target_role || '';
            document.getElementById('adminInterviewFields').value = (data.site?.interview_fields || []).join('\n');

            const features = ['default', 'skills', 'chat_interview', 'video_interview', 'resume', 'career'];
            const featureLabels = {
                'default': 'Default (General)', 'skills': 'Skills Assessment', 
                'chat_interview': 'Chat Interview', 'video_interview': 'Video Interview', 
                'resume': 'Resume Review', 'career': 'Career Path'
            };
            const providers = ['openrouter', 'openai', 'huggingface', 'ollama', 'lmstudio'];
            
            // Build Main Routing Table
            const tbody = document.getElementById('adminRoutingRows');
            if(tbody) {
                tbody.innerHTML = features.map(f => {
                    const curOverride = data.routing_overrides?.[f] || {};
                    const options = `<option value="">-- Active Provider --</option>` + providers.map(p => `<option value="${p}" ${curOverride.provider===p?'selected':''}>${p}</option>`).join('');
                    return `
                        <tr>
                            <td><span class="feature-label">${featureLabels[f]}</span></td>
                            <td><select class="routing-provider-select" data-feature="${f}">${options}</select></td>
                            <td><input type="text" class="routing-model-input" list="commonModelsList" data-feature="${f}" value="${curOverride.model||''}" placeholder="Inherit default"></td>
                        </tr>
                    `;
                }).join('');
            }
            
            if(!document.getElementById('commonModelsList')) {
                const dl = document.createElement('datalist');
                dl.id = 'commonModelsList';
                dl.innerHTML = `
                    <option value="gpt-4o-mini">
                    <option value="gpt-4o">
                    <option value="claude-3-5-sonnet">
                    <option value="openai/gpt-4o-mini">
                    <option value="anthropic/claude-3-haiku">
                    <option value="llama3">
                    <option value="llama-3-8b-instruct">
                `;
                document.body.appendChild(dl);
            }

            // Provider fields
            providers.forEach(p => {
                const prov = data.providers?.[p] || {};
                const keyInput = document.querySelector(`.admin-provider-key[data-provider="${p}"]`);
                if (keyInput) keyInput.value = prov.api_key || '';
                const inputs = document.querySelectorAll(`.admin-provider-input[data-provider="${p}"]`);
                inputs.forEach(inp => {
                    const field = inp.dataset.field;
                    inp.value = prov[field] || '';
                });
                const check = document.querySelector(`.admin-provider-check[data-provider="${p}"]`);
                if (check) check.checked = prov.enabled !== false;
                

            });

            const sel = document.getElementById('adminActiveProvider');
            const current = sel.value;
            sel.innerHTML = providers.map(p => `<option value="${p}">${p.charAt(0).toUpperCase() + p.slice(1)}</option>`).join('');
            sel.value = current || data.active_provider || 'openrouter';
        },
        collectSettings() {
            const features = ['default', 'skills', 'chat_interview', 'video_interview', 'resume', 'career'];
            const providersList = ['openrouter', 'openai', 'huggingface', 'ollama', 'lmstudio'];
            const providers = {};
            
            providersList.forEach(p => {
                const keyInput = document.querySelector(`.admin-provider-key[data-provider="${p}"]`);
                const check = document.querySelector(`.admin-provider-check[data-provider="${p}"]`);
                const inputs = document.querySelectorAll(`.admin-provider-input[data-provider="${p}"]`);
                const prov = { enabled: check ? check.checked : true, models: {} };
                if (keyInput) prov.api_key = keyInput.value;
                inputs.forEach(inp => { prov[inp.dataset.field] = inp.value; });
                
                features.forEach(f => {
                    const inp = document.querySelector(`.admin-model-input[data-provider="${p}"][data-feature="${f}"]`);
                    if (inp && inp.value) prov.models[f] = inp.value;
                });
                providers[p] = prov;
            });
            
            const routing_overrides = {};
            features.forEach(f => {
                const pSel = document.querySelector(`.routing-provider-select[data-feature="${f}"]`);
                const mInp = document.querySelector(`.routing-model-input[data-feature="${f}"]`);
                if(pSel && (pSel.value || mInp.value)) {
                    routing_overrides[f] = {};
                    if(pSel.value) routing_overrides[f].provider = pSel.value;
                    if(mInp.value) routing_overrides[f].model = mInp.value;
                }
            });

            return {
                active_provider: document.getElementById('adminActiveProvider').value,
                fallback_order: document.getElementById('adminFallbackOrder').value.split(/[,\s]+/).filter(Boolean),
                providers,
                routing_overrides,
                site: {
                    app_name: document.getElementById('adminAppName').value,
                    default_target_role: document.getElementById('adminDefaultRole').value,
                    interview_fields: document.getElementById('adminInterviewFields').value.split('\n').map(s => s.trim()).filter(Boolean),
                    max_activity_items: 20
                }
            };
        },
        async saveSettings() {
            const msg = document.getElementById('adminSaveMessage');
            msg.style.display = 'none';
            try {
                const data = this.collectSettings();
                const resp = await fetch('/api/admin/settings', {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + this.token },
                    body: JSON.stringify(data)
                });
                if (resp.status === 401) { sessionStorage.removeItem('talentmetric_admin_token'); window.location.href = '/login'; return; }
                const result = await resp.json();
                msg.textContent = result.ok ? '\u2713 Settings saved successfully!' : 'Error saving';
                msg.style.display = 'block';
                msg.style.color = result.ok ? 'var(--success)' : 'var(--danger)';
                setTimeout(() => { msg.style.display = 'none'; }, 3000);
            } catch (err) { console.error(err); }
        },
        async testProvider(name) {
            const el = document.getElementById('test' + name.charAt(0).toUpperCase() + name.slice(1));
            if (el) { el.textContent = 'Testing...'; el.style.color = 'var(--text-muted)'; }
            try {
                const resp = await fetch('/api/admin/test', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + this.token },
                    body: JSON.stringify({ provider: name })
                });
                if (resp.status === 401) { sessionStorage.removeItem('talentmetric_admin_token'); window.location.href = '/login'; return; }
                const data = await resp.json();
                if (el) {
                    if (data.ok) {
                        el.innerHTML = '\u2713 OK: ' + (data.response || '').substring(0, 80);
                        el.style.color = 'var(--success)';
                    } else {
                        el.textContent = '\u2717 ' + (data.error || 'Failed');
                        el.style.color = 'var(--danger)';
                    }
                }
            } catch (err) {
                if (el) { el.textContent = '\u2717 ' + err.message; el.style.color = 'var(--danger)'; }
            }
        },
        async refreshStatus() {
            try {
                const resp = await fetch('/api/admin/local-status', { headers: { 'Authorization': 'Bearer ' + this.token } });
                if (resp.status === 401) { sessionStorage.removeItem('talentmetric_admin_token'); window.location.href = '/login'; return; }
                const localData = await resp.json();

                Object.keys(localData).forEach(p => {
                    const dot = document.querySelector(`.admin-status-dot[data-provider="${p}"]`);
                    if (dot) dot.className = 'admin-status-dot ' + (localData[p].reachable ? 'online' : 'offline');
                });

                const cloudProviders = ['openrouter', 'openai', 'huggingface'];
                for (const p of cloudProviders) {
                    const dot = document.querySelector(`.admin-status-dot[data-provider="${p}"]`);
                    if (!dot) continue;
                    const keyInput = document.querySelector(`.admin-provider-key[data-provider="${p}"]`);
                    if (keyInput && keyInput.value) {
                        dot.className = 'admin-status-dot unknown'; dot.title = 'Has key, not tested';
                    } else {
                        dot.className = 'admin-status-dot offline'; dot.title = 'No API key';
                    }
                }
            } catch (err) { console.error(err); }
        }
    }
};

/* ═══════ GLOBAL INIT ═══════ */
document.addEventListener('DOMContentLoaded', () => {
    const path = window.location.pathname;

    // Load site configuration globally
    TalentMetric.loadSiteConfig();

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
            try { await TalentMetric.api('/api/auth/logout', { method: 'POST' }); } catch (e) {}
            TalentMetric.clearAuth();
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
    if (path === '/login') TalentMetric.Auth.init();
    else if (path === '/dashboard') TalentMetric.Dashboard.init();
    else if (path === '/skills') TalentMetric.Skills.init();
    else if (path === '/interview') TalentMetric.Interview.init();
    else if (path === '/resume') TalentMetric.Resume.init();
    else if (path === '/career') TalentMetric.Career.init();
    else if (path === '/admin') TalentMetric.Admin.init();
});
