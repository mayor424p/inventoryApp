# backend/inventory_app/utils.py

import barcode
from barcode.writer import ImageWriter
from io import BytesIO
import os
import uuid
from django.conf import settings # Import settings for MEDIA_ROOT
from django.core.files.base import ContentFile

def generate_barcode_string():
    """
    Generates a unique barcode string using UUID4.

    Returns:
        str: A unique UUID string, e.g., '123e4567-e89b-12d3-a456-426614174000'.
             Returns None if generation fails (unlikely for UUID).
    """
    try:
        # Generate a random UUID4 string
        barcode_uuid = str(uuid.uuid4())
        return barcode_uuid
    except Exception as e:
        print(f"Error generating barcode string: {e}")
        return None

def generate_barcode_image_from_string(barcode_string, barcode_type='code128', output_filename=None):
    """
    Generates a barcode image from a given barcode string (e.g., UUID)
    and saves it to the filesystem.

    Args:
        barcode_string (str): The barcode code to encode (e.g., a UUID).
        barcode_type (str): The type of barcode (e.g., 'code128', 'ean13'). Defaults to 'code128'.
        output_filename (str, optional): Desired filename for the saved image. If None, defaults to {barcode_string}.png.

    Returns:
        str: The relative path to the saved barcode image (relative to MEDIA_ROOT)
             e.g., 'barcodes/123e4567-e89b-12d3-a456-426614174000.png'
             Returns None if generation fails.
    """
    try:
        # Get the barcode class
        barcode_class = barcode.get_barcode_class(barcode_type)
        if not barcode_class:
            print(f"Unsupported barcode type: {barcode_type}")
            return None

        # Create the barcode object
        writer_options = {
            "module_width": 0.2,
            "module_height": 15,
            "quiet_zone": 1,
            "font_size": 10,
            "text_distance": 5,
            "write_text": True, # Usually good to show the code itself on the image
        }
        barcode_obj = barcode_class(barcode_string, writer=ImageWriter())

        # Prepare the filename and path
        if not output_filename:
            output_filename = f"{barcode_string}.png" # Default filename based on the string

        # Define the directory within MEDIA_ROOT to store barcodes
        barcode_directory = 'barcodes'
        barcode_path = os.path.join(settings.MEDIA_ROOT, barcode_directory)
        os.makedirs(barcode_path, exist_ok=True) # Create directory if it doesn't exist

        full_file_path = os.path.join(barcode_path, output_filename)

        # Generate the barcode image and save it to the file path
        barcode_obj.save(full_file_path, options=writer_options)

        # Return the path relative to MEDIA_ROOT for potential storage or response
        relative_path = os.path.join(barcode_directory, output_filename).replace("\\", "/") # Ensure forward slashes for URLs
        return relative_path

    except Exception as e:
        print(f"Error generating barcode image for string '{barcode_string}': {e}")
        return None

# Optional: Function to generate barcode data in memory (for returning Base64 via API or displaying in admin without saving)
def generate_barcode_image_bytes_from_string(barcode_string, barcode_type='code128'):
    """
    Generates a barcode image from a given barcode string and returns it as bytes.

    Args:
        barcode_string (str): The barcode code to encode (e.g., a UUID).
        barcode_type (str): The type of barcode (e.g., 'code128', 'ean13'). Defaults to 'code128'.

    Returns:
        bytes: The image data, or None if generation fails.
    """
    try:
        barcode_class = barcode.get_barcode_class(barcode_type)
        if not barcode_class:
            print(f"Unsupported barcode type: {barcode_type}")
            return None

        writer_options = {
            "module_width": 0.2,
            "module_height": 15,
            "quiet_zone": 1,
            "font_size": 10,
            "text_distance": 5,
            "write_text": True,
        }
        barcode_obj = barcode_class(barcode_string, writer=ImageWriter())

        # Use BytesIO to capture the image in memory
        temp_buffer = BytesIO()
        barcode_obj.write(temp_buffer, options=writer_options)

        # Get the image bytes
        image_bytes = temp_buffer.getvalue()
        temp_buffer.close()

        return image_bytes

    except Exception as e:
        print(f"Error generating barcode image bytes for string '{barcode_string}': {e}")
        return None
