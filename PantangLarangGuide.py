from flask import Flask, request, jsonify, render_template, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import os
from openai import OpenAI
from dotenv import load_dotenv
from datetime import datetime, timezone # Import datetime and timezone for timestamps
import random
import json

# Load environment variables from a .env file
load_dotenv("app.env")

# Initialize the OpenAI client with your API key
client = OpenAI(
    base_url="https://api.groq.com/openai/v1",
    api_key=os.getenv("GROQ_API_KEY"),
)

# Initialize the Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'a_very_secret_key_for_dev_only_change_this_in_production')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///nenekbotdb.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Initialize Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'home' # Redirect to home if login is required

# Define User Model for Gamification Tracking
class User(UserMixin, db.Model): # Inherit from UserMixin
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(128)) # Store hashed password
    points = db.Column(db.Integer, default=0)
    stickers = db.Column(db.Text)  # Store stickers as comma-separated values
    quizzes_completed = db.Column(db.Integer, default=0)
    total_quiz_score = db.Column(db.Integer, default=0)
    # New customization fields
    user_avatar_url = db.Column(db.String(255), default='/static/user_default.jpg') # New field for user's chosen avatar
    user_bubble_class = db.Column(db.String(50), default='user-bubble-default')
    bot_bubble_class = db.Column(db.String(50), default='bot-bubble-default')
    # Owned customization items (stored as JSON string)
    owned_customizations = db.Column(db.Text, default='{}') # Default to empty JSON string

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


# NEW: Community Chat Message Model
class CommunityChatMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    message = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=db.func.current_timestamp())
    user = db.relationship('User', backref='chat_messages') # Relationship to User model

# User loader callback for Flask-Login
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Create the database tables
with app.app_context():
    db.create_all()
    # Initialize default owned customizations for existing users if they don't have it
    # This migration logic should ideally be run once, not on every app start in production
    for user in User.query.all():
        if not user.owned_customizations or user.owned_customizations == '{}':
            user.owned_customizations = json.dumps({
                "user_avatars": ["/static/user_default.jpg"],
                "user_bubbles": ["user-bubble-default"],
                "bot_bubbles": ["bot-bubble-default"]
            })
            db.session.commit()



# --- Quiz Data (In-memory for demonstration - ensure 'category' field is present and consistent) ---
# Added 'category' field to each quiz item for better organization and future filtering.
QUIZ_DATA = [
    {
        "id": 1,
        "question": "Pantang larang apa yang melarang menyapu di waktu malam?",
        "choices": ["Rezeki akan hilang", "Rumah akan berhantu", "Tetamu akan datang", "Malas"],
        "correct_answer": "Rezeki akan hilang",
        "explanation": "Menurut kepercayaan tradisional, menyapu di waktu malam dipercayai boleh menghalau rezeki keluar dari rumah.",
        "difficulty": "easy",
        "time_limit": 30,
        "category": "Aktiviti Rumah Tangga"
    },
    {
        "id": 2,
        "question": "Mengapa orang Melayu dahulu melarang duduk di atas bantal?",
        "choices": ["Nanti punggung bisul", "Nanti jadi malas", "Nanti dimarahi ibu", "Nanti tak dapat jodoh"],
        "correct_answer": "Nanti punggung bisul",
        "explanation": "Kepercayaan ini bertujuan mendidik agar menghormati bantal sebagai tempat kepala, dan juga untuk menjaga kebersihan.",
        "difficulty": "easy",
        "time_limit": 30,
        "category": "Aktiviti Rumah Tangga"
    },
    {
        "id": 3,
        "question": "Pantang larang ibu mengandung: Jangan makan buah nanas. Mengapa?",
        "choices": ["Boleh menyebabkan keguguran", "Boleh menyebabkan bayi demam", "Boleh menyebabkan bayi besar",
                    "Boleh menyebabkan bayi kuning"],
        "correct_answer": "Boleh menyebabkan keguguran",
        "explanation": "Meskipun secara saintifik nanas dalam jumlah kecil tidak berbahaya, pantang larang ini wujud kerana kepercayaan ia boleh menyebabkan keguguran atau panas badan.",
        "difficulty": "medium",
        "time_limit": 25,
        "category": "Kehamilan dan Kelahiran"
    },
    {
        "id": 4,
        "question": "Apakah pantang larang berkaitan memotong kuku pada waktu malam?",
        "choices": ["Boleh memendekkan umur", "Boleh menyebabkan sakit", "Boleh membuang rezeki",
                    "Boleh mengundang hantu"],
        "correct_answer": "Boleh membuang rezeki",
        "explanation": "Pantang larang ini mungkin berasal dari zaman dahulu apabila tiada pencahayaan yang cukup, menyebabkan risiko kecederaan. Ia kemudian dikaitkan dengan kepercayaan rezeki.",
        "difficulty": "medium",
        "time_limit": 25,
        "category": "Aktiviti Rumah Tangga"
    },
    {
        "id": 5,
        "question": "Jangan bersiul di dalam rumah. Apa yang dipercayai akan berlaku?",
        "choices": ["Ular akan masuk rumah", "Rezeki lari", "Rumah jadi bising", "Jiran marah"],
        "correct_answer": "Ular akan masuk rumah",
        "explanation": "Kepercayaan ini mungkin bertujuan untuk mengelakkan bunyi bising yang tidak perlu atau menarik perhatian makhluk lain.",
        "difficulty": "hard",
        "time_limit": 20,
        "category": "Adab Sosial"
    },
    {
        "id": 6,
        "question": "Mengapa tidak boleh menyanyi di dapur?",
        "choices": ["Nanti dapat suami/isteri tua", "Nanti makanan hangit", "Nanti suara sumbang", "Nanti dapur kotor"],
        "correct_answer": "Nanti dapat suami/isteri tua",
        "explanation": "Pantang larang ini mungkin bertujuan untuk mengelakkan seseorang daripada leka dan tidak fokus semasa memasak, yang boleh menyebabkan makanan hangit atau kemalangan.",
        "difficulty": "hard",
        "time_limit": 20,
        "category": "Adab Sosial"
    }
]

