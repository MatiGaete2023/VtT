#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Pipeline V5.2: rendimiento, conteos explícitos y Auto identity-aware."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Mapping, Sequence

import transcriptor_whisper as base
import vtt_core as core
import vtt_diarization_service_v52 as dservice52
import vtt_performance as perf
import vtt_pipeline_v51 as v51
import vtt_reporting as reporting_base
import vtt_reporting_v52 as reporting52
import vtt_validation_v52 as validation52


def speaker_count_snapshot(
    meta: Mapping[str, Any], speakers: Sequence[Mapping[str, Any]]
) -> Dict[str, Any]:
    """Separa explícitamente conteos acústicos, identidad y texto.

    El conjunto de identidades auditadas es autoritativo cuando existe. Esto
    evita volver a confundir el número de etiquetas que recibieron palabras
    con el número de identidades acústicas que sobrevivieron al refinamiento.
    """
    consistency = dict(meta.get("identity_consistency") or {})
    raw = int(
        meta.get("raw_sherpa_selected_speakers")
        or meta.get("detected_speakers_before_identity")
        or meta.get("detected_speakers_engine")
        or meta.get("detected_speakers")
        or 0
    )
    engine_identity_n = int(
        meta.get("detected_speakers_engine")
        or meta.get("detected_speakers")
        or raw
        or 0
    )
    assigned_raw = {
        int(s.get("raw_numeric_id")) for s in (speakers or [])
        if s.get("raw_numeric_id") is not None
    }
    all_identity_raw = {
        int(s.get("speaker")) for s in (consistency.get("speakers") or [])
        if s.get("speaker") is not None
    }
    identity_n = len(all_identity_raw) if all_identity_raw else engine_identity_n
    text_n = len(speakers or [])
    unassigned = sorted(all_identity_raw - assigned_raw)
    assigned_without_identity = sorted(assigned_raw - all_identity_raw) if all_identity_raw else []
    return {
        "raw_acoustic_clusters": raw,
        "engine_identity_clusters": engine_identity_n,
        "identity_consistency_clusters": len(all_identity_raw),
        "identity_clusters_after_refinement": identity_n,
        "text_assigned_speakers": text_n,
        "unassigned_acoustic_clusters": len(unassigned),
        "unassigned_raw_ids": unassigned,
        "text_ids_missing_from_identity_audit": assigned_without_identity,
        "identity_count_mismatch": bool(
            all_identity_raw and engine_identity_n != len(all_identity_raw)
        ),
    }


