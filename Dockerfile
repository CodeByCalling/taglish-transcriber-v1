# Use Python 3.11 Full (Includes compiler tools like gcc)
FROM python:3.11

# Install System Dependencies (FFmpeg + Nginx)
RUN apt-get update && apt-get install -y \
    ffmpeg \
    nginx \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set Working Directory
WORKDIR /app

# Copy Requirements and Install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy App Code
COPY . .

# Expose Port 8080 (Cloud Run Requirement)
EXPOSE 8080

# Run Streamlit Directly
CMD ["streamlit", "run", "app.py", "--server.port=8080", "--server.address=0.0.0.0"]
