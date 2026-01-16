import streamlit as st
import os
import traceback
from dotenv import load_dotenv
import openai
from pydub import AudioSegment
import math
import firebase_admin
from firebase_admin import credentials, firestore, storage
from datetime import datetime

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
            cred = credentials.Certificate("serviceAccountKey.json")
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

def save_metadata(db, filename, context, transcript_text, storage_url):
    """
    Saves transcription metadata to Firestore.
    """
    try:
        doc_ref = db.collection("transcripts").document()
        doc_ref.set({
            "filename": filename,
            "upload_date": datetime.now(),
            "context_provided": context,
            "status": "completed",
            "storage_url": storage_url,
            "transcript": transcript_text
        })
        return doc_ref.id
    except Exception as e:
        st.error(f"Firestore save failed: {e}")
        return None


def process_chunk(client, file_path, system_prompt, chunk_index, total_chunks):
    """
    Transcribes a single audio chunk.
    """
    try:
        with open(file_path, "rb") as audio_file:
            st.text(f"  ... Transcribing segment {chunk_index + 1}/{total_chunks} ...")
            transcript_response = client.audio.transcriptions.create(
                model="whisper-1", 
                file=audio_file, 
                prompt=system_prompt,
                temperature=0.3
            )
            return transcript_response.text
    except Exception as e:
        st.error(f"Error processing chunk {chunk_index + 1}: {e}")
        return f"[Missing Segment {chunk_index + 1}]"

