import sys
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QTabWidget, QWidget, QVBoxLayout,
    QHBoxLayout, QGridLayout, QLabel, QLineEdit, QPushButton,
    QComboBox, QMessageBox, QTableView, QHeaderView, QDialog, QFormLayout,
    QDateEdit, QDateTimeEdit, QCheckBox, QSpinBox, QDoubleSpinBox, QGroupBox,
    QFileDialog, QStatusBar
)
from PyQt5.QtCore import Qt, QAbstractTableModel, QModelIndex, QVariant, QDate, QDateTime, QRegExp
from PyQt5.QtGui import QFont, QRegExpValidator

# Mevcut bağımlılıklar
from db_operations import DBManager
from reports import ReportGenerator
from datetime import datetime, timedelta # timedelta da eklendi
import pandas as pd
import re

def calculate_iso6346_check_digit(container_id_without_check_digit):
    """
    ISO 6346 standardına göre bir konteyner numarasının kontrol basamağını (check digit) DOĞRU şekilde hesaplar.
    Parametre olarak 4 harf ve 6 rakamdan oluşan bir string alır (örn: 'CSQU305438').
    """
    if not re.fullmatch(r"^[A-Z]{4}\d{6}$", container_id_without_check_digit):
        return None # Geçersiz format

    # Harflere karşılık gelen DOĞRU sayısal değerler (11 ve katları atlanarak)
    letter_values = {}
    value = 10
    for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
        letter_values[letter] = value
        value += 1
        if value % 11 == 0:
            value += 1
            
    total_sum = 0
    # İlk 4 harfi işle
    for i in range(4):
        total_sum += letter_values[container_id_without_check_digit[i]] * (2 ** i)

    # Sonraki 6 rakamı işle
    for i in range(4, 10):
        total_sum += int(container_id_without_check_digit[i]) * (2 ** i)
        
    # Modulo 11 al
    check_digit = total_sum % 11
    
    # Eğer sonuç 10 ise, kontrol basamağı 0 olur
    return 0 if check_digit == 10 else check_digit


# QTableView için özel PandasModel
class PandasModel(QAbstractTableModel):
    def __init__(self, df=pd.DataFrame()):
        super().__init__()
        self._data = df

    def rowCount(self, parent=QModelIndex()):
        return self._data.shape[0]

    def columnCount(self, parent=QModelIndex()):
        return self._data.shape[1]

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return QVariant()
        if role == Qt.DisplayRole:
            value = self._data.iloc[index.row(), index.column()]
            if pd.isna(value): # NaN değerleri boş string olarak göster
                return ""
            # Tarih formatlama
            if isinstance(value, (datetime, pd.Timestamp)):
                return value.strftime('%Y-%m-%d %H:%M:%S')
            # Boolean değerler için
            if isinstance(value, bool):
                return "Evet" if value else "Hayır"
            return str(value)
        elif role == Qt.TextAlignmentRole:
            # Sütunlara göre hizalama ayarı
            if self._data.columns[index.column()] in ['imo_number', 'container_size', 'weight_kg']:
                return Qt.AlignRight | Qt.AlignVCenter
            return Qt.AlignLeft | Qt.AlignVCenter
        return QVariant()

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole:
            if orientation == Qt.Horizontal:
                # Sütun isimlerini daha okunaklı hale getirebiliriz
                header_map = {
                    "vessel_name": "Gemi Adı",
                    "imo_number": "IMO Numarası",
                    "arrival_port": "Varış Limanı",
                    "departure_port": "Kalkış Limanı",
                    "container_id": "Konteyner Numarası",
                    "container_size": "Konteyner Boyutu",
                    "container_type": "Konteyner Tipi",
                    "operation_type": "Operasyon Tipi",
                    "timestamp": "Genel İşlem Zamanı",
                    "terminal_name": "Terminal Adı",
                    "transport_mode": "Taşıma Modu",
                    "container_status": "Konteyner Durumu",
                    "location_area": "Lokasyon Alanı",
                    "handling_equipment": "Elleçleme Ekipmanı",
                    "customs_clearance_status": "Gümrük Durumu",
                    "weight_kg": "Ağırlık (kg)",
                    "hazmat_flag": "Tehlikeli Madde",
                    "arrival_date": "Limana Giriş Tarihi",
                    "departure_date": "Limandan Çıkış Tarihi",
                    "log_id": "Log ID",
                    "action_id": "Eylem ID",
                    "username": "Kullanıcı Adı",
                    "action_type": "Eylem Tipi",
                    "description": "Açıklama",
                    "action_time": "Eylem Zamanı",
                    "id": "Kullanıcı ID", # Kullanıcı yönetimi için
                    "password_hash": "Şifre Hash" # Kullanıcı yönetimi için
                }
                return header_map.get(self._data.columns[section], self._data.columns[section].replace('_', ' ').title())
            elif orientation == Qt.Vertical:
                return str(section + 1)
        return QVariant()

    def setDataFrame(self, dataframe):
        self.beginResetModel()
        self._data = dataframe
        self.endResetModel()

    def getDataFrame(self):
        return self._data


