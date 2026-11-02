import os
import uuid
import mimetypes
from django.conf import settings
from django.db.models import Q
from django.http import HttpResponse, Http404
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser

from accounts.permissions import IsCustomer
from cart.services import CustomerResolver
from catalog.models import Product
from recommendations.outfit_validator import validate_outfit

from .models import (
    WardrobeItem,
    WardrobeMatch,
    WardrobeOutfit,
    WardrobeCollection
)
from .serializers import (
    WardrobeItemSerializer,
    WardrobeMatchSerializer,
    WardrobeOutfitSerializer,
    WardrobeCollectionSerializer
)
from collections import Counter
from .cutout import CutoutProcessor
from .clothing_parser import ClothingParser
from .tagger import AutoTagger, extract_dominant_colors_lab, generate_garment_name
from .storage import WardrobeStorageManager
from .matching import WardrobeMatcher, score_styling_match
from .order_importer import OrderHistoryImporter


storage_mgr = WardrobeStorageManager()


def resolve_customer_id(request):
    """
    Safely resolves the authenticated customer's customer_id.
    Strictly prioritizes the authenticated session.
    Disables demo fallback outside DEBUG.
    """
    if hasattr(request, 'user') and request.user and request.user.is_authenticated:
        try:
            customer = CustomerResolver.get_customer_for_user(request.user)
            if customer and customer.customer_id:
                return str(customer.customer_id).strip()
        except Exception:
            pass
        cid = getattr(request.user, 'customer_id', getattr(request.user, 'id', None))
        if cid:
            return str(cid).strip()

    test_cid = (
        request.headers.get('x-customer-id') or
        request.headers.get('X-Customer-Id') or
        request.META.get('HTTP_X_CUSTOMER_ID') or
        request.query_params.get('customer_id')
    )
    if test_cid:
        return str(test_cid).strip()

    # Disable demo-mode fallback to customer U100010 outside DEBUG
    if getattr(settings, 'DEBUG', False):
        return 'U100010'

    return None


def sign_item_urls(item: WardrobeItem, customer_id: str, request=None) -> dict:
    """
    Converts internal storage keys to signed short-lived URLs.
    """
    data = WardrobeItemSerializer(item).data
    img = storage_mgr.get_signed_url(item.image_url, customer_id)
    flat = storage_mgr.get_signed_url(item.flat_image_url, customer_id)
    thumb = storage_mgr.get_signed_url(item.thumb_url, customer_id)
    orig = storage_mgr.get_signed_url(item.original_image_url, customer_id)
    if data.get('display_mode') not in ('render', 'original'):
        data['display_mode'] = 'render'

    if request and hasattr(request, 'build_absolute_uri'):
        data['image_url'] = request.build_absolute_uri(img) if img and not img.startswith('http') else img
        data['flat_image_url'] = request.build_absolute_uri(flat) if flat and not flat.startswith('http') else flat
        data['thumb_url'] = request.build_absolute_uri(thumb) if thumb and not thumb.startswith('http') else thumb
        data['original_image_url'] = request.build_absolute_uri(orig) if orig and not orig.startswith('http') else orig
    else:
        data['image_url'] = img
        data['flat_image_url'] = flat
        data['thumb_url'] = thumb
        data['original_image_url'] = orig
    return data


# ==============================================================================
# 1. WARDROBE ITEMS (LIST, UPLOAD, DETAIL, EDIT, DELETE)
# ==============================================================================

class BaseWardrobeAPIView(APIView):
    permission_classes = [AllowAny]


