import os
import logging
import urllib.parse
from flask import Flask, request, jsonify, abort
from flask_cors import CORS
import requests
import cloudinary
import cloudinary.uploader
import cloudinary.api
from datetime import datetime

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": ["https://www.itsalittlesketchy.com", "https://itsalittlesketchy.com"]}})
logging.basicConfig(level=logging.INFO)

# Cloudinary config (set these in Render env vars)
cloudinary.config(
    cloud_name=os.environ.get("CLOUDINARY_CLOUD_NAME"),
    api_key=os.environ.get("CLOUDINARY_API_KEY"),
    api_secret=os.environ.get("CLOUDINARY_API_SECRET")
)

WEBHOOK_SECRET = os.environ.get("WEBHOOK_SECRET")  # optional

# In-memory storage for contestant metadata (replace with database in production)
contestant_videos = {}

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

def extract_contestant_info(payload):
    """Extract contestant name and video title from Cognito form data"""
    contestant_name = "Unknown Contestant"
    video_title = "Untitled Video"
    
    if payload and isinstance(payload, dict):
        fields = payload.get("Fields", {})
        if isinstance(fields, dict):
            # Try multiple field name variations
            contestant_name = (fields.get("ContestantName") or 
                             fields.get("Contestant_Name") or 
                             fields.get("Name") or 
                             fields.get("Full Name") or 
                             "Unknown Contestant")
            video_title = (fields.get("VideoTitle") or 
                          fields.get("Video_Title") or 
                          fields.get("Title") or 
                          "Untitled Video")
    
    return contestant_name, video_title

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

        # Extract contestant info from payload
        contestant_name, video_title = extract_contestant_info(payload)
        logging.info("Contestant: %s, Video: %s", contestant_name, video_title)

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
            tags=[contestant_name.lower().replace(" ", "_")],
            context={"contestant": contestant_name, "title": video_title}
        )
        
        public_id = upload_result.get("public_id")
        logging.info("Cloudinary upload successful: %s", public_id)
        
        # Store video metadata
        contestant_videos[public_id] = {
            "contestantName": contestant_name,
            "videoTitle": video_title,
            "publicId": public_id,
            "uploadedAt": datetime.utcnow().isoformat(),
            "cloudinaryData": upload_result
        }

        return jsonify({
            "status": "ok",
            "public_id": public_id,
            "contestant": contestant_name,
            "title": video_title,
            "cloudinary": upload_result
        }), 200

    except requests.exceptions.RequestException as e:
        logging.exception("Network error during download/upload")
        return jsonify({"error": "network", "message": str(e)}), 500
    except Exception as e:
        logging.exception("Unexpected error")
        return jsonify({"error": "unexpected", "message": str(e)}), 500

@app.route("/api/videos", methods=["GET"])
def get_videos():
    """Get all uploaded videos with contestant metadata"""
    try:
        videos = list(contestant_videos.values())
        return jsonify({
            "videos": videos,
            "count": len(videos)
        }), 200
    except Exception as e:
        logging.exception("Error fetching videos")
        return jsonify({"error": "failed_to_fetch", "message": str(e)}), 500

@app.route("/api/videos/<public_id>", methods=["GET"])
def get_video(public_id):
    """Get a specific video by public_id"""
    try:
        if public_id not in contestant_videos:
            return jsonify({"error": "not_found"}), 404
        
        return jsonify(contestant_videos[public_id]), 200
    except Exception as e:
        logging.exception("Error fetching video")
        return jsonify({"error": "failed_to_fetch", "message": str(e)}), 500

@app.route("/api/health", methods=["GET"])
def health_check():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "cloudinary_configured": bool(os.environ.get("CLOUDINARY_CLOUD_NAME")),
        "total_videos": len(contestant_videos)
    }), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))