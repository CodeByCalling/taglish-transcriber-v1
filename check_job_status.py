import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime

# Initialize Firebase
if not firebase_admin._apps:
    cred = credentials.Certificate("serviceAccountKey.json")
    firebase_admin.initialize_app(cred)

db = firestore.client()

# Check the specific job
job_id = "job_1768904188"
doc = db.collection("transcripts").document(job_id).get()

if doc.exists:
    data = doc.to_dict()
    print(f"\n=== Job Status for {job_id} ===")
    print(f"Filename: {data.get('filename')}")
    print(f"Status: {data.get('status')}")
    print(f"Progress: {data.get('progress')}%")
    print(f"Message: {data.get('message')}")
    print(f"Upload Date: {data.get('upload_date')}")
    print(f"\nTranscript preview (first 500 chars):")
    transcript = data.get('transcript', '')
    print(transcript[:500] if transcript else "(No transcript yet)")
else:
    print(f"Job {job_id} not found in database")
