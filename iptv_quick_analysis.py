# ───────────────────────────────────────────────
# SECTION 0.0.0 — Overview and Header
# ───────────────────────────────────────────────

"""
IPTV Quick Analysis Toolkit — Version 1.0
Author: Andrew's AI Assistant
Date: September 2025

📌 Purpose:
This production-grade Python script performs automated analysis of IPTV playlists and EPG (Electronic Program Guide) data. It includes:

1. URL validation with retry logic and mirror suggestions
2. Metadata extraction from M3U playlists and EPG XML files
3. Smart matching of channels to EPG entries using fuzzy logic
4. HTML report generation with hyperlinks
5. A CLI menu interface for interactive execution

🛠 Requirements:
- Python 3.8+
- Internet access for URL validation and metadata retrieval
- JSON-formatted input file: `playlist_epg_urls.json`

📁 Output Files:
- `channels_metadata.json` — extracted channel data
- `epg_metadata.json` — extracted EPG data
- `dead_links.json` — failed URLs with error types
- `iptv_report.html` — final report with linked metadata
- `iptv_analysis.log` — detailed execution logs

⚠️ Note:
This script is designed for production use. All functions include robust error handling, detailed logging, and modular design for easy maintenance and extension.
"""

# ───────────────────────────────────────────────
# SECTION 1.0.0 — Imports and Setup
# ───────────────────────────────────────────────

# ✅ 1.1.0 — Python standard and third-party imports
import os
import json
import requests
import xml.etree.ElementTree as ET
import re
import logging
import time
import html  # ✅ Required for HTML escaping in format_html_table()
from datetime import datetime
from difflib import get_close_matches

# ───────────────────────────────────────────────
# SECTION 2.0.0 — Setup and Configuration
# ───────────────────────────────────────────────

# ✅ 2.1.0 — Base directory (use raw string to avoid Windows path errors)
BASE_DIR = r"C:\Users\Lenovo\PROJECTS\IPTV\IPTV_quick_analysis"

# ✅ 2.1.1 — File paths
URL_JSON = os.path.join(BASE_DIR, "playlist_epg_urls.json")
CHANNELS_JSON = os.path.join(BASE_DIR, "channels_metadata.json")
EPG_JSON = os.path.join(BASE_DIR, "epg_metadata.json")
DEAD_LINKS_JSON = os.path.join(BASE_DIR, "dead_links.json")
HTML_OUTPUT = os.path.join(BASE_DIR, "iptv_report.html")

# ✅ 2.1.2 — Known mirror replacements
MIRROR_MAP = {
    "iptv-org.github.io": "raw.githubusercontent.com/iptv-org",
    "epg.pw": "epgshare01.online"
}

# ✅ 2.1.3 — Logging setup
logging.basicConfig(
    filename=os.path.join(BASE_DIR, "iptv_analysis.log"),
    level=logging.DEBUG,
    format="%(asctime)s — %(levelname)s — %(message)s"
)
logging.info("🚀 IPTV Quick Analysis script started.")

# ───────────────────────────────────────────────
# SECTION 3.0.0 — Helper Functions
# ───────────────────────────────────────────────

# ✅ 3.1.0 — categorize_error()
def categorize_error(e):
    """
    Categorize common request exceptions for structured logging.
    Returns a string label for the error type.
    """
    msg = str(e).lower()
    if "timeout" in msg:
        return "Timeout"
    elif "dns" in msg or "name resolution" in msg:
        return "DNSFailure"
    elif "connection" in msg:
        return "ConnectionError"
    else:
        return "UnknownError"

# ✅ 3.1.1 — suggest_mirror()
def suggest_mirror(url, data):
    """
    Suggest alternative mirror URLs for known sources if original fails.
    Updates the JSON data with mirror suggestions.
    """
    for key, mirror in MIRROR_MAP.items():
        if key in url:
            suggested = url.replace(key, mirror)
            logging.warning(f"[MIRROR] Original failed: {url} → Suggested: {suggested}")
            data.setdefault("mirror_suggestions", {})[url] = suggested

# ───────────────────────────────────────────────
# SECTION 4.0.0 — URL Validation
# ───────────────────────────────────────────────

# ✅ 4.1.0 — validate_urls()
def validate_urls():
    """
    Validate all playlist and EPG URLs listed in playlist_epg_urls.json.

    🔍 Features:
    - HEAD requests with 3 retries and exponential backoff
    - Categorizes errors (Timeout, DNSFailure, etc.)
    - Logs response time, status codes, and errors
    - Suggests mirror URLs for known domains
    - Updates status history and last_status in JSON
    - Writes dead links to dead_links.json

    📁 Input: playlist_epg_urls.json
    📁 Output: updated playlist_epg_urls.json, dead_links.json
    📝 Logs: iptv_analysis.log
    """
    try:
        with open(URL_JSON) as f:
            data = json.load(f)
    except Exception as e:
        logging.critical(f"[LOAD ERROR] Failed to read {URL_JSON}: {e}")
        print(f"❌ Failed to load URL list: {e}")
        return

    timestamp = datetime.now().isoformat()
    summary = {"checked": 0, "alive": 0, "dead": 0, "errors": {}}

    for category in ["playlist_urls", "epg_urls"]:
        urls = data.get(category, [])
        logging.info(f"[VALIDATION] Starting validation for {category} — {len(urls)} URLs")
        for url in urls:
            summary["checked"] += 1
            success = False
            for attempt in range(3):
                try:
                    start = time.time()
                    response = requests.head(url, timeout=10)
                    elapsed = int((time.time() - start) * 1000)
                    status = {
                        "timestamp": timestamp,
                        "status_code": response.status_code,
                        "ok": response.ok,
                        "response_time_ms": elapsed
                    }
                    data.setdefault("status_history", {}).setdefault(url, []).append(status)
                    data.setdefault("last_status", {})[url] = {
                        "alive": response.ok,
                        "last_checked": timestamp,
                        "response_time_ms": elapsed
                    }
                    logging.info(f"[URL] {url} — Status: {response.status_code}, Time: {elapsed}ms")
                    if response.ok:
                        summary["alive"] += 1
                        success = True
                        break
                except Exception as e:
                    error_type = categorize_error(e)
                    summary["dead"] += 1
                    summary["errors"][error_type] = summary["errors"].get(error_type, 0) + 1
                    error_log = {
                        "timestamp": timestamp,
                        "error_type": error_type,
                        "error_message": str(e)
                    }
                    data.setdefault("status_history", {}).setdefault(url, []).append(error_log)
                    data.setdefault("last_status", {})[url] = {
                        "alive": False,
                        "last_checked": timestamp,
                        "error_type": error_type,
                        "error_message": str(e)
                    }
                    logging.warning(f"[ERROR] {url} — {error_type}: {e}")
                    time.sleep(2 ** attempt)
            if not success:
                suggest_mirror(url, data)

    try:
        with open(URL_JSON, "w") as f:
            json.dump(data, f, indent=2)
        logging.info(f"[SAVE] Updated URL status written to {URL_JSON}")
    except Exception as e:
        logging.error(f"[SAVE ERROR] Failed to write {URL_JSON}: {e}")

    try:
        dead_links = {
            url: data["last_status"][url]
            for url in data.get("last_status", {})
            if not data["last_status"][url].get("alive", False)
        }
        with open(DEAD_LINKS_JSON, "w") as f:
            json.dump(dead_links, f, indent=2)
        logging.info(f"[SAVE] Dead links written to {DEAD_LINKS_JSON}")
    except Exception as e:
        logging.error(f"[SAVE ERROR] Failed to write {DEAD_LINKS_JSON}: {e}")

    logging.info(f"[SUMMARY] Checked: {summary['checked']}, Alive: {summary['alive']}, Dead: {summary['dead']}, Errors: {summary['errors']}")
    print(f"✅ Validation complete. {summary['alive']} alive, {summary['dead']} dead. See log and dead_links.json.")

