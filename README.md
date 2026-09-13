# VtT Ultra Windows

Esta rama (`windows-ultra-fast`) es una variante separada de VtT orientada específicamente a **Windows 10/11 y máxima velocidad en CPU**.

No reemplaza la rama estable V5.2.1. Su objetivo es terminar mucho más rápido, manteniendo:

- transcripción local/offline;
- timestamps útiles por segmento;
- intento de separación de hablantes (`Persona 1`, `Persona 2`, etc.);
- checkpoint ASR recuperable;
- exportación TXT/MD/SRT/VTT/JSON/DOCX;
- métricas de tiempo y trazabilidad.

## Estrategia Ultra

Configuración por defecto:

| Componente | Ultra Windows |
|---|---|
| Whisper | `tiny` |
| Perfil ASR | `Rápido` |
| Beam | `1` |
| Batch | `8` |
| Hablantes | `Auto` |
| Diarización | `Ultrarrápida` |
| Shift | `0.35` |
| Threshold Auto | `0.82` |
| Pasadas Sherpa | **1** |
| Identidad V5.2 | **omitida** |
| Alineación | por segmento ASR |
| Word timestamps forzados | **no** |

La reducción de costo es deliberada: la rama prioriza velocidad por sobre separación fina de cambios de voz dentro de un mismo segmento.

## Ejecutar en Windows

Requisito: Python 3.9+ instalado para el usuario; no se requieren privilegios de administrador en el flujo normal.

Entra a `desktop/` y ejecuta:

```bat
run.bat
```

También puedes usar:

```bat
python run.py
```

La ventana debe indicar **VtT Ultra Windows**.

## Diferencias con V5.2.1 estable

Ultra:

- no ejecuta una segunda pasada Sherpa;
- no ejecuta refinamiento/consistencia de identidad V5.2;
- no fuerza timestamps por palabra solo por activar hablantes;
- usa una resolución de diarización menor (`shift 0.35`);
- asigna el hablante predominante a cada segmento ASR;
- marca Auto como `estimacion_ultra_una_pasada`.

La rama estable debe preferirse si la separación fina de voces importa más que la velocidad.

## Objetivo temporal

El preset Ultra usa como referencia:

`processing_seconds <= 0.60 × duración del audio`

No es una garantía. Debe validarse en el PC Windows objetivo.

## Documentación específica

Consulta [`ULTRA_WINDOWS.md`](ULTRA_WINDOWS.md) para el diseño, tradeoffs y protocolo de prueba.

La documentación histórica V5.2.1 (`AUDITORIA.md`, `PLAN_MAESTRO.md`, etc.) sigue disponible como referencia de la arquitectura heredada.

## Privacidad

ASR y diarización se ejecutan localmente. La red solo se usa para instalación de dependencias/modelos, descargas explícitas y CI/build.
