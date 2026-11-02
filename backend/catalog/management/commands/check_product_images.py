"""
Management command: check_product_images
Validates product image URLs via HTTP HEAD requests with rate limiting.
Flags bad/unreachable images by setting is_image_valid = False without deleting data.
"""
from catalog.management.commands.validate_product_images import Command as ValidateImagesCommand

class Command(ValidateImagesCommand):
    help = (
        "Validates product image URLs via HTTP HEAD requests with rate limiting. "
        "Flags bad/unreachable images by setting is_image_valid = False without deleting data."
    )
