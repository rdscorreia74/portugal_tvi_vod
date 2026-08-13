import re
import json
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
    headers = {
        "User-Agent": USER_AGENT,
        "Referer": BASE_URL,
        "Accept": "application/json, text/plain, */*"
    }
    
    # Method 1: Fetch via TVI's Matrix token API endpoint
    print("Trying TVI Auth API...")
    try:
        api_res = requests.get("https://services.iol.pt/matrix/init/tviplayer", headers=headers, timeout=10)
        if api_res.status_code == 200:
            data = api_res.json()
            token = data.get("wmsAuthSign") or data.get("token")
            if token:
                print("Successfully obtained token from API!")
                return token
    except Exception as e:
        print(f"API attempt failed: {e}")

    # Method 2: Extract from page state (JSON blocks in HTML)
    for show in SHOWS_TO_SCRAPE:
        print(f"Checking JSON state for: {show['name']}...")
        try:
            res = requests.get(show["url"], headers={"User-Agent": USER_AGENT, "Referer": BASE_URL}, timeout=10)
            if res.status_code == 200:
                # Look for __NEXT_DATA__ or embedded JSON
                soup = BeautifulSoup(res.text, "html.parser")
                script = soup.find("script", id="__NEXT_DATA__")
                if script and script.string:
                    json_data = json.loads(script.string)
                    # Deep search for wmsAuthSign string in JSON
                    json_str = json.dumps(json_data)
                    match = re.search(r'wmsAuthSign["\']?\s*:\s*["\']([^"\'\s]+)["\']', json_str)
                    if match:
                        print("Successfully extracted token from __NEXT_DATA__!")
                        return match.group(1)

                # Direct regex search on the raw page
                match = re.search(r'wmsAuthSign=([^\s"\'&]+)', res.text)
                if match:
                    print("Successfully extracted token via regex!")
                    return match.group(1)
        except Exception as e:
            print(f"Error checking {show['name']}: {e}")

    print("Error: Could not extract wmsAuthSign token from any source.")
    return None

def build_m3u():
    token = fetch_global_token()
    
    # Fallback to empty token string if unavailable so playlist generates anyway
    if not token:
        print("Warning: Token missing, proceeding without token query param.")
        token = ""

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

        # Find 24-char hex IDs
        video_ids = list(set(re.findall(r'[a-f0-9]{24}', res.text)))
        show_id_match = re.search(r'[a-f0-9]{24}', show["url"])
        if show_id_match:
            video_ids = [v for v in video_ids if v != show_id_match.group(0)]

        print(f"Found {len(video_ids)} episode video IDs for {show['name']}")

        for idx, video_id in enumerate(video_ids[:10]):
            ep_title = f"Episódio {idx + 1}"
            auth_suffix = f"?wmsAuthSign={token}" if token else ""
            stream_url = f"https://streaming-vod2.iol.pt/vod/smil:{video_id}-L.smil/playlist.m3u8{auth_suffix}"
            
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
