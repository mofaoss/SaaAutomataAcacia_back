import cv2
import numpy as np


def add_noise(image, noise_factor=0.01):
    noise = np.random.normal(0, 1, image.shape) * noise_factor
    noisy_image = np.clip(image + noise, 0, 255).astype(np.uint8)
    return noisy_image


def count_color_blocks(image, lower_color, upper_color, preview=False):
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, lower_color, upper_color)

    if preview:
        masked_img = cv2.bitwise_and(image, image, mask=mask)
        cv2.imshow("Mask Preview", masked_img)
        cv2.waitKey(0)

    contours, _ = cv2.findContours(mask, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    return len(contours)


def rgb_to_opencv_hsv(r, g, b):
    rgb_color = np.uint8([[[b, g, r]]])
    hsv_color = cv2.cvtColor(rgb_color, cv2.COLOR_BGR2HSV)
    return hsv_color[0][0]


def get_hsv(target_rgb):
    h, s, v = rgb_to_opencv_hsv(*target_rgb)

    h_tolerance = 2
    s_tolerance = 35
    v_tolerance = 10

    lower_color = np.array([max(0, h - h_tolerance), max(0, s - s_tolerance), max(0, v - v_tolerance)])
    upper_color = np.array([min(179, h + h_tolerance), min(255, s + s_tolerance), min(255, v + v_tolerance)])

    print(f"Lower HSV: {lower_color}")
    print(f"Upper HSV: {upper_color}")
