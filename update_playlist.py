import re
import requests
from bs4 import BeautifulSoup

BASE_URL = "https://tviplayer.iol.pt"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

SHOWS_TO_SCRAPE = [
    {
        "name": "Dois às 10",
        "category": "Entretenimento",
        "url": "https://tviplayer.iol.pt/programa/dois-as-10/5fdcb61a0cf2432ec4cb03e2"
    },
    {
        "name": "Goucha",
        "category": "Entretenimento",
        "url": "https://tviplayer.iol.pt/programa/goucha/5fe350a40cf2febe232a5ff5"
    }
]

def fetch_global_token():
    headers = {"User-Agent": USER_AGENT, "Referer": BASE_URL}
    
    for show in SHOWS_TO_SCRAPE:
        print(f"Checking show page for episodes: {show['name']}...")
        try:
            res = requests.get(show["url"], headers=headers, timeout=10)
            if res.status_code == 200:
                soup = BeautifulSoup(res.text, "html.parser")
                # Find the first episode link
                ep_link = soup.find("a", href=re.compile(r'/video/'))
                
                if ep_link:
                    ep_url = ep_link['href']
                    if not ep_url.startswith("http"):
                        ep_url = BASE_URL + ep_url
                        
                    print(f"Fetching token from episode page: {ep_url}...")
                    ep_res = requests.get(ep_url, headers=headers, timeout=10)
                    
                    if ep_res.status_code == 200:
                        # Extract wmsAuthSign from the episode player HTML/JS
                        match = re.search(r'wmsAuthSign=([^\s"\'&]+)', ep_res.text)
                        if match:
                            print("Successfully extracted token!")
                            return match.group(1)
        except Exception as e:
            print(f"Error checking {show['name']}: {e}")
            
    print("Error: Could not extract wmsAuthSign token from any episode page.")
    return None

def build_m3u():
    token = fetch_global_token()
    if not token:
        print("Aborting: missing token.")
        return

    m3u_lines = ["#EXTM3U\n"]
    headers = {"User-Agent": USER_AGENT, "Referer": BASE_URL}

    for show in SHOWS_TO_SCRAPE:
        print(f"Scraping episodes for: {show['name']}...")
        res = requests.get(show["url"], headers=headers)
        if res.status_code != 200:
            continue
            
        soup = BeautifulSoup(res.text, "html.parser")
        
        # Show poster / logo
        logo_tag = soup.find("meta", property="og:image")
        show_logo = logo_tag["content"] if logo_tag else ""

        # Extract all episode links
        episodes = soup.find_all("a", href=re.compile(r'/video/'))
        
        for idx, ep in enumerate(episodes):
            ep_title = ep.text.strip() or f"Episódio {idx + 1}"
            
            video_match = re.search(r'video/([a-f0-9]+)', ep['href'])
            if not video_match:
                continue
                
            video_id = video_match.group(1)
            stream_url = f"https://streaming-vod2.iol.pt/vod/smil:{video_id}-L.smil/playlist.m3u8?wmsAuthSign={token}"
            
            # media="true" forces Kodi PVR to list this item under Recordings / VOD
            m3u_lines.append(
                f'#EXTINF:-1 tvg-logo="{show_logo}" '
                f'group-title="{show["category"]} - {show["name"]}" '
                f'media="true",{show["name"]} - {ep_title}'
            )
            m3u_lines.append("#KODIPROP:inputstream=inputstream.adaptive")
            m3u_lines.append("#KODIPROP:inputstream.adaptive.manifest_type=hls")
            m3u_lines.append(f"#KODIPROP:inputstream.adaptive.manifest_headers=User-Agent={USER_AGENT}&Referer={BASE_URL}/&Origin={BASE_URL}")
            m3u_lines.append(f"#KODIPROP:inputstream.adaptive.stream_headers=User-Agent={USER_AGENT}&Referer={BASE_URL}/&Origin={BASE_URL}")
            m3u_lines.append(f"{stream_url}\n")

    with open("portugal_tvi.m3u", "w", encoding="utf-8") as f:
        f.write("\n".join(m3u_lines))

    print("Saved playlist as portugal_tvi.m3u successfully!")

if __name__ == "__main__":
    build_m3u()
