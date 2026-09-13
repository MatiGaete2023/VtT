#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Errores compartidos por todos los servicios de diarización.

La cancelación debe conservar identidad de excepción aunque cambie la versión
concreta del servicio (V5/V5.1/V5.2), para que el pipeline traduzca siempre la
interrupción a ``transcriptor_whisper.Cancelado`` y guarde el resultado ASR
recuperable en vez de tratarla como un fallo de transcripción.
"""


class DiarizacionCancelada(Exception):
    """El usuario canceló un trabajo de diarización en curso."""

    pass
