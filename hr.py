import os
import json
import shutil
import glob
import sys
import xml.etree.ElementTree as ET
from datetime import datetime
import re
import argparse
import time

# --- Configuration ---
SRC_DIR = "src"
WEB_DIR = "hike_and_run/tours"
COPY_TIMESTAMP_FILE = "last_copy.txt"  # Tracks the last time files were copied

# --- Dependencies ---
try:
    from rdp import rdp
    import polyline
except ImportError:
    print("Error: Missing libraries. Please run: pip install rdp polyline")
    sys.exit(1)

# ==========================================
# GPX PROCESSOR CLASS
# ==========================================

class GPXProcessor:
    """Handles GPX parsing, merging, cleaning, and stats generation."""

    NS = {'gpx': 'http://www.topografix.com/GPX/1/1'}
    ET.register_namespace('', NS['gpx'])

    def _get_tag(self, elem):
        return elem.tag.split('}', 1)[1] if '}' in elem.tag else elem.tag

    def _parse_time(self, time_str):
        if not time_str: return None
        try:
            return datetime.fromisoformat(time_str.strip().replace('Z', '+00:00'))
        except ValueError:
            return None

    def _extract_date_from_tree(self, root):
        """Scans metadata and track points for the first valid timestamp."""
        # 1. Check Metadata
        for meta in root.findall('gpx:metadata', self.NS):
            time_elem = meta.find('gpx:time', self.NS)
            if time_elem is not None and time_elem.text:
                return self._parse_time(time_elem.text)
        
        # 2. Check Track Points (Deep scan)
        for trk in root.findall('gpx:trk', self.NS):
            for seg in trk.findall('gpx:trkseg', self.NS):
                for pt in seg.findall('gpx:trkpt', self.NS):
                    time_elem = pt.find('gpx:time', self.NS)
                    if time_elem is not None and time_elem.text:
                        return self._parse_time(time_elem.text)
        return None

    def create_clean_gpx(self, raw_files, output_path, tour_id):
        """Merges multiple raw GPX files into one clean, anonymized file."""
        try:
            # A. Find earliest date among all files
            found_date = None
            for f in raw_files:
                try:
                    tree = ET.parse(f)
                    date = self._extract_date_from_tree(tree.getroot())
                    if date and (found_date is None or date < found_date):
                        found_date = date
                except: continue

            # B. Build New GPX
            new_gpx = ET.Element('gpx', {
                'version': '1.1', 'creator': 'HikeAndRun', 'xmlns': self.NS['gpx']
            })

            # Metadata
            meta = ET.SubElement(new_gpx, 'metadata')
            is_race = tour_id.startswith("_")
            
            # Title Generation
            title = f"🏁 {found_date.year} - {tour_id}" if (is_race and found_date) else (f"🏁 {tour_id}" if is_race else tour_id)

            ET.SubElement(meta, 'name').text = title
            ET.SubElement(meta, 'desc')
            author = ET.SubElement(meta, 'author')
            ET.SubElement(author, 'name').text = 'Nicolas Seriot'
            copy = ET.SubElement(meta, 'copyright', {'author': 'seriot.ch'})
            ET.SubElement(copy, 'year').text = str(datetime.now().year)
            
            # DATE FORMATTING LOGIC
            if found_date:
                if is_race:
                    # Races keep precise date: YYYY-MM-DD
                    date_str = found_date.strftime('%Y-%m-%d')
                else:
                    # Regular tours get month/year: Month YYYY
                    date_str = found_date.strftime('%B %Y')
                
                ET.SubElement(meta, 'keywords').text = date_str

            # Tracks (Merge & Clean)
            # Iterate through files in the SORTED order provided
            for f in raw_files:
                try:
                    root = ET.parse(f).getroot()
                    for trk in root.findall('gpx:trk', self.NS):
                        new_trk = ET.SubElement(new_gpx, 'trk')
                        
                        # Name
                        name_node = trk.find('gpx:name', self.NS)
                        ET.SubElement(new_trk, 'name').text = name_node.text if (name_node is not None) else title
                        
                        for seg in trk.findall('gpx:trkseg', self.NS):
                            new_seg = ET.SubElement(new_trk, 'trkseg')
                            for pt in seg.findall('gpx:trkpt', self.NS):
                                attr = {'lat': pt.get('lat'), 'lon': pt.get('lon')}
                                new_pt = ET.SubElement(new_seg, 'trkpt', attr)
                                # Keep Elevation
                                ele = pt.find('gpx:ele', self.NS)
                                if ele is not None:
                                    ET.SubElement(new_pt, 'ele').text = ele.text
                except: continue

            # Write
            tree = ET.ElementTree(new_gpx)
            if hasattr(ET, 'indent'): ET.indent(tree, space="  ", level=0)
            tree.write(output_path, encoding='utf-8', xml_declaration=True)
            return True
        except Exception as e:
            print(f"  [Error] Failed to create GPX for {tour_id}: {e}")
            return False

    def get_stats(self, gpx_path):
        """Calculates heavy stats (Polyline & Max Ele) for caching."""
        points = []
        max_ele = 0
        try:
            tree = ET.parse(gpx_path)
            root = tree.getroot()
            for trk in root.findall('gpx:trk', self.NS):
                for seg in trk.findall('gpx:trkseg', self.NS):
                    for pt in seg.findall('gpx:trkpt', self.NS):
                        try:
                            points.append((float(pt.get('lat')), float(pt.get('lon'))))
                            ele = pt.find('gpx:ele', self.NS)
                            if ele is not None:
                                max_ele = max(max_ele, float(ele.text))
                        except: pass
            
            if not points: return None
            
            return {
                "summary_polyline": polyline.encode(rdp(points, epsilon=0.0002)),
                "max_elevation": int(max_ele)
            }
        except Exception as e:
            print(f"  [Error] Stats failed for {gpx_path}: {e}")
            return None

    def parse_metadata(self, gpx_path):
        """Extracts lightweight metadata (Name, Date) for indexing."""
        try:
            tree = ET.parse(gpx_path)
            root = tree.getroot()
            name, date_str = None, None
            
            meta = root.find('gpx:metadata', self.NS)
            if meta is not None:
                n = meta.find('gpx:name', self.NS)
                k = meta.find('gpx:keywords', self.NS)
                if n is not None: name = n.text
                if k is not None: date_str = k.text
            return name, date_str
        except:
            return None, None

