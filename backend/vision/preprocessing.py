import cv2

def display_frame(frame, max_width=1920):
    if frame.shape[1]>max_width:
        frame=cv2.resize(frame,(max_width,round(frame.shape[0]*max_width/frame.shape[1])))
    return frame
