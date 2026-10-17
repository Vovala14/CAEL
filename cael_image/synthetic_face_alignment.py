"""Blind classical alignment of supplied synthetic tensors; no file discovery."""
import itertools
import numpy as np
import torch

from .portrait_appearance import align_similarity


def align_synthetic_faces(images):
    import cv2
    face_detector = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
    eye_detector = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_eye_tree_eyeglasses.xml')
    detections = []
    face_boxes = []
    for index, tensor in enumerate(images):
        rgb = tensor.numpy()
        size = rgb.shape[0]
        grey = cv2.equalizeHist(cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY))
        faces = face_detector.detectMultiScale(grey, 1.05, 5, minSize=(24, 24))
        if not len(faces):
            continue
        x, y, width, height = max(faces, key=lambda box: box[2] * box[3])
        face_boxes.append((index, float(x + width / 2), float(y + height / 2), float(width)))
        roi = grey[y:y + int(height * .65), x:x + width]
        enlarged = cv2.resize(roi, None, fx=3, fy=3)
        eyes = eye_detector.detectMultiScale(enlarged, 1.05, 4, minSize=(max(9, int(width * .3)),) * 2)
        options = []
        for first, second in itertools.combinations(eyes, 2):
            left, right = sorted([first, second], key=lambda box: box[0])
            p = np.array([left[0] + left[2] / 2, left[1] + left[3] / 2]) / 3 + [x, y]
            q = np.array([right[0] + right[2] / 2, right[1] + right[3] / 2]) / 3 + [x, y]
            dx, dy = q - p
            centre = (p + q) / 2
            if (.25 * width <= dx <= .65 * width and abs(dy) <= .3 * dx and
                    x + .3 * width <= centre[0] <= x + .7 * width and y + .12 * height <= centre[1] <= y + .6 * height):
                options.append((abs(dy) / max(dx, 1) + abs(dx / width - .4), p, q))
        if options:
            _, left, right = min(options, key=lambda row: row[0])
            detections.append((index, left, right))
    if len(detections) < 24:
        if len(face_boxes) >= 24:
            cx, cy, width = np.median(np.array([row[1:] for row in face_boxes]), axis=0)
            target_left, target_right = [cx - width / 4, cy], [cx + width / 4, cy]
            output = [align_similarity(images[index].numpy(), [x - span / 4, y], [x + span / 4, y],
                                       target_left, target_right, output_size=images.shape[1])
                      for index, x, y, span in face_boxes]
            return torch.stack(output), [row[0] for row in face_boxes], dict(applied=True, method='Classical face-box similarity fallback',
                    accepted_eye_pairs=len(detections), accepted_faces=len(face_boxes), target_left=list(target_left),
                    target_right=list(target_right), target_estimated_from_fitting_only=True)
        return images, list(range(len(images))), dict(applied=False, accepted_eye_pairs=len(detections), reason='Too few verified pairs; no alignment')
    left = np.median(np.stack([row[1] for row in detections]), axis=0)
    right = np.median(np.stack([row[2] for row in detections]), axis=0)
    left[1] = right[1] = (left[1] + right[1]) / 2
    output = [align_similarity(images[index].numpy(), p, q, left, right, output_size=images.shape[1]) for index, p, q in detections]
    return torch.stack(output), [index for index, _, _ in detections], dict(applied=True, accepted_eye_pairs=len(detections),
                                                                         method='Classical verified-eye similarity alignment',
                                                                         target_left=left.tolist(), target_right=right.tolist(),
                                                                         target_estimated_from_fitting_only=True)
