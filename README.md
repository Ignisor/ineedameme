# AI MemeGen - Situational Meme Generator

A hackathon project that leverages AI to generate contextual memes based on user descriptions and optional customizations.

## 🎯 Project Overview

"I need a MEME" is a situational meme generation and lookup application that combines the power of text AI and image generation to create personalized memes. Users can describe situations or desired memes, and the system intelligently matches them with appropriate templates from the Memegen.link API, then generates custom content using Gemini 2.5 Flash Image Preview.

## 🚀 Core Features

### Key Capabilities
- **Situational Meme Generation**: Transform any situation description into a relevant meme
- **Intelligent Template Matching**: AI-powered selection of the most suitable meme template
- **Custom Face Integration**: Replace main characters with uploaded face references
- **AI-Powered Content Generation**: Dynamic text and visual content creation
- **Real-time Preview**: Instant meme generation and display

### User Journey
1. **Describe**: User inputs situation or meme concept + optional face reference
2. **Match**: AI finds the perfect template from Memegen.link's library
3. **Generate**: AI creates appropriate text and visual content
4. **Assemble**: System combines template, content, and custom faces
5. **Deliver**: Generated meme is displayed to user

## 🛠 Technical Architecture

### Technology Stack
- **Frontend**: Simple HTML/CSS/JavaScript interface
- **Backend**: Python with FastAPI
- **AI Services**: Google Gemini for all AI operations
  - Template matching and selection
  - Content generation and prompt creation
  - Image generation with Gemini 2.5 Flash Image Preview
- **External APIs**: Memegen.link for template discovery and reference

### Key Components

#### 1. Template Matching Engine
- Uses Gemini to analyze all 207 available meme templates
- Sends user situation + template list (ID + name) to Gemini
- Returns top 3 ranked templates with confidence weights
- Selects best template based on AI ranking

#### 2. Content Generation Module
- Uses Gemini to generate appropriate meme text based on situation
- Creates comprehensive prompts for Gemini 2.5 Flash Image Preview
- Handles context-aware content creation and humor adaptation

#### 3. Face Integration System
- Processes uploaded face references
- Uses Gemini to convert face images to descriptive prompts
- Integrates face descriptions into image generation prompts
- Handles face upload validation and processing

#### 4. Meme Assembly Pipeline
- Orchestrates all Gemini AI operations
- Combines template style, situation, and face references
- Manages Gemini 2.5 Flash Image Preview generation
- Handles different output formats and quality settings

## 📋 Implementation Plan (2-Day Sprint)

### Day 1: Core PoC Development
- [X] **Morning**: Project setup + Gemini API integration
- [X] **Afternoon**: Memegen.link API integration + template fetching
- [ ] **Evening**: Core pipeline: situation → template selection → content generation → image generation

### Day 2: Interface & Polish
- [ ] **Morning**: CLI interface for testing + face upload handling
- [ ] **Afternoon**: FastAPI backend + basic web interface
- [ ] **Evening**: Demo preparation + error handling

### Core PoC Pipeline
1. ✅ Load 207 templates from local JSON file (pre-fetched from Memegen.link)
2. ✅ Send situation + template list to Gemini for selection
3. ✅ Process Gemini response to get best template
4. ✅ Send situation + template to Gemini for content generation
5. ✅ Create image generation prompt
6. ✅ Send to Gemini 2.5 Flash for image generation
7. ✅ Save result to local file
8. ✅ CLI interface for testing

## 🎨 User Interface Design (MVP)

### Minimal Interface
- **Text Input**: Simple textarea for situation description
- **File Upload**: Basic file input for face reference (optional)
- **Generate Button**: One big button to create meme
- **Result Display**: Show generated meme image
- **Loading State**: Simple spinner while generating

### Design Philosophy
- Function over form - get it working first
- Single page application
- Minimal CSS, focus on functionality

## 🔧 Technical Requirements

### Dependencies
- Python 3.8+
- Web framework (FastAPI/Flask)
- AI/ML libraries for text processing
- HTTP client for API calls
- Frontend framework (if needed)

### API Integrations
- **Memegen.link API**: Template discovery and reference (207 templates)
- **Google Gemini API**: All AI operations (template matching, content generation, image generation)

## 🎯 Success Metrics (2-Day MVP)

### Technical Goals
- ✅ Working meme generation (under 30 seconds)
- ✅ Basic template matching (5-10 templates)
- ✅ Simple face upload integration
- ✅ Functional web interface

### Demo Goals
- ✅ Live meme generation from user input
- ✅ Face replacement demonstration
- ✅ Show AI coordination between services
- ✅ Demonstrate the core concept works

## 🚧 Challenges & Considerations

### Technical Challenges
- **Template Matching Accuracy**: Ensuring AI correctly identifies appropriate templates
- **Face Replacement Quality**: Maintaining natural appearance when replacing faces
- **API Rate Limits**: Managing external API usage efficiently
- **Image Processing Performance**: Optimizing for fast generation

### User Experience Challenges
- **Input Clarity**: Helping users provide effective descriptions
- **Expectation Management**: Setting realistic expectations for AI generation
- **Error Handling**: Graceful handling of generation failures

## 🎉 Demo Features

### Live Demo Capabilities
- Real-time meme generation from user input
- Face replacement demonstration
- Template browsing and selection
- Multiple output format options

### Presentation Points
- AI-powered template matching showcase
- Custom face integration demonstration
- Speed and quality of generation
- User-friendly interface walkthrough

## 📝 Future Enhancements

### Post-Hackathon Possibilities
- Template creation and sharing
- Community meme gallery
- Advanced AI features (style transfer, etc.)
- Mobile app development
- Social media integration

---

*This project demonstrates the power of combining multiple AI services to create engaging, personalized content generation tools.*
