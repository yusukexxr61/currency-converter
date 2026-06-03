import customtkinter as ctk  # Modern Tkinter arayüz kütüphanesi
import tkinter as tk  # Standart Tkinter kütüphanesi
from tkinter import messagebox  # Hata ve bilgi kutuları için
from PIL import Image, ImageTk  # Görsel işlemleri için
import os  # Dosya ve dizin işlemleri için
import json  # JSON dosya işlemleri için
import threading  # Çoklu iş parçacığı (thread) desteği
import time  # Zaman işlemleri için
import requests  # HTTP istekleri için
import matplotlib  # Grafik çizimi için
import matplotlib.pyplot as plt  # Grafik çizimi için
import matplotlib.animation as animation  # Grafik animasyonu için
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg  # Matplotlib grafiğini Tkinter'a gömmek için
import matplotlib.dates as mdates  # Tarih ekseni işlemleri için
from datetime import datetime, timedelta  # Tarih ve zaman işlemleri için
import numpy as np  # Sayısal işlemler için
import xml.etree.ElementTree as ET  # XML verisi işlemek için
import re  # Düzenli ifadeler için
import random  # Rastgele sayı üretmek için
import configparser  # INI dosyası okumak için
import sys  # Sistem işlemleri için

# Uygulama ayarları
ctk.set_appearance_mode("dark")  # Varsayılan tema: "dark" veya "light"
ctk.set_default_color_theme("blue")  # Varsayılan renk teması

class RGBAnimation:
    def __init__(self, canvas):
        self.canvas = canvas  # Arka plan animasyonu için canvas
        self.running = False  # Animasyonun çalışıp çalışmadığını belirten bayrak
        self.theme_mode = "dark"  # Varsayılan tema
        
    def set_theme(self, mode):
        """Tema modunu günceller."""
        self.theme_mode = mode
        self.update_background()
        
    def start(self):
        self.running = True
        self.update_background()
        
    def stop(self):
        self.running = False
        
    def update_background(self):
        """Arka plan rengini günceller."""
        if not self.running:
            return

        # Canvas boyutunu güncelle (Tkinter'ın boyut güncellemelerini uygula)
        self.canvas.update_idletasks()
        width = self.canvas.winfo_width()
        height = self.canvas.winfo_height()

        # Çok küçük boyutlarda çizim yapma (bozulmayı önle)
        if width < 10 or height < 10:
            self.canvas.configure(bg='#1a1a2e' if self.theme_mode == "dark" else '#f0f0f0')
            self.canvas.delete('all')
            return

        # Eğer canvas boyutları çok hızlı değişiyorsa (örn. tam ekran), bir sonraki event döngüsünde tekrar dene
        if not hasattr(self, '_last_size') or self._last_size != (width, height):
            self._last_size = (width, height)
            # Birkaç kez gecikmeli tekrar dene (tam ekran ve kapla için)
            self.canvas.after(50, self.update_background)
            self.canvas.after(150, self.update_background)
            self.canvas.after(300, self.update_background)

        # Canvas'ı temizle
        self.canvas.delete('all')

        # Tema rengine göre arka plan rengi
        if self.theme_mode == "dark":
            # Koyu tema için gradient
            for y in range(height):
                color = self._interpolate_color(
                    '#1a1a2e',
                    '#0f3460',
                    y / max(1, height-1)
                )
                self.canvas.create_line(0, y, width, y, fill=color)
        else:
            self.canvas.configure(bg='#f0f0f0')
            self.canvas.create_rectangle(0, 0, width, height, fill='#f0f0f0', outline='')
    
    def _interpolate_color(self, color1, color2, factor):
        """İki renk arasında geçiş yapar."""
        # Renkleri RGB bileşenlerine ayır
        r1, g1, b1 = int(color1[1:3], 16), int(color1[3:5], 16), int(color1[5:7], 16)
        r2, g2, b2 = int(color2[1:3], 16), int(color2[3:5], 16), int(color2[5:7], 16)
        
        # Renkleri karıştır
        r = int(r1 + (r2 - r1) * factor)
        g = int(g1 + (g2 - g1) * factor)
        b = int(b1 + (b2 - b1) * factor)
        
        # Hex renk koduna dönüştür
        return f'#{r:02x}{g:02x}{b:02x}'

