# Cricket Fan Insights

A Streamlit dashboard for collecting and analysing YouTube cricket comments.

## Features
- Collect comments by entering video links.
- Clean text and remove duplicate comment IDs.
- Filter by video, topic, player and estimated sentiment.
- View charts and export filtered results.

## Setup
1. Create a Python virtual environment.
2. Install dependencies: pip install -r requirements.txt
3. Copy .env.example to .env.
4. Set YOUTUBE_API_KEY in .env to your own API key.
5. Run: python -m streamlit run app.py
6. Open Add Videos in the sidebar to collect data.

## Dataset
The initial single-video collection retrieved 2,500 unique top-level
comments from https://www.youtube.com/watch?v=MAm0RLQpYas.
Replies are excluded. Additional collections can change the dataset.

## Limitations
Topics, player names and sentiment use keyword rules.
Sarcasm, slang and mixed-language comments may be misclassified.
Sentiment labels are estimates, not validated predictions.
This sample does not represent all cricket fans.

## Security
Never commit .env or API keys.
Collected data and local reports are excluded from this repository.
