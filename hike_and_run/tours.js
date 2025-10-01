window.addEventListener('DOMContentLoaded', () => {
    // -- CONFIGURATION --
    const config = {
        apiKey: '6170aad10dfd42a38d4d8c709a536f38',
        trackColors: ['#ff7f00', '#984ea3', '#000000', '#f781bf', '#a65628', '#4daf4a']
    };

    const OVERVIEW_INIT = { center: [46.4485501, 7.2854171], zoom: 8 };

    // -- STATE MANAGEMENT --
    let detailMap = null;
    let overviewMap = null;
    let allToursData = [];
    let selectedCategories = new Set();
    let allOverviewPolylines = {};
    let highlightedTrack = null;
    let currentDetailTracks = [];
    let currentDetailMarkers = [];

    function debounce(fn, wait = 120) {
      let t; return (...args) => { clearTimeout(t); t = setTimeout(() => fn(...args), wait); };
    }

    function matchesSelectedPrefix(category) {
      if (selectedCategories.size === 0) return true;
      for (const sel of selectedCategories) {
        // case-sensitive; switch to toLowerCase() on both sides if you prefer CI
        if (category.startsWith(sel)) return true;
      }
      return false;
    }

    // --- VIEW MANAGEMENT ---
    function showView(viewName) {
        const elements = {
            overview: [document.getElementById('overview-map'), document.querySelector('.intro-text'), document.querySelector('.picker-container'), document.getElementById('trackInfo')],
            detail: [document.querySelector('.map-container'), document.querySelector('.elevation-container'), document.querySelector('.info-panel'), document.getElementById('trackInfo')]
        };
        [...elements.overview, ...elements.detail].forEach(el => {
            if (el) el.style.display = 'none';
        });
        elements[viewName].forEach(el => {
            if (el) el.style.display = 'block';
        });
    }

    // --- TOUR LIST & FILTERING ---
    function renderTourList() {
        const infoPanel = document.getElementById('trackInfo');
        infoPanel.className = '';
        
        const categoriesToShow = allToursData.filter(cat => 
            matchesSelectedPrefix(cat.category)
        );

        let tableHTML = '<table>';
        categoriesToShow.forEach(cat => {
            if (cat.tours && cat.tours.length > 0) {
                tableHTML += `<tr><th>${cat.category}</th></tr>`;
                cat.tours.forEach(tour => {
                    tableHTML += `<tr><td><a href="?${tour.id}">${tour.title}</a></td></tr>`;
                });
            }
        });
        tableHTML += '</table>';
        infoPanel.innerHTML = tableHTML;
    }

    // Debounced recenter to visible polylines; fall back to initial view if none visible
    const fitOverviewToVisible = debounce(() => {
      if (!overviewMap) return;
      const visibleGroups = [];
      for (const key in allOverviewPolylines) {
        const group = allOverviewPolylines[key];
        if (overviewMap.hasLayer(group)) visibleGroups.push(group);
      }
      if (!visibleGroups.length) {
        overviewMap.setView(OVERVIEW_INIT.center, OVERVIEW_INIT.zoom);
        return;
      }
      const fg = L.featureGroup(visibleGroups);
      const bounds = fg.getBounds();
      if (bounds && bounds.isValid()) {
        overviewMap.fitBounds(bounds, { padding: [40, 40], maxZoom: 13 });
      }
    }, 120);
    
    function filterOverviewMap() {
      if (!overviewMap) return;
    
      const showAll = selectedCategories.size === 0;
    
      for (const category in allOverviewPolylines) {
        const group = allOverviewPolylines[category];
    
        // substring match (change to .startsWith if you prefer prefix-only)
        const match = showAll || Array.from(selectedCategories)
          .some(sel => category.toLowerCase().includes(sel.toLowerCase()));
    
        if (match) {
          if (!overviewMap.hasLayer(group)) overviewMap.addLayer(group);
        } else {
          if (overviewMap.hasLayer(group)) overviewMap.removeLayer(group);
        }
      }
    
      // Recenter: initial view if no selection; otherwise fit to visible polylines
      if (showAll) {
        overviewMap.setView(OVERVIEW_INIT.center, OVERVIEW_INIT.zoom);
      } else {
        fitOverviewToVisible();
      }
    }
    
    function setupCategoryPicker() {
        const picker = document.getElementById('category-picker');
        picker.querySelectorAll('g').forEach(g => {
            g.addEventListener('click', () => {
                const category = g.dataset.category;
                g.classList.toggle('selected');
                if (selectedCategories.has(category)) {
                    selectedCategories.delete(category);
                } else {
                    selectedCategories.add(category);
                }
                renderTourList();
                filterOverviewMap();
            });
        });
    }

    // --- MAP INITIALIZATION ---
function initializeOverviewMap(tourData) {
    if (overviewMap) return;
    setTimeout(() => {
        overviewMap = L.map('overview-map').setView(OVERVIEW_INIT.center, OVERVIEW_INIT.zoom);
        
        // Add fullscreen control with Safari fix
        overviewMap.addControl(new L.Control.FullScreen({ forceSeparateButton: true, forcePseudoFullscreen: true }));
        overviewMap.on('enterFullscreen exitFullscreen', () => { setTimeout(() => overviewMap.invalidateSize(), 100); });

        const outdoorUrl = `https://tile.thunderforest.com/outdoors/{z}/{x}/{y}{r}.png?apikey=${config.apiKey}`;
        const layers = {
            "🗺️ Standard": L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', { attribution: '© OpenStreetMap contributors' }),
            "🏔️ Outdoor": L.tileLayer(outdoorUrl, { attribution: '© Thunderforest, OpenStreetMap contributors' }),
            "🛰️ Satellite": L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', { attribution: '© Esri, OpenStreetMap contributors' })
        };
        layers["🏔️ Outdoor"].addTo(overviewMap);
        L.control.layers(layers).addTo(overviewMap);

        // --- STYLE DEFINITIONS FOR HIGHLIGHTING ---
        const originalStyle = { color: "#FF0000", weight: 3, opacity: 0.7 };
        const highlightStyle = { color: "#1492FF", weight: 5, opacity: 1.0 };

        allOverviewPolylines = {};
        tourData.forEach(cat => {
            const categoryPolylines = [];
            cat.tours.forEach(tour => {
                if (tour.summary_polyline) {
                    const track = L.polyline(polyline.decode(tour.summary_polyline), originalStyle);
                    track.bindPopup(`<b>${tour.title}</b><br><a href="?${tour.id}">View Details</a>`);
                    
                    // --- CLICK EVENT FOR HIGHLIGHTING ---
                    track.on('click', (e) => {
                        // Reset the previously highlighted track if it exists
                        if (highlightedTrack) {
                            highlightedTrack.setStyle(originalStyle);
                        }

                        // Highlight the new track
                        track.setStyle(highlightStyle);
                        track.bringToFront();
                        highlightedTrack = track;
                        
                        // Prevent map click event from firing
                        L.DomEvent.stopPropagation(e);
                    });

                    categoryPolylines.push(track);
                }
            });
            allOverviewPolylines[cat.category] = L.featureGroup(categoryPolylines).addTo(overviewMap);
        });

        // --- MAP CLICK TO DESELECT ---
        overviewMap.on('click', () => {
            if (highlightedTrack) {
                highlightedTrack.setStyle(originalStyle);
                highlightedTrack = null;
            }
        });

    }, 0);
}

    function initializeDetailMap() {
        if (detailMap) return detailMap;
        detailMap = L.map('map', { 
            preferCanvas: true, 
            zoomControl: true, 
            attributionControl: true
        }).setView(OVERVIEW_INIT.center, OVERVIEW_INIT.zoom);
        
        // Add fullscreen control with Safari fix
        detailMap.addControl(new L.Control.FullScreen({ forceSeparateButton: true, forcePseudoFullscreen: true }));
        detailMap.on('enterFullscreen exitFullscreen', () => { setTimeout(() => detailMap.invalidateSize(), 100); });

        const outdoorUrl = `https://tile.thunderforest.com/outdoors/{z}/{x}/{y}{r}.png?apikey=${config.apiKey}`;
        const layers = {
            "🗺️ Standard": L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', { attribution: '© OpenStreetMap contributors' }),
            "🏔️ Outdoor": L.tileLayer(outdoorUrl, { attribution: '© Thunderforest, OpenStreetMap contributors' }),
            "🛰️ Satellite": L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', { attribution: '© Esri, OpenStreetMap contributors' })
        };
        layers["🏔️ Outdoor"].addTo(detailMap);
        L.control.layers(layers).addTo(detailMap);
        return detailMap;
    }
    
    // --- DATA LOADING & PARSING ---
    async function loadTourData(tourFolder) {
        try {
            const tourConfig = {};
            const basePath = `tours/${tourFolder}`;
            const gpxFileName = `${tourFolder}.gpx`;
            const sanitizedGpxName = sanitizeFileName(gpxFileName);
            if (!sanitizedGpxName) throw new Error(`Invalid GPX filename from folder: ${tourFolder}`);
            tourConfig.gpxPath = `${basePath}/${sanitizedGpxName}`;
            tourConfig.gpx = sanitizedGpxName;
            tourConfig.basePath = basePath;
            await loadGPXFromConfig(tourConfig);
        } catch (error) {
            document.getElementById('trackInfo').innerHTML = `<div class="error">❌ <strong>Cannot load tour data</strong><br><small>${error.message}</small></div>`;
        }
    }

    async function loadGPXFromConfig(tourConfig) {
        try {
            const map = initializeDetailMap();
            const response = await fetch(tourConfig.gpxPath);
            if (!response.ok) throw new Error(`GPX file not found: ${tourConfig.gpxPath}`);
            const gpxContent = await response.text();
            parseAndDisplayGPX(gpxContent, tourConfig, map);
        } catch (error) {
            document.getElementById('trackInfo').innerHTML = `<div class="error">❌ <strong>Cannot load GPX file</strong><br><small>${error.message}</small></div>`;
        }
    }

    function parseAndDisplayGPX(gpxContent, tourConfig, map) {
        try {
            currentDetailTracks.forEach(track => map.removeLayer(track));
            currentDetailMarkers.forEach(marker => map.removeLayer(marker));
            currentDetailTracks = [];
            currentDetailMarkers = [];

            const parser = new DOMParser();
            const gpx = parser.parseFromString(gpxContent, "text/xml");
            if (gpx.querySelector('parsererror')) throw new Error('XML parsing error');

            const metadata = {
                nameNode: gpx.querySelector('metadata > name') || gpx.querySelector('trk > name'),
                descNode: gpx.querySelector('metadata > desc'),
                keywordsNode: gpx.querySelector('metadata > keywords')
            };
            tourConfig.name = metadata.nameNode ? metadata.nameNode.textContent : tourConfig.gpx.replace(/\.gpx$/i, '').replace(/_/g, ' ');
            tourConfig.comments = metadata.descNode ? metadata.descNode.textContent : '';
            tourConfig.date = metadata.keywordsNode ? metadata.keywordsNode.textContent : '';

            const allTrackPoints = Array.from(gpx.querySelectorAll('trk')).map(trackNode => {
                return Array.from(trackNode.querySelectorAll('trkpt')).map(pt => {
                    const lat = parseFloat(pt.getAttribute('lat'));
                    const lon = parseFloat(pt.getAttribute('lon'));
                    const eleElement = pt.querySelector('ele');
                    if (eleElement) {
                        const ele = parseFloat(eleElement.textContent);
                        return [lat, lon, ele];
                    }
                    return null;
                }).filter(p => p !== null);
            }).filter(track => track.length > 0);

            if (allTrackPoints.length === 0) throw new Error('No valid track points with elevation found in GPX file.');

            allTrackPoints.forEach((trackPoints, index) => {
                const latlngs = trackPoints.map(p => [p[0], p[1]]);
                const polyline = L.polyline(latlngs, { color: config.trackColors[index % config.trackColors.length], weight: 4, opacity: 0.85 }).addTo(map);
                currentDetailTracks.push(polyline);
            });

            const group = L.featureGroup(currentDetailTracks);
            map.fitBounds(group.getBounds(), { padding: [40, 40], maxZoom: 16 });

            const firstTrack = allTrackPoints[0];
            const lastTrack = allTrackPoints[allTrackPoints.length - 1];
            if (firstTrack.length > 0) {
                const startIcon = L.divIcon({ html: '🚀', className: 'start-marker', iconSize: [24, 24] });
                const startMarker = L.marker(firstTrack[0], { icon: startIcon }).bindPopup('🚀 Start').addTo(map);
                currentDetailMarkers.push(startMarker);
            }
            if (lastTrack.length > 0) {
                const endIcon = L.divIcon({ html: '🏁', className: 'end-marker', iconSize: [24, 24] });
                const endMarker = L.marker(lastTrack[lastTrack.length - 1], { icon: endIcon }).bindPopup('🏁 Finish').addTo(map);
                currentDetailMarkers.push(endMarker);
            }

            createElevationChart(allTrackPoints);
            displayTrackStats(allTrackPoints.flat(), tourConfig);
        } catch (error) {
            document.getElementById('trackInfo').innerHTML = `<div class="error">❌ <strong>Error processing GPX file</strong><br><small>${error.message}</small></div>`;
        }
    }

    // --- UI DISPLAY ---
    function displayTrackStats(trackPoints, tourConfig) {
        const stats = calculateStats(trackPoints);
        document.title = tourConfig.name || 'Tour';
        document.getElementById('tour-title').textContent = tourConfig.name || 'Tour';
        
        const statsContainer = document.getElementById('trackInfo');
        statsContainer.className = 'stats';
        
        const linkedComments = tourConfig.comments ? linkify(tourConfig.comments) : '-';
        
        statsContainer.innerHTML = `
            <table class="stats-table">
                <tr><td class="stat-label">Distance:</td><td class="stat-value">${stats.distance.toFixed(2)} km</td></tr>
                <tr><td class="stat-label">Elevation:</td><td class="stat-value">${stats.elevationGain.toFixed(0)} D+</td></tr>
                <tr><td class="stat-label">Date:</td><td class="stat-value">${tourConfig.date || '-'}</td></tr>
                <tr><td class="stat-label">Comments:</td><td class="stat-value">${linkedComments}</td></tr>
                <tr><td class="stat-label">GPX file:</td><td class="stat-value"><a href="${tourConfig.gpxPath}" download="${tourConfig.gpx}">${tourConfig.gpx}</a></td></tr>
            </table>
        `;
        
        const additionalInfoPanel = document.getElementById('additionalInfo');
        let photoHTML = '<div class="photos-container">';
        for (let i = 1; i <= 3; i++) {
            photoHTML += `<a href="${tourConfig.basePath}/${i}.jpg" target="_blank" rel="noopener noreferrer"><img src="${tourConfig.basePath}/${i}.jpg" alt="Photo ${i}" loading="lazy"></a>`;
        }
        photoHTML += '</div>';
        additionalInfoPanel.innerHTML = photoHTML;
    }

    function createElevationChart(allTrackPoints) {
        const elevationContainer = document.getElementById('elevation');
        const stats = calculateStats(allTrackPoints.flat());
        
        function renderChart() {
            const containerWidth = elevationContainer.offsetWidth;
            const width = Math.max(300, containerWidth - 30);
            const height = 190;
            const padding = 45;

            const flatPoints = allTrackPoints.flat();
            const elevations = flatPoints.map(point => point[2]);
            const minEle = Math.min(...elevations);
            const maxEle = Math.max(...elevations);
            const eleRange = maxEle - minEle || 100;

            const numTicks = 6;
            const tickStep = Math.ceil(eleRange / numTicks / 50) * 50;
            const minTick = Math.floor(minEle / tickStep) * tickStep;
            const maxTick = Math.ceil(maxEle / tickStep) * tickStep;

            function getDistanceStep(totalDistance) {
                if (totalDistance <= 5) return 1;
                else if (totalDistance <= 10) return 2;
                else if (totalDistance <= 25) return 5;
                else return 10;
            }

            const distanceStep = getDistanceStep(stats.distance);
            const numDistanceSteps = Math.ceil(stats.distance / distanceStep);
            
            let allPaths = '';
            let trackSeparators = '';
            const pathPoints = [];
            let cumulativeDistance = 0;

            allTrackPoints.forEach((trackPoints, trackIndex) => {
                if (trackPoints.length === 0) return;
                
                const trackColor = config.trackColors[trackIndex % config.trackColors.length];
                let pathData = '';
                const trackPathPoints = [];

                trackPoints.forEach((point, pointIndex) => {
                    const ele = point[2];
                    if (pointIndex > 0) {
                        const prevPoint = trackPoints[pointIndex - 1];
                        cumulativeDistance += calculateDistance(prevPoint[0], prevPoint[1], point[0], point[1]) / 1000;
                    }

                    const x = padding + (cumulativeDistance / stats.distance) * (width - 2 * padding);
                    const y = height - padding - ((ele - minEle) / eleRange) * (height - 2 * padding);

                    trackPathPoints.push({ x, y, trackIndex, elevation: ele, trackPoint: point, distance: cumulativeDistance });
                    if (pointIndex === 0) { pathData += `M ${x} ${y}`; } else { pathData += ` L ${x} ${y}`; }
                });

                pathPoints.push(...trackPathPoints);
                allPaths += `<path d="${pathData}" fill="none" stroke="${trackColor}" stroke-width="2.5" opacity="0.9"/>`;

                if (trackIndex > 0 && trackPathPoints.length > 0) {
                    const separatorX = trackPathPoints[0].x;
                    trackSeparators += `<line x1="${separatorX}" y1="${padding}" x2="${separatorX}" y2="${height - padding}" stroke="#666" stroke-width="1" stroke-dasharray="3,3" opacity="0.7"/>`;
                }
            });

            let gridLines = '';
            let elevationLabels = '';
            for (let tick = minTick; tick <= maxTick; tick += tickStep) {
                if (tick >= minEle && tick <= maxEle) {
                    const y = height - padding - ((tick - minEle) / eleRange) * (height - 2 * padding);
                    gridLines += `<line x1="${padding}" y1="${y}" x2="${width - padding}" y2="${y}" stroke="#e0e0e0" stroke-width="1" stroke-dasharray="2,2"/>`;
                    elevationLabels += `<text x="${padding - 5}" y="${y + 4}" font-size="11" fill="#666" text-anchor="end">${tick.toFixed(0)}m</text>`;
                }
            }

            let distanceGridLines = '';
            let distanceLabels = '';
            for (let i = 0; i <= numDistanceSteps; i++) {
                const distance = i * distanceStep;
                if (distance <= stats.distance) {
                    const x = padding + (distance / stats.distance) * (width - 2 * padding);
                    distanceGridLines += `<line x1="${x}" y1="${padding}" x2="${x}" y2="${height - padding}" stroke="#e0e0e0" stroke-width="1" stroke-dasharray="2,2"/>`;
                    distanceLabels += `<text x="${x}" y="${height - 25}" font-size="11" fill="#666" text-anchor="middle">${distance.toFixed(0)}km</text>`;
                }
            }

            elevationContainer.innerHTML = `<div style="background: white; border-radius: 6px; padding: 15px 0; height: 100%; box-sizing: border-box;"><div style="position: relative;"><svg id="elevation-chart" width="100%" height="${height}" style="cursor: crosshair;"><rect width="100%" height="100%" fill="#fafafa"/>${gridLines}${distanceGridLines}${allPaths}${trackSeparators}<line id="hover-line" x1="0" y1="${padding}" x2="0" y2="${height - padding}" stroke="#e74c3c" stroke-width="2" opacity="0"/><circle id="hover-circle" cx="0" cy="0" r="4" fill="#e74c3c" opacity="0"/>${elevationLabels}${distanceLabels}<text x="${(width-padding)/2 + padding}" y="15" font-size="12" fill="#333" text-anchor="middle" font-weight="bold">Altitude (m)</text><text x="${(width-padding)/2 + padding}" y="${height - 8}" font-size="12" fill="#333" text-anchor="middle" font-weight="bold">Distance (km)</text><rect width="100%" height="100%" fill="transparent" id="chart-overlay"/></svg><div id="elevation-tooltip" style="position: absolute; background: rgba(0,0,0,0.8); color: white; padding: 8px 12px; border-radius: 4px; font-size: 12px; pointer-events: none; opacity: 0; transition: opacity 0.2s; box-shadow: 0 2px 8px rgba(0,0,0,0.3);"><div id="tooltip-elevation" style="font-weight: bold;"></div><div id="tooltip-distance"></div><div id="tooltip-track" style="font-size: 10px; opacity: 0.8;"></div></div></div><div style="margin-top: 10px; font-size: 13px; color: #666; display: flex; justify-content: space-between; flex-wrap: wrap; gap: 10px;"><span><strong>Elevation +:</strong> ${stats.elevationGain.toFixed(0)}m</span><span><strong>Min/Max:</strong> ${minEle.toFixed(0)}m / ${maxEle.toFixed(0)}m</span><span><strong>Tracks:</strong> ${allTrackPoints.length}</span></div></div>`;
            addChartInteractivity(pathPoints, width, padding);
        }
        window.renderElevationChart = renderChart;
        renderChart();
    }

    function addChartInteractivity(pathPoints, width, padding) {
        const svg = document.getElementById('elevation-chart');
        const overlay = document.getElementById('chart-overlay');
        const hoverLine = document.getElementById('hover-line');
        const hoverCircle = document.getElementById('hover-circle');
        const tooltip = document.getElementById('elevation-tooltip');
        if (!svg || !overlay) return;

        let hoverMarker = null;
        overlay.addEventListener('mousemove', (e) => {
            const rect = svg.getBoundingClientRect();
            const mouseX = e.clientX - rect.left;
            if (mouseX >= padding && mouseX <= rect.width - padding) {
                let closestPoint = pathPoints[0];
                let minDiff = Infinity;
                for (const point of pathPoints) {
                    const diff = Math.abs(point.x - mouseX);
                    if (diff < minDiff) { minDiff = diff; closestPoint = point; }
                }
                if (closestPoint) {
                    const hoverColor = config.trackColors[closestPoint.trackIndex % config.trackColors.length];
                    hoverLine.setAttribute('x1', closestPoint.x);
                    hoverLine.setAttribute('x2', closestPoint.x);
                    hoverLine.setAttribute('stroke', hoverColor);
                    hoverLine.setAttribute('opacity', '0.7');
                    hoverCircle.setAttribute('cx', closestPoint.x);
                    hoverCircle.setAttribute('cy', closestPoint.y);
                    hoverCircle.setAttribute('fill', hoverColor);
                    hoverCircle.setAttribute('opacity', '1');
                    document.getElementById('tooltip-elevation').textContent = `${closestPoint.elevation.toFixed(0)}m`;
                    document.getElementById('tooltip-distance').textContent = `${closestPoint.distance.toFixed(2)}km`;
                    document.getElementById('tooltip-track').textContent = `Track ${closestPoint.trackIndex + 1}`;
                    tooltip.style.left = Math.min(closestPoint.x, width - 120) + 'px';
                    tooltip.style.top = Math.max(closestPoint.y - 70, 10) + 'px';
                    tooltip.style.opacity = '1';

                    if (currentDetailTracks.length > 0 && closestPoint.trackPoint) {
                        if (hoverMarker) detailMap.removeLayer(hoverMarker);
                        hoverMarker = L.circleMarker([closestPoint.trackPoint[0], closestPoint.trackPoint[1]], { radius: 6, color: hoverColor, fillColor: hoverColor, fillOpacity: 0.8, weight: 2 }).addTo(detailMap);
                    }
                }
            }
        });
        overlay.addEventListener('mouseleave', () => {
            hoverLine.setAttribute('opacity', '0');
            hoverCircle.setAttribute('opacity', '0');
            tooltip.style.opacity = '0';
            if (hoverMarker) { detailMap.removeLayer(hoverMarker); hoverMarker = null; }
        });
    }

    // --- UTILITY FUNCTIONS ---
    function linkify(text) {
        const urlRegex = /(\b(https?|ftp|file):\/\/[-A-Z0-9+&@#\/%?=~_|!:,.;]*[-A-Z0-9+&@#\/%=~_|])/ig;
        return text.replace(urlRegex, (url) => {
            return `<a href="${url}" target="_blank" rel="noopener noreferrer">${url}</a>`;
        });
    }

    function calculateStats(trackPoints) {
        let distance = 0, elevationGain = 0;
        let maxElevation = -Infinity, minElevation = Infinity;
        for (let i = 0; i < trackPoints.length; i++) {
            const ele = trackPoints[i][2];
            if (ele) { maxElevation = Math.max(maxElevation, ele); minElevation = Math.min(minElevation, ele); }
            if (i > 0) {
                distance += calculateDistance(trackPoints[i - 1][0], trackPoints[i - 1][1], trackPoints[i][0], trackPoints[i][1]);
                const eleDiff = trackPoints[i][2] - trackPoints[i - 1][2];
                if (eleDiff > 0) elevationGain += eleDiff;
            }
        }
        return { distance: distance / 1000, elevationGain, maxElevation, minElevation };
    }

    function calculateDistance(lat1, lon1, lat2, lon2) {
        const R = 6371e3;
        const φ1 = lat1 * Math.PI / 180, φ2 = lat2 * Math.PI / 180;
        const Δφ = (lat2 - lat1) * Math.PI / 180, Δλ = (lon2 - lon1) * Math.PI / 180;
        const a = Math.sin(Δφ / 2) * Math.sin(Δφ / 2) + Math.cos(φ1) * Math.cos(φ2) * Math.sin(Δλ / 2) * Math.sin(Δλ / 2);
        const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
        return R * c;
    }
    
    function getTourFolder() {
        const urlParams = new URLSearchParams(window.location.search);
        const params = Array.from(urlParams.keys());
        return params.length > 0 ? sanitizeFolderName(params[0]) : null;
    }

    function sanitizeFolderName(folderName) {
        if (!folderName || typeof folderName !== 'string') return null;
        const sanitized = folderName.replace(/\.\./g, '').replace(/[/\\]/g, '').replace(/[<>:"|?*]/g, '').trim();
        if (!/^[a-zA-Z0-9_-]+$/.test(sanitized)) return null;
        return sanitized.length > 0 ? sanitized : null;
    }

    function sanitizeFileName(fileName) {
        if (!fileName || typeof fileName !== 'string') return null;
        const sanitized = fileName.replace(/\.\./g, '').replace(/[/\\]/g, '').replace(/[<>:"|?*]/g, '').trim();
        if (!/^[a-zA-Z0-9._-]+$/.test(sanitized) || !sanitized.toLowerCase().endsWith('.gpx') || sanitized.length <= 4) return null;
        return sanitized;
    }

    // --- MAIN EXECUTION LOGIC ---
    async function main() {
        const tourFolder = getTourFolder();
        if (tourFolder) {
            showView('detail');
            loadTourData(tourFolder);
        } else {
            showView('overview');
            document.title = 'Hike and Run';
            try {
                const response = await fetch('tours/tours.json');
                if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
                allToursData = await response.json();                
                initializeOverviewMap(allToursData);
                renderTourList();
                setupCategoryPicker();
            } catch (error) {
                console.error("Could not load and render tour list:", error);
                document.getElementById('trackInfo').innerHTML = `<div class="error">Could not load tour list. Please check that a valid tours/tours.json file exists.</div>`;
            }
        }
    }

    window.addEventListener('resize', () => {
        if (window.renderElevationChart) { setTimeout(() => { window.renderElevationChart(); }, 100); }
        if (detailMap) { setTimeout(() => { detailMap.invalidateSize(); }, 100); }
        if (overviewMap) { setTimeout(() => { overviewMap.invalidateSize(); }, 100); }
    });
    
    main();
});