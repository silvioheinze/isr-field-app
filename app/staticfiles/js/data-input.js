// Global variables
var map;
var currentPoint = null;
var allFields = [];
var uploadedFiles = [];
var typologyData = null;
var markers = [];
var addPointMode = false;
var addPointMarker = null;
var lastAddedLatLng = null;
var gotoLocationMode = false;
var gotoLocationClickHandler = null;

// Mapping areas variables
var mappingAreasMode = false;
var mappingAreasPanelVisible = false;
var mappingAreaPolygons = [];
var collaboratorMappingAreaPolygons = [];
var currentDrawingPolygon = null;
var currentEditingPolygon = null;
var selectedMappingArea = null;
var drawControl = null;
var drawnItems = null;
var drawingPolygonPoints = [];
var drawingClickHandler = null;

function escapeHtml(value) {
    if (value === null || value === undefined) {
        return '';
    }
    return String(value)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

function normalizeFieldChoices(field) {
    var options = [];
    if (field && Array.isArray(field.typology_choices) && field.typology_choices.length > 0) {
        field.typology_choices.forEach(function(choice) {
            if (choice === null || choice === undefined) return;
            if (typeof choice === 'object') {
                var rawValue = choice.value !== undefined ? choice.value : (choice.code !== undefined ? choice.code : '');
                var label = choice.label || choice.name || rawValue;
                if (rawValue !== undefined && rawValue !== null && label !== undefined && label !== null) {
                    options.push({
                        value: String(rawValue),
                        label: String(label)
                    });
                }
            } else {
                options.push({
                    value: String(choice),
                    label: String(choice)
                });
            }
        });
    } else if (field && field.choices) {
        var rawChoices = Array.isArray(field.choices) ? field.choices : field.choices.split(',');
        rawChoices.forEach(function(choice) {
            if (choice === null || choice === undefined) return;
            var trimmed = typeof choice === 'string' ? choice.trim() : choice;
            if (trimmed !== '') {
                options.push({
                    value: String(trimmed),
                    label: String(trimmed)
                });
            }
        });
    }
    return options;
}

// Initialize the data input functionality
function initializeDataInput(typologyDataParam, fieldsData) {
    allFields = fieldsData || [];
    window.allFields = fieldsData || [];
    typologyData = typologyDataParam;

    initializeMap();
    setupEventListeners();
    initializeFileUpload();
    if (typeof initializeResponsiveLayout === 'function') {
        initializeResponsiveLayout();
    }
}

// Initialize the map
function initializeMap() {
    var defaultLat = (typeof window.mapDefaultLat === 'number') ? window.mapDefaultLat : 48.2082;
    var defaultLng = (typeof window.mapDefaultLng === 'number') ? window.mapDefaultLng : 16.3738;
    var defaultZoom = (typeof window.mapDefaultZoom === 'number') ? Math.max(1, Math.min(18, window.mapDefaultZoom)) : 11;
    map = L.map('map', {
        zoomControl: false,
        scrollWheelZoom: false,
        doubleClickZoom: false,
        boxZoom: false,
        keyboard: false,
        dragging: true,
        touchZoom: true
    }).setView([defaultLat, defaultLng], defaultZoom);
    
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '© OpenStreetMap contributors'
    }).addTo(map);

    map.on('click', function(e) {
        if (addPointMode) {
            addNewPoint(e.latlng);
        } else if (gotoLocationMode && gotoLocationClickHandler) {
            gotoLocationClickHandler(e);
        }
    });

    loadMapData();
}

// Load map data via AJAX
function loadMapData(preserveView) {
    var url = window.location.origin + '/datasets/' + getDatasetId() + '/map-data/';
    fetch(url, {
        method: 'GET',
        credentials: 'same-origin',
        headers: { 'X-Requested-With': 'XMLHttpRequest' }
    })
    .then(response => response.json())
    .then(data => {
        if (data.map_data) addMarkersToMap(data.map_data, preserveView);
        loadCollaboratorMappingAreaOutlines();
    })
    .catch(() => {
        loadCollaboratorMappingAreaOutlines();
    });
}

// Load fields from API when window.allFields is empty
function loadFieldsFromAPI() {
    var pathParts = window.location.pathname.split('/');
    var datasetId = null;
    for (var i = 0; i < pathParts.length; i++) {
        if (pathParts[i] === 'datasets' && i + 1 < pathParts.length) {
            datasetId = pathParts[i + 1];
            break;
        }
    }
    
    if (!datasetId) {
        console.error('Could not determine dataset ID from URL');
        return;
    }
    
    var url = window.location.origin + '/datasets/' + datasetId + '/fields/';
    
    fetch(url, {
        method: 'GET',
        credentials: 'same-origin',
        headers: { 'X-Requested-With': 'XMLHttpRequest' }
    })
    .then(response => response.json())
    .then(data => {
        if (data.fields) {
            window.allFields = data.fields;
            allFields = data.fields;
            
            if (currentPoint) {
                showGeometryDetails(currentPoint);
            }
        } else {
            console.error('No fields in API response');
        }
    })
    .catch(error => {
        console.error('Error loading fields from API:', error);
        var entriesList = document.getElementById('entriesList');
        if (entriesList) {
            entriesList.innerHTML = '<div class="alert alert-info"><i class="bi bi-info-circle"></i> No fields configured for this dataset.</div>';
        }
    });
}

// Load detailed data for a specific geometry point
function loadGeometryDetails(geometryId) {
    var url = window.location.origin + '/datasets/geometry/' + geometryId + '/details/';
    return fetch(url, {
        method: 'GET',
        credentials: 'same-origin',
        headers: { 'X-Requested-With': 'XMLHttpRequest' }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success && data.geometry) return data.geometry;
        throw new Error('Failed to load geometry details');
    });
}

// Add markers to the map
function addMarkersToMap(mapData, preserveView) {
    // Save current map view if preserveView is true
    var savedView = null;
    if (preserveView && map) {
        savedView = {
            center: map.getCenter(),
            zoom: map.getZoom()
        };
    }
    
    markers.forEach(marker => map.removeLayer(marker));
    markers = [];
    if (!Array.isArray(mapData) || mapData.length === 0) return;

    mapData.forEach(function(point) {
        var marker = L.circleMarker([point.lat, point.lng], {
            radius: 8,
            fillColor: '#0047BB',
            color: '#001A70',
            weight: 2,
            opacity: 1,
            fillOpacity: 0.8
        });
        marker.pointData = point;
        marker.on('click', function() { selectPoint(point); });
        marker.addTo(map);
        markers.push(marker);
    });

    // Only focus on all points if we're not preserving the view
    if (!preserveView) {
        focusOnAllPoints();
    } else if (savedView) {
        // Restore the saved view
        map.setView(savedView.center, savedView.zoom);
    }

    // Auto-select newly added marker if we have a cached location
    if (lastAddedLatLng && markers.length > 0) {
        var nearest = null;
        var bestDist = Infinity;
        markers.forEach(function(m) {
            var mp = m.pointData || m.geometryData;
            if (!mp) return;
            var dLat = (mp.lat - lastAddedLatLng.lat);
            var dLng = (mp.lng - lastAddedLatLng.lng);
            var dist = dLat * dLat + dLng * dLng;
            if (dist < bestDist) { bestDist = dist; nearest = m; }
        });
        if (nearest) selectPoint(nearest.pointData || nearest.geometryData);
        lastAddedLatLng = null;
    }
}

// Focus on all points on the map
function focusOnAllPoints() {
    if (!map || markers.length === 0) return;
    var group = new L.featureGroup(markers);
    map.fitBounds(group.getBounds().pad(0.1));
}

// Select a point and show its details
function selectPoint(point) {
    currentPoint = point;
    markers.forEach(marker => {
        var markerId = null;
        if (marker.pointData && marker.pointData.id) markerId = marker.pointData.id;
        else if (marker.geometryData && marker.geometryData.id) markerId = marker.geometryData.id;
        if (markerId === point.id) {
            marker.setStyle({ fillColor: '#FFB81C', color: '#FFB81C' });
        } else {
            marker.setStyle({ fillColor: '#0047BB', color: '#001A70' });
        }
    });

    loadGeometryDetails(point.id)
        .then(detailedPoint => { showGeometryDetails(detailedPoint); })
        .catch(() => { showGeometryDetails(point); });
}

// Show geometry details
function showGeometryDetails(point) {
    currentPoint = point;
    // Reset selected entry when switching to a new geometry
    selectedEntryId = null;

    if (!window.allFields || window.allFields.length === 0) {
        try {
            var allFieldsElement = document.getElementById('allFields');
            if (allFieldsElement && allFieldsElement.textContent) {
                window.allFields = JSON.parse(allFieldsElement.textContent);
                allFields = window.allFields;
            } else {
                window.allFields = [];
                allFields = [];
            }
        } catch (e) {
            window.allFields = [];
            allFields = [];
        }
    }

    if (!window.allFields || window.allFields.length === 0) {
        loadFieldsFromAPI();
        return;
    }

    var detailsDiv = document.getElementById('geometryDetails');
    detailsDiv.classList.add('active');
    generateEntriesTable(point);
    loadUploadedFiles();
    if (typeof adjustColumnLayout === 'function') adjustColumnLayout();
}

// Global variable to track selected entry
var selectedEntryId = null;

