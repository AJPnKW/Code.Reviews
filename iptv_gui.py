import sys, json, requests, re, logging, csv
import xml.etree.ElementTree as ET
from datetime import datetime
from difflib import get_close_matches
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QPushButton, QTextEdit, QLabel,
    QComboBox, QLineEdit, QTableWidget, QTableWidgetItem, QHBoxLayout
)

# Logging setup
logging.basicConfig(filename='iptv_analysis.log', level=logging.DEBUG)

# File paths
BASE = r'C:\Users\Lenovo\PROJECTS\IPTV\IPTV_quick_analysis'
URL_JSON = f'{BASE}\\playlist_epg_urls.json'
CHANNELS_JSON = f'{BASE}\\channels_metadata.json'
EPG_JSON = f'{BASE}\\epg_metadata.json'

class IPTVApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("IPTV Quick Analysis")
        self.resize(900, 600)
        self.layout = QVBoxLayout()
        self.status = QTextEdit()
        self.status.setReadOnly(True)

        # Buttons
        self.layout.addWidget(QLabel("Choose an action:"))
        self.layout.addWidget(self.make_button("Validate URLs", self.validate_urls))
        self.layout.addWidget(self.make_button("Extract M3U Metadata", self.extract_m3u))
        self.layout.addWidget(self.make_button("Extract EPG Metadata", self.extract_epg))
        self.layout.addWidget(self.make_button("Export to CSV/HTML", self.export_data))
        self.layout.addWidget(self.make_button("Smart Match Channels to EPG", self.smart_match))
        self.layout.addWidget(self.make_button("View Logs", self.view_logs))

        # Filters
        self.filter_layout = QHBoxLayout()
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Search channel name or ID...")
        self.search_box.textChanged.connect(self.filter_channels)
        self.filter_layout.addWidget(self.search_box)

        self.language_filter = QComboBox()
        self.language_filter.addItem("All Languages")
        self.language_filter.currentTextChanged.connect(self.filter_channels)
        self.filter_layout.addWidget(self.language_filter)

        self.group_filter = QComboBox()
        self.group_filter.addItem("All Groups")
        self.group_filter.currentTextChanged.connect(self.filter_channels)
        self.filter_layout.addWidget(self.group_filter)

        self.layout.addLayout(self.filter_layout)

        # Table
        self.table = QTableWidget()
        self.layout.addWidget(self.table)
        self.layout.addWidget(self.status)
        self.setLayout(self.layout)

        self.channels = []
        self.load_filters()

    def make_button(self, text, func):
        btn = QPushButton(text)
        btn.clicked.connect(func)
        return btn

    def log(self, msg):
        self.status.append(msg)
        logging.debug(msg)

    def load_filters(self):
        try:
            with open(CHANNELS_JSON) as f:
                self.channels = json.load(f)
            langs = sorted(set(c.get('TVG-LANGUAGE', 'Unknown') for c in self.channels))
            groups = sorted(set(c.get('TVG-GROUP', 'Unknown') for c in self.channels))
            self.language_filter.addItems(langs)
            self.group_filter.addItems(groups)
        except:
            pass

    def filter_channels(self):
        query = self.search_box.text().lower()
        lang = self.language_filter.currentText()
        group = self.group_filter.currentText()
        filtered = []
        for c in self.channels:
            if query and query not in str(c.get('TVG-NAME', '')).lower():
                continue
            if lang != "All Languages" and c.get('TVG-LANGUAGE') != lang:
                continue
            if group != "All Groups" and c.get('TVG-GROUP') != group:
                continue
            filtered.append(c)
        self.display_table(filtered)

    def display_table(self, data):
        self.table.setRowCount(len(data))
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["TVG-ID", "Name", "Group", "Language", "URL"])
        for i, c in enumerate(data):
            self.table.setItem(i, 0, QTableWidgetItem(c.get('TVG-ID', '')))
            self.table.setItem(i, 1, QTableWidgetItem(c.get('TVG-NAME', '')))
            self.table.setItem(i, 2, QTableWidgetItem(c.get('TVG-GROUP', '')))
            self.table.setItem(i, 3, QTableWidgetItem(c.get('TVG-LANGUAGE', '')))
            self.table.setItem(i, 4, QTableWidgetItem(c.get('TVG-URL', '')))

    def validate_urls(self):
        self.log("🔍 Validating URLs...")
        with open(URL_JSON) as f:
            data = json.load(f)
        timestamp = datetime.now().isoformat()
        for category in ['playlist_urls', 'epg_urls']:
            for url in data.get(category, []):
                try:
                    r = requests.head(url, timeout=10)
                    status = {'timestamp': timestamp, 'status_code': r.status_code, 'ok': r.ok}
                    data.setdefault('status_history', {}).setdefault(url, []).append(status)
                    self.log(f"✅ {url} → {r.status_code}")
                except Exception as e:
                    data.setdefault('status_history', {}).setdefault(url, []).append({
                        'timestamp': timestamp, 'error': str(e)
                    })
                    self.log(f"❌ {url} → {e}")
        with open(URL_JSON, 'w') as f:
            json.dump(data, f, indent=2)

    def extract_m3u(self):
        self.log("📺 Extracting M3U metadata...")
        with open(URL_JSON) as f:
            data = json.load(f)
        channels = []
        for url in data.get('playlist_urls', []):
            try:
                r = requests.get(url, timeout=15)
                lines = r.text.splitlines()
                for i in range(len(lines)):
                    if lines[i].startswith('#EXTINF'):
                        info = lines[i]
                        stream = lines[i+1] if i+1 < len(lines) else ''
                        match = re.search(r'tvg-id="(.*?)".*?tvg-name="(.*?)".*?tvg-logo="(.*?)".*?group-title="(.*?)"', info)
                        if match:
                            channels.append({
                                'TVG-ID': match.group(1),
                                'TVG-NAME': match.group(2),
                                'TVG-LOGO': match.group(3),
                                'TVG-GROUP': match.group(4),
                                'TVG-URL': stream,
                                'TVG-LANGUAGE': 'Unknown',
                                'source_url': url
                            })
                self.log(f"✅ Parsed {url} → {len(channels)} channels")
            except Exception as e:
                self.log(f"❌ Failed to parse {url}: {e}")
        with open(CHANNELS_JSON, 'w') as f:
            json.dump(channels, f, indent=2)
        self.channels = channels
        self.load_filters()
        self.display_table(channels)

    def extract_epg(self):
        self.log("📅 Extracting EPG metadata...")
        with open(URL_JSON) as f:
            data = json.load(f)
        epg_data = []
        for url in data.get('epg_urls', []):
            try:
                r = requests.get(url, timeout=15)
                root = ET.fromstring(r.content)
                for channel in root.findall('channel'):
                    epg_data.append({
                        'TVG-ID': channel.get('id'),
                        'TVG-EPGID': channel.findtext('display-name'),
                        'TVG-EPGURL': url,
                        'type': 'EPG',
                        'language': 'unknown'
                    })
                self.log(f"✅ Parsed {url} → {len(epg_data)} entries")
            except Exception as e:
                self.log(f"❌ Failed to parse {url}: {e}")
        with open(EPG_JSON, 'w') as f:
            json.dump(epg_data, f, indent=2)

    def export_data(self):
        self.log("📤 Exporting to CSV and HTML...")
        try:
            with open(CHANNELS_JSON) as f:
                channels = json.load(f)
            with open(f'{BASE}\\channels_export.csv', 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=channels[0].keys())
                writer.writeheader()
                writer.writerows(channels)
            with open(f'{BASE}\\channels_export.html', 'w', encoding='utf-8') as f:
                f.write("<html><body><table border='1'>")
                f.write("<tr>" + "".join(f"<th>{k}</th>" for k in channels[0].keys()) + "</tr>")
                for c in channels:
                f.write("</table></body></html>")
            self.log("📤 Exported channels to CSV and HTML.")
        except Exception as e:
            self.log(f"❌ Export failed: {e}")

    def smart_match(self):
        self.log("🧠 Smart matching channels to EPG entries...")
        try:
            with open(CHANNELS_JSON) as f:
                channels = json.load(f)
            with open(EPG_JSON) as f:
                epg = json.load(f)
            epg_names = [e.get('TVG-EPGID', '') for e in epg if e.get('TVG-EPGID')]
            for c in channels:
                name = c.get('TVG-NAME', '')
                match = get_close_matches(name, epg_names, n=1, cutoff=0.8)
                if match:
                    c['matched_epg_id'] = match[0]
            with open(CHANNELS_JSON, 'w') as f:
                json.dump(channels, f, indent=2)
            self.log(f"✅ Smart match complete. Updated channels_metadata.json.")
            self.channels = channels
            self.display_table(channels)
        except Exception as e:
            self.log(f"❌ Smart match failed: {e}")

    def view_logs(self):
        try:
            with open('iptv_analysis.log', 'r') as f:
                lines = f.readlines()[-20:]
                self.status.append("📝 Last log entries:")
                self.status.append("\n".join(lines))
        except Exception as e:
            self.status.append(f"❌ Error reading log: {e}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = IPTVApp()
    window.show()
    sys.exit(app.exec())