# ───────────────────────────────────────────────
# SECTION 5.0.0 — Core Functions
# ───────────────────────────────────────────────

# ───────────────────────────────────────────────
# SECTION 5.1.0 — CM3U Metadata Extraction
# ───────────────────────────────────────────────

# ✅ 5.1.1 — extract_m3u_metadata()
def extract_m3u_metadata():
    """
    Extract metadata from all M3U playlist URLs.
    Parses #EXTINF lines and captures stream URLs.
    Writes structured channel metadata to channels_metadata.json.
    """
    try:
        with open(URL_JSON) as f:
            data = json.load(f)
    except Exception as e:
        logging.critical(f"[LOAD ERROR] Failed to read {URL_JSON}: {e}")
        print(f"❌ Failed to load playlist URLs: {e}")
        return

    channels = []
    for url in data.get("playlist_urls", []):
        logging.info(f"[M3U] Fetching playlist: {url}")
        try:
            response = requests.get(url, timeout=15)
            lines = response.text.splitlines()
            for i in range(len(lines)):
                if lines[i].startswith("#EXTINF"):
                    info = lines[i]
                    stream = lines[i+1] if i+1 < len(lines) else ""

                    # More flexible parsing
                    tvg_id = re.search(r'tvg-id="(.*?)"', info)
                    tvg_name = re.search(r'tvg-name="(.*?)"', info)
                    tvg_logo = re.search(r'tvg-logo="(.*?)"', info)
                    group_title = re.search(r'group-title="(.*?)"', info)

                    channel = {
                        "TVG-ID": tvg_id.group(1) if tvg_id else "",
                        "TVG-NAME": tvg_name.group(1) if tvg_name else "",
                        "TVG-LOGO": tvg_logo.group(1) if tvg_logo else "",
                        "TVG-GROUP": group_title.group(1) if group_title else "",
                        "TVG-URL": stream,
                        "TVG-LANGUAGE": "Unknown",
                        "source_url": url
                    }

                    if channel["TVG-NAME"] or channel["TVG-ID"]:
                        channels.append(channel)
                        logging.debug(f"[M3U] Parsed channel: {channel['TVG-NAME']} from {url}")
            logging.info(f"[M3U] Parsed {len(channels)} channels from {url}")
        except Exception as e:
            logging.error(f"[M3U ERROR] Failed to parse {url}: {e}")

    try:
        with open(CHANNELS_JSON, "w") as f:
            json.dump(channels, f, indent=2)
        logging.info(f"[SAVE] Channel metadata written to {CHANNELS_JSON}")
    except Exception as e:
        logging.error(f"[SAVE ERROR] Failed to write {CHANNELS_JSON}: {e}")

    print(f"📺 Extracted {len(channels)} channels to channels_metadata.json")
    
# ───────────────────────────────────────────────
# SECTION 5.2.0 — EPG Metadata Extraction
# ───────────────────────────────────────────────

# ✅ 5.2.1 — extract_epg_metadata() [UPDATED: grouped by source, filters nulls]
def extract_epg_metadata():
    """
    Extract metadata from all EPG XML URLs.

    🔍 Features:
    - Parses <channel> tags for id and display-name
    - Skips entries with no usable metadata
    - Groups entries by source URL
    - Logs parsing success and skipped entries
    - Writes structured EPG metadata to epg_metadata.json

    📁 Input: playlist_epg_urls.json
    📁 Output: epg_metadata.json (grouped by source)
    📝 Logs: iptv_analysis.log
    """
    try:
        with open(URL_JSON) as f:
            data = json.load(f)
    except Exception as e:
        logging.critical(f"[LOAD ERROR] Failed to read {URL_JSON}: {e}")
        print(f"❌ Failed to load EPG URLs: {e}")
        return

    epg_data = {}

    for url in data.get("epg_urls", []):
        logging.info(f"[EPG] Fetching XML guide: {url}")
        try:
            response = requests.get(url, timeout=15)
            root = ET.fromstring(response.content)
            entries = []

            for channel in root.findall("channel"):
                tvg_id = channel.get("id")
                tvg_epgid = channel.findtext("display-name")

                # Skip entries with no usable metadata
                if not tvg_id and not tvg_epgid:
                    logging.warning(f"[EPG SKIP] Empty channel entry in {url}")
                    continue

                entry = {
                    "TVG-ID": tvg_id,
                    "TVG-EPGID": tvg_epgid,
                    "TVG-EPGURL": url,
                    "type": "EPG",
                    "language": "unknown"
                }
                entries.append(entry)
                logging.debug(f"[EPG] Parsed EPG entry: {tvg_epgid}")

            epg_data[url] = entries
            logging.info(f"[EPG] Parsed {len(entries)} entries from {url}")

        except Exception as e:
            logging.error(f"[EPG ERROR] Failed to parse {url}: {e}")

    try:
        with open(EPG_JSON, "w") as f:
            json.dump(epg_data, f, indent=2)
        logging.info(f"[SAVE] Grouped EPG metadata written to {EPG_JSON}")
    except Exception as e:
        logging.error(f"[SAVE ERROR] Failed to write {EPG_JSON}: {e}")

    print(f"📅 Extracted EPG metadata from {len(epg_data)} sources to epg_metadata.json")

