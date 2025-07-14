# Port Container Management System

**Modern liman konteyner yönetim sistemi**

## Özellikler

- ✅ **Güvenli Giriş Sistemi** - Kullanıcı kimlik doğrulama
- ✅ **Konteyner Takip** - Konteyner durumu ve lokasyon
- ✅ **Liman Operasyonları** - Gemi ve konteyner yönetimi
- ✅ **Rapor Sistemi** - Analiz ve raporlama
- ✅ **Dual Tema** - Koyu/Açık tema desteği
- ✅ **PostgreSQL** - Veritabanı entegrasyonu

## Kurulum

### Gereksinimler

- Python 3.8+
- PostgreSQL 12+

### Adımlar

1. **Gerekli paketleri yükleyin:**
```bash
pip install -r requirements.txt
```

2. **PostgreSQL veritabanı oluşturun:**
```sql
CREATE DATABASE port_db;
```

3. **Environment variables ayarlayın:**
```bash
# .env dosyasını oluşturun
copy .env.example .env
# Kendi bilgilerinizi girin
```

4. **Uygulamayı çalıştırın:**
```bash
python main_pyqt.py
```

## Konfigürasyon

`.env` dosyasında veritabanı bağlantı bilgilerini ayarlayın:

```
DB_NAME=port_db
DB_USER=postgres
DB_PASSWORD=your_password
DB_HOST=localhost
DB_PORT=5432
```

## Kullanım

1. Uygulama ilk çalıştırıldığında veritabanı tabloları otomatik oluşturulur
2. Giriş ekranından kullanıcı adı ve şifre ile giriş yapın
3. Ana ekrandan konteyner işlemlerini yönetin

## Proje Yapısı

```
├── main_pyqt.py         # Ana uygulama
├── gui_pyqt.py          # GUI bileşenleri
├── db_operations.py     # Veritabanı işlemleri
├── config.py            # Konfigürasyon yönetimi
├── reports.py           # Rapor sistemi
├── requirements.txt     # Python bağımlılıkları
├── .env.example         # Örnek environment dosyası
└── README.md            # Bu dosya
```

## Lisans

MIT License