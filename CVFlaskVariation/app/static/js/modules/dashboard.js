/**
 * Dashboard module for server monitoring and control
 */

import VoiceComm from './voiceComm.js';

let metricsRefreshInterval = null;
let isRefreshing = false;
let currentView = 'server-health';
let selectedCameraId = null;
let voiceComm = null;
let currentVoiceSession = null;

/**
 * Initialize dashboard on page load
 */
document.addEventListener('DOMContentLoaded', () => {
    console.log('Dashboard initializing...');

    // Initialize voice communication
    voiceComm = new VoiceComm();

    // Load initial metrics and start auto-refresh
    loadMetrics();
    startAutoRefresh();

    console.log('Dashboard auto-refresh enabled with 10s interval');
});

/**
 * Fetch and display all metrics
 */
async function loadMetrics() {
    if (isRefreshing) {
        console.log('Already refreshing, skipping...');
        return;
    }

    isRefreshing = true;
    console.log('Fetching metrics from /admin/metrics...');

    try {
        const response = await fetch('/admin/metrics');
        console.log('Response status:', response.status);

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();
        console.log('Metrics data received:', data);
        updateDashboard(data);

        // Hide loading, show content
        document.getElementById('loadingIndicator').style.display = 'none';
        document.getElementById('dashboardContent').style.display = 'block';

    } catch (error) {
        console.error('Error loading metrics:', error);
        console.error('Error details:', error.stack);
        showError('Failed to load metrics: ' + error.message);
    } finally {
        isRefreshing = false;
    }
}

/**
 * Update all dashboard components with new data
 */
function updateDashboard(data) {
    updateHealthStatus(data.health);
    updateCPU(data.cpu);
    updateMemory(data.memory);
    updateGPU(data.gpu);
    updateDisk(data.disk);
    updateModel(data.model);
    updatePerformance(data.performance);
    updateLastUpdate();
}

/**
 * Update health status section
 */
function updateHealthStatus(health) {
    const statusElement = document.getElementById('overallStatus');
    const statusText = health.status.toUpperCase();

    statusElement.textContent = statusText;

    // Update status badge color
    statusElement.className = 'value';
    if (health.status === 'healthy') {
        statusElement.style.color = '#4ade80';
    } else if (health.status === 'warning') {
        statusElement.style.color = '#fb923c';
    } else {
        statusElement.style.color = '#ef4444';
    }

    // Update warnings if any
    const warningsContainer = document.getElementById('warningsContainer');
    if (health.warnings && health.warnings.length > 0) {
        const warningsHTML = `
            <div class="warnings">
                <h4>Warnings</h4>
                <ul>
                    ${health.warnings.map(w => `<li>${w}</li>`).join('')}
                </ul>
            </div>
        `;
        warningsContainer.innerHTML = warningsHTML;
    } else {
        warningsContainer.innerHTML = '';
    }
}

/**
 * Update CPU metrics
 */
function updateCPU(cpu) {
    document.getElementById('cpuValue').textContent = cpu.percent.toFixed(1) + '%';
    document.getElementById('cpuCores').textContent = cpu.count;
    document.getElementById('cpuBar').style.width = cpu.percent + '%';

    // Change color based on usage
    const bar = document.getElementById('cpuBar');
    if (cpu.percent >= 90) {
        bar.style.background = 'linear-gradient(135deg, #ef4444 0%, #dc2626 100%)';
    } else if (cpu.percent >= 70) {
        bar.style.background = 'linear-gradient(135deg, #fb923c 0%, #f59e0b 100%)';
    } else {
        bar.style.background = 'linear-gradient(135deg, #06b6d4 0%, #3b82f6 100%)';
    }
}

/**
 * Update memory metrics
 */
function updateMemory(memory) {
    document.getElementById('memoryValue').textContent = memory.percent.toFixed(1) + '%';
    document.getElementById('memoryUsed').textContent = memory.used_gb.toFixed(1);
    document.getElementById('memoryTotal').textContent = memory.total_gb.toFixed(1);
    document.getElementById('memoryBar').style.width = memory.percent + '%';

    // Change color based on usage
    const bar = document.getElementById('memoryBar');
    if (memory.percent >= 90) {
        bar.style.background = 'linear-gradient(135deg, #ef4444 0%, #dc2626 100%)';
    } else if (memory.percent >= 70) {
        bar.style.background = 'linear-gradient(135deg, #fb923c 0%, #f59e0b 100%)';
    } else {
        bar.style.background = 'linear-gradient(135deg, #06b6d4 0%, #3b82f6 100%)';
    }
}

