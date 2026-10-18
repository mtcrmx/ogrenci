# Veli ilk giriş şifresi

Kullanıcı tercihi: ayrı kod dağıtılmaz. Öğrenci numarası ve mevcut ortak veli şifresi, yalnızca kişisel şifre henüz belirlenmemişse şifre oluşturma akışını başlatır. Kişisel şifre kaydedilmeden panel açılmaz. Sonrasında ortak şifre o hesap için kabul edilmez.

Bu yöntem ilk giriş yapan kişinin gerçekten veli olduğunu doğrulamaz: öğrenci numarası ve ortak şifreyi bilen kişi henüz sahiplenilmemiş hesabın şifresini belirleyebilir. Bu sınır kullanıcıya açıklanmıştır.

Özellik varsayılan olarak açıktır (`VELI_KISISEL_SIFRE=1`). `0` yalnızca eski sisteme açıkça geri dönmek için kullanılmalıdır; ortak şifreyi yeniden etkinleştirir. Öğretmen girişi değişmez.

Şifre belirleme oturumu 10 dakika geçerlidir. Yeni şifre 12–128 karakter olmalıdır. CSRF ve şifre tekrarı kontrol edilir, şifre hash olarak saklanır. Beş hatalı girişten sonra 15 dakika bekleme uygulanır. Eski veli oturumları geçersizdir; şifre oluşturulduğunda eski Android cihaz anahtarları silinir. Şifre belirlememiş öğrencilerin eski cihaz anahtarları bilgi döndürmez.

`veli_auth.issue_code(ogrenci_id)` hesap kurtarma için 30 gün geçerli özel kod üretme altyapısıdır; normal ilk girişte kullanılmaz. Yönetici kurtarma arayüzü henüz yoktur. Şifre kaydetmek önceki kodu ve oturum sürümünü geçersiz kılar.

Doğrulama: `python -m unittest discover -s tests -p test_parent_credentials.py -q`. Eski testlerde doğrudan oturum yerleştiren fixture kontrolleri `VELI_KISISEL_SIFRE=0` ile çalıştırılır; credential testleri ayrıca özelliği açarak gerçek giriş ve eski oturum reddini doğrular.
