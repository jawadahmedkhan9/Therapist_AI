# M - Your Therapeutic AI Companion

A modern, empathetic AI chatbot built with Flask and Groq AI.

## Deployment on Vercel

### Prerequisites

1. Install Vercel CLI:
```bash
npm install -g vercel
```

2. Create a Vercel account at https://vercel.com

3. Get your Groq API key from https://console.groq.com

### Deployment Steps

1. Clone the repository:
```bash
git clone <your-repo-url>
cd M-bot
```

2. Login to Vercel:
```bash
vercel login
```

3. Set up environment variables on Vercel:
- Go to your Vercel dashboard
- Select your project
- Go to Settings > Environment Variables
- Add the following variables:
  - `GROQ_API_KEY`: Your Groq API key
  - `FLASK_ENV`: production
  - `FLASK_APP`: MVP.py

4. Deploy:
```bash
vercel
```

5. For subsequent deployments:
```bash
vercel --prod
```

## Local Development

1. Create a `.env` file in the root directory:
```
GROQ_API_KEY=your_api_key_here
FLASK_ENV=development
FLASK_APP=MVP.py
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Run the application:
```bash
flask run
```

The app will be available at `http://localhost:5000`

## Project Structure

- `MVP.py`: Main application file
- `static/`: Static assets (CSS, images)
- `requirements.txt`: Python dependencies
- `vercel.json`: Vercel deployment configuration
- `.env`: Environment variables (local development)

## Features

- Modern, responsive UI
- Real-time chat interface
- Conversation persistence
- Empathetic AI responses
- Suggestion tabs for common topics
- User profile customization

## Tech Stack

- Flask
- Groq AI
- Python
- HTML/CSS
- JavaScript 