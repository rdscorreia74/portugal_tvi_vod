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

def extract_token(text):
    """Search for wmsAuthSign across URL parameters, JS variables, and JSON strings."""
    patterns = [
        r'wmsAuthSign=([^\s"\'&]+)',
        r'["\']wmsAuthSign["\']\s*:\s*["\']([^"\'\s]+)["\']',
        r'wmsAuthSign["\']?\s*=\s*["\']([^"\'\s]+)["\']'
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(1)
    return None

def fetch_global_token():
    headers = {"User-Agent": USER_AGENT, "Referer": BASE_URL}
    
    # 1. Primary Method: TVI Direto player page (guaranteed to contain active wmsAuthSign token)
    print("Fetching global token from TVI Direto...")
    try:
        res = requests.get(f"{BASE_URL}/direto", headers=headers, timeout=10)
        if res.status_code == 200:
            token = extract_token(res.text)
            if token:
                print("Successfully extracted token from Direto!")
                return token
    except Exception as e:
        print(f"Error checking Direto page: {e}")

    # 2. Fallback: Search show pages directly
    for show in SHOWS_TO_SCRAPE:
        print(f"Fallback searching: {show['name']}...")
        try:
            res = requests.get(show["url"], headers=headers, timeout=10)
            if res.status_code == 200:
                token = extract_token(res.text)
                if token:
                    print("Successfully extracted token!")
                    return token
        except Exception as e:
            print(f"Error checking {show['name']}: {e}")

    print("Error: Could not extract wmsAuthSign token from any source.")
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
        
        # Extract show poster / logo
        logo_tag = soup.find("meta", property="og:image")
        show_logo = logo_tag["content"] if logo_tag else ""

        # Extract 24-character hexadecimal video IDs from any links or attributes
        video_ids = list(set(re.findall(r'[a-f0-9]{24}', res.text)))
        
        # Filter out the show ID itself if present in URL
        show_id_match = re.search(r'[a-f0-9]{24}', show["url"])
        if show_id_match:
            show_id = show_id_match.group(0)
            video_ids = [v for v in video_ids if v != show_id]

        print(f"Found {len(video_ids)} episode video IDs for {show['name']}")

        for idx, video_id in enumerate(video_ids[:10]):  # Limit to 10 latest episodes per show
            ep_title = f"Episódio {idx + 1}"
            stream_url = f"https://streaming-vod2.iol.pt/vod/smil:{video_id}-L.smil/playlist.m3u8?wmsAuthSign={token}"
            
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
