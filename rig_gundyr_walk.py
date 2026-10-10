"""Bake an articulated walk from the existing Gundyr armor, without repainting it.

Leg layers are separated from one aligned source pose. Two-bone joints move
each thigh, shin and boot through contact/down/passing/up, with one planted
foot while the other clears the floor. These tools are only used offline.
"""

from __future__ import annotations

import math

import pygame


KEYFRAME_COUNT = 20
STANCE_FRACTION = 0.55
FOOT_TRAVEL = 54.0
FOOT_CLEARANCE = 16.0
THIGH_LENGTH = 24.0
SHIN_LENGTH = 25.0
SOURCE_SIZE = (154, 122)
BODY_AXIS = 60

LEG_RIGS = (
    {
        "name": "far",
        "phase_offset": 0.5,
        "hip": (53, 78), "knee": (43, 92), "ankle": (31, 111),
        "target_hip": (58, 76), "front_x": 86,
        "outline": (
            (50, 77), (57, 78), (56, 87), (51, 97), (47, 107),
            (47, 122), (19, 122), (19, 111), (26, 107),
            (28, 96), (34, 87), (43, 83),
        ),
    },
    {
        "name": "near",
        "phase_offset": 0.0,
        "hip": (73, 78), "knee": (79, 89), "ankle": (86, 110),
        "target_hip": (70, 76), "front_x": 92,
        "outline": (
            (71, 77), (81, 78), (87, 85), (89, 97), (92, 105),
            (99, 108), (106, 111), (106, 120), (81, 121),
            (80, 112), (76, 105), (74, 96), (73, 86),
        ),
    },
)


def foot_pose(phase: float, front_x: float, ankle_ground_y: float):
    """Return ankle position, boot angle and support state for one leg."""
    phase %= 1.0
    if phase <= STANCE_FRACTION:
        # The planted foot moves backwards relative to the travelling body.
        x = front_x - FOOT_TRAVEL * phase / STANCE_FRACTION
        return (x, ankle_ground_y), 0.0, True
    progress = (phase - STANCE_FRACTION) / (1 - STANCE_FRACTION)
    eased = progress * progress * (3 - 2 * progress)
    lift = FOOT_CLEARANCE * math.sin(math.pi * progress) ** 2
    x = front_x - FOOT_TRAVEL + FOOT_TRAVEL * eased
    return (x, ankle_ground_y - lift), -18 * math.sin(math.pi * progress), False


def knee_joint(hip, ankle):
    """Solve a forward-bending knee with stable thigh and shin lengths."""
    dx, dy = ankle[0] - hip[0], ankle[1] - hip[1]
    distance = math.hypot(dx, dy)
    if not 0 < distance < THIGH_LENGTH + SHIN_LENGTH:
        raise ValueError("Walk ankle lies outside the calibrated leg reach")
    along = (THIGH_LENGTH ** 2 - SHIN_LENGTH ** 2 + distance ** 2) / (2 * distance)
    bend = math.sqrt(max(0, THIGH_LENGTH ** 2 - along ** 2))
    return (
        hip[0] + (dx * along + dy * bend) / distance,
        hip[1] + (dy * along - dx * bend) / distance,
    )


