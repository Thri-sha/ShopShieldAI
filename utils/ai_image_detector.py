import os
import json
import pillow_avif
from google import genai
from PIL import Image


def analyze_product_image(image_path):

    api_key = os.getenv("GEMINI_API_KEY")

    if not api_key:
        return {
            "is_product": False,
            "category": "Unknown",
            "confidence": 0,
            "status": "AI_ERROR",
            "message": "Gemini API key is missing. Please configure it."
        }

    try:
        client = genai.Client(api_key=api_key)

        with Image.open(image_path) as image:
            image = image.convert("RGB")

            response = client.models.generate_content(
                model="gemini-3.8-flash",
                contents=[
                    """
                    Analyze the uploaded image for a shopping website.

                    Decide whether the MAIN SUBJECT is a recognizable
                    physical product commonly sold online.

                    Examples of products:
                    shirts, trousers, shoes, bags, phones, laptops,
                    watches, furniture and household products.

                    Examples that are not shopping product images:
                    trees, landscapes, ordinary portraits, pets and
                    unrelated scenery.

                    A person wearing clothes is not automatically
                    a clothing product.

                    If uncertain, return UNCERTAIN.

                    Return only valid JSON in this format:
                    {
                      "is_product": true,
                      "category": "Clothing",
                      "confidence": 0.90,
                      "status": "PRODUCT_DETECTED",
                      "message": "A clothing product was identified."
                    }

                    is_product must be true, false, or null.
                    confidence must be between 0 and 1.
                    status must be PRODUCT_DETECTED,
                    NOT_A_PRODUCT, or UNCERTAIN.
                    """,
                    image
                ]
            )

        text = (response.text or "").strip()

        # Remove optional Markdown formatting.
        if text.startswith("```"):
            lines = text.splitlines()
            if lines and lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            text = "\n".join(lines).strip()

        result = json.loads(text)

        is_product = result.get("is_product")
        confidence = float(result.get("confidence", 0))
        status = result.get("status", "UNCERTAIN")

        if not 0 <= confidence <= 1:
            raise ValueError("AI returned an invalid confidence score.")

        if (
            is_product is True
            and status == "PRODUCT_DETECTED"
            and confidence >= 0.80
        ):
            return {
                "is_product": True,
                "category": result.get("category", "Unknown"),
                "confidence": confidence,
                "status": "PRODUCT_DETECTED",
                "message": result.get(
                    "message",
                    "A potential shopping product was detected."
                )
            }

        if is_product is False and status == "NOT_A_PRODUCT":
            return {
                "is_product": False,
                "category": result.get("category", "Unknown"),
                "confidence": confidence,
                "status": "NOT_A_PRODUCT",
                "message": "No shopping product was identified."
            }

        return {
            "is_product": False,
            "category": result.get("category", "Unknown"),
            "confidence": confidence,
            "status": "UNCERTAIN",
            "message": (
                "The product could not be identified confidently. "
                "Please upload a clearer product image."
            )
        }

    except Exception as e:
        print("\n========== GEMINI AI ERROR ==========")
        print(type(e).__name__)
        print(str(e))
        print("====================================\n")

        return {
            "is_product": False,
            "category": "Unknown",
            "confidence": 0,
            "status": "AI_ERROR",
            "message": (
                "AI analysis failed. Check the VS Code terminal."
            )
        }