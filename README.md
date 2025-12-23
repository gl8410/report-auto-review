<div align="center">
<img width="1200" height="475" alt="GHBanner" src="https://github.com/user-attachments/assets/0aa67016-6eaf-458a-adb2-6e31a0763ed6" />
</div>

# Run and deploy your AI Studio app

This contains everything you need to run your app locally.

View your app in AI Studio: https://ai.studio/apps/drive/13Q_KQxhIxbtIwSKr5tqNPxrrdkmcizmC

## Run Locally

**Prerequisites:**  Node.js


1. Install dependencies:
   `npm install`
2. Set the `GEMINI_API_KEY` in [.env.local](.env.local) to your Gemini API key
3. Run the app:
   `npm run dev`

## Run Backend

**Prerequisites:** Python 3.10+

1. Navigate to the backend directory:
   `cd backend`
2. Install dependencies:
   `pip install -r requirements.txt`
3. Run the backend server:
   `uvicorn backend.main:app --reload`
