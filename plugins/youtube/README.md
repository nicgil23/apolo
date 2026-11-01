# Plugin de Apolo para YouTube y YouTube Music

Extensión Manifest V3 ligera para navegadores basados en Chromium (Helium, Brave, Chrome) que integra la descarga directa a la biblioteca de Apolo desde el navegador.

---

## Requisitos

1. Apolo instalado en el sistema.
2. Servidor local de Apolo activo:
   ```bash
   apolo serve
   ```
   *(O mediante el servicio de systemd: `systemctl --user start apolo-server`)*

---

## Instalación en Helium / Chromium

1. Abre `chrome://extensions` en tu navegador.
2. Activa el **Modo de desarrollador** (arriba a la derecha).
3. Haz clic en **Cargar descomprimida** (Load unpacked).
4. Selecciona la carpeta:
   ```text
   /home/hypr/repos/apolo/plugins/youtube
   ```

---

## Uso

Al hacer clic en el icono de Apolo en la barra de extensiones del navegador:

- **Descarga con 1 clic**: Pulsa "Descargar pestaña activa" mientras estés en cualquier vídeo, canción, álbum o playlist de YouTube o YouTube Music.
- **Monitor de estado**: Muestra si el servidor local de Apolo está conectado (`127.0.0.1:4533`).
- **Historial y progreso en vivo**: Visualiza el progreso en tiempo real de descargas individuales y listas de reproducción, con opción de cancelar tareas o vaciar el historial.
