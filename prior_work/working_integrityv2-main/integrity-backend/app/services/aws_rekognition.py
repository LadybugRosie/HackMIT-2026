"""
AWS Rekognition Service for Face Verification
Provides face comparison and collection management using AWS Rekognition
"""
import os
import base64
import logging
from typing import Dict, Optional, Tuple
import boto3
from botocore.exceptions import ClientError, BotoCoreError
from PIL import Image
import io

logger = logging.getLogger(__name__)

# AWS Configuration
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
REKOGNITION_COLLECTION_ID = os.getenv("AWS_REKOGNITION_COLLECTION_ID", "integrity-faces")

# Initialize AWS Rekognition client
rekognition_client = None
AWS_AVAILABLE = False

def initialize_aws_rekognition():
    """Initialize AWS Rekognition client"""
    global rekognition_client, AWS_AVAILABLE
    
    if not AWS_ACCESS_KEY_ID or not AWS_SECRET_ACCESS_KEY:
        logger.warning("⚠️ AWS credentials not configured. Face verification via AWS will be disabled.")
        return False
    
    try:
        rekognition_client = boto3.client(
            'rekognition',
            aws_access_key_id=AWS_ACCESS_KEY_ID,
            aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
            region_name=AWS_REGION
        )
        
        # Test the connection by listing collections
        rekognition_client.list_collections()
        
        AWS_AVAILABLE = True
        logger.info(f"✅ AWS Rekognition initialized successfully (Region: {AWS_REGION})")
        
        # Try to create collection if it doesn't exist
        _ensure_collection_exists()
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Failed to initialize AWS Rekognition: {e}")
        AWS_AVAILABLE = False
        return False


def _ensure_collection_exists():
    """Ensure the face collection exists, create if not"""
    global rekognition_client
    
    if not rekognition_client:
        return False
    
    try:
        # Try to describe the collection
        rekognition_client.describe_collection(CollectionId=REKOGNITION_COLLECTION_ID)
        logger.info(f"✅ Face collection '{REKOGNITION_COLLECTION_ID}' exists")
        return True
        
    except ClientError as e:
        if e.response['Error']['Code'] == 'ResourceNotFoundException':
            # Collection doesn't exist, create it
            try:
                rekognition_client.create_collection(CollectionId=REKOGNITION_COLLECTION_ID)
                logger.info(f"✅ Created face collection '{REKOGNITION_COLLECTION_ID}'")
                return True
            except Exception as create_error:
                logger.error(f"❌ Failed to create collection: {create_error}")
                return False
        else:
            logger.error(f"❌ Error checking collection: {e}")
            return False


def decode_base64_image_bytes(base64_string: str) -> bytes:
    """
    Decode base64 image string to bytes for AWS Rekognition
    
    Args:
        base64_string: Base64 encoded image (with or without data URL prefix)
    
    Returns:
        bytes: Image bytes
    """
    # Remove data URL prefix if present
    if ',' in base64_string:
        base64_string = base64_string.split(',')[1]
    
    # Decode base64
    img_bytes = base64.b64decode(base64_string)
    
    return img_bytes


def validate_image(image_bytes: bytes) -> Tuple[bool, Optional[str]]:
    """
    Validate image format and size
    
    Args:
        image_bytes: Image bytes
    
    Returns:
        Tuple[bool, Optional[str]]: (is_valid, error_message)
    """
    try:
        # Check size (AWS Rekognition max: 5MB for comparison, 15MB for indexing)
        if len(image_bytes) > 5 * 1024 * 1024:
            return False, "Image too large. Maximum size is 5MB."
        
        # Validate it's a valid image
        img = Image.open(io.BytesIO(image_bytes))
        
        # Check format
        if img.format not in ['JPEG', 'PNG']:
            return False, f"Unsupported image format: {img.format}. Use JPEG or PNG."
        
        # Check dimensions (AWS Rekognition minimum: 80px in both dimensions)
        if img.width < 80 or img.height < 80:
            return False, "Image too small. Minimum dimensions are 80x80 pixels."
        
        return True, None
        
    except Exception as e:
        return False, f"Invalid image: {str(e)}"


