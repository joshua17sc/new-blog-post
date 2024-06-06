#!/usr/bin/python3

import requests
from bs4 import BeautifulSoup
from openai import OpenAI
from datetime import datetime, timedelta, timezone
import os
import subprocess
import logging
from concurrent.futures import ThreadPoolExecutor

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Load API keys from environment variables
NEWS_API_KEY = os.getenv('NEWS_API_KEY')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
GITHUB_REPO = os.getenv('GITHUB_REPO')

# Set the API key for OpenAI
client = OpenAI(api_key=OPENAI_API_KEY)

def fetch_top_articles():
    logging.info("Fetching top articles...")
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
        logging.info(f"Fetched {len(articles)} articles.")
        return articles
    except requests.exceptions.HTTPError as e:
        logging.error(f"HTTP error fetching articles: {e}")
    except requests.exceptions.RequestException as e:
        logging.error(f"Error fetching articles: {e}")
    return []

def scrape_article_content(url):
    logging.info(f"Scraping content from {url}...")
    try:
        response = requests.get(url)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        paragraphs = soup.find_all('p')
        full_text = ' '.join([para.text for para in paragraphs])
        logging.info(f"Scraped content from {url}")
        return full_text
    except requests.exceptions.HTTPError as e:
        logging.error(f"HTTP error scraping content from {url}: {e}")
    except requests.exceptions.RequestException as e:
        logging.error(f"Error scraping content from {url}: {e}")
    return ""

def summarize_article(article_text):
    logging.info("Summarizing article...")
    try:
        stream = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {
                    "role": "user",
                    "content": f"As a cybersecurity professional that is trying to help other cyber professionals understand the latest cybersecurity news, summarize the following article: {article_text}"
                }
            ],
            stream=True,
        )
        summary = ""
        for chunk in stream:
            if chunk.choices[0].delta.content is not None:
                summary += chunk.choices[0].delta.content
        logging.info("Article summarized.")
        return summary
    except Exception as e:
        logging.error(f"Error summarizing article: {e}")
    return ""

def filter_relevant_articles(articles):
    logging.info("Filtering relevant articles...")
    try:
        summaries = [summarize_article(scrape_article_content(article['url'])) for article in articles]
        relevant_articles = [
            {
                'new_title': article['title'],
                'url': article['url'],
                'summary': summaries[idx]
            }
            for idx, article in enumerate(articles) if summaries[idx]
        ]
        logging.info(f"Filtered {len(relevant_articles)} relevant articles.")
        return relevant_articles
    except Exception as e:
        logging.error(f"Error filtering relevant articles: {e}")
    return []

def create_blog_post(summaries):
    logging.info("Creating blog post...")
    today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    filename = f"../cybersecurity-news/_posts/{today}-cybersecurity-news.md"
    try:
        with open(filename, 'w') as f:
            f.write(f"---\n")
            f.write(f"title: Cybersecurity News for {today}\n")
            f.write(f"date: {today}\n")
            f.write(f"---\n\n")
            for article in summaries:
                f.write(f"## {article['new_title']}\n")
                f.write(f"[Read more]({article['url']})\n\n")
                f.write(f"{article['summary']}\n\n")
        logging.info("Blog post created.")
    except Exception as e:
        logging.error(f"Error creating blog post: {e}")

def push_to_github():
    logging.info("Pushing to GitHub...")
    repo_dir = "../cybersecurity-news"
    os.chdir(repo_dir)
    try:
        subprocess.run(["git", "add", "."], check=True)
        
        result = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True)
        if result.stdout.strip():
            subprocess.run(["git", "commit", "-m", "Automated update of cybersecurity news"], check=True)
            subprocess.run(["git", "push", "origin", "main"], check=True)
            logging.info("Changes pushed to GitHub.")
        else:
            logging.info("No changes to commit.")
    except subprocess.CalledProcessError as e:
        logging.error(f"Error during GitHub push: {e}")

if __name__ == "__main__":
    articles = fetch_top_articles()
    relevant_articles = filter_relevant_articles(articles)
    create_blog_post(relevant_articles)
    push_to_github()