def transcribe_audio(file_obj, context_text, model_choice):
    """
    Real OpenAI Whisper Integration (v1.x) with Chunking
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        st.error("🚨 OpenAI API Key not found. Please check your .env file.")
        return None
    
    # Critical Fix: Strip whitespace that often creeps in from copy-pasting
    api_key = api_key.strip()

    client = openai.OpenAI(
        api_key=api_key,
        timeout=300.0 # Increase timeout to 5 minutes for large uploads
    )

    # Construct the Specialized Taglish Query (Anti-Hallucination V2)
    system_prompt = (
        "You are an expert transcriber for Taglish (Tagalog-English) church meetings. "
        "Audio is often noisy. If you hear silence, music, or unclear sounds, DO NOT hallucinate. "
        "DO NOT REPEAT phrases in a loop. If a phrase repeats more than twice, stop writing it. "
        "Transcribe English in US English. Transcribe Tagalog in Filipino orthography. "
        "Context: " + context_text
    )
    
    status_text = st.empty()
    progress_bar = st.progress(0)
    
    try:
        # 1. Save Uploaded File to Disk (Required for Pydub)
        file_ext = file_obj.name.split('.')[-1]
        temp_filename = f"temp_upload.{file_ext}"
        
        with open(temp_filename, "wb") as f:
            f.write(file_obj.getbuffer())
            
        # 2. Check Size and Chunk if necessary
        status_text.text("Analyzing audio file...")
        audio = AudioSegment.from_file(temp_filename)
        duration_ms = len(audio)
        duration_minutes = duration_ms / 1000 / 60
        
        st.info(f"Audio Duration: {duration_minutes:.2f} minutes")
        
        # Split into 10-minute chunks (10 * 60 * 1000 ms)
        chunk_length_ms = 10 * 60 * 1000
        chunks = math.ceil(duration_ms / chunk_length_ms)
        
        full_transcript = ""
        
        for i in range(chunks):
            start_ms = i * chunk_length_ms
            end_ms = min((i + 1) * chunk_length_ms, duration_ms)
            
            # Export chunk
            chunk = audio[start_ms:end_ms]
            chunk_filename = f"temp_chunk_{i}.mp3"
            chunk.export(chunk_filename, format="mp3")
            
            # Update UI
            progress = (i / chunks)
            progress_bar.progress(progress)
            status_text.text(f"Processing Part {i+1}/{chunks} (sending to OpenAI)...")
            
            # Transcribe
            chunk_text = process_chunk(client, chunk_filename, system_prompt, i, chunks)
            
            # Anti-Loop: If a chunk is just repeating the same word, discard it or warn.
            # Simple heuristic: If the text is shorter than 50 chars but audio was 10 mins, it's likely noise.
            # For now, we trust the new system prompt.
            
            full_transcript += chunk_text + "\n\n"
            
            # Cleanup Chunk
            if os.path.exists(chunk_filename):
                os.remove(chunk_filename)
        
        # Cleanup Original
        if os.path.exists(temp_filename):
            # UPLOAD TO FIREBASE STORAGE BEFORE DELETING
            status_text.text("Saving to Cloud Vault...")
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            storage_path = f"meetings/{timestamp}_{file_obj.name}"
            storage_url = upload_to_firebase(temp_filename, storage_path)
            
            # SAVE TO FIRESTORE
            if db and storage_url:
                doc_id = save_metadata(db, file_obj.name, context_text, full_transcript, storage_url)
                st.success(f"✅ Saved to Secure Vault (ID: {doc_id})")
                st.session_state['refresh_history'] = True # Trigger reload
            
            os.remove(temp_filename)
            
        progress_bar.progress(100)
        status_text.text("Transcription Complete!")
        
        return full_transcript
        
    except Exception as e:
        st.error(f"An error occurred during transcription: {e}")
        st.code(traceback.format_exc()) # Show full traceback
        return None

# --- UI Layout ---

# Sidebar
with st.sidebar:
    st.header("Settings")
    model_choice = st.selectbox(
        "Model", 
        ["whisper-1 (High Accuracy)", "whisper-1 (Standard)"], 
        index=0
    )
    speaker_count = st.number_input("Est. Speakers", min_value=1, value=4)
    
    st.divider()
    st.subheader("History")
    
    # HISTORY FETCH LOGIC
    if db:
        docs = db.collection("transcripts").order_by("upload_date", direction=firestore.Query.DESCENDING).limit(10).stream()
        
        found_any = False
        for doc in docs:
            found_any = True
            data = doc.to_dict()
            date_str = data.get('upload_date', datetime.now()).strftime("%b %d %H:%M")
            fname = data.get('filename', 'Unknown File')
            
            with st.expander(f"{date_str} - {fname[:15]}..."):
                st.caption(f"Status: {data.get('status')}")
                # Download Button for History Item
                st.download_button(
                    label="Download",
                    data=data.get('transcript', ''),
                    file_name=f"transcript_{doc.id}.txt",
                    mime="text/plain",
                    key=doc.id
                )
        
        if not found_any:
            st.caption("No transcripts found in Cloud.")
    else:
        st.caption("Database disconnected.")

# Top Navigation
col1, col2 = st.columns([8, 1])
with col1:
    st.title("🇵🇭 Taglish Transcriber")
with col2:
    st.caption("Profile")

# Main Canvas (State 1: Setup)
st.markdown("### Upload Church Meeting Recording")

# Context Box
context_input = st.text_area(
    "Meeting Context & Vocabulary",
    placeholder="Example: Budget planning, 'Tithe', 'Gawain', Pastor John, Vallejo campus...",
    help="Helping the AI know these words improves Tagalog spelling"
)

# Drop Zone
uploaded_file = st.file_uploader(
    "Drag & Drop MP3, WAV, or M4A here", 
    type=["mp3", "wav", "m4a"],
    help="Max 500MB (System will auto-chunk)"
)


if uploaded_file is not None:
    # State 2: Processing (Simulated)
    st.divider()
    st.markdown("### ⚙️ Processing...")
    
    # Trigger Transcription Button (for Phase 1 testing)
    if st.button("Start Transcription"):
        transcript = transcribe_audio(uploaded_file, context_input, model_choice)
        
        if transcript:
            # State 3: Output
            st.divider()
            st.subheader("Transcript Preview")
            st.write(transcript)
            
            # Download Button
            st.download_button(
                label="Download Transcript",
                data=transcript,
                file_name="transcript.txt",
                mime="text/plain"
            )