// Generate entries table
function generateEntriesTable(point) {
    var entriesList = document.getElementById('entriesList');
    if (!entriesList) return;

    var entriesHtml = '';
    console.log('generateEntriesTable called with point:', point);
    console.log('window.allFields:', window.allFields);
    
    // Sort entries by year (newest first)
    var sortedEntries = (point.entries || []).sort(function(a, b) {
        return (b.year || 0) - (a.year || 0);
    });
    
    // Entry Selection Dropdown - only show if multiple entries are allowed and there are entries
    if (window.allowMultipleEntries && sortedEntries.length > 0) {
        // Horizontal entry list with "All Entries (N)" header and entry badges
        entriesHtml += '<div class="card mb-3">';
        entriesHtml += '<div class="card-header bg-light fw-semibold">';
        entriesHtml += '<i class="bi bi-list-ul me-2"></i>';
        entriesHtml += 'All Entries (' + sortedEntries.length + ')';
        entriesHtml += '</div>';
        entriesHtml += '<div class="card-body">';
        // Determine initial selection before building badges
        var hasInitialSelection = false;
        if (sortedEntries.length > 0 && selectedEntryId === null) {
            selectedEntryId = sortedEntries[0].id;
            hasInitialSelection = true;
        }
        entriesHtml += '<div id="entriesHorizontalList" class="d-flex flex-wrap gap-2 mb-3">';
        sortedEntries.forEach(function(entry, index) {
            var isSelected = (selectedEntryId !== null && selectedEntryId !== 'new' &&
                (entry.id === selectedEntryId || entry.id === parseInt(selectedEntryId))) ||
                (index === 0 && hasInitialSelection);
            var badgeClass = 'entry-badge btn btn-sm btn-outline-secondary' + (isSelected ? ' entry-badge-selected' : '');
            entriesHtml += '<button type="button" class="' + badgeClass + '" data-entry-id="' + entry.id + '" onclick="selectEntryFromBadge(' + entry.id + ')">';
            entriesHtml += escapeHtml(entry.name || 'Unnamed Entry');
            if (entry.year) entriesHtml += ' <span class="text-muted">(' + escapeHtml(String(entry.year)) + ')</span>';
            if (entry.user) entriesHtml += ' <span class="text-muted">- ' + escapeHtml(entry.user) + '</span>';
            entriesHtml += '</button>';
        });
        entriesHtml += '</div>';
        entriesHtml += '<div class="mb-3">';
        entriesHtml += '<select class="form-select" id="entrySelector" onchange="selectEntryFromDropdown(this.value)">';
        
        // Add option for creating new entry
        var isNewSelected = selectedEntryId === 'new';
        entriesHtml += '<option value="new"' + (isNewSelected ? ' selected' : '') + '>';
        entriesHtml += '➕ Create New Entry';
        entriesHtml += '</option>';
        
        // Add options for existing entries
        sortedEntries.forEach(function(entry, index) {
            var isSelected = false;
            if (selectedEntryId !== null && selectedEntryId !== 'new') {
                var entryIdNum = typeof selectedEntryId === 'string' ? parseInt(selectedEntryId) : selectedEntryId;
                isSelected = entry.id === entryIdNum || entry.id === selectedEntryId;
            } else if (index === 0 && hasInitialSelection) {
                isSelected = true;
            }
            
            var entryName = entry.name || 'Unnamed Entry';
            var entryYear = entry.year ? ' (' + entry.year + ')' : '';
            var entryUser = entry.user ? ' - ' + entry.user : '';
            
            entriesHtml += '<option value="' + entry.id + '"' + (isSelected ? ' selected' : '') + '>';
            entriesHtml += escapeHtml(entryName) + escapeHtml(entryYear) + escapeHtml(entryUser);
            entriesHtml += '</option>';
        });
        
        entriesHtml += '</select>';
        entriesHtml += '</div>';
        entriesHtml += '</div>';
        entriesHtml += '</div>';
    }
    
    // Entry Detail Form Section - Show selected entry or new entry form
    var selectedEntry = null;
    var selectedEntryIndex = -1;
    var showNewEntryForm = false;
    
    // If multiple entries are not allowed, automatically select the first (and only) entry if it exists
    if (!window.allowMultipleEntries && sortedEntries.length > 0) {
        selectedEntry = sortedEntries[0];
        selectedEntryIndex = 0;
        selectedEntryId = sortedEntries[0].id;
    }
    // Check if we should show new entry form
    // Show new entry form if "new" is selected, or if no entries exist
    else if (selectedEntryId === 'new' || (selectedEntryId === null && sortedEntries.length === 0)) {
        showNewEntryForm = true;
    } else {
        // Find the selected entry
        sortedEntries.forEach(function(entry, index) {
            var entryIdNum = typeof selectedEntryId === 'string' ? parseInt(selectedEntryId) : selectedEntryId;
            if (entry.id === entryIdNum || entry.id === selectedEntryId) {
                selectedEntry = entry;
                selectedEntryIndex = index;
            }
        });
    }
    
    // Show selected entry form
    if (selectedEntry) {
        var entry = selectedEntry;
        var entryIndex = selectedEntryIndex;
        
        entriesHtml += '<div class="card mb-3 border-info">';
        entriesHtml += '<div class="card-header bg-info bg-opacity-10 d-flex justify-content-between align-items-center">';
        entriesHtml += '<h6 class="mb-0 fw-semibold"><i class="bi bi-pencil-square me-2"></i>' + (entry.name || 'Unnamed Entry') + '</h6>';
        entriesHtml += '<small class="text-muted">Editing Entry</small>';
        entriesHtml += '</div>';
        entriesHtml += '<div class="card-body">';
        
        // Create form for this entry
        entriesHtml += '<form class="entry-form" data-entry-id="' + entry.id + '">';
        
        // Dynamic fields - render all configured fields from window.allFields or allFields
        var fieldsToUse = window.allFields || allFields || [];
        
        if (fieldsToUse && fieldsToUse.length > 0) {
            // Sort fields by order (treat negative values as last)
            var sortedFields = fieldsToUse.sort(function(a, b) {
                var orderA = a.order || 0;
                var orderB = b.order || 0;
                // Treat negative numbers as very large numbers (appear last)
                if (orderA < 0) orderA = 999999;
                if (orderB < 0) orderB = 999999;
                return orderA - orderB;
            });
            
            // Check if there are any enabled fields
            var hasEnabledFields = sortedFields.some(function(field) {
                return field.enabled;
            });
            
            if (hasEnabledFields) {
                sortedFields.forEach(function(field) {
                    if (field.enabled) {
                    var value = '';
                    if (entry[field.field_name] !== undefined) {
                        value = entry[field.field_name];
                    }
                    
                    if (field.field_type === 'headline') {
                        entriesHtml += '<div class="mb-2">';
                        entriesHtml += createFormFieldInput(field, value, entryIndex);
                        entriesHtml += '</div>';
                    } else {
                        entriesHtml += '<div class="mb-3">';
                        entriesHtml += '<label for="field_' + field.field_name + '_' + entryIndex + '" class="form-label">';
                        entriesHtml += field.label;
                        if (field.required) {
                            entriesHtml += ' <span class="text-danger">*</span>';
                        }
                        entriesHtml += '</label>';
                        var inputHtml = createFormFieldInput(field, value, entryIndex);
                        entriesHtml += inputHtml;
                        if (field.help_text) {
                            entriesHtml += '<div class="form-text">' + field.help_text + '</div>';
                        }
                        entriesHtml += '</div>';
                    }
                    }
                });
            } else {
                entriesHtml += '<div class="alert alert-info">';
                entriesHtml += '<i class="bi bi-info-circle"></i> No fields configured for this dataset.';
                entriesHtml += '</div>';
            }
        } else {
            entriesHtml += '<div class="alert alert-info">';
            entriesHtml += '<i class="bi bi-info-circle"></i> No fields configured for this dataset.';
            entriesHtml += '</div>';
        }
        
        entriesHtml += '</form>';
        entriesHtml += '</div>';
        entriesHtml += '</div>';
    }
    
    // Show new entry form if selected
    if (showNewEntryForm) {
        entriesHtml += '<div class="card mb-3 new-entry-form border-success">';
        entriesHtml += '<div class="card-header bg-success bg-opacity-10 fw-semibold">';
        entriesHtml += '<i class="bi bi-plus-circle me-2"></i>' + (window.translations?.createEntry || 'Create New Entry');
        entriesHtml += '</div>';
        entriesHtml += '<div class="card-body">';
        
        // Entry name field
        entriesHtml += '<div class="mb-3">';
        entriesHtml += '<label for="new-entry-name" class="form-label">Entry Name <span class="text-danger">*</span></label>';
        entriesHtml += '<input type="text" class="form-control" id="new-entry-name" placeholder="Enter entry name" value="' + point.id_kurz + '">';
        entriesHtml += '</div>';
        
        // Dynamic fields for new entry
        var fieldsToUse = window.allFields || allFields || [];
        console.log('New entry form - Checking window.allFields:', fieldsToUse);
        
        if (fieldsToUse && fieldsToUse.length > 0) {
            // Sort fields by order (treat negative values as last)
            var sortedFields = fieldsToUse.sort(function(a, b) {
                var orderA = a.order || 0;
                var orderB = b.order || 0;
                // Treat negative numbers as very large numbers (appear last)
                if (orderA < 0) orderA = 999999;
                if (orderB < 0) orderB = 999999;
                return orderA - orderB;
            });
            
            // Check if there are any enabled fields
            var hasEnabledFields = sortedFields.some(function(field) {
                return field.enabled;
            });
            console.log('New entry form - Has enabled fields:', hasEnabledFields);
            
            if (hasEnabledFields) {
                sortedFields.forEach(function(field) {
                    if (field.enabled) {
                        console.log('New entry form - Rendering field:', field.field_name);
                        if (field.field_type === 'headline') {
                            entriesHtml += '<div class="mb-2">';
                            entriesHtml += createFormFieldInput(field, '', -1);
                            entriesHtml += '</div>';
                        } else {
                            entriesHtml += '<div class="mb-3">';
                            entriesHtml += '<label for="field_' + field.field_name + '" class="form-label">';
                            entriesHtml += field.label;
                            if (field.required) {
                                entriesHtml += ' <span class="text-danger">*</span>';
                            }
                            entriesHtml += '</label>';
                            var inputHtml = createFormFieldInput(field, '', -1); // -1 indicates new entry
                            entriesHtml += inputHtml;
                            if (field.help_text) {
                                entriesHtml += '<div class="form-text">' + field.help_text + '</div>';
                            }
                            entriesHtml += '</div>';
                        }
                    }
                });
            } else {
                entriesHtml += '<div class="alert alert-info">';
                entriesHtml += '<i class="bi bi-info-circle"></i> No fields configured for this dataset.';
                entriesHtml += '</div>';
            }
        } else {
            entriesHtml += '<div class="alert alert-info">';
            entriesHtml += '<i class="bi bi-info-circle"></i> No fields configured for this dataset.';
            entriesHtml += '</div>';
        }
        
        entriesHtml += '</div>';
        entriesHtml += '</div>';
    }
    
    // Add action buttons
    entriesHtml += '<div class="mt-3 d-flex gap-2 flex-wrap">';
    if (showNewEntryForm) {
        entriesHtml += '<button type="button" class="btn btn-primary" onclick="createEntry()">';
        entriesHtml += '<i class="bi bi-plus-circle"></i> ' + (window.translations?.createEntry || 'Create Entry');
        entriesHtml += '</button>';
    }
    if (selectedEntry) {
        entriesHtml += '<button type="button" class="btn btn-success" onclick="saveEntries()">';
        entriesHtml += '<i class="bi bi-save"></i> ' + (window.translations?.saveEntries || 'Save Changes');
        entriesHtml += '</button>';
        if (window.allowMultipleEntries) {
            entriesHtml += '<button type="button" class="btn btn-outline-secondary" id="copyEntryBtn" onclick="copyToNewEntry(' + selectedEntry.id + ', ' + selectedEntryIndex + ', this)">';
            entriesHtml += '<i class="bi bi-files"></i> Copy</button>';
        }
        if (currentPoint && currentPoint.lat && currentPoint.lng) {
            var googleStreetViewUrl = 'https://www.google.com/maps/@?api=1&map_action=pano&viewpoint=' + currentPoint.lat + ',' + currentPoint.lng;
            entriesHtml += '<a href="' + googleStreetViewUrl + '" class="btn btn-outline-primary" target="_blank" rel="noopener noreferrer">';
            entriesHtml += '<i class="bi bi-geo-alt"></i> Street View</a>';
        }
        entriesHtml += '<a href="/entries/' + selectedEntry.id + '/" class="btn btn-outline-info" target="_blank">';
        entriesHtml += '<i class="bi bi-eye"></i> View Details</a>';
    }
    entriesHtml += '</div>';
    
    entriesList.innerHTML = entriesHtml;
}

// Select an entry from the dropdown
function selectEntryFromDropdown(value) {
    if (value === 'new') {
        selectedEntryId = 'new'; // Use 'new' string to distinguish from null
    } else {
        selectedEntryId = value ? parseInt(value) : null;
    }
    // Regenerate the entries table to show the selected entry
    if (currentPoint) {
        generateEntriesTable(currentPoint);
    }
}

// Legacy function for backward compatibility (if needed)
function selectEntry(entryId, entryIndex) {
    selectedEntryId = entryId ? parseInt(entryId) : null;
    // Update the dropdown to reflect the selection
    var selector = document.getElementById('entrySelector');
    if (selector) {
        selector.value = entryId || 'new';
    }
    // Regenerate the entries table to show the selected entry
    if (currentPoint) {
        generateEntriesTable(currentPoint);
    }
}

// Legacy helper used by horizontal entry list badges
function selectEntryFromBadge(entryId) {
    if (!entryId) {
        return;
    }
    selectedEntryId = parseInt(entryId);
    if (currentPoint) {
        generateEntriesTable(currentPoint);
    }
    var selector = document.getElementById('entrySelector');
    if (selector) {
        selector.value = entryId;
    }
}

// Legacy badge updater to support horizontal entry list tests
function updateEntryBadges(sortedEntries) {
    var badges = document.querySelectorAll('.entry-badge');
    if (!badges || badges.length === 0) {
        return;
    }
    badges.forEach(function(badge, index) {
        badge.classList.remove('entry-badge-selected');
        var badgeEntryId = parseInt(badge.getAttribute('data-entry-id'));
        if (selectedEntryId && badgeEntryId === selectedEntryId) {
            badge.classList.add('entry-badge-selected');
        }
        if (index < sortedEntries.length) {
            var entry = sortedEntries[index];
            badge.innerHTML = escapeHtml(entry.name || 'Unnamed Entry') +
                (entry.year ? ' <span class="text-muted">(' + escapeHtml(String(entry.year)) + ')</span>' : '') +
                (entry.user ? ' <span class="text-muted">- ' + escapeHtml(entry.user) + '</span>' : '');
        }
    });
}

