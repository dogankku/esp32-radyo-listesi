import base64
import datetime
import requests
import streamlit as st

OWNER = "dogankku"
REPO = "esp32-radyo-listesi"
BRANCH = "main"
FILE_PATH = "radyolar.txt"

RAW_URL = f"https://raw.githubusercontent.com/{OWNER}/{REPO}/{BRANCH}/{FILE_PATH}"
API_URL = f"https://api.github.com/repos/{OWNER}/{REPO}/contents/{FILE_PATH}"

CATEGORIES = [
    "Pop",
    "Turku",
    "Dini",
    "Karadeniz",
    "Klasik",
    "Arabesk",
    "Yabanci",
    "Haber",
    "Genel",
]

BLACKLIST = [
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
    "yayin.yayindakiler.com:3156",
    "diyanet.gov.tr:8000",
]


st.set_page_config(
    page_title="ESP32 Radyo Paneli",
    page_icon="📻",
    layout="wide",
)


def get_token():
    try:
        return st.secrets["GITHUB_TOKEN"]
    except Exception:
        return ""


def is_valid_esp32_url(url: str):
    url = (url or "").strip()

    if not url.startswith("http://"):
        return False, "ESP32 için yayın linki http:// ile başlamalı."

    low = url.lower()

    for bad in BLACKLIST:
        if bad in low:
            return False, f"Bu link ESP32 için uygun değil: {bad}"

    return True, "OK"


def parse_radios(text: str):
    radios = []

    for line in text.splitlines():
        line = line.strip()

        if not line or line.startswith("#"):
            continue

        parts = line.split("|")

        if len(parts) == 3:
            category, name, url = parts
        elif len(parts) == 2:
            category = "Genel"
            name, url = parts
        else:
            continue

        category = category.strip()
        name = name.strip()
        url = url.strip()

        if category and name and url:
            radios.append(
                {
                    "Kategori": category,
                    "Radyo": name,
                    "URL": url,
                }
            )

    return radios


def make_text(radios):
    lines = []
    now = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    lines.append(f"# Panelden güncellendi: {now}")

    for r in radios:
        category = str(r.get("Kategori", "Genel")).replace("|", " ").strip()
        name = str(r.get("Radyo", "")).replace("|", " ").strip()
        url = str(r.get("URL", "")).replace("|", "").strip()

        if not category:
            category = "Genel"

        if name and url:
            lines.append(f"{category}|{name}|{url}")

    return "\n".join(lines) + "\n"


def load_from_github():
    token = get_token()

    if not token:
        st.error("GITHUB_TOKEN yok. Streamlit Secrets içine eklemelisin.")
        return "", None

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
    }

    r = requests.get(API_URL, headers=headers, timeout=20)

    if r.status_code != 200:
        st.error(f"GitHub dosyası okunamadı. HTTP {r.status_code}")
        st.code(r.text)
        return "", None

    data = r.json()
    sha = data.get("sha")
    content = data.get("content", "")

    decoded = base64.b64decode(content).decode("utf-8")

    return decoded, sha


def save_to_github(text, sha):
    token = get_token()

    if not token:
        st.error("GITHUB_TOKEN yok.")
        return False

    encoded = base64.b64encode(text.encode("utf-8")).decode("utf-8")

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
    }

    payload = {
        "message": "Radyo listesi panelden güncellendi",
        "content": encoded,
        "branch": BRANCH,
    }

    if sha:
        payload["sha"] = sha

    r = requests.put(API_URL, headers=headers, json=payload, timeout=20)

    if r.status_code not in [200, 201]:
        st.error(f"GitHub kaydetme hatası. HTTP {r.status_code}")
        st.code(r.text)
        return False

    return True


def load_radio_browser(country="TR", limit=100):
    url = f"https://de1.api.radio-browser.info/json/stations/bycountrycodeexact/{country}"
    params = {
        "hidebroken": "true",
        "order": "votes",
        "reverse": "true",
        "limit": str(limit),
    }
    headers = {"User-Agent": "ESP32-Radio-Panel/1.0"}

    r = requests.get(url, params=params, headers=headers, timeout=20)
    r.raise_for_status()

    results = []

    for item in r.json():
        name = item.get("name") or ""
        tags = item.get("tags") or ""
        url_resolved = item.get("url_resolved") or item.get("url") or ""

        ok, reason = is_valid_esp32_url(url_resolved)

        if not ok:
            continue

        category = detect_category(name, tags)

        results.append(
            {
                "Kategori": category,
                "Radyo": name.strip(),
                "URL": url_resolved.strip(),
            }
        )

    return results


def detect_category(name, tags):
    text = f"{name} {tags}".lower()

    if any(x in text for x in ["islam", "islami", "dini", "kuran", "quran", "ilah", "akra", "ribat", "erkam", "radyo 7", "sufi"]):
        return "Dini"

    if any(x in text for x in ["turku", "türkü", "folk", "halk"]):
        return "Turku"

    if any(x in text for x in ["karadeniz", "trabzon", "rize", "ordu", "samsun"]):
        return "Karadeniz"

    if any(x in text for x in ["classic", "classical", "klasik"]):
        return "Klasik"

    if any(x in text for x in ["arabesk", "fantazi"]):
        return "Arabesk"

    if any(x in text for x in ["news", "haber"]):
        return "Haber"

    if any(x in text for x in ["pop", "hit", "hits", "top"]):
        return "Pop"

    return "Genel"


