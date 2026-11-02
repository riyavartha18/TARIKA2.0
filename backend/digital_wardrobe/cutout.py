import io
import math
from typing import Dict, Any, Tuple, Optional
from PIL import Image, ImageOps, ImageFilter, ImageDraw, ImageEnhance
import numpy as np

import os

REMBG_AVAILABLE = None


def create_studio_background(width: int = 1000, height: int = 1000) -> Image.Image:
    """
    Creates a luxury minimalist studio neutral background:
    Seamless, ultra-clean neutral off-white (#FAF9F8) with soft radial falloff.
    """
    base = Image.new("RGBA", (width, height), (250, 249, 248, 255))
    
    # Soft ambient radial glow in the center-top (studio softbox fill)
    glow = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    gdraw = ImageDraw.Draw(glow)
    cx, cy = width // 2, int(height * 0.45)
    rx, ry = int(width * 0.65), int(height * 0.55)
    gdraw.ellipse([cx - rx, cy - ry, cx + rx, cy + ry], fill=(255, 255, 255, 60))
    glow_blurred = glow.filter(ImageFilter.GaussianBlur(radius=60))
    
    base.paste(glow_blurred, (0, 0), glow_blurred)
    return base


def enhance_garment_texture_and_depth(garment_rgba: Image.Image) -> Image.Image:
    """
    Enhances natural fabric folds, micro-contrast, and fabric weave (e.g. ribbing, stitching).
    Also performs edge alpha defringing to clean any background color bleed.
    """
    if garment_rgba.mode != "RGBA":
        garment_rgba = garment_rgba.convert("RGBA")

    r, g, b, a = garment_rgba.split()
    rgb = Image.merge("RGB", (r, g, b))
    
    # 1. Subtle micro-contrast to make fabric folds pop with realistic depth
    enhancer_con = ImageEnhance.Contrast(rgb)
    rgb = enhancer_con.enhance(1.06)
    
    # 2. Subtle color vibrance
    enhancer_col = ImageEnhance.Color(rgb)
    rgb = enhancer_col.enhance(1.03)
    
    # 3. Soft sharpness to bring out weave/ribbing texture without harsh noise
    rgb = rgb.filter(ImageFilter.UnsharpMask(radius=1.1, percent=110, threshold=2))
    
    # 4. Defringe alpha border: smooth edge feathering (0.5px)
    a_feathered = a.filter(ImageFilter.GaussianBlur(radius=0.5))
    
    r_enh, g_enh, b_enh = rgb.split()
    return Image.merge("RGBA", (r_enh, g_enh, b_enh, a_feathered))