def detect_faces(image_base64: str) -> Dict:
    """
    Detect faces in an image using AWS Rekognition
    
    Args:
        image_base64: Base64 encoded image
    
    Returns:
        dict: Detection results with face details
    """
    global rekognition_client
    
    if not AWS_AVAILABLE or not rekognition_client:
        return {
            "success": False,
            "error": "AWS Rekognition not available"
        }
    
    try:
        # Decode image
        image_bytes = decode_base64_image_bytes(image_base64)
        
        # Validate image
        is_valid, error_msg = validate_image(image_bytes)
        if not is_valid:
            return {
                "success": False,
                "error": error_msg
            }
        
        # Detect faces
        response = rekognition_client.detect_faces(
            Image={'Bytes': image_bytes},
            Attributes=['ALL']
        )
        
        face_details = response.get('FaceDetails', [])
        
        if len(face_details) == 0:
            return {
                "success": False,
                "error": "No face detected in image",
                "no_face": True
            }
        
        if len(face_details) > 1:
            return {
                "success": False,
                "error": "Multiple faces detected. Please ensure only one face is visible.",
                "multiple_faces": True,
                "face_count": len(face_details)
            }
        
        # Return face details
        face = face_details[0]
        
        return {
            "success": True,
            "face_detected": True,
            "confidence": face.get('Confidence'),
            "bounding_box": face.get('BoundingBox'),
            "age_range": face.get('AgeRange'),
            "gender": face.get('Gender'),
            "emotions": face.get('Emotions', []),
            "face_quality": face.get('Quality')
        }
        
    except ClientError as e:
        logger.error(f"AWS Rekognition ClientError: {e}")
        return {
            "success": False,
            "error": f"AWS Error: {e.response['Error']['Message']}"
        }
    except Exception as e:
        logger.error(f"Face detection error: {e}")
        return {
            "success": False,
            "error": str(e)
        }


def compare_faces(baseline_image_base64: str, current_image_base64: str, similarity_threshold: float = 90.0) -> Dict:
    """
    Compare two faces using AWS Rekognition
    
    Args:
        baseline_image_base64: Base64 encoded baseline (reference) image
        current_image_base64: Base64 encoded current image to compare
        similarity_threshold: Minimum similarity percentage (0-100) to consider a match
    
    Returns:
        dict: Comparison results
    """
    global rekognition_client
    
    if not AWS_AVAILABLE or not rekognition_client:
        return {
            "success": False,
            "error": "AWS Rekognition not available"
        }
    
    try:
        # Decode images
        baseline_bytes = decode_base64_image_bytes(baseline_image_base64)
        current_bytes = decode_base64_image_bytes(current_image_base64)
        
        # Validate both images
        for img_bytes, name in [(baseline_bytes, "baseline"), (current_bytes, "current")]:
            is_valid, error_msg = validate_image(img_bytes)
            if not is_valid:
                return {
                    "success": False,
                    "error": f"{name.capitalize()} image error: {error_msg}"
                }
        
        # Compare faces
        response = rekognition_client.compare_faces(
            SourceImage={'Bytes': baseline_bytes},
            TargetImage={'Bytes': current_bytes},
            SimilarityThreshold=similarity_threshold
        )
        
        face_matches = response.get('FaceMatches', [])
        unmatched_faces = response.get('UnmatchedFaces', [])
        
        # Check if faces were found
        if len(face_matches) == 0:
            # Check if no face was detected
            if len(unmatched_faces) == 0:
                return {
                    "success": False,
                    "verified": False,
                    "error": "No face detected in current image",
                    "no_face": True
                }
            else:
                # Face detected but doesn't match
                return {
                    "success": True,
                    "verified": False,
                    "similarity": 0.0,
                    "message": "Face does not match baseline"
                }
        
        # Get the best match
        best_match = face_matches[0]
        similarity = best_match['Similarity']
        
        result = {
            "success": True,
            "verified": True,
            "similarity": similarity,
            "confidence": best_match['Face'].get('Confidence', 0),
            "bounding_box": best_match['Face'].get('BoundingBox'),
            "threshold": similarity_threshold,
            "message": f"Face verified with {similarity:.1f}% similarity"
        }
        
        # --- Loophole #4 Fix: Extract liveness heuristic data ---
        # Run detect_faces on the current image to get pose, eyes, quality
        try:
            detect_response = rekognition_client.detect_faces(
                Image={'Bytes': current_bytes},
                Attributes=['ALL']
            )
            detect_faces_list = detect_response.get('FaceDetails', [])
            if detect_faces_list:
                face_detail = detect_faces_list[0]
                pose = face_detail.get('Pose', {})
                eyes_open = face_detail.get('EyesOpen', {})
                quality = face_detail.get('Quality', {})
                result["liveness_data"] = {
                    "pose_yaw": pose.get('Yaw', 0),
                    "pose_pitch": pose.get('Pitch', 0),
                    "pose_roll": pose.get('Roll', 0),
                    "eyes_open": eyes_open.get('Value', True),
                    "eyes_open_confidence": eyes_open.get('Confidence', 0),
                    "quality_sharpness": quality.get('Sharpness', 100),
                    "quality_brightness": quality.get('Brightness', 100)
                }
        except Exception as liveness_err:
            logger.warning(f"Liveness data extraction failed (non-fatal): {liveness_err}")
        
        return result
        
    except ClientError as e:
        error_code = e.response['Error']['Code']
        error_message = e.response['Error']['Message']
        
        logger.error(f"AWS Rekognition ClientError [{error_code}]: {error_message}")
        
        # Handle specific errors - most InvalidParameterException errors are due to no face/bad image
        if error_code == 'InvalidParameterException':
            return {
                "success": False,
                "verified": False,
                "error": "No face detected or image quality too low",
                "no_face": True
            }
        
        # Any other AWS error - treat as no face for safety
        return {
            "success": False,
            "verified": False,
            "error": f"AWS Error: {error_message}",
            "no_face": True
        }
        
    except Exception as e:
        logger.error(f"Face comparison error: {e}")
        return {
            "success": False,
            "verified": False,
            "error": str(e)
        }