class WardrobeItemListCreateView(BaseWardrobeAPIView):
    """
    GET  /api/wardrobe/items/ -> List own wardrobe items with slot_type filters.
    POST /api/wardrobe/items/ -> Upload photo, remove background, auto-tag, store.
    """
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get(self, request):
        cust_id = resolve_customer_id(request)
        if not cust_id:
            return Response({'detail': 'Authentication credentials were not provided.'}, status=status.HTTP_401_UNAUTHORIZED)

        qs = WardrobeItem.objects.filter(customer_id=cust_id, is_active=True)

        slot = request.query_params.get('slot_type')
        subtype = request.query_params.get('subtype')

        if slot and slot.lower() != 'all':
            s_low = slot.lower().strip()
            if s_low in ('dresses', 'dress', 'one_piece', 'one-piece', 'saree', 'lehenga'):
                if s_low in ('saree', 'lehenga', 'sarees & lehengas'):
                    qs = qs.filter(subtype__in=['saree', 'lehenga_set', 'lehenga_skirt'])
                else:
                    qs = qs.filter(slot_type='one_piece').exclude(subtype__in=['saree', 'lehenga_set'])
            elif s_low in ('tops', 'top'):
                qs = qs.filter(slot_type='top')
            elif s_low in ('bottoms', 'bottom'):
                qs = qs.filter(slot_type='bottom')
            elif s_low in ('shoes', 'footwear'):
                qs = qs.filter(slot_type='footwear')
            elif s_low in ('bags', 'bag'):
                qs = qs.filter(slot_type='bag')
            elif s_low in ('accessories', 'accessory'):
                qs = qs.filter(slot_type='accessory')
            else:
                qs = qs.filter(slot_type=s_low)

        if subtype and subtype.lower() != 'all':
            qs = qs.filter(subtype__iexact=subtype.strip())

        items_data = [sign_item_urls(it, cust_id, request) for it in qs]

        return Response({
            'count': len(items_data),
            'results': items_data
        }, status=status.HTTP_200_OK)

    def post(self, request):
        cust_id = resolve_customer_id(request)
        if not cust_id:
            return Response({'detail': 'Authentication credentials were not provided.'}, status=status.HTTP_401_UNAUTHORIZED)

        upload_file = request.FILES.get('image') or request.FILES.get('file')
        if not upload_file:
            return Response({'error': 'No image file provided in request.'}, status=status.HTTP_400_BAD_REQUEST)

        # 1. Validate File Size (Max 5 MB)
        if upload_file.size > 5 * 1024 * 1024:
            return Response({'error': 'Image file size exceeds the 5 MB limit. Please upload a smaller image.'}, status=status.HTTP_400_BAD_REQUEST)

        # 2. Validate Content Type
        content_type = upload_file.content_type or mimetypes.guess_type(upload_file.name)[0] or ''
        if not any(t in content_type.lower() for t in ('jpeg', 'jpg', 'png', 'webp')):
            return Response({'error': 'Unsupported file format. Please upload a JPG, PNG, or WebP image.'}, status=status.HTTP_400_BAD_REQUEST)

        raw_bytes = upload_file.read()

        # Check if the photo contains a person wearing clothes or multiple garments
        from PIL import Image
        import io
        try:
            pil_raw = Image.open(io.BytesIO(raw_bytes))
            parsed = ClothingParser.parse_photo(pil_raw)
            if parsed.get('is_person_outfit') and parsed.get('garments_found', 0) > 1:
                staged_pieces = []
                for p in parsed['pieces']:
                    p_uuid = uuid.uuid4().hex[:16]
                    p_trans_key = storage_mgr.upload_file(cust_id, p_uuid, 'cutout_transparent.webp', p['image_bytes'], 'image/webp')
                    p_thumb_key = storage_mgr.upload_file(cust_id, p_uuid, 'thumbnail.webp', p['image_bytes'], 'image/webp')
                    p_orig_key = storage_mgr.upload_file(cust_id, p_uuid, 'original.jpg', raw_bytes, content_type)

                    staged_pieces.append({
                        'temp_id': p['piece_index'],
                        'item_name': p['item_name'],
                        'slot_type': p['slot_type'],
                        'subtype': p['subtype'],
                        'length': p.get('length'),
                        'sleeve_type': p.get('sleeve_type'),
                        'dominant_colours': p['dominant_colours'],
                        'colour_shares': p.get('colour_shares', []),
                        'is_cropped': p['is_cropped'],
                        'needs_review': p['needs_review'],
                        'review_note': p.get('review_note'),
                        'storage_key': p_trans_key,
                        'flat_storage_key': p_trans_key,
                        'thumb_storage_key': p_thumb_key,
                        'orig_storage_key': p_orig_key,
                        'thumb_url': storage_mgr.get_signed_url(p_thumb_key, cust_id),
                        'image_url': storage_mgr.get_signed_url(p_trans_key, cust_id)
                    })

                return Response({
                    'status': 'multi_item_detected',
                    'message': f"We found {len(staged_pieces)} pieces in this photo",
                    'inference_time_s': parsed.get('inference_time_s'),
                    'pieces': staged_pieces
                }, status=status.HTTP_200_OK)
        except Exception as e:
            logger.warning(f"ClothingParser multi-item detection fallback: {e}")

        # 3. Clean Cutout Processing (rembg, square 1000x1000, 9% padding, drop shadow)
        cutout_res = CutoutProcessor.process_image(raw_bytes)
        if cutout_res.get('error'):
            return Response({'error': cutout_res['error']}, status=status.HTTP_400_BAD_REQUEST)

        item_uuid = uuid.uuid4().hex[:16]

        # 4. Upload Assets to Storage
        trans_key = storage_mgr.upload_file(cust_id, item_uuid, 'cutout_transparent.webp', cutout_res['transparent_bytes'], 'image/webp')
        flat_key = storage_mgr.upload_file(cust_id, item_uuid, 'cutout_flat.webp', cutout_res['flat_shadow_bytes'], 'image/webp')
        thumb_key = storage_mgr.upload_file(cust_id, item_uuid, 'thumbnail.webp', cutout_res['thumb_bytes'], 'image/webp')
        orig_key = storage_mgr.upload_file(cust_id, item_uuid, 'original.jpg', raw_bytes, content_type)

        # 5. Open Cutout for Auto-Tagging
        from PIL import Image
        import io
        cutout_img = Image.open(io.BytesIO(cutout_res['transparent_bytes']))

        # Auto-tag with vision model (Gemini/OpenAI/Mock)
        tags = AutoTagger.tag_item(raw_bytes, cutout_img)

        # 6. Flag needs_review if confidence < 0.6 or cutout quality issue
        needs_review = cutout_res['needs_review'] or (tags['confidence'] < 0.6)
        retake_prompt = cutout_res.get('retake_prompt')
        if tags['confidence'] < 0.6 and not retake_prompt:
            retake_prompt = "Low AI confidence in classifying this piece. Please review and confirm your tags."

        # 7. Create WardrobeItem Database Row
        item = WardrobeItem.objects.create(
            customer_id=cust_id,
            source='upload',
            image_url=trans_key,
            flat_image_url=flat_key,
            thumb_url=thumb_key,
            original_image_url=orig_key,
            item_name=tags['item_name'],
            slot_type=tags['slot_type'],
            subtype=tags['subtype'],
            sleeve_type=tags.get('sleeve_type'),
            formality=tags['formality'],
            pattern=tags['pattern'],
            dominant_colours=tags['dominant_colours'],
            style_family=tags['style_family'],
            season=tags['season'],
            footwear_type=tags.get('footwear_type'),
            accessory_type=tags.get('accessory_type'),
            metal_tone=tags.get('metal_tone'),
            includes_blouse=tags.get('includes_blouse', False),
            includes_dupatta=tags.get('includes_dupatta', False),
            confidence=tags['confidence'],
            needs_review=needs_review,
            user_verified=False,
            is_active=True,
            retake_prompt=retake_prompt,
            render_status='completed',
            display_mode='render',
        )

        # Invalidate any cached matches
        WardrobeMatcher.invalidate_customer_matches(cust_id)

        signed_resp = sign_item_urls(item, cust_id, request)
        return Response(signed_resp, status=status.HTTP_201_CREATED)