// Create form field input based on field configuration
function createFormFieldInput(field, value, entryIndex) {
    var inputHtml = '';
    var fieldId = 'field_' + field.field_name;
    var fieldName = 'fields[' + field.field_name + ']';
    var fieldValue = value || '';
    
    // Add entry index to field name and ID for existing entries
    if (entryIndex >= 0) {
        fieldId += '_' + entryIndex;
        fieldName = 'fields[' + field.field_name + '][' + entryIndex + ']';
    }
    
    switch (field.field_type) {
        case 'headline':
            inputHtml = '<div class="headline-field small text-muted text-uppercase fw-semibold mt-3 mb-2">' + escapeHtml(field.label || '') + '</div>';
            break;
        case 'text':
            inputHtml = '<input type="text" class="form-control" id="' + fieldId + '" name="' + fieldName + '" value="' + fieldValue + '" placeholder="' + (field.placeholder || 'Enter ' + field.label) + '"';
            if (field.required) inputHtml += ' required';
            if (field.max_length) inputHtml += ' maxlength="' + field.max_length + '"';
            if (field.non_editable) inputHtml += ' readonly';
            inputHtml += '>';
            break;
            
        case 'textarea':
            inputHtml = '<textarea class="form-control" id="' + fieldId + '" name="' + fieldName + '" placeholder="' + (field.placeholder || 'Enter ' + field.label) + '"';
            if (field.required) inputHtml += ' required';
            if (field.max_length) inputHtml += ' maxlength="' + field.max_length + '"';
            inputHtml += ' rows="' + (field.rows || 4) + '"';
            if (field.non_editable) inputHtml += ' readonly';
            inputHtml += '>' + escapeHtml(fieldValue || '') + '</textarea>';
            break;
            
        case 'integer':
            inputHtml = '<input type="number" class="form-control" id="' + fieldId + '" name="' + fieldName + '" value="' + fieldValue + '" placeholder="' + (field.placeholder || 'Enter ' + field.label) + '"';
            if (field.required) inputHtml += ' required';
            if (field.min_value !== undefined) inputHtml += ' min="' + field.min_value + '"';
            if (field.max_value !== undefined) inputHtml += ' max="' + field.max_value + '"';
            if (field.non_editable) inputHtml += ' readonly';
            inputHtml += '>';
            break;
            
        case 'float':
            inputHtml = '<input type="number" step="0.01" class="form-control" id="' + fieldId + '" name="' + fieldName + '" value="' + fieldValue + '" placeholder="' + (field.placeholder || 'Enter ' + field.label) + '"';
            if (field.required) inputHtml += ' required';
            if (field.min_value !== undefined) inputHtml += ' min="' + field.min_value + '"';
            if (field.max_value !== undefined) inputHtml += ' max="' + field.max_value + '"';
            if (field.non_editable) inputHtml += ' readonly';
            inputHtml += '>';
            break;
            
        case 'boolean':
            inputHtml = '<select class="form-select" id="' + fieldId + '" name="' + fieldName + '"';
            if (field.required) inputHtml += ' required';
            if (field.non_editable) inputHtml += ' disabled';
            inputHtml += '>';
            inputHtml += '<option value="">' + (field.placeholder || 'Select option') + '</option>';
            inputHtml += '<option value="true"' + (fieldValue === 'true' || fieldValue === true ? ' selected' : '') + '>' + (field.true_label || 'Yes') + '</option>';
            inputHtml += '<option value="false"' + (fieldValue === 'false' || fieldValue === false ? ' selected' : '') + '>' + (field.false_label || 'No') + '</option>';
            inputHtml += '</select>';
            if (field.non_editable) {
                inputHtml += '<input type="hidden" name="' + fieldName + '" value="' + fieldValue + '">';
            }
            break;
            
        case 'choice':
            var options = normalizeFieldChoices(field);
            var fieldValueStr = fieldValue !== undefined && fieldValue !== null ? String(fieldValue) : '';
            inputHtml = '<select class="form-select" id="' + fieldId + '" name="' + fieldName + '"';
            if (field.required) inputHtml += ' required';
            if (field.non_editable) inputHtml += ' disabled';
            inputHtml += '>';
            inputHtml += '<option value="">' + escapeHtml(field.placeholder || 'Select option') + '</option>';

            options.forEach(function(option) {
                var optionValue = option.value !== undefined ? option.value : '';
                var optionLabel = option.label !== undefined ? option.label : optionValue;
                var selected = fieldValueStr !== '' && fieldValueStr === String(optionValue) ? ' selected' : '';
                inputHtml += '<option value="' + escapeHtml(optionValue) + '"' + selected + '>' + escapeHtml(optionLabel) + '</option>';
            });

            inputHtml += '</select>';
            if (field.non_editable) {
                inputHtml += '<input type="hidden" name="' + fieldName + '" value="' + fieldValue + '">';
            }
            break;

        case 'multiple_choice':
            var mcOptions = normalizeFieldChoices(field);
            var selectedValues = [];
            try {
                if (fieldValue !== undefined && fieldValue !== null) {
                    var fv = String(fieldValue);
                    if (fv.trim().startsWith('[')) {
                        selectedValues = JSON.parse(fv);
                    } else if (fv.includes(',')) {
                        selectedValues = fv.split(',').map(function(v) { return v.trim(); });
                    } else if (fv.trim()) {
                        selectedValues = [fv.trim()];
                    }
                }
            } catch (e) {
                selectedValues = fieldValue ? [String(fieldValue)] : [];
            }
            if (mcOptions.length > 0) {
                inputHtml = '<div class="multiple-choice-group" id="' + fieldId + '_group">';
                mcOptions.forEach(function(option) {
                    var optionValue = option.value !== undefined ? String(option.value) : '';
                    var optionLabel = option.label !== undefined ? option.label : optionValue;
                    var checkboxId = fieldId + '_' + optionValue.replace(/[^a-zA-Z0-9]/g, '_');
                    var checked = selectedValues.indexOf(optionValue) !== -1 ? ' checked' : '';
                    inputHtml += '<div class="form-check">';
                    inputHtml += '<input class="form-check-input" type="checkbox" id="' + checkboxId + '" value="' + escapeHtml(optionValue) + '"' + checked;
                    if (field.non_editable) inputHtml += ' disabled';
                    inputHtml += '>';
                    inputHtml += '<label class="form-check-label" for="' + checkboxId + '">' + escapeHtml(optionLabel) + '</label>';
                    inputHtml += '</div>';
                });
                inputHtml += '</div>';
                inputHtml += '<input type="hidden" name="' + fieldName + '" id="' + fieldId + '_hidden" value=\'' + JSON.stringify(selectedValues) + '\'>';
                if (!field.non_editable) {
                    inputHtml += '<script>';
                    inputHtml += '(function() {';
                    inputHtml += '  var group = document.getElementById("' + fieldId + '_group");';
                    inputHtml += '  var hidden = document.getElementById("' + fieldId + '_hidden");';
                    inputHtml += '  if (group && hidden) {';
                    inputHtml += '    group.addEventListener("change", function(e) {';
                    inputHtml += '      if (e.target.type === "checkbox") {';
                    inputHtml += '        var checkboxes = group.querySelectorAll("input[type=checkbox]");';
                    inputHtml += '        var selected = [];';
                    inputHtml += '        for (var i = 0; i < checkboxes.length; i++) {';
                    inputHtml += '          if (checkboxes[i].checked) selected.push(checkboxes[i].value);';
                    inputHtml += '        }';
                    inputHtml += '        hidden.value = JSON.stringify(selected);';
                    inputHtml += '      }';
                    inputHtml += '    });';
                    inputHtml += '  }';
                    inputHtml += '})();';
                    inputHtml += '</script>';
                }
            } else {
                inputHtml = '<input type="text" class="form-control" id="' + fieldId + '" name="' + fieldName + '" value="' + fieldValue + '" placeholder="' + (field.placeholder || 'Enter ' + field.label) + '"';
                if (field.required) inputHtml += ' required';
                if (field.non_editable) inputHtml += ' readonly';
                inputHtml += '>';
            }
            break;
            
        case 'date':
            // Only set value if it's a valid date format (YYYY-MM-DD)
            var dateValue = '';
            if (fieldValue && typeof fieldValue === 'string' && fieldValue.match(/^\d{4}-\d{2}-\d{2}$/)) {
                dateValue = fieldValue;
            } else if (fieldValue && typeof fieldValue === 'string' && fieldValue.length > 0) {
                // Try to parse date if it's in a different format
                try {
                    var date = new Date(fieldValue);
                    if (!isNaN(date.getTime())) {
                        dateValue = date.toISOString().split('T')[0];
                    }
                } catch (e) {
                    // Invalid date, leave empty
                    dateValue = '';
                }
            }
            inputHtml = '<input type="date" class="form-control" id="' + fieldId + '" name="' + fieldName + '" value="' + dateValue + '"';
            if (field.required) inputHtml += ' required';
            if (field.min_date) inputHtml += ' min="' + field.min_date + '"';
            if (field.max_date) inputHtml += ' max="' + field.max_date + '"';
            if (field.non_editable) inputHtml += ' readonly';
            inputHtml += '>';
            break;
            
        case 'datetime':
            inputHtml = '<input type="datetime-local" class="form-control" id="' + fieldId + '" name="' + fieldName + '" value="' + fieldValue + '"';
            if (field.required) inputHtml += ' required';
            if (field.min_date) inputHtml += ' min="' + field.min_date + '"';
            if (field.max_date) inputHtml += ' max="' + field.max_date + '"';
            if (field.non_editable) inputHtml += ' readonly';
            inputHtml += '>';
            break;
            
        case 'time':
            inputHtml = '<input type="time" class="form-control" id="' + fieldId + '" name="' + fieldName + '" value="' + fieldValue + '"';
            if (field.required) inputHtml += ' required';
            if (field.non_editable) inputHtml += ' readonly';
            inputHtml += '>';
            break;
            
        case 'email':
            inputHtml = '<input type="email" class="form-control" id="' + fieldId + '" name="' + fieldName + '" value="' + fieldValue + '" placeholder="' + (field.placeholder || 'Enter email address') + '"';
            if (field.required) inputHtml += ' required';
            if (field.non_editable) inputHtml += ' readonly';
            inputHtml += '>';
            break;
            
        case 'url':
            inputHtml = '<input type="url" class="form-control" id="' + fieldId + '" name="' + fieldName + '" value="' + fieldValue + '" placeholder="' + (field.placeholder || 'Enter URL') + '"';
            if (field.required) inputHtml += ' required';
            if (field.non_editable) inputHtml += ' readonly';
            inputHtml += '>';
            break;
            
        case 'phone':
            inputHtml = '<input type="tel" class="form-control" id="' + fieldId + '" name="' + fieldName + '" value="' + fieldValue + '" placeholder="' + (field.placeholder || 'Enter phone number') + '"';
            if (field.required) inputHtml += ' required';
            if (field.non_editable) inputHtml += ' readonly';
            inputHtml += '>';
            break;
            
        default:
            inputHtml = '<input type="text" class="form-control" id="' + fieldId + '" name="' + fieldName + '" value="' + fieldValue + '" placeholder="' + (field.placeholder || 'Enter ' + field.label) + '"';
            if (field.required) inputHtml += ' required';
            if (field.non_editable) inputHtml += ' readonly';
            inputHtml += '>';
    }
    
    return inputHtml;
}

// Create custom field input
function createCustomFieldInput(field) {
    var inputHtml = '';
    var fieldId = 'field_' + field.field_name;
    var fieldName = 'fields[' + field.field_name + ']';
    var fieldValue = '';
    
    switch (field.field_type) {
        case 'text':
            inputHtml = '<input type="text" class="form-control form-control-sm" id="' + fieldId + '" name="' + fieldName + '" value="' + fieldValue + '" placeholder="' + (window.translations?.enterField || 'Enter') + ' ' + field.label + '"';
            if (field.non_editable) inputHtml += ' readonly';
            inputHtml += '>';
            break;
        case 'textarea':
            inputHtml = '<textarea class="form-control form-control-sm" id="' + fieldId + '" name="' + fieldName + '" rows="4" placeholder="' + (window.translations?.enterField || 'Enter') + ' ' + field.label + '"';
            if (field.non_editable) inputHtml += ' readonly';
            inputHtml += '>' + escapeHtml(fieldValue) + '</textarea>';
            break;
        case 'integer':
            inputHtml = '<input type="number" class="form-control form-control-sm" id="' + fieldId + '" name="' + fieldName + '" value="' + fieldValue + '" placeholder="' + (window.translations?.enterField || 'Enter') + ' ' + field.label + '"';
            if (field.non_editable) inputHtml += ' readonly';
            inputHtml += '>';
            break;
        case 'float':
            inputHtml = '<input type="number" step="0.01" class="form-control form-control-sm" id="' + fieldId + '" name="' + fieldName + '" value="' + fieldValue + '" placeholder="' + (window.translations?.enterField || 'Enter') + ' ' + field.label + '"';
            if (field.non_editable) inputHtml += ' readonly';
            inputHtml += '>';
            break;
        case 'boolean':
            inputHtml = '<select class="form-select form-select-sm" id="' + fieldId + '" name="' + fieldName + '"';
            if (field.non_editable) inputHtml += ' disabled';
            inputHtml += '>';
            inputHtml += '<option value="">' + (window.translations?.selectOption || 'Select option') + '</option>';
            inputHtml += '<option value="true">' + (window.translations?.yes || 'Yes') + '</option>';
            inputHtml += '<option value="false">' + (window.translations?.no || 'No') + '</option>';
            inputHtml += '</select>';
            if (field.non_editable) {
                inputHtml += '<input type="hidden" name="' + fieldName + '" value="' + fieldValue + '">';
            }
            break;
        case 'choice':
            var customOptions = normalizeFieldChoices(field);
            if (customOptions.length > 0) {
                inputHtml = '<select class="form-select form-select-sm" id="' + fieldId + '" name="' + fieldName + '"';
                if (field.non_editable) inputHtml += ' disabled';
                inputHtml += '>';
                inputHtml += '<option value="">' + escapeHtml(window.translations?.selectOption || 'Select option') + '</option>';
                customOptions.forEach(function(option) {
                    var optionValue = option.value !== undefined ? option.value : '';
                    var optionLabel = option.label !== undefined ? option.label : optionValue;
                    inputHtml += '<option value="' + escapeHtml(optionValue) + '">' + escapeHtml(optionLabel) + '</option>';
                });
                inputHtml += '</select>';
                if (field.non_editable) {
                    inputHtml += '<input type="hidden" name="' + fieldName + '" value="' + fieldValue + '">';
                }
            } else {
                inputHtml = '<input type="text" class="form-control form-control-sm" id="' + fieldId + '" name="' + fieldName + '" value="' + fieldValue + '" placeholder="' + (window.translations?.enterField || 'Enter') + ' ' + field.label + '"';
                if (field.non_editable) inputHtml += ' readonly';
                inputHtml += '>';
            }
            break;
        case 'date':
            // Only set value if it's a valid date format (YYYY-MM-DD)
            var dateValue = '';
            if (fieldValue && typeof fieldValue === 'string' && fieldValue.match(/^\d{4}-\d{2}-\d{2}$/)) {
                dateValue = fieldValue;
            } else if (fieldValue && typeof fieldValue === 'string' && fieldValue.length > 0) {
                // Try to parse date if it's in a different format
                try {
                    var date = new Date(fieldValue);
                    if (!isNaN(date.getTime())) {
                        dateValue = date.toISOString().split('T')[0];
                    }
                } catch (e) {
                    // Invalid date, leave empty
                    dateValue = '';
                }
            }
            inputHtml = '<input type="date" class="form-control form-control-sm" id="' + fieldId + '" name="' + fieldName + '" value="' + dateValue + '"';
            if (field.non_editable) inputHtml += ' readonly';
            inputHtml += '>';
            break;
        case 'multiple_choice':
            var customOptions = normalizeFieldChoices(field);
            if (customOptions.length > 0) {
                // Create checkbox group
                inputHtml = '<div class="multiple-choice-group" id="' + fieldId + '_group">';
                customOptions.forEach(function(option) {
                    var optionValue = option.value !== undefined ? String(option.value) : '';
                    var optionLabel = option.label !== undefined ? option.label : optionValue;
                    var checkboxId = fieldId + '_' + optionValue.replace(/[^a-zA-Z0-9]/g, '_');
                    inputHtml += '<div class="form-check">';
                    inputHtml += '<input class="form-check-input" type="checkbox" id="' + checkboxId + '" value="' + escapeHtml(optionValue) + '"';
                    if (field.non_editable) inputHtml += ' disabled';
                    inputHtml += '>';
                    inputHtml += '<label class="form-check-label" for="' + checkboxId + '">' + escapeHtml(optionLabel) + '</label>';
                    inputHtml += '</div>';
                });
                inputHtml += '</div>';
                
                // Hidden input to store JSON array of selected values
                inputHtml += '<input type="hidden" name="' + fieldName + '" id="' + fieldId + '_hidden" value=\'[]\'>';
                
                // JavaScript to update hidden input when checkboxes change
                if (!field.non_editable) {
                    inputHtml += '<script>';
                    inputHtml += '(function() {';
                    inputHtml += '  var group = document.getElementById("' + fieldId + '_group");';
                    inputHtml += '  var hidden = document.getElementById("' + fieldId + '_hidden");';
                    inputHtml += '  if (group && hidden) {';
                    inputHtml += '    group.addEventListener("change", function(e) {';
                    inputHtml += '      if (e.target.type === "checkbox") {';
                    inputHtml += '        var checkboxes = group.querySelectorAll("input[type=checkbox]");';
                    inputHtml += '        var selected = [];';
                    inputHtml += '        for (var i = 0; i < checkboxes.length; i++) {';
                    inputHtml += '          if (checkboxes[i].checked) {';
                    inputHtml += '            selected.push(checkboxes[i].value);';
                    inputHtml += '          }';
                    inputHtml += '        }';
                    inputHtml += '        hidden.value = JSON.stringify(selected);';
                    inputHtml += '      }';
                    inputHtml += '    });';
                    inputHtml += '  }';
                    inputHtml += '})();';
                    inputHtml += '</script>';
                } else {
                    // For non-editable fields, add hidden input with empty array
                    inputHtml += '<input type="hidden" name="' + fieldName + '" value=\'[]\'>';
                }
            } else {
                // Fallback to text input if no options
                inputHtml = '<input type="text" class="form-control form-control-sm" id="' + fieldId + '" name="' + fieldName + '" value="' + fieldValue + '" placeholder="' + (window.translations?.enterField || 'Enter') + ' ' + field.label + '"';
                if (field.non_editable) inputHtml += ' readonly';
                inputHtml += '>';
            }
            break;
        default:
            inputHtml = '<input type="text" class="form-control form-control-sm" id="' + fieldId + '" name="' + fieldName + '" value="' + fieldValue + '" placeholder="' + (window.translations?.enterField || 'Enter') + ' ' + field.label + '"';
            if (field.non_editable) inputHtml += ' readonly';
            inputHtml += '>';
    }
    
    return inputHtml;
}

