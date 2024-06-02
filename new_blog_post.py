import requests
from bs4 import BeautifulSoup
from openai import OpenAI
from datetime import datetime, timedelta, timezone
import os
import subprocess

# Load API keys from environment variables
NEWS_API_KEY = os.getenv('NEWS_API_KEY')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
GITHUB_REPO = os.getenv('GITHUB_REPO')

# Set the API key for OpenAI
client = OpenAI(api_key=OPENAI_API_KEY)

def fetch_top_articles():
    try:
        url = 'https://newsapi.org/v2/everything'
        yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).strftime('%Y-%m-%d')
        params = {
            'q': 'cybersecurity',
            'from': yesterday,
            'to': yesterday,
            'sortBy': 'popularity',
            'pageSize': 20,
            'apiKey': NEWS_API_KEY,
        }
        response = requests.get(url, params=params)
        response.raise_for_status()
        articles = response.json().get('articles', [])
        return articles
    except requests.exceptions.RequestException as e:
        print(f"Error fetching articles: {e}")
        return []

def scrape_article_content(url):
    try:
        response = requests.get(url)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        paragraphs = soup.find_all('p')
        full_text = ' '.join([para.text for para in paragraphs])
        return full_text
    except requests.exceptions.RequestException as e:
        print(f"Error scraping article content from {url}: {e}")
        return ""

def summarize_article(article_text):
    try:
        stream = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {
                    "role": "user",
                    "content": f"Acting as a cybersecurity professional, summarize this article for me into one to two paragraphs of the most important points of the article:\n\n{article_text}"
                }
            ],
            stream=True,
        )
        summary = ""
        for chunk in stream:
            if chunk.choices[0].delta.content is not None:
                summary += chunk.choices[0].delta.content
        return summary
    except Exception as e:
        print(f"Error summarizing article: {e}")
        return "Summary unavailable due to an error."

def filter_relevant_articles(articles):
    full_texts = []
    for article in articles:
        full_text = scrape_article_content(article['url'])
        if full_text:
            full_texts.append({
                'title': article['title'],
                'url': article['url'],
                'full_text': full_text
            })
    
    try:
        # Combine all article texts and ask the AI to select the top 10 relevant articles
        combined_texts = "\n\n".join([f"Title: {article['title']}\nContent: {article['full_text']}" for article in full_texts])
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {
                    "role": "user",
                    "content": f"Select the top 10 most relevant articles for a cybersecurity professional from the following list:\n\n{combined_texts}"
                }
            ],
            stream=True,
        )
        relevant_titles = ""
        for chunk in stream:
            if chunk.choices[0].delta.content is not None:
                relevant_titles += chunk.choices[0].delta.content
        
        relevant_articles = []
        for article in full_texts:
            if article['title'] in relevant_titles:
                summary = summarize_article(article['full_text'])
                relevant_articles.append({
                    'title': article['title'],
                    'url': article['url'],
                    'summary': summary
                })
                if len(relevant_articles) == 10:
                    break

        return relevant_articles
    except Exception as e:
        print(f"Error filtering relevant articles: {e}")
        return []

def create_blog_post(summaries):
    today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    filename = f"../cybersecurity-news/_posts/{today}-cybersecurity-news.md"
    with open(filename, 'w') as f:
        f.write(f"---\n")
        f.write(f"title: Cybersecurity News for {today}\n")
        f.write(f"date: {today}\n")
        f.write(f"---\n\n")
        for article in summaries:
            f.write(f"## {article['title']}\n")
            f.write(f"[Read more]({article['url']})\n\n")
            f.write(f"{article['summary']}\n\n")

def push_to_github():
    repo_dir = "../cybersecurity-news"
    os.chdir(repo_dir)
    subprocess.run(["git", "add", "."], check=True)
    
    # Check for changes before committing
    result = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True)
    if result.stdout.strip():
        subprocess.run(["git", "commit", "-m", "Automated update of cybersecurity news"], check=True)
        subprocess.run(["git", "push", "origin", "main"], check=True)
    else:
        print("No changes to commit.")

if __name__ == "__main__":
    articles = fetch_top_articles()
    relevant_articles = filter_relevant_articles(articles)
    create_blog_post(relevant_articles)
    push_to_github()
