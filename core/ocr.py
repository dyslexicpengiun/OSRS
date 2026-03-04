"""
OCR System for reading in-game text.
Uses EasyOCR with fallback to custom pixel-based OSRS font reading.
"""

import cv2
import numpy as np
from typing import Optional, List, Tuple
import re

try:
    import easyocr
    EASYOCR_AVAILABLE = True
except ImportError:
    EASYOCR_AVAILABLE = False


class OSRSTextReader:
    """
    Reads text from OSRS screenshots.
    Optimized for OSRS's specific fonts and text rendering.
    """

    # OSRS text colors (BGR format)
    TEXT_COLORS = {
        'yellow': (0, 255, 255),
        'white': (255, 255, 255),
        'cyan': (255, 255, 0),
        'green': (0, 255, 0),
        'red': (0, 0, 255),
        'orange': (0, 152, 255),
        'black': (0, 0, 0),
        'dark_red': (0, 0, 128),
        'chat_blue': (255, 0, 0),
    }

    def __init__(self):
        self._reader = None
        if EASYOCR_AVAILABLE:
            try:
                self._reader = easyocr.Reader(['en'], gpu=False, verbose=False)
            except Exception as e:
                print(f"[OCR] EasyOCR init failed: {e}")

    def read_text(
        self,
        image: np.ndarray,
        region: Tuple[int, int, int, int] = None,
        text_color: str = None,
        invert: bool = False,
        scale: float = 2.0
    ) -> str:
        """
        Read text from an image region.

        Args:
            image: BGR numpy array
            region: (x, y, w, h) to read from
            text_color: Name of text color to isolate
            invert: Invert image colors before OCR
            scale: Scale factor for better OCR accuracy
        """
        if image is None:
            return ""

        roi = image
        if region:
            x, y, w, h = region
            roi = image[y:y+h, x:x+w]

        # Preprocess for better OCR
        processed = self._preprocess_for_ocr(roi, text_color, invert, scale)

        if self._reader:
            try:
                results = self._reader.readtext(processed, detail=0, paragraph=True)
                return ' '.join(results).strip()
            except Exception:
                pass

        # Fallback: simple threshold + pytesseract-style reading
        return self._basic_text_extract(processed)

    def read_number(
        self,
        image: np.ndarray,
        region: Tuple[int, int, int, int] = None,
        text_color: str = 'white'
    ) -> Optional[int]:
        """Read a number from the screen (e.g., stack sizes, XP drops)."""
        text = self.read_text(image, region, text_color)
        # Clean up OCR artifacts
        text = re.sub(r'[^0-9kKmM,.]', '', text)

        if not text:
            return None

        try:
            # Handle k/m suffixes
            text_lower = text.lower().replace(',', '')
            if 'k' in text_lower:
                return int(float(text_lower.replace('k', '')) * 1000)
            elif 'm' in text_lower:
                return int(float(text_lower.replace('m', '')) * 1000000)
            else:
                return int(float(text_lower))
        except (ValueError, OverflowError):
            return None

    def read_chatbox(self, image: np.ndarray, chatbox_region: Tuple[int, int, int, int]) -> List[str]:
        """Read chatbox messages."""
        roi = image[chatbox_region[1]:chatbox_region[1]+chatbox_region[3],
                     chatbox_region[0]:chatbox_region[0]+chatbox_region[2]]

        # Split into lines (each chat line is about 14px tall in OSRS)
        line_height = 14
        lines = []
        h = roi.shape[0]

        for y in range(0, h - line_height, line_height):
            line_img = roi[y:y+line_height, :]
            text = self.read_text(line_img)
            if text.strip():
                lines.append(text.strip())

        return lines

    def find_text_on_screen(
        self,
        image: np.ndarray,
        target_text: str,
        text_color: str = None,
        region: Tuple[int, int, int, int] = None,
        threshold: float = 0.7
    ) -> Optional[Tuple[int, int]]:
        """
        Find specific text on screen and return its center position.

        Uses fuzzy matching to account for OCR inaccuracies.
        """
        if not self._reader:
            return None

        roi = image
        offset_x, offset_y = 0, 0
        if region:
            x, y, w, h = region
            roi = image[y:y+h, x:x+w]
            offset_x, offset_y = x, y

        processed = self._preprocess_for_ocr(roi, text_color, scale=2.0)

        try:
            results = self._reader.readtext(processed)
            from rapidfuzz import fuzz

            for (bbox, text, conf) in results:
                similarity = fuzz.partial_ratio(target_text.lower(), text.lower()) / 100
                if similarity >= threshold:
                    # Calculate center of text bbox
                    points = np.array(bbox)
                    cx = int(points[:, 0].mean() / 2) + offset_x  # Divide by scale
                    cy = int(points[:, 1].mean() / 2) + offset_y
                    return (cx, cy)
        except Exception:
            pass

        return None

    def _preprocess_for_ocr(
        self,
        image: np.ndarray,
        text_color: str = None,
        invert: bool = False,
        scale: float = 2.0
    ) -> np.ndarray:
        """Preprocess image for better OCR results."""
        result = image.copy()

        # Isolate text color if specified
        if text_color and text_color in self.TEXT_COLORS:
            color = self.TEXT_COLORS[text_color]
            tolerance = 40
            lower = np.array([max(0, c - tolerance) for c in color], dtype=np.uint8)
            upper = np.array([min(255, c + tolerance) for c in color], dtype=np.uint8)
            mask = cv2.inRange(result, lower, upper)
            result = cv2.bitwise_and(result, result, mask=mask)

        # Convert to grayscale
        if len(result.shape) == 3:
            result = cv2.cvtColor(result, cv2.COLOR_BGR2GRAY)

        # Scale up for better recognition
        if scale != 1.0:
            result = cv2.resize(result, None, fx=scale, fy=scale,
                                interpolation=cv2.INTER_CUBIC)

        # Threshold
        _, result = cv2.threshold(result, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

        if invert:
            result = cv2.bitwise_not(result)

        return result

    def _basic_text_extract(self, image: np.ndarray) -> str:
        """Basic text extraction without ML-based OCR."""
        # This is a placeholder for pixel-based font matching
        # In production, you'd match against OSRS font bitmaps
        return ""