// Create editable field input for existing entries
function createEditableFieldInput(field, value, entryIndex) {
    var inputHtml = '';
    var fieldId = 'field_' + field.field_name + '_' + entryIndex;
    var fieldName = 'fields[' + field.field_name + '][' + entryIndex + ']';
    var fieldValue = value || '';
    
    switch (field.field_type) {
        case 'text':
            inputHtml = '<input type="text" class="form-control form-control-sm" id="' + fieldId + '" name="' + fieldName + '" value="' + fieldValue + '" placeholder="' + (window.translations?.enterField || 'Enter') + ' ' + field.label + '"';
            if (field.non_editable) inputHtml += ' readonly';
            inputHtml += '>';
            break;
        case 'textarea':
            inputHtml = '<textarea class="form-control form-control-sm" id="' + fieldId + '" name="' + fieldName + '" rows="4" placeholder="' + (window.translations?.enterField || 'Enter') + ' ' + field.label + '"';
            if (field.non_editable) inputHtml += ' readonly';
            inputHtml += '>' + escapeHtml(fieldValue) + '</textarea>';
            break;
        case 'integer':
            inputHtml = '<input type="number" class="form-control form-control-sm" id="' + fieldId + '" name="' + fieldName + '" value="' + fieldValue + '" placeholder="' + (window.translations?.enterField || 'Enter') + ' ' + field.label + '"';
            if (field.non_editable) inputHtml += ' readonly';
            inputHtml += '>';
            break;
        case 'float':
            inputHtml = '<input type="number" step="0.01" class="form-control form-control-sm" id="' + fieldId + '" name="' + fieldName + '" value="' + fieldValue + '" placeholder="' + (window.translations?.enterField || 'Enter') + ' ' + field.label + '"';
            if (field.non_editable) inputHtml += ' readonly';
            inputHtml += '>';
            break;
        case 'boolean':
            inputHtml = '<select class="form-select form-select-sm" id="' + fieldId + '" name="' + fieldName + '"';
            if (field.non_editable) inputHtml += ' disabled';
            inputHtml += '>';
            inputHtml += '<option value="">' + (window.translations?.selectOption || 'Select option') + '</option>';
            inputHtml += '<option value="true"' + (fieldValue === 'true' || fieldValue === true ? ' selected' : '') + '>' + (window.translations?.yes || 'Yes') + '</option>';
            inputHtml += '<option value="false"' + (fieldValue === 'false' || fieldValue === false ? ' selected' : '') + '>' + (window.translations?.no || 'No') + '</option>';
            inputHtml += '</select>';
            if (field.non_editable) {
                inputHtml += '<input type="hidden" name="' + fieldName + '" value="' + fieldValue + '">';
            }
            break;
        case 'choice':
            var editableOptions = normalizeFieldChoices(field);
            var editableValue = fieldValue !== undefined && fieldValue !== null ? String(fieldValue) : '';
            if (editableOptions.length > 0) {
                inputHtml = '<select class="form-select form-select-sm" id="' + fieldId + '" name="' + fieldName + '"';
                if (field.non_editable) inputHtml += ' disabled';
                inputHtml += '>';
                inputHtml += '<option value="">' + escapeHtml(window.translations?.selectOption || 'Select option') + '</option>';
                editableOptions.forEach(function(option) {
                    var optionValue = option.value !== undefined ? option.value : '';
                    var optionLabel = option.label !== undefined ? option.label : optionValue;
                    var selected = editableValue !== '' && editableValue === String(optionValue) ? ' selected' : '';
                    inputHtml += '<option value="' + escapeHtml(optionValue) + '"' + selected + '>' + escapeHtml(optionLabel) + '</option>';
                });
                inputHtml += '</select>';
                if (field.non_editable) {
                    inputHtml += '<input type="hidden" name="' + fieldName + '" value="' + fieldValue + '">';
                }
            } else {
                inputHtml = '<input type="text" class="form-control form-control-sm" id="' + fieldId + '" name="' + fieldName + '" value="' + fieldValue + '" placeholder="' + (window.translations?.enterField || 'Enter') + ' ' + field.label + '"';
                if (field.non_editable) inputHtml += ' readonly';
                inputHtml += '>';
            }
            break;
        case 'multiple_choice':
            var editableOptions = normalizeFieldChoices(field);
            var editableValue = fieldValue !== undefined && fieldValue !== null ? String(fieldValue) : '';
            
            // Parse JSON array if value is stored as JSON
            var selectedValues = [];
            try {
                if (editableValue && editableValue.trim().startsWith('[')) {
                    selectedValues = JSON.parse(editableValue);
                } else if (editableValue && editableValue.includes(',')) {
                    // Fallback: comma-separated
                    selectedValues = editableValue.split(',').map(function(v) { return v.trim(); });
                } else if (editableValue && editableValue.trim()) {
                    selectedValues = [editableValue.trim()];
                }
            } catch (e) {
                selectedValues = editableValue ? [editableValue] : [];
            }
            
            if (editableOptions.length > 0) {
                // Create checkbox group
                inputHtml = '<div class="multiple-choice-group" id="' + fieldId + '_group">';
                editableOptions.forEach(function(option) {
                    var optionValue = option.value !== undefined ? String(option.value) : '';
                    var optionLabel = option.label !== undefined ? option.label : optionValue;
                    var checked = selectedValues.indexOf(optionValue) !== -1 ? ' checked' : '';
                    var checkboxId = fieldId + '_' + optionValue.replace(/[^a-zA-Z0-9]/g, '_');
                    inputHtml += '<div class="form-check">';
                    inputHtml += '<input class="form-check-input" type="checkbox" id="' + checkboxId + '" value="' + escapeHtml(optionValue) + '"' + checked;
                    if (field.non_editable) inputHtml += ' disabled';
                    inputHtml += '>';
                    inputHtml += '<label class="form-check-label" for="' + checkboxId + '">' + escapeHtml(optionLabel) + '</label>';
                    inputHtml += '</div>';
                });
                inputHtml += '</div>';
                
                // Hidden input to store JSON array of selected values
                inputHtml += '<input type="hidden" name="' + fieldName + '" id="' + fieldId + '_hidden" value=\'' + JSON.stringify(selectedValues) + '\'>';
                
                // JavaScript to update hidden input when checkboxes change
                if (!field.non_editable) {
                    inputHtml += '<script>';
                    inputHtml += '(function() {';
                    inputHtml += '  var group = document.getElementById("' + fieldId + '_group");';
                    inputHtml += '  var hidden = document.getElementById("' + fieldId + '_hidden");';
                    inputHtml += '  if (group && hidden) {';
                    inputHtml += '    group.addEventListener("change", function(e) {';
                    inputHtml += '      if (e.target.type === "checkbox") {';
                    inputHtml += '        var checkboxes = group.querySelectorAll("input[type=checkbox]");';
                    inputHtml += '        var selected = [];';
                    inputHtml += '        for (var i = 0; i < checkboxes.length; i++) {';
                    inputHtml += '          if (checkboxes[i].checked) {';
                    inputHtml += '            selected.push(checkboxes[i].value);';
                    inputHtml += '          }';
                    inputHtml += '        }';
                    inputHtml += '        hidden.value = JSON.stringify(selected);';
                    inputHtml += '      }';
                    inputHtml += '    });';
                    inputHtml += '  }';
                    inputHtml += '})();';
                    inputHtml += '</script>';
                } else {
                    // For non-editable fields, add hidden input with current value
                    inputHtml += '<input type="hidden" name="' + fieldName + '" value=\'' + JSON.stringify(selectedValues) + '\'>';
                }
            } else {
                // Fallback to text input if no options
                inputHtml = '<input type="text" class="form-control form-control-sm" id="' + fieldId + '" name="' + fieldName + '" value="' + escapeHtml(editableValue) + '" placeholder="' + (window.translations?.enterField || 'Enter') + ' ' + field.label + '"';
                if (field.non_editable) inputHtml += ' readonly';
                inputHtml += '>';
            }
            break;
        case 'date':
            // Only set value if it's a valid date format (YYYY-MM-DD)
            var dateValue = '';
            if (fieldValue && typeof fieldValue === 'string' && fieldValue.match(/^\d{4}-\d{2}-\d{2}$/)) {
                dateValue = fieldValue;
            } else if (fieldValue && typeof fieldValue === 'string' && fieldValue.length > 0) {
                // Try to parse date if it's in a different format
                try {
                    var date = new Date(fieldValue);
                    if (!isNaN(date.getTime())) {
                        dateValue = date.toISOString().split('T')[0];
                    }
                } catch (e) {
                    // Invalid date, leave empty
                    dateValue = '';
                }
            }
            inputHtml = '<input type="date" class="form-control form-control-sm" id="' + fieldId + '" name="' + fieldName + '" value="' + dateValue + '"';
            if (field.non_editable) inputHtml += ' readonly';
            inputHtml += '>';
            break;
        default:
            inputHtml = '<input type="text" class="form-control form-control-sm" id="' + fieldId + '" name="' + fieldName + '" value="' + fieldValue + '" placeholder="' + (window.translations?.enterField || 'Enter') + ' ' + field.label + '"';
            if (field.non_editable) inputHtml += ' readonly';
            inputHtml += '>';
    }
    
    return inputHtml;
}

