# Rehberlik servisi

Alperen Murat Leblebici, mevcut öğretmen girişinden kendi adıyla giriş yapar. Veritabanı başlangıcındaki kadro senkronizasyonu mevcut hesabını `rehber` rolüne taşır; şifresini değiştirmez. Diğer öğretmenlerin görevleri değişmez.

## Kullanım

1. **İçerik paylaş:** başlık, kategori, kısa açıklama; video/sunum veya yazılı rehber. İsteğe bağlı **Evde deneyelim** etkinliği.
2. **Alıcı seç:** tüm aktif sınıfların velileri, seçilen şubeler veya bir/çok öğrencinin veli hesabı. Sınıf düzeyine göndermek için o düzeydeki şubeleri seçin.
3. **Taslak / önizleme:** içerik ve isimli alıcı listesi kontrol edilir; taslak düzenlenebilir. Henüz velilere görünmez.
4. **Yayınla:** veli kütüphanesine eklenir; alıcılara birer bildirim kaydı oluşturulur. Mevcut aktif telefon aboneliklerine Web Push gönderimi başlatılır. Aynı yayına tekrar basmak bildirimleri çoğaltmaz.
5. **Geri bildirim:** sayfanın açılması, “İnceledim” ve “Evde uyguladık” ayrı ayrı tutulur. Açılması videonun tamamının izlendiği veya rehberin okunduğu anlamına gelmez.
6. **Görüşmeler:** veli genel bir konu ya da belirli içerik için talep gönderir. Rehber öğretmen durum ve veliye görünen yanıtı kaydeder. Bu talepler genel öğretmen görüşme tablosundan ayrıdır.
7. **Arşivle:** içerik ve dosya velilere kapanır; danışman ekranındaki kayıtlar/geri bildirimler korunur. Arşivden doğrudan tekrar yayınlama yoktur; yeniden paylaşım için yeni taslak hazırlanır.

## Dosyalar ve yayına geçiş

- Görsel (JPG, PNG, GIF, WebP), PDF, DOCX, XLSX/XLS, PPTX, MP3/M4A: en fazla 20 MB. MP4 / WebM / MOV / M4V: en fazla 100 MB. İstek üst sınırı 102 MB; yükleme sınırı ve dosya imzası sunucuda kontrol edilir. Eski DOC/PPT kabul edilmez (DOCX/PPTX olarak kaydedilmeli).
- Tüm dosyalar sayfa içinde önizlenir; indirme düğmesi yoktur. Dosya adresi doğrudan sekmede açılırsa (`Sec-Fetch-Dest: document`) 403 döner, yanıt her zaman `Content-Disposition: inline`'dır. Video/ses `controlslist="nodownload"` ile, görseller sağ tık/sürükleme kapalı gösterilir. Tarayıcıya gelen içerik ekran görüntüsü veya geliştirici araçlarıyla yine kaydedilebilir; bu bir caydırmadır, tam koruma değildir.
- PDF, yerel olarak sunulan PDF.js 6.3.289 ile sayfa sayfa çizilir. Lisansı `static/vendor/pdfjs/LICENSE` içindedir.
- Word `docx-preview` 0.4.1 (Apache-2.0) + JSZip 3.10.2, Excel SheetJS 0.20.3 (Apache-2.0, sayfa sekmeli), PowerPoint `pptx-preview` 1.0.7 (ISC, slayt slayt) ile tarayıcıda çizilir; hepsi `static/vendor/` altından yerel sunulur, dosya dış servise gönderilmez. Karmaşık animasyon/efektler PowerPoint'teki kadar birebir görünmeyebilir.
- Video kalitesi değiştirilmez; orijinal dosya aralık istekleriyle sunulur. Oynatım cihazın video biçimi/kodek desteğine bağlıdır.
- Dosyalar `static` içinde tutulmaz. Her dosya isteğinde rehber rolü veya öğrencinin yayın alıcısı olması doğrulanır; taslak/arşiv dosyaları veliye açılmaz.
- `REHBERLIK_DOSYA_KLASORU` verilmezse dosyalar veritabanının yanındaki `rehberlik-dosyalar` klasörüne kaydedilir. Mevcut Render yapılandırmasında bu **`/data/rehberlik-dosyalar`** olur; `/data` kalıcı disktir. Ayrı klasör ayarlanırsa kalıcı disk üzerinde olmalıdır.
- Dosyalar veritabanı yedeğinden ayrıdır. Yedeklemede hem veritabanını hem bu klasörü saklayın. Mevcut disk kapasitesi 1 GB; büyük videolar için kapasite takip edilmelidir.
- Telefon bildirimi mevcut Web Push/VAPID ayarlarına, aktif aboneliğe ve cihazın bildirim iznine bağlıdır. Yerel doğrulamada gerçek telefonlara gönderim kapatılmıştır; bildirim kayıtları ve yönlendirme akışı doğrulanmıştır.
- Bu çalışma canlı siteye gönderilmedi; uygulamanın güncel kodla yeniden başlatılması rol ve tablo geçişini uygular.

## Doğrulama

`python -m unittest discover -s tests -v`

Rehberlik testleri: özel alıcı/draft erişimi; şube/okul hedefleri; taslak düzenleme; dosya erişimi ve Range; arşiv; rol/CSRF; bozuk dosya ve alıcılar; geri bildirim/görüşme mahremiyeti; tekrar ve eşzamanlı yayınlamada tek bildirim; JavaScript modül MIME türü. Tarayıcıda PDF ve gerçek MP4 yükleme/oynatma, veli geri bildirimi, rehber yanıtı ve mobil görünüm denendi.