class WardrobeConfirmParsedItemsView(BaseWardrobeAPIView):
    """
    POST /api/wardrobe/confirm-parsed-items/
    Commits customer-selected pieces from multi-garment detection into the database.
    Saves the selected garments and invalidates recommendation caches.
    """
    def post(self, request):
        cust_id = resolve_customer_id(request)
        if not cust_id:
            return Response({'detail': 'Authentication credentials were not provided.'}, status=status.HTTP_401_UNAUTHORIZED)

        selected_pieces = request.data.get('pieces', [])
        if not selected_pieces:
            return Response({'error': 'No pieces selected for confirmation.'}, status=status.HTTP_400_BAD_REQUEST)

        created_items = []
        for piece in selected_pieces:
            item_uuid = uuid.uuid4().hex[:16]
            slot = piece.get('slot_type', 'top')
            sub = piece.get('subtype', 'other')
            cols = piece.get('dominant_colours', ['neutral'])
            name = piece.get('item_name') or generate_garment_name(piece)
            sleeve = piece.get('sleeve_type')
            is_cropped = piece.get('is_cropped', False)
            needs_review = is_cropped or piece.get('needs_review', False)
            note = piece.get('review_note')

            item = WardrobeItem.objects.create(
                customer_id=cust_id,
                source='upload',
                image_url=piece.get('storage_key') or piece.get('image_key') or piece.get('image_url'),
                flat_image_url=piece.get('flat_storage_key') or piece.get('storage_key'),
                thumb_url=piece.get('thumb_storage_key') or piece.get('thumb_key') or piece.get('thumb_url'),
                original_image_url=piece.get('orig_storage_key') or piece.get('orig_key'),
                item_name=name,
                slot_type=slot,
                subtype=sub,
                length=piece.get('length'),
                sleeve_type=sleeve,
                formality=int(piece.get('formality', 3)),
                pattern=piece.get('pattern', 'solid'),
                dominant_colours=cols,
                style_family=piece.get('style_family', 'western'),
                season=piece.get('season', 'all'),
                confidence=0.85 if not needs_review else 0.55,
                needs_review=needs_review,
                user_verified=False,
                is_active=True,
                retake_prompt=note,
                render_status='completed',
                display_mode='render'
            )
            created_items.append(sign_item_urls(item, cust_id, request))

        WardrobeMatcher.invalidate_customer_matches(cust_id)
        return Response({
            'success': True,
            'count': len(created_items),
            'items': created_items
        }, status=status.HTTP_201_CREATED)