class OperationFormDialog(QDialog):
    def __init__(self, parent=None, db_manager=None, data=None):
        super().__init__(parent)
        self.setWindowTitle("Operasyon Kaydı Detayları")
        self.db = db_manager
        self.data = data # Mevcut veri, eğer güncelleme ise

        self.form_layout = QFormLayout()
        self.inputs = {}

        # Sütun bilgileri ve varsayılan seçenekler (DB'den dinamik çekilecek)
        self.fields = [
            # BU SATIRIN DOĞRU OLDUĞUNDAN EMİN OLUN
            ("container_id", "Konteyner Numarası", QLineEdit, r"^[A-Z]{4}\d{7}$"), # ABCD1234567 formatı (Bitişik, tiresiz)
            ("vessel_name", "Gemi Adı", QComboBox, self.db.get_unique_column_values('vessel_name')),
            ("imo_number", "IMO Numarası", QLineEdit, r"^\d{7}$"), # 7 basamaklı sayı
            ("arrival_port", "Varış Limanı", QComboBox, self.db.get_unique_column_values('arrival_port')),
            ("departure_port", "Kalkış Limanı", QComboBox, self.db.get_unique_column_values('departure_port')),
            ("arrival_date", "Limana Giriş Tarihi", QDateTimeEdit, None),
            ("departure_date", "Limandan Çıkış Tarihi", QDateTimeEdit, None),
            ("container_status", "Konteyner Durumu", QComboBox, self.db.get_unique_column_values('container_status') or ['In Port', 'On Vessel', 'Departed', 'In Transit', 'Customs Hold', 'Maintenance']),
            ("location_area", "Lokasyon Alanı", QComboBox, self.db.get_unique_column_values('location_area') or ['Yard', 'Quay', 'Warehouse', 'Sea', 'Truck', 'Rail']),
            ("operation_type", "Operasyon Tipi", QComboBox, self.db.get_unique_column_values('operation_type') or ['Arrival', 'Departure', 'Yard Move', 'Customs Clearance', 'Maintenance', 'Loading', 'Unloading', 'Manual Update']),
            ("timestamp", "Genel İşlem Zamanı", QDateTimeEdit, None), # Bu alan genellikle otomatik doldurulur
            ("terminal_name", "Terminal Adı", QComboBox, self.db.get_unique_column_values('terminal_name') or ['Terminal A', 'Terminal B']),
            ("transport_mode", "Taşıma Modu", QComboBox, self.db.get_unique_column_values('transport_mode') or ['SEA', 'ROAD', 'RAIL']),
            ("container_size", "Konteyner Boyutu", QComboBox, self.db.get_unique_column_values('container_size') or ['20', '40', '45']),
            ("container_type", "Konteyner Tipi", QComboBox, self.db.get_unique_column_values('container_type') or ['DRY', 'REEFER', 'OPEN TOP', 'FLAT RACK', 'TANK']),
            ("handling_equipment", "Elleçleme Ekipmanı", QComboBox, self.db.get_unique_column_values('handling_equipment')),
            ("customs_clearance_status", "Gümrük Durumu", QComboBox, self.db.get_unique_column_values('customs_clearance_status') or ['Cleared', 'Pending', 'Rejected']),
            ("weight_kg", "Ağırlık (kg)", QSpinBox, None),
            ("hazmat_flag", "Tehlikeli Madde?", QCheckBox, None)
        ]

        # Sütun isimleri map'i (Türkçe etiketler için)
        self.column_name_map = {
            "vessel_name": "Gemi Adı", "imo_number": "IMO Numarası", "arrival_port": "Varış Limanı",
            "departure_port": "Kalkış Limanı", "container_id": "Konteyner Numarası", "container_size": "Konteyner Boyutu",
            "container_type": "Konteyner Tipi", "operation_type": "Operasyon Tipi", "timestamp": "Genel İşlem Zamanı",
            "terminal_name": "Terminal Adı", "transport_mode": "Taşıma Modu", "container_status": "Konteyner Durumu",
            "location_area": "Lokasyon Alanı", "handling_equipment": "Elleçleme Ekipmanı",
            "customs_clearance_status": "Gümrük Durumu", "weight_kg": "Ağırlık (kg)", "hazmat_flag": "Tehlikeli Madde?",
            "arrival_date": "Limana Giriş Tarihi",
            "departure_date": "Limandan Çıkış Tarihi"
        }


        for col_name, label_text, widget_type, options_or_regex in self.fields:
            input_widget = None
            if widget_type == QLineEdit:
                input_widget = QLineEdit()
                if options_or_regex: # Bu durumda regex pattern'i
                    validator = QRegExpValidator(QRegExp(options_or_regex), input_widget)
                    input_widget.setValidator(validator)
                if col_name == "container_id" and self.data: # Güncelleme modunda container_id'yi düzenlenemez yap
                    input_widget.setReadOnly(True)
            elif widget_type == QComboBox:
                input_widget = QComboBox()
                if options_or_regex: # Bu durumda seçenek listesi
                    input_widget.addItems(sorted(list(set(map(str, options_or_regex))))) # Tüm seçenekleri string'e çevir
                input_widget.setEditable(True) # Kullanıcının kendi değerini girmesine izin ver
            elif widget_type == QDateTimeEdit:
                input_widget = QDateTimeEdit(QDateTime.currentDateTime())
                input_widget.setCalendarPopup(True)
                input_widget.setDisplayFormat("yyyy-MM-dd HH:mm:ss")
            elif widget_type == QCheckBox:
                input_widget = QCheckBox()
            elif widget_type == QSpinBox:
                input_widget = QSpinBox()
                input_widget.setRange(0, 1000000) # Geniş bir aralık
            elif widget_type == QDoubleSpinBox:
                input_widget = QDoubleSpinBox()
                input_widget.setRange(0.0, 1000000.0)

            self.inputs[col_name] = input_widget
            self.form_layout.addRow(QLabel(label_text), input_widget)

            # Eğer güncelleme modu ise, mevcut verileri yükle
            if self.data and col_name in self.data:
                value = self.data[col_name]
                if isinstance(input_widget, QLineEdit):
                    input_widget.setText(str(value) if value is not None else "")
                elif isinstance(input_widget, QComboBox):
                    # ComboBox'a mevcut değeri ekle eğer listede yoksa
                    if value is not None and str(value) not in [input_widget.itemText(i) for i in range(input_widget.count())]:
                        input_widget.addItem(str(value))
                    input_widget.setCurrentText(str(value) if value is not None else "")
                elif isinstance(input_widget, QDateTimeEdit):
                    if value and pd.notna(value): # Pandas NaT kontrolü
                        dt_value = value.to_pydatetime() if isinstance(value, pd.Timestamp) else value
                        qdt = QDateTime(dt_value.year, dt_value.month, dt_value.day, dt_value.hour, dt_value.minute, dt_value.second)
                        input_widget.setDateTime(qdt)
                    else:
                        input_widget.setDateTime(QDateTime(2000, 1, 1, 0, 0, 0)) # Boşsa varsayılan bir tarih
                elif isinstance(input_widget, QCheckBox):
                    input_widget.setChecked(bool(value))
                elif isinstance(input_widget, QSpinBox):
                    input_widget.setValue(int(value) if value is not None and pd.notna(value) else 0)
                elif isinstance(input_widget, QDoubleSpinBox):
                    input_widget.setValue(float(value) if value is not None and pd.notna(value) else 0.0)


        self.save_button = QPushButton("Kaydet")
        self.save_button.clicked.connect(self.accept) # QDialog'u accept() ile kapat
        self.form_layout.addRow(self.save_button)
        self.setLayout(self.form_layout)

    def get_data(self):
        # Kullanıcının girdiği verileri topla
        collected_data = {}
        for col_name, input_widget in self.inputs.items():
            value = None
            if isinstance(input_widget, QLineEdit):
                value = input_widget.text().strip()
                if not value: value = None # Boş stringleri None yap
            elif isinstance(input_widget, QComboBox):
                value = input_widget.currentText().strip()
                if not value: value = None
            elif isinstance(input_widget, QDateTimeEdit):
                # Eğer tarih seçilmemişse veya boşsa None olarak ayarla
                # QDateTime(2000, 1, 1, 0, 0, 0) varsayılan boş tarihi temsil eder
                if input_widget.dateTime().toString("yyyy-MM-dd HH:mm:ss") == "2000-01-01 00:00:00":
                    value = None
                else:
                    value = input_widget.dateTime().toPyDateTime()
            elif isinstance(input_widget, QCheckBox):
                value = input_widget.isChecked()
            elif isinstance(input_widget, (QSpinBox, QDoubleSpinBox)):
                value = input_widget.value()
            
            # Özel format kontrolleri ve None atamaları
            if col_name == 'imo_number' and value is not None:
                try:
                    value = int(value)
                except ValueError:
                    value = None # Geçersiz sayı ise None yap

            if col_name == 'container_size' and value is not None:
                try:
                    value = int(value)
                except ValueError:
                    value = None
            
            if col_name == 'weight_kg' and value is not None:
                try:
                    value = int(value) # int veya float olabilir
                except ValueError:
                    value = None

            collected_data[col_name] = value
        return collected_data

    def validate_data(self, data):
        # Gerekli alanların boş olup olmadığını kontrol et
        required_fields = ["vessel_name", "container_id", "operation_type", "container_status"]
        for field in required_fields:
            if not data.get(field):
                QMessageBox.warning(self, "Eksik Bilgi", f"'{self.column_name_map.get(field, field)}' alanı boş bırakılamaz.")
                return False

        # IMO Numarası kontrolü
        imo = data.get('imo_number')
        if imo is not None and (not isinstance(imo, int) or not (1000000 <= imo <= 9999999)):
            QMessageBox.warning(self, "Geçersiz Format", "IMO Numarası 7 basamaklı bir sayı olmalıdır.")
            return False

       # Konteyner Numarası formatı (ör: ABCD1234567)
        container_id = data.get('container_id')
        if not container_id or not re.fullmatch(r"^[A-Z]{4}\d{7}$", container_id):
            QMessageBox.warning(self, "Geçersiz Format", "Konteyner Numarası 'ABCD1234567' gibi bir formatta olmalıdır (4 harf, 7 rakam).")
            return False
            
        # --- YENİ EKLENEN KONTROL BASAMAĞI (CHECK DIGIT) DOĞRULAMASI ---
        id_part = container_id[:-1]  # Son haneyi (check digit) hariç tut
        user_check_digit = int(container_id[-1]) # Kullanıcının girdiği check digit

        correct_check_digit = calculate_iso6346_check_digit(id_part)

        if correct_check_digit is None: # Bu durum normalde format kontrolünden geçilirse yaşanmaz
             QMessageBox.critical(self, "Hesaplama Hatası", "Konteyner ID formatı nedeniyle kontrol basamağı hesaplanamadı.")
             return False

        if user_check_digit != correct_check_digit:
            QMessageBox.warning(self, "Geçersiz Konteyner Numarası",
                                f"Girdiğiniz konteyner numarası geçersiz.\n\n"
                                f"Hesaplanan doğru kontrol basamağı: {correct_check_digit}\n"
                                f"Doğru numara şu şekilde olmalı: {id_part}{correct_check_digit}")
            return False
        # --- KONTROL BASAMAĞI DOĞRULAMASI SONU ---
            
        # Konteyner Boyutu kontrolü

        # Konteyner Boyutu kontrolü
        container_size = data.get('container_size')
        if container_size is not None and not isinstance(container_size, int):
            QMessageBox.warning(self, "Geçersiz Format", "Konteyner Boyutu sayısal bir değer olmalıdır.")
            return False

        # Ağırlık kontrolü (pozitif olmalı)
        weight_kg = data.get('weight_kg')
        if weight_kg is not None and weight_kg < 0:
            QMessageBox.warning(self, "Geçersiz Değer", "Ağırlık (kg) negatif olamaz.")
            return False

        return True

