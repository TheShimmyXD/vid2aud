# Changelog

Todos los cambios relevantes de vid2aud se registran aquí.
Formato basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/) y versiones
[SemVer](https://semver.org/lang/es/): MAYOR.MENOR.PARCHE.

## [1.0.0] - 2026-10-06

### Agregado
- Motor: lectura del video con `ffmpeg -i`, plan de codificación (Opus, AAC, MP3; voz,
  equilibrada, alta; copia directa), conversión con avance, cancelación y archivo `.part`.
- Interfaz: zona de soltar, rutas con buscador, formato y calidad, estimado de peso, avance,
  resultado con el ahorro y *Abrir carpeta*; tema «Descifrado» claro y oscuro.
- Acceso en el menú del escritorio (Linux) o en el menú Inicio (Windows) con
  `main.py --install-launcher`.
- Instaladores `install.sh` (Linux) e `install.bat` (Windows) y `requirements.txt`.
