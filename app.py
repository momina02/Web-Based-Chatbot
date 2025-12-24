import uuid
import os
import json
from pathlib import Path
from flask import Flask, render_template, request, jsonify, send_from_directory
from openai import OpenAI
from dotenv import load_dotenv
import pandas as pd
from datetime import datetime

load_dotenv()

app = Flask(__name__)
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Audio storage
AUDIO_DIR = os.path.join(app.static_folder, "audio")
os.makedirs(AUDIO_DIR, exist_ok=True)

# Session storage: session_id → {history, language, user_name}
sessions = {}

# Tea menu with prices (PKR)
TEAS = {
    "Green Tea": 150,
    "Black Tea": 120,
    "Sulemani Tea": 100,
    "English Breakfast Tea 50g": 180,
    "Ginger Tea with Honey": 160,
    "Ginger Tea with Lemon": 160,
    "Peshawari Kehwa": 200,
    "Kashmiri Chai": 220,
    "Classical Tea": 140
}

# Excel file
ORDERS_FILE = "tea_orders.xlsx"

def get_next_order_id():
    """Get the next available order ID"""
    if os.path.exists(ORDERS_FILE):
        try:
            df = pd.read_excel(ORDERS_FILE)
            if not df.empty and 'OrderID' in df.columns:
                return int(df['OrderID'].max()) + 1
        except:
            pass
    return 1001

def save_order(order_id, user_name, tea, quantity, price_per_unit, date, time):
    """Save individual order line to Excel"""
    row = {
        'OrderID': order_id,
        'UserName': user_name,
        'TeaType': tea,
        'Quantity': quantity,
        'PricePerUnit': price_per_unit,
        'TotalPrice': price_per_unit * quantity,
        'OrderDate': date,
        'OrderTime': time
    }
    df_new = pd.DataFrame([row])
    
    if os.path.exists(ORDERS_FILE):
        df = pd.read_excel(ORDERS_FILE)
        df = pd.concat([df, df_new], ignore_index=True)
    else:
        df = df_new
    
    df.to_excel(ORDERS_FILE, index=False)

def is_urdu(text):
    """Detect if text is primarily Urdu script"""
    urdu_count = sum(1 for c in text if '\u0600' <= c <= '\u06FF')
    total_alpha = sum(1 for c in text if c.isalpha())
    return total_alpha > 0 and (urdu_count / total_alpha) > 0.5

@app.route('/')
def index():
    return render_template('call.html')

@app.route('/audio/<filename>')
def serve_audio(filename):
    return send_from_directory(AUDIO_DIR, filename)

