# Plugin de Apolo para YouTube y YouTube Music

Extensión Manifest V3 para navegadores basados en Chromium (Helium, Brave, Chrome) que integra la descarga directa a la biblioteca de Apolo desde la interfaz web de YouTube y YouTube Music.

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
3. Haz clic en **Cargar descomprimida**.
4. Selecciona la carpeta:
   ```text
   /home/hypr/repos/apolo/plugins/youtube
   ```

---

## Uso

### YouTube (youtube.com)
- **Vídeos**: Se añade un botón "Apolo" en la barra de acciones debajo del reproductor.
- **Playlists**: Se añade el botón "Descargar Playlist" en la cabecera de la lista.

### YouTube Music (music.youtube.com)
- **Barra de reproducción**: Se añade un icono discreto en los controles inferiores para descargar la pista en reproducción.
- **Álbumes y Playlists**: Se añade el botón "Descargar con Apolo" en la barra de acciones de la cabecera.

### Menú de la extensión
- Indicador de estado de conexión (`online` / `offline`).
- Botón para descargar la pestaña activa.
- Historial de descargas recientes.