# ✅ 5.2.2 — audit_epg_metadata()
def audit_epg_metadata():
    """
    Audit the grouped EPG metadata for anomalies.

    🔍 Features:
    - Scans epg_metadata.json for:
        • Duplicate TVG-IDs across sources
        • Null or empty entries
        • Source URLs with no valid entries
    - Logs summary statistics
    - Prints audit results to console

    📁 Input: epg_metadata.json (grouped by source)
    📝 Logs: iptv_analysis.log
    """
    try:
        with open(EPG_JSON) as f:
            epg_data = json.load(f)
    except Exception as e:
        logging.error(f"[AUDIT ERROR] Failed to load EPG metadata: {e}")
        print(f"❌ Audit failed: {e}")
        return

    seen_ids = set()
    duplicates = []
    null_entries = []
    empty_sources = []

    for source, entries in epg_data.items():
        if not entries:
            empty_sources.append(source)
            continue

        for entry in entries:
            tvg_id = entry.get("TVG-ID")
            tvg_epgid = entry.get("TVG-EPGID")

            if not tvg_id and not tvg_epgid:
                null_entries.append((source, entry))
            elif tvg_id in seen_ids:
                duplicates.append((source, tvg_id))
            else:
                seen_ids.add(tvg_id)

    print(f"\n🔍 EPG Metadata Audit Results")
    print(f"-----------------------------")
    print(f"• Total sources scanned: {len(epg_data)}")
    print(f"• Sources with no valid entries: {len(empty_sources)}")
    print(f"• Null entries (missing ID and name): {len(null_entries)}")
    print(f"• Duplicate TVG-IDs across sources: {len(duplicates)}")

    logging.info(f"[AUDIT] Sources: {len(epg_data)}, Empty: {len(empty_sources)}, Nulls: {len(null_entries)}, Duplicates: {len(duplicates)}")

# ───────────────────────────────────────────────
# SECTION 5.3.0 — Smart Matching (Fuzzy Logic)
# ───────────────────────────────────────────────

# ✅  5.3.1 — smart_match() [Updated for grouped EPG]

def smart_match():
    """
    Match channels to EPG entries using fuzzy logic.

    🔍 Features:
    - Loads channels and grouped EPG metadata
    - Flattens EPG entries
    - Uses fuzzy_match_channel_name()
    - Updates channels_metadata.json with matched_epg_id
    """
    try:
        with open(CHANNELS_JSON) as f:
            channels = json.load(f)
        with open(EPG_JSON) as f:
            epg_grouped = json.load(f)
    except Exception as e:
        logging.error(f"[MATCH ERROR] Failed to load input files: {e}")
        print(f"❌ Failed to load metadata: {e}")
        return

    # Flatten EPG entries
    epg_entries = []
    for entries in epg_grouped.values():
        epg_entries.extend(entries)

    matched = 0
    for ch in channels:
        name = ch.get("TVG-NAME")
        if not name:
            continue
        match = fuzzy_match_channel_name(name, epg_entries)
        if match:
            ch["matched_epg_id"] = match
            matched += 1

    try:
        with open(CHANNELS_JSON, "w") as f:
            json.dump(channels, f, indent=2)
        logging.info(f"[MATCH] Matched {matched} channels to EPG")
        print(f"🧠 Smart match complete. {matched} channels matched. Updated channels_metadata.json.")
    except Exception as e:
        logging.error(f"[SAVE ERROR] Failed to write matched channels: {e}")
        print(f"❌ Failed to save matched channels: {e}")


# ───────────────────────────────────────────────
# SECTION 5.3.2 — Matching Logic Using difflib
# ───────────────────────────────────────────────

# ✅ 5.3.2 — fuzzy_match_channel_name()
def fuzzy_match_channel_name(channel_name, epg_entries, threshold=0.85):
    """
    Match a channel name to the closest EPG entry using difflib.

    🔍 Features:
    - Uses difflib.get_close_matches for fuzzy matching
    - Returns best match above threshold
    - Logs match quality

    📥 Input: channel_name (str), epg_entries (list of dicts)
    📤 Output: matched EPG-ID or None
    """
    epg_names = [entry.get("TVG-EPGID", "") for entry in epg_entries if entry.get("TVG-EPGID")]
    matches = difflib.get_close_matches(channel_name, epg_names, n=1, cutoff=threshold)

    if matches:
        logging.debug(f"[MATCH] '{channel_name}' matched to '{matches[0]}'")
        return matches[0]
    else:
        logging.debug(f"[MATCH] No match found for '{channel_name}'")
        return None

# ───────────────────────────────────────────────
# SECTION 5.3.3 — Match M3U Channels to EPG Entries
# ───────────────────────────────────────────────

# ✅ 5.3.3 — match_channels_to_epg()
def match_channels_to_epg():
    """
    Match M3U channel metadata to EPG entries using fuzzy logic.

    🔍 Features:
    - Loads channels_metadata.json and epg_metadata.json
    - Flattens grouped EPG entries
    - Uses fuzzy_match_channel_name() to find best match
    - Adds 'matched_epg_id' to each channel
    - Logs match count and saves updated metadata
    """
    try:
        with open(CHANNELS_JSON) as f:
            channels = json.load(f)
        with open(EPG_JSON) as f:
            epg_grouped = json.load(f)
    except Exception as e:
        logging.error(f"[MATCH ERROR] Failed to load input files: {e}")
        print(f"❌ Failed to load metadata: {e}")
        return

    # Flatten EPG entries
    epg_entries = []
    for entries in epg_grouped.values():
        epg_entries.extend(entries)

    matched = 0
    for ch in channels:
        name = ch.get("TVG-NAME")
        if not name:
            continue
        match = fuzzy_match_channel_name(name, epg_entries)
        if match:
            ch["matched_epg_id"] = match
            matched += 1

    try:
        with open(CHANNELS_JSON, "w") as f:
            json.dump(channels, f, indent=2)
        logging.info(f"[MATCH] Matched {matched} channels to EPG")
        print(f"🔗 Channel-to-EPG match complete. {matched} channels matched.")
    except Exception as e:
        logging.error(f"[SAVE ERROR] Failed to write matched channels: {e}")
        print(f"❌ Failed to save matched channels: {e}")