# --- List of possible stickers ---
POSSIBLE_STICKERS = ["⭐", "✨", "🎉", "💯", "✅", "👍", "💡", "🧠", "🏆"]

# Dictionary to temporarily store correct answers and explanations for AI-generated questions
# This is a simple in-memory cache. For a production app, consider a more robust caching solution.
ai_quiz_correct_answers = {}

# Define available customization options
CUSTOMIZATION_OPTIONS = {
    "user_avatars": [ # User Avatars
        {"name": "Pengguna Asal", "value": "/static/user_default.jpg", "cost": 0},
        {"name": "Wanita", "value": "/static/women.jpg", "cost": 50},
        {"name": "Lelaki", "value": "/static/men.jpg", "cost": 50},
        {"name": "Atuk", "value": "/static/atuk.jpg", "cost": 70},
        {"name": "Nenek", "value": "/static/nenek.jpg", "cost": 70},
        {"name": "Kucing", "value": "/static/kucing.jpg", "cost": 100}
    ],
    "user_bubbles": [
        {"name": "Asal", "value": "user-bubble-default", "cost": 0},
        {"name": "Biru", "value": "user-bubble-blue", "cost": 20},
        {"name": "Hijau", "value": "user-bubble-green", "cost": 20},
        {"name": "Merah Jambu", "value": "user-bubble-pink", "cost": 20},
        {"name": "Gelap", "value": "user-bubble-dark", "cost": 30}
    ],
    "bot_bubbles": [
        {"name": "Asal", "value": "bot-bubble-default", "cost": 0},
        {"name": "Biru Cerah", "value": "bot-bubble-light-blue", "cost": 20},
        {"name": "Hijau Cerah", "value": "bot-bubble-light-green", "cost": 20},
        {"name": "Merah Jambu Cerah", "value": "bot-bubble-light-pink", "cost": 20},
        {"name": "Kelabu", "value": "bot-bubble-grey", "cost": 30}
    ]
}


