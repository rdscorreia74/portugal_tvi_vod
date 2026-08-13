import re
import requests
from bs4 import BeautifulSoup

BASE_URL = "https://tviplayer.iol.pt"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

SHOWS_TO_SCRAPE = [
    {
        "name": "Dois às 10",
        "category": "Entretenimento",
        "rss": "https://tviplayer.iol.pt/rss/programa/dois-as-10/5fdcb61a0cf2432ec4cb03e2"
    },
    {
        "name": "Goucha",
        "category": "Entretenimento",
        "rss": "https://tviplayer.iol.pt/rss/programa/goucha/5fe350a40cf2febe232a5ff5"
    }
]

def fetch_global_token():
    headers = {"User-Agent": USER_AGENT, "Referer": BASE_URL}
    try:
        res = requests.get("https://services.iol.pt/matrix/init/tviplayer", headers=headers, timeout=10)
        if res.status_code == 200:
            data = res.json()
            return data.get("wmsAuthSign") or data.get("token") or ""
    except Exception as e:
        print(f"Token error: {e}")
    return ""

def build_m3u():
    token = fetch_global_token()
    m3u_lines = ["#EXTM3U"]
    headers = {"User-Agent": USER_AGENT, "Referer": BASE_URL}
    auth_suffix = f"?wmsAuthSign={token}" if token else ""

    for show in SHOWS_TO_SCRAPE:
        print(f"Fetching RSS feed for: {show['name']}...")
        try:
            res = requests.get(show["rss"], headers=headers, timeout=10)
            if res.status_code != 200:
                print(f"Failed to load RSS for {show['name']} (HTTP {res.status_code})")
                continue

            # Parse XML feed
            soup = BeautifulSoup(res.text, "xml")
            items = soup.find_all("item")
            print(f"Found {len(items)} episodes in RSS for {show['name']}")

            for idx, item in enumerate(items[:10]):  # Grab 10 latest episodes
                title_tag = item.find("title")
                link_tag = item.find("link")
                
                title = title_tag.text.strip() if title_tag else f"Episódio {idx + 1}"
                link = link_tag.text.strip() if link_tag else ""

                # Extract 24-character hexadecimal video ID from link URL
                video_match = re.search(r'[a-f0-9]{24}', link)
                if not video_match:
                    continue

                video_id = video_match.group(0)
                
                # Check for enclosure/thumbnail image
                media_thumb = item.find("media:thumbnail") or item.find("enclosure")
                show_logo = media_thumb["url"] if media_thumb and media_thumb.has_attr("url") else ""

                stream_url = f"https://streaming-vod2.iol.pt/vod/smil:{video_id}-L.smil/playlist.m3u8{auth_suffix}"

                m3u_lines.append(
                    f'#EXTINF:-1 tvg-logo="{show_logo}" '
                    f'group-title="{show["category"]} - {show["name"]}" '
                    f'media="true",{show["name"]} - {title}'
                )
                m3u_lines.append("#KODIPROP:inputstream=inputstream.adaptive")
                m3u_lines.append("#KODIPROP:inputstream.adaptive.manifest_type=hls")
                m3u_lines.append(f"#KODIPROP:inputstream.adaptive.manifest_headers=User-Agent={USER_AGENT}&Referer={BASE_URL}/&Origin={BASE_URL}")
                m3u_lines.append(f"#KODIPROP:inputstream.adaptive.stream_headers=User-Agent={USER_AGENT}&Referer={BASE_URL}/&Origin={BASE_URL}")
                m3u_lines.append(stream_url)

        except Exception as e:
            print(f"Error reading RSS for {show['name']}: {e}")

    content = "\n".join(m3u_lines) + "\n"
    with open("portugal_tvi.m3u", "w", encoding="utf-8") as f:
        f.write(content)

    print("Saved playlist as portugal_tvi.m3u successfully!")

if __name__ == "__main__":
    build_m3u()
