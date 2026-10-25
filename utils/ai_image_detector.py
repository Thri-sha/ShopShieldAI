import os
import json
import logging

import pillow_avif
from google import genai
from google.genai import types
from PIL import Image, ImageOps, UnidentifiedImageError


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def analyze_product_image(image_path):
    """
    Analyze an uploaded image and determine whether it shows
    a physical product commonly sold through shopping websites.
    """

    api_key = os.getenv("GEMINI_API_KEY")

    if not api_key:
        logger.error("GEMINI_API_KEY is not configured.")

        return {
            "is_product": None,
            "category": "Unknown",
            "confidence": 0,
            "status": "AI_ERROR",
            "message": "AI service is not configured correctly."
        }

    try:
        # Open and normalize the uploaded image.
        with Image.open(image_path) as original:
            original = ImageOps.exif_transpose(original)
            original.load()
            image = original.convert("RGB")

        # Create the Gemini client.
        client = genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(timeout=60000)
        )

        prompt = """
        You are a visual product-image classifier for ShopShieldAI.

        Examine the uploaded image and identify its MAIN SUBJECT.

        PRODUCT examples:
        - Sandals, slippers, shoes and boots
        - Shirts, trousers, dresses and other clothing
        - Handbags, backpacks and wallets
        - Mobile phones, laptops and electronics
        - Watches, jewelry and accessories
        - Furniture, kitchen items and home products
        - Cosmetics, toys and other physical retail products

        NOT A PRODUCT:
        - Trees, landscapes and scenery
        - Animals shown as the main subject
        - Ordinary portraits without a clear product focus
        - Images that do not show a recognizable physical product

        If the image contains a product alongside decorations,
        plants or a background, classify the main product correctly.

        A product image does not prove that the item is genuine,
        high quality or safe to purchase.

        Return a JSON object with exactly these fields:
        {
          "is_product": true,
          "category": "Footwear",
          "confidence": 0.95,
          "message": "A pair of sandals was identified."
        }

        Rules:
        - is_product must be true, false, or null.
        - category should be a specific category when possible.
        - confidence must be a number from 0 to 1.
        - message should briefly explain the visual finding.
        - Use null for is_product if the image is genuinely unclear.
        - Do not classify an image as a product merely because
          it has good image quality.
        """

        response = client.models.generate_content(
            model="gemini-3.7-flash",
            contents=[prompt, image],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema={
                    "type": "OBJECT",
                    "properties": {
                        "is_product": {
                            "type": "BOOLEAN",
                            "nullable": True
                        },
                        "category": {
                            "type": "STRING"
                        },
                        "confidence": {
                            "type": "NUMBER"
                        },
                        "message": {
                            "type": "STRING"
                        }
                    },
                    "required": [
                        "is_product",
                        "category",
                        "confidence",
                        "message"
                    ]
                },
                temperature=0.1
            )
        )

        response_text = response.text

        if not response_text:
            raise ValueError("Gemini returned an empty response.")

        result = json.loads(response_text)

        is_product = result.get("is_product")
        category = str(result.get("category") or "Unknown")
        confidence = float(result.get("confidence", 0))
        message = str(result.get("message") or "")

        if is_product not in (True, False, None):
            raise ValueError("Invalid product classification.")

        if not 0 <= confidence <= 1:
            raise ValueError("Invalid confidence score.")

        if is_product is True:
            status = "PRODUCT_DETECTED"
            message = message or (
                f"A potential shopping product was identified: {category}."
            )

        elif is_product is False:
            status = "NOT_A_PRODUCT"
            message = message or (
                "The image does not appear to show a shopping product."
            )

        else:
            status = "UNCERTAIN"
            message = message or (
                "The main subject could not be identified confidently."
            )

        logger.info(
            "Image analysis completed: status=%s, category=%s, confidence=%.2f",
            status,
            category,
            confidence
        )

        return {
            "is_product": is_product,
            "category": category,
            "confidence": confidence,
            "status": status,
            "message": message
        }

    except UnidentifiedImageError:
        logger.exception("The uploaded file could not be decoded as an image.")

        return {
            "is_product": None,
            "category": "Unknown",
            "confidence": 0,
            "status": "AI_ERROR",
            "message": "The uploaded image could not be read."
        }

    except Exception as e:
        # Keep the actual exception in Render logs for troubleshooting.
        logger.exception(
            "Gemini image analysis failed: %s: %s",
            type(e).__name__,
            str(e)
        )

        return {
            "is_product": None,
            "category": "Unknown",
            "confidence": 0,
            "status": "AI_ERROR",
            "message": (
                "Image analysis is temporarily unavailable. "
                "Please try again later."
            )
        }