class PipelineV52Mixin(v51.PipelineV51Mixin):
    def _diar_service(self):
        svc = getattr(self, "_v52_diar_service", None)
        if svc is None:
            svc = dservice52.PersistentDiarizationService(
                base.CARPETA_DATOS / "modelos_hablantes"
            )
            self._v52_diar_service = svc
        return svc

    def _prepare_diarization_opts(self, dur: float, asr_seconds: float, opts):
        out = dict(opts)
        mode = str(getattr(self, "_global_profile_run", "Personalizado") or "Personalizado")
        if bool(out.get("diarizar")) and str(out.get("num_speakers", "Auto")) == "Auto":
            budget = perf.diarization_budget_seconds(
                audio_seconds=dur,
                asr_seconds=asr_seconds,
                profile_name=mode,
            )
            if budget is not None:
                out["_diar_time_budget_seconds"] = float(budget)
                self.cola.put((
                    "log",
                    f"Presupuesto Auto ({mode}): hasta {base.ts_simple(budget)} para diarización "
                    "antes de decidir si conviene repetir sherpa.",
                ))
        return out

    def _diarizar_pipeline(self, archivo: str, segs, dur: float, opts, log):
        asignados, speakers, meta = super()._diarizar_pipeline(
            archivo, segs, dur, opts, log
        )
        meta = dict(meta or {})
        counts = speaker_count_snapshot(meta, speakers)
        meta["speaker_counts"] = counts

        raw = int(counts["raw_acoustic_clusters"])
        identity_n = int(counts["identity_clusters_after_refinement"])
        text_n = int(counts["text_assigned_speakers"])
        unassigned = list(counts["unassigned_raw_ids"])

        modo = str(opts.get("num_speakers", "Auto"))
        requested = None if modo == "Auto" else int(modo)
        meta["speaker_count_validation"] = validation52.evaluar(
            meta, acoustic_clusters=raw, identity_clusters=identity_n,
            text_speakers=text_n, unassigned_raw_ids=unassigned,
            manual_requested=requested,
        )
        if meta.get("retry_skipped_budget"):
            meta["speaker_count_validation"]["ambiguous"] = True
            meta["speaker_count_validation"]["budget_limited"] = True
            meta["speaker_count_validation"]["status"] = "estimacion_ambigua_presupuesto"

        if raw != identity_n or identity_n != text_n or unassigned:
            log(
                "Conteo V5.2: "
                f"sherpa {raw} · identidad {identity_n} · con texto {text_n} · "
                f"sin texto {unassigned or 'ninguno'}."
            )
        if counts["identity_count_mismatch"]:
            log(
                "Diagnóstico: el conteo resumido del motor difiere del conjunto de "
                "identidades auditadas; se usa el conjunto explícito para el reporte."
            )
        if meta["speaker_count_validation"].get("ambiguous"):
            log("Auto V5.2: resultado ambiguo; se conserva trazabilidad completa en JSON/Word.")
        return asignados, speakers, meta

    def _metricas_base(
        self, dur: float, perfil: Mapping[str, Any], perfil_nombre: str,
        device: str, compute: str, opts, model_load_seconds: float,
        asr_seconds: float, diar_seconds: float, speakers,
        diar_meta: Mapping[str, Any], overhead_seconds: float = 0.0,
    ):
        m = super()._metricas_base(
            dur, perfil, perfil_nombre, device, compute, opts,
            model_load_seconds, asr_seconds, diar_seconds, speakers,
            diar_meta, overhead_seconds,
        )
        counts = dict(diar_meta.get("speaker_counts") or {})
        if counts:
            m["speaker_detected"] = int(
                counts.get("identity_clusters_after_refinement", m.get("speaker_detected", 0)) or 0
            )
            m["speaker_text_assigned"] = int(
                counts.get("text_assigned_speakers", len(speakers or [])) or 0
            )
        m.update({
            "speaker_counts": counts,
            "speaker_count_validation": diar_meta.get("speaker_count_validation") or {},
            "auto_precheck": diar_meta.get("auto_precheck") or {},
            "auto_retry_requested": bool(diar_meta.get("retry_requested", False)),
            "auto_retry_avoided": bool(diar_meta.get("retry_avoided", False)),
            "auto_retry_skipped_budget": bool(diar_meta.get("retry_skipped_budget", False)),
            "diarization_time_budget_seconds": diar_meta.get("time_budget_seconds"),
            "identity_aware_selection": diar_meta.get("identity_aware_selection") or {},
            "global_profile": getattr(self, "_global_profile_run", None),
        })
        return self._recalcular_metricas_finales(m)

    def _recalcular_metricas_finales(self, metricas: Mapping[str, Any]):
        m = reporting_base.cerrar_metricas(metricas)
        m["performance"] = perf.performance_status(m)
        return m

    def _escribir_vtt_detallado(
        self, out, archivo, modelo, idioma, texto, segs,
        bloques, speakers, metricas, formatos, perfil, glosario,
    ):
        """V5.2 difiere JSON/DOCX hasta que los tiempos funcionales sean finales."""
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
            x = p("json"); escritos.append(x.name); paths["json"] = str(x)
        if formatos.get("docx"):
            x = p("docx"); escritos.append(x.name); paths["docx"] = str(x)
        return escritos, paths

    def _reescribir_reportes(
        self, paths, archivo, modelo, idioma, texto, segs, bloques,
        speakers, metricas, perfil, glosario,
    ):
        if paths.get("json"):
            doc = reporting52.documento_json_detallado(
                archivo, modelo, idioma, texto, segs, bloques,
                speakers, metricas, perfil, glosario,
            )
            Path(paths["json"]).write_text(core.json_texto(doc), encoding="utf-8")
        if paths.get("docx"):
            reporting52.escribir_docx_detallado(
                Path(paths["docx"]), archivo, modelo, idioma,
                bloques, metricas, perfil,
            )

    def _reescribir_json_final(
        self, paths, archivo, modelo, idioma, texto, segs, bloques,
        speakers, metricas, perfil, glosario,
    ):
        if paths.get("json"):
            doc = reporting52.documento_json_detallado(
                archivo, modelo, idioma, texto, segs, bloques,
                speakers, metricas, perfil, glosario,
            )
            Path(paths["json"]).write_text(core.json_texto(doc), encoding="utf-8")
