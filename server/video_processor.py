import os
os.environ["KMP_DUPLICATE_LIB_OK"]="TRUE"

import shutil
# import json
from utils.file_handling import *
from utils.frames_process import FrameHandler
# from utils.track_processed import TrackProcessedCSVswithTimestamps
from utils.probability_creation import SaveEventDataAndProbabilities

from utils.file_handling import *
import cv2
# import numpy as np
from tqdm import tqdm
from config import *
from ultralytics import YOLO
# import matplotlib.pyplot as plt

# import torch
# from torchvision.models.resnet import resnet50, ResNet50_Weights # 18, 34 other options
# # from torchvision.models import densenet121, DenseNet121_Weights
# device = torch.device('cuda:0' if torch.cuda.is_available() else 'cpu')
# resnet = resnet50(weights=ResNet50_Weights.DEFAULT)
# resnet.fc = torch.nn.Identity() # Setting the fully connected (fc) layer to identity
# # densenet = densenet121(weights=DenseNet121_Weights.DEFAULT)
# # densenet.classifier = torch.nn.Identity()
# model = resnet
# model.to(device)

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
    
# ---------------- helpers -----------------------
def iou(b1, b2):
    xA, yA = max(b1[0], b2[0]), max(b1[1], b2[1])
    xB, yB = min(b1[2], b2[2]), min(b1[3], b2[3])
    inter = max(0, xB - xA) * max(0, yB - yA)
    area1 = (b1[2] - b1[0]) * (b1[3] - b1[1])
    area2 = (b2[2] - b2[0]) * (b2[3] - b2[1])
    return inter / (area1 + area2 - inter + 1e-6)

# --------------- player crop encoding ---------------

# def cnn_feature_extraction(img):
#     torch.cuda.empty_cache()        
#     # Prepare the image for inference
#     # img = cv2.cvtColor(img, cv2.COLOR_BGR2HSV_FULL)
#     img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

#     img = cv2.resize(img, dsize=(224,224), interpolation=cv2.INTER_NEAREST_EXACT)
#     img = np.expand_dims(np.moveaxis(img, -1, 0), 0)
#     img = torch.Tensor(img).to(device)
#     # Extract features
#     with torch.no_grad():
#         feats = model(img)
#     return feats.cpu()


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
    # output_video_name = "nfl_blitz_updated_tags_tracked.mp4"
    # out = cv2.VideoWriter(output_video_name, cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))

    # ----------------  main loop  ---------------------------
    moves_2_defenderCount_dict = {}
    moves_2_timeSincePlayBegan = {}

    # Loading start_frame to action_frame dict: {start_frame_number: [(action_tag, action_frame_num, down_number), ...], ...}
    for start_time_frame, moves in tqdm(frame_handler.huddle_to_moves_map.items()):
        if not moves:
            continue

        # 1) find exact snap frame inside 1-second window
        last_huddle_frame = find_snap_frame(cap, huddle_detection, start_time_frame, fps)
        first_frame = start_time_frame
        last_frame  = moves[-1][1]
        id_to_side = {}        # track_id -> "A" / "D"

        # if show_trail_in_heatmap:
        #     heat_map = np.zeros((h, w, 3), dtype=np.uint8)  # black at start of each play

        fine_window = int(fps // 2)

        frame_idx = start_time_frame - fine_window
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)

        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break

            # 2) label on snap frame
            if frame_idx == last_huddle_frame:
                results = model.track(frame, imgsz=1280, conf=0.15, iou=0.5, persist=False, tracker=tracker, classes=[0], verbose=False)
                if results[0].boxes.id is not None:
                    trk_boxes = results[0].boxes.xyxy.cpu().numpy().astype(int)
                    trk_ids   = results[0].boxes.id.cpu().numpy().astype(int)

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

            # 3) continue tracking with locked labels
            results = model.track(frame, imgsz=1280, conf=0.15, iou=0.5, persist=True, tracker=tracker, classes=[0], verbose=False)
            
            action_tags = [tag for tag, frm, _ in moves if frm == frame_idx]
            down_nums = [down for _, frm, down in moves if frm == frame_idx]
            if action_tags:
                if results[0].boxes.id is not None:
                    # boxes = results[0].boxes.xyxy.cpu().numpy().astype(int)
                    # ids   = results[0].boxes.id.cpu().numpy().astype(int)
                    defenders_count = list(id_to_side.values()).count('D')
                    for tag, down in zip(action_tags, down_nums):
                        # Save move to defender count in a dictionary
                        moves_2_defenderCount_dict[frame_idx] = (tag, defenders_count)    
                        # Time in seconds (whole numbers) 
                        # moves_2_timeSincePlayBegan[move_frame_number] = (action_tag, round((move_frame_number - start_time_frame)/fps, 3), down_number)
                        # Time in frames (multiples of 60)
                        moves_2_timeSincePlayBegan[frame_idx] = (tag, frame_idx - start_time_frame, down)     

            if frame_idx >= last_frame + 60:
                break
            frame_idx += 1

    cap.release()
    # out.release()
    # heat_out.release()   # ### NEW ###  close heat-map writer
    # print(f"saved → {output_video_name}")
    # print(f"saved → {heat_video_name}")   # ### NEW ###
    return moves_2_defenderCount_dict, moves_2_timeSincePlayBegan

# def temp_save_processed_frames(team_representations: TeamRepresentationLearning):
#     for frame in team_representations.huddle_frames:

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
    # processed = TrackProcessedCSVswithTimestamps(csv_name).processed
    # if processed:
    #     return
    
    # move_annot_filepath = f'./data/Annotations/actions/{csv_name}'
    # huddle_annot_filepath = f'./data/Annotations/start_times/start times {csv_name}'
    # VIDEOS_DIR = './data/videos/'
    # # yolo_model_path = './models/yolo11m.pt'
    # yolo_model_path = './models/yolo26m.pt'
    
    # print_line_to_fill_terminal()
    # frame_handler = FrameHandler(move_annot_filepath, huddle_annot_filepath, VIDEOS_DIR, yolo_model_path)
    # if not frame_handler.video_exists_on_yt:
    #     return 
    
    # print_line_to_fill_terminal()
    # print_line_to_fill_terminal()
    # print('Extracting relevant information from the video')
    moves_2_defenderCount_dict, moves_2_timeSincePlayBegan = track_players(csv_name)
    
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

# For Testing
if __name__ == '__main__':
    process_from_app('#14.csv')
    # process_from_app('#15.csv')
    # process_from_app('#16.csv')
    # process_from_app('#17.csv')
