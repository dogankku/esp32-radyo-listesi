import requests
from datetime import datetime

RADIO_BROWSER_URL = "https://de1.api.radio-browser.info/json/stations/bycountrycodeexact/TR"

MAX_RADIOS = 40

# Her zaman listede kalacak, test ettiğimiz güvenli radyolar
MANUAL_RADIOS = [
    ("90lar Turkce", "http://37.247.98.8/stream/166/;stream.mp3"),
    ("Turkuler", "http://37.247.98.8/stream/22/"),
    ("Radyo 7", "http://46.20.3.251/stream/169/;"),
]

# Dini / islami radyo aramak için anahtar kelimeler
KEYWORDS = [
    "dini",
    "islam",
    "islami",
    "kuran",
    "kur'an",
    "quran",
    "ilah",
    "ilahi",
    "sohbet",
    "tasavvuf",
    "akra",
    "radyo 7",
    "ribat",
    "erkam",
    "semerkand",
    "lalegul",
    "lalegül",
    "moral",
    "cinar",
    "çınar",
    "fitrat",
    "fıtrat",
    "sufi",
]

# ESP32'yi kilitleyen veya uygun olmayan linkleri engelle
BLACKLIST_PARTS = [
    "yayin.yayindakiler.com:3156",
    "diyanet.gov.tr:8000",
    ".m3u8",
    ".m3u",
    ".pls",
    "playlist",
    "video",
    "videoonlylive",
    "youtube",
    "youtu.be",
    "spotify",
    "soundcloud",
]


def clean(value):
    return str(value or "").strip()


def is_blacklisted(url):
    low = url.lower()
    return any(bad in low for bad in BLACKLIST_PARTS)


def is_esp32_url(url):
    url = clean(url)

    if not url.startswith("http://"):
        return False

    if is_blacklisted(url):
        return False

    return True


def looks_religious(name, tags):
    text = f"{name} {tags}".lower()
    return any(word in text for word in KEYWORDS)


def check_stream(url):
    try:
        headers = {
            "User-Agent": "ESP32-Radio-Checker/1.0",
            "Icy-MetaData": "1",
        }

        r = requests.get(
            url,
            headers=headers,
            stream=True,
            timeout=8,
            allow_redirects=True,
        )

        final_url = r.url or url

        # Redirect https'e gittiyse ESP32 için alma
        if not final_url.startswith("http://"):
            r.close()
            return False

        if r.status_code >= 400:
            r.close()
            return False

        content_type = r.headers.get("content-type", "").lower()

        good_content_types = [
            "audio",
            "mpeg",
            "mp3",
            "aacp",
            "octet-stream",
        ]

        if any(x in content_type for x in good_content_types):
            r.close()
            return True

        chunk = b""
        try:
            chunk = next(r.iter_content(chunk_size=128), b"")
        except Exception:
            pass

        r.close()

        # MP3 ID3 başlangıcı
        if chunk.startswith(b"ID3"):
            return True

        # MPEG frame başlangıcı
        if len(chunk) >= 2 and chunk[0] == 0xFF and (chunk[1] & 0xE0) == 0xE0:
            return True

        return False

    except Exception:
        return False


def fetch_radio_browser():
    params = {
        "hidebroken": "true",
        "order": "votes",
        "reverse": "true",
        "limit": "500",
    }

    headers = {
        "User-Agent": "ESP32-Radio-Updater/1.0",
    }

    r = requests.get(
        RADIO_BROWSER_URL,
        params=params,
        headers=headers,
        timeout=20,
    )

    r.raise_for_status()
    return r.json()


def add_radio(radios, name, url, check=False):
    name = clean(name).replace("|", " ")
    url = clean(url).replace("|", "")

    if not name or not is_esp32_url(url):
        return

    if check and not check_stream(url):
        return

    if url in radios.values():
        return

    radios[name] = url


def main():
    radios = {}

    # Önce güvenli manuel liste
    for name, url in MANUAL_RADIOS:
        add_radio(radios, name, url, check=False)

    # Sonra otomatik bulunanlar
    try:
        stations = fetch_radio_browser()
    except Exception as e:
        print("Radio Browser alınamadı:", e)
        stations = []

    for st in stations:
        if len(radios) >= MAX_RADIOS:
            break

        name = clean(st.get("name"))
        tags = clean(st.get("tags"))
        url = clean(st.get("url_resolved") or st.get("url"))

        if not name or not url:
            continue

        if not looks_religious(name, tags):
            continue

        add_radio(radios, name, url, check=True)

    lines = []
    lines.append("# Otomatik güncellendi: " + datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"))

    for name, url in radios.items():
        lines.append(f"{name}|{url}")

    output = "\n".join(lines) + "\n"

    with open("radyolar.txt", "w", encoding="utf-8") as f:
        f.write(output)

    print("Toplam kanal:", len(radios))
    print(output)


if __name__ == "__main__":
    main()
