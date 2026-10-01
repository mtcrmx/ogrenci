# Ders sonuçları ve öğretmen işlem geçmişi

- Ortak arama ad, Türkçe harfler ve okul numarasıyla çalışır. LGS'de sadece 8. sınıflar aranır ve sonuç aynı LGS ekranını açar. Sonuç girişinde arama öğrencinin sonuç ekranını açar.
- `/lgs/kurum-pdf` yalnızca veritabanındaki Adem Akgül ve Metehan Cücen hesaplarına açıktır. Oturumdaki görünen ad tek başına yetki sağlamaz.
- `/sonuclar`: tüm sınıflar için tek ders testi veya seçilen derslerle deneme. Her dersin soru sayısı 1–500; boş sayısı otomatik. Yanlış götürme kuralı yok / 3 / 4. Tarih, negatif sayılar, eksik satırlar ve toplamlar sunucuda doğrulanır.
- Öğretmen kendi sonuçlarını düzenler. Kurum sonuçlarını yalnızca yetkili iki öğretmen düzenler. Kurum sınavının ortak adı/tarihi bireysel düzenlemede değiştirilmez.
- `/veli/sonuclar` yalnızca giriş yapan velinin öğrencisini gösterir. Derslerin doğru yüzdesi ve tarihsel gelişimi burada yer alır. LGS koçluğu, ders testlerini genel deneme toplamına katmaz; yalnızca aynı ders/soru/net kuralındaki denemeleri karşılaştırır.
- `/islem-gecmisi` öğretmenin kendi yeni ödev, kitap, davranış, puan ve sonuç işlemlerini gösterir. Haftalık kayıtların düzenleme bağlantısı mevcut takip ekranını açar. Yayınlanmış ödev ve sonuçların ayrı düzenleme ekranları vardır. Kitap onayı/puan değişikliğinde önce geri alıp yeniden girilebilir.

## Geri alma

Güncelleme sonrası öğretmen yazma istekleri, bağlantıya özel SQLite TEMP tetikleyicileriyle izlenir. Aynı isteğin kaynak kayıtları ve bağlı XP/sınıf puanı/rozet değişiklikleri tek işlemde gruplanır. Normal bakım ve veli yazmaları işlem geçmişi oluşturmaz.

Geri alma tek transaction içinde, satırların ters sırasıyla uygulanır. Her satırın mevcut değeri kayıtlı son durumla eşleşmek zorundadır. Sonradan başka bir değişiklik yapılmışsa transaction bütünüyle geri döner. Sonradan eklenen ödev onayları veya sınav ders satırları sessizce silinmez. Öğretmen başka öğretmenin işlemini geri alamaz. Geri alınmış işlem tekrar uygulanmaz.

Eski işlemlerin önceki durumu bilinmediği için bu güncellemeden önceki işlemler geçmişten geri alınamaz. Gönderilmiş telefon bildirimi geri çekilemez; etkilenen velilere düzeltme bildirimi gönderilir. Fiziksel dosyalar geri almada silinmez.

## Yayına alma

Yeni Python modülleri, şablonlar ve statik dosyalar birlikte yayınlanmalıdır. Veritabanı kolonları ve işlem geçmişi tabloları uygulama başlangıcında mevcut veriler korunarak eklenir. Veritabanı kopyası kod dağıtımıyla değiştirilmemelidir.

## Doğrulama

`python -m unittest discover -s tests`: arama, kurum yetkisi, farklı soru sayıları, veli analizi, sonuç düzenleme, sürüm çakışması, başka öğretmenin işlemi, kitap onayı/XP/rozet geri alma, kurum PDF yenileme geri alma ve ödev düzenleme senaryoları geçici veritabanında doğrulanır.
