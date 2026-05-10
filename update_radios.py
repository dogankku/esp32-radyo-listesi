import requests
from datetime import datetime

RADIO_BROWSER_URL = "https://de1.api.radio-browser.info/json/stations/bycountrycodeexact/TR"

KEYWORDS = [
    "dini",
    "islam",
    "islami",
    "kuran",
    "kur'an",
    "quran",
    "tasavvuf",
    "ilah",
    "sohbet",
    "akra",
    "radyo 7",
    "ribat",
    "erkam",
    "semerkand",
    "dost",
    "bayram",
    "lalegul",
    "lalegül",
    "moral",
    "cinar",
    "çınar",
    "fitrat",
    "fıtrat"
]

MANUAL_RADIOS = [
    ("90lar Turkce", "http://37.247.98.8/stream/166/;stream.mp3"),
    ("Turkuler", "http://37.247.98.8/stream/22/"),
    ("Radyo 7", "http://canliyayin.radyo7.com/;stream"),
    ("Radyo 7 Alternatif", "http://46.20.3.251/stream/169/;"),
    ("Akra FM", "http://yayin.akradyo.net:8000/"),
    ("Ribat FM", "http://yayin1.canliyayin.org:7010/;"),
    ("Erkam Radyo", "http://5.44.154.18:9000/;"),
    ("Seyr FM", "http://yayin1.canliyayin.org:8300/"),
    ("Radyo Fitrat", "http://shaincast.caster.fm:22344/listen.mp3"),
    ("Dost Radyo Erzincan", "http://yayin.yayindakiler.com:3156/;stream.mp3"),
    ("Sufi Mistik", "http://37.247.98.8/stream/23/")
]


def clean_text(value):
    return str(value or "").strip()


def is_esp32_compatible(url):
    url = clean_text(url)

    if not url.startswith("http://"):
        return False

    bad_parts = [
        ".m3u8",
        ".m3u",
        ".pls",
        "playlist",
        "video",
        "youtube",
        "youtu.be"
    ]

    low = url.lower()

    for bad in bad_parts:
        if bad in low:
            return False

    return True


def looks_religious(name, tags):
    text = f"{name} {tags}".lower()

    for word in KEYWORDS:
        if word in text:
            return True

    return False


def check_stream(url):
    try:
        headers = {
            "User-Agent": "ESP32-Radio-Updater/1.0"
        }

        r = requests.get(
            url,
            headers=headers,
            stream=True,
            timeout=8,
            allow_redirects=True
        )

        if r.status_code >= 400:
            return False

        content_type = r.headers.get("content-type", "").lower()

        good_types = [
            "audio",
            "mpeg",
            "mp3",
            "octet-stream",
            "application/ogg"
        ]

        if any(t in content_type for t in good_types):
            return True

        chunk = next(r.iter_content(chunk_size=64), b"")

        if chunk.startswith(b"ID3"):
            return True

        return False

    except Exception:
        return False


def fetch_radio_browser():
    params = {
        "hidebroken": "true",
        "order": "votes",
        "reverse": "true",
        "limit": "500"
    }

    headers = {
        "User-Agent": "ESP32-Radio-Updater/1.0"
    }

    r = requests.get(
        RADIO_BROWSER_URL,
        params=params,
        headers=headers,
        timeout=20
    )

    r.raise_for_status()

    return r.json()


def main():
    radios = {}

    for name, url in MANUAL_RADIOS:
        if is_esp32_compatible(url):
            radios[name] = url

    try:
        stations = fetch_radio_browser()
    except Exception as e:
        print("Radio Browser alınamadı:", e)
        stations = []

    for st in stations:
        name = clean_text(st.get("name"))
        tags = clean_text(st.get("tags"))
        url = clean_text(st.get("url_resolved") or st.get("url"))

        if not name or not url:
            continue

        if not looks_religious(name, tags):
            continue

        if not is_esp32_compatible(url):
            continue

        if len(radios) >= 50:
            break

        if check_stream(url):
            radios[name] = url

    lines = []

    lines.append("# Otomatik güncellendi: " + datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"))

    for name, url in radios.items():
        safe_name = name.replace("|", " ").strip()
        safe_url = url.replace("|", "").strip()
        lines.append(f"{safe_name}|{safe_url}")

    output = "\n".join(lines) + "\n"

    with open("radyolar.txt", "w", encoding="utf-8") as f:
        f.write(output)

    print("Toplam kanal:", len(radios))


if __name__ == "__main__":
    main()
