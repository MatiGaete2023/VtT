#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Pipeline VtT con Auto adaptativo, reducción por regiones y métricas por etapa."""
from __future__ import annotations

import time
import traceback
from pathlib import Path
from typing import Any, Dict, List, Mapping

import transcriptor_whisper as base
import vtt_core as core
import vtt_diarization_process as dproc
import vtt_reporting as reporting
import vtt_tuning as tuning


class PipelineV3Mixin:
    """Sobrescribe solo el pipeline; la UI sigue en ``vtt_app.VtTApp``."""

    def _actualizar_resumen_config(self):
        if not hasattr(self, "lbl_config_main"):
            return
        if self.v_diarizar.get():
            modo = self.v_num_speakers.get()
            hablantes = "Sí (Auto adaptativo)" if modo == "Auto" else f"Sí ({modo})"
        else:
            hablantes = "No"
        gpu = "automática" if self.v_gpu_auto.get() else "CPU"
        self.lbl_config_main.configure(
            text=(
                f"Configuración actual: {self.cmb_m.get()} · "
                f"{self.v_perfil.get()} · Hablantes: {hablantes} · "
                f"Word: {'Sí' if self.v_docx.get() else 'No'} · GPU: {gpu}"
            )
        )

    def _diarizar_pipeline(self, archivo: str, segs, dur: float, opts, log):
        modo = str(opts.get("num_speakers", "Auto"))
        ns = -1 if modo == "Auto" else int(modo)
        regiones, reduccion_pre = tuning.regiones_voz_desde_segmentos(segs, dur)
        if reduccion_pre.get("enabled"):
            log(
                "Regiones de voz candidatas: "
                f"{float(reduccion_pre.get('coverage', 0.0))*100:.0f}% del audio; "
                f"ahorro potencial ~{base.ts_simple(reduccion_pre.get('saved_seconds', 0.0))}."
            )
        else:
            log(
                "Regiones de voz: se conserva audio completo "
                f"({reduccion_pre.get('reason', 'sin ahorro seguro')})."
            )

        inicio = time.monotonic()
        nombre = Path(archivo).name
        self._cola_diar_ui.put((0.0, None, nombre))

        def avance(pct: float):
            self._emitir_progreso_diarizacion(pct, inicio, nombre)

        try:
            turnos, meta = dproc.diarizar_responsivo(
                archivo,
                base.CARPETA_DATOS / "modelos_hablantes",
                num_speakers=ns,
                threshold=0.5,
                log=log,
                progreso=avance,
                cancelado=self.cancelar.is_set,
                speech_regions=regiones if reduccion_pre.get("enabled") else None,
                adaptive=(ns < 0),
                return_meta=True,
            )
        except dproc.DiarizacionCancelada:
            raise base.Cancelado()

        asignados, _ = core.asignar_hablantes(segs, turnos)
        asignados, speakers = tuning.renumerar_hablantes_en_uso(asignados)
        meta = dict(meta or {})
        meta["wall_seconds"] = time.monotonic() - inicio
        meta["detected_speakers"] = len(speakers)
        return asignados, speakers, meta

    def _metricas_base(self, dur: float, perfil: Mapping[str, Any], perfil_nombre: str,
                       device: str, compute: str, opts, model_load_seconds: float,
                       asr_seconds: float, diar_seconds: float, speakers,
                       diar_meta: Mapping[str, Any], overhead_seconds: float = 0.0):
        modo = str(opts.get("num_speakers", "Auto")) if opts.get("diarizar") else "No"
        solicitado = None if modo in ("No", "Auto") else int(modo)
        m = {
            "audio_seconds": max(0.0, float(dur or 0.0)),
            "model_load_seconds": max(0.0, float(model_load_seconds or 0.0)),
            "asr_seconds": max(0.0, float(asr_seconds or 0.0)),
            "diarization_seconds": max(0.0, float(diar_seconds or 0.0)),
            "export_seconds": 0.0,
            "overhead_seconds": max(0.0, float(overhead_seconds or 0.0)),
            "device": device,
            "compute_type": compute,
            "batched": bool(perfil.get("batched")),
            "batch_size": int(perfil.get("batch_size", 1)),
            "beam_size": int(perfil.get("beam_size", 5)),
            "profile": perfil_nombre,
            "diarization_enabled": bool(opts.get("diarizar")),
            "speaker_mode": modo,
            "speaker_requested": solicitado,
            "speaker_detected": len(speakers or []),
            "auto_threshold": diar_meta.get("selected_threshold"),
            "auto_pilot": diar_meta.get("pilot"),
            "speech_region_reduction": diar_meta.get("speech_region_reduction"),
            "diarization_threads": diar_meta.get("num_threads"),
            "auto_retry": diar_meta.get("retry"),
            "auto_initial_speakers": diar_meta.get("initial_speakers"),
        }
        return reporting.cerrar_metricas(m)

    def _escribir_vtt_detallado(self, out, archivo, modelo, idioma, texto, segs,
                                 bloques, speakers, metricas, formatos, perfil, glosario):
        out.mkdir(parents=True, exist_ok=True)
        tronco = self._tronco_salida_disponible(out, archivo, formatos)
        escritos: List[str] = []
        paths: Dict[str, str] = {}

        def p(ext):
            return tronco.with_name(tronco.name + "." + ext)

        if formatos.get("txt"):
            x = p("txt"); x.write_text(core.texto_bloques(bloques), encoding="utf-8")
            escritos.append(x.name); paths["txt"] = str(x)
        if formatos.get("md"):
            x = p("md"); x.write_text(
                core.markdown_bloques(archivo, modelo, idioma, bloques, metricas), encoding="utf-8"
            )
            escritos.append(x.name); paths["md"] = str(x)
        if formatos.get("srt"):
            x = p("srt"); x.write_text(core.srt_segmentos(segs), encoding="utf-8")
            escritos.append(x.name); paths["srt"] = str(x)
        if formatos.get("vtt"):
            x = p("vtt"); x.write_text(core.vtt_segmentos(segs), encoding="utf-8")
            escritos.append(x.name); paths["vtt"] = str(x)
        if formatos.get("json"):
            x = p("json")
            doc = reporting.documento_json_detallado(
                archivo, modelo, idioma, texto, segs, bloques, speakers, metricas, perfil, glosario
            )
            x.write_text(core.json_texto(doc), encoding="utf-8")
            escritos.append(x.name); paths["json"] = str(x)
        if formatos.get("docx"):
            x = p("docx")
            reporting.escribir_docx_detallado(
                x, archivo, modelo, idioma, bloques, metricas, perfil
            )
            escritos.append(x.name); paths["docx"] = str(x)
        return escritos, paths

    def _reescribir_reportes(self, paths, archivo, modelo, idioma, texto, segs,
                              bloques, speakers, metricas, perfil, glosario):
        if paths.get("json"):
            doc = reporting.documento_json_detallado(
                archivo, modelo, idioma, texto, segs, bloques, speakers, metricas, perfil, glosario
            )
            Path(paths["json"]).write_text(core.json_texto(doc), encoding="utf-8")
        if paths.get("docx"):
            reporting.escribir_docx_detallado(
                Path(paths["docx"]), archivo, modelo, idioma, bloques, metricas, perfil
            )

    def _worker_vtt(self, archivos, modelo, idioma, salida, formatos, vad, words, opts):
        try:
            from faster_whisper import BatchedInferencePipeline, WhisperModel

            perfil_nombre = opts.get("perfil") if opts.get("perfil") in core.PERFILES else "Equilibrado"
            perfil = core.PERFILES[perfil_nombre]
            device, compute = self._backend()
            backend_key = (modelo, device, compute)
            model_load_seconds = 0.0
            if self.modelo is None or self._modelo_backend != backend_key:
                carga_ini = time.perf_counter()
                try:
                    self.cola.put(("log", f"Cargando '{modelo}' en {device}/{compute}…"))
                    self.modelo = WhisperModel(modelo, device=device, compute_type=compute)
                except Exception:
                    if device != "cuda":
                        raise
                    self.cola.put(("log", "GPU no utilizable; se vuelve a CPU int8."))
                    device, compute = "cpu", "int8"
                    backend_key = (modelo, device, compute)
                    self.modelo = WhisperModel(modelo, device=device, compute_type=compute)
                model_load_seconds = time.perf_counter() - carga_ini
                self.modelo_nombre = modelo
                self._modelo_backend = backend_key

            motor = BatchedInferencePipeline(model=self.modelo) if perfil["batched"] else self.modelo
            correctos = fallidos = 0

            for i, archivo in enumerate(archivos, 1):
                if self.cancelar.is_set():
                    raise base.Cancelado()
                nombre = Path(archivo).name
                t_archivo = time.perf_counter()
                seg_objs = []
                partes = []
                self.cola.put(("status", f"Transcribiendo {i}/{len(archivos)}: {nombre}"))
                self.cola.put(("progress", 0))

                try:
                    kwargs = dict(
                        language=idioma,
                        vad_filter=vad,
                        word_timestamps=words,
                        beam_size=int(perfil["beam_size"]),
                        hotwords=core.glosario_a_hotwords(opts.get("glosario", "")),
                    )
                    t_asr = time.perf_counter()
                    if perfil["batched"]:
                        segments, info = motor.transcribe(
                            archivo, batch_size=int(perfil["batch_size"]), **kwargs
                        )
                    else:
                        segments, info = motor.transcribe(archivo, **kwargs)
                    dur = float(info.duration or 0)
                    self.dur_actual = dur
                    self.t_transcripcion_inicio = time.time()
                    for s in segments:
                        if self.cancelar.is_set():
                            raise base.Cancelado()
                        seg_objs.append(s); partes.append(s.text)
                        if dur:
                            self.cola.put(("progress", min(100.0, s.end / dur * 100)))
                        self.cola.put(("segmento", (s.start, s.end, s.text)))
                    asr_seconds = time.perf_counter() - t_asr
                    self.cola.put((
                        "log", f"Transcripción ASR completada: ~{base.ts_simple(asr_seconds)}."
                    ))

                    texto = core.limpiar_texto(" ".join(partes))
                    segs = core.segmentos_a_dicts(seg_objs)
                    speakers: List[Dict[str, Any]] = []
                    diar_meta: Dict[str, Any] = {
                        "speech_region_reduction": {
                            "enabled": False, "reason": "diarizacion_desactivada"
                        }
                    }
                    diar_seconds = 0.0

                    if opts.get("diarizar") and segs:
                        self.cola.put(("status", f"Identificando hablantes: {nombre}"))
                        t_diar = time.perf_counter()
                        segs, speakers, diar_meta = self._diarizar_pipeline(
                            archivo, segs, dur, opts,
                            lambda x: self.cola.put(("log", str(x))),
                        )
                        diar_seconds = time.perf_counter() - t_diar
                        self.cola.put((
                            "log",
                            "Identificación de hablantes completada: "
                            f"~{base.ts_simple(diar_seconds)} · {len(speakers)} detectado(s)."
                        ))

                    bloques = core.agrupar_segmentos(
                        segs,
                        max_segundos=float(opts["max_bloque"]),
                        pausa_corte=float(opts["pausa_bloque"]),
                    )
                    pre_export = time.perf_counter()
                    overhead = max(
                        0.0,
                        pre_export - t_archivo - asr_seconds - diar_seconds,
                    )
                    metricas = self._metricas_base(
                        dur, perfil, perfil_nombre, device, compute, opts,
                        model_load_seconds if i == 1 else 0.0,
                        asr_seconds, diar_seconds, speakers, diar_meta, overhead,
                    )

                    out = Path(salida) if salida else (
                        base.CARPETA_TRANSCRIPCIONES if self._es_temporal(archivo)
                        else Path(archivo).parent
                    )
                    t_export = time.perf_counter()
                    escritos, paths = self._escribir_vtt_detallado(
                        out, archivo, modelo, idioma, texto, segs, bloques,
                        speakers, metricas, formatos, perfil_nombre,
                        opts.get("glosario", ""),
                    )
                    metricas["export_seconds"] = time.perf_counter() - t_export
                    metricas = reporting.cerrar_metricas(metricas)

                    t_reporte = time.perf_counter()
                    self._reescribir_reportes(
                        paths, archivo, modelo, idioma, texto, segs, bloques,
                        speakers, metricas, perfil_nombre, opts.get("glosario", ""),
                    )
                    metricas["export_seconds"] += time.perf_counter() - t_reporte
                    metricas = reporting.cerrar_metricas(metricas)
                    self._reescribir_reportes(
                        paths, archivo, modelo, idioma, texto, segs, bloques,
                        speakers, metricas, perfil_nombre, opts.get("glosario", ""),
                    )

                    self.ultima_salida = str(out)
                    self.cola.put(("salida_nueva", str(out)))
                    self.cola.put(("progress", 100))
                    velocidad = metricas.get("speed_x") or 0
                    self.cola.put((
                        "log",
                        f"OK {nombre}: {len(segs)} segmentos → {len(bloques)} bloques · "
                        f"ASR {base.ts_simple(asr_seconds)} · "
                        f"diarización {base.ts_simple(diar_seconds)} · "
                        f"exportación {base.ts_simple(metricas.get('export_seconds', 0.0))} · "
                        f"{velocidad:.2f}× tiempo real",
                    ))
                    for e in escritos:
                        self.cola.put(("log", f"  -> {e}"))
                    self.ultima_revision = {
                        "source": archivo,
                        "model": modelo,
                        "language": idioma or "auto",
                        "text": texto,
                        "segments": segs,
                        "blocks": bloques,
                        "speakers": speakers,
                        "metrics": metricas,
                        "profile": perfil_nombre,
                        "hotwords": opts.get("glosario", ""),
                        "paths": paths,
                    }
                    correctos += 1

                except base.Cancelado:
                    if seg_objs:
                        try:
                            segs = core.segmentos_a_dicts(seg_objs)
                            texto = core.limpiar_texto(" ".join(partes))
                            bloques = core.agrupar_segmentos(
                                segs,
                                max_segundos=float(opts["max_bloque"]),
                                pausa_corte=float(opts["pausa_bloque"]),
                            )
                            metricas = reporting.cerrar_metricas({
                                "audio_seconds": self.dur_actual,
                                "asr_seconds": max(0.0, time.perf_counter() - t_archivo),
                                "diarization_seconds": 0.0,
                                "export_seconds": 0.0,
                                "overhead_seconds": 0.0,
                                "device": device,
                                "compute_type": compute,
                                "partial": True,
                            })
                            out = Path(salida) if salida else (
                                base.CARPETA_TRANSCRIPCIONES if self._es_temporal(archivo)
                                else Path(archivo).parent
                            )
                            parcial = str(Path(archivo).with_name(
                                Path(archivo).stem + "_PARCIAL" + Path(archivo).suffix
                            ))
                            escritos, _ = self._escribir_vtt_detallado(
                                out, parcial, modelo, idioma, texto, segs, bloques,
                                [], metricas, formatos, perfil_nombre,
                                opts.get("glosario", ""),
                            )
                            self.cola.put(("log", f"PARCIAL {nombre}: " + ", ".join(escritos)))
                        except Exception:
                            self.cola.put((
                                "log", "No se pudo guardar el parcial:\n" + traceback.format_exc()
                            ))
                    raise
                except Exception:
                    self.cola.put(("log", f"ERROR {nombre}:\n{traceback.format_exc()}"))
                    self.cola.put(("archivo_fallido", nombre))
                    fallidos += 1

            if correctos == 0 and fallidos:
                self.cola.put(("lote_error", "No se pudo transcribir ningún archivo."))
            elif fallidos:
                self.cola.put(("lote_parcial", (correctos, fallidos)))
            else:
                self.cola.put(("log", f"=== Completado: {correctos} archivo(s) ==="))

        except base.Cancelado:
            self.cola.put(("cancelado", None))
        except ModuleNotFoundError as e:
            self.cola.put(("dep_error", (e.name or "faster_whisper", "la transcripción")))
        except Exception:
            self.cola.put(("error", traceback.format_exc()))
        finally:
            self.cola.put(("done", None))
