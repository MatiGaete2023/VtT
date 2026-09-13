# VtT Ultra Windows

Esta rama (`windows-ultra-fast`) es una variante separada de VtT orientada específicamente a **Windows 10/11 y velocidad en CPU**.

No reemplaza la rama estable V5.2.1. Mantiene transcripción local/offline, timestamps, separación de hablantes, checkpoint ASR recuperable y exportación TXT/MD/SRT/VTT/JSON/DOCX.

## Dos modos Ultra

| Componente | Ultra Máxima | Ultra Calidad 90s |
|---|---|---|
| Whisper | `tiny` | `base` |
| Perfil ASR | `Rápido` | `Rápido` |
| Beam / Batch | `1 / 8` | `1 / 8` |
| Hablantes | `Auto` | `Auto` |
| Diarización | `Ultrarrápida` | `Ultrarrápida` |
| Shift | `0.35` | `0.35` |
| Threshold Auto | `0.82` | `0.82` |
| Pasadas Sherpa | **1** | **1** |
| Alineación | segmento ASR | **palabra ↔ turno Sherpa** |
| Word timestamps internos | no forzados | **sí** |
| Identidad acústica | omitida | **ligera, máx. 10 embeddings** |
| Escaneo largo V5.2 | no | no |
| Segunda pasada | no | no |
| Re-ASR selectivo | no | **desactivado hasta benchmark real** |

### Ultra Máxima

Es la ruta de borrador inmediato. Conserva la estrategia de la primera prueba real: `tiny`, una pasada Sherpa y hablante predominante por segmento.

### Ultra Calidad 90s

Usa deliberadamente parte del margen de velocidad para mejorar el resultado:

1. cambia `tiny` por `base`;
2. fuerza timestamps por palabra internamente;
3. divide segmentos cuando los turnos Sherpa indican cambios de voz;
4. ejecuta una verificación de identidad ligera y limitada;
5. mantiene **una sola pasada Sherpa 0.35**;
6. no activa re-ASR selectivo hasta medir cuánto presupuesto queda realmente en el PC institucional.

El objetivo para el video patrón de 6:44 es aproximadamente **90 s de procesamiento** (`0.22 × duración`). Es un objetivo de diseño, no una garantía hasta repetir la prueba en el hardware real.

## Ejecutar en Windows

Requisito: Python 3.9+ instalado para el usuario; el flujo normal no requiere privilegios de administrador.

En `desktop/`:

```bat
run.bat
```

o:

```bat
python run.py
```

La ventana debe indicar **VtT Ultra Windows**. El selector `Modo global` permite elegir `Ultrarrápido` o `Ultra Calidad 90s`; la elección Ultra se conserva entre sesiones.

## Resultado de referencia — Ultra Máxima

Video: 6:44 / 404 s, PC institucional Windows.

- carga modelo: ~8.9 s;
- ASR: ~10.3 s;
- diarización: ~41.5 s;
- procesamiento: ~51.8 s;
- extremo a extremo: ~60.8 s;
- velocidad: ~7.79× tiempo real;
- Sherpa: 6 clusters acústicos;
- salida textual: 3 hablantes, debido a la alineación por segmento.

Ese resultado motivó `Ultra Calidad 90s`: el cuello de botella visible no era detectar clusters sino **aprovechar sus cambios dentro de segmentos Whisper largos**.

## Privacidad

ASR y diarización se ejecutan localmente. La red solo se usa para instalación de dependencias/modelos, descargas explícitas y CI/build.

Consulta [`ULTRA_WINDOWS.md`](ULTRA_WINDOWS.md) para detalles técnicos, tradeoffs y protocolo de prueba.