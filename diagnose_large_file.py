import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime

# Initialize Firebase
if not firebase_admin._apps:
    cred = credentials.Certificate("serviceAccountKey.json")
    firebase_admin.initialize_app(cred)

db = firestore.client()

# Check the specific job
job_id = "job_1768905574"
doc = db.collection("transcripts").document(job_id).get()

if doc.exists:
    data = doc.to_dict()
    print(f"\n=== Job Status for {job_id} ===")
    print(f"Filename: {data.get('filename')}")
    print(f"Status: {data.get('status')}")
    print(f"Progress: {data.get('progress')}%")
    print(f"Message: {data.get('message')}")
    print(f"Upload Date: {data.get('upload_date')}")
    
    upload_time = data.get('upload_date')
    if upload_time:
        now = datetime.now(upload_time.tzinfo)
        elapsed = now - upload_time
        print(f"Time Elapsed: {elapsed}")
    
    print(f"\nTranscript length: {len(data.get('transcript', ''))} chars")
    print(f"Context provided: {data.get('context_provided', 'N/A')}")
else:
    print(f"Job {job_id} not found in database")
