# Cyberpunk CameraTools v1.0.44: gamepad incelemesi

İnceleme tarihi: 2026-10-09. Yerel paketin `Readme.txt`, `IGCSClientSettings.ini`
ve istemci EXE'sindeki statik UI etiketleri incelendi. EXE/DLL çalıştırılmadı,
oyuna DLL enjekte edilmedi, mevcut CameraTools ayarları değiştirilmedi.
Özellikler bağımsız Blender uygulaması için değerlendirilmiştir.

## Yerel ayarların gösterdiği profil

| Ayar | Yerel değer | Blender açısından anlamı |
|---|---:|---|
| `MovementSpeed` | 0.04 | Oyuna özgü ölçek; Blender birim/sn değerine doğrudan taşınmaz |
| `RotationSpeed` | 0.04 | Blender'da derece/sn cinsinden ayrı kontrol gerekir |
| `FastMovementMultiplier` | 20 | Mevcut Blender eklentisi 4×; ayarlanabilir olabilir |
| `SlowMovementMultiplier` | 0.1 | Mevcut Blender eklentisi 0.2× |
| `UpMovementMultiplier` | 0.7 | Dikey hareket için ayrı hız katsayısı yararlı |
| `InterpolationFactorMovement` | 8 | Hareket yumuşatması açık |
| `InterpolationFactorRotation` | 8 | Bakış yumuşatması açık |
| `InterpolationFactorFoV` | 1 | FOV'a ek yumuşatma uygulanmıyor |
| `FoVZoomSpeed` | 0.4217879 | Ayrı zoom hızı |
| `InvertYLookDirection` | False | Dikey bakış ters çevrilmemiş |
| Hareket / dönüş stick seçimi | 0 / 1 | Sol hareket, sağ bakış |
| Yukarı / aşağı trigger seçimi | 0 / 1 | Sol tetik yükseltir, sağ tetik alçaltır |
| Hareket/dönüş shake frekans ve gücü | Hepsi 0 | Kullanıcının mevcut profilinde shake kapalı |

`CameraControlDevice=1` dosyada mevcut. Sayısal cihaz modu enumunun anlamını yalnızca
INI'den kesinleştirmiyoruz. Modların controller/klavye-fare/ikisi olarak sunulduğu belgeli.
Interpolation sayıları milisaniye değildir; Blender'a aynı sayıyı kopyalamak aynı hissi sağlamaz.

## Gamepad düzeni

Yerel INI'deki eylemler, istemcideki button UI sırası ve resmi kontrol tablosu birlikte
okunduğunda aşağıdaki düzen görülüyor. DualSense karşılıkları fiziksel konuma göredir;
CameraTools'un native DualSense USB/Bluetooth desteği burada çalıştırılarak doğrulanmadı.

| İşlev | Xbox adı | DualSense karşılığı |
|---|---|---|
| Hızlı / yavaş hareket | Y / X | Üçgen / Kare |
| FOV daralt / genişlet | D-pad yukarı / aşağı | Aynı |
| FOV sıfırla | B | Daire |
| Roll sola / sağa | D-pad sol / sağ | Aynı |
| Kamera yolu node ekle | A | X |
| Önceki / sonraki node | LB / RB | L1 / R1 |
| Yol oynat/duraklat | Start | Options |
| Yol durdur | Back | Create |
| Gamespeed modunu aç/kapat | Sol stick basma | L3; değiştirici davranışı çalışma anında test edilmedi |

İlk eklentinin tetik yönü bunun tersidir: **L2 alçalır, R2 yükselir**. Eşleşme değiştirilirse
ayrı bir “CameraTools” profiliyle yapılmalıdır. Mevcut X duraklatma, Options bitirme,
L1/R1 hız ve D-pad hız tuşları yeni kamera-yolu/FOV işlevleriyle çakışır.

Readme v1.0.19 hızlı hareket katsayısının dönüşü artık etkilemediğini söylüyor.
Güncel genel kontrol tablosunda daha geniş bir ifade var; kurulu sürüm için yerel
changelog'u esas alıyoruz. Yavaş bakış ve hızlı hareket katsayıları ayrı tasarlanabilir.

