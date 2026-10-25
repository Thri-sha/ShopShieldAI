import os
import uuid
import logging
from urllib.parse import urlparse

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    flash,
)
from werkzeug.utils import secure_filename
from PIL import Image, UnidentifiedImageError
import pillow_avif

from utils.website_detector import analyze_website
from utils.ai_image_detector import analyze_product_image


# ==================================================
# APPLICATION CONFIGURATION
# ==================================================

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

UPLOAD_FOLDER = os.path.join(
    BASE_DIR,
    "static",
    "uploads",
)

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app = Flask(__name__)

app.secret_key = os.environ.get(
    "SHIELDSHOP_SECRET_KEY",
    "change-this-development-secret",
)

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 12 * 1024 * 1024

logging.basicConfig(level=logging.INFO)

# Supported image extensions
ALLOWED_IMAGE_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".bmp",
    ".gif",
    ".webp",
    ".tif",
    ".tiff",
    ".ico",
    ".jfif",
    ".dib",
    ".avif",
}

# Formats that Pillow can potentially decode after plugin registration.
# Actual support depends on the installed Pillow plugins.
ALLOWED_IMAGE_FORMATS = {
    "JPEG",
    "PNG",
    "BMP",
    "GIF",
    "WEBP",
    "TIFF",
    "ICO",
    "AVIF",
}


# ==================================================
# HELPER FUNCTIONS
# ==================================================

def validate_image_extension(filename):
    """Check the uploaded filename's extension."""

    extension = os.path.splitext(filename)[1].lower()

    return extension in ALLOWED_IMAGE_EXTENSIONS


def valid_web_address(value):
    """Perform basic validation of a website URL."""

    value = (value or "").strip()

    if not value:
        return None, "Please enter a website URL."

    if any(character.isspace() for character in value):
        return None, "The website URL cannot contain spaces."

    if "://" not in value:
        value = "https://" + value

    parsed = urlparse(value)

    if (
        parsed.scheme not in ("http", "https")
        or not parsed.hostname
        or "." not in parsed.hostname
    ):
        return None, "Please enter a valid website address."

    return value, None


def remove_file(path):
    """Safely remove a temporary or invalid file."""

    try:
        if path and os.path.isfile(path):
            os.remove(path)
    except OSError:
        app.logger.warning(
            "Could not remove file: %s",
            path,
        )


def prepare_image_for_ai(original_path):
    """
    Create a temporary JPEG for AI analysis.

    This allows AVIF and other supported image formats to be
    converted to JPEG when the AI detector does not handle
    the original format directly.

    Returns:
        (ai_image_path, temporary_path)

    The caller is responsible for removing temporary_path.
    """

    with Image.open(original_path) as image:
        image.seek(0)

        # Convert palette, grayscale, and transparent images
        # to a format suitable for JPEG.
        converted = image.convert("RGB")

        temporary_path = os.path.join(
            UPLOAD_FOLDER,
            f"{uuid.uuid4().hex}_ai.jpg",
        )

        converted.save(
            temporary_path,
            format="JPEG",
            quality=90,
        )

    return temporary_path, temporary_path


# ==================================================
# HOME PAGE
# ==================================================

@app.route("/")
def index():
    return render_template("index.html")


# ==================================================
# WEBSITE CHECKER
# ==================================================

@app.route("/check-website", methods=["POST"])
def check_website():

    url, error = valid_web_address(
        request.form.get("url")
    )

    if error:
        flash(error, "error")

        return redirect(
            url_for("index") + "#website-checker"
        )

    try:
        result = analyze_website(url)

        return render_template(
            "website_result.html",
            url=url,
            result=result,
        )

    except Exception:
        app.logger.exception(
            "Website analysis failed"
        )

        flash(
            "Website analysis failed. Please check "
            "your connection and try again.",
            "error",
        )

        return redirect(
            url_for("index") + "#website-checker"
        )


# ==================================================
# IMAGE CHECKER
# ==================================================

