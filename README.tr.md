# Akademik Bildiri Değerlendirme Portalı (YMH303)

Bir üniversite konferans değerlendirme sistemi için veritabanı projesi. İş kuralları
(İK-01 … İK-29) **doğrudan PostgreSQL tarafından** uygulanır; backend ve ekranlar bunun üzerinde çalışır.

| Üye    | Görev                                           | Test klasörü |
| ------ | ----------------------------------------------- | ------------ |
| Eyup   | G1. Hesaplar ve bildiri gönderimi               | `tests/t1`   |
| Kadir  | G2. Konferans kurulumu ve hakem atama           | `tests/t2`   |
| Sidney | G3. Kör değerlendirme, erişim güvenliği ve veri | `tests/t3`   |
| Selim  | G4. Kararlar, denetim kaydı ve entegrasyon      | `tests/t4`   |

---

## 1. Kurulum (bir kez, yaklaşık 15 dakika)

Gerekenler: **Git**, **Docker Desktop** (açık olmalı), **Python 3.11+**, **VS Code**.
Aşağıdaki komutlar Windows'ta VS Code terminali (PowerShell) içindir. macOS/Linux'ta
`Copy-Item` yerine `cp`, etkinleştirmek için `source .venv/bin/activate` kullanın.

```powershell
# 1. kodu indirin
cd $HOME\Documents
git clone https://github.com/Sidney-Reich/Akademik-Bildiri-Portali.git
cd Akademik-Bildiri-Portali

# 2. kendi ayar dosyanız (asla yüklenmez); parolayı değiştirebilirsiniz
Copy-Item .env.example .env

# 3. PostgreSQL 19'u Docker'da başlatın
docker compose up -d
docker compose ps                     # STATUS "healthy" olmalı

# 4. Python ortamı ve paketler
python -m venv .venv
.\.venv\Scripts\Activate.ps1          # komut satırı artık (.venv) ile başlar
pip install -r requirements.txt

# 5. veritabanını kurun ve testleri çalıştırın
python manage.py migrate
python manage.py test
```

Ardından klasörü VS Code'da açın: **File → Open Folder… → Akademik-Bildiri-Portali**.

**Sorun mu var?**

- `running scripts is disabled` → bir kez çalıştırın: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`
- `password authentication failed` → bilgisayarınızda kurulu başka bir PostgreSQL 5432 portunu kullanıyor.
  `.env` dosyanızda `POSTGRES_PORT=5433` yapın, sonra yeniden `docker compose up -d` çalıştırın.
- Dosyalar yanlış yerde oluşuyor → `pwd` çalıştırın; depo klasörünün içinde olmalısınız.

## 2. Her çalışma oturumunda

```powershell
cd $HOME\Documents\Akademik-Bildiri-Portali
.\.venv\Scripts\Activate.ps1
docker compose up -d
git checkout main
git pull
python manage.py migrate
```

## 3. Komutlar

| Komut                                   | Ne yapar                                                                                 |
| --------------------------------------- | ---------------------------------------------------------------------------------------- |
| `python manage.py migrate`              | `db/migrations` içindeki yeni dosyaları uygular                                          |
| `python manage.py status`               | uygulanmış ve bekleyen geçiş dosyalarını listeler                                        |
| `python manage.py seed`                 | başlangıç verisini yükler (`db/seed/seed_minimal.sql`)                                   |
| `python manage.py reset`                | veritabanını siler, sonra migrate + seed (sık kullanın)                                  |
| `python manage.py test`                 | tüm testleri çalıştırır; `test t2` tek bir görevi, `test test_schema.py` tek bir dosyayı |
| `python manage.py psql`                 | veritabanında SQL komut satırı açar (`\q` ile çıkılır)                                   |
| `uvicorn backend.app.main:app --reload` | backend'i başlatır; http://127.0.0.1:8000/docs adresini açın                             |

VS Code'da tablolara göz atmak ve SQL çalıştırmak için **PostgreSQL** eklentisini (Microsoft)
kurun ve `localhost`, port `5432`, veritabanı `portal`, `.env` dosyanızdaki kullanıcı ve parolayla bağlanın.

## 4. Nasıl çalışıyoruz

1. **Önce tablolar (25–26 Kasım).** Her üye kendi tablo dosyalarını yazar
   (sıralama `db/migrations/README.md` dosyasındadır). Bir tablo dosyası yalnızca
   `python manage.py test test_schema.py` kendi tabloları için geçtiğinde birleştirilir.
2. **Sonra kurallar (27 Kasım'dan itibaren).** Bir kural = yeni bir geçiş dosyası + o kuralı
   bozmaya çalışan bir test.
3. **Dallar (branch).** Asla doğrudan `main` üzerinde çalışmayın:
   ```
   git checkout -b t2/conference-tables
   ... çalışın, sonra:
   git add .
   git commit -m "T2: conference tables (002)"
   git push -u origin t2/conference-tables
   ```
   GitHub'da bir pull request açın. Testler geçtiğinde (GitHub bunları otomatik çalıştırır)
   ve bir takım arkadaşı onayladığında birleştirilir.
4. **Birleştirilmiş bir geçiş dosyasını asla düzenlemeyin**; yeni bir dosya ekleyin.
5. **Adlar görev önekiyle başlar:** `trg_t1_…`, `fn_t2_…`, `v_t3_…`, `idx_t4_…`.
6. **Her test sonucunu** `tests/results.md` dosyasına kaydedin.

## 5. Klasörler

```
backend/        FastAPI uygulaması (backend/app/main.py)
db/migrations/  veritabanını oluşturan ve değiştiren SQL dosyaları, sırayla uygulanır
db/seed/        tüm testlerin kullandığı başlangıç verisi
db/queries/     iş sorguları
docs/           ER ve EER diyagramları (draw.io ile açın)
frontend/       ekranlar
import/         DBLP içe aktarma (G3)
tests/          test_schema.py (tablo sözleşmesi), t1/ … t4/ (her üyenin testleri)
manage.py       proje komutları
```
