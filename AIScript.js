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

    /* ═══════ BILINGUAL TRANSLATION ENGINE ═══════ */
    Lang: {
        current: 'ar',
        dict: {
            // Navbar Links & Global UI
            'لوحة التحكم': 'Dashboard',
            'تقييم المهارات': 'Skills Assessment',
            'المقابلات': 'Interviews',
            'السجل': 'History',
            'السيرة الذاتية': 'Resume Builder',
            'المسار المهني': 'Career Path',
            'حسابي': 'Account Settings',
            'خروج': 'Logout',
            'دخول المشرف': 'Admin Login',
            
            // Dashboard page
            'لوحة التحكم الخاصة بك': 'Your Dashboard',
            'مرحباً بك مجدداً،': 'Welcome back,',
            'نظرة عامة على نشاطك المهني وتطور مهاراتك.': 'Overview of your professional activity and skills progress.',
            'تقييمات المهارات': 'Skills Assessments',
            'المقابلات التجريبية': 'Mock Interviews',
            'السير الذاتية المحسنة': 'Enhanced Resumes',
            'توصيات المسار المهني': 'Career Recommendations',
            'آخر النشاطات': 'Recent Activities',
            'ابدأ بتقييم مهاراتك أو إجراء مقابلة تجريبية الآن!': 'Start assessing your skills or take a mock interview now!',
            
            // Account settings page
            'معلومات الحساب': 'Account Information',
            'الاسم الكامل': 'Full Name',
            'أدخل اسمك الكامل': 'Enter your full name',
            'البريد الإلكتروني': 'Email Address',
            'حفظ التغييرات': 'Save Changes',
            'تغيير كلمة المرور': 'Change Password',
            'كلمة المرور الحالية': 'Current Password',
            'كلمة المرور الجديدة': 'New Password',
            'تأكيد كلمة المرور': 'Confirm Password',
            'ملخص الحساب': 'Account Summary',
            'تاريخ الانضمام': 'Member Since',
            'إجمالي المقابلات': 'Total Interviews',
            'إجمالي التقييمات': 'Total Assessments',
            
            // History Page
            'سجل المقابلات': 'Interview History',
            'راجع نتائج مقابلاتك السابقة': 'Review your previous interview results',
            'لا توجد مقابلات سابقة': 'No previous interviews',
            'لم تُجرِ أي مقابلة تجريبية حتى الآن. ابدأ مقابلتك الأولى وستظهر نتائجها هنا.': 'You haven\'t taken any mock interviews yet. Start your first and your results will show here.',
            'ابدأ مقابلة الآن': 'Start Interview Now',
            'الجلسات السابقة': 'Previous Sessions',
            
            // Skills Assessment Page
            'تقييم المهارات الذكي': 'Smart Skills Assessment',
            'حدد مهاراتك واحصل على تقييم شامل لخلفيتك التقنية والمهنية.': 'Select your skills and get a comprehensive evaluation of your technical background.',
            '1. اختر المهارات': '1. Choose Skills',
            '2. المهارات المحددة': '2. Selected Skills',
            'اضف مهارة مخصصة': 'Add custom skill',
            'أدخل اسم مهارة واضغط Enter': 'Enter skill name and press Enter',
            'الدور المستهدف (اختياري)': 'Target Role (Optional)',
            'ابدأ التقييم': 'Start Assessment',
            'مسار التطوير المقترح': 'Suggested Roadmap',
            'الفجوات المهنية والتوصيات': 'Skill Gaps & Recommendations',
            'نقاط القوة': 'Strengths',
            'التحليل المهني': 'Professional Analysis',
            'إعادة التقييم': 'Re-assess',
            
            // Mock Interview Page
            'المقابلات الشخصية الذكية': 'Smart Mock Interviews',
            'تدرّب على المقابلات الشخصية وتلقّ تقييماً فورياً لأدائك مع مدرب الذكاء الاصطناعي.': 'Practice job interviews and receive instant feedback on your performance with AI.',
            'اختر مجال المقابلة': 'Choose Interview Field',
            'الدور الوظيفي المستهدف': 'Target Job Role',
            'مثال: مهندس برمجيات': 'e.g. Software Engineer',
            'نوع المقابلة': 'Interview Type',
            'مقابلة نصية / صوتية': 'Text / Voice Interview',
            'تعتمد على المحادثة الكتابية والتعرف على الصوت.': 'Relies on chat messaging and speech recognition.',
            'مقابلة مرئية (فيديو)': 'Video Interview (Camera)',
            'تتضمن تشغيل الكاميرا وتحليل الحضور ولغة الجسد.': 'Includes camera activation, analyzing presence and body language.',
            'ابدأ المقابلة': 'Start Interview',
            'السؤال': 'Question',
            'أرسل': 'Send',
            'إنهاء المقابلة': 'End Interview',
            'التحليل والتقييم النهائي': 'Final Analysis & Score',
            'النتيجة العامة': 'Overall Score',
            'الملخص العام': 'General Summary',
            'نقاط القوة والمميزات': 'Strengths & Advantages',
            'نقاط التحسين والتطوير': 'Areas for Improvement',
            'نصائح للنجاح': 'Success Tips',
            'إغلاق المعاينة': 'Close Preview',
            'ميكروفون': 'Microphone',
            'كاميرا': 'Camera',
            'صوت المساعد': 'AI Voice',
            'تحدث الآن...': 'Speak now...',
            'اكتب إجابتك هنا...': 'Type your answer here...',
            'التعرف على الصوت مفعل': 'Voice recognition active',
            
            // Resume Enhancer
            'محسّن السير الذاتية الذكي': 'Smart Resume Enhancer',
            'أنشئ سيرة ذاتية احترافية متوافقة مع أنظمة الفرز الذاتية بمساعدة الذكاء الاصطناعي.': 'Create a professional, ATS-compatible resume with AI assistance.',
            'المعلومات الأساسية': 'Basic Information',
            'الخبرات العملية': 'Work Experience',
            'التعليم والمهارات': 'Education & Skills',
            'رؤية المعاينة': 'Live Preview',
            'الاسم': 'Name',
            'البريد': 'Email',
            'الهاتف': 'Phone',
            'المسمى المهني': 'Job Title',
            'الملخص المهني الحالي': 'Current Professional Summary',
            'تحسين السيرة الذاتية': 'Enhance Resume',
            'تصدير PDF': 'Export PDF',
            'اسم الشركة / المنظمة': 'Company / Organization Name',
            'من': 'From',
            'إلى': 'To',
            'شرح المهام والإنجازات': 'Description of tasks and achievements',
            'الدرجة العلمية / التخصص': 'Degree / Specialization',
            'الجامعة / المؤسسة': 'University / Institution',
            'سنة التخرج': 'Graduation Year',
            'المهارات التقنية (مفصولة بفاصلة)': 'Technical Skills (comma separated)',
            'المهارات الشخصية': 'Soft Skills',
            'اللغات': 'Languages',
            'ابدأ بملء البيانات لرؤية المعاينة': 'Start filling in details to see live preview',
            
            // Career Advisory
            'استيراد المهارات المقيمة': 'Import Assessed Skills',
            'مستشار المسار المهني': 'Career Path Advisor',
            'اكتشف الخيارات المهنية المتاحة وتلقّ نصائح عملية لتحقيق أهدافك الوظيفية.': 'Discover available career options and receive practical advice to achieve goals.',
            'أدخل مهاراتك الحالية': 'Enter your current skills',
            'مثال: Python, SQL, تحليل البيانات': 'e.g. Python, SQL, Data Analysis',
            'اهتماماتك ومجالات شغفك': 'Your interests and passion areas',
            'مثال: الذكاء الاصطناعي، العمل المالي': 'e.g. AI, Finance, Web development',
            'سنوات الخبرة المهنية': 'Years of professional experience',
            'الحصول على التوصيات': 'Get Recommendations',
            'توصيات المسارات المهنية': 'Recommended Career Paths',
            'إعادة البحث': 'Search Again',
            'نسبة التوافق': 'Compatibility',
            'الطلب المستقبلي': 'Growth Outlook',
            'متوسط الرواتب': 'Salary Range'
        },
        revDict: {},
        
        init() {
            // Build the reverse mapping dictionary dynamically to keep footprint low
            for (const [ar, en] of Object.entries(this.dict)) {
                this.revDict[en] = ar;
            }
            
            // Set language from local storage, default to 'ar'
            this.current = localStorage.getItem('talentmetric_lang') || 'ar';
            
            // Bind language toggle button click listeners
            document.querySelectorAll('#langToggleBtn, .lang-toggle-btn').forEach(btn => {
                btn.addEventListener('click', () => {
                    const next = this.current === 'ar' ? 'en' : 'ar';
                    this.setLang(next);
                });
            });
            
            // Apply language modifications to active DOM
            this.applyTranslations();
        },
        
        setLang(lang) {
            this.current = lang;
            localStorage.setItem('talentmetric_lang', lang);
            this.applyTranslations();
            TalentMetric.toast(lang === 'en' ? 'Language switched to English' : 'تم تغيير اللغة إلى العربية', 'success');
        },
        
        applyTranslations() {
            const isEn = this.current === 'en';
            
            // Update page directional metadata and body styles
            document.documentElement.setAttribute('lang', this.current);
            document.documentElement.setAttribute('dir', isEn ? 'ltr' : 'rtl');
            document.body.style.fontFamily = isEn ? "'Inter', sans-serif" : "'Cairo', sans-serif";
            
            // Update text inside the toggle buttons themselves
            document.querySelectorAll('#langToggleBtn, .lang-toggle-btn').forEach(btn => {
                btn.textContent = isEn ? 'AR' : 'EN';
            });
            
            // Recursively scan DOM Text nodes to apply text mapping
            const walk = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT, null, false);
            let node;
            while (node = walk.nextNode()) {
                const parent = node.parentNode;
                if (!parent || parent.tagName === 'SCRIPT' || parent.tagName === 'STYLE' || parent.tagName === 'I' || parent.closest('.chat-message')) continue;
                
                const trimmed = node.nodeValue.trim();
                if (!trimmed) continue;
                
                if (isEn) {
                    if (this.dict[trimmed]) {
                        node.nodeValue = node.nodeValue.replace(trimmed, this.dict[trimmed]);
                    }
                } else {
                    if (this.revDict[trimmed]) {
                        node.nodeValue = node.nodeValue.replace(trimmed, this.revDict[trimmed]);
                    }
                }
            }
            
            // Translate placeholders, inputs, and layout styles
            document.querySelectorAll('input, textarea').forEach(el => {
                const ph = el.getAttribute('placeholder');
                if (ph) {
                    const trimmed = ph.trim();
                    if (isEn) {
                        if (this.dict[trimmed]) el.setAttribute('placeholder', this.dict[trimmed]);
                    } else {
                        if (this.revDict[trimmed]) el.setAttribute('placeholder', this.revDict[trimmed]);
                    }
                }
            });
            
            // Toggle LTR layout rules across standard components
            document.querySelectorAll('.navbar-app, .nav-container, .nav-links, .dash-card, .form-group').forEach(el => {
                if (isEn) {
                    el.classList.add('ltr-layout');
                    el.classList.remove('rtl-layout');
                } else {
                    el.classList.add('rtl-layout');
                    el.classList.remove('ltr-layout');
                }
            });
        }
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
            if (dateEl) {
                const isEn = TalentMetric.Lang.current === 'en';
                dateEl.textContent = new Date().toLocaleDateString(isEn ? 'en-US' : 'ar-SA', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' });
            }
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
                if (data.activity && data.activity.length > 0) {
                    feed.innerHTML = data.activity.map(a => `
                        <div class="activity-item">
                            <div class="activity-icon ${a.type}"><i class="fas fa-${a.type === 'skills' ? 'chart-line' : a.type === 'interview' ? 'microphone-lines' : a.type === 'resume' ? 'file-lines' : a.type === 'career' ? 'route' : 'user'}"></i></div>
                            <div class="activity-info"><span>${a.title}</span><span class="activity-date">${new Date(a.created_at).toLocaleDateString(TalentMetric.Lang.current === 'en' ? 'en-US' : 'ar-SA')}</span></div>
                        </div>`).join('');
                }
            } catch (err) { console.error(err); }
        }
    },

    /* ═══════ SKILLS MODULE ═══════ */
    Skills: {
        skillsState: [],
        init() {
            if (!TalentMetric.requireAuth()) return;
            
            // Load saved skills from assessment
            const saved = localStorage.getItem('talentmetric_user_skills');
            if (saved) {
                try {
                    this.skillsState = JSON.parse(saved);
                    if (this.skillsState && this.skillsState.length > 0) {
                        setTimeout(() => {
                            const placeholder = document.getElementById('skillsPlaceholder');
                            const container = document.getElementById('skillsContainer');
                            const assessBtn = document.getElementById('assessBtn');
                            if (placeholder) placeholder.style.display = 'none';
                            if (container) container.style.display = 'block';
                            if (assessBtn) assessBtn.style.display = 'block';
                            this.renderSkillsList();
                        }, 50);
                    }
                } catch (e) { this.skillsState = []; }
            }
            
            const suggestBtn = document.getElementById('suggestSkillsBtn');
            const targetInput = document.getElementById('targetRole');
            
            if (suggestBtn) {
                suggestBtn.addEventListener('click', () => this.fetchSuggestions());
            }
            if (targetInput) {
                targetInput.addEventListener('keydown', e => {
                    if (e.key === 'Enter') {
                        e.preventDefault();
                        this.fetchSuggestions();
                    }
                });
            }

            const addBtn = document.getElementById('addCustomSkill');
            const customInput = document.getElementById('customSkill');
            const customLevelSelect = document.getElementById('customSkillLevel');

            if (addBtn) {
                const addCustom = () => {
                    const name = customInput.value.trim();
                    const level = parseInt(customLevelSelect.value) || 3;
                    if (name) {
                        const exists = this.skillsState.some(s => s.name.toLowerCase() === name.toLowerCase());
                        if (exists) {
                            TalentMetric.toast(TalentMetric.Lang.current === 'en' ? 'Skill already added!' : 'تم إضافة المهارة بالفعل!', 'warning');
                            return;
                        }
                        const isEn = TalentMetric.Lang.current === 'en';
                        this.skillsState.push({
                            name: name,
                            category: isEn ? 'Custom Skill' : 'مهارة مخصصة',
                            level: level
                        });
                        this.renderSkillsList();
                        customInput.value = '';
                    }
                };
                addBtn.addEventListener('click', addCustom);
                customInput.addEventListener('keypress', e => {
                    if (e.key === 'Enter') {
                        e.preventDefault();
                        addCustom();
                    }
                });
            }

            const assessBtn = document.getElementById('assessBtn');
            if (assessBtn) assessBtn.addEventListener('click', () => this.assess());
            const resetBtn = document.getElementById('resetSkills');
            if (resetBtn) resetBtn.addEventListener('click', () => this.reset());
        },
        getLevelLabel(level) {
            const isEn = TalentMetric.Lang.current === 'en';
            const labels = {
                1: isEn ? 'Novice' : 'أساسيات',
                2: isEn ? 'Beginner' : 'مبتدئ',
                3: isEn ? 'Intermediate' : 'متوسط',
                4: isEn ? 'Advanced' : 'متقدم',
                5: isEn ? 'Expert' : 'خبير'
            };
            return labels[level] || (isEn ? 'Intermediate' : 'متوسط');
        },
        async fetchSuggestions() {
            const targetRole = document.getElementById('targetRole').value.trim();
            if (!targetRole) {
                TalentMetric.toast(TalentMetric.Lang.current === 'en' ? 'Please enter a target role first!' : 'يرجى إدخال الوظيفة المستهدفة أولاً!', 'warning');
                return;
            }
            
            TalentMetric.showLoading();
            try {
                const response = await TalentMetric.api('/api/skills/suggest', {
                    method: 'POST',
                    body: JSON.stringify({ target_role: targetRole, lang: TalentMetric.Lang.current })
                });
                
                if (response && response.skills && response.skills.length > 0) {
                    this.skillsState = response.skills.map(s => ({
                        name: s.name,
                        category: s.category || (TalentMetric.Lang.current === 'en' ? 'Core Skill' : 'مهارة أساسية'),
                        level: 3
                    }));
                    
                    document.getElementById('skillsPlaceholder').style.display = 'none';
                    document.getElementById('skillsContainer').style.display = 'block';
                    document.getElementById('assessBtn').style.display = 'block';
                    
                    this.renderSkillsList();
                    TalentMetric.toast(TalentMetric.Lang.current === 'en' ? 'Skills generated successfully!' : 'تم توليد المهارات بنجاح!', 'success');
                } else {
                    TalentMetric.toast(TalentMetric.Lang.current === 'en' ? 'No suggestions generated, feel free to add custom ones!' : 'لم نتمكن من اقتراح مهارات، يمكنك إضافتها يدوياً!', 'info');
                    document.getElementById('skillsPlaceholder').style.display = 'none';
                    document.getElementById('skillsContainer').style.display = 'block';
                    document.getElementById('assessBtn').style.display = 'block';
                    this.skillsState = [];
                    this.renderSkillsList();
                }
            } catch (err) {
                TalentMetric.toast(err.error || 'حدث خطأ أثناء اقتراح المهارات', 'error');
            } finally {
                TalentMetric.hideLoading();
            }
        },
        renderSkillsList() {
            const listContainer = document.getElementById('skillsList');
            const assessBtn = document.getElementById('assessBtn');
            if (!listContainer) return;
            
            // Save current skillsState to localStorage
            localStorage.setItem('talentmetric_user_skills', JSON.stringify(this.skillsState));
            
            if (this.skillsState.length === 0) {
                listContainer.innerHTML = `<div class="empty-skills-msg" style="grid-column: 1 / -1; text-align: center; padding: 2rem; color: var(--text-muted);">
                    <i class="fas fa-layer-group" style="font-size: 2rem; margin-bottom: 0.5rem; display: block; opacity: 0.5;"></i>
                    ${TalentMetric.Lang.current === 'en' ? 'No skills in list. Add custom ones below!' : 'لا توجد مهارات في القائمة. أضف مهارات مخصصة أدناه!'}
                </div>`;
                if (assessBtn) assessBtn.style.display = 'none';
                return;
            }

            if (assessBtn) assessBtn.style.display = 'block';

            listContainer.innerHTML = this.skillsState.map((skill, index) => {
                const starsHtml = Array.from({ length: 5 }, (_, i) => {
                    const starVal = i + 1;
                    const isSolid = starVal <= skill.level;
                    return `<i class="rating-star ${isSolid ? 'fas' : 'far'} fa-star" data-skill-idx="${index}" data-val="${starVal}"></i>`;
                }).join('');

                return `
                    <div class="skill-assess-card" data-idx="${index}">
                        <div class="skill-assess-header">
                            <span class="skill-assess-name">${skill.name}</span>
                            <span class="skill-assess-badge">${skill.category}</span>
                        </div>
                        <div class="skill-assess-body">
                            <div class="skill-assess-rating">
                                <div class="rating-stars">
                                    ${starsHtml}
                                </div>
                                <span class="rating-label">${this.getLevelLabel(skill.level)}</span>
                            </div>
                        </div>
                        <button class="skill-delete-btn" data-idx="${index}" title="${TalentMetric.Lang.current === 'en' ? 'Remove' : 'حذف'}">
                            <i class="fas fa-trash-alt"></i>
                        </button>
                    </div>
                `;
            }).join('');

            listContainer.querySelectorAll('.rating-star').forEach(star => {
                star.addEventListener('click', (e) => {
                    const idx = parseInt(e.currentTarget.dataset.skillIdx);
                    const val = parseInt(e.currentTarget.dataset.val);
                    this.skillsState[idx].level = val;
                    this.renderSkillsList();
                });
            });

            listContainer.querySelectorAll('.skill-delete-btn').forEach(btn => {
                btn.addEventListener('click', (e) => {
                    const idx = parseInt(e.currentTarget.dataset.idx);
                    this.skillsState.splice(idx, 1);
                    this.renderSkillsList();
                });
            });
        },
        async assess() {
            if (this.skillsState.length === 0) { TalentMetric.toast(TalentMetric.Lang.current === 'en' ? 'Please add at least one skill' : 'يرجى إضافة مهارة واحدة على الأقل', 'error'); return; }
            const targetRole = document.getElementById('targetRole').value.trim();
            TalentMetric.showLoading();
            try {
                const payloadSkills = this.skillsState.map(s => ({
                    name: s.name,
                    level: s.level
                }));
                const result = await TalentMetric.api('/api/skills/assess', {
                    method: 'POST',
                    body: JSON.stringify({ skills: payloadSkills, target_role: targetRole, lang: TalentMetric.Lang.current })
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
            
            const score = data.score || 0;
            document.getElementById('scoreText').textContent = score + '%';
            const fill = document.getElementById('scoreFill');
            if (fill) { const offset = 339.3 - (339.3 * score / 100); fill.style.strokeDashoffset = offset; }
            
            document.getElementById('analysisText').textContent = data.analysis || '';
            
            const sList = document.getElementById('strengthsList');
            sList.innerHTML = (data.strengths || []).map(s => `<li>${s}</li>`).join('');
            
            const gList = document.getElementById('gapsList');
            gList.innerHTML = (data.gaps || []).map(g => {
                const imp = g.importance === 'عالية' || g.importance === 'High' ? 'high' : g.importance === 'متوسطة' || g.importance === 'Medium' ? 'medium' : 'low';
                return `<div class="gap-item"><h4>${g.skill}</h4><span class="gap-importance ${imp}">${g.importance}</span><p>${g.recommendation}</p></div>`;
            }).join('');
            
            const rList = document.getElementById('roadmapList');
            rList.innerHTML = (data.roadmap || []).map(r => `<div class="roadmap-item">${r}</div>`).join('');
        },
        reset() {
            document.getElementById('skillsInputSection').style.display = 'block';
            document.getElementById('skillsResults').style.display = 'none';
            document.getElementById('skillsPlaceholder').style.display = 'block';
            document.getElementById('skillsContainer').style.display = 'none';
            document.getElementById('assessBtn').style.display = 'none';
            this.skillsState = [];
            localStorage.removeItem('talentmetric_user_skills');
            document.getElementById('targetRole').value = '';
            this.renderSkillsList();
        }
    },

    /* ═══════ INTERVIEW MODULE ═══════ */
    Interview: {
        sessionId: null, questionCount: 0, mode: 'chat',
        stream: null, recognition: null, synth: window.speechSynthesis, ttsEnabled: true,
        timerInt: null, seconds: 0, accumulatedStreamText: '',
        silenceTimer: null, silenceDelay: 4000, isListening: false,
        
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

            // Video Mode — sttMicBtn is now a "Send Now" override button
            document.getElementById('videoSendBtn')?.addEventListener('click', () => this.sendAnswer('video'));
            document.getElementById('endVideoInterviewBtn')?.addEventListener('click', () => this.end());
            document.getElementById('endVideoCallBtn')?.addEventListener('click', () => this.end());
            document.getElementById('videoTranscriptInput')?.addEventListener('keydown', e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); this.stopListeningAndSend(); } });
            
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
            // sttMicBtn: if listening → send now; if idle → start listening
            document.getElementById('sttMicBtn')?.addEventListener('click', () => {
                const input = document.getElementById('videoTranscriptInput');
                if (this.isListening) {
                    this.stopListeningAndSend();
                } else if (input && input.value.trim()) {
                    this.sendAnswer('video');
                } else {
                    this.startListeningForAnswer();
                }
            });

            document.getElementById('closeSummaryModal')?.addEventListener('click', () => { document.getElementById('interviewSummaryModal').style.display = 'none'; });

            this.initSpeech();
        },

        initSpeech() {
            // Recognition instances are created fresh per session in _makeFreshRecognition()
            // This just checks browser support and stores a null placeholder
            const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
            this.recognition = SR ? null : null; // will be created in _doListenLoop
        },

        /**
         * Creates a new SpeechRecognition instance.
         * continuous=false is intentional: Chrome is unreliable with continuous=true.
         * We restart manually in onend to create a rolling listen loop.
         */
        _makeFreshRecognition() {
            const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
            if (!SR) return null;
            const r = new SR();
            r.continuous     = false;   // each phrase = one session; we restart in onend
            r.interimResults = true;
            r.lang = TalentMetric.Lang.current === 'en' ? 'en-US' : 'ar-SA';
            return r;
        },

        /**
         * Starts the hands-free listening cycle for video interview.
         * Called automatically after the AI speaks (TTS onend).
         * The loop runs until stopListeningAndSend() is called.
         */
        startListeningForAnswer() {
            if (!this.sessionId || this.isListening) return;

            const isEn      = TalentMetric.Lang.current === 'en';
            const input     = document.getElementById('videoTranscriptInput');
            const sttBtn    = document.getElementById('sttMicBtn');
            const sttWave   = document.getElementById('sttWave');
            const statusTxt = document.getElementById('sttStatusText');

            this.isListening      = true;
            this._finalTranscript = '';         // reset accumulated text for this question round

            if (input)     input.value = '';
            if (sttBtn)    { sttBtn.classList.add('listening'); sttBtn.querySelector('i').className = 'fas fa-paper-plane'; sttBtn.title = isEn ? 'Send now' : 'إرسال الآن'; }
            if (sttWave)   sttWave.classList.add('listening');
            if (statusTxt) statusTxt.textContent = isEn ? '🎙 Listening — speak your answer' : '🎙 جاري الاستماع — تحدث الآن';

            // Start the rolling loop
            this._doListenLoop(isEn, input, sttBtn, sttWave, statusTxt);
        },

        /**
         * Internal: starts one recognition session and auto-restarts in onend.
         * This creates a rolling loop that keeps capturing until stopListeningAndSend() is called.
         */
        _doListenLoop(isEn, input, sttBtn, sttWave, statusTxt) {
            // Exit if the loop was stopped externally
            if (!this.isListening || !this.sessionId) return;

            const rec = this._makeFreshRecognition();
            if (!rec) return;
            this.recognition = rec;     // store so the manual send button can ref it

            rec.onresult = (e) => {
                // Accumulate results: each session gives fresh indices starting at 0
                let interim = '';
                for (let i = 0; i < e.results.length; i++) {
                    if (e.results[i].isFinal) {
                        this._finalTranscript += e.results[i][0].transcript + ' ';
                    } else {
                        interim += e.results[i][0].transcript;
                    }
                }

                // Show running transcript (final so far + current interim)
                const displayed = (this._finalTranscript + interim).trim();
                if (input) input.value = displayed;

                // Reset the silence timer: user spoke → 4s countdown resets
                if (this.silenceTimer) clearTimeout(this.silenceTimer);
                if (displayed) {
                    this.silenceTimer = setTimeout(() => this.stopListeningAndSend(), this.silenceDelay);
                }
            };

            rec.onerror = (e) => {
                // no-speech / aborted — non-fatal, onend handles the restart
                if (e.error === 'no-speech' || e.error === 'aborted') return;
                // not-allowed / audio-capture — fatal, show error
                this.isListening = false;
                if (sttBtn)  { sttBtn.classList.remove('listening'); sttBtn.querySelector('i').className = 'fas fa-microphone'; sttBtn.title = ''; }
                if (sttWave) sttWave.classList.remove('listening');
                if (statusTxt) {
                    statusTxt.textContent = e.error === 'not-allowed'
                        ? (isEn ? 'Mic blocked — grant browser permission' : 'تم حظر الميكروفون — اسمح بالوصول')
                        : (isEn ? 'Mic error — click mic button to retry' : 'خطأ في الميكروفون — انقر زر المايك');
                }
            };

            rec.onend = () => {
                // If we are still supposed to be listening, restart the loop immediately.
                // isListening is set to false by stopListeningAndSend() to break the loop.
                if (this.isListening && this.sessionId) {
                    setTimeout(() => this._doListenLoop(isEn, input, sttBtn, sttWave, statusTxt), 150);
                }
            };

            try {
                rec.start();
            } catch (err) {
                // InvalidStateError = already started (race condition) — ignore and let onend restart
                if (err.name !== 'InvalidStateError') {
                    this.isListening = false;
                }
            }
        },

        /**
         * Stops the listening loop and submits whatever has been captured.
         * Called by: silence timer (auto), sttMicBtn click (manual), sendAnswer (cleanup).
         */
        stopListeningAndSend() {
            if (this.silenceTimer) { clearTimeout(this.silenceTimer); this.silenceTimer = null; }
            this.isListening = false;   // breaks the _doListenLoop restart chain
            const sttBtn    = document.getElementById('sttMicBtn');
            const sttWave   = document.getElementById('sttWave');
            const statusTxt = document.getElementById('sttStatusText');
            if (sttBtn)    { sttBtn.classList.remove('listening'); sttBtn.querySelector('i').className = 'fas fa-microphone'; sttBtn.title = ''; }
            if (sttWave)   sttWave.classList.remove('listening');

            const input = document.getElementById('videoTranscriptInput');
            if (input && input.value.trim()) {
                if (statusTxt) statusTxt.textContent = TalentMetric.Lang.current === 'en' ? 'Sending answer...' : 'إرسال الإجابة...';
                setTimeout(() => this.sendAnswer('video'), 100);
            } else {
                if (statusTxt) statusTxt.textContent = TalentMetric.Lang.current === 'en' ? 'No speech captured' : 'لم يُكشف صوت';
            }
        },

        /* ─── Chat-mode manual STT toggle (unchanged) ─── */
        toggleSTT(inputId, btnId) {
            if (!this.recognition) { TalentMetric.toast(TalentMetric.Lang.current === 'en' ? 'Browser does not support Speech Recognition.' : 'المتصفح لا يدعم التعرف على الصوت', 'error'); return; }
            const btn   = document.getElementById(btnId);
            const input = document.getElementById(inputId);
            const isEn  = TalentMetric.Lang.current === 'en';

            if (btn.classList.contains('listening')) {
                this.recognition.stop();
                btn.classList.remove('listening');
            } else {
                btn.classList.add('listening');
                this.recognition.lang = isEn ? 'en-US' : 'ar-SA';
                this.recognition.onresult = (e) => {
                    let text = '';
                    for (let i = 0; i < e.results.length; ++i) text += e.results[i][0].transcript;
                    input.value = text;
                };
                this.recognition.onerror = () => btn.classList.remove('listening');
                this.recognition.onend   = () => btn.classList.remove('listening');
                this.recognition.start();
            }
        },

        speak(text) {
            if (!this.ttsEnabled || !this.synth) {
                // If TTS disabled in video mode, go straight to listening
                if (this.mode === 'video') setTimeout(() => this.startListeningForAnswer(), 400);
                return;
            }
            this.synth.cancel();

            // Flag mic as stopped (a fresh instance is created in startListeningForAnswer)
            // Do NOT call recognition.stop() here — it can fire aborted into the next session
            if (this.isListening) {
                this.isListening = false;
            }
            if (this.silenceTimer) { clearTimeout(this.silenceTimer); this.silenceTimer = null; }

            const sttBtn    = document.getElementById('sttMicBtn');
            const sttWave   = document.getElementById('sttWave');
            const statusTxt = document.getElementById('sttStatusText');
            const isEn      = TalentMetric.Lang.current === 'en';
            if (sttBtn)    { sttBtn.classList.remove('listening'); sttBtn.querySelector('i').className = 'fas fa-microphone'; }
            if (sttWave)   sttWave.classList.remove('listening');
            if (statusTxt) statusTxt.textContent = isEn ? 'AI is speaking...' : 'المحاور يتحدث...';

            const utterance = new SpeechSynthesisUtterance(text);
            utterance.lang  = isEn ? 'en-US' : 'ar-SA';

            const avatar = document.getElementById('aiSpeakingIndicator');
            utterance.onstart = () => { if (avatar) avatar.classList.add('active'); };
            utterance.onend   = () => {
                if (avatar) avatar.classList.remove('active');
                // Auto-start listening after AI finishes — give browser 900ms to fully release audio
                if (this.mode === 'video' && this.sessionId) {
                    if (statusTxt) statusTxt.textContent = isEn ? 'Your turn — speak your answer' : 'دورك — تحدث الآن';
                    setTimeout(() => this.startListeningForAnswer(), 900);
                }
            };
            utterance.onerror = () => {
                if (avatar) avatar.classList.remove('active');
                if (this.mode === 'video' && this.sessionId) setTimeout(() => this.startListeningForAnswer(), 900);
            };

            this.synth.speak(utterance);
        },
        async setupPreview() {
            const prev = document.getElementById('videoPreviewSetup');
            if(prev) prev.style.display = 'block';
            try {
                const stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: true });
                const video = document.getElementById('previewVideo');
                if(video) video.srcObject = stream;
                document.getElementById('camStatusText').textContent = TalentMetric.Lang.current === 'en' ? 'Camera & Mic active' : 'الكاميرا والميكروفون تعملان';
                document.getElementById('camDot').classList.add('active');
            } catch(e) {
                document.getElementById('camStatusText').textContent = TalentMetric.Lang.current === 'en' ? 'Cannot access camera' : 'تعذر الوصول للكاميرا';
                document.getElementById('camDot').classList.remove('active');
                TalentMetric.toast(TalentMetric.Lang.current === 'en' ? 'Please grant camera access.' : 'يرجى السماح بالوصول للكاميرا', 'error');
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
                    method: 'POST', body: JSON.stringify({ role, field, mode: this.mode, lang: TalentMetric.Lang.current })
                });
                this.sessionId = data.session_id;
                this.questionCount = 1;
                
                document.getElementById('interviewSetup').style.display = 'none';
                const isEn = TalentMetric.Lang.current === 'en';
                
                if(this.mode === 'video') {
                    document.getElementById('interviewVideo').style.display = 'block';
                    document.getElementById('videoQuestionCounter').textContent = (isEn ? 'Question ' : 'السؤال ') + this.questionCount;
                    this.startTimer();
                } else {
                    document.getElementById('interviewChat').style.display = 'block';
                    document.getElementById('questionCounter').textContent = (isEn ? 'Question ' : 'السؤال ') + this.questionCount;
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
            
            if(this.synth) this.synth.cancel(); // Stop AI speaking when user sends answer
            
            // Clear silence detection — mic will not stop explicitly since a fresh instance is used next time
            if (this.silenceTimer) { clearTimeout(this.silenceTimer); this.silenceTimer = null; }
            this.isListening = false;
            const sttBtn  = document.getElementById('sttMicBtn');
            const sttWave = document.getElementById('sttWave');
            const statusTxt = document.getElementById('sttStatusText');
            if (sttBtn)    { sttBtn.classList.remove('listening'); sttBtn.querySelector('i').className = 'fas fa-microphone'; }
            if (sttWave)   sttWave.classList.remove('listening');
            if (statusTxt && modeStr === 'video') statusTxt.textContent = TalentMetric.Lang.current === 'en' ? 'Processing...' : 'جاري المعالجة...';
            
            input.value = '';
            this.addMessage(answer, 'user');
            this.showTyping();
            document.getElementById(btnId).disabled = true;

            // Capture base64 snapshot from camera vision if in video mode
            let frameB64 = null;
            if (this.mode === 'video') {
                try {
                    const video = document.getElementById('interviewVideoFeed');
                    const canvas = document.getElementById('videoCaptureCanvas');
                    if (video && canvas) {
                        canvas.width = 320;
                        canvas.height = 240;
                        const ctx = canvas.getContext('2d');
                        ctx.drawImage(video, 0, 0, 320, 240);
                        const dataUrl = canvas.toDataURL('image/jpeg', 0.7);
                        frameB64 = dataUrl.split(',')[1];
                    }
                } catch (e) {
                    console.error("Failed to capture video snapshot for AI Vision:", e);
                }
            }
            
            try {
                // Post answer to live streaming SSE endpoint
                const response = await fetch('/api/interview/respond/stream', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Authorization': 'Bearer ' + TalentMetric.getToken()
                    },
                    body: JSON.stringify({
                        session_id: this.sessionId,
                        answer,
                        frame_b64: frameB64
                    })
                });
                
                this.hideTyping();
                if (!response.ok) {
                    const errorData = await response.json();
                    throw new Error(errorData.error || 'Failed to stream response');
                }
                
                const reader = response.body.getReader();
                const decoder = new TextDecoder("utf-8");
                let buffer = "";
                this.accumulatedStreamText = "";
                
                while (true) {
                    const { value, done } = await reader.read();
                    if (done) break;
                    buffer += decoder.decode(value, { stream: true });
                    
                    const lines = buffer.split("\n");
                    buffer = lines.pop(); // save incomplete line in buffer
                    
                    for (const line of lines) {
                        if (line.startsWith("data: ")) {
                            const jsonStr = line.substring(6).trim();
                            if (jsonStr) {
                                try {
                                    const parsed = JSON.parse(jsonStr);
                                    if (parsed.error) throw new Error(parsed.error);
                                    
                                    if (parsed.token) {
                                        this.accumulatedStreamText += parsed.token;
                                        this.updateStreamBubble(this.accumulatedStreamText);
                                    }
                                    
                                    if (parsed.done) {
                                        // Final finished token packet received
                                        const finalData = parsed;
                                        
                                        // Remove streaming bubble preview
                                        const bubble = document.getElementById('streamingBubble');
                                        if (bubble) bubble.remove();
                                        
                                        this.questionCount = finalData.question_count;
                                        const counterId = this.mode === 'video' ? 'videoQuestionCounter' : 'questionCounter';
                                        const counterEl = document.getElementById(counterId);
                                        if (counterEl) {
                                            counterEl.textContent = (TalentMetric.Lang.current === 'en' ? 'Question ' : 'السؤال ') + this.questionCount;
                                        }
                                        
                                        if (!finalData.interview_done && finalData.next_question) {
                                            this.addMessage(finalData.next_question, 'ai', finalData.feedback, finalData.score);
                                            this.speak(finalData.next_question);
                                        } else if (finalData.interview_done) {
                                            this.addMessage(TalentMetric.Lang.current === 'en' ? 'Thank you! The interview is complete.' : 'شكرًا لك! تم الانتهاء من المقابلة.', 'ai', finalData.feedback, finalData.score);
                                            setTimeout(() => this.end(), 1500);
                                        }
                                        return;
                                    }
                                } catch (e) {
                                    console.error("Stream parse error:", e);
                                }
                            }
                        }
                    }
                }
            } catch (err) {
                this.hideTyping();
                const bubble = document.getElementById('streamingBubble');
                if (bubble) bubble.remove();
                TalentMetric.toast(err.message || 'خطأ في الاتصال بالبث المباشر', 'error');
            } finally {
                document.getElementById(btnId).disabled = false;
            }
        },
        updateStreamBubble(text) {
            const container = this.mode === 'video' ? document.getElementById('videoMessages') : document.getElementById('chatMessages');
            if (!container) return;
            
            let bubble = document.getElementById('streamingBubble');
            if (!bubble) {
                bubble = document.createElement('div');
                bubble.className = 'chat-message ai streaming';
                bubble.id = 'streamingBubble';
                container.appendChild(bubble);
            }
            
            const isEn = TalentMetric.Lang.current === 'en';
            const fbTag = isEn ? '[FEEDBACK]:' : '[التقييم]:';
            const scTag = isEn ? '[SCORE]:' : '[النقاط]:';
            const quTag = isEn ? '[QUESTION]:' : '[السؤال]:';
            
            let fbText = "";
            let scText = "";
            let quText = "";
            
            const fbIdx = text.indexOf(fbTag);
            const scIdx = text.indexOf(scTag);
            const quIdx = text.indexOf(quTag);
            
            const sorted = [
                { tag: 'fb', idx: fbIdx, tagLen: fbTag.length },
                { tag: 'sc', idx: scIdx, tagLen: scTag.length },
                { tag: 'qu', idx: quIdx, tagLen: quTag.length }
            ].filter(o => o.idx !== -1).sort((a,b) => a.idx - b.idx);
            
            if (sorted.length === 0) {
                bubble.innerHTML = `<div class="streaming-text">${text}</div>`;
            } else {
                let html = '';
                for (let i = 0; i < sorted.length; i++) {
                    const current = sorted[i];
                    const startPos = current.idx + current.tagLen;
                    const nextIdx = (i + 1 < sorted.length) ? sorted[i+1].idx : text.length;
                    const content = text.substring(startPos, nextIdx).trim();
                    
                    if (current.tag === 'fb') fbText = content;
                    else if (current.tag === 'sc') scText = content;
                    else if (current.tag === 'qu') quText = content;
                }
                
                if (fbText) {
                    html += `<div class="stream-section feedback-section" style="margin-bottom:0.8rem; background:rgba(255,255,255,0.03); padding:0.6rem; border-radius:8px; border-left: 3px solid var(--primary);">
                        <strong style="display:block;margin-bottom:0.2rem;color:var(--primary);font-size:0.85rem;"><i class="fas fa-comment-dots"></i> ${isEn ? 'Evaluation' : 'التقييم'}:</strong>
                        <p style="margin:0;font-size:0.9rem;color:var(--text-main);">${fbText}</p>
                    </div>`;
                }
                if (scText) {
                    html += `<div class="stream-section score-section" style="margin-bottom:0.8rem; background:rgba(16,185,129,0.08); padding:0.6rem; border-radius:8px; border-left: 3px solid #34d399; display:inline-flex; align-items:center; gap:0.5rem;">
                        <strong style="color:#34d399;font-size:0.85rem;"><i class="fas fa-star"></i> ${isEn ? 'Score' : 'النقاط'}:</strong>
                        <span class="score-pill" style="font-weight:700;color:#34d399;">${scText}/10</span>
                    </div>`;
                }
                if (quText) {
                    html += `<div class="stream-section question-section" style="background:rgba(59,130,246,0.08); padding:0.6rem; border-radius:8px; border-left: 3px solid #60a5fa;">
                        <strong style="display:block;margin-bottom:0.2rem;color:#60a5fa;font-size:0.85rem;"><i class="fas fa-question-circle"></i> ${isEn ? 'Next Question' : 'السؤال التالي'}:</strong>
                        <p class="question-text" style="margin:0;font-size:0.92rem;font-weight:600;color:#e2e8f0;">${quText}</p>
                    </div>`;
                }
                bubble.innerHTML = html;
            }
            container.scrollTop = container.scrollHeight;
        },
        async end() {
            if (!this.sessionId) return;
            if(this.timerInt) clearInterval(this.timerInt);
            if(this.synth) this.synth.cancel();
            // Stop hands-free listening and clear any pending silence timers
            if(this.silenceTimer) { clearTimeout(this.silenceTimer); this.silenceTimer = null; }
            this.isListening = false;
            if(this.recognition) { try { this.recognition.stop(); } catch(e) {} }
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
                preview.innerHTML = `<div class="preview-placeholder"><i class="fas fa-file-lines"></i><p>${TalentMetric.Lang.current === 'en' ? 'Start filling details to see live preview' : 'ابدأ بملء البيانات لرؤية المعاينة'}</p></div>`;
                return;
            }
            let html = '<div class="preview-name">' + (d.name || '') + '</div>';
            html += '<div class="preview-contact">' + [d.title, d.email, d.phone].filter(Boolean).join(' | ') + '</div>';
            if (d.summary) html += `<div class="preview-section"><h2>${TalentMetric.Lang.current === 'en' ? 'Professional Summary' : 'الملخص المهني'}</h2><p>` + d.summary + '</p></div>';
            if (d.experience.length) {
                html += `<div class="preview-section"><h2>${TalentMetric.Lang.current === 'en' ? 'Work Experience' : 'الخبرات العملية'}</h2>`;
                d.experience.forEach(e => { html += '<h3>' + e.title + ' - ' + e.company + '</h3><p style="color:#999;font-size:.75rem">' + e.from + ' - ' + e.to + '</p><p>' + e.description + '</p>'; });
                html += '</div>';
            }
            if (d.education.length) {
                html += `<div class="preview-section"><h2>${TalentMetric.Lang.current === 'en' ? 'Education' : 'التعليم'}</h2>`;
                d.education.forEach(e => { html += '<h3>' + e.degree + '</h3><p>' + e.school + ' - ' + e.year + '</p>'; });
                html += '</div>';
            }
            if (d.skills_tech) html += `<div class="preview-section"><h2>${TalentMetric.Lang.current === 'en' ? 'Technical Skills' : 'المهارات التقنية'}</h2><p>` + d.skills_tech + '</p></div>';
            if (d.skills_soft) html += `<div class="preview-section"><h2>${TalentMetric.Lang.current === 'en' ? 'Soft Skills' : 'المهارات الشخصية'}</h2><p>` + d.skills_soft + '</p></div>';
            if (d.languages) html += `<div class="preview-section"><h2>${TalentMetric.Lang.current === 'en' ? 'Languages' : 'اللغات'}</h2><p>` + d.languages + '</p></div>';
            preview.innerHTML = html;
        },
        async generate() {
            const data = this.getData();
            if (!data.name) { TalentMetric.toast(TalentMetric.Lang.current === 'en' ? 'Please fill in your name first' : 'يرجى إدخال الاسم على الأقل', 'error'); return; }
            TalentMetric.showLoading();
            try {
                const result = await TalentMetric.api('/api/resume/generate', { method: 'POST', body: JSON.stringify({ ...data, lang: TalentMetric.Lang.current }) });
                if (result.enhancements?.professional_summary) {
                    document.getElementById('resSummary').value = result.enhancements.professional_summary;
                }
                this.updatePreview();
                document.getElementById('exportPdfBtn').style.display = 'inline-flex';
                TalentMetric.toast(TalentMetric.Lang.current === 'en' ? 'Resume optimized successfully!' : 'تم تحسين السيرة الذاتية بنجاح!', 'success');
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
                TalentMetric.toast(TalentMetric.Lang.current === 'en' ? 'Resume downloaded!' : 'تم تصدير السيرة الذاتية!', 'success');
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
            
            const loadBtn = document.getElementById('loadAssessedSkillsBtn');
            if (loadBtn) {
                loadBtn.addEventListener('click', () => {
                    const saved = localStorage.getItem('talentmetric_user_skills');
                    if (saved) {
                        try {
                            const skills = JSON.parse(saved);
                            if (skills && skills.length > 0) {
                                const names = skills.map(s => s.name).join(', ');
                                const textarea = document.getElementById('careerSkills');
                                if (textarea) {
                                    textarea.value = names;
                                    textarea.classList.add('flash-glow');
                                    setTimeout(() => textarea.classList.remove('flash-glow'), 1000);
                                    TalentMetric.toast(TalentMetric.Lang.current === 'en' ? 'Skills imported successfully!' : 'تم استيراد المهارات بنجاح!', 'success');
                                }
                            } else {
                                this.showNoSkillsToast();
                            }
                        } catch (e) {
                            this.showNoSkillsToast();
                        }
                    } else {
                        this.showNoSkillsToast();
                    }
                });
            }
        },
        showNoSkillsToast() {
            TalentMetric.toast(
                TalentMetric.Lang.current === 'en' 
                    ? 'No assessed skills found. Please assess your skills first in the "Skills Assessment" page.' 
                    : 'لم يتم العثور على مهارات مقيمة. يرجى تقييم مهاراتك أولاً في صفحة "تقييم المهارات".', 
                'warning'
            );
        },
        async recommend() {
            const skills = document.getElementById('careerSkills').value.trim().split(/[,،]+/).map(s => s.trim()).filter(Boolean);
            const interests = document.getElementById('careerInterests').value.trim();
            const experience = parseInt(document.getElementById('careerExperience').value) || 0;
            if (skills.length === 0) { TalentMetric.toast(TalentMetric.Lang.current === 'en' ? 'Please fill in your current skills' : 'يرجى إدخال مهاراتك', 'error'); return; }
            TalentMetric.showLoading();
            try {
                const result = await TalentMetric.api('/api/career/recommend', {
                    method: 'POST', body: JSON.stringify({ skills, interests, experience_years: experience, lang: TalentMetric.Lang.current })
                });
                this.showResults(result);
            } catch (err) { TalentMetric.toast(err.error || 'خطأ', 'error'); }
            finally { TalentMetric.hideLoading(); }
        },
        showResults(data) {
            const isEn = TalentMetric.Lang.current === 'en';
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
                    <div class="career-detail"><i class="fas fa-money-bill-wave"></i> ${isEn ? 'Salary: ' : 'الراتب: '} ${p.salary_range || (isEn ? 'Not set' : 'غير محدد')}</div>
                    <div class="career-detail"><i class="fas fa-chart-line"></i> ${isEn ? 'Outlook: ' : 'الطلب المستقبلي: '} ${p.growth_outlook || (isEn ? 'Not set' : 'غير محدد')}</div>
                    <div class="career-skills">${(p.required_skills || []).map(s => '<span>' + s + '</span>').join('')}</div>
                </div>
            `).join('');
        }
    },

    /* ═══════ INTERVIEW HISTORY MODULE ═══════ */
    History: {
        init() {
            if (!TalentMetric.requireAuth()) return;
            this.loadHistory();
        },
        async loadHistory() {
            const loading = document.getElementById('historyLoading');
            const empty = document.getElementById('historyEmpty');
            const list = document.getElementById('historyList');
            const count = document.getElementById('sessionCount');
            if (!list) return;
            
            try {
                const data = await TalentMetric.api('/api/interview/history');
                if (loading) loading.style.display = 'none';
                
                const items = data.items || [];
                if (items.length === 0) {
                    if (empty) empty.style.display = 'block';
                    list.style.display = 'none';
                } else {
                    if (empty) empty.style.display = 'none';
                    list.style.display = 'block';
                    
                    const isEn = TalentMetric.Lang.current === 'en';
                    if (count) {
                        count.textContent = isEn ? `${data.total || items.length} Sessions` : `${data.total || items.length} جلسة`;
                    }
                    
                    // Render Cards
                    const toolbar = list.querySelector('.section-toolbar');
                    const cards = list.querySelectorAll('.history-card');
                    cards.forEach(c => c.remove());
                    
                    items.forEach(item => {
                        const score = item.overall_score || 0;
                        const scoreClass = score >= 8 ? 'score-high' : score >= 6 ? 'score-mid' : 'score-low';
                        const modeIcon = item.mode === 'video' ? 'fa-video' : 'fa-comments';
                        const modeText = item.mode === 'video' 
                            ? (isEn ? 'Video' : 'فيديو') 
                            : (isEn ? 'Chat' : 'محادثة');
                            
                        const card = document.createElement('div');
                        card.className = 'history-card';
                        card.dataset.id = item.id;
                        
                        card.innerHTML = `
                            <div class="history-card-header">
                                <div class="history-card-title">${item.role || (isEn ? 'General' : 'عام')}</div>
                                <div class="history-card-meta">
                                    <span class="history-date">${new Date(item.created_at).toLocaleDateString(isEn ? 'en-US' : 'ar-SA', { year: 'numeric', month: 'short', day: 'numeric' })}</span>
                                    <span class="score-badge ${scoreClass}">${score}/10</span>
                                </div>
                            </div>
                            <div class="history-tags">
                                <span class="tag-chip"><i class="fas fa-layer-group"></i> ${item.field || (isEn ? 'General' : 'عام')}</span>
                                <span class="tag-chip"><i class="fas ${modeIcon}"></i> ${modeText}</span>
                            </div>
                            <button class="toggle-details-btn">
                                <i class="fas fa-chevron-down"></i>
                                <span>${isEn ? 'View Analysis Details' : 'عرض تفاصيل التحليل'}</span>
                            </button>
                            <div class="history-details">
                                <div style="margin-bottom: 1rem; font-size: 0.9rem; color: var(--text-muted); line-height: 1.5;">
                                    <strong>${isEn ? 'Summary:' : 'الملخص:'}</strong> ${item.summary || ''}
                                </div>
                                <div class="detail-group strengths">
                                    <h4><i class="fas fa-circle-check"></i> ${isEn ? 'Strengths' : 'نقاط القوة'}</h4>
                                    <ul class="detail-list strengths-list">
                                        ${(item.strengths || []).map(s => `<li>${s}</li>`).join('')}
                                    </ul>
                                </div>
                                <div class="detail-group improvements">
                                    <h4><i class="fas fa-circle-exclamation"></i> ${isEn ? 'Areas for Improvement' : 'نقاط التحسين'}</h4>
                                    <ul class="detail-list improvements-list">
                                        ${(item.improvements || []).map(i => `<li>${i}</li>`).join('')}
                                    </ul>
                                </div>
                                <div class="detail-group tips">
                                    <h4><i class="fas fa-lightbulb"></i> ${isEn ? 'Tips for Success' : 'نصائح للنجاح'}</h4>
                                    <ul class="detail-list tips-list">
                                        ${(item.tips || []).map(t => `<li>${t}</li>`).join('')}
                                    </ul>
                                </div>
                            </div>
                        `;
                        
                        // Accordion collapsible trigger click logic
                        const toggleBtn = card.querySelector('.toggle-details-btn');
                        const details = card.querySelector('.history-details');
                        
                        const toggle = (e) => {
                            e.stopPropagation();
                            const isOpen = details.classList.toggle('open');
                            toggleBtn.classList.toggle('open', isOpen);
                            toggleBtn.querySelector('span').textContent = isOpen 
                                ? (isEn ? 'Hide Analysis Details' : 'إخفاء تفاصيل التحليل')
                                : (isEn ? 'View Analysis Details' : 'عرض تفاصيل التحليل');
                        };
                        
                        card.addEventListener('click', toggle);
                        toggleBtn.addEventListener('click', toggle);
                        
                        list.appendChild(card);
                    });
                }
            } catch(err) {
                console.error(err);
                if (loading) loading.style.display = 'none';
                TalentMetric.toast(TalentMetric.Lang.current === 'en' ? 'Failed to load history' : 'تعذر تحميل السجل', 'error');
            }
        }
    },

    /* ═══════ USER PROFILE SETTINGS MODULE ═══════ */
    Profile: {
        async init() {
            if (!TalentMetric.requireAuth()) return;
            
            const user = TalentMetric.getUser();
            if (user) {
                this.renderUserProfile(user);
            }
            
            // Load dashboard stats and member date
            this.loadProfileData();
            
            // Hook settings clicks
            document.getElementById('saveProfileBtn')?.addEventListener('click', () => this.saveProfile());
            document.getElementById('changePasswordBtn')?.addEventListener('click', () => this.changePassword());
        },
        
        renderUserProfile(user) {
            const nameEl = document.getElementById('profileName');
            const emailEl = document.getElementById('profileEmail');
            const initials = document.getElementById('profileAvatarInitials');
            const name = document.getElementById('profileAvatarName');
            const email = document.getElementById('profileAvatarEmail');
            
            if (nameEl) nameEl.value = user.name || '';
            if (emailEl) emailEl.value = user.email || '';
            if (name) name.textContent = user.name || '—';
            if (email) email.textContent = user.email || '—';
            if (initials && user.name) {
                initials.textContent = user.name.trim().charAt(0).toUpperCase();
            }
        },
        
        async loadProfileData() {
            try {
                const data = await TalentMetric.api('/api/dashboard/stats');
                
                const interviews = document.getElementById('profileInterviews');
                const assessments = document.getElementById('profileAssessments');
                const memberSince = document.getElementById('memberSince');
                
                if (interviews) interviews.textContent = data.stats.interviews || 0;
                if (assessments) assessments.textContent = data.stats.assessments || 0;
                
                if (memberSince) {
                    const isEn = TalentMetric.Lang.current === 'en';
                    memberSince.textContent = new Date().toLocaleDateString(isEn ? 'en-US' : 'ar-SA', { year: 'numeric', month: 'long' });
                }
                
                if (data.user) {
                    this.renderUserProfile(data.user);
                    TalentMetric.setUser(data.user);
                }
            } catch(e) { console.error('Failed to load profile data:', e); }
        },
        
        async saveProfile() {
            const nameEl = document.getElementById('profileName');
            const emailEl = document.getElementById('profileEmail');
            const msgEl = document.getElementById('profileSaveMsg');
            if (!nameEl || !emailEl || !msgEl) return;
            
            const name = nameEl.value.trim();
            const email = emailEl.value.trim();
            const isEn = TalentMetric.Lang.current === 'en';
            
            if (!name || !email) {
                msgEl.textContent = isEn ? '✗ Please fill all fields' : '✗ يرجى ملء جميع الحقول';
                msgEl.className = 'save-msg error';
                return;
            }
            
            msgEl.textContent = isEn ? 'Saving...' : 'جاري الحفظ...';
            msgEl.className = 'save-msg';
            
            try {
                const result = await TalentMetric.api('/api/auth/profile', {
                    method: 'PUT',
                    body: JSON.stringify({ name, email })
                });
                
                if (result.ok && result.user) {
                    TalentMetric.setUser(result.user);
                    this.renderUserProfile(result.user);
                    msgEl.textContent = isEn ? '✓ Profile saved successfully!' : '✓ تم حفظ الملف الشخصي بنجاح!';
                    msgEl.className = 'save-msg success';
                }
            } catch(e) {
                msgEl.textContent = '✗ ' + (e.error || e.message || (isEn ? 'Failed to save' : 'تعذر الحفظ'));
                msgEl.className = 'save-msg error';
            }
            setTimeout(() => { msgEl.textContent = ''; msgEl.className = 'save-msg'; }, 4000);
        },
        
        async changePassword() {
            const curEl = document.getElementById('currentPassword');
            const newEl = document.getElementById('newPassword');
            const confEl = document.getElementById('confirmPassword');
            const msgEl = document.getElementById('passwordChangeMsg');
            if (!curEl || !newEl || !confEl || !msgEl) return;
            
            const current_password = curEl.value;
            const new_password = newEl.value;
            const confirm = confEl.value;
            const isEn = TalentMetric.Lang.current === 'en';
            
            if (!current_password || !new_password || !confirm) {
                msgEl.textContent = isEn ? '✗ Please fill all fields' : '✗ يرجى ملء جميع الحقول';
                msgEl.className = 'save-msg error';
                return;
            }
            
            if (new_password !== confirm) {
                msgEl.textContent = isEn ? '✗ Passwords do not match' : '✗ كلمات المرور غير متطابقة';
                msgEl.className = 'save-msg error';
                return;
            }
            
            msgEl.textContent = isEn ? 'Updating...' : 'جاري التحديث...';
            msgEl.className = 'save-msg';
            
            try {
                const result = await TalentMetric.api('/api/auth/profile', {
                    method: 'PUT',
                    body: JSON.stringify({ current_password, new_password })
                });
                
                if (result.ok) {
                    msgEl.textContent = isEn ? '✓ Password changed successfully!' : '✓ تم تغيير كلمة المرور بنجاح!';
                    msgEl.className = 'save-msg success';
                    curEl.value = '';
                    newEl.value = '';
                    confEl.value = '';
                }
            } catch(e) {
                msgEl.textContent = '✗ ' + (e.error || e.message || (isEn ? 'Failed to change password' : 'تعذر تغيير كلمة المرور'));
                msgEl.className = 'save-msg error';
            }
            setTimeout(() => { msgEl.textContent = ''; msgEl.className = 'save-msg'; }, 4000);
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
            document.getElementById('fetchOpenRouterModels')?.addEventListener('click', () => this.fetchOpenRouterModels());
            document.getElementById('changeAdminPasswordBtn')?.addEventListener('click', () => this.changePassword());

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

            // OpenRouter Provider Dropdown Filter
            const orFilter = document.getElementById('openrouterProviderFilter');
            if (orFilter) {
                orFilter.addEventListener('change', () => {
                    const filterVal = orFilter.value;
                    const card = orFilter.closest('.provider-card');
                    if (!card) return;

                    // 1. Filter static quick-select chips
                    const staticArea = card.querySelector('.model-chips-area');
                    if (staticArea) {
                        const labels = staticArea.querySelectorAll('.chip-group-label');
                        const chips = staticArea.querySelectorAll('.model-chip');

                        labels.forEach(lbl => {
                            const group = lbl.dataset.group;
                            if (filterVal === 'all' || group === filterVal) {
                                lbl.style.display = 'block';
                            } else {
                                lbl.style.display = 'none';
                            }
                        });

                        chips.forEach(chip => {
                            const model = chip.dataset.model || '';
                            const matches = filterVal === 'all' ||
                                            model.startsWith(filterVal + '/') ||
                                            (filterVal === 'meta-llama' && model.startsWith('meta-llama/')) ||
                                            (filterVal === 'mistral' && model.startsWith('mistralai/')) ||
                                            (filterVal === 'x-ai' && (model.startsWith('x-ai/') || model.startsWith('microsoft/') || model.startsWith('cohere/')));

                            if (matches) {
                                chip.style.display = 'inline-block';
                            } else {
                                chip.style.display = 'none';
                            }
                        });
                    }

                    // 2. Filter dynamic fetched chips
                    const dynamicChips = card.querySelectorAll('#openrouterModelsChips .model-chip');
                    dynamicChips.forEach(chip => {
                        const model = chip.dataset.model || '';
                        const matches = filterVal === 'all' ||
                                        model.startsWith(filterVal + '/') ||
                                        (filterVal === 'meta-llama' && model.startsWith('meta-llama/')) ||
                                        (filterVal === 'mistral' && model.startsWith('mistralai/')) ||
                                        (filterVal === 'x-ai' && (model.startsWith('x-ai/') || model.startsWith('microsoft/') || model.startsWith('cohere/')));

                        if (matches) {
                            chip.style.display = 'inline-block';
                        } else {
                            chip.style.display = 'none';
                        }
                    });
                });
            }

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
                        // Fix for array chip bug mapping simple strings
                        chips.innerHTML = list.map(m => {
                            const name = typeof m === 'object' ? (m.name || m.id || '') : m;
                            return `<button class="model-chip" data-model="${name}" data-provider="${provider}">${name}</button>`;
                        }).join('');
                    }
                    container.classList.add('visible');
                }
            } catch(e) { console.error(e); }
        },
        async fetchOpenRouterModels() {
            const btn = document.getElementById('fetchOpenRouterModels');
            if (!btn) return;
            const originalHtml = btn.innerHTML;
            btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Loading...';
            btn.disabled = true;
            try {
                const resp = await fetch('/api/admin/openrouter-models', { headers: { 'Authorization': 'Bearer ' + this.token } });
                if (resp.status === 401) { sessionStorage.removeItem('talentmetric_admin_token'); window.location.href = '/login'; return; }
                const data = await resp.json();
                const list = data.models || [];
                 const chips = document.getElementById('openrouterModelsChips');
                 const container = document.getElementById('openrouterModelsList');
                 if (chips && container) {
                     if (list.length === 0) {
                         chips.innerHTML = '<span style="color:var(--text-muted);font-size:.8rem">No models found or error. Check key.</span>';
                     } else {
                         chips.innerHTML = list.map(m => {
                             const icon = m.vision ? '👁 ' : '';
                             const vClass = m.vision ? ' vision-chip' : '';
                             return `<button class="model-chip${vClass}" data-model="${m.id}" data-provider="openrouter" title="Context: ${m.context || 'unknown'}">${icon}${m.name || m.id}</button>`;
                         }).join('');
                     }
                     container.classList.add('visible');
                     // Trigger active filter automatically on newly fetched models
                     document.getElementById('openrouterProviderFilter')?.dispatchEvent(new Event('change'));
                 }
            } catch(e) {
                console.error(e);
                TalentMetric.toast('Failed to fetch OpenRouter models', 'error');
            } finally {
                btn.innerHTML = originalHtml;
                btn.disabled = false;
            }
        },
        async changePassword() {
            const curInp = document.getElementById('adminCurrentPassword');
            const newInp = document.getElementById('adminNewPassword');
            const msgEl = document.getElementById('adminPasswordMsg');
            if (!curInp || !newInp || !msgEl) return;
            
            const curPass = curInp.value;
            const newPass = newInp.value;
            if (!curPass || !newPass) {
                msgEl.textContent = 'Please fill all fields.';
                msgEl.style.color = 'var(--danger)';
                return;
            }
            try {
                const resp = await fetch('/api/admin/change-password', {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + this.token },
                    body: JSON.stringify({ current_password: curPass, new_password: newPass })
                });
                if (resp.status === 401) { sessionStorage.removeItem('talentmetric_admin_token'); window.location.href = '/login'; return; }
                const result = await resp.json();
                if (resp.ok && result.ok) {
                    msgEl.textContent = '✓ Password updated successfully!';
                    msgEl.style.color = 'var(--success)';
                    curInp.value = '';
                    newInp.value = '';
                } else {
                    msgEl.textContent = '✗ ' + (result.error || 'Failed');
                    msgEl.style.color = 'var(--danger)';
                }
            } catch(e) {
                msgEl.textContent = '✗ Error: ' + e.message;
                msgEl.style.color = 'var(--danger)';
            }
            setTimeout(() => { msgEl.textContent = ''; }, 4000);
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
            const featureIcons = {
                'default': 'fa-layer-group', 'skills': 'fa-chart-bar',
                'chat_interview': 'fa-comments', 'video_interview': 'fa-video',
                'resume': 'fa-file-lines', 'career': 'fa-road'
            };
            const providers = ['openrouter', 'openai', 'huggingface', 'ollama', 'lmstudio'];
            const providerLabels = {
                'openrouter': '☁ OpenRouter', 'openai': '☁ OpenAI',
                'huggingface': '☁ HuggingFace', 'ollama': '🖥 Ollama', 'lmstudio': '🖥 LM Studio'
            };

            // Build Main Routing Table
            const tbody = document.getElementById('adminRoutingRows');
            if(tbody) {
                const listMap = {
                    'openrouter': 'orModelsList',
                    'openai': 'oaiModelsList',
                    'huggingface': 'hfModelsList',
                    'ollama': 'commonModelsList',
                    'lmstudio': 'commonModelsList'
                };
                tbody.innerHTML = features.map(f => {
                    const curOverride = data.routing_overrides?.[f] || {};
                    const options = `<option value="">— Active Provider —</option>` + providers.map(p => `<option value="${p}" ${curOverride.provider===p?'selected':''}>${providerLabels[p]||p}</option>`).join('');
                    const listId = listMap[curOverride.provider] || 'commonModelsList';
                    return `
                        <tr>
                            <td><span class="feature-label"><i class="fas ${featureIcons[f]||'fa-cog'}"></i>${featureLabels[f]}</span></td>
                            <td><select class="routing-provider-select" data-feature="${f}">${options}</select></td>
                            <td><input type="text" class="routing-model-input" list="${listId}" data-feature="${f}" value="${curOverride.model||''}" placeholder="Inherit default"></td>
                        </tr>
                    `;
                }).join('');

                // Wire up change listener on provider selects to switch list dynamic
                tbody.querySelectorAll('.routing-provider-select').forEach(select => {
                    select.addEventListener('change', (e) => {
                        const feature = e.target.dataset.feature;
                        const provider = e.target.value;
                        const input = tbody.querySelector(`.routing-model-input[data-feature="${feature}"]`);
                        if (input) {
                            input.setAttribute('list', listMap[provider] || 'commonModelsList');
                        }
                    });
                });
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
            sel.innerHTML = providers.map(p => `<option value="${p}">${providerLabels[p]||p}</option>`).join('');
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
            if (el) { el.textContent = 'Testing…'; el.style.color = 'var(--text-muted)'; }

            const keyInp  = document.querySelector(`.admin-provider-key[data-provider="${name}"]`);
            const urlInp  = document.querySelector(`.admin-provider-input[data-provider="${name}"][data-field="base_url"]`);
            const modelInp = document.querySelector(`.admin-provider-input[data-provider="${name}"][data-field="model"]`);
            const payload = { provider: name };
            if (keyInp   && keyInp.value)   payload.api_key  = keyInp.value;
            if (urlInp   && urlInp.value)   payload.base_url = urlInp.value;
            if (modelInp && modelInp.value) payload.model    = modelInp.value;

            try {
                const resp = await fetch('/api/admin/test', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + this.token },
                    body: JSON.stringify(payload)
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

    // Initialize bilingual layout engine
    TalentMetric.Lang.init();

    // Navbar scroll effect
    window.addEventListener('scroll', () => {
        const nav = document.getElementById('navbar');
        if (nav) nav.classList.toggle('scrolled', window.scrollY > 50);
    });

    // Mobile menu toggle
    const mobileBtn = document.getElementById('mobileMenuBtn');
    if (mobileBtn) {
        mobileBtn.addEventListener('click', () => {
            document.getElementById('navLinks').classList.toggle('open');
        });
    }

    // Standardized Global Logout
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
            el.textContent = Math.floor(current).toLocaleString(TalentMetric.Lang.current === 'en' ? 'en-US' : 'ar-EG');
        }, 30);
    });

    // Page-specific initialization routing
    if (path === '/login') TalentMetric.Auth.init();
    else if (path === '/dashboard') TalentMetric.Dashboard.init();
    else if (path === '/skills') TalentMetric.Skills.init();
    else if (path === '/interview') TalentMetric.Interview.init();
    else if (path === '/resume') TalentMetric.Resume.init();
    else if (path === '/career') TalentMetric.Career.init();
    else if (path === '/history') TalentMetric.History.init();
    else if (path === '/profile') TalentMetric.Profile.init();
    else if (path === '/admin') TalentMetric.Admin.init();
});