def generate_ai_quiz_question(category="Pantang Larang Melayu", difficulty="medium"):
    """Generates a single quiz question using OpenAI's API."""
    try:
        prompt = f"Hasilkan satu soalan kuiz aneka pilihan tentang {category} dengan aras kesukaran {difficulty}. " \
                 "Soalan tersebut perlu mempunyai satu jawapan yang betul dan tiga pilihan jawapan yang salah tetapi munasabah. " \
                 "Formatkan respons sebagai objek JSON dengan kunci-kunci berikut: 'question' (soalan dalam Bahasa Melayu), " \
                 "'choices' (array pilihan jawapan dalam Bahasa Melayu), 'correct_answer' (jawapan yang betul dalam Bahasa Melayu), " \
                 "dan 'explanation' (penjelasan dalam Bahasa Melayu)."

        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": "Anda adalah penjana soalan kuiz."},
                {"role": "user", "content": prompt},
            ],
            max_tokens=300,
            temperature=0.4, # Lower temperature for more factual/consistent quiz questions
            response_format={"type": "json_object"}
        )

        content = response.choices[0].message.content
        if content:
            try:
                quiz_data = json.loads(content)
                if all(key in quiz_data for key in ["question", "choices", "correct_answer", "explanation"]):
                    question_id = random.randint(100000, 999999) # Generate a temporary unique ID
                    quiz_data['id'] = question_id
                    quiz_data['time_limit'] = 30 # Default time limit for AI-generated questions
                    # Store both correct_answer and explanation for AI-generated questions
                    ai_quiz_correct_answers[question_id] = {
                        "correct_answer": quiz_data['correct_answer'],
                        "explanation": quiz_data['explanation']
                    }
                    return quiz_data
                else:
                    print(f"Incomplete JSON response from OpenAI: {quiz_data}")
                    return None
            except json.JSONDecodeError as e:
                print(f"Error decoding JSON from OpenAI: {e}\nContent: {content}")
                return None
        else:
            print("Empty response from OpenAI.")
            return None

    except Exception as e:
        print(f"Error generating quiz question with OpenAI: {e}")
        return None


@app.route("/generate_quiz", methods=["GET"])
def generate_quiz_route():
    # Attempt to generate with AI first
    ai_generated_quiz = generate_ai_quiz_question()
    if ai_generated_quiz:
        return jsonify({
            "question": ai_generated_quiz["question"],
            "choices": ai_generated_quiz["choices"],
            "question_id": ai_generated_quiz["id"],
            "time_limit": ai_generated_quiz.get("time_limit", 30)
        })
    else:
        # Fallback to static data if AI generation fails
        # Ensure we only pick from QUIZ_DATA that has a 'category' for consistency
        valid_static_quiz_data = [q for q in QUIZ_DATA if q.get("category")]
        if valid_static_quiz_data:
            quiz_question = random.choice(valid_static_quiz_data)
            # For static quizzes, the correct_answer and explanation are part of the QUIZ_DATA
            # but we don't send them to the frontend directly for security.
            # The quiz_answer_route will retrieve them from QUIZ_DATA using the question_id.
            return jsonify({
                "question": quiz_question["question"],
                "choices": quiz_question["choices"],
                "question_id": quiz_question["id"],
                "time_limit": quiz_question.get("time_limit", 30)
            })
        else:
            return jsonify({"error": "Tiada soalan kuiz yang tersedia dari AI atau data statik."}), 500


