#!/usr/bin/env python3
"""
Program to clean and merge multiple GPX files.

This script processes one or more GPX files, cleans and merges them,
and then prints a final JSON object to the console containing the track ID
and a simplified polyline. All informational output is sent to stderr.
"""

import os
import glob
import xml.etree.ElementTree as ET
import sys
from datetime import datetime
import json
from rdp import rdp
import polyline

class GPXProcessor:
    """
    A class to read, clean, and merge GPX files.
    """
    def __init__(self):
        self.tracks = []
        self.first_timestamp = None
        self.source_file_order = []

    def read_gpx_file(self, filepath):
        """Read a GPX file and extract track information, including time."""
        try:
            tree = ET.parse(filepath)
            root = tree.getroot()
            namespaces = {'gpx': 'http://www.topografix.com/GPX/1/1'}

            tracks_in_file = []
            for trk in root.findall('.//gpx:trk', namespaces):
                track_data = {'name': None, 'segments': [], 'source_file': os.path.basename(filepath)}
                name_elem = trk.find('gpx:name', namespaces)
                track_data['name'] = name_elem.text if name_elem is not None and name_elem.text else os.path.splitext(os.path.basename(filepath))[0]

                for trkseg in trk.findall('gpx:trkseg', namespaces):
                    segment_points = []
                    for trkpt in trkseg.findall('gpx:trkpt', namespaces):
                        time_elem = trkpt.find('gpx:time', namespaces)
                        timestamp = None
                        if time_elem is not None and time_elem.text:
                            try:
                                timestamp = datetime.fromisoformat(time_elem.text.replace('Z', '+00:00'))
                            except ValueError:
                                print(f"Warning: Could not parse timestamp '{time_elem.text}'", file=sys.stderr)
                        
                        segment_points.append({
                            'latitude': float(trkpt.get('lat')),
                            'longitude': float(trkpt.get('lon')),
                            'elevation': float(trkpt.find('gpx:ele', namespaces).text) if trkpt.find('gpx:ele', namespaces) is not None else None,
                            'time': timestamp
                        })
                    if segment_points:
                        track_data['segments'].append(segment_points)
                if track_data['segments']:
                    tracks_in_file.append(track_data)

            if not tracks_in_file:
                waypoints = []
                for wpt in root.findall('.//gpx:wpt', namespaces):
                    time_elem = wpt.find('gpx:time', namespaces)
                    timestamp = None
                    if time_elem is not None and time_elem.text:
                        try:
                            timestamp = datetime.fromisoformat(time_elem.text.replace('Z', '+00:00'))
                        except ValueError:
                             print(f"Warning: Could not parse timestamp '{time_elem.text}'", file=sys.stderr)
                    
                    waypoints.append({
                        'latitude': float(wpt.get('lat')),
                        'longitude': float(wpt.get('lon')),
                        'elevation': float(wpt.find('gpx:ele', namespaces).text) if wpt.find('gpx:ele', namespaces) is not None else None,
                        'time': timestamp
                    })
                if waypoints:
                    tracks_in_file.append({
                        'name': f"{os.path.splitext(os.path.basename(filepath))[0]} (from waypoints)",
                        'segments': [waypoints],
                        'source_file': os.path.basename(filepath)
                    })
            return tracks_in_file
        except Exception as e:
            print(f"Error reading GPX file {filepath}: {e}", file=sys.stderr)
            return []

    def process_files(self, file_patterns):
        """Process GPX files, respecting the command-line order."""
        ordered_gpx_paths = []
        processed_paths = set()
        for pattern in file_patterns:
            files_from_pattern = sorted(glob.glob(pattern))
            for filepath in files_from_pattern:
                if filepath not in processed_paths and filepath.lower().endswith('.gpx'):
                    ordered_gpx_paths.append(filepath)
                    processed_paths.add(filepath)

        if not ordered_gpx_paths:
            print("No GPX files found with the provided patterns.", file=sys.stderr)
            return

        print(f"Processing {len(ordered_gpx_paths)} GPX files...", file=sys.stderr)
        for filepath in ordered_gpx_paths:
            print(f"Reading {filepath}...", file=sys.stderr)
            tracks = self.read_gpx_file(filepath)
            
            if not tracks:
                print(f"  → No tracks or waypoints found in {filepath}", file=sys.stderr)
                continue
            
            self.source_file_order.append(os.path.basename(filepath))

            if self.first_timestamp is None:
                for track in tracks:
                    for segment in track['segments']:
                        for point in segment:
                            if point.get('time'):
                                self.first_timestamp = point['time']
                                break
                        if self.first_timestamp: break
                    if self.first_timestamp: break
            
            for track in tracks:
                total_points = sum(len(segment) for segment in track['segments'])
                print(f"  → Track '{track['name']}': {len(track['segments'])} segments, {total_points} points", file=sys.stderr)
            self.tracks.extend(tracks)
        
        total_tracks = len(self.tracks)
        total_points = sum(sum(len(segment) for segment in track['segments']) for track in self.tracks)
        print(f"\nFound a total of {total_tracks} tracks with {total_points} points.", file=sys.stderr)

    def remove_duplicates_within_tracks(self, tolerance=0.0001):
        """Remove duplicate points within each track based on lat/lon tolerance."""
        total_removed = 0
        for track in self.tracks:
            for segment in track['segments']:
                if not segment: continue
                unique_points = []
                for point in segment:
                    is_duplicate = False
                    if unique_points and (abs(point['latitude'] - unique_points[-1]['latitude']) < tolerance and abs(point['longitude'] - unique_points[-1]['longitude']) < tolerance):
                        is_duplicate = True
                    if not is_duplicate:
                        unique_points.append(point)
                removed = len(segment) - len(unique_points)
                total_removed += removed
                segment[:] = unique_points
        if total_removed > 0:
            print(f"Removed {total_removed} duplicate points.", file=sys.stderr)

    def export_to_gpx(self, output_file):
        """Export the processed tracks to a single GPX file with custom metadata."""
        if not self.tracks:
            print("No tracks to export.", file=sys.stderr)
            return

        gpx = ET.Element('gpx', {'version': '1.1', 'creator': 'GPX Processor - seriot.ch', 'xmlns': 'http://www.topografix.com/GPX/1/1'})

        metadata = ET.SubElement(gpx, 'metadata')
        ET.SubElement(metadata, 'name')
        ET.SubElement(metadata, 'desc')
        
        author = ET.SubElement(metadata, 'author')
        author_name = ET.SubElement(author, 'name')
        author_name.text = 'Nicolas Seriot'
        
        copyright_tag = ET.SubElement(metadata, 'copyright', {'author': 'seriot.ch'})
        copyright_year = ET.SubElement(copyright_tag, 'year')
        copyright_year.text = str(datetime.now().year)
        
        keywords = ET.SubElement(metadata, 'keywords')
        keywords.text = self.first_timestamp.strftime('%B %Y') if self.first_timestamp else ''
        
        for track_data in self.tracks:
            trk = ET.SubElement(gpx, 'trk')
            trk_name = ET.SubElement(trk, 'name')
            trk_name.text = track_data['name']
            for segment in track_data['segments']:
                if not segment: continue
                trkseg = ET.SubElement(trk, 'trkseg')
                for point in segment:
                    trkpt = ET.SubElement(trkseg, 'trkpt', {'lat': str(point['latitude']), 'lon': str(point['longitude'])})
                    if point['elevation'] is not None:
                        ET.SubElement(trkpt, 'ele').text = str(point['elevation'])

        self._indent(gpx)
        tree = ET.ElementTree(gpx)
        tree.write(output_file, encoding='utf-8', xml_declaration=True)
        print(f"\nSuccessfully exported {len(self.tracks)} track(s) to {output_file}", file=sys.stderr)

    def generate_polyline(self, epsilon=0.0001):
        """
        Combines all processed track points, simplifies them, and returns an encoded polyline.
        """
        all_points = []
        for track in self.tracks:
            for segment in track['segments']:
                for point in segment:
                    all_points.append((point['latitude'], point['longitude']))
        
        if not all_points:
            return None
            
        simplified_points = rdp(all_points, epsilon=epsilon)
        encoded_polyline = polyline.encode(simplified_points)
        return encoded_polyline

    def _indent(self, elem, level=0):
        """Add pretty printing indentation to XML for readability."""
        i = "\n" + level * "  "
        if len(elem):
            if not elem.text or not elem.text.strip(): elem.text = i + "  "
            if not elem.tail or not elem.tail.strip(): elem.tail = i
            for sub_elem in elem: self._indent(sub_elem, level + 1)
            if not sub_elem.tail or not sub_elem.tail.strip(): sub_elem.tail = i
        else:
            if level and (not elem.tail or not elem.tail.strip()): elem.tail = i

