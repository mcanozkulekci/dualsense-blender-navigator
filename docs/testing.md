# Test edilen kapsam

2026-10-09, Windows x64, Blender 5.2.2 LTS, standart DualSense.

- 24 runtime kontrolü: USB/basic-Bluetooth/enhanced-Bluetooth parser, CRC,
  deadzone, stale input/reconnect ve gerçek RegionView3D hareket geometrisi.
- Canlı Bluetooth enhanced raporları okunabildi.
- Ayrı GUI oturumunda modal başlatma/durdurma/yeniden başlatma geçti.
- Extension paketi Blender'ın build/validate araçlarından geçti.
- Install from Disk operatorü, disable/enable ve kaydedilmiş izole profilden
  yeniden yükleme geçti. Normal tercih dosyasının SHA256'sı bu son test akışında değişmedi.

USB paket ayrıştırma testi fiziksel USB cihaz testi değildir. DualSense Edge cihaz
kimliği tanınır fakat fiziksel Edge test edilmedi. Diğer Blender sürümleri ve controller'ın
tüm düğmeleri kullanıcı tarafından uçtan uca test edilmiş değildir.

`scripts/test.ps1` config ve extension dizinlerini Blender başlamadan oluşturur.
`tests/verify_install.py`, gerçek config yolu test profiliyle eşleşmiyorsa herhangi bir
tercih kaydı yapmadan durur. Boş/var olmayan bir BLENDER_USER_CONFIG dizininin izolasyon
sağladığı varsayılmamalıdır.
