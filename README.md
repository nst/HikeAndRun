## Run & Hikes

A static, lightweight web software for displaying and sharing GPX tracks.

### Features

- tours list and details
- GPX file download
- overview map with clickable paths
- 3 photos per tour

### Live Demo

[https://seriot.ch/hike\_and\_run/](https://seriot.ch/hike_and_run/)

### Architecture

No database. Everything runs in the browser.

```
tours.html         - HTML container
tours.css          - stylesheet
tours.js           - logic to displaying maps, lists, and tours
                   
/tours/tours.json  - tours index
/tours/*/          - one directory per tour
```

### Installation

Copy the `hike_and_run` directory on your web server.

There's no step 2.

-----

### How to Add a New Tour

#### Step 1: Create the Tour Folder

Pick a unique ID (eg. `my_new_hike`) and create the tour folder in `/tours/`.

Example: `/tours/my_new_hike/`

#### Step 2: Add the GPX File

The GPX file must be named exactly the same as the folder, with a `.gpx` extension.

Example: `/tours/my_new_hike/my_new_hike.gpx`

I use the script [tools/gpx_processor.py](https://github.com/nst/HikeAndRun/blob/main/tools/gpx_processor.py) to:

  * clean a GPX file, removing timestamps
  * create the tour directory
  * create the cleaned GPX inside the tour directory
  * output the polyline to be copied into tours.json

Depending on what you want to achieve, your workflow may vary.

#### Step 3: Add Metadata to the GPX File

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

#### Step 5: Update `tours.json`

Finally, open the main `/tours/tours.json` file and add an entry for your new tour.

You will need to provide:

  * `"id"`: The name of the folder you created.
  * `"title"`: The full, display-friendly name of the tour.
  * `"summary_polyline"`: The encoded polyline string for the overview map.

Add your new tour to the appropriate geographical category.

Example:

```json
[
  {
    "category": "Vaud",
    "tours": [
      {
        "id": "my_new_hike",
        "title": "My New Hike 2500 m",
        "summary_polyline": "encoded string for your new tour..."
      }
    ]
  },
...
]
```

Your new tour will then appear on the main list and overview map.

#### License

This project is licensed under the MIT License. See the [LICENSE](https://github.com/nst/HikeAndRun/blob/main/LICENSE) file for details.
