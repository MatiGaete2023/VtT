#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Pipeline V5: alineación por palabra + worker persistente + instrumentación sherpa."""
from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Mapping

import transcriptor_whisper as base
import vtt_alignment as alignment
import vtt_core as core
import vtt_diarization_service as dservice
import vtt_pipeline_v4 as v4
import vtt_reporting_v5 as reporting5
import vtt_tuning as tuning
import vtt_validation as validation


class PipelineV5Mixin(v4.PipelineV4Mixin):
    def _worker_vtt(self, archivos, modelo, idioma, salida, formatos, vad, words, opts):
        self._v5_user_words_run = bool(words)
        effective_words = bool(words or opts.get("diarizar"))
        self._v5_forced_words_run = bool(opts.get("diarizar") and not words)
        if self._v5_forced_words_run:
            self.cola.put((
                "log",
                "Diarización: timestamps por palabra activados internamente para alinear voces."
            ))
        return super()._worker_vtt(
            archivos, modelo, idioma, salida, formatos, vad, effective_words, opts
        )

    def _diar_service(self):
        svc = getattr(self, "_v5_diar_service", None)
        if svc is None:
            svc = dservice.PersistentDiarizationService(
                base.CARPETA_DATOS / "modelos_hablantes"
            )
            self._v5_diar_service = svc
        return svc

    def _diarizar_pipeline(self, archivo: str, segs, dur: float, opts, log):
        modo = str(opts.get("num_speakers", "Auto"))
        ns = -1 if modo == "Auto" else int(modo)
        perfil_diar = str(
            getattr(self, "_diar_profile_run", "Equilibrada") or "Equilibrada"
        )

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
            turnos, meta = self._diar_service().diarize(
                archivo,
                num_speakers=ns,
                threshold=0.5,
                log=log,
                progreso=avance,
                cancelado=self.cancelar.is_set,
                speech_regions=regiones if reduccion_pre.get("enabled") else None,
                adaptive=(ns < 0),
                diar_profile=perfil_diar,
            )
        except dservice.DiarizacionCancelada:
            raise base.Cancelado()

        asignados, align_meta = alignment.alinear_y_dividir(segs, turnos)
        asignados, speakers = tuning.renumerar_hablantes_en_uso(asignados)

        if not bool(getattr(self, "_v5_user_words_run", False)):
            for s in asignados:
                s["words"] = []

        meta = dict(meta or {})
        meta["wall_seconds"] = time.monotonic() - inicio
        meta["detected_speakers"] = len(speakers)
        meta["alignment"] = align_meta
        meta["word_timestamps_forced_for_diarization"] = bool(
            getattr(self, "_v5_forced_words_run", False)
        )
        meta["speaker_count_validation"] = validation.evaluar_conteo_hablantes(
            meta,
            len(speakers),
            manual_requested=(None if ns < 0 else ns),
        )

        log(
            "Alineación palabra↔hablante: "
            f"{align_meta.get('input_segments', 0)} segmento(s) ASR → "
            f"{align_meta.get('output_segments', 0)} segmento(s); "
            f"{align_meta.get('speaker_switches_inside_segments', 0)} cambio(s) "
            "de voz detectado(s) dentro de segmentos."
        )
        internal = meta.get("sherpa_internal") or {}
        if meta.get("sherpa_internal_timing_available"):
            log(
                "Sherpa interno: "
                f"segmentación {float(internal.get('segmentation_seconds', 0.0)):.2f}s · "
                f"embeddings {float(internal.get('embedding_seconds', 0.0)):.2f}s · "
                f"clustering {float(internal.get('clustering_seconds', 0.0)):.2f}s · "
                f"total {float(internal.get('sherpa_total_seconds', 0.0)):.2f}s."
            )
        else:
            log(
                "Sherpa: timers internos nativos no capturables en este entorno; "
                "se conserva tiempo wall de process()."
            )
        return asignados, speakers, meta

    def _metricas_base(
        self,
        dur: float,
        perfil: Mapping[str, Any],
        perfil_nombre: str,
        device: str,
        compute: str,
        opts,
        model_load_seconds: float,
        asr_seconds: float,
        diar_seconds: float,
        speakers,
        diar_meta: Mapping[str, Any],
        overhead_seconds: float = 0.0,
    ):
        m = super()._metricas_base(
            dur, perfil, perfil_nombre, device, compute, opts,
            model_load_seconds, asr_seconds, diar_seconds, speakers,
            diar_meta, overhead_seconds,
        )
        m.update({
            "word_timestamps_forced_for_diarization": bool(
                diar_meta.get("word_timestamps_forced_for_diarization", False)
            ),
            "speaker_alignment": diar_meta.get("alignment") or {},
            "speaker_count_validation": diar_meta.get("speaker_count_validation") or {},
            "diarization_worker_job_index": diar_meta.get("worker_job_index"),
            "diarization_models_reused": diar_meta.get("models_reused"),
            "diarization_engine_reused": diar_meta.get("engine_reused"),
            "diarization_model_prepare_seconds": diar_meta.get("model_prepare_seconds", 0.0),
            "diarization_engine_init_seconds": diar_meta.get("engine_init_seconds", 0.0),
            "diarization_clustering_config_seconds": diar_meta.get("clustering_config_seconds", 0.0),
            "diarization_decode_seconds": diar_meta.get("decode_seconds", 0.0),
            "diarization_reduction_seconds": diar_meta.get("reduction_seconds", 0.0),
            "diarization_process_wall_seconds": diar_meta.get("sherpa_process_wall_seconds", 0.0),
            "sherpa_internal_timing_available": diar_meta.get("sherpa_internal_timing_available", False),
            "sherpa_internal": diar_meta.get("sherpa_internal") or {},
            "sherpa_pass_timings": diar_meta.get("sherpa_pass_timings") or [],
        })
        return m

    def _reescribir_reportes(
        self,
        paths,
        archivo,
        modelo,
        idioma,
        texto,
        segs,
        bloques,
        speakers,
        metricas,
        perfil,
        glosario,
    ):
        if paths.get("json"):
            doc = reporting5.documento_json_detallado(
                archivo, modelo, idioma, texto, segs, bloques,
                speakers, metricas, perfil, glosario,
            )
            Path(paths["json"]).write_text(core.json_texto(doc), encoding="utf-8")
        if paths.get("docx"):
            reporting5.escribir_docx_detallado(
                Path(paths["docx"]), archivo, modelo, idioma,
                bloques, metricas, perfil,
            )
