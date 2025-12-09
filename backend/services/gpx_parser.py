import gpxpy
import os

def parse_gpx_file(filepath):
    """
    Parse a GPX file and extract latitude, longitude, elevation and time data.
    
    Args:
        filepath: Path to the GPX file
    
    Returns:
        Dictionary with lists of latitudes, longitudes, elevations and times
    
    Raises:
        FileNotFoundError: If file doesn't exist
        ValueError: If file is not a GPX file
    """
    if not os.path.exists(filepath):
        raise FileNotFoundError('File does not exist')
    
    if not filepath.endswith('.gpx'):
        raise ValueError('File must be a GPX file')
    
    with open(filepath, 'r') as gpx_file:
        gpx = gpxpy.parse(gpx_file)
    
    latitudes = []
    longitudes = []
    elevations = []
    times = []
    
    for track in gpx.tracks:
        for segment in track.segments:
            for point in segment.points:
                latitudes.append(point.latitude)
                longitudes.append(point.longitude)
                elevations.append(point.elevation)
                times.append(point.time.isoformat() if point.time else None)
    
    return {
        'latitudes': latitudes,
        'longitudes': longitudes,
        'elevations': elevations,
        'times': times
    }
