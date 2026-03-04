"""
Computer Vision System
Template matching, object detection, and image analysis for OSRS.
"""

import os
import cv2
import numpy as np
from typing import List, Tuple, Optional, Dict
import threading
import time


class TemplateMatch:
    """Represents a template match result."""

    def __init__(self, x: int, y: int, width: int, height: int,
                 confidence: float, name: str = ""):
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.confidence = confidence
        self.name = name

    @property
    def center(self) -> Tuple[int, int]:
        return (self.x + self.width // 2, self.y + self.height // 2)

    @property
    def center_x(self) -> int:
        return self.x + self.width // 2

    @property
    def center_y(self) -> int:
        return self.y + self.height // 2

    @property
    def rect(self) -> Tuple[int, int, int, int]:
        return (self.x, self.y, self.width, self.height)

    def __repr__(self):
        return f"TemplateMatch('{self.name}' at ({self.x},{self.y}) conf={self.confidence:.3f})"


class Vision:
    """
    Computer vision system for OSRS.
    Handles template matching, color detection, contour finding, etc.
    """

    def __init__(self, assets_path: str = "assets"):
        self.assets_path = assets_path
        self.template_cache: Dict[str, np.ndarray] = {}
        self.mask_cache: Dict[str, np.ndarray] = {}
        self._lock = threading.Lock()

    def load_template(self, template_path: str, with_mask: bool = False) -> np.ndarray:
        """
        Load a template image, using cache if available.

        Args:
            template_path: Path relative to assets/templates/
            with_mask: If True, also create a mask from alpha channel
        """
        full_path = os.path.join(self.assets_path, "templates", template_path)

        if template_path in self.template_cache:
            return self.template_cache[template_path]

        if not os.path.exists(full_path):
            return None

        # Load with alpha channel
        template = cv2.imread(full_path, cv2.IMREAD_UNCHANGED)
        if template is None:
            return None

        # If has alpha channel, create mask and convert to BGR
        if template.shape[2] == 4 and with_mask:
            mask = template[:, :, 3]
            self.mask_cache[template_path] = mask
            template = cv2.cvtColor(template, cv2.COLOR_BGRA2BGR)
        elif template.shape[2] == 4:
            template = cv2.cvtColor(template, cv2.COLOR_BGRA2BGR)

        self.template_cache[template_path] = template
        return template

    def find_template(
        self,
        screen: np.ndarray,
        template_path: str,
        threshold: float = 0.85,
        region: Tuple[int, int, int, int] = None,
        method: int = cv2.TM_CCOEFF_NORMED,
        use_mask: bool = False
    ) -> Optional[TemplateMatch]:
        """
        Find the best match of a template in the screen image.

        Args:
            screen: BGR screenshot numpy array
            template_path: Path to template relative to assets/templates/
            threshold: Minimum confidence threshold (0-1)
            region: Optional (x, y, w, h) to search within
            method: OpenCV template matching method
            use_mask: Use alpha mask for matching

        Returns:
            TemplateMatch or None if not found above threshold
        """
        template = self.load_template(template_path, with_mask=use_mask)
        if template is None or screen is None:
            return None

        search_area = screen
        offset_x, offset_y = 0, 0

        if region is not None:
            rx, ry, rw, rh = region
            search_area = screen[ry:ry+rh, rx:rx+rw]
            offset_x, offset_y = rx, ry

        if search_area.shape[0] < template.shape[0] or search_area.shape[1] < template.shape[1]:
            return None

        mask = self.mask_cache.get(template_path) if use_mask else None

        if mask is not None:
            result = cv2.matchTemplate(search_area, template, method, mask=mask)
        else:
            result = cv2.matchTemplate(search_area, template, method)

        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

        # For TM_SQDIFF methods, minimum is best
        if method in [cv2.TM_SQDIFF, cv2.TM_SQDIFF_NORMED]:
            confidence = 1 - min_val
            loc = min_loc
        else:
            confidence = max_val
            loc = max_loc

        if confidence >= threshold:
            return TemplateMatch(
                x=loc[0] + offset_x,
                y=loc[1] + offset_y,
                width=template.shape[1],
                height=template.shape[0],
                confidence=confidence,
                name=template_path
            )

        return None

    def find_all_templates(
        self,
        screen: np.ndarray,
        template_path,          # str  OR  List[str]  — supports multi-variant objects
        threshold: float = 0.85,
        region: Tuple[int, int, int, int] = None,
        method: int = cv2.TM_CCOEFF_NORMED,
        max_results: int = 50,
        nms_threshold: float = 0.3
    ) -> List[TemplateMatch]:
        """
        Find all instances of one or more templates in the screen.

        template_path may be:
          - a single path string  e.g. "objects/oak_tree.png"
          - a list of path strings e.g. ["objects/oak_tree_1.png",
                                          "objects/oak_tree_2.png"]

        When a list is supplied every variant is searched and the combined
        results are de-duplicated with Non-Maximum Suppression before being
        returned.  This is the correct way to handle objects that have
        multiple distinct 3-D models (trees, rocks, fishing spots).
        """
        if screen is None:
            return []

        # Normalise to a list so the rest of the method is uniform
        paths = [template_path] if isinstance(template_path, str) else list(template_path)

        search_area = screen
        offset_x, offset_y = 0, 0
        if region is not None:
            rx, ry, rw, rh = region
            search_area = screen[ry:ry+rh, rx:rx+rw]
            offset_x, offset_y = rx, ry

        all_matches: List[TemplateMatch] = []

        for path in paths:
            template = self.load_template(path)
            if template is None:
                continue

            if (search_area.shape[0] < template.shape[0] or
                    search_area.shape[1] < template.shape[1]):
                continue

            result = cv2.matchTemplate(search_area, template, method)
            th, tw = template.shape[:2]

            locations = np.where(result >= threshold)
            for pt_y, pt_x in zip(*locations):
                all_matches.append(TemplateMatch(
                    x=int(pt_x) + offset_x,
                    y=int(pt_y) + offset_y,
                    width=tw,
                    height=th,
                    confidence=float(result[pt_y, pt_x]),
                    name=path
                ))

        # Suppress overlapping detections across all variants
        if len(all_matches) > 1:
            all_matches = self._nms(all_matches, nms_threshold)

        all_matches.sort(key=lambda m: m.confidence, reverse=True)
        return all_matches[:max_results]

    def _nms(self, matches: List[TemplateMatch], threshold: float) -> List[TemplateMatch]:
        """Non-maximum suppression for overlapping detections."""
        if not matches:
            return []

        boxes = np.array([[m.x, m.y, m.x + m.width, m.y + m.height] for m in matches])
        scores = np.array([m.confidence for m in matches])

        x1 = boxes[:, 0]
        y1 = boxes[:, 1]
        x2 = boxes[:, 2]
        y2 = boxes[:, 3]
        areas = (x2 - x1) * (y2 - y1)

        order = scores.argsort()[::-1]
        keep = []

        while order.size > 0:
            i = order[0]
            keep.append(i)

            xx1 = np.maximum(x1[i], x1[order[1:]])
            yy1 = np.maximum(y1[i], y1[order[1:]])
            xx2 = np.minimum(x2[i], x2[order[1:]])
            yy2 = np.minimum(y2[i], y2[order[1:]])

            w = np.maximum(0, xx2 - xx1)
            h = np.maximum(0, yy2 - yy1)

            inter = w * h
            iou = inter / (areas[i] + areas[order[1:]] - inter)

            inds = np.where(iou <= threshold)[0]
            order = order[inds + 1]

        return [matches[i] for i in keep]

    def find_color_clusters(
        self,
        screen: np.ndarray,
        color_bgr: Tuple[int, int, int],
        tolerance: int = 15,
        min_area: int = 20,
        region: Tuple[int, int, int, int] = None
    ) -> List[Tuple[int, int, int, int]]:
        """
        Find clusters of a specific color in the screen.

        Returns list of (x, y, w, h) bounding rectangles.
        """
        search_area = screen
        offset_x, offset_y = 0, 0

        if region:
            rx, ry, rw, rh = region
            search_area = screen[ry:ry+rh, rx:rx+rw]
            offset_x, offset_y = rx, ry

        # Create color range
        lower = np.array([max(0, c - tolerance) for c in color_bgr], dtype=np.uint8)
        upper = np.array([min(255, c + tolerance) for c in color_bgr], dtype=np.uint8)

        mask = cv2.inRange(search_area, lower, upper)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        results = []
        for contour in contours:
            area = cv2.contourArea(contour)
            if area >= min_area:
                x, y, w, h = cv2.boundingRect(contour)
                results.append((x + offset_x, y + offset_y, w, h))

        return results

    def find_color_hsv(
        self,
        screen: np.ndarray,
        lower_hsv: Tuple[int, int, int],
        upper_hsv: Tuple[int, int, int],
        min_area: int = 20,
        region: Tuple[int, int, int, int] = None
    ) -> List[Tuple[int, int, int, int]]:
        """Find color clusters using HSV color space for better color matching."""
        search_area = screen
        offset_x, offset_y = 0, 0

        if region:
            rx, ry, rw, rh = region
            search_area = screen[ry:ry+rh, rx:rx+rw]
            offset_x, offset_y = rx, ry

        hsv = cv2.cvtColor(search_area, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv, np.array(lower_hsv), np.array(upper_hsv))

        # Morphological operations to clean up
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)

        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        results = []
        for contour in contours:
            area = cv2.contourArea(contour)
            if area >= min_area:
                x, y, w, h = cv2.boundingRect(contour)
                results.append((x + offset_x, y + offset_y, w, h))

        return results

    def pixel_matches_color(
        self,
        screen: np.ndarray,
        x: int, y: int,
        color_bgr: Tuple[int, int, int],
        tolerance: int = 10
    ) -> bool:
        """Check if a specific pixel matches a color within tolerance."""
        if screen is None or y >= screen.shape[0] or x >= screen.shape[1]:
            return False

        pixel = screen[y, x]
        return all(abs(int(pixel[i]) - int(color_bgr[i])) <= tolerance for i in range(3))

    def find_text_region(
        self,
        screen: np.ndarray,
        text_color_bgr: Tuple[int, int, int] = (0, 255, 255),  # Yellow text default
        tolerance: int = 30,
        region: Tuple[int, int, int, int] = None
    ) -> List[Tuple[int, int, int, int]]:
        """Find regions of colored text (useful for object names, NPC text, etc.)."""
        return self.find_color_clusters(screen, text_color_bgr, tolerance, min_area=10, region=region)

    def get_dominant_colors(
        self,
        screen: np.ndarray,
        region: Tuple[int, int, int, int] = None,
        k: int = 3
    ) -> List[Tuple[int, int, int]]:
        """Get the k most dominant colors in a region using k-means clustering."""
        search_area = screen
        if region:
            rx, ry, rw, rh = region
            search_area = screen[ry:ry+rh, rx:rx+rw]

        pixels = search_area.reshape(-1, 3).astype(np.float32)

        criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 10, 1.0)
        _, labels, centers = cv2.kmeans(pixels, k, None, criteria, 3, cv2.KMEANS_PP_CENTERS)

        centers = centers.astype(int)
        # Sort by frequency
        counts = np.bincount(labels.flatten())
        sorted_indices = np.argsort(-counts)

        return [tuple(centers[i]) for i in sorted_indices]

    def compare_images(self, img1: np.ndarray, img2: np.ndarray) -> float:
        """
        Compare two images and return similarity score (0-1).
        Useful for detecting if screen has changed (idle detection).
        """
        if img1 is None or img2 is None:
            return 0.0

        if img1.shape != img2.shape:
            img2 = cv2.resize(img2, (img1.shape[1], img1.shape[0]))

        # Convert to grayscale for comparison
        gray1 = cv2.cvtColor(img1, cv2.COLOR_BGR2GRAY)
        gray2 = cv2.cvtColor(img2, cv2.COLOR_BGR2GRAY)

        # Structural Similarity
        diff = cv2.absdiff(gray1, gray2)
        non_zero = np.count_nonzero(diff > 10)
        total = diff.size

        return 1.0 - (non_zero / total)

    def clear_cache(self):
        """Clear the template cache."""
        with self._lock:
            self.template_cache.clear()
            self.mask_cache.clear()