import os
import requests
from skyfield.api import Loader, EarthSatellite, wgs84
import matplotlib.pyplot as plt
import cartopy.crs as ccrs
import datetime
import math

# ----------------- CONFIG -----------------
TLE_URL = "https://celestrak.org/NORAD/elements/gp.php?GROUP=active&FORMAT=tle"
DATA_DIR = "D:/projects/sat-ground-tracking/data"
TLE_CACHE_FILE = os.path.join(DATA_DIR, "tle_cache.txt")
CACHE_UPDATE_DAYS = 7  # refresh once per week
GROUND_TRACK_HOURS = 2  # forecast in hours
POINTS_PER_HOUR = 60  # points per hour
DEBUG = False # Set to False for cleaner output, True for detailed lat/lon prints
# -----------------------------------------

def ensure_data_dir():
    """Creates the data directory if it doesn't exist."""
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)

def download_tle():
    """Downloads fresh TLE data and saves it with UTF-8 encoding."""
    print("Downloading fresh TLE data from CelesTrak...")
    response = requests.get(TLE_URL)
    response.raise_for_status()
    response.encoding = 'utf-8'
    with open(TLE_CACHE_FILE, 'w', encoding='utf-8') as f:
        f.write(response.text)
    print(f"TLE data saved to {TLE_CACHE_FILE}")

def is_tle_fresh():
    """Checks if the cached TLE file is recent."""
    if not os.path.exists(TLE_CACHE_FILE):
        return False
    cache_mtime = datetime.datetime.fromtimestamp(os.path.getmtime(TLE_CACHE_FILE), tz=datetime.timezone.utc)
    now = datetime.datetime.now(datetime.timezone.utc)
    age_days = (now - cache_mtime).days
    print(f"TLE cache age: {age_days} day(s)")
    return age_days < CACHE_UPDATE_DAYS

def load_tle_lines():
    """Manages cache and loads TLE file lines with UTF-8 encoding."""
    ensure_data_dir()
    if not is_tle_fresh():
        download_tle()
    else:
        print("Using cached TLE data.")
    with open(TLE_CACHE_FILE, 'r', encoding='utf-8') as f:
        return f.readlines()

def get_satellite_from_file(sat_name, tle_lines, load):
    """
    Finds a satellite from a clean list of TLE lines (no blank lines).
    """
    print(f"Searching for satellite '{sat_name}' in clean TLE data...")
    ts = load.timescale()
    # This simple 3-line step loop works because the data is pre-cleaned
    for i in range(0, len(tle_lines), 3):
        if i + 2 >= len(tle_lines):
            continue

        name = tle_lines[i].strip()
        line1 = tle_lines[i + 1].strip()
        line2 = tle_lines[i + 2].strip()

        if sat_name.upper() in name.upper():
            try:
                print(f"Found '{name}'. Attempting to parse...")
                sat = EarthSatellite(line1, line2, name, ts)
                print(f"TLE for {name} loaded successfully.")
                return sat, name + "\n" + line1 + "\n" + line2
            except Exception as e:
                print(f"Found '{name}' but failed to parse its TLE data. Error: {e}")
                return None, None
    return None, None

def get_user_location():
    """Gets user's approximate location from their IP address."""
    try:
        print("Detecting your location...")
        res = requests.get("https://ipinfo.io/json")
        res.raise_for_status()
        data = res.json()
        loc = data['loc'].split(',')
        lat, lon = float(loc[0]), float(loc[1])
        print(f"Detected location: Latitude={lat}, Longitude={lon}")
        return lat, lon
    except Exception as e:
        print(f"Could not detect location due to {e}. Using Dublin, Ireland as default.")
        return 53.3498, -6.2603