# Yeni: Tarih aralığı ve periyot seçimi için diyalog
class BillingReportDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Faturalandırma Raporu Seçenekleri")
        self.setGeometry(300, 300, 400, 200)

        layout = QFormLayout()

        self.start_date_edit = QDateEdit(QDate.currentDate().addYears(-1)) # Varsayılan: 1 yıl öncesi
        self.start_date_edit.setCalendarPopup(True)
        self.start_date_edit.setDisplayFormat("yyyy-MM-dd")
        layout.addRow("Başlangıç Tarihi:", self.start_date_edit)

        self.end_date_edit = QDateEdit(QDate.currentDate()) # Varsayılan: Bugün
        self.end_date_edit.setCalendarPopup(True)
        self.end_date_edit.setDisplayFormat("yyyy-MM-dd")
        layout.addRow("Bitiş Tarihi:", self.end_date_edit)

        self.period_combo = QComboBox()
        self.period_combo.addItems(['monthly', 'weekly', 'daily', 'yearly'])
        self.period_combo.setCurrentText('monthly') # Varsayılan: Aylık
        layout.addRow("Periyot:", self.period_combo)

        button_box = QHBoxLayout()
        self.generate_button = QPushButton("Rapor Oluştur")
        self.generate_button.clicked.connect(self.accept)
        button_box.addWidget(self.generate_button)

        layout.addRow(button_box)
        self.setLayout(layout)

    def get_report_parameters(self):
        start_date = self.start_date_edit.date().toPyDate()
        end_date = self.end_date_edit.date().toPyDate()
        period = self.period_combo.currentText()
        return datetime.combine(start_date, datetime.min.time()), datetime.combine(end_date, datetime.max.time()), period

# Yeni: Gemiye Özel Faturalandırma Raporu Diyaloğu
class VesselBillingReportDialog(QDialog):
    def __init__(self, parent=None, db_manager=None):
        super().__init__(parent)
        self.setWindowTitle("Gemiye Özel Fatura Raporu Seçenekleri")
        self.setGeometry(300, 300, 450, 250)
        self.db = db_manager

        layout = QFormLayout()

        self.vessel_combo = QComboBox()
        self.vessel_combo.setEditable(True)
        self.vessel_combo.addItems([""] + sorted(self.db.get_unique_column_values('vessel_name')))
        layout.addRow("Gemi Adı:", self.vessel_combo)

        self.start_date_edit = QDateEdit(QDate.currentDate().addYears(-1))
        self.start_date_edit.setCalendarPopup(True)
        self.start_date_edit.setDisplayFormat("yyyy-MM-dd")
        layout.addRow("Başlangıç Tarihi:", self.start_date_edit)

        self.end_date_edit = QDateEdit(QDate.currentDate())
        self.end_date_edit.setCalendarPopup(True)
        self.end_date_edit.setDisplayFormat("yyyy-MM-dd")
        layout.addRow("Bitiş Tarihi:", self.end_date_edit)

        self.period_combo = QComboBox()
        self.period_combo.addItems(['monthly', 'weekly', 'daily', 'yearly'])
        self.period_combo.setCurrentText('monthly')
        layout.addRow("Periyot:", self.period_combo)

        button_box = QHBoxLayout()
        self.generate_button = QPushButton("Rapor Oluştur")
        self.generate_button.clicked.connect(self.accept)
        button_box.addWidget(self.generate_button)

        layout.addRow(button_box)
        self.setLayout(layout)

    def get_report_parameters(self):
        vessel_name = self.vessel_combo.currentText().strip()
        start_date = self.start_date_edit.date().toPyDate()
        end_date = self.end_date_edit.date().toPyDate()
        period = self.period_combo.currentText()
        return vessel_name, datetime.combine(start_date, datetime.min.time()), datetime.combine(end_date, datetime.max.time()), period

# Yeni: Kullanıcı Yönetimi Diyaloğu
class UserManagementDialog(QDialog):
    def __init__(self, parent=None, db_manager=None):
        super().__init__(parent)
        self.setWindowTitle("Kullanıcı Yönetimi")
        self.setGeometry(200, 200, 700, 500)
        self.db = db_manager

        main_layout = QVBoxLayout(self)

        # Kullanıcı Ekle/Güncelle Formu
        form_group = QGroupBox("Kullanıcı Ekle/Güncelle")
        form_layout = QFormLayout(form_group)

        self.user_id_input = QLineEdit()
        self.user_id_input.setReadOnly(True) # ID otomatik atanacak veya seçilince dolacak
        form_layout.addRow("Kullanıcı ID:", self.user_id_input)

        self.username_input = QLineEdit()
        form_layout.addRow("Kullanıcı Adı:", self.username_input)

        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.Password)
        form_layout.addRow("Şifre (Boş bırakılırsa değişmez):", self.password_input)

        self.role_combo = QComboBox()
        self.role_combo.addItems(["operator", "admin"])
        form_layout.addRow("Rol:", self.role_combo)

        button_hbox = QHBoxLayout()
        self.add_user_button = QPushButton("Kullanıcı Ekle")
        self.add_user_button.clicked.connect(self._add_user)
        button_hbox.addWidget(self.add_user_button)

        self.update_user_button = QPushButton("Kullanıcı Güncelle")
        self.update_user_button.clicked.connect(self._update_user)
        button_hbox.addWidget(self.update_user_button)

        self.delete_user_button = QPushButton("Kullanıcı Sil")
        self.delete_user_button.clicked.connect(self._delete_user)
        button_hbox.addWidget(self.delete_user_button)

        self.clear_form_button = QPushButton("Formu Temizle")
        self.clear_form_button.clicked.connect(self._clear_form)
        button_hbox.addWidget(self.clear_form_button)

        form_layout.addRow(button_hbox)
        main_layout.addWidget(form_group)

        # Kullanıcı Listesi Tablosu
        list_group = QGroupBox("Kullanıcı Listesi")
        list_layout = QVBoxLayout(list_group)

        self.user_table_view = QTableView()
        self.user_model = PandasModel()
        self.user_table_view.setModel(self.user_model)
        self.user_table_view.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.user_table_view.clicked.connect(self._load_selected_user_to_form)
        list_layout.addWidget(self.user_table_view)

        main_layout.addWidget(list_group)

        self._display_users()

    def _display_users(self):
        df_users = self.db.get_all_users()
        self.user_model.setDataFrame(df_users)
        if df_users.empty:
            QMessageBox.information(self, "Bilgi", "Sistemde kayıtlı kullanıcı bulunmamaktadır.")

    def _add_user(self):
        username = self.username_input.text().strip()
        password = self.password_input.text().strip()
        role = self.role_combo.currentText()

        if not username or not password:
            QMessageBox.warning(self, "Eksik Bilgi", "Kullanıcı adı ve şifre boş bırakılamaz.")
            return
        
        try:
            if self.db.add_user(username, password, role):
                QMessageBox.information(self, "Başarılı", f"'{username}' kullanıcısı başarıyla eklendi.")
                self.db.add_user_action_log("admin_user", "Add User", f"Added user: {username} with role {role}")
                self._display_users()
                self._clear_form()
            else:
                QMessageBox.warning(self, "Hata", f"'{username}' kullanıcısı eklenirken bir sorun oluştu.")
        except Exception as e:
            QMessageBox.critical(self, "Veritabanı Hatası", f"Kullanıcı eklenirken hata: {e}")
            self.db.add_user_action_log("admin_user", "Add User Failed", f"Failed to add user {username}: {e}")

    def _update_user(self):
        user_id = self.user_id_input.text().strip()
        username = self.username_input.text().strip()
        password = self.password_input.text().strip() # Boşsa değişmez
        role = self.role_combo.currentText()

        if not user_id:
            QMessageBox.warning(self, "Seçim Hatası", "Lütfen güncellemek için bir kullanıcı seçin.")
            return
        if not username:
            QMessageBox.warning(self, "Eksik Bilgi", "Kullanıcı adı boş bırakılamaz.")
            return

        try:
            if self.db.update_user(int(user_id), username, password if password else None, role):
                QMessageBox.information(self, "Başarılı", f"'{username}' kullanıcısı başarıyla güncellendi.")
                self.db.add_user_action_log("admin_user", "Update User", f"Updated user ID {user_id}: {username} with role {role}")
                self._display_users()
                self._clear_form()
            else:
                QMessageBox.warning(self, "Hata", f"'{username}' kullanıcısı güncellenirken bir sorun oluştu.")
        except Exception as e:
            QMessageBox.critical(self, "Veritabanı Hatası", f"Kullanıcı güncellenirken hata: {e}")
            self.db.add_user_action_log("admin_user", "Update User Failed", f"Failed to update user {username}: {e}")

    def _delete_user(self):
        user_id = self.user_id_input.text().strip()
        username = self.username_input.text().strip()

        if not user_id:
            QMessageBox.warning(self, "Seçim Hatası", "Lütfen silmek için bir kullanıcı seçin.")
            return
        
        reply = QMessageBox.question(self, 'Silme Onayı',
                                     f"'{username}' kullanıcısını silmek istediğinizden emin misiniz?",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)

        if reply == QMessageBox.Yes:
            try:
                if self.db.delete_user(int(user_id)):
                    QMessageBox.information(self, "Başarılı", f"'{username}' kullanıcısı başarıyla silindi.")
                    self.db.add_user_action_log("admin_user", "Delete User", f"Deleted user: {username} (ID: {user_id})")
                    self._display_users()
                    self._clear_form()
                else:
                    QMessageBox.warning(self, "Hata", f"'{username}' kullanıcısı silinirken bir sorun oluştu.")
            except Exception as e:
                QMessageBox.critical(self, "Veritabanı Hatası", f"Kullanıcı silinirken hata: {e}")
                self.db.add_user_action_log("admin_user", "Delete User Failed", f"Failed to delete user {username}: {e}")

    def _load_selected_user_to_form(self, index):
        row = index.row()
        df_users = self.user_model.getDataFrame()
        if df_users.empty or row >= len(df_users):
            return

        selected_user_data = df_users.iloc[row].to_dict()
        self.user_id_input.setText(str(selected_user_data.get('id', '')))
        self.username_input.setText(selected_user_data.get('username', ''))
        self.password_input.clear() # Şifre alanı temizlenir, manuel girilmelidir
        self.role_combo.setCurrentText(selected_user_data.get('role', 'operator'))

    def _clear_form(self):
        self.user_id_input.clear()
        self.username_input.clear()
        self.password_input.clear()
        self.role_combo.setCurrentIndex(0) # Varsayılan rolü seç