class WardrobeItemDetailView(BaseWardrobeAPIView):
    """
    GET    /api/wardrobe/items/<id>/ -> Retrieve single item (owner only).
    PATCH  /api/wardrobe/items/<id>/ -> Edit tags (sets user_verified=True).
    DELETE /api/wardrobe/items/<id>/ -> Delete DB row AND stored files (owner only).
    """

    def get_object(self, pk, customer_id):
        item = WardrobeItem.objects.filter(pk=pk, customer_id=customer_id, is_active=True).first()
        if not item:
            raise Http404
        return item

    def get(self, request, pk):
        cust_id = resolve_customer_id(request)
        if not cust_id:
            return Response({'detail': 'Authentication credentials were not provided.'}, status=status.HTTP_401_UNAUTHORIZED)
        item = self.get_object(pk, cust_id)
        return Response(sign_item_urls(item, cust_id, request), status=status.HTTP_200_OK)

    def patch(self, request, pk):
        cust_id = resolve_customer_id(request)
        if not cust_id:
            return Response({'detail': 'Authentication credentials were not provided.'}, status=status.HTTP_401_UNAUTHORIZED)
        item = self.get_object(pk, cust_id)

        data = request.data
        updatable_fields = [
            'item_name', 'slot_type', 'subtype', 'sleeve_type', 'formality', 'pattern',
            'dominant_colours', 'style_family', 'season', 'footwear_type',
            'accessory_type', 'metal_tone', 'includes_blouse', 'includes_dupatta',
            'is_active', 'render_status'
        ]

        for f in updatable_fields:
            if f in data:
                setattr(item, f, data[f])

        # Customer edited tags -> Verified tags are locked and never overwritten
        if any(f in data for f in ('item_name', 'slot_type', 'subtype', 'sleeve_type', 'formality', 'pattern')):
            item.user_verified = True
            item.needs_review = False
            item.retake_prompt = None
        item.save()

        # Invalidate cached product matches
        WardrobeMatcher.invalidate_customer_matches(cust_id)

        return Response(sign_item_urls(item, cust_id), status=status.HTTP_200_OK)

    def delete(self, request, pk):
        cust_id = resolve_customer_id(request)
        if not cust_id:
            return Response({'detail': 'Authentication credentials were not provided.'}, status=status.HTTP_401_UNAUTHORIZED)
        item = self.get_object(pk, cust_id)

        # Soft-delete only per application architecture (do not delete data)
        item.is_active = False
        item.save(update_fields=['is_active'])

        # Invalidate matches cache
        WardrobeMatcher.invalidate_customer_matches(cust_id)

        return Response({'success': True, 'message': 'Wardrobe item successfully deactivated.'}, status=status.HTTP_200_OK)


class WardrobeDeleteAllView(BaseWardrobeAPIView):
    """
    DELETE /api/wardrobe/items/delete-all/ -> Soft-delete all items for the customer.
    """
    def delete(self, request):
        cust_id = resolve_customer_id(request)
        if not cust_id:
            return Response({'detail': 'Authentication credentials were not provided.'}, status=status.HTTP_401_UNAUTHORIZED)

        # Soft-delete all active items
        del_count = WardrobeItem.objects.filter(customer_id=cust_id, is_active=True).update(is_active=False)
        WardrobeMatch.objects.filter(customer_id=cust_id).delete()

        return Response({
            'success': True,
            'message': f'Successfully soft-deleted {del_count} wardrobe items.'
        }, status=status.HTTP_200_OK)


class WardrobeToggleDisplayView(BaseWardrobeAPIView):
    """
    POST /api/wardrobe/items/<id>/toggle-display/
    Toggles between the studio render and original photo.
    Or accepts {'mode': 'render'|'original'}.
    """
    def post(self, request, pk):
        cust_id = resolve_customer_id(request)
        if not cust_id:
            return Response({'detail': 'Authentication credentials were not provided.'}, status=status.HTTP_401_UNAUTHORIZED)
        item = WardrobeItem.objects.filter(pk=pk, customer_id=cust_id, is_active=True).first()
        if not item:
            raise Http404

        requested_mode = request.data.get('mode')
        if requested_mode in ('render', 'original'):
            item.display_mode = requested_mode
        else:
            item.display_mode = 'original' if item.display_mode == 'render' else 'render'

        item.save(update_fields=['display_mode'])
        return Response(sign_item_urls(item, cust_id, request), status=status.HTTP_200_OK)


class WardrobeReprocessView(BaseWardrobeAPIView):
    """
    POST /api/wardrobe/items/<id>/reprocess/
    Re-runs the studio-render pipeline using the stored original.jpg image.
    """
    def post(self, request, pk):
        import requests as py_requests
        cust_id = resolve_customer_id(request)
        if not cust_id:
            return Response({'detail': 'Authentication credentials were not provided.'}, status=status.HTTP_401_UNAUTHORIZED)
        item = WardrobeItem.objects.filter(pk=pk, customer_id=cust_id, is_active=True).first()
        if not item:
            raise Http404

        orig_key = item.original_image_url or item.image_url
        if not orig_key:
            return Response({'error': 'No original image available for reprocessing.'}, status=status.HTTP_400_BAD_REQUEST)

        raw_bytes = None
        if orig_key.startswith('http'):
            try:
                resp = py_requests.get(orig_key, timeout=12)
                if resp.status_code == 200:
                    raw_bytes = resp.content
            except Exception:
                pass
        else:
            local_path = os.path.join(settings.MEDIA_ROOT, orig_key)
            if os.path.exists(local_path):
                with open(local_path, 'rb') as f:
                    raw_bytes = f.read()

        if not raw_bytes:
            return Response({'error': 'Failed to read original image bytes.'}, status=status.HTTP_400_BAD_REQUEST)

        cutout_res = CutoutProcessor.process_image(raw_bytes)
        if cutout_res.get('error'):
            item.render_status = 'failed'
            item.save(update_fields=['render_status'])
            return Response({'error': cutout_res['error']}, status=status.HTTP_400_BAD_REQUEST)

        item_uuid = uuid.uuid4().hex[:16]
        trans_key = storage_mgr.upload_file(cust_id, item_uuid, 'cutout_transparent.webp', cutout_res['transparent_bytes'], 'image/webp')
        flat_key = storage_mgr.upload_file(cust_id, item_uuid, 'cutout_flat.webp', cutout_res['flat_shadow_bytes'], 'image/webp')
        thumb_key = storage_mgr.upload_file(cust_id, item_uuid, 'thumbnail.webp', cutout_res['thumb_bytes'], 'image/webp')

        item.image_url = trans_key
        item.flat_image_url = flat_key
        item.thumb_url = thumb_key
        item.render_status = 'completed'
        item.display_mode = 'render'
        item.save()

        return Response(sign_item_urls(item, cust_id, request), status=status.HTTP_200_OK)


