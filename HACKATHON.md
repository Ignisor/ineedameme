# I need a MEME — Hackathon

"I need a MEME" is a situational meme generation and lookup
application that combines the power of text AI and image generation to
create personalized memes. Users can describe situations or desired
memes, and the system intelligently matches them with appropriate
templates from the Memegen.link API, then generates custom content
using Gemini 2.5 Flash Image Preview.

## Live demo

[Live Demo](https://add-demo-link-here)

## How it works

- Picks the best templates from a Memegen.link dataset
- Builds a meme idea
- Returns a fresh meme ready to use (hopefully)

## Try it

- Type your situation (e.g., "When boss asked to create an AI something")
- Optionally add a face image or URL, then hit Generate

## Tech

FastAPI backend + OpenRouter models (Gemini 2.5 Flash Image Preview) + Tailwind UI.
