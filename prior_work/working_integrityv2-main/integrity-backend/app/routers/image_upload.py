"""
Simple image upload/serve endpoint.
Stores graph images in MongoDB so they survive page reloads.
"""

import base64
import uuid
import logging
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/images", tags=["images"])

# Set by main.py during startup
images_collection = None


def set_images_collection(col):
    global images_collection
    images_collection = col


class ImageUploadRequest(BaseModel):
    data_url: str  # e.g. "data:image/png;base64,iVBOR..."


@router.post("/upload")
async def upload_image(req: ImageUploadRequest):
    """Upload a base64 data-URL image and return a permanent serving URL."""
    if images_collection is None:
        raise HTTPException(status_code=503, detail="Image storage not initialized")

    try:
        # Parse data URL
        header, encoded = req.data_url.split(",", 1)
        content_type = header.split(":")[1].split(";")[0]
        image_bytes = base64.b64decode(encoded)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid data URL format")

    image_id = uuid.uuid4().hex

    await images_collection.insert_one({
        "_id": image_id,
        "data": image_bytes,
        "content_type": content_type,
        "size": len(image_bytes),
        "created_at": datetime.now(timezone.utc),
    })

    return {"image_id": image_id, "url": f"/api/images/{image_id}"}


@router.get("/{image_id}")
async def serve_image(image_id: str):
    """Serve an uploaded image by ID."""
    if images_collection is None:
        raise HTTPException(status_code=503, detail="Image storage not initialized")

    doc = await images_collection.find_one({"_id": image_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Image not found")

    return Response(
        content=doc["data"],
        media_type=doc.get("content_type", "image/png"),
        headers={"Cache-Control": "public, max-age=31536000, immutable"},
    )
