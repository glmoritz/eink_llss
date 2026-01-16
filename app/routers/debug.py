"""
Debug routes - Device emulator for testing
"""

import hashlib
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, Response
from sqlalchemy.orm import Session

from database import get_db
from db_models import Device, DeviceInstanceMap, Frame, Instance

router = APIRouter(prefix="/debug", tags=["Debug"])


@router.get("", response_class=HTMLResponse)
async def debug_emulator(request: Request) -> HTMLResponse:
    """
    Serve the device emulator debug page.

    Provides an interactive UI to emulate a physical e-Ink device
    with all buttons and screen display.
    """
    base_url = str(request.base_url).rstrip("/")

    html_content = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>LLSS Device Emulator</title>
    <style>
        * {{
            box-sizing: border-box;
        }}
        
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            min-height: 100vh;
            margin: 0;
            padding: 20px;
            color: #eee;
        }}
        
        .container {{
            max-width: 800px;
            margin: 0 auto;
        }}
        
        h1 {{
            text-align: center;
            color: #00d9ff;
            margin-bottom: 20px;
            font-size: 1.8rem;
        }}
        
        .device-selector {{
            background: rgba(255,255,255,0.1);
            padding: 20px;
            border-radius: 12px;
            margin-bottom: 20px;
        }}
        
        .device-selector label {{
            display: block;
            margin-bottom: 8px;
            color: #aaa;
            font-size: 0.9rem;
        }}
        
        .device-selector select {{
            width: 100%;
            padding: 12px;
            border: none;
            border-radius: 8px;
            background: #2a2a4a;
            color: #fff;
            font-size: 1rem;
            cursor: pointer;
        }}
        
        .device-selector select:focus {{
            outline: 2px solid #00d9ff;
        }}
        
        .refresh-btn {{
            margin-top: 10px;
            padding: 8px 16px;
            background: #00d9ff;
            color: #1a1a2e;
            border: none;
            border-radius: 6px;
            cursor: pointer;
            font-weight: bold;
        }}
        
        .refresh-btn:hover {{
            background: #00b8d4;
        }}
        
        .device-info {{
            background: rgba(255,255,255,0.05);
            padding: 15px;
            border-radius: 8px;
            margin-top: 15px;
            font-size: 0.85rem;
            color: #888;
        }}
        
        .device-info span {{
            color: #00d9ff;
        }}
        
        /* Device Emulator */
        .emulator {{
            background: #2d2d2d;
            border-radius: 20px;
            padding: 20px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.5), inset 0 1px 0 rgba(255,255,255,0.1);
            position: relative;
        }}
        
        .emulator-header {{
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            margin-bottom: 15px;
        }}
        
        /* Context buttons (top left) */
        .context-buttons {{
            display: flex;
            gap: 8px;
        }}
        
        .context-btn {{
            width: 40px;
            height: 40px;
            border-radius: 50%;
            border: none;
            background: linear-gradient(145deg, #3a3a3a, #252525);
            color: #888;
            font-size: 0.7rem;
            cursor: pointer;
            box-shadow: 2px 2px 5px rgba(0,0,0,0.3), -1px -1px 3px rgba(255,255,255,0.05);
            transition: all 0.1s;
            display: flex;
            align-items: center;
            justify-content: center;
        }}
        
        .context-btn:hover {{
            background: linear-gradient(145deg, #454545, #2a2a2a);
            color: #00d9ff;
        }}
        
        .context-btn:active {{
            box-shadow: inset 2px 2px 5px rgba(0,0,0,0.3);
            transform: scale(0.95);
        }}
        
        /* Navigation buttons (top right) */
        .nav-buttons {{
            display: flex;
            gap: 8px;
        }}
        
        .nav-btn {{
            width: 50px;
            height: 40px;
            border-radius: 8px;
            border: none;
            font-size: 0.75rem;
            font-weight: bold;
            cursor: pointer;
            box-shadow: 2px 2px 5px rgba(0,0,0,0.3), -1px -1px 3px rgba(255,255,255,0.05);
            transition: all 0.1s;
        }}
        
        .nav-btn.esc {{
            background: linear-gradient(145deg, #c0392b, #922b21);
            color: #fff;
        }}
        
        .nav-btn.enter {{
            background: linear-gradient(145deg, #27ae60, #1e8449);
            color: #fff;
        }}
        
        .nav-btn:hover {{
            filter: brightness(1.1);
        }}
        
        .nav-btn:active {{
            box-shadow: inset 2px 2px 5px rgba(0,0,0,0.3);
            transform: scale(0.95);
        }}
        
        /* Screen */
        .screen-container {{
            background: #1a1a1a;
            border-radius: 8px;
            padding: 10px;
            margin-bottom: 20px;
        }}
        
        .screen {{
            width: 100%;
            aspect-ratio: 4/3;
            background: #e8e4d9;
            border-radius: 4px;
            display: flex;
            align-items: center;
            justify-content: center;
            position: relative;
            overflow: hidden;
        }}
        
        .screen img {{
            max-width: 100%;
            max-height: 100%;
            object-fit: contain;
            image-rendering: pixelated;
        }}
        
        .screen .no-frame {{
            color: #666;
            font-size: 0.9rem;
            text-align: center;
        }}
        
        .screen .no-frame small {{
            display: block;
            margin-top: 5px;
            color: #999;
            font-size: 0.75rem;
        }}
        
        /* Bottom buttons */
        .bottom-buttons {{
            display: grid;
            grid-template-columns: repeat(8, 1fr);
            gap: 8px;
        }}
        
        .bottom-btn {{
            aspect-ratio: 1;
            border-radius: 8px;
            border: none;
            background: linear-gradient(145deg, #3a3a3a, #252525);
            color: #aaa;
            font-size: 0.8rem;
            font-weight: bold;
            cursor: pointer;
            box-shadow: 3px 3px 8px rgba(0,0,0,0.4), -2px -2px 6px rgba(255,255,255,0.05);
            transition: all 0.1s;
        }}
        
        .bottom-btn:hover {{
            background: linear-gradient(145deg, #454545, #2a2a2a);
            color: #00d9ff;
        }}
        
        .bottom-btn:active {{
            box-shadow: inset 3px 3px 8px rgba(0,0,0,0.4);
            transform: scale(0.95);
            background: linear-gradient(145deg, #252525, #3a3a3a);
        }}
        
        /* Status */
        .status {{
            margin-top: 20px;
            padding: 15px;
            background: rgba(0,0,0,0.3);
            border-radius: 8px;
            font-family: 'Courier New', monospace;
            font-size: 0.8rem;
            max-height: 200px;
            overflow-y: auto;
        }}
        
        .status-line {{
            margin: 4px 0;
            padding: 4px 8px;
            border-radius: 4px;
        }}
        
        .status-line.info {{
            color: #00d9ff;
        }}
        
        .status-line.success {{
            color: #2ecc71;
            background: rgba(46, 204, 113, 0.1);
        }}
        
        .status-line.error {{
            color: #e74c3c;
            background: rgba(231, 76, 60, 0.1);
        }}
        
        .status-line.event {{
            color: #f39c12;
        }}
        
        /* No device state */
        .no-device {{
            text-align: center;
            padding: 60px 20px;
            color: #666;
        }}
        
        .no-device h3 {{
            color: #888;
            margin-bottom: 10px;
        }}
        
        /* Register device button */
        .register-section {{
            margin-top: 15px;
            padding-top: 15px;
            border-top: 1px solid rgba(255,255,255,0.1);
        }}
        
        .register-btn {{
            width: 100%;
            padding: 12px;
            background: linear-gradient(145deg, #9b59b6, #8e44ad);
            color: #fff;
            border: none;
            border-radius: 8px;
            font-size: 1rem;
            cursor: pointer;
            font-weight: bold;
        }}
        
        .register-btn:hover {{
            background: linear-gradient(145deg, #a569bd, #9b59b6);
        }}
        
        .register-form {{
            display: none;
            margin-top: 15px;
            padding: 15px;
            background: rgba(0,0,0,0.2);
            border-radius: 8px;
        }}
        
        .register-form.active {{
            display: block;
        }}
        
        .register-form input {{
            width: 100%;
            padding: 10px;
            margin-bottom: 10px;
            border: none;
            border-radius: 6px;
            background: #2a2a4a;
            color: #fff;
        }}
        
        .register-form .form-row {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 10px;
        }}
        
        .register-form button {{
            width: 100%;
            padding: 10px;
            background: #27ae60;
            color: #fff;
            border: none;
            border-radius: 6px;
            cursor: pointer;
            font-weight: bold;
        }}
        
        .hidden {{
            display: none;
        }}
        
        /* Test panel */
        .test-panel {{
            background: rgba(255,255,255,0.05);
            padding: 15px;
            border-radius: 12px;
            margin-top: 15px;
        }}
        
        .test-panel h3 {{
            margin: 0 0 15px 0;
            color: #f39c12;
            font-size: 1rem;
        }}
        
        .test-section {{
            display: flex;
            gap: 10px;
            align-items: center;
            flex-wrap: wrap;
        }}
        
        .test-section label {{
            color: #aaa;
            font-size: 0.85rem;
        }}
        
        .test-section input[type="file"] {{
            flex: 1;
            min-width: 200px;
            padding: 8px;
            background: #2a2a4a;
            border: 1px solid #444;
            border-radius: 6px;
            color: #fff;
        }}
        
        .test-section button {{
            padding: 8px 16px;
            background: #f39c12;
            color: #1a1a2e;
            border: none;
            border-radius: 6px;
            cursor: pointer;
            font-weight: bold;
        }}
        
        .test-section button:hover {{
            background: #e67e22;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>🖥️ LLSS Device Emulator</h1>
        
        <div class="device-selector">
            <label for="device-select">Select Device:</label>
            <select id="device-select">
                <option value="">-- Select a device --</option>
            </select>
            <button class="refresh-btn" onclick="loadDevices()">🔄 Refresh List</button>
            
            <div id="device-info" class="device-info hidden">
                <div><strong>Device ID:</strong> <span id="info-device-id">-</span></div>
                <div><strong>Hardware ID:</strong> <span id="info-hardware-id">-</span></div>
                <div><strong>Display:</strong> <span id="info-display">-</span></div>
                <div><strong>Firmware:</strong> <span id="info-firmware">-</span></div>
            </div>
            
            <div class="register-section">
                <button class="register-btn" onclick="toggleRegisterForm()">+ Register New Device</button>
                <div id="register-form" class="register-form">
                    <input type="text" id="reg-hardware-id" placeholder="Hardware ID (e.g., ESP32-ABC123)">
                    <input type="text" id="reg-firmware" placeholder="Firmware Version (e.g., 1.0.0)">
                    <div class="form-row">
                        <input type="number" id="reg-width" placeholder="Width (e.g., 800)" value="800">
                        <input type="number" id="reg-height" placeholder="Height (e.g., 600)" value="600">
                    </div>
                    <div class="form-row">
                        <input type="number" id="reg-bit-depth" placeholder="Bit Depth" value="4">
                        <select id="reg-partial">
                            <option value="false">No Partial Refresh</option>
                            <option value="true">Partial Refresh</option>
                        </select>
                    </div>
                    <button onclick="registerDevice()">Register Device</button>
                </div>
            </div>
        </div>
        
        <div id="emulator-container">
            <div class="no-device">
                <h3>No Device Selected</h3>
                <p>Select a device from the dropdown above or register a new one.</p>
            </div>
        </div>
        
        <div class="status" id="status">
            <div class="status-line info">[System] Device emulator ready</div>
        </div>
    </div>
    
    <script>
        const BASE_URL = '{base_url}';
        let currentDevice = null;
        let currentToken = null;  // JWT access token
        let currentRefreshToken = null;  // JWT refresh token
        let deviceSecret = null;  // Stored device secret for authentication
        let pollInterval = null;
        
        // Local storage keys
        const STORAGE_PREFIX = 'llss_emulator_';
        
        function getStoredCredentials(deviceId) {{
            try {{
                const data = localStorage.getItem(STORAGE_PREFIX + deviceId);
                return data ? JSON.parse(data) : null;
            }} catch (e) {{
                return null;
            }}
        }}
        
        function storeCredentials(deviceId, secret, refreshToken) {{
            try {{
                localStorage.setItem(STORAGE_PREFIX + deviceId, JSON.stringify({{
                    device_secret: secret,
                    refresh_token: refreshToken
                }}));
            }} catch (e) {{
                console.error('Failed to store credentials:', e);
            }}
        }}
        
        // Button mappings
        const BUTTONS = {{
            BTN_1: 'BTN_1', BTN_2: 'BTN_2', BTN_3: 'BTN_3', BTN_4: 'BTN_4',
            BTN_5: 'BTN_5', BTN_6: 'BTN_6', BTN_7: 'BTN_7', BTN_8: 'BTN_8',
            ENTER: 'ENTER', ESC: 'ESC',
            HL_LEFT: 'HL_LEFT', HL_RIGHT: 'HL_RIGHT'
        }};
        
        async function loadDevices() {{
            try {{
                const resp = await fetch(`${{BASE_URL}}/debug/devices`);
                const devices = await resp.json();
                
                const select = document.getElementById('device-select');
                const currentValue = select.value;
                
                select.innerHTML = '<option value="">-- Select a device --</option>';
                
                devices.forEach(device => {{
                    const option = document.createElement('option');
                    option.value = device.device_id;
                    const statusBadge = device.auth_status === 'authorized' ? '✅' : 
                                       device.auth_status === 'pending' ? '⏳' : '❌';
                    option.textContent = `${{statusBadge}} ${{device.hardware_id}} (${{device.device_id}})`;
                    option.dataset.device = JSON.stringify(device);
                    select.appendChild(option);
                }});
                
                if (currentValue && devices.some(d => d.device_id === currentValue)) {{
                    select.value = currentValue;
                }}
                
                log('info', `Loaded ${{devices.length}} device(s)`);
            }} catch (err) {{
                log('error', `Failed to load devices: ${{err.message}}`);
            }}
        }}
        
        function selectDevice() {{
            const select = document.getElementById('device-select');
            const selectedOption = select.selectedOptions[0];
            
            if (!select.value) {{
                showNoDevice();
                return;
            }}
            
            currentDevice = JSON.parse(selectedOption.dataset.device);
            
            // Update device info
            document.getElementById('device-info').classList.remove('hidden');
            document.getElementById('info-device-id').textContent = currentDevice.device_id;
            document.getElementById('info-hardware-id').textContent = currentDevice.hardware_id;
            document.getElementById('info-display').textContent = 
                `${{currentDevice.display.width}}x${{currentDevice.display.height}} @ ${{currentDevice.display.bit_depth}}bpp`;
            document.getElementById('info-firmware').textContent = currentDevice.firmware_version;
            
            // Check auth status
            if (currentDevice.auth_status === 'pending') {{
                log('warning', `Device is pending authorization. Please authorize via admin panel.`);
                showEmulator();
                return;
            }}
            
            if (currentDevice.auth_status !== 'authorized') {{
                log('error', `Device status: ${{currentDevice.auth_status}}. Cannot authenticate.`);
                showEmulator();
                return;
            }}
            
            // Try to get tokens
            authenticateDevice();
        }}
        
        async function authenticateDevice() {{
            if (!currentDevice) return;
            
            // Check for stored credentials
            const stored = getStoredCredentials(currentDevice.device_id);
            
            if (stored && stored.refresh_token) {{
                // Try to refresh the access token
                log('info', 'Found stored credentials, refreshing access token...');
                const success = await refreshAccessToken(stored.refresh_token);
                if (success) {{
                    currentRefreshToken = stored.refresh_token;
                    showEmulator();
                    log('success', `Authenticated device: ${{currentDevice.hardware_id}}`);
                    return;
                }}
            }}
            
            // Need to get new refresh token - requires device_secret
            if (stored && stored.device_secret) {{
                deviceSecret = stored.device_secret;
            }} else {{
                // For the emulator, we'll use debug endpoint to get the device secret
                log('warning', 'No stored credentials. Getting device secret from debug endpoint...');
                const secretResp = await fetch(`${{BASE_URL}}/debug/devices/${{currentDevice.device_id}}/secret`);
                if (secretResp.ok) {{
                    const secretData = await secretResp.json();
                    deviceSecret = secretData.device_secret;
                }} else {{
                    log('error', 'Could not get device secret. Device may need to be re-registered.');
                    showEmulator();
                    return;
                }}
            }}
            
            // Get refresh token using device secret
            const authSuccess = await getRefreshToken();
            if (authSuccess) {{
                showEmulator();
                log('success', `Authenticated device: ${{currentDevice.hardware_id}}`);
            }} else {{
                showEmulator();
            }}
        }}
        
        async function getRefreshToken() {{
            if (!currentDevice || !deviceSecret) {{
                log('error', 'Missing device or secret');
                return false;
            }}
            
            try {{
                const authReq = {{
                    hardware_id: currentDevice.hardware_id,
                    device_secret: deviceSecret,
                    firmware_version: currentDevice.firmware_version,
                    display: currentDevice.display
                }};
                
                const resp = await fetch(`${{BASE_URL}}/auth/devices/token`, {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json' }},
                    body: JSON.stringify(authReq)
                }});
                
                const data = await resp.json();
                
                if (data.auth_status === 'pending') {{
                    log('warning', 'Device pending authorization');
                    return false;
                }}
                
                if (!resp.ok) {{
                    log('error', `Auth failed: ${{data.detail || resp.status}}`);
                    return false;
                }}
                
                if (data.refresh_token) {{
                    currentRefreshToken = data.refresh_token;
                    storeCredentials(currentDevice.device_id, deviceSecret, data.refresh_token);
                    
                    // Now get access token
                    return await refreshAccessToken(data.refresh_token);
                }}
                
                return false;
            }} catch (err) {{
                log('error', `Auth error: ${{err.message}}`);
                return false;
            }}
        }}
        
        async function refreshAccessToken(refreshToken) {{
            try {{
                const resp = await fetch(`${{BASE_URL}}/auth/devices/refresh`, {{
                    method: 'POST',
                    headers: {{
                        'Authorization': `Bearer ${{refreshToken}}`
                    }}
                }});
                
                if (resp.status === 401) {{
                    log('warning', 'Refresh token expired. Need to re-authenticate.');
                    return false;
                }}
                
                if (!resp.ok) {{
                    log('error', `Token refresh failed: ${{resp.status}}`);
                    return false;
                }}
                
                const data = await resp.json();
                currentToken = data.access_token;
                log('info', `Access token obtained (expires in ${{Math.round(data.expires_in/3600)}}h)`);
                return true;
            }} catch (err) {{
                log('error', `Token refresh error: ${{err.message}}`);
                return false;
            }}
        }}
        
        async function apiCallWithRetry(url, options = {{}}) {{
            // Add auth header
            options.headers = options.headers || {{}};
            if (currentToken) {{
                options.headers['Authorization'] = `Bearer ${{currentToken}}`;
            }}
            
            let resp = await fetch(url, options);
            
            // If 401, try to refresh token and retry
            if (resp.status === 401 && currentRefreshToken) {{
                log('info', 'Token expired, refreshing...');
                const refreshed = await refreshAccessToken(currentRefreshToken);
                if (refreshed) {{
                    options.headers['Authorization'] = `Bearer ${{currentToken}}`;
                    resp = await fetch(url, options);
                }}
            }}
            
            return resp;
        }}
        
        function showNoDevice() {{
            currentDevice = null;
            currentToken = null;
            currentRefreshToken = null;
            deviceSecret = null;
            stopPolling();
            
            document.getElementById('device-info').classList.add('hidden');
            document.getElementById('emulator-container').innerHTML = `
                <div class="no-device">
                    <h3>No Device Selected</h3>
                    <p>Select a device from the dropdown above or register a new one.</p>
                </div>
            `;
        }}
        
        function showEmulator() {{
            document.getElementById('emulator-container').innerHTML = `
                <div class="emulator">
                    <div class="emulator-header">
                        <div class="context-buttons">
                            <button class="context-btn" onclick="sendButton('HL_LEFT')" title="Context Left">◀</button>
                            <button class="context-btn" onclick="sendButton('HL_RIGHT')" title="Context Right">▶</button>
                        </div>
                        <div class="nav-buttons">
                            <button class="nav-btn esc" onclick="sendButton('ESC')">ESC</button>
                            <button class="nav-btn enter" onclick="sendButton('ENTER')">ENT</button>
                        </div>
                    </div>
                    
                    <div class="screen-container">
                        <div class="screen" id="screen">
                            <div class="no-frame">
                                No frame available
                                <small>Waiting for HLSS to submit a frame...</small>
                            </div>
                        </div>
                    </div>
                    
                    <div class="bottom-buttons">
                        <button class="bottom-btn" onclick="sendButton('BTN_1')">1</button>
                        <button class="bottom-btn" onclick="sendButton('BTN_2')">2</button>
                        <button class="bottom-btn" onclick="sendButton('BTN_3')">3</button>
                        <button class="bottom-btn" onclick="sendButton('BTN_4')">4</button>
                        <button class="bottom-btn" onclick="sendButton('BTN_5')">5</button>
                        <button class="bottom-btn" onclick="sendButton('BTN_6')">6</button>
                        <button class="bottom-btn" onclick="sendButton('BTN_7')">7</button>
                        <button class="bottom-btn" onclick="sendButton('BTN_8')">8</button>
                    </div>
                </div>
                
                <div class="test-panel">
                    <h3>🧪 Test Tools</h3>
                    <div class="test-section">
                        <label>Upload Test Frame (PNG):</label>
                        <input type="file" id="test-frame-file" accept="image/png,image/jpeg,image/*">
                        <button onclick="uploadTestFrame()">Upload Frame</button>
                    </div>
                </div>
                
                <div class="test-panel">
                    <h3>�️ Frame Detector</h3>
                    <div class="test-section">
                        <button onclick="manualPollFrame()" style="padding:8px 16px;background:#27ae60;color:#fff;border:none;border-radius:6px;cursor:pointer;font-weight:bold;">🔄 Check for Frame</button>
                        <label style="margin-left:15px;">Auto-poll:</label>
                        <input type="number" id="frame-poll-interval" value="2" min="1" max="60" style="width:60px;padding:8px;background:#2a2a4a;border:1px solid #444;border-radius:6px;color:#fff;text-align:center;">
                        <label>sec</label>
                        <button id="frame-poll-toggle" onclick="toggleFramePolling()" style="padding:8px 16px;background:#9b59b6;color:#fff;border:none;border-radius:6px;cursor:pointer;font-weight:bold;">Start Auto</button>
                    </div>
                </div>
                
                <div class="test-panel">
                    <h3>�🔄 HLSS Instance Status</h3>
                    <div class="test-section">
                        <label>Instance:</label>
                        <select id="instance-select" style="flex:1;min-width:200px;padding:8px;background:#2a2a4a;border:1px solid #444;border-radius:6px;color:#fff;">
                            <option value="">-- Select instance --</option>
                        </select>
                        <button onclick="loadInstances()" style="padding:8px 12px;background:#666;color:#fff;border:none;border-radius:6px;cursor:pointer;">🔄</button>
                    </div>
                    <div class="test-section" style="margin-top:10px;">
                        <button onclick="refreshInstanceStatus()" style="padding:8px 16px;background:#27ae60;color:#fff;border:none;border-radius:6px;cursor:pointer;font-weight:bold;">Force Refresh Status</button>
                        <label style="margin-left:15px;">Auto-refresh:</label>
                        <input type="number" id="auto-refresh-interval" value="5" min="1" max="300" style="width:60px;padding:8px;background:#2a2a4a;border:1px solid #444;border-radius:6px;color:#fff;text-align:center;">
                        <label>sec</label>
                        <button id="auto-refresh-toggle" onclick="toggleAutoRefresh()" style="padding:8px 16px;background:#9b59b6;color:#fff;border:none;border-radius:6px;cursor:pointer;font-weight:bold;">Start Auto</button>
                    </div>
                    <div id="instance-status" class="device-info" style="margin-top:10px;display:none;">
                        <div><strong>Instance:</strong> <span id="status-instance-name">-</span></div>
                        <div><strong>Type:</strong> <span id="status-instance-type">-</span></div>
                        <div><strong>Initialized:</strong> <span id="status-initialized">-</span></div>
                        <div><strong>Ready:</strong> <span id="status-ready">-</span></div>
                        <div><strong>Needs Config:</strong> <span id="status-needs-config">-</span></div>
                        <div><strong>Config URL:</strong> <span id="status-config-url">-</span></div>
                        <div><strong>Last Refresh:</strong> <span id="status-last-refresh">-</span></div>
                    </div>
                    <div class="test-section" style="margin-top:15px;padding-top:15px;border-top:1px solid #444;">
                        <button onclick="checkFrameSync()" style="padding:8px 16px;background:#f39c12;color:#1a1a2e;border:none;border-radius:6px;cursor:pointer;font-weight:bold;">🔍 Check Frame Sync</button>
                        <button onclick="syncFrame()" style="padding:8px 16px;background:#e74c3c;color:#fff;border:none;border-radius:6px;cursor:pointer;font-weight:bold;">📥 Sync Frame from HLSS</button>
                    </div>
                    <div id="frame-sync-status" class="device-info" style="margin-top:10px;display:none;">
                        <div><strong>HLSS has frame:</strong> <span id="sync-hlss-has-frame">-</span></div>
                        <div><strong>HLSS frame hash:</strong> <span id="sync-hlss-hash">-</span></div>
                        <div><strong>LLSS has frame:</strong> <span id="sync-llss-has-frame">-</span></div>
                        <div><strong>LLSS frame hash:</strong> <span id="sync-llss-hash">-</span></div>
                        <div><strong>In Sync:</strong> <span id="sync-in-sync">-</span></div>
                        <div><strong>Action:</strong> <span id="sync-action">-</span></div>
                    </div>
                </div>
            `;
            
            // Fetch current frame and load instances
            fetchFrame();
            loadInstances();
        }}
        
        async function uploadTestFrame() {{
            if (!currentDevice) {{
                log('error', 'No device selected');
                return;
            }}
            
            const fileInput = document.getElementById('test-frame-file');
            if (!fileInput.files || !fileInput.files[0]) {{
                log('error', 'Please select a file first');
                return;
            }}
            
            const formData = new FormData();
            formData.append('file', fileInput.files[0]);
            
            try {{
                const resp = await fetch(
                    `${{BASE_URL}}/debug/devices/${{currentDevice.device_id}}/test-frame`,
                    {{
                        method: 'POST',
                        body: formData
                    }}
                );
                
                if (resp.ok) {{
                    const result = await resp.json();
                    log('success', `Test frame uploaded: ${{result.frame_id}}`);
                    fetchFrame();
                }} else {{
                    log('error', `Failed to upload frame: ${{resp.status}}`);
                }}
            }} catch (err) {{
                log('error', `Upload error: ${{err.message}}`);
            }}
        }}
        
        async function sendButton(button) {{
            if (!currentDevice || !currentToken) {{
                log('error', 'No device selected or not authenticated');
                return;
            }}
            
            const event = {{
                button: button,
                event_type: 'PRESS',
                timestamp: new Date().toISOString()
            }};
            
            log('event', `Button pressed: ${{button}}`);
            
            try {{
                const resp = await apiCallWithRetry(
                    `${{BASE_URL}}/devices/${{currentDevice.device_id}}/inputs`,
                    {{
                        method: 'POST',
                        headers: {{
                            'Content-Type': 'application/json'
                        }},
                        body: JSON.stringify(event)
                    }}
                );
                
                if (resp.ok) {{
                    log('success', `Input event sent: ${{button}}`);
                    // Poll for new frame after button press
                    setTimeout(pollState, 100);
                }} else {{
                    log('error', `Failed to send input: ${{resp.status}}`);
                }}
            }} catch (err) {{
                log('error', `Error sending input: ${{err.message}}`);
            }}
        }}
        
        async function pollState() {{
            if (!currentDevice || !currentToken) return;
            
            try {{
                const resp = await apiCallWithRetry(
                    `${{BASE_URL}}/devices/${{currentDevice.device_id}}/state`
                );
                
                if (resp.ok) {{
                    const state = await resp.json();
                    
                    if (state.action === 'FETCH_FRAME' && state.frame_id) {{
                        log('info', `New frame available: ${{state.frame_id}}`);
                        await fetchFrameById(state.frame_id);
                    }}
                }}
            }} catch (err) {{
                // Silent fail for polling
            }}
        }}
        
        async function fetchFrame() {{
            if (!currentDevice) return;
            
            try {{
                // Try to get current frame from debug endpoint (no auth needed)
                const resp = await fetch(
                    `${{BASE_URL}}/debug/devices/${{currentDevice.device_id}}/frame`
                );
                
                if (resp.ok) {{
                    const blob = await resp.blob();
                    if (blob.size > 0) {{
                        const url = URL.createObjectURL(blob);
                        document.getElementById('screen').innerHTML = `<img src="${{url}}" alt="Device Frame">`;
                        log('success', 'Frame loaded');
                    }}
                }}
            }} catch (err) {{
                // Frame not available yet
            }}
        }}
        
        async function fetchFrameById(frameId) {{
            if (!currentDevice || !currentToken) return;
            
            try {{
                const resp = await apiCallWithRetry(
                    `${{BASE_URL}}/devices/${{currentDevice.device_id}}/frames/${{frameId}}`
                );
                
                if (resp.ok) {{
                    const blob = await resp.blob();
                    if (blob.size > 0) {{
                        const url = URL.createObjectURL(blob);
                        document.getElementById('screen').innerHTML = `<img src="${{url}}" alt="Device Frame">`;
                        log('success', `Frame ${{frameId}} displayed`);
                    }}
                }}
            }} catch (err) {{
                log('error', `Failed to fetch frame: ${{err.message}}`);
            }}
        }}
        
        // Frame Detector Functions
        async function manualPollFrame() {{
            if (!currentDevice) {{
                log('error', 'No device selected');
                return;
            }}
            log('info', 'Checking for new frame...');
            if (currentToken) {{
                await pollState();
            }}
            await fetchFrame();
        }}
        
        function toggleFramePolling() {{
            const btn = document.getElementById('frame-poll-toggle');
            if (!btn) return;
            
            if (pollInterval) {{
                stopPolling();
                btn.textContent = 'Start Auto';
                btn.style.background = '#9b59b6';
                log('info', 'Frame auto-poll stopped');
            }} else {{
                const intervalInput = document.getElementById('frame-poll-interval');
                const seconds = parseInt(intervalInput.value) || 2;
                
                if (seconds < 1 || seconds > 60) {{
                    log('error', 'Interval must be between 1 and 60 seconds');
                    return;
                }}
                
                startPolling(seconds);
                btn.textContent = 'Stop Auto';
                btn.style.background = '#e74c3c';
                log('info', `Frame auto-poll started: every ${{seconds}} seconds`);
            }}
        }}
        
        function startPolling(seconds = 2) {{
            stopPolling();
            pollInterval = setInterval(pollState, seconds * 1000);
            pollState();
        }}
        
        function stopPolling() {{
            if (pollInterval) {{
                clearInterval(pollInterval);
                pollInterval = null;
            }}
        }}
        
        function toggleRegisterForm() {{
            const form = document.getElementById('register-form');
            form.classList.toggle('active');
        }}
        
        async function registerDevice() {{
            const hardwareId = document.getElementById('reg-hardware-id').value;
            const firmware = document.getElementById('reg-firmware').value;
            const width = parseInt(document.getElementById('reg-width').value);
            const height = parseInt(document.getElementById('reg-height').value);
            const bitDepth = parseInt(document.getElementById('reg-bit-depth').value);
            const partial = document.getElementById('reg-partial').value === 'true';
            
            if (!hardwareId || !firmware) {{
                log('error', 'Hardware ID and Firmware are required');
                return;
            }}
            
            const registration = {{
                hardware_id: hardwareId,
                firmware_version: firmware,
                display: {{
                    width: width || 800,
                    height: height || 600,
                    bit_depth: bitDepth || 4,
                    partial_refresh: partial
                }}
            }};
            
            try {{
                // Use new auth endpoint for registration
                const resp = await fetch(`${{BASE_URL}}/auth/devices/register`, {{
                    method: 'POST',
                    headers: {{
                        'Content-Type': 'application/json'
                    }},
                    body: JSON.stringify(registration)
                }});
                
                if (resp.ok) {{
                    const result = await resp.json();
                    log('success', `Device registered: ${{result.device_id}}`);
                    log('info', `Status: ${{result.auth_status}} - ${{result.message}}`);
                    
                    // Store the device secret for later authentication
                    storeCredentials(result.device_id, result.device_secret, null);
                    
                    // Clear form and close
                    document.getElementById('reg-hardware-id').value = '';
                    document.getElementById('reg-firmware').value = '';
                    document.getElementById('register-form').classList.remove('active');
                    
                    // Reload devices and select the new one
                    await loadDevices();
                    document.getElementById('device-select').value = result.device_id;
                    selectDevice();
                }} else {{
                    const error = await resp.json();
                    log('error', `Registration failed: ${{error.detail || resp.status}}`);
                }}
            }} catch (err) {{
                log('error', `Registration error: ${{err.message}}`);
            }}
        }}
        
        function log(type, message) {{
            const status = document.getElementById('status');
            const time = new Date().toLocaleTimeString();
            const line = document.createElement('div');
            line.className = `status-line ${{type}}`;
            line.textContent = `[${{time}}] ${{message}}`;
            status.appendChild(line);
            status.scrollTop = status.scrollHeight;
            
            // Keep only last 50 messages
            while (status.children.length > 50) {{
                status.removeChild(status.firstChild);
            }}
        }}
        
        // HLSS Instance Status Functions
        let instancesList = [];
        let autoRefreshInterval = null;
        
        async function loadInstances() {{
            try {{
                const resp = await fetch(`${{BASE_URL}}/admin/instances`);
                if (!resp.ok) throw new Error(`HTTP ${{resp.status}}`);
                instancesList = await resp.json();
                
                const select = document.getElementById('instance-select');
                if (!select) return;
                
                const currentValue = select.value;
                select.innerHTML = '<option value="">-- Select instance --</option>';
                
                instancesList.forEach(inst => {{
                    const option = document.createElement('option');
                    option.value = inst.instance_id;
                    option.textContent = `${{inst.name}} (${{inst.type}})`;
                    select.appendChild(option);
                }});
                
                if (currentValue && instancesList.some(i => i.instance_id === currentValue)) {{
                    select.value = currentValue;
                }}
                
                log('info', `Loaded ${{instancesList.length}} instance(s)`);
            }} catch (err) {{
                log('error', `Failed to load instances: ${{err.message}}`);
            }}
        }}
        
        async function refreshInstanceStatus() {{
            const select = document.getElementById('instance-select');
            if (!select || !select.value) {{
                log('error', 'Please select an instance first');
                return;
            }}
            
            const instanceId = select.value;
            log('info', `Refreshing status for instance: ${{instanceId}}`);
            
            try {{
                const resp = await fetch(`${{BASE_URL}}/admin/instances/${{instanceId}}/refresh-status`, {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json' }}
                }});
                
                if (!resp.ok) {{
                    const error = await resp.json().catch(() => ({{ detail: `HTTP ${{resp.status}}` }}));
                    throw new Error(error.detail || `HTTP ${{resp.status}}`);
                }}
                
                const instance = await resp.json();
                updateInstanceStatusDisplay(instance);
                log('success', `Status refreshed: ready=${{instance.hlss_ready}}, needs_config=${{instance.needs_configuration}}`);
            }} catch (err) {{
                log('error', `Failed to refresh status: ${{err.message}}`);
            }}
        }}
        
        function updateInstanceStatusDisplay(instance) {{
            const statusDiv = document.getElementById('instance-status');
            if (!statusDiv) return;
            
            statusDiv.style.display = 'block';
            document.getElementById('status-instance-name').textContent = instance.name;
            document.getElementById('status-instance-type').textContent = instance.type || instance.hlss_type_id || '-';
            document.getElementById('status-initialized').textContent = instance.hlss_initialized ? '✅ Yes' : '❌ No';
            document.getElementById('status-ready').textContent = instance.hlss_ready ? '✅ Yes' : '❌ No';
            document.getElementById('status-needs-config').textContent = instance.needs_configuration ? '⚠️ Yes' : '✅ No';
            document.getElementById('status-config-url').innerHTML = instance.configuration_url 
                ? `<a href="${{instance.configuration_url}}" target="_blank" style="color:#00d9ff;">${{instance.configuration_url}}</a>` 
                : '-';
            document.getElementById('status-last-refresh').textContent = new Date().toLocaleTimeString();
        }}
        
        function toggleAutoRefresh() {{
            const btn = document.getElementById('auto-refresh-toggle');
            if (!btn) return;
            
            if (autoRefreshInterval) {{
                clearInterval(autoRefreshInterval);
                autoRefreshInterval = null;
                btn.textContent = 'Start Auto';
                btn.style.background = '#9b59b6';
                log('info', 'Auto-refresh stopped');
            }} else {{
                const intervalInput = document.getElementById('auto-refresh-interval');
                const seconds = parseInt(intervalInput.value) || 5;
                
                if (seconds < 1 || seconds > 300) {{
                    log('error', 'Interval must be between 1 and 300 seconds');
                    return;
                }}
                
                // Do an immediate refresh
                refreshInstanceStatus();
                
                autoRefreshInterval = setInterval(refreshInstanceStatus, seconds * 1000);
                btn.textContent = 'Stop Auto';
                btn.style.background = '#e74c3c';
                log('info', `Auto-refresh started: every ${{seconds}} seconds`);
            }}
        }}
        
        // Frame Sync Functions
        async function checkFrameSync() {{
            const select = document.getElementById('instance-select');
            if (!select || !select.value) {{
                log('error', 'Please select an instance first');
                return;
            }}
            
            const instanceId = select.value;
            log('info', `Checking frame sync for instance: ${{instanceId}}`);
            
            try {{
                const resp = await fetch(`${{BASE_URL}}/admin/instances/${{instanceId}}/frame-status`);
                
                if (!resp.ok) {{
                    const error = await resp.json().catch(() => ({{ detail: `HTTP ${{resp.status}}` }}));
                    throw new Error(error.detail || `HTTP ${{resp.status}}`);
                }}
                
                const result = await resp.json();
                updateFrameSyncDisplay(result);
                
                if (result.error) {{
                    log('error', `Frame sync check: ${{result.error}}`);
                }} else if (result.in_sync) {{
                    log('success', 'Frames are in sync');
                }} else {{
                    log('event', 'Frames are OUT OF SYNC - click "Sync Frame from HLSS" to fix');
                }}
            }} catch (err) {{
                log('error', `Failed to check frame sync: ${{err.message}}`);
            }}
        }}
        
        async function syncFrame() {{
            const select = document.getElementById('instance-select');
            if (!select || !select.value) {{
                log('error', 'Please select an instance first');
                return;
            }}
            
            const instanceId = select.value;
            log('info', `Requesting frame sync for instance: ${{instanceId}}`);
            
            try {{
                const resp = await fetch(`${{BASE_URL}}/admin/instances/${{instanceId}}/sync-frame`, {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json' }}
                }});
                
                if (!resp.ok) {{
                    const error = await resp.json().catch(() => ({{ detail: `HTTP ${{resp.status}}` }}));
                    throw new Error(error.detail || `HTTP ${{resp.status}}`);
                }}
                
                const result = await resp.json();
                updateFrameSyncDisplay(result);
                
                if (result.error) {{
                    log('error', `Frame sync failed: ${{result.error}}`);
                }} else if (result.action_taken) {{
                    log('success', `Frame sync: ${{result.action_taken}}`);
                }}
            }} catch (err) {{
                log('error', `Failed to sync frame: ${{err.message}}`);
            }}
        }}
        
        function updateFrameSyncDisplay(result) {{
            const statusDiv = document.getElementById('frame-sync-status');
            if (!statusDiv) return;
            
            statusDiv.style.display = 'block';
            document.getElementById('sync-hlss-has-frame').textContent = result.hlss_has_frame ? '✅ Yes' : '❌ No';
            document.getElementById('sync-hlss-hash').textContent = result.hlss_frame_hash || '-';
            document.getElementById('sync-llss-has-frame').textContent = result.llss_has_frame ? '✅ Yes' : '❌ No';
            document.getElementById('sync-llss-hash').textContent = result.llss_frame_hash || '-';
            document.getElementById('sync-in-sync').textContent = result.in_sync ? '✅ Yes' : '❌ No';
            document.getElementById('sync-action').textContent = result.action_taken || result.error || '-';
        }}
        
        // Event listeners
        document.getElementById('device-select').addEventListener('change', selectDevice);
        
        // Initial load
        loadDevices();
    </script>
</body>
</html>
    """
    return HTMLResponse(content=html_content)


@router.get("/devices")
async def list_devices(db: Session = Depends(get_db)) -> list:
    """
    List all registered devices for the debug emulator.
    """
    devices = db.query(Device).all()
    return [device.to_dict() for device in devices]


@router.get("/devices/{device_id}/secret")
async def get_device_secret(
    device_id: str,
    db: Session = Depends(get_db),
):
    """
    Get device secret for the emulator (DEBUG ONLY).

    This endpoint should be disabled in production!
    It allows the emulator to authenticate as a device.
    """
    device = db.query(Device).filter(Device.device_id == device_id).first()
    if not device:
        return {"error": "Device not found"}

    return {
        "device_id": device.device_id,
        "device_secret": device.device_secret,
        "auth_status": device.auth_status,
    }


@router.get("/devices/{device_id}/frame")
async def get_device_current_frame(
    device_id: str,
    db: Session = Depends(get_db),
):
    """
    Get the current frame for a device (for the emulator).
    """
    device = db.query(Device).filter(Device.device_id == device_id).first()
    if not device:
        return Response(content=b"", media_type="application/octet-stream")

    current_frame_id = device.current_frame_id
    if not current_frame_id:
        return Response(content=b"", media_type="application/octet-stream")

    frame = db.query(Frame).filter(Frame.frame_id == current_frame_id).first()
    if not frame or not frame.data:
        return Response(content=b"", media_type="application/octet-stream")

    return Response(content=frame.data, media_type="image/png")


@router.post("/devices/{device_id}/test-frame")
async def upload_test_frame(
    device_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """
    Upload a test frame directly to a device (for testing).
    """
    device = db.query(Device).filter(Device.device_id == device_id).first()
    if not device:
        return {"error": "Device not found"}

    content = await file.read()

    # Generate frame ID
    frame_id = f"frame_{uuid.uuid4().hex[:12]}"
    frame_hash = hashlib.sha256(content).hexdigest()[:16]

    # Store the frame in database
    frame = Frame(
        frame_id=frame_id,
        data=content,
        hash=frame_hash,
    )
    db.add(frame)

    # Update device
    device.current_frame_id = frame_id
    db.commit()

    return {
        "frame_id": frame_id,
        "size": len(content),
        "message": "Test frame uploaded successfully",
    }


@router.post("/devices/{device_id}/link-instance")
async def link_device_to_instance(
    device_id: str,
    instance_id: str = Form(...),
    db: Session = Depends(get_db),
):
    """
    Link a device to an instance (for testing).
    """
    device = db.query(Device).filter(Device.device_id == device_id).first()
    if not device:
        return {"error": "Device not found"}

    # Update device's active instance
    device.active_instance_id = instance_id

    # Also add to mapping table
    existing_map = (
        db.query(DeviceInstanceMap)
        .filter(
            DeviceInstanceMap.device_id == device_id,
            DeviceInstanceMap.instance_id == instance_id,
        )
        .first()
    )

    if not existing_map:
        mapping = DeviceInstanceMap(
            device_id=device_id,
            instance_id=instance_id,
        )
        db.add(mapping)

    db.commit()

    return {
        "device_id": device_id,
        "instance_id": instance_id,
        "message": "Device linked to instance successfully",
    }


@router.get("/instances")
async def list_instances(db: Session = Depends(get_db)):
    """
    List all instances (for the debug interface).
    """
    instances = db.query(Instance).all()
    return [inst.to_dict() for inst in instances]
