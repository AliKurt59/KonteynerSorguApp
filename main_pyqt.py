import sys
import os
import logging
from PyQt5.QtWidgets import QApplication, QDialog, QLineEdit, QPushButton, QVBoxLayout, QHBoxLayout, QLabel, QMessageBox, QComboBox
from PyQt5.QtCore import Qt
from db_operations import DBManager
from gui_pyqt import KonteynerSorgulamaApp
from config import app_config

class LoginDialog(QDialog):
    def __init__(self, db_manager, parent=None):
        super().__init__(parent)
        self.db = db_manager
        self.logger = logging.getLogger(__name__)
        self.setWindowTitle("Giriş Yap")
        self.setGeometry(300, 200, 400, 250) # x ve y değerlerini de ortalamak için değiştirdim
        self.setFixedSize(400, 250)

        self.username_logged_in = None
        self.user_role_logged_in = None

        layout = QVBoxLayout()
        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("Kullanıcı Adı")
        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("Şifre")
        self.password_input.setEchoMode(QLineEdit.Password)

        # Enter tuşu ile giriş yapabilme
        self.username_input.returnPressed.connect(self.check_login)
        self.password_input.returnPressed.connect(self.check_login)

        login_button = QPushButton("Giriş")
        login_button.clicked.connect(self.check_login)

        layout.addWidget(QLabel("Kullanıcı Adı:"))
        layout.addWidget(self.username_input)
        layout.addWidget(QLabel("Şifre:"))
        layout.addWidget(self.password_input)
        layout.addWidget(login_button)

        self.setLayout(layout)

    def check_login(self):
        username = self.username_input.text().strip()
        password = self.password_input.text().strip()

        # Input validation
        if not username or not password:
            QMessageBox.warning(self, "Eksik Bilgi", "Lütfen kullanıcı adı ve şifre giriniz.")
            return

        # SQL injection korunması için strip ve temel validasyon
        if len(username) > 50 or len(password) > 100:
            QMessageBox.warning(self, "Geçersiz Giriş", "Kullanıcı adı veya şifre çok uzun.")
            return

        try:
            user_info = self.db.validate_user(username, password) # (username, role) veya None döner
            if user_info:
                self.username_logged_in = user_info[0]
                self.user_role_logged_in = user_info[1]
                self.logger.info(f"Başarılı giriş: {username} ({self.user_role_logged_in})")
                QMessageBox.information(self, "Başarılı", f"Giriş başarılı! Hoş geldiniz, {self.username_logged_in} ({self.user_role_logged_in}).")
                self.accept() # Giriş başarılıysa dialog'u kapat
            else:
                self.logger.warning(f"Başarısız giriş denemesi: {username}")
                QMessageBox.warning(self, "Hata", "Geçersiz kullanıcı adı veya şifre.")
                try:
                    self.db.add_user_action_log(username, "Login Attempt Failed", f"Invalid credentials for user: {username}")
                except Exception as log_error:
                    self.logger.error(f"Log yazma hatası: {log_error}")
        except Exception as e:
            self.logger.error(f"Giriş kontrolü hatası: {e}")
            QMessageBox.critical(self, "Sistem Hatası", "Giriş kontrolü sırasında bir hata oluştu. Lütfen tekrar deneyin.")

    def get_logged_in_user_info(self):
        return self.username_logged_in, self.user_role_logged_in


