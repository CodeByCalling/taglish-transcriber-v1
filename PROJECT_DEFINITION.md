# [cite_start]Project Specification: Taglish Meeting Transcriber [cite: 4]

[cite_start]**Project Manager:** Serge Santos [cite: 5]
[cite_start]**Target Users:** Church Staff & Ministry Leaders (Manila & Vallejo) [cite: 6]
[cite_start]**Core Objective:** Create a cost-effective, high-accuracy meeting transcription tool specifically designed for "Taglish" (Tagalog-English code-switching) and Filipino accents[cite: 7].

---

## [cite_start]1. Technical Architecture (The "Google Edition" Stack) [cite: 8]
[cite_start]**Goal:** A "Serverless" architecture that keeps costs low and leverages the Google ecosystem[cite: 9].

* [cite_start]**Development Environment:** Google Project IDX (formerly "Antigravity")[cite: 10].
* [cite_start]**Application Framework:** Streamlit (Python) - Chosen for rapid UI development[cite: 11].
* [cite_start]**Compute Engine:** Google Cloud Run - Runs the Python container; scales to zero when not in use[cite: 12].
* [cite_start]**AI Engine (Transcription):** OpenAI Whisper API (model="whisper-1" or large-v3)[cite: 13].
* [cite_start]**AI Engine (Speaker ID):** Pyannote.audio - For identifying "Speaker A" vs "Speaker B"[cite: 14].
* [cite_start]**Database:** Firebase Firestore - Stores metadata, transcript text, and speaker labels[cite: 15].
* [cite_start]**File Storage:** Firebase Storage - Stores the raw MP3/WAV audio files[cite: 16].
* [cite_start]**Audio Processing:** Pydub & FFmpeg - For splitting large files to prevent API crashes[cite: 17].

---

## [cite_start]2. User Interface (UI) Specifications [cite: 18]
[cite_start]The app is a Single Page Application (SPA) with three distinct "States"[cite: 19].

### [cite_start]State 1: The "Setup" View (Pre-Upload) [cite: 20]
[cite_start]**Visual Goal:** Clean, intimidating, and focused on context[cite: 21].

* **Top Navigation Bar:**
    * [cite_start]**Logo:** "🇵🇭 Transcriber" (Left aligned)[cite: 23].
    * [cite_start]**Login/Profile:** Small circle avatar (Right aligned)[cite: 24].
* [cite_start]**Sidebar (Settings):** [cite: 25]
    * **Model Selector:** Dropdown [Standard, High Accuracy (Slower)]. [cite_start]Default: High[cite: 26].
    * **Speaker Count Guess:** Number Input [4]. [cite_start]Label: "How many people (approx)?"[cite: 27].
    * **History Tab:** A list of the last 5 transcripts. [cite_start]Clicking one loads it[cite: 28].
* [cite_start]**Main Canvas (Center):** [cite: 29]
    * [cite_start]**Hero Text:** "Upload Church Meeting Recording"[cite: 30].
    * [cite_start]**The "Context" Box (Critical Feature):** A large text input field[cite: 31].
        * [cite_start]**Label:** "Meeting Context & Vocabulary"[cite: 32].
        * [cite_start]**Placeholder:** "Example: Budget planning, 'Tithe', 'Gawain', Pastor John, Vallejo campus..."[cite: 33].
        * [cite_start]**Tooltip:** "Helping the AI know these words improves Tagalog spelling"[cite: 34].
    * [cite_start]**Drop Zone:** A large, dashed-border box[cite: 35].
        * [cite_start]**Text:** "Drag & Drop MP3, WAV, or M4A here"[cite: 36].
        * [cite_start]**Limit:** "Max 500MB (System will auto-chunk)"[cite: 37].

### [cite_start]State 2: The "Processing" View (During Operation) [cite: 38]
**Visual Goal:** Transparency. [cite_start]The user must know the app hasn't crashed[cite: 39].

* [cite_start]**Status Header:** A colored banner (Blue) at the top reading "Processing Meeting... Please do not close this tab"[cite: 40, 41].
* [cite_start]**The "Pipeline" Progress Bar:** Shows 3 stages[cite: 42]:
    1.  [cite_start][✔] Uploading to Secure Storage (Firebase)[cite: 43].
    2.  [cite_start][===...] Segmentation (Slicing audio into 10-minute chunks)[cite: 44].
    3.  [cite_start][......] AI Transcription (Sending to Whisper)[cite: 45].
* [cite_start]**Live Terminal Log (Bottom):** A small, collapsible box showing real-time system thoughts (e.g., "Detected silence at 09:45...")[cite: 46, 47].

### State 3: The "Review Station" (Quality Assurance)
**Goal:** Allow users to rapidly validate and correct the AI draft.

* **Layout:** "Smart Segments" Vertical List.
    * Instead of one large text block, display the transcript as a list of editable text areas (one per sentence/segment).
