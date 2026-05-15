import sys, os, json, subprocess, platform, threading, time
from pathlib import Path
import speech_recognition as sr
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTabWidget, QToolButton, QStyle, QLineEdit, QPushButton, QLabel,
    QAction, QMenu, QColorDialog, QComboBox, QDialog, QFileDialog, QMessageBox,
    QListWidget, QListWidgetItem, QProgressBar, QSplashScreen
)
from PyQt5.QtGui import QPalette, QColor, QPixmap
from PyQt5.QtCore import Qt, QSize, QUrl, QTimer, pyqtSignal, QObject
import requests
from urllib.parse import urlparse

try:
    from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEnginePage, QWebEngineProfile
    WEBVIEW_SUPPORTED = True
except ImportError:
    WEBVIEW_SUPPORTED = False

SETTINGS_FILE = "settings.json"
BOOKMARKS_FILE = "bookmarks.json"
OPEN_TABS_FILE = "open_tabs.json"
DOWNLOADS_HISTORY_FILE = "downloads_history.json"

class DownloadSignal(QObject):
    progress = pyqtSignal(int, str, int, int)  # download_id, filename, bytes_received, total_bytes
    finished = pyqtSignal(int, str, bool)       # download_id, file_path, success

class DownloadThread(threading.Thread):
    def __init__(self, download_id, url, file_path, signal_obj):
        super().__init__()
        self.download_id = int(download_id)
        self.url = url
        self.file_path = file_path
        self.signal = signal_obj
        self._stop = False

    def stop(self):
        self._stop = True

    def run(self):
        try:
            with requests.get(self.url, stream=True, timeout=15) as r:
                r.raise_for_status()
                total = int(r.headers.get('content-length', 0) or 0)
                bytes_received = 0
                chunk_size = 1024 * 16
                with open(self.file_path, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=chunk_size):
                        if self._stop:
                            f.close()
                            try:
                                os.remove(self.file_path)
                            except:
                                pass
                            self.signal.finished.emit(self.download_id, self.file_path, False)
                            return
                        if chunk:
                            f.write(chunk)
                            bytes_received += len(chunk)
                            self.signal.progress.emit(self.download_id, os.path.basename(self.file_path), bytes_received, total)
                self.signal.finished.emit(self.download_id, self.file_path, True)
        except Exception as e:
            try:
                os.remove(self.file_path)
            except:
                pass
            self.signal.finished.emit(self.download_id, self.file_path, False)

