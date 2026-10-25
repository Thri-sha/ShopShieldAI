import os
import json
import logging
import time

import pillow_avif
from google import genai
from google.genai import types
from PIL import Image, ImageOps, UnidentifiedImageError


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Try these models in order. Availability depends on your Gemini API access.
GEMINI_MODELS = [
    "gemini-3.8-flash",
    "gemini-3.5-flash-lite",
]


def analyze_product_image(image_path):
    """
    Identify whether an uploaded image appears to contain
    a physical shopping product.

    This function identifies product categories only.
    It does not verify authenticity or seller trustworthiness.
    """

    api_key = os.getenv("GEMINI_API_KEY")

    if not api_key:
        logger.error("GEMINI_API_KEY is not configured.")

        return {
            "is_product": None,
            "category": "Unknown",
            "confidence": 0,
            "status": "AI_ERROR",
            "message": "The AI service is not configured. Please try again later."
        }

    try:
        # Open and normalize the image, including AVIF and EXIF orientation.
        with Image.open(image_path) as original:
            original = ImageOps.exif_transpose(original)
            original.load()
            image = original.convert("RGB")

        client = genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(timeout=45000)
        )

        prompt = """
        You are ShopShieldAI, a shopping product image classifier.

        Identify the MAIN physical product visible in this image.

        Examples of products:
        - Footwear: sandals, slippers, shoes, boots
        - Clothing: shirts, trousers, dresses
        - Bags: handbags, backpacks, wallets
        - Electronics: phones, laptops, headphones
        - Accessories: watches, jewelry, belts
        - Home products: furniture, kitchenware, decorations
        - Beauty products, toys and other retail goods

        Background objects such as plants, walls and furniture
        should not prevent you from identifying the main product.

        A tree, landscape, animal or ordinary portrait without
        a clearly identifiable shopping product is not a product image.

        Return only a JSON object with these fields:
        {
          "is_product": true,
          "category": "Footwear",
          "confidence": 0.95,
          "message": "A pair of sandals is visible."
        }

        Requirements:
        - is_product must be true, false, or null.
        - category should be specific, such as Footwear or Electronics.
        - confidence must be a number from 0 to 1.
        - message must briefly explain the result.
        - Use null if the image is genuinely unclear.
        - Judge the visible subject, not whether the image is attractive.
        - Do not claim that the item is genuine or safe to purchase.
        """

        response = None
        last_error = None

        # Try a second model if the first one is temporarily unavailable.
        for model_name in GEMINI_MODELS:
            for attempt in range(2):
                try:
                    logger.info(
                        "Analyzing product image with %s (attempt %s)",
                        model_name,
                        attempt + 1
                    )

                    response = client.models.generate_content(
                        model=model_name,
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

                    if not response.text:
                        raise ValueError("Gemini returned an empty response.")

                    # A valid response was received.
                    break

                except Exception as exc:
                    last_error = exc
                    response = None

                    logger.warning(
                        "Gemini model %s failed: %s: %s",
                        model_name,
                        type(exc).__name__,
                        str(exc)
                    )

                    error_text = str(exc).lower()
                    retryable = (
                        "503" in error_text
                        or "429" in error_text
                        or "500" in error_text
                        or "502" in error_text
                        or "504" in error_text
                        or "unavailable" in error_text
                        or "resource_exhausted" in error_text
                        or "deadline" in error_text
                        or "timeout" in error_text
                    )

                    if attempt == 0 and retryable:
                        time.sleep(1)
                        continue

                    # Don't repeatedly retry an invalid key or model.
                    break

            if response is not None and response.text:
                logger.info("Image analysis succeeded using %s", model_name)
                break

        if response is None or not response.text:
            raise RuntimeError(
                "All configured Gemini models failed. "
                f"Last error: {last_error}"
            )

        result = json.loads(response.text)

        is_product = result.get("is_product")
        category = str(result.get("category") or "Unknown")
        confidence = float(result.get("confidence", 0))
        message = str(result.get("message") or "")

        if is_product not in (True, False, None):
            raise ValueError("Invalid product classification returned by AI.")

        if not 0 <= confidence <= 1:
            raise ValueError("Invalid confidence score returned by AI.")

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
        logger.exception("Uploaded file is not a readable image.")

        return {
            "is_product": None,
            "category": "Unknown",
            "confidence": 0,
            "status": "AI_ERROR",
            "message": "The uploaded image could not be read."
        }

    except Exception as exc:
        logger.exception(
            "Product image analysis failed: %s: %s",
            type(exc).__name__,
            str(exc)
        )

        return {
            "is_product": None,
            "category": "Unknown",
            "confidence": 0,
            "status": "AI_ERROR",
            "message": (
                "AI image analysis is temporarily unavailable. "
                "Please try again later."
            )
        }