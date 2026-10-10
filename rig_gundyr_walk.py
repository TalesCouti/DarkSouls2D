"""Bake an articulated walk from the existing Gundyr armor, without repainting it.

The supplied eight-pose walk is a movement reference only. Armor textures
come exclusively from Gundyr's source. The pelvis, spine, shoulders, arms,
cape and rigid halberd follow the same continuous gait, baked offline.
"""

from __future__ import annotations

import math

import pygame


KEYFRAME_COUNT = 20
FRAME_COUNT = 60
STANCE_FRACTION = 0.52
FOOT_TRAVEL = 50.0
FOOT_CLEARANCE = 10.0
THIGH_LENGTH = 20.5
SHIN_LENGTH = 23.5
SOURCE_SIZE = (154, 122)
BODY_AXIS = 60

LEG_RIGS = (
    {
        "name": "far",
        "phase_offset": 0.5,
        "hip": (53, 74), "knee": (43, 92), "ankle": (31, 111),
        "target_hip": (58, 77), "front_x": 84,
        "outline": (
            (50, 77), (57, 78), (56, 87), (51, 97), (47, 107),
            (47, 122), (19, 122), (19, 111), (26, 107),
            (28, 96), (34, 87), (43, 83),
        ),
    },
    {
        "name": "near",
        "phase_offset": 0.0,
        "hip": (71, 72), "knee": (79, 89), "ankle": (86, 110),
        "target_hip": (66, 77), "front_x": 90,
        "outline": (
            (71, 77), (81, 78), (87, 85), (89, 97), (92, 105),
            (99, 108), (106, 111), (106, 120), (81, 121),
            (80, 112), (76, 105), (74, 96), (73, 86),
        ),
    },
)

ARM_RIGS = (
    {
        "shoulder": (45, 38), "elbow": (47, 55), "hand": (53, 65),
        "outline": ((43, 31), (55, 35), (53, 46), (53, 55),
                    (60, 63), (57, 69), (46, 67), (40, 60), (37, 42)),
    },
    {
        "shoulder": (73, 42), "elbow": (76, 61), "hand": (83, 75),
        "outline": ((69, 34), (80, 37), (82, 47), (85, 56),
                    (87, 68), (89, 78), (78, 80), (72, 69), (67, 48)),
    },
)


def cyclic_curve(phase, values):
    """Periodic Catmull-Rom: smooth velocity across the eight reference beats."""
    position = (phase % 1.0) * len(values)
    index, t = int(position), position % 1
    a, b, c, d = (values[(index + offset) % len(values)] for offset in (-1, 0, 1, 2))
    return 0.5 * (
        2 * b + (-a + c) * t + (2 * a - 5 * b + 4 * c - d) * t * t
        + (-a + 3 * b - 3 * c + d) * t * t * t
    )


def body_bob(phase):
    # Contact, absorption, passing, rise; repeated for the opposite foot.
    return cyclic_curve(phase, (0, 1.25, -1.5, -2.25, 0, 1.25, -1.5, -2.25))


def body_landmark(point, phase):
    """Continuous spine deformation shared by the torso and limb attachments."""
    x, y = point
    theta = 2 * math.pi * phase
    sway = math.sin(theta)
    upper = max(0.0, min(1.0, (68 - y) / 30))
    head = max(0.0, min(1.0, (35 - y) / 17))
    dx = (1 - upper) * 1.2 * sway - upper * 2.0 * sway
    dx = dx * (1 - head) - head * 0.9 * math.sin(theta - 0.2)
    twist = -0.025 * sway * upper
    return (
        x + dx + (x - BODY_AXIS) * twist,
        y + body_bob(phase) + 0.045 * sway * upper * (x - BODY_AXIS),
    )


