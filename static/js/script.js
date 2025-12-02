// Global state
let currentState = null;
let currentSelectionType = 'AC wise';
let currentSamples = 300;

// DOM Elements
const stateSelect = document.getElementById('state-select');
const selectionTypeRadios = document.querySelectorAll('input[name="selection-type"]');
const samplesInput = document.getElementById('samples-input');
const generateBtn = document.getElementById('generate-btn');
const configInfo = document.getElementById('config-info');
const configDetails = document.getElementById('config-details');
const progressSection = document.getElementById('progress-section');
const progressFill = document.getElementById('progress-fill');
const progressText = document.getElementById('progress-text');
const errorMessage = document.getElementById('error-message');
const successMessage = document.getElementById('success-message');
const welcomeSection = document.getElementById('welcome-section');
const resultsSection = document.getElementById('results-section');

// Tab elements
const tabBtns = document.querySelectorAll('.tab-btn');
const tabPanes = document.querySelectorAll('.tab-pane');

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    setupEventListeners();
});

function setupEventListeners() {
    // State selection
    stateSelect.addEventListener('change', handleStateChange);
    
    // Selection type
    selectionTypeRadios.forEach(radio => {
        radio.addEventListener('change', handleSelectionTypeChange);
    });
    
    // Samples input
    samplesInput.addEventListener('input', handleSamplesChange);
    
    // Generate button
    generateBtn.addEventListener('click', handleGenerate);
    
    // Tab switching
    tabBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            const tabName = btn.dataset.tab;
            switchTab(tabName);
        });
    });
    
    // Download buttons
    document.getElementById('download-summary-btn').addEventListener('click', downloadSummary);
    document.getElementById('download-booths-btn').addEventListener('click', downloadBooths);
    document.getElementById('download-maps-btn').addEventListener('click', downloadMaps);
    
    // Map selector
    document.getElementById('map-select').addEventListener('change', handleMapSelect);
}

function handleStateChange() {
    currentState = stateSelect.value;
    
    if (currentState) {
        generateBtn.disabled = false;
        updateConfigInfo();
        fetchACPCList();
    } else {
        generateBtn.disabled = true;
        configInfo.style.display = 'none';
    }
}

function handleSelectionTypeChange(e) {
    currentSelectionType = e.target.value;
    updateConfigInfo();
    if (currentState) {
        fetchACPCList();
    }
}

function handleSamplesChange() {
    currentSamples = parseInt(samplesInput.value);
    updateConfigInfo();
}

function updateConfigInfo() {
    if (!currentState) return;
    
    const clustersPerAC = Math.round(currentSamples / 25);
    const boothsPerAC = clustersPerAC * 2;
    
    configDetails.innerHTML = `
        <strong>Configuration:</strong><br>
        - State: ${currentState}<br>
        - ${clustersPerAC} clusters per ${currentSelectionType === 'AC wise' ? 'AC' : 'PC'}<br>
        - 2 booths per cluster<br>
        - ~${boothsPerAC} booths selected per ${currentSelectionType === 'AC wise' ? 'AC' : 'PC'}
    `;
    configInfo.style.display = 'block';
}

async function fetchACPCList() {
    try {
        const response = await fetch(`/api/ac_pc_list/${currentState}/${currentSelectionType}`);
        const data = await response.json();
        
        if (data.count) {
            const clustersPerAC = Math.round(currentSamples / 25);
            const boothsPerAC = clustersPerAC * 2;
            
            configDetails.innerHTML = `
                <strong>Configuration:</strong><br>
                - ${data.count} ${currentSelectionType === 'AC wise' ? 'ACs' : 'PCs'} in ${currentState}<br>
                - ${clustersPerAC} clusters per ${currentSelectionType === 'AC wise' ? 'AC' : 'PC'}<br>
                - 2 booths per cluster<br>
                - ~${boothsPerAC} booths selected per ${currentSelectionType === 'AC wise' ? 'AC' : 'PC'}
            `;
        }
    } catch (error) {
        console.error('Error fetching AC/PC list:', error);
    }
}

async function handleGenerate() {
    if (!currentState) {
        showError('Please select a state first');
        return;
    }
    
    // Reset messages
    hideMessages();
    
    // Show progress
    progressSection.style.display = 'block';
    progressFill.style.width = '0%';
    progressText.textContent = 'Starting processing...';
    generateBtn.disabled = true;
    
    try {
        // Simulate progress animation
        let progress = 0;
        const progressInterval = setInterval(() => {
            progress += 1;
            if (progress <= 90) {
                progressFill.style.width = progress + '%';
                progressText.textContent = `Processing... ${progress}%`;
            }
        }, 500);
        
        const response = await fetch('/api/process', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                state: currentState,
                selection_type: currentSelectionType,
                samples_per_ac: currentSamples
            })
        });
        
        clearInterval(progressInterval);
        
        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.detail || 'Processing failed');
        }
        
        const data = await response.json();
        
        // Complete progress
        progressFill.style.width = '100%';
        progressText.textContent = 'Processing complete!';
        
        // Show success message
        showSuccess(data.message);
        
        // Display results
        displayResults(data);
        
        // Hide progress after a delay
        setTimeout(() => {
            progressSection.style.display = 'none';
        }, 2000);
        
    } catch (error) {
        showError('Error: ' + error.message);
        progressSection.style.display = 'none';
    } finally {
        generateBtn.disabled = false;
    }
}