# ========== TEXT CHAT ==========
@app.route('/chat', methods=['POST'])
def chat():
    data = request.json
    user_message = data.get('message', '').strip()
    session_id = data.get('session_id')

    if not user_message:
        return jsonify({"reply": "Please type something."}), 400

    # Create new session if none exists
    if not session_id or session_id not in sessions:
        session_id = str(uuid.uuid4())
        sessions[session_id] = {
            "history": [],
            "language": None,
            "user_name": None
        }

    session = sessions[session_id]
    history = session["history"]

    # Detect and lock language on first message
    if session["language"] is None:
        session["language"] = "urdu" if is_urdu(user_message) else "english"

    lang = session["language"]
    
    # Build context-aware user message
    context_message = user_message
    if session["user_name"]:
        context_message = f"[User's name is {session['user_name']}] {user_message}"
    
    history.append({"role": "user", "content": context_message})

    # Enhanced system prompt with conversation state awareness
    system_prompt = f"""
You are Sana, a warm, friendly, and professional female assistant at Vital Tea Café.

**Available Teas and Prices (PKR):**
{chr(10).join([f'- {tea}: {price} PKR' for tea, price in TEAS.items()])}

**IMPORTANT CONVERSATION STATE RULES:**
- Check the conversation history to see if you already know the user's name
- If the user's name appears in previous messages or context, DO NOT ask for it again
- If you already greeted the user, move directly to helping them with their order
- Remember what you've already discussed with the user

**Your Conversation Flow:**

1. **First Interaction ONLY:**
   - Greet warmly: "Hello! Welcome to Vital Tea Café."
   - Ask for name: "May I know your name, please?"
   - Wait for response

2. **After Name is Known:**
   - Use their name naturally
   - Move to tea selection immediately
   - Present 2-3 tea options at a time with prices
   - Example: "Great! Let me show you some of our popular teas..."

3. **Tea Selection Process:**
   - Present 2-3 tea options at a time with their prices
   - After presenting, ask: "Would you like to see more options, or would you like to order from these?"
   - If they want more, show 2-3 different options
   - Continue until they make a choice

4. **Order Taking:**
   - When customer shows interest, confirm: "Great choice! How many cups of [tea name] would you like?"
   - After quantity, ask: "Would you like to add anything else to your order?"
   - Keep track of all items

5. **Order Confirmation:**
   - Summarize everything clearly:
     * All tea items with quantities
     * Individual prices
     * Total amount
   - Ask: "Is this correct? Shall I place your order?"

6. **Placing Order:**
   - Only after explicit confirmation, call place_order function
   - Function saves everything to the system

**CRITICAL LANGUAGE RULE:**
- If conversation started in English → respond ONLY in English
- If conversation started in Urdu script → respond ONLY in Urdu script
- Never mix languages. Never use Roman Urdu.

**Tone:** Warm, natural, conversational, professional
"""

    tools = [{
        "type": "function",
        "function": {
            "name": "place_order",
            "description": "Save the complete confirmed order. Only call after customer explicitly confirms.",
            "parameters": {
                "type": "object",
                "properties": {
                    "user_name": {"type": "string"},
                    "orders": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "tea": {"type": "string", "enum": list(TEAS.keys())},
                                "quantity": {"type": "integer", "minimum": 1}
                            },
                            "required": ["tea", "quantity"]
                        }
                    }
                },
                "required": ["user_name", "orders"]
            }
        }
    }]

    messages = [{"role": "system", "content": system_prompt}] + history

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            tools=tools,
            tool_choice="auto",
            temperature=0.7,
            max_tokens=1000
        )

        msg = response.choices[0].message
        reply = msg.content.strip() if msg.content else ""

        # Handle function calls
        if msg.tool_calls:
            for call in msg.tool_calls:
                if call.function.name == "place_order":
                    args = json.loads(call.function.arguments)
                    user_name = args["user_name"]
                    session["user_name"] = user_name

                    now = datetime.now()
                    order_id = get_next_order_id()
                    grand_total = 0
                    order_summary = []
                    
                    for item in args["orders"]:
                        tea = item["tea"]
                        qty = item["quantity"]
                        price_per = TEAS.get(tea, 0)
                        item_total = price_per * qty
                        grand_total += item_total
                        
                        save_order(
                            order_id=order_id,
                            user_name=user_name,
                            tea=tea,
                            quantity=qty,
                            price_per_unit=price_per,
                            date=now.strftime("%Y-%m-%d"),
                            time=now.strftime("%H:%M:%S")
                        )
                        
                        order_summary.append(f"{qty}x {tea} @ {price_per} PKR = {item_total} PKR")

                    if lang == "english":
                        summary = "\n".join(order_summary)
                        reply = f"""Thank you {user_name}! 🎉

Your Order #{order_id} has been placed successfully!

Order Details:
{summary}

Grand Total: {grand_total} PKR

Your delicious tea will be ready shortly. Enjoy! ☕✨"""
                    else:
                        summary = "\n".join(order_summary)
                        reply = f"""شکریہ {user_name} صاحب! 🎉

آپ کا آرڈر نمبر {order_id} کامیابی سے موصول ہو گیا ہے!

آرڈر کی تفصیلات:
{summary}

کل رقم: {grand_total} روپے

آپ کی لذیذ چائے جلد تیار ہو گی۔ لطف اٹھائیں! ☕✨"""

        # Extract user name from assistant's context if present
        if not session["user_name"] and "name" in user_message.lower():
            potential_name = user_message.strip()
            if len(potential_name.split()) <= 3 and len(potential_name) < 50:
                session["user_name"] = potential_name

        history.append({"role": "assistant", "content": reply})
        session["history"] = history[-20:]

        return jsonify({
            "reply": reply,
            "session_id": session_id
        })

    except Exception as e:
        print("Error:", e)
        error_msg = "معاف کیجیے، تکنیکی مسئلہ ہے۔" if lang == "urdu" else "Sorry, there's a technical issue."
        return jsonify({"reply": error_msg, "session_id": session_id})


