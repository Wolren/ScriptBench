"""
ScriptBench — benchmark and compare PyQGIS scripts.

classFactory(iface)  -->  ScriptBenchPlugin instance
"""


def classFactory(iface):
    try:
        from .plugin import ScriptBenchPlugin

        return ScriptBenchPlugin(iface)
    except Exception:
        import traceback
        from qgis.core import QgsMessageLog

        QgsMessageLog.logMessage(
            f"Failed to load ScriptBench:\n{traceback.format_exc()}",
            "ScriptBench",
            level=2,
        )
        raise
