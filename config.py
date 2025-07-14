import os
import logging
from configparser import ConfigParser

class Config:
    """Uygulama konfigürasyon sınıfı"""
    
    def __init__(self):
        self.config_file = 'app.ini'
        self.setup_logging()
        self.load_config()
    
    def setup_logging(self):
        """Logging sistemini konfigüre eder"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('app.log', encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
    
    def load_config(self):
        """Konfigürasyon dosyasını yükler veya varsayılan değerlerle oluşturur"""
        config = ConfigParser()
        
        # Konfigürasyon dosyası yoksa oluştur
        if not os.path.exists(self.config_file):
            self.create_default_config(config)
        else:
            config.read(self.config_file, encoding='utf-8')
        
        # Environment variables'dan veya config dosyasından değerleri al
        self.DB_NAME = os.getenv("DB_NAME", config.get('database', 'name', fallback='port_db'))
        self.DB_USER = os.getenv("DB_USER", config.get('database', 'user', fallback='postgres'))
        self.DB_PASSWORD = os.getenv("DB_PASSWORD", config.get('database', 'password', fallback=''))
        self.DB_HOST = os.getenv("DB_HOST", config.get('database', 'host', fallback='localhost'))
        self.DB_PORT = os.getenv("DB_PORT", config.get('database', 'port', fallback='5432'))
        
         # Şifre kontrolü
        if not self.DB_PASSWORD:
            self.logger.error("Veritabanı şifresi bulunamadı! Environment variable DB_PASSWORD tanımlanmalı.")
            self.logger.info("Lütfen .env dosyasını oluşturun ve DB_PASSWORD değerini ayarlayın.")
            self.DB_PASSWORD = None  # Şifre yok
        
        # Tema ayarı
        self.DEFAULT_THEME = config.get('ui', 'default_theme', fallback='Koyu Tema')
        
        self.logger.info("Konfigürasyon yüklendi.")
    
    def create_default_config(self, config):
        """Varsayılan konfigürasyon dosyasını oluşturur"""
        config.add_section('database')
        config.set('database', 'name', 'port_db')
        config.set('database', 'user', 'postgres')
        config.set('database', 'password', '')  # Şifreyi burada saklamıyoruz
        config.set('database', 'host', 'localhost')
        config.set('database', 'port', '5432')
        
        config.add_section('ui')
        config.set('ui', 'default_theme', 'Koyu Tema')
        
        config.add_section('logging')
        config.set('logging', 'level', 'INFO')
        
        with open(self.config_file, 'w', encoding='utf-8') as configfile:
            config.write(configfile)
        
        self.logger.info(f"Varsayılan konfigürasyon dosyası oluşturuldu: {self.config_file}")
    
    def get_db_config(self):
        """Veritabanı konfigürasyon bilgilerini döndürür"""
        return {
            'dbname': self.DB_NAME,
            'user': self.DB_USER,
            'password': self.DB_PASSWORD,
            'host': self.DB_HOST,
            'port': self.DB_PORT
        }
    
    def validate_db_config(self):
        """Veritabanı konfigürasyonunu doğrular"""
        required_fields = ['DB_NAME', 'DB_USER', 'DB_PASSWORD', 'DB_HOST', 'DB_PORT']
        missing_fields = []
        
        for field in required_fields:
            if not getattr(self, field):
                missing_fields.append(field)
        
        if missing_fields:
            self.logger.error(f"Eksik veritabanı konfigürasyon alanları: {', '.join(missing_fields)}")
            return False, missing_fields
        
        return True, []

# Global config instance
app_config = Config()