// Create entry
function createEntry() {
    console.log('[createEntry] Function called');
    console.log('[createEntry] currentPoint:', currentPoint);
    
    if (!currentPoint) {
        console.error('[createEntry] No currentPoint selected');
        alert('Please select a geometry point first.');
        return;
    }
    
    console.log('[createEntry] allowMultipleEntries:', window.allowMultipleEntries);
    console.log('[createEntry] currentPoint.entries:', currentPoint.entries);
    
    if (!window.allowMultipleEntries && currentPoint.entries && currentPoint.entries.length > 0) {
        console.warn('[createEntry] Multiple entries not allowed and entries already exist');
        alert('Multiple entries are not allowed for this dataset. Please edit the existing entry instead.');
        return;
    }
    
    var entryNameInput = document.getElementById('new-entry-name');
    console.log('[createEntry] entryNameInput element:', entryNameInput);
    
    if (!entryNameInput) {
        console.error('[createEntry] new-entry-name input not found');
        alert('Entry name input field not found.');
        return;
    }
    
    var entryName = entryNameInput.value;
    console.log('[createEntry] entryName value:', entryName);
    
    if (!entryName) {
        console.warn('[createEntry] Entry name is empty');
        alert('Please enter an entry name.');
        return;
    }
    
    var csrfToken = document.querySelector('[name=csrfmiddlewaretoken]');
    console.log('[createEntry] CSRF token element:', csrfToken);
    
    if (!csrfToken) {
        console.error('[createEntry] CSRF token not found');
        alert('CSRF token not found. Please refresh the page.');
        return;
    }
    
    var formData = new FormData();
    formData.append('name', entryName);
    formData.append('geometry_id', currentPoint.id);
    formData.append('csrfmiddlewaretoken', csrfToken.value);
    
    console.log('[createEntry] FormData created with name:', entryName, 'geometry_id:', currentPoint.id);
    
    // Add field values
    console.log('[createEntry] window.allFields:', window.allFields);
    if (window.allFields && window.allFields.length > 0) {
        var fieldsAdded = 0;
        window.allFields.forEach(function(field) {
            if (field.enabled && field.field_type !== 'headline') {
                var fieldElement = document.getElementById('field_' + field.field_name);
                // For multiple_choice, check for hidden input
                if (field.field_type === 'multiple_choice') {
                    fieldElement = document.getElementById('field_' + field.field_name + '_hidden');
                }
                if (fieldElement) {
                    // Skip empty date fields to avoid browser validation errors
                    if (field.field_type === 'date' && !fieldElement.value) {
                        console.log('[createEntry] Skipping empty date field:', field.field_name);
                        return; // Skip empty date fields
                    }
                    // Skip empty multiple_choice fields (empty JSON array)
                    if (field.field_type === 'multiple_choice' && (!fieldElement.value || fieldElement.value === '[]')) {
                        console.log('[createEntry] Skipping empty multiple_choice field:', field.field_name);
                        return; // Skip empty multiple_choice fields
                    }
                    // Send field name directly (not wrapped in fields[])
                    formData.append(field.field_name, fieldElement.value);
                    fieldsAdded++;
                    console.log('[createEntry] Added field:', field.field_name, '=', fieldElement.value);
                } else {
                    console.warn('[createEntry] Field element not found:', 'field_' + field.field_name);
                }
            }
        });
        console.log('[createEntry] Total fields added to FormData:', fieldsAdded);
    } else {
        console.log('[createEntry] No fields to add (window.allFields is empty or undefined)');
    }
    
    var url = window.location.origin + '/geometries/' + currentPoint.id + '/entries/create/';
    console.log('[createEntry] Fetching URL:', url);
    console.log('[createEntry] FormData entries:', Array.from(formData.entries()));
    
    fetch(url, {
        method: 'POST',
        body: formData,
        credentials: 'same-origin',
        headers: { 'X-Requested-With': 'XMLHttpRequest' }
    })
    .then(response => {
        console.log('[createEntry] Response received, status:', response.status, 'statusText:', response.statusText);
        console.log('[createEntry] Response headers:', response.headers);
        return response.json();
    })
    .then(data => {
        console.log('[createEntry] Response data:', data);
        if (data.success) {
            // Clear form
            document.getElementById('new-entry-name').value = '';
            if (window.allFields && window.allFields.length > 0) {
                window.allFields.forEach(function(field) {
                    if (field.enabled) {
                        var fieldElement = document.getElementById('field_' + field.field_name);
                        if (fieldElement) {
                            if (fieldElement.tagName === 'SELECT') {
                                fieldElement.selectedIndex = 0;
                            } else {
                                fieldElement.value = '';
                            }
                        }
                    }
                });
            }
            
            // Reset file upload button (if it exists)
            var photoUploadInput = document.querySelector('#photo-upload-new');
            if (photoUploadInput && photoUploadInput.nextElementSibling) {
                var button = photoUploadInput.nextElementSibling;
                button.textContent = 'No files selected';
                button.className = 'btn btn-outline-secondary';
            }
            
            // Reload map data to show new entry, but preserve current view
            console.log('[createEntry] Success! Reloading map data...');
            loadMapData(true);
            
            // Reload geometry details to show the new entry in the dropdown
            if (currentPoint && currentPoint.id) {
                console.log('[createEntry] Reloading geometry details for point:', currentPoint.id);
                // Set the selected entry to the newly created entry before reloading
                if (data.entry_id) {
                    selectedEntryId = data.entry_id;
                    console.log('[createEntry] Set selectedEntryId to:', selectedEntryId);
                }
                loadGeometryDetails(currentPoint.id)
                    .then(function(detailedPoint) {
                        console.log('[createEntry] Geometry details loaded, showing details with new entry selected');
                        showGeometryDetails(detailedPoint);
                        // Ensure dropdown is set to the new entry after table is generated
                        setTimeout(function() {
                            var selector = document.getElementById('entrySelector');
                            if (selector && data.entry_id) {
                                selector.value = data.entry_id;
                                console.log('[createEntry] Updated dropdown selector to entry_id:', data.entry_id);
                            }
                        }, 100);
                    })
                    .catch(function(error) {
                        console.error('[createEntry] Error reloading geometry details:', error);
                        // Fallback: just reload the current point data
                        if (currentPoint) {
                            showGeometryDetails(currentPoint);
                        }
                    });
            }
        } else {
            console.error('[createEntry] Server returned error:', data.error || 'Unknown error');
            console.error('[createEntry] Full response data:', data);
            alert('Error creating entry: ' + (data.error || 'Unknown error'));
        }
    })
    .catch(error => {
        console.error('[createEntry] Fetch error:', error);
        console.error('[createEntry] Error name:', error.name);
        console.error('[createEntry] Error message:', error.message);
        console.error('[createEntry] Error stack:', error.stack);
        alert('Error creating entry: ' + error.message);
    });
}

// Copy entry to new entry
function copyToNewEntry(entryId, entryIndex, buttonElement) {
    if (!currentPoint) {
        alert('Please select a geometry point first.');
        return;
    }
    
    if (!window.allowMultipleEntries && currentPoint.entries && currentPoint.entries.length > 0) {
        alert('Multiple entries are not allowed for this dataset.');
        return;
    }
    
    // Get the entry name (use current entry name with "Copy" suffix)
    var currentEntryName = '';
    if (currentPoint.entries && currentPoint.entries[entryIndex]) {
        currentEntryName = currentPoint.entries[entryIndex].name || currentPoint.id_kurz || 'Entry';
    } else {
        currentEntryName = currentPoint.id_kurz || 'Entry';
    }
    var newEntryName = currentEntryName + ' (Copy)';
    
    var formData = new FormData();
    formData.append('name', newEntryName);
    formData.append('geometry_id', currentPoint.id);
    formData.append('csrfmiddlewaretoken', document.querySelector('[name=csrfmiddlewaretoken]').value);
    
    // Copy field values from the current entry's form (excluding images)
    if (window.allFields && window.allFields.length > 0) {
        window.allFields.forEach(function(field) {
            if (field.enabled) {
                // Get field value from the current entry's form
                var fieldElement = document.getElementById('field_' + field.field_name + '_' + entryIndex);
                // For multiple_choice, check for hidden input
                if (field.field_type === 'multiple_choice') {
                    fieldElement = document.getElementById('field_' + field.field_name + '_' + entryIndex + '_hidden');
                }
                if (fieldElement) {
                    var fieldValue = fieldElement.value;
                    // Skip empty date fields to avoid browser validation errors
                    if (field.field_type === 'date' && !fieldValue) {
                        return; // Skip empty date fields
                    }
                    // Skip empty multiple_choice fields (empty JSON array)
                    if (field.field_type === 'multiple_choice' && (!fieldValue || fieldValue === '[]')) {
                        return; // Skip empty multiple_choice fields
                    }
                    // Send field name directly (not wrapped in fields[])
                    formData.append(field.field_name, fieldValue);
                }
            }
        });
    }
    
    // Show loading state
    var copyBtn = buttonElement || document.getElementById('copyEntryBtn');
    var originalText = copyBtn.innerHTML;
    copyBtn.innerHTML = '<i class="bi bi-hourglass-split"></i> Copying...';
    copyBtn.disabled = true;
    
    fetch(window.location.origin + '/geometries/' + currentPoint.id + '/entries/create/', {
        method: 'POST',
        body: formData,
        credentials: 'same-origin',
        headers: { 'X-Requested-With': 'XMLHttpRequest' }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            // Reload map data to show new entry, but preserve current view
            loadMapData(true);
            
            // After reloading, select the new entry
            if (data.entry_id) {
                // Wait a bit for the data to load, then select the new entry
                setTimeout(function() {
                    selectedEntryId = data.entry_id;
                    // Reload geometry details to get the new entry
                    loadGeometryDetails(currentPoint.id)
                        .then(function(detailedPoint) {
                            showGeometryDetails(detailedPoint);
                            // Select the new entry in the dropdown
                            var selector = document.getElementById('entrySelector');
                            if (selector) {
                                selector.value = data.entry_id;
                            }
                        })
                        .catch(function() {
                            // Fallback: just reload the current point
                            if (currentPoint) {
                                generateEntriesTable(currentPoint);
                            }
                        });
                }, 500);
            }
        } else {
            alert('Error copying entry: ' + (data.error || 'Unknown error'));
            copyBtn.innerHTML = originalText;
            copyBtn.disabled = false;
        }
    })
    .catch(error => {
        console.error('Error copying entry:', error);
        alert('Error copying entry: ' + error.message);
        copyBtn.innerHTML = originalText;
        copyBtn.disabled = false;
    });
}

// Save entries
function saveEntries() {
    if (!currentPoint) {
        alert('Please select a geometry point first.');
        return;
    }
    
    if (!currentPoint.entries || currentPoint.entries.length === 0) {
        alert('No entries to save.');
        return;
    }
    
    var formData = new FormData();
    formData.append('geometry_id', currentPoint.id);
    formData.append('csrfmiddlewaretoken', document.querySelector('[name=csrfmiddlewaretoken]').value);
    
    // Add field values for each entry
    if (window.allFields && window.allFields.length > 0) {
        for (var i = 0; i < currentPoint.entries.length; i++) {
            var entry = currentPoint.entries[i];
            formData.append('entries[' + i + '][id]', entry.id);
            
            window.allFields.forEach(function(field) {
                if (field.enabled && field.field_type !== 'headline') {
                    var fieldElement = document.getElementById('field_' + field.field_name + '_' + i);
                    // For multiple_choice, check for hidden input
                    if (field.field_type === 'multiple_choice') {
                        fieldElement = document.getElementById('field_' + field.field_name + '_' + i + '_hidden');
                    }
                    if (fieldElement) {
                        formData.append('entries[' + i + '][fields][' + field.field_name + ']', fieldElement.value);
                    }
                }
            });
        }
    }
    
    // Show loading state
    var saveBtn = document.querySelector('button[onclick="saveEntries()"]');
    var originalText = saveBtn.innerHTML;
    saveBtn.innerHTML = '<i class="bi bi-hourglass-split"></i> Saving...';
    saveBtn.disabled = true;
    
    fetch(window.location.origin + '/entries/save/', {
        method: 'POST',
        body: formData,
        credentials: 'same-origin',
        headers: { 'X-Requested-With': 'XMLHttpRequest' }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            // Reload map data to show updated entries, but preserve current view
            loadMapData(true);
        } else {
            alert('Error saving entries: ' + (data.error || 'Unknown error'));
        }
    })
    .catch(error => {
        console.error('Error saving entries:', error);
        alert('Error saving entries: ' + error.message);
    })
    .finally(() => {
        // Reset button state
        saveBtn.innerHTML = originalText;
        saveBtn.disabled = false;
    });
}

// Setup event listeners
function setupEventListeners() {
    document.addEventListener('change', function(e) {
        if (e.target.type === 'file') {
            var files = e.target.files;
            var button = e.target.nextElementSibling;
            if (files.length > 0) {
                button.textContent = files.length + ' file(s) selected';
                button.className = 'btn btn-success';
            } else {
                button.textContent = 'No files selected';
                button.className = 'btn btn-outline-secondary';
            }
        }
        // Multiple-choice: sync checkbox state to hidden input (scripts in innerHTML don't run)
        if (e.target && e.target.type === 'checkbox') {
            var group = e.target.closest ? e.target.closest('.multiple-choice-group') : null;
            if (group) {
                var groupId = group.id;
                if (groupId && groupId.indexOf('_group') !== -1) {
                    var hiddenId = groupId.replace(/_group$/, '_hidden');
                    var hidden = document.getElementById(hiddenId);
                    if (hidden) {
                        var checkboxes = group.querySelectorAll('input[type=checkbox]');
                        var selected = [];
                        for (var i = 0; i < checkboxes.length; i++) {
                            if (checkboxes[i].checked) selected.push(checkboxes[i].value);
                        }
                        hidden.value = JSON.stringify(selected);
                    }
                }
            }
        }
    });

    setTimeout(function() {
        var addPointBtn = document.getElementById('addPointBtn');
        if (addPointBtn) {
            addPointBtn.replaceWith(addPointBtn.cloneNode(true));
            addPointBtn = document.getElementById('addPointBtn');
            addPointBtn.addEventListener('click', function(e) {
                e.preventDefault();
                toggleAddPointMode();
            });
        }

        var focusAllBtn = document.getElementById('focusAllBtn');
        if (focusAllBtn) focusAllBtn.addEventListener('click', focusOnAllPoints);
        var gotoLocationBtn = document.getElementById('gotoLocationBtn');
        if (gotoLocationBtn) gotoLocationBtn.addEventListener('click', toggleGotoLocationMode);
        var myLocationBtn = document.getElementById('myLocationBtn');
        if (myLocationBtn) myLocationBtn.addEventListener('click', zoomToMyLocation);
        var zoomInBtn = document.getElementById('zoomInBtn');
        if (zoomInBtn) zoomInBtn.addEventListener('click', function() { map.zoomIn(); });
        var zoomOutBtn = document.getElementById('zoomOutBtn');
        if (zoomOutBtn) zoomOutBtn.addEventListener('click', function() { map.zoomOut(); });
    }, 100);
}

// Focus on all points
function focusOnAllPoints() {
    if (!map || markers.length === 0) return;
    var group = new L.featureGroup(markers);
    map.fitBounds(group.getBounds().pad(0.1));
}

// Toggle goto location mode
function toggleGotoLocationMode() {
    // Disable add point mode if active
    if (addPointMode) {
        toggleAddPointMode();
    }
    
    gotoLocationMode = !gotoLocationMode;
    var button = document.getElementById('gotoLocationBtn');
    if (!button) return;

    if (gotoLocationMode) {
        // Enable goto location mode
        button.classList.remove('btn-light');
        button.classList.add('btn-success');
        button.innerHTML = '<i class="bi bi-check-circle"></i> Click on Map';
        button.title = 'Click on the map to zoom to that location, or click this button to cancel';
        
        // Set up click handler
        gotoLocationClickHandler = function(e) {
            // Get maximum zoom level for the map
            var maxZoom = map.getMaxZoom();
            // Zoom to the clicked location at maximum zoom
            map.setView(e.latlng, maxZoom);
            // Exit mode after clicking
            toggleGotoLocationMode();
        };
        
        // Change cursor to indicate mode
        if (map && map.getContainer()) map.getContainer().style.cursor = 'crosshair';
    } else {
        // Disable goto location mode
        button.classList.remove('btn-success');
        button.classList.add('btn-light');
        button.innerHTML = '<i class="bi bi-crosshair"></i> Goto location';
        button.title = 'Goto Location';
        
        // Remove click handler
        gotoLocationClickHandler = null;
        
        // Reset cursor
        if (map && map.getContainer()) map.getContainer().style.cursor = '';
    }
}

