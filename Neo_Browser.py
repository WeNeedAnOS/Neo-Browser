import sys, os, json
import speech_recognition as sr
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTabWidget, QToolButton, QStyle, QLineEdit, QPushButton, QLabel,
    QAction, QMenu, QColorDialog, QComboBox, QDialog
)
from PyQt5.QtGui import QPalette, QColor, QPixmap
from PyQt5.QtCore import Qt, QSize, QUrl, QTimer
from PyQt5.QtWidgets import QSplashScreen

try:
    from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEnginePage, QWebEngineProfile
    WEBVIEW_SUPPORTED = True
except ImportError:
    WEBVIEW_SUPPORTED = False

SETTINGS_FILE = "settings.json"
BOOKMARKS_FILE = "bookmarks.json"
OPEN_TABS_FILE = "open_tabs.json"

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
        self.profile = QWebEngineProfile("AlibotProfile", self)
        self.load_settings()
        self.load_bookmarks()
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
