import os
os.environ["KMP_DUPLICATE_LIB_OK"]="TRUE"

import shutil
import subprocess
import json
from utils.frames_process import FrameHandler
from utils.probability_creation import SaveEventDataAndProbabilities

import cv2
from tqdm import tqdm
from config import *
from ultralytics import YOLO
import numpy as np

# ----------  NEW:  find snap frame inside 1-second window ----------
def find_snap_frame(cap, huddle_model, start_frame, fps):
    """
    Returns the last frame BEFORE players start moving (snap).
    cap: opened cv2.VideoCapture
    huddle_model: your huddle-detection YOLO
    start_frame: csv / annot start-of-huddle
    fps: video fps
    """
    window = int(fps)                      # 1 second
    coarse_step = max(1, int(fps // 5))    # every 200 ms
    conf_thresh = 0.3
    min_num_players_required = 8

    # 1.  coarse search – huddle confidence drop
    candidates = []
    for offset in range(0, window, coarse_step):
        cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame + offset)
        ret, frm = cap.read()
        if not ret:
            break
        res = huddle_model(frm, verbose=False)[0]
        if len(res) < min_num_players_required:
            continue
        conf = res.boxes.conf.max().item() if res.boxes else 0.0
        candidates.append((start_frame + offset, conf))
    # last frame with conf > thresh
    last_high = None
    for frm, conf in candidates:
        if conf > conf_thresh:
            last_high = frm
        else:
            break
    if last_high is None:
        last_high = start_frame + window // 2   # fallback

    # 2.  fine search – optical-flow jump in ±½ second
    fine_window = int(fps // 2)
    flow_mag = []
    prev = None
    for frm_idx in range(last_high - fine_window, last_high + fine_window):
        cap.set(cv2.CAP_PROP_POS_FRAMES, frm_idx)
        ret, frm = cap.read()
        if not ret:
            break
        gray = cv2.cvtColor(frm, cv2.COLOR_BGR2GRAY)
        if prev is None:
            prev = gray
            continue
        flow = cv2.calcOpticalFlowFarneback(prev, gray, None, 0.5, 3, 15, 3, 5, 1.2, 0)
        mag, _ = cv2.cartToPolar(flow[..., 0], flow[..., 1])
        flow_mag.append((frm_idx, mag.mean()))
        prev = gray

    # largest jump
    if flow_mag:
        snap_frame, _ = max(flow_mag, key=lambda x: x[1])
        # snap_frame is the FIRST big motion → last *quiet* frame is one before
        return snap_frame - 1
    else:
        return last_high   # fallback
    
# ----------  convert to browser-playable H.264 ----------
def convert_to_h264(input_path, output_path):
    """Re-encode an OpenCV mp4v video to H.264 so browsers can play it."""
    subprocess.run([
        'ffmpeg', '-y', '-i', input_path,
        '-c:v', 'h264_videotoolbox', '-b:v', '5M',
        '-pix_fmt', 'yuv420p',
        '-movflags', '+faststart',
        output_path
    ], check=True, capture_output=True)
    os.remove(input_path)

# ---------------- helpers -----------------------
def iou(b1, b2):
    xA, yA = max(b1[0], b2[0]), max(b1[1], b2[1])
    xB, yB = min(b1[2], b2[2]), min(b1[3], b2[3])
    inter = max(0, xB - xA) * max(0, yB - yA)
    area1 = (b1[2] - b1[0]) * (b1[3] - b1[1])
    area2 = (b2[2] - b2[0]) * (b2[3] - b2[1])
    return inter / (area1 + area2 - inter + 1e-6)


def _assign_role_bands(id_to_side, id_to_initial_y):
    """
    Approximate position-groups (e.g., line/back/deep) per side by vertical bands
    from the first reliable labeled frame. Returns track_id -> band index.
    """
    side_to_ids = {"A": [], "D": []}
    for tid, side in id_to_side.items():
        if tid in id_to_initial_y:
            side_to_ids.setdefault(side, []).append(tid)

    id_to_band = {}
    for side, ids in side_to_ids.items():
        if not ids:
            continue
        ys = np.array([id_to_initial_y[i] for i in ids], dtype=float)
        q1 = float(np.quantile(ys, 0.33))
        q2 = float(np.quantile(ys, 0.66))
        for tid in ids:
            y = float(id_to_initial_y[tid])
            if y <= q1:
                id_to_band[tid] = 0
            elif y <= q2:
                id_to_band[tid] = 1
            else:
                id_to_band[tid] = 2
    return id_to_band

def track_players(csv_name):
    # ----------------  models  ------------------------------
    model = YOLO("./models/yolo11m.pt")          # tracker
    huddle_detection = YOLO("./models/best_huddle_detection.pt")
    yolo_model_path = './models/yolo26m.pt'
    tracker = "bytetrack.yaml"

    # ----------------  data loader  -------------------------
    move_annot_filepath = f'{MOVE_ANNOT_FOLDER}/{csv_name}'
    huddle_annot_filepath = f'{START_TIMES_ANNOT_FOLDER}/start times {csv_name}'
    frame_handler = FrameHandler(move_annot_filepath, huddle_annot_filepath, VIDEOS_DIR, yolo_model_path)

    # ----------------  video setup  -------------------------
    cap = cv2.VideoCapture(frame_handler.video_path)
    w, h, fps = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)), int(cap.get(cv2.CAP_PROP_FPS))

    os.makedirs('./results', exist_ok=True)
    output_video_raw = './results/tracked_video_raw.mp4'
    output_video_path = './results/tracked_video.mp4'
    heatmap_video_raw = './results/heatmap_video_raw.mp4'
    heatmap_video_path = './results/heatmap_video.mp4'
    out = cv2.VideoWriter(output_video_raw, cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))
    out_heatmap = cv2.VideoWriter(heatmap_video_raw, cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))

    # ----------------  main loop  ---------------------------
    moves_2_defenderCount_dict = {}
    moves_2_timeSincePlayBegan = {}
    tracked_timeline_segments = []
    output_frame_idx = 0

    # Loading start_frame to action_frame dict: {start_frame_number: [(action_tag, action_frame_num, down_number), ...], ...}
    for start_time_frame, moves in tqdm(frame_handler.huddle_to_moves_map.items()):
        if not moves:
            continue

        # 1) find exact snap frame inside 1-second window
        last_huddle_frame = find_snap_frame(cap, huddle_detection, start_time_frame, fps)
        last_frame  = moves[-1][1]
        play_source_start = None
        play_source_end = None
        play_output_start = output_frame_idx
        id_to_side = {}        # track_id -> "A" / "D"
        id_to_initial_y = {}   # track_id -> initial center y
        id_to_role_band = {}   # track_id -> band index (0/1/2)

        fine_window = int(fps // 2)

        frame_idx = start_time_frame - fine_window
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)

        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break

            # 2) label on snap frame
            if frame_idx == last_huddle_frame:
                snap_results = model.track(frame, imgsz=1280, conf=0.15, iou=0.5, persist=False, tracker=tracker, classes=[0], verbose=False)
                if snap_results[0].boxes.id is not None:
                    trk_boxes = snap_results[0].boxes.xyxy.cpu().numpy().astype(int)
                    trk_ids   = snap_results[0].boxes.id.cpu().numpy().astype(int)

                    hdl_res = huddle_detection(frame, verbose=False)[0]
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
                            iou_val = iou(tb, hb)
                            if iou_val > best_iou:
                                best_iou, best_side = iou_val, side
                        if best_iou > 0.3:
                            id_to_side[tid] = best_side
                            id_to_initial_y[tid] = float((tb[1] + tb[3]) / 2.0)
                id_to_role_band = _assign_role_bands(id_to_side, id_to_initial_y)

            # 3) continue tracking with locked labels
            results = model.track(frame, imgsz=1280, conf=0.15, iou=0.5, persist=True, tracker=tracker, classes=[0], verbose=False)

            # Draw bounding boxes on a copy of the frame for video output
            annotated = frame.copy()
            heatmap_frame = np.zeros((h, w, 3), dtype=np.uint8)
            if results[0].boxes.id is not None:
                boxes = results[0].boxes.xyxy.cpu().numpy().astype(int)
                ids   = results[0].boxes.id.cpu().numpy().astype(int)
                side_points = {"A": [], "D": []}
                for (x1, y1, x2, y2), tid in zip(boxes, ids):
                    side = id_to_side.get(tid)
                    cx = int((x1 + x2) / 2)
                    cy = int((y1 + y2) / 2)
                    if side is None:
                        colour, label = (255, 255, 255), f"UNK {tid}"
                    else:
                        colour = (0, 255, 0) if side == "A" else (0, 0, 255)
                        label  = f"{'ATT' if side == 'A' else 'DEF'} {tid}"
                    cv2.rectangle(annotated, (x1, y1), (x2, y2), colour, 2)
                    cv2.putText(annotated, label, (x1, y1 - 5),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.6, colour, 2)
                    if side is not None:
                        # Bigger solid markers for better visibility.
                        cv2.circle(heatmap_frame, (cx, cy), 8, colour, -1)
                        side_points[side].append((cx, cy))

                # Connect all players of the same side to each other (complete graph).
                for side, pts in side_points.items():
                    if len(pts) < 2:
                        continue
                    line_colour = (0, 255, 0) if side == "A" else (0, 0, 255)
                    for i in range(len(pts)):
                        for j in range(i + 1, len(pts)):
                            cv2.line(heatmap_frame, pts[i], pts[j], line_colour, 2, lineType=cv2.LINE_AA)
            out.write(annotated)
            out_heatmap.write(heatmap_frame)
            if play_source_start is None:
                play_source_start = frame_idx
            play_source_end = frame_idx
            output_frame_idx += 1

            action_tags = [tag for tag, frm, _ in moves if frm == frame_idx]
            down_nums = [down for _, frm, down in moves if frm == frame_idx]
            if action_tags:
                if results[0].boxes.id is not None:
                    defenders_count = list(id_to_side.values()).count('D')
                    for tag, down in zip(action_tags, down_nums):
                        # Save move to defender count in a dictionary
                        moves_2_defenderCount_dict[frame_idx] = (tag, defenders_count)    
                        # Time in frames (multiples of 60)
                        moves_2_timeSincePlayBegan[frame_idx] = (tag, frame_idx - start_time_frame, down)     

            if frame_idx >= last_frame + 60:
                break
            frame_idx += 1

        if play_source_start is not None and play_source_end is not None and output_frame_idx > play_output_start:
            tracked_timeline_segments.append({
                "source_start_frame": int(play_source_start),
                "source_end_frame": int(play_source_end),
                "tracked_start_frame": int(play_output_start),
                "tracked_end_frame": int(output_frame_idx - 1),
            })

    cap.release()
    out.release()
    out_heatmap.release()

    tracked_timeline_map_path = "./results/tracked_timeline_map.json"
    with open(tracked_timeline_map_path, "w", encoding="utf-8") as f:
        json.dump({
            "fps": int(fps),
            "segments": tracked_timeline_segments,
        }, f, indent=2)

    print("Converting tracked video to H.264 for browser playback...")
    convert_to_h264(output_video_raw, output_video_path)
    print("Converting heatmap video to H.264 for browser playback...")
    convert_to_h264(heatmap_video_raw, heatmap_video_path)
    print(f"saved → {output_video_path}")
    print(f"saved → {heatmap_video_path}")

    return moves_2_defenderCount_dict, moves_2_timeSincePlayBegan, output_video_path, heatmap_video_path, tracked_timeline_map_path

