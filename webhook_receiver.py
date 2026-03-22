import os
import logging
import urllib.parse
from flask import Flask, request, jsonify, abort
import requests
import cloudinary
import cloudinary.uploader
import cloudinary.api

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

# Cloudinary config (set these in Render env vars)
cloudinary.config(
    cloud_name=os.environ.get("CLOUDINARY_CLOUD_NAME"),
    api_key=os.environ.get("CLOUDINARY_API_KEY"),
    api_secret=os.environ.get("CLOUDINARY_API_SECRET")
)

WEBHOOK_SECRET = os.environ.get("WEBHOOK_SECRET")  # optional

def find_first_url(obj):
    if not obj: return None
    if isinstance(obj, str):
        if obj.startswith("http://") or obj.startswith("https://"):
            return obj
        return None
    if isinstance(obj, list):
        for item in obj:
            r = find_first_url(item)
            if r: return r
    if isinstance(obj, dict):
        fields = obj.get("Fields")
        if isinstance(fields, dict):
            upload = fields.get("UploadYourVideoSketchHERE")
            if isinstance(upload, dict):
                for key in ("Url", "UrlFull", "UrlFullSecure", "fileUrl", "url"):
                    if upload.get(key): return upload.get(key)
        r = find_first_url(fields)
        if r: return r
        for v in obj.values():
            r = find_first_url(v)
            if r: return r
    return None

@app.route("/cognito-webhook", methods=["POST"])
def cognito_webhook():
    token = request.args.get("token")
    if WEBHOOK_SECRET and token != WEBHOOK_SECRET:
        logging.warning("Unauthorized webhook call (bad token)")
        abort(403)

    try:
        raw_text = request.get_data(as_text=True)
        logging.info("Webhook raw body received")
        payload = None
        try:
            payload = request.get_json(force=True)
        except Exception:
            logging.warning("Payload not JSON-parsable")

        temp_url = find_first_url(payload) if payload else None
        logging.info("Extracted temp file URL: %s", temp_url)
        if not temp_url:
            logging.error("No file URL found in payload. Raw payload logged.")
            logging.debug(raw_text)
            return jsonify({"error": "no_file_url"}), 400

        # Stream download from Cognito temp URL
        logging.info("Starting download from Cognito temp URL")
        r = requests.get(temp_url, stream=True, timeout=60)
        r.raise_for_status()
        filename = os.path.basename(urllib.parse.urlparse(temp_url).path) or "upload.mp4"

        # Upload to Cloudinary as video
        logging.info("Uploading to Cloudinary...")
        upload_result = cloudinary.uploader.upload(
            r.raw,
            resource_type="video",
            filename=filename,
            # optional: set a public_id or folder if you want a predictable URL
            # public_id="videos/" + filename.split(".")[0]
        )
        logging.info("Cloudinary upload successful: %s", upload_result.get("public_id"))

        # Return success
        return jsonify({"status": "ok", "cloudinary": upload_result}), 200

    except requests.exceptions.RequestException as e:
        logging.exception("Network error during download/upload")
        return jsonify({"error": "network", "message": str(e)}), 500
    except Exception as e:
        logging.exception("Unexpected error")
        return jsonify({"error": "unexpected", "message": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))

On your webpage, embed the player like this (replace [CLOUD_NAME] and [PUBLIC_ID]):
<iframe
  src="https://player.cloudinary.com/embed/?cloud_name=[CLOUD_NAME]&public_id=[PUBLIC_ID]"
  width="640" height="360" frameborder="0" allowfullscreen></iframe>

  
   