@app.route("/quiz_answer", methods=["POST"])
def quiz_answer_route():
    data = request.json
    user_answer = data.get("answer", "").strip()
    question_id = data.get("question_id")
    timed_out = data.get("timed_out", False)

    correct_answer_info = None  # Will store dict with 'correct_answer' and 'explanation'

    # Check if the question ID exists in our static data (original IDs are 1-6)
    static_question = next((q for q in QUIZ_DATA if q["id"] == question_id), None)
    if static_question:
        correct_answer_info = {
            "correct_answer": static_question["correct_answer"],
            "explanation": static_question["explanation"]
        }
    # Check if the question ID exists in our AI-generated cache (random large IDs)
    elif question_id in ai_quiz_correct_answers:
        correct_answer_info = ai_quiz_correct_answers.get(question_id)
        # Clean up the temporary storage after processing the answer
        del ai_quiz_correct_answers[question_id]

    if correct_answer_info is None:
        return jsonify({"message": "Jawapan yang betul tidak dapat ditentukan.", "points": 0, "stickers": "",
                        "explanation": "Maaf, jawapan yang betul tidak dapat dikenalpasti untuk soalan ini."}), 400

    correct_answer_text = correct_answer_info["correct_answer"]
    explanation = correct_answer_info["explanation"]

    # Get username based on login status
    username = current_user.username if current_user.is_authenticated else "guest"

    is_correct = False
    message = ""

    # Initialize points and stickers to 0/empty for both guest and authenticated users
    # These will be updated from DB for authenticated users later if applicable
    response_points = 0
    response_stickers = ""

    if timed_out:
        message = f"Masa tamat! Jawapan yang betul ialah: {correct_answer_text}."
    elif user_answer.lower() == correct_answer_text.lower():
        is_correct = True
        random_sticker = random.choice(POSSIBLE_STICKERS)
        message = f"Betul! Anda mendapat 20 mata dan pelekat {random_sticker}!"
    else:
        message = f"Alamak, salah jawapan. Jawapan yang betul ialah: {correct_answer_text}."

    # Only update database for authenticated users
    if username != "guest":
        user = User.query.filter_by(username=username).first()
        if user:  # Should always be true for authenticated users
            if is_correct:
                user.points += 20
                stickers = user.stickers.split(',') if user.stickers else []
                if random_sticker not in stickers:
                    stickers.append(random_sticker)
                user.stickers = ','.join(stickers)
            user.quizzes_completed += 1
            if is_correct:
                user.total_quiz_score += 1
            db.session.commit()
            response_points = user.points
            response_stickers = user.stickers
        else:
            # Fallback for some unexpected case where authenticated user not found in DB
            print(f"Warning: Authenticated user '{username}' not found in DB during quiz_answer.")
            # For this rare case, still return 0/empty for safety
            response_points = 0
            response_stickers = ""
    else:
        # For guest users, even if they answer correctly, points/stickers are not persisted
        # and should be reported as 0/empty in the response to the frontend.
        response_points = 0
        response_stickers = ""

    return jsonify({
        "message": message,
        "points": response_points,  # Return the calculated or user's actual points
        "stickers": response_stickers,  # Return the calculated or user's actual stickers
        "explanation": explanation,
        "correct": is_correct,
        "correct_answer": correct_answer_text
    })


@app.route('/quiz_progress')
@login_required # Protect this route
def quiz_progress_route():
    # Use current_user for authenticated users
    username = current_user.username if current_user.is_authenticated else "guest"
    user = User.query.filter_by(username=username).first()

    if not user:
        # This case should ideally not be hit with @login_required, but for guest it's a fallback
        return jsonify({"completed_quizzes": 0, "average_score": 0, "points": 0, "stickers": ""})

    completed_quizzes = user.quizzes_completed
    average_score = 0
    if completed_quizzes > 0:
        average_score = (user.total_quiz_score / completed_quizzes) * 100

    return jsonify({
        "completed_quizzes": completed_quizzes,
        "average_score": round(average_score, 2),
        "points": user.points,
        "stickers": user.stickers
    })


# Conversation history to maintain context per user
conversation_history = {}

# Comprehensive persona for Pantang Larang Bot
persona = (
    "You are a friendly and knowledgeable assistant named 'Nenek Bot'. You help people understand "
    "traditional Malay 'Pantang Larang' (taboos and prohibitions) in a fun and easy-to-understand way. "
    "You are familiar with various categories of Pantang Larang, including:\n"
    "- Pregnancy and Childbirth\n"
    "- Food and Eating Habits\n"
    "- Interactions with Nature and Animals\n"
    "- Household Activities\n"
    "- Social Interactions and Etiquette\n"
    "- Travel and Journeys\n"
    "- Specific Times of Day or Events\n"
    "When you answer questions, use simple language (in bahasa melayu) and explain the traditional meanings or reasons behind the Pantang Larang. "
    "Incorporate a touch of humor where appropriate to make learning engaging. Be respectful of the cultural significance "
    "of these traditions. If you don’t know the answer, say, 'Hmm, Nenek Bot belum pasti tentang itu, tapi mari kita cari tahu bersama!'"
)


# Flask route for the main page
@app.route("/")
def home():
    return render_template("index_PantangBot.html")