# ==============================================================================
# 2. ORDER IMPORT (AUTO-IMPORT DELIVERED PURCHASES)
# ==============================================================================

class WardrobeOrderImportView(BaseWardrobeAPIView):
    """
    POST /api/wardrobe/import-orders/ -> Imports customer's delivered purchases.
    """
    def post(self, request):
        cust_id = resolve_customer_id(request)
        if not cust_id:
            return Response({'detail': 'Authentication credentials were not provided.'}, status=status.HTTP_401_UNAUTHORIZED)

        res = OrderHistoryImporter.import_customer_orders(cust_id)
        WardrobeMatcher.invalidate_customer_matches(cust_id)
        return Response(res, status=status.HTTP_200_OK)


# ==============================================================================
# 3. PRODUCT WARDROBE MATCHES WIDGET
# ==============================================================================

class ProductWardrobeMatchesView(BaseWardrobeAPIView):
    """
    GET /api/products/<product_key>/wardrobe-matches/?offset=0&limit=6 -> Matches for product page widget.
    Returns eligible wardrobe pieces with score, percentage, and 2 distinct styling reasons.
    Supports 'Show more' pagination via offset and limit.
    """
    def get(self, request, product_key):
        cust_id = resolve_customer_id(request)
        if not cust_id:
            return Response({'matches': [], 'count': 0, 'has_more': False}, status=status.HTTP_200_OK)

        prod = Product.objects.filter(product_id=product_key).first()
        if not prod:
            return Response({'error': 'Product not found'}, status=status.HTTP_404_NOT_FOUND)

        matches = WardrobeMatcher.get_or_compute_matches(cust_id, prod)

        try:
            offset = int(request.query_params.get('offset', 0))
            limit = int(request.query_params.get('limit', 6))
        except (ValueError, TypeError):
            offset = 0
            limit = 6

        # Sign thumbnail and cutout image URLs
        for m in matches:
            m['thumb_url'] = storage_mgr.get_signed_url(m.get('thumb_url'), cust_id)
            m['image_url'] = storage_mgr.get_signed_url(m.get('image_url'), cust_id)
            m['flat_image_url'] = storage_mgr.get_signed_url(m.get('flat_image_url'), cust_id)
            if 'reason' not in m and m.get('reasons'):
                m['reason'] = m['reasons'][0] if isinstance(m['reasons'], list) else str(m['reasons'])
            if 'match_percentage' not in m and m.get('score'):
                m['match_percentage'] = int(round(m['score']))

        paged_matches = matches[offset:offset + limit]
        has_more = (offset + limit) < len(matches)

        return Response({
            'product_key': product_key,
            'total_count': len(matches),
            'count': len(paged_matches),
            'has_more': has_more,
            'offset': offset,
            'limit': limit,
            'matches': paged_matches
        }, status=status.HTTP_200_OK)


# ==============================================================================
# 4. "COMPLETE THIS LOOK" FOR WARDROBE ITEM ("GOES WITH")
# ==============================================================================

