import shutil
import json
from utils.file_handling import *
from utils.frames_process import FrameHandler
from utils.track_processed import TrackProcessedCSVswithTimestamps
from team_learning_and_detection import TeamRepresentationLearning
from utils.probability_creation import SaveEventDataAndProbabilities

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

def process_from_app(csv_name):
    print(csv_name)
    processed = TrackProcessedCSVswithTimestamps(csv_name).processed
    if processed:
        return
    
    move_annot_filepath = f'./data/Annotations/actions/{csv_name}'
    huddle_annot_filepath = f'./data/Annotations/start_times/start times {csv_name}'
    VIDEOS_DIR = './data/videos/'
    yolo_model_path = './models/yolo11m.pt'
    
    print_line_to_fill_terminal()
    frame_handler = FrameHandler(move_annot_filepath, huddle_annot_filepath, VIDEOS_DIR, yolo_model_path)
    if not frame_handler.video_exists_on_yt:
        return 
    
    print_line_to_fill_terminal()
    huddle_frames = frame_handler.huddle_frames
    team_representations = TeamRepresentationLearning(huddle_frames, yolo_model_path)
    
    print_line_to_fill_terminal()
    print('Extracting relevant information from the video')
    moves_2_defenderCount_dict, moves_2_timeSincePlayBegan = frame_handler.analyze_move_frames(team_representations)
    
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
    
    return

# For Testing
if __name__ == '__main__':
    process_from_app('#1.csv')



    
