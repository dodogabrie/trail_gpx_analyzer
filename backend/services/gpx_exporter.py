"""GPX Exporter service for generating GPX files with predictions."""

from typing import Dict, List, Optional
from datetime import datetime, timedelta
import xml.etree.ElementTree as ET


class GPXExporter:
    """Exports predictions as GPX files with pace data."""

    def export_with_predictions(
        self,
        gpx_data: Dict,
        prediction_data: Dict,
        annotations: Optional[Dict] = None
    ) -> str:
        """Export GPX file with predicted paces.

        Args:
            gpx_data: Original GPX data with points
            prediction_data: Prediction data with segment paces
            annotations: Optional annotation data

        Returns:
            GPX XML string
        """
        # Create GPX root
        gpx = ET.Element('gpx', {
            'version': '1.1',
            'creator': 'GPX Analyzer',
            'xmlns': 'http://www.topografix.com/GPX/1/1',
            'xmlns:xsi': 'http://www.w3.org/2001/XMLSchema-instance',
            'xsi:schemaLocation': 'http://www.topografix.com/GPX/1/1 http://www.topografix.com/GPX/1/1/gpx.xsd'
        })

        # Metadata
        metadata = ET.SubElement(gpx, 'metadata')
        name = ET.SubElement(metadata, 'name')
        name.text = 'Predicted Route'
        time_elem = ET.SubElement(metadata, 'time')
        time_elem.text = datetime.utcnow().isoformat() + 'Z'

        # Track
        trk = ET.SubElement(gpx, 'trk')
        trk_name = ET.SubElement(trk, 'name')
        trk_name.text = 'Predicted Route'

        # Track segment
        trkseg = ET.SubElement(trk, 'trkseg')

        # Get points and predicted data
        points = gpx_data.get('points', [])
        segments = prediction_data.get('segments', [])

        # Map predicted paces to points
        current_time = datetime.utcnow()
        predicted_paces = self._map_paces_to_points(points, segments)

        # Add waypoints with predicted data
        for i, point in enumerate(points):
            trkpt = ET.SubElement(trkseg, 'trkpt', {
                'lat': str(point['latitude']),
                'lon': str(point['longitude'])
            })

            # Elevation
            if 'elevation' in point:
                ele = ET.SubElement(trkpt, 'ele')
                ele.text = str(point['elevation'])

            # Time (calculated from predicted pace)
            if i > 0 and i < len(predicted_paces):
                pace_min_per_km = predicted_paces[i]
                distance_delta = points[i].get('distance', 0) - points[i-1].get('distance', 0)
                time_delta_minutes = (distance_delta / 1000) * pace_min_per_km
                current_time += timedelta(minutes=time_delta_minutes)

            time_elem = ET.SubElement(trkpt, 'time')
            time_elem.text = current_time.isoformat() + 'Z'

            # Extensions with predicted pace
            if i < len(predicted_paces):
                extensions = ET.SubElement(trkpt, 'extensions')
                pace_elem = ET.SubElement(extensions, 'predicted_pace')
                pace_elem.text = f"{predicted_paces[i]:.2f}"  # min/km

        # Add annotations as waypoints
        if annotations and 'annotations' in annotations:
            for ann in annotations['annotations']:
                wpt = ET.SubElement(gpx, 'wpt', {
                    'lat': str(ann.get('lat', 0)),
                    'lon': str(ann.get('lon', 0))
                })
                wpt_name = ET.SubElement(wpt, 'name')
                wpt_name.text = ann.get('label', 'Annotation')
                wpt_desc = ET.SubElement(wpt, 'desc')
                wpt_desc.text = ann.get('type', 'marker')

        # Convert to string
        tree = ET.ElementTree(gpx)
        ET.indent(tree, space='  ')

        import io
        output = io.BytesIO()
        tree.write(output, encoding='utf-8', xml_declaration=True)
        return output.getvalue().decode('utf-8')

    def _map_paces_to_points(
        self,
        points: List[Dict],
        segments: List[Dict]
    ) -> List[float]:
        """Map segment-level predicted paces to individual points.

        Args:
            points: List of GPX points with distances
            segments: List of prediction segments with paces

        Returns:
            List of predicted paces (min/km) for each point
        """
        if not segments:
            return [5.0] * len(points)  # Default 5 min/km

        paces = []
        segment_idx = 0

        for point in points:
            distance_km = point.get('distance', 0) / 1000

            # Find which segment this point belongs to
            while segment_idx < len(segments) - 1:
                next_seg = segments[segment_idx + 1]
                if distance_km >= next_seg.get('start_distance', 0):
                    segment_idx += 1
                else:
                    break

            # Get pace from current segment
            if segment_idx < len(segments):
                seg = segments[segment_idx]
                pace = seg.get('predicted_pace', 5.0)
                paces.append(pace)
            else:
                paces.append(paces[-1] if paces else 5.0)

        return paces
