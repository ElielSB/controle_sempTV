import asyncio
import threading
import socket
import os
from functools import partial

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.popup import Popup
from kivy.clock import Clock
from kivy.core.window import Window

from zeroconf import Zeroconf, ServiceBrowser
from androidtvremote2 import AndroidTVRemote

# Cor de fundo escura estilo controle moderno
Window.clearcolor = (0.1, 0.1, 0.1, 1)

class ControleSempApp(App):
    def build(self):
        self.remote = None
        self.loop = asyncio.new_event_loop()
        
        # Inicia o motor assíncrono em segundo plano para não travar a tela
        threading.Thread(target=self._iniciar_loop_async, daemon=True).start()

        # Layout Principal
        self.layout_principal = BoxLayout(orientation='vertical', padding=20, spacing=15)

        # Texto de Status no topo
        self.lbl_status = Label(
            text="Procurando TV Semp no Wi-Fi...",
            size_hint=(1, 0.1),
            font_size='18sp',
            bold=True,
            color=(0, 1, 0.5, 1)
        )
        self.layout_principal.add_widget(self.lbl_status)

        # Grade de Botões (6 linhas x 3 colunas)
        grade = GridLayout(cols=3, spacing=12, size_hint=(1, 0.9))

        # Definição dos botões: (Texto, Código_Tecla_Oficial, Cor_RGBA)
        cor_padrao = (0.22, 0.22, 0.22, 1)
        cor_power = (0.8, 0.15, 0.15, 1)
        cor_ok = (0, 0.48, 0.8, 1)

        botoes = [
            ("", None, (0,0,0,0)), ("DESLIGAR", "POWER", cor_power), ("", None, (0,0,0,0)),
            ("", None, (0,0,0,0)), ("▲", "DPAD_UP", cor_padrao), ("", None, (0,0,0,0)),
            ("◀", "DPAD_LEFT", cor_padrao), ("OK", "DPAD_CENTER", cor_ok), ("▶", "DPAD_RIGHT", cor_padrao),
            ("", None, (0,0,0,0)), ("▼", "DPAD_DOWN", cor_padrao), ("", None, (0,0,0,0)),
            ("Voltar", "BACK", cor_padrao), ("Home", "HOME", cor_padrao), ("Mudo", "VOLUME_MUTE", cor_padrao),
            ("Vol -", "VOLUME_DOWN", cor_padrao), ("", None, (0,0,0,0)), ("Vol +", "VOLUME_UP", cor_padrao),
        ]

        for texto, comando, cor in botoes:
            if comando is None:
                # Espaço vazio para manter o alinhamento da cruz direcional
                grade.add_widget(Label())
            else:
                btn = Button(
                    text=texto,
                    font_size='20sp',
                    bold=True,
                    background_normal='',
                    background_color=cor
                )
                btn.bind(on_press=partial(self.ao_clicar_botao, comando))
                grade.add_widget(btn)

        self.layout_principal.add_widget(grade)

        # Inicia a busca pela TV na rede assim que o app abre
        threading.Thread(target=self.buscar_e_conectar_tv, daemon=True).start()

        return self.layout_principal

    def _iniciar_loop_async(self):
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    def atualizar_status(self, texto, cor=(0, 1, 0.5, 1)):
        Clock.schedule_once(lambda dt: setattr(self.lbl_status, 'text', texto))
        Clock.schedule_once(lambda dt: setattr(self.lbl_status, 'color', cor))

    def buscar_e_conectar_tv(self):
        ip_tv = None
        nome_tv = "Android TV"

        class Ouvinte:
            def remove_service(self, zc, type, name): pass
            def update_service(self, zc, type, name): pass
            def add_service(self, zc, type, name):
                nonlocal ip_tv, nome_tv
                info = zc.get_service_info(type, name)
                if info and info.addresses:
                    ip_tv = socket.inet_ntoa(info.addresses[0])
                    nome_tv = name.split('.')[0]

        zc = Zeroconf()
        ServiceBrowser(zc, "_androidtvremote2._tcp.local.", Ouvinte())
        
        import time
        for _ in range(50): # Procura por até 5 segundos
            if ip_tv:
                break
            time.sleep(0.1)
        zc.close()

        if not ip_tv:
            self.atualizar_status("Nenhuma Android TV achada no Wi-Fi.", (1, 0.3, 0.3, 1))
            return

        self.atualizar_status(f"Conectando a {nome_tv} ({ip_tv})...")
        asyncio.run_coroutine_threadsafe(self._conectar_protocolo_oficial(ip_tv, nome_tv), self.loop)

    async def _conectar_protocolo_oficial(self, ip_tv, nome_tv):
        # Define onde os certificados digitais serão salvos no celular
        pasta_dados = self.user_data_dir
        cert_file = os.path.join(pasta_dados, "cert.pem")
        key_file = os.path.join(pasta_dados, "key.pem")

        self.remote = AndroidTVRemote(
            client_name="Controle Semp App",
            certfile=cert_file,
            keyfile=key_file,
            host=ip_tv
        )

        # Gera certificados na primeira vez que o app é aberto
        await self.remote.async_generate_cert_if_missing()

        try:
            await self.remote.async_connect()
            self.atualizar_status(f"Conectado: {nome_tv}")
        except Exception:
            # Se ainda não foi pareado, inicia o pedido de PIN na tela da TV
            await self.remote.async_start_pairing()
            Clock.schedule_once(lambda dt: self.abrir_janela_pin(nome_tv))

    def abrir_janela_pin(self, nome_tv):
        box = BoxLayout(orientation='vertical', padding=15, spacing=10)
        box.add_widget(Label(text=f"Digite o código de 6 dígitos\nque apareceu na tela da {nome_tv}:"))
        
        entrada_pin = TextInput(multiline=False, font_size='24sp', halign='center')
        box.add_widget(entrada_pin)

        btn_confirmar = Button(text="Conectar", size_hint=(1, 0.4), background_color=(0, 0.6, 0.3, 1))
        box.add_widget(btn_confirmar)

        popup = Popup(title="Pareamento da TV", content=box, size_hint=(0.85, 0.45), auto_dismiss=False)

        def confirmar(instance):
            pin = entrada_pin.text.strip()
            if pin:
                popup.dismiss()
                asyncio.run_coroutine_threadsafe(self._finalizar_pareamento(pin, nome_tv), self.loop)

        btn_confirmar.bind(on_press=confirmar)
        popup.open()

    async def _finalizar_pareamento(self, pin, nome_tv):
        try:
            await self.remote.async_finish_pairing(pin)
            await self.remote.async_connect()
            self.atualizar_status(f"Conectado: {nome_tv}")
        except Exception as e:
            self.atualizar_status("PIN inválido ou erro ao parear.", (1, 0.3, 0.3, 1))

    def ao_clicar_botao(self, comando, instance):
        if self.remote:
            try:
                self.remote.send_key_command(comando)
            except Exception as e:
                print("Erro ao enviar comando:", e)

if __name__ == '__main__':
    ControleSempApp().run()
