"""
兼容层：旧代码 `from true_pixel_core import process_image` 仍然可用。
新代码请直接 `from truepixel import process_image`。
"""
from truepixel.ops import add_outline, remove_specks
from truepixel.pipeline import composite_layers, process_image, process_vfx_image

# 旧函数名
add_solid_pixel_outline = add_outline
remove_isolated_noise_pixels = remove_specks

__all__ = [
    "process_image", "process_vfx_image", "composite_layers",
    "add_solid_pixel_outline", "remove_isolated_noise_pixels",
]
