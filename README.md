## Run & Hikes

A static, lightweight web software for displaying and sharing GPX tracks.

### Features

  * tours list and details
  * GPX file download
  * overview map with clickable paths
  * 3 photos per tour

### Live Demo

[https://seriot.ch/hike\_and\_run/](https://seriot.ch/hike_and_run/)

### Structure

No database. Everything runs in the browser.

```
.
├── hr.py             # The build script
├── src/              # Source directory (Input)
│   ├── 10 Valais/    # Region folder (Organized by you)
│   └── 20 France/
│
└── hike_and_run/     # Web directory (Output / Web Server Root)
    ├── tours.html    # Main application HTML
    ├── tours.css     # Styles
    ├── tours.js      # Front-end Logic
    └── tours/        # One project per tour
```

### Adding a new Tour

#### Step 1: Add the GPX File

Copy a GPX file in `/src/REGION/TOUR_ID/`.

Example: `/src/France/mont_blanc/`.

A tour can be made of several GPX files.

* **Ordering:** You can prefix region folders with numbers (e.g., `10 Valais`, `20 France`) to define the sort order.
* **Races:** If the tour is a race, start the folder name with an underscore (e.g., `_sierre_zinal`).

#### Step 2: Generate the Public GPX file and the Metadata

Run `python3 hr.py`.

The script will:

  * merge multiple GPX files if present
  * create a clean file at `src/REGION/TOUR_ID/TOUR_ID.gpx`
  * move the original raw GPX files into `~/.Trash`
  * add metadata (title, author, copyright)
  * auto-format dates: `YYYY-MM-DD` for races, `Month YYYY` for tours
  * generate a cached geometry file at `src/REGION/TOUR_ID/polyline.json`
  * copy the clean GPX and photos to the web folder: `hike_and_run/tours/TOUR_ID/`
  * update the global index at `hike_and_run/tours/tours.json`
  * tours are ordered by region
  * races are sorted by date (newest first)
  * other tours are sorted by highest altitude

#### Step 3: Edit the Source GPX Metadata

Example:

    <metadata>
      <name>Trail del Monte Soglio</name>
      <desc>https://www.trailmontesoglio.it/</desc>
      <author>
        <name>Nicolas Seriot</name>
      </author>
      <copyright author="seriot.ch">
        <year>2025</year>
      </copyright>
      <keywords>2025-06-01</keywords>
    </metadata>

#### Step 4: Add the Photos

Add exactly three photos, named `1.jpg`, `2.jpg`, and `3.jpg`.

### Local Run

You can run Hike and Run localy with:

    python3 -m http.server -d hike_and_run

and open [http://localhost:8000/](http://localhost:8000/)

### Deployment

Copy the `hike_and_run` directory on your web server.

#### License

This project is licensed under the MIT License. See the [LICENSE](https://github.com/nst/HikeAndRun/blob/main/LICENSE) file for details.
