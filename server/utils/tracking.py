import os
import cv2
import json
import numpy as np
from tqdm import tqdm
from ultralytics import YOLO

from config import *
from utils.frames_process import FrameHandler
from utils.h264_conversion import convert_to_h264

class Tracking:
    def __init__(self, csv_name, frame_handler: FrameHandler):
        # ------------------------------  models  ------------------------------
        # Tracking config and init
        self.track_model = YOLO("./models/yolo11m.pt")          # tracker
        self.track_img_size = 1280
        self.track_conf = 0.15
        self.track_iou = 0.5
        self.huddle_detection_model = YOLO("./models/best_huddle_detection.pt")
        self.tracker = "./models/my_bytetrack.yaml"

        self.frame_handler = frame_handler

    def initialize_video_handling(self):
        self.cap = cv2.VideoCapture(self.frame_handler.video_path)
        self.w, self.h, self.fps = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT)), int(self.cap.get(cv2.CAP_PROP_FPS))

        os.makedirs('./results', exist_ok=True)
        self.output_video_raw = './results/tracked_video_raw.mp4'
        self.output_video_path = './results/tracked_video.mp4'
        self.heatmap_video_raw = './results/heatmap_video_raw.mp4'
        self.heatmap_video_path = './results/heatmap_video.mp4'
        self.out = cv2.VideoWriter(self.output_video_raw, cv2.VideoWriter_fourcc(*"mp4v"), self.fps, (self.w, self.h))
        self.out_heatmap = cv2.VideoWriter(self.heatmap_video_raw, cv2.VideoWriter_fourcc(*"mp4v"), self.fps, (self.w, self.h))
        return
    
    def iou(self, b1, b2):
        xA, yA = max(b1[0], b2[0]), max(b1[1], b2[1])
        xB, yB = min(b1[2], b2[2]), min(b1[3], b2[3])
        inter = max(0, xB - xA) * max(0, yB - yA)
        area1 = (b1[2] - b1[0]) * (b1[3] - b1[1])
        area2 = (b2[2] - b2[0]) * (b2[3] - b2[1])
        return inter / (area1 + area2 - inter + 1e-6)
    
    def track_in_each_play(self):
        self.initialize_video_handling()

        def initialize_tracking_tags():
            """
            Processes the huddle frame where it assigns tags (A:Attack, D:Defence) to each detection from the tracking algorithm
            """
            nonlocal snap_results, id_to_side, id_to_initial_y 
            if snap_results[0].boxes.id is not None:
                trk_boxes = snap_results[0].boxes.xyxy.cpu().numpy().astype(int)
                trk_ids   = snap_results[0].boxes.id.cpu().numpy().astype(int)
                hdl_res = self.huddle_detection_model(frame, verbose=False)[0]
                hdl_boxes = []
                for b in hdl_res.boxes:
                    xyxy = b.xyxy[0].cpu().numpy().astype(int)
                    cls  = int(b.cls[0])          # 0 = attacker, 1 = defender
                    side = "A" if cls == 0 else "D"
                    hdl_boxes.append((xyxy, side))

                # match huddle boxes to track IDs via IOU
                for (tb, tid) in zip(trk_boxes, trk_ids):
                    best_iou, best_side = 0, None
                    for hb, side in hdl_boxes:
                        iou_val = self.iou(tb, hb)
                        if iou_val > best_iou:
                            best_iou, best_side = iou_val, side
                    if best_iou > 0.3:
                        id_to_side[tid] = best_side
                        id_to_initial_y[tid] = float((tb[1] + tb[3]) / 2.0)
            return 
        
        def draw_tracking_results():
            nonlocal results, annotated_frame, heatmap_frame
            if results[0].boxes.id is not None:
                boxes = results[0].boxes.xyxy.cpu().numpy().astype(int)
                ids   = results[0].boxes.id.cpu().numpy().astype(int)
                team_side_coordinates = {"A": [], "D": []}
                for (x1, y1, x2, y2), tid in zip(boxes, ids):
                    side = id_to_side.get(tid)
                    cx = int((x1 + x2) / 2)
                    cy = int((y1 + y2) / 2)
                    if side is None:
                        colour, label = (255, 255, 255), f"UNK {tid}"
                    else:
                        colour = (0, 255, 0) if side == "A" else (0, 0, 255)
                        label  = f"{'ATT' if side == 'A' else 'DEF'} {tid}"
                    cv2.rectangle(annotated_frame, (x1, y1), (x2, y2), colour, 2)
                    cv2.putText(annotated_frame, label, (x1, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.6, colour, 2)
                    if side is not None:
                        # Bigger solid markers for better visibility.
                        cv2.circle(heatmap_frame, (cx, cy), 7, colour, -1)
                        team_side_coordinates[side].append((cx, cy))

                # Connect all players of the same side to each other (complete graph).
                for side, pts in team_side_coordinates.items():
                    if len(pts) < 2:
                        continue
                    line_colour = (0, 255, 0) if side == "A" else (0, 0, 255)
                    for i in range(len(pts)):
                        for j in range(i + 1, len(pts)):
                            cv2.line(heatmap_frame, pts[i], pts[j], line_colour, 2, lineType=cv2.LINE_AA)
            return

        moves_2_defenderCount_dict = {}
        moves_2_timeSincePlayBegan = {}
        tracked_timeline_segments = []
        output_frame_idx = 0

        # Loading start_frame to action_frame dict: {start_frame_number: [(action_tag, action_frame_num, down_number), ...], ...}
        for start_time_frame, moves in tqdm(self.frame_handler.huddle_to_moves_map.items()):
            if not moves:
                continue
            
            last_frame  = moves[-1][1] # To end tracking
            
            # Variables to track frame counts and finally map timestamps from original video to tracked video
            play_source_start = None
            play_source_end = None
            play_output_start = output_frame_idx

            # Dictionaries to track attacker and defender tracks
            ##### Will use these to extend tracking to handle unknown tracks
            id_to_side = {}        # track_id -> "A" / "D"
            id_to_initial_y = {}   # track_id -> initial center y
            # id_to_role_band = {}   # track_id -> band index (0/1/2)

            fine_window = int(self.fps // 2)
            frame_idx = start_time_frame - fine_window
            
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)

            while self.cap.isOpened():
                ret, frame = self.cap.read()
                if not ret:
                    break
  
                # ----------------- 1) label on snap frame -----------------
                if frame_idx == start_time_frame:
                    snap_results = self.track_model.track(frame, imgsz=self.track_img_size, conf=self.track_conf, iou=self.track_iou, 
                                                          persist=False, tracker=self.tracker, classes=[0], verbose=False)
                    initialize_tracking_tags()
                    
                # ----------------- 2) continue tracking with locked labels -----------------
                results = self.track_model.track(frame, imgsz=self.track_img_size, conf=self.track_conf, iou=self.track_iou, 
                                                 persist=True, tracker=self.tracker, classes=[0], verbose=False)

                # ----------------- Draw bounding boxes on a copy of the frame for video output -----------------
                annotated_frame = frame.copy()
                heatmap_frame = np.zeros((self.h, self.w, 3), dtype=np.uint8)

                draw_tracking_results()
                
                self.out.write(annotated_frame)
                self.out_heatmap.write(heatmap_frame)

                # ----------------- Tracking frame counts to map from original video to cropped tracked video ----------------- 
                if play_source_start is None:
                    play_source_start = frame_idx
                play_source_end = frame_idx
                output_frame_idx += 1

                # ----------------- Storing info from tracking for Probability Distribution ----------------- 
                action_tags = [tag for tag, frm, _ in moves if frm == frame_idx]
                down_nums = [down for _, frm, down in moves if frm == frame_idx]
                if action_tags:
                    if results[0].boxes.id is not None:
                        defenders_count = list(id_to_side.values()).count('D')
                        for tag, down in zip(action_tags, down_nums):
                            moves_2_defenderCount_dict[frame_idx] = (tag, defenders_count)  # Save move to defender count in a dictionary    
                            moves_2_timeSincePlayBegan[frame_idx] = (tag, frame_idx - start_time_frame, down) # Time in frames
                
                # Track till a second after the beginning of the last action of the play
                if frame_idx >= last_frame + self.fps:
                    break
                frame_idx += 1
            
            # ----------------- Mapping timestamps (via frame count) from original video to cropped tracked video ----------------- 
            if play_source_start is not None and play_source_end is not None and output_frame_idx > play_output_start:
                tracked_timeline_segments.append({
                    "source_start_frame": int(play_source_start),
                    "source_end_frame": int(play_source_end),
                    "tracked_start_frame": int(play_output_start),
                    "tracked_end_frame": int(output_frame_idx - 1),
                })
            
            # Reset tracker for following play
            self.track_model.predictor.trackers[0].reset()
        
        # Release all videos to save them
        self.cap.release()
        self.out.release()
        self.out_heatmap.release()

        # ----------------- Saving the Timestamps Map from original video to cropped tracked video for frontend ----------------- 
        tracked_timeline_map_path = "./results/tracked_timeline_map.json"
        with open(tracked_timeline_map_path, "w", encoding="utf-8") as f:
            json.dump({
                "fps": int(self.fps),
                "segments": tracked_timeline_segments,
            }, f, indent=2)

        print("Converting tracked video to H.264 for browser playback...")
        convert_to_h264(self.output_video_raw, self.output_video_path)
        print("Converting heatmap video to H.264 for browser playback...")
        convert_to_h264(self.heatmap_video_raw, self.heatmap_video_path)
        print(f"Saved → {self.output_video_path}")
        print(f"Saved → {self.heatmap_video_path}")

        return moves_2_defenderCount_dict, moves_2_timeSincePlayBegan, self.output_video_path, self.heatmap_video_path, tracked_timeline_map_path


#### Original function
# def track_players(csv_name):
#     # ----------------  models  ------------------------------
#     model = YOLO("./models/yolo11m.pt")          # tracker
#     huddle_detection = YOLO("./models/best_huddle_detection.pt")
#     yolo_model_path = './models/yolo11m.pt'
#     tracker = "./models/my_bytetrack.yaml"

#     # ----------------  data loader  -------------------------
#     move_annot_filepath = f'{MOVE_ANNOT_FOLDER}/{csv_name}'
#     huddle_annot_filepath = f'{START_TIMES_ANNOT_FOLDER}/start times {csv_name}'
#     frame_handler = FrameHandler(move_annot_filepath, huddle_annot_filepath, VIDEOS_DIR, yolo_model_path)

#     # ----------------  video setup  -------------------------
#     cap = cv2.VideoCapture(frame_handler.video_path)
#     w, h, fps = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)), int(cap.get(cv2.CAP_PROP_FPS))

#     os.makedirs('./results', exist_ok=True)
#     output_video_raw = './results/tracked_video_raw.mp4'
#     output_video_path = './results/tracked_video.mp4'
#     heatmap_video_raw = './results/heatmap_video_raw.mp4'
#     heatmap_video_path = './results/heatmap_video.mp4'
#     out = cv2.VideoWriter(output_video_raw, cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))
#     out_heatmap = cv2.VideoWriter(heatmap_video_raw, cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))

#     # ----------------  main loop  ---------------------------
#     moves_2_defenderCount_dict = {}
#     moves_2_timeSincePlayBegan = {}
#     tracked_timeline_segments = []
#     output_frame_idx = 0

#     # Loading start_frame to action_frame dict: {start_frame_number: [(action_tag, action_frame_num, down_number), ...], ...}
#     for start_time_frame, moves in tqdm(frame_handler.huddle_to_moves_map.items()):
#         if not moves:
#             continue

#         # 1) find exact snap frame inside 1-second window
#         last_huddle_frame = start_time_frame
#         last_frame  = moves[-1][1]
#         play_source_start = None
#         play_source_end = None
#         play_output_start = output_frame_idx
#         id_to_side = {}        # track_id -> "A" / "D"
#         id_to_initial_y = {}   # track_id -> initial center y
#         # id_to_role_band = {}   # track_id -> band index (0/1/2)

#         fine_window = int(fps // 2)
#         frame_idx = start_time_frame - fine_window
        
#         cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)

#         while cap.isOpened():
#             ret, frame = cap.read()
#             if not ret:
#                 break

#             # 2) label on snap frame
#             if frame_idx == last_huddle_frame:
#                 snap_results = model.track(frame, imgsz=1280, conf=0.15, iou=0.5, persist=False, tracker=tracker, classes=[0], verbose=False)
#                 if snap_results[0].boxes.id is not None:
#                     trk_boxes = snap_results[0].boxes.xyxy.cpu().numpy().astype(int)
#                     trk_ids   = snap_results[0].boxes.id.cpu().numpy().astype(int)

#                     hdl_res = huddle_detection(frame, verbose=False)[0]
#                     hdl_boxes = []
#                     for b in hdl_res.boxes:
#                         xyxy = b.xyxy[0].cpu().numpy().astype(int)
#                         cls  = int(b.cls[0])          # 0 = attacker, 1 = defender
#                         side = "A" if cls == 0 else "D"
#                         hdl_boxes.append((xyxy, side))

#                     # match huddle boxes to track IDs via IOU
#                     for (tb, tid) in zip(trk_boxes, trk_ids):
#                         best_iou, best_side = 0, None
#                         for hb, side in hdl_boxes:
#                             iou_val = iou(tb, hb)
#                             if iou_val > best_iou:
#                                 best_iou, best_side = iou_val, side
#                         if best_iou > 0.3:
#                             id_to_side[tid] = best_side
#                             id_to_initial_y[tid] = float((tb[1] + tb[3]) / 2.0)
#                 # id_to_role_band = _assign_role_bands(id_to_side, id_to_initial_y)

#             # 3) continue tracking with locked labels
#             results = model.track(frame, imgsz=1280, conf=0.15, iou=0.5, persist=True, tracker=tracker, classes=[0], verbose=False)

#             # Draw bounding boxes on a copy of the frame for video output
#             annotated = frame.copy()
#             heatmap_frame = np.zeros((h, w, 3), dtype=np.uint8)
#             if results[0].boxes.id is not None:
#                 boxes = results[0].boxes.xyxy.cpu().numpy().astype(int)
#                 ids   = results[0].boxes.id.cpu().numpy().astype(int)
#                 side_points = {"A": [], "D": []}
#                 for (x1, y1, x2, y2), tid in zip(boxes, ids):
#                     side = id_to_side.get(tid)
#                     cx = int((x1 + x2) / 2)
#                     cy = int((y1 + y2) / 2)
#                     if side is None:
#                         colour, label = (255, 255, 255), f"UNK {tid}"
#                     else:
#                         colour = (0, 255, 0) if side == "A" else (0, 0, 255)
#                         label  = f"{'ATT' if side == 'A' else 'DEF'} {tid}"
#                     cv2.rectangle(annotated, (x1, y1), (x2, y2), colour, 2)
#                     cv2.putText(annotated, label, (x1, y1 - 5),
#                                 cv2.FONT_HERSHEY_SIMPLEX, 0.6, colour, 2)
#                     if side is not None:
#                         # Bigger solid markers for better visibility.
#                         cv2.circle(heatmap_frame, (cx, cy), 7, colour, -1)
#                         side_points[side].append((cx, cy))

#                 # Connect all players of the same side to each other (complete graph).
#                 for side, pts in side_points.items():
#                     if len(pts) < 2:
#                         continue
#                     line_colour = (0, 255, 0) if side == "A" else (0, 0, 255)
#                     for i in range(len(pts)):
#                         for j in range(i + 1, len(pts)):
#                             cv2.line(heatmap_frame, pts[i], pts[j], line_colour, 2, lineType=cv2.LINE_AA)
#             out.write(annotated)
#             out_heatmap.write(heatmap_frame)
#             if play_source_start is None:
#                 play_source_start = frame_idx
#             play_source_end = frame_idx
#             output_frame_idx += 1

#             action_tags = [tag for tag, frm, _ in moves if frm == frame_idx]
#             down_nums = [down for _, frm, down in moves if frm == frame_idx]
#             if action_tags:
#                 if results[0].boxes.id is not None:
#                     defenders_count = list(id_to_side.values()).count('D')
#                     for tag, down in zip(action_tags, down_nums):
#                         # Save move to defender count in a dictionary
#                         moves_2_defenderCount_dict[frame_idx] = (tag, defenders_count)    
#                         # Time in frames (multiples of 60)
#                         moves_2_timeSincePlayBegan[frame_idx] = (tag, frame_idx - start_time_frame, down)     

#             if frame_idx >= last_frame + 60:
#                 break
#             frame_idx += 1

#         if play_source_start is not None and play_source_end is not None and output_frame_idx > play_output_start:
#             tracked_timeline_segments.append({
#                 "source_start_frame": int(play_source_start),
#                 "source_end_frame": int(play_source_end),
#                 "tracked_start_frame": int(play_output_start),
#                 "tracked_end_frame": int(output_frame_idx - 1),
#             })

#     cap.release()
#     out.release()
#     out_heatmap.release()

#     tracked_timeline_map_path = "./results/tracked_timeline_map.json"
#     with open(tracked_timeline_map_path, "w", encoding="utf-8") as f:
#         json.dump({
#             "fps": int(fps),
#             "segments": tracked_timeline_segments,
#         }, f, indent=2)

#     print("Converting tracked video to H.264 for browser playback...")
#     convert_to_h264(output_video_raw, output_video_path)
#     print("Converting heatmap video to H.264 for browser playback...")
#     convert_to_h264(heatmap_video_raw, heatmap_video_path)
#     print(f"saved → {output_video_path}")
#     print(f"saved → {heatmap_video_path}")

#     return moves_2_defenderCount_dict, moves_2_timeSincePlayBegan, output_video_path, heatmap_video_path, tracked_timeline_map_path