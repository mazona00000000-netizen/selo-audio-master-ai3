# SELO AUDIO MASTER AI

A browser-based Arabic voiceover and podcast studio with script emotion cues, voice selection, and WAV export.

## Web deployment (Render)

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/mazona00000000-netizen/selo-audio-master-ai3)

This repository includes a Render Blueprint in `render.yaml`.

1. Sign in to Render and connect the GitHub account that can access this repository.
2. In Render, choose **New → Blueprint**, select this repository, and apply the Blueprint.
3. Render builds the Python service and provides an HTTPS `onrender.com` URL.

The free Render web service sleeps after 15 minutes without traffic and can take about a minute to wake on the next visit. Its local filesystem is temporary, so do not use it for permanent storage. See [Render free instance limitations](https://render.com/docs/free).

## Voice generation

The primary option is VoiceTut Egyptian TTS through its online Gradio service. It requires an internet connection and depends on that external service being available. Chatterbox is an optional local engine and needs its own model dependencies. Darijat requires a paid API token.

## Privacy

When deployed as a public web service, visitors can access the app URL. Text submitted for VoiceTut generation is sent to the external VoiceTut service. Do not submit passwords, private personal data, or confidential scripts.

## Local development

Requires Python 3.10 or newer.

```bash
pip install -r requirements.txt
python -m app.server
```

Open `http://127.0.0.1:8000`.

## Windows installer

A Windows packaging workflow is also included at `.github/workflows/windows-build.yml`. Its installer is a separate build from the web deployment.
