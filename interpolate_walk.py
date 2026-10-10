"""Offline geometric inbetweens for the aligned Gundyr walk cells.

The game only loads the exported PNG; OpenCV is needed at export time, not
while playing. Original key poses are copied unchanged into the final strip.
"""

from __future__ import annotations

import pygame


WALK_INBETWEENS = 2


def interpolate_walk_cells(cells: list[pygame.Surface]) -> list[pygame.Surface]:
    if not cells:
        return []
    width, height = cells[0].get_size()
    if any(cell.get_size() != (width, height) for cell in cells):
        raise ValueError("Walk cells must share their size and ground anchor")
    try:
        import cv2
        import numpy as np
    except ImportError as error:
        raise RuntimeError(
            "Walk export needs the optional asset tools: "
            "py -m pip install -r requirements-assets.txt"
        ) from error

    def rgba(surface):
        rgb = pygame.surfarray.array3d(surface).transpose(1, 0, 2)
        alpha = pygame.surfarray.array_alpha(surface).T[..., None]
        return np.concatenate((rgb, alpha), axis=2)

    def flow_image(pixels):
        # A neutral matte distinguishes the dark armor from transparency;
        # comparing alpha alone cannot follow the knee plates or the boots.
        alpha = pixels[..., 3:4].astype(np.float32) / 255
        matte = pixels[..., :3] * alpha + 112 * (1 - alpha)
        return cv2.cvtColor(matte.astype(np.uint8), cv2.COLOR_RGB2GRAY)

    def motion(start, end):
        flow = cv2.calcOpticalFlowFarneback(
            start, end, None, 0.5, 4, 15, 6, 5, 1.1, 0
        )
        # Both source poses have grounded feet. Do not let the motion estimate
        # move floor-contact pixels vertically below or above that baseline.
        floor_weight = np.clip((height - 3 - grid_y) / 6, 0, 1)
        flow[..., 1] *= floor_weight
        return flow

    def warp(pixels, flow, amount):
        # Solve the inverse of x' = x + amount * flow(x). A single subtraction
        # samples motion at the wrong position and stretches thin weapon edges.
        source_x, source_y = grid_x.copy(), grid_y.copy()
        for _ in range(5):
            sampled = cv2.remap(
                flow, source_x, source_y, cv2.INTER_LINEAR,
                borderMode=cv2.BORDER_REPLICATE,
            )
            source_x = grid_x - amount * sampled[..., 0]
            source_y = grid_y - amount * sampled[..., 1]
        alpha = pixels[..., 3:4].astype(np.float32) / 255
        premultiplied = np.concatenate(
            (pixels[..., :3].astype(np.float32) * alpha, alpha), axis=2
        )
        return cv2.remap(
            premultiplied, source_x, source_y, cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_CONSTANT, borderValue=0,
        )

    def distance(alpha):
        silhouette = (alpha > 0.1).astype(np.uint8)
        inside = cv2.distanceTransform(silhouette, cv2.DIST_L2, 5)
        outside = cv2.distanceTransform(1 - silhouette, cv2.DIST_L2, 5)
        return inside - outside

    def inbetween(start, end, forward, backward, amount):
        warped_start = warp(start, forward, amount)
        warped_end = warp(end, backward, 1 - amount)
        blended = warped_start * (1 - amount) + warped_end * amount

        # Interpolate one geometric contour instead of cross-fading two alpha
        # outlines, which would leave a second translucent boot/halberd behind.
        contour = (
            distance(warped_start[..., 3]) * (1 - amount)
            + distance(warped_end[..., 3]) * amount
        )
        coverage = np.clip(contour + 0.5, 0, 1)
        blended_alpha = blended[..., 3]
        rgb = blended[..., :3] / np.maximum(blended_alpha[..., None], 1e-6)
        result = np.zeros(start.shape, dtype=np.uint8)
        result[..., :3] = np.clip(np.rint(rgb), 0, 255).astype(np.uint8)
        result[..., 3] = np.rint(coverage * 255).astype(np.uint8)
        result[result[..., 3] == 0, :3] = 0
        return pygame.image.frombytes(result.tobytes(), (width, height), "RGBA")

    grid_x, grid_y = np.meshgrid(
        np.arange(width, dtype=np.float32),
        np.arange(height, dtype=np.float32),
    )
    pixels = [rgba(cell) for cell in cells]
    gray = [flow_image(frame) for frame in pixels]
    output = []
    for index, cell in enumerate(cells):
        following = (index + 1) % len(cells)
        output.append(cell.copy())
        if np.array_equal(pixels[index], pixels[following]):
            output.extend(cell.copy() for _ in range(WALK_INBETWEENS))
            continue
        forward = motion(gray[index], gray[following])
        backward = motion(gray[following], gray[index])
        for step in range(1, WALK_INBETWEENS + 1):
            output.append(inbetween(
                pixels[index], pixels[following], forward, backward,
                step / (WALK_INBETWEENS + 1),
            ))
    return output
