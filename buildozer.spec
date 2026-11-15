[app]
title = Controle Semp
package.name = controlesemp
package.domain = org.meuapp
source.dir = .
source.include_exts = py,png,jpg,kv,atlas
version = 1.0

# Bibliotecas necessárias para o app funcionar no Android
requirements = python3,kivy,zeroconf,androidtvremote2,protobuf,cryptography,ifaddr

orientation = portrait
fullscreen = 0

# Permissões essenciais para achar e controlar a TV no Wi-Fi
android.permissions = INTERNET,ACCESS_NETWORK_STATE,ACCESS_WIFI_STATE,CHANGE_WIFI_MULTICAST_STATE

android.api = 33
android.minapi = 21
android.archs = arm64-v8a
android.accept_sdk_license = True

[buildozer]
log_level = 2
warn_on_root = 1
