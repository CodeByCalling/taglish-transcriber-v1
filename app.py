import streamlit as st
import os
import traceback
import threading
import time
import json
from dotenv import load_dotenv
import openai
from pydub import AudioSegment
import math
import firebase_admin
from firebase_admin import credentials, firestore, storage
from datetime import datetime, timedelta

# Load environment variables
load_dotenv()

# Constants
BUCKET_NAME = "taglish-transcriber-v1.firebasestorage.app" 

# Configure Page
st.set_page_config(
    page_title="Taglish Meeting Transcriber",
    page_icon="🇵🇭",
    layout="wide"
)

# --- Security (The Gatekeeper) ---
def check_password():
    """Returns `True` if the user had the correct password."""
    
    # If no password is set in env, allow access (Dev Mode)
    # BUT in production, we must set APP_PASSWORD
    password_env = os.getenv("APP_PASSWORD")
    if not password_env:
        return True

    if st.session_state.get("authenticated", False):
        return True

    st.title("🔒 Login Required")
    password_input = st.text_input("Enter App Password", type="password")
    
    if st.button("Log In"):
        if password_input == password_env:
            st.session_state["authenticated"] = True
            st.rerun()
        else:
            st.error("Incorrect Password")
            
    return False

if not check_password():
    st.stop()

# --- Logic & State Management ---

def initialize_firebase():
    """
    Initializes Firebase Admin SDK if not already initialized.
    """
    if not firebase_admin._apps:
        try:
            # Dual Auth Strategy: Local Key vs Cloud Identity
            if os.path.exists("serviceAccountKey.json"):
                cred = credentials.Certificate("serviceAccountKey.json")
            else:
                # Production: Use Google Cloud Identity (ADC)
                print("🔑 Using Application Default Credentials (Cloud Run)")
                cred = credentials.ApplicationDefault()
                
            firebase_admin.initialize_app(cred, {
                'storageBucket': BUCKET_NAME 
            })
        except Exception as e:
            st.error(f"Failed to initialize Firebase: {e}")
            return None
    return firestore.client()

# Initialize Firebase on app load (Global Scope)
db = initialize_firebase()

def upload_to_firebase(local_path, destination_path):
    """
    Uploads a file to Firebase Storage.
    """
    try:
        # Explicitly call the bucket by name to avoid default config issues
        bucket = storage.bucket(name=BUCKET_NAME)
        blob = bucket.blob(destination_path)
        blob.upload_from_filename(local_path)
        # Make public for easy access (optional, usually keeps private)
        # blob.make_public() 
        return blob.public_url
    except Exception as e:
        st.error(f"Upload failed: {e}")
        return None


def generate_signed_upload_url(filename, content_type="audio/mpeg"):
    """Generates a Signed URL for Direct-to-GCS upload."""
    try:
        bucket = storage.bucket(name=BUCKET_NAME)
        blob = bucket.blob(f"uploads/{filename}")
        
        url = blob.generate_signed_url(
            version="v4",
            expiration=timedelta(minutes=15),
            method="PUT",
            content_type=content_type
        )
        return url, blob.name
    except Exception as e:
        st.error(f"Signed URL Error: {e}")
        return None, None