def generate_multi_layer_3d_shadow(
    canvas_size: int = 1000,
    paste_x: int = 0,
    paste_y: int = 0,
    new_w: int = 0,
    new_h: int = 0
) -> Image.Image:
    """
    Generates a realistic 3D floating shadow:
    Layer 1: Contact depth oval immediately beneath bottom hem.
    Layer 2: Soft expansive diffuse floor pool ~20px below.
    """
    shadow_canvas = Image.new("RGBA", (canvas_size, canvas_size), (0, 0, 0, 0))
    sdraw = ImageDraw.Draw(shadow_canvas)
    
    # --- Layer 2: Diffuse Floor Float Shadow (Soft, wide ambient pool) ---
    pool_w = int(new_w * 0.88)
    pool_h = max(18, int(new_h * 0.09))
    pool_cx = paste_x + (new_w // 2)
    pool_cy = min(canvas_size - pool_h - 30, paste_y + new_h + 16)
    
    pool_box = [pool_cx - (pool_w // 2), pool_cy - (pool_h // 2), pool_cx + (pool_w // 2), pool_cy + (pool_h // 2)]
    sdraw.ellipse(pool_box, fill=(40, 32, 36, 32))
    
    # --- Layer 1: Contact Depth Oval (Darker, tighter beneath garment) ---
    contact_w = int(new_w * 0.72)
    contact_h = max(10, int(new_h * 0.055))
    contact_cx = pool_cx
    contact_cy = min(canvas_size - contact_h - 20, paste_y + new_h - 4)
    
    contact_box = [contact_cx - (contact_w // 2), contact_cy - (contact_h // 2), contact_cx + (contact_w // 2), contact_cy + (contact_h // 2)]
    sdraw.ellipse(contact_box, fill=(28, 20, 24, 65))
    
    # Blur the combined shadow for natural light dispersion
    shadow_blurred = shadow_canvas.filter(ImageFilter.GaussianBlur(radius=20))
    return shadow_blurred


class CutoutProcessor:
    """
    Standardized visual pipeline for Digital Wardrobe items:
    1. EXIF auto-rotation & minimum dimension validation (reject < 400px).
    2. Background removal via rembg (u2net / isnet).
    3. Bounding box cropping and quality health checks (area >= 15%, border touching).
    4. Centering onto a square 1000x1000 canvas with golden padding and upper elevation.
    5. Fabric micro-contrast and weave texture enhancement.
    6. Luxury neutral studio canvas (#FAF9F8) with softbox radial lighting.
    7. Multi-layer floating 3D shadow (contact depth + floor float pool).
    8. Generating (a) transparent WebP, (b) floating 3D render WebP, (c) 400x400 thumbnail.
    """

    _session = None

    @classmethod
    def get_session(cls):
        global REMBG_AVAILABLE
        if os.environ.get('DISABLE_REMBG', 'false').lower() == 'true':
            return None
        if cls._session is None:
            try:
                from rembg import remove, new_session
                REMBG_AVAILABLE = True
                try:
                    cls._session = new_session("u2net")
                except Exception:
                    cls._session = new_session("isnet-general-use")
            except Exception:
                cls._session = None
                REMBG_AVAILABLE = False
        return cls._session

    @classmethod
    def process_image(cls, image_bytes: bytes) -> Dict[str, Any]:
        """
        Takes raw image bytes, validates, and processes into standardized formats.
        Returns a dictionary containing:
        - transparent_bytes: bytes (1000x1000 WebP)
        - flat_shadow_bytes: bytes (1000x1000 WebP 3D render on studio neutral background)
        - thumb_bytes: bytes (400x400 WebP)
        - original_bytes: bytes
        - needs_review: bool
        - retake_prompt: Optional[str]
        - dimensions: (1000, 1000)
        - error: Optional[str]
        """
        try:
            raw_img = Image.open(io.BytesIO(image_bytes))
        except Exception:
            return {"error": "Invalid or corrupted image file. Please provide a valid JPG, PNG, or WebP."}

        # 1. EXIF auto-rotate
        img = ImageOps.exif_transpose(raw_img)

        # 2. Dimension validation: if under 400px but >= 120px, upscale with high-quality Lanczos
        if img.width < 120 or img.height < 120:
            return {
                "error": f"Image resolution ({img.width}x{img.height}) is too small. Please upload a photo at least 120x120 pixels."
            }
        if img.width < 400 or img.height < 400:
            upscale_ratio = max(400 / img.width, 400 / img.height)
            target_w = int(round(img.width * upscale_ratio))
            target_h = int(round(img.height * upscale_ratio))
            img = img.resize((target_w, target_h), Image.Resampling.LANCZOS)

        orig_w, orig_h = img.size

        # 3. Background removal
        session = cls.get_session()
        cutout_img = None
        if REMBG_AVAILABLE and session is not None:
            try:
                from rembg import remove
                cutout_img = remove(img, session=session)
            except Exception:
                cutout_img = None

        if cutout_img is None:
            # Fallback for systems without onnx models: Convert to RGBA
            cutout_img = img.convert("RGBA")

        if cutout_img.mode != "RGBA":
            cutout_img = cutout_img.convert("RGBA")

        # 4. Extract alpha & bounding box
        alpha = cutout_img.split()[3]
        bbox = alpha.getbbox()

        needs_review = False
        retake_prompt = None

        if not bbox:
            # Nothing detected
            bbox = (0, 0, orig_w, orig_h)
            needs_review = True
            retake_prompt = "No clothing piece detected. Please lay item flat on a plain background."
            cropped = cutout_img
        else:
            left, top, right, bottom = bbox
            crop_w = right - left
            crop_h = bottom - top

            # Border touching check: does the bounding box touch 3 or more outer borders?
            touches_left = left <= 4
            touches_top = top <= 4
            touches_right = right >= (orig_w - 4)
            touches_bottom = bottom >= (orig_h - 4)
            edge_touches = sum([touches_left, touches_top, touches_right, touches_bottom])

            if edge_touches >= 3:
                needs_review = True
                retake_prompt = "Item is cut off at the edges. Please position the entire garment inside the camera frame."

            cropped = cutout_img.crop(bbox)

            # Check area of item relative to original image
            item_area = crop_w * crop_h
            canvas_area = orig_w * orig_h
            if canvas_area > 0 and (item_area / canvas_area) < 0.15:
                needs_review = True
                retake_prompt = "Item appears very small in photo. Please take a closer photo."

        # 5. Smart Garment Scaling: 1000x1000 canvas with upper elevation for 3D floating effect
        CANVAS_SIZE = 1000
        MAX_CONTENT_W = 750
        MAX_CONTENT_H = 700

        c_w, c_h = cropped.size
        scale = min(MAX_CONTENT_W / max(1, c_w), MAX_CONTENT_H / max(1, c_h))
        new_w = max(1, int(round(c_w * scale)))
        new_h = max(1, int(round(c_h * scale)))

        scaled_item = cropped.resize((new_w, new_h), Image.Resampling.LANCZOS)
        enhanced_item = enhance_garment_texture_and_depth(scaled_item)

        # Transparent 1000x1000 canvas
        paste_x = (CANVAS_SIZE - new_w) // 2
        paste_y = int((CANVAS_SIZE - new_h) * 0.42)

        transparent_canvas = Image.new("RGBA", (CANVAS_SIZE, CANVAS_SIZE), (0, 0, 0, 0))
        transparent_canvas.paste(enhanced_item, (paste_x, paste_y), enhanced_item)

        # 6. Realistic Floating 3D Studio Render
        # Studio canvas + Multi-layer 3D floating shadow + Garment
        studio_bg = create_studio_background(CANVAS_SIZE, CANVAS_SIZE)
        shadow = generate_multi_layer_3d_shadow(CANVAS_SIZE, paste_x, paste_y, new_w, new_h)

        studio_bg.paste(shadow, (0, 0), shadow)
        studio_bg.paste(enhanced_item, (paste_x, paste_y), enhanced_item)
        flat_rgb = studio_bg.convert("RGB")

        # 7. 400x400 Square Thumbnail
        thumb_img = flat_rgb.resize((400, 400), Image.Resampling.LANCZOS)

        # Export buffers in WebP format
        transparent_buf = io.BytesIO()
        transparent_canvas.save(transparent_buf, format="WEBP", quality=90, method=6)
        transparent_bytes = transparent_buf.getvalue()

        flat_buf = io.BytesIO()
        flat_rgb.save(flat_buf, format="WEBP", quality=92, method=6)
        flat_bytes = flat_buf.getvalue()

        thumb_buf = io.BytesIO()
        thumb_img.save(thumb_buf, format="WEBP", quality=88, method=6)
        thumb_bytes = thumb_buf.getvalue()

        return {
            "transparent_bytes": transparent_bytes,
            "flat_shadow_bytes": flat_bytes,
            "thumb_bytes": thumb_bytes,
            "original_bytes": image_bytes,
            "needs_review": needs_review,
            "retake_prompt": retake_prompt,
            "dimensions": (CANVAS_SIZE, CANVAS_SIZE),
            "render_status": "completed",
            "error": None,
        }