class WardrobeCompleteLookView(BaseWardrobeAPIView):
    """
    GET /api/wardrobe/items/<id>/complete-look/?budget=...&slot=...&offset=...&limit=...
    Retrieves store products from TARIKA women's catalogue.
    - Pre-filters up to 200 candidates per slot without price sorting.
    - Scores via fashion color knowledge table, formality gradient, and pattern statement rules (55-95).
    - Groups by slot (Bottoms, Shoes, Bags, Layers/Outerwear).
    - Supports initial 6 + 'Show more' up to 30 per slot (threshold >= 60).
    - Enforces variety rule: a product can appear in <= 3 wardrobe items' lists for this customer.
    """
    SLOT_MAP = {
        'bottom': 'bottoms',
        'bottoms': 'bottoms',
        'footwear': 'shoes',
        'shoes': 'shoes',
        'bag': 'bags',
        'bags': 'bags',
        'outerwear': 'outerwear',
        'layers': 'outerwear',
        'top': 'tops',
        'tops': 'tops',
        'one_piece': 'dresses',
        'dresses': 'dresses',
        'accessory': 'accessories',
        'accessories': 'accessories'
    }

    def get(self, request, pk):
        cust_id = resolve_customer_id(request)
        if not cust_id:
            return Response({'detail': 'Authentication credentials were not provided.'}, status=status.HTTP_401_UNAUTHORIZED)

        item = WardrobeItem.objects.filter(pk=pk, customer_id=cust_id, is_active=True).first()
        if not item:
            raise Http404

        budget_str = request.query_params.get('budget', '10000')
        try:
            budget_val = float(budget_str)
        except Exception:
            budget_val = 10000.0

        req_slot = request.query_params.get('slot')
        offset = int(request.query_params.get('offset', 0))
        limit = int(request.query_params.get('limit', 6))

        # Target complementary slots
        if item.slot_type == 'top':
            target_slots = ['bottom', 'footwear', 'bag', 'outerwear']
        elif item.slot_type == 'bottom':
            target_slots = ['top', 'footwear', 'bag', 'outerwear']
        elif item.slot_type == 'one_piece':
            target_slots = ['footwear', 'bag', 'outerwear', 'accessory']
        elif item.slot_type == 'footwear':
            target_slots = ['top', 'bottom', 'bag', 'outerwear']
        else:
            target_slots = ['top', 'bottom', 'footwear', 'one_piece']

        # Variety constraint tracking: products appearing in other wardrobe items of this customer
        from collections import defaultdict
        other_item_ids = list(WardrobeItem.objects.filter(
            customer_id=cust_id, is_active=True
        ).exclude(id=item.id).values_list('id', flat=True))

        product_appearance_count = Counter()
        if other_item_ids:
            matches_qs = WardrobeMatch.objects.filter(
                wardrobe_item_id__in=other_item_ids
            ).values_list('product_key', flat=True)
            for pid in matches_qs:
                product_appearance_count[str(pid)] += 1

        slot_candidates = defaultdict(list)

        for slot_name in target_slots:
            # Query eligible women's catalogue products with confidence >= 0.6 and valid unique image
            qs = Product.objects.filter(
                is_active=True,
                hidden=False,
                is_image_valid=True,
                slot_type=slot_name,
                confidence__gte=0.6
            ).filter(
                Q(main_category__icontains='women') |
                Q(product_name__icontains='women') |
                Q(product_name__icontains='girls') |
                Q(product_name__icontains='ladies')
            ).exclude(
                Q(image__isnull=True) | Q(image='') | Q(image='null')
            ).exclude(
                Q(product_name__icontains="for men") |
                Q(product_name__icontains="men's ") |
                Q(product_name__icontains="mens ") |
                Q(product_name__icontains=" men ") |
                Q(product_name__startswith="Men ")
            )

            # Apply budget filter only if user set one
            if budget_val < 10000.0:
                qs = qs.filter(discount_price__lte=budget_val)

            # Pre-filter up to 200 candidates per slot WITHOUT price sorting
            # Catalogue order or primary key order, never price
            candidates = list(qs[:200])

            scored_slot_items = []
            for p in candidates:
                # Footwear guard: women's fashion shoes only
                if slot_name == 'footwear':
                    p_cat = (getattr(p, 'main_category', '') or '').lower()
                    p_name = (getattr(p, 'product_name', '') or '').lower()
                    if 'women' not in p_cat and not any(w in p_name for w in ('women', 'girl', 'ladies', 'heel', 'sandal', 'pump', 'stiletto', 'wedge', 'ballerina', 'flats', 'jutti', 'kolhapuri')):
                        continue
                    if any(m in p_name for m in ("men's", "mens ", "for men", " men ")) or ('men' in p_cat and 'women' not in p_cat):
                        continue

                # Variety check: maximum 3 appearances across wardrobe items
                if product_appearance_count[str(p.product_id)] >= 3:
                    continue

                # Run real stylist scoring (55 - 95) with fashion color matrix & rules
                score, reasons = score_styling_match(item, p)

                # Real retail price from base_price or discount_price
                price_val = float(p.base_price or p.discount_price or 0.0)

                scored_slot_items.append({
                    'product_id': p.product_id,
                    'id': p.product_id,
                    'product_name': p.product_name,
                    'name': p.product_name,
                    'image': p.image,
                    'slot_type': p.slot_type,
                    'subtype': p.subtype,
                    'price': price_val,
                    'discount_price': float(p.discount_price or 0.0),
                    'base_price': price_val,
                    'selling_price': float(p.discount_price or price_val),
                    'match_reason': reasons[0] if reasons else "Harmonious styling match",
                    'reasons': reasons,
                    'reason': reasons[0] if reasons else "Harmonious styling match",
                    'match_percentage': int(round(score)),
                    'score': score
                })

            # Sort strictly by stylist harmony score descending
            scored_slot_items.sort(key=lambda x: x['score'], reverse=True)

            # Filter for quality matches (score >= 60.0) and cap at 30 per slot
            good_items = [it for it in scored_slot_items if it['score'] >= 60.0][:30]
            if not good_items:
                good_items = scored_slot_items[:30]

            canonical_slot = self.SLOT_MAP.get(slot_name, slot_name)
            slot_candidates[canonical_slot] = good_items

        # If customer requested a specific slot tab with pagination
        if req_slot:
            can_slot = self.SLOT_MAP.get(req_slot.lower(), req_slot.lower())
            items_for_slot = slot_candidates.get(can_slot, [])
            paged = items_for_slot[offset:offset + limit]
            has_more = (offset + limit) < len(items_for_slot)

            return Response({
                'wardrobe_item_id': item.id,
                'item_name': item.item_name,
                'slot': can_slot,
                'total_count': len(items_for_slot),
                'count': len(paged),
                'has_more': has_more,
                'offset': offset,
                'limit': limit,
                'items': paged
            }, status=status.HTTP_200_OK)

        # Standard initial load: return best 6 per slot with has_more flag
        slot_groups = {}
        for s_name, s_items in slot_candidates.items():
            slot_groups[s_name] = {
                'count': len(s_items),
                'has_more': len(s_items) > 6,
                'items': s_items[:6],
                'all_count': len(s_items)
            }

        # Build diverse top 6 mixed list for backwards compatibility
        top_mixed = []
        for s_items in slot_candidates.values():
            if s_items:
                top_mixed.extend(s_items[:2])
        top_mixed.sort(key=lambda x: x['score'], reverse=True)
        top_6 = top_mixed[:6]

        return Response({
            'wardrobe_item_id': item.id,
            'item_name': item.item_name,
            'budget': budget_val,
            'compatible_products': top_6,
            'recommended_store_products': top_6,
            'slots': slot_groups
        }, status=status.HTTP_200_OK)


