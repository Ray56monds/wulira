# Wulira Mobile 📱

Android app for Wulira — extract, view, translate, and share lyrics from any YouTube video.

## Setup

```bash
cd mobile
npm install

# Start development
npx expo start --android
```

## Build APK

```bash
# Install EAS CLI
npm install -g eas-cli

# Login to Expo
eas login

# Build Android APK
eas build --platform android --profile preview
```

## Configuration

Edit `src/api.js` and set `API_BASE` to your deployed Wulira API URL:

```js
const API_BASE = 'https://your-wulira-api.com';
```

## Features

- 🎤 Submit YouTube URLs for lyrics extraction
- 📋 View and manage transcription jobs
- 🎵 Timestamped lyrics viewer
- 🔍 Search within lyrics
- 🌍 Translate lyrics (Luganda → English, etc.)
- 📤 Share lyrics via any app
- 📋 Copy lyrics to clipboard
- ⚡ Real-time progress via WebSocket
- 🎨 Dark theme matching the web dashboard
