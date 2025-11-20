## ** AI Voice & Chat Assistant **

This project is a **bilingual AI assistant** for **The Bank of Punjab (BOP)** that supports:

✅ **Text chat** (Urdu + English + Roman Urdu)
✅ **Voice chat** (Speech-to-Text + AI reply + Text-to-Speech)
✅ **Female persona "Sana"** with polished Urdu/Roman Urdu responses
✅ **Flask backend**
✅ **OpenAI GPT-4o-mini, Whisper, and TTS models**

You can run the application locally using:

```
python app.py
```

---

## **Features**

### 🔹 **Text Chat**

- Auto-detects language (English, Urdu, Roman Urdu)
- Reply in _same_ language
- Professional and polite tone
- Markdown formatting support
- No hallucination — must answer only from provided BOP content

### 🔹 **Voice Chat**

- Uses **Whisper** for Urdu + English speech recognition
- AI responds with correct language
- Audio reply generated using **TTS ("shimmer", "nova")**
- Returns:

  - Clean text response
  - Audio file URL
  - Transcription (optional for debugging)

### 🔹 **Persona**

The AI always behaves as **Sana**, a female BOP assistant:

- Warm, polite, feminine tone
- Never breaks character
- Only discusses BOP services
- Roman Urdu supported

---

## **Project Structure**

```
project/
│── app.py
│── requirements.txt
│── templates/
│     └── call.html
│── static/
      └── css/ styles.css
      └── assets/ logo.png
      └── audio/   (generated audio files)
```

---

## **Requirements**

Install dependencies:

```
pip install flask python-dotenv openai
```

---

## **Environment Variables**

Create a `.env` file:

```
OPENAI_API_KEY=your_api_key_here
```

---

## **How to Run**

1. Activate your virtual environment (optional)
2. Run the Flask app:

```
python app.py
```

3. Open your browser:

```
http://localhost:6077
```

Your AI assistant will load with both **text** and **voice** chat enabled.

---

## **API Endpoints**

### **1. GET /**

Returns the main UI (`call.html`).

---

### **2. POST /chat**

**Request (JSON):**

```json
{
  "message": "Hello"
}
```

**Response:**

```json
{
  "reply": "Hello! How can I help you?"
}
```

---

### **3. POST /voice**

Upload audio (webm/mp3/wav):

**Response:**

```json
{
  "reply": "AI message",
  "audio_url": "/audio/bot_xxxx.mp3",
  "transcription": "User said..."
}
```

---

## **Notes**

- Audio files are auto-generated and stored in `static/audio/`.
- App uses port **6077** (you can change this in `app.py`).
- For deployment, ensure static file paths and environment variables are configured.
