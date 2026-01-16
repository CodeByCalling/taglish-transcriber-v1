import firebase_admin
from firebase_admin import credentials, storage

try:
    cred = credentials.Certificate("serviceAccountKey.json")
    firebase_admin.initialize_app(cred)
    
    print("Authenticated successfully.")
    
    client = storage.storage.Client(credentials=cred.get_credential(), project=cred.project_id)
    buckets = list(client.list_buckets())
    
    if not buckets:
        print("No buckets found accessible to this service account.")
    else:
        print(f"Found {len(buckets)} buckets:")
        for bucket in buckets:
            print(f"- {bucket.name}")
            
except Exception as e:
    print(f"Error: {e}")