// Zoom to my location
function zoomToMyLocation() {
    if (!navigator.geolocation) {
        alert(window.translations?.geolocationNotSupported || 'Geolocation is not supported by this browser.');
        return;
    }
    
    navigator.geolocation.getCurrentPosition(
        function(position) {
            var lat = position.coords.latitude;
            var lng = position.coords.longitude;
            
            map.setView([lat, lng], 15);
            
            // Add a marker for current location
            L.marker([lat, lng], {
                icon: L.divIcon({
                    className: 'current-location-marker',
                    html: '<i class="bi bi-geo-fill" style="color: #FF6B6B; font-size: 20px;"></i>',
                    iconSize: [20, 20],
                    iconAnchor: [10, 10]
                })
            }).addTo(map);
        },
        function(error) {
            var errorMessage = window.translations?.geolocationError || 'Error getting your location: ';
            switch(error.code) {
                case error.PERMISSION_DENIED:
                    errorMessage += 'Permission denied';
                    break;
                case error.POSITION_UNAVAILABLE:
                    errorMessage += 'Position unavailable';
                    break;
                case error.TIMEOUT:
                    errorMessage += 'Request timeout';
                    break;
                default:
                    errorMessage += 'Unknown error';
                    break;
            }
            alert(errorMessage);
        }
    );
}

// Clear selection
function clearSelection() {
    currentPoint = null;
    var detailsDiv = document.getElementById('geometryDetails');
    if (detailsDiv) {
        detailsDiv.classList.remove('active');
    }
    
    // Reset all markers to default blue style
    markers.forEach(marker => {
        marker.setStyle({ fillColor: '#0047BB', color: '#001A70' });
    });
    
    // Clear geometry info (only if elements exist)
    var geometryId = document.getElementById('geometryId');
    if (geometryId) geometryId.textContent = '-';
    var geometryAddress = document.getElementById('geometryAddress');
    if (geometryAddress) geometryAddress.textContent = '-';
    var entriesCount = document.getElementById('entriesCount');
    if (entriesCount) entriesCount.textContent = '-';
    
    // Clear entries list
    var entriesList = document.getElementById('entriesList');
    if (entriesList) {
        entriesList.innerHTML = '';
    }
    
    // Adjust column layout
    if (typeof adjustColumnLayout === 'function') {
        adjustColumnLayout();
    }
}

// Get dataset ID from URL
function getDatasetId() {
    var path = window.location.pathname;
    var matches = path.match(/\/datasets\/(\d+)\//);
    return matches ? matches[1] : null;
}

// Adjust column layout based on content
function adjustColumnLayout() {
    var mapColumn = document.getElementById('mapColumn');
    // Keep map column full width; geometry details is an overlay on md+ and flows below on small screens
    if (mapColumn) {
        mapColumn.className = 'col-12';
    }
}

// Initialize responsive layout
function initializeResponsiveLayout() {
    // Initial layout adjustment
    adjustColumnLayout();
    
    // Listen for window resize
    window.addEventListener('resize', adjustColumnLayout);
}

// File upload functionality
function initializeFileUpload() {
    const fileUploadForm = document.getElementById('fileUploadForm');
    if (!fileUploadForm) return;
    
    fileUploadForm.addEventListener('submit', function(e) {
        e.preventDefault();
        uploadFiles();
    });
}

function uploadFiles() {
    if (!currentPoint) {
        alert('Please select a geometry point first.');
        return;
    }
    
    const fileInput = document.getElementById('fileInput');
    const files = fileInput.files;
    
    if (files.length === 0) {
        alert('Please select at least one image to upload.');
        return;
    }
    
    // Validate that all files are images
    for (let i = 0; i < files.length; i++) {
        if (!files[i].type.startsWith('image/')) {
            alert('Please select only image files.');
            return;
        }
    }
    
    const formData = new FormData();
    formData.append('geometry_id', currentPoint.id);
    
    // Add all selected files
    for (let i = 0; i < files.length; i++) {
        formData.append('files', files[i]);
    }
    
    // Show loading state
    const submitBtn = document.querySelector('#fileUploadForm button[type="submit"]');
    const originalText = submitBtn.innerHTML;
    submitBtn.innerHTML = '<i class="bi bi-hourglass-split"></i> Uploading...';
    submitBtn.disabled = true;
    
    // Get CSRF token
    const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]').value;
    
    fetch('/datasets/upload-files/', {
        method: 'POST',
        body: formData,
        headers: { 'X-CSRFToken': csrfToken }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            alert('Images uploaded successfully!');
            // Clear form
            fileInput.value = '';
            // Refresh files list
            loadUploadedFiles();
        } else {
            alert('Error uploading images: ' + (data.error || 'Unknown error'));
        }
    })
    .catch(error => {
        console.error('Upload error:', error);
        alert('Error uploading images. Please try again.');
    })
    .finally(() => {
        // Reset button state
        submitBtn.innerHTML = originalText;
        submitBtn.disabled = false;
    });
}

function loadUploadedFiles() {
    if (!currentPoint) return;
    
    const filesList = document.getElementById('filesList');
    if (!filesList) return;
    
    // Get CSRF token
    const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]').value;
    
    fetch('/datasets/geometry/' + currentPoint.id + '/files/', {
        headers: { 'X-CSRFToken': csrfToken }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            displayUploadedFiles(data.files);
        } else {
            filesList.innerHTML = '<p class="text-muted">Error loading files.</p>';
        }
    })
    .catch(error => {
        console.error('Error loading files:', error);
        filesList.innerHTML = '<p class="text-muted">Error loading files.</p>';
    });
}

function displayUploadedFiles(files) {
    const filesList = document.getElementById('filesList');
    if (!filesList) return;
    
    if (files.length === 0) {
        filesList.innerHTML = '<p class="text-muted">No files uploaded yet.</p>';
        return;
    }
    
    let html = '<div class="list-group">';
    files.forEach(file => {
        const fileIcon = getFileIcon(file.file_type);
        const fileSize = formatFileSize(file.file_size);
        const uploadDate = file.uploaded_at ? new Date(file.uploaded_at).toLocaleDateString() : 'Unknown';
        
        html += '<div class="list-group-item d-flex justify-content-between align-items-center">' +
            '<div>' +
                '<i class="' + fileIcon + ' me-2"></i>' +
                '<strong>' + (file.original_name || 'Unknown') + '</strong>' +
                '<small class="text-muted ms-2">(' + fileSize + ')</small>' +
                '<br><small class="text-muted">Uploaded: ' + uploadDate + '</small>' +
            '</div>' +
            '<div>' +
                '<a href="' + (file.download_url || '#') + '" class="btn btn-sm btn-outline-primary me-1" title="Download">' +
                    '<i class="bi bi-download"></i>' +
                '</a>' +
                '<button class="btn btn-sm btn-outline-danger" onclick="deleteFile(' + (file.id || 0) + ')" title="Delete">' +
                    '<i class="bi bi-trash"></i>' +
                '</button>' +
            '</div>' +
        '</div>';
    });
    html += '</div>';
    
    filesList.innerHTML = html;
}

function getFileIcon(fileType) {
    if (!fileType) return 'bi bi-file';
    if (fileType.startsWith('image/')) {
        return 'bi bi-image';
    } else if (fileType === 'application/pdf') {
        return 'bi bi-file-pdf';
    } else if (fileType.includes('word') || fileType.includes('document')) {
        return 'bi bi-file-word';
    } else if (fileType.includes('text')) {
        return 'bi bi-file-text';
    } else {
        return 'bi bi-file';
    }
}

function formatFileSize(bytes) {
    if (!bytes || bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

function deleteFile(fileId) {
    if (!confirm('Are you sure you want to delete this file?')) {
        return;
    }
    
    const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]').value;
    
    fetch('/datasets/files/' + fileId + '/delete/', {
        method: 'POST',
        headers: { 'X-CSRFToken': csrfToken, 'Content-Type': 'application/json' }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            alert('File deleted successfully!');
            loadUploadedFiles(); // Refresh the list
        } else {
            alert('Error deleting file: ' + (data.error || 'Unknown error'));
        }
    })
    .catch(error => {
        console.error('Delete error:', error);
        alert('Error deleting file. Please try again.');
    });
}

// Toggle add point mode
function toggleAddPointMode() {
    // Disable goto location mode if active
    if (gotoLocationMode) {
        toggleGotoLocationMode();
    }
    
    addPointMode = !addPointMode;
    var button = document.getElementById('addPointBtn');
    if (!button) return;

    if (addPointMode) {
        button.classList.remove('btn-primary');
        button.classList.add('btn-success');
        button.innerHTML = '<i class="bi bi-check-circle"></i> Click on Map';
        button.title = 'Click on the map to add a new point, or click this button to cancel';
        if (map && map.getContainer()) map.getContainer().style.cursor = 'crosshair';
    } else {
        button.classList.remove('btn-success');
        button.classList.add('btn-primary');
        button.innerHTML = '<i class="bi bi-plus-circle"></i> Add Point';
        button.title = 'Add New Point';
        if (map && map.getContainer()) map.getContainer().style.cursor = '';
        if (addPointMarker) { map.removeLayer(addPointMarker); addPointMarker = null; }
    }
}

// Add new point to the map
function addNewPoint(latlng) {
    if (addPointMarker) { map.removeLayer(addPointMarker); }
    addPointMarker = L.marker(latlng, {
        icon: L.divIcon({
            className: 'custom-marker add-point-marker',
            html: '<div style="background-color: #28a745; color: white; border-radius: 50%; width: 20px; height: 20px; display: flex; align-items: center; justify-content: center; font-size: 12px; font-weight: bold;">+</div>',
            iconSize: [20, 20], iconAnchor: [10, 10]
        })
    }).addTo(map);
    createNewGeometry(latlng);
}

// Create new geometry via AJAX
function createNewGeometry(latlng) {
    var datasetId = getDatasetId();
    var csrfToken = document.querySelector('[name=csrfmiddlewaretoken]').value;
    var newId = 'NEW_' + Date.now();
    var geometryData = { id_kurz: newId, address: 'New Point', geometry: { type: 'Point', coordinates: [latlng.lng, latlng.lat] } };
    
    fetch('/datasets/' + datasetId + '/geometries/create/', {
        method: 'POST',
        headers: { 'X-CSRFToken': csrfToken, 'Content-Type': 'application/json', 'X-Requested-With': 'XMLHttpRequest' },
        body: JSON.stringify(geometryData)
    })
    .then(async (response) => {
        const contentType = response.headers ? (response.headers.get && response.headers.get('content-type')) || '' : '';
        if (!response.ok) {
            const text = await (response.text ? response.text() : Promise.resolve(''));
            throw new Error('HTTP ' + response.status + (text ? (' - ' + text.substring(0, 200)) : ''));
        }
        if (contentType && contentType.indexOf('application/json') !== -1) return response.json();
        return { success: true, fallback: true };
    })
    .then(data => {
        if (addPointMarker) { try { map.removeLayer(addPointMarker); } catch(e) {} addPointMarker = null; }

        if (data && data.success && !data.fallback) {
            var newMarker = L.circleMarker([latlng.lat, latlng.lng], {
                radius: 8, fillColor: '#0047BB', color: '#001A70', weight: 2, opacity: 1, fillOpacity: 0.8
            }).addTo(map);
            newMarker.geometryData = { id: data.geometry_id, id_kurz: data.id_kurz, address: data.address, lat: latlng.lat, lng: latlng.lng, entries: [] };
            markers.push(newMarker);
            newMarker.on('click', function() { selectPoint(newMarker.geometryData); });
            toggleAddPointMode();
            selectPoint(newMarker.geometryData);
        } else {
            lastAddedLatLng = { lat: latlng.lat, lng: latlng.lng };
            toggleAddPointMode();
            loadMapData(true);
        }
    })
    .catch(() => {
        lastAddedLatLng = { lat: latlng.lat, lng: latlng.lng };
        toggleAddPointMode();
        loadMapData(true);
    });
}

// ==================== MAPPING AREAS FUNCTIONS ====================

function clearCollaboratorMappingAreaOutlines() {
    if (!map) return;
    collaboratorMappingAreaPolygons.forEach(function(polygon) {
        try {
            map.removeLayer(polygon);
        } catch (e) {
            /* ignore */
        }
    });
    collaboratorMappingAreaPolygons = [];
}

function drawCollaboratorMappingAreaOutlines(areas) {
    clearCollaboratorMappingAreaOutlines();
    if (!map || !areas || !areas.length) return;
    areas.forEach(function(area) {
        if (!area.geometry || !area.geometry.coordinates) return;
        var coordinates = area.geometry.coordinates[0];
        var latlngs = coordinates.map(function(coord) {
            return [coord[1], coord[0]];
        });
        var polygon = L.polygon(latlngs, {
            color: '#0f766e',
            weight: 2,
            dashArray: '8 6',
            opacity: 0.95,
            fillColor: '#14b8a6',
            fillOpacity: 0.12,
            interactive: false
        }).addTo(map);
        collaboratorMappingAreaPolygons.push(polygon);
    });
}

function loadCollaboratorMappingAreaOutlines() {
    if (typeof window.showCollaboratorMappingAreaOutlines === 'undefined' || !window.showCollaboratorMappingAreaOutlines) {
        clearCollaboratorMappingAreaOutlines();
        return;
    }
    if (!window.datasetId || !map) {
        return;
    }
    fetch('/datasets/' + window.datasetId + '/mapping-areas/outlines/', {
        method: 'GET',
        credentials: 'same-origin',
        headers: { 'X-Requested-With': 'XMLHttpRequest' }
    })
        .then(function(response) {
            return response.json();
        })
        .then(function(data) {
            if (data.success && Array.isArray(data.mapping_areas)) {
                drawCollaboratorMappingAreaOutlines(data.mapping_areas);
            } else {
                clearCollaboratorMappingAreaOutlines();
            }
        })
        .catch(function() {
            clearCollaboratorMappingAreaOutlines();
        });
}