def compute_ground_track(satellite, load):
    """Calculates the satellite's ground track for the configured duration."""
    print("Calculating satellite ground track...")
    ts = load.timescale()
    now = datetime.datetime.now(datetime.timezone.utc)
    total_points = GROUND_TRACK_HOURS * POINTS_PER_HOUR
    
    times = [ts.utc(now + datetime.timedelta(minutes=i)) for i in range(total_points)]
    
    lats, lons = [], []
    for t in times:
        geocentric = satellite.at(t)
        subpoint = wgs84.subpoint(geocentric)
        lat_deg = subpoint.latitude.degrees
        lon_deg = subpoint.longitude.degrees
        lats.append(lat_deg)
        lons.append(lon_deg)
        if DEBUG and not math.isnan(lat_deg):
            print(f"Time {t.utc_iso()} -> lat={lat_deg:.4f}, lon={lon_deg:.4f}")
            
    # Handle longitude wraparound for plotting
    lats_fixed, lons_fixed = [], []
    for i in range(len(lons)):
        if i > 0 and abs(lons[i] - lons[i-1]) > 180:
            lats_fixed.append(None)
            lons_fixed.append(None)
        lats_fixed.append(lats[i])
        lons_fixed.append(lons[i])

    valid_points = sum(1 for pt in lats if not math.isnan(pt))
    print(f"Collected {valid_points} valid ground track points.")
    return lats_fixed, lons_fixed

def plot_map(lats, lons, user_lat, user_lon, satellite_name):
    """Plots the satellite track and user location on a world map."""
    print("Plotting map...")
    fig = plt.figure(figsize=(15, 8))
    ax = plt.axes(projection=ccrs.PlateCarree())
    ax.set_global()
    ax.stock_img()
    ax.coastlines()
    ax.gridlines(draw_labels=True, dms=True, x_inline=False, y_inline=False)

    # Plot user location
    ax.plot(user_lon, user_lat, 'ro', markersize=8, transform=ccrs.Geodetic(), label='Your Location')

    # Plot satellite ground track
    ax.plot(lons, lats, color='cyan', linewidth=2, transform=ccrs.Geodetic(), label=f'{satellite_name} Track')
    
    # Plot the satellite's current position (the first point in the track)
    current_lat = next((lat for lat in lats if lat is not None), None)
    current_lon = next((lon for lon in lons if lon is not None), None)
    if current_lat is not None:
        ax.plot(current_lon, current_lat, 'o', color='yellow', markersize=8, transform=ccrs.Geodetic(), label=f'{satellite_name} Current Position')

    plt.title(f"{satellite_name} Ground Track for the Next {GROUND_TRACK_HOURS} Hours")
    plt.legend()
    plt.show()

# ----------------- MAIN SCRIPT EXECUTION -----------------
if __name__ == '__main__':
    # 1. Initialize the Skyfield loader in our data directory
    ensure_data_dir()
    load = Loader(DATA_DIR)

    # 2. Load the raw lines from the TLE file
    tle_lines_raw = load_tle_lines()
    
    # 3. THE CRITICAL FIX: Create a new, clean list by removing all empty/blank lines.
    tle_lines = [line for line in tle_lines_raw if line.strip()]

    # 4. Get user input
    satellite_name = input("Enter satellite name (e.g., 'ISS (ZARYA)'): ").strip()
    if not satellite_name:
        satellite_name = "ISS (ZARYA)"

    print_tle = input("Print TLE? [y/N]: ").strip().lower() == 'y'

    # 5. Find the satellite using the CLEANED tle_lines list
    sat, tle_text = get_satellite_from_file(satellite_name, tle_lines, load)
    
    if sat is None:
        print(f"Satellite '{satellite_name}' not found in TLE data.")
        exit()

    if print_tle:
        print(f"\nTLE for {sat.name}:\n{tle_text}\n")

    
    print(f"Satellite Epoch: {sat.epoch.utc_iso()}")

    # 6. Calculate and plot the track
    user_lat, user_lon = get_user_location()
    lats, lons = compute_ground_track(sat, load)

    if any(pt is not None and not math.isnan(pt) for pt in lats):
        plot_map(lats, lons, user_lat, user_lon, sat.name)
    else:
        print("No valid ground track points were generated. Cannot plot.")
