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
    """Attempts to grab wmsAuthSign token from TVI's public Matrix API."""
    headers = {"User-Agent": USER_AGENT, "Referer": BASE_URL}
    try:
        res = requests.get("https://services.iol.pt/matrix/init/tviplayer", headers=headers, timeout=10)
        if res.status_code == 200:
            data = res.json()
            token = data.get("wmsAuthSign") or data.get("token") or ""
            if token:
                print("Token successfully retrieved from API!")
                return token
    except Exception as e:
        print(f"Token retrieval note: {e}")
    return ""

def build_m3u():
    token = fetch_global_token()
    m3u_lines = ["#EXTM3U"]
    headers = {"User-Agent": USER_AGENT, "Referer": BASE_URL}
    auth_suffix = f"?wmsAuthSign={token}" if token else ""

    for show in SHOWS_TO_SCRAPE:
        print(f"Fetching page for show: {show['name']}...")
        try:
            res = requests.get(show["url"], headers=headers, timeout=10)
            print(f"[{show['name']}] HTTP Status: {res.status_code}, Page Size: {len(res.text)} bytes")

            if res.status_code != 200:
                continue

            soup = BeautifulSoup(res.text, "html.parser")

            # Extract logo/cover image from meta tags
            logo_tag = soup.find("meta", property="og:image")
            show_logo = logo_tag["content"] if logo_tag and logo_tag.has_attr("content") else ""

            # Search for any links containing /video/ in href
            video_links = soup.find_all("a", href=re.compile(r'/video/'))
            
            # Fallback: search raw HTML for video href patterns if BeautifulSoup tags missed any
            if not video_links:
                raw_hrefs = re.findall(r'href=["\']([^"\']*?/video/[^"\']+)["\']', res.text)
                episodes_found = list(set(raw_hrefs))
            else:
                episodes_found = []
                for a in video_links:
                    href = a.get("href", "")
                    title = a.text.strip()
                    if href and href not in [e[0] for e in episodes_found]:
                        episodes_found.append((href, title))

            print(f"[{show['name']}] Found {len(episodes_found)} raw video links.")

            added_ids = set()
            count = 0

            for ep in episodes_found:
                href = ep[0] if isinstance(ep, tuple) else ep
                title = ep[1] if isinstance(ep, tuple) and ep[1] else ""

                # Extract 24-char hex ID for the video stream
                video_match = re.search(r'video/([a-f0-9]{24})', href)
                if not video_match:
                    video_match = re.search(r'([a-f0-9]{24})', href)
                    if not video_match or video_match.group(1) in show["url"]:
                        continue

                video_id = video_match.group(1)
                if video_id in added_ids:
                    continue

                added_ids.add(video_id)
                count += 1
                if count > 10:  # Limit to top 10 latest episodes
                    break

                ep_title = title if title else f"Episódio {count}"
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
                m3u_lines.append(stream_url)

        except Exception as e:
            print(f"Error scraping {show['name']}: {e}")

    content = "\n".join(m3u_lines) + "\n"
    with open("portugal_tvi.m3u", "w", encoding="utf-8") as f:
        f.write(content)

    print("Saved playlist as portugal_tvi.m3u successfully!")

if __name__ == "__main__":
    build_m3u()