* **Audio Sync Controls:**
    * **Segment Player:** Each text segment must have a dedicated `▶ Play` button that plays *only* that specific timestamp range (e.g., 00:12 -> 00:18).
    * **Speed Toggle:** Sidebar control to set audio speed (1.0x, 1.5x, 2.0x).
* **Visual Confidence cues:**
    * If Whisper's confidence score for a segment is low (< -0.5 logprob), change the border color of that text box to **Yellow** to alert the user.
* **Global Search & Replace:**
    * A tool to fix entities globally (e.g., Change "Pasta John" to "Pastor John" everywhere with one click).

---

## [cite_start]3. Functional Logic (The "Brain") [cite: 67]

### [cite_start]A. The "Taglish" Prompt Strategy [cite: 68]
Inject this System Prompt into every API call:
> [cite_start]"This is a meeting recording in Taglish, mixing Tagalog and English. The speakers have Filipino accents. Transcribe English segments in standard US English. Transcribe Tagalog segments using proper Filipino orthography. Do not translate. Recognize church terminology: [Insert User Context Here]." [cite: 69, 70]

### [cite_start]B. The "Anti-Crash" Chunking Logic [cite: 71]
[cite_start]To handle OpenAI's 25MB limit using `pydub`[cite: 72]:
1.  [cite_start]Detect file size[cite: 73].
2.  [cite_start]If > 25MB, scan for "Silence" (pauses > 1000ms)[cite: 74].
3.  [cite_start]Cut audio at silence to create <25MB chunks[cite: 75].
4.  [cite_start]Send chunks sequentially[cite: 76].
5.  [cite_start]Stitch text back together seamlessly[cite: 77].

### C. AI Post-Processing (The "Secretary" Features)
**Goal:** Convert raw transcripts into standard business outputs using LLMs (GPT-4 or Gemini 1.5 Pro).

**1. "One-Click" Output Formats:**
   The user can select from a dropdown to generate specific document types:

   * **📄 Executive Summary:** A 1-page high-level overview of the discussion.
   * **✅ Action Items & Owners:** A bulleted checklist of tasks, assigned owners, and deadlines detected in the conversation.
   * **📝 Standard Meeting Minutes:** Formal documentation including:
       * Date/Time/Attendees.
       * Agenda Items discussed.
       * Decisions made.
       * Action items.
   * **⛪ Sermon/Study Guide:** (Context-Specific) Extracts key scripture references, theological points, and life applications.

**2. The "Refinement" Workflow:**
   * **Step 1:** User reviews raw transcript in "Editor View" and corrects names/terms.
   * **Step 2:** User clicks "Generate Documents".
   * **Step 3:** System feeds the *corrected* transcript to the LLM with a specific "Format Prompt."
   * **Step 4:** System generates a downloadable `.docx` or PDF.

**3. Proposed Prompts (System Logic):**
   * *Action Item Prompt:* "Analyze the following transcript. Extract every specific task, the person responsible, and the mentioned deadline. Format as a checkbox list."
   * *Minutes Prompt:* "Summarize this meeting into formal minutes. Group by topic. Bold any final decisions."

---

## [cite_start]4. Security & Data (The "Vault") [cite: 78]

* **Authentication:** Currently "Open" (obscure URL) for internal testing. [cite_start]Future: Google Login via Firebase Auth[cite: 79].
* [cite_start]**API Key Security:** OpenAI API Key stored in Google Cloud Run Environment Variables (never in code)[cite: 80].
* **Data Retention:**
    * [cite_start]**Audio:** Auto-delete from Firebase Storage after 7 days[cite: 82].
    * [cite_start]**Transcripts:** Kept indefinitely in Firestore[cite: 83].

---

## [cite_start]5. Development Roadmap [cite: 84]

[cite_start]**Phase 1: The "Skeleton" (Days 1-2)** [cite: 85]
* [cite_start]Setup Project IDX environment[cite: 86].
* [cite_start]Connect `app.py` to OpenAI API[cite: 87].
* [cite_start]Build basic Streamlit UI (Upload + Output)[cite: 88].
* [cite_start]*Milestone:* Transcribe a small 2-minute test file[cite: 89].

[cite_start]**Phase 2: The "Muscle" (Days 3-4)** [cite: 90]
* [cite_start]Implement `pydub` chunking logic[cite: 91].
* [cite_start]Connect Firebase Storage for uploads[cite: 92].
* [cite_start]Add "Context" input box[cite: 93].
* [cite_start]*Milestone:* Transcribe a full 1-hour sermon/meeting[cite: 94].

[cite_start]**Phase 3: The "Cloud" (Day 5)** [cite: 95]
* [cite_start]Create Dockerfile[cite: 96].
* [cite_start]Deploy to Google Cloud Run[cite: 97].
* [cite_start]Set up IAM permissions for Firebase[cite: 98].
* [cite_start]*Milestone:* App is live via URL[cite: 99].