class CurrencyDataProvider:
    """
    Para birimi verilerini sağlayan sınıf.
    TCMB API'sini kullanarak döviz kurlarını alır.
    """
    def get_frankfurter_rate(self, from_currency, to_currency):
        try:
            url = f"https://api.frankfurter.app/latest?from={from_currency}&to={to_currency}"
            response = requests.get(url, timeout=self.api_timeout)
            if response.status_code == 200:
                data = response.json()
                rate = data["rates"].get(to_currency)
                if rate is not None:
                    return rate
            return None
        except Exception as e:
            print(f"Frankfurter API hatası: {e}")
            return None

    def __init__(self):
        """CurrencyDataProvider sınıfını başlatır ve gerekli değişkenleri ayarlar."""
        self.cache = {}
        self.cache_time = {}
        self.cache_duration = 0  # Her zaman API'den çek, cache yok
        self.api_timeout = 10  # API istekleri için zaman aşımı süresi (saniye)
        self.max_retries = 3  # Maksimum yeniden deneme sayısı
        self.retry_delay = 2  # Yeniden denemeler arası bekleme süresi (saniye)
        
        # TCMB'den alınan para birimleri ve kodları
        self.currency_codes = {}
        self.update_currency_codes()
        
        # Gerçek zamanlı veri güncelleme için timer
        self.start_real_time_updates()
    
    def start_real_time_updates(self):
        """Gerçek zamanlı veri güncellemelerini başlatır."""
        def update_loop():
            while True:
                try:
                    self.update_currency_codes()
                    time.sleep(self.cache_duration)
                except Exception as e:
                    print(f"Gerçek zamanlı güncelleme hatası: {str(e)}")
                    time.sleep(5)  # Hata durumunda 5 saniye bekle
        
        threading.Thread(target=update_loop, daemon=True).start()
    
    def update_currency_codes(self):
        """TCMB'den para birimi kodlarını günceller."""
        try:
            data = self.fetch_tcmb_data()
            if data:
                for currency in data:
                    code = currency.get('code', '')
                    name = currency.get('name', '')
                    if code and name:
                        self.currency_codes[code] = name
                
                # TRY'yi ekle (TCMB listesinde yok)
                self.currency_codes['TRY'] = 'TÜRK LİRASI'
        except Exception as e:
            print(f"Para birimi kodları güncellenirken hata: {str(e)}")
            # Hata durumunda varsayılan para birimlerini ekle
            self.currency_codes = {
                'USD': 'ABD DOLARI',
                'EUR': 'EURO',
                'GBP': 'İNGİLİZ STERLİNİ',
                'TRY': 'TÜRK LİRASI',
                'JPY': 'JAPON YENİ',
                'CHF': 'İSVİÇRE FRANGI',
                'CAD': 'KANADA DOLARI',
                'AUD': 'AVUSTRALYA DOLARI',
                'CNY': 'ÇİN YUANI',
                'RUB': 'RUS RUBLESİ'
            }
    
    def fetch_tcmb_data(self):
        """TCMB'den güncel döviz kuru verilerini alır."""
        for attempt in range(self.max_retries):
            try:
                url = "https://www.tcmb.gov.tr/kurlar/today.xml"
                response = requests.get(url, timeout=self.api_timeout)
                
                if response.status_code != 200:
                    raise Exception(f"TCMB API yanıt kodu: {response.status_code}")
                
                # XML verisini parse et
                root = ET.fromstring(response.content)
                
                currencies = []
                for currency in root.findall('Currency'):
                    code = currency.get('CurrencyCode')
                    name = currency.find('CurrencyName').text
                    unit = int(currency.find('Unit').text)
                    
                    # Forex alış/satış değerlerini al
                    forex_buying = self._parse_rate(currency.find('ForexBuying').text)
                    forex_selling = self._parse_rate(currency.find('ForexSelling').text)
                    
                    # Birim başına değeri hesapla
                    rate_buying = forex_buying / unit
                    rate_selling = forex_selling / unit
                    
                    # Ortalama kur
                    rate_avg = (rate_buying + rate_selling) / 2
                    
                    currencies.append({
                        'code': code,
                        'name': name,
                        'unit': unit,
                        'forex_buying': forex_buying,
                        'forex_selling': forex_selling,
                        'rate_buying': rate_buying,
                        'rate_selling': rate_selling,
                        'rate_avg': rate_avg
                    })
                
                return currencies
            except Exception as e:
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay)
                    continue
                print(f"TCMB verileri alınırken hata: {str(e)}")
                return None
    
    def _parse_rate(self, rate_str):
        """
        Kur değerini parse eder.
        
        Args:
            rate_str (str): Kur değeri string'i
            
        Returns:
            float: Parse edilmiş kur değeri
        """
        if not rate_str or rate_str == "None":
            return 0.0
        
        # Nokta ve virgülleri düzelt
        rate_str = rate_str.replace(',', '.')
        
        try:
            return float(rate_str)
        except ValueError:
            return 0.0
    
    def get_rate(self, from_currency, to_currency):
        """
        İki para birimi arasındaki dönüşüm oranını alır.
        Artık exchangerate-api.com API'si ile gerçek zamanlı veri kullanılır.
        """
        cache_key = f"{from_currency}_{to_currency}"
        current_time = time.time()
        # Cache'de varsa ve güncel ise cache'den al
        if cache_key in self.cache and current_time - self.cache_time.get(cache_key, 0) < self.cache_duration:
            return self.cache[cache_key]
        api_key = None
        # Önce settings.json'dan oku
        settings_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "settings.json")
        if os.path.exists(settings_path):
            try:
                with open(settings_path, "r", encoding="utf-8") as f:
                    settings = json.load(f)
                    api_key = settings.get("exchangerate_api_key")
            except Exception:
                pass
        if not api_key:
            api_key = "af40c566d1659d18d592e7b3"
        try:
            if from_currency == to_currency:
                return 1.0
            url = f"https://v6.exchangerate-api.com/v6/{api_key}/latest/{from_currency}"
            response = requests.get(url, timeout=self.api_timeout)
            data = response.json()
            if data.get("result") == "success" and data.get("conversion_rates") and to_currency in data["conversion_rates"]:
                rate = data["conversion_rates"][to_currency]
                self.cache[cache_key] = rate
                self.cache_time[cache_key] = current_time
                return rate
            else:
                raise Exception("exchangerate-api.com API'den veri alınamadı")
        except Exception as e:
            print(f"exchangerate-api.com API hatası: {e}")
            try:
                messagebox.showwarning("Veri Uyarısı", "Gerçek zamanlı veri alınamadı, yedek veri gösteriliyor!")
            except:
                pass
            # Yedek olarak TCMB'den çek
            try:
                currencies = self.fetch_tcmb_data()
                if not currencies:
                    raise Exception("TCMB verileri alınamadı")
                from_curr_data = None
                to_curr_data = None
                for curr in currencies:
                    if curr['code'] == from_currency:
                        from_curr_data = curr
                    if curr['code'] == to_currency:

                        to_curr_data = curr
                if from_curr_data and to_curr_data:
                    rate = from_curr_data['rate_avg'] / to_curr_data['rate_avg']
                    self.cache[cache_key] = rate
                    self.cache_time[cache_key] = current_time
                    return rate
            except Exception as e2:
                print(f"TCMB yedeği de başarısız: {e2}")
                # Son fallback: Frankfurter API
                frankfurter_rate = self.get_frankfurter_rate(from_currency, to_currency)
                if frankfurter_rate is not None:
                    print("Frankfurter API ile veri alındı.")
                    self.cache[cache_key] = frankfurter_rate
                    self.cache_time[cache_key] = current_time
                    return frankfurter_rate
                raise Exception(f"Döviz kuru alınamadı: {str(e)} | Yedek TCMB: {str(e2)} | Frankfurter API başarısız")
    
    def convert(self, amount, from_currency, to_currency):
        """
        Para birimi dönüşümü yapar.
        
        Args:
            amount (float): Dönüştürülecek miktar
            from_currency (str): Kaynak para birimi kodu
            to_currency (str): Hedef para birimi kodu
            
        Returns:
            float: Dönüştürülmüş miktar
            
        Raises:
            ValueError: Miktar negatif veya sıfır ise hata fırlatır
        """
        if amount <= 0:
            raise ValueError("Miktar pozitif bir sayı olmalıdır")
        
        rate = self.get_rate(from_currency, to_currency)
        return amount * rate
    
    def get_available_currencies(self):
        """
        Kullanılabilir para birimlerini döndürür.
        
        Returns:
            list: Para birimi kodları listesi
        """
        # TCMB verilerini güncelle
        self.update_currency_codes()
        
        # Kodları döndür
        return list(self.currency_codes.keys())
    
    def fetch_collectapi_rate(self, from_currency, to_currency):
        """
        Collect API'den iki para birimi arasındaki kuru alır.
        API anahtarı settings.json veya config.ini dosyasından okunur.
        """
        api_key = None
        # Önce settings.json'dan oku
        settings_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "settings.json")
        if os.path.exists(settings_path):
            try:
                with open(settings_path, "r", encoding="utf-8") as f:
                    settings = json.load(f)
                    api_key = settings.get("collectapi_key")
            except Exception:
                pass
        # config.ini'den oku
        if not api_key:
            import configparser
            config = configparser.ConfigParser()
            config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.ini")
            if os.path.exists(config_path):
                config.read(config_path)
                api_key = config.get("API", "collectapi_key", fallback=None)
        if not api_key:
            print("Collect API anahtarı bulunamadı!")
            return None
        url = f"https://api.collectapi.com/economy/exchange?int=10&to={to_currency}&base={from_currency}"
        headers = {
            'content-type': "application/json",
            'authorization': f"apikey {api_key}"
        }
        try:
            response = requests.get(url, headers=headers, timeout=self.api_timeout)
            if response.status_code == 200:
                data = response.json()
                if data.get("success") and data["result"].get("data"):
                    return float(data["result"]["data"][0]["rate"])
            return None
        except Exception as e:
            print(f"Collect API hatası: {e}")
            return None

    def get_historical_rates(self, from_currency, to_currency, days=30):
        """
        Belirli bir tarih aralığı için geçmiş kur verilerini alır.
        Frankfurter API kullanılarak gerçek zamanlı veriler çekilir.
        """
        try:
            end_date = datetime.now().date()
            start_date = end_date - timedelta(days=days-1)
            
            # Frankfurter API kullan (daha güvenilir)
            url = f"https://api.frankfurter.app/{start_date.strftime('%Y-%m-%d')}..{end_date.strftime('%Y-%m-%d')}?from={from_currency}&to={to_currency}"
            
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            if data and "rates" in data:
                dates = []
                rates = []
                
                # Tarihleri sırala
                sorted_dates = sorted(data["rates"].keys())
                
                for date_str in sorted_dates:
                    date_obj = datetime.strptime(date_str, "%Y-%m-%d")
                    rate = data["rates"][date_str][to_currency]
                    dates.append(date_obj)
                    rates.append(rate)
                
                if dates and rates:
                    return dates, rates
            
            # Frankfurter API başarısız olursa, CollectAPI'yi dene
            return self._try_collect_api_historical(from_currency, to_currency, days)
        except Exception as e:
            print(f"Frankfurter API hatası: {e}")
            # Hata durumunda CollectAPI'yi dene
            return self._try_collect_api_historical(from_currency, to_currency, days)

    def _try_collect_api_historical(self, from_currency, to_currency, days=30):
        """
        CollectAPI kullanarak geçmiş kur verilerini almayı dener.
        """
        try:
            # CollectAPI anahtarını al
            api_key = None
            config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.ini")
            if os.path.exists(config_path):
                config = configparser.ConfigParser()
                config.read(config_path)
                api_key = config.get("API", "collectapi_key", fallback=None)
            
            if not api_key:
                print("Collect API anahtarı bulunamadı!")
                return self._generate_sample_data(from_currency, to_currency, days)
            
            # Son 30 günlük veri için bugünden başlayarak geriye doğru gidelim
            end_date = datetime.now().date()
            dates = []
            rates = []
            
            # CollectAPI tek seferde geçmiş verileri vermediği için
            # her gün için ayrı istek yapmalıyız (bu yavaş olabilir)
            for i in range(min(days, 30)):  # En fazla 30 gün
                current_date = end_date - timedelta(days=i)
                date_str = current_date.strftime("%Y-%m-%d")
                
                url = f"https://api.collectapi.com/economy/exchange?int=10&to={to_currency}&base={from_currency}"
                headers = {
                    'content-type': "application/json",
                    'authorization': f"apikey {api_key}"
                }
                
                response = requests.get(url, headers=headers, timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    if data.get("success") and data["result"].get("data"):
                        rate = float(data["result"]["data"][0]["rate"])
                        dates.append(datetime.combine(current_date, datetime.min.time()))
                        rates.append(rate)
                
                # API limit aşımını önlemek için kısa bir bekleme
                time.sleep(0.5)
            
            if dates and rates:
                # Tarihe göre sırala
                sorted_data = sorted(zip(dates, rates), key=lambda x: x[0])
                dates = [d for d, r in sorted_data]
                rates = [r for d, r in sorted_data]
                return dates, rates
            
            # Her iki API de başarısız olursa örnek veriler kullan
            messagebox.showwarning("API Uyarısı", "Gerçek zamanlı veriler alınamadı. Örnek veriler kullanılıyor.")
            return self._generate_sample_data(from_currency, to_currency, days)
        except Exception as e:
            print(f"CollectAPI hatası: {e}")
            messagebox.showwarning("API Uyarısı", f"API isteği başarısız oldu: {e}\nÖrnek veriler kullanılıyor.")
            return self._generate_sample_data(from_currency, to_currency, days)
            
    def _generate_sample_data(self, from_currency, to_currency, days=30):
        """
        API yanıt vermediğinde kullanılacak örnek veriler oluşturur.
        """
        end_date = datetime.now().date()
        dates = [end_date - timedelta(days=i) for i in range(days-1, -1, -1)]
        
        # Para birimlerine göre temel kur değeri belirle
        base_rate = 0.0
        if from_currency == "USD" and to_currency == "TRY":
            base_rate = 30.0
        elif from_currency == "EUR" and to_currency == "TRY":
            base_rate = 32.0
        elif from_currency == "USD" and to_currency == "EUR":
            base_rate = 0.92
        elif from_currency == "EUR" and to_currency == "USD":
            base_rate = 1.09
        else:
            base_rate = 1.0  # Diğer para birimleri için varsayılan değer
        
        # Gerçekçi dalgalanmalar ekle
        rates = []
        for i in range(days):
            # %5 dalgalanma ekle
            fluctuation = random.uniform(-0.05, 0.05)
            # Hafif yukarı trend ekle
            trend = i * 0.001
            rate = base_rate * (1 + fluctuation + trend)
            rates.append(rate)
        
        # datetime nesnelerine dönüştür
        dates = [datetime.combine(d, datetime.min.time()) for d in dates]
        
        return dates, rates

class CurrencyConverterApp(ctk.CTk):
    """
    Döviz çevirici uygulamasının ana sınıfı.
    Kullanıcı arayüzünü oluşturur ve tüm işlevselliği yönetir.
    """
    def __init__(self):
        """CurrencyConverterApp sınıfını başlatır ve arayüzü oluşturur."""
        super().__init__()
        
        # Global hata yakalayıcı ekleyin
        def handle_exception(exc_type, exc_value, exc_traceback):
            error_msg = f"Beklenmeyen hata: {exc_type.__name__}: {exc_value}"
            print(error_msg)
            try:
                messagebox.showerror("Uygulama Hatası", error_msg)
            except:
                pass
            return True  # Hatayı işlediğimizi belirt
        
        # Global hata yakalayıcıyı ayarla
        self.old_excepthook = sys.excepthook
        sys.excepthook = handle_exception
        
        # Ana pencere ayarları
        self.title("Döviz Çevirici")
        self.geometry("900x600")
        self.minsize(800, 550)
        
        # RGB animasyon için canvas
        self.animation_canvas = tk.Canvas(self, width=900, height=600, bg='#1E1E2E', highlightthickness=0)
        self.animation_canvas.place(x=0, y=0, relwidth=1, relheight=1)
        self.rgb_animation = RGBAnimation(self.animation_canvas)
        self.rgb_animation.start()
        
        # Pencere boyutu değiştiğinde arka planı güncelle (debounce ile)
        self._resize_after_id = None
        def on_resize_event(event):
            if self._resize_after_id is not None:
                self.after_cancel(self._resize_after_id)
            self._resize_after_id = self.after(120, self.rgb_animation.update_background)
        self.bind("<Configure>", on_resize_event)
        
        # Değişkenler
        self.data_provider = CurrencyDataProvider()
        self.from_currency = ctk.StringVar(value="USD")
        self.to_currency = ctk.StringVar(value="TRY")
        self.amount = ctk.StringVar(value="100")
        self.result = ctk.StringVar(value="0.00")
        self.conversion_rate = ctk.StringVar(value="1 USD = 0.00 TRY")
        
        # Popüler para birimleri
        self.popular_currencies = [
            f"{code} ({self.data_provider.currency_codes.get(code, code)})" for code in ["USD", "EUR", "GBP", "TRY", "JPY", "CAD", "AUD", "CHF", "CNY", "RUB"]
        ]
        # Tüm para birimleri
        self.all_currencies = [
            f"{code} ({self.data_provider.currency_codes.get(code, code)})" for code in self.data_provider.get_available_currencies()
        ]
        
        # Tema ayarları
        self.theme_mode = ctk.StringVar(value="dark")
        self.color_theme = ctk.StringVar(value="blue")
        
        # Ayarlar dosyası
        self.settings_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "settings.json")
        self.load_settings()
        
        # Arayüz oluşturma
        self.create_widgets()
        
        # İlk dönüşümü yap
        self.convert_currency()
        
        # Grafik penceresi referansı
        self.graph_window = None
        
        # Tema ayarları penceresi referansı
        self.theme_window = None
    
    def load_settings(self):
        """Kayıtlı ayarları yükler."""
        try:
            if os.path.exists(self.settings_file):
                with open(self.settings_file, 'r') as f:
                    settings = json.load(f)
                    
                    if 'theme_mode' in settings:
                        mode = settings['theme_mode']
                        # Geçerli tema modunu kontrol et
                        if mode in ["light", "dark", "system"]:
                            self.theme_mode.set(mode)
                            ctk.set_appearance_mode(mode)
                    
                    if 'color_theme' in settings:
                        color = settings['color_theme']
                        # Geçerli renk temasını kontrol et
                        if color in ["blue", "green", "dark-blue"]:
                            self.color_theme.set(color)
                            ctk.set_default_color_theme(color)
                    
                    if 'from_currency' in settings:
                        self.from_currency.set(settings['from_currency'])
                    
                    if 'to_currency' in settings:
                        self.to_currency.set(settings['to_currency'])
        except Exception as e:
            print(f"Ayarlar yüklenirken hata: {str(e)}")
            # Hata durumunda varsayılan ayarları kullan
            self.theme_mode.set("dark")
            self.color_theme.set("blue")
            ctk.set_appearance_mode("dark")
            ctk.set_default_color_theme("blue")
    
    def save_settings(self):
        """Ayarları kaydeder."""
        try:
            settings = {
                'theme_mode': self.theme_mode.get(),
                'color_theme': self.color_theme.get(),
                'from_currency': self.from_currency.get(),
                'to_currency': self.to_currency.get()
            }
            
            with open(self.settings_file, 'w') as f:
                json.dump(settings, f)
        except Exception as e:
            print(f"Ayarlar kaydedilirken hata: {str(e)}")
            # Hata durumunda kullanıcıya bildir
            self.show_error("Ayarlar kaydedilirken hata oluştu", str(e))
    
    def show_error(self, title, message):
        """
        Hata mesajı gösterir.
        
        Args:
            title (str): Hata başlığı
            message (str): Hata mesajı
        """
        try:
            messagebox.showerror(title, message)
        except:
            print(f"Hata: {title} - {message}")
    
    def _create_header_frame_widgets(self):
        """Header frame and its widgets."""
        self.header_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.header_frame.grid(row=0, column=0, padx=10, pady=(10, 5), sticky="ew")
        self.header_frame.grid_columnconfigure(0, weight=1)
        self.header_frame.grid_columnconfigure(1, weight=0)
        
        self.title_label = ctk.CTkLabel(
            self.header_frame, 
            text="Döviz Çevirici", 
            font=ctk.CTkFont(size=24, weight="bold")
        )
        self.title_label.grid(row=0, column=0, padx=10, pady=10, sticky="w")
        
        self.theme_button = ctk.CTkButton(
            self.header_frame,
            text="Tema Ayarları",
            command=self.open_theme_settings
        )
        self.theme_button.grid(row=0, column=1, padx=10, pady=10, sticky="e")

    def _create_from_frame_widgets(self):
        """Widgets for the 'from' currency panel."""
        self.from_frame = ctk.CTkFrame(self.converter_frame, fg_color="transparent")
        self.from_frame.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")
        self.from_frame.grid_columnconfigure(0, weight=1)
        
        self.from_label = ctk.CTkLabel(
            self.from_frame, 
            text="Dönüştürülecek", 
            font=ctk.CTkFont(size=14)
        )
        self.from_label.grid(row=0, column=0, padx=10, pady=(10, 5), sticky="w")
        
        self.from_currency_menu = ctk.CTkOptionMenu(
    self.from_frame,
    values=self.popular_currencies,
    variable=self.from_currency,
    command=self.on_currency_change,
    width=200,
    anchor="w"
)
        self.from_currency_menu.grid(row=1, column=0, padx=10, pady=5, sticky="ew")
        
        self.from_all_currencies_button = ctk.CTkButton(
            self.from_frame,
            text="Tüm Para Birimleri",
            command=lambda: self.show_all_currencies("from"),
            fg_color="transparent",
            border_width=1
        )
        self.from_all_currencies_button.grid(row=2, column=0, padx=10, pady=5, sticky="ew")
        
        self.amount_label = ctk.CTkLabel(
            self.from_frame, 
            text="Miktar", 
            font=ctk.CTkFont(size=14)
        )
        self.amount_label.grid(row=3, column=0, padx=10, pady=(15, 5), sticky="w")
        
        self.amount_entry = ctk.CTkEntry(
            self.from_frame,
            textvariable=self.amount,
            font=ctk.CTkFont(size=24, weight="bold"),
            width=200
        )
        self.amount_entry.grid(row=4, column=0, padx=10, pady=5, sticky="ew")
        self.amount_entry.bind("<KeyRelease>", lambda event: self.convert_currency())

    def _create_middle_frame_widgets(self):
        """Widgets for the middle (swap button) panel."""
        self.middle_frame = ctk.CTkFrame(self.converter_frame, fg_color="transparent")
        self.middle_frame.grid(row=0, column=1, padx=5, pady=10)
        
        self.swap_button = ctk.CTkButton(
            self.middle_frame,
            text="⇄",
            command=self.swap_currencies,
            width=40,
            height=40,
            font=ctk.CTkFont(size=20)
        )
        self.swap_button.grid(row=0, column=0, padx=5, pady=80)

    def _create_to_frame_widgets(self):
        """Widgets for the 'to' currency panel."""
        self.to_frame = ctk.CTkFrame(self.converter_frame, fg_color="transparent")
        self.to_frame.grid(row=0, column=2, padx=10, pady=10, sticky="nsew")
        self.to_frame.grid_columnconfigure(0, weight=1)
        
        self.to_label = ctk.CTkLabel(
            self.to_frame, 
            text="Dönüştürülmüş", 
            font=ctk.CTkFont(size=14)
        )
        self.to_label.grid(row=0, column=0, padx=10, pady=(10, 5), sticky="w")
        
        self.to_currency_menu = ctk.CTkOptionMenu(
    self.to_frame,
    values=self.popular_currencies,
    variable=self.to_currency,
    command=self.on_currency_change,
    width=200,
    anchor="w"
)
        self.to_currency_menu.grid(row=1, column=0, padx=10, pady=5, sticky="ew")
        
        self.to_all_currencies_button = ctk.CTkButton(
            self.to_frame,
            text="Tüm Para Birimleri",
            command=lambda: self.show_all_currencies("to"),
            fg_color="transparent",
            border_width=1
        )
        self.to_all_currencies_button.grid(row=2, column=0, padx=10, pady=5, sticky="ew")
        
        self.result_label = ctk.CTkLabel(
            self.to_frame, 
            text="Sonuç", 
            font=ctk.CTkFont(size=14)
        )
        self.result_label.grid(row=3, column=0, padx=10, pady=(15, 5), sticky="w")
        
        self.result_frame = ctk.CTkFrame(self.to_frame, fg_color=("gray90", "gray20"))
        self.result_frame.grid(row=4, column=0, padx=10, pady=5, sticky="ew")
        
        self.result_value = ctk.CTkLabel(
            self.result_frame,
            textvariable=self.result,
            font=ctk.CTkFont(size=24, weight="bold")
        )
        self.result_value.grid(row=0, column=0, padx=10, pady=10, sticky="w")

    def _create_converter_frame_widgets(self):
        """Converter frame and its sub-panels."""
        self.converter_frame = ctk.CTkFrame(self.main_frame)
        self.converter_frame.grid(row=1, column=0, padx=10, pady=10, sticky="nsew")
        self.converter_frame.grid_columnconfigure(0, weight=1)
        self.converter_frame.grid_columnconfigure(1, weight=0)
        self.converter_frame.grid_columnconfigure(2, weight=1)

        self._create_from_frame_widgets()
        self._create_middle_frame_widgets()
        self._create_to_frame_widgets()

    def _create_rate_frame_widgets(self):
        """Rate frame and its widgets."""
        self.rate_frame = ctk.CTkFrame(self.main_frame)
        self.rate_frame.grid(row=2, column=0, padx=10, pady=(0, 10), sticky="ew")
        self.rate_frame.grid_columnconfigure(0, weight=1)
        self.rate_frame.grid_columnconfigure(1, weight=1)
        
        self.rate_label = ctk.CTkLabel(
            self.rate_frame,
            textvariable=self.conversion_rate,
            font=ctk.CTkFont(size=16)
        )
        self.rate_label.grid(row=0, column=0, padx=20, pady=10, sticky="w")
        # Veri kaynağı etiketi
        self.source_label = ctk.CTkLabel(
            self.rate_frame,
            text="Veri kaynağı: exchangerate-api.com",
            font=ctk.CTkFont(size=10, slant="italic")
        )
        self.source_label.grid(row=1, column=0, padx=20, pady=(0, 5), sticky="w")
        
        self.graph_button = ctk.CTkButton(
            self.rate_frame,
            text="Kur Grafiği Göster",
            command=self.show_exchange_rate_graph
        )
        self.graph_button.grid(row=0, column=1, padx=20, pady=10, sticky="e")

    def _create_status_bar_widgets(self):
        """Status bar and its widgets."""
        self.status_frame = ctk.CTkFrame(self.main_frame, height=30, fg_color=("gray85", "gray25"))
        self.status_frame.grid(row=3, column=0, padx=10, pady=(0, 10), sticky="ew")
        
        self.status_label = ctk.CTkLabel(
            self.status_frame,
            text="Hazır",
            font=ctk.CTkFont(size=12)
        )
        self.status_label.grid(row=0, column=0, padx=10, pady=5, sticky="w")

    def create_widgets(self):
        """Arayüz bileşenlerini oluşturur ve yerleştirir."""
        # Ana çerçeve düzeni
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        
        # Ana içerik çerçevesi
        self.main_frame = ctk.CTkFrame(self)
        self.main_frame.grid(row=0, column=0, padx=20, pady=20, sticky="nsew")
        self.main_frame.grid_columnconfigure(0, weight=1)
        self.main_frame.grid_rowconfigure(0, weight=0)  # Başlık
        self.main_frame.grid_rowconfigure(1, weight=1)  # Dönüştürücü
        self.main_frame.grid_rowconfigure(2, weight=0)  # Dönüşüm oranı
        self.main_frame.grid_rowconfigure(3, weight=0)  # Durum çubuğu
        
        # Create widget sections
        self._create_header_frame_widgets()
        self._create_converter_frame_widgets()
        self._create_rate_frame_widgets()
        self._create_status_bar_widgets()
        
        # Yükleme animasyonu için değişkenler
        self.loading = False
        self.loading_dots = 0
    
    def on_currency_change(self, *args):
        # Seçilen değerden sadece kodu al
        from_code = self.from_currency.get().split()[0]
        to_code = self.to_currency.get().split()[0]
        self.from_currency.set(from_code)
        self.to_currency.set(to_code)
        self.convert_currency()
        self.save_settings()
    
    def show_all_currencies(self, target):
        """
        Tüm para birimleri penceresini gösterir.
        
        Args:
            target (str): Hedef seçim alanı ("from" veya "to")
        """
        # Tüm para birimleri penceresini oluştur
        currencies_window = ctk.CTkToplevel(self)
        currencies_window.title("Tüm Para Birimleri")
        currencies_window.geometry("400x500")
        currencies_window.transient(self)
        currencies_window.grab_set()
        
        # Arama çerçevesi
        search_frame = ctk.CTkFrame(currencies_window)
        search_frame.pack(fill="x", padx=10, pady=10)
        
        search_var = ctk.StringVar()
        search_entry = ctk.CTkEntry(search_frame, placeholder_text="Para birimi ara...", textvariable=search_var, width=300)
        search_entry.pack(padx=10, pady=10, fill="x", expand=True)
        
        # Para birimleri listesi çerçevesi
        list_frame = ctk.CTkScrollableFrame(currencies_window)
        list_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Para birimleri butonları
        currency_buttons = []
        
        def update_list(*args):
            search_text = search_var.get().upper()
            for button in currency_buttons:
                button.pack_forget()
            
            for button in currency_buttons:
                if search_text in button.cget("text"):
                    button.pack(fill="x", padx=5, pady=2)
        
        def select_currency(currency_code):
            if target == "from":
                self.from_currency.set(currency_code)
            else:
                self.to_currency.set(currency_code)
            currencies_window.destroy()
            self.convert_currency()
            self.save_settings()
        
        for currency in self.all_currencies:
            btn = ctk.CTkButton(
                list_frame, 
                text=currency, 
                command=lambda c=currency: select_currency(c),
                anchor="w",
                height=30
            )
            btn.pack(fill="x", padx=5, pady=2)
            currency_buttons.append(btn)
        
        search_var.trace_add("write", update_list)
        search_entry.focus()
    
    def swap_currencies(self):
        """Para birimlerini birbiriyle değiştirir."""
        # Para birimlerini değiştir
        from_curr = self.from_currency.get()
        to_curr = self.to_currency.get()
        
        # Animasyon efekti
        self.from_currency_menu.configure(state="disabled")
        self.to_currency_menu.configure(state="disabled")
        
        # Değişim animasyonu
        def animate_swap():
            self.from_currency.set(to_curr)
            self.to_currency.set(from_curr)
            time.sleep(0.3)
            self.from_currency_menu.configure(state="normal")
            self.to_currency_menu.configure(state="normal")
            self.convert_currency()
            self.save_settings()
        
        threading.Thread(target=animate_swap).start()
    
    def convert_currency(self):
        """Para birimi dönüşümünü başlatır."""
        # Yükleme animasyonunu başlat
        self.start_loading_animation("Dönüştürülüyor")
        
        # Dönüşüm işlemini arka planda yap
        threading.Thread(target=self._perform_conversion).start()
    
    def _perform_conversion(self):
        """Dönüşüm işlemini gerçekleştirir."""
        try:
            # Girilen miktarı al
            try:
                amount_str = self.amount.get().replace(',', '.')
                if not amount_str:
                    self.result.set("0.00")
                    self.conversion_rate.set("Miktar giriniz")
                    self.stop_loading_animation("Miktar giriniz")
                    return
                
                amount_value = float(amount_str)
                if amount_value <= 0:
                    self.result.set("0.00")
                    self.conversion_rate.set("Miktar pozitif olmalıdır")
                    self.stop_loading_animation("Hata: Miktar pozitif olmalıdır")
                    return
            except ValueError:
                self.result.set("0.00")
                self.conversion_rate.set("Geçersiz miktar")
                self.stop_loading_animation("Hata: Geçersiz miktar")
                return
            
            from_curr = self.from_currency.get()
            to_curr = self.to_currency.get()
            
            # Dönüşüm yap
            try:
                converted_amount = self.data_provider.convert(amount_value, from_curr, to_curr)
                rate = self.data_provider.get_rate(from_curr, to_curr)
                
                # Sonuçları güncelle
                self.result.set(f"{converted_amount:.2f}")
                self.conversion_rate.set(f"1 {from_curr} = {rate:.4f} {to_curr}")
                self.stop_loading_animation("Dönüşüm tamamlandı")
            except Exception as e:
                self.result.set("Hata")
                self.conversion_rate.set(f"Dönüşüm hatası")
                self.stop_loading_animation(f"Hata: {str(e)}")
        except Exception as e:
            self.stop_loading_animation(f"Hata: {str(e)}")
    
    def start_loading_animation(self, message):
        """
        Yükleme animasyonunu başlatır.
        
        Args:
            message (str): Yükleme mesajı
        """
        self.loading = True
        self.loading_dots = 0
        
        def animate():
            if not self.loading:
                return
            
            dots = "." * self.loading_dots
            self.status_label.configure(text=f"{message}{dots}")
            
            self.loading_dots = (self.loading_dots + 1) % 4
            self.after(300, animate)
        
        animate()
    
    def stop_loading_animation(self, message):
        """
        Yükleme animasyonunu durdurur.
        
        Args:
            message (str): Gösterilecek durum mesajı
        """
        self.loading = False
        self.status_label.configure(text=message)
    
    def show_exchange_rate_graph(self):
        """Döviz kuru grafiğini gösterir."""
        try:
            if self.graph_window is not None:
                try:
                    plt.close('all')
                    self.graph_window.destroy()
                except:
                    pass
                self.graph_window = None
            
            from_curr = self.from_currency.get()
            to_curr = self.to_currency.get()
            
            # Grafik penceresini oluştur
            self.graph_window = ctk.CTkToplevel(self)
            self.graph_window.title(f"{from_curr}/{to_curr} Kur Grafiği")
            self.graph_window.geometry("1000x800")
            self.graph_window.transient(self)
            
            # Pencere kapatıldığında grafikleri temizle
            def on_closing():
                plt.close('all')
                self.graph_window.destroy()
                self.graph_window = None
            
            self.graph_window.protocol("WM_DELETE_WINDOW", on_closing)
            
            # Ana çerçeve
            main_frame = ctk.CTkFrame(self.graph_window)
            main_frame.pack(fill="both", expand=True, padx=10, pady=10)
            
            # Zaman aralığı seçimi
            time_frame = ctk.CTkFrame(main_frame)
            time_frame.pack(fill="x", padx=5, pady=5)
            
            time_var = ctk.StringVar(value="30")  # Varsayılan 30 gün
            
            # Canvas referansını tut
            canvas_ref = [None]
            
            def update_graph(*args):
                try:
                    # Yükleme mesajı göster
                    self.start_loading_animation("Grafik oluşturuluyor...")
                    
                    # Önceki grafikleri temizle
                    plt.close('all')
                    
                    days = int(time_var.get())
                    # Son günlerin verilerini al
                    dates, rates = self.data_provider.get_historical_rates(from_curr, to_curr, days)

                    # DATES'i datetime nesnesine dönüştür
                    dates = [datetime.strptime(str(d), "%Y-%m-%d") if isinstance(d, str) else d for d in dates]

                    if not dates or not rates:
                        messagebox.showerror("Hata", "Kur verileri alınamadı!")
                        self.stop_loading_animation("Grafik oluşturulamadı")
                        return
                    
                    # Matplotlib figürü oluştur - DPI değerini düşürerek performansı artır
                    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10), dpi=80)
                    fig.patch.set_facecolor('#2b2b2b' if self.theme_mode.get() == "dark" else '#f0f0f0')
                    
                    # Her iki grafik için ortak ayarlar
                    for ax in [ax1, ax2]:
                        ax.set_facecolor('#2b2b2b' if self.theme_mode.get() == "dark" else '#f0f0f0')
                        ax.grid(True, linestyle='--', alpha=0.7)
                        ax.tick_params(colors='white' if self.theme_mode.get() == "dark" else 'black')
                        for spine in ax.spines.values():
                            spine.set_edgecolor('white' if self.theme_mode.get() == "dark" else 'black')
                    
                    # Çizgi grafiği (üst) - marker sayısını azalt
                    if len(dates) > 30:
                        marker_every = len(dates) // 15  # Daha az marker göster
                    else:
                        marker_every = 1
                        
                    line = ax1.plot(dates, rates, color='#1f6aa5', linewidth=2, 
                                   marker='o', markersize=4, markevery=marker_every)
                    ax1.set_title(f'{from_curr}/{to_curr} Kur Değişimi', 
                                 color='white' if self.theme_mode.get() == "dark" else 'black', pad=20)
                    ax1.set_ylabel('Kur Değeri', color='white' if self.theme_mode.get() == "dark" else 'black')
                    
                    # Son noktayı vurgula
                    ax1.plot(dates[-1], rates[-1], 'o', color='#ff5722', markersize=8)
                    
                    # Modern bar chart (bottom)
                    from matplotlib.patches import FancyBboxPatch
                    import numpy as np
                    
                    # Kısa zaman aralıkları için tüm verileri göster
                    if len(dates) <= 10:  # 10 veya daha az veri noktası varsa
                        bar_dates = dates
                        bar_rates = rates
                    elif len(dates) > 30:
                        # Çubuk sayısını azalt
                        step = len(dates) // 30
                        bar_dates = dates[::step]
                        bar_rates = rates[::step]
                        
                        # Son değeri ekle
                        if bar_dates[-1] != dates[-1]:
                            bar_dates = list(bar_dates) + [dates[-1]]
                            bar_rates = list(bar_rates) + [rates[-1]]
                    else:
                        bar_dates = dates
                        bar_rates = rates

                    bar_count = len(bar_dates)  # Çubuk (bar) sayısını al
                    bar_width = max(0.2, min(0.95, 0.95 - (bar_count * 0.01)))  # Çubuk genişliğini dinamik olarak ayarla (çok fazla çubuk olursa incelmesin)
                    bar_colors = plt.cm.viridis(np.linspace(0.2, 0.8, bar_count))  # Çubuklar için renk gradyanı oluştur
                    bars = ax2.bar(bar_dates, bar_rates, width=bar_width, color=bar_colors, alpha=0.85, zorder=3)  # Modern ve dolgun çubuk grafiği çiz

                    for bar in bars:
                        height = bar.get_height()  # Çubuğun yüksekliğini al
                        ax2.annotate(f'{height:.2f}',
                                     xy=(bar.get_x() + bar.get_width() / 2, height),  # Çubuğun üstüne değer yaz
                                     xytext=(0, 5),
                                     textcoords="offset points",
                                     ha='center', va='bottom', fontsize=9, color='#444')  # Yazı ayarları

                    ax2.spines['top'].set_visible(False)  # Üst kenarlığı gizle
                    ax2.spines['right'].set_visible(False)  # Sağ kenarlığı gizle
                    ax2.grid(axis='y', linestyle='--', alpha=0.2, zorder=0)  # Y eksenine hafif grid ekle

                    ax2.set_title(f'{from_curr}/{to_curr} Günlük Değişim', color='white' if self.theme_mode.get() == "dark" else 'black', pad=20)  # Başlık
                    ax2.set_xlabel('Tarih', color='white' if self.theme_mode.get() == "dark" else 'black')  # X ekseni başlığı
                    ax2.set_ylabel('Kur Değeri', color='white' if self.theme_mode.get() == "dark" else 'black')  # Y ekseni başlığı

                    # Tarih formatını ayarla
                    plt.xticks(rotation=45)
                    fig.autofmt_xdate()
                    
                    # Fare ile veri noktası üzerine gelindiğinde tooltip göster
                    # Sadece üstteki çizgi grafik için tooltip ekle
                    annot = ax1.annotate("", xy=(0,0), xytext=(15,15), textcoords="offset points",
                                        bbox=dict(boxstyle="round", fc="w"),
                                        arrowprops=dict(arrowstyle="->"))
                    annot.set_visible(False)

                    def update_annot(ind):
                        x, y = dates[ind["ind"][0]], rates[ind["ind"][0]]
                        annot.xy = (x, y)
                        text = f"Tarih: {x.strftime('%d.%m.%Y')}\nKur: {y:.4f}"
                        annot.set_text(text)
                        annot.get_bbox_patch().set_facecolor("#f0f0f0")
                        annot.get_bbox_patch().set_alpha(0.9)

                    def hover(event):
                        vis = annot.get_visible()
                        if event.inaxes == ax1:
                            cont, ind = line[0].contains(event)
                            if cont:
                                update_annot(ind)
                                annot.set_visible(True)
                                fig.canvas.draw_idle()
                            else:
                                if vis:
                                    annot.set_visible(False)
                                    fig.canvas.draw_idle()

                    fig.canvas.mpl_connect("motion_notify_event", hover)
                    
                    # Önceki canvas'ı temizle
                    if canvas_ref[0] is not None:
                        canvas_ref[0].get_tk_widget().destroy()
                    
                    # Grafikleri canvas'a yerleştir
                    canvas = FigureCanvasTkAgg(fig, master=main_frame)
                    canvas.draw()
                    canvas.get_tk_widget().pack(fill="both", expand=True, padx=5, pady=5)
                    canvas_ref[0] = canvas
                    
                    # Yükleme mesajını kaldır
                    self.stop_loading_animation("Grafik hazır")
                    
                except Exception as e:
                    messagebox.showerror("Hata", f"Grafik oluşturulurken hata: {str(e)}")
                    self.stop_loading_animation("Grafik oluşturulamadı")
            
            # Zaman aralığı butonları
            time_ranges = {
                "7": "1 Hafta",
                "30": "1 Ay",
                "90": "3 Ay",
                "180": "6 Ay",
                "365": "1 Yıl"
            }

            # Modern butonlar için çerçeve ve seçili buton referansı
            button_frame = ctk.CTkFrame(time_frame, fg_color="transparent")
            button_frame.pack(fill="x", padx=5, pady=5)
            selected_btn = [None]

            def on_time_btn_click(days, btn):
                time_var.set(days)
                update_graph()
                # Tüm butonları varsayılana döndür
                for child in button_frame.winfo_children():
                    if isinstance(child, ctk.CTkButton):
                        child.configure(fg_color="#1f6aa5", hover_color="#174a7c")
                # Seçili butonu vurgula
                btn.configure(fg_color="#ff5722", hover_color="#e65100")
                selected_btn[0] = btn

            for days, text in time_ranges.items():
                btn = ctk.CTkButton(
                    button_frame,
                    text=text,
                    fg_color="#1f6aa5",
                    hover_color="#174a7c",
                    text_color="white",
                    corner_radius=15,
                    font=ctk.CTkFont(size=14, weight="bold"),
                    width=90,
                    height=36
                )
                btn.configure(command=lambda d=days, b=btn: on_time_btn_click(d, b))
                btn.pack(side="left", expand=True, padx=5)
                # Varsayılan seçili buton
                if days == time_var.get():
                    btn.configure(fg_color="#ff5722", hover_color="#e65100")
                    selected_btn[0] = btn

            # İlk grafiği çiz
            update_graph()
            
            # Grafik penceresinde de veri kaynağı etiketi ekle
            source_label = ctk.CTkLabel(
                main_frame,
                text="Veri kaynağı: Frankfurter API, CollectAPI (yedek) | API yanıt vermediğinde örnek veriler kullanılır",
                font=ctk.CTkFont(size=12, weight="bold"),
                text_color="#1bc47d"
            )
            source_label.pack(anchor="n", padx=5, pady=(0, 10))
            
        except Exception as e:
            messagebox.showerror("Hata", f"Grafik penceresi açılırken hata: {str(e)}")
            if self.graph_window and self.graph_window.winfo_exists():
                plt.close('all')
                self.graph_window.destroy()
                self.graph_window = None
    
    def open_theme_settings(self):
        """Tema ayarları penceresini açar."""
        try:
            if self.theme_window is not None:
                try:
                    self.theme_window.destroy()
                except:
                    pass
                finally:
                    self.theme_window = None
            
            # Tema ayarları penceresini oluştur
            self.theme_window = ctk.CTkToplevel(self)
            self.theme_window.title("Tema Seçimi")
            self.theme_window.geometry("300x150")
            self.theme_window.transient(self)
            self.theme_window.grab_set()
            
            # Pencere kapatıldığında
            self.theme_window.protocol("WM_DELETE_WINDOW", lambda: self.on_theme_window_close())
            
            # Ana çerçeve
            main_frame = ctk.CTkFrame(self.theme_window)
            main_frame.pack(fill="both", expand=True, padx=20, pady=20)
            
            # Tema modu değişkeni
            current_mode = self.theme_mode.get()
            mode_var = ctk.StringVar(value=current_mode)
            
            # Tema butonları çerçevesi
            button_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
            button_frame.pack(fill="x", padx=20, pady=10)
            
            def update_buttons():
                selected_mode = mode_var.get()
                for btn in button_frame.winfo_children():
                    if isinstance(btn, ctk.CTkButton):
                        btn_text = btn.cget("text").lower()
                        if (btn_text == "açık tema" and selected_mode == "light") or \
                           (btn_text == "koyu tema" and selected_mode == "dark"):
                            btn.configure(fg_color="#ff5722", hover_color="#e65100")  # Turuncu vurgu rengi
                        else:
                            btn.configure(fg_color="#1f6aa5", hover_color="#174a7c")  # Mavi varsayılan renk
            
            # Açık tema butonu
            light_button = ctk.CTkButton(
                button_frame,
                text="Açık Tema",
                command=lambda: [mode_var.set("light"), update_buttons()]
            )
            light_button.pack(side="left", expand=True, padx=5)
            
            # Koyu tema butonu
            dark_button = ctk.CTkButton(
                button_frame,
                text="Koyu Tema",
                command=lambda: [mode_var.set("dark"), update_buttons()]
            )
            dark_button.pack(side="left", expand=True, padx=5)
            
            # Uygula butonu
            apply_button = ctk.CTkButton(
                main_frame,
                text="Uygula",
                command=lambda: self.apply_theme(mode_var.get())
            )
            apply_button.pack(pady=20)
            
            # İlk güncellemeleri yap
            update_buttons()
            
        except Exception as e:
            self.show_error("Tema Ayarları Hatası", f"Tema ayarları penceresi açılırken hata oluştu: {str(e)}")
            if self.theme_window and self.theme_window.winfo_exists():
                self.theme_window.destroy()
                self.theme_window = None
    
    def apply_theme(self, mode):
        """
        Tema değişikliklerini uygular.
        
        Args:
            mode (str): Tema modu ("light" veya "dark")
        """
        try:
            # Geçerli tema modunu kontrol et
            if mode not in ["light", "dark"]:
                mode = "dark"  # Varsayılan tema
            
            # Tema değişkenlerini güncelle
            self.theme_mode.set(mode)
            
            # CustomTkinter tema ayarları
            ctk.set_appearance_mode(mode)
            
            # RGB animasyonunun temasını güncelle
            if hasattr(self, 'rgb_animation'):
                self.rgb_animation.set_theme(mode)
            
            # Animasyon efekti
            self.start_loading_animation("Tema uygulanıyor")
            
            # Tema penceresini kapat (önce kapat, sonra değişiklikleri uygula)
            if self.theme_window and self.theme_window.winfo_exists():
                self.theme_window.destroy()
                self.theme_window = None
            
            # Değişiklikleri kaydet ve tamamla
            self.save_settings()
            self.after(500, lambda: self.stop_loading_animation("Tema değiştirildi"))
        except Exception as e:
            self.show_error("Tema Hatası", f"Tema uygulanırken hata oluştu: {str(e)}")
            # Hata durumunda varsayılan temaya dön
            self.theme_mode.set("dark")
            ctk.set_appearance_mode("dark")
    
    def on_theme_window_close(self):
        """Tema ayarları penceresi kapatıldığında çağrılır."""
        try:
            if self.theme_window and self.theme_window.winfo_exists():
                self.theme_window.destroy()
        except:
            pass
        finally:
            self.theme_window = None
    
    def _on_mousewheel(self, event):
        """Fare tekerleği ile kaydırma işlemi."""
        # Kaydırma özelliğini kaldır
        pass
        
    def on_closing(self):
        try:
            # Tüm matplotlib figürlerini kapat
            plt.close('all')
            
            # Tüm alt pencereleri kapat
            if self.graph_window and self.graph_window.winfo_exists():
                self.graph_window.destroy()
            
            if self.theme_window and self.theme_window.winfo_exists():
                self.theme_window.destroy()
            
            # Ayarları kaydet
            self.save_settings()
            
            # Animasyonları durdur
            if hasattr(self, 'rgb_animation'):
                self.rgb_animation.stop()
            
            # Sys.excepthook'u eski haline getir
            if hasattr(self, 'old_excepthook'):
                sys.excepthook = self.old_excepthook
            
            # Uygulamayı kapat
            self.quit()
            self.destroy()
        except Exception as e:
            print(f"Kapatma hatası: {e}")
            self.quit()
            self.destroy()

if __name__ == "__main__":
    try:
        app = CurrencyConverterApp()
        app.protocol("WM_DELETE_WINDOW", app.on_closing)
        app.mainloop()
    except Exception as e:
        print(f"Uygulama başlatılırken hata: {str(e)}")
        messagebox.showerror("Uygulama Hatası", f"Uygulama başlatılırken hata oluştu: {str(e)}")
