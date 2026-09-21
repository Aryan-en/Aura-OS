"""
Unit tests for AURA OS Vision Subsystem & Multimodal Fusion.
"""

from aura.vision.fusion import MultimodalFusionEngine
from aura.vision.gestures import GestureClassifier, GestureType
from aura.vision.landmarks import HandLandmarks, Point3D
from aura.vision.raycaster import SpatialRaycaster


def _create_mock_landmarks(open_palm: bool = False, pointing: bool = False, pinch: bool = False) -> HandLandmarks:
    """Generate synthetic 21-point hand pose."""
    # Wrist at (0.5, 0.8)
    points = [Point3D(x=0.5, y=0.8, z=0.0) for _ in range(21)]
    points[0] = Point3D(x=0.5, y=0.8, z=0.0)

    # By default, curl all fingers into palm:
    # MCP at 0.65, PIP at 0.55, TIP curled inward at 0.75 (closer to wrist than PIP)
    for pip_idx, tip_idx in [(6, 8), (10, 12), (14, 16), (18, 20)]:
        points[pip_idx] = Point3D(x=0.5, y=0.55, z=0.0)
        points[tip_idx] = Point3D(x=0.5, y=0.75, z=0.0)
    points[4] = Point3D(x=0.5, y=0.70, z=0.0)  # Thumb tip

    if open_palm:
        # Extend all fingers upward
        points[4] = Point3D(x=0.3, y=0.4, z=0.0)   # Thumb
        points[6] = Point3D(x=0.45, y=0.5, z=0.0)  # Index PIP
        points[8] = Point3D(x=0.45, y=0.2, z=0.0)  # Index TIP
        points[10] = Point3D(x=0.5, y=0.5, z=0.0)  # Middle PIP
        points[12] = Point3D(x=0.5, y=0.18, z=0.0) # Middle TIP
        points[14] = Point3D(x=0.55, y=0.5, z=0.0) # Ring PIP
        points[16] = Point3D(x=0.55, y=0.22, z=0.0)# Ring TIP
        points[18] = Point3D(x=0.6, y=0.5, z=0.0)  # Pinky PIP
        points[20] = Point3D(x=0.6, y=0.25, z=0.0) # Pinky TIP

    elif pointing:
        # Index extended, others remain curled
        points[5] = Point3D(x=0.5, y=0.6, z=0.0)   # Index MCP
        points[6] = Point3D(x=0.5, y=0.45, z=0.0)  # Index PIP
        points[8] = Point3D(x=0.5, y=0.2, z=0.0)   # Index TIP

    elif pinch:
        # Thumb and index tips touch
        points[4] = Point3D(x=0.5, y=0.4, z=0.0)
        points[8] = Point3D(x=0.51, y=0.4, z=0.0)

    return HandLandmarks(points=points)


def test_open_palm_emergency_stop() -> None:
    classifier = GestureClassifier()
    landmarks = _create_mock_landmarks(open_palm=True)
    event = classifier.classify(landmarks)
    assert event.gesture == GestureType.OPEN_PALM


def test_pointing_gesture_classification() -> None:
    classifier = GestureClassifier()
    landmarks = _create_mock_landmarks(pointing=True)
    event = classifier.classify(landmarks)
    assert event.gesture == GestureType.POINT
    assert event.screen_x is not None


def test_pinch_gesture_classification() -> None:
    classifier = GestureClassifier()
    landmarks = _create_mock_landmarks(pinch=True)
    event = classifier.classify(landmarks)
    assert event.gesture == GestureType.PINCH


def test_spatial_raycaster_projection() -> None:
    raycaster = SpatialRaycaster(display_width=1920, display_height=1080)
    landmarks = _create_mock_landmarks(pointing=True)
    target = raycaster.project(landmarks)
    assert target.is_pointing is True
    assert 0 <= target.screen_x <= 1920
    assert 0 <= target.screen_y <= 1080


def test_multimodal_fusion_deictic_binding() -> None:
    fusion = MultimodalFusionEngine(temporal_window_ms=400)
    raycaster = SpatialRaycaster(display_width=1920, display_height=1080)
    landmarks = _create_mock_landmarks(pointing=True)

    target = raycaster.project(landmarks)
    fusion.record_target(target)

    # User simultaneously says "close that"
    deictic = fusion.resolve_deictic_reference("close that")
    assert deictic is not None
    assert deictic.word == "that"
    assert deictic.screen_x == target.screen_x
    assert deictic.screen_y == target.screen_y

    # Non-deictic utterance returns None
    assert fusion.resolve_deictic_reference("list all my files") is None
