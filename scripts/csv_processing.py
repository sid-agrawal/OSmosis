""" 
Convert a raw CSV output from the CellulOS implementation to the OSmosis model

Transformations:
- Any PD with access to more than one ADS is converted into separate PDs per ADS 
"""

import numpy as np
import pandas as pd
import os
import re

ROOT_TASK_PD = "PD_1"

def read_csv_to_dataframe(filename):
    try:
        # Read CSV file into a pandas DataFrame
        df = pd.read_csv(filename, on_bad_lines='skip')
        return df
    except FileNotFoundError:
        print(f"Error: File '{filename}' not found.")
        return None
    except Exception as e:
        print(f"An error occurred: {e}")
        return None
    
def split_by_ads(df):
    # Find resource ID of all ADS
    ads_ids = df[df['RES_TYPE'] == 'ADS']['RES_ID']
    ads_ids = ads_ids.dropna().unique().tolist()

    # Find which ADS each PD has access to
    ads_rows = df[df['RESOURCE_TO'].isin(ads_ids) & df['PD_FROM'].notnull()]
    ads_rows = ads_rows[['RESOURCE_TO','PD_FROM']]
    ads_rows = ads_rows[ads_rows['PD_FROM'] != ROOT_TASK_PD]   # Ignore the root task
    ads_rows_grouped = ads_rows.groupby('PD_FROM')

    # Check which PDs have more than one ADS
    for pd_id, group in ads_rows_grouped:
        #if group.shape[0] == 1:
        #    continue # No operation necessary for PD with 1 ADS

        # Get all relations of the original PD
        pd_relations = df[(df['PD_FROM'] == pd_id) | (df['PD_ID'] == pd_id)]

        # Remove the original PD relations from the df
        df = df[(df['PD_FROM'] != pd_id) & (df['PD_ID'] != pd_id)]

        for i, ads_id in enumerate(group['RESOURCE_TO']):
            # Replace pd id
            new_pd_id = f"{pd_id}.{i}"

            # Copy all relations except to the other ADSs
            # exclude_ads = [id for id in ads_ids if id != ads_id] 
            exclude_ads = [] # Don't actually want to exclude the other ADS?
            new_pd_relations = pd_relations[~pd_relations['RESOURCE_TO'].isin(exclude_ads)]
            new_pd_relations = new_pd_relations.replace(pd_id, new_pd_id)
            df = df.replace(pd_id, new_pd_id)

            # Add to the DF
            df = pd.concat([df, new_pd_relations], ignore_index=True)

            # Create relations to all VMR in this ADS
            vmr_ids = df[(df['RESOURCE_TO'] == ads_id) & (df['RESOURCE_FROM'].str.startswith("VMR"))]['RESOURCE_FROM']
            vmr_ids = vmr_ids.dropna().unique().tolist()
            new_rows = [{'PD_FROM': new_pd_id, 'RESOURCE_TO': vmr_id} for vmr_id in vmr_ids]
            temp_df = pd.DataFrame(new_rows)

            df = pd.concat([df, temp_df], ignore_index=True)

    return df

if __name__ == "__main__":
    # Define the folder path and regex pattern
    folder_path = "./"
    regex_pattern = r"raw_kvstore.*\.csv"

    # Compile the regex pattern
    pattern = re.compile(regex_pattern)

    # List to store matching filenames
    matching_files = []

    # Iterate through all files in the folder
    for filename in os.listdir(folder_path):
        if pattern.match(filename):
            print(f"Load file '{filename}'")

            # Load CSV to dataframe
            df = read_csv_to_dataframe(filename)

            # Process data
            df = split_by_ads(df)
            print("Split PDs by ADS")

            # Save dataframe to CSV file
            out_filename = filename[4:]
            df.to_csv(out_filename, index=False)

            print(f"DataFrame saved to '{out_filename}'")