/**
 * Update GPU metrics
 */
function updateGPU(gpu) {
    if (!gpu.available) {
        document.getElementById('gpuValue').textContent = 'N/A';
        document.getElementById('gpuName').textContent = 'No GPU Available';
        document.getElementById('gpuMemory').textContent = '0';
        document.getElementById('gpuMemoryTotal').textContent = '0';
        document.getElementById('gpuBar').style.width = '0%';
        return;
    }

    const utilization = gpu.utilization_percent || 0;
    document.getElementById('gpuValue').textContent = utilization.toFixed(1) + '%';
    document.getElementById('gpuName').textContent = gpu.name || 'Unknown GPU';
    document.getElementById('gpuMemory').textContent = gpu.memory_allocated_gb.toFixed(1);
    document.getElementById('gpuMemoryTotal').textContent = gpu.memory_total_gb.toFixed(1);
    document.getElementById('gpuBar').style.width = utilization + '%';

    // Change color based on usage
    const bar = document.getElementById('gpuBar');
    if (utilization >= 95) {
        bar.style.background = 'linear-gradient(135deg, #ef4444 0%, #dc2626 100%)';
    } else if (utilization >= 70) {
        bar.style.background = 'linear-gradient(135deg, #fb923c 0%, #f59e0b 100%)';
    } else {
        bar.style.background = 'linear-gradient(135deg, #06b6d4 0%, #3b82f6 100%)';
    }
}

/**
 * Update disk metrics
 */
function updateDisk(disk) {
    if (disk.error) {
        document.getElementById('diskValue').textContent = 'Error';
        return;
    }

    document.getElementById('diskValue').textContent = disk.percent.toFixed(1) + '%';
    document.getElementById('diskUsed').textContent = disk.used_gb.toFixed(1);
    document.getElementById('diskTotal').textContent = disk.total_gb.toFixed(1);
    document.getElementById('diskBar').style.width = disk.percent + '%';

    // Change color based on usage
    const bar = document.getElementById('diskBar');
    if (disk.percent >= 90) {
        bar.style.background = 'linear-gradient(135deg, #ef4444 0%, #dc2626 100%)';
    } else if (disk.percent >= 70) {
        bar.style.background = 'linear-gradient(135deg, #fb923c 0%, #f59e0b 100%)';
    } else {
        bar.style.background = 'linear-gradient(135deg, #06b6d4 0%, #3b82f6 100%)';
    }
}

/**
 * Update model status
 */
function updateModel(model) {
    document.getElementById('modelType').textContent = model.model_type || 'Unknown';
    document.getElementById('modelClasses').textContent = model.classes;
    document.getElementById('modelDevice').textContent = model.device;

    const statusBadge = document.getElementById('modelStatus');
    if (model.loaded) {
        statusBadge.textContent = 'Loaded';
        statusBadge.className = 'status-badge status-healthy';
    } else {
        statusBadge.textContent = 'Not Loaded';
        statusBadge.className = 'status-badge status-error';
    }
}

/**
 * Update performance metrics
 */
function updatePerformance(performance) {
    document.getElementById('uptime').textContent = performance.uptime_formatted;
    document.getElementById('totalRequests').textContent = performance.total_requests;
    document.getElementById('totalErrors').textContent = performance.total_errors;
    document.getElementById('errorRate').textContent = performance.error_rate_percent.toFixed(2);
    document.getElementById('avgInference').textContent = performance.avg_inference_time_ms.toFixed(2);
    document.getElementById('totalInferences').textContent = performance.total_inferences;
}

/**
 * Update last update timestamp
 */
function updateLastUpdate() {
    const now = new Date();
    const timeString = now.toLocaleTimeString();
    document.getElementById('lastUpdate').textContent = timeString;
}

/**
 * Start auto-refresh interval
 */
function startAutoRefresh() {
    // Refresh every 10 seconds (reduced from 5s to prevent request freezing)
    metricsRefreshInterval = setInterval(() => {
        if (currentView === 'server-health') {
            loadMetrics();
        } else if (currentView === 'camera-management') {
            loadCameras();
        }
    }, 10000);
}

