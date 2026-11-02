import io
import time
import hashlib
import numpy as np
from PIL import Image, ImageOps
from typing import List, Dict, Any, Tuple, Optional
import scipy.ndimage as ndi
import rembg

from .tagger import extract_dominant_colors_lab, generate_garment_name


class ClothingParser:
    """
    Deep neural clothing parser separating individual garments from human photos.
    Runs on the original upload (after EXIF rotation).
    Isolates upper-body, lower-body, and full-body clothes from skin, hair, and backgrounds.
    """

    _session = None

    @classmethod
    def get_session(cls):
        if cls._session is None:
            cls._session = rembg.new_session('u2net_cloth_seg')
        return cls._session

    @classmethod
    def parse_photo(cls, pil_image: Image.Image) -> Dict[str, Any]:
        """
        Takes a PIL image of an upload, applies EXIF rotation,
        and isolates individual garments from skin, hair, and backgrounds.
        Returns:
            {
                'is_person_outfit': bool,
                'garments_found': int,
                'pieces': List[Dict[str, Any]],
                'inference_time_s': float
            }
        """
        t0 = time.time()
        # 1. EXIF auto-rotation on the ORIGINAL upload
        rgb_img = ImageOps.exif_transpose(pil_image).convert('RGB')
        w, h = rgb_img.size
        total_px = w * h
        arr = np.array(rgb_img)

        # 2. Run garment parsing on original image
        session = cls.get_session()
        masks = session.predict(rgb_img)
        inference_time = round(time.time() - t0, 3)

        up_mask_raw = np.array(masks[0]) > 50
        low_mask_raw = np.array(masks[1]) > 50
        full_mask_raw = np.array(masks[2]) > 50

        up_share = float(np.sum(up_mask_raw) / total_px)
        low_share = float(np.sum(low_mask_raw) / total_px)
        full_share = float(np.sum(full_mask_raw) / total_px)

        is_multi = (up_share >= 0.02 and low_share >= 0.02)
        is_person = is_multi or (full_share >= 0.07)

        garment_configs = []
        if full_share >= 0.07 and not is_multi:
            # Person wearing one-piece dress / saree
            garment_configs.append(('one_piece', 'dress', full_mask_raw))
        elif is_multi:
            # Multi-piece outfit: Top + Bottom
            garment_configs.append(('top', 'sleeveless top' if up_share < 0.07 else 'top', up_mask_raw))
            garment_configs.append(('bottom', 'skirt' if low_share < 0.12 else 'pants', low_mask_raw))
        else:
            # Single item or flat-lay fallback
            return {
                'is_person_outfit': False,
                'garments_found': 1,
                'pieces': [],
                'inference_time_s': inference_time
            }

        # 3. Detect skin and hair across the image to strictly exclude from garment cutouts
        r_f = arr[:, :, 0].astype(float)
        g_f = arr[:, :, 1].astype(float)
        b_f = arr[:, :, 2].astype(float)

        # Kovac YCbCr skin detection
        cb = 128 - 0.168736 * r_f - 0.331264 * g_f + 0.5 * b_f
        cr = 128 + 0.5 * r_f - 0.418688 * g_f - 0.081312 * b_f
        skin_mask = (cb >= 77) & (cb <= 127) & (cr >= 133) & (cr <= 173)

        # Hair & dark shadow detection
        hsv_arr = np.array(rgb_img.convert('HSV'))
        val_channel = hsv_arr[:, :, 2]
        hair_mask = ((r_f < 55) & (g_f < 55) & (b_f < 55)) | (val_channel < 45)

        pieces = []
        for idx, (slot, default_sub, raw_mask) in enumerate(garment_configs, 1):
            raw_px_count = float(np.sum(raw_mask))

            # Strip skin, hair, and background
            clean_mask = raw_mask & (~skin_mask) & (~hair_mask)

            # Morphological closing (fill small gaps, close hair strand slits)
            struct_size = 9 if slot == 'bottom' else 7
            clean_mask = ndi.binary_closing(clean_mask, structure=np.ones((struct_size, struct_size)))

            # Keep largest connected component per garment
            labeled, num_features = ndi.label(clean_mask)
            if num_features > 0:
                sizes = ndi.sum(clean_mask, labeled, range(1, num_features + 1))
                max_label = np.argmax(sizes) + 1
                clean_mask = (labeled == max_label)
            else:
                clean_mask = raw_mask

            # Fill only small interior holes (< 2000 px) so open necklines/collars are preserved
            filled_mask = ndi.binary_fill_holes(clean_mask)
            raw_holes = filled_mask & (~clean_mask)
            lbl_holes, n_h = ndi.label(raw_holes)
            small_holes = np.zeros_like(clean_mask, dtype=bool)
            if n_h > 0:
                h_sizes = ndi.sum(raw_holes, lbl_holes, range(1, n_h + 1))
                for h_i, sz in enumerate(h_sizes, 1):
                    if sz < 2000:
                        small_holes = small_holes | (lbl_holes == h_i)
            
            final_garment_mask = clean_mask | small_holes

            # Inpaint small holes from surrounding garment fabric colour
            inpainted_arr = arr.copy()
            if np.any(small_holes):
                indices = ndi.distance_transform_edt(~clean_mask, return_distances=False, return_indices=True)
                inpainted_arr[small_holes] = arr[indices[0][small_holes], indices[1][small_holes]]

            # 4. Hidden by hair/arms or cropped by frame evaluation
            clean_px_count = float(np.sum(clean_mask))
            hidden_ratio = (raw_px_count - clean_px_count) / max(1.0, raw_px_count)

            # Frame boundary check
            h_m, w_m = clean_mask.shape
            border_px = int(
                np.sum(clean_mask[0, :]) +
                np.sum(clean_mask[h_m - 1, :]) +
                np.sum(clean_mask[:, 0]) +
                np.sum(clean_mask[:, w_m - 1])
            )
            is_cropped = bool(border_px > 30)
            is_obscured = bool(hidden_ratio > 0.15)
            needs_review = is_cropped or is_obscured
            review_note = "Part of this item is not visible. Retake a flat photo for the best result." if needs_review else None

            # 5. Create garment RGBA cutout
            garment_cutout = Image.new('RGBA', (w, h), (0, 0, 0, 0))
            garment_cutout.paste(Image.fromarray(inpainted_arr), mask=Image.fromarray((final_garment_mask * 255).astype('uint8')))

            # 6. Crop each garment to its own bounding box, center on 1000x1000 canvas with 9% padding
            bbox = garment_cutout.getbbox()
            length_attr = None
            if bbox:
                cropped = garment_cutout.crop(bbox)
                w_c, h_c = cropped.size

                # Determine length and subtype
                if slot == 'bottom':
                    is_floor_length = (h_c > 450) or (bbox[3] >= h - 15)
                    if default_sub == 'skirt' or 'skirt' in default_sub:
                        subtype = 'maxi skirt' if is_floor_length else 'midi skirt'
                        length_attr = 'maxi' if is_floor_length else 'midi'
                    else:
                        subtype = 'jeans' if is_floor_length else 'trousers'
                        length_attr = 'ankle'
                elif slot == 'one_piece':
                    if h_c > 550 or bbox[3] >= h - 15:
                        length_attr = 'maxi'
                        subtype = 'dress'
                    elif h_c > 350:
                        length_attr = 'midi'
                        subtype = 'dress'
                    else:
                        length_attr = 'mini'
                        subtype = 'dress'
                else:
                    subtype = default_sub

                # Scale with 9% padding (820px usable area inside 1000x1000)
                target_dim = 820
                scale = min(target_dim / w_c, target_dim / h_c)
                new_w = max(1, int(round(w_c * scale)))
                new_h = max(1, int(round(h_c * scale)))
                resized = cropped.resize((new_w, new_h), Image.Resampling.LANCZOS)

                square_img = Image.new('RGBA', (1000, 1000), (0, 0, 0, 0))
                offset = ((1000 - new_w) // 2, (1000 - new_h) // 2)
                square_img.paste(resized, offset, resized)
            else:
                square_img = garment_cutout
                subtype = default_sub

            # 7. Extract colors strictly from that garment's mask (>= 8% threshold)
            raw_colors, shares = extract_dominant_colors_lab(square_img)
            valid_shares = [s for s in shares if s.get('share', 0) >= 0.08]

            # Canonical palette mapping without metallic one-offs like "gold" on fabric
            mapped_colors = []
            for s in valid_shares:
                c_name = s['name']
                if c_name == 'gold':
                    if 'yellow' not in mapped_colors: mapped_colors.append('yellow')
                    if 'mustard' not in mapped_colors: mapped_colors.append('mustard')
                elif c_name == 'mustard':
                    if 'mustard' not in mapped_colors: mapped_colors.append('mustard')
                    if 'yellow' not in mapped_colors: mapped_colors.append('yellow')
                elif c_name == 'silver':
                    if 'grey' not in mapped_colors: mapped_colors.append('grey')
                elif c_name in ('navy', 'denim blue') and slot == 'bottom':
                    if 'denim blue' not in mapped_colors: mapped_colors.append('denim blue')
                    if 'navy' not in mapped_colors: mapped_colors.append('navy')
                elif c_name not in ('black', 'hair', 'skin') or slot != 'top':
                    if c_name not in mapped_colors:
                        mapped_colors.append(c_name)

            if not mapped_colors:
                mapped_colors = raw_colors[:2] if raw_colors else ['neutral']

            tags = {
                'dominant_colours': mapped_colors,
                'slot_type': slot,
                'subtype': subtype,
                'pattern': 'solid',
                'sleeve_type': 'sleeveless' if slot == 'top' else None,
                'length': length_attr
            }
            name = generate_garment_name(tags)

            # Convert to WebP bytes
            buf = io.BytesIO()
            square_img.save(buf, format='WEBP', quality=90)
            img_bytes = buf.getvalue()

            pieces.append({
                'piece_index': idx,
                'slot_type': slot,
                'subtype': subtype,
                'length': length_attr,
                'item_name': name,
                'dominant_colours': mapped_colors,
                'colour_shares': valid_shares,
                'sleeve_type': tags.get('sleeve_type'),
                'is_cropped': is_cropped,
                'needs_review': needs_review,
                'review_note': review_note,
                'image_bytes': img_bytes,
                'width': 1000,
                'height': 1000
            })

        return {
            'is_person_outfit': True,
            'garments_found': len(pieces),
            'pieces': pieces,
            'inference_time_s': inference_time
        }