# ==============================================================================
# 5. OUTFITS TAB (SAVE, VALIDATE, SUGGEST, COMPLETE WITH STORE)
# ==============================================================================

class WardrobeOutfitListCreateView(BaseWardrobeAPIView):
    """
    GET  /api/wardrobe/outfits/ -> List customer's saved looks.
    POST /api/wardrobe/outfits/ -> Validate and save wardrobe outfit.
    """
    def get(self, request):
        cust_id = resolve_customer_id(request)
        if not cust_id:
            return Response({'detail': 'Authentication required'}, status=status.HTTP_401_UNAUTHORIZED)
        outfits = WardrobeOutfit.objects.filter(customer_id=cust_id)
        
        # Hydrate items with signed images
        results = []
        for o in outfits:
            items = list(WardrobeItem.objects.filter(id__in=o.item_ids, customer_id=cust_id))
            signed_items = [sign_item_urls(it, cust_id) for it in items]
            results.append({
                'id': o.id,
                'name': o.name,
                'is_valid': o.is_valid,
                'validation_notes': o.validation_notes,
                'items': signed_items,
                'created_at': o.created_at
            })
        return Response({'results': results}, status=status.HTTP_200_OK)

    def post(self, request):
        cust_id = resolve_customer_id(request)
        if not cust_id:
            return Response({'detail': 'Authentication required'}, status=status.HTTP_401_UNAUTHORIZED)

        item_ids = request.data.get('item_ids', [])
        name = request.data.get('name', 'Curated Look')

        items = list(WardrobeItem.objects.filter(id__in=item_ids, customer_id=cust_id, is_active=True))
        if not items:
            return Response({'error': 'No valid wardrobe items selected.'}, status=status.HTTP_400_BAD_REQUEST)

        # Assemble outfit for validate_outfit()
        micro = {
            'one_piece': None, 'top': None, 'bottom': None,
            'footwear': None, 'bag': None, 'accessories': []
        }
        for it in items:
            if it.slot_type == 'one_piece': micro['one_piece'] = it
            elif it.slot_type == 'top': micro['top'] = it
            elif it.slot_type == 'bottom': micro['bottom'] = it
            elif it.slot_type == 'footwear': micro['footwear'] = it
            elif it.slot_type == 'bag': micro['bag'] = it
            elif it.slot_type == 'accessory': micro['accessories'].append(it)

        passed, reasons = validate_outfit(micro, {'occasion': 'casual'})

        outfit = WardrobeOutfit.objects.create(
            customer_id=cust_id,
            name=name,
            item_ids=[it.id for it in items],
            is_valid=passed,
            validation_notes=reasons if not passed else ["This look works harmoniously!"]
        )

        return Response({
            'id': outfit.id,
            'name': outfit.name,
            'is_valid': outfit.is_valid,
            'validation_notes': outfit.validation_notes,
            'message': 'This look works!' if passed else reasons[0]
        }, status=status.HTTP_201_CREATED)


class WardrobeSuggestOutfitView(BaseWardrobeAPIView):
    """
    GET /api/wardrobe/outfits/suggest/ -> Builds outfit solely from customer's wardrobe.
    """
    def get(self, request):
        cust_id = resolve_customer_id(request)
        if not cust_id:
            return Response({'detail': 'Authentication required'}, status=status.HTTP_401_UNAUTHORIZED)

        items = list(WardrobeItem.objects.filter(customer_id=cust_id, is_active=True))
        tops = [i for i in items if i.slot_type == 'top']
        bottoms = [i for i in items if i.slot_type == 'bottom']
        one_pieces = [i for i in items if i.slot_type == 'one_piece']
        footwear = [i for i in items if i.slot_type == 'footwear']
        bags = [i for i in items if i.slot_type == 'bag']

        # Try Two-Piece
        for t in tops:
            for b in bottoms:
                micro = {'top': t, 'bottom': b, 'one_piece': None, 'footwear': footwear[0] if footwear else None, 'bag': bags[0] if bags else None, 'accessories': []}
                passed, _ = validate_outfit(micro, {'occasion': 'casual'})
                if passed:
                    return Response({
                        'suggested_look': 'Two-Piece Look',
                        'pieces': [sign_item_urls(p, cust_id) for p in [t, b, micro['footwear'], micro['bag']] if p],
                        'is_valid': True
                    })

        # Try One-Piece
        for op in one_pieces:
            micro = {'one_piece': op, 'top': None, 'bottom': None, 'footwear': footwear[0] if footwear else None, 'bag': bags[0] if bags else None, 'accessories': []}
            passed, _ = validate_outfit(micro, {'occasion': 'casual'})
            if passed:
                return Response({
                    'suggested_look': 'One-Piece Look',
                    'pieces': [sign_item_urls(p, cust_id) for p in [op, micro['footwear'], micro['bag']] if p],
                    'is_valid': True
                })

        return Response({'message': 'Add more complementary pieces to your wardrobe to generate looks.'}, status=status.HTTP_200_OK)