# ==========================================
# WORKFLOW PHASES
# ==========================================

def clean_category_name(folder_name):
    """
    Removes leading numbers and separators to produce a clean title.
    e.g. "10 Bas Valais" -> "Bas Valais"
    e.g. "20_France" -> "France"
    """
    return re.sub(r'^\d+[\s_-]*', '', folder_name)

def run_pipeline(skip_images):
    print("--- Starting HikeAndRun Build ---")
    
    if not os.path.exists(SRC_DIR):
        print(f"Error: '{SRC_DIR}' directory not found.")
        return

    processor = GPXProcessor()
    
    # --- PHASE 1: PROCESS & CACHE (In SRC) ---
    print(f"\n[Phase 1] Processing Source ({SRC_DIR})...")
    
    trash_dir = os.path.expanduser("~/.Trash")
    if not os.path.exists(trash_dir):
        try: os.makedirs(trash_dir)
        except: pass

    # Iterate sorted folders (so 10... processes before 20...)
    for category_folder in sorted(os.listdir(SRC_DIR)):
        cat_path = os.path.join(SRC_DIR, category_folder)
        if not os.path.isdir(cat_path) or category_folder.startswith('.'): continue

        for tour_id in sorted(os.listdir(cat_path)):
            tour_path = os.path.join(cat_path, tour_id)
            if not os.path.isdir(tour_path) or tour_id.startswith('.'): continue

            clean_gpx = os.path.join(tour_path, f"{tour_id}.gpx")
            cache_json = os.path.join(tour_path, "polyline.json")

            # A. Generate Clean GPX if missing
            if not os.path.exists(clean_gpx):
                raw_files = sorted([f for f in glob.glob(os.path.join(tour_path, "*.gpx")) if f != clean_gpx])
                
                if raw_files:
                    print(f"  + Generating GPX: {tour_id} (merging {len(raw_files)} files)")
                    if processor.create_clean_gpx(raw_files, clean_gpx, tour_id):
                        # --- MOVE TO TRASH ON SUCCESS ---
                        print(f"  - Moving {len(raw_files)} raw files to Trash")
                        for raw_f in raw_files:
                            try:
                                fname = os.path.basename(raw_f)
                                trash_name = f"{tour_id}_{fname}"
                                dst = os.path.join(trash_dir, trash_name)
                                shutil.move(raw_f, dst)
                            except Exception as e:
                                print(f"    [Warning] Failed to trash {raw_f}: {e}")
            
            # B. Update Cache if missing or stale
            if os.path.exists(clean_gpx):
                needs_update = not os.path.exists(cache_json) or \
                               os.path.getmtime(clean_gpx) > os.path.getmtime(cache_json)
                
                if needs_update:
                    stats = processor.get_stats(clean_gpx)
                    if stats:
                        with open(cache_json, 'w', encoding='utf-8') as f:
                            json.dump(stats, f)
                        # print(f"  + Cached Stats: {tour_id}")

    # --- PHASE 2: PUBLISH (Copy to Web) ---
    print(f"\n[Phase 2] Publishing to ({WEB_DIR})...")
    os.makedirs(WEB_DIR, exist_ok=True)
    
    # 1. Determine Last Run Timestamp
    last_copy_ts = 0.0
    if os.path.exists(COPY_TIMESTAMP_FILE):
        last_copy_ts = os.path.getmtime(COPY_TIMESTAMP_FILE)
        print(f"  [Info] Incremental copy: Only files newer than {last_copy_ts}")
    else:
        print("  [Info] First run (or timestamp missing): Copying all files.")

    # Selective Tour Copy
    copied_count = 0
    for root, dirs, files in os.walk(SRC_DIR):
        if os.path.basename(root) == SRC_DIR: continue
        
        tour_id = os.path.basename(root)
        src_gpx = os.path.join(root, f"{tour_id}.gpx")
        
        # Only process if we have a valid processed GPX
        if os.path.exists(src_gpx):
            dst_folder = os.path.join(WEB_DIR, tour_id)
            os.makedirs(dst_folder, exist_ok=True)
            
            # 1. Copy GPX (Only if modified)
            if os.path.getmtime(src_gpx) > last_copy_ts:
                # copy2 preserves timestamps
                shutil.copy2(src_gpx, os.path.join(dst_folder, f"{tour_id}.gpx"))
                print(f"  > Copied GPX: {tour_id}.gpx")
                copied_count += 1

            # 2. Copy Photos (Only if modified)
            if not skip_images:
                for img in ['1.jpg', '2.jpg', '3.jpg']:
                    src_img = os.path.join(root, img)
                    if os.path.exists(src_img):
                        if os.path.getmtime(src_img) > last_copy_ts:
                            shutil.copy2(src_img, os.path.join(dst_folder, img))
                            print(f"  > Copied Photo: {tour_id}/{img}")

    # --- PHASE 3: INDEX ---
    print(f"\n[Phase 3] Generating Index...")

    final_index = []

    for category_folder in sorted(os.listdir(SRC_DIR)):
        cat_path = os.path.join(SRC_DIR, category_folder)
        if not os.path.isdir(cat_path) or category_folder.startswith('.'): continue

        display_category = clean_category_name(category_folder)
        current_cat_tours = []

        for tour_id in sorted(os.listdir(cat_path)):
            # Paths
            web_gpx = os.path.join(WEB_DIR, tour_id, f"{tour_id}.gpx")
            src_cache = os.path.join(cat_path, tour_id, "polyline.json")
            
            if not os.path.exists(web_gpx) or not os.path.exists(src_cache):
                continue
            
            # Read Stats (Cache)
            try:
                with open(src_cache, 'r') as f: stats = json.load(f)
            except: continue
            
            # Read Metadata (Live GPX from Web/Dst)
            name, date_str = processor.parse_metadata(web_gpx)
            
            # Process Metadata
            title = name.strip() if name else tour_id
            is_race = tour_id.startswith("_")
            
            if is_race and "🏁" not in title:
                year = None
                if date_str:
                    match = re.search(r'\b(19|20)\d{2}\b', date_str)
                    if match: year = match.group(0)
                title = f"🏁 {year} - {title}" if year else f"🏁 {title}"
            
            # Date Sort Helper
            sort_ts = 0.0
            if date_str:
                try: sort_ts = datetime.fromisoformat(date_str).timestamp()
                except:
                    try: sort_ts = datetime.strptime(date_str, "%B %Y").timestamp()
                    except: pass

            entry = {
                "id": tour_id,
                "title": title,
                "summary_polyline": stats.get('summary_polyline', ''),
                "_is_race": is_race,
                "_max_ele": stats.get('max_elevation', 0),
                "_sort_ts": sort_ts
            }
            
            current_cat_tours.append(entry)

        # Sort Tours
        if current_cat_tours:
            current_cat_tours.sort(key=lambda x: (
                1 if x['_is_race'] else 0,
                -x['_sort_ts'] if x['_is_race'] else -x['_max_ele'],
                x['title']
            ))
            
            # Cleanup internal keys
            for t in current_cat_tours:
                for k in ['_is_race', '_max_ele', '_sort_ts']: t.pop(k, None)
                
            final_index.append({
                "category": display_category,
                "tours": current_cat_tours
            })

    # Save
    with open(os.path.join(WEB_DIR, "tours.json"), 'w', encoding='utf-8') as f:
        json.dump(final_index, f, indent=4, ensure_ascii=False)
    
    # Update Timestamp File at end of successful run
    with open(COPY_TIMESTAMP_FILE, 'w') as f:
        f.write("timestamp")
    
    print(f"Done! Site built in '{WEB_DIR}'. Indexed {len(final_index)} categories.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-s", "--skip-images", action="store_true", help="Skip copying images.")
    args = parser.parse_args()
    
    run_pipeline(args.skip_images)