def print_line_to_fill_terminal(character='-'):
    """
    Prints a single character repeatedly to fill the entire width of the terminal.

    Args:
        character (str): The character to be printed. Defaults to '-'.
    """
    try:
        # Get the terminal width
        terminal_width = shutil.get_terminal_size().columns
        
        # Print the character repeated to fill the width
        print(character * terminal_width)
    except OSError:
        # Handle cases where terminal size cannot be determined (e.g., non-interactive environments)
        print("Warning: Could not determine terminal size. Printing a default line.")
        print(character * 80) # Print a default length line
    return


def process_from_app(csv_name):
    print(csv_name)
    moves_2_defenderCount_dict, moves_2_timeSincePlayBegan, tracked_video_path, heatmap_video_path, tracked_timeline_map_path = track_players(csv_name)
    
    print_line_to_fill_terminal()
    def_count_event_csv_filepath = './results/move_vs_defenders_events.csv'
    def_count_prob_json_filepath = './results/move_policy_by_defenderCount_bin.json'
    time_since_play_event_csv_filepath = './results/move_vs_timeSinceDownFrameCount.csv'
    time_since_play_prob_json_filepath = './results/move_policy_by_frameCountSincePlayStart_bin.json'

    # Defender count: groupby_header = "num_defenders"
    SaveEventDataAndProbabilities(groupby_header="num_defenders",
                                  events_dict=moves_2_defenderCount_dict,
                                  event_csv_filepath=def_count_event_csv_filepath,
                                  prob_json_filepath=def_count_prob_json_filepath)
    
    # Time Since Play Began: groupby_header = "TimeSincePlayBegan"
    SaveEventDataAndProbabilities(groupby_header="TimeSincePlayBegan",
                                  events_dict=moves_2_timeSincePlayBegan,
                                  event_csv_filepath=time_since_play_event_csv_filepath,
                                  prob_json_filepath=time_since_play_prob_json_filepath)

    return tracked_video_path, heatmap_video_path, tracked_timeline_map_path

# For Testing
if __name__ == '__main__':
    process_from_app('#14.csv')
    # process_from_app('#15.csv')
    # process_from_app('#16.csv')
    # process_from_app('#17.csv')