/**
 * Stop auto-refresh interval
 */
function stopAutoRefresh() {
    if (metricsRefreshInterval) {
        clearInterval(metricsRefreshInterval);
        metricsRefreshInterval = null;
    }
}

/**
 * Manually refresh metrics
 */
window.refreshMetrics = function() {
    console.log('Manual refresh triggered');
    loadMetrics();
};

/**
 * Ping the server
 */
window.pingServer = async function() {
    try {
        const start = performance.now();
        const response = await fetch('/admin/ping');
        const end = performance.now();
        const latency = (end - start).toFixed(2);

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();
        alert(`Server is online!\nStatus: ${data.status}\nLatency: ${latency}ms`);
    } catch (error) {
        console.error('Ping failed:', error);
        alert('Ping failed: ' + error.message);
    }
};

/**
 * Reset tracking statistics
 */
window.resetTracking = async function() {
    if (!confirm('Are you sure you want to reset tracking statistics?')) {
        return;
    }

    try {
        const response = await fetch('/admin/tracking/reset', {
            method: 'POST'
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();
        alert(data.message || 'Tracking reset successfully');
        loadMetrics();
    } catch (error) {
        console.error('Reset tracking failed:', error);
        alert('Failed to reset tracking: ' + error.message);
    }
};

/**
 * Shutdown the server
 */
window.shutdownServer = async function() {
    const confirmed = confirm(
        'Are you sure you want to shutdown the server?\n\n' +
        'This will stop all running services and close the application.'
    );

    if (!confirmed) {
        return;
    }

    try {
        stopAutoRefresh();

        const response = await fetch('/admin/system/shutdown', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ delay: 1 })
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();
        alert(data.message || 'Server shutting down...');

        // Show shutdown message
        document.getElementById('dashboardContent').innerHTML = `
            <div class="loading">
                <div class="spinner"></div>
                <p>Server is shutting down...</p>
                <p style="margin-top: 10px; font-size: 0.9rem;">Uptime: ${data.uptime}</p>
            </div>
        `;

    } catch (error) {
        console.error('Shutdown failed:', error);
        alert('Failed to shutdown server: ' + error.message);
        startAutoRefresh();
    }
};

/**
 * Show error message
 */
function showError(message) {
    const loadingIndicator = document.getElementById('loadingIndicator');
    loadingIndicator.innerHTML = `
        <div style="color: #ef4444;">
            <h3>Error</h3>
            <p>${message}</p>
            <button class="btn btn-primary" onclick="location.reload()" style="margin-top: 20px;">
                Retry
            </button>
        </div>
    `;
}

// Clean up on page unload
window.addEventListener('beforeunload', () => {
    stopAutoRefresh();
});

/**
 * Switch between Server Health and Camera Management views
 */
window.switchView = function(view) {
    currentView = view;

    // Hide loading indicator (in case it's still showing)
    document.getElementById('loadingIndicator').style.display = 'none';

    // Update button states
    document.getElementById('serverHealthBtn').classList.toggle('active', view === 'server-health');
    document.getElementById('cameraManagementBtn').classList.toggle('active', view === 'camera-management');

    // Update view visibility
    document.getElementById('dashboardContent').style.display = view === 'server-health' ? 'block' : 'none';
    document.getElementById('cameraManagementView').style.display = view === 'camera-management' ? 'block' : 'none';

    // Load camera data if switching to camera management
    if (view === 'camera-management') {
        loadCameras();
    }
};

/**
 * Load cameras from server
 */
async function loadCameras() {
    console.log('Loading cameras...');
    try {
        const response = await fetch('/admin/cameras/list');
        console.log('Camera list response status:', response.status);

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();
        console.log('Cameras data received:', data);

        if (data.success) {
            updateCameraView(data);
        } else {
            console.error('Camera list failed:', data.error);
            showError('Failed to load cameras: ' + (data.error || 'Unknown error'));
        }
    } catch (error) {
        console.error('Error loading cameras:', error);
        showError('Failed to load cameras: ' + error.message);
    }
}

/**
 * Update camera management view with data
 */
function updateCameraView(data) {
    console.log('Updating camera view with data:', data);
    const stats = data.statistics;
    const cameras = data.cameras;

    // Update statistics
    document.getElementById('totalCameras').textContent = stats.total_cameras;
    document.getElementById('onlineCameras').textContent = stats.online_cameras;
    document.getElementById('offlineCameras').textContent = stats.offline_cameras;

    // Update camera grid
    const cameraGrid = document.getElementById('cameraGrid');
    const emptyState = document.getElementById('emptyCamerasState');

    if (cameras.length === 0) {
        console.log('No cameras found, showing empty state');
        cameraGrid.innerHTML = '';
        emptyState.style.display = 'block';
        return;
    }

    console.log(`Displaying ${cameras.length} cameras`);
    emptyState.style.display = 'none';
    cameraGrid.innerHTML = cameras.map(camera => createCameraCard(camera)).join('');
}

/**
 * Create HTML for a camera card
 */
function createCameraCard(camera) {
    const isOffline = camera.status === 'offline';
    const statusClass = isOffline ? 'offline' : '';
    const statusDotClass = isOffline ? 'camera-status-dot offline' : 'camera-status-dot';

    const batteryInfo = camera.battery_level !== null
        ? `<div class="camera-info-row">
               <span>Battery:</span>
               <span class="value">${camera.battery_level}%${camera.is_charging ? ' (Charging)' : ''}</span>
           </div>`
        : '';

    const locationInfo = camera.location
        ? `<div class="camera-info-row">
               <span>Location:</span>
               <span class="value">${camera.location.latitude.toFixed(4)}, ${camera.location.longitude.toFixed(4)}</span>
           </div>`
        : '';

    const streamingInfo = `<div class="camera-info-row">
        <span>Streaming:</span>
        <span class="value">${camera.dashboard_streaming_enabled ? 'Enabled' : 'Disabled'}</span>
    </div>`;

    const voiceStatusInfo = camera.voice_session_active
        ? `<div class="camera-info-row" style="color: #10b981;">
               <span>Voice:</span>
               <span class="value">Active</span>
           </div>`
        : '';

    return `
        <div class="camera-card ${statusClass}">
            <div class="camera-header">
                <div class="camera-title">${camera.camera_name}</div>
                <div class="${statusDotClass}"></div>
            </div>
            <div class="camera-info">
                <div class="camera-info-row">
                    <span>Status:</span>
                    <span class="value">${camera.status}</span>
                </div>
                <div class="camera-info-row">
                    <span>Uptime:</span>
                    <span class="value">${camera.uptime_formatted}</span>
                </div>
                <div class="camera-info-row">
                    <span>Detection:</span>
                    <span class="value">${camera.detection_active ? 'Active' : 'Inactive'}</span>
                </div>
                <div class="camera-info-row">
                    <span>FPS:</span>
                    <span class="value">${camera.current_fps.toFixed(1)}</span>
                </div>
                <div class="camera-info-row">
                    <span>Detections:</span>
                    <span class="value">${camera.total_detections}</span>
                </div>
                ${streamingInfo}
                ${voiceStatusInfo}
                ${batteryInfo}
                ${locationInfo}
            </div>
            <div class="camera-actions">
                <button class="camera-btn camera-btn-view" onclick="showCameraView('${camera.camera_id}', '${camera.camera_name}')">
                    View
                </button>
                <button class="camera-btn camera-btn-message" onclick="showMessageModal('${camera.camera_id}', '${camera.camera_name}')">
                    Message
                </button>
                <button class="camera-btn camera-btn-voice" id="voiceBtn-${camera.camera_id}" onclick="toggleVoiceCall('${camera.camera_id}', '${camera.camera_name}')">
                    Voice Call
                </button>
            </div>
        </div>
    `;
}

/**
 * Show message modal for specific camera
 */
window.showMessageModal = function(cameraId, cameraName) {
    selectedCameraId = cameraId;
    document.getElementById('modalTitle').textContent = `Send Message to ${cameraName}`;
    document.getElementById('messageInput').value = '';
    document.getElementById('messageModal').classList.add('active');
};

/**
 * Show broadcast modal
 */
window.showBroadcastModal = function() {
    selectedCameraId = null;
    document.getElementById('modalTitle').textContent = 'Broadcast Message to All Cameras';
    document.getElementById('messageInput').value = '';
    document.getElementById('messageModal').classList.add('active');
};

/**
 * Close message modal
 */
window.closeModal = function() {
    document.getElementById('messageModal').classList.remove('active');
    selectedCameraId = null;
};

/**
 * Send message to camera or broadcast
 */
window.sendMessage = async function() {
    const message = document.getElementById('messageInput').value.trim();

    if (!message) {
        alert('Please enter a message');
        return;
    }

    try {
        let url, method;

        if (selectedCameraId) {
            // Send to specific camera
            url = `/admin/cameras/${selectedCameraId}/message`;
            method = 'POST';
        } else {
            // Broadcast to all cameras
            url = '/admin/cameras/broadcast';
            method = 'POST';
        }

        const response = await fetch(url, {
            method: method,
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ message: message })
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();

        if (data.success) {
            alert(data.message || 'Message sent successfully');
            closeModal();
        } else {
            alert('Failed to send message: ' + (data.error || 'Unknown error'));
        }
    } catch (error) {
        console.error('Error sending message:', error);
        alert('Failed to send message: ' + error.message);
    }
};

/**
 * Show camera view modal with live stream
 */
let cameraStreamInterval = null;
let currentViewedCameraId = null;

window.showCameraView = async function(cameraId, cameraName) {
    currentViewedCameraId = cameraId;
    document.getElementById('cameraViewTitle').textContent = `Camera View - ${cameraName}`;
    document.getElementById('viewCameraName').textContent = cameraName;
    document.getElementById('cameraViewModal').classList.add('active');

    // Load initial camera info
    await updateCameraViewInfo(cameraId);

    // Start streaming
    startCameraStream(cameraId);
};

/**
 * Close camera view modal
 */
window.closeCameraViewModal = function() {
    document.getElementById('cameraViewModal').classList.remove('active');
    stopCameraStream();
    currentViewedCameraId = null;
};

/**
 * Start camera stream
 */
function startCameraStream(cameraId) {
    stopCameraStream(); // Stop any existing stream

    const streamImage = document.getElementById('cameraStreamImage');
    const statusElement = document.getElementById('cameraStreamStatus');
    const noStreamMessage = document.getElementById('noStreamMessage');

    let isUpdating = false;
    let consecutiveErrors = 0;

    // Function to fetch and update stream
    const updateStream = async () => {
        // Skip if already updating
        if (isUpdating) {
            console.log('Stream update already in progress, skipping...');
            return;
        }

        isUpdating = true;

        try {
            const startTime = performance.now();
            const response = await fetch(`/admin/cameras/${cameraId}/stream`, {
                method: 'GET',
                cache: 'no-cache'
            });

            if (!response.ok) {
                throw new Error(`Stream fetch failed: ${response.status}`);
            }

            const data = await response.json();
            const fetchTime = performance.now() - startTime;

            console.log(`Frame fetched in ${fetchTime.toFixed(0)}ms`);

            if (data.success && data.streaming_enabled) {
                if (data.frame) {
                    // Update image with base64 frame
                    streamImage.src = 'data:image/jpeg;base64,' + data.frame;
                    streamImage.style.display = 'block';
                    noStreamMessage.style.display = 'none';
                    statusElement.textContent = `Live - ${data.fps.toFixed(1)} FPS`;
                    statusElement.style.background = 'rgba(16, 185, 129, 0.8)';
                    consecutiveErrors = 0;
                } else {
                    statusElement.textContent = 'Waiting for Frame...';
                    statusElement.style.background = 'rgba(251, 146, 60, 0.8)';
                }
            } else {
                // Streaming disabled by user
                streamImage.style.display = 'none';
                noStreamMessage.style.display = 'block';
                statusElement.textContent = 'Streaming Disabled';
                statusElement.style.background = 'rgba(239, 68, 68, 0.8)';
            }
        } catch (error) {
            consecutiveErrors++;
            console.error('Error fetching camera stream:', error);
            statusElement.textContent = `Connection Error (${consecutiveErrors})`;
            statusElement.style.background = 'rgba(239, 68, 68, 0.8)';

            // If too many errors, slow down polling
            if (consecutiveErrors > 5) {
                console.warn('Too many errors, slowing down stream polling');
            }
        } finally {
            isUpdating = false;
        }
    };

    // Initial update
    updateStream();

    // Update stream every 100ms for very smooth playback (10 FPS max polling rate)
    // Client uploads at detection rate (~1.25 FPS = 800ms), we poll faster to minimize latency
    cameraStreamInterval = setInterval(updateStream, 100);
}

/**
 * Stop camera stream
 */
function stopCameraStream() {
    if (cameraStreamInterval) {
        clearInterval(cameraStreamInterval);
        cameraStreamInterval = null;
    }
}

/**
 * Update camera view info
 */
async function updateCameraViewInfo(cameraId) {
    try {
        const response = await fetch(`/admin/cameras/${cameraId}`);

        if (!response.ok) {
            throw new Error(`Failed to fetch camera info: ${response.status}`);
        }

        const data = await response.json();

        if (data.success) {
            const camera = data.camera;
            document.getElementById('viewCameraStatus').textContent = camera.status;
            document.getElementById('viewCameraFPS').textContent = camera.current_fps.toFixed(1);
            document.getElementById('viewStreamingStatus').textContent = camera.dashboard_streaming_enabled ? 'Enabled' : 'Disabled';
        }
    } catch (error) {
        console.error('Error fetching camera info:', error);
    }
}

/**
 * Toggle voice call with a camera
 */
window.toggleVoiceCall = async function(cameraId, cameraName) {
    const btn = document.getElementById(`voiceBtn-${cameraId}`);

    // Check if currently in a voice session
    if (voiceComm.isRecording) {
        // Stop current session
        const result = await voiceComm.stopVoiceSession();

        if (result.success) {
            btn.textContent = 'Voice Call';
            btn.style.background = 'linear-gradient(135deg, #06b6d4 0%, #3b82f6 100%)';
            currentVoiceSession = null;
            console.log('Voice call ended');
        } else {
            alert('Failed to stop voice call: ' + result.error);
        }
    } else {
        // Start new session
        const result = await voiceComm.startVoiceSession(cameraId, cameraName);

        if (result.success) {
            btn.textContent = 'End Call';
            btn.style.background = 'linear-gradient(135deg, #ef4444 0%, #dc2626 100%)';
            currentVoiceSession = { cameraId, cameraName };
            console.log('Voice call started with', cameraName);
        } else {
            if (result.error.includes('Permission denied') || result.error.includes('NotAllowedError')) {
                alert('Microphone permission denied. Please enable microphone access in your browser settings.');
            } else {
                alert('Failed to start voice call: ' + result.error);
            }
        }
    }
};

/**
 * Start broadcast voice to all cameras
 */
window.startBroadcastVoice = async function() {
    if (voiceComm.isRecording) {
        alert('Already in a voice session. Please end current session first.');
        return;
    }

    const confirmed = confirm('Start voice broadcast to all online cameras?');
    if (!confirmed) {
        return;
    }

    const result = await voiceComm.startVoiceSession(null, 'All Cameras');

    if (result.success) {
        // Update UI to show broadcast is active
        const broadcastBtn = document.getElementById('broadcastVoiceBtn');
        if (broadcastBtn) {
            broadcastBtn.textContent = 'Stop Broadcast';
            broadcastBtn.style.background = 'linear-gradient(135deg, #ef4444 0%, #dc2626 100%)';
        }
        currentVoiceSession = { cameraId: null, cameraName: 'All Cameras' };
        console.log('Voice broadcast started');
    } else {
        if (result.error.includes('Permission denied') || result.error.includes('NotAllowedError')) {
            alert('Microphone permission denied. Please enable microphone access in your browser settings.');
        } else {
            alert('Failed to start broadcast: ' + result.error);
        }
    }
};

/**
 * Stop broadcast voice
 */
window.stopBroadcastVoice = async function() {
    if (!voiceComm.isRecording || !voiceComm.isBroadcasting) {
        return;
    }

    const result = await voiceComm.stopVoiceSession();

    if (result.success) {
        // Update UI
        const broadcastBtn = document.getElementById('broadcastVoiceBtn');
        if (broadcastBtn) {
            broadcastBtn.textContent = 'Broadcast Voice';
            broadcastBtn.style.background = 'linear-gradient(135deg, #06b6d4 0%, #3b82f6 100%)';
        }
        currentVoiceSession = null;
        console.log('Voice broadcast stopped');
    } else {
        alert('Failed to stop broadcast: ' + result.error);
    }
};
