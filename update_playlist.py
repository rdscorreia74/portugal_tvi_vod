import json
import re
import requests
from bs4 import BeautifulSoup

BASE_URL = "https://tviplayer.iol.pt"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

SHOWS_TO_SCRAPE = [
    {
        "name": "Dois às 10",
        "category": "Entretenimento",
        "url": "https://tviplayer.iol.pt/programa/dois-as-10",
        "max_episodes": 30
    },
    {
        "name": "Goucha",
        "category": "Entretenimento",
        "url": "https://tviplayer.iol.pt/programa/goucha",
        "max_episodes": 30
    }
]

def fetch_wms_token():
    """Fetches a valid wmsAuthSign token directly from TVI's auth service."""
    headers = {
        "User-Agent": USER_AGENT,
        "Referer": "https://tviplayer.iol.pt/",
        "Origin": "https://tviplayer.iol.pt"
    }
    endpoints = [
        "https://services.iol.pt/matrix/init/tviplayer",
        "https://tviplayer.iol.pt/api/v1/init"
    ]
    
    for ep in endpoints:
        try:
            res = requests.get(ep, headers=headers, timeout=10)
            if res.status_code == 200:
                data = res.json()
                token = data.get("wmsAuthSign") or data.get("token")
                if token:
                    print(f"Obtained wmsAuthSign token from API: {token[:15]}...")
                    return token
        except Exception as e:
            print(f"Error checking token endpoint {ep}: {e}")

    return ""

def build_m3u():
    token = fetch_wms_token()
    token_param = f"?wmsAuthSign={token}" if token else ""
    
    m3u_lines = ["#EXTM3U"]
    headers = {"User-Agent": USER_AGENT, "Referer": BASE_URL}

    for show in SHOWS_TO_SCRAPE:
        print(f"Scraping metadata for: {show['name']}...")
        try:
            res = requests.get(show["url"], headers=headers, timeout=15)
            if res.status_code != 200:
                print(f"Failed to load show page for {show['name']} (HTTP {res.status_code})")
                continue

            soup = BeautifulSoup(res.text, "html.parser")
            
            # Default show logo fallback from meta og:image
            meta_logo = soup.find("meta", property="og:image")
            show_logo = meta_logo["content"] if meta_logo and meta_logo.has_attr("content") else ""

            episodes_data = []

            # 1. Try extracting structured JSON from __NEXT_DATA__
            next_data_script = soup.find("script", id="__NEXT_DATA__")
            if next_data_script and next_data_script.string:
                try:
                    json_data = json.loads(next_data_script.string)
                    # Traverse JSON to find episode arrays
                    props = json_data.get("props", {}).get("pageProps", {})
                    episodes_list = props.get("videos", []) or props.get("episodes", []) or props.get("initialData", {}).get("videos", [])
                    
                    for ep in episodes_list:
                        vid_id = ep.get("id") or ep.get("videoId") or ep.get("_id")
                        title = ep.get("title") or ep.get("name", "")
                        summary = ep.get("description") or ep.get("synopsis") or ep.get("summary", "")
                        cover = ep.get("cover") or ep.get("image") or ep.get("thumbnailUrl", show_logo)
                        
                        if vid_id:
                            episodes_data.append({
                                "id": vid_id,
                                "title": title,
                                "summary": summary,
                                "logo": cover
                            })
                except Exception as json_err:
                    print(f"Error parsing JSON state: {json_err}")

            # 2. Fallback: Parse video cards from HTML DOM directly
            if not episodes_data:
                video_cards = soup.find_all(["article", "div", "a"], href=re.compile(r'/video/|/episodio/'))
                for card in video_cards:
                    href = card.get("href") or (card.find("a") and card.find("a").get("href"))
                    if not href:
                        continue

                    vid_match = re.search(r'([a-f0-9]{24})', href)
                    if not vid_match:
                        continue

                    vid_id = vid_match.group(1)
                    
                    # Extract title & summary text
                    title_elem = card.find(["h2", "h3", "h4", "span", "p"])
                    title = title_elem.text.strip() if title_elem else ""

                    img_elem = card.find("img")
                    img_url = img_elem.get("src") or img_elem.get("data-src") if img_elem else show_logo

                    if not any(e["id"] == vid_id for e in episodes_data):
                        episodes_data.append({
                            "id": vid_id,
                            "title": title,
                            "summary": "",
                            "logo": img_url or show_logo
                        })

            limit = show.get("max_episodes", 30)
            episodes_data = episodes_data[:limit]
            print(f"[{show['name']}] Found {len(episodes_data)} detailed episodes.")

            for idx, ep in enumerate(episodes_data):
                video_id = ep["id"]
                ep_title = ep["title"] if ep["title"] else f"Episódio {idx + 1}"
                ep_logo = ep["logo"] if ep["logo"] else show_logo
                ep_summary = ep["summary"].replace("\n", " ").strip() if ep["summary"] else ""

                stream_url = f"https://streaming-vod2.iol.pt/vod/smil:{video_id}-L.smil/playlist.m3u8{token_param}"

                # Construct M3U entry with metadata tags
                m3u_lines.append(
                    f'#EXTINF:-1 tvg-logo="{ep_logo}" '
                    f'group-title="{show["category"]} - {show["name"]}" '
                    f'tvg-name="{show["name"]} - {ep_title}" '
                    f'group-logo="{show_logo}",{show["name"]} - {ep_title}'
                )
                if ep_summary:
                    m3u_lines.append(f'#EXTVLCOPT:description={ep_summary}')
                
                # Kodi InputStream Adaptive Headers
                m3u_lines.append("#KODIPROP:inputstream=inputstream.adaptive")
                m3u_lines.append("#KODIPROP:inputstream.adaptive.manifest_type=hls")
                m3u_lines.append(f"#KODIPROP:inputstream.adaptive.manifest_headers=User-Agent={USER_AGENT}&Referer={BASE_URL}/&Origin={BASE_URL}")
                m3u_lines.append(f"#KODIPROP:inputstream.adaptive.stream_headers=User-Agent={USER_AGENT}&Referer={BASE_URL}/&Origin={BASE_URL}")
                m3u_lines.append(stream_url)

        except Exception as e:
            print(f"Error scraping {show['name']}: {e}")

    content = "\n".join(m3u_lines) + "\n"
    with open("portugal_tvi.m3u", "w", encoding="utf-8") as f:
        f.write(content)

    print("Saved playlist as portugal_tvi.m3u successfully!")

if __name__ == "__main__":
    build_m3u()