# --- Authentication Routes ---
@app.route("/register", methods=["POST"])
def register():
    data = request.json
    username = data.get("username")
    password = data.get("password")

    if not username or not password:
        return jsonify({"message": "Username dan kata laluan diperlukan."}), 400

    existing_user = User.query.filter_by(username=username).first()
    if existing_user:
        return jsonify({"message": "Nama pengguna sudah wujud. Sila pilih nama lain."}), 409

    new_user = User(username=username)
    new_user.set_password(password)
    # Initialize owned customizations for new user
    new_user.owned_customizations = json.dumps({
        "user_avatars": ["/static/user_default.jpg"],
        "user_bubbles": ["user-bubble-default"],
        "bot_bubbles": ["bot-bubble-default"]
    })
    db.session.add(new_user)
    db.session.commit()
    login_user(new_user) # Log the user in immediately after registration
    return jsonify({
        "message": "Pendaftaran berjaya! Selamat datang, " + username + "!",
        "username": username,
        "points": new_user.points,
        "stickers": new_user.stickers,
        "user_avatar_url": new_user.user_avatar_url, # New
        "user_bubble_class": new_user.user_bubble_class,
        "bot_bubble_class": new_user.bot_bubble_class,
        "owned_customizations": json.loads(new_user.owned_customizations)
    }), 201

@app.route("/login", methods=["POST"])
def login():
    data = request.json
    username = data.get("username")
    password = data.get("password")

    user = User.query.filter_by(username=username).first()

    if user and user.check_password(password):
        login_user(user)
        return jsonify({
            "message": "Log masuk berjaya! Selamat datang kembali, " + username + "!",
            "username": username,
            "points": user.points,
            "stickers": user.stickers,
            "user_avatar_url": user.user_avatar_url, # New
            "user_bubble_class": user.user_bubble_class,
            "bot_bubble_class": user.bot_bubble_class,
            "owned_customizations": json.loads(user.owned_customizations)
        }), 200
    else:
        return jsonify({"message": "Nama pengguna atau kata laluan salah."}), 401

@app.route("/logout")
@login_required
def logout():
    logout_user()
    return jsonify({"message": "Anda telah log keluar."}), 200

@app.route("/get_user_status")
def get_user_status():
    if current_user.is_authenticated:
        return jsonify({
            "is_authenticated": True,
            "username": current_user.username,
            "points": current_user.points,
            "stickers": current_user.stickers,
            "user_avatar_url": current_user.user_avatar_url, # New
            "user_bubble_class": current_user.user_bubble_class,
            "bot_bubble_class": current_user.bot_bubble_class,
            "owned_customizations": json.loads(current_user.owned_customizations)
        })
    else:
        return jsonify({
            "is_authenticated": False,
            "username": "guest",
            "points": 0,
            "stickers": "",
            "user_avatar_url": "/static/user_default.jpg", # Default for guest
            "user_bubble_class": "user-bubble-default", # Default for guest
            "bot_bubble_class": "bot-bubble-default", # Default for guest
            "owned_customizations": {
                "user_avatars": ["/static/user_default.jpg"],
                "user_bubbles": ["user-bubble-default"],
                "bot_bubbles": ["bot-bubble-default"]
            }
        })


# Function to generate a response for the chatbot
def generate_response(user_input, username):
    global conversation_history
    # Ensure conversation history is per user
    if username not in conversation_history:
        conversation_history[username] = []

    conversation_history[username].append({"role": "user", "content": user_input})
    messages = [{"role": "system", "content": persona}] + conversation_history[username]

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages,
            max_tokens=300,
            temperature=0.8, # Keep medium temperature for chatbot responses
        )
        bot_response = response.choices[0].message.content.strip()

        conversation_history[username].append({"role": "assistant", "content": bot_response})

        # Limit the conversation history to avoid excessive context length
        if len(conversation_history[username]) > 6:
            conversation_history[username] = conversation_history[username][-6:]

        # Reward users for asking questions ONLY IF NOT GUEST
        if username != "guest":
            user = User.query.filter_by(username=username).first()
            if user:
                user.points += 5
                db.session.commit()

        return bot_response
    except Exception as e:
        print(f"Error generating response: {e}")
        return "Nenek Bot ada masalah sikit. Cuba tanya lagi nanti ya?"