def _sanitize_external_id(external_id: str) -> str:
    """
    Sanitize external ID to match AWS requirements.
    AWS ExternalImageId must match: [a-zA-Z0-9_.\-:]+
    """
    import re
    # Replace @ with _at_ and any other invalid chars with underscore
    sanitized = external_id.replace('@', '_at_').replace('+', '_plus_')
    # Remove any remaining invalid characters
    sanitized = re.sub(r'[^a-zA-Z0-9_.\-:]', '_', sanitized)
    return sanitized


def index_face(image_base64: str, external_image_id: str) -> Dict:
    """
    Index a face into the collection for future searches
    
    Args:
        image_base64: Base64 encoded image
        external_image_id: External ID to associate with this face (e.g., user email)
    
    Returns:
        dict: Indexing results with face_id
    """
    global rekognition_client
    
    if not AWS_AVAILABLE or not rekognition_client:
        return {
            "success": False,
            "error": "AWS Rekognition not available"
        }
    
    try:
        image_bytes = decode_base64_image_bytes(image_base64)
        
        # Validate image
        is_valid, error_msg = validate_image(image_bytes)
        if not is_valid:
            return {
                "success": False,
                "error": error_msg
            }
        
        # Sanitize external ID for AWS compatibility
        safe_external_id = _sanitize_external_id(external_image_id)
        
        # Index the face
        response = rekognition_client.index_faces(
            CollectionId=REKOGNITION_COLLECTION_ID,
            Image={'Bytes': image_bytes},
            ExternalImageId=safe_external_id,
            MaxFaces=1,
            QualityFilter='AUTO',
            DetectionAttributes=['ALL']
        )
        
        face_records = response.get('FaceRecords', [])
        
        if len(face_records) == 0:
            return {
                "success": False,
                "error": "No face detected or face quality too low",
                "no_face": True
            }
        
        face_record = face_records[0]
        face_id = face_record['Face']['FaceId']
        
        logger.info(f"✅ Indexed face for {external_image_id}: {face_id}")
        
        return {
            "success": True,
            "face_id": face_id,
            "image_id": face_record['Face']['ImageId'],
            "confidence": face_record['Face']['Confidence'],
            "bounding_box": face_record['Face']['BoundingBox']
        }
        
    except ClientError as e:
        logger.error(f"AWS Rekognition ClientError: {e}")
        return {
            "success": False,
            "error": f"AWS Error: {e.response['Error']['Message']}"
        }
    except Exception as e:
        logger.error(f"Face indexing error: {e}")
        return {
            "success": False,
            "error": str(e)
        }