class Browser(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Modern Browser. Secure. Fast. And AI Powered.")
        self.setGeometry(100, 100, 1000, 700)
        self.style = self.style()
        self.search_engine = "Google"
        self.theme_color = "#ecf0f1"
        self.bookmarks = []
        self.last_query = ""
        self.downloads = {}
        self.download_counter = 0
        self.download_widgets = {}
        self.downloads_dir = Path.home() / "Downloads"
        self.downloads_dir.mkdir(parents=True, exist_ok=True)
        self.profile = QWebEngineProfile("AlibotProfile", self)
        self.profile.downloadRequested.connect(self.on_download_requested)
        # signal for manual (requests-based) downloads
        self.download_signal = DownloadSignal()
        self.download_signal.progress.connect(self.on_download_progress)
        self.download_signal.finished.connect(self.on_download_finished)
        self.load_settings()
        self.load_bookmarks()
        self.load_downloads_history()
        self.init_ui()
        self.restore_tabs()
    def init_ui(self):
        self.tabs = QTabWidget()
        self.tabs.setTabsClosable(True)
        self.tabs.tabCloseRequested.connect(self.close_tab)
        self.setCentralWidget(self.tabs)

        self.new_tab_button = QToolButton()
        self.new_tab_button.setText("+")
        self.new_tab_button.clicked.connect(self.new_tab)
        self.tabs.setCornerWidget(self.new_tab_button, Qt.TopLeftCorner)

        menu = self.menuBar()
        file_menu = menu.addMenu("File")

        new_tab_action = QAction("New Tab", self)
        new_tab_action.triggered.connect(self.new_tab)
        file_menu.addAction(new_tab_action)

        ai_panel_action = QAction("AI Panel", self)
        ai_panel_action.triggered.connect(self.open_ai_panel)
        file_menu.addAction(ai_panel_action)

        self.bookmarks_menu = QMenu("Bookmarks", self)
        file_menu.addMenu(self.bookmarks_menu)

        add_fav_action = QAction("Add to Bookmarks", self)
        add_fav_action.triggered.connect(self.add_bookmark)
        file_menu.addAction(add_fav_action)

        settings_action = QAction("Settings", self)
        settings_action.triggered.connect(self.open_settings)
        file_menu.addAction(settings_action)

        downloads_action = QAction("📥 Downloads", self)
        downloads_action.triggered.connect(self.open_downloads)
        file_menu.addAction(downloads_action)

        self.update_bookmarks_menu()
        self.apply_theme()
        self.new_tab()
    def open_ai_panel(self):
        ai_tab = QWidget()
        layout = QVBoxLayout()

        label = QLabel("😊 Hello. How can I help you? (Beta)")
        layout.addWidget(label)

        self.ai_input = QLineEdit()
        self.ai_input.setPlaceholderText("Send a message to AI...")
        layout.addWidget(self.ai_input)

        self.ai_output = QLabel("")
        self.ai_output.setWordWrap(True)
        layout.addWidget(self.ai_output)

        ask_button = QPushButton("Send")
        ask_button.clicked.connect(self.fake_ai_answer)
        layout.addWidget(ask_button)

        ai_tab.setLayout(layout)
        self.tabs.addTab(ai_tab, "AI Assistant")
        self.tabs.setCurrentWidget(ai_tab)

    def fake_ai_answer(self):
        query = self.ai_input.text().strip().lower()
        if not query:
            self.ai_output.setText("Please write something.")
            return

        if "weather" in query:
            response = "Today the weather is sunny with a high of 25°C in Ankara. ☀️"
        elif "hello" in query:
            response = "Hello! 😄 How can I help you?"
        else:
            response = f"I can't do that right now, but I noted the expression '\"{query}\"' 🧠"

        self.ai_output.setText(response)

    def new_tab(self, tab_title=None, url=None):
        tab_title = tab_title or "New Tab"
        url = url or ""
        if tab_title == "New Tab" and not url:
            last = getattr(self, "last_query", "")
            if last:
                url = f"https://www.google.com/search?q={last}"
                tab_title = "Smart Tab"
        try:
            tab = BrowserTab(self.style, self.search_engine, tab_title, self.profile, initial_url=url)
            index = self.tabs.addTab(tab, tab_title)
            self.tabs.setCurrentIndex(index)
        except Exception as e:
            error_tab = QWidget()
            layout = QVBoxLayout()
            msg = QLabel(f"Hata oluştu:\n{str(e)}")
            layout.addWidget(msg)
            error_tab.setLayout(layout)
            index = self.tabs.addTab(error_tab, "Tab Error")
            self.tabs.setCurrentIndex(index)

    def close_tab(self, index):
        if self.tabs.count() > 1:
            self.tabs.removeTab(index)

    def open_settings(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("Settings")
        dlg.setFixedSize(300, 200)
        layout = QVBoxLayout()

        engine_label = QLabel("Default Search Engine:")
        combo = QComboBox()
        combo.addItems([
            "Google", "Duckduckgo", "NeonSearch (Beta)", "Bing", "Yandex",
            "Brave", "You.com", "Swisscows", "Ecosia", "Startpage", "Qwant"
        ])
        combo.setCurrentText(self.search_engine)
        combo.currentTextChanged.connect(self.set_search_engine)
        layout.addWidget(engine_label)
        layout.addWidget(combo)

        theme_button = QPushButton("Choose Theme Color")
        theme_button.clicked.connect(self.choose_theme_color)
        layout.addWidget(theme_button)

        dlg.setLayout(layout)
        dlg.exec_()

    def choose_theme_color(self):
        color = QColorDialog.getColor()
        if color.isValid():
            self.theme_color = color.name()
            self.apply_theme()
            self.save_settings()

    def apply_theme(self):
        palette = self.palette()
        palette.setColor(QPalette.Window, QColor(self.theme_color))
        self.setPalette(palette)

    def set_search_engine(self, engine):
        self.search_engine = engine
        self.save_settings()

    def load_settings(self):
        if os.path.exists(SETTINGS_FILE):
            with open(SETTINGS_FILE, "r") as f:
                data = json.load(f)
                self.search_engine = data.get("engine", "Google")
                self.theme_color = data.get("theme", "#ecf0f1")

    def save_settings(self):
        with open(SETTINGS_FILE, "w") as f:
            json.dump({
                "engine": self.search_engine,
                "theme": self.theme_color
            }, f)

    def save_bookmarks(self):
        with open(BOOKMARKS_FILE, "w") as f:
            json.dump(self.bookmarks, f)

    def load_bookmarks(self):
        if os.path.exists(BOOKMARKS_FILE):
            with open(BOOKMARKS_FILE, "r") as f:
                self.bookmarks = json.load(f)

    def update_bookmarks_menu(self):
        self.bookmarks_menu.clear()
        for url in self.bookmarks:
            action = QAction(url, self)
            action.triggered.connect(lambda _, u=url: self.new_tab(tab_title="Favorites", url=u))
            self.bookmarks_menu.addAction(action)

    def save_open_tabs(self):
        urls = []
        for i in range(self.tabs.count()):
            tab = self.tabs.widget(i)
            if hasattr(tab, 'address_bar'):
                addr = tab.address_bar.text().strip()
                if addr:
                    urls.append(addr)
        with open(OPEN_TABS_FILE, "w") as f:
            json.dump(urls, f)

    def restore_tabs(self):
        if os.path.exists(OPEN_TABS_FILE):
            with open(OPEN_TABS_FILE, "r") as f:
                urls = json.load(f)
                for url in urls:
                    self.new_tab(tab_title="Restored Tabs", url=url)

    def add_bookmark(self):
        tab = self.tabs.currentWidget()
        if hasattr(tab, 'address_bar'):
            address = tab.address_bar.text().strip()
            if address and address not in self.bookmarks:
                self.bookmarks.append(address)
                self.save_bookmarks()
                self.update_bookmarks_menu()

    def closeEvent(self, event):
        self.save_open_tabs()
        event.accept()

    def on_download_requested(self, download_item):
        suggested_name = download_item.suggestedFileName()
        file_path = self.downloads_dir / suggested_name
        
        counter = 1
        original_stem = file_path.stem
        original_suffix = file_path.suffix
        
        while file_path.exists():
            file_path = self.downloads_dir / f"{original_stem}({counter}){original_suffix}"
            counter += 1
        
        self.download_counter += 1
        download_id = self.download_counter
        
        self.downloads[download_id] = {
            'filename': suggested_name,
            'file_path': str(file_path),
            'status': 'indiriliyor',
            'bytes_received': 0,
            'total_bytes': 0
        }
        
        download_item.setPath(str(file_path))
        
        download_item.downloadProgress.connect(
            lambda bytes_received, total_bytes: self.on_download_progress(download_id, bytes_received, total_bytes)
        )
        download_item.finished.connect(
            lambda: self.on_download_finished(download_id, str(file_path), download_item)
        )
        
        download_item.accept()
        
        QMessageBox.information(
            self, 
            "İndirme Başladı",
            f"Dosya indiriliyor:\n{suggested_name}\n\nKonum: {file_path}"
        )

    def on_download_progress(self, download_id, bytes_received, total_bytes):
        try:
            did = int(download_id)
        except:
            try:
                did = int(str(download_id))
            except:
                did = download_id
        if did in self.downloads:
            self.downloads[did]['bytes_received'] = bytes_received
            self.downloads[did]['total_bytes'] = total_bytes
            
            if total_bytes > 0:
                progress_percent = int((bytes_received / total_bytes) * 100)
                mb_received = bytes_received / (1024 * 1024)
                mb_total = total_bytes / (1024 * 1024)
                
                status = f"{self.downloads[did]['filename']}: {progress_percent}% ({mb_received:.1f}/{mb_total:.1f} MB)"
                self.statusBar().showMessage(status)
                if did in self.download_widgets:
                    try:
                        self.download_widgets[did].setMaximum(100)
                        self.download_widgets[did].setValue(progress_percent)
                    except:
                        pass
            else:
                # streaming/unknown size
                self.statusBar().showMessage(f"{self.downloads[did]['filename']}: {bytes_received} bytes received")

    def on_download_finished(self, download_id, file_path, download_item):
        try:
            did = int(download_id)
        except:
            try:
                did = int(str(download_id))
            except:
                did = download_id
        if did in self.downloads:
            info = self.downloads[did]
            success = False
            # handle QWebEngineDownloadItem
            try:
                if hasattr(download_item, 'state'):
                    success = (download_item.state() == 0)
                else:
                    # manual download thread passes boolean success
                    success = bool(download_item)
            except:
                success = bool(download_item)

            if success:
                info['status'] = 'tamamlandı'
                info['file_path'] = file_path
                self.save_downloads_history()
                if did in self.download_widgets:
                    try:
                        self.download_widgets[did].setMaximum(100)
                        self.download_widgets[did].setValue(100)
                    except:
                        pass
                reply = QMessageBox.question(
                    self,
                    "İndirme Tamamlandı",
                    f"Dosya başarıyla indirildi:\n{file_path}\n\nDosya konumunu açmak ister misiniz?",
                    QMessageBox.Yes | QMessageBox.No
                )
                if reply == QMessageBox.Yes:
                    self.open_file_location(file_path)
            else:
                # if it was cancelled already, keep that status
                if info.get('status') != 'iptal edildi':
                    info['status'] = 'başarısız'
                QMessageBox.warning(self, "İndirme Başarısız", "Dosya indirilirken bir hata oluştu.")
            self.statusBar().showMessage("Hazır")

    def open_file_location(self, file_path):
        if platform.system() == "Windows":
            import subprocess
            subprocess.Popen(f'explorer /select, "{file_path}"')
        elif platform.system() == "Darwin":
            subprocess.Popen(["open", "-R", file_path])
        else:
            subprocess.Popen(["xdg-open", str(Path(file_path).parent)])

    def save_link_as(self, url):
        # manual download via requests with a save-as dialog
        try:
            parsed = urlparse(url)
            suggested = os.path.basename(parsed.path) or "download"
        except:
            suggested = "download"
        fname, _ = QFileDialog.getSaveFileName(self, "Dosyayı Kaydet", str(self.downloads_dir / suggested))
        if not fname:
            return
        self.download_counter += 1
        download_id = self.download_counter
        self.downloads[download_id] = {
            'filename': os.path.basename(fname),
            'file_path': fname,
            'status': 'indiriliyor',
            'bytes_received': 0,
            'total_bytes': 0
        }
        self.save_downloads_history()
        thread = DownloadThread(download_id, url, fname, self.download_signal)
        thread.start()
        self.downloads[download_id]['thread'] = thread
        QMessageBox.information(self, "İndirme Başladı", f"Dosya indiriliyor:\n{os.path.basename(fname)}\n\nKonum: {fname}")

    def cancel_download(self, download_id):
        info = self.downloads.get(int(download_id))
        if not info:
            return
        thread = info.get('thread')
        if thread and hasattr(thread, 'stop'):
            thread.stop()
        info['status'] = 'iptal edildi'
        self.save_downloads_history()
        if int(download_id) in self.download_widgets:
            try:
                self.download_widgets[int(download_id)].setValue(0)
            except:
                pass
        QMessageBox.information(self, "İptal", "İndirme iptal edildi.")

    def open_downloads(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("📥 İndirmeler")
        dlg.setGeometry(200, 200, 600, 400)
        layout = QVBoxLayout()
        
        title = QLabel("📥 İndirme Geçmişi")
        title.setStyleSheet("font-size: 14px; font-weight: bold;")
        layout.addWidget(title)
        
        downloads_list = QListWidget()
        
        if not self.downloads:
            empty_label = QLabel("Henüz indirme yok")
            item = QListWidgetItem()
            widget = QWidget()
            h = QHBoxLayout()
            h.addWidget(empty_label)
            widget.setLayout(h)
            item.setSizeHint(widget.sizeHint())
            downloads_list.addItem(item)
            downloads_list.setItemWidget(item, widget)
        else:
            # Show each download with progress bar and buttons
            for download_id, info in sorted(self.downloads.items(), key=lambda x: int(x[0]) if isinstance(x[0], str) else int(x[0]), reverse=True):
                widget = QWidget()
                row = QHBoxLayout()
                vbox = QVBoxLayout()
                label = QLabel(f"📄 {info.get('filename','?')}\nDurum: {info.get('status','?')}\nKonum: {info.get('file_path','?')}")
                vbox.addWidget(label)
                progress = QProgressBar()
                total = info.get('total_bytes', 0) or 0
                received = info.get('bytes_received', 0) or 0
                if total > 0:
                    progress.setMaximum(100)
                    try:
                        progress.setValue(int((received / total) * 100))
                    except:
                        progress.setValue(0)
                else:
                    progress.setMaximum(0)
                vbox.addWidget(progress)
                row.addLayout(vbox)
                open_btn = QPushButton("Aç")
                open_btn.clicked.connect(lambda _, p=info.get('file_path',''): self.open_file_location(p))
                row.addWidget(open_btn)
                cancel_btn = QPushButton("İptal")
                cancel_btn.clicked.connect(lambda _, did=download_id: self.cancel_download(did))
                row.addWidget(cancel_btn)
                widget.setLayout(row)
                item = QListWidgetItem()
                item.setSizeHint(widget.sizeHint())
                downloads_list.addItem(item)
                downloads_list.setItemWidget(item, widget)
                try:
                    self.download_widgets[int(download_id)] = progress
                except:
                    try:
                        self.download_widgets[int(str(download_id))] = progress
                    except:
                        pass
        
        layout.addWidget(downloads_list)
        
        button_layout = QHBoxLayout()
        
        open_folder_btn = QPushButton("📁 İndirmeler Klasörünü Aç")
        open_folder_btn.clicked.connect(lambda: self.open_downloads_folder())
        button_layout.addWidget(open_folder_btn)
        
        clear_btn = QPushButton("🗑️ Geçmişi Temizle")
        clear_btn.clicked.connect(lambda: self.clear_downloads_history(dlg))
        button_layout.addWidget(clear_btn)
        
        layout.addLayout(button_layout)
        
        dlg.setLayout(layout)
        dlg.exec_()

    def open_downloads_folder(self):
        if platform.system() == "Windows":
            os.startfile(str(self.downloads_dir))
        elif platform.system() == "Darwin":
            subprocess.Popen(["open", str(self.downloads_dir)])
        else:
            subprocess.Popen(["xdg-open", str(self.downloads_dir)])

    def clear_downloads_history(self, parent_dialog):
        reply = QMessageBox.question(
            parent_dialog,
            "Onay",
            "İndirme geçmişini temizlemek istediğinizden emin misiniz?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self.downloads.clear()
            self.save_downloads_history()
            parent_dialog.close()
            self.open_downloads()

    def save_downloads_history(self):
        serializable = {}
        for k, v in self.downloads.items():
            key = str(k)
            copyv = {kk: vv for kk, vv in v.items() if kk != 'thread'}
            serializable[key] = copyv
        with open(DOWNLOADS_HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(serializable, f, ensure_ascii=False, indent=2)

    def load_downloads_history(self):
        if os.path.exists(DOWNLOADS_HISTORY_FILE):
            try:
                with open(DOWNLOADS_HISTORY_FILE, "r", encoding="utf-8") as f:
                    raw = json.load(f)
                    # normalize keys to int
                    self.downloads = {int(k): v for k, v in raw.items()}
                    if self.downloads:
                        max_id = max(int(k) for k in self.downloads.keys())
                        self.download_counter = max_id
            except:
                self.downloads = {}


class BrowserTab(QWidget):
    def __init__(self, style, search_engine, tab_name, shared_profile, initial_url=""):
        super().__init__()
        self.style = style
        self.search_engine = search_engine
        self.layout = QVBoxLayout()
        self.setLayout(self.layout)

        self.address_bar = QLineEdit()
        self.address_bar.setPlaceholderText("Enter address...")
        self.layout.addWidget(self.address_bar)

        nav = QHBoxLayout()
        self.back = QPushButton()
        self.back.setIcon(style.standardIcon(QStyle.SP_ArrowBack))
        self.back.setIconSize(QSize(28, 28))
        nav.addWidget(self.back)

        self.forward = QPushButton()
        self.forward.setIcon(style.standardIcon(QStyle.SP_ArrowForward))
        self.forward.setIconSize(QSize(28, 28))
        nav.addWidget(self.forward)

        self.refresh = QPushButton()
        self.refresh.setIcon(style.standardIcon(QStyle.SP_BrowserReload))
        self.refresh.setIconSize(QSize(28, 28))
        nav.addWidget(self.refresh)

        self.layout.addLayout(nav)

        if WEBVIEW_SUPPORTED:
            self.browser_view = QWebEngineView()
            if shared_profile:
                self.page = QWebEnginePage(shared_profile, self.browser_view)
                self.browser_view.setPage(self.page)
            # enable custom context menu for link downloads
            self.browser_view.setContextMenuPolicy(Qt.CustomContextMenu)
            self.browser_view.customContextMenuRequested.connect(self.on_context_menu)
            self.layout.addWidget(self.browser_view)

        if tab_name in ["Welcome!", "New Tab", "Smart Tab"]:
            self.search_bar = QLineEdit()
            self.search_bar.setPlaceholderText("Enter search query...")
            self.search_bar.returnPressed.connect(self.perform_search)
            self.layout.addWidget(self.search_bar)

            search_row = QHBoxLayout()
            self.search_button = QPushButton("Search")
            self.search_button.clicked.connect(self.perform_search)
            search_row.addWidget(self.search_button)

            self.mic_button = QPushButton("🎤")
            self.mic_button.clicked.connect(self.listen_and_search)
            search_row.addWidget(self.mic_button)

            self.layout.addLayout(search_row)

        if WEBVIEW_SUPPORTED:
            self.back.clicked.connect(lambda: self.browser_view.back())
            self.forward.clicked.connect(lambda: self.browser_view.forward())
            self.refresh.clicked.connect(lambda: self.browser_view.reload())

            if initial_url:
                self.browser_view.setUrl(QUrl(initial_url))
                self.address_bar.setText(initial_url)

    def on_context_menu(self, pos):
        data = self.browser_view.page().contextMenuData()
        menu = QMenu(self)
        try:
            if data.linkUrl() and not data.linkUrl().isEmpty():
                link = data.linkUrl().toString()
                save_action = QAction("Bağlantıyı Farklı Kaydet...", self)
                save_action.triggered.connect(lambda: self.parent().window().save_link_as(link))
                menu.addAction(save_action)
        except:
            pass
        # add default actions
        menu.addAction(self.browser_view.pageAction(QWebEnginePage.OpenLinkInNewWindow))
        menu.exec_(self.browser_view.mapToGlobal(pos))

    def perform_search(self):
        if hasattr(self, 'search_bar'):
            query = self.search_bar.text()
            self.parent().window().last_query = query
        else:
            return

        engines = {
            "Google": f"https://www.google.com/search?q={query}",
            "Duckduckgo": f"https://duckduckgo.com/?q={query}",
            "AliSearch": f"http://localhost:5000/search?q={query}",
            "Bing": f"https://www.bing.com/search?q={query}",
            "Yandex": f"https://yandex.com/search/?text={query}",
            "Brave": f"https://search.brave.com/search?q={query}",
            "You.com": f"https://you.com/search?q={query}",
            "Swisscows": f"https://swisscows.com/web?query={query}",
            "Ecosia": f"https://www.ecosia.org/search?q={query}",
            "Startpage": f"https://www.startpage.com/do/search?query={query}",
            "Qwant": f"https://www.qwant.com/?q={query}"
        }

        engine = getattr(self.parent().window(), "search_engine", self.search_engine)
        url = engines.get(engine, engines["Google"])

        if WEBVIEW_SUPPORTED:
            self.browser_view.setUrl(QUrl(url))
            self.address_bar.setText(url)

    def listen_and_search(self):
        if not hasattr(self, 'search_bar'):
            return
        recognizer = sr.Recognizer()
        with sr.Microphone() as source:
            try:
                self.search_bar.setText("Listening...")
                audio = recognizer.listen(source, timeout=3, phrase_time_limit=5)
                query = recognizer.recognize_google(audio, language="tr-TR")
                self.search_bar.setText(query)
                self.perform_search()
            except:
                self.search_bar.setText("No speech detected.")

if __name__ == "__main__":
    app = QApplication(sys.argv)

    splash_pix = QPixmap(600, 400)
    splash_pix.fill(QColor("#2c3e50"))
    splash = QSplashScreen(splash_pix)
    splash.showMessage("AI is Loading...", Qt.AlignBottom | Qt.AlignCenter, Qt.white)
    splash.show()

    win = Browser()
    QTimer.singleShot(2000, splash.close)
    QTimer.singleShot(2000, lambda: win.show())

    sys.exit(app.exec_())
