"""5. sınıf okuma kitaplarının içerikleri, kazanımları ve değer rozetleri.

Değerler Türkiye Yüzyılı Maarif Modeli Erdem-Değer-Eylem Çerçevesi'ndeki 20 değerdir.
"""
import re

DEGERLER: dict[str, tuple[str, str]] = {
    "Adalet": ("⚖️", "Herkese hakkını vermek."),
    "Aile Bütünlüğü": ("🏡", "Ailesine bağlı olmak, ailesini korumak."),
    "Çalışkanlık": ("🐝", "Emek vermek, azimle çalışmak."),
    "Dostluk": ("🤝", "İyi günde kötü günde arkadaşının yanında olmak."),
    "Duyarlılık": ("🌱", "Doğaya, canlılara ve topluma karşı duyarlı olmak."),
    "Dürüstlük": ("💎", "Doğruyu söylemek, doğru davranmak."),
    "Estetik": ("🎨", "Güzelliği, sanatı ve yaratıcılığı fark etmek."),
    "Mahremiyet": ("🔒", "Kendi ve başkalarının özel alanına saygı göstermek."),
    "Merhamet": ("🕊️", "Canlılara şefkatle yaklaşmak."),
    "Mütevazılık": ("🌾", "Alçakgönüllü olmak, kendini üstün görmemek."),
    "Özgürlük": ("🦅", "Kendi yolunu seçebilmek, özgür düşünmek."),
    "Sabır": ("⏳", "Zorluklar karşısında dayanmak, pes etmemek."),
    "Sağlıklı Yaşam": ("🍎", "Bedenini ve ruhunu iyi korumak."),
    "Saygı": ("🙏", "Farklılıklara ve başkalarının haklarına saygı duymak."),
    "Sevgi": ("❤️", "İnsanları, canlıları ve yaşamı sevmek."),
    "Sorumluluk": ("🧭", "Görevini üstlenmek, sözünü tutmak."),
    "Tasarruf": ("🐷", "Sahip olduklarını israf etmeden kullanmak."),
    "Temizlik": ("🧼", "Kendini ve çevresini temiz tutmak."),
    "Vatanseverlik": ("🇹🇷", "Vatanını, milletini ve tarihini sevmek."),
    "Yardımseverlik": ("🤲", "Karşılık beklemeden iyilik yapmak."),
}

_KOD_HARF = str.maketrans("çğıöşüÇĞİÖŞÜâîû", "cgiosuCGIOSUaiu")


def deger_kodu(deger: str) -> str:
    return re.sub(r"[^a-z]+", "_", deger.translate(_KOD_HARF).lower()).strip("_")


def deger_bilgisi(deger: str) -> tuple[str, str]:
    return DEGERLER.get(deger, ("🏅", ""))


def _anahtar(ad: str) -> str:
    ad = (ad or "").replace("I", "ı").replace("İ", "i").lower().translate(_KOD_HARF)
    return re.sub(r"[^a-z0-9]+", " ", ad).strip()


