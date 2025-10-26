import requests
import pandas as pd
import time

def fetch_all_parking_data(limit=1000):
    """
    Fetch all Melbourne on-street parking bay sensor records with pagination.
    Saves the data into a pandas DataFrame.
    """
    url = "https://data.melbourne.vic.gov.au/api/explore/v2.1/catalog/datasets/on-street-parking-bay-sensors/records"
    
    all_records = []
    offset = 0
    
    while True:
        params = {
            "limit": limit,
            "offset": offset
        }
        
        try:
            response = requests.get(url, params=params, timeout=20)
            response.raise_for_status()
        except requests.RequestException as e:
            print("Error fetching data:", e)
            break
        
        data = response.json()
        
        # Extract records from JSON
        records = data.get("results") or data.get("records") or data.get("data")
        
        if not records:
            print("No more records found.")
            break
        
        all_records.extend(records)
        
        print(f"Fetched {len(records)} records (total so far: {len(all_records)})")
        
        # If fewer records than the limit are returned, we've reached the end
        if len(records) < limit:
            break
        
        # Increase offset for next batch
        offset += limit
        
        # Be kind to the API – short delay
        time.sleep(0.5)
    
    # Normalize JSON into DataFrame
    df = pd.json_normalize(all_records)
    return df


if __name__ == "__main__":
    df = fetch_all_parking_data(limit=1000)  # fetch in batches of 1000
    
    print(f"\nTotal records fetched: {len(df)}")
    print(df.head())
    
    # Save to CSV
    df.to_csv("melbourne_parking_bay_sensors.csv", index=False)
    print("✅ Data saved to melbourne_parking_bay_sensors.csv")
