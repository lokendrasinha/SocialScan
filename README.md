# 🔍 SocialScan – AI-Based Social Media Evidence Collection Tool

**SocialScan** is an AI-powered tool designed to automate the extraction and behavioral analysis of social media profiles. Built specifically for forensic investigations, it helps investigators scrape publicly available social media data, analyze user behavior using fine-tuned Large Language Models (LLMs), and generate comprehensive, downloadable reports.

---

## 🚀 Features

- 🔗 Easily input and process Instagram profile URLs  
- 🤖 Perform AI-driven behavioral analysis using fine-tuned LLMs  
- 🧠 LangChain integration for dynamic and contextual prompt handling  
- 💻 Interactive and user-friendly frontend built with Streamlit  
- 🕵️‍♂️ Tailored to assist forensic and investigative workflows  
- 📥 Export structured, detailed evidence reports in PDF format  

---

## 🛠️ Tech Stack

- **Frontend:** Streamlit  
- **Backend:** Python, Selenium, BeautifulSoup  
- **AI Layer:** LangChain + LLM (Ollama, GPT, or custom fine-tuned model)  
- **Utilities:** python-dotenv, html5lib  

---

## 📸 Screenshots

![Screenshot 2025-05-10 010812](https://github.com/user-attachments/assets/52cdd7c1-bb1c-4c4e-b6f4-7dbdf2924e16)
**Image 1: Instagram Profile Scraper - Single Profile View**  
Shows the "SocialScan Pro" interface scraping a single Instagram profile with user info like full name, category, and business details.

![Screenshot 2025-05-10 010841](https://github.com/user-attachments/assets/5399c6dc-1000-4b7b-a1a9-afd20a52d1d9)
**Image 2: Latest Posts from Scraped Profile**  
Displays recent posts including post IDs, like counts, captions, and user mentions.

![Screenshot 2025-05-10 011121](https://github.com/user-attachments/assets/d90ebbb6-7e2f-41b5-8ed7-16573eb7b7a7)
**Image 3: Batch Scraping Interface**  
Highlights the batch scraping feature with role assessment, normalization options, and a success/failure summary.

![Screenshot 2025-05-10 011315](https://github.com/user-attachments/assets/8a035ea3-a4b3-416b-87f8-7a321feed13c)
**Image 4: AI-Powered Profile Analysis Setup**  
Demonstrates the AI analysis interface with metrics like activity volume and ongoing analysis loading indicators.

![Screenshot 2025-05-10 011332](https://github.com/user-attachments/assets/d3c5d5cd-7a2f-4f50-a350-103f497ec8e4)
**Image 5: Custom Analysis Report for High-Profile Account**  
Presents a detailed behavioral report on a selected Instagram account with insights on engagement, interests, and professional background.

---

## 📂 Project Structure
SocialScan/
│
├── app.py              # Streamlit frontend interface,scrapping logic,backend
## 🔧 Installation

### 1. Clone the repository

```bash
git clone https://github.com/yourusername/SocialScan.git
cd SocialScan