KITAP_ICERIK: dict[str, dict] = {
    'Bana Derler Küp Cadısı': {
        "yazar": 'Nur İçözü',
        "konu": "Kitabın kahramanı, kendisine 'küp cadısı' denen Tuğçe adlı neşeli bir kız. Tuğçe, ağabeyinin önerisiyle izciler gibi her akşam 'Bugün ne iyilik ettim?' diye düşünür ve yaptıklarını defterlere yazar. Kitapta bu günlüklerden, ailesiyle ve çevresiyle yaşadığı komik olaylardan ve iyiliklerinden oluşan maceraları okuruz.",
        "mesaj": 'Yazar, küçük de olsa her gün yapılan iyiliklerin hayatı güzelleştirdiğini ve başkalarının ne dediğine takılmadan iyilik yapmaya devam etmenin değerli olduğunu anlatıyor.',
        "ulastiklarin": [
            "Gün sonunda 'Bugün kime iyilik ettim?' diye düşünmenin seni daha iyi bir insan yaptığını fark ettin.",
            'Başkaları sana farklı bir lakap taksa bile kendin olmaya ve doğru bildiğini yapmaya devam edebileceğini gördün.',
            'Yaşadıklarını günlüğe yazmanın hem eğlenceli hem de kendini tanımanın güzel bir yolu olduğunu öğrendin.',
        ],
        "bilgiler": [
            "İzcilerin 'her gün bir iyilik yap' diye bilinen bir geleneği vardır.",
        ],
        "deger": 'Yardımseverlik',
        "deger_neden": "Tuğçe'nin her gün birilerine iyilik yapmayı kendine görev edinmesi sana yardımseverliğin küçük adımlarla başladığını gösterdi.",
        "kaynaklar": [
            'https://www.kitapyurdu.com/kitap/bana-derler-kup-cadisi/102073.html',
            'https://www.kitapstore.com/urun/99134/kitap/altin-kitaplar/nur-icozu/bana-derler-kup-cadisi/',
            'https://dipnotski.com/2017/02/28/nur-icozu-bana-derler-kup-cadisi-2007/',
            'https://www.kitapova.com/bana-derler-kup-cadisi',
        ],
    },
    'Karne Hediyesi At Kestanesi': {
        "yazar": 'Miyase Sertbarut',
        "konu": 'Suphi, çalışmadan sınavlardan en yüksek notu almayı hayal eden bir öğrencidir; babası da ona her dönem sonunda karne hediyesi olarak at kestanesi toplar. Suphi her sınavdan önce kurnazca planlar yapıp hileli yollara başvurur, ama bu planlar hep başına iş açar. Okul müdürü onu odasına çağırdığında işler değişmeye başlar.',
        "mesaj": 'Yazar, kestirme ve hileli yolların insanı başarıya değil sorunlara götürdüğünü; gerçek başarının emekle ve dürüstlükle geldiğini mizahla anlatıyor.',
        "ulastiklarin": [
            'Kopya ve hile gibi kolay yolların sonunda insanın başını derde soktuğunu gülerek fark ettin.',
            'Öğrenmenin, not almaktan çok daha değerli olduğunu düşündün.',
            'Hata yapan birinin de doğru yolu bulup değişebileceğini gördün.',
        ],
        "bilgiler": [
        ],
        "deger": 'Dürüstlük',
        "deger_neden": "Suphi'nin hileli planlarının hep ters tepmesi sana dürüst olmanın her zaman en doğru yol olduğunu hatırlattı.",
        "kaynaklar": [
            'https://www.kitapyurdu.com/kitap/karne-hediyesi-at-kestanesi/576902.html',
            'https://www.iyikitap.net/2021/06/01/suslu-puslu-paketteki-at-kestaneleri/',
            'https://1000kitap.com/kitap/karne-hediyesi-at-kestanesi--277413',
        ],
    },
    'Yürek Dede ile Padişah': {
        "yazar": 'Cahit Zarifoğlu',
        "konu": 'Yaşlı ve yoksul ama gönlü zengin Yürekdede ile eşi Ayşe Nine, eşeklerini kaybedince küçük bir deve alır ve her yıl olduğu gibi yaylaya doğru yola çıkarlar. Yolda karşılaştıkları atlıları misafir eder, onları doyurmak için tek develerini keserler; oysa bu misafirlerin arasında kılık değiştirmiş padişah da vardır. Yürekdede daha sonra şehre, padişahın namaz kıldırdığı camiye gider ve orada önemli bir karar verir.',
        "mesaj": 'Yazar, gerçek zenginliğin gönülde olduğunu; cömertliğin, misafirperverliğin ve dünya malına gönül bağlamamanın insanı yücelttiğini anlatıyor.',
        "ulastiklarin": [
            'Az şeyi olan birinin bile elindekini gönülden paylaşabileceğini gördün.',
            'Misafiri en güzel şekilde ağırlamanın ne kadar değerli bir davranış olduğunu fark ettin.',
            'Makam ve zenginliğin geçici, iyiliğin ise kalıcı olduğunu düşündün.',
        ],
        "bilgiler": [
            'Eski zamanlarda bazı padişahlar, halkın nasıl yaşadığını görmek için kılık değiştirerek (tebdil-i kıyafet) dolaşırdı.',
            "Anadolu'da bazı aileler yazın serin yaylalara göç eder, kışı köylerinde geçirirdi.",
        ],
        "deger": 'Mütevazılık',
        "deger_neden": "Yürekdede'nin dünya malına değer vermeyip padişahtan bile bir şey istememesi sana alçakgönüllü olmanın güzelliğini gösterdi.",
        "kaynaklar": [
            'https://www.beyanyayinlari.com/kitap/yurekdede-ile-padisah-9789754731279',
            'https://dergipark.org.tr/tr/download/article-file/726655',
            'https://kitap.yazarokur.com/yurekdede-ile-padisah',
            'https://www.liseedebiyat.com/ktap-oezetler/14229-yurek-dede-ile-padisah-czarifoglu.html',
        ],
    },
    'Sadako': {
        "yazar": 'Eleanor Coerr',
        "konu": "Kitap, Japonya'nın Hiroşima kentinde yaşamış Sadako Sasaki adlı kızın gerçek hikâyesine dayanır. Okulunun atletizm takımında koşan, enerjik bir kız olan Sadako, atom bombasının yıllar sonra ortaya çıkan etkisi yüzünden lösemiye yakalanır. Hastanede, bin kâğıt turna katlayanın dileğinin gerçekleşeceğine dair Japon inancını öğrenir ve umutla turna katlamaya başlar.",
        "mesaj": 'Yazar, savaşın en çok masum çocuklara zarar verdiğini ve en zor anlarda bile umudu ve cesareti korumanın insanı güçlü kıldığını anlatıyor.',
        "ulastiklarin": [
            'Zor bir durumda umudunu kaybetmemenin ne kadar büyük bir cesaret olduğunu fark ettin.',
            'Savaşların insanlara ve özellikle çocuklara verdiği zararı düşünerek barışın değerini anladın.',
            'Sevdiklerimizin zor zamanında yanında olmanın onlara güç verdiğini gördün.',
        ],
        "bilgiler": [
            'Japon geleneğine göre kâğıttan bin turna kuşu katlayan kişinin dileğinin gerçekleşeceğine inanılır.',
            "İkinci Dünya Savaşı'nda, 1945 yılında Japonya'nın Hiroşima kentine atom bombası atılmıştır.",
            "Kâğıt turna kuşu bugün dünyada barışın simgesi olarak bilinir; Hiroşima'da Sadako anısına bir anıt vardır.",
        ],
        "deger": 'Sabır',
        "deger_neden": "Sadako'nun hasta yatağında bile turnaları tek tek, sabırla katlaması sana umudun sabırla büyüdüğünü gösterdi.",
        "kaynaklar": [
            'https://www.beyazbalina.com.tr/urun/sadako-ve-kagittan-bin-turna-kusu-yenilenmis-baski',
            'https://tr.wikipedia.org/wiki/Sadako_ve_K%C3%A2%C4%9F%C4%B1ttan_Bin_Turna_Ku%C5%9Fu',
        ],
    },
    'Hachiko': {
        "yazar": 'Leslea Newman',
        "konu": "Kitap, Japonya'da yaşamış Akita cinsi köpek Hachiko'nun gerçek hikâyesine dayanır. Hachiko her gün sahibi Profesör Ueno'yu Shibuya tren istasyonuna kadar uğurlar, akşam da aynı saatte onu karşılamaya gider. Bir gün profesör geri dönmez; Hachiko ise yıllarca istasyona gidip beklemeyi sürdürür ve bu bağlılığı çevresindeki insanları derinden etkiler.",
        "mesaj": 'Yazar, sevginin ve sadakatin ne kadar güçlü olabileceğini, bir hayvanın bağlılığının insanların hayatını bile değiştirebileceğini anlatıyor.',
        "ulastiklarin": [
            'Hayvanların da sevgi ve bağlılık gösterebildiğini, onların duygularına saygı duymamız gerektiğini fark ettin.',
            'Sevdiklerine bağlı kalmanın ve onlara vefa göstermenin ne kadar değerli olduğunu düşündün.',
            'Küçük bir canlının sevgisinin bile insanların kalbine dokunabileceğini gördün.',
        ],
        "bilgiler": [
            "Hachiko, 1923-1935 yılları arasında Japonya'da yaşamış gerçek bir köpektir.",
            "Akita, Japonya'ya özgü bir köpek cinsidir.",
            "Hachiko'nun beklediği Shibuya istasyonu Tokyo'dadır ve orada onun anısına bir heykel bulunur.",
        ],
        "deger": 'Sevgi',
        "deger_neden": "Hachiko'nun sahibini yıllarca beklemesi sana gerçek sevginin zamanla bitmeyen bir bağ olduğunu gösterdi.",
        "kaynaklar": [
            'https://lesleakids.com/books-for-kids-teens/middle-grade-novels/hachiko-waits/',
            'https://www.hiperkitap.com/Book/Index/BOOK2018121311010000000354',
            'https://www.beyazbalina.com.tr/urun/hachiko',
            'https://iodergi.com/haciko/',
        ],
    },
    'Dünyayı Bisikletle Dolaşan Çocuk': {
        "yazar": 'Alastair Humphreys',
        "konu": "Kâşif olup dünyayı dolaşmayı hayal eden Tom, onunla alay eden sınıf arkadaşlarına yanıldıklarını kanıtlamak için bisikletine atlayıp yola çıkar. İngiltere'den başlayan yolculuğu onu Afrika'ya, Mısır, Sudan ve Etiyopya gibi ülkelerden geçerek kıtanın sonuna kadar götürür. Yolda zorluklarla karşılaşır, farklı insanlarla tanışır ve eğlenceli maceralar yaşar.",
        "mesaj": 'Yazar, hayallerin peşinden cesaretle gitmenin ve başkalarının alaylarına aldırmadan kararlı olmanın insanı büyük başarılara taşıyabileceğini anlatıyor.',
        "ulastiklarin": [
            'Başkaları inanmasa bile kendi hayalinin peşinden gidebileceğini fark ettin.',
            'Farklı ülkeleri ve kültürleri tanımanın dünyaya bakışını zenginleştirdiğini gördün.',
            'Zorluklar karşısında pes etmeyip yola devam etmenin ne kadar değerli olduğunu anladın.',
        ],
        "bilgiler": [
            'Yazar Alastair Humphreys, gerçek hayatta dört yıl boyunca bisikletle dünyayı dolaşmış bir gezgindir.',
            "Afrika'ya bisikletle giden bir yol Mısır, Sudan ve Etiyopya gibi ülkelerden geçer.",
            "Masailer, Doğu Afrika'da yaşayan bir halktır.",
        ],
        "deger": 'Özgürlük',
        "deger_neden": "Tom'un alay edilmesine aldırmadan kendi yolunu seçip hayalindeki yolculuğa çıkması sana özgürce hayal kurmanın gücünü gösterdi.",
        "kaynaklar": [
            'https://www.beyazbalina.com.tr/urun/dunyayi-bisikletle-dolasan-cocuk-1-afrika-yolunda',
            'https://www.beyazbalinatoptan.com.tr/content/images/product/pdf/9789759995850.pdf',
            'https://www.beyazbalina.com.tr/marka/alastair-humphreys',
        ],
    },
    'Matematik Romanı: Şifrelerin Peşinde İstanbul': {
        "yazar": 'Hasan Topdemir',
        "konu": "Bir gün bütün sınıf arkadaşları ve öğretmenleri donup kalır, yaşadıkları yerde zaman durur. Nehir, Efe ve Cafer, zamanı yeniden işletmek için İstanbul'un önemli mekânlarına gizlenmiş şifreleri bulup çözmeye çalışır. Macera boyunca matematik bilgilerini kullanarak ipuçlarını takip ederler.",
        "mesaj": 'Yazar, matematiğin sadece derste değil, hayatın içinde ve bulmaca çözerken de işe yaradığını; birlikte düşünerek zor sorunların üstesinden gelinebileceğini anlatıyor.',
        "ulastiklarin": [
            'Matematiğin sıkıcı değil, heyecanlı bir macera kadar eğlenceli olabileceğini fark ettin.',
            'Arkadaşlarınla birlikte düşünüp çalışınca zor şifrelerin bile çözülebileceğini gördün.',
            'Şehrindeki ve ülkendeki tarihî mekânları merak edip tanımak istedin.',
        ],
        "bilgiler": [
        ],
        "deger": 'Çalışkanlık',
        "deger_neden": "Nehir, Efe ve Cafer'in şifreleri çözmek için pes etmeden düşünüp uğraşması sana emeğin ve azmin sonuç getirdiğini gösterdi.",
        "kaynaklar": [
            'https://www.beyazbalina.com.tr/urun/matematik-romani-1-sifrelerin-pesinde-istanbul',
            'https://www.pandora.com.tr/kitap/sifrelerin-pesinde-istanbul-matematik-romani-1/773107',
        ],
    },
    'Yüz Elbisenin Sırrı': {
        "yazar": 'Eleanor Estes',
        "konu": "Wanda her gün okula aynı eski ve solmuş mavi elbiseyle gelir ama evinde 'sıra sıra dizili' yüz elbisesi olduğunu söyler. Sınıftaki kızlar ona inanmaz; Peggy bunu Wanda'yla her gün alay ettikleri bir oyuna çevirir. Peggy'nin en iyi arkadaşı Maddy bu durumdan içten içe rahatsız olsa da sesini çıkaracak cesareti bulamaz; bir gün Wanda okula gelmez ve kızlar yüz elbiseyle ilgili gerçeği öğrenir.",
        "mesaj": 'Yazar, alay etmenin ve bir haksızlık karşısında susmanın insanları nasıl incittiğini; anlayış, şefkat ve cömertliğin önemini anlatıyor.',
        "ulastiklarin": [
            'Birini dış görünüşüne veya kıyafetine göre yargılamanın ne kadar yanlış olduğunu fark ettin.',
            'Bir arkadaşına haksızlık yapıldığında susmak yerine ona destek olmanın cesaret istediğini anladın.',
            'Karşındakinin yerine kendini koymanın, yani empati kurmanın önemini düşündün.',
        ],
        "bilgiler": [
        ],
        "deger": 'Saygı',
        "deger_neden": "Wanda'ya yapılan alayların onu nasıl üzdüğünü görmek sana her insanın farklılıklarıyla saygıyı hak ettiğini hatırlattı.",
        "kaynaklar": [
            'https://www.kitapstore.com/urun/423445/kitap/beyaz-balina-yayinlari/eleanor-estes/yuz-elbisenin-sirri/',
            'https://1000kitap.com/kitap/yuz-elbisenin-sirri--161484',
            'https://www.beyazbalinatoptan.com.tr/kitap/beyaz-balina-yayinlari/yuz-elbisenin-sirri/9786051880730',
        ],
    },
    'Kum Saati': {
        "yazar": 'Fatih Tuncay',
        "konu": "Emre, babasını iki yıl önce bir laboratuvar patlamasında kaybettiğini düşünen, bu yüzden içine kapanmış bir çocuktur. Okulun yeni rehber öğretmeninin önerisiyle babasının gönderdiği ama hiç açmadığı hediyeler açılır ve aralarından çıkan kum saatinin gizemli şifreler taşıdığı anlaşılır. Emre ve arkadaşları bu şifrelerin peşine düşerek Antalya'dan Konya'ya uzanan heyecanlı bir maceraya atılır.",
        "mesaj": 'Yazar, dostluğun, dayanışmanın ve kendine güvenin insanı en zor durumlardan bile çıkarabileceğini ve zamanı iyi kullanmanın önemini anlatıyor.',
        "ulastiklarin": [
            'Arkadaşlarınla dayanışma içinde olunca tek başına aşamayacağın zorlukları aşabileceğini gördün.',
            'Korkularınla yüzleşmenin ve kendine güvenmenin seni güçlendirdiğini fark ettin.',
            'Zamanın çok değerli olduğunu ve onu iyi kullanman gerektiğini düşündün.',
        ],
        "bilgiler": [
            'Kum saati, kumun bir hazneden diğerine akmasıyla zamanı ölçen eski bir araçtır.',
        ],
        "deger": 'Dostluk',
        "deger_neden": 'Emre ve arkadaşlarının birbirine destek olarak şifreleri çözmesi sana gerçek dostluğun zor zamanlarda belli olduğunu gösterdi.',
        "kaynaklar": [
            'https://www.bilgiyayinevi.com.tr/kum-saati-1',
            'https://dersturkce.com/anasayfa/yazigoster/KUM-SAATI-TANITIMI-OZETIFATIH-TUNCAY',
            'https://elektrikelektronikegitimi.blogspot.com/2019/05/kum-saati-fatih-tuncay-kitabnn-ozeti.html',
        ],
    },
    'Zaman Bisikleti': {
        "yazar": 'Bilgin Adalı',
        "konu": "Yağmur ile Damla adlı iki kardeş, eski bir bisikleti bilgisayara bağlayarak insanları geçmişe götürebilen bir zaman bisikleti icat eder. Babalarıyla birlikte yüz bin yıl öncesine, Antalya'daki Karain Mağarası'nın yakınına giderler ve orada ilk insanları görürler. Mağarada yaşayan, gördüklerinden yeni buluşlar çıkaran Çuka ile Anin kardeşlerle tanışırlar.",
        "mesaj": 'Yazar, merakın ve yaratıcılığın insanlığı ilk çağlardan bugüne taşıdığını; geçmişi tanımanın bugünü anlamamıza yardım ettiğini anlatıyor.',
        "ulastiklarin": [
            'İlk insanların da senin gibi merak ederek ve deneyerek yeni şeyler bulduğunu fark ettin.',
            'Hayal gücünü kullanarak yeni icatlar düşünmenin ne kadar heyecan verici olduğunu gördün.',
            'Tarih öncesi çağlara ve insanlığın geçmişine karşı merak duydun.',
        ],
        "bilgiler": [
            "Antalya'daki Karain Mağarası, Türkiye'de ilk insanların yaşadığı en eski yerleşim yerlerinden biridir.",
            'Bisikletlerdeki dinamo, pedal çevrildikçe elektrik üretir.',
        ],
        "deger": 'Estetik',
        "deger_neden": "Yağmur ile Damla'nın ve Çuka ile Anin'in yaratıcı buluşları sana hayal gücünün ve yaratıcılığın güzelliğini gösterdi.",
        "kaynaklar": [
            'https://www.canyayinlari.com/zaman-bisikleti-9789750703508',
            'https://www.birazoku.com/zaman-bisikleti',
            'https://www.kitapzen.com/bilgin-adali/zaman-bisikleti-uclemesi-kutulu-set.htm',
        ],
    },
    'Domates Saçlı Kız': {
        "yazar": 'Sevim Ak',
        "konu": "Hikâye, Çürük Yumurta Kenti'nde evlerden belge aşırıp okuyan Tiktak ve Tıktık adlı iki geveze karganın konuşmaları üzerinden anlatılır. Kargaların okuduğu yaşam öyküsünde, yetiştirme yurdunda büyüyen ve ip örmeyi çok seven Güneş adlı kızın annesine kavuşması anlatılır. Güneş yeni evine ve ailesine alışmakta zorlanır, ama zamanla ailenin bir parçası olduğunu hissetmeye başlar.",
        "mesaj": 'Yazar, bir aileye ait olmanın, sevilmenin ve kabul görmenin önemini; yeni duruma alışmanın zaman ve sabır gerektirdiğini hem hüzünlü hem komik bir dille anlatıyor.',
        "ulastiklarin": [
            'Yeni bir ortama alışmanın zaman alabileceğini ve bunun çok doğal olduğunu fark ettin.',
            'Ailenin ve sevgi dolu bir yuvanın insana ne kadar güç verdiğini düşündün.',
            'Farklı yerlerde büyüyen çocukların duygularını anlamaya çalıştın.',
        ],
        "bilgiler": [
        ],
        "deger": 'Aile Bütünlüğü',
        "deger_neden": "Güneş'in annesine ve ailesine kavuşup onlarla bağ kurması sana ailenin bir arada olmasının değerini gösterdi.",
        "kaynaklar": [
            'https://getem.boun.edu.tr/?q=node%2F10584',
            'https://kitap.yazarokur.com/domates-sacli-kiz',
            'https://kitapdiyari.com.tr/roman/domates-sacli-kiz/',
        ],
    },
    'Martıya Uçmayı Öğreten Kedi': {
        "yazar": 'Luis Sepúlveda',
        "konu": "Denize dökülen petrolden zehirlenen martı Kengah, son gücüyle Hamburg limanında bir balkona ulaşır ve yumurtasını kara kedi Zorba'ya emanet eder. Zorba ona yumurtayı yemeyeceğine, yavru çıkana kadar ona bakacağına ve yavruya uçmayı öğreteceğine söz verir. Yumurtadan çıkan ve Zorba'yı annesi sanan yavru martı Şanslı'yı, Zorba liman kedisi dostlarıyla birlikte büyütür ve verdiği sözü tutmaya çalışır.",
        "mesaj": 'Yazar, birbirinden çok farklı canlıların da birbirini sevip sayabileceğini, verilen sözün tutulması gerektiğini ve insanların doğaya verdiği zararı anlatıyor.',
        "ulastiklarin": [
            'Verdiğin bir sözü, zor olsa bile tutmanın ne kadar değerli olduğunu fark ettin.',
            'Senden farklı olanı sevmenin ve ona destek olmanın güzelliğini gördün.',
            'Denizleri kirletmenin canlılara ne kadar zarar verdiğini düşünerek doğayı korumanın önemini anladın.',
        ],
        "bilgiler": [
            'Denize dökülen petrol, deniz kuşlarının tüylerine yapışarak uçmalarını engeller ve onları zehirler.',
            "Hamburg, Almanya'da Elbe Nehri üzerinde kurulmuş büyük bir liman kentidir; Elbe, Kuzey Denizi'ne dökülür.",
        ],
        "deger": 'Sorumluluk',
        "deger_neden": "Zorba'nın Kengah'a verdiği sözü tutmak için yavru martıyı büyütüp ona uçmayı öğretmeye çalışması sana sorumluluk almanın ne demek olduğunu gösterdi.",
        "kaynaklar": [
            'https://www.kitapyurdu.com/kitap/martiya-ucmayi-ogreten-kedi/16956.html',
            'https://dergipark.org.tr/tr/download/article-file/3586944',
            'https://pazartesi14.com/2021/04/10/martiya-ucmayi-ogreten-kedi/',
        ],
    },
    "Büyük Atatürk'ten Küçük Öyküler 1": {
        "yazar": 'Süleyman Bulut',
        "konu": "Kitap, Atatürk'ün hayatından seçilmiş onlarca kısa öyküden oluşuyor. Mustafa Kemal'in nasıl Atatürk olduğunu, sevdiği atını, köpeği Foks'un komik hâllerini, kesilen iğde ağacını arayışını, çiftçilik serüvenlerini ve en sevdiği çiçek olan al karanfilin öyküsünü anlatıyor.",
        "mesaj": "Yazar, Atatürk'ü yalnızca büyük bir lider olarak değil; hayvanları, doğayı ve insanları seven sıcak bir insan olarak da tanıtmak istiyor.",
        "ulastiklarin": [
            "Atatürk'ü büyük bir komutan olmanın yanında sevgi dolu, meraklı ve doğayı seven bir insan olarak da tanıdın.",
            'Ülkemizin bugünlere nasıl bir emekle geldiğini küçük öyküler sayesinde daha iyi anladın.',
            'Büyük insanların hayatındaki küçük anların da çok şey öğretebileceğini fark ettin.',
        ],
        "bilgiler": [
            "Atatürk'ün en sevdiği çiçeğin al karanfil olduğu bilinir.",
            "Atatürk'ün Foks adında bir köpeği vardı.",
        ],
        "deger": 'Vatanseverlik',
        "deger_neden": "Atatürk'ün hayatından öyküler okuyarak vatanı için neler yaptığını öğrendin ve ülkene olan sevgin güçlendi.",
        "kaynaklar": [
            'https://www.kitapdegisimi.com/kitap/buyuk-ataturk-ten-kucuk-oykuler-1/221',
            'https://canlikitap.aynitap.com/kitap/buyuk-ataturkten-kucuk-oykuler-1/',
            'https://books.google.com/books/about/B%C3%BCy%C3%BCk_Atat%C3%BCrk_ten_K%C3%BC%C3%A7%C3%BCk_%C3%96yk%C3%BCler.html?id=3ik0CgAAQBAJ',
        ],
    },
    'Kitaplardan Korkan Çocuk': {
        "yazar": 'Susanna Tamaro',
        "konu": 'Sekiz yaşındaki Leopoldo (Leopold) kitaplardan çok korkar; çünkü kitabı açınca harfler gözünde kara lekeler gibi uçuşur. Doğum gününde koşu ayakkabısı beklerken kitap hediye edilince çok üzülür, ailesinin baskısına dayanamayıp evden kaçar. Parkta tanıştığı yaşlı, görme engelli bir adamla yaşadıkları, onun kitaplara bakışını değiştirmeye başlar.',
        "mesaj": 'Yazar, bir çocuğun davranışının ardındaki gerçek nedeni anlamak için onu dinlemek ve onun gözünden bakmak gerektiğini; kitap sevgisinin zorlamayla değil, anlayışla doğduğunu anlatıyor.',
        "ulastiklarin": [
            'Birinin bir şeyden neden korktuğunu anlamak için önce onu dinlemenin önemini fark ettin.',
            'Zorlandığın bir konuyu saklamak yerine anlatmanın sorunları çözmeye yardım ettiğini gördün.',
            'Kitapların korkulacak değil, yeni dünyalara açılan kapılar olabileceğini hissettin.',
        ],
        "bilgiler": [
        ],
        "deger": 'Saygı',
        "deger_neden": "Leopoldo'nun hikâyesiyle, herkesin duygularına ve farklı ihtiyaçlarına saygı göstermenin insanları anlamanın ilk adımı olduğunu gördün.",
        "kaynaklar": [
            'https://kitapdiyari.com.tr/hikayeler/kitaplardan-korkan-cocuk/',
            'https://kitap.yazarokur.com/kitaplardan-korkan-cocuk',
            'https://dergipark.org.tr/tr/pub/chedar/article/413021',
            'https://litopya.com/kitap/kitaplardan-korkan-cocuk-susanna-tamaro',
        ],
    },
    'Küçük Kara Balık': {
        "yazar": 'Samed Behrengi',
        "konu": "Denizin dibindeki yaşlı bir balık, torunlarına Küçük Kara Balık'ın masalını anlatır. Küçük Kara Balık, yaşadığı derenin nereye aktığını merak eder ve annesiyle komşularının korkutmalarına rağmen denizi görmek için yola çıkar. Yolculuğunda iribaşlar, yengeç, kertenkele ve balıkçıl gibi canlılarla karşılaşır ve cesaretiyle zorlukları aşmaya çalışır.",
        "mesaj": 'Yazar, merak etmenin, sorgulamanın ve hayallerin peşinden cesaretle gitmenin önemini; birlik olunca büyük zorlukların bile aşılabileceğini anlatıyor.',
        "ulastiklarin": [
            'Merak ettiğin şeyleri sorgulamanın ve öğrenmek istemenin çok değerli olduğunu fark ettin.',
            'Korkulara rağmen hayallerinin peşinden gitmenin cesaret istediğini anladın.',
            'Küçük olanların bile birlik olduklarında büyük zorlukları aşabileceğini gördün.',
        ],
        "bilgiler": [
            'İribaşlar, kurbağaların yavrularıdır; büyüyünce kurbağaya dönüşürler.',
            'Pelikanların gagalarının altında, yakaladıkları balıkları topladıkları esnek bir kese bulunur.',
        ],
        "deger": 'Özgürlük',
        "deger_neden": "Küçük Kara Balık'ın dar dereden çıkıp denize ulaşma çabasıyla, kendi yolunu seçmenin ve özgürce düşünmenin ne kadar değerli olduğunu gördün.",
        "kaynaklar": [
            'https://tr.wikipedia.org/wiki/K%C3%BC%C3%A7%C3%BCk_Kara_Bal%C4%B1k',
            'https://kitap.yazarokur.com/kucuk-kara-balik',
            'https://seslenenkitap.com/kitap/kucuk-kara-balik/',
        ],
    },
    'Uçan Sınıf': {
        "yazar": 'Erich Kästner',
        "konu": "Kirchberg'deki yatılı okulda okuyan Martin, Johnny, Matz, Uli ve Sebastian, Noel'den önce 'Uçan Sınıf' adlı bir tiyatro oyunu hazırlar. Rakip okulun öğrencileri arkadaşları Rudi'yi ve dikte defterlerini kaçırınca beş arkadaş onu kurtarmak için harekete geçer. Bu sırada her biri kendi korkuları ve dertleriyle de yüzleşir.",
        "mesaj": 'Yazar, gerçek cesaretin korkusuz görünmek değil, korkuyu tanıyıp doğru olanı yapmak olduğunu; arkadaşlık ve dayanışmanın hayatın zorluklarını hafiflettiğini anlatıyor.',
        "ulastiklarin": [
            'Gerçek arkadaşların zor anlarda birbirine destek olduğunu fark ettin.',
            'Cesaretin, korkmamak değil korkuna rağmen doğru olanı yapmak olduğunu anladın.',
            'Seni anlayan ve dinleyen büyüklerin hayatında ne kadar önemli olduğunu gördün.',
        ],
        "bilgiler": [
            "Kitabın başında yazar, Almanya'nın en yüksek dağı Zugspitze'nin karşısındaki Grainau'da tatil yaparken bu hikâyeyi yazmaya karar verir.",
            "Uçan Sınıf ilk kez 1933 yılında Almanya'da yayımlanmıştır.",
        ],
        "deger": 'Dostluk',
        "deger_neden": 'Beş arkadaşın zor anlarda birbirine sahip çıkmasıyla, dostluğun insanı güçlü kılan bir bağ olduğunu gördün.',
        "kaynaklar": [
            'https://www.canyayinlari.com/ucan-sinif-9789755100937',
            'https://www.babaminsiirdefteri.com/erich-kastner-ucan-sinif-eser-incelemesi/',
            'https://de.m.wikipedia.org/wiki/Das_fliegende_Klassenzimmer',
            'https://wikipediatr.org/wiki/U%C3%A7an_S%C4%B1n%C4%B1f',
        ],
    },
    'Yeşil Kafalar 1': {
        "yazar": 'Tuğba Coşkuner',
        "konu": "Serinin ilk kitabı 'Ormanı Yemek Yasak', ağaçlara şiir okuyan, kuş yuvalarını merak eden ve yıldızları kavanoza dolduran dört neşeli arkadaşın maceralarını anlatıyor. 'Yeşil Kafalar' diye anılan bu çocuklar, ormanı kendi çıkarı için tüketmek isteyen insanları ormanı yemenin yasak olduğuna ikna etmeye çalışır.",
        "mesaj": 'Yazar, doğayı korumanın yalnızca büyüklerin değil herkesin sorumluluğu olduğunu ve orman gibi doğal alanların tüm canlıların ortak evi olduğunu eğlenceli bir dille anlatıyor.',
        "ulastiklarin": [
            'Ormanların ve içindeki canlıların korunması gereken ortak bir hazine olduğunu fark ettin.',
            'Doğayı korumak için büyümeyi beklemene gerek olmadığını, çocukların da fark yaratabileceğini gördün.',
            'Arkadaşlarla birlikte hareket etmenin bir amaca ulaşmayı kolaylaştırdığını anladın.',
        ],
        "bilgiler": [
        ],
        "deger": 'Duyarlılık',
        "deger_neden": "Yeşil Kafalar'ın ormanı korumak için verdiği mücadeleyle doğaya ve çevreye karşı duyarlı olmanın önemini hissettin.",
        "kaynaklar": [
            'https://mgvpublications.com/yesil-kafalar-1-ormani-yemek-yasak/',
            'https://www.kitapstore.com/urun/438826/kitap/cezve-cocuk/tugba-coskuner/yesil-kafalar-1-ormani-yemek-yasak/',
            'https://litopya.com/kitap/yesil-kafalar-1-ormani-yemek-yasak-tugba-coskuner',
        ],
    },
    'Yeşil Kafalar 2': {
        "yazar": 'Tuğba Coşkuner',
        "konu": "Serinin ikinci kitabı 'Duvarları Gıdıklanan Okul', Yeşil Kafalar'ın maceralarını asık suratlı duvarları olan bir yatılı okulda sürdürüyor. Çiçeklere doğum günü partisi düzenlenen, hayvanların ve bitkilerin insanlara mektup yazdığı, kamp ve doğa maceralarıyla dolu, hem komik hem heyecanlı bir hikâye anlatılıyor.",
        "mesaj": 'Yazar, hayal gücüyle en sıkıcı yerlerin bile renklenebileceğini ve doğayla iç içe olmanın, canlıları dinlemenin insana çok şey kattığını anlatıyor.',
        "ulastiklarin": [
            'Hayal gücünü kullanarak sıradan bir günü bile maceraya dönüştürebileceğini fark ettin.',
            'Bitkilerin ve hayvanların da korunmayı ve anlaşılmayı hak eden canlılar olduğunu düşündün.',
            'Doğada vakit geçirmenin ve kamp yapmanın ne kadar keyifli ve öğretici olabileceğini gördün.',
        ],
        "bilgiler": [
        ],
        "deger": 'Duyarlılık',
        "deger_neden": 'Hayvanların ve bitkilerin insanlara mektup yazdığı bu yeşil hikâyeyle doğadaki canlılara karşı daha duyarlı olmayı öğrendin.',
        "kaynaklar": [
            'https://mgvpublications.com/de/duvarlari-gidiklanan-okul-yesil-kafalar-2/',
            'https://www.kitapsec.com/Products/Yesil-Kafalar-2-Duvarlari-Gidiklanan-Okul-Tugba-Coskuner-Cezve-Cocuk-422120.html',
            'https://www.ekinkitap.com/yesil-kafalar-2-duvarlari-gidiklanan-okul',
        ],
    },
    'Gıdıklanan Kitap': {
        "yazar": 'Mavisel Yener',
        "konu": "Bu bir şiir kitabı: 'Şiirlerle Değerler Eğitimi' alt başlığıyla, çocuklar için yazılmış eğlenceli şiirler, çizimler ve yaratıcı yazma etkinlikleri içeriyor. Kitap okurla konuşarak onu sayfaları çevirmeye ve etkinlikleri yapıp kitabın 'diğer yazarı' olmaya davet ediyor.",
        "mesaj": 'Yazar, şiirin eğlenceli olduğunu, değerlerin şiirlerle de öğrenilebileceğini ve her çocuğun hayal gücünü kullanarak kendi şiirini yazabileceğini göstermek istiyor.',
        "ulastiklarin": [
            'Şiirlerin hem güldürebildiğini hem de düşündürebildiğini fark ettin.',
            'Etkinlikleri yaparken kendi hayal gücünü kullanıp yazar gibi üretebileceğini gördün.',
            'Sözcüklerle oynamanın ve dize kurmanın ne kadar keyifli olduğunu keşfettin.',
        ],
        "bilgiler": [
        ],
        "deger": 'Estetik',
        "deger_neden": 'Şiirlerin güzelliğini tadıp kendi yaratıcılığınla yazılar ürettikçe sanatın ve güzel sözün değerini hissettin.',
        "kaynaklar": [
            'https://maviselyener.net/?p=1042',
            'https://www.doganyayinlari.com.tr/magaza/urun/gidiklanan-kitap',
            'https://www.kitapyurdu.com/kitap/gidiklanan-kitap/380350.html',
        ],
    },
    'Cingo': {
        "yazar": 'Şermin Yaşar',
        "konu": "Kendini yalnız hisseden 11 yaşındaki Can'ın (Cango) ailesi, barınaktan bir Golden Retriever yavrusu sahiplenir ve adını Cingo koyar. Kendini insan sanan Cingo; evde, düğünde, parkta ve ofiste Gocukoğlu ailesinin başına türlü komik işler açar. Olaylar bazen Cingo'nun, bazen de ailenin diğer üyelerinin ağzından anlatılır.",
        "mesaj": 'Yazar, bir hayvanı sahiplenmenin sevgi kadar sabır ve sorumluluk da gerektirdiğini; sevginin hem insanları hem hayvanları değiştirebileceğini anlatıyor.',
        "ulastiklarin": [
            'Bir hayvanı sahiplenmenin sevgi kadar emek ve sorumluluk da istediğini fark ettin.',
            'Olaylara bir köpeğin gözünden bakarak başkalarının duygularını anlamayı denedin.',
            'Yalnızlık hissinin, sevgi ve dostlukla hafifleyebileceğini gördün.',
        ],
        "bilgiler": [
            'Golden Retriever, uysal ve eğitilebilir yapısıyla bilinen bir köpek cinsidir.',
            "Sivas Kangalı, Türkiye'ye özgü bir çoban köpeği cinsidir.",
        ],
        "deger": 'Merhamet',
        "deger_neden": "Barınaktan sahiplenilen Cingo'nun hikâyesiyle hayvanlara şefkat göstermenin ve onlara bir yuva vermenin ne kadar güzel olduğunu gördün.",
        "kaynaklar": [
            'https://kitap.yazarokur.com/cingo',
            'https://www.idefix.com/cingo-p-304743',
            'https://kitapdiyari.com.tr/cocuk/cingo/',
            'https://www.doganyayinlari.com.tr/magaza/urun/cingo-sc-2',
        ],
    },
    'Oh Ne Ala Memleket': {
        "yazar": 'Şermin Yaşar',
        "konu": "Emre, Kerem, Elif ve Reco, baş harflerinden oluşan 'EKER' adıyla bilinen dört kafadar arkadaştır. Her gün aynı saatte uyanmaktan, ödevlerden ve yetişkinlerin katı kurallarından sıkılan bu çocuklar, kendi hayallerindeki okulu kurmaya karar verir ve harekete geçer.",
        "mesaj": 'Yazar, çocukların düşüncelerinin ve hayallerinin dinlenmeye değer olduğunu; kurallar ve özgürlük arasında dengeyi bulmanın, sorumluluk almayı da gerektirdiğini eğlenceli bir dille anlatıyor.',
        "ulastiklarin": [
            'Fikirlerini söylemenin ve hayal ettiğin şeyler için harekete geçmenin değerli olduğunu fark ettin.',
            'Bir düzen kurmanın ve onu yürütmenin sanıldığından daha çok emek ve sorumluluk istediğini düşündün.',
            'Arkadaşlarla birlikte hayal kurup üretmenin ne kadar eğlenceli olduğunu gördün.',
        ],
        "bilgiler": [
        ],
        "deger": 'Sorumluluk',
        "deger_neden": "EKER'in kendi okulunu kurma macerasıyla, istediğin düzeni kurmanın o düzenin sorumluluğunu da üstlenmek demek olduğunu gördün.",
        "kaynaklar": [
            'https://www.edebiyathaber.net/sermin-yasardan-cocuklara-yeni-kitap-oh-ne-ala-memleket/',
            'https://bianet.org/haber/oh-ne-ala-memleket-yetiskinlerin-asiri-sikici-kurallarina-son-223383',
            'https://www.artfulliving.com.tr/gundem/sermin-yasardan-cocuklar-icin-oh-ne-l-memleket-i-21613',
        ],
    },
    'Sözcüklerin Kamera Arkası': {
        "yazar": 'Ferhat Taştekin',
        "konu": "Türkçe öğretmeninin verdiği sunum ödevinde gruba giremeyen, birbirinden çok farklı üç öğrenci, Ece, Ozan ve Mete, birlikte çalışmak zorunda kalır. Ece'nin bir sözcüğün kökenini merak etmesiyle başlayan araştırma, emekli sinemacı komşuları Süha Bey'in rehberliğinde sözcükler, deyimler ve atasözleri üzerine bir film çekme projesine dönüşür. Bu süreçte üç arkadaş birbirlerini tanır ve dertlerini paylaşmayı öğrenir.",
        "mesaj": 'Yazar, dilimizin sanıldığından çok daha heyecanlı bir dünya olduğunu; farklı insanların birlikte çalışıp birbirine destek olduğunda hem güzel işler çıkardığını hem de yaralarını sarabildiğini anlatıyor.',
        "ulastiklarin": [
            'Sıkıcı sandığın bir ödevin bile merakla ele alınınca eğlenceli bir maceraya dönüşebileceğini gördün.',
            'Bir sözcüğün nereden geldiğini merak etmenin seni yeni keşiflere götürebileceğini fark ettin.',
            'Farklı karakterdeki insanların birbirini tanıyınca gerçek dostlara dönüşebileceğini anladın.',
        ],
        "bilgiler": [
            'Sözcüklerin kökenini ve zamanla nasıl değiştiğini inceleyen bilim dalına etimoloji denir.',
            'Diller birbirinden etkilenir; Türkçeye başka dillerden, başka dillere de Türkçeden sözcükler geçmiştir.',
        ],
        "deger": 'Dostluk',
        "deger_neden": "Ece, Ozan ve Mete'nin farklılıklarına rağmen birbirine destek olmasıyla, dostluğun zor zamanlarda insana güç verdiğini gördün.",
        "kaynaklar": [
            'https://timasokul.com/icerik/sozcuklerin-kamera-arkasi/5356',
            'https://kitap.yazarokur.com/sozcuklerin-kamera-arkasi',
            'https://www.kitapozeti.net.tr/kitap/sozcuklerin-kamera-arkasi',
        ],
    },
    'Güzel Ülkem Türkiye 1': {
        "yazar": 'Metin Özdamarlar',
        "konu": "Eğlenceli Gezi dizisinden bu kitap, okuru Türkiye'nin şehirlerinde, tarihi ve doğal güzelliklerinde bir gezintiye çıkarıyor. Edirne'de Selimiye Camii, Bursa'da Ulu Cami ve Uludağ, Manyas Kuş Cenneti, Efes, Pamukkale, Aspendos, Cennet ve Cehennem Mağaraları, Konya'da Mevlana Müzesi, Ankara'da ilk TBMM, Tuz Gölü ve Safranbolu evleri tanıtılıyor. Kitabın sonundaki koordinatlarla bu yerlerin uydu görüntüleri de bulunabiliyor.",
        "mesaj": 'Yazar, ülkemizin ne kadar zengin bir tarihe ve eşsiz doğal güzelliklere sahip olduğunu çocuklara eğlenceli bir dille tanıtarak ülke sevgisini güçlendirmek istiyor.',
        "ulastiklarin": [
            'Ülkemizin her köşesinin görmeye değer bir güzellik sakladığını fark ettin.',
            'Tarihi yapıların ve doğal alanların korunması gereken ortak mirasımız olduğunu anladın.',
            'Haritalar ve koordinatlarla bir yeri keşfetmenin ne kadar eğlenceli olduğunu gördün.',
        ],
        "bilgiler": [
            "Mimar Sinan'ın eseri olan Selimiye Camii Edirne'dedir.",
            "Manyas Kuş Cenneti, Balıkesir'deki Manyas (Kuş) Gölü kıyısında bulunan önemli bir kuş yaşam alanıdır.",
            "Türkiye Büyük Millet Meclisi ilk kez 23 Nisan 1920'de Ankara'da açılmıştır.",
        ],
        "deger": 'Vatanseverlik',
        "deger_neden": "Türkiye'nin güzelliklerini ve tarihini keşfettikçe ülkene olan sevgin ve ona sahip çıkma isteğin arttı.",
        "kaynaklar": [
            'https://timas.com.tr/guzel-ulkem-turkiye-1',
            'https://www.ahiskayayinevi.com/guzel-ulkem-turkiye-1',
            'https://timas.com.tr/minik-kasifler-icin-turkiye-seti-metin-ozdamarlar-4-kitap-set',
        ],
    },
    'Ballı Çörek Kafeteryası': {
        "yazar": 'Zeynep Cemali',
        "konu": "Annesini kaybetmenin acısını yaşayan Sıla, annesiyle birlikte hayalini kurdukları kafeteryayı babası ve teyzesinin yardımıyla açar. Adını annesinin çok sevdiği ballı çöreklerden alan kafeteryaya gelen ilginç müşteriler, anlattıkları öykülerle Sıla'nın hayatını renklendirir.",
        "mesaj": 'Yazar, zorlukların ve kayıpların sevgiyle, aile dayanışmasıyla ve bir hayali gerçekleştirme çabasıyla aşılabileceğini anlatıyor.',
        "ulastiklarin": [
            'Üzücü olayların ardından sevdiklerinle birlikte yeniden umut bulunabileceğini fark ettin.',
            'Bir hayali gerçeğe dönüştürmenin emek ve kararlılık istediğini gördün.',
            'Her insanın dinlemeye değer bir hikâyesi olduğunu anladın.',
        ],
        "bilgiler": [
        ],
        "deger": 'Aile Bütünlüğü',
        "deger_neden": "Sıla'nın babası ve teyzesiyle birlikte kafeteryayı açıp zor günleri atlatmasıyla, ailenin birbirine destek olmasının gücünü gördün.",
        "kaynaklar": [
            'https://gunisigikitapligi.com/kitaplar/balli-corek-kafeteryasi/',
            'https://gunisigiyou.com/book/balli-corek-kafeteryasi/',
            'https://books.google.com/books/about/Ball%C4%B1_%C3%87%C3%B6rek_Kafeteryas%C4%B1.html?id=kJ2kDwAAQBAJ',
        ],
    },
    'Dedem Bir Kiraz Ağacı': {
        "yazar": 'Angela Nanetti',
        "konu": "Şehirde yaşayan Tonino, köydeki dedesi Ottaviano ile anneannesi Teodolinda'ya çok düşkündür. Onların yanında özgür ve mutlu günler geçirir; dedesinin annesi doğduğunda diktiği kiraz ağacı Felice ve anneannesinin akıllı kazı Alfonsina onun için çok özeldir. Hayatındaki kaçınılmaz değişiklikler, Tonino'nun ağaca ve kaza yepyeni bir gözle bakmasına yol açar.",
        "mesaj": 'Aile büyüklerimizle kurduğumuz sevgi bağı, onlar yanımızda olmasa bile bizde yaşamaya devam eder. Kitap ayrıca insanı doğadan koparan kent yaşamı üzerine düşündürür.',
        "ulastiklarin": [
            'Dedelerin ve ninelerin sevgisinin ne kadar değerli olduğunu fark ettin.',
            'Kaybetmek gibi zor duygularla baş ederken sevdiklerimizi anılarla yaşatabileceğimizi öğrendin.',
            'Bir ağacın bile bir aile için ne kadar anlamlı olabileceğini ve doğaya sahip çıkmanın önemini düşündün.',
        ],
        "bilgiler": [
        ],
        "deger": 'Aile Bütünlüğü',
        "deger_neden": "Tonino'nun dedesi ve anneannesiyle kurduğu sıcak bağ, sana aile büyüklerinle arandaki sevginin ne kadar güçlü olduğunu gösterdi.",
        "kaynaklar": [
            'https://gunisigikitapligi.com/kitaplar/dedem-bir-kiraz-agaci/',
            'https://kitapdiyari.com.tr/cocuk/dedem-bir-kiraz-agaci/',
            'https://litopya.com/kitap/dedem-bir-kiraz-agaci-angela-nanetti',
        ],
    },
    'Yaşasın Ç Harfi Kardeşliği': {
        "yazar": 'Behiç Ak',
        "konu": "Beşinci sınıftaki Ali, okul ödevi için yeni nüfus kâğıdı çıkartırken soyadının kayıtlarda yanlışlıkla sonuna Ç eklenerek 'Hoşgörüç' yazıldığını öğrenir. Babası buna çok kızsa da Ali bu harften memnundur ve sosyal paylaşım sitesinde de okulda da 'Bay Ç' olarak tanınır. Ali, her şeyin hızla tüketilip atıldığı bir dünyada kendini bulmaya çalışır.",
        "mesaj": 'Sosyal medya ve hızlı tüketim hayatımızı ve iletişimimizi değiştiriyor; bu değişimi fark edip bilinçli davranmalıyız. Kitap bunu mizahla, gülümseterek anlatır.',
        "ulastiklarin": [
            'Sosyal medyada paylaştıklarının sandığından çok daha fazla kişiye ulaşabileceğini fark ettin.',
            'Ailenle yüz yüze konuşmanın ve onları dinlemenin ne kadar değerli olduğunu düşündün.',
            'Her şeyi hemen tüketip atmak yerine eşyalarına ve çevrene daha dikkatle bakmayı öğrendin.',
        ],
        "bilgiler": [
            'Kişilerin adı ve soyadı nüfus kayıtlarında resmî olarak tutulur; kayıtta bir yanlışlık olursa düzeltilmesi için başvuru yapılabilir.',
            'İnternette paylaşılan kişisel bilgiler, tanımadığımız kişiler tarafından da görülebilir.',
        ],
        "deger": 'Mahremiyet',
        "deger_neden": "Ali'nin ailesiyle ilgili her şeyi sosyal medyada paylaşmasının sonuçlarını görünce, özel hayatını korumanın önemini fark ettin.",
        "kaynaklar": [
            'https://gunisigikitapligi.com/kitaplar/yasasin-c-harfi-kardesligi/',
            'https://kitap.yazarokur.com/yasasin-c-harfi-kardesligi',
            'https://en.gunisigikitapligi.com/books/yasasin-c-harfi-kardesligi/',
        ],
    },
    'Postayla Gelen Deniz Kabuğu': {
        "yazar": 'Behiç Ak',
        "konu": "Pantomimci babası ve avukat annesi çok yoğun çalıştığı için Sude ailesiyle az vakit geçirir. Bir tablet bilgisayar edinen Sude kısa sürede kendini sanal dünyaya kaptırır; dersleri, yolları, hatta tiyatroyu bile ekrandan izler hâle gelir. Endişelenen annesi, kızını bu dijital labirentten kurtarmak için bir 'kurtarma operasyonu' başlatır.",
        "mesaj": 'Anı yaşamak yerine her şeyi ekrandan izlemek bizi doğadan, ailemizden ve arkadaşlarımızdan uzaklaştırabilir. Teknolojiyle gerçek hayat arasında denge kurmalıyız.',
        "ulastiklarin": [
            'Ekran başında geçirdiğin zamanı dengelemenin ne kadar önemli olduğunu fark ettin.',
            'Anları kaydetmek yerine onları gerçekten yaşamanın ve hissetmenin güzelliğini düşündün.',
            'Ailenle ve doğayla vakit geçirmenin sana iyi geleceğini anladın.',
        ],
        "bilgiler": [
            'Pantomim, hiç konuşmadan yalnızca beden hareketleri ve yüz ifadeleriyle yapılan bir sahne sanatıdır.',
            'Bir alışkanlığı kendi isteğimizle bırakamayıp kontrolünü kaybetmemize bağımlılık denir; ekranlara aşırı bağlanmak da bir bağımlılık türü olabilir.',
        ],
        "deger": 'Sağlıklı Yaşam',
        "deger_neden": "Sude'nin ekran bağımlılığından kurtulma çabası, sana teknolojiyi dengeli kullanmanın sağlıklı bir yaşam için ne kadar önemli olduğunu gösterdi.",
        "kaynaklar": [
            'https://gunisigikitapligi.com/kitaplar/postayla-gelen-deniz-kabugu/',
            'https://kitap.yazarokur.com/postayla-gelen-deniz-kabugu',
            'https://gunisigiyou.com/book/postayla-gelen-deniz-kabugu/',
            'https://dergipark.org.tr/tr/pub/atdd/article/587785',
        ],
    },
    'Haritada Kaybolmak': {
        "yazar": 'Vladimir Tumanov',
        "konu": 'Büyük kente yeni taşınan Chris ve Francis kardeşler, yağmurdan kaçmak için tuhaf eşyalarla dolu bir dükkâna sığınır ve orada izinsiz yedikleri şekerler yüzünden hızla yaşlanmaya başlar. Bunu durdurmanın tek yolu, sihirli bir dünya haritasında beliren on coğrafya bilmecesini çözmektir. Kardeşler atlas ve ansiklopedilerle araştırma yaparken bir de peşlerine takılan hırslı bir muhabirden kaçmak zorunda kalırlar.',
        "mesaj": 'Coğrafya hayatımızın içindedir ve araştırarak öğrenmek eğlenceli olabilir. Yaptığımız hataların sorumluluğunu alıp birlikte çalışarak sorunları çözebiliriz.',
        "ulastiklarin": [
            'Harita ve atlas okumanın bir problemi çözmek için ne kadar işe yarayabileceğini gördün.',
            'Ansiklopedi gibi kaynaklardan araştırma yaparak doğru bilgiye ulaşmanın keyfini tattın.',
            'İzinsiz yapılan bir davranışın sonuçlarıyla yüzleşmenin ve kardeşinle dayanışmanın önemini fark ettin.',
        ],
        "bilgiler": [
            'Dünya haritası ve atlas kullanarak ülkelerin, okyanusların ve kıtaların yerini bulabiliriz.',
            'Etiyopya Afrika kıtasında, Kuzey Kore ise Asya kıtasında yer alan ülkelerdir; Hint Okyanusu dünyanın büyük okyanuslarından biridir.',
        ],
        "deger": 'Sorumluluk',
        "deger_neden": "Chris ve Francis'in izinsiz yedikleri şekerlerin sonuçlarını düzeltmek için verdikleri mücadele, sana yaptıklarının sorumluluğunu üstlenmenin önemini gösterdi.",
        "kaynaklar": [
            'https://gunisigikitapligi.com/kitaplar/gizemli-haritalar-dizisi/haritada-kaybolmak/',
            'https://kitapdergisi.com/cografya-haritada-kaybolarak-sevilir/',
            'https://www.neptunlucadi.com/2025/06/haritada-kaybolmak-gizemli-haritalar.html',
        ],
    },
    'Kraliçeyi Kurtarmak': {
        "yazar": 'Vladimir Tumanov',
        "konu": "Matematikle arası iyi olmayan Aleks, yolda bulduğu tuhaf kalemin matematik problemlerini çözdüğünü keşfeder. Ardından kitaplığında beliren gizemli bir kitap, onu ve arkadaşları Sam ile Vanessa'yı büyük bir maceraya sürükler. Kötü Kral Rechner'in şatosuna kaçırılan Zümrüt Kraliçe Jayden'ı kurtarmak için üç arkadaşın yüzlerce matematik bilmecesini çözmesi gerekir.",
        "mesaj": 'Matematik hayatın içindedir ve vazgeçmeden, araştırarak ve arkadaşlarımızdan destek alarak en zor problemleri bile çözebiliriz.',
        "ulastiklarin": [
            'Zor görünen bir problemi adım adım düşünerek çözebileceğini gördün.',
            'Hemen pes etmek yerine sabırla uğraşınca başarının geldiğini fark ettin.',
            'Zorlandığında arkadaşlarından yardım istemenin ve birlikte çalışmanın gücünü öğrendin.',
        ],
        "bilgiler": [
            "Üslü sayılar, bir sayının kendisiyle tekrar tekrar çarpımını kısaca gösterir; örneğin 2³ = 2 × 2 × 2 = 8'dir.",
            'Uzunluk ve ağırlık ölçüleri, hız ve yaş problemleri günlük hayatta sıkça karşılaştığımız matematik konularıdır.',
        ],
        "deger": 'Sabır',
        "deger_neden": 'Aleks ve arkadaşlarının kraliçeyi kurtarmak için bilmeceleri tek tek, vazgeçmeden çözmesi sana sabrın başarıya götürdüğünü gösterdi.',
        "kaynaklar": [
            'https://gunisigikitapligi.com/kitaplar/kraliceyi-kurtarmak/',
            'https://www.cocukicinicerik.com/tr/incelemeler/kitap/kraliceyi-kurtarmak',
            'https://cogem.ankara.edu.tr/wp-content/uploads/sites/311/2017/01/kraliceyikurtarmak80c4.pdf',
            'https://gunisigiyou.com/wp-content/uploads/Vladimir-Tumanov-Kraliceyi-Kurtarmak.pdf',
        ],
    },
    'Çatıdaki Gezegen': {
        "yazar": 'Behiç Ak',
        "konu": "Evden okula servisle gidip gelen, sokakta top oynamayı bile bilmeyen Serdar sıradan bir kentli çocuktur. Apartman arkadaşı Ceren'in peşinden çatı katına çıktığında kendini bambaşka bir 'gezegende' bulur: Burada şairler, hikâyeler, hatta Don Kişot bile vardır. Çatıda buldukları eski bir seyir defteri de onları yepyeni maceralara ve düşüncelere sürükler.",
        "mesaj": 'Kentin daralttığı hayatlarda bile hayal gücü ve edebiyat bize yeni dünyaların kapısını açar. Merak etmek ve keşfetmek bizi özgürleştirir.',
        "ulastiklarin": [
            'Kitapların ve hayal gücünün seni bambaşka dünyalara götürebileceğini fark ettin.',
            'Merak etmenin ve yeni şeyler keşfetmenin hayatı ne kadar renklendirdiğini gördün.',
            'Gerçek bir arkadaşlığın sana cesaret verip yeni kapılar açabileceğini öğrendin.',
        ],
        "bilgiler": [
            "Don Kişot, İspanyol yazar Miguel de Cervantes'in dünyaca ünlü romanının kahramanıdır.",
            'Seyir defteri, bir yolculuk sırasında yaşananların ve gözlemlerin kaydedildiği defterdir.',
        ],
        "deger": 'Özgürlük',
        "deger_neden": "Serdar'ın apartmana sıkışmış hayatından çıkıp çatıdaki hayal dünyasını keşfetmesi, sana kendi yolunu ve hayallerini seçmenin özgürlüğünü gösterdi.",
        "kaynaklar": [
            'https://gunisigikitapligi.com/kitaplar/catidaki-gezegen/',
            'https://www.edebiyathaber.net/behic-aktan-cocuklara-catidaki-gezegen/',
            'https://www.birgun.net/makale/cati-katindaki-gezegenle-birlikte-kendi-hikayeni-kesfetmek-135529',
            'https://www.kitapyurdu.com/kitap/catidaki-gezegen/404863.html',
        ],
    },
    'Ağaçtaki Ev': {
        "yazar": 'Bianca Pitzorno',
        "konu": "Şehirde apartman dairesinde yaşamaktan sıkılan sekiz yaşındaki Aglaia ile yetişkin Bianca, kocaman bir meşe ağacının dallarına ev kurar ve kedileri Mürdüm'le keyifli bir yaşama başlar. Ağaçta yalnız olmadıklarını, tuhaf komşuları Çalçene Boşboğaz Bey ile tanışınca anlarlar. Uçan köpekler, konuşan kediler ve leyleklerin getirdiği bebekler gibi mizah dolu, tuhaf olaylar birbirini izler.",
        "mesaj": 'İnsan doğadan koptukça mutsuzlaşır; farklı canlılarla bir arada yaşamak anlayış ve uyum gerektirir. Yazar toplumsal sorunları mizahla eleştirir.',
        "ulastiklarin": [
            'Doğayla iç içe yaşamanın insana ne kadar huzur verebileceğini düşündün.',
            'Farklı canlılarla ve komşularla bir arada yaşamanın anlayış gerektirdiğini fark ettin.',
            'Hayal gücünün ve mizahın, ciddi konuları düşünmenin eğlenceli bir yolu olabileceğini gördün.',
        ],
        "bilgiler": [
            'Torpil balığı, vücudunda elektrik üretebilen bir deniz canlısıdır.',
            "Kitabın resimleri, Roald Dahl'ın kitaplarını da resimleyen ünlü İngiliz çizer Quentin Blake'e aittir.",
        ],
        "deger": 'Duyarlılık',
        "deger_neden": "Aglaia ile Bianca'nın doğanın içinde kurduğu yaşam, sana doğaya ve çevrendeki canlılara karşı duyarlı olmayı düşündürdü.",
        "kaynaklar": [
            'https://gunisigikitapligi.com/kitaplar/agactaki-ev/',
            'http://www.kitapkurduanne.com/cocuklar-icin-kitap-onerileri/agactaki-ev-by-bianca-pitzorno-10-yas-ve-uzeri',
            'https://www.derskitabicevaplarim.com/agactaki-ev-kitabinin-konusu-ozeti-karakterleri-aciklamasi-pdf-yorumlari-yazari/',
        ],
    },
    'Eyvah Kitap': {
        "yazar": 'Mine Soysal',
        "konu": "Bu kitap bir roman değil, deneme türünde bir kitaptır. Yazar Mine Soysal'ın on binlerce öğrenciyle yaptığı sohbetlerden esinlenerek yazdığı 32 kısa öyküde, çocuklar ve gençler kitap okuma deneyimlerini anlatır: Klasiklerden nefret ettiğini sananlar, sürekli 'Odana git, kitabını oku!' denenler, bilgisayarla kitap arasında seçime zorlananlar ve yalnızca kitap okurken kendini iyi hissedenler bunlardan bazılarıdır. Son öyküde yazar kendi deneyimini anlatır.",
        "mesaj": 'Okuma sevgisi zorlamayla değil; çocukların isteklerine saygı göstererek, nitelikli seçenekler sunarak ve iletişim kurarak kazanılır.',
        "ulastiklarin": [
            'Kitap okumakla ilgili duygularının ve düşüncelerinin önemli olduğunu fark ettin.',
            'Farklı çocukların okumaya bakışlarını tanıyarak kendi okuma alışkanlığını düşündün.',
            'Sevdiğin kitabı bulduğunda okumanın zorunluluk değil keyif olabileceğini gördün.',
        ],
        "bilgiler": [
        ],
        "deger": 'Saygı',
        "deger_neden": 'Kitaptaki çocukların farklı okuma hikâyeleri, sana herkesin okuma zevkine ve tercihine saygı duymanın önemini gösterdi.',
        "kaynaklar": [
            'https://gunisigikitapligi.com/kitaplar/eyvah-kitap/',
            'https://gunisigiyou.com/wp-content/uploads/Mine-Soysal-Eyvah-Kitap.pdf',
            'https://www.getem.boun.edu.tr/?q=node%2F38091',
        ],
    },
    'Son Adanın Çocukları': {
        "yazar": 'Zülfü Livaneli',
        "konu": "Ada sakinlerinin kardeşçe ve huzur içinde yaşadığı Son Ada'ya bir gün eski bir başkan gelir. Adaya 'medeniyet' getireceğini söyleyen başkan, adanın asıl sahipleri olan martıları düşman ilan eder ve doğanın dengesi bozulmaya başlar. Adanın çocukları, büyüklerin kararlarına boyun eğmek yerine barış, özgürlük ve adadaki hayatı korumak için mücadele eder.",
        "mesaj": 'Doğanın dengesi bozulduğunda herkes zarar görür; haksızlığa karşı sessiz kalmamak ve doğayı korumak gerekir. Çocuklar da dünyayı değiştirecek güce sahiptir.',
        "ulastiklarin": [
            'Doğadaki her canlının dengede önemli bir yeri olduğunu fark ettin.',
            'Yanlış kararlara karşı sesini yükseltmenin ve haklıyı savunmanın cesaret istediğini gördün.',
            'Umudunu kaybetmeden yeniden başlamanın mümkün olduğunu öğrendin.',
        ],
        "bilgiler": [
            'Doğada canlılar arasında bir denge vardır; bir türün yok edilmesi başka bir türün aşırı çoğalmasına yol açabilir.',
            'Leylekler yılan gibi sürüngenlerle de beslenen kuşlardır.',
        ],
        "deger": 'Duyarlılık',
        "deger_neden": 'Martıların ve adanın doğasının zarar görmesine karşı çıkan çocuklar, sana doğaya ve topluma duyarlı olmanın önemini gösterdi.',
        "kaynaklar": [
            'https://www.inkilap.com/son-adanin-cocuklari-zulfu-livaneli',
            'https://kitap.yazarokur.com/son-adanin-cocuklari',
            'https://kitapdiyari.com.tr/roman/son-adanin-cocuklari/',
        ],
    },
    "Mutlukent'in Yöneticisi": {
        "yazar": 'Emin Özdemir',
        "konu": 'Bilge bir baba, oğlu Emircan için bir kitap yazıp ona miras bırakır. Emircan bu kitabı okur, söylenenleri eksiksiz yerine getirir ve dilini, duygu ve düşünce dünyasını geliştirir. Sonra dertli bir kente yönetici seçmek için düzenlenen büyük bir yarışmaya katılır ve zor soruların doğru yanıtlarını bulmaya çalışır.',
        "mesaj": 'Anadilini doğru, güzel ve etkili kullanmak; okumak, dinlemek ve düşünmek insanı başarıya ve mutluluğa taşır.',
        "ulastiklarin": [
            'Okumanın ve kendini geliştirmenin seni hayata hazırlayan bir hazine olduğunu fark ettin.',
            'Türkçeyi doğru ve güzel kullanmanın insanlarla iletişimini güçlendirdiğini öğrendin.',
            'Büyüklerinin deneyimlerinden ve öğütlerinden yararlanmanın değerini gördün.',
        ],
        "bilgiler": [
            'Masal içinde masal, bir hikâyenin içinde başka hikâyelerin de anlatıldığı bir anlatım yöntemidir.',
        ],
        "deger": 'Çalışkanlık',
        "deger_neden": "Emircan'ın babasının kitabını okuyup emek vererek kendini geliştirmesi, sana çalışmanın insanı hedeflerine ulaştırdığını gösterdi.",
        "kaynaklar": [
            'https://www.kokyayincilik.com.tr/urun/mutlukentin-yoneticisi',
            'https://www.kitapyurdu.com/kitap/mutlukentin-yoneticisi/75148.html',
            'http://ensevilencocukkitaplari.blogspot.com/2010/10/mutlukentin-yoneticisi-emin-ozdemir-kok.html',
        ],
    },
    'Deyim mi Demeyim mi': {
        "yazar": 'Melek Çe',
        "konu": "Kitapta bir kız çocuğu ile ninesi arasındaki sıcak sohbetler üzerinden Türkçedeki deyimlerin öyküleri masalsı bir dille anlatılır. Nine her seferinde 'Deyim mi, demeyim mi?' diye sorar ve bir deyimin hikâyesini anlatır. 'İki dirhem bir çekirdek', 'etekleri zil çalmak', 'pireyi deve yapmak' gibi pek çok deyim öykülerle tanıtılır.",
        "mesaj": 'Deyimler Türkçenin zenginliği ve güzelliğidir; onları öğrenmek dilimizi daha etkili ve renkli kullanmamızı sağlar.',
        "ulastiklarin": [
            'Türkçenin ne kadar zengin ve renkli bir dil olduğunu fark ettin.',
            'Deyimlerin ardındaki hikâyeleri öğrenerek onları daha kolay hatırlayabileceğini gördün.',
            'Konuşurken ve yazarken deyimleri kullanarak anlatımını güzelleştirebileceğini öğrendin.',
        ],
        "bilgiler": [
            'Deyimler, genellikle gerçek anlamından farklı bir anlam taşıyan kalıplaşmış söz gruplarıdır.',
            "'İki dirhem bir çekirdek' çok süslü ve şık giyinmiş anlamına gelir.",
            "'Etekleri zil çalmak' çok sevinmek anlamında kullanılır.",
        ],
        "deger": 'Estetik',
        "deger_neden": 'Deyimlerin masalsı öyküleri, sana Türkçenin güzelliğini ve dilimizi zevkle kullanmanın inceliğini gösterdi.',
        "kaynaklar": [
            'https://www.kitapyurdu.com/kitap/deyim-mi-demeyim-mi/564127.html',
            'https://www.naryayinlari.com/urun/deyim-mi-demeyim-mig-melek-ce-9786053707639',
            'https://dipnotski.com/2017/08/11/melek-ce-deyim-mi-demeyim-mi-2008/',
        ],
    },
    'Kayıp Küp': {
        "yazar": 'Mehmet Vicdan',
        "konu": "Yiğit ve Arda, gri bir arabadan inen esrarengiz adamların konuşmalarına tanık olur ve bir sır öğrenir. Konuşmalarda, eski bir uygarlıktan kalan 'büyük küp'e ulaştıracak bir haritadan söz edilmektedir. İki arkadaş, haritanın bir parçasını adamlardan önce bulmak için heyecanlı ve tehlikeli bir maceraya atılır.",
        "mesaj": 'Çocuklar da doğru kararlar verebilir; arkadaşlık, cesaret ve akıl birleşince zorlukların üstesinden gelinir. Kültürel mirasımızı tanımak ve korumak önemlidir.',
        "ulastiklarin": [
            'Arkadaşınla birlikte hareket etmenin seni daha güçlü kıldığını fark ettin.',
            'Zor bir durumda aklını kullanarak doğru kararlar verebileceğini gördün.',
            'Eski uygarlıklardan kalan kültürel mirasın değerli olduğunu ve korunması gerektiğini düşündün.',
        ],
        "bilgiler": [
        ],
        "deger": 'Vatanseverlik',
        "deger_neden": "Yiğit ve Arda'nın eski bir uygarlıktan kalan küpün izini sürmesi, sana ülkenin millî ve kültürel varlıklarına sahip çıkmayı düşündürdü.",
        "kaynaklar": [
            'https://paragrafinsifresi.com/yayinlar/kultur/prd-kayip-kup',
            'https://www.kitapstore.com/urun/632217/kitap/paragrafin-sifresi-kitapcilik/mehmet-vicdan/kayip-kup/',
            'https://www.kitapsec.com/Products/Kayip-Kup-Paragrafin-Sifresi-Yayincilik-790024.html',
        ],
    },
    'Şamatalı Köy': {
        "yazar": 'Astrid Lindgren',
        "konu": 'Şamatalı Köy, yalnızca üç çiftlik evinden (Kuzey Çiftliği, Orta Çiftlik, Güney Çiftliği) oluşan küçük bir İsveç köyüdür. Kitabı anlatan Lisa; kardeşleri Lasse ve Bosse, komşu çocukları Olle, Britta ve Anna ile birlikte okul, oyun, hayvanlar ve mevsimlik işler arasında neşeli maceralar yaşar. Çocuklar bazen atışsalar da birlikte çok eğlenir, hatta yalnız bir köpeği huysuz bir ayakkabı tamircisinin elinden kurtarırlar.',
        "mesaj": 'Yazar, basit ve sıradan günlerin bile arkadaşlarla paylaşıldığında ne kadar güzel ve eğlenceli olabileceğini anlatıyor. Doğayla iç içe, paylaşarak ve dayanışarak geçen bir çocukluğun değerini hatırlatıyor.',
        "ulastiklarin": [
            'Mutlu olmak için büyük olaylara değil, arkadaşlarınla paylaştığın küçük anlara ihtiyaç olduğunu fark ettin.',
            'Arkadaşlarınla bazen anlaşamasan da barışıp birlikte eğlenmenin ne kadar değerli olduğunu gördün.',
            'Hayal gücünü kullanarak sıradan bir günü bile bir maceraya dönüştürebileceğini keşfettin.',
        ],
        "bilgiler": [
            "Kitabın özgün adı 'Alla vi barn i Bullerbyn'dir; 'Şamatalı Köy' adı, köyün İsveççe adı olan Bullerbyn'den gelir.",
            "Kitap, İsveç'in kırsalındaki çiftlik yaşamını; hayvan bakımı, mevsimlik işler ve köy okulu gibi yönleriyle anlatır.",
        ],
        "deger": 'Dostluk',
        "deger_neden": 'Lisa ve arkadaşlarının her gününü birlikte oynayıp paylaşarak şenlendirmesi, sana gerçek arkadaşlığın hayatı nasıl güzelleştirdiğini gösterdi.',
        "kaynaklar": [
            'https://tr.wikipedia.org/wiki/%C5%9Eamatal%C4%B1_K%C3%B6y',
            'https://kitapdiyari.com.tr/roman/samatali-koy/',
            'https://litopya.com/kitap/samatali-koy-astrid-lindgren-456154',
            'https://litopya.com/kitap/samatali-koy-ciltli-astrid-lindgren',
        ],
    },
    'Dünyayı Sırtında Taşıyan Balık': {
        "yazar": 'Özgür Balpınar',
        "konu": "Emir, İran-Irak Savaşı yıllarında Tebriz'de sokakta yaşayan, kulakları iyi duymayan, annesiz babasız bir çocuktur. Bir gün bir dükkânın camında gördüğü kırmızı balıktan çok etkilenir ve onu özgürlüğüne kavuşturmak ister; farkında olmadan kendi özgürlüğünü de balığınkine bağlar. Savaşın gölgesinde, arkadaşlarıyla terk edilmiş bir evde yaşayan Emir, hayallerinin peşinde zorlu bir yolculuğa çıkar.",
        "mesaj": 'Yazar, en zor koşullarda bile umudun ve hayal kurmanın insanı ayakta tuttuğunu anlatıyor. Savaşın çocuklara verdiği acıyı gösterirken, dünyanın olması gerektiği gibi, daha iyi bir yer olabileceğine inandırıyor.',
        "ulastiklarin": [
            'Savaşın ve yoksulluğun çocukların hayatını nasıl etkilediğini görerek sahip olduklarının kıymetini fark ettin.',
            'Zor durumda olsan bile umudunu ve hayallerini kaybetmemenin insana güç verdiğini öğrendin.',
            'Bir canlının özgür olmasını istemenin, onu gerçekten sevmek anlamına geldiğini düşündün.',
        ],
        "bilgiler": [
            "İran ile Irak arasında 1980'lerde yıllarca süren büyük bir savaş yaşanmıştır; bu savaştan en çok etkilenenlerden biri de çocuklar olmuştur.",
            "Tebriz, İran'ın kuzeybatısında yer alan büyük ve tarihî bir şehirdir.",
        ],
        "deger": 'Özgürlük',
        "deger_neden": "Emir'in kırmızı balığı özgürlüğüne kavuşturma hayaliyle kendi özgürlüğünü araması, sana özgür olmanın her canlı için ne kadar değerli olduğunu hissettirdi.",
        "kaynaklar": [
            'https://www.kitapstore.com/urun/556854/kitap/timas-genc-yayinlari/ozgur-balpinar/dunyayi-sirtinda-tasiyan-balik/',
            'https://www.neokuyorum.org/yuz-yuz-dunyayi-sirtinda-tasiyan-balik-caner-almaz/',
            'https://kitapdiyari.com.tr/roman/dunyayi-sirtinda-tasiyan-balik/',
            'https://www.kitapyurdu.com/kitap/dunyayi-sirtinda-tasiyan-balik/762511.html',
        ],
    },
    'Göğü Yere İndirelim': {
        "yazar": 'Özgür Balpınar',
        "konu": "Durmadan başını belaya sokan Deniz, ailesinin isteğiyle bir Öğrenci Değişim Programı'na katılır; ancak bir yanlışlık sonucu kendini Afrika'da bir kabilede bulur. Başta bu yeni ve zorlu hayata uyum sağlamakta zorlanan Deniz, zamanla paylaşmayı, birlikte hareket etmeyi, doğayı ve dostluğu öğrenir. Babasının anlattığı, denizin ortasındaki duvarı görünmez kılan alaca kuş masalı da onun yolculuğuna eşlik eder.",
        "mesaj": 'Yazar, farklı dillerin, kültürlerin ve insanların bizi ayırmadığını; önyargı duvarlarını yıkınca aynı gökyüzü altında barış ve sevgiyle yaşayabileceğimizi anlatıyor.',
        "ulastiklarin": [
            'Farklı bir kültürü önyargıyla değil, merakla tanımaya çalışmanın insanı nasıl zenginleştirdiğini fark ettin.',
            'Paylaşmanın ve birlikte hareket etmenin zor koşullarda bile insanları güçlü kıldığını gördün.',
            'Hatalar yapan birinin de doğru ortamda değişip gelişebileceğini öğrendin.',
        ],
        "bilgiler": [
        ],
        "deger": 'Saygı',
        "deger_neden": "Deniz'in kabile yaşamını tanıdıkça içindeki önyargı duvarlarını yıkması, sana farklı insanlara ve kültürlere saygı duymanın önemini gösterdi.",
        "kaynaklar": [
            'https://timas.com.tr/gogu-yere-indirelim-9786050823905',
            'https://www.neokuyorum.org/gogu-yere-indirelim-ozgur-balpinar/',
            'https://cumabozkurt.com/gogu-yere-indirelim-ozgur-balpinar-kitap-incelemesi',
        ],
    },
    'Düşler Atlası': {
        "yazar": 'Özgür Balpınar',
        "konu": "Serinin son kitabında, Göğü Yere İndirelim'den tanıdığımız Deniz ile Yeryüzünün Kalbi'nden tanıdığımız Bamba bir araya gelir. İkisi mahsur kaldıkları bir adada çıkış yolu ararken, kaderleri adanın yerlisi Ra ile birleşir. Bu macera; hayaller, cesaret, beklemek ve zorluklarla başa çıkmak üzerine bir yolculuğa dönüşür.",
        "mesaj": 'Yazar, dünyayı meraklı gözlerin ve hayal kuranların değiştirebileceğini; hayallere ulaşmak için yürümekten, beklemekten ve zorluklara dayanmaktan vazgeçmemek gerektiğini anlatıyor.',
        "ulastiklarin": [
            'Hayallerine ulaşmak için bazen sabırla beklemen ve zorluklara dayanman gerektiğini fark ettin.',
            'Farklı yerlerden gelen insanların dostluk ve yardımlaşmayla birlikte güçlü olabileceğini gördün.',
            'Merakın ve hayal gücünün seni ileriye taşıyan en değerli hazineler olduğunu keşfettin.',
        ],
        "bilgiler": [
        ],
        "deger": 'Sabır',
        "deger_neden": "Deniz, Bamba ve Ra'nın adadan çıkış yolu ararken pes etmemesi, sana hayallere kavuşmak için sabırla yürümeye devam etmenin önemini öğretti.",
        "kaynaklar": [
            'https://timas.com.tr/dusler-atlasi',
            'https://timasokul.com/icerik/dusler-atlasi/1396',
            'https://yayindedektifi.com/kitap/dusler-atlasi',
        ],
    },
    'Zerdali Dedemle Bir Yıl': {
        "yazar": 'Yaşar Bayraktar',
        "konu": "Altıncı sınıfa geçen Yağız, dedesi Said Bey'in evinin yakınındaki yeni bir okula başlar. Yılda sadece birkaç kez gördüğü dedesi, gri beton apartmanların arasında bahçeli küçük bir evde, çok sevdiği ağaçlarıyla yaşamaktadır. Doğum gününde son model bir tablet yerine bir zerdali ağacı hediye edilen Yağız'ın dedesiyle geçirdiği bir yıl, aralarındaki dostluğun da ağaçla birlikte büyüdüğü bir yolculuğa dönüşür.",
        "mesaj": 'Yazar, hayattaki en değerli şeylerin eşyalar ya da teknoloji değil; sevgi, aile, birlikte geçirilen zaman ve emekle büyütülen şeyler olduğunu anlatıyor.',
        "ulastiklarin": [
            'Büyüklerinle vakit geçirmenin ve onları tanımanın sana ne kadar çok şey katabileceğini fark ettin.',
            'Bir şeyi emek vererek ve sabırla büyütmenin, hazır alınan eşyalardan daha değerli olduğunu gördün.',
            'Şehrin kalabalığında doğayı ve ağaçları korumanın önemini düşündün.',
        ],
        "bilgiler": [
        ],
        "deger": 'Aile Bütünlüğü',
        "deger_neden": "Yağız'ın uzak olduğu dedesiyle zerdali ağacı sayesinde yakınlaşması, sana aile bağlarını güçlendirmenin ve büyüklerine değer vermenin önemini gösterdi.",
        "kaynaklar": [
            'https://timas.com.tr/zerdali---dedemle-bir-yil-9786050838954',
            'https://timas.com.tr/zerdali-dedemle-bir-yil',
            'https://e-dokuman.com/index.php/2025/03/09/yasar-bayraktar-zerdali-dedemle-bir-yil-kitap-ozeti/',
        ],
    },
    'Mırıldanan Çocuk': {
        "yazar": 'Gabriele Clima',
        "konu": 'Hikâyeyi anlatan meraklı ev kedisi Pepe; Anne, Baba ve Tato ile yaşar, günlerini komşunun köpeğiyle atışıp güvercinlere söylenerek geçirir. Binanın dördüncü katına hiç dışarı çıkmayan, zamanının çoğunu resim çizerek geçiren, otizmli bir çocuk taşınınca Pepe onu tanımak ve güldürmek ister. Bir kedi olarak insanlarla nasıl iletişim kuracağını bilmese de hayvan dostlarından ve komşulardan yardım alarak bu yalnız çocuğun kalbine ulaşmaya çalışır.',
        "mesaj": 'Yazar, ne kadar farklı olursak olalım bizi birleştiren duyguların olduğunu; farklı olanı kalp gözüyle görmenin ve ona şefkatle yaklaşmanın önemini anlatıyor.',
        "ulastiklarin": [
            'Farklı olan birini yargılamadan önce onu tanımaya çalışmanın önemini fark ettin.',
            'Yalnız kalan birine uzatılan küçük bir dostluk elinin onun hayatını değiştirebileceğini gördün.',
            'Anlaşmakta zorlandığın biriyle bile sabır ve sevgiyle bir bağ kurabileceğini öğrendin.',
        ],
        "bilgiler": [
            'Otizm, bazı insanların çevreleriyle iletişim kurma ve dünyayı algılama biçimini etkileyen bir farklılıktır; otizmli çocuklar da herkes gibi arkadaşlığa ve sevgiye ihtiyaç duyar.',
        ],
        "deger": 'Merhamet',
        "deger_neden": "Pepe'nin eve kapanmış yalnız çocuğa şefkatle yaklaşıp onu mutlu etmek için pes etmeden uğraşması, sana merhametin en güzel örneğini gösterdi.",
        "kaynaklar": [
            'https://kitapdiyari.com.tr/cocuk/mirildanan-cocuk/',
            'https://degerler.net/mirildanan-cocuk-kitabi-online-test-sinav-sorulari/',
            'https://www.edebiyathaber.net/yassiz-bir-kitap-mirildanan-cocuk-seda-sevinc/',
            'https://timas.com.tr/gabriele-clima',
        ],
    },
    'Yankılı Kayalar': {
        "yazar": 'Ahmet Yılmaz Boyunağa',
        "konu": "Doğu Anadolu'da bir dağ köyünde yaşayan Mehmet, anne ve babasını kaybettikten sonra küçük kız kardeşi Hatice ile birlikte İstanbul'daki dayısının yanına gider. Burada, özellikle kendilerini istemeyen yengesi yüzünden pek çok zorlukla karşılaşır ama hem çalışıp hem okumaktan vazgeçmez. Mehmet'in en büyük hayali okuyup doktor olmak ve köyüne dönüp insanlara hizmet etmektir.",
        "mesaj": 'Yazar, azim, fedakârlık ve dürüstlükle yürünen yolda en zor koşulların bile aşılabileceğini; iyi insanların varlığının umut verdiğini anlatıyor.',
        "ulastiklarin": [
            'Hayallerine ulaşmak için zorluklar karşısında yılmadan çalışmanın ne kadar önemli olduğunu fark ettin.',
            "Kardeşine sahip çıkan Mehmet'i görerek sevdiklerini korumanın bir sorumluluk olduğunu düşündün.",
            'Öğrendiklerini başkalarına faydalı olmak için kullanma hayalinin insana güç verdiğini gördün.',
        ],
        "bilgiler": [
        ],
        "deger": 'Çalışkanlık',
        "deger_neden": "Mehmet'in her zorluğa rağmen hem çalışıp hem okuyarak doktor olma hayalinin peşinden gitmesi, sana azmin ve emeğin gücünü gösterdi.",
        "kaynaklar": [
            'https://timas.com.tr/yankili-kayalar-9789752632073',
            'https://timas.com.tr/yankili-kayalar',
            'https://kitap.yazarokur.com/yankili-kayalar',
            'https://www.liseedebiyat.com/ktap-oezetler/14228-yankili-kayalar-a-yilmaz-boyunaga.html',
        ],
    },
    'Bir Küçük Osmancık Vardı': {
        "yazar": 'Hasan Nail Canat',
        "konu": "İki yaşındaki Osman, anne babası Fatma Hanım ve Abdullah Bey ile mutlu bir hayat sürerken para hırsına kapılmış bir çete tarafından kaçırılır. Çete polisten kaçarken onu ıssız bir evde bırakır; ağlayan Osman'ı oradan geçen kamyoncu Ali ve yardımcısı Garip bulur. Adını bilmedikleri için Hüseyin diye çağrılan Osman, onu sevgiyle büyüten bir ailenin yanında büyürken gerçek ailesi de ona kavuşmanın yollarını arar.",
        "mesaj": 'Yazar, aile sevgisinin ve umudun gücünü; iyi kalpli insanların kimsesiz kalan bir çocuğa kucak açmasının ne kadar değerli olduğunu anlatıyor.',
        "ulastiklarin": [
            'Ailenin sevgisinin ve birbirine duyduğu özlemin ne kadar güçlü olduğunu hissettin.',
            'Zor durumdaki bir çocuğa sahip çıkan iyi insanları görerek iyiliğin önemini fark ettin.',
            'Tanımadığın kişilere karşı dikkatli olmanın ve güvenliğine özen göstermenin gerekli olduğunu düşündün.',
        ],
        "bilgiler": [
        ],
        "deger": 'Aile Bütünlüğü',
        "deger_neden": "Osman'ın ailesinin onu bir an bile unutmadan ona kavuşmayı beklemesi, sana aile bağlarının hiçbir zaman kopmayan bir sevgi olduğunu gösterdi.",
        "kaynaklar": [
            'https://timas.com.tr/bir-kucuk-osmancik-vardi',
            'https://www.milliyet.com.tr/egitim/bir-kucuk-osmancik-vardi-kitap-ozeti-oku-konusu-karakterleri-ve-sayfa-sayisi-6930204',
            'https://kitap.yazarokur.com/bir-kucuk-osmancik-vardi',
        ],
    },
    'Çiçek Ekspresi': {
        "yazar": 'Özgür Balpınar',
        "konu": "Uykudan önce dinlediği masalları rüyasına taşıyan Can, bu kez kendini bütün masalların oluştuğu yer olan Masallar Diyarı'na giden Çiçek Ekspresi'nde bulur. Nil, Yiğit ve Narin de bu yolculukta ona eşlik eder. Pinokyo, Peter Pan, Rapunzel ve Nasreddin Hoca gibi kahramanların yaşadığı bu diyarda kötülük çiçekleri masalları değiştirip mutsuz sonlar hazırlamaktadır; çocuklar da onlara sevgi, cesaret, merhamet ve dürüstlükle karşı koymaya çalışır.",
        "mesaj": 'Yazar, masalların sevgi, cesaret, merhamet ve dürüstlük gibi değerleri yaşatan birer ışık olduğunu; iyiliğin ve dayanışmanın kötülüğe karşı her zaman bir yol bulacağını anlatıyor.',
        "ulastiklarin": [
            'Kötülüğe karşı durmanın en güçlü yolunun dürüstlük, sevgi ve cesaret olduğunu fark ettin.',
            'Arkadaşlarınla birlikte hareket ettiğinde zor görünen işlerin üstesinden gelebileceğini gördün.',
            'Masalların sadece eğlence değil, içimizdeki iyiliği koruyan değerli hikâyeler olduğunu keşfettin.',
        ],
        "bilgiler": [
            'Pinokyo, Peter Pan ve Rapunzel dünyaca bilinen masal ve hikâye kahramanlarıdır; Nasreddin Hoca ise Türk kültürünün en sevilen fıkra kahramanıdır.',
        ],
        "deger": 'Dürüstlük',
        "deger_neden": 'Can ve arkadaşlarının masalları kurtarmak için kötülük çiçeklerine dürüstlük ve iyilikle karşı koyması, sana doğruluğun karanlığı yenen bir güç olduğunu gösterdi.',
        "kaynaklar": [
            'https://timas.com.tr/cicek-ekspresi-9786050835892',
            'https://www.kitapyurdu.com/kitap/cicek-ekspresi/571612.html',
            'https://bibliyoraf.com/ozgur-balpinardan-cicek-ekspresi-inceleme/',
        ],
    },
    "Yuan Huan'ın Kulübesi": {
        "yazar": 'Miyase Sertbarut',
        "konu": "Kitap okumayı sevmeyen İlhami, eski sirk alanında kalan bir telefon kulübesine oyun olsun diye girer ve ahizeden gizemli hikâyeler dinlemeye başlar. İşçi çocukların, parmaklıklar ardında büyüyen ve okula gidemeyen çocukların hikâyelerini dinledikçe bunları Türkçe ödevi için kullanmaya karar verir ve yazar olarak 'Yuan Huan' adında Çinli birini uydurur. Ama işler karışır: Ya kitabı okula getirmesini isterlerse? Kulübedeki sesin ardında nasıl bir sır vardır?",
        "mesaj": 'Yazar, herkesin bir hikâyesi olduğunu ve hikâyelerin ölümsüz olduğunu anlatıyor. Okumaya mesafeli çocukları hikâyelerin değiştirici gücüyle tanıştırıp eleştirel düşünmeye davet ediyor.',
        "ulastiklarin": [
            'Hikâyelerin seni başka hayatlara, başka zamanlara götürebilecek sihirli kapılar olduğunu keşfettin.',
            'Okuduğun ya da dinlediğin her şeyi sorgulayarak düşünmenin ne kadar önemli olduğunu fark ettin.',
            'Senin yaşındaki bazı çocukların çok farklı ve zor hayatlar yaşadığını görerek onları anlamaya çalıştın.',
        ],
        "bilgiler": [
            'Dünyada hâlâ okula gidemeyen ya da çalışmak zorunda kalan çocuklar vardır; eğitim her çocuğun temel hakkıdır.',
        ],
        "deger": 'Estetik',
        "deger_neden": "İlhami'nin telefon kulübesinden dinlediği hikâyelerle okumayı ve anlatmayı sevmeye başlaması, sana hikâye sanatının güzelliğini ve yaratıcılığın gücünü gösterdi.",
        "kaynaklar": [
            'https://www.tudem.com/urun/kultur/1008/tudem_edebiyat/10711/yuan_huanin_kulubesi.aspx',
            'https://tudem.com/urun/kultur/1008/tudem_edebiyat/11450/tudem_modern_klasikler__yuan_huanin_kulubesi.aspx',
            'https://www.tudem.com/images/kitaprehberi/9afdayuan_huanin_kulubesi_kitap_rehberipdf.pdf',
            'https://cogem.ankara.edu.tr/wp-content/uploads/sites/311/2022/06/Cansu-Kerimoglu-Cansu-Atay-Yuan-Huanin-Kulubesi-Tanitim-Yazisi.pdf',
        ],
    },
    'Gülen Sakız Ağacı': {
        "yazar": 'Koray Avcı Çakman',
        "konu": "Öğretmeni 'Çocukluk nedir?' konulu bir proje ödevi verince Arda, servis şoförü Adnan amcanın önerisiyle annesinden, babasından ve komşularından çocukluk anılarını dinlemeye başlar. Kitap, birbirine bağlanan on yedi kısa öyküden oluşur. Bu öykülerde beton binalara karşı direnen ağaçlar, çevre kirliliğinden zarar gören martılar, çocukların kendi yaptığı uçurtmalar ve oyuncaklar gibi renkli anılar yer alır.",
        "mesaj": 'Yazar, çocuklarla yetişkinler arasında köprü kurarak çocukluğun değerini hatırlatıyor. Doğayı ve canlıları korumanın, paylaşmanın ve hayal gücünün önemini anlatıyor.',
        "ulastiklarin": [
            'Büyüklerinin de bir zamanlar çocuk olduğunu ve onların anılarından çok şey öğrenebileceğini fark ettin.',
            'Ağaçları, martıları ve suyu korumanın hepimizin görevi olduğunu düşündün.',
            'Kendi ellerinle yaptığın bir uçurtmanın ya da oyuncağın ne kadar değerli olabileceğini gördün.',
        ],
        "bilgiler": [
            'Suyu bilinçsizce kullanmak ve çevreyi kirletmek, martılar gibi pek çok canlının yaşamına zarar verir.',
        ],
        "deger": 'Duyarlılık',
        "deger_neden": "Arda'nın dinlediği öykülerde ağaçları ve martıları korumaya çalışan insanlar, sana doğaya ve canlılara karşı duyarlı olmanın önemini gösterdi.",
        "kaynaklar": [
            'https://www.tudem.com/urun/kultur/1008/tudem_edebiyat/2232/gulen_sakiz_agaci.aspx',
            'https://www.tudem.com/images/urundetaykutu/gulen_sakiz_agaci.pdf',
            'http://korayavcicakman.com/portfolio/gulen-sakiz-agaci/',
        ],
    },
    'Ölümsüz Aile': {
        "yazar": 'Natalie Babbitt',
        "konu": 'On yaşındaki Winnie Foster, ailesinin ormanında dolaşırken bir ağacın dibindeki pınardan su içen genç Jesse Tuck ile karşılaşır ve ardından Mae ve Miles Tuck ile tanışır. Tuck ailesi, bu pınarın suyundan içtikleri için yaşlanmayan, ölümsüz bir ailedir; ama ölümsüz olmaktan hiç de hoşnut değildir. Pınarın sırrını öğrenen ve onu satmak isteyen Sarı Giysili Adam ortaya çıkınca Winnie hem aileyi korumak hem de kendi hayatı için önemli bir karar vermek zorunda kalır.',
        "mesaj": 'Yazar, doğup büyümenin, değişmenin ve yaşlanmanın hayatın doğal bir parçası olduğunu; yaşamı değerli kılanın sonsuzluk değil, her anın kıymetini bilmek olduğunu anlatıyor.',
        "ulastiklarin": [
            'Sahip olduğun her anın değerli olduğunu ve onu dolu dolu yaşaman gerektiğini fark ettin.',
            'Herkesin istediğini sandığı bir şeyin aslında beklenmedik zorluklar getirebileceğini düşündün.',
            'Önemli kararlar verirken sonuçlarını dikkatle düşünmenin gerektiğini öğrendin.',
        ],
        "bilgiler": [
            'Doğada her canlı doğar, büyür, değişir ve yaşlanır; bu döngü yaşamın doğal bir parçasıdır.',
            "Kitabın özgün adı 'Tuck Everlasting'tir; birçok dile çevrilmiş ve iki kez filme uyarlanmıştır.",
        ],
        "deger": 'Sorumluluk',
        "deger_neden": "Tuck ailesinin pınarın sırrını başkalarına zarar vermesin diye koruması ve Winnie'nin büyük bir kararın sorumluluğunu taşıması, sana sorumluluk sahibi olmanın ne demek olduğunu gösterdi.",
        "kaynaklar": [
            'https://www.iskultur.com.tr/olumsuz-aile.aspx',
            'https://dergipark.org.tr/tr/download/article-file/5599968',
            'https://www.turkceci.com/olumsuz-aile-natalie-babbitt-kitabinin-konusu-karakterleri-ve-kisa-ozeti.html',
            'https://kitapokurum.blogspot.com/2017/12/natalie-babbitt-olumsuz-aile.html',
        ],
    },
    'Olmayan Ülke': {
        "yazar": 'Ahmet Ümit',
        "konu": "Akıl Ülkesi'nin Padişahı ile Hayal Ülkesi'nin Büyücü Kralı dünyayı paylaşamayıp savaşmıştır; ay tozundan yaratılan büyücüler insanları küçümser, insanlar da büyücüleri uğursuz sayar. Bu umutsuz dönemde Padişah'ın kızı Su Hanım ile Büyücü Kral'ın oğlu Rüzgâr el ele verir ve önyargılara, engellere rağmen sevgiyle yoğrulmuş yeni bir dünya kurmaya çalışır.",
        "mesaj": 'Yazar, öfke, korku ve önyargının savaşları sürdürdüğünü, sevginin ve iyiliğin ise düşmanlıkları sona erdirebileceğini masalsı bir dille anlatıyor.',
        "ulastiklarin": [
            'Önyargıların insanları birbirinden nasıl uzaklaştırdığını fark ettin.',
            'Sevginin ve iyiliğin düşmanlıkları bitirebilecek kadar güçlü olduğunu düşündün.',
            'Farklı olanlarla da barış içinde yaşanabileceğini gördün.',
        ],
        "bilgiler": [
            'Anka kuşu, Doğu masallarında ve efsanelerinde geçen hayalî, efsanevi bir kuştur.',
        ],
        "deger": 'Sevgi',
        "deger_neden": "Su Hanım ile Rüzgâr'ın iki düşman ülkenin arasına sevgiyle köprü kurmasıyla sevginin öfkeden ve korkudan daha güçlü olduğunu gördün.",
        "kaynaklar": [
            'https://kitap.ykykultur.com.tr/kitaplar/olmayan-ulke',
            'https://www.ahmetumit.com/kitap-detay.php?k=381171',
            'https://kitap.yazarokur.com/olmayan-ulke',
        ],
    },
    'Masal Masal İçinde': {
        "yazar": 'Ahmet Ümit',
        "konu": "Halkını seven ama övünmeyi çok seven genç bir Padişah, Veziriyle birlikte insanların sırlarını öğrenmek için yola çıkar. Yolculukta Şapkacı, Müezzin, Köradam, Kuyumcu ve Demirci'nin iç içe geçmiş masallarını dinlerler; her masal hatalar, pişmanlıklar ve bu hatalardan çıkarılan derslerle örülüdür.",
        "mesaj": 'Yazar, annesinden dinlediği masallarla açgözlülüğün, kıskançlığın ve kibrin insanı mutsuz ettiğini; hatalarından ders çıkaran ve elindekiyle yetinmeyi bilenin huzur bulduğunu anlatıyor.',
        "ulastiklarin": [
            'Yaptığın iyilikleri övünmeden yapmanın daha güzel olduğunu fark ettin.',
            'Açgözlülüğün insanı mutsuz ettiğini, elindekilerle yetinmenin huzur verdiğini düşündün.',
            'Hatalarından ders çıkarmanın insanı olgunlaştırdığını gördün.',
        ],
        "bilgiler": [
            'Bir hikâyenin içinde başka hikâyelerin anlatıldığı bu yönteme "çerçeve hikâye tekniği" denir; Binbir Gece Masalları da bu teknikle anlatılmıştır.',
            '"Evvel zaman içinde, kalbur saman içinde" gibi kalıplaşmış sözler, Türk masallarının başında söylenen tekerlemelerdir.',
        ],
        "deger": 'Mütevazılık',
        "deger_neden": "Övünmeyi seven Padişah'ın ve açgözlü masal kahramanlarının başına gelenlerle alçakgönüllü olmanın ve yetinmeyi bilmenin değerini gördün.",
        "kaynaklar": [
            'https://www.yapikrediyayinlari.com.tr/masal-masal-icinde.aspx',
            'https://www.ahmetumit.com/kitap-detay.php?k=380524',
            'https://www.birazoku.com/masal-masal-icinde',
            'https://dergipark.org.tr/tr/pub/anadoluded/article/1755135',
        ],
    },
    'Kiki ve Bir Diğer Cadı': {
        "yazar": 'Eiko Kadono',
        "konu": "Küçük cadı Kiki artık on altı yaşındadır ve dört yıldır Koriko şehrinde yaşayıp 'Kiki'nin Cadı Kargosu' ile büyü gücünü şehir halkının yararına kullanmaktadır. Bir gün şehre on iki yaşında, özgür ruhlu ve yaramaz bir kız olan Keke gelir ve Kiki'nin tüm düzenini altüst eder. Kiki, kedisi Jiji ve şehir sakinlerinin yardımıyla bu zorlukların üstesinden gelmeye çalışır.",
        "mesaj": 'Yeteneklerimizi başkalarına yardım etmek için kullandığımızda değerli olurlar; zor insanlarla karşılaştığımızda da anlayışlı olmak ve destek istemek bizi güçlendirir.',
        "ulastiklarin": [
            'Sahip olduğun yetenekleri başkalarının işine yarayacak şekilde kullanmanın ne kadar güzel olduğunu fark ettin.',
            'Seni zorlayan biriyle karşılaştığında hemen öfkelenmek yerine onu anlamaya çalışmanın önemini gördün.',
            'Zor bir durumda yalnız olmadığını, çevrendeki insanlardan yardım isteyebileceğini öğrendin.',
        ],
        "bilgiler": [
        ],
        "deger": 'Yardımseverlik',
        "deger_neden": 'Kiki gibi sen de yeteneklerini çevrendeki insanlara yardım etmek için kullandığında hem onları hem kendini mutlu edebilirsin.',
        "kaynaklar": [
            'https://www.kitapyurdu.com/kitap/kiki-ve-bir-diger-cadi/707682.html',
            'https://www.kitapavrupa.com/kitap/kiki-ve-bir-diger-cadi/707682.html',
            'https://www.imge.com.tr/urun/kiki-ve-bir-diger-cadi-eiko-kadono-9786052655238',
        ],
    },
    'Abartma Tozu': {
        "yazar": 'Şermin Yaşar',
        "konu": 'Buğdaylı kasabasında bir sabah herkes her şeyi abartmaya başlar: anne ve baba sağlıklı yaşam takıntısına kapılır, yenge temizlikle, babaanne para kazanmakla, okuldakiler başarıyla aşırı uğraşır. Kasabada normal kalan tek kişi olan anlatıcı çocuk, müfettiş Tevfik Kılıkırkyarar ile birlikte bu tuhaflığın nedenini bulmaya çalışır.',
        "mesaj": 'Her şeyin fazlası zararlıdır; tüketimde, çalışmada, temizlikte ve hatta sevgide bile ölçülü olmak ve insani ilişkileri unutmamak gerekir.',
        "ulastiklarin": [
            'İyi bir şeyin bile aşırısının insanı ve çevresini mutsuz edebileceğini fark ettin.',
            'Gereğinden fazla tüketmenin ve hep daha fazlasını istemenin elimizdekilerin değerini unutturduğunu düşündün.',
            'Herkes bir şeye kapılsa bile sağduyulu kalıp çözüm aramanın cesaret istediğini gördün.',
        ],
        "bilgiler": [
        ],
        "deger": 'Tasarruf',
        "deger_neden": "Abartma Tozu'ndaki kasaba halkının hâli, sana tüketimde ve her işte ölçülü olmanın, israftan kaçınmanın önemini gösteriyor.",
        "kaynaklar": [
            'https://www.tazekitap.com/abartma-tozu',
            'https://www.kitapzen.com/sermin-yasar/abartma-tozu-ciltli.htm',
            'https://bilgiyelpazesi.com/egitim_ogretim/kitap_ozetleri/roman_ozetleri/abartma_tozu_ozet.asp',
        ],
    },
    'Yerdeniz Büyücüsü': {
        "yazar": 'Ursula K. Le Guin',
        "konu": "Gont adasında keçi çobanlığı yapan Ged'in (Çevik Atmaca) büyü yeteneği küçük yaşta teyzesi tarafından fark edilir; sonra büyücü Ogion'un yanında ve Roke adasındaki büyücülük okulunda eğitim alır. Okulda kendini kanıtlamak isteyen Ged, hırsı ve gururu yüzünden yasak bir büyü yapar ve dünyaya karanlık bir gölge salar. Kitap, Ged'in kendi yarattığı bu gölgeyle yüzleşme yolculuğunu anlatır.",
        "mesaj": 'Gerçek güç başkalarına üstün gelmek değil, kendini tanımak ve hatalarının sorumluluğunu almaktır; büyümek kendi karanlık yanlarımızla yüzleşmeyi gerektirir.',
        "ulastiklarin": [
            "Kibir ve 'ben herkesten iyiyim' düşüncesinin insanı nasıl büyük hatalara sürükleyebileceğini gördün.",
            'Hatalarından kaçmak yerine onlarla yüzleşmenin insanı gerçekten büyüttüğünü fark ettin.',
            'Bir güce ya da yeteneğe sahip olmanın, onu dikkatli ve sorumlu kullanmayı da gerektirdiğini düşündün.',
        ],
        "bilgiler": [
        ],
        "deger": 'Mütevazılık',
        "deger_neden": "Ged'in gururu yüzünden yaşadıkları, sana yeteneklerin ne kadar büyük olursa olsun alçakgönüllü kalmanın önemini hatırlatıyor.",
        "kaynaklar": [
            'https://www.metiskitap.com/Catalog/Book/5052',
            'https://1000kitap.com/kitap/yerdeniz-buyucusu--3583',
            'https://tr.wikipedia.org/wiki/Ged_(Yerdeniz)',
            'https://www.edebiyathaber.net/aysen-gencturkten-ursula-k-le-guinin-yerdeniz-buyucusu-serisinin-ilk-kitabi-uzerine-bir-yazi/',
        ],
    },
    'Gece Gündüzüm Olsa': {
        "yazar": 'Andreas Steinhöfel',
        "konu": 'Dokuz yaşındaki Max, huzurevinde yaşayan ve hafızası her geçen gün zayıflayan büyükbabasını çok özlemektedir. Bir gün cesaretini toplayıp büyükbabasını huzurevinden kaçırmaya karar verir. Birlikte kırlara gittikleri mutlu saatlerde birbirlerini ne kadar sevdiklerini asla unutmayacaklarından emin olmak isterler.',
        "mesaj": 'Gerçek sevgi unutkanlığa ve uzaklığa rağmen yaşar; birini sevmek için onu her zaman görmek gerekmez. Büyükanne ve büyükbabalarımız hayatımızda çok değerlidir.',
        "ulastiklarin": [
            'Büyükanne ve büyükbabanla geçirdiğin zamanın ne kadar kıymetli olduğunu fark ettin.',
            'Yaşlanan ve unutkanlaşan insanlara karşı sabırlı ve şefkatli olmanın önemini düşündün.',
            'Sevginin, görmeden ve hatırlamadan bile sürebilecek kadar güçlü bir bağ olduğunu hissettin.',
        ],
        "bilgiler": [
        ],
        "deger": 'Aile Bütünlüğü',
        "deger_neden": "Max'in büyükbabasına duyduğu özlem, sana aile büyüklerinle bağını korumanın ve onlara vakit ayırmanın önemini gösteriyor.",
        "kaynaklar": [
            'https://tudem.com/urun/kultur/1008/tudem_edebiyat/10584/gecen_gunduzum_olsa.aspx',
            'https://www.iyikitap.net/2019/04/02/unutuslara-direnen-sevgi/',
            'https://www.kitapavrupa.com/kitap/gecen-gunduzum-olsa/495203.html',
        ],
    },
    'Gemideki Cesur Ses': {
        "yazar": 'İdil Pişgin',
        "konu": 'Heyecanlandığında dili dolaşan Işıtan, konuşma güçlüğüyle başa çıkmak için pek çok yol denemiş ama yüreğindeki fırtınaları dindirememiştir. Bir gün düşle gerçeğin kesiştiği bir anda kendini okyanusta ilerleyen hayalî bir gemide bulur. Bu gizemli yolculuk, onun korkularıyla yüzleşip kendini olduğu gibi kabul etmesinin hikâyesine dönüşür.',
        "mesaj": "Kendimizde 'kusur' sandığımız farklılıkları gözümüzde büyütmemeli, kendimizi olduğumuz gibi kabul etmeliyiz; herkesin zorlukları olabilir ve üstüne giderek bunlar aşılabilir.",
        "ulastiklarin": [
            'Kendini olduğun gibi kabul etmenin, başarmanın ilk adımı olduğunu fark ettin.',
            'Korkularından kaçmak yerine onların üzerine cesaretle gidebileceğini gördün.',
            'Farklı konuşan ya da farklı özellikleri olan arkadaşlarına daha anlayışlı yaklaşman gerektiğini düşündün.',
        ],
        "bilgiler": [
        ],
        "deger": 'Saygı',
        "deger_neden": "Işıtan'ın yolculuğu, sana hem kendine hem de farklılıkları olan herkese saygı duymanın önemini hatırlatıyor.",
        "kaynaklar": [
            'https://www.tudem.com/urun/kultur/1008/tudem_edebiyat/11426/gemideki_cesur_ses.aspx',
            'https://www.kitapyurdu.com/kitap/gemideki-cesur-ses/709611.html',
            'https://1000kitap.com/kitap/gemideki-cesur-ses--489623',
        ],
    },
    'Yeryüzünün Kalbi': {
        "yazar": 'Özgür Balpınar',
        "konu": "Afrika'daki Mbuti Kabilesi'nden Bamba, iki aylık bir program için Türkiye'ye gelir ve kendini ağaçsız, çiçeksiz, betonlarla dolu bir şehirde bulur. Çocukların saatlerini ekran başında geçirdiğini, doğanın unutulduğunu üzülerek fark eder. Bamba, çevresindekilere yeşilin kıymetini, hayvanların dostluğunu, paylaşmanın ve sevginin önemini yeniden hatırlatmaya karar verir.",
        "mesaj": 'Doğa ve canlılar hayatımızın kalbidir; ekranlara gömülüp onları unutmamalıyız. Hiçbir ayrım yapmaksızın dünyaya gelen her çocuk yeryüzünün çocuğudur.',
        "ulastiklarin": [
            'Ağaçların, çiçeklerin ve hayvanların yaşamımız için ne kadar değerli olduğunu yeniden fark ettin.',
            'Ekran başında geçirdiğin zamanın bir kısmını doğaya ve arkadaşlarına ayırmanın güzelliğini düşündün.',
            'Farklı bir ülkeden ve kültürden gelen birinin gözünden kendi çevrene yeniden bakmayı öğrendin.',
        ],
        "bilgiler": [
            "Mbuti halkı, Orta Afrika'da Kongo'daki İturi Ormanı'nda yaşayan bir topluluktur.",
        ],
        "deger": 'Duyarlılık',
        "deger_neden": "Bamba'nın doğayı ve canlıları koruma çabası, sana çevrene ve doğaya karşı duyarlı olmanın önemini gösteriyor.",
        "kaynaklar": [
            'https://timas.com.tr/yeryuzunun-kalbi',
            'https://cdn.timas.com.tr/preview/9786050827569.pdf',
            'https://1000kitap.com/kitap/yeryuzunun-kalbi--99403',
        ],
    },
    'Kiraz Ağacıyla Aramızdaki Mesafe': {
        "yazar": 'Paola Peretti',
        "konu": "Dokuz yaşındaki Mafalda, Stargardt adlı bir göz hastalığı nedeniyle altı ay içinde görme yetisini tamamen kaybedeceğini öğrenir. Okul bahçesindeki kiraz ağacı onun sığınağı olur; görmeden de yapabileceği şeylerin listesini çıkarır. Ailesi, kedisi Ottimo Turcaret ve okuldaki görevli Estella'nın desteğiyle korkularıyla baş etmeye çalışır.",
        "mesaj": 'Hayat bize zor bir durum getirdiğinde bile cesaretle, sevdiklerimizin desteğiyle ve umudumuzu kaybetmeden yolumuza devam edebiliriz.',
        "ulastiklarin": [
            'Zor bir durumla karşılaştığında neler yapamayacağına değil, neler yapabileceğine odaklanmanın gücünü gördün.',
            'Görme engelli insanların dünyayı nasıl algıladığını ve onlara nasıl destek olunabileceğini düşündün.',
            'Korktuğunda yanındaki insanlara güvenip destek almanın seni güçlendirdiğini fark ettin.',
        ],
        "bilgiler": [
            'Stargardt hastalığı, görmeyi giderek azaltan kalıtsal (aileden geçen) bir göz hastalığıdır.',
            'Görme engelliler, parmaklarıyla dokunarak okudukları altı noktalı kabartma alfabeyi (Braille alfabesi) kullanır.',
        ],
        "deger": 'Sabır',
        "deger_neden": "Mafalda'nın zorlu bir değişimi adım adım kabullenmesi, sana zor zamanlarda sabırlı ve umutlu kalmayı öğretiyor.",
        "kaynaklar": [
            'https://timas.com.tr/kiraz-agaci-ile-aramizdaki-mesafe-fleksi-kapak',
            'https://edebiyatsultani.com/kiraz-agaci-ile-aramizdaki-mesafe-paola-peretti-kitap-yorumu-ozet/',
            'https://kureansiklopedi.com/tr/detay/kiraz-agaci-ile-aramizdaki-mesafe-kitap-c0604',
            'https://kayiprihtim.com/kayip-rihtim/kayip-koseler/cevirmenin-cemberi-kiraz-agaci-ile-aramizdaki-mesafe/',
        ],
    },
    'Yıldızlara Yakın': {
        "yazar": 'Metin Özdamarlar',
        "konu": 'Mustafa, babasını bir iş kazasında kaybettikten sonra annesi ve ikiz kız kardeşleriyle zor koşullarda büyür. Yolunu aydınlatan komşu, manav, öğretmen ve dost gibi iyi insanların adlarını küçük mavi defterine not eder. Robotik kodlama ve yapay zekâ alanında azimle çalışarak hayallerine ulaşır ve büyüdüğünde kendisine iyilik edenlere vefa borcunu öder.',
        "mesaj": 'Azim ve emekle hayallere ulaşılabilir; hayatımıza dokunan iyi insanları unutmamalı, sıra bize geldiğinde biz de başkalarının yolunu aydınlatmalıyız.',
        "ulastiklarin": [
            'Zor koşullarda bile çalışmayı bırakmazsan hayallerine yaklaşabileceğini gördün.',
            'Sana iyilik yapan insanları hatırlamanın ve onlara teşekkür etmenin önemini fark ettin.',
            "Bir gün senin de başkalarının hayatında yol gösteren bir 'yıldız' olabileceğini düşündün.",
        ],
        "bilgiler": [
            'Yapay zekâ, bilgisayarların öğrenme, problem çözme ve karar verme gibi insana özgü becerileri taklit etmesini sağlayan bir teknoloji alanıdır.',
        ],
        "deger": 'Çalışkanlık',
        "deger_neden": "Mustafa'nın zorluklara rağmen azimle çalışıp hayaline ulaşması, sana emeğin ve çalışkanlığın gücünü gösteriyor.",
        "kaynaklar": [
            'https://satinal.timas.com.tr/yildizlara-yakin',
            'https://kitap.yazarokur.com/yildizlara-yakin',
            'https://kitapdiyari.com.tr/yeni-cikan-kitaplar/yildizlara-yakin/',
        ],
    },
    'Yürüyen Şato': {
        "yazar": 'Diana Wynne Jones',
        "konu": "Sophie Hatter, üç kız kardeşin en büyüğüdür ve babasının şapka dükkânında çalışmaktadır. Farkında olmadan Çöl Cadısı'nın öfkesini üstüne çekince yaşlı bir kadına dönüştürülür. Büyüyü bozdurmak için tepelerde durmadan hareket eden Büyücü Howl'un şatosuna gider; burada bir ateş ciniyle pazarlık eder ve hem Howl'un hem de kendisinin bilinmeyen yanlarını keşfeder.",
        "mesaj": 'Kendimize biçtiğimiz sınırlar ve başkalarının hakkımızdaki yargıları bizi tanımlamaz; cesaretle yola çıktığımızda içimizdeki gücü keşfedebiliriz.',
        "ulastiklarin": [
            "'Ben yapamam' diye düşündüğün şeylerin aslında sandığından fazlasını yapabileceğini fark ettin.",
            'İnsanları dedikodulara göre değil, onları tanıdıktan sonra değerlendirmen gerektiğini gördün.',
            'Zor bir durumda bile mizahını ve cesaretini koruyarak yolunu kendin çizebileceğini düşündün.',
        ],
        "bilgiler": [
        ],
        "deger": 'Özgürlük',
        "deger_neden": "Sophie'nin kendine biçilen sıradan hayatın ve lanetin dışına çıkıp kendi yolunu araması, sana kendi yolunu seçmenin değerini gösteriyor.",
        "kaynaklar": [
            'https://tr.wikipedia.org/wiki/Y%C3%BCr%C3%BCyen_%C5%9Eato_(roman)',
            'https://www.kitapyurdu.com/kitap/yuruyen-sato/623993.html',
            'https://kayiprihtim.com/haberler/edebiyat/yuruyen-sato-kitaplari-yeniden/',
        ],
    },
    'Eşek Klanı': {
        "yazar": 'Bilgin Adalı',
        "konu": "Buzul Çağı kitabının devamında, zorlu bir yolculuğun ardından evlerinden çok uzaktaki yeni topraklara ulaşan kardeşler Orka ve Şin, Eşek Klanı'na katılır. Burada savaşla ve kölecilerle tanışırlar; kölecilerden alınan bir gemiyle Büyük Su'da keşfe çıkarlar. Denizin zorluklarıyla sınandıktan sonra kendilerine hiç benzemeyen 'sarışın' denizci bir klanla karşılaşır ve onlarla dostluk kurarlar.",
        "mesaj": 'Birlikte çalışan ve farklı insanlarla dostluk kuran topluluklar zorlukların üstesinden gelir; farklı kültürlerle tanışmak yeni bilgiler ve güzellikler getirir.',
        "ulastiklarin": [
            'Kendine benzemeyen insanlarla dostluk kurmanın dünyanı nasıl genişlettiğini gördün.',
            'Bir topluluğun zorluklara karşı dayanışmayla ayakta kalabileceğini fark ettin.',
            'İlk insanların doğada hayatta kalmak için ne kadar emek verdiğini hayal ettin.',
        ],
        "bilgiler": [
            'İlk insanlar zamanla bazı hayvanları evcilleştirerek yük taşımak gibi işlerde onlardan yararlanmaya başlamıştır.',
        ],
        "deger": 'Dostluk',
        "deger_neden": "Orka ve Şin'in denizci klanla kurduğu dostluk, sana farklı insanlarla kurulan dostlukların ne kadar değerli olduğunu gösteriyor.",
        "kaynaklar": [
            'https://www.yapikrediyayinlari.com.tr/esek-klani.aspx',
            'https://1000kitap.com/kitap/esek-klani--84914',
            'https://www.kitapcity.com.tr/esek-klani',
        ],
    },
    'Savaşı Bitiren Sinek': {
        "yazar": 'Bryndís Björgvinsdóttir',
        "konu": "Kolkex, Sinek ve Hermann Şeker adlı üç sıradan karasinek, evdeki insanlar elektrikli sineklik alınca evden ayrılır ve bir sineği bile incitmeyen Nepal'in iyi kalpli keşişlerini aramaya koyulur. Yolculukları sırasında konakladıkları ülkede savaşla ilk kez tanışan sinekler, bu saçmalığa bir son vermeye karar verir.",
        "mesaj": 'Yazar, savaşın ne kadar anlamsız olduğunu ve en küçük bir canlının bile cesaret ve dayanışmayla büyük bir değişim yaratabileceğini anlatıyor. Savaştan kaçıp güvenli bir hayat arayan insanlara da dikkat çekiyor.',
        "ulastiklarin": [
            '"Benim elimden ne gelir ki?" demeden harekete geçmenin gücünü fark ettin.',
            'Savaşın insanlara ne kadar zarar verdiğini ve barışın ne kadar değerli olduğunu düşündün.',
            'Birlikte çalışan küçük bir ekibin büyük işler başarabileceğini gördün.',
        ],
        "bilgiler": [
            "Nepal, Himalaya Dağları'nın bulunduğu bir Asya ülkesidir; oradaki Budist keşişler canlılara zarar vermemeye büyük özen gösterir.",
        ],
        "deger": 'Duyarlılık',
        "deger_neden": 'Savaşın ve evini terk etmek zorunda kalan insanların acısını sineklerin gözünden görerek topluma ve dünyaya karşı duyarlı olmayı öğrendin.',
        "kaynaklar": [
            'https://www.canyayinlari.com/savasi-bitiren-sinek-9789750734304',
            'https://www.insanokur.org/savasi-bitiren-sinek-bryndis-bjorgvinsdottir-unutulmayacak-bir-cesaret-ve-dayanisma-oykusu/',
            'https://www.edebiyathaber.net/hem-cocuklar-hem-yetiskinler-icin-savasi-bitiren-sinek/',
        ],
    },
    'Dünya Sular Altında': {
        "yazar": 'Cary Fagan',
        "konu": 'Rafe sıradan bir güne uyandığını sanırken penceresinden yalnızca maviliği görür: Odası, evinden kopmuş küçük bir kulübe gibi uçsuz bucaksız sularda köpeğiyle birlikte sürüklenmektedir. Günler boyunca suyun üzerinde yüzerken kendisiyle benzer kaderi paylaşan insanlarla yolları kesişir ve hayatta kalmak için mücadele eder.',
        "mesaj": 'Yazar, gezegenimizi tehdit eden iklim krizine dikkat çekiyor ve kaderimizi elimize almak için hiçbir zaman geç olmadığını hatırlatıyor. Ortak bir amaç için birlik olmanın gücünü anlatıyor.',
        "ulastiklarin": [
            'Doğayı korumazsak dünyamızın nasıl değişebileceğini düşündün.',
            'Zor bir durumda umudunu kaybetmeden çözüm aramanın önemini fark ettin.',
            'İnsanların ortak bir amaç için el ele verdiğinde güçlendiğini gördün.',
        ],
        "bilgiler": [
            'İklim krizi, dünyanın ısınmasına ve buna bağlı olarak deniz seviyesinin yükselmesine yol açabilen önemli bir çevre sorunudur.',
        ],
        "deger": 'Duyarlılık',
        "deger_neden": "Rafe'nin sular altındaki dünyasını okurken daha yaşanabilir bir gezegen için çevreye duyarlı olmanın ne kadar önemli olduğunu fark ettin.",
        "kaynaklar": [
            'https://www.tudem.com/urun/kultur/1008/tudem_edebiyat/11444/dunya_sular_altinda.aspx',
            'https://www.edebiyathaber.net/cary-fagandan-cocuklar-icin-carpici-bir-distopya/',
            'https://www.kitapyurdu.com/kitap/dunya-sular-altinda/717233.html',
        ],
    },
    'Dedemin Bakkalı': {
        "yazar": 'Şermin Yaşar',
        "konu": 'Bursa\'nın bir köyünde yaşayan sekiz yaşındaki Şebnem, büyüyünce ne olacağını düşünürken dedesinin bakkalında çıraklığa başlar. Cin fikirleriyle satışları artırmak için içecekleri karıştırmak, organik ürünler satmak gibi yenilikler dener ama sık sık yetişkinlerin dünyasına tosladığı için başından geçenleri "Çocukların Yetişkinlerle İletişimde Dikkat Etmesi Gereken Hassas Konular" listesine yazar.',
        "mesaj": 'Yazar, kendi çocukluk anılarından yola çıkarak çocuklarla büyükler arasındaki iletişimi, aile bağlarını ve yaratıcı düşünmenin değerini anlatıyor. Büyüklere de çocukların gözünden kendilerini görme fırsatı veriyor.',
        "ulastiklarin": [
            'Yeni fikirler üretmenin ve cesurca denemenin ne kadar eğlenceli olduğunu fark ettin.',
            'Büyüklerle konuşurken onları anlamaya çalışmanın ve kendini ifade etmenin önemini düşündün.',
            'Aile büyüklerinle birlikte vakit geçirip onlardan öğrenmenin değerini gördün.',
        ],
        "bilgiler": [
            'Eskiden köy bakkallarında kolonya gibi ürünler büyük kaplardan şişelere doldurularak satılırdı.',
        ],
        "deger": 'Aile Bütünlüğü',
        "deger_neden": "Şebnem'in dedesiyle bakkalda geçirdiği günler sana aile büyükleriyle kurulan sevgi dolu bağın ve kuşaklar arası iletişimin ne kadar değerli olduğunu gösterdi.",
        "kaynaklar": [
            'https://www.tazekitap.com/dedemin-bakkali',
            'https://www.milliyet.com.tr/bilgi-rehberi/dedemin-bakkali-kitap-ozeti-oku-dedemin-bakkali-konusu-karakterleri-ve-sayfa-sayisi-7501008',
            'https://kitapdiyari.com.tr/hikayeler/dedemin-bakkali/',
            'https://fatmaerdem.com/2017/06/22/oyuncu-anne-sermin-carkaci-dedemin-bakkali-roportaji-12-12-2016/',
        ],
    },
    "Şamatalı Köy'de Eğlence": {
        "yazar": 'Astrid Lindgren',
        "konu": "Yalnızca üç çiftlik evinden oluşan Şamatalı Köy'de yaşayan Lisa, Lasse, Bosse, Olle, Britta ve Anna'nın (Olle'nin küçük kardeşi Kerstin'le yedi çocuk) neşeli maceraları devam eder. Okula götürülen bir kuzu, Olle'nin diş çektirme korkusu, yaz ortası kutlamaları, kiraz satışı ve bebek bakıcılığı gibi eğlenceli olaylar yaşanır.",
        "mesaj": 'Yazar, doğanın içinde birlikte oynayan, paylaşan ve hayal kuran çocukların mutluluğunu anlatıyor. Arkadaşlarla geçirilen sade günlerin ne kadar güzel olabileceğini gösteriyor.',
        "ulastiklarin": [
            'Arkadaşlarınla paylaşmanın ve birlikte oynamanın insanı ne kadar mutlu ettiğini fark ettin.',
            'Mutlu olmak için pahalı şeylere değil, doğaya ve sevdiklerine ihtiyaç olduğunu düşündün.',
            'Korkularını arkadaşlarının desteğiyle daha kolay yenebileceğini gördün.',
        ],
        "bilgiler": [
            'Astrid Lindgren İsveçli bir yazardır; kitabın orijinal adı İsveççe "Bara roligt i Bullerbyn"dir.',
            "Yaz ortası (midsommar) kutlamaları İsveç'te çok sevilen geleneksel bir yaz bayramıdır.",
        ],
        "deger": 'Dostluk',
        "deger_neden": "Şamatalı Köy'ün çocukları gibi arkadaşlarınla oyunlarını, sevinçlerini ve maceralarını paylaşmanın dostluğu nasıl güçlendirdiğini gördün.",
        "kaynaklar": [
            'https://pegasusyayinlari.com/kitap_detay.php?kitapid=13189216292',
            'https://www.kitapyurdu.com/kitap/samatali-koyde-eglence-samatali-koy-2-kitap-ciltli/414537.html',
            'https://kitapdiyari.com.tr/roman/samatali-koy/',
        ],
    },
    'Dilek Kütüphanesi': {
        "yazar": 'Christine Evans',
        "konu": "Lincoln İlkokulu'nda okuyan Raven ve yeni arkadaşı Luca Flores, yerin altındaki gizemli Dilek Kütüphanesi'ni keşfeder. Orada dileklerini gerçekleştirebilen gizemli Kütüphaneci'yle tanışırlar, ama her dileğin beklenmedik sonuçları olur ve iki arkadaş başlarına gelenleri düzeltmek için uğraşır.",
        "mesaj": 'Yazar, "Ne dilediğine dikkat et" diyerek sorunlardan kaçmak yerine onlarla yüzleşmenin ve verilen sözü tutmanın önemini anlatıyor. Gerçek arkadaşlığın paylaşmak ve birbirine danışmakla güçlendiğini gösteriyor.',
        "ulastiklarin": [
            'Sorunlardan kaçmanın onları çözmediğini, bazen daha da büyüttüğünü fark ettin.',
            'Arkadaşına verdiğin sözü tutmanın ve ona danışmanın ne kadar önemli olduğunu düşündün.',
            'Bir şeyi istemeden önce sonuçlarını düşünmen gerektiğini öğrendin.',
        ],
        "bilgiler": [
        ],
        "deger": 'Sorumluluk',
        "deger_neden": "Raven ve Luca'nın dileklerinin sonuçlarıyla uğraşmasını okurken yaptığın seçimlerin ve verdiğin sözlerin sorumluluğunu üstlenmenin önemini gördün.",
        "kaynaklar": [
            'https://www.iskultur.com.tr/dilek-kutuphanesi-mayista-kar-yagisi.aspx',
            'https://www.imge.com.tr/urun/dilek-kutuphanesi-yeni-okul-muduru-christine-evans-9786254295430',
            'https://www.iskultur.com.tr/dilek-kutuphanesi-sonsuza-dek-arkadas.aspx',
        ],
    },
    'Kiralık Canavar': {
        "yazar": 'Andreas Steinhöfel',
        "konu": 'Opera sanatçısı olmayı hayal eden ve korku filmlerine bayılan Gianna, geceleri gizlice evden kaçıp nehir kıyısında aryalar söyler. Bir gece kırmızı gözlü, simsiyah, kocaman bir canavarla karşılaşır; canavar onu korku filmi izlememesi için tehdit eder. Okuldaki bütün çocukların da korkuyla sindiğini fark eden cesur Gianna, canavarın peşine düşer ve taş kalpli bu varlığı sevgiyle tanıştırmaya çalışır.',
        "mesaj": 'Yazar, sevginin gücüne inanmanın korkulara boyun eğmekten çok daha anlamlı olduğunu anlatıyor. Anne babalarla çocuklar arasındaki ilişkiler üzerine de düşündürüyor.',
        "ulastiklarin": [
            'Korkularının üzerine cesaretle gidebileceğini fark ettin.',
            'Sevginin en katı kalpleri bile yumuşatabileceğini düşündün.',
            'Hayallerine tutkuyla bağlı kalmanın insana güç verdiğini gördün.',
        ],
        "bilgiler": [
            'Operada bir sanatçının tek başına söylediği şarkılara "arya" denir.',
        ],
        "deger": 'Sevgi',
        "deger_neden": "Gianna'nın korkutucu canavarın taşlaşmış kalbini sevgiyle ısıtmaya çalışmasıyla sevginin korkudan daha güçlü olduğunu gördün.",
        "kaynaklar": [
            'https://www.tudem.com/urun/kultur/1008/tudem_edebiyat/2552/kiralik_canavar.aspx',
            'https://tudem.com/images/urundetaykutu/kiralik_canavar.pdf',
            'https://www.perpakitap.com/urun/kiralik-canavar-andreas-steinhofel-9789944699853',
        ],
    },
    'Yabanın Çağrısı': {
        "yazar": 'Jack London',
        "konu": "Buck, Kaliforniya'da zengin bir yargıcın evinde rahat bir hayat süren büyük ve güçlü bir köpektir. Kaçırılıp satılınca kendini kuzeyin dondurucu topraklarında, kızak çeken bir köpek olarak bulur. Zorlu koşullarda ayakta kalmaya çalışırken içindeki yabanıl içgüdüler uyanır ve doğanın çağrısını giderek daha güçlü duyar.",
        "mesaj": 'Yazar, zorluklar karşısında dayanıklı olmayı, uyum sağlamayı ve insanın kendi doğasını keşfetmesini bir köpeğin gözünden anlatıyor. Özgürlüğün ve doğanın gücünü vurguluyor.',
        "ulastiklarin": [
            'Zor koşullara uyum sağlayıp güçlenmenin mümkün olduğunu fark ettin.',
            'Hayvanların da duyguları olduğunu ve onlara iyi davranılması gerektiğini düşündün.',
            'Kendi yolunu seçmenin ve kim olduğunu keşfetmenin önemini gördün.',
        ],
        "bilgiler": [
            "Kitap, 1890'larda insanların altın aramak için akın ettiği Kanada'nın Klondike bölgesinde geçer.",
            'O dönemde kuzeyin karlı topraklarında postalar ve yükler köpeklerin çektiği kızaklarla taşınırdı.',
            'Jack London kitabı 1903 yılında yayımlamıştır.',
        ],
        "deger": 'Özgürlük',
        "deger_neden": "Buck'ın esaretten kurtulup sonunda kendi özgür seçimini yapmasıyla özgürlüğün bir canlı için ne kadar değerli olduğunu gördün.",
        "kaynaklar": [
            'https://www.canyayinlari.com/kitap-vahsetin-cagrisi-9789750754753',
            'https://www.bkmkitap.com/vahsetin-cagrisi-373030',
            'https://litopya.com/kitap/yabanin-cagrisi-jack-london-323582',
            'https://www.edebiyathaber.net/jack-londonin-kult-eseriyabanin-cagrisi-gencler-icin-yeniden-yorumlandi/',
        ],
    },
    'Bisiklet Yarışçıları': {
        "yazar": 'Ferda İzbudak Akıncı',
        "konu": "Karne hediyesi olarak mavi bir bisiklet alan Sur, yeni taşındıkları sitede arkadaşları Can ve Birgül'le bisiklet sürmeye başlar. İnternette Bisiklet Federasyonu'nun yarış takvimini görünce yarışta birinci olmayı kafaya koyar ve arkadaşlarıyla çalışmaya başlar. Ancak birinci olma tutkusu onu kural tanımayan birine dönüştürür ve arkadaşlarıyla, ailesiyle ilişkilerini etkiler.",
        "mesaj": 'Yazar, çocukların hedef koyarak, hayal kurarak ve bu hayaller için çalışarak gelişebileceğini anlatıyor. Kazanma tutkusunun arkadaşlığın ve paylaşmanın önüne geçmemesi gerektiğini hatırlatıyor.',
        "ulastiklarin": [
            'Bir hedefe ulaşmak için düzenli çalışmanın gerektiğini fark ettin.',
            'Kazanmanın, arkadaşlarını kırmaya ve kuralları çiğnemeye değmeyeceğini düşündün.',
            'Sporun, doğanın ve birlikte yapılan çalışmaların güzelliğini gördün.',
        ],
        "bilgiler": [
        ],
        "deger": 'Çalışkanlık',
        "deger_neden": 'Sur ve arkadaşlarının yarışa hazırlanırken gösterdiği emekle hayallerin yalnızca istemekle değil, çalışarak gerçekleşeceğini öğrendin.',
        "kaynaklar": [
            'https://www.tudem.com/urun/kultur/1008/tudem_edebiyat/2395/bisiklet_yariscilari.aspx',
            'https://www.iyikitap.net/2014/05/01/bisiklet-paylasmayi-ogrenmektir/',
            'https://teis.yesevi.edu.tr/madde-detay/ferda-izbudak-akinci-mdbir',
        ],
    },
    'Dünyanın En Önemli Öğrencisi': {
        "yazar": 'Şermin Yaşar',
        "konu": 'Herkesin "Fikri Bey" dediği patron, genel müdür ve yönetim kurulu başkanı, bir gün ortaokuldan hiç mezun olmadığını öğrenir; derslerini tamamlamazsa bütün diplomaları geçersiz sayılacaktır. Okula dönmemek için parayla çözmeyi, rapor almayı, kaçmayı dener ama sonunda çocuklarla aynı sıraları paylaşmak zorunda kalır. Sınıftaki öğrenciler, öğretmenler ve okul hayatı onu yavaş yavaş değiştirir.',
        "mesaj": 'Yazar, unvanların ve paranın insanı değerli yapmadığını, herkesin eşit ve saygıyı hak ettiğini anlatıyor. Öğrenmenin yaşı olmadığını ve yetişkinlerin de çocuklardan öğreneceği çok şey olduğunu gösteriyor.',
        "ulastiklarin": [
            'İnsanların değerinin unvanlarından ya da paralarından gelmediğini fark ettin.',
            'Öğrenmenin her yaşta mümkün ve güzel olduğunu düşündün.',
            'Arkadaşlarına ve öğretmenlerine saygıyla davranmanın okulu daha güzel bir yer yaptığını gördün.',
        ],
        "bilgiler": [
        ],
        "deger": 'Saygı',
        "deger_neden": "Fikri Bey'in sınıftaki çocuklarla eşit olmayı öğrenmesiyle saygının parayla satın alınamayacağını, herkesin saygıyı hak ettiğini gördün.",
        "kaynaklar": [
            'https://cogem.ankara.edu.tr/wp-content/uploads/sites/311/2026/02/Du%CC%88nyanin-En-O%CC%88nemli-O%CC%88g%CC%86rencisi-S%CC%A7ermin-YAS%CC%A7AR-Tanitim-Yazisi.pdf',
            'https://ilkses.com.tr/kultur-sanat/yazar-sermin-yasar-in-yeni-kitabi-raflarda-yerini-aldi-300774',
            'https://mobil.sekizincigunhaber.com/haber/sermin-yasar-in-dunyanin-en-onemli-ogrencisi-kitabi-uzerine/1065/',
        ],
    },
}

