$ErrorActionPreference = "Stop"
$env:JAVA_HOME = "C:\Program Files\Android\Android Studio\jbr"
$env:Path = "$env:JAVA_HOME\bin;" + $env:Path

$buildTools = "C:\Users\Admin\AppData\Local\Android\Sdk\build-tools\36.0.0"
$androidJar = "C:\Users\Admin\AppData\Local\Android\Sdk\platforms\android-36\android.jar"
$jarExe = "$env:JAVA_HOME\bin\jar.exe"

Write-Host "Linking resources..."
& "$buildTools\aapt2.exe" link -I $androidJar --manifest AndroidManifest.xml -o base.apk resources.zip --min-sdk-version 24 --target-sdk-version 35

Write-Host "Adding classes.dex..."
Copy-Item base.apk unaligned.apk -Force
& "$jarExe" -uf unaligned.apk classes.dex

Write-Host "Aligning and signing..."
Remove-Item aligned.apk, VaultCompanion.apk, VaultCompanion.apk.idsig -Force -ErrorAction SilentlyContinue
& "$buildTools\zipalign.exe" -p -f -v 4 unaligned.apk aligned.apk
& "$buildTools\apksigner.bat" sign --ks debug.keystore --ks-pass pass:android --out VaultCompanion.apk aligned.apk

Write-Host "Installing to connected device..."
adb install -r VaultCompanion.apk
Write-Host "Done!"