// Toggle mapping areas panel
function toggleMappingAreas() {
    var panel = document.getElementById('mappingAreasPanel');
    if (!panel) return;
    if (!window.enableMappingAreas) {
        console.warn('Mapping areas are not enabled for this dataset.');
        return;
    }
    if (!window.isDatasetOwner) {
        console.warn('Mapping areas are only available to dataset owners.');
        return;
    }
    
    mappingAreasPanelVisible = !mappingAreasPanelVisible;
    
    if (mappingAreasPanelVisible) {
        panel.style.display = 'block';
        loadMappingAreas();
        loadUsersForAllocation();
    } else {
        panel.style.display = 'none';
        stopDrawingPolygon();
        stopEditingPolygon();
        clearSelectedPolygon();
    }
}

// Load mapping areas from API
function loadMappingAreas() {
    if (!window.enableMappingAreas || !window.isDatasetOwner) {
        drawMappingAreasOnMap([]);
        return;
    }
    if (!window.datasetId) {
        console.error('Dataset ID is not available for loading mapping areas.');
        var listContainer = document.getElementById('mappingAreasList');
        if (listContainer) {
            listContainer.innerHTML = '<div class="alert alert-warning">Dataset ID not available. Reload the page and try again.</div>';
        }
        return;
    }
    
    console.debug('Loading mapping areas for dataset', window.datasetId);
    fetch('/datasets/' + window.datasetId + '/mapping-areas/', {
        method: 'GET',
        credentials: 'same-origin',
        headers: { 'X-Requested-With': 'XMLHttpRequest' }
    })
    .then(async response => {
        const contentType = response.headers.get('content-type') || '';
        console.debug('Mapping areas response status:', response.status, 'content-type:', contentType);
        const text = await response.text();
        console.debug('Mapping areas raw response:', text);
        let payload = {};
        if (text) {
            if (contentType.includes('application/json')) {
                try {
                    payload = JSON.parse(text);
                } catch (parseError) {
                    console.error('Error parsing mapping area list response JSON:', parseError, text);
                    throw new Error('Invalid response format from server.');
                }
            } else {
                console.warn('Unexpected content type for mapping area list response:', contentType, text);
                throw new Error('Unexpected response from server.');
            }
        }

        if (!response.ok) {
            const errorMessage = (payload && payload.error) ? payload.error : `Request failed with status ${response.status}`;
            var listContainer = document.getElementById('mappingAreasList');
            if (listContainer) {
                listContainer.innerHTML = '<div class="alert alert-danger">' + escapeHtml(errorMessage) + '</div>';
            }
            throw new Error(errorMessage);
        }

        return payload;
    })
    .then(data => {
        if (data.success) {
            displayMappingAreas(data.mapping_areas);
            drawMappingAreasOnMap(data.mapping_areas);
            if (data.warning) {
                console.warn('Mapping areas warning:', data.warning);
                var listContainer = document.getElementById('mappingAreasList');
                if (listContainer) {
                    var warningAlert = document.createElement('div');
                    warningAlert.className = 'alert alert-warning mb-2';
                    warningAlert.innerHTML = '<i class="bi bi-exclamation-triangle me-2"></i>' + escapeHtml(data.warning);
                    listContainer.prepend(warningAlert);
                }
            }
        } else {
            console.error('Error loading mapping areas:', data.error);
            document.getElementById('mappingAreasList').innerHTML = '<div class="alert alert-danger">Error loading mapping areas</div>';
        }
    })
    .catch(error => {
        console.error('Error loading mapping areas:', error);
        var listContainer = document.getElementById('mappingAreasList');
        if (listContainer) {
            listContainer.innerHTML = '<div class="alert alert-danger">' + escapeHtml(error.message || 'Error loading mapping areas') + '</div>';
        }
    });
}

// Display mapping areas in the list
function displayMappingAreas(areas) {
    var listContainer = document.getElementById('mappingAreasList');
    if (!listContainer) return;
    
    if (areas.length === 0) {
        listContainer.innerHTML = '<div class="text-center text-muted py-3"><i class="bi bi-inbox"></i> No mapping areas yet. Draw a polygon to create one.</div>';
        return;
    }
    
    var html = '';
    areas.forEach(function(area) {
        html += '<div class="list-group-item mapping-area-item d-flex justify-content-between align-items-start" data-area-id="' + area.id + '" onclick="selectMappingArea(' + area.id + ')">';
        html += '<div class="flex-grow-1">';
        html += '<h6 class="mb-1 fw-semibold">' + escapeHtml(area.name) + '</h6>';
        html += '<div class="small text-muted">';
        html += '<div><i class="bi bi-geo-alt"></i> Points inside: <strong>' + area.point_count + '</strong></div>';
        if (area.allocated_user_names && area.allocated_user_names.length > 0) {
            html += '<div><i class="bi bi-people"></i> Users: ' + escapeHtml(area.allocated_user_names.join(', ')) + '</div>';
        }
        html += '</div>';
        html += '</div>';
        html += '<div class="ms-2 d-flex flex-column align-items-end gap-2">';
        if (selectedMappingArea === area.id) {
            html += '<span class="badge bg-primary"><i class="bi bi-check-circle"></i> Selected</span>';
        }
        html += '<div class="btn-group btn-group-sm" role="group">';
        html += '<button type="button" class="btn btn-outline-primary" title="Edit polygon" onclick="event.stopPropagation(); editMappingArea(' + area.id + ');"><i class="bi bi-pencil-square"></i></button>';
        html += '<button type="button" class="btn btn-outline-danger" title="Delete polygon" onclick="event.stopPropagation(); deleteMappingArea(' + area.id + ');"><i class="bi bi-trash"></i></button>';
        html += '</div>';
        html += '</div>';
        html += '</div>';
    });
    
    listContainer.innerHTML = html;
}

// Draw mapping areas on the map (GeoJSON Polygon or MultiPolygon)
function drawMappingAreasOnMap(areas) {
    mappingAreaPolygons.forEach(function(layer) {
        map.removeLayer(layer);
    });
    mappingAreaPolygons = [];

    if (!window.enableMappingAreas || !window.isDatasetOwner) {
        return;
    }

    // Draw new polygons
    areas.forEach(function(area) {
        if (!area.geometry || !area.geometry.type) {
            return;
        }
        if (area.geometry.type !== 'Polygon' && area.geometry.type !== 'MultiPolygon') {
            return;
        }
        var gj = L.geoJSON(area.geometry, {
            style: {
                color: '#ffc107',
                weight: 2,
                opacity: 0.8,
                fillColor: '#ffc107',
                fillOpacity: 0.2
            }
        }).addTo(map);

        gj.mappingAreaId = area.id;
        gj.mappingAreaData = area;

        gj.on('click', function() {
            selectMappingArea(area.id);
        });

        gj.bindPopup('<strong>' + escapeHtml(area.name) + '</strong><br>Points: ' + area.point_count);
        mappingAreaPolygons.push(gj);
    });
}

// Select a mapping area
function selectMappingArea(areaId) {
    selectedMappingArea = areaId;
    
    // Update UI
    document.querySelectorAll('.mapping-area-item').forEach(function(item) {
        item.classList.remove('active');
        if (parseInt(item.getAttribute('data-area-id')) === areaId) {
            item.classList.add('active');
        }
    });
    
    // Highlight polygon on map
    mappingAreaPolygons.forEach(function(polygon) {
        if (polygon.mappingAreaId === areaId) {
            polygon.setStyle({
                color: '#0d6efd',
                fillColor: '#0d6efd',
                fillOpacity: 0.3,
                weight: 3
            });
            map.fitBounds(polygon.getBounds());
        } else {
            polygon.setStyle({
                color: '#ffc107',
                fillColor: '#ffc107',
                fillOpacity: 0.2,
                weight: 2
            });
        }
    });
    
}

// Clear selected polygon
function clearSelectedPolygon() {
    selectedMappingArea = null;
    document.querySelectorAll('.mapping-area-item').forEach(function(item) {
        item.classList.remove('active');
    });
    mappingAreaPolygons.forEach(function(polygon) {
        polygon.setStyle({
            color: '#ffc107',
            fillColor: '#ffc107',
            fillOpacity: 0.2,
            weight: 2
        });
    });
}

// Start drawing a new polygon
function startDrawingPolygon() {
    stopEditingPolygon();
    clearSelectedPolygon();
    
    // Remove existing drawing polygon if any
    if (currentDrawingPolygon) {
        map.removeLayer(currentDrawingPolygon);
        currentDrawingPolygon = null;
    }
    
    // Reset drawing state
    drawingPolygonPoints = [];
    if (drawingClickHandler) {
        map.off('click', drawingClickHandler);
        drawingClickHandler = null;
    }
    
    drawingClickHandler = function(e) {
        drawingPolygonPoints.push(e.latlng);
        
        if (currentDrawingPolygon) {
            map.removeLayer(currentDrawingPolygon);
            currentDrawingPolygon = null;
        }
        
        if (drawingPolygonPoints.length >= 3) {
            currentDrawingPolygon = L.polygon(drawingPolygonPoints, {
                color: '#28a745',
                weight: 2,
                opacity: 0.8,
                fillColor: '#28a745',
                fillOpacity: 0.2
            }).addTo(map);
        } else if (drawingPolygonPoints.length === 2) {
            currentDrawingPolygon = L.polyline(drawingPolygonPoints, {
                color: '#28a745',
                weight: 2,
                opacity: 0.8
            }).addTo(map);
        } else if (drawingPolygonPoints.length === 1) {
            currentDrawingPolygon = L.circleMarker(drawingPolygonPoints[0], {
                radius: 4,
                color: '#28a745',
                fillColor: '#28a745',
                fillOpacity: 0.8
            }).addTo(map);
        }
    };
    
    map.on('click', drawingClickHandler);
    
    document.getElementById('drawPolygonBtn').classList.add('active');
    document.getElementById('drawPolygonBtn').innerHTML = '<i class="bi bi-x-circle"></i> Cancel Drawing';
    document.getElementById('drawPolygonBtn').onclick = stopDrawingPolygon;
    
    var finishBtn = document.getElementById('finishDrawingBtn');
    if (finishBtn) {
        finishBtn.style.display = 'inline-block';
        finishBtn.disabled = false;
    }
    
    alert('Click on the map to add points to the polygon. Use "Finish Drawing" when you are done.');
}

// Stop drawing polygon
function stopDrawingPolygon() {
    if (drawingClickHandler) {
        map.off('click', drawingClickHandler);
        drawingClickHandler = null;
    }
    drawingPolygonPoints = [];
    
    if (currentDrawingPolygon) {
        map.removeLayer(currentDrawingPolygon);
        currentDrawingPolygon = null;
    }
    
    document.getElementById('drawPolygonBtn').classList.remove('active');
    document.getElementById('drawPolygonBtn').innerHTML = '<i class="bi bi-pencil"></i> Draw Polygon';
    document.getElementById('drawPolygonBtn').onclick = startDrawingPolygon;
    
    var finishBtn = document.getElementById('finishDrawingBtn');
    if (finishBtn) {
        finishBtn.disabled = true;
        finishBtn.style.display = 'none';
    }
}

// Finish drawing polygon
function finishDrawingPolygon() {
    if (!drawingPolygonPoints || drawingPolygonPoints.length < 3) {
        alert('Add at least three points before finishing the polygon.');
        return;
    }
    
    var coordinates = drawingPolygonPoints.map(function(latlng) {
        return [latlng.lng, latlng.lat];
    });
    coordinates.push(coordinates[0]);
    
    if (drawingClickHandler) {
        map.off('click', drawingClickHandler);
        drawingClickHandler = null;
    }
    drawingPolygonPoints = [];
    
    var drawBtn = document.getElementById('drawPolygonBtn');
    if (drawBtn) {
        drawBtn.classList.remove('active');
        drawBtn.innerHTML = '<i class="bi bi-pencil"></i> Draw Polygon';
        drawBtn.onclick = startDrawingPolygon;
    }
    
    var finishBtn = document.getElementById('finishDrawingBtn');
    if (finishBtn) {
        finishBtn.disabled = true;
        finishBtn.style.display = 'none';
    }
    
    var drawGeometry = { type: 'Polygon', coordinates: [coordinates] };
    showPolygonForm(null, coordinates, { geometry: drawGeometry });
}

// Start editing a polygon
function startEditingPolygon(areaId) {
    if (typeof areaId === 'number' && selectedMappingArea !== areaId) {
        selectMappingArea(areaId);
    }
    if (!selectedMappingArea) return;

    stopDrawingPolygon();

    var polygon = mappingAreaPolygons.find(function(p) {
        return p.mappingAreaId === selectedMappingArea;
    });

    if (!polygon) return;

    currentEditingPolygon = polygon;

    polygon.setStyle({
        color: '#28a745',
        fillColor: '#28a745',
        fillOpacity: 0.3,
        weight: 3
    });

    showPolygonForm(selectedMappingArea, null);
}

// Stop editing polygon
function stopEditingPolygon() {
    if (currentEditingPolygon) {
        // Reset polygon style
        if (currentEditingPolygon.mappingAreaId === selectedMappingArea) {
            currentEditingPolygon.setStyle({
                color: '#0d6efd',
                fillColor: '#0d6efd',
                fillOpacity: 0.3,
                weight: 3
            });
        } else {
            currentEditingPolygon.setStyle({
                color: '#ffc107',
                fillColor: '#ffc107',
                fillOpacity: 0.2,
                weight: 2
            });
        }
        currentEditingPolygon = null;
    }
    currentEditingPolygonCoordinates = null;
}