_TAKMA_ADLAR = {
    "Sadako ve Kağıttan Bin Turna Kuşu": "Sadako",
    "Yürekdede ile Padişah": "Yürek Dede ile Padişah",
    "Kiraz Ağacı ile Aramızdaki Mesafe": "Kiraz Ağacıyla Aramızdaki Mesafe",
    "Gecen Gündüzüm Olsa": "Gece Gündüzüm Olsa",
    "Vahşetin Çağrısı": "Yabanın Çağrısı",
    "Ormanı Yemek Yasak": "Yeşil Kafalar 1",
    "Duvarları Gıdıklanan Okul": "Yeşil Kafalar 2",
    "Şifrelerin Peşinde İstanbul": "Matematik Romanı: Şifrelerin Peşinde İstanbul",
}

_DIZIN: dict[str, str] = {}


def _dizin() -> dict[str, str]:
    if not _DIZIN:
        for ad in KITAP_ICERIK:
            _DIZIN[_anahtar(ad)] = ad
        for takma, ad in _TAKMA_ADLAR.items():
            _DIZIN[_anahtar(takma)] = ad
    return _DIZIN


def kitap_icerigi(ad: str) -> dict | None:
    gercek = _dizin().get(_anahtar(ad))
    if not gercek:
        return None
    return {"ad": gercek, **KITAP_ICERIK[gercek]}


KITAPLA_KAZANILAN_DEGERLER: list[str] = [d for d in DEGERLER if any(k["deger"] == d for k in KITAP_ICERIK.values())]
