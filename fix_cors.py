
from firebase_admin import credentials, storage, initialize_app
import firebase_admin

# Init
cred = credentials.Certificate("serviceAccountKey.json")
initialize_app(cred, {'storageBucket': 'taglish-transcriber-v1.firebasestorage.app'})

bucket = storage.bucket()

# Define flexible CORS policy
cors_configuration = [
    {
        "origin": ["*"],  # Allow all origins (Production: restrict to run.app URL)
        "method": ["GET", "PUT", "POST", "OPTIONS"],
        "responseHeader": ["Content-Type", "x-goog-resumable"],
        "maxAgeSeconds": 3600
    }
]

bucket.cors = cors_configuration
bucket.patch()

print(f"✅ CORS enabled on {bucket.name}")
