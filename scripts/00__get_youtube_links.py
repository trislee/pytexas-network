import requests
from bs4 import BeautifulSoup

from config import YOUTUBE_LINKS_FILE

URL = "https://www.pytexas.org/conference"

if __name__ == "__main__":
    response = requests.get(URL)
    soup = BeautifulSoup(response.text, features="lxml")
    links = [a["href"] for a in soup.find_all("a", href=True) if (("youtube.com" in a["href"]) & ("/c/pytexas" not in a["href"]))]
    YOUTUBE_LINKS_FILE.write_text("\n".join(links), encoding="utf-8")