# ───────────────────────────────────────────────
# SECTION 5.4.0 — HTML Report Generation
# ───────────────────────────────────────────────

# ───────────────────────────────────────────────
# SECTION 5.4.1 — generate_html_report() [FINAL VERSION WITH ALL OPTIONS]
# ───────────────────────────────────────────────

def generate_html_report():
    """
    Generate a full-featured HTML report from channel metadata.

    🔍 Features:
    - Full metadata table with logos and EPG match
    - Wrapped URLs with tooltips
    - Filtering by group, language, and match status
    - Sorting by column headers
    - Export buttons (CSV, PDF via browser)
    - Group and language distribution charts
    - Export filtered results directly from the page
    """
    try:
        with open(CHANNELS_JSON) as f:
            channels = json.load(f)
    except Exception as e:
        logging.error(f"[HTML ERROR] Failed to load channels: {e}")
        print(f"❌ Failed to load channel metadata: {e}")
        return

    def esc(text):
        return html.escape(str(text)) if text else ""

    rows = []
    group_counts = {}
    language_counts = {}

    for ch in channels[:100]:  # Limit for readability
        group = ch.get("TVG-GROUP", "Unknown")
        lang = ch.get("TVG-LANGUAGE", "Unknown")
        matched = "yes" if ch.get("matched_epg_id") else "no"

        group_counts[group] = group_counts.get(group, 0) + 1
        language_counts[lang] = language_counts.get(lang, 0) + 1

        rows.append(f"""
        <tr data-group="{esc(group)}" data-lang="{esc(lang)}" data-matched="{matched}">
            <td>{esc(ch.get("TVG-ID"))}</td>
            <td>{esc(ch.get("TVG-NAME"))}</td>
            <td><img src="{esc(ch.get("TVG-LOGO"))}" alt="logo" width="50"></td>
            <td>{esc(group)}</td>
            <td class="url"><div style="word-wrap: break-word; white-space: normal; max-width: 300px;" title="{esc(ch.get("TVG-URL", ""))}">{esc(ch.get("TVG-URL", ""))}</div></td>
            <td>{esc(ch.get("matched_epg_id"))}</td>
            <td>{esc(lang)}</td>
            <td>{esc(ch.get("source_url"))}</td>
        </tr>
        """)

    chart_labels = list(group_counts.keys())
    chart_data = list(group_counts.values())

    lang_labels = list(language_counts.keys())
    lang_data = list(language_counts.values())

    html_content = f"""
    <html>
    <head>
      <title>IPTV Channel Metadata</title>
      <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
      <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        table {{ width: 100%; border-collapse: collapse; font-size: 12px; }}
        th, td {{ border: 1px solid #ccc; padding: 6px; text-align: left; vertical-align: top; }}
        th {{ background-color: #f2f2f2; cursor: pointer; }}
        .url div {{ word-wrap: break-word; white-space: normal; max-width: 300px; }}
        .filter {{ margin-bottom: 10px; }}
        .export-buttons {{ margin-top: 10px; }}
        canvas {{ max-width: 600px; margin-top: 20px; }}
      </style>
      <script>
        function filterTable() {{
          const group = document.getElementById("groupFilter").value.toLowerCase();
          const lang = document.getElementById("langFilter").value.toLowerCase();
          const match = document.getElementById("matchFilter").value;
          const rows = document.querySelectorAll("tbody tr");
          rows.forEach(row => {{
            const g = row.getAttribute("data-group").toLowerCase();
            const l = row.getAttribute("data-lang").toLowerCase();
            const m = row.getAttribute("data-matched");
            const groupMatch = g.includes(group);
            const langMatch = l.includes(lang);
            const matchStatus = (match === "all") || (match === m);
            row.style.display = (groupMatch && langMatch && matchStatus) ? "" : "none";
          }});
        }}
        function sortTable(n) {{
          const table = document.querySelector("table");
          let rows = Array.from(table.rows).slice(1);
          let asc = table.getAttribute("data-sort") !== "asc";
          rows.sort((a, b) => {{
            let x = a.cells[n].innerText.toLowerCase();
            let y = b.cells[n].innerText.toLowerCase();
            return asc ? x.localeCompare(y) : y.localeCompare(x);
          }});
          rows.forEach(row => table.tBodies[0].appendChild(row));
          table.setAttribute("data-sort", asc ? "asc" : "desc");
        }}
        function exportTableToCSV(filename) {{
          const rows = document.querySelectorAll("table tr");
          let csv = Array.from(rows).map(row => {{
            const cells = row.querySelectorAll("th, td");
            return Array.from(cells).map(c => `"${c.innerText}"`).join(",");
          }}).join("\\n");
          let blob = new Blob([csv], {{ type: 'text/csv' }});
          let link = document.createElement("a");
          link.href = URL.createObjectURL(blob);
          link.download = filename;
          link.click();
        }}
      </script>
    </head>
    <body>
      <h1>IPTV Channel Metadata</h1>

      <div class="filter">
        Filter by Group: <input type="text" id="groupFilter" onkeyup="filterTable()">
        Filter by Language: <input type="text" id="langFilter" onkeyup="filterTable()">
        Match Status:
        <select id="matchFilter" onchange="filterTable()">
          <option value="all">All</option>
          <option value="yes">Matched</option>
          <option value="no">Unmatched</option>
        </select>
      </div>

      <div class="export-buttons">
        <button onclick="exportTableToCSV('iptv_channels_filtered.csv')">📄 Export Filtered to CSV</button>
        <p>To export to PDF, use your browser's Print → Save as PDF.</p>
      </div>

      <table data-sort="asc">
        <thead>
          <tr>
            <th onclick="sortTable(0)">TVG-ID</th>
            <th onclick="sortTable(1)">Name</th>
            <th>Logo</th>
            <th onclick="sortTable(3)">Group</th>
            <th class="url">Stream URL</th>
            <th>EPG Match</th>
            <th>Language</th>
            <th>Source URL</th>
          </tr>
        </thead>
        <tbody>
          {''.join(rows)}
        </tbody>
      </table>

      <h2>📊 Group Distribution</h2>
      <canvas id="groupChart"></canvas>
      <script>
        new Chart(document.getElementById('groupChart'), {{
          type: 'bar',
          data: {{
            labels: {chart_labels},
            datasets: [{{
              label: 'Channels per Group',
              data: {chart_data},
              backgroundColor: 'rgba(54, 162, 235, 0.6)'
            }}]
          }},
          options: {{
            responsive: true,
            scales: {{
              y: {{ beginAtZero: true }}
            }}
          }}
        }});
      </script>

      <h2>🌍 Language Distribution</h2>
      <canvas id="langChart"></canvas>
      <script>
        new Chart(document.getElementById('langChart'), {{
          type: 'pie',
          data: {{
            labels: {lang_labels},
            datasets: [{{
              label: 'Channels per Language',
              data: {lang_data},
              backgroundColor: [
                'rgba(255, 99, 132, 0.6)',
                'rgba(54, 162, 235, 0.6)',
                'rgba(255, 206, 86, 0.6)',
                'rgba(75, 192, 192, 0.6)',
                'rgba(153, 102, 255, 0.6)',
                'rgba(255, 159, 64, 0.6)'
              ]
            }}]
          }},
          options: {{
            responsive: true
          }}
        }});
      </script>
    </body>
    </html>
    """

    try:
        with open(os.path.join(BASE_DIR, "iptv_report.html"), "w", encoding="utf-8") as f:
            f.write(html_content)
        logging.info("[HTML] Enhanced report generated")