st.title("📻 ESP32 Radyo Yönetim Paneli")
st.caption("Kategori seç, radyo ekle, GitHub’daki radyolar.txt dosyasını güncelle. ESP32 açılışta bu dosyayı çeker.")

with st.sidebar:
    st.header("Bağlantı")
    st.write("Repo:", f"`{OWNER}/{REPO}`")
    st.write("Dosya:", f"`{FILE_PATH}`")
    st.link_button("Raw radyolar.txt aç", RAW_URL)

    st.divider()

    if st.button("GitHub’dan listeyi yenile"):
        st.session_state.pop("radios", None)
        st.session_state.pop("sha", None)
        st.rerun()


if "radios" not in st.session_state:
    text, sha = load_from_github()
    st.session_state.sha = sha
    st.session_state.radios = parse_radios(text)

radios = st.session_state.radios

col1, col2, col3, col4 = st.columns(4)
col1.metric("Toplam Radyo", len(radios))
col2.metric("Kategori", len(set(r["Kategori"] for r in radios)) if radios else 0)
col3.metric("ESP32 Formatı", "Kategori|Ad|URL")
col4.metric("Repo", REPO)

st.divider()

tab1, tab2, tab3 = st.tabs(["📋 Liste", "➕ Radyo Ekle", "🔎 Otomatik Bul"])

with tab1:
    st.subheader("Mevcut Liste")

    category_filter = st.selectbox("Kategori filtresi", ["Tümü"] + sorted(set(r["Kategori"] for r in radios)))

    shown = radios
    if category_filter != "Tümü":
        shown = [r for r in radios if r["Kategori"] == category_filter]

    for i, r in enumerate(shown):
        real_index = radios.index(r)

        with st.expander(f"{r['Kategori']} | {r['Radyo']}"):
            new_cat = st.selectbox(
                "Kategori",
                CATEGORIES,
                index=CATEGORIES.index(r["Kategori"]) if r["Kategori"] in CATEGORIES else CATEGORIES.index("Genel"),
                key=f"cat_{real_index}",
            )
            new_name = st.text_input("Radyo adı", r["Radyo"], key=f"name_{real_index}")
            new_url = st.text_input("URL", r["URL"], key=f"url_{real_index}")

            c1, c2 = st.columns(2)

            if c1.button("Güncelle", key=f"upd_{real_index}"):
                ok, reason = is_valid_esp32_url(new_url)

                if not ok:
                    st.error(reason)
                else:
                    radios[real_index] = {
                        "Kategori": new_cat,
                        "Radyo": new_name.strip(),
                        "URL": new_url.strip(),
                    }
                    st.success("Güncellendi")

            if c2.button("Sil", key=f"del_{real_index}"):
                radios.pop(real_index)
                st.success("Silindi")
                st.rerun()

with tab2:
    st.subheader("Yeni Radyo Ekle")

    new_cat = st.selectbox("Kategori", CATEGORIES)
    new_name = st.text_input("Radyo adı")
    new_url = st.text_input("Yayın URL", placeholder="http://...")

    if st.button("Listeye Ekle"):
        ok, reason = is_valid_esp32_url(new_url)

        if not ok:
            st.error(reason)
        elif not new_name.strip():
            st.error("Radyo adı boş olamaz.")
        else:
            radios.append(
                {
                    "Kategori": new_cat,
                    "Radyo": new_name.strip(),
                    "URL": new_url.strip(),
                }
            )
            st.success("Listeye eklendi")

with tab3:
    st.subheader("Radio Browser’dan Otomatik Bul")

    country = st.selectbox("Ülke", ["TR", "DE", "GB", "US", "FR", "NL", "BE", "AZ"])
    limit = st.slider("Kaç sonuç taransın?", 20, 300, 100)

    if st.button("Uygun Radyoları Bul"):
        try:
            found = load_radio_browser(country, limit)
            st.session_state.found_radios = found
            st.success(f"{len(found)} uygun radyo bulundu")
        except Exception as e:
            st.error(str(e))

    found = st.session_state.get("found_radios", [])

    if found:
        st.write("Bulunanlar")
        for idx, r in enumerate(found):
            with st.expander(f"{r['Kategori']} | {r['Radyo']}"):
                st.code(f"{r['Kategori']}|{r['Radyo']}|{r['URL']}")

                if st.button("Bu radyoyu ekle", key=f"add_found_{idx}"):
                    if not any(x["URL"] == r["URL"] for x in radios):
                        radios.append(r)
                        st.success("Eklendi")
                    else:
                        st.warning("Bu URL zaten listede var")

st.divider()

left, right = st.columns([1, 1])

with left:
    st.subheader("ESP32 Dosya Çıktısı")
    output_text = make_text(radios)
    st.code(output_text, language="text")

with right:
    st.subheader("Kaydet")

    if st.button("GitHub’a Kaydet", type="primary"):
        output_text = make_text(radios)
        ok = save_to_github(output_text, st.session_state.sha)

        if ok:
            st.success("GitHub’daki radyolar.txt güncellendi.")
            text, sha = load_from_github()
            st.session_state.sha = sha
            st.session_state.radios = parse_radios(text)
