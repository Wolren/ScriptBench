def classFactory(iface):
    from .plugin import ScriptBenchPlugin
    return ScriptBenchPlugin(iface)
