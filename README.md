# DualSense Blender Navigator

PS5 DualSense ile Blender'ın 3D View alanında gezinmek için Windows eklentisi.
USB ve Bluetooth HID girdilerini doğrudan okur; ek Python paketi veya sürücü gerektirmez.

## Kurulum

1. `dist/dualsense_navigator-1.0.0.zip` paketini oluştur veya sağlanan ZIP'i kullan.
2. Blender: **Edit > Preferences > Add-ons > sağ üst menü > Install from Disk**.
3. ZIP'i seç ve **DualSense Navigator** eklentisini etkinleştir.
4. Otomatik tercih kaydı kapalıysa **Save Preferences** seç.
5. 3D View içinde **N > DualSense > DualSense ile gezin**.

Fareyi 3D View içinde tut. Blender ön planda değilse hareket duraklar.
Eklentinin etkinleşmesi gezinmeyi kendiliğinden başlatmaz.

| Kontrol | İşlev |
|---|---|
| Sol çubuk | İleri/geri, sağa/sola |
| Sağ çubuk | Etrafa bakış |
| L2 / R2 | Alçal / yüksel |
| L1 / R1 basılı | Hassas 0.2× / hızlı 4× hareket |
| D-pad yukarı / aşağı | Hız artır / azalt |
| X | Duraklat / sürdür |
| Üçgen | Yatay yürüyüş / bakış yönünde uçuş |
| Daire | Başlangıç görünümüne dön ve bitir |
| Options / Esc | Son konumda bitir |

Panelden hız, bakış hızı, deadzone ve dikey bakış yönü ayarlanır.
Yalnızca viewport değişir. Sahnedeki kamera veya nesnelerin dönüşümleri değişmez.
Yerçekimi, duvar çarpışması, roll, FOV kontrolü ve kamera yolu kaydı 1.0.0'da yoktur.

## Uyumluluk ve doğrulama

- Paket hedefi: Windows x64, Blender 4.2+.
- Test edilen: Blender 5.2.2 LTS, standart DualSense, enhanced Bluetooth HID.
- USB/basic Bluetooth/enhanced Bluetooth ayrıştırma, CRC, deadzone, stale-input koruması
  ve gerçek RegionView3D hareket/bakış geometrisi: 24 kontrol geçti.
- Ayrı GUI oturumunda modal başlatma, durdurma ve yeniden başlatma testleri geçti.
- Extension ZIP kurulumu, devre dışı bırakma, yeniden etkinleştirme ve kayıtlı test
  profilinden tekrar yükleme geçti.
- Fiziksel USB, DualSense Edge ve Blender'ın diğer sürümleri test edilmedi.
- Birden fazla controller varsa ilk erişilebilir cihaz kullanılır. Quad View desteklenmez.
- Steam Input / HidHide cihazı gizliyorsa eklentinin cihazı görmesine izin verilmelidir.

## Geliştirme

Kaynak eklenti `__init__.py`, paket tanımı `blender_manifest.toml` dosyasındadır.

```powershell
.\scripts\build.ps1 -BlenderExe 'C:\Program Files (x86)\Steam\steamapps\common\Blender\blender.exe'
.\scripts\test.ps1 -BlenderExe 'C:\Program Files (x86)\Steam\steamapps\common\Blender\blender.exe'
```

Build Blender'ın kendi extension aracıyla ZIP oluşturur ve doğrular. Testler kullanıcı
tercihleri yerine önceden oluşturulmuş `.test-profile` dizinini kullanır; gerçek tercih
dizinine yönelirse test kayıt yapmadan durur. Sonuçlar `test-output` altındadır.

## CameraTools incelemesi

[Cyberpunk CameraTools v1.0.44 gamepad incelemesi](docs/cameratools-review.md), eklentiye
alınabilecek özellikleri ve önceliklerini açıklar. Bu özellikler 1.0.0'a eklenmiş değildir.
Vendor DLL/EXE veya kaynak kodu bu repoya dahil edilmemiştir.

## Lisans ve kaynaklar

GPL-3.0-or-later; [LICENSE](LICENSE).

- [DualSense HID rapor haritası](https://github.com/nondebug/dualsense/blob/main/README.md)
- [PlayStation HID sürücüsü](https://github.com/torvalds/linux/blob/master/drivers/hid/hid-playstation.c)
- [Microsoft HID input documentation](https://learn.microsoft.com/en-us/windows-hardware/drivers/hid/obtaining-hid-reports)