def main():
    """Main function to parse arguments and run the processor."""
    if len(sys.argv) < 2:
        print("Usage:", file=sys.stderr)
        print("  To clean a single GPX file:", file=sys.stderr)
        print("    python gpx_processor.py <input.gpx>", file=sys.stderr)
        print("    (Output is saved to <input>/<input>.gpx)", file=sys.stderr)
        print("\n  To merge multiple GPX files:", file=sys.stderr)
        print("    python gpx_processor.py <file1.gpx> <file2.gpx>...", file=sys.stderr)
        print("    (Output is saved to <file1_file2>/<file1_file2>.gpx)", file=sys.stderr)
        return

    input_patterns = sys.argv[1:]
    processor = GPXProcessor()
    processor.process_files(input_patterns)

    if not processor.tracks:
        print("No valid tracks or waypoints found to process.", file=sys.stderr)
        return

    processor.remove_duplicates_within_tracks()

    source_files = processor.source_file_order
    if not source_files:
        print("Could not determine source files for naming the output file.", file=sys.stderr)
        return
        
    if len(source_files) == 1:
        input_basename = source_files[0]
        base_name = os.path.splitext(input_basename)[0]
        output_directory = base_name
        output_filename = input_basename
    else:
        base_names = [os.path.splitext(f)[0] for f in source_files]
        concatenated_name = "_".join(base_names)
        output_directory = concatenated_name
        output_filename = f"{concatenated_name}.gpx"

    try:
        os.makedirs(output_directory, exist_ok=True)
        print(f"Output will be saved in directory: '{output_directory}'", file=sys.stderr)
    except OSError as e:
        print(f"Error creating directory {output_directory}: {e}", file=sys.stderr)
        return

    final_output_path = os.path.join(output_directory, output_filename)
    processor.export_to_gpx(final_output_path)

    encoded_poly = processor.generate_polyline()

    # --- Generate and Print Final JSON Output to stdout ---
    if encoded_poly:
        json_object = {
            "id": output_directory,
            "title": "",
            "summary_polyline": encoded_poly
        }
        print(json.dumps(json_object, indent=4))

if __name__ == "__main__":
    main()