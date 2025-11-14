import os
import pandas as pd
import yt_dlp

class CSVVideoInfoProcessor:
    def __init__(self, move_annot_filepath, huddle_annot_filepath, VIDEOS_DIR):
        '''
            Loads the csv file, processes it, and downloads the youtube video required 
            Args:
                file_path (str): Path to the CSV file
                VIDEOS_DIR (str): Path to video downloads
        '''
        self.move_annot_filepath = move_annot_filepath
        self.huddle_annot_filepath = huddle_annot_filepath
        self.VIDEOS_DIR = VIDEOS_DIR
        self.video_url = None
        self.csv_data = None
        self.video_path = None
        self.video_name = None
        self.move_annotations = self.process_csv(self.move_annot_filepath)
        self.huddle_annotations = self.process_csv(self.huddle_annot_filepath)
        self.video_exists_on_yt = self.download_youtube_video()
        return
    
    def open_csv(self, file_path):
        file_extension = file_path.split('.')[-1]
        if file_extension == 'xlsx':
            df = pd.read_excel(file_path, engine='openpyxl', header=None)
        elif file_extension == 'xls':
            df = pd.read_excel(file_path, header=None)
        elif file_extension == 'csv':
            df = pd.read_csv(file_path, header=None)
        else:
            raise ValueError("Unsupported file format. Please provide an Excel or CSV file.")
        
        return df

    # Function to open Excel or CSV file and extract video URL and annotations
    def process_csv(self, file_path=None):
        '''
            Loads the excel to a dataframe, slices the dataframe to extract the video URL and move annotations.
            Returns the URL and annotations separately
            Args:
                file_path (str): Path to the CSV file
            Returns:
                str: URL of the YouTube video to download
                pd dataframe: video_annotations with appropriate headers for the annotation data
        '''

        self.csv_data = self.open_csv(file_path)
        df = self.csv_data
        
        blank_row_index = df[df[0].isna()].index[0]
        video_info = df.iloc[:blank_row_index]
        video_info = video_info.set_index(0).T  # Make keys columns (transpose)
        video_info.columns = [col.replace(' ', '') for col in video_info.columns]
        video_url = video_info['LINK-'].values[0]

        # Set new header and trim dataframe
        annotations = df.iloc[blank_row_index + 2:]
        annotations.columns = df.iloc[blank_row_index + 1].values  # Set the first row as header
        annotations = annotations.reset_index(drop=True)
        
        self.video_url = video_url
        return annotations
    
    
    # Function to download YouTube video
    def download_youtube_video(self):
        '''
            Downloads a YouTube video using yt-dlp and saves it to the specified directory.
            If the video is already downloaded, it will not download it again.
            Returns the path to the downloaded video file.
            Args:
                url (str): The URL of the YouTube video to download.
                download_dir (str): The directory where the video will be saved.
            Returns:
                True or False (bool): Success or failure 
        '''

        print(f"Video URL: {self.video_url}")

        if self.video_url.__contains__('?'):
            self.video_name = self.video_url.split('/')[-1].split('?')[0]
        else:
            self.video_name = self.video_url.split('/')[-1]
        self.video_path = f'{self.VIDEOS_DIR}/{self.video_name}.mp4'
        if os.path.exists(self.video_path):
            print(f"Video already exists at {self.video_path}. Skipping download.")
            return True
        
        ydl_opts = {
            'outtmpl': os.path.join(self.VIDEOS_DIR, '%(id)s.%(ext)s'),
            'format': 'bestvideo+bestaudio/best',
            'merge_output_format': 'mp4',
            'quiet': True,
        }
        # try:
        #     with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        #         info = ydl.extract_info(self.video_url, download=False)
        #         video_path = ydl.prepare_filename(info)
        #         if not video_path.endswith('.mp4'):
        #             video_path = os.path.splitext(video_path)[0] + '.mp4'
        #         if os.path.exists(video_path):
        #             print(f"Video already exists at {video_path}. Skipping download.")
        #             self.video_path = video_path
        #             self.video_name = os.path.basename(video_path).split('.')[0]
        #             return True

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(self.video_url, download=True)
                video_path = ydl.prepare_filename(info)
            
                if not video_path.endswith('.mp4'):
                    video_path = os.path.splitext(video_path)[0] + '.mp4'
                self.video_path = video_path
                self.video_name = os.path.basename(video_path).split('.')[0]
                print(f'Video downloaded at location: {self.VIDEOS_DIR}')
                return True
        except Exception as e:
            print(f"Error downloading video: {e}")
            return False