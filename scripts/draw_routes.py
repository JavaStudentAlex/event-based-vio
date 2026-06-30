from itertools import pairwise

import cv2


def _routes(width, height):
    positive_route = [(width // 4, height // 4), (width // 2, height // 2), (3 * width // 4, 3 * height // 4)]
    negative_route = [(width // 4, 3 * height // 4), (width // 2, height // 4), (3 * width // 4, height // 4)]
    return positive_route, negative_route


def _draw_route_points(img, route, label_prefix, color):
    for i, point in enumerate(route, start=1):
        cv2.circle(img, point, radius=20, color=color, thickness=-1)
        cv2.putText(
            img,
            f"{label_prefix} WP{i}",
            (point[0] + 30, point[1] - 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            1.5,
            color,
            3,
        )


def _draw_route_segments(img, route, color):
    for start, end in pairwise(route):
        cv2.line(img, start, end, color, thickness=5)


def _draw_route(img, route, label_prefix, color):
    _draw_route_points(img, route, label_prefix, color)
    _draw_route_segments(img, route, color)


def main():
    out_path = "data/reference_with_routes.jpg"
    img = cv2.imread("data/example_reference.jpg")
    h, w = img.shape[:2]
    positive_route, negative_route = _routes(w, h)

    _draw_route(img, positive_route, "Pos", (0, 255, 0))
    _draw_route(img, negative_route, "Neg", (0, 0, 255))
    cv2.imwrite(out_path, img)
    print(f"Saved route map to {out_path}")


if __name__ == "__main__":
    main()