def weapon_pose(phase):
    theta = 2 * math.pi * phase
    return (
        (0.2 * math.sin(theta), body_bob(phase) + 0.8 * math.sin(theta)),
        2.4 * math.sin(theta - 0.3) + 1.2 * math.sin(2 * theta),
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
    angle = math.sin(math.pi * progress) * (-20 * (1 - progress) + 8 * progress)
    return (x, ankle_ground_y - lift), angle, False


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


def build_walk_frames(source: pygame.Surface, frame_count: int = FRAME_COUNT) -> list[pygame.Surface]:
    try:
        import cv2
        import numpy as np
    except ImportError as error:
        raise RuntimeError(
            "Walk export needs the optional asset tools: "
            "py -m pip install -r requirements-assets.txt"
        ) from error

    if frame_count <= 0:
        raise ValueError("Walk frame count must be positive")
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
    arm_masks, arm_layers = [], []
    for rig in ARM_RIGS:
        mask = np.zeros((height, width), dtype=np.uint8)
        cv2.fillPoly(mask, [np.array(rig["outline"], dtype=np.int32)], 255)
        mask[weapon_mask > 0] = 0
        arm_masks.append(mask)
        arm_layers.append(pixels * (mask[..., None] / 255))
    body_mask = np.maximum.reduce(masks + arm_masks + [weapon_mask])
    body = pixels * (1 - body_mask[..., None] / 255)
    cape_mask = np.zeros((height, width), dtype=np.uint8)
    cv2.fillPoly(cape_mask, [np.array(
        ((49, 73), (52, 88), (37, 102), (17, 109), (17, 93), (35, 76)),
        dtype=np.int32,
    )], 255)
    cape = body * (cape_mask[..., None] / 255)
    body *= 1 - cape_mask[..., None] / 255

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

    def transform_point(matrix, point):
        return tuple(matrix @ np.array((*point, 1)))

    def arm_layer(rig, layer, phase, weapon_matrix):
        shoulder = body_landmark(rig["shoulder"], phase)
        hand = transform_point(weapon_matrix, rig["hand"])
        upper_length = math.dist(rig["shoulder"], rig["elbow"])
        lower_length = math.dist(rig["elbow"], rig["hand"])
        dx, dy = hand[0] - shoulder[0], hand[1] - shoulder[1]
        reach = math.hypot(dx, dy)
        stretch = max(1.0, reach / (upper_length + lower_length) * 1.001)
        if stretch > 1.12:
            raise ValueError("Halberd grip moved outside the calibrated arm reach")
        upper_length, lower_length = upper_length * stretch, lower_length * stretch
        along = (upper_length ** 2 - lower_length ** 2 + reach ** 2) / (2 * reach)
        bend = math.sqrt(max(0, upper_length ** 2 - along ** 2))
        elbow = (
            shoulder[0] + (dx * along - dy * bend) / reach,
            shoulder[1] + (dy * along + dx * bend) / reach,
        )
        rows = np.arange(height)[:, None]
        upper = layer * (rows <= rig["elbow"][1] + 2)[..., None]
        lower = layer * ((rows >= rig["elbow"][1] - 2) & (rows <= rig["hand"][1] - 1))[..., None]
        fingers = layer * (rows >= rig["hand"][1] - 3)[..., None]
        upper = transform_bone(upper, rig["shoulder"], rig["elbow"], shoulder, elbow)
        lower = transform_bone(lower, rig["elbow"], rig["hand"], elbow, hand)
        fingers = cv2.warpAffine(fingers, weapon_matrix, (width, height), flags=cv2.INTER_LINEAR)
        return over(over(upper, lower), fingers)

    grid_x, grid_y = np.meshgrid(
        np.arange(width, dtype=np.float32), np.arange(height, dtype=np.float32),
    )

    def deform_body(phase):
        theta = 2 * math.pi * phase
        upper = np.clip((68 - grid_y) / 30, 0, 1)
        head = np.clip((35 - grid_y) / 17, 0, 1)
        dx = (1 - upper) * 1.2 * math.sin(theta) - upper * 2.0 * math.sin(theta)
        dx = dx * (1 - head) - head * 0.9 * math.sin(theta - 0.2)
        twist = -0.025 * math.sin(theta) * upper
        roll = 0.045 * math.sin(theta) * upper
        # Invert the same smooth deformation used by the shoulder/hip joints.
        sx, sy = grid_x.copy(), grid_y.copy()
        for _ in range(4):
            du = cv2.remap(dx, sx, sy, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
            dt = cv2.remap(twist, sx, sy, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
            dr = cv2.remap(roll, sx, sy, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
            sx = (grid_x - du + BODY_AXIS * dt) / (1 + dt)
            sy = grid_y - body_bob(phase) - dr * (sx - BODY_AXIS)
        return cv2.remap(body, sx, sy, cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT)

    frames = []
    for index in range(frame_count):
        phase = index / frame_count
        leg_images = []
        for rig, layer, ground_y in zip(LEG_RIGS, layers, ground_offsets):
            ankle, angle, _ = foot_pose(phase + rig["phase_offset"], rig["front_x"], ground_y)
            # Rock the boot without letting its toe penetrate the floor.
            boot_y, boot_x = np.nonzero(
                (layer[..., 3] > 24 / 255) & (grid_y >= rig["ankle"][1] - 4)
            )
            rotation = cv2.getRotationMatrix2D(rig["ankle"], angle, 1.0)
            rotated_y = rotation[1, 0] * boot_x + rotation[1, 1] * boot_y + rotation[1, 2]
            ankle = (ankle[0], ankle[1] - (rotated_y.max() - boot_y.max()))
            hip = body_landmark(rig["target_hip"], phase)
            knee = knee_joint(hip, ankle)
            leg_images.append(leg_layer(rig, layer, hip, knee, ankle, angle))
        grip_delta, weapon_angle = weapon_pose(phase)
        weapon_matrix = cv2.getRotationMatrix2D((53, 65), weapon_angle, 1.0)
        weapon_matrix[:, 2] += grip_delta
        moved_weapon = cv2.warpAffine(weapon, weapon_matrix, (width, height), flags=cv2.INTER_LINEAR)
        cape_matrix = cv2.getRotationMatrix2D((49, 75), 7 * math.sin(2 * math.pi * (phase - 0.14)), 1.0)
        cape_matrix[:, 2] += np.asarray(body_landmark((49, 75), phase)) - (49, 75)
        moved_cape = cv2.warpAffine(cape, cape_matrix, (width, height), flags=cv2.INTER_LINEAR)
        frame = over(moved_cape, leg_images[0])
        frame = over(frame, leg_images[1])
        frame = over(frame, deform_body(phase))
        for rig, layer in zip(ARM_RIGS, arm_layers):
            frame = over(frame, arm_layer(rig, layer, phase, weapon_matrix))
        frame = over(frame, moved_weapon)
        rgba = np.zeros((height, width, 4), dtype=np.uint8)
        rgba[..., :3] = np.clip(np.rint(frame[..., :3] / np.maximum(frame[..., 3:4], 1e-6)), 0, 255)
        rgba[..., 3] = np.clip(np.rint(frame[..., 3] * 255), 0, 255)
        rgba[rgba[..., 3] == 0, :3] = 0
        frames.append(pygame.image.frombytes(rgba.tobytes(), (width, height), "RGBA"))
    return frames


def build_walk_keyframes(source: pygame.Surface) -> list[pygame.Surface]:
    return build_walk_frames(source, KEYFRAME_COUNT)