# ========== VOICE CHAT ==========
@app.route('/voice', methods=['POST'])
def voice_chat():
    if 'audio' not in request.files:
        return jsonify({"error": "No audio"}), 400

    audio_file = request.files['audio']
    session_id = request.form.get('session_id')
    temp_path = os.path.join(AUDIO_DIR, f"user_{uuid.uuid4().hex}.webm")
    audio_file.save(temp_path)

    if not session_id or session_id not in sessions:
        session_id = str(uuid.uuid4())
        sessions[session_id] = {
            "history": [],
            "language": None,
            "user_name": None
        }

    session = sessions[session_id]
    history = session["history"]

    try:
        with open(temp_path, "rb") as f:
            transcription = client.audio.transcriptions.create(
                model="whisper-1",
                file=f
            ).text.strip()

        if session["language"] is None:
            session["language"] = "urdu" if is_urdu(transcription) else "english"

        lang = session["language"]
        
        context_message = transcription
        if session["user_name"]:
            context_message = f"[User's name is {session['user_name']}] {transcription}"
        
        history.append({"role": "user", "content": context_message})

        system_prompt = f"""
You are Sana, a warm, friendly, and professional female assistant at Vital Tea Café.

**Available Teas and Prices (PKR):**
{chr(10).join([f'- {tea}: {price} PKR' for tea, price in TEAS.items()])}

**IMPORTANT CONVERSATION STATE RULES:**
- Check conversation history to see if you already know the user's name
- If name appears in previous messages, DO NOT ask for it again
- If you already greeted the user, move directly to helping them
- Remember what you've already discussed

**Your Conversation Flow:**

1. **First Interaction ONLY:**
   - Greet warmly and ask for name once
   
2. **After Name is Known:**
   - Use their name naturally
   - Move to tea selection immediately
   - Present 2-3 options at a time with prices

3. **Tea Selection:**
   - Present 2-3 options at a time
   - Ask if they want more or ready to order
   
4. **Order Taking:**
   - Confirm tea choice and ask quantity
   - Ask if they want anything else

5. **Order Confirmation:**
   - Summarize all items, quantities, and total
   - Ask for explicit confirmation

6. **Placing Order:**
   - Only after confirmation, call place_order function

**CRITICAL LANGUAGE RULE:**
- English conversation → English responses only
- Urdu conversation → Urdu script only
- Never mix. Never use Roman Urdu.
"""

        tools = [{
            "type": "function",
            "function": {
                "name": "place_order",
                "description": "Save confirmed order after explicit confirmation.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "user_name": {"type": "string"},
                        "orders": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "tea": {"type": "string", "enum": list(TEAS.keys())},
                                    "quantity": {"type": "integer", "minimum": 1}
                                },
                                "required": ["tea", "quantity"]
                            }
                        }
                    },
                    "required": ["user_name", "orders"]
                }
            }
        }]

        messages = [{"role": "system", "content": system_prompt}] + history

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            tools=tools,
            tool_choice="auto",
            temperature=0.7,
            max_tokens=1000
        )

        msg = response.choices[0].message
        reply_text = msg.content.strip() if msg.content else ""

        if msg.tool_calls:
            for call in msg.tool_calls:
                if call.function.name == "place_order":
                    args = json.loads(call.function.arguments)
                    user_name = args["user_name"]
                    session["user_name"] = user_name

                    now = datetime.now()
                    order_id = get_next_order_id()
                    grand_total = 0
                    order_summary = []

                    for item in args["orders"]:
                        tea = item["tea"]
                        qty = item["quantity"]
                        price_per = TEAS.get(tea, 0)
                        item_total = price_per * qty
                        grand_total += item_total
                        
                        save_order(
                            order_id=order_id,
                            user_name=user_name,
                            tea=tea,
                            quantity=qty,
                            price_per_unit=price_per,
                            date=now.strftime("%Y-%m-%d"),
                            time=now.strftime("%H:%M:%S")
                        )
                        
                        order_summary.append(f"{qty}x {tea} @ {price_per} PKR = {item_total} PKR")

                    if lang == "english":
                        summary = ", ".join(order_summary)
                        reply_text = f"Thank you {user_name}! Your order number {order_id} has been placed successfully. {summary}. Grand total: {grand_total} PKR. Your tea will be ready shortly!"
                    else:
                        summary = "، ".join(order_summary)
                        reply_text = f"شکریہ {user_name} صاحب! آپ کا آرڈر نمبر {order_id} موصول ہو گیا۔ {summary}۔ کل رقم: {grand_total} روپے۔"

        history.append({"role": "assistant", "content": reply_text})
        session["history"] = history[-20:]

        voice = "shimmer" if lang == "urdu" else "nova"
        tts = client.audio.speech.create(
            model="tts-1",
            voice=voice,
            input=reply_text
        )

        bot_path = os.path.join(AUDIO_DIR, f"bot_{uuid.uuid4().hex}.mp3")
        tts.stream_to_file(bot_path)
        os.remove(temp_path)

        return jsonify({
            "reply": reply_text,
            "audio_url": f"/audio/{os.path.basename(bot_path)}",
            "transcription": transcription,
            "session_id": session_id
        })

    except Exception as e:
        print("Voice error:", e)
        try:
            os.remove(temp_path)
        except:
            pass
        error_reply = "معاف کیجیے، آڈیو میں مسئلہ ہے۔" if session.get("language") == "urdu" else "Sorry, audio issue."
        return jsonify({"reply": error_reply, "session_id": session_id})


if __name__ == '__main__':
    app.run(debug=True, port=6077)