if __name__ == "__main__":
    app = QApplication(sys.argv)

    # Temaları tanımla
    themes = {
        "Koyu Tema": """
            QMainWindow {
                background-color: #2e2e2e;
                color: #f0f0f0;
            }
            QTabWidget::pane {
                border: 1px solid #444;
                background-color: #3c3c3c;
            }
            QTabBar::tab {
                background: #555;
                color: #f0f0f0;
                padding: 8px 15px;
                border-top-left-radius: 5px;
                border-top-right-radius: 5px;
                border: 1px solid #666;
                margin-right: 2px;
            }
            QTabBar::tab:selected {
                background: #4a90e2;
                color: #ffffff;
                border-color: #4a90e2;
            }
            QGroupBox {
                font-weight: bold;
                color: #f0f0f0;
                margin-top: 10px;
                border: 1px solid #555;
                border-radius: 5px;
                padding-top: 15px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 5px;
                color: #4a90e2;
            }
            QLabel {
                color: #f0f0f0;
            }
            QLineEdit, QComboBox, QDateTimeEdit, QSpinBox, QDoubleSpinBox {
                background-color: #444;
                color: #f0f0f0;
                border: 1px solid #666;
                border-radius: 3px;
                padding: 5px;
            }
            QPushButton {
                background-color: #4a90e2;
                color: #ffffff;
                border: none;
                border-radius: 5px;
                padding: 8px 15px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #5b9ff7;
            }
            QPushButton:pressed {
                background-color: #3a7bd5;
            }
            QTableView {
                background-color: #3c3c3c;
                color: #f0f0f0;
                gridline-color: #555;
                selection-background-color: #6a6a6a;
                selection-color: #ffffff;
                border: 1px solid #555;
                border-radius: 5px;
            }
            QHeaderView::section {
                background-color: #555;
                color: #f0f0f0;
                padding: 5px;
                border: 1px solid #666;
                border-radius: 3px;
            }
            QDialog {
                background-color: #3c3c3c;
                color: #f0f0f0;
            }
        """,
        "Açık Tema": """
            QMainWindow {
                background-color: #f0f0f0;
                color: #333333;
            }
            QTabWidget::pane {
                border: 1px solid #cccccc;
                background-color: #ffffff;
            }
            QTabBar::tab {
                background: #e0e0e0;
                color: #333333;
                padding: 8px 15px;
                border-top-left-radius: 5px;
                border-top-right-radius: 5px;
                border: 1px solid #cccccc;
                margin-right: 2px;
            }
            QTabBar::tab:selected {
                background: #6cb6ff;
                color: #ffffff;
                border-color: #6cb6ff;
            }
            QGroupBox {
                font-weight: bold;
                color: #333333;
                margin-top: 10px;
                border: 1px solid #cccccc;
                border-radius: 5px;
                padding-top: 15px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 5px;
                color: #007bff;
            }
            QLabel {
                color: #333333;
            }
            QLineEdit, QComboBox, QDateTimeEdit, QSpinBox, QDoubleSpinBox {
                background-color: #ffffff;
                color: #333333;
                border: 1px solid #cccccc;
                border-radius: 3px;
                padding: 5px;
            }
            QPushButton {
                background-color: #007bff;
                color: #ffffff;
                border: none;
                border-radius: 5px;
                padding: 8px 15px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #0056b3;
            }
            QPushButton:pressed {
                background-color: #004085;
            }
            QTableView {
                background-color: #ffffff;
                color: #333333;
                gridline-color: #e0e0e0;
                selection-background-color: #b3d7ff;
                selection-color: #333333;
                border: 1px solid #cccccc;
                border-radius: 5px;
            }
            QHeaderView::section {
                background-color: #e0e0e0;
                color: #333333;
                padding: 5px;
                border: 1px solid #cccccc;
                border-radius: 3px;
            }
            QDialog {
                background-color: #ffffff;
                color: #333333;
            }
        """
    }

    def apply_theme(theme_name):
        if theme_name in themes:
            app.setStyleSheet(themes[theme_name])

    # Varsayılan temayı uygula
    apply_theme(app_config.DEFAULT_THEME)

    try:
        # Konfigürasyon kontrolü
        if not app_config.DB_PASSWORD:
            QMessageBox.critical(None, "Konfigürasyon Hatası", 
                "Veritabanı şifresi bulunamadı!\n\n" +
                "Lütfen .env dosyasını oluşturun ve DB_PASSWORD değerini ayarlayın.\n" +
                "Örnek: .env.example dosyasını .env olarak kopyalayın.")
            sys.exit(1)
        
        # Veritabanı bağlantısı
        db_config = app_config.get_db_config()
        db_manager = DBManager(**db_config)

        try:
            if not db_manager.check_and_create_tables():
                QMessageBox.critical(None, "Veritabanı Hatası", "Veritabanı tabloları oluşturulamadı veya kontrol edilemedi. Lütfen konsolu kontrol edin.")
                sys.exit(1)

            # Kullanıcı ekleme (sadece ilk çalıştırmada veya manuel olarak)
            # Örnek kullanıcılar, isterseniz yorum satırı yapabilirsiniz
            # db_manager.add_user("admin", "adminpass", "admin")
            # db_manager.add_user("operator", "oppass", "operator")

            # Giriş ekranını aktif hale getirmek için aşağıdaki satırları kullanın:
            login_dialog = LoginDialog(db_manager)
            if login_dialog.exec_() == QDialog.Accepted:
                current_username, current_user_role = login_dialog.get_logged_in_user_info()
                if current_username and current_user_role:
                    window = KonteynerSorgulamaApp(db_manager, current_username, current_user_role, apply_theme)
                    window.show()
                    sys.exit(app.exec_())
                else:
                    QMessageBox.critical(None, "Giriş Hatası", "Kullanıcı bilgileri alınamadı. Uygulama kapatılıyor.")
                    sys.exit(1)
            else:
                sys.exit(0) # Giriş yapılmazsa uygulamayı kapat

            # Giriş ekranı pasifken uygulamayı doğrudan başlatmak için bu satırları kullanın:
            # window = KonteynerSorgulamaApp(db_manager, "guest", "operator", apply_theme) # Misafir kullanıcı olarak başlat
            # window.show()
            # sys.exit(app.exec_())


        except Exception as e:
            app_config.logger.error(f"Uygulama başlatılırken hata: {e}")
            QMessageBox.critical(None, "Uygulama Hatası", f"Uygulama başlatılırken bir hata oluştu:\n{e}\nLütfen veritabanı bağlantı bilgilerini ve PostgreSQL sunucusunun çalıştığından emin olun.")
            sys.exit(1)

        finally:
            if 'db_manager' in locals() and db_manager:
                db_manager.close()
    except Exception as e:
        QMessageBox.critical(None, "Hata", f"Beklenmeyen bir hata oluştu: {e}")
        sys.exit(1)
