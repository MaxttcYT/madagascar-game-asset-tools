bl_info = {
    "name": "Madagascar RW BSP Importer",
    "author": "Maxttc",
    "version": (0, 1, 0),
    "blender": (3, 0, 0),
    "location": "File > Import > BSP (.bsp)",
    "description": "Imports BSP files",
    "category": "Import-Export",
}

import bpy  # noqa: E402
from bpy.utils import register_class, unregister_class  # noqa: E402
from .gui import gui # noqa: E402

_classes = [
    gui.IMPORT_OT_bsp,
]

def register():
    for cls in _classes:
        register_class(cls)
        
    bpy.types.TOPBAR_MT_file_import.append(gui.import_bsp_func)


def unregister():
    bpy.types.TOPBAR_MT_file_import.remove(gui.import_bsp_func)
    
    for cls in _classes:
        unregister_class(cls)