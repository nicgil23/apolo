[Si eres español y te gusta la paella pulsa aquí](#spanish-version)

---

# The Local Music Journey

If you've ended up in this repository, it means that one way or another you want to start truly 'owning' the music you listen to—whether it's for collecting it or to break free from streaming platforms like Spotify, Apple Music, or YouTube Music.

## Why Bother Going Through All This Trouble?

- **Say goodbye to ads and subscriptions forever**: you control your music and where you play it, so you'll never have to worry about 60-second unskippable ads or recurring $10/month subscription fees.
- **All your music in one place**: no need to jump between platforms just because an indie or niche artist isn't available on one of them; you have everything stored locally.
- **It's an enjoyable journey**: you'll learn far more about music technology than you currently know: codecs, metadata tags, loudness normalization, and audio engineering basics.
- **Immunity to network outages and licensing disputes**: your library is always accessible offline. You'll never see your favorite tracks grayed out or abruptly deleted overnight just because a platform lost its regional distribution rights.
- **Absolute control over audio quality**: you decide the exact format and bitrate of every file—keeping bit-perfect lossless masters or efficient custom encodes—without being subject to dynamic compression algorithms or variable bitrates imposed by streaming services.
- **You get to be a larper**: you can boast about how unique and cultured you are for not relying on mainstream streaming algorithms, or even better, load everything onto a retro iPod to achieve peak supreme larper status.
- Perhaps most importantly, **you can genuinely support the artists you love**: streaming platforms pay artists notoriously little. For instance, YouTube pays around \$0.001–\$0.002 per view, and Tidal (the highest-paying mainstream platform) hovers around \$0.012–\$0.015. This means that to match the revenue of buying a single \$5.88 album on Bandcamp (which delivers 85% directly to the artist), you would need to stream that artist's songs anywhere between 333 and 5,000 times.

| Platform | Payout per Stream | Streams Needed to Match $5 |
| :--- | :--- | :--- |
| **Tidal** | $0.012 - $0.015 | 333 - 417 |
| **Apple Music** | $0.007 - $0.010 | 500 - 714 |
| **Deezer** | $0.005 - $0.007 | 714 - 1,000 |
| **Amazon Music** | $0.004 - $0.008 | 625 - 1,250 |
| **Spotify** | $0.003 - $0.005 | 1,000 - 1,667 |
| **YouTube Music** | $0.001 - $0.002 | 2,500 - 5,000 |

If you were supporting an artist through Spotify's average payout ($0.004), you would have to play their music **1,250 times** to match that exact same economic impact.

I could keep listing reasons, but you get the point: it's up to you to decide whether it's worth it. Obviously, it's not without trade-offs—you'll have to invest some initial time and effort—but the end result is deeply rewarding.

---

## Where Do I Get the Music?

### Traditional Methods

- **Bandcamp**: The best platform for directly supporting independent artists and record labels (artists take home ~85% of each sale). Whenever you buy a track or album, the platform lets you download it in DRM-free lossless formats like FLAC, ALAC, WAV, or AIFF. Similar high-quality digital storefronts include: **Qobuz**, **HDtracks**, **Bleep**, **Juno Download**, **7digital**, and **HIGHRESAUDIO**.
- **Ripping CDs / Vinyl**: Extracting uncompressed digital audio directly from your physical media is one of the most reliable ways to guarantee pristine lossless quality using battle-tested tools such as **Exact Audio Copy (EAC)** (Windows) or **Whipper** (Linux).

### Modern Methods

- **YouTube Downloads with `apolo`**: A CLI tool that uses `yt-dlp` to extract audio streams directly from YouTube servers. Although it uses lossy formats (.opus, which YouTube serves at roughly 130–160 kbps), the quality is remarkably clean (unless you're listening through high-end audiophile gear, you won't hear any difference).
- **Soulseek**: A legendary peer-to-peer (P2P) network focused almost entirely on sharing music archives. It is hands down the most effective way to hunt down lossless FLAC rips, complete discographies, rare b-sides, or out-of-print recordings that are nowhere to be found on official platforms. To connect, you'll need a client: personally I use SoulseekQt, but **Nicotine+** is a modern, polished alternative with a clean interface.

### Frequently Asked Questions (FAQ)

#### I want to download music directly from Spotify / Apple Music
To be clear: currently, it is technically impossible to download audio directly from Spotify or Apple Music streams (which are encrypted with DRM like FairPlay, unlike purchasing DRM-free M4A tracks from the classic iTunes Store). I strongly recommend looking into alternative channels instead.

Moreover, even if someone managed to strip Spotify's DRM, the maximum quality available is lossy Ogg Vorbis at 320 kbps. If your motivation for building a local library is maximizing audio fidelity, cracking Spotify makes very little sense compared to real lossless (FLAC) sources like Soulseek or Bandcamp.

Whenever someone claims to have an app that "downloads songs from Spotify/Apple Music for free", all it's really doing under the hood is reading the track metadata and searching YouTube to grab the audio. And if that's genuinely not what they're doing, please, have them explain how they cracked it and I'll gladly buy them a kebab.

#### How do I download a Spotify playlist?
If you're looking for a way to batch-download playlists straight from Spotify, I have bad news: there is no 100% reliable way to automate this. The only practical workaround is parsing the metadata of each track in the playlist and running automated searches against YouTube one by one.

What's the catch? Roughly 1 out of every 10 songs (depending on how mainstream your taste is—the more obscure, the worse it gets) will end up matching the wrong video or audio version. I actually tried implementing this feature in this repository, but the false matches were frustrating enough that I decided to remove it.

To avoid migrating hundreds or thousands of songs by hand, the best approach is using free web tools like **TuneMyMusic** or **Soundiiz** to convert your Spotify playlist into a YouTube playlist automatically. Once the playlist is generated on YouTube, simply hand the URL over to `apolo` to download the entire list.

---

## I Have the Music, Now What?

### Where to Listen?

- **Desktop (Linux, macOS, and Windows)**: Having tested dozens of open-source desktop players, I cannot recommend anything higher than [Tauon](https://github.com/Taiko2k/Tauon). It is fast, lightweight, visually appealing, and runs on all major platforms. If you want something different, check out [rmpc](https://rmpc.mierak.dev/) (a terminal UI player powered by the [mpd](https://github.com/MusicPlayerDaemon/MPD) daemon) or [Harmonoid](https://harmonoid.com/) (styled around Material 3).
- **Mobile (Android)**: I've tried even more mobile music apps than desktop ones, and my personal favorite is [PixelPlayer](https://github.com/PixelPlayerHQ/PixelPlayer)—a clean Material 3 player available as an APK. There are also great options directly on Google Play, such as Harmonoid.

*Sorry iPhone users, I don't use iOS, so you'll have to explore the App Store on your own.*

### How to Transfer Between Devices?

- **Physical Cable / Drive**: The most rudimentary approach. It worked in 2010, but please do yourself a favor and invest a little time to set up something smoother for the future—especially with how quick and easy it is to configure things nowadays with AI assistance.
- **Google Drive**: Use Google Cloud as both a syncing bridge and an off-site backup. Upload your collection from your computer and sync it down to your phone or secondary machines. For this setup, I recommend **`rclone`** on Linux, **`Google Drive Desktop`** on Windows, and **`DriveSync`** on Android.
- **Self-hosted Streaming with Jellyfin**: If your library is too large to fit comfortably on your phone's local storage, host your own open-source streaming platform. By running a Jellyfin server on your home PC, a NAS, or a Raspberry Pi, it indexes your music collection and lets you stream it anywhere over the internet. Most of the players recommended above feature native Jellyfin integration out of the box (with the exception of rmpc/mpd, which needs plugins).

---

Written by nicgil23, because music is my favorite art form, and I like having full control over it.

### References
- [deckard's Guide](https://www.youtube.com/watch?v=WafxmKRIoQc)
- Extensive hands-on experimentation with numerous alternatives over the time.

<br>

---
---

<br>

<a id="spanish-version"></a>

# El viaje de la música local

Si has terminado en este repositorio, significa que de una manera o de otra quieres empezar a 'poseer' la música que escuchas, ya sea para coleccionarla o para no depender de servicios de streaming como Spotify, Apple Music o YouTube Music.

## ¿Por qué complicarse tanto?

- **Adiós a los anuncios y suscripciones para siempre**: tú controlas tu música y dónde la escuchas, por lo que no te vas a tener que preocupar por anuncios de 60 segundos, ni suscripciones de 10 euros al mes permanentes.
- **Toda tu música en un mismo sitio**: no vas a tener que cambiar de plataforma cada vez que quieras escuchar un artista más nicho, ya que tienes todo descargado.
- **Es un viaje entretenido**: vas a aprender mucho más de lo que sabes ahora mismo sobre música: codecs, metadatos, normalización...
- **Inmunidad a la conexión y licencias**: tu biblioteca está siempre disponible sin depender de internet y evitas que tus canciones favoritas desaparezcan repentinamente de un día para otro porque la plataforma de turno pierda los derechos de distribución.
- **Control absoluto sobre la calidad de audio**: tú decides el formato y el bitrate exacto de cada archivo, pudiendo conservar copias sin pérdida o usar codificaciones eficientes a tu medida, sin estar sujeto a los algoritmos de compresión dinámicos de cada servicio.
- **Puedes ser un larper**: puedes gritar que eres único y especial por no usar plataformas de streaming para escuchar música, o aún mejor, puedes escuchar la música desde un iPod antiguo o algo parecido para llegar al nivel de larper supremo.
- Posiblemente la más importante, **puedes apoyar de verdad la música que más te gusta**: las plataformas de streaming generalmente pagan mal a artistas. Por ejemplo, YouTube paga de \$0,001-\$0,002 por visita y Tidal, que es la que mejor paga, oscila \$0,012-\$0,015. Esto significa que para igualar, por ejemplo, la compra de un álbum en Bandcamp (que le cede el 85% de la venta a los artistas) de 5,88$, tendrías que escuchar entre 333 y 5000 veces canciones de dicho artista.

| Plataforma | 1 reproducción | Escuchas para 5$ |
| :--- | :--- | :--- |
| **Tidal** | $0,012 - $0,015 | 333 - 417 |
| **Apple Music** | $0,007 - $0,010 | 500 - 714 |
| **Deezer** | $0,005 - $0,007 | 714 - 1.000 |
| **Amazon Music** | $0,004 - $0,008 | 625 - 1.250 |
| **Spotify** | $0,003 - $0,005 | 1.000 - 1.667 |
| **YouTube Music** | $0,001 - $0,002 | 2.500 - 5.000 |

Si dieses soporte al artista desde el promedio de Spotify ($0,004), tendrías que reproducir su música **1.250 veces** para conseguir ese mismo impacto económico.

Podría seguir dando más razones de por qué hacerlo, pero creo que no es necesario continuar: tú decides si te merece la pena o no. Obviamente no todo son ventajas, vas a tener que gastar tiempo y esfuerzo, pero creo que el resultado acaba mereciendo la pena.

---

## ¿De dónde saco la música?

### Medios convencionales

- **Bandcamp**: ideal para apoyar directamente a los artistas y sellos independientes (los artistas se llevan un 85% de la venta). Al realizar la compra de un disco o pista, el sistema siempre ofrece la opción de descargar los archivos en formatos sin pérdida como FLAC, ALAC, WAV o AIFF. Como esta plataforma existen muchas otras: **Qobuz**, **HDtracks**, **Bleep**, **Juno Download**, **7digital**, **HIGHRESAUDIO**.
- **Ripear CD/Vinilos**: extraer el audio digital directamente de tus medios físicos es una de las formas más seguras de garantizar calidad sin pérdida usando estándares como **Exact Audio Copy (EAC)** (Windows) o **Whipper** (Linux).

### Medios modernos

- **Descargas de YouTube con `apolo`**: herramienta que, usando `yt-dlp`, extrae el audio directamente de los servidores de YouTube. Aunque se trata de formatos con pérdida (.opus, que YouTube sirve a unos 130-160 kbps), la calidad a la que se descarga es bastante buena (a no ser que tengas un equipo de audio de alta gama, no vas a notar diferencia).
- **Soulseek**: red P2P (peer-to-peer) histórica enfocada casi exclusivamente en compartir bibliotecas musicales. Es el método más efectivo para encontrar archivos FLAC sin pérdida, discografías completas, géneros muy nicho o rips descatalogados que ya no existen en plataformas oficiales. Para conectarse a la red hace falta un cliente: personalmente utilizo SoulSeekQT, pero Nicotine+ es una alternativa más moderna y estética, por si te interesa.

### Preguntas frecuentes

#### Quiero descargar música de Spotify/Apple Music
Quiero puntualizar que actualmente es imposible descargar música de manera directa desde Spotify o Apple Music (cuyo servicio de streaming cifra las pistas con DRM FairPlay, a diferencia de la compra de archivos M4A sin DRM en la tienda clásica de iTunes), por lo que te recomiendo usar otras vías.

Además, incluso si alguien lograse romper el DRM de Spotify, la calidad máxima que obtendría es Ogg Vorbis a 320 kbps (con pérdida). Si el objetivo de coleccionar música local es obtener la máxima fidelidad, piratear Spotify no tiene sentido frente a alternativas sin pérdida (FLAC) como Soulseek o Bandcamp.

Si alguien reclama tener una herramienta que 'descarga' canciones de Spotify/Apple Music de manera gratuita, lo que hace realmente es extraer los metadatos de dicha canción y hacer una consulta a YouTube para la descarga. Y si no es así, por favor, que me explique cómo lo ha hecho y le invito a un kebab.

#### ¿Cómo me descargo una playlist de Spotify?
Si estás buscando maneras de descargar playlists directamente de Spotify te tengo que dar una mala noticia, no existe una manera 100% confiable de automatizar este proceso. Por desgracia, la única manera de 'descargar' desde Spotify es extraer los metadatos de cada una de las canciones de la playlist, y después hacer búsquedas filtradas en YouTube de manera individual.

¿Cuál es el problema entonces? Que 1 de cada 10 canciones (dependiendo cómo de mainstream seas; cuanto más nicho, peor), no se va a corresponder realmente a la canción que querías descargar. Llegué a intentar implementarlo en este repositorio, pero me dio malos resultados así que lo acabé quitando.

Para evitar pasar cientos o miles de canciones a mano, la mejor alternativa es usar herramientas web gratuitas como **TuneMyMusic** o **Soundiiz** para exportar automáticamente tu playlist de Spotify a YouTube rápidamente. Una vez generada la playlist en YouTube, solo tienes que pasarle el enlace a `apolo` para descargarla completa.

---

## Ya tengo la música, ¿ahora qué?

### ¿Dónde escucharla?

- **Desktop (Linux, MacOS y Windows)**: después de probar muchos reproductores de código abierto para escritorio, no puedo recomendar otro que no sea [Tauon](https://github.com/Taiko2k/Tauon). Es bonito, rápido, eficiente y está disponible en todas las plataformas. Si por lo que sea no te gusta, puedes probar otros como [rmpc](https://rmpc.mierak.dev/) (que necesita el daemon [mpd](https://github.com/MusicPlayerDaemon/MPD)), que es una TUI, o [Harmonoid](https://harmonoid.com/), que es estilo Material 3.
- **Móvil (Android)**: he probado casi más aplicaciones de música para móvil que de PC, y la que más me ha gustado es [PixelPlayer](https://github.com/PixelPlayerHQ/PixelPlayer), que es una aplicación estilo Material 3 descargada como APK. También hay buenas aplicaciones en la PlayStore, como la de Harmonoid.

*Lo siento, pero no uso iPhone, así que posiblemente te tengas que buscar la vida si usas uno.*

### ¿Cómo transferirla entre dispositivos?

- **Físico**: el método más rudimentario. Te puede servir si estuvieses en 2010, pero te pido que inviertas un poco de tiempo para hacerte la vida más fácil en el futuro, más aún con lo fácil que es montar todo con la ayuda de la IA.
- **Google Drive**: utilizar la nube de Google como puente y copia de seguridad simultánea. Subes tu biblioteca desde el PC y la descargas en el móvil o en otros PC. Para gestionar esto, recomiendo para Linux **`rclone`**, para Windows **`Google Drive Desktop`** y para Android **`DriveSync`**.
- **Auto streaming con Jellyfin**: si tu biblioteca ocupa demasiado espacio para llevarla en el móvil, puedes montar tu propia plataforma de streaming de código abierto. Instalando el servidor Jellyfin en tu ordenador, un NAS o una Raspberry Pi, el programa indexará toda tu música local y te permitirá reproducirla en remoto a través de internet. Las aplicaciones que he recomendado anteriormente tienen por defecto integración con Jellyfin (menos rmpc con mpd, que necesita plugins).

---

Escrito por nicgil23, porque la música es mi expresión de arte favorita, y me gusta tener control sobre ella.

### Bibliografía
- [Guía de deckard](https://www.youtube.com/watch?v=WafxmKRIoQc)
- Experimentación con muchas alternativas a lo largo del tiempo.
