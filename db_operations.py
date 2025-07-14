import psycopg2
import pandas as pd
from datetime import datetime
import hashlib # Şifre hash'leme için

class DBManager:
    def __init__(self, dbname, user, password, host='localhost', port='5432'):
        self.dbname = dbname
        self.user = user
        self.password = password
        self.host = host
        self.port = port
        self.conn = None

    def connect(self):
        """Veritabanına bağlanır veya mevcut bağlantıyı kontrol eder."""
        if self.conn is None or self.conn.closed:
            try:
                self.conn = psycopg2.connect(
                    dbname=self.dbname,
                    user=self.user,
                    password=self.password,
                    host=self.host,
                    port=self.port
                )
                self.conn.autocommit = True
                print("PostgreSQL veritabanına başarıyla bağlandı.")
            except Exception as e:
                raise Exception(f"Veritabanı bağlantı hatası: {e}")

    def close(self):
        """Veritabanı bağlantısını kapatır."""
        if self.conn and not self.conn.closed:
            self.conn.close()
            self.conn = None
            print("Veritabanı bağlantısı kapatıldı.")

    def execute_query(self, query, params=None, fetch=False):
        """Veritabanında sorgu çalıştırır."""
        try:
            self.connect()
            if self.conn is None or self.conn.closed:
                raise Exception("Veritabanı bağlantısı kurulamadı veya kapalı.")

            with self.conn.cursor() as cur:
                cur.execute(query, params)
                if fetch:
                    results = cur.fetchall()
                    return results
                return None
        except psycopg2.Error as e:
            raise Exception(f"Veritabanı sorgu hatası: {e}")
        except Exception as e:
            raise Exception(f"Beklenmeyen hata: {e}")

    def hash_password(self, password):
        """Şifreyi SHA256 ile hash'ler."""
        return hashlib.sha256(password.encode()).hexdigest()

    def check_and_create_tables(self):
        """Gerekli tabloları kontrol eder ve yoksa oluşturur."""
        try:
            # users tablosu (Kullanıcı kimlik doğrulama için)
            users_table_sql = """
            CREATE TABLE IF NOT EXISTS public.users (
                id SERIAL PRIMARY KEY,
                username VARCHAR(50) UNIQUE NOT NULL,
                password_hash VARCHAR(256) NOT NULL,
                role VARCHAR(50) DEFAULT 'operator'
            );
            """
            self.execute_query(users_table_sql)

            # port_operations tablosu
            port_operations_table_sql = """
            CREATE TABLE IF NOT EXISTS public.port_operations (
                vessel_name VARCHAR(255),
                imo_number INTEGER,
                arrival_port VARCHAR(255),
                departure_port VARCHAR(255),
                container_id VARCHAR(50) PRIMARY KEY,
                container_size INTEGER,
                container_type VARCHAR(50),
                operation_type VARCHAR(50),
                timestamp TIMESTAMP WITH TIME ZONE,
                terminal_name VARCHAR(255),
                transport_mode VARCHAR(100),
                container_status VARCHAR(50),
                location_area VARCHAR(255),
                handling_equipment VARCHAR(255),
                customs_clearance_status VARCHAR(50),
                weight_kg INTEGER,
                hazmat_flag BOOLEAN,
                arrival_date TIMESTAMP WITH TIME ZONE,
                departure_date TIMESTAMP WITH TIME ZONE
            );
            """
            self.execute_query(port_operations_table_sql)

            # container_logs tablosu
            container_logs_table_sql = """
            CREATE TABLE IF NOT EXISTS public.container_logs (
                log_id SERIAL PRIMARY KEY,
                container_id VARCHAR(50) REFERENCES public.port_operations(container_id) ON DELETE CASCADE,
                operation_type VARCHAR(100),
                old_status VARCHAR(50),
                new_status VARCHAR(50),
                old_location VARCHAR(50),
                new_location VARCHAR(50),
                operation_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """
            self.execute_query(container_logs_table_sql)

            # user_actions_log tablosu (Kullanıcı eylemlerini loglamak için)
            user_actions_log_table_sql = """
            CREATE TABLE IF NOT EXISTS public.user_actions_log (
                action_id SERIAL PRIMARY KEY,
                username VARCHAR(50),
                action_type VARCHAR(100),
                description TEXT,
                action_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """
            self.execute_query(user_actions_log_table_sql)

            # vessel_tariffs tablosu
            vessel_tariffs_table_sql = """
            CREATE TABLE IF NOT EXISTS public.vessel_tariffs (
                vessel_name VARCHAR(255) PRIMARY KEY,
                daily_rate NUMERIC(10, 2) NOT NULL
            );
            """
            self.execute_query(vessel_tariffs_table_sql)

            print("Veritabanı tabloları kontrol edildi/oluşturuldu.")
            return True
        except Exception as e:
            print(f"Tablo oluşturma/kontrol hatası: {e}")
            return False

    def add_user(self, username, password, role='operator'):
        """Yeni bir kullanıcı ekler."""
        password_hash = self.hash_password(password)
        query = "INSERT INTO public.users (username, password_hash, role) VALUES (%s, %s, %s) ON CONFLICT (username) DO NOTHING;"
        try:
            self.execute_query(query, (username, password_hash, role))
            print(f"Kullanıcı '{username}' başarıyla eklendi veya zaten mevcut.")
            return True
        except Exception as e:
            print(f"Kullanıcı eklenirken hata: {e}")
            return False

    def validate_user(self, username, password):
        """Kullanıcı adı ve şifreyi doğrular."""
        hashed_password = self.hash_password(password)
        query = "SELECT username, role FROM public.users WHERE username = %s AND password_hash = %s;"
        results = self.execute_query(query, (username, hashed_password), fetch=True)
        if results:
            self.add_user_action_log(username, "Login Success", "User logged in successfully.")
            return results[0] # (username, role) döner
        return None

    def get_user_role(self, username):
        """Bir kullanıcının rolünü çeker."""
        query = "SELECT role FROM public.users WHERE username = %s;"
        results = self.execute_query(query, (username,), fetch=True)
        if results:
            return results[0][0]
        return None

    def get_all_users(self):
        """Tüm kullanıcıları çeker."""
        query = "SELECT id, username, role FROM public.users ORDER BY username;"
        results = self.execute_query(query, fetch=True)
        if results:
            return pd.DataFrame(results, columns=['id', 'username', 'role'])
        return pd.DataFrame()

    def update_user(self, user_id, username, password=None, role=None):
        """Bir kullanıcının bilgilerini günceller."""
        set_clauses = []
        params = []
        if username:
            set_clauses.append("username = %s")
            params.append(username)
        if password:
            password_hash = self.hash_password(password)
            set_clauses.append("password_hash = %s")
            params.append(password_hash)
        if role:
            set_clauses.append("role = %s")
            params.append(role)
        
        if not set_clauses:
            return False # Güncellenecek bir şey yok

        query = f"UPDATE public.users SET {', '.join(set_clauses)} WHERE id = %s;"
        params.append(user_id)
        try:
            self.execute_query(query, params)
            return True
        except Exception as e:
            raise Exception(f"Kullanıcı güncellenirken hata: {e}")

    def delete_user(self, user_id):
        """Belirtilen ID'ye sahip kullanıcıyı siler."""
        query = "DELETE FROM public.users WHERE id = %s;"
        try:
            self.execute_query(query, (user_id,))
            return True
        except Exception as e:
            raise Exception(f"Kullanıcı silinirken hata: {e}")


    def add_user_action_log(self, username, action_type, description):
        """Kullanıcı eylemlerini loglar."""
        query = "INSERT INTO public.user_actions_log (username, action_type, description) VALUES (%s, %s, %s);"
        try:
            self.execute_query(query, (username, action_type, description))
            return True
        except Exception as e:
            print(f"Kullanıcı eylem logu eklenirken hata: {e}")
            return False

    def get_all_user_action_logs(self):
        """Tüm kullanıcı eylem loglarını çeker."""
        query = "SELECT action_id, username, action_type, description, action_time FROM public.user_actions_log ORDER BY action_time DESC;"
        results = self.execute_query(query, fetch=True)
        if results:
            df = pd.DataFrame(results, columns=['action_id', 'username', 'action_type', 'description', 'action_time'])
            return df
        return pd.DataFrame()

    def add_port_operation(self, data):
        """Yeni bir port operasyonu kaydı ekler."""
        query = """
        INSERT INTO public.port_operations (
            vessel_name, imo_number, arrival_port, departure_port, container_id,
            container_size, container_type, operation_type, timestamp, terminal_name,
            transport_mode, container_status, location_area, handling_equipment,
            customs_clearance_status, weight_kg, hazmat_flag, arrival_date, departure_date
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
        """
        params = (
            data.get('vessel_name'), data.get('imo_number'), data.get('arrival_port'),
            data.get('departure_port'), data.get('container_id'), data.get('container_size'),
            data.get('container_type'), data.get('operation_type'), data.get('timestamp'),
            data.get('terminal_name'), data.get('transport_mode'), data.get('container_status'),
            data.get('location_area'), data.get('handling_equipment'),
            data.get('customs_clearance_status'), data.get('weight_kg'), data.get('hazmat_flag'),
            data.get('arrival_date'), data.get('departure_date')
        )
        try:
            self.execute_query(query, params)
            return True
        except Exception as e:
            raise Exception(f"Operasyon eklenirken hata: {e}")

    def update_port_operation(self, container_id, data):
        """Mevcut bir port operasyonu kaydını günceller."""
        set_clauses = []
        params = []
        
        # Mevcut veriyi çekerek eski durum ve lokasyonu al (log için)
        # Not: Bu kısım loglama için kullanılabilir, ancak şu an loglama gui tarafında yapılıyor.
        # old_data_df = self.get_port_operation_by_container_id(container_id)
        # old_status = old_data_df['container_status'].iloc[0] if not old_data_df.empty else None
        # old_location = old_data_df['location_area'].iloc[0] if not old_data_df.empty else None

        for key, value in data.items():
            if key != 'container_id': # container_id primary key olduğu için güncellenmez
                set_clauses.append(f"{key} = %s")
                params.append(value)
        
        if not set_clauses:
            raise ValueError("Güncellenecek veri bulunamadı.")

        query = f"UPDATE public.port_operations SET {', '.join(set_clauses)} WHERE container_id = %s;"
        params.append(container_id)

        try:
            self.execute_query(query, params)
            return True
        except Exception as e:
            raise Exception(f"Operasyon güncellenirken hata: {e}")

    def delete_port_operation(self, container_id):
        """Belirtilen container_id'ye sahip port operasyonu kaydını siler."""
        query = "DELETE FROM public.port_operations WHERE container_id = %s;"
        try:
            self.execute_query(query, (container_id,))
            return True
        except Exception as e:
            raise Exception(f"Operasyon silinirken hata: {e}")

    def get_port_operation_by_container_id(self, container_id):
        """Belirli bir konteyner ID'sine ait port operasyonu kaydını çeker."""
        query = """
        SELECT vessel_name, imo_number, arrival_port, departure_port,
               container_id, container_size, container_type, operation_type,
               timestamp, terminal_name, transport_mode, container_status,
               location_area, handling_equipment, customs_clearance_status,
               weight_kg, hazmat_flag, arrival_date, departure_date
        FROM public.port_operations
        WHERE container_id ILIKE %s;
        """
        results = self.execute_query(query, (container_id,), fetch=True)
        if results:
            columns = [
                "vessel_name", "imo_number", "arrival_port", "departure_port",
                "container_id", "container_size", "container_type", "operation_type",
                "timestamp", "terminal_name", "transport_mode", "container_status",
                "location_area", "handling_equipment", "customs_clearance_status",
                "weight_kg", "hazmat_flag", "arrival_date", "departure_date"
            ]
            return pd.DataFrame(results, columns=columns)
        return pd.DataFrame()

    def get_all_port_operations_data(self):
        """port_operations tablosundaki tüm verileri çeker."""
        query = """
        SELECT vessel_name, imo_number, arrival_port, departure_port,
               container_id, container_size, container_type, operation_type,
               timestamp, terminal_name, transport_mode, container_status,
               location_area, handling_equipment, customs_clearance_status,
               weight_kg, hazmat_flag, arrival_date, departure_date
        FROM public.port_operations
        ORDER BY timestamp DESC;
        """
        results = self.execute_query(query, fetch=True)
        if results:
            columns = [
                "vessel_name", "imo_number", "arrival_port", "departure_port",
                "container_id", "container_size", "container_type", "operation_type",
                "timestamp", "terminal_name", "transport_mode", "container_status",
                "location_area", "handling_equipment", "customs_clearance_status",
                "weight_kg", "hazmat_flag", "arrival_date", "departure_date"
            ]
            df = pd.DataFrame(results, columns=columns)
            return df
        return pd.DataFrame()

    def search_port_operations(self, criteria):
        """
        Belirtilen kriterlere göre port operasyonlarını arar.
        criteria: {'column_name': 'search_value', 'start_date': datetime, 'end_date': datetime ...} şeklinde bir sözlük.
        """
        base_query = """
        SELECT vessel_name, imo_number, arrival_port, departure_port,
               container_id, container_size, container_type, operation_type,
               timestamp, terminal_name, transport_mode, container_status,
               location_area, handling_equipment, customs_clearance_status,
               weight_kg, hazmat_flag, arrival_date, departure_date
        FROM public.port_operations
        """
        where_clauses = []
        params = []

        for col, val in criteria.items():
            if val is not None and val != '': # Boş stringleri veya None'ları filtreleme
                if col == 'start_date':
                    where_clauses.append("timestamp >= %s")
                    params.append(val)
                elif col == 'end_date':
                    where_clauses.append("timestamp <= %s")
                    params.append(val)
                elif col in ['imo_number', 'container_size', 'weight_kg']:
                    # Sayısal sütunlar için tam eşleşme
                    where_clauses.append(f"{col} = %s")
                    params.append(val)
                else:
                    # Metin sütunları için kısmi ve case-insensitive eşleşme
                    where_clauses.append(f"{col} ILIKE %s")
                    params.append(f"%{val}%")

        if where_clauses:
            base_query += " WHERE " + " AND ".join(where_clauses)
        
        base_query += " ORDER BY timestamp DESC;"

        results = self.execute_query(base_query, tuple(params), fetch=True)
        if results:
            columns = [
                "vessel_name", "imo_number", "arrival_port", "departure_port",
                "container_id", "container_size", "container_type", "operation_type",
                "timestamp", "terminal_name", "transport_mode", "container_status",
                "location_area", "handling_equipment", "customs_clearance_status",
                "weight_kg", "hazmat_flag", "arrival_date", "departure_date"
            ]
            df = pd.DataFrame(results, columns=columns)
            return df
        return pd.DataFrame()


    def add_container_log(self, container_id, operation_type, old_status, new_status, old_location, new_location):
        """Konteyner hareketleri için log kaydı ekler ('container_logs' tablosuna)."""
        query = """
        INSERT INTO public.container_logs (container_id, operation_type, old_status, new_status, old_location, new_location)
        VALUES (%s, %s, %s, %s, %s, %s);
        """
        try:
            self.execute_query(query, (container_id, operation_type, old_status, new_status, old_location, new_location))
            return True
        except Exception as e:
            print(f"Log kaydı eklenirken hata: {e}")
            return False

    def get_container_logs(self, container_id):
        """Belirli bir konteynerin log verilerini çeker ('container_logs' tablosundan)."""
        query = """
        SELECT log_id, container_id, operation_type, old_status, new_status, old_location, new_location, operation_time
        FROM public.container_logs
        WHERE container_id = %s
        ORDER BY operation_time DESC;
        """
        results = self.execute_query(query, (container_id,), fetch=True)
        if results:
            df = pd.DataFrame(results, columns=[
                'log_id', 'container_id', 'operation_type', 'old_status', 'new_status', 'old_location', 'new_location', 'operation_time'
            ])
            return df
        return pd.DataFrame()

    def get_all_logs(self):
        """Tüm log verilerini çeker ('container_logs' tablosundan)."""
        query = """
        SELECT log_id, container_id, operation_type, old_status, new_status, old_location, new_location, operation_time
        FROM public.container_logs
        ORDER BY operation_time DESC;
        """
        results = self.execute_query(query, fetch=True)
        if results:
            df = pd.DataFrame(results, columns=[
                'log_id', 'container_id', 'old_status', 'new_status', 'old_location', 'new_location', 'operation_type', 'operation_time'
            ])
            return df
        return pd.DataFrame()

    def get_vessel_tariff(self, vessel_name):
        """Belirli bir gemi için günlük tarifeyi çeker."""
        query = """
        SELECT daily_rate FROM public.vessel_tariffs WHERE vessel_name ILIKE %s;
        """
        self.connect()
        if self.conn is None or self.conn.closed:
             print("DEBUG_DB_TARIFF: Bağlantı kurulamadı, tarife çekilemiyor.")
             return None
        
        with self.conn.cursor() as cur:
            cur.execute(query, (vessel_name,))
            result = cur.fetchone()
            if result:
                return result[0]
            return None

    def add_or_update_vessel_tariff(self, vessel_name, daily_rate):
        """Bir gemi tarifesi ekler veya günceller."""
        query = """
        INSERT INTO public.vessel_tariffs (vessel_name, daily_rate)
        VALUES (%s, %s)
        ON CONFLICT (vessel_name) DO UPDATE SET daily_rate = EXCLUDED.daily_rate;
        """
        try:
            self.execute_query(query, (vessel_name, daily_rate))
            print(f"Gemi '{vessel_name}' için günlük tarife {daily_rate} olarak ayarlandı/güncellendi.")
            return True
        except Exception as e:
            print(f"Gemi tarifesi eklenirken/güncellenirken hata oluştu: {e}")
            return False

    def get_all_vessel_tariffs(self):
        """Tüm gemi tarifelerini çeker."""
        query = """
        SELECT vessel_name, daily_rate FROM public.vessel_tariffs ORDER BY vessel_name;
        """
        results = self.execute_query(query, fetch=True)
        if results:
            df = pd.DataFrame(results, columns=['vessel_name', 'daily_rate'])
            return df
        return pd.DataFrame()

    def get_unique_column_values(self, column_name):
        """port_operations tablosundaki belirli bir sütunun benzersiz değerlerini çeker."""
        allowed_columns = [
            "vessel_name", "arrival_port", "departure_port", "container_type",
            "operation_type", "terminal_name", "transport_mode", "container_status",
            "location_area", "handling_equipment", "customs_clearance_status", "container_size", "imo_number", "weight_kg"
        ]
        if column_name not in allowed_columns:
            print(f"Uyarı: '{column_name}' sütunu için benzersiz değerler çekilemez. İzin verilen sütunlar: {', '.join(allowed_columns)}")
            return []
        
        # Sayısal sütunlar için özel işleme
        numeric_columns = ["container_size", "imo_number", "weight_kg"]
        
        where_clause = f"WHERE {column_name} IS NOT NULL"
        if column_name not in numeric_columns:
            # Sadece sayısal olmayan sütunlar için boş string kontrolü yap
            where_clause += f" AND {column_name} != ''"
        
        query = f"SELECT DISTINCT {column_name} FROM public.port_operations {where_clause} ORDER BY {column_name};"
        results = self.execute_query(query, fetch=True)

        if results:
            if column_name in numeric_columns:
                # Sayısal sütunlar için int'e çevir ve sırala
                try:
                    # None değerleri filtrelemeden önce int'e çevirmeye çalış
                    return sorted([int(row[0]) for row in results if row[0] is not None])
                except (ValueError, TypeError):
                    # Eğer int'e çevrilemezse (örn: boş string veya geçersiz metin), string olarak döndür
                    return sorted([str(row[0]) for row in results if row[0] is not None])
            else:
                # Diğer sütunlar için string olarak döndür
                return sorted([str(row[0]) for row in results if row[0] is not None])
        return []

    def export_table_to_csv(self, table_name, file_path):
        """Belirtilen tabloyu CSV dosyasına aktarır."""
        query = f"SELECT * FROM public.{table_name};"
        try:
            results = self.execute_query(query, fetch=True)
            if results:
                # Sütun isimlerini dinamik olarak al
                self.connect()
                with self.conn.cursor() as cur:
                    cur.execute(query)
                    columns = [desc[0] for desc in cur.description]
                
                df = pd.DataFrame(results, columns=columns)
                df.to_csv(file_path, index=False, encoding='utf-8-sig')
                return True
            return False
        except Exception as e:
            print(f"CSV'ye aktarılırken hata oluştu ({table_name}): {e}")
            raise

    def import_data_from_csv(self, table_name, file_path):
        """CSV dosyasından belirtilen tabloya veri aktarır."""
        try:
            df = pd.read_csv(file_path, encoding='utf-8-sig')
            
            # Tabloya özel işlem mantığı
            if table_name == 'port_operations':
                # Tarih sütunlarını datetime objesine çevir
                for col in ['timestamp', 'arrival_date', 'departure_date']:
                    if col in df.columns:
                        df[col] = pd.to_datetime(df[col], errors='coerce') # Hatalı tarihleri NaT yapar
                        df[col] = df[col].replace({pd.NaT: None}) # NaT'leri None'a çevir

                # IMO numarası ve container_size için float'tan int'e güvenli dönüşüm
                for col_int in ['imo_number', 'container_size', 'weight_kg']:
                    if col_int in df.columns:
                        # Önce float'a çevir, NaN'ları None'a dönüştür, sonra int'e çevir (eğer None değilse)
                        df[col_int] = pd.to_numeric(df[col_int], errors='coerce').apply(lambda x: int(x) if pd.notna(x) else None)

                # Hazmat flag için boolean dönüşüm
                if 'hazmat_flag' in df.columns:
                    df['hazmat_flag'] = df['hazmat_flag'].astype(bool)

                # Her satırı tek tek ekle (PRIMARY KEY çakışmalarını yönetmek için)
                success_count = 0
                fail_count = 0
                for index, row in df.iterrows():
                    try:
                        self.add_port_operation(row.to_dict())
                        success_count += 1
                    except Exception as e:
                        # PRIMARY KEY çakışması durumunda güncelleme yap veya atla
                        if "duplicate key value violates unique constraint" in str(e):
                            print(f"Uyarı: Konteyner ID '{row['container_id']}' zaten mevcut. Güncelleniyor...")
                            try:
                                self.update_port_operation(row['container_id'], row.to_dict())
                                success_count += 1 # Güncelleme de başarılı sayılır
                            except Exception as update_e:
                                print(f"Konteyner ID '{row['container_id']}' güncellenirken hata: {update_e}")
                                fail_count += 1
                        else:
                            print(f"Konteyner ID '{row['container_id']}' eklenirken hata: {e}")
                            fail_count += 1
                return True, f"Başarılı: {success_count}, Hata: {fail_count}"
            
            elif table_name == 'vessel_tariffs':
                success_count = 0
                fail_count = 0
                for index, row in df.iterrows():
                    try:
                        self.add_or_update_vessel_tariff(row['vessel_name'], row['daily_rate'])
                        success_count += 1
                    except Exception as e:
                        print(f"Tarife eklenirken/güncellenirken hata ('{row['vessel_name']}'): {e}")
                        fail_count += 1
                return True, f"Başarılı: {success_count}, Hata: {fail_count}"
            
            else:
                raise ValueError(f"'{table_name}' tablosu için içe aktarma desteklenmiyor.")

        except FileNotFoundError:
            raise Exception("Dosya bulunamadı.")
        except pd.errors.EmptyDataError:
            raise Exception("CSV dosyası boş.")
        except Exception as e:
            raise Exception(f"CSV'den içe aktarılırken hata oluştu: {e}")

