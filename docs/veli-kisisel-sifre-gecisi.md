# Veli ilk giriş şifresi — hazırlık

Bu özellik varsayılan olarak kapalıdır. `VELI_KISISEL_SIFRE=1` yalnızca öğrenciye özel kodlar özel olarak dağıtıldıktan sonra açılmalıdır. Ortak şifre kişisel giriş modunda kabul edilmez. Öğretmen girişi değişmez.

`veli_auth.issue_code(ogrenci_id)` 30 gün geçerli rastgele bir kod üretir; veritabanında yalnızca hash saklar. Kod sadece çağırana döner; günlüklerde veya toplu herkese açık listelerde gösterilmemelidir. Yeni kod, önceki kodu ve bekleyen şifre belirleme işlemini geçersiz kılar. Kod üretimi ve dağıtım ekranı henüz bu değişikliğin kapsamında değildir; üretim veritabanında kod oluşturulmadı.

Kodla giriş panel oturumu açmaz; 10 dakika geçerli şifre belirleme oturumu açar. Veli 12–128 karakterlik yeni şifreyi iki kez yazar. CSRF doğrulamasından sonra şifre hash olarak kaydedilir; kod ve bekleyen işlem tek atomik güncellemeyle tüketilir. Ortak şifreyle bu işlemi başlatmak mümkün değildir. Beş hatalı giriş hesabı 15 dakika bekletir.

Dağıtım sonrası canlı geçişten önce eski veli oturumları ve Android cihaz anahtarlarının geçersizleştirilmesi ayrıca planlanmalıdır. Bu hazırlık mevcut girişleri veya cihazları kapatmaz. Hesap kurtarma yönetici arayüzü ve dağıtım kartları ayrı adımdır. Mevcut kişisel şifre, yeni geçici kod üretilmesiyle hemen iptal edilmez; yeni şifre kaydedilince değiştirilir.

Doğrulama: `python -m unittest discover -s tests -p test_parent_credentials.py -q`