def build_walk_keyframes(source: pygame.Surface) -> list[pygame.Surface]:
    try:
        import cv2
        import numpy as np
    except ImportError as error:
        raise RuntimeError(
            "Walk export needs the optional asset tools: "
            "py -m pip install -r requirements-assets.txt"
        ) from error

    if source.get_size() != SOURCE_SIZE:
        raise ValueError(f"Gundyr walk rig expects an aligned {SOURCE_SIZE} source cell")
    width, height = source.get_size()
    baseline = height - 2
    rgb = pygame.surfarray.array3d(source).transpose(1, 0, 2)
    alpha = pygame.surfarray.array_alpha(source).T[..., None].astype(np.float32) / 255
    pixels = np.concatenate((rgb.astype(np.float32) * alpha, alpha), axis=2)

    # Keep the entire halberd on an independent foreground layer. In particular
    # its shaft crosses the thigh: bending that region would bend the weapon.
    weapon_mask = np.zeros((height, width), dtype=np.uint8)
    cv2.line(weapon_mask, (23, 56), (138, 104), 255, 6)
    cv2.fillPoly(weapon_mask, [np.array((
        (98, 85), (109, 88), (117, 94), (127, 84), (134, 92),
        (135, 97), (140, 97), (148, 102), (150, 111),
        (121, 113), (106, 105), (100, 98),
    ), dtype=np.int32)], 255)
    weapon = pixels * (weapon_mask[..., None] / 255)

    masks, layers, ground_offsets = [], [], []
    for rig in LEG_RIGS:
        mask = np.zeros((height, width), dtype=np.uint8)
        cv2.fillPoly(mask, [np.array(rig["outline"], dtype=np.int32)], 255)
        mask[weapon_mask > 0] = 0
        layer = pixels * (mask[..., None] / 255)
        occupied_y = np.nonzero(layer[..., 3] > 24 / 255)[0]
        ground_offsets.append(baseline - 1 - occupied_y.max() + rig["ankle"][1])
        masks.append(mask)
        layers.append(layer)
    body_mask = np.maximum(masks[0], masks[1])
    body = pixels * (1 - body_mask[..., None] / 255) * (1 - weapon_mask[..., None] / 255)

    def over(bottom, top):
        return top + bottom * (1 - top[..., 3:4])

    def transform_bone(layer, start, end, target_start, target_end):
        a, b = np.asarray(start, np.float32), np.asarray(end, np.float32)
        c, d = np.asarray(target_start, np.float32), np.asarray(target_end, np.float32)
        direction = b - a
        normal = np.array((-direction[1], direction[0])) / np.linalg.norm(direction)
        target_direction = d - c
        target_normal = np.array((-target_direction[1], target_direction[0]))
        target_normal /= np.linalg.norm(target_direction)
        matrix = cv2.getAffineTransform(
            np.array((a, b, a + normal * 10), np.float32),
            np.array((c, d, c + target_normal * 10), np.float32),
        )
        return cv2.warpAffine(layer, matrix, (width, height), flags=cv2.INTER_LINEAR)

    def leg_layer(rig, layer, hip, knee, ankle, foot_angle):
        rows = np.arange(height)[:, None]
        knee_y, ankle_y = rig["knee"][1], rig["ankle"][1]
        # Slightly overlapping pieces keep the armor joints covered as they
        # bend; every piece is sampled from the same leg, never another frame.
        thigh = layer * (rows <= knee_y + 2)[..., None]
        shin = layer * ((rows >= knee_y - 2) & (rows <= ankle_y - 2))[..., None]
        boot = layer * (rows >= ankle_y - 4)[..., None]
        thigh = transform_bone(thigh, rig["hip"], rig["knee"], hip, knee)
        shin = transform_bone(shin, rig["knee"], rig["ankle"], knee, ankle)
        boot_matrix = cv2.getRotationMatrix2D(rig["ankle"], foot_angle, 1.0)
        boot_matrix[:, 2] += np.asarray(ankle) - np.asarray(rig["ankle"])
        boot = cv2.warpAffine(boot, boot_matrix, (width, height), flags=cv2.INTER_LINEAR)
        return over(over(thigh, shin), boot)

    frames = []
    for index in range(KEYFRAME_COUNT):
        phase = index / KEYFRAME_COUNT
        bob = 1.5 * math.sin(4 * math.pi * phase)
        leg_images = []
        for rig, layer, ground_y in zip(LEG_RIGS, layers, ground_offsets):
            ankle, angle, _ = foot_pose(phase + rig["phase_offset"], rig["front_x"], ground_y)
            hip = (rig["target_hip"][0], rig["target_hip"][1] + bob)
            knee = knee_joint(hip, ankle)
            leg_images.append(leg_layer(rig, layer, hip, knee, ankle, angle))
        shift = np.array(((1, 0, 0), (0, 1, bob)), dtype=np.float32)
        moved_body = cv2.warpAffine(body, shift, (width, height), flags=cv2.INTER_LINEAR)
        moved_weapon = cv2.warpAffine(weapon, shift, (width, height), flags=cv2.INTER_LINEAR)
        frame = over(leg_images[0], leg_images[1])
        frame = over(frame, moved_body)
        frame = over(frame, moved_weapon)
        rgba = np.zeros((height, width, 4), dtype=np.uint8)
        rgba[..., :3] = np.clip(np.rint(frame[..., :3] / np.maximum(frame[..., 3:4], 1e-6)), 0, 255)
        rgba[..., 3] = np.clip(np.rint(frame[..., 3] * 255), 0, 255)
        rgba[rgba[..., 3] == 0, :3] = 0
        frames.append(pygame.image.frombytes(rgba.tobytes(), (width, height), "RGBA"))
    return frames