# Flask route for the chatbot API
@app.route("/chat", methods=["POST"])
def chat():
    data = request.json
    user_input = data.get("message", "")

    # Determine username based on authentication status
    username = current_user.username if current_user.is_authenticated else "guest"

    # Handle guest users separately for points/stickers
    if username == "guest":
        # For guest, points and stickers are not persistent.
        # They are effectively 0 and "Tiada" for each new session.
        # The backend doesn't store them for guests.
        response_text = generate_response(user_input, username)  # Call generate_response (won't add points for guest)
        return jsonify({
            "response": response_text,
            "points": 0,  # Always return 0 for guest
            "stickers": "",  # Always return "" for guest
            "username": username
        })
    else:
        # For authenticated users, interact with the database
        user = User.query.filter_by(username=username).first()
        if not user:  # Should not happen for authenticated users, but as a safeguard
            return jsonify({"error": "User not found."}), 404

        response_text = generate_response(user_input, username)  # This will update user.points in DB

        # Re-fetch to get latest points/stickers after generate_response might have updated them
        user = User.query.filter_by(username=username).first()
        return jsonify({
            "response": response_text,
            "points": user.points,
            "stickers": user.stickers,
            "username": username
        })


# Flask route to clear conversation history if needed
@app.route("/clear", methods=["POST"])
@login_required # Only allow logged-in users to clear their history
def clear_history():
    global conversation_history
    if current_user.username in conversation_history:
        del conversation_history[current_user.username]
    return jsonify({"message": "Sejarah perbualan anda telah dibersihkan."})


def reset_user_points():
    # This function is typically for development/testing,
    # it resets all user points. Be careful using in production.
    with app.app_context():
        users = User.query.all()
        for user in users:
            user.points = 0
            user.stickers = ""
            user.quizzes_completed = 0
            user.total_quiz_score = 0
            # Reset customization to defaults and owned status
            user.user_avatar_url = '/static/user_default.jpg'
            user.user_bubble_class = 'user-bubble-default'
            user.bot_bubble_class = 'bot-bubble-default'
            user.owned_customizations = json.dumps({
                "user_avatars": ["/static/user_default.jpg"],
                "user_bubbles": ["user-bubble-default"],
                "bot_bubbles": ["bot-bubble-default"]
            })
        db.session.commit()



# New Flask route for Leaderboard
@app.route("/leaderboard")
def leaderboard():
    # Fetch all users, ordered by points in descending order, excluding 'guest' users
    top_users = User.query.filter(User.username != 'guest').order_by(User.points.desc()).limit(
        10).all()  #top10 only

    leaderboard_data = []
    for user in top_users:
        leaderboard_data.append({
            "username": user.username,
            "points": user.points
        })
    return jsonify({"leaderboard": leaderboard_data})

@app.route("/customizations")
@login_required
def get_customizations():
    user = current_user
    owned_customizations = json.loads(user.owned_customizations)

    # Prepare customization data with 'owned' status
    response_customizations = {}
    for category, items in CUSTOMIZATION_OPTIONS.items():
        response_items = []
        for item in items:
            item_copy = item.copy()
            item_copy['owned'] = item['value'] in owned_customizations.get(category, [])
            response_items.append(item_copy)
        response_customizations[category] = response_items

    return jsonify({
        "customizations": response_customizations,
        "current_user_customizations": {
            "user_avatar_url": user.user_avatar_url,
            "user_bubble_class": user.user_bubble_class,
            "bot_bubble_class": user.bot_bubble_class
        }
    })

@app.route("/apply_customization", methods=["POST"])
@login_required
def apply_customization():
    data = request.json
    item_type = data.get("type") # e.g., 'user_avatar_url', 'user_bubble_class', 'bot_bubble_class'
    item_value = data.get("value")

    user = current_user
    owned_customizations = json.loads(user.owned_customizations)
    user_points = user.points

    # Map item_type to the corresponding category key in CUSTOMIZATION_OPTIONS
    category_key_map = {
        'user_avatar_url': 'user_avatars',
        'user_bubble_class': 'user_bubbles',
        'bot_bubble_class': 'bot_bubbles'
    }
    category_key = category_key_map.get(item_type)

    if not category_key:
        return jsonify({"message": "Jenis penyesuaian tidak sah."}), 400

    # Find the item and its cost
    item_cost = 0
    found_item = None
    if category_key in CUSTOMIZATION_OPTIONS:
        for item in CUSTOMIZATION_OPTIONS[category_key]:
            if item['value'] == item_value:
                found_item = item
                item_cost = item['cost']
                break

    if not found_item:
        return jsonify({"message": "Pilihan penyesuaian tidak sah."}), 400

    # Check if already owned
    if item_value in owned_customizations.get(category_key, []):
        # Item is owned, just apply it (no cost)
        setattr(user, item_type, item_value)
        db.session.commit()
        return jsonify({"message": f"{found_item['name']} telah digunakan!", "points": user.points}), 200
    else:
        # Item is not owned, check points and purchase
        if user_points >= item_cost:
            user.points -= item_cost
            # Add to owned items
            if category_key not in owned_customizations:
                owned_customizations[category_key] = []
            owned_customizations[category_key].append(item_value)
            user.owned_customizations = json.dumps(owned_customizations)

            # Apply the customization
            setattr(user, item_type, item_value)
            db.session.commit()
            return jsonify({"message": f"Anda telah membeli dan menggunakan {found_item['name']}!", "points": user.points}), 200
        else:
            return jsonify({"message": f"Mata tidak mencukupi untuk membeli {found_item['name']}. Anda memerlukan {item_cost} mata.", "points": user.points}), 400


