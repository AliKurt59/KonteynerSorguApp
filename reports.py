import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime, timedelta
from tkinter import messagebox # messagebox'u buraya da ekledik

# matplotlib'in Türkçe karakterleri doğru gösterebilmesi için ayarlar
plt.rcParams['font.family'] = 'DejaVu Sans'
plt.rcParams['font.sans-serif'] = ['DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

from db_operations import DBManager

class ReportGenerator:
    def __init__(self, db_manager):
        self.db = db_manager
        plt.style.use('seaborn-v0_8-darkgrid') # Modern bir tema

        # Türkçe ay isimleri
        self.turkish_months = {
            1: 'Ocak', 2: 'Şubat', 3: 'Mart', 4: 'Nisan',
            5: 'Mayıs', 6: 'Haziran', 7: 'Temmuz', 8: 'Ağustos',
            9: 'Eylül', 10: 'Ekim', 11: 'Kasım', 12: 'Aralık'
        }

    def _get_all_port_operations_data(self):
        """Tüm raporların ana veri kaynağı. port_operations tablosundan veri çeker."""
        df = self.db.get_all_port_operations_data()
        
        # timestamp, arrival_date ve departure_date sütunlarını datetime'a çevir
        # ve zaman dilimi bilgisi varsa kaldırarak timezone-naive yap
        for col in ['timestamp', 'arrival_date', 'departure_date']:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors='coerce')
                # Eğer sütun zaman dilimi bilgisi içeriyorsa, onu kaldır
                if df[col].dt.tz is not None:
                    df[col] = df[col].dt.tz_localize(None)
        return df

    def _calculate_single_container_billing(self, container_data):
        """
        Tek bir konteynerin kalış süresine ve gemi tarifesine göre fatura tutarını hesaplar.
        """
        vessel_name = container_data.get('vessel_name')
        arrival_date = container_data.get('arrival_date')
        departure_date = container_data.get('departure_date')
        
        total_cost = 0.0
        stay_duration_days = 0

        # arrival_date ve departure_date'in datetime objeleri olduğundan emin ol
        # (Pandas Timestamp ise Python datetime'a çevir)
        if isinstance(arrival_date, pd.Timestamp):
            arrival_date = arrival_date.to_pydatetime()
        if isinstance(departure_date, pd.Timestamp):
            departure_date = departure_date.to_pydatetime()

        if isinstance(arrival_date, datetime) and isinstance(departure_date, datetime):
            if departure_date >= arrival_date:
                stay_duration = departure_date - arrival_date
                stay_duration_days = stay_duration.days
                if stay_duration_days == 0 and stay_duration.total_seconds() > 0: # Aynı gün içinde ama saat farkı varsa 1 gün say
                    stay_duration_days = 1
                elif stay_duration_days == 0 and stay_duration.total_seconds() == 0: # Tamamen aynı zaman ise 0 gün say
                    stay_duration_days = 0
                
                daily_rate = self.db.get_vessel_tariff(vessel_name)
                if daily_rate is not None:
                    total_cost = stay_duration_days * float(daily_rate)
        return total_cost


    def generate_status_distribution(self):
        """Konteyner durum dağılımını gösteren bir çubuk grafik oluşturur."""
        df = self._get_all_port_operations_data()
        if df.empty:
            messagebox.showinfo("Rapor Hatası", "Konteyner durum dağılımı raporu için veri bulunamadı.")
            return None

        status_counts = df['container_status'].value_counts()

        if status_counts.empty:
            messagebox.showinfo("Rapor Hatası", "Konteyner durum dağılımı raporu için yeterli veri yok.")
            return None

        fig, ax = plt.subplots(figsize=(10, 6))
        sns.barplot(x=status_counts.index, y=status_counts.values, ax=ax, palette='viridis')
        ax.set_title('Konteyner Durum Dağılımı', fontsize=14)
        ax.set_xlabel('Konteyner Durumu', fontsize=12)
        ax.set_ylabel('Sayı', fontsize=12)
        plt.xticks(rotation=45, ha='right')
        plt.grid(True)
        plt.tight_layout()
        plt.show()
        return fig

    def generate_location_distribution(self):
        """
        Konteynerlerin lokasyon bazında dağılımını gösteren bir çubuk grafik oluşturur.
        Sadece en yoğun ilk 10 lokasyonu gösterir.
        """
        df = self._get_all_port_operations_data()
        if df.empty:
            messagebox.showinfo("Rapor Hatası", "Konteyner lokasyon dağılımı raporu için veri bulunamadı.")
            return None

        # Geçerli lokasyon alanlarını filtrele
        location_counts = df['location_area'].dropna().value_counts()

        if location_counts.empty:
            messagebox.showinfo("Rapor Hatası", "Konteyner lokasyon dağılımı raporu için yeterli veri yok.")
            return None

        # En yoğun ilk 10 lokasyonu al
        top_n = 10
        top_locations = location_counts.head(top_n)

        if top_locations.empty:
            messagebox.showinfo("Rapor Hatası", f"En yoğun ilk {top_n} lokasyon için yeterli veri yok.")
            return None

        fig, ax = plt.subplots(figsize=(12, 7))
        sns.barplot(x=top_locations.index, y=top_locations.values, ax=ax, palette='coolwarm')
        ax.set_title(f'En Yoğun Konteyner Lokasyonları (İlk {top_n})', fontsize=14)
        ax.set_xlabel('Lokasyon Alanı', fontsize=12)
        ax.set_ylabel('Konteyner Sayısı', fontsize=12)
        plt.xticks(rotation=45, ha='right')
        plt.grid(True)
        plt.tight_layout()
        plt.show()
        return fig

    def generate_monthly_operations(self):
        """Aylık işlem sayılarını gösteren bir çizgi grafik oluşturur."""
        df = self._get_all_port_operations_data()
        if df.empty:
            messagebox.showinfo("Rapor Hatası", "Aylık işlem sayısı raporu için veri bulunamadı.")
            return None

        # 'timestamp' sütununda NaT değerlerini düşür
        df_filtered = df.dropna(subset=['timestamp'])

        if df_filtered.empty:
            messagebox.showinfo("Rapor Hatası", "Aylık işlem sayısı raporu için geçerli zaman damgası verisi yok.")
            return None

        # Yıl ve ay bilgisini al
        df_filtered['year_month'] = df_filtered['timestamp'].dt.to_period('M')
        monthly_counts = df_filtered['year_month'].value_counts().sort_index()

        if monthly_counts.empty:
            messagebox.showinfo("Rapor Hatası", "Aylık işlem sayısı raporu için yeterli veri yok.")
            return None

        # X ekseni etiketlerini Türkçe ay isimleri ve yıl olarak formatla
        x_labels = [f"{self.turkish_months[period.month]} {period.year}" for period in monthly_counts.index]

        fig, ax = plt.subplots(figsize=(12, 6))
        sns.lineplot(x=monthly_counts.index.astype(str), y=monthly_counts.values, ax=ax, marker='o', color='skyblue')
        ax.set_title('Aylık Toplam Konteyner İşlem Sayısı', fontsize=14)
        ax.set_xlabel('Ay', fontsize=12)
        ax.set_ylabel('İşlem Sayısı', fontsize=12)
        
        # Etiketleri ayarla
        ax.set_xticks(monthly_counts.index.astype(str))
        ax.set_xticklabels(x_labels, rotation=45, ha='right')
        
        plt.grid(True)
        plt.tight_layout()
        plt.show()
        return fig

    def generate_annual_operations(self): # Fonksiyon adı değiştirildi
        """Yıllık işlem sayılarını gösteren bir çizgi grafik oluşturur."""
        df = self._get_all_port_operations_data()
        if df.empty:
            messagebox.showinfo("Rapor Hatası", "Yıllık işlem sayısı raporu için veri bulunamadı.")
            return None

        # 'timestamp' sütununda NaT değerlerini düşür
        df_filtered = df.dropna(subset=['timestamp'])

        if df_filtered.empty:
            messagebox.showinfo("Rapor Hatası", "Yıllık işlem sayısı raporu için geçerli zaman damgası verisi yok.")
            return None

        # Yıllık periyoda çevir
        df_filtered['year'] = df_filtered['timestamp'].dt.to_period('Y')
        annual_counts = df_filtered['year'].value_counts().sort_index()

        if annual_counts.empty:
            messagebox.showinfo("Rapor Hatası", "Yıllık işlem sayısı raporu için yeterli veri yok.")
            return None

        # X ekseni etiketlerini yıl olarak formatla
        x_labels = [str(period.year) for period in annual_counts.index]

        fig, ax = plt.subplots(figsize=(12, 6))
        sns.lineplot(x=annual_counts.index.astype(str), y=annual_counts.values, ax=ax, marker='o', color='lightcoral')
        ax.set_title('Yıllık Toplam Konteyner İşlem Sayısı', fontsize=14) # Başlık değiştirildi
        ax.set_xlabel('Yıl', fontsize=12) # Etiket değiştirildi
        ax.set_ylabel('İşlem Sayısı', fontsize=12)
        
        # Etiketleri ayarla
        ax.set_xticks(annual_counts.index.astype(str))
        ax.set_xticklabels(x_labels, rotation=45, ha='right')
        
        plt.grid(True)
        plt.tight_layout()
        plt.show()
        return fig

    def generate_top_ports(self):
        """En yoğun limanları (varış ve kalkış) gösteren bir çubuk grafik oluşturur."""
        df = self._get_all_port_operations_data()
        if df.empty:
            messagebox.showinfo("Rapor Hatası", "En yoğun limanlar raporu için veri bulunamadı.")
            return None

        # Varış ve kalkış limanlarını birleştir
        # NaN değerleri düşürerek sadece geçerli liman isimlerini al
        arrival_ports = df['arrival_port'].dropna()
        departure_ports = df['departure_port'].dropna()

        # Her iki seriyi birleştir ve frekanslarını say
        all_ports = pd.concat([arrival_ports, departure_ports])
        port_counts_raw = all_ports.value_counts()

        if port_counts_raw.empty:
            messagebox.showinfo("Rapor Hatası", "En yoğun limanlar raporu için yeterli veri yok.")
            return None

        top_n = 10
        port_counts = port_counts_raw.head(top_n) # head() metodu artık boş olmayan bir seri üzerinde çağrılıyor

        if port_counts.empty:
            messagebox.showinfo("Rapor Hatası", f"En yoğun ilk {top_n} liman için yeterli veri yok.")
            return None

        fig, ax = plt.subplots(figsize=(10, 8))
        sns.barplot(x=port_counts.values, y=port_counts.index, ax=ax, palette='magma')
        ax.set_title(f'En Yoğun Limanlar (İlk {top_n} - Varış/Kalkış)', fontsize=14)
        ax.set_xlabel('İşlem Sayısı', fontsize=12)
        ax.set_ylabel('Liman', fontsize=12)
        plt.grid(True)
        plt.tight_layout()
        plt.show()
        return fig

    def generate_vessel_operation_counts(self):
        """
        Gemiye göre konteyner işlem sayılarını gösteren bir çubuk grafik oluşturur.
        """
        df = self._get_all_port_operations_data()
        if df.empty:
            messagebox.showinfo("Rapor Hatası", "Gemiye göre konteyner sayısı raporu için veri bulunamadı.")
            return None

        df_filtered = df.dropna(subset=['vessel_name'])
        if df_filtered.empty:
            messagebox.showinfo("Rapor Hatası", "Gemiye göre konteyner sayısı raporu için geçerli gemi adı verisi yok.")
            return None

        vessel_counts = df_filtered['vessel_name'].value_counts().head(10) # En çok işlem yapılan ilk 10 gemi
        if vessel_counts.empty:
            messagebox.showinfo("Rapor Hatası", "Gemiye göre konteyner sayısı raporu için yeterli veri yok.")
            return None

        fig, ax = plt.subplots(figsize=(14, 7))
        sns.barplot(x=vessel_counts.index, y=vessel_counts.values, ax=ax, palette='cool')
        ax.set_title('En Çok Konteyner İşlemi Yapılan Gemiler (İlk 10)', fontsize=14)
        ax.set_xlabel('Gemi Adı', fontsize=12)
        ax.set_ylabel('İşlem Sayısı', fontsize=12)
        ax.tick_params(axis='x', rotation=45, ha='right') # Etiketlerin üst üste binmesini engelle
        plt.grid(True)
        plt.tight_layout()
        plt.show()
        return fig

    def generate_billing_report(self, start_date=None, end_date=None, period='monthly'):
        """
        Belirli bir tarih aralığında ve periyotta (günlük, haftalık, aylık, yıllık)
        toplam faturalandırma miktarını gösteren bir çizgi grafik oluşturur.
        start_date ve end_date None ise, tüm veri setindeki min/max tarihleri kullanır.
        """
        df = self._get_all_port_operations_data()
        if df.empty:
            messagebox.showinfo("Rapor Hatası", "Faturalandırma raporu için veri bulunamadı.")
            return None

        # Eğer tarih aralığı belirtilmemişse, tüm veri setindeki min/max tarihleri bul
        if start_date is None or end_date is None:
            if 'arrival_date' not in df.columns or df['arrival_date'].isnull().all():
                messagebox.showinfo("Rapor Hatası", "Faturalandırma raporu için geçerli 'Limana Giriş Tarihi' verisi bulunamadı.")
                return None
            
            # DataFrame'deki en erken ve en geç tarihleri bul
            min_date = df['arrival_date'].min()
            max_date = df['arrival_date'].max()

            if pd.isna(min_date) or pd.isna(max_date):
                messagebox.showinfo("Rapor Hatası", "Faturalandırma raporu için geçerli tarih aralığı bulunamadı.")
                return None
            
            start_date = min_date
            end_date = max_date

        # start_date ve end_date'in timezone-naive olduğundan emin ol
        if start_date.tzinfo is not None:
            start_date = start_date.replace(tzinfo=None)
        if end_date.tzinfo is not None:
            end_date = end_date.replace(tzinfo=None)

        # arrival_date'i baz alarak tarih aralığına göre filtrele
        df_filtered = df[(df['arrival_date'] >= start_date) & (df['arrival_date'] <= end_date)].copy()
        
        # Gerekli sütunların varlığını kontrol et
        required_cols = ['vessel_name', 'arrival_date', 'departure_date']
        if not all(col in df_filtered.columns for col in required_cols):
            messagebox.showinfo("Rapor Hatası", "Faturalandırma raporu için gerekli sütunlar (gemi adı, varış/çıkış tarihi) eksik.")
            return None

        # Fatura tutarlarını hesapla
        df_filtered['billing_amount'] = df_filtered.apply(self._calculate_single_container_billing, axis=1)

        if df_filtered['billing_amount'].sum() == 0:
            messagebox.showinfo("Rapor Hatası", "Belirtilen tarih aralığında faturalandırılabilecek işlem bulunamadı veya tarifeler eksik.")
            return None

        # Periyoda göre grupla ve toplam fatura miktarını al
        if period == 'daily':
            freq = 'D'
            title_period = 'Günlük'
            xlabel = 'Tarih'
            date_format = '%Y-%m-%d'
        elif period == 'weekly':
            freq = 'W'
            title_period = 'Haftalık'
            xlabel = 'Yıl-Hafta'
            date_format = '%Y-%W'
        elif period == 'monthly':
            freq = 'M'
            title_period = 'Aylık'
            xlabel = 'Ay'
            date_format = '%Y-%m'
        elif period == 'yearly':
            freq = 'Y'
            title_period = 'Yıllık'
            xlabel = 'Yıl'
            date_format = '%Y'
        else:
            messagebox.warning("Rapor Hatası", "Geçersiz periyot seçimi. Lütfen 'daily', 'weekly', 'monthly' veya 'yearly' seçin.")
            return None

        # arrival_date'e göre grupla
        billing_by_period = df_filtered.groupby(pd.Grouper(key='arrival_date', freq=freq))['billing_amount'].sum()
        
        # Boş dönemleri 0 ile doldur
        billing_by_period = billing_by_period.asfreq(freq, fill_value=0)

        if billing_by_period.empty:
            messagebox.showinfo("Rapor Hatası", "Belirtilen periyot için faturalandırma verisi yok.")
            return None

        # X ekseni etiketlerini formatla
        x_labels = []
        if period == 'monthly':
            x_labels = [f"{self.turkish_months[idx.month]} {idx.year}" for idx in billing_by_period.index]
        elif period == 'weekly':
            # isocalendar()[1] ISO hafta numarasını verir (1'den 52 veya 53'e kadar)
            x_labels = [f"{idx.year}-{idx.isocalendar()[1]}. Hafta" for idx in billing_by_period.index]
        else: # daily, yearly
            x_labels = [idx.strftime(date_format) for idx in billing_by_period.index]


        fig, ax = plt.subplots(figsize=(14, 7))
        sns.lineplot(x=billing_by_period.index.astype(str), y=billing_by_period.values, ax=ax, marker='o', color='green')
        ax.set_title(f'{title_period} Toplam Faturalandırma Miktarı ({start_date.strftime("%Y-%m-%d")} - {end_date.strftime("%Y-%m-%d")})', fontsize=14)
        ax.set_xlabel(xlabel, fontsize=12)
        ax.set_ylabel('Toplam Fatura Miktarı ($)', fontsize=12)
        
        # Etiketleri ayarla
        ax.set_xticks(billing_by_period.index.astype(str))
        ax.set_xticklabels(x_labels, rotation=45, ha='right')
        
        plt.grid(True)
        plt.tight_layout()
        plt.show()
        return fig

    def generate_vessel_specific_billing_report(self, vessel_name, start_date, end_date, period='monthly'):
        """
        Belirli bir gemi için, belirli bir tarih aralığında ve periyotta
        toplam faturalandırma miktarını gösteren bir çizgi grafik oluşturur.
        """
        df = self._get_all_port_operations_data()
        if df.empty:
            messagebox.showinfo("Rapor Hatası", "Faturalandırma raporu için veri bulunamadı.")
            return None

        # Gemiye göre filtrele
        df_vessel_filtered = df[df['vessel_name'] == vessel_name].copy()
        if df_vessel_filtered.empty:
            messagebox.showinfo("Rapor Hatası", f"'{vessel_name}' gemisi için faturalandırma verisi bulunamadı.")
            return None

        # Tarih aralığına göre filtrele
        # start_date ve end_date'in timezone-naive olduğundan emin ol
        if start_date.tzinfo is not None:
            start_date = start_date.replace(tzinfo=None)
        if end_date.tzinfo is not None:
            end_date = end_date.replace(tzinfo=None)

        df_filtered_by_date = df_vessel_filtered[(df_vessel_filtered['arrival_date'] >= start_date) & (df_vessel_filtered['arrival_date'] <= end_date)].copy()
        
        if df_filtered_by_date.empty:
            messagebox.showinfo("Rapor Hatası", f"'{vessel_name}' gemisi için belirtilen tarih aralığında faturalandırma verisi bulunamadı.")
            return None

        # Gerekli sütunların varlığını kontrol et
        required_cols = ['vessel_name', 'arrival_date', 'departure_date']
        if not all(col in df_filtered_by_date.columns for col in required_cols):
            messagebox.showinfo("Rapor Hatası", "Faturalandırma raporu için gerekli sütunlar (gemi adı, varış/çıkış tarihi) eksik.")
            return None

        # Fatura tutarlarını hesapla
        df_filtered_by_date['billing_amount'] = df_filtered_by_date.apply(self._calculate_single_container_billing, axis=1)

        if df_filtered_by_date['billing_amount'].sum() == 0:
            messagebox.showinfo("Rapor Hatası", "Belirtilen tarih aralığında faturalandırılabilecek işlem bulunamadı veya tarifeler eksik.")
            return None

        # Periyoda göre grupla ve toplam fatura miktarını al
        if period == 'daily':
            freq = 'D'
            title_period = 'Günlük'
            xlabel = 'Tarih'
            date_format = '%Y-%m-%d'
        elif period == 'weekly':
            freq = 'W'
            title_period = 'Haftalık'
            xlabel = 'Yıl-Hafta'
            date_format = '%Y-%W'
        elif period == 'monthly':
            freq = 'M'
            title_period = 'Aylık'
            xlabel = 'Ay'
            date_format = '%Y-%m'
        elif period == 'yearly':
            freq = 'Y'
            title_period = 'Yıllık'
            xlabel = 'Yıl'
            date_format = '%Y'
        else:
            messagebox.warning("Rapor Hatası", "Geçersiz periyot seçimi. Lütfen 'daily', 'weekly', 'monthly' veya 'yearly' seçin.")
            return None

        # arrival_date'e göre grupla
        billing_by_period = df_filtered_by_date.groupby(pd.Grouper(key='arrival_date', freq=freq))['billing_amount'].sum()
        
        # Boş dönemleri 0 ile doldur
        billing_by_period = billing_by_period.asfreq(freq, fill_value=0)

        if billing_by_period.empty:
            messagebox.showinfo("Rapor Hatası", "Belirtilen periyot için faturalandırma verisi yok.")
            return None

        # X ekseni etiketlerini formatla
        x_labels = []
        if period == 'monthly':
            x_labels = [f"{self.turkish_months[idx.month]} {idx.year}" for idx in billing_by_period.index]
        elif period == 'weekly':
            x_labels = [f"{idx.year}-{idx.isocalendar()[1]}. Hafta" for idx in billing_by_period.index]
        else: # daily, yearly
            x_labels = [idx.strftime(date_format) for idx in billing_by_period.index]


        fig, ax = plt.subplots(figsize=(14, 7))
        sns.lineplot(x=billing_by_period.index.astype(str), y=billing_by_period.values, ax=ax, marker='o', color='purple')
        ax.set_title(f'{vessel_name} - {title_period} Toplam Faturalandırma Miktarı ({start_date.strftime("%Y-%m-%d")} - {end_date.strftime("%Y-%m-%d")})', fontsize=14)
        ax.set_xlabel(xlabel, fontsize=12)
        ax.set_ylabel('Toplam Fatura Miktarı ($)', fontsize=12)
        
        # Etiketleri ayarla
        ax.set_xticks(billing_by_period.index.astype(str))
        ax.set_xticklabels(x_labels, rotation=45, ha='right')
        
        plt.grid(True)
        plt.tight_layout()
        plt.show()
        return fig
