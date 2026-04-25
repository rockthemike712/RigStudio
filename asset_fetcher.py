import os
import re
import sys
import requests
import yt_dlp

BING_ENDPOINT = "https://api.bing.microsoft.com/v7.0/images/search"
VALID_EXTENSIONS = {"jpg", "jpeg", "png", "webp", "gif"}
MAX_IMAGE_BYTES = 20 * 1024 * 1024  # 20 MB

_USER_AGENT = "Mozilla/5.0 (compatible; AssetFetcher/1.0)"


def _get_api_key() -> str:
    key = os.environ.get("BING_API_KEY", "")
    if not key:
        sys.exit("Error: BING_API_KEY environment variable is not set.")
    return key


def _safe_filename(query: str) -> str:
    """Reduce an arbitrary query string to a safe, filesystem-friendly name."""
    return re.sub(r"[^a-z0-9_-]", "_", query.lower()).strip("_")


def _parse_extension(url: str) -> str:
    """Extract a validated image extension from a URL, defaulting to 'jpg'."""
    path = url.split("?")[0]
    ext = path.rsplit(".", 1)[-1].lower() if "." in path else ""
    return ext if ext in VALID_EXTENSIONS else "jpg"


def download_bing_images(query: str, max_results: int = 3, output_folder: str = "assets/images") -> None:
    """Fetch up to max_results images matching query from Bing Image Search."""
    os.makedirs(output_folder, exist_ok=True)
    headers = {
        "Ocp-Apim-Subscription-Key": _get_api_key(),
        "User-Agent": _USER_AGENT,
    }
    params = {
        "q": query,
        "count": max_results,
        "imageType": "Photo",
        "safeSearch": "Moderate",
    }

    print(f"Searching Bing for: {query}...")
    try:
        response = requests.get(BING_ENDPOINT, headers=headers, params=params, timeout=10)
        response.raise_for_status()
    except requests.RequestException as e:
        print(f"Bing API error for '{query}': {e}")
        return

    results = response.json().get("value", [])
    base_name = _safe_filename(query)

    for i, img in enumerate(results):
        img_url = img.get("contentUrl", "")
        if not img_url:
            continue

        ext = _parse_extension(img_url)
        filename = f"{base_name}_{i + 1}.{ext}"
        filepath = os.path.join(output_folder, filename)

        if os.path.exists(filepath):
            print(f"Skipping (already exists): {filename}")
            continue

        try:
            with requests.get(img_url, headers={"User-Agent": _USER_AGENT}, timeout=10, stream=True) as r:
                r.raise_for_status()
                downloaded = 0
                chunks = []
                for chunk in r.iter_content(chunk_size=65536):
                    downloaded += len(chunk)
                    if downloaded > MAX_IMAGE_BYTES:
                        print(f"Skipping {filename}: response exceeds {MAX_IMAGE_BYTES // (1024*1024)} MB limit.")
                        break
                    chunks.append(chunk)
                else:
                    with open(filepath, "wb") as f:
                        for chunk in chunks:
                            f.write(chunk)
                    print(f"Downloaded: {filename}")
        except requests.RequestException as e:
            print(f"Failed to download {filename}: {e}")


def download_youtube_clip(query: str, max_results: int = 1, output_folder: str = "assets/videos") -> None:
    """Search YouTube and download the top result(s) as MP4 via yt-dlp."""
    os.makedirs(output_folder, exist_ok=True)
    print(f"Searching YouTube for: {query}...")

    ydl_opts = {
        "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        "outtmpl": os.path.join(output_folder, "%(title)s.%(ext)s"),
        "noplaylist": True,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            ydl.download([f"ytsearch{max_results}:{query}"])
            print("Video download complete.")
        except Exception as e:
            print(f"Error downloading video for '{query}': {e}")


if __name__ == "__main__":
    download_bing_images("Mark Zuckerberg Senate Hearing 2024", max_results=2)
    download_youtube_clip("Tim Cook CNBC interview snippet", max_results=1)
