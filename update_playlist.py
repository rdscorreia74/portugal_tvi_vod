import requests

BASE_URL = "https://tviplayer.iol.pt"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

# Show IDs extracted from TVI Player API
SHOWS_TO_SCRAPE = [
    {
        "name": "Dois às 10",
        "category": "Entretenimento",
        "id": "5fdcb61a0cf2432ec4cb03e2"
    },
    {
        "name": "Goucha",
        "category": "Entretenimento",
        "id": "5fe350a40cf2febe232a5ff5"
    }
]

def fetch_global_token():
    """Try to grab wmsAuthSign from TVI's public token API."""
    headers = {"User-Agent": USER_AGENT, "Referer": BASE_URL}
    try:
        res = requests.get("https://services.iol.pt/matrix/init/tviplayer", headers=headers, timeout=10)
        if res.status_code == 200:
            data = res.json()
            return data.get("wmsAuthSign") or data.get("token") or ""
    except Exception as e:
        print(f"Token fetch error: {e}")
    return ""

def get_show_episodes(show_id):
    """Fetch episodes using TVI's API endpoint."""
    headers = {"User-Agent": USER_AGENT, "Referer": BASE_URL}
    # TVI API endpoint for program videos
    api_url = f"https://tviplayer.iol.pt/api/v1/program/{show_id}/videos/1/10"
    
    try:
        res = requests.get(api_url, headers=headers, timeout=10)
        if res.status_code == 200:
            data = res.json()
            # Extract video items from API response
            if isinstance(data, dict):
                return data.get("videos", data.get("data", []))
            elif isinstance(data, list):
                return data
    except Exception as e:
        print(f"Error fetching API for {show_id}: {e}")
    return []

def build_m3u():
    token = fetch_global_token()
    if token:
        print("Successfully obtained wmsAuthSign token!")
    else:
        print("Proceeding without auth token (will build standard stream URLs).")

    m3u_lines = ["#EXTM3U"]
    auth_suffix = f"?wmsAuthSign={token}" if token else ""

    for show in SHOWS_TO_SCRAPE:
        print(f"Fetching episodes for: {show['name']}...")
        episodes = get_show_episodes(show["id"])
        
        print(f"Found {len(episodes)} episodes for {show['name']}")

        for idx, ep in enumerate(episodes):
            video_id = ep.get("id") or ep.get("videoId")
            if not video_id:
                continue

            ep_title = ep.get("title") or f"Episódio {idx + 1}"
            show_logo = ep.get("cover") or ep.get("image") or ""
            
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

    # Write out the file line by line
    content = "\n".join(m3u_lines) + "\n"
    with open("portugal_tvi.m3u", "w", encoding="utf-8") as f:
        f.write(content)

    print("Saved playlist as portugal_tvi.m3u successfully!")

if __name__ == "__main__":
    build_m3u()
