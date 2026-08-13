import re
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup

BASE_URL = "https://tviplayer.iol.pt"

SHOWS_TO_SCRAPE = [
    {
        "name": "Dois às 10",
        "category": "Entretenimento",
        "url": "https://tviplayer.iol.pt/programa/dois-as-10"
    },
    {
        "name": "Goucha",
        "category": "Entretenimento",
        "url": "https://tviplayer.iol.pt/programa/goucha"
    }
]

def build_m3u():
    m3u_lines = ["#EXTM3U"]

    with sync_playwright() as p:
        # Launch headless Chromium with standard desktop viewport
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 720}
        )
        page = context.new_page()

        for show in SHOWS_TO_SCRAPE:
            print(f"Loading page for show: {show['name']}...")
            try:
                # Go to show page and wait until DOM content is fully loaded
                response = page.goto(show["url"], wait_until="domcontentloaded", timeout=30000)
                status = response.status if response else "Unknown"
                print(f"[{show['name']}] Response Status: {status}")

                # Wait 3 seconds for dynamic content to render
                page.wait_for_timeout(3000)
                html_content = page.content()

                soup = BeautifulSoup(html_content, "html.parser")

                # Extract cover image
                logo_tag = soup.find("meta", property="og:image")
                show_logo = logo_tag["content"] if logo_tag and logo_tag.has_attr("content") else ""

                # Find episode video IDs from rendered HTML
                matches = re.findall(r'([a-f0-9]{24})', html_content)
                
                # Deduplicate and clean IDs
                video_ids = []
                for vid in matches:
                    if vid not in video_ids:
                        video_ids.append(vid)

                print(f"[{show['name']}] Extracted {len(video_ids)} video IDs.")

                count = 0
                for vid in video_ids:
                    count += 1
                    if count > 10:
                        break

                    ep_title = f"Episódio {count}"
                    stream_url = f"https://streaming-vod2.iol.pt/vod/smil:{vid}-L.smil/playlist.m3u8"

                    m3u_lines.append(
                        f'#EXTINF:-1 tvg-logo="{show_logo}" '
                        f'group-title="{show["category"]} - {show["name"]}" '
                        f'media="true",{show["name"]} - {ep_title}'
                    )
                    m3u_lines.append("#KODIPROP:inputstream=inputstream.adaptive")
                    m3u_lines.append("#KODIPROP:inputstream.adaptive.manifest_type=hls")
                    m3u_lines.append(f"#KODIPROP:inputstream.adaptive.manifest_headers=User-Agent=Mozilla/5.0&Referer={BASE_URL}/&Origin={BASE_URL}")
                    m3u_lines.append(f"#KODIPROP:inputstream.adaptive.stream_headers=User-Agent=Mozilla/5.0&Referer={BASE_URL}/&Origin={BASE_URL}")
                    m3u_lines.append(stream_url)

            except Exception as e:
                print(f"Error rendering {show['name']}: {e}")

        browser.close()

    content = "\n".join(m3u_lines) + "\n"
    with open("portugal_tvi.m3u", "w", encoding="utf-8") as f:
        f.write(content)

    print("Saved playlist as portugal_tvi.m3u successfully!")

if __name__ == "__main__":
    build_m3u()