class KonteynerSorgulamaApp(QMainWindow):
    def __init__(self, db_manager, current_username, current_user_role, apply_theme_callback):
        super().__init__()
        self.db = db_manager
        self.reporter = ReportGenerator(self.db)
        self.current_username = current_username
        self.current_user_role = current_user_role
        self.apply_theme_callback = apply_theme_callback # Tema değiştirme callback'i

        self.setWindowTitle("Port Operasyonları Yönetim Sistemi")
        self.setGeometry(100, 100, 1200, 800)

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QVBoxLayout(self.central_widget)

        self.notebook = QTabWidget()
        self.main_layout.addWidget(self.notebook)

        self.statusBar = QStatusBar()
        self.setStatusBar(self.statusBar)

        self._setup_tabs()
        self.notebook.currentChanged.connect(self._on_tab_change)
        self._apply_role_permissions() # Rol bazlı izinleri uygula

        self._setup_settings_menu() # Tema seçimi için ayarlar menüsü

    def _setup_settings_menu(self):
        # Tema seçimi için bir QComboBox oluştur
        self.theme_selector = QComboBox()
        self.theme_selector.addItems(["Koyu Tema", "Açık Tema"])
        # Mevcut temayı varsayılan olarak ayarla
        # Bu kısım, main_pyqt.py'de varsayılan tema ayarlandığı için başlangıçta doğru olacaktır.
        # Eğer dinamik olarak temayı tespit etmek istersek daha karmaşık bir yapı gerekir.
        self.theme_selector.currentTextChanged.connect(self.apply_theme_callback)

        theme_layout = QHBoxLayout()
        theme_layout.addStretch(1) # Sağa hizala
        theme_layout.addWidget(QLabel("Tema Seçimi:"))
        theme_layout.addWidget(self.theme_selector)
        self.main_layout.insertLayout(0, theme_layout) # En üste ekle


    def _setup_tabs(self):
        # Konteyner Sorgula Sekmesi
        self.container_query_tab = QWidget()
        self.notebook.addTab(self.container_query_tab, "Konteyner Sorgula")
        self._setup_container_query_tab()

        # Faturalandırma Sekmesi
        self.billing_tab = QWidget()
        self.notebook.addTab(self.billing_tab, "Faturalandırma")
        self._setup_billing_tab()

        # Raporlar Sekmesi
        self.reports_tab = QWidget()
        self.notebook.addTab(self.reports_tab, "Raporlar")
        self._setup_reports_tab()

        # Kullanıcı Eylem Logları Sekmesi
        self.user_logs_tab = QWidget()
        self.notebook.addTab(self.user_logs_tab, "Kullanıcı Logları")
        self._setup_user_logs_tab()

        # Kullanıcı Yönetimi Sekmesi (Sadece Adminler için)
        if self.current_user_role == 'admin':
            self.user_management_tab = QWidget()
            self.notebook.addTab(self.user_management_tab, "Kullanıcı Yönetimi")
            self._setup_user_management_tab()
        else:
            self.user_management_tab = None # Admin değilse bu sekme oluşturulmaz


    def _apply_role_permissions(self):
        """Kullanıcı rolüne göre UI elementlerinin görünürlüğünü/etkinliğini ayarlar."""
        is_admin = (self.current_user_role == 'admin')

        # Sekme erişimleri - Artık _setup_tabs içinde koşullu olarak ekleniyor.
        # Bu kısım sadece butonların etkinliğini kontrol edecek.

        # Konteyner Sorgula Sekmesi butonları
        self.add_button.setEnabled(is_admin or self.current_user_role == 'operator')
        self.update_button.setEnabled(is_admin or self.current_user_role == 'operator')
        self.delete_button.setEnabled(is_admin) # Sadece admin silebilir
        self.import_button.setEnabled(is_admin) # Sadece admin içe aktarabilir

        # Tarife Yönetimi butonu (Faturalandırma sekmesinde)
        # Tarife yönetimi sadece adminler için olsun
        # findChild ile butonu bulup etkinliğini ayarla
        tariff_button = self.findChild(QPushButton, "tariff_management_button")
        if tariff_button:
            tariff_button.setEnabled(is_admin)


    def _setup_container_query_tab(self):
        layout = QVBoxLayout(self.container_query_tab)

        # Arama ve İşlem Alanı
        query_group = QGroupBox("Konteyner Sorgula ve Yönet")
        query_layout = QVBoxLayout(query_group)

        # Gelişmiş Arama Kısmı
        search_grid = QGridLayout()
        
        search_grid.addWidget(QLabel("Konteyner Numarası:"), 0, 0)
        self.container_id_input = QLineEdit()
        self.container_id_input.setPlaceholderText("Konteyner Numarası Girin (örn: ABCD1234567)")
        self.container_id_input.returnPressed.connect(self._query_container_by_criteria)
        search_grid.addWidget(self.container_id_input, 0, 1)

        search_grid.addWidget(QLabel("Gemi Adı:"), 0, 2)
        self.vessel_name_filter = QComboBox()
        self.vessel_name_filter.setEditable(True)
        self.vessel_name_filter.addItems([""] + sorted(self.db.get_unique_column_values('vessel_name')))
        search_grid.addWidget(self.vessel_name_filter, 0, 3)

        search_grid.addWidget(QLabel("Durum:"), 1, 0)
        self.status_filter = QComboBox()
        self.status_filter.setEditable(True)
        self.status_filter.addItems([""] + sorted(self.db.get_unique_column_values('container_status')))
        search_grid.addWidget(self.status_filter, 1, 1)

        search_grid.addWidget(QLabel("Lokasyon:"), 1, 2)
        self.location_filter = QComboBox()
        self.location_filter.setEditable(True)
        self.location_filter.addItems([""] + sorted(self.db.get_unique_column_values('location_area')))
        search_grid.addWidget(self.location_filter, 1, 3)

        search_grid.addWidget(QLabel("Başlangıç Tarihi:"), 2, 0)
        self.start_date_filter = QDateEdit(calendarPopup=True)
        self.start_date_filter.setDisplayFormat("yyyy-MM-dd")
        self.start_date_filter.setDate(QDate(2000, 1, 1)) # Çok eski bir tarih veya boş başlangıç
        search_grid.addWidget(self.start_date_filter, 2, 1)

        search_grid.addWidget(QLabel("Bitiş Tarihi:"), 2, 2)
        self.end_date_filter = QDateEdit(calendarPopup=True)
        self.end_date_filter.setDisplayFormat("yyyy-MM-dd")
        self.end_date_filter.setDate(QDate.currentDate().addYears(1)) # Gelecek bir tarih veya boş bitiş
        search_grid.addWidget(self.end_date_filter, 2, 3)


        search_button = QPushButton("Filtrele/Sorgula")
        search_button.clicked.connect(self._query_container_by_criteria)
        search_grid.addWidget(search_button, 3, 0, 1, 2) # 2 satır, 0 sütun, 1 satır yayılma, 2 sütun yayılma

        all_operations_button = QPushButton("Tüm Operasyonları Göster")
        all_operations_button.clicked.connect(self._show_all_operations)
        search_grid.addWidget(all_operations_button, 3, 2, 1, 2)

        query_layout.addLayout(search_grid)

        # CRUD ve Diğer Butonlar
        crud_hbox = QHBoxLayout()
        self.add_button = QPushButton("Operasyon Ekle")
        self.add_button.clicked.connect(self._add_operation)
        crud_hbox.addWidget(self.add_button)

        self.update_button = QPushButton("Operasyon Güncelle")
        self.update_button.clicked.connect(self._update_operation)
        crud_hbox.addWidget(self.update_button)

        self.delete_button = QPushButton("Operasyon Sil")
        self.delete_button.clicked.connect(self._delete_operation)
        crud_hbox.addWidget(self.delete_button)
        
        self.view_logs_button = QPushButton("Konteyner Logları")
        self.view_logs_button.clicked.connect(self._view_selected_operation_logs)
        crud_hbox.addWidget(self.view_logs_button)

        self.export_button = QPushButton("CSV'ye Aktar")
        self.export_button.clicked.connect(self._export_current_table_to_csv)
        crud_hbox.addWidget(self.export_button)

        self.import_button = QPushButton("CSV'den İçe Aktar")
        self.import_button.clicked.connect(self._import_data_from_csv)
        crud_hbox.addWidget(self.import_button)


        query_layout.addLayout(crud_hbox)
        layout.addWidget(query_group)

        # Sonuç Tablosu
        self.query_results_table_view = QTableView()
        self.query_results_model = PandasModel()
        self.query_results_table_view.setModel(self.query_results_model)
        self.query_results_table_view.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.query_results_table_view)

    def _query_container_by_criteria(self):
        container_id = self.container_id_input.text().strip().upper()
        vessel_name = self.vessel_name_filter.currentText().strip()
        container_status = self.status_filter.currentText().strip()
        location_area = self.location_filter.currentText().strip()
        start_date = self.start_date_filter.date().toPyDate()
        end_date = self.end_date_filter.date().toPyDate()

        search_criteria = {}
        if container_id:
            search_criteria['container_id'] = container_id
        if vessel_name:
            search_criteria['vessel_name'] = vessel_name
        if container_status:
            search_criteria['container_status'] = container_status
        if location_area:
            search_criteria['location_area'] = location_area
        
        # Tarih filtrelerini datetime objelerine dönüştür
        # Eğer QDateEdit'ten varsayılan (çok eski/gelecek) tarih geliyorsa, bunu None olarak kabul et
        default_start_date = QDate(2000, 1, 1).toPyDate()
        default_end_date = QDate.currentDate().addYears(1).toPyDate()

        if start_date != default_start_date:
            search_criteria['start_date'] = datetime.combine(start_date, datetime.min.time())
        if end_date != default_end_date:
            search_criteria['end_date'] = datetime.combine(end_date, datetime.max.time())


        if not search_criteria:
            QMessageBox.warning(self, "Uyarı", "Lütfen arama için en az bir kriter girin veya tarih aralığını ayarlayın.")
            self.query_results_model.setDataFrame(pd.DataFrame())
            return

        try:
            df = self.db.search_port_operations(search_criteria) 
            if df.empty:
                QMessageBox.information(self, "Sonuç Yok", "Belirtilen kriterlere uygun operasyon kaydı bulunamadı.")
            self.query_results_model.setDataFrame(df)
            self.statusBar.showMessage(f"{len(df)} kayıt bulundu.", 3000) # 3 saniye göster
        except Exception as e:
            QMessageBox.critical(self, "Sorgu Hatası", f"Konteyner sorgulanırken bir hata oluştu: {e}")
            self.statusBar.showMessage("Sorgu hatası!", 3000)


    def _show_all_operations(self):
        try:
            df = self.db.get_all_port_operations_data()
            if df.empty:
                QMessageBox.information(self, "Veri Yok", "Sistemde hiç operasyon kaydı bulunamadı.")
            self.query_results_model.setDataFrame(df)
            self.container_id_input.clear() # Inputu temizle
            self.vessel_name_filter.setCurrentIndex(0) # Filtreleri temizle
            self.status_filter.setCurrentIndex(0)
            self.location_filter.setCurrentIndex(0)
            self.start_date_filter.setDate(QDate(2000, 1, 1)) # Tarih filtrelerini temizle
            self.end_date_filter.setDate(QDate.currentDate().addYears(1))
            self.statusBar.showMessage(f"Tüm {len(df)} kayıt gösteriliyor.", 3000)
        except Exception as e:
            QMessageBox.critical(self, "Veritabanı Hatası", f"Tüm operasyonlar çekilirken bir hata oluştu: {e}")
            self.statusBar.showMessage("Veritabanı hatası!", 3000)

    def _add_operation(self):
        dialog = OperationFormDialog(self, self.db)
        if dialog.exec_() == QDialog.Accepted:
            new_data = dialog.get_data()
            if dialog.validate_data(new_data):
                try:
                    # timestamp'i burada otomatik olarak ayarla
                    new_data['timestamp'] = datetime.now()
                    self.db.add_port_operation(new_data)
                    QMessageBox.information(self, "Başarılı", "Operasyon kaydı başarıyla eklendi.")
                    self.db.add_user_action_log(self.current_username, "Add Operation", f"Added container {new_data.get('container_id')}")
                    self._show_all_operations() # Tabloyu yenile
                    self.statusBar.showMessage(f"Operasyon '{new_data.get('container_id')}' eklendi.", 3000)
                except Exception as e:
                    if "duplicate key" in str(e):
                        QMessageBox.critical(self, "Veritabanı Hatası",
                                             f"Bu Konteyner Numarası ({new_data.get('container_id')}) zaten mevcut. "
                                             "Lütfen güncelleme işlevini kullanın veya farklı bir numara girin.")
                    else:
                        QMessageBox.critical(self, "Veritabanı Hatası", f"Operasyon eklenirken bir hata oluştu: {e}")
                    self.db.add_user_action_log(self.current_username, "Add Operation Failed", f"Failed to add container {new_data.get('container_id')}: {e}")
                    self.statusBar.showMessage("Operasyon eklenemedi!", 3000)

            else:
                self.statusBar.showMessage("Veri doğrulama hatası!", 3000) # Validate_data içinde zaten QMessageBox gösteriliyor

    def _update_operation(self):
        selected_indexes = self.query_results_table_view.selectedIndexes()
        if not selected_indexes:
            QMessageBox.warning(self, "Seçim Hatası", "Lütfen güncellemek için bir operasyon kaydı seçin.")
            return

        row = selected_indexes[0].row()
        df = self.query_results_model.getDataFrame()
        
        if df.empty or row >= len(df):
            QMessageBox.warning(self, "Hata", "Geçerli bir satır seçilemedi. Lütfen tabloyu yenileyin.")
            return

        current_data = df.iloc[row].to_dict()
        container_id_to_update = current_data.get('container_id')

        if not container_id_to_update:
            QMessageBox.critical(self, "Hata", "Seçilen kaydın Konteyner Numarası bulunamadı.")
            return

        dialog = OperationFormDialog(self, self.db, data=current_data)
        if dialog.exec_() == QDialog.Accepted:
            updated_data = dialog.get_data()
            if dialog.validate_data(updated_data):
                try:
                    # timestamp'i burada otomatik olarak güncelleyebiliriz
                    updated_data['timestamp'] = datetime.now()
                    self.db.update_port_operation(container_id_to_update, updated_data)
                    QMessageBox.information(self, "Başarılı", f"Konteyner '{container_id_to_update}' operasyonu başarıyla güncellendi.")
                    self.db.add_user_action_log(self.current_username, "Update Operation", f"Updated container {container_id_to_update}")
                    self._show_all_operations()
                    self.statusBar.showMessage(f"Operasyon '{container_id_to_update}' güncellendi.", 3000)
                except Exception as e:
                    QMessageBox.critical(self, "Veritabanı Hatası", f"Operasyon güncellenirken bir hata oluştu: {e}")
                    self.db.add_user_action_log(self.current_username, "Update Operation Failed", f"Failed to update container {container_id_to_update}: {e}")
                    self.statusBar.showMessage("Operasyon güncellenemedi!", 3000)
            else:
                self.statusBar.showMessage("Veri doğrulama hatası!", 3000)

    def _delete_operation(self):
        selected_indexes = self.query_results_table_view.selectedIndexes()
        if not selected_indexes:
            QMessageBox.warning(self, "Seçim Hatası", "Lütfen silmek için bir operasyon kaydı seçin.")
            return

        row = selected_indexes[0].row()
        df = self.query_results_model.getDataFrame()

        if df.empty or row >= len(df):
            QMessageBox.warning(self, "Hata", "Geçerli bir satır seçilemedi. Lütfen tabloyu yenileyin.")
            return
            
        container_id_to_delete = df.iloc[row]['container_id']

        reply = QMessageBox.question(self, 'Silme Onayı',
                                     f"'{container_id_to_delete}' numaralı konteyner operasyon kaydını silmek istediğinizden emin misiniz?",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)

        if reply == QMessageBox.Yes:
            try:
                self.db.delete_port_operation(container_id_to_delete)
                QMessageBox.information(self, "Başarılı", f"Konteyner '{container_id_to_delete}' operasyon kaydı başarıyla silindi.")
                self.db.add_user_action_log(self.current_username, "Delete Operation", f"Deleted container {container_id_to_delete}")
                self._show_all_operations()
                self.statusBar.showMessage(f"Operasyon '{container_id_to_delete}' silindi.", 3000)
            except Exception as e:
                QMessageBox.critical(self, "Veritabanı Hatası", f"Operasyon silinirken bir hata oluştu: {e}")
                self.db.add_user_action_log(self.current_username, "Delete Operation Failed", f"Failed to delete container {container_id_to_delete}: {e}")
                self.statusBar.showMessage("Operasyon silinemedi!", 3000)

    def _view_selected_operation_logs(self):
        selected_indexes = self.query_results_table_view.selectedIndexes()
        if not selected_indexes:
            QMessageBox.warning(self, "Seçim Hatası", "Lütfen loglarını görmek için bir operasyon kaydı seçin.")
            return

        row = selected_indexes[0].row()
        df = self.query_results_model.getDataFrame()

        if df.empty or row >= len(df):
            QMessageBox.warning(self, "Hata", "Geçerli bir satır seçilemedi. Lütfen tabloyu yenileyin.")
            return
            
        container_id_to_view_logs = df.iloc[row]['container_id']

        logs_df = self.db.get_container_logs(container_id_to_view_logs)

        log_dialog = QDialog(self)
        log_dialog.setWindowTitle(f"Konteyner {container_id_to_view_logs} Logları")
        log_dialog.setGeometry(200, 200, 900, 500)
        log_layout = QVBoxLayout(log_dialog)

        log_table_view = QTableView()
        log_model = PandasModel(logs_df)
        log_table_view.setModel(log_model)
        log_table_view.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        log_layout.addWidget(log_table_view)

        if logs_df.empty:
            log_layout.addWidget(QLabel("Bu konteyner için log kaydı bulunmamaktadır.").setAlignment(Qt.AlignCenter))

        log_dialog.exec_()
        self.statusBar.showMessage(f"Konteyner {container_id_to_view_logs} logları görüntülendi.", 3000)


    def _export_current_table_to_csv(self):
        df = self.query_results_model.getDataFrame()
        if df.empty:
            QMessageBox.warning(self, "Uyarı", "Dışa aktarılacak veri bulunmamaktadır.")
            return

        file_name, _ = QFileDialog.getSaveFileName(self, "CSV Olarak Kaydet", "konteyner_operasyonlari.csv", "CSV Dosyaları (*.csv);;Tüm Dosyalar (*)")
        if file_name:
            try:
                # Sadece mevcut tabloda gösterilen veriyi dışa aktar
                df_to_export = self.query_results_model.getDataFrame()
                df_to_export.to_csv(file_name, index=False, encoding='utf-8-sig')
                QMessageBox.information(self, "Başarılı", f"Veriler '{file_name}' dosyasına başarıyla aktarıldı.")
                self.db.add_user_action_log(self.current_username, "Export Data", f"Exported current table data to {file_name}")
                self.statusBar.showMessage(f"Veriler '{file_name}' dosyasına aktarıldı.", 3000)
            except Exception as e:
                QMessageBox.critical(self, "Hata", f"Veriler dışa aktarılırken bir hata oluştu: {e}")
                self.db.add_user_action_log(self.current_username, "Export Data Failed", f"Failed to export current table data: {e}")
                self.statusBar.showMessage("Veri dışa aktarılamadı!", 3000)

    def _import_data_from_csv(self):
        file_name, _ = QFileDialog.getOpenFileName(self, "CSV Dosyası Seç", "", "CSV Dosyaları (*.csv);;Tüm Dosyalar (*)")
        if file_name:
            reply = QMessageBox.question(self, "İçe Aktarma Onayı", 
                                         "Mevcut verilerle çakışan konteynerler güncellenecektir. Devam etmek istiyor musunuz?",
                                         QMessageBox.Yes | QMessageBox.No)
            if reply == QMessageBox.No:
                return

            try:
                # 'port_operations' tablosuna aktarılacak
                success, message = self.db.import_data_from_csv('port_operations', file_name)
                if success:
                    QMessageBox.information(self, "Başarılı", f"Veriler başarıyla içe aktarıldı.\n{message}")
                    self.db.add_user_action_log(self.current_username, "Import Data", f"Imported port_operations data from {file_name}. {message}")
                    self._show_all_operations() # Tabloyu yenile
                    self.statusBar.showMessage(f"Veriler '{file_name}' dosyasından içe aktarıldı. {message}", 3000)
                else:
                    QMessageBox.critical(self, "Hata", f"Veriler içe aktarılırken bir hata oluştu: {message}")
                    self.db.add_user_action_log(self.current_username, "Import Data Failed", f"Failed to import port_operations data from {file_name}: {message}")
                    self.statusBar.showMessage("Veri içe aktarılamadı!", 3000)
            except Exception as e:
                QMessageBox.critical(self, "Hata", f"Veriler içe aktarılırken bir hata oluştu: {e}")
                self.db.add_user_action_log(self.current_username, "Import Data Failed", f"Failed to import port_operations data: {e}")
                self.statusBar.showMessage("Veri içe aktarılamadı!", 3000)


    def _setup_billing_tab(self):
        layout = QVBoxLayout(self.billing_tab)

        billing_group = QGroupBox("Fatura Hesaplama")
        billing_layout = QGridLayout(billing_group)

        billing_layout.addWidget(QLabel("Konteyner Numarası:"), 0, 0)
        self.billing_container_id_input = QLineEdit()
        self.billing_container_id_input.setPlaceholderText("Konteyner Numarası Girin")
        billing_layout.addWidget(self.billing_container_id_input, 0, 1)

        calculate_button = QPushButton("Fatura Hesapla")
        calculate_button.clicked.connect(self._calculate_billing)
        billing_layout.addWidget(calculate_button, 0, 2)

        tariff_button = QPushButton("Tarife Yönetimi")
        tariff_button.setObjectName("tariff_management_button") # Rol bazlı erişim için isim verildi
        tariff_button.clicked.connect(self._open_tariff_management_dialog)
        billing_layout.addWidget(tariff_button, 0, 3)

        layout.addWidget(billing_group)

        self.billing_result_label = QLabel("Fatura Detayları Burada Gösterilecektir.")
        self.billing_result_label.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.billing_result_label.setWordWrap(True)
        layout.addWidget(self.billing_result_label)
        layout.addStretch(1)

    def _calculate_billing(self):
        container_id = self.billing_container_id_input.text().strip().upper()
        if not container_id:
            QMessageBox.warning(self, "Uyarı", "Lütfen faturalandırmak için bir konteyner numarası girin.")
            self.billing_result_label.setText("Fatura Detayları Burada Gösterilecektir.")
            self.statusBar.showMessage("Konteyner numarası girin!", 3000)
            return

        container_data_df = self.db.get_port_operation_by_container_id(container_id)
        if container_data_df.empty:
            self.billing_result_label.setText(f"'{container_id}' numaralı konteyner bulunamadı.")
            self.statusBar.showMessage(f"Konteyner '{container_id}' bulunamadı.", 3000)
            return

        container_data = container_data_df.iloc[0].to_dict() # İlk satırı al
        
        # Fatura hesaplama mantığını ReportGenerator'dan çağır
        total_cost = self.reporter._calculate_single_container_billing(container_data)

        vessel_name = container_data.get('vessel_name')
        arrival_date = container_data.get('arrival_date')
        departure_date = container_data.get('departure_date')
        
        billing_text = f"Konteyner No: {container_id}\n"
        billing_text += f"Gemi Adı: {vessel_name if vessel_name else 'Bilinmiyor'}\n"
        billing_text += f"Varış Limanı: {container_data.get('arrival_port', 'Bilinmiyor')}\n"
        billing_text += f"Kalkış Limanı: {container_data.get('departure_port', 'Bilinmiyor')}\n"
        billing_text += f"Mevcut Durum: {container_data.get('container_status', 'Bilinmiyor')}\n"
        billing_text += f"Mevcut Lokasyon: {container_data.get('location_area', 'Bilinmiyor')}\n"

        stay_duration_days = 0
        if isinstance(arrival_date, datetime) and isinstance(departure_date, datetime) and departure_date >= arrival_date:
            stay_duration = departure_date - arrival_date
            stay_duration_days = stay_duration.days
            if stay_duration_days == 0 and stay_duration.total_seconds() > 0:
                stay_duration_days = 1
            elif stay_duration_days == 0 and stay_duration.total_seconds() == 0:
                stay_duration_days = 0

        if arrival_date:
            billing_text += f"Limana Giriş Tarihi: {arrival_date.strftime('%Y-%m-%d %H:%M:%S')}\n"
        else:
            billing_text += "Limana Giriş Tarihi: Bilinmiyor\n"

        if departure_date:
            billing_text += f"Limandan Çıkış Tarihi: {departure_date.strftime('%Y-%m-%d %H:%M:%S')}\n"
        else:
            billing_text += "Limandan Çıkış Tarihi: Bilinmiyor\n"

        billing_text += f"Kalış Süresi: {stay_duration_days} gün\n"
        
        daily_rate = self.db.get_vessel_tariff(vessel_name)
        if daily_rate is not None:
            billing_text += f"Günlük Tarife: {float(daily_rate):.2f} $\n"
            billing_text += f"Toplam Fatura: {total_cost:.2f} $"
        else:
            billing_text += "\n***Uyarı: Bu gemi için tarife bilgisi bulunamadı. Lütfen 'Tarife Yönetimi' ekranından tarife ekleyin.***"
        
        self.billing_result_label.setText(billing_text)
        self.statusBar.showMessage(f"Fatura hesaplandı: {total_cost:.2f} $", 3000)


    def _open_tariff_management_dialog(self):
        tariff_dialog = QDialog(self)
        tariff_dialog.setWindowTitle("Tarife Yönetimi")
        tariff_dialog.setGeometry(200, 200, 600, 400)
        tariff_layout = QVBoxLayout(tariff_dialog)

        # Tarife Giriş Alanı
        input_group = QGroupBox("Tarife Ekle/Güncelle")
        input_layout = QFormLayout(input_group)

        # Gemi Adı için QComboBox kullan
        self.vessel_name_tariff_input = QComboBox()
        self.vessel_name_tariff_input.setEditable(True) # Kullanıcının yeni gemi adı girmesine izin ver
        # Mevcut gemi adlarını veritabanından çek ve ComboBox'a ekle
        self.vessel_name_tariff_input.addItems([""] + sorted(self.db.get_unique_column_values('vessel_name')))
        input_layout.addRow("Gemi Adı:", self.vessel_name_tariff_input)

        self.daily_rate_input = QDoubleSpinBox() # self. olarak tanımlandı
        self.daily_rate_input.setRange(0.0, 100000.0)
        self.daily_rate_input.setDecimals(2)
        input_layout.addRow("Günlük Tarife ($):", self.daily_rate_input)

        save_tariff_button = QPushButton("Kaydet")
        def save_tariff():
            vessel_name = self.vessel_name_tariff_input.currentText().strip() # ComboBox'tan değeri al
            daily_rate = self.daily_rate_input.value() # self. ile erişim

            if not vessel_name:
                QMessageBox.warning(tariff_dialog, "Giriş Hatası", "Gemi Adı boş bırakılamaz.")
                return
            if daily_rate <= 0:
                QMessageBox.warning(tariff_dialog, "Giriş Hatası", "Günlük tarife pozitif bir sayı olmalıdır.")
                return
            
            try:
                if self.db.add_or_update_vessel_tariff(vessel_name, daily_rate):
                    QMessageBox.information(tariff_dialog, "Başarılı", f"'{vessel_name}' gemisi için tarife başarıyla kaydedildi.")
                    _display_tariffs() # Tabloyu yenile
                    self.vessel_name_tariff_input.setCurrentIndex(0) # ComboBox'ı temizle
                    # Yeniden yüklemeden önce mevcut öğeleri temizle
                    self.vessel_name_tariff_input.clear() 
                    self.vessel_name_tariff_input.addItems([""] + sorted(self.db.get_unique_column_values('vessel_name'))) # Yeni eklenen gemiyi listeye ekle
                    self.daily_rate_input.clear() # self. ile erişim
                    self.db.add_user_action_log(self.current_username, "Update Tariff", f"Updated tariff for {vessel_name} to {daily_rate}")
                    self.statusBar.showMessage(f"Tarife '{vessel_name}' kaydedildi.", 3000)
                else:
                    QMessageBox.critical(tariff_dialog, "Hata", "Tarife kaydedilirken bir hata oluştu.")
                    self.db.add_user_action_log(self.current_username, "Update Tariff Failed", f"Failed to update tariff for {vessel_name}")
                    self.statusBar.showMessage("Tarife kaydedilemedi!", 3000)
            except Exception as e:
                QMessageBox.critical(tariff_dialog, "Veritabanı Hatası", f"Tarife kaydedilirken bir hata oluştu: {e}")
                self.db.add_user_action_log(self.current_username, "Update Tariff Failed", f"Failed to update tariff for {vessel_name}: {e}")
                self.statusBar.showMessage("Tarife kaydedilemedi!", 3000)

        save_tariff_button.clicked.connect(save_tariff)
        input_layout.addWidget(save_tariff_button)

        # Yeni: Güncelle butonu
        update_selected_tariff_button = QPushButton("Seçili Tarifeyi Güncelle")
        def update_selected_tariff():
            selected_indexes = self.tariff_table_view.selectedIndexes()
            if not selected_indexes:
                QMessageBox.warning(tariff_dialog, "Seçim Hatası", "Lütfen güncellemek için bir tarife seçin.")
                return

            row = selected_indexes[0].row()
            df_tariffs = self.tariff_model.getDataFrame()
            
            if df_tariffs.empty or row >= len(df_tariffs):
                QMessageBox.warning(tariff_dialog, "Hata", "Geçerli bir satır seçilemedi. Lütfen tabloyu yenileyin.")
                return

            selected_vessel_name = df_tariffs.iloc[row]['vessel_name']
            selected_daily_rate = df_tariffs.iloc[row]['daily_rate']

            # Seçilen verileri giriş alanlarına yükle
            self.vessel_name_tariff_input.setCurrentText(str(selected_vessel_name))
            self.daily_rate_input.setValue(float(selected_daily_rate))

            QMessageBox.information(tariff_dialog, "Bilgi", f"'{selected_vessel_name}' gemisinin tarifesi düzenleme alanına yüklendi. Değişiklikleri yapıp 'Kaydet' butonuna tıklayın.")
            self.statusBar.showMessage(f"Tarife '{selected_vessel_name}' düzenleme için yüklendi.", 3000)

        update_selected_tariff_button.clicked.connect(update_selected_tariff)
        input_layout.addWidget(update_selected_tariff_button)


        tariff_layout.addWidget(input_group)

        # Tarife Listesi Tablosu
        tariff_table_group = QGroupBox("Mevcut Tarifeler")
        tariff_table_layout = QVBoxLayout(tariff_table_group)
        self.tariff_table_view = QTableView() # self. ile tanımlandığı için dışarıdan erişilebilir
        self.tariff_model = PandasModel()
        self.tariff_table_view.setModel(self.tariff_model)
        # Hata alınan satır düzeltildi:
        self.tariff_table_view.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        tariff_table_layout.addWidget(self.tariff_table_view)
        tariff_layout.addWidget(tariff_table_group)

        def _display_tariffs():
            df_tariffs = self.db.get_all_vessel_tariffs()
            self.tariff_model.setDataFrame(df_tariffs)

        _display_tariffs() # Pencere açıldığında tarifeleri göster
        tariff_dialog.exec_()


    def _setup_reports_tab(self):
        layout = QVBoxLayout(self.reports_tab)
        reports_group = QGroupBox("Raporlar")
        reports_layout = QVBoxLayout(reports_group)

        btn_status_distribution = QPushButton("Konteyner Durum Dağılımı")
        btn_status_distribution.clicked.connect(self.reporter.generate_status_distribution)
        reports_layout.addWidget(btn_status_distribution)

        btn_location_distribution = QPushButton("Konteyner Lokasyon Dağılımı")
        btn_location_distribution.clicked.connect(self.reporter.generate_location_distribution)
        reports_layout.addWidget(btn_location_distribution)

        btn_monthly_operations = QPushButton("Aylık İşlem Sayısı")
        btn_monthly_operations.clicked.connect(self.reporter.generate_monthly_operations)
        reports_layout.addWidget(btn_monthly_operations)

        btn_annual_operations = QPushButton("Yıllık İşlem Sayısı")
        btn_annual_operations.clicked.connect(self.reporter.generate_annual_operations)
        reports_layout.addWidget(btn_annual_operations)

        btn_top_ports = QPushButton("En Yoğun Limanlar")
        btn_top_ports.clicked.connect(self.reporter.generate_top_ports)
        reports_layout.addWidget(btn_top_ports)

        # Genel Faturalandırma Raporları
        general_billing_report_group = QGroupBox("Genel Faturalandırma Raporları")
        general_billing_report_layout = QVBoxLayout(general_billing_report_group)

        btn_billing_annual_all_data = QPushButton("Tüm Veri - Yıllık Fatura Raporu")
        btn_billing_annual_all_data.clicked.connect(lambda: self.reporter.generate_billing_report(None, None, 'yearly'))
        general_billing_report_layout.addWidget(btn_billing_annual_all_data)

        btn_billing_monthly_all_data = QPushButton("Tüm Veri - Aylık Fatura Raporu")
        btn_billing_monthly_all_data.clicked.connect(lambda: self.reporter.generate_billing_report(None, None, 'monthly'))
        general_billing_report_layout.addWidget(btn_billing_monthly_all_data)

        btn_billing_weekly_all_data = QPushButton("Tüm Veri - Haftalık Fatura Raporu")
        btn_billing_weekly_all_data.clicked.connect(lambda: self.reporter.generate_billing_report(None, None, 'weekly'))
        general_billing_report_layout.addWidget(btn_billing_weekly_all_data)

        btn_billing_daily_all_data = QPushButton("Tüm Veri - Günlük Fatura Raporu")
        btn_billing_daily_all_data.clicked.connect(lambda: self.reporter.generate_billing_report(None, None, 'daily'))
        general_billing_report_layout.addWidget(btn_billing_daily_all_data)

        btn_billing_custom_range = QPushButton("Özel Tarih Aralığı Fatura Raporu")
        btn_billing_custom_range.clicked.connect(self._open_billing_report_dialog)
        general_billing_report_layout.addWidget(btn_billing_custom_range)

        reports_layout.addWidget(general_billing_report_group)


        # Yeni: Gemiye Özel Faturalandırma Raporları
        vessel_billing_report_group = QGroupBox("Gemiye Göre Faturalandırma Raporları")
        vessel_billing_report_layout = QVBoxLayout(vessel_billing_report_group)

        btn_vessel_billing_report = QPushButton("Gemiye Özel Fatura Raporu Oluştur")
        btn_vessel_billing_report.clicked.connect(self._open_vessel_billing_report_dialog)
        vessel_billing_report_layout.addWidget(btn_vessel_billing_report)

        reports_layout.addWidget(vessel_billing_report_group)


        layout.addWidget(reports_group)
        layout.addStretch(1) # Boş alanı doldurmak için

    def _open_billing_report_dialog(self):
        """Genel faturalandırma raporu için tarih aralığı ve periyot seçimi diyalogunu açar."""
        dialog = BillingReportDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            start_date, end_date, period = dialog.get_report_parameters()
            try:
                self.reporter.generate_billing_report(start_date, end_date, period)
                self.db.add_user_action_log(self.current_username, "Generate Custom Range Billing Report", f"Generated custom billing report for {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')} ({period})")
                self.statusBar.showMessage(f"Özel aralık fatura raporu oluşturuldu.", 3000)
            except Exception as e:
                QMessageBox.critical(self, "Rapor Hatası", f"Faturalandırma raporu oluşturulurken bir hata oluştu: {e}")
                self.db.add_user_action_log(self.current_username, "Generate Custom Range Billing Report Failed", f"Failed to generate custom billing report: {e}")
                self.statusBar.showMessage("Rapor oluşturulamadı!", 3000)

    def _open_vessel_billing_report_dialog(self):
        """Gemiye özel faturalandırma raporu için gemi, tarih aralığı ve periyot seçimi diyalogunu açar."""
        dialog = VesselBillingReportDialog(self, self.db)
        if dialog.exec_() == QDialog.Accepted:
            vessel_name, start_date, end_date, period = dialog.get_report_parameters()
            if not vessel_name:
                QMessageBox.warning(self, "Uyarı", "Lütfen rapor oluşturmak için bir gemi adı seçin veya girin.")
                return
            try:
                self.reporter.generate_vessel_specific_billing_report(vessel_name, start_date, end_date, period)
                self.db.add_user_action_log(self.current_username, "Generate Vessel Billing Report", f"Generated vessel billing report for {vessel_name} from {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')} ({period})")
                self.statusBar.showMessage(f"Gemiye özel fatura raporu oluşturuldu: {vessel_name}", 3000)
            except Exception as e:
                QMessageBox.critical(self, "Rapor Hatası", f"Gemiye özel faturalandırma raporu oluşturulurken bir hata oluştu: {e}")
                self.db.add_user_action_log(self.current_username, "Generate Vessel Billing Report Failed", f"Failed to generate vessel billing report for {vessel_name}: {e}")
                self.statusBar.showMessage("Gemiye özel rapor oluşturulamadı!", 3000)


    def _setup_user_logs_tab(self):
        layout = QVBoxLayout(self.user_logs_tab)
        user_logs_group = QGroupBox("Kullanıcı Eylem Logları")
        user_logs_layout = QVBoxLayout(user_logs_group)

        self.user_logs_table_view = QTableView()
        self.user_logs_model = PandasModel()
        self.user_logs_table_view.setModel(self.user_logs_model)
        self.user_logs_table_view.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        user_logs_layout.addWidget(self.user_logs_table_view)

        refresh_button = QPushButton("Logları Yenile")
        refresh_button.clicked.connect(self._display_user_action_logs)
        user_logs_layout.addWidget(refresh_button)

        layout.addWidget(user_logs_group)
        layout.addStretch(1)

    def _display_user_action_logs(self):
        logs_df = self.db.get_all_user_action_logs()
        if 'action_time' in logs_df.columns:
            logs_df['action_time'] = pd.to_datetime(logs_df['action_time'], errors='coerce').dt.strftime('%Y-%m-%d %H:%M:%S').fillna('')
        self.user_logs_model.setDataFrame(logs_df)
        if logs_df.empty:
            QMessageBox.information(self, "Bilgi", "Henüz kullanıcı eylem logu bulunmamaktadır.")
        self.statusBar.showMessage(f"Kullanıcı logları yüklendi. Toplam {len(logs_df)} kayıt.", 3000)

    def _setup_user_management_tab(self):
        """Kullanıcı yönetimi sekmesini ayarlar."""
        layout = QVBoxLayout(self.user_management_tab)
        self.user_management_dialog_instance = UserManagementDialog(self, self.db)
        layout.addWidget(self.user_management_dialog_instance)


    def _on_tab_change(self, index):
        tab_name = self.notebook.tabText(index)
        if tab_name == 'Konteyner Sorgula':
            self.query_results_model.setDataFrame(pd.DataFrame()) # Tabloyu boşalt
            self.container_id_input.clear() # Arama inputunu temizle
            self.vessel_name_filter.setCurrentIndex(0) # Filtreleri temizle
            self.status_filter.setCurrentIndex(0)
            self.location_filter.setCurrentIndex(0)
            self.start_date_filter.setDate(QDate(2000, 1, 1)) # Tarih filtrelerini temizle
            self.end_date_filter.setDate(QDate.currentDate().addYears(1))
        elif tab_name == 'Kullanıcı Logları':
            self._display_user_action_logs() # Kullanıcı logları sekmesine geçildiğinde logları yükle
        elif tab_name == 'Kullanıcı Yönetimi':
            # Kullanıcı Yönetimi sekmesine geçildiğinde kullanıcı listesini yenile
            # Bu sekme artık sadece adminler için oluşturulduğu için ekstra yetki kontrolüne gerek yok.
            if self.user_management_tab: # Sekme var mı kontrolü
                self.user_management_dialog_instance._display_users()

