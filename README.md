# NenekBot

A Flask app for Pantang Larang guidance with user accounts, quiz/gamification features, community submissions, and Groq-powered chat responses.

## Run Locally

1. Install Python dependencies:

   ```bat
   py -m pip install -r requirements.txt
   ```

2. Create `app.env` from the example file and add your Groq API key:

   ```bat
   copy app.env.example app.env
   ```

3. Start the Flask app:

   ```bat
   py PantangLarangGuide.py
   ```

4. Open:

   ```text
   http://127.0.0.1:5000
   ```