def search_faces_by_image(image_base64: str, threshold: float = 90.0) -> Dict:
    """
    Search for matching faces in the collection
    
    Args:
        image_base64: Base64 encoded image to search
        threshold: Minimum similarity threshold (0-100)
    
    Returns:
        dict: Search results with matched faces
    """
    global rekognition_client
    
    if not AWS_AVAILABLE or not rekognition_client:
        return {
            "success": False,
            "error": "AWS Rekognition not available"
        }
    
    try:
        image_bytes = decode_base64_image_bytes(image_base64)
        
        is_valid, error_msg = validate_image(image_bytes)
        if not is_valid:
            return {
                "success": False,
                "error": error_msg
            }
        
        response = rekognition_client.search_faces_by_image(
            CollectionId=REKOGNITION_COLLECTION_ID,
            Image={'Bytes': image_bytes},
            FaceMatchThreshold=threshold,
            MaxFaces=5
        )
        
        face_matches = response.get('FaceMatches', [])
        
        if len(face_matches) == 0:
            return {
                "success": True,
                "matched": False,
                "matches": []
            }
        
        matches = []
        for match in face_matches:
            matches.append({
                "face_id": match['Face']['FaceId'],
                "external_image_id": match['Face'].get('ExternalImageId'),
                "similarity": match['Similarity'],
                "confidence": match['Face']['Confidence']
            })
        
        return {
            "success": True,
            "matched": True,
            "matches": matches,
            "best_match": matches[0] if matches else None
        }
        
    except ClientError as e:
        logger.error(f"AWS Rekognition ClientError: {e}")
        return {
            "success": False,
            "error": f"AWS Error: {e.response['Error']['Message']}"
        }
    except Exception as e:
        logger.error(f"Face search error: {e}")
        return {
            "success": False,
            "error": str(e)
        }


def verify_identity_via_collection(
    current_image_base64: str,
    expected_external_id: str,
    threshold: float = 85.0
) -> Dict:
    """
    Cost-optimized identity verification using the face collection.
    
    Instead of CompareFaces (requires loading both images each time), this uses
    SearchFacesByImage against the indexed collection. Benefits:
    - ~40% cheaper than CompareFaces (one image vs two)
    - Simultaneously detects if a DIFFERENT enrolled student is at the screen
    - No need to load the baseline image from DB each time
    
    Args:
        current_image_base64: Base64 image from webcam
        expected_external_id: Sanitized email/ID of the expected student
        threshold: Minimum similarity threshold
    
    Returns:
        dict with keys: verified, is_different_person, matched_identity, similarity, liveness_data
    """
    global rekognition_client
    
    if not AWS_AVAILABLE or not rekognition_client:
        return {"verified": True, "bypass": True, "reason": "AWS not available"}
    
    try:
        image_bytes = decode_base64_image_bytes(current_image_base64)
        
        is_valid, error_msg = validate_image(image_bytes)
        if not is_valid:
            return {"success": False, "verified": False, "error": error_msg, "no_face": True}
        
        # Single API call: search the collection
        response = rekognition_client.search_faces_by_image(
            CollectionId=REKOGNITION_COLLECTION_ID,
            Image={'Bytes': image_bytes},
            FaceMatchThreshold=threshold,
            MaxFaces=3
        )
        
        face_matches = response.get('FaceMatches', [])
        
        # Extract liveness heuristics (one detect_faces call, shared with verification)
        liveness_data = {}
        try:
            detect_response = rekognition_client.detect_faces(
                Image={'Bytes': image_bytes},
                Attributes=['ALL']
            )
            faces = detect_response.get('FaceDetails', [])
            if faces:
                face = faces[0]
                pose = face.get('Pose', {})
                eyes_open = face.get('EyesOpen', {})
                quality = face.get('Quality', {})
                liveness_data = {
                    "pose_yaw": pose.get('Yaw', 0),
                    "pose_pitch": pose.get('Pitch', 0),
                    "pose_roll": pose.get('Roll', 0),
                    "eyes_open": eyes_open.get('Value', True),
                    "eyes_open_confidence": eyes_open.get('Confidence', 0),
                    "quality_sharpness": quality.get('Sharpness', 100),
                    "quality_brightness": quality.get('Brightness', 100),
                }
            if len(faces) == 0:
                return {
                    "success": False, "verified": False,
                    "no_face": True, "message": "No face detected"
                }
        except Exception:
            pass
        
        sanitized_expected = _sanitize_external_id(expected_external_id)
        
        if not face_matches:
            return {
                "success": True,
                "verified": False,
                "is_different_person": False,
                "message": "Face not recognized in collection (may not be enrolled)",
                "no_face": False,
                "liveness_data": liveness_data,
            }
        
        # Check ALL returned matches — the expected user may not be the top
        # hit if they're enrolled under multiple accounts or if Rekognition
        # returns a slightly higher similarity for another face vector.
        expected_match = None
        for fm in face_matches:
            if fm['Face'].get('ExternalImageId', '') == sanitized_expected:
                expected_match = fm
                break

        if expected_match:
            return {
                "success": True,
                "verified": True,
                "is_different_person": False,
                "similarity": expected_match['Similarity'],
                "confidence": expected_match['Face'].get('Confidence', 0),
                "liveness_data": liveness_data,
                "message": f"Identity verified ({expected_match['Similarity']:.1f}% match)",
            }

        best = face_matches[0]
        best_ext_id = best['Face'].get('ExternalImageId', '')
        best_similarity = best['Similarity']

        return {
            "success": True,
            "verified": False,
            "is_different_person": True,
            "matched_identity": best_ext_id,
            "similarity": best_similarity,
            "liveness_data": liveness_data,
            "message": "Different enrolled person detected at this workstation",
        }
    
    except ClientError as e:
        error_code = e.response['Error']['Code']
        if error_code == 'InvalidParameterException':
            return {
                "success": False, "verified": False,
                "no_face": True, "error": "No face detected or image quality too low"
            }
        logger.error(f"Collection verify error [{error_code}]: {e}")
        return {"success": False, "verified": False, "error": str(e)}
    except Exception as e:
        logger.error(f"Collection verify error: {e}")
        return {"success": False, "verified": False, "error": str(e)}