# ───────────────────────────────────────────────
# SECTION 5.4.2 — format_html_table() [UPDATED VERSION]
# ───────────────────────────────────────────────

def format_html_table(channels):
    """
    Generate HTML table rows from channel metadata.

    🔍 Features:
    - Builds table with headers and rows
    - Includes matched EPG ID and logo
    - Escapes HTML-sensitive characters
    - Wraps long URLs
    - Adds data attributes for filtering (group, language, match)
    
    📥 Input: channels (list of dicts)
    📤 Output: HTML string
    """
    def esc(text):
        return html.escape(str(text)) if text else ""

    rows = []
    for ch in channels:
        group = ch.get("TVG-GROUP", "Unknown")
        lang = ch.get("TVG-LANGUAGE", "Unknown")
        matched = "yes" if ch.get("matched_epg_id") else "no"

        rows.append(f"""
        <tr data-group="{esc(group)}" data-lang="{esc(lang)}" data-matched="{matched}">
            <td>{esc(ch.get("TVG-ID"))}</td>
            <td>{esc(ch.get("TVG-NAME"))}</td>
            <td><img src="{esc(ch.get("TVG-LOGO"))}" alt="logo" width="50"></td>
            <td>{esc(group)}</td>
            <td class="url"><div style="word-wrap: break-word; white-space: normal; max-width: 300px;" title="{esc(ch.get("TVG-URL", ""))}">{esc(ch.get("TVG-URL", ""))}</div></td>
            <td>{esc(ch.get("matched_epg_id"))}</td>
            <td>{esc(lang)}</td>
            <td>{esc(ch.get("source_url"))}</td>
        </tr>
        """)

    return f"""
    <table border="1" cellpadding="5" cellspacing="0" data-sort="asc">
        <thead>
            <tr>
                <th>TVG-ID</th>
                <th>Name</th>
                <th>Logo</th>
                <th>Group</th>
                <th>Stream URL</th>
                <th>Matched EPG</th>
                <th>Language</th>
                <th>Source URL</th>
            </tr>
        </thead>
        <tbody>
            {''.join(rows)}
        </tbody>
    </table>
    """

# ───────────────────────────────────────────────
# SECTION 5.5.0 — CSV Export
# ───────────────────────────────────────────────

# ✅ 5.5.1 — export_channels_to_csv()
import csv  # Ensure this is included in SECTION 1.0.0 if not already

CSV_OUTPUT = os.path.join(BASE_DIR, "channels_metadata.csv")  # Add to SECTION 2.1.1