@app.route("/check-image", methods=["GET", "POST"])
def check_image():

    # Allow users to open the route directly.
    if request.method == "GET":
        return redirect(
            url_for("index") + "#image-checker"
        )

    uploaded = request.files.get("image")

    if not uploaded or not uploaded.filename:
        flash(
            "Please select an image before checking.",
            "error",
        )

        return redirect(
            url_for("index") + "#image-checker"
        )

    original_name = (
        secure_filename(uploaded.filename)
        or "uploaded_image"
    )

    # Check the filename extension.
    extension = os.path.splitext(
        original_name
    )[1].lower()

    if not validate_image_extension(original_name):
        flash(
            "Unsupported image type. Please upload "
            "JPG, JPEG, PNG, WEBP, BMP, GIF, TIFF, "
            "AVIF, or another supported image format.",
            "error",
        )

        return redirect(
            url_for("index") + "#image-checker"
        )

    # Use a generated filename rather than trusting the upload.
    saved_name = f"{uuid.uuid4().hex}{extension}"

    saved_path = os.path.join(
        app.config["UPLOAD_FOLDER"],
        saved_name,
    )

    temporary_ai_path = None

    try:
        # ------------------------------------------
        # STEP 1: SAVE AND VALIDATE IMAGE
        # ------------------------------------------

        uploaded.save(saved_path)

        file_size = os.path.getsize(saved_path)

        if file_size == 0:
            raise ValueError("The uploaded file is empty.")

        with Image.open(saved_path) as image:

            image_format = (image.format or "").upper()
            width, height = image.size
            mode = image.mode
            frame_count = getattr(image, "n_frames", 1)

            # Validate the file's real format instead of
            # relying only on its filename extension.
            if image_format not in ALLOWED_IMAGE_FORMATS:
                raise ValueError(
                    "The actual image format is not supported."
                )

            if width <= 0 or height <= 0:
                raise ValueError(
                    "Invalid image dimensions."
                )

            # Verify that the image data is readable.
            image.verify()

        # ------------------------------------------
        # STEP 2: PREPARE IMAGE FOR GEMINI
        # ------------------------------------------

        try:
            temporary_ai_path, _ = prepare_image_for_ai(
                saved_path
            )

        except Exception:
            app.logger.exception(
                "Could not prepare image for AI"
            )

            raise ValueError(
                "The image could not be converted for AI analysis."
            )

        # ------------------------------------------
        # STEP 3: ANALYZE IMAGE USING GEMINI AI
        # ------------------------------------------

        try:
            ai_result = analyze_product_image(
                temporary_ai_path
            )

            if not isinstance(ai_result, dict):
                raise ValueError(
                    "The AI detector returned an invalid result."
                )

        except Exception:
            app.logger.exception(
                "AI image analysis failed"
            )

            ai_result = {
                "is_product": False,
                "category": "Unknown",
                "confidence": 0,
                "status": "AI_ERROR",
                "message": (
                    "The image was uploaded successfully, "
                    "but AI analysis failed. Check your "
                    "Gemini API key, model availability, "
                    "internet connection, and terminal errors."
                ),
            }

        # ------------------------------------------
        # STEP 4: INTERPRET AI RESULT
        # ------------------------------------------

        try:
            confidence = float(
                ai_result.get("confidence", 0)
            )
        except (TypeError, ValueError):
            confidence = 0.0

        # Support either 0-1 or 0-100 confidence values.
        if confidence > 1:
            confidence /= 100.0

        confidence = max(
            0.0,
            min(1.0, confidence),
        )

        status = ai_result.get(
            "status",
            "UNCERTAIN",
        )

        is_product = (
            ai_result.get("is_product") is True
            and status == "PRODUCT_DETECTED"
            and confidence >= 0.80
        )

        if is_product:
            label = "Shopping Product Detected"

        elif status == "AI_ERROR":
            label = "AI Analysis Failed"

        elif status == "NOT_A_PRODUCT":
            label = "Not a Shopping Product"

        else:
            label = "Product Not Confirmed"

        # ------------------------------------------
        # STEP 5: PREPARE RESULT PAGE
        # ------------------------------------------

        result = {
            "status": status,
            "label": label,
            "category": ai_result.get(
                "category",
                "Unknown",
            ),
            "confidence": round(
                confidence * 100,
                1,
            ),
            "message": ai_result.get(
                "message",
                "The image could not be identified confidently.",
            ),
            "format": image_format,
            "width": width,
            "height": height,
            "mode": mode,
            "frames": frame_count,
            "size_kb": round(
                file_size / 1024,
                1,
            ),
            "image_url": url_for(
                "static",
                filename=f"uploads/{saved_name}",
            ),
            "notes": [
                "AI checks whether the image appears to show a shopping product.",
                "Image classification is an estimate, not a guarantee.",
                "A product image alone cannot prove authenticity or quality.",
                "Review the seller, payment method, return policy, and independent reviews before purchasing.",
            ],
        }

        return render_template(
            "image_result.html",
            result=result,
            original_name=original_name,
        )

    except (
        UnidentifiedImageError,
        OSError,
        ValueError,
        Image.DecompressionBombError,
    ) as error:

        app.logger.warning(
            "Image validation failed: %s",
            error,
        )

        remove_file(saved_path)

        flash(
            "The image could not be read or validated. "
            "Please try another image or convert it to "
            "JPG or PNG.",
            "error",
        )

        return redirect(
            url_for("index") + "#image-checker"
        )

    finally:
        # Remove the temporary JPEG used for AI analysis.
        remove_file(temporary_ai_path)


# ==================================================
# FILE SIZE ERROR HANDLER
# ==================================================

@app.errorhandler(413)
def too_large(_error):

    flash(
        "The image is too large. Please upload an image "
        "smaller than 12 MB.",
        "error",
    )

    return redirect(
        url_for("index") + "#image-checker"
    )


# ==================================================
# START APPLICATION
# ==================================================

if __name__ == "__main__":

    print("ShopShieldAI is starting...")
    print("Open http://127.0.0.1:5000 in your browser")

    app.run(
        host="127.0.0.1",
        port=5000,
        debug=True,
    )
