from utils.file_handling import *
from utils.frames_process import FrameHandler
from team_learning_and_detection import TeamRepresentationLearning

# def temp_save_processed_frames(team_representations: TeamRepresentationLearning):
#     for frame in team_representations.huddle_frames:



def process_from_app(csv_name):
    print(csv_name)
    move_annot_filepath = f'./data/Annotations/actions/{csv_name}'
    huddle_annot_filepath = f'./data/Annotations/start_times/start times {csv_name}'
    VIDEOS_DIR = './data/videos/'
    yolo_model_path = './models/yolo11m.pt'

    frame_handler = FrameHandler(move_annot_filepath, huddle_annot_filepath, VIDEOS_DIR, yolo_model_path)
    huddle_frames = frame_handler.huddle_frames

    team_representations = TeamRepresentationLearning(huddle_frames, yolo_model_path)

    return



    
