import json
import re
import requests
from playwright.sync_api import sync_playwright

BASE_URL = "https://tviplayer.iol.pt"

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
    """Grab a wmsAuthSign token directly from TVI's public service endpoint."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://tviplayer.iol.pt/",
        "Origin": "https://tviplayer.iol.pt"
    }
    try:
        res = requests.get("https://services.iol.pt/matrix/init/tviplayer", headers=headers, timeout=10)
        if res.status_code == 200:
            data = res.json()
            token = data.get("wmsAuthSign") or data.get("token") or ""
            if token:
                print(f"Obtained wmsAuthSign token: {token[:15]}...")
                return token
    except Exception as e:
        print(f"Token fetch note: {e}")
    return ""

def build_m3u():
    token = fetch_wms_token()
    token_param = f"?wmsAuthSign={token}" if token else ""
    
    m3u_lines = ["#EXTM3U"]

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 720}
        )
        page = context.new_page()

        for show in SHOWS_TO_SCRAPE:
            print(f"Loading page via Playwright for: {show['name']}...")
            try:
                page.goto(show["url"], wait_until="domcontentloaded", timeout=30000)
                page.wait_for_timeout(3000)  # Allow JS hydration

                html_content = page.content()

                # Extract default show logo from og:image meta tag
                meta_logo_match = re.search(r'<meta[^>]*property=["\']og:image["\'][^>]*content=["\']([^"\']+)["\']', html_content)
                show_logo = meta_logo_match.group(1) if meta_logo_match else ""

                episodes_data = []

                # 1. Look for __NEXT_DATA__ JSON payload in the rendered page
                next_data_match = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', html_content, re.DOTALL)
                if next_data_match:
                    try:
                        json_data = json.loads(next_data_match.group(1))
                        props = json_data.get("props", {}).get("pageProps", {})
                        
                        # Find episode lists dynamically in pageProps
                        ep_list = props.get("videos", []) or props.get("episodes", []) or props.get("initialData", {}).get("videos", [])
                        
                        for ep in ep_list:
                            vid_id = ep.get("id") or ep.get("videoId") or ep.get("_id")
                            if not vid_id:
                                continue
                            
                            episodes_data.append({
                                "id": vid_id,
                                "title": ep.get("title") or ep.get("name") or "",
                                "summary": ep.get("description") or ep.get("synopsis") or "",
                                "logo": ep.get("cover") or ep.get("image") or ep.get("thumbnailUrl") or show_logo
                            })
                    except Exception as json_err:
                        print(f"JSON parsing fallback: {json_err}")

                # 2. Fallback: Parse 24-character hexadecimal video IDs if JSON structure varies
                if not episodes_data:
                    raw_ids = re.findall(r'([a-f0-9]{24})', html_content)
                    seen = set()
                    for vid in raw_ids:
                        if vid not in seen:
                            seen.add(vid)
                            episodes_data.append({
                                "id": vid,
                                "title": "",
                                "summary": "",
                                "logo": show_logo
                            })

                limit = show.get("max_episodes", 30)
                episodes_data = episodes_data[:limit]
                print(f"[{show['name']}] Successfully processed {len(episodes_data)} episodes.")

                for idx, ep in enumerate(episodes_data):
                    video_id = ep["id"]
                    ep_title = ep["title"] if ep["title"] else f"Episódio {idx + 1}"
                    ep_logo = ep["logo"] if ep["logo"] else show_logo
                    ep_summary = ep["summary"].replace("\n", " ").strip() if ep["summary"] else ""

                    stream_url = f"https://streaming-vod2.iol.pt/vod/smil:{video_id}-L.smil/playlist.m3u8{token_param}"

                    m3u_lines.append(
                        f'#EXTINF:-1 tvg-logo="{ep_logo}" '
                        f'group-title="{show["category"]} - {show["name"]}" '
                        f'tvg-name="{show["name"]} - {ep_title}" '
                        f'group-logo="{show_logo}",{show["name"]} - {ep_title}'
                    )
                    if ep_summary:
                        m3u_lines.append(f'#EXTVLCOPT:description={ep_summary}')
                    
                    m3u_lines.append("#KODIPROP:inputstream=inputstream.adaptive")
                    m3u_lines.append("#KODIPROP:inputstream.adaptive.manifest_type=hls")
                    m3u_lines.append(f"#KODIPROP:inputstream.adaptive.manifest_headers=User-Agent=Mozilla/5.0&Referer={BASE_URL}/&Origin={BASE_URL}")
                    m3u_lines.append(f"#KODIPROP:inputstream.adaptive.stream_headers=User-Agent=Mozilla/5.0&Referer={BASE_URL}/&Origin={BASE_URL}")
                    m3u_lines.append(stream_url)

            except Exception as e:
                print(f"Error reading {show['name']}: {e}")

        browser.close()

    content = "\n".join(m3u_lines) + "\n"
    with open("portugal_tvi.m3u", "w", encoding="utf-8") as f:
        f.write(content)

    print("Saved playlist as portugal_tvi.m3u successfully!")

if __name__ == "__main__":
    build_m3u()
