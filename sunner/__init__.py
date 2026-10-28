# SPDX-License-Identifier: GPL-3.0-or-later
"""Sunner: rotate one dial through daylight, twilight, and moonlight."""

import bpy

from . import operators, ui, weather_ui

CLASSES = operators.CLASSES + ui.CLASSES + weather_ui.CLASSES


def register():
    for cls in CLASSES:
        bpy.utils.register_class(cls)


def unregister():
    # Generated native data belongs to the scene and survives disabling the UI.
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)
