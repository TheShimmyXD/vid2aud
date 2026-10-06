# vid2aud

Aplicación de escritorio que saca el audio de un video y lo deja mucho más liviano sin que se
note la diferencia. Sirve para guardar clases, reuniones, charlas o música de un video ocupando
una fracción del espacio.

Ejemplo real: un video de 1:31 (19,9 MB) queda en un audio Opus de 1,06 MB, un 94,7 % menos.

- Suelta un video en la ventana (o búscalo) y elige formato y calidad.
- Muestra el peso estimado antes de convertir, el avance mientras convierte y el ahorro al final.
- Se puede cancelar en cualquier momento; el video original nunca se toca.
- Tema claro y oscuro (o el del sistema).
- Funciona en Linux y Windows. ffmpeg viene incluido: no hay que instalarlo aparte.

## Requisitos

- **Python 3.12 o superior.**
  - Windows: descárgalo de [python.org](https://www.python.org/downloads/) y marca
    *Add python.exe to PATH* al instalarlo.
  - Linux: suele venir con el sistema. En Debian, Ubuntu o Mint hace falta además el paquete
    `python3-venv` (`sudo apt install python3-venv`).
- Linux con X11: si la ventana no abre y aparece un error del plugin `xcb`, instala
  `libxcb-cursor0` (`sudo apt install libxcb-cursor0`).

## Instalación rápida

Descarga o clona el repositorio y ejecuta el instalador desde su carpeta. Crea un entorno
virtual en `.venv`, instala las dependencias y agrega vid2aud al menú del sistema.

**Linux**

```bash
git clone https://github.com/TheShimmyXD/vid2aud.git
cd vid2aud
./install.sh
```

**Windows**

```bat
git clone https://github.com/TheShimmyXD/vid2aud.git
cd vid2aud
install.bat
```

(o doble clic sobre `install.bat` en el Explorador).

Después, abre **vid2aud** desde el menú de aplicaciones (Linux) o el menú Inicio (Windows).

> El acceso del menú apunta a la carpeta donde instalaste. Si la mueves, vuelve a ejecutar el
> instalador.

## Instalación manual

```bash
python3 -m venv .venv
# Linux
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python main.py                      # abre la aplicación
.venv/bin/python main.py --install-launcher   # (opcional) agrega el acceso al menú

# Windows
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python main.py
.venv\Scripts\python main.py --install-launcher
```

En Windows usa `py -3` en lugar de `python3` si `python3` no existe.

## Desinstalar

Borra la carpeta del proyecto y el acceso del menú:

- Linux: `~/.local/share/applications/vid2aud.desktop` y
  `~/.local/share/icons/hicolor/256x256/apps/vid2aud.png`.
- Windows: `%APPDATA%\Microsoft\Windows\Start Menu\Programs\vid2aud.lnk` y la carpeta
  `%LOCALAPPDATA%\vid2aud`.

## Cómo reduce el peso

Saca solo la primera pista de audio y la escribe en **Opus** (por defecto, .opus), **AAC**
(.m4a) o **MP3**, con tres calidades:

| Calidad | Para qué |
|---|---|
| *Voz* | Mono, pensada para clases, reuniones y podcasts. |
| *Equilibrada* | La recomendada para música y voz. |
| *Alta* | Más bitrate, para quien quiere más margen. |

Nunca usa más canales ni más bitrate que el original, y si el audio ya viene en el formato
elegido lo copia sin recodificar. El audio se escribe primero en un archivo `.part` y solo se
renombra cuando termina bien, así que una conversión cancelada no deja archivos a medias.

ffmpeg: si el sistema tiene uno instalado se usa ese; si no, el que trae el paquete
`imageio-ffmpeg`.

## Configuración

La aplicación recuerda el formato, la calidad, el tema y la última carpeta en
`resources/json/app_settings.json` (se crea al usarla y no se versiona). Los registros quedan en
`resources/logs/`.

## Desarrollo

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/ruff format .      # formatea el código
.venv/bin/ruff check .       # revisa errores y estilo
.venv/bin/pytest             # ejecuta las pruebas (usan videos sintéticos generados con ffmpeg)
```

Estructura por capas: `logic/` (reglas puras, sin Qt ni ffmpeg) → coordinador → `workers/`
(hilos) → `services/` (el único que llama a ffmpeg). La interfaz (`ui/`) solo habla con el
coordinador.

### Glosario de dominio

Términos de negocio y su nombre en el código (el código va en inglés).

| Español (negocio) | Inglés (código) |
|---|---|
| Convertir | convert |
| Leer el archivo de entrada | probe |
| Sonido del archivo de entrada | SourceAudio |
| Decisión de codificación | EncodePlan |
| Formato de salida (Opus, AAC, MP3) | AudioFormat, `FORMATS` |
| Calidad (Voz, Equilibrada, Alta) | Quality (`voice`, `balanced`, `high`) |
| Copia directa (sin recodificar) | copy |
| Contenedor de salida (`-f`) | muxer |
| Archivo a medias | part (`.part`) |
| Zona de soltar | DropZone |

## Licencia

[MIT](LICENSE). Incluye las letras IBM Plex (SIL OFL 1.1, `resources/fonts/OFL.txt`) y los
íconos Phosphor (MIT, `resources/icons/LICENSE.txt`). ffmpeg se descarga con `imageio-ffmpeg`
bajo su propia licencia (LGPL/GPL).
