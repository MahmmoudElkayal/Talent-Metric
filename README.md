# Talent Metric 🚀

**Talent Metric** is a powerful, AI-driven career development platform designed to help job seekers evaluate their skills, practice interviews, and generate professional resumes using state-of-the-art AI models.

Built with a lightweight Flask backend and a lightning-fast Vanilla JS frontend, Talent Metric features a highly configurable, multi-provider AI routing engine that allows administrators to seamlessly switch between cloud AI providers and local, privacy-focused models.

## ✨ Key Features

- **Multi-Provider AI Engine:** Out-of-the-box support for OpenRouter, OpenAI, Hugging Face, Ollama, and LM Studio.
- **Dynamic Routing:** Route specific features to different AI models (e.g., use local `llama3` for mock interviews, and `gpt-4o` for resume generation).
- **Mock Interviews (Chat & Video):** Practice answering interview questions with an AI recruiter using real-time text-to-speech and speech-to-text.
- **Skills Assessment:** Analyze your current skills against your target role to generate a personalized learning roadmap.
- **Smart Resume Builder:** Automatically generate, improve, and export ATS-friendly resumes to PDF.
- **Career Path Recommendations:** Discover tailored career trajectories based on your unique skill set.
- **Admin Control Panel:** A secure dashboard to manage API keys, test connections, view local models, and configure site-wide settings dynamically.

## 🛠️ Technology Stack

- **Backend:** Python, Flask, ReportLab (for PDF generation), Requests
- **Frontend:** HTML5, Vanilla JavaScript, CSS3 (Custom Design System)
- **AI Integrations:** OpenAI API, Hugging Face Hub API, Ollama Native API

## 🚀 Getting Started

### Prerequisites
- Python 3.10+
- (Optional) [Ollama](https://ollama.com/) or [LM Studio](https://lmstudio.ai/) for running local AI models.

### Installation

1. **Clone the repository:**
   ```bash
   git clone <your-repo-url>
   cd Talent-Metric
   ```

2. **Install Python dependencies:**
   ```bash
   pip install flask requests huggingface_hub reportlab
   ```

3. **Set Environment Variables (Optional):**
   ```bash
   # Set a custom admin password (default is 'admin123')
   export ADMIN_PASSWORD="your_secure_password"
   
   # Set Flask secret key
   export FLASK_SECRET="your_secret_key"
   ```

4. **Run the Server:**
   ```bash
   python AIWebbased.py
   ```

5. **Access the Application:**
   - **Main Site:** `http://localhost:5000`
   - **Admin Panel:** `http://localhost:5000/admin` *(Login with the password: `admin123`)*

## ⚙️ Configuration (Admin Panel)

The entire application can be configured via the built-in Admin Panel without modifying code:
1. Navigate to `/admin`.
2. **Provider Configuration:** Add your API keys for OpenRouter or HuggingFace, or set your base URLs for local providers like Ollama.
3. **Feature Routing:** Assign specific models to specific tasks (e.g., "Video Interview" uses `llama3`, "Resume Generation" uses `gpt-4o-mini`).
4. **Site Settings:** Customize the application name and default target roles globally.

## 📄 License
This project is open-source and available for educational and commercial use.