// Delete mapping area
function deleteMappingArea(areaId) {
    if (typeof areaId === 'number' && selectedMappingArea !== areaId) {
        selectMappingArea(areaId);
    }
    if (!selectedMappingArea) return;
    
    if (!confirm('Are you sure you want to delete this mapping area?')) {
        return;
    }
    
    var csrfToken = document.querySelector('[name=csrfmiddlewaretoken]').value;
    
    fetch('/datasets/' + window.datasetId + '/mapping-areas/' + selectedMappingArea + '/delete/', {
        method: 'POST',
        headers: {
            'X-CSRFToken': csrfToken,
            'X-Requested-With': 'XMLHttpRequest'
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            clearSelectedPolygon();
            hidePolygonForm();
            stopEditingPolygon();
            loadMappingAreas();
            drawMappingAreasOnMap([]);
        } else {
            alert('Error deleting mapping area: ' + (data.error || 'Unknown error'));
        }
    })
    .catch(error => {
        console.error('Error deleting mapping area:', error);
        alert('Error deleting mapping area: ' + error.message);
    });
}

function editMappingArea(areaId) {
    startEditingPolygon(areaId);
}

// --- GeoJSON import (Polygon / MultiPolygon, optional holes) ---

function normalizeExteriorRingLngLat(ring) {
    if (!ring || ring.length < 3) {
        return null;
    }
    var out = [];
    for (var i = 0; i < ring.length; i++) {
        var lng = parseFloat(ring[i][0]);
        var lat = parseFloat(ring[i][1]);
        if (!isFinite(lng) || !isFinite(lat)) {
            return null;
        }
        out.push([lng, lat]);
    }
    while (out.length >= 2) {
        var a = out[0];
        var b = out[out.length - 1];
        if (a[0] === b[0] && a[1] === b[1]) {
            out.pop();
        } else {
            break;
        }
    }
    if (out.length < 3) {
        return null;
    }
    var closed = out.slice();
    closed.push(closed[0]);
    return closed;
}

function normalizePolygonCoordinatesLngLat(polyCoords) {
    if (!polyCoords || !polyCoords.length) {
        return null;
    }
    var rings = [];
    for (var r = 0; r < polyCoords.length; r++) {
        var ring = normalizeExteriorRingLngLat(polyCoords[r]);
        if (!ring) {
            return null;
        }
        rings.push(ring);
    }
    return rings;
}

function normalizeMultiPolygonCoordinatesLngLat(multiCoords) {
    if (!multiCoords || !multiCoords.length) {
        return null;
    }
    var polys = [];
    for (var p = 0; p < multiCoords.length; p++) {
        var rings = normalizePolygonCoordinatesLngLat(multiCoords[p]);
        if (!rings) {
            return null;
        }
        polys.push(rings);
    }
    return polys.length ? polys : null;
}

function geometryFromGeojsonFragment(geom) {
    if (!geom || !geom.type) {
        return null;
    }
    if (geom.type === 'Polygon') {
        var coords = normalizePolygonCoordinatesLngLat(geom.coordinates);
        if (!coords) {
            return null;
        }
        return { type: 'Polygon', coordinates: coords };
    }
    if (geom.type === 'MultiPolygon') {
        var mc = normalizeMultiPolygonCoordinatesLngLat(geom.coordinates);
        if (!mc) {
            return null;
        }
        return { type: 'MultiPolygon', coordinates: mc };
    }
    if (geom.type === 'GeometryCollection' && geom.geometries) {
        var collected = [];
        for (var i = 0; i < geom.geometries.length; i++) {
            var inner = geometryFromGeojsonFragment(geom.geometries[i]);
            if (!inner) {
                continue;
            }
            if (inner.type === 'Polygon') {
                collected.push(inner.coordinates);
            } else if (inner.type === 'MultiPolygon') {
                for (var j = 0; j < inner.coordinates.length; j++) {
                    collected.push(inner.coordinates[j]);
                }
            }
        }
        if (collected.length === 0) {
            return null;
        }
        if (collected.length === 1) {
            return { type: 'Polygon', coordinates: collected[0] };
        }
        return { type: 'MultiPolygon', coordinates: collected };
    }
    return null;
}

function extractMappingAreaGeometryFromGeojson(root) {
    if (!root || typeof root !== 'object') {
        return null;
    }
    var nameHint = null;

    if (root.type === 'FeatureCollection' && root.features) {
        for (var fi = 0; fi < root.features.length; fi++) {
            var got = extractMappingAreaGeometryFromGeojson(root.features[fi]);
            if (got && got.geometry) {
                return got;
            }
        }
        return null;
    }

    if (root.type === 'Feature' && root.geometry) {
        if (root.properties) {
            nameHint = root.properties.name || root.properties.Name || root.properties.NAME;
        }
        var g = geometryFromGeojsonFragment(root.geometry);
        if (g) {
            return { geometry: g, nameHint: nameHint };
        }
        return null;
    }

    var direct = geometryFromGeojsonFragment(root);
    if (direct) {
        return { geometry: direct, nameHint: null };
    }
    return null;
}

function triggerImportMappingAreaGeojson() {
    var input = document.getElementById('importMappingAreaGeojsonInput');
    if (input) {
        input.click();
    }
}

function onMappingAreaGeojsonFileSelected(ev) {
    var input = ev.target;
    var file = input.files && input.files[0];
    input.value = '';
    if (!file) {
        return;
    }
    var reader = new FileReader();
    reader.onload = function(e) {
        try {
            var json = JSON.parse(e.target.result);
            var extracted = extractMappingAreaGeometryFromGeojson(json);
            if (!extracted || !extracted.geometry) {
                alert('Could not find a valid Polygon or MultiPolygon in the GeoJSON. Use WGS84 (longitude, latitude) and rings with at least three vertices.');
                return;
            }
            stopDrawingPolygon();
            if (typeof map !== 'undefined' && map) {
                try {
                    var tmpLayer = L.geoJSON(extracted.geometry);
                    map.fitBounds(tmpLayer.getBounds(), { padding: [24, 24], maxZoom: 16 });
                    map.removeLayer(tmpLayer);
                } catch (errFit) {
                    console.debug('fitBounds skipped:', errFit);
                }
            }
            showPolygonForm(null, null, { nameHint: extracted.nameHint, geometry: extracted.geometry });
        } catch (err) {
            console.error(err);
            alert('Invalid GeoJSON file.');
        }
    };
    reader.onerror = function() {
        alert('Could not read the file.');
    };
    reader.readAsText(file, 'UTF-8');
}

// Show polygon form
function showPolygonForm(areaId, coordinates, options) {
    options = options || {};
    var form = document.getElementById('polygonForm');
    var nameInput = document.getElementById('polygonName');
    var formTitle = document.querySelector('#polygonForm h6');
    
    if (areaId) {
        // Editing existing polygon
        var polygon = mappingAreaPolygons.find(function(p) {
            return p.mappingAreaId === areaId;
        });
        if (polygon && polygon.mappingAreaData) {
            nameInput.value = polygon.mappingAreaData.name || '';
            // Set selected users
            var userSelect = document.getElementById('polygonUsers');
            if (polygon.mappingAreaData.allocated_users) {
                Array.from(userSelect.options).forEach(function(option) {
                    option.selected = polygon.mappingAreaData.allocated_users.includes(parseInt(option.value));
                });
            }
            if (formTitle) formTitle.textContent = 'Edit Polygon Details';
            if (polygon.mappingAreaData.geometry) {
                currentMappingAreaGeometry = JSON.parse(JSON.stringify(polygon.mappingAreaData.geometry));
            } else {
                currentMappingAreaGeometry = null;
            }
        }
        currentEditingPolygonCoordinates = null;
    } else {
        // Creating new polygon
        if (options.nameHint != null && String(options.nameHint).trim() !== '') {
            nameInput.value = String(options.nameHint).trim();
        } else {
            nameInput.value = '';
        }
        document.getElementById('polygonUsers').selectedIndex = -1;
        if (formTitle) formTitle.textContent = 'New Polygon Details';
        if (options.geometry) {
            currentMappingAreaGeometry = options.geometry;
            currentDrawingPolygonCoordinates = null;
        } else if (coordinates) {
            currentDrawingPolygonCoordinates = coordinates;
            currentMappingAreaGeometry = { type: 'Polygon', coordinates: [coordinates] };
        } else {
            currentDrawingPolygonCoordinates = null;
            currentMappingAreaGeometry = null;
        }
    }
    
    form.style.display = 'block';
    form.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

// Hide polygon form
function hidePolygonForm() {
    document.getElementById('polygonForm').style.display = 'none';
    document.getElementById('polygonName').value = '';
    document.getElementById('polygonUsers').selectedIndex = -1;
    currentDrawingPolygonCoordinates = null;
    currentEditingPolygonCoordinates = null;
    currentMappingAreaGeometry = null;
}

// Cancel polygon form
function cancelPolygonForm() {
    hidePolygonForm();
    stopDrawingPolygon();
    stopEditingPolygon();
    
    // Remove drawing polygon if exists
    if (currentDrawingPolygon) {
        map.removeLayer(currentDrawingPolygon);
        currentDrawingPolygon = null;
    }
}

// Variables to store coordinates / GeoJSON geometry for mapping areas
var currentDrawingPolygonCoordinates = null;
var currentEditingPolygonCoordinates = null;
var currentMappingAreaGeometry = null;

// Load users for allocation dropdown
function loadUsersForAllocation() {
    // Get users from the page or make an API call
    // For now, we'll populate from a simple list or make an API call
    // This would need a users endpoint or pass users in the template
    var userSelect = document.getElementById('polygonUsers');
    if (!userSelect) return;
    
    // For now, leave it empty - users can be added via an API call if needed
    // Or we can pass users in the template context
}

// Handle polygon form submission
document.addEventListener('DOMContentLoaded', function() {
    var form = document.getElementById('mappingAreaForm');
    if (form) {
        form.addEventListener('submit', function(e) {
            e.preventDefault();
            saveMappingArea();
        });
    }
    var geoInput = document.getElementById('importMappingAreaGeojsonInput');
    if (geoInput) {
        geoInput.addEventListener('change', onMappingAreaGeojsonFileSelected);
    }
});

// Save mapping area
function saveMappingArea() {
    if (!window.isDatasetOwner) {
        alert('Only the dataset owner can manage mapping areas.');
        return;
    }
    
    var name = document.getElementById('polygonName').value;
    if (!name) {
        alert('Please enter a name for the mapping area.');
        return;
    }
    
    var geometry = currentMappingAreaGeometry;
    if (!geometry) {
        var coordinates = currentDrawingPolygonCoordinates || currentEditingPolygonCoordinates;
        if (!coordinates || coordinates.length < 3) {
            alert('Invalid polygon coordinates.');
            return;
        }
        geometry = { type: 'Polygon', coordinates: [coordinates] };
    } else if (geometry.type === 'Polygon') {
        var polyCoords = geometry.coordinates;
        if (!polyCoords || !polyCoords[0] || polyCoords[0].length < 4) {
            alert('Invalid polygon geometry.');
            return;
        }
    } else if (geometry.type === 'MultiPolygon') {
        if (!geometry.coordinates || !geometry.coordinates.length) {
            alert('Invalid multipolygon geometry.');
            return;
        }
    } else {
        alert('Invalid geometry.');
        return;
    }

    console.debug('Using mapping area geometry:', geometry);

    // Get selected users
    var userSelect = document.getElementById('polygonUsers');
    var selectedUsers = Array.from(userSelect.selectedOptions).map(function(option) {
        return parseInt(option.value);
    });

    var data = {
        name: name,
        geometry: geometry,
        allocated_users: selectedUsers
    };
    console.debug('Prepared mapping area payload:', data);
    
    var url = '/datasets/' + window.datasetId + '/mapping-areas/create/';
    var method = 'POST';
    
    // If editing, use update endpoint
    if (selectedMappingArea) {
        url = '/datasets/' + window.datasetId + '/mapping-areas/' + selectedMappingArea + '/update/';
    }
    
    var csrfToken = document.querySelector('[name=csrfmiddlewaretoken]').value;
    
    console.debug('Submitting mapping area request to', url, 'with method', method);
    fetch(url, {
        method: method,
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': csrfToken,
            'X-Requested-With': 'XMLHttpRequest'
        },
        body: JSON.stringify(data)
    })
    .then(async response => {
        console.debug('Mapping area save response status:', response.status);
        const text = await response.text();
        console.debug('Mapping area save raw response:', text);
        let payload = null;
        if (text) {
            const contentType = response.headers.get('content-type') || '';
            if (contentType.includes('application/json')) {
                try {
                    payload = JSON.parse(text);
                } catch (parseError) {
                    console.error('Error parsing mapping area response JSON:', parseError, text);
                    payload = null;
                }
            }
        }

        if (!response.ok) {
            const errorMessage =
                (payload && payload.error) ? payload.error :
                (text ? text : `Request failed with status ${response.status}`);
            throw new Error(errorMessage);
        }

        return payload || {};
    })
    .then(data => {
        if (data.success) {
            console.debug('Mapping area save successful response payload:', data);
            // Reload mapping areas
            loadMappingAreas();
            hidePolygonForm();
            stopDrawingPolygon();
            stopEditingPolygon();
            
            // Remove drawing polygon
            if (currentDrawingPolygon) {
                map.removeLayer(currentDrawingPolygon);
                currentDrawingPolygon = null;
            }
            
            // Select the new/updated area
            if (data.mapping_area && data.mapping_area.id) {
                setTimeout(function() {
                    selectMappingArea(data.mapping_area.id);
                }, 500);
            }
        } else {
            alert('Error saving mapping area: ' + (data.error || 'Unknown error'));
        }
    })
    .catch(error => {
        console.error('Error saving mapping area:', error);
        alert('Error saving mapping area: ' + (error.message || error));
        console.debug('Mapping area request payload that failed:', data);
    });
}