def export_channels_to_csv():
    """
    Export enriched channel metadata to a CSV file.

    🔍 Features:
    - Reads channels_metadata.json
    - Includes matched EPG ID if available
    - Writes structured rows to channels_metadata.csv
    - Logs export status and errors

    📁 Input: channels_metadata.json
    📁 Output: channels_metadata.csv
    📝 Logs: iptv_analysis.log
    """
    try:
        with open(CHANNELS_JSON) as f:
            channels = json.load(f)
    except Exception as e:
        logging.critical(f"[LOAD ERROR] Failed to read {CHANNELS_JSON}: {e}")
        print(f"❌ Failed to load channel metadata: {e}")
        return

    fieldnames = [
        "TVG-ID", "TVG-NAME", "TVG-LOGO", "TVG-GROUP",
        "TVG-URL", "TVG-LANGUAGE", "matched_epg_id", "source_url"
    ]

    try:
        with open(CSV_OUTPUT, "w", newline='', encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for channel in channels:
                writer.writerow({
                    "TVG-ID": channel.get("TVG-ID", ""),
                    "TVG-NAME": channel.get("TVG-NAME", ""),
                    "TVG-LOGO": channel.get("TVG-LOGO", ""),
                    "TVG-GROUP": channel.get("TVG-GROUP", ""),
                    "TVG-URL": channel.get("TVG-URL", ""),
                    "TVG-LANGUAGE": channel.get("TVG-LANGUAGE", ""),
                    "matched_epg_id": channel.get("matched_epg_id", ""),
                    "source_url": channel.get("source_url", "")
                })
        logging.info(f"[CSV EXPORT] Channel metadata exported to {CSV_OUTPUT}")
        print(f"📄 CSV export complete: {CSV_OUTPUT}")
    except Exception as e:
        logging.error(f"[CSV ERROR] Failed to write CSV file: {e}")
        print(f"❌ Failed to export CSV: {e}")

# ───────────────────────────────────────────────
# SECTION 5.6.0 — CSV Export for EPG Metadata
# ───────────────────────────────────────────────

# ✅ 5.6.1 — export_epg_to_csv()
def export_epg_to_csv():
    """
    Export grouped EPG metadata to a flat CSV file.
    """
    try:
        with open(EPG_JSON) as f:
            epg_data = json.load(f)
    except Exception as e:
        logging.error(f"[CSV ERROR] Failed to load EPG metadata: {e}")
        print(f"❌ Failed to load EPG metadata: {e}")
        return

    fieldnames = ["TVG-ID", "TVG-EPGID", "TVG-EPGURL", "type", "language"]
    try:
        with open(os.path.join(BASE_DIR, "epg_metadata.csv"), "w", newline='', encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for source, entries in epg_data.items():
                for entry in entries:
                    writer.writerow(entry)
        logging.info("[CSV EXPORT] EPG metadata exported to epg_metadata.csv")
        print("📄 EPG CSV export complete.")
    except Exception as e:
        logging.error(f"[CSV ERROR] Failed to write EPG CSV: {e}")
        print(f"❌ Failed to export EPG CSV: {e}")

# ───────────────────────────────────────────────
# SECTION 5.7.0 — JSON Cleanup or Deduplication Logic
# ───────────────────────────────────────────────

# ✅ 5.7.1 — deduplicate_channels()
def deduplicate_channels():
    """
    Remove duplicate entries from channels_metadata.json based on TVG-ID.
    """
    try:
        with open(CHANNELS_JSON) as f:
            channels = json.load(f)
    except Exception as e:
        logging.error(f"[DEDUP ERROR] Failed to load channels: {e}")
        print(f"❌ Failed to load channels: {e}")
        return

    seen = set()
    unique = []
    for ch in channels:
        tvg_id = ch.get("TVG-ID")
        if tvg_id and tvg_id not in seen:
            seen.add(tvg_id)
            unique.append(ch)

    try:
        with open(CHANNELS_JSON, "w") as f:
            json.dump(unique, f, indent=2)
        logging.info(f"[DEDUP] Removed duplicates. Final count: {len(unique)}")
        print(f"🧹 Deduplication complete. {len(unique)} unique channels saved.")
    except Exception as e:
        logging.error(f"[SAVE ERROR] Failed to write cleaned channels: {e}")
        print(f"❌ Failed to save cleaned channels: {e}")

# ───────────────────────────────────────────────
# SECTION 5.8.0 — Export HTML to PDF
# ───────────────────────────────────────────────

# ✅ 5.8.1 — export_html_to_pdf()
def export_html_to_pdf():
    """
    Convert iptv_report.html to a PDF file.

    📦 Requires: pdfkit and wkhtmltopdf installed
    """
    try:
        import pdfkit
    except ImportError:
        print("❌ pdfkit not installed. Run: pip install pdfkit")
        return

    html_path = os.path.join(BASE_DIR, "iptv_report.html")
    pdf_path = os.path.join(BASE_DIR, "iptv_report.pdf")

    try:
        pdfkit.from_file(html_path, pdf_path)
        logging.info(f"[PDF EXPORT] Report saved to {pdf_path}")
        print(f"📄 PDF export complete: {pdf_path}")
    except Exception as e:
        logging.error(f"[PDF ERROR] Failed to export PDF: {e}")
        print(f"❌ Failed to export PDF: {e}")

# ───────────────────────────────────────────────
# SECTION 5.9.0 — Filter Channels by Group or Language
# ───────────────────────────────────────────────

# ✅ 5.9.1 — filter_channels()
def filter_channels():
    """
    Filter channels by group or language and display results.
    """
    try:
        with open(CHANNELS_JSON) as f:
            channels = json.load(f)
    except Exception as e:
        logging.error(f"[FILTER ERROR] Failed to load channels: {e}")
        print(f"❌ Failed to load channels: {e}")
        return

    group = input("Enter group name to filter (or leave blank): ").strip().lower()
    lang = input("Enter language to filter (or leave blank): ").strip().lower()

    filtered = []
    for ch in channels:
        g = ch.get("TVG-GROUP", "").lower()
        l = ch.get("TVG-LANGUAGE", "").lower()
        if (not group or group in g) and (not lang or lang in l):
            filtered.append(ch)

    print(f"🔍 Found {len(filtered)} matching channels.")
    for ch in filtered[:20]:  # Show first 20
        print(f"• {ch.get('TVG-NAME')} ({ch.get('TVG-GROUP')}, {ch.get('TVG-LANGUAGE')})")

    logging.info(f"[FILTER] Returned {len(filtered)} channels for group='{group}' lang='{lang}'")

# ───────────────────────────────────────────────
# SECTION 5.10.0 — Search Channels by Name or ID
# ───────────────────────────────────────────────

# ✅ 5.10.1 — search_channels()
def search_channels():
    """
    Search channels by name or TVG-ID.
    """
    try:
        with open(CHANNELS_JSON) as f:
            channels = json.load(f)
    except Exception as e:
        logging.error(f"[SEARCH ERROR] Failed to load channels: {e}")
        print(f"❌ Failed to load channels: {e}")
        return

    query = input("Enter channel name or ID to search: ").strip().lower()
    results = [ch for ch in channels if query in str(ch.get("TVG-NAME", "")).lower() or query in str(ch.get("TVG-ID", "")).lower()]

    print(f"🔍 Found {len(results)} matching channels.")
    for ch in results[:20]:  # Show first 20
        print(f"• {ch.get('TVG-NAME')} ({ch.get('TVG-ID')})")

    logging.info(f"[SEARCH] Returned {len(results)} results for query='{query}'")

# ───────────────────────────────────────────────
# SECTION 5.11.0 — Export Filtered Results to CSV
# ───────────────────────────────────────────────

# ✅ 5.11.1 — export_filtered_channels_to_csv()
def export_filtered_channels_to_csv():
    """
    Filter channels by group or language and export results to CSV.
    """
    try:
        with open(CHANNELS_JSON) as f:
            channels = json.load(f)
    except Exception as e:
        logging.error(f"[FILTER CSV ERROR] Failed to load channels: {e}")
        print(f"❌ Failed to load channels: {e}")
        return

    group = input("Enter group name to filter (or leave blank): ").strip().lower()
    lang = input("Enter language to filter (or leave blank): ").strip().lower()

    filtered = []
    for ch in channels:
        g = ch.get("TVG-GROUP", "").lower()
        l = ch.get("TVG-LANGUAGE", "").lower()
        if (not group or group in g) and (not lang or lang in l):
            filtered.append(ch)

    if not filtered:
        print("⚠️ No matching channels found.")
        return

    fieldnames = [
        "TVG-ID", "TVG-NAME", "TVG-LOGO", "TVG-GROUP",
        "TVG-URL", "TVG-LANGUAGE", "matched_epg_id", "source_url"
    ]

    try:
        with open(os.path.join(BASE_DIR, "filtered_channels.csv"), "w", newline='', encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for ch in filtered:
                writer.writerow(ch)
        logging.info(f"[FILTER CSV] Exported {len(filtered)} channels to filtered_channels.csv")
        print(f"📄 Exported {len(filtered)} channels to filtered_channels.csv")
    except Exception as e:
        logging.error(f"[FILTER CSV ERROR] Failed to write CSV: {e}")
        print(f"❌ Failed to export filtered CSV: {e}")

# ───────────────────────────────────────────────
# SECTION 5.12.0 — Compare Two Channels Side-by-Side
# ───────────────────────────────────────────────

# ✅ 5.12.1 — compare_channels()
def compare_channels():
    """
    Compare two channels by TVG-ID or name.
    """
    try:
        with open(CHANNELS_JSON) as f:
            channels = json.load(f)
    except Exception as e:
        logging.error(f"[COMPARE ERROR] Failed to load channels: {e}")
        print(f"❌ Failed to load channels: {e}")
        return

    id1 = input("Enter first channel name or ID: ").strip().lower()
    id2 = input("Enter second channel name or ID: ").strip().lower()

    def find_channel(query):
        return next((ch for ch in channels if query in str(ch.get("TVG-ID", "")).lower() or query in str(ch.get("TVG-NAME", "")).lower()), None)

    ch1 = find_channel(id1)
    ch2 = find_channel(id2)

    if not ch1 or not ch2:
        print("⚠️ One or both channels not found.")
        return

    print("\n📊 Channel Comparison")
    print("---------------------")
    for key in ["TVG-ID", "TVG-NAME", "TVG-GROUP", "TVG-LANGUAGE", "matched_epg_id"]:
        print(f"{key:<15}: {ch1.get(key, ''):<30} | {ch2.get(key, ''):<30}")

# ───────────────────────────────────────────────
# SECTION 5.13.1 — generate_summary_dashboard() [REPLACEMENT]
# ───────────────────────────────────────────────

def generate_summary_dashboard():
    """
    Generate a clean HTML summary dashboard with group and language distribution.

    🔍 Features:
    - Sanitizes corrupted group names
    - Displays total channel count
    - Lists unique groups and languages
    - Adds group distribution chart
    """
    try:
        with open(CHANNELS_JSON) as f:
            channels = json.load(f)
    except Exception as e:
        logging.error(f"[SUMMARY ERROR] Failed to load channels: {e}")
        print(f"❌ Failed to load channels: {e}")
        return

    def clean(text):
        return str(text).encode("utf-8", errors="ignore").decode("utf-8").replace("�", "").strip()

    total = len(channels)
    groups = [clean(ch.get("TVG-GROUP", "Unknown")) for ch in channels]
    languages = [clean(ch.get("TVG-LANGUAGE", "Unknown")) for ch in channels]

    group_counts = {}
    for g in groups:
        group_counts[g] = group_counts.get(g, 0) + 1

    language_counts = {}
    for l in languages:
        language_counts[l] = language_counts.get(l, 0) + 1

    chart_labels = list(group_counts.keys())
    chart_data = list(group_counts.values())

    lang_labels = list(language_counts.keys())
    lang_data = list(language_counts.values())

    html_content = f"""
    <html>
    <head>
      <title>IPTV Summary Dashboard</title>
      <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
      <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        ul {{ columns: 3; -webkit-columns: 3; -moz-columns: 3; }}
        canvas {{ max-width: 600px; margin-top: 20px; }}
      </style>
    </head>
    <body>
      <h1>IPTV Summary Dashboard</h1>
      <p><strong>Total Channels:</strong> {total}</p>

      <h2>📦 Groups</h2>
      <ul>
        {''.join(f"<li>{g} ({group_counts[g]})</li>" for g in chart_labels)}
      </ul>

      <h2>🌍 Languages</h2>
      <ul>
        {''.join(f"<li>{l} ({language_counts[l]})</li>" for l in lang_labels)}
      </ul>

      <h2>📊 Group Distribution</h2>
      <canvas id="groupChart"></canvas>
      <script>
        new Chart(document.getElementById('groupChart'), {{
          type: 'bar',
          data: {{
            labels: {chart_labels},
            datasets: [{{
              label: 'Channels per Group',
              data: {chart_data},
              backgroundColor: 'rgba(75, 192, 192, 0.6)'
            }}]
          }},
          options: {{
            responsive: true,
            scales: {{
              y: {{ beginAtZero: true }}
            }}
          }}
        }});
      </script>

      <h2>🌐 Language Distribution</h2>
      <canvas id="langChart"></canvas>
      <script>
        new Chart(document.getElementById('langChart'), {{
          type: 'pie',
          data: {{
            labels: {lang_labels},
            datasets: [{{
              label: 'Channels per Language',
              data: {lang_data},
              backgroundColor: [
                'rgba(255, 99, 132, 0.6)',
                'rgba(54, 162, 235, 0.6)',
                'rgba(255, 206, 86, 0.6)',
                'rgba(75, 192, 192, 0.6)',
                'rgba(153, 102, 255, 0.6)',
                'rgba(255, 159, 64, 0.6)'
              ]
            }}]
          }},
          options: {{
            responsive: true
          }}
        }});
      </script>
    </body>
    </html>
    """

    try:
        with open(os.path.join(BASE_DIR, "iptv_summary.html"), "w", encoding="utf-8") as f:
            f.write(html_content)
        logging.info("[SUMMARY] Dashboard written to iptv_summary.html")
        print("📊 Summary dashboard generated: iptv_summary.html")
    except Exception as e:
        logging.error(f"[SUMMARY ERROR] Failed to write dashboard: {e}")
        print(f"❌ Failed to generate summary dashboard: {e}")

# ───────────────────────────────────────────────
# SECTION 6.0.0 — CLI Menu and Entry Point
# ───────────────────────────────────────────────

# ✅ 6.1.0 — menu()
def menu():
    """
    Display a looping command-line menu for running analysis tasks.

    🔍 Features:
    - Interactive CLI with numbered options
    - Calls corresponding functions for each task
    - Handles invalid input gracefully
    - Logs each user selection and execution status
    """
    while True:
        print("\nIPTV Quick Analysis Menu")
        print("-------------------------")
        print("1. Validate all URLs in JSON")
        print("2. Extract channel metadata from M3U")
        print("3. Extract EPG metadata from XML")
        print("4. Smart match channels to EPG")
        print("5. Generate HTML report")
        print("6. Export channel metadata to CSV")
        print("7. Audit EPG metadata for anomalies")
        print("8. Deduplicate channels")
        print("9. Export EPG metadata to CSV")
        print("10. Launch web dashboard")
        print("11. Export HTML report to PDF")
        print("12. Filter channels by group or language")
        print("13. Search channels by name or ID")
        print("14. Export filtered channels to CSV")
        print("15. Compare two channels side-by-side")
        print("16. Generate summary dashboard in HTML")
        print("17. Match M3U channels to EPG entries")
        print("99. Exit")

        choice = input("Select an option: ").strip()
        logging.info(f"[MENU] User selected option: {choice}")

        if choice == '1':
            logging.info("[EXECUTE] Running validate_urls()")
            validate_urls()
        elif choice == '2':
            logging.info("[EXECUTE] Running extract_m3u_metadata()")
            extract_m3u_metadata()
        elif choice == '3':
            logging.info("[EXECUTE] Running extract_epg_metadata()")
            extract_epg_metadata()
        elif choice == '4':
            logging.info("[EXECUTE] Running smart_match()")
            smart_match()
        elif choice == '5':
            logging.info("[EXECUTE] Running generate_html_report()")
            generate_html_report()
        elif choice == '6':
            logging.info("[EXECUTE] Running export_channels_to_csv()")
            export_channels_to_csv()   
        elif choice == '7':
            logging.info("[EXECUTE] Running audit_epg_metadata()")
            audit_epg_metadata()
        elif choice == '8':
            logging.info("[EXECUTE] Running deduplicate_channels()")
            deduplicate_channels()
        elif choice == '9':
            logging.info("[EXECUTE] Running export_epg_to_csv()")
            export_epg_to_csv()
        elif choice == '10':
            logging.info("[EXECUTE] Running launch_dashboard()")
            launch_dashboard()
        elif choice == '11':
            logging.info("[EXECUTE] Running export_html_to_pdf()")
            export_html_to_pdf()
        elif choice == '12':
            logging.info("[EXECUTE] Running filter_channels()")
            filter_channels()
        elif choice == '13':
            logging.info("[EXECUTE] Running search_channels()")
            search_channels()
        elif choice == '14':
            logging.info("[EXECUTE] Running export_filtered_channels_to_csv()")
            export_filtered_channels_to_csv()
        elif choice == '15':
            logging.info("[EXECUTE] Running compare_channels()")
            compare_channels()
        elif choice == '16':
            logging.info("[EXECUTE] Running generate_summary_dashboard()")
            generate_summary_dashboard()
        elif choice == '17':
            logging.info("[EXECUTE] Running match_channels_to_epg()")
            match_channels_to_epg()
        elif choice == '99':
            logging.info("[EXIT] User exited the program.")
            print("👋 Exiting IPTV Quick Analysis.")
            break
        else:
            logging.warning(f"[INVALID] Invalid menu selection: {choice}")
            print("❌ Invalid choice. Please try again.")

# ✅ 6.2.0 — if __name__ == "__main__"
if __name__ == "__main__":
    """
    Entry point for the script.
    - Starts the CLI menu loop
    - Logs script start and end
    """
    logging.info("📍 Script entry point reached.")
    try:
        menu()
    except Exception as e:
        logging.critical(f"[FATAL ERROR] Unhandled exception in main loop: {e}")
        print(f"❌ Fatal error occurred: {e}")
    finally:
        logging.info("🏁 IPTV Quick Analysis script terminated.")
 
# ───────────────────────────────────────────────
# SECTION 7.0.0 — GUI Wrapper or Web Dashboard
# ───────────────────────────────────────────────

# ───────────────────────────────────────────────
# SECTION 7.0.1 — launch_dashboard()
# ───────────────────────────────────────────────

def launch_dashboard():
    """
    Launch a simple Flask-based web dashboard for IPTV analysis.
    """
    from flask import Flask, render_template_string

    app = Flask(__name__)

    try:
        with open(CHANNELS_JSON) as f:
            channels = json.load(f)
    except Exception as e:
        logging.error(f"[DASHBOARD ERROR] Failed to load channels: {e}")
        channels = []

    def esc(text):
        return html.escape(str(text)) if text else ""

    rows = []
    for ch in channels[:100]:
        rows.append(f"""
        <tr>
            <td>{esc(ch.get("TVG-ID"))}</td>
            <td>{esc(ch.get("TVG-NAME"))}</td>
            <td><img src="{esc(ch.get("TVG-LOGO"))}" width="50"></td>
            <td>{esc(ch.get("TVG-GROUP"))}</td>
            <td><div style="word-wrap: break-word; max-width: 300px;">{esc(ch.get("TVG-URL", ""))}</div></td>
            <td>{esc(ch.get("matched_epg_id"))}</td>
        </tr>
        """)

    html_template = f"""
    <html>
    <head><title>IPTV Dashboard</title></head>
    <body>
        <h1>IPTV Channel Metadata</h1>
        <table border="1" cellpadding="5" cellspacing="0">
            <thead>
                <tr>
                    <th>TVG-ID</th>
                    <th>Name</th>
                    <th>Logo</th>
                    <th>Group</th>
                    <th>Stream URL</th>
                    <th>EPG Match</th>
                </tr>
            </thead>
            <tbody>
                {''.join(rows)}
            </tbody>
        </table>
    </body>
    </html>
    """

    @app.route("/")
    def home():
        return render_template_string(html_template)

    logging.info("[DASHBOARD] Launching dashboard at http://localhost:5000")
    print("🌐 Dashboard running at http://localhost:5000")
    app.run(debug=False)
