FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Install system deps for audio (ffmpeg is required for whisper)
RUN apt-get update && apt-get install -y ffmpeg && apt-get clean

# Copy requirements if you have one
# If not, create a minimal one as below
COPY requirements.txt .

# Install python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY . .

# Expose your Flask port
EXPOSE 6077

# Run the app
CMD ["python", "app.py"]