# NEW: Community Features Routes
@app.route("/submit_community_pantang", methods=["POST"])
@login_required
def submit_community_pantang():
    data = request.json
    pantang = data.get("pantang").strip()
    explanation = data.get("explanation").strip()

    if not pantang or not explanation:
        return jsonify({"message": "Sila masukkan pantang larang dan penjelasannya."}), 400

    new_submission = SubmittedPantang(
        user_id=current_user.id,
        pantang=pantang,
        explanation=explanation,
        status='pending'  # New submissions are pending moderation
    )
    db.session.add(new_submission)
    db.session.commit()
    return jsonify(
        {"message": "Sumbangan anda telah dihantar untuk semakan! Terima kasih!", "id": new_submission.id}), 201


@app.route("/community_pantang", methods=["GET"])
def get_community_pantang():
    # Fetch only approved pantang larang for display
    approved_pantang = SubmittedPantang.query.filter_by(status='approved').all()

    pantang_list = []
    for p in approved_pantang:
        user_vote = None
        if current_user.is_authenticated:
            vote = PantangVote.query.filter_by(user_id=current_user.id, submitted_pantang_id=p.id).first()
            if vote:
                user_vote = vote.vote_type

        pantang_list.append({
            "id": p.id,
            "pantang": p.pantang,
            "explanation": p.explanation,
            "upvotes": p.upvotes,
            "downvotes": p.downvotes,
            "user_voted": user_vote  # 'up', 'down', or None
        })
    # Sort by net votes (upvotes - downvotes) for a simple ranking
    pantang_list.sort(key=lambda x: x['upvotes'] - x['downvotes'], reverse=True)
    return jsonify({"community_pantang": pantang_list})



# NEW: Community Chat Routes
@app.route("/post_community_chat", methods=["POST"])
@login_required
def post_community_chat():
    data = request.json
    message_content = data.get("message").strip()

    if not message_content:
        return jsonify({"message": "Mesej tidak boleh kosong."}), 400

    new_message = CommunityChatMessage(
        user_id=current_user.id,
        message=message_content,
        timestamp = datetime.now(timezone.utc)
    )
    db.session.add(new_message)
    db.session.commit()
    return jsonify({"message": "Mesej dihantar!", "timestamp": new_message.timestamp.isoformat()}), 201


@app.route("/get_community_chat", methods=["GET"])
def get_community_chat():
    # Fetch the last 20 messages, ordered by timestamp descending
    messages = CommunityChatMessage.query.order_by(CommunityChatMessage.timestamp.asc()).limit(20).all()

    chat_history = []
    for msg in messages:
        chat_history.append({
            "id": msg.id,
            "username": msg.user.username,
            "message": msg.message,
            "timestamp": msg.timestamp.isoformat(),
            "user_avatar_url": msg.user.user_avatar_url,  # Include user's avatar
            "user_bubble_class": msg.user.user_bubble_class  # Include user's bubble class
        })
    return jsonify({"chat_history": chat_history})



if __name__ == "__main__":
    # IMPORTANT: Comment out or remove reset_user_points() if you want user data to persist across restarts.
    # It's useful for development to start with a clean slate, but will wipe all users.
    # reset_user_points()
    app.run(debug=True)
