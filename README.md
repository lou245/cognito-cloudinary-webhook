# cognito-viloud-webhook

Cognito → Cloudinary webhook uploader. Receives webhook notifications from Cognito forms, downloads temporary files, and streams them to Cloudinary for video hosting.

## Features

- Receives form submissions from Cognito with file uploads
- Extracts video URLs from Cognito payload
- Streams downloads directly to Cloudinary (no local disk storage)
- Secure webhook validation with optional token authentication
- Returns Cloudinary public IDs for embed integration

## Setup

### Prerequisites

- Python 3.9+
- Cloudinary account
- Render or similar hosting (for environment variables)

### Local Development

1. **Clone the repository:**
   ```bash
   git clone https://github.com/lou245/cognito-viloud-webhook.git
   cd cognito-viloud-webhook
   ```

2. **Create virtual environment:**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables:**
   ```bash
   cp .env.example .env
   # Edit .env with your actual credentials
   ```

5. **Run the application:**
   ```bash
   python webhook_receiver.py
   ```

## Environment Variables

Create a `.env` file in the root directory or set these in your hosting platform:

| Variable | Required | Description |
|----------|----------|-------------|
| `CLOUDINARY_CLOUD_NAME` | Yes | Your Cloudinary cloud name |
| `CLOUDINARY_API_KEY` | Yes | Your Cloudinary API key |
| `CLOUDINARY_API_SECRET` | Yes | Your Cloudinary API secret |
| `WEBHOOK_SECRET` | No | Optional token for webhook verification |
| `PORT` | No | Server port (default: 5000) |

### Getting Cloudinary Credentials

1. Sign up at [cloudinary.com](https://cloudinary.com/)
2. Go to Dashboard → Settings → API Keys
3. Copy your Cloud Name, API Key, and API Secret

## Usage

### Webhook Endpoint

**POST** `/cognito-webhook?token=YOUR_WEBHOOK_SECRET`

The webhook expects a POST request with form data in JSON format.

#### Optional Query Parameter
- `token` - Webhook secret token (if `WEBHOOK_SECRET` is configured, this is required)

#### Expected Payload
The webhook searches for a video URL in the Cognito form data, looking for common field names:
- `Fields.UploadYourVideoSketchHERE` → `Url`, `UrlFull`, `UrlFullSecure`, `fileUrl`, `url`
- Recursively searches all nested objects and arrays

#### Response Examples

**Success (200):**
```json
{
  "status": "ok",
  "cloudinary": {
    "public_id": "video_abc123",
    "secure_url": "https://res.cloudinary.com/...",
    "url": "http://res.cloudinary.com/...",
    "format": "mp4"
  }
}
```

**Error - No file URL (400):**
```json
{
  "error": "no_file_url"
}
```

**Error - Network issue (500):**
```json
{
  "error": "network",
  "message": "Connection timeout"
}
```

## Embedding Videos

Use the `public_id` from the response to embed videos in your webpage:

```html
<iframe
  src="https://player.cloudinary.com/embed/?cloud_name=[CLOUD_NAME]&public_id=[PUBLIC_ID]"
  width="640" height="360" frameborder="0" allowfullscreen>
</iframe>
```

Example:
```html
<iframe
  src="https://player.cloudinary.com/embed/?cloud_name=demo&public_id=video_abc123"
  width="640" height="360" frameborder="0" allowfullscreen>
</iframe>
```

## Deployment

### Render

1. **Connect your GitHub repository** to Render
2. **Set Environment Variables** in Render dashboard:
   - Add all variables from `.env.example`
3. **Configure Build & Start Commands:**
   - Build: `pip install -r requirements.txt`
   - Start: `gunicorn webhook_receiver:app`
4. **Deploy** - Your webhook URL will be provided by Render

### Other Platforms

For Heroku, AWS, or similar:
1. Set environment variables in your platform's dashboard
2. Ensure `runtime.txt` specifies Python version
3. Use `gunicorn webhook_receiver:app` as start command

## Project Structure

```
.
├── webhook_receiver.py   # Main Flask application
├── config.py             # Configuration management
├── requirements.txt      # Python dependencies
├── runtime.txt           # Python version specification
├── .env.example          # Example environment variables
└── README.md             # This file
```

## Troubleshooting

### "No file URL found in payload"
- Check that Cognito is sending form data correctly
- Verify the field name matches expected structure
- Review raw payload in logs for debugging

### Cloudinary upload fails
- Verify `CLOUDINARY_API_KEY` and `CLOUDINARY_API_SECRET` are correct
- Check that your Cloudinary account has video upload enabled
- Ensure the temporary URL from Cognito is accessible

### "Unauthorized webhook call"
- If using `WEBHOOK_SECRET`, ensure `token` query parameter is included
- Verify the token matches your `WEBHOOK_SECRET` environment variable

## License

MIT