function displayResults(stats) {
    // Hide welcome, show results
    welcomeSection.style.display = 'none';
    resultsSection.style.display = 'block';
    
    // Update stats cards
    document.getElementById('stat-total-acs').textContent = stats.total_acs;
    document.getElementById('stat-completed').textContent = `${stats.completed}/${stats.total_acs}`;
    document.getElementById('stat-total-booths').textContent = stats.total_booths;
    document.getElementById('stat-total-selected').textContent = stats.total_selected;
    
    // Load summary data
    loadSummaryData();
    loadBoothsData();
    loadMapsData();
}

async function loadSummaryData() {
    try {
        const response = await fetch('/api/results/summary');
        const data = await response.json();
        
        const table = document.getElementById('summary-table');
        const thead = table.querySelector('thead');
        const tbody = table.querySelector('tbody');
        
        // Clear existing content
        thead.innerHTML = '';
        tbody.innerHTML = '';
        
        if (data.data.length > 0) {
            // Create headers
            const headers = Object.keys(data.data[0]);
            const headerRow = document.createElement('tr');
            headers.forEach(header => {
                const th = document.createElement('th');
                th.textContent = header;
                headerRow.appendChild(th);
            });
            thead.appendChild(headerRow);
            
            // Create rows
            data.data.forEach(row => {
                const tr = document.createElement('tr');
                headers.forEach(header => {
                    const td = document.createElement('td');
                    td.textContent = row[header];
                    tr.appendChild(td);
                });
                tbody.appendChild(tr);
            });
        }
    } catch (error) {
        console.error('Error loading summary:', error);
    }
}

async function loadBoothsData() {
    try {
        const response = await fetch('/api/results/selected_booths');
        const data = await response.json();
        
        const table = document.getElementById('booths-table');
        const thead = table.querySelector('thead');
        const tbody = table.querySelector('tbody');
        
        // Clear existing content
        thead.innerHTML = '';
        tbody.innerHTML = '';
        
        if (data.data.length > 0) {
            // Create headers
            const headers = Object.keys(data.data[0]);
            const headerRow = document.createElement('tr');
            headers.forEach(header => {
                const th = document.createElement('th');
                th.textContent = header;
                headerRow.appendChild(th);
            });
            thead.appendChild(headerRow);
            
            // Create rows
            data.data.forEach(row => {
                const tr = document.createElement('tr');
                headers.forEach(header => {
                    const td = document.createElement('td');
                    td.textContent = row[header];
                    tr.appendChild(td);
                });
                tbody.appendChild(tr);
            });
        }
    } catch (error) {
        console.error('Error loading booths:', error);
    }
}

async function loadMapsData() {
    try {
        const response = await fetch('/api/results/maps');
        const data = await response.json();
        
        const mapSelect = document.getElementById('map-select');
        mapSelect.innerHTML = '<option value="">-- Select AC/PC --</option>';
        
        data.maps.forEach(map => {
            const option = document.createElement('option');
            option.value = map.filename;
            option.textContent = `${map.code} - ${map.name}`;
            mapSelect.appendChild(option);
        });
    } catch (error) {
        console.error('Error loading maps:', error);
    }
}

function handleMapSelect() {
    const mapSelect = document.getElementById('map-select');
    const mapViewer = document.getElementById('map-viewer');
    const filename = mapSelect.value;
    
    if (filename) {
        mapViewer.innerHTML = `<iframe src="/api/map/${filename}" style="width:100%;height:100%;border:none;"></iframe>`;
    } else {
        mapViewer.innerHTML = '<p class="text-muted">Select an AC/PC to view its map</p>';
    }
}

function switchTab(tabName) {
    // Update buttons
    tabBtns.forEach(btn => {
        if (btn.dataset.tab === tabName) {
            btn.classList.add('active');
        } else {
            btn.classList.remove('active');
        }
    });
    
    // Update panes
    tabPanes.forEach(pane => {
        if (pane.id === `${tabName}-tab`) {
            pane.classList.add('active');
        } else {
            pane.classList.remove('active');
        }
    });
}

async function downloadSummary() {
    try {
        const response = await fetch('/api/download/summary');
        const blob = await response.blob();
        downloadBlob(blob, 'summary.csv');
    } catch (error) {
        showError('Error downloading summary: ' + error.message);
    }
}

async function downloadBooths() {
    try {
        const response = await fetch('/api/download/selected_booths');
        const blob = await response.blob();
        downloadBlob(blob, 'selected_booths.csv');
    } catch (error) {
        showError('Error downloading booths: ' + error.message);
    }
}

async function downloadMaps() {
    try {
        showSuccess('Preparing maps download... This may take a moment.');
        const response = await fetch('/api/download/maps');
        const blob = await response.blob();
        downloadBlob(blob, 'maps.zip');
        showSuccess('Maps downloaded successfully!');
    } catch (error) {
        showError('Error downloading maps: ' + error.message);
    }
}

function downloadBlob(blob, filename) {
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    window.URL.revokeObjectURL(url);
    document.body.removeChild(a);
}

function showError(message) {
    errorMessage.textContent = message;
    errorMessage.style.display = 'block';
    successMessage.style.display = 'none';
}

function showSuccess(message) {
    successMessage.textContent = message;
    successMessage.style.display = 'block';
    errorMessage.style.display = 'none';
}

function hideMessages() {
    errorMessage.style.display = 'none';
    successMessage.style.display = 'none';
}
