import os
import json
import pathlib
import numpy as np
import pandas as pd


class SaveEventDataAndProbabilities:
    def __init__(self, groupby_header, events_dict, event_csv_filepath, prob_json_filepath):
        self.groupby_header = groupby_header
        self.event_csv_filepath = event_csv_filepath
        self.prob_json_filepath = prob_json_filepath

        # Saving events to a csv
        self.save_events_to_csv(events_dict)
        # Calculating probabilities
        self.freq_df, self.prob_matrix = self.calculate_conditional_probabilities() 
        # Saving probabilities to json
        self.save_to_nested_by_bin_json(self.freq_df, self.groupby_header, self.prob_json_filepath)

        return 
    
    def save_events_to_csv(self, events_dict: dict):
    
        if self.groupby_header == "num_defenders":
            # convert dict → dataframe
            df = pd.DataFrame.from_dict(events_dict, orient='index', columns=["move", "num_defenders"])
            
            # Smoothing the results because the current representation is tending to over represent one of the two teams
            # df['num_defenders'] = np.where(df['num_defenders'] >= 10, df['num_defenders'] - 8, df['num_defenders'])
            # df['num_defenders'] = np.where(df['num_defenders'] > 7, df['num_defenders'] - 5, df['num_defenders'])
            print_message = f'\nMove vs Defender Count events saved at location: {self.event_csv_filepath}'
        
        else:
            # convert dict → dataframe
            df = pd.DataFrame.from_dict(events_dict, orient='index', columns=["move", "TimeSincePlayBegan", "down_number"])
            print_message = f'\nMove vs Time Since Play Started and Down events saved at location: {self.event_csv_filepath}'

        # check if file exists
        file_exists = os.path.isfile(self.event_csv_filepath)
        
        # if exists -> append without header
        # if not -> create file with header
        df.to_csv(self.event_csv_filepath, mode='a', index=False, header=not file_exists)
        print(print_message)
        return
    

    def calculate_conditional_probabilities(self):

        df = pd.read_csv(self.event_csv_filepath)

        # Count occurrences
        freq = df.groupby(['move', self.groupby_header]).size().reset_index(name='count')

        # Normalize within each n_front
        freq['prob'] = freq.groupby(self.groupby_header)['count'].transform(lambda x: x/x.sum())

        # # # Convert to matrix form (optional)
        # prob_matrix = freq.pivot(index=self.groupby_header, columns='move', values='prob').fillna(0)

        # Smoothing the probabilities to have non-zero probabilities at all instances
        alpha = 1
        freq['smoothed_prob'] = (
            (freq['count'] + alpha) /
            (freq.groupby(self.groupby_header)['count'].transform('sum') + alpha * df['move'].nunique())
        )

        # # Convert to matrix form (optional)
        prob_matrix = freq.pivot(index=self.groupby_header, columns='move', values='smoothed_prob').fillna(0)
        
        # freq is a dataframe containing all the data points (move to number of defenders and the conditional probabilities for each move)
        return freq, prob_matrix


    # freq_df: DataFrame with [num_defenders, move, smoothed_prob]
    # groupgby_header in ["TimeSincePlayBegan", "num_defenders"]
    def save_to_nested_by_bin_json(self, freq_df, groupby_header, json_save_path=None):
        
        out = {}
        K = freq_df['move'].nunique()
        for n, sub in freq_df.groupby(groupby_header):
            # ensure exact normalization per n
            s = sub['smoothed_prob'].sum()
            rows = [
                {"move": m, "p": float(p / s if s > 0 else 0.0)}
                for m, p in zip(sub['move'], sub['smoothed_prob'])
            ]
            out[int(n)] = rows
            if json_save_path is None:
                json_save_path = f"./results/move_policy_by_{groupby_header}_bin.json"
            pathlib.Path(json_save_path).write_text(json.dumps(out, indent=2))
        print(f"P(Move|{self.groupby_header}) saved at location: {json_save_path}")
        return

