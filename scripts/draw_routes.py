import cv2
import os

def main():
    ref_path = "data/example_reference.jpg"
    out_path = "data/reference_with_routes.jpg"
    
    img = cv2.imread(ref_path)
    h, w = img.shape[:2]
    
    positive_route = [
        (w // 4, h // 4),
        (w // 2, h // 2),
        (3 * w // 4, 3 * h // 4)
    ]
    
    negative_route = [
        (w // 4, 3 * h // 4),
        (w // 2, h // 4),
        (3 * w // 4, h // 4)
    ]
    
    # Draw Positive Route (Green)
    for i in range(len(positive_route)):
        pt1 = positive_route[i]
        cv2.circle(img, pt1, radius=20, color=(0, 255, 0), thickness=-1)
        cv2.putText(img, f"Pos WP{i+1}", (pt1[0]+30, pt1[1]-30), cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0, 255, 0), 3)
        if i > 0:
            pt0 = positive_route[i-1]
            cv2.line(img, pt0, pt1, (0, 255, 0), thickness=5)
            
    # Draw Negative Route (Red)
    for i in range(len(negative_route)):
        pt1 = negative_route[i]
        cv2.circle(img, pt1, radius=20, color=(0, 0, 255), thickness=-1)
        cv2.putText(img, f"Neg WP{i+1}", (pt1[0]+30, pt1[1]-30), cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0, 0, 255), 3)
        if i > 0:
            pt0 = negative_route[i-1]
            cv2.line(img, pt0, pt1, (0, 0, 255), thickness=5)
            
    cv2.imwrite(out_path, img)
    print(f"Saved route map to {out_path}")

if __name__ == "__main__":
    main()
