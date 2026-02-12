# 🛠️ Taglish Transcriber Setup Guide

This guide covers how to set up the development environment on a new machine (Mac, Windows, or Linux).

## 📋 Prerequisites
*   **Python 3.11** (Recommended)
*   **Git**

## 🚀 Installation Steps

### 1. Install System Dependencies (FFmpeg)
The app uses `pydub` for audio processing, which requires **FFmpeg** to be installed at the system level.

*   **Mac:** `brew install ffmpeg`
*   **Windows:** Download from [ffmpeg.org](https://ffmpeg.org/download.html) and add to your System PATH.
*   **Linux:** `sudo apt-get install ffmpeg`

### 2. Install Python Libraries
Navigate to the project folder and run:

```bash
pip install -r requirements.txt
```

### 3. Configure Secrets (Critical Step)
For security reasons, the following files are **not** in the repository. You must manually copy them from your primary developer machine or recreate them:

#### A. Environment Variables (`.env`)
1.  Copy `.env.example` to a new file named `.env`:
    ```bash
    cp .env.example .env
    ```
2.  Open `.env` and fill in your keys:
    *   `OPENAI_API_KEY`: Your OpenAI Secret Key.
    *   `APP_PASSWORD`: The password for the Streamlit app login.

#### B. Firebase Credentials (`serviceAccountKey.json`)
*   Place your **`serviceAccountKey.json`** file in the root directory of the project.
*   *Note: This file contains sensitive private keys for Firebase Admin access.*

## ▶️ Running the App

Once installed, verify everything works by running:

```bash
streamlit run app.py
```

## 🐳 Docker (Alternative)
You can also build the container locally:

```bash
docker build -t taglish-transcriber .
docker run -p 8080:8080 taglish-transcriber
```
