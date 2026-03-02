# NANOSOFT ASK AI - Frontend

This is a modern, high-performance AI chat interface built with **Next.js 14** (App Router). It features real-time text streaming, optimized voice recording.

##  Key Features

* Smart Voice Recording: Captures audio using the browser's MediaRecorder API and processes it into high-quality blobs for backend transcription.
*  Real-time UI:  Features a sleek chat interface with distinct styling for User and AI roles, including markdown support and a live typing cursor.
*  Responsive Design:  Built with Tailwind CSS and Lucide React icons for a professional dark-themed experience.

##  Tech Stack

* **Framework: [Next.js 14](https://nextjs.org/) (App Router)
* **Language: [TypeScript](https://www.typescriptlang.org/)
* **Styling: [Tailwind CSS](https://tailwindcss.com/)
* **Icons: [Lucide React](https://lucide.dev/)

## 📂 Project Structure

```text
nanosoft-ai-frontend/
├── app/
│   ├── layout.tsx       # Root layout, fonts, and global meta tags
│   ├── page.tsx         # Main Chat logic (Merged Voice & Text functions)
│   └── globals.css      # Tailwind directives & global styling
├── public/              # Static assets (favicons, logos)
├── .env.local           # Backend API URLs
└── package.json         # Project dependencies and scripts
```
# Getting Started
## 1. Installation
Navigate to the project folder and install the necessary libraries:

```Bash
cd nanosoft-ai-frontend
npm install
```

## 2. Configure Environment
```bash
Create a .env.local file in the root directory to point to your FastAPI server:
API_URL=[http://127.0.0.1:8001/chat]
```

## 3. Run Development Server
```
cd app
npm run dev
Open http://localhost:3000 in your browser.
```

# API Workflow
The frontend acts as the "Controller" in the following sequence:

* Capture: page.tsx captures user text or triggers the microphone.

* Request: Data is sent via POST to the /chat endpoint.

* Stream: The frontend reads the response body as a stream and updates the AI bubble in real-time.

* Display: The renderMarkdown helper formats the text into readable HTML.
## Learn More

To learn more about Next.js, take a look at the following resources:

- [Next.js Documentation](https://nextjs.org/docs) - learn about Next.js features and API.
- [Learn Next.js](https://nextjs.org/learn) - an interactive Next.js tutorial.

You can check out [the Next.js GitHub repository](https://github.com/vercel/next.js) - your feedback and contributions are welcome!