def delete_face_from_collection(face_id: str) -> Dict:
    """
    Delete a face from the collection
    
    Args:
        face_id: Face ID to delete
    
    Returns:
        dict: Deletion results
    """
    global rekognition_client
    
    if not AWS_AVAILABLE or not rekognition_client:
        return {
            "success": False,
            "error": "AWS Rekognition not available"
        }
    
    try:
        response = rekognition_client.delete_faces(
            CollectionId=REKOGNITION_COLLECTION_ID,
            FaceIds=[face_id]
        )
        
        deleted_faces = response.get('DeletedFaces', [])
        
        if face_id in deleted_faces:
            logger.info(f"✅ Deleted face from collection: {face_id}")
            return {
                "success": True,
                "deleted": True
            }
        else:
            return {
                "success": False,
                "error": "Face not found in collection"
            }
        
    except ClientError as e:
        logger.error(f"AWS Rekognition ClientError: {e}")
        return {
            "success": False,
            "error": f"AWS Error: {e.response['Error']['Message']}"
        }
    except Exception as e:
        logger.error(f"Face deletion error: {e}")
        return {
            "success": False,
            "error": str(e)
        }


def get_collection_stats() -> Dict:
    """Get statistics about the face collection"""
    global rekognition_client
    
    if not AWS_AVAILABLE or not rekognition_client:
        return {
            "success": False,
            "error": "AWS Rekognition not available"
        }
    
    try:
        response = rekognition_client.describe_collection(
            CollectionId=REKOGNITION_COLLECTION_ID
        )
        
        return {
            "success": True,
            "collection_id": response.get('CollectionId', REKOGNITION_COLLECTION_ID),
            "face_count": response.get('FaceCount', 0),
            "created": response.get('CreationTimestamp'),
            "collection_arn": response.get('CollectionARN', '')
        }
        
    except ClientError as e:
        logger.error(f"AWS Rekognition ClientError: {e}")
        return {
            "success": False,
            "error": f"AWS Error: {e.response['Error']['Message']}"
        }
    except Exception as e:
        logger.error(f"Collection stats error: {e}")
        return {
            "success": False,
            "error": str(e)
        }