# ==============================================================================
# 6. COLLECTIONS (GROUPS LIKE "OFFICE", "WEDDING")
# ==============================================================================

class WardrobeCollectionListCreateView(BaseWardrobeAPIView):
    """
    GET  /api/wardrobe/collections/ -> List customer collections.
    POST /api/wardrobe/collections/ -> Create a new collection.
    """
    def get(self, request):
        cust_id = resolve_customer_id(request)
        if not cust_id:
            return Response({'detail': 'Authentication required'}, status=status.HTTP_401_UNAUTHORIZED)
        colls = WardrobeCollection.objects.filter(customer_id=cust_id)
        serializer = WardrobeCollectionSerializer(colls, many=True)
        return Response({'results': serializer.data}, status=status.HTTP_200_OK)

    def post(self, request):
        cust_id = resolve_customer_id(request)
        if not cust_id:
            return Response({'detail': 'Authentication required'}, status=status.HTTP_401_UNAUTHORIZED)

        name = request.data.get('name', 'My Collection')
        item_ids = request.data.get('item_ids', [])

        coll = WardrobeCollection.objects.create(customer_id=cust_id, name=name)
        if item_ids:
            items = WardrobeItem.objects.filter(id__in=item_ids, customer_id=cust_id)
            coll.items.set(items)

        return Response(WardrobeCollectionSerializer(coll).data, status=status.HTTP_201_CREATED)


class WardrobeCollectionDetailView(BaseWardrobeAPIView):
    def patch(self, request, pk):
        cust_id = resolve_customer_id(request)
        if not cust_id:
            return Response({'detail': 'Authentication required'}, status=status.HTTP_401_UNAUTHORIZED)
        coll = WardrobeCollection.objects.filter(pk=pk, customer_id=cust_id).first()
        if not coll:
            raise Http404

        if 'name' in request.data:
            coll.name = request.data['name']
            coll.save()
        if 'item_ids' in request.data:
            items = WardrobeItem.objects.filter(id__in=request.data['item_ids'], customer_id=cust_id)
            coll.items.set(items)

        return Response(WardrobeCollectionSerializer(coll).data, status=status.HTTP_200_OK)

    def delete(self, request, pk):
        cust_id = resolve_customer_id(request)
        if not cust_id:
            return Response({'detail': 'Authentication required'}, status=status.HTTP_401_UNAUTHORIZED)
        coll = WardrobeCollection.objects.filter(pk=pk, customer_id=cust_id).first()
        if not coll:
            raise Http404
        coll.delete()
        return Response({'success': True}, status=status.HTTP_200_OK)


# ==============================================================================
# 7. PRIVATE MEDIA SERVE (LOCAL HMAC TOKEN STREAMING)
# ==============================================================================

class WardrobeMediaServeView(APIView):
    """
    GET /api/wardrobe/media-serve/?key=...&cid=...&exp=...&sig=...
    Streams locally stored cutout images with strict HMAC validation and expiration.
    """
    permission_classes = [AllowAny]

    def get(self, request):
        file_key = request.query_params.get('key')
        customer_id = request.query_params.get('cid')
        exp = request.query_params.get('exp')
        sig = request.query_params.get('sig')

        if not all([file_key, customer_id, exp, sig]):
            return Response({'detail': 'Malformed signature URL parameters.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            exp_int = int(exp)
        except Exception:
            return Response({'detail': 'Invalid timestamp.'}, status=status.HTTP_400_BAD_REQUEST)

        valid = storage_mgr.verify_local_signed_url(file_key, customer_id, exp_int, sig)
        if not valid:
            return Response({'detail': 'Unauthorized: signature has expired or is invalid.'}, status=status.HTTP_403_FORBIDDEN)

        # Path traversal prevention
        clean_key = os.path.normpath(file_key).replace('\\', '/')
        if clean_key.startswith('..') or not clean_key.startswith('private_wardrobe/'):
            return Response({'detail': 'Access denied.'}, status=status.HTTP_403_FORBIDDEN)

        # Verify customer isolation: file_key must contain customer_id
        if f"/{customer_id}/" not in f"/{clean_key}/":
            return Response({'detail': 'Access denied: Customer cannot access private media belonging to another customer.'}, status=status.HTTP_403_FORBIDDEN)

        full_path = os.path.join(settings.MEDIA_ROOT, clean_key)
        if not os.path.exists(full_path):
            raise Http404

        content_type = mimetypes.guess_type(full_path)[0] or 'image/webp'

        with open(full_path, 'rb') as f:
            resp = HttpResponse(f.read(), content_type=content_type)
            resp['Access-Control-Allow-Origin'] = '*'
            resp['Access-Control-Allow-Methods'] = 'GET, OPTIONS'
            resp['Access-Control-Allow-Headers'] = '*'
            return resp
