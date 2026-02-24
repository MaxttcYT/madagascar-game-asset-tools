from .bsp_ot import IMPORT_OT_bsp

def import_bsp_func(self, context):
    self.layout.operator(IMPORT_OT_bsp.bl_idname, text="BSP (.bsp)")
