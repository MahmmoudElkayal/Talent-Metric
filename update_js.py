import re

with open("AIScript.js", "r", encoding="utf-8") as f:
    content = f.read()

# 1. Replace Interview Module
new_interview = """    /* ═══════ INTERVIEW MODULE ═══════ */
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
            if (!role) { TalentMetric.toast('يرجى إدخال الوظيفة المستهدفة', 'error'); return; }
            
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
    },"""

# 2. Replace Admin Module
new_admin = """    /* ═══════ ADMIN MODULE ═══════ */
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
            document.getElementById('adminRefreshBtn').addEventListener('click', () => this.refreshStatus());

            document.querySelectorAll('.admin-test-btn').forEach(btn => {
                btn.addEventListener('click', () => this.testProvider(btn.dataset.provider));
            });

            document.querySelectorAll('.admin-tab').forEach(tab => {
                tab.addEventListener('click', () => {
                    document.querySelectorAll('.admin-tab').forEach(t => t.classList.remove('active'));
                    document.querySelectorAll('.admin-tab-content').forEach(c => c.classList.remove('active'));
                    tab.classList.add('active');
                    document.getElementById(tab.dataset.tab).classList.add('active');
                });
            });

            const logoutBtn = document.getElementById('adminLogoutBtn');
            if (logoutBtn) logoutBtn.addEventListener('click', () => {
                this.token = null;
                sessionStorage.removeItem('talentmetric_admin_token');
                window.location.href = '/login';
            });
            
            document.getElementById('fetchOllamaModels')?.addEventListener('click', () => this.fetchLocalModels('ollama'));
            document.getElementById('fetchLMStudioModels')?.addEventListener('click', () => this.fetchLocalModels('lmstudio'));
            
            // HF model chips
            document.querySelectorAll('.hf-model-chip').forEach(chip => {
                chip.addEventListener('click', () => {
                    const inp = document.querySelector('.admin-provider-input[data-provider="huggingface"][data-field="model"]');
                    if(inp) inp.value = chip.dataset.model;
                });
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
                if(container && chips) {
                    if(list.length === 0) {
                        chips.innerHTML = '<span style="color:var(--text-muted);font-size:.8rem">No models found.</span>';
                    } else {
                        chips.innerHTML = list.map(m => `<button class="local-model-chip" data-model="${m.name}">${m.name}</button>`).join('');
                        chips.querySelectorAll('.local-model-chip').forEach(c => {
                            c.addEventListener('click', () => {
                                const inp = document.querySelector(`.admin-provider-input[data-provider="${provider}"][data-field="model"]`);
                                if(inp) inp.value = c.dataset.model;
                            });
                        });
                    }
                    container.style.display = 'block';
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
            document.getElementById('adminInterviewFields').value = (data.site?.interview_fields || []).join('\\n');

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
                            <td><input type="text" class="routing-model-input" data-feature="${f}" value="${curOverride.model||''}" placeholder="Inherit default"></td>
                        </tr>
                    `;
                }).join('');
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
                
                // Feature Model Overrides per provider grid
                const grid = document.getElementById(`featureModels${p.charAt(0).toUpperCase() + p.slice(1)}`);
                if(grid) {
                    grid.innerHTML = features.map(f => `
                        <div class="feature-model-row">
                            <label>${featureLabels[f]}</label>
                            <input type="text" class="admin-model-input" data-provider="${p}" data-feature="${f}" value="${prov.models?.[f]||''}">
                        </div>
                    `).join('');
                }
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
                fallback_order: document.getElementById('adminFallbackOrder').value.split(/[,\\s]+/).filter(Boolean),
                providers,
                routing_overrides,
                site: {
                    app_name: document.getElementById('adminAppName').value,
                    default_target_role: document.getElementById('adminDefaultRole').value,
                    interview_fields: document.getElementById('adminInterviewFields').value.split('\\n').map(s => s.trim()).filter(Boolean),
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
                msg.textContent = result.ok ? '\\u2713 Settings saved successfully!' : 'Error saving';
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
                        el.innerHTML = '\\u2713 OK: ' + (data.response || '').substring(0, 80);
                        el.style.color = 'var(--success)';
                    } else {
                        el.textContent = '\\u2717 ' + (data.error || 'Failed');
                        el.style.color = 'var(--danger)';
                    }
                }
            } catch (err) {
                if (el) { el.textContent = '\\u2717 ' + err.message; el.style.color = 'var(--danger)'; }
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
    }"""

start_str1 = "/* ═══════ INTERVIEW MODULE ═══════ */"
end_str1 = "/* ═══════ RESUME MODULE ═══════ */"
start_idx1 = content.find(start_str1)
end_idx1 = content.find(end_str1)

content = content[:start_idx1] + new_interview + "\\n\\n    " + content[end_idx1:]

start_str2 = "/* ═══════ ADMIN MODULE ═══════ */"
end_str2 = "/* ═══════ GLOBAL INIT ═══════ */"
start_idx2 = content.find(start_str2)
end_idx2 = content.find(end_str2)

# Find the end of the talent metric object
# Actually let's just search for the last '};' before global init
part1 = content[:start_idx2]
part2 = content[end_idx2:]

content = part1 + new_admin + "\\n};\\n\\n" + part2

with open("AIScript.js", "w", encoding="utf-8") as f:
    f.write(content)
print("Updated AIScript.js")
