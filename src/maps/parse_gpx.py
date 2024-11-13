import gpxpy
import os


def parse_gpx(filepath):
    """ Parse a GPX file and extract latitude, longitude, elevation and time data
    :param: filepath: str, path to the GPX file
    :return: tuple, containing lists of latitudes, longitudes, elevations and times
    """
    if os.path.exists(filepath) is False:
        raise FileNotFoundError('File does not exist')

    if not filepath.endswith('.gpx'):
        raise ValueError('File must be a GPX file')

    # Load the GPX file
    with open(filepath, 'r') as gpx_file:
        gpx = gpxpy.parse(gpx_file)

    # Extract data
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
                times.append(point.time)

    return latitudes, longitudes, elevations, times


if __name__ == '__main__':
    example_file = os.path.join('data', 'example.gpx')
    latitudes, longitudes, elevations, times = parse_gpx(example_file)
    print(latitudes)
    print(longitudes)
    print(elevations)
    print(times)