import requests
from skyfield.api import load, EarthSatellite, wgs84
import cartopy.crs as ccrs
import matplotlib.pyplot as plt
import datetime

def get_user_location():
    try:
        res = requests.get("https://ipinfo.io/json")
        data = res.json()
        loc = data['loc'].split(',')
        lat, lon = float(loc[0]), float(loc[1])
        print(f"Detected location: Latitude={lat}, Longitude={lon}")
        return lat, lon
    except:
        print("Could not detect location. Using (0, 0).")
        return 0.0, 0.0

def get_satellite_from_local_file(sat_name, tle_file_path):
    with open(tle_file_path, 'r') as file:
        lines = file.readlines()
    for i in range(0, len(lines) - 2, 3):
        name = lines[i].strip()
        line1 = lines[i+1].strip()
        line2 = lines[i+2].strip()
        if sat_name.upper() in name.upper():
            return EarthSatellite(line1, line2, name, load.timescale())
    return None

def plot_satellite_ground_track(satellite, user_lat, user_lon):
    # Generate timestamps for next 2 hours
    ts = load.timescale()
    now = datetime.datetime.now(datetime.timezone.utc)
    times = ts.utc(now.year, now.month, now.day, now.hour, range(120))
    
    # Calculate ground track
    lats, lons = [], []
    for t in times:
        geocentric = satellite.at(t)
        subpoint = wgs84.subpoint(geocentric)
        lats.append(subpoint.latitude.degrees)
        lons.append(subpoint.longitude.degrees)

    # Handle longitude wraparound
    lats_fixed = [lats[0]]
    lons_fixed = [lons[0]]
    for i in range(1, len(lons)):
        if abs(lons[i] - lons[i - 1]) > 180:
            lats_fixed.append(None)
            lons_fixed.append(None)
        lats_fixed.append(lats[i])
        lons_fixed.append(lons[i])

    # Plot using Cartopy
    fig = plt.figure(figsize=(12, 6))
    ax = plt.axes(projection=ccrs.PlateCarree())
    ax.set_global()
    ax.stock_img()
    ax.coastlines()
    ax.gridlines(draw_labels=True)

    # Zoom in around user
    ax.set_extent([user_lon - 40, user_lon + 40, user_lat - 20, user_lat + 20], crs=ccrs.PlateCarree())

    # Plot user location
    ax.plot(user_lon, user_lat, 'ro', markersize=6, label='You')

    # Plot satellite ground track
    ax.plot(lons_fixed, lats_fixed, color='cyan', linewidth=1.5, label=satellite.name)

    plt.title(f"{satellite.name} Ground Track (Zoomed on You)")
    plt.legend()
    plt.show()

# ---------- Main ----------
tle_file_path = "D:/projects/sat-ground-tracking/data/tle_cache.txt"
satellite_name = input("Enter satellite name: ")

sat = get_satellite_from_local_file(satellite_name, tle_file_path)
user_lat, user_lon = get_user_location()

if sat:
    print(f"TLE for {sat.name} loaded successfully.")
    plot_satellite_ground_track(sat, user_lat, user_lon)
else:
    print(f"Satellite '{satellite_name}' not found in TLE file.")