def format_timestamp(seconds):
    """Converts seconds to [MM:SS] format."""
    minutes = int(seconds // 60)
    sec = int(seconds % 60)
    return f"[{minutes:02d}:{sec:02d}]"

def transcribe_segment_with_timestamps(client, file_path, system_prompt, offset_seconds, temperature):
    """Transcribes a chunk and returns text with global timestamps."""
    try:
        with open(file_path, "rb") as audio_file:
            response = client.audio.transcriptions.create(
                model="whisper-1", 
                file=audio_file, 
                prompt=system_prompt,
                temperature=temperature,
                response_format="verbose_json" # Critical for timestamps
            )
            
            segment_text = ""
            for segment in response.segments:
                start_time = segment.start + offset_seconds
                text = segment.text.strip()
                if text:
                    ts = format_timestamp(start_time)
                    segment_text += f"**{ts}** {text}\n\n"
            
            return segment_text
    except Exception as e:
        print(f"Error in segment: {e}")
        return f"\n⚠️ [SYSTEM ERROR at {format_timestamp(offset_seconds)}]: {str(e)}\n"

def background_worker(job_id, filename, context, temperature_setting, db):
    """
    The function that runs in a separate thread (The 'Plug-Out' Logic).
    Now with streaming chunks and keepalive heartbeat for Cloud Run.
    """
    try:
        print(f"Starting Background Job {job_id} for {filename}")
        doc_ref = db.collection("transcripts").document(job_id)
        doc_ref.update({
            "status": "processing", 
            "progress": 0, 
            "message": "Starting engine...",
            "last_heartbeat": datetime.now()
        })

        # 1. Download from Storage (Direct Upload Location)
        bucket = storage.bucket(name=BUCKET_NAME)
        blob = bucket.blob(f"uploads/{filename}")
        local_filename = f"temp_bg_{filename}"
        
        # Detect original file format
        original_format = "mp3"  # default
        if filename.lower().endswith(".m4a"):
            original_format = "m4a"
        elif filename.lower().endswith(".wav"):
            original_format = "wav"
        
        doc_ref.update({"message": "Downloading from cloud storage..."})
        blob.download_to_filename(local_filename)
        
        doc_ref.update({"message": "Analyzing audio file..."})
        
        # 2. Get audio metadata WITHOUT loading entire file into memory
        # Use pydub's lightweight probe first
        try:
            from pydub.utils import mediainfo
            info = mediainfo(local_filename)
            duration_ms = float(info.get('duration', 0)) * 1000  # Convert to milliseconds
        except Exception as e:
            # Fallback: Load just to get duration then release memory
            print(f"Mediainfo failed, using fallback: {e}")
            audio_temp = AudioSegment.from_file(local_filename)
            duration_ms = len(audio_temp)
            del audio_temp  # Release memory immediately
        
        chunk_length_ms = 10 * 60 * 1000  # 10 mins
        chunks = math.ceil(duration_ms / chunk_length_ms)
        
        doc_ref.update({
            "message": f"File duration: {int(duration_ms/1000/60)} minutes. Processing {chunks} chunks...",
            "total_chunks": chunks
        })
        
        # 3. Setup OpenAI
        api_key = os.getenv("OPENAI_API_KEY", "").strip()
        client = openai.OpenAI(api_key=api_key)
        system_prompt = (
            "You are an expert transcriber for Taglish (Tagalog-English) church meetings. "
            "Transcribe exactly what is said. "
            "Context: " + context
        )

        full_transcript = ""
        
        # 4. Process Loop - Load and process ONE chunk at a time
        for i in range(chunks):
            # Update heartbeat to keep Cloud Run alive
            doc_ref.update({
                "progress": int((i / chunks) * 100),
                "message": f"Transcribing chunk {i+1} of {chunks}...",
                "last_heartbeat": datetime.now()
            })
            
            start_ms = i * chunk_length_ms
            end_ms = min((i + 1) * chunk_length_ms, duration_ms)
            
            # Load ONLY this chunk into memory
            audio_chunk = AudioSegment.from_file(local_filename)[start_ms:end_ms]
            
            # Preserve original format - no conversion needed
            chunk_name = f"chunk_{job_id}_{i}.{original_format}"
            audio_chunk.export(chunk_name, format=original_format)
            
            # Release chunk from memory immediately
            del audio_chunk
            
            # Offset logic for global timestamps
            offset_seconds = (start_ms / 1000)
            chunk_text = transcribe_segment_with_timestamps(
                client, chunk_name, system_prompt, offset_seconds, temperature_setting
            )
            full_transcript += chunk_text
            
            # Clean up chunk file
            if os.path.exists(chunk_name):
                os.remove(chunk_name)
            
            # Periodic save to Firestore (every 5 chunks) for crash recovery
            if (i + 1) % 5 == 0:
                doc_ref.update({"transcript": full_transcript})
        
        # 5. Finish
        doc_ref.update({
            "status": "completed",
            "progress": 100,
            "message": "Done!",
            "transcript": full_transcript,
            "last_heartbeat": datetime.now()
        })
        
        # Clean up downloaded file
        if os.path.exists(local_filename):
            os.remove(local_filename)
            
        print(f"Job {job_id} Completed Success.")

    except Exception as e:
        error_msg = f"Background Job Failed: {e}"
        print(error_msg)
        traceback.print_exc()
        # Try to update DB with error
        try:
            doc_ref.update({
                "status": "error", 
                "message": str(e),
                "last_heartbeat": datetime.now()
            })
        except:
            pass

# --- UI Layout ---

# --- UI Layout ---

# Sidebar
with st.sidebar:
    st.header("Settings")
    model_labels = ["whisper-1 (High Accuracy)", "whisper-1 (Fast/Creative)"]
    model_selection = st.selectbox("Model", model_labels, index=0)
    
    # Map selection to temperature
    temp_map = {
        "whisper-1 (High Accuracy)": 0.0,
        "whisper-1 (Fast/Creative)": 0.4
    }
    selected_temp = temp_map[model_selection]
    
    st.divider()
    st.subheader("History")

    # History Logic
    if db:
        history_docs = db.collection("transcripts").order_by("upload_date", direction=firestore.Query.DESCENDING).limit(10).stream()
        for doc in history_docs:
            data = doc.to_dict()
            fname = data.get('filename', 'Unknown File')
            status = data.get('status', 'unknown')
            upload_date = data.get('upload_date')
            date_str = upload_date.strftime("%Y-%m-%d %H:%M") if upload_date else "Unknown Date"
            
            with st.expander(f"{date_str} - {fname}"):
                st.caption(f"Status: {status}")
                
                col_h1, col_h2 = st.columns(2)
                
                with col_h1:
                    if status == 'completed':
                        st.download_button("Download", data.get('transcript', ''), file_name=f"{fname}.txt", key=f"dl_{doc.id}")
                    elif status == 'processing':
                         st.progress(data.get('progress', 0))
                         if st.button("Track", key=f"track_{doc.id}"):
                            st.session_state['job_id'] = doc.id
                            st.rerun()
                
                with col_h2:
                    if st.button("🗑️ Delete", key=f"del_{doc.id}"):
                        db.collection("transcripts").document(doc.id).delete()
                        # If we just deleted the active job, reset state
                        if st.session_state.get('job_id') == doc.id:
                            del st.session_state['job_id']
                        st.rerun()

# --- Main UI Functions ---

def render_upload_ui():
    st.markdown("### 1. Direct-to-Cloud Upload")
    context_input = st.text_area("Meeting Context", placeholder="Budget, Tithe, Pastor John...")
    
    # Step 1: Define Filename
    col1, col2 = st.columns([3, 1])
    with col1:
        filename_input = st.text_input("Target Filename (Optional)", placeholder="MyMeeting")
    with col2:
         st.text(" ") # Spacer
    
    if st.button("Generate Secure Link 🔗"):
        # Auto-Name Logic
        final_filename = filename_input.strip()
        
        # 1. Handle Empty Input -> Timestamped Filename
        if not final_filename:
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            final_filename = f"recording_{timestamp}.mp3"
        
        # 2. Handle Missing Extension -> Append .mp3
        elif "." not in final_filename:
            final_filename += ".mp3"
            
        # 3. Handle Existing Extension (Respect User Choice)
        # (No change needed, if they typed meeting.m4a, we keep it)

        # Detect Mime (for the Browser Upload)
        mime_type = "audio/mpeg" 
        if final_filename.lower().endswith(".m4a"):
            mime_type = "audio/mp4"
        elif final_filename.lower().endswith(".wav"):
           mime_type = "audio/wav"

        signed_url, blob_name = generate_signed_upload_url(final_filename, content_type=mime_type)
        
        if signed_url:
            st.success(f"Ready to upload: {final_filename}")
            st.session_state['signed_url'] = signed_url
            st.session_state['target_filename'] = final_filename
            st.session_state['blob_name'] = blob_name
            st.session_state['mime_type'] = mime_type

    # Step 2: HTML Upload
    if 'signed_url' in st.session_state:
        st.markdown(f"**Target:** `{st.session_state['target_filename']}`")
        
        # JS Uploader
        html_code = f"""
        <html>
        <body>
            <input type="file" id="fileInput" />
            <button onclick="uploadFile()">⬆️ Upload Now</button>
            <div id="status"></div>
            <progress id="progressBar" value="0" max="100" style="width:100%; display:none;"></progress>
            
            <script>
            function uploadFile() {{
                var fileInput = document.getElementById('fileInput');
                if (fileInput.files.length === 0) {{
                    document.getElementById('status').innerText = '⚠️ Please select a file first!';
                    return;
                }}
                var file = fileInput.files[0];
                var url = "{st.session_state['signed_url']}";
                var serverMime = "{st.session_state['mime_type']}"; 
                
                var xhr = new XMLHttpRequest();
                xhr.upload.onprogress = function(e) {{
                    if (e.lengthComputable) {{
                        var percentComplete = (e.loaded / e.total) * 100;
                        document.getElementById('progressBar').value = percentComplete;
                        document.getElementById('progressBar').style.display = 'block';
                        document.getElementById('status').innerText = 'Uploading: ' + Math.round(percentComplete) + '%';
                    }}
                }};
                xhr.onload = function() {{
                    if (xhr.status == 200 || xhr.status == 201) {{
                        document.getElementById('status').innerHTML = '✅ <b>Upload Complete!</b><br>👇 Now click <b>Start Transcription</b> below.';
                    }} else {{
                        document.getElementById('status').innerText = '❌ Error: ' + xhr.status + ' (' + xhr.statusText + ')';
                    }}
                }};
                xhr.open("PUT", url, true);
                xhr.setRequestHeader("Content-Type", serverMime); 
                xhr.send(file);
            }}
            </script>
        </body>
        </html>
        """
        st.components.v1.html(html_code, height=150)
        
        st.markdown("### 2. Start Intelligence Engine")
        if st.button("🚀 Start Transcription"):
            bucket = storage.bucket(name=BUCKET_NAME)
            blob = bucket.blob(st.session_state['blob_name'])
            
            if blob.exists():
                job_id = f"job_{int(time.time())}"
                st.session_state['job_id'] = job_id
                
                # Create Init Doc
                db.collection("transcripts").document(job_id).set({
                    "filename": st.session_state['target_filename'],
                    "upload_date": datetime.now(),
                    "status": "queued",
                    "progress": 0,
                    "message": "Queued context...",
                    "context_provided": context_input
                })
                
                # Spawn Thread
                thread = threading.Thread(
                    target=background_worker, 
                    args=(job_id, st.session_state['target_filename'], context_input, selected_temp, db)
                )
                thread.start()
                st.rerun()
            else:
                st.error("File not found in cloud. Did you finish uploading?")

def render_monitor_ui(job_id):
    st.info(f"Monitoring Job: {job_id}")
    
    if st.button("Start New Upload"):
        del st.session_state['job_id']
        if 'signed_url' in st.session_state: del st.session_state['signed_url']
        st.rerun()
    
    # Poll Firestore
    doc_ref = db.collection("transcripts").document(job_id)
    doc = doc_ref.get()
    
    if doc.exists:
        data = doc.to_dict()
        status = data.get('status', 'unknown')
        progress = data.get('progress', 0)
        msg = data.get('message', '')
        
        st.subheader(f"Status: {status.upper()}")
        st.progress(progress)
        st.text(f"Log: {msg}")
        
        if status == 'completed':
            st.success("Analysis Finished!")
            st.text_area("Transcript", data.get('transcript', ''), height=400)
            st.download_button("Download Text", data.get('transcript', ''), file_name="final.txt")
        elif status == 'error':
            st.error(f"Failed: {msg}")
    else:
        st.warning("Job not found in database. It might have been deleted.")
        if st.button("Back to Home"):
            del st.session_state['job_id']
            st.rerun()
    
    time.sleep(2)
    st.rerun()

# --- Main Canvas ---
st.title("🇵🇭 Taglish Transcriber (Async)")
st.caption("Auto-Chunking • No Size Limits • Timestamped")

if 'job_id' not in st.session_state:
    render_upload_ui()
else:
    render_monitor_ui(st.session_state['job_id'])