## Alınabilecek özellikler

| Öncelik | Özellik | Blender uygulaması ve sınırı |
|---|---|---|
| 1 | Ayrı hareket/bakış/FOV yumuşatması | FPS'ten bağımsız zaman sabitleriyle input filtreleme; bağlantı kesilince filtre kuyruğu hemen sıfırlanmalı |
| 1 | Serbest tuş eşleme ve profiller | Gezinme ve sinematik mod, solak stick değişimi, tetik yönünü seçme; çakışma kontrolü |
| 1 | FOV zoom ve sıfırlama | Viewport lens kontrolü; gerçek kamera lensini değiştirmek ayrıca açık bir mod olmalı |
| 1 | Roll ve ufuk sıfırlama | D-pad sol/sağ, R3 sıfırla önerilebilir; mevcut her-frame ufuk sabitleme değiştirilir |
| 1 | Ayarlanabilir hızlı/yavaş/dikey hız | 20×, 0.1×, 0.7 gibi kullanıcı değerlerini profil olarak saklama; hızları Blender birimlerine göre kalibre etme |
| 2 | Üç kamera bookmark slotu | Bakış konumu, dönüş ve lens; Scene özelliklerinde saklanarak .blend ile taşınabilir |
| 2 | Node tabanlı kamera yolları | Controller'dan node ekle/gez/oynat; gerçek Camera nesnesine transform ve lens keyframe'leri üretme |
| 2 | Yol easing ve sabit hız | Yol uzunluğu üzerinden yeniden örnekleme; yalnızca keyframe'leri eşit aralıklarla koymak sabit dünya hızı sağlamaz |
| 3 | Ayrı hareket/dönüş shake | Seed'li prosedürel noise; isteğe bağlı, varsayılan kapalı |
| 3 | Zaman/framestep | Blender timeline/frame ve animasyon playback kontrolü; oyunun global timescale'inin bire bir karşılığı değildir |
| 3 | HUD/overlay gizleme | Viewport overlays/gizmos; Blender'ın tüm arayüzünü veya render çözünürlüğünü değiştirmez |

En yararlı ilk sürüm: **smoothing + FOV + roll + yapılandırılabilir sinematik profil**.
Sonraki adım: **bookmark + controller ile kamera yolu/keyframe kaydı**.
Node oynatma sırasında manuel navigasyonun kamera dönüşümlerini ezmemesi sağlanmalı.

## Doğrudan taşınmayan özellikler

Hotsampling'in Blender karşılığı oyun penceresini büyütmek değil render çözünürlüğüdür.
Islaklık/su birikintisi shader'a; gün saati ışık rig'ine; head/body/eyes look-at karakter
rig'ine bağlıdır. Bunlar genel viewport navigasyon eklentisine tek bir global slider olarak
eklenemez. CyberLit, yerel v1.0.33 changelog'una göre ana araçtan ayrılmıştır; eski özellik
listesinde “integrated” yazması bu v1.0.44 paketinde yerleşik olduğunu kanıtlamaz.

## Kanıt ve referanslar

Yerel dosya SHA256'ları (vendor dosyalarının kendisi dağıtılmıyor):

- `Readme.txt`: `405893a7cf51c9e7dba2532ae09188c736f88aeb85d1c3a58f581f2f2906b3c7`
- `IGCSClientSettings.ini`: `e1c4385c9f2efbf71cfbf6181d3f68c176b1965700d3f225c550f5a266027ae7`

Resmi belgeler daha yeni sürümleri de anlatabilir; kurulu 1.0.44'e ilişkin iddialar yerel
config/changelog ile sınırlandı. Önerilen Blender karşılıkları uygulama tasarımıdır,
CameraTools kaynak kodunun aktarımı değildir. 1.0.0 eklentisine henüz eklenmemişlerdir.

- [Genel yapılandırma ve kontrol listesi](https://opm.fransbouma.com/generalconfiguration.htm)
- [Kamera yolları](https://opm.fransbouma.com/camerapaths.htm)
- [Cyberpunk özellikleri ve CyberLit ayrımı](https://opm.fransbouma.com/Cameras/cyberpunk2077.htm)
