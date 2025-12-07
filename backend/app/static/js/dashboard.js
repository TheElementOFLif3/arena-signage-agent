// ---------------------------
// Helpers / globals
// ---------------------------
function showSkeletonRows() {
    const tbody = document.querySelector("#players-table tbody");
    if (!tbody) return;
    tbody.innerHTML = "";
    const skeletonCount = 3;

    for (let i = 0; i < skeletonCount; i++) {
        const tr = document.createElement("tr");
        tr.classList.add("skeleton-row");
        for (let c = 0; c < 8; c++) {
            const td = document.createElement("td");
            const bar = document.createElement("div");
            bar.className = "skeleton-bar";
            td.appendChild(bar);
            tr.appendChild(td);
        }
        tbody.appendChild(tr);
    }
}

function getTempClass(tempC) {
    if (tempC === null || tempC === undefined) return "";
    if (tempC < 55) return "temp-ok";
    if (tempC < 70) return "temp-warn";
    return "temp-hot";
}

let selectedPlayerId = null;
let selectedPlayerRow = null;
let playlistsLoadedOnce = false;
let allPlaylistsCache = null;

let userTimeZone = (Intl.DateTimeFormat().resolvedOptions().timeZone) || "Local";
let timeZoneShort = "LOCAL TIME";

try {
    const now = new Date();
    const locale = navigator.language || "en-US";
    const parts = new Intl.DateTimeFormat(locale, {
        timeZone: userTimeZone,
        timeZoneName: "short"
    }).formatToParts(now);
    const tzPart = parts.find(p => p.type === "timeZoneName");
    if (tzPart && tzPart.value) {
        timeZoneShort = tzPart.value;
    }
} catch (err) {
    console.warn("Failed to resolve time zone name, using fallback.", err);
}

function formatLastRefresh(date) {
    try {
        const locale = navigator.language || "en-US";
        return date.toLocaleTimeString(locale, {
            hour12: false,
            hour: "2-digit",
            minute: "2-digit",
            second: "2-digit",
            timeZone: userTimeZone
        }) + " " + timeZoneShort;
    } catch {
        return date.toISOString().split("T")[1].split(".")[0] + " " + timeZoneShort;
    }
}

function clearSelectedRowHighlight() {
    if (selectedPlayerRow) {
        selectedPlayerRow.classList.remove("row-selected");
    }
}

function setSelectedRowHighlight(row) {
    clearSelectedRowHighlight();
    selectedPlayerRow = row;
    if (selectedPlayerRow) {
        selectedPlayerRow.classList.add("row-selected");
    }
}

function setPlaylistControlsEnabled(enabled) {
    const select = document.getElementById("active-playlist-select");
    const assignBtn = document.getElementById("playlist-assign-btn");
    const clearBtn = document.getElementById("playlist-clear-btn");
    const refreshBtn = document.getElementById("playlist-refresh-btn");

    if (!select || !assignBtn || !clearBtn || !refreshBtn) return;

    select.disabled = !enabled;
    assignBtn.disabled = !enabled;
    clearBtn.disabled = !enabled;
    refreshBtn.disabled = !enabled;
}

// ---------------------------
// Weather
// ---------------------------
async function fetchPlayerWeather(player, cell) {
    if (!player.city || !player.country_code) {
        cell.innerHTML = `<span class="small">n/a</span>`;
        return;
    }

    cell.innerHTML = `<span class="small">loading…</span>`;

    try {
        const resp = await fetch(`/players/${player.id}/weather`);
        if (!resp.ok) throw new Error("HTTP " + resp.status);

        const data = await resp.json();
        const w = data.weather || {};

        const temp = w.temp_display;
        const unit = w.temp_unit || "C";

        if (temp === null || temp === undefined) {
            cell.innerHTML = `<span class="small">n/a</span>`;
            return;
        }

        const parts = [];
        parts.push(`${temp}°${unit}`);
        if (data.city) parts.push(data.city);

        cell.innerHTML = `<div class="small">${parts.join(" – ")}</div>`;
    } catch (err) {
        console.error("Failed to load weather for player", player.id, err);
        cell.innerHTML = `<span class="small">n/a</span>`;
    }
}

// ---------------------------
// Active playlist selector
// ---------------------------
async function loadPlaylistsForSelector(currentPlaylistId) {
    const select = document.getElementById("active-playlist-select");
    const assignBtn = document.getElementById("playlist-assign-btn");
    const clearBtn = document.getElementById("playlist-clear-btn");

    if (!select || !assignBtn || !clearBtn) return;

    select.disabled = true;
    assignBtn.disabled = true;
    clearBtn.disabled = selectedPlayerId == null;
    select.innerHTML = `<option value="">Loading playlists…</option>`;

    try {
        if (!allPlaylistsCache) {
            const resp = await fetch("/playlists/");
            if (!resp.ok) throw new Error("HTTP " + resp.status);
            allPlaylistsCache = await resp.json();
        }

        const playlists = allPlaylistsCache || [];
        if (!playlists.length) {
            select.innerHTML = `<option value="">No playlists defined</option>`;
            return;
        }

        let optionsHtml = `<option value="">Select active playlist…</option>`;
        playlists.forEach((pl) => {
            const name = pl.name || "Untitled playlist";
            optionsHtml += `<option value="${pl.id}">${name}</option>`;
        });

        select.innerHTML = optionsHtml;

        if (currentPlaylistId) {
            select.value = String(currentPlaylistId);
        }

        select.disabled = false;
        assignBtn.disabled = false;
        clearBtn.disabled = false;
    } catch (err) {
        console.error("Failed to load playlists for selector:", err);
        select.innerHTML = `<option value="">Error loading playlists</option>`;
    }
}

function syncSelectorWithPlaylist(pkg) {
    const select = document.getElementById("active-playlist-select");
    if (!select) return;

    const playlistId = pkg && pkg.playlist_id ? String(pkg.playlist_id) : "";
    if (playlistId && Array.from(select.options).some(o => o.value === playlistId)) {
        select.value = playlistId;
    } else if (!playlistId) {
        select.value = "";
    }
}

async function setActivePlaylistForPlayer(playerId, playlistId) {
    if (playerId == null) return;

    const subtitle = document.getElementById("playlist-subtitle");
    const select = document.getElementById("active-playlist-select");
    const assignBtn = document.getElementById("playlist-assign-btn");
    const clearBtn = document.getElementById("playlist-clear-btn");

    try {
        if (playlistId === null) {
            subtitle.textContent = `Clearing active playlist for player ${playerId}…`;
        } else {
            subtitle.textContent = `Setting active playlist for player ${playerId}…`;
        }

        if (select) select.disabled = true;
        if (assignBtn) assignBtn.disabled = true;
        if (clearBtn) clearBtn.disabled = true;

        const resp = await fetch(`/players/${playerId}/active-playlist`, {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ playlist_id: playlistId }),
        });

        if (!resp.ok) throw new Error("HTTP " + resp.status);
        await resp.json();

        if (playlistId === null) {
            subtitle.textContent = `Active playlist cleared for player ${playerId}.`;
        } else {
            subtitle.textContent = `Active playlist set for player ${playerId}.`;
        }

        fetchPlayerPlaylist(playerId);

        if (playlistId === null && select) {
            select.value = "";
        }
    } catch (err) {
        console.error("Failed to update active playlist:", err);
        subtitle.textContent = `Failed to update active playlist for player ${playerId}.`;
    } finally {
        if (select) select.disabled = false;
        if (assignBtn) assignBtn.disabled = false;
        if (clearBtn) clearBtn.disabled = false;
    }
}

// ---------------------------
// Playlist package panel
// ---------------------------
function renderPlaylistPackage(pkg) {
    const body = document.getElementById("player-playlist-body");
    const subtitle = document.getElementById("playlist-subtitle");

    if (!pkg) {
        body.innerHTML = `
            <div style="padding: 16px;">
                <span class="muted-pill">
                    No active playlist for this player.
                </span>
            </div>
        `;
        subtitle.textContent = "No active playlist assigned.";
        syncSelectorWithPlaylist(null);
        return;
    }

    const items = pkg.items || [];
    subtitle.textContent =
        `Player ${pkg.player_id} – playlist "${pkg.playlist_name || "Untitled"}" (${items.length} item(s))`;

    syncSelectorWithPlaylist(pkg);

    const updated = pkg.playlist_updated_at || "n/a";
    const timezone = pkg.timezone || "device default";

    let html = "";

    html += `<div style="padding: 14px 16px 10px 16px;">`;
    html += `<div class="playlist-details-grid">`;
    html += `
        <div>
            <div class="playlist-details-label">Playlist</div>
            <div>${pkg.playlist_name || "Untitled"} (#${pkg.playlist_id || "n/a"})</div>
        </div>
    `;
    html += `
        <div>
            <div class="playlist-details-label">Last updated</div>
            <div>${updated}</div>
        </div>
    `;
    html += `
        <div>
            <div class="playlist-details-label">Items</div>
            <div>${items.length}</div>
        </div>
    `;
    html += `
        <div>
            <div class="playlist-details-label">Timezone</div>
            <div>${timezone}</div>
        </div>
    `;
    html += `</div>`;
    html += `</div>`;

    html += `
        <div style="border-top: 1px solid var(--border-soft); padding: 10px 0 0 0;">
            <div style="overflow-x:auto;">
                <table class="playlist-items-table">
                    <thead>
                        <tr>
                            <th>#</th>
                            <th>Position</th>
                            <th>Type</th>
                            <th>Duration</th>
                            <th>Media URL</th>
                            <th>Checksum</th>
                            <th>Valid From</th>
                            <th>Valid Until</th>
                        </tr>
                    </thead>
                    <tbody>
    `;

    if (!items.length) {
        html += `
            <tr>
                <td colspan="8" class="small">Playlist has no items.</td>
            </tr>
        `;
    } else {
        items.forEach((it, idx) => {
            const pos = (it.position !== null && it.position !== undefined)
                ? it.position
                : idx;

            const duration = it.duration_seconds != null
                ? `${it.duration_seconds}s`
                : "auto";

            const shortUrl = it.media_url
                ? (it.media_url.length > 60
                    ? it.media_url.slice(0, 57) + "…"
                    : it.media_url)
                : "n/a";

            const checksum = it.checksum
                ? (it.checksum.length > 16
                    ? it.checksum.slice(0, 13) + "…"
                    : it.checksum)
                : "n/a";

            html += `
                <tr>
                    <td>${idx + 1}</td>
                    <td>${pos}</td>
                    <td>${it.media_type || "n/a"}</td>
                    <td>${duration}</td>
                    <td><span class="small" title="${it.media_url || ""}">${shortUrl}</span></td>
                    <td><span class="small" title="${it.checksum || ""}">${checksum}</span></td>
                    <td><span class="small">${it.valid_from || ""}</span></td>
                    <td><span class="small">${it.valid_until || ""}</span></td>
                </tr>
            `;
        });
    }

    html += `
                    </tbody>
                </table>
            </div>
        </div>
    `;

    body.innerHTML = html;
}

async function fetchPlayerPlaylist(playerId) {
    const body = document.getElementById("player-playlist-body");
    const subtitle = document.getElementById("playlist-subtitle");
    const refreshBtn = document.getElementById("playlist-refresh-btn");

    subtitle.textContent = `Loading playlist for player ${playerId}…`;
    body.innerHTML = `
        <div style="padding: 16px;">
            <span class="small">Loading playlist…</span>
        </div>
    `;

    if (refreshBtn) refreshBtn.disabled = true;

    try {
        const resp = await fetch(`/players/${playerId}/playlist`);
        if (resp.status === 404) {
            renderPlaylistPackage(null);
            return;
        }
        if (!resp.ok) throw new Error("HTTP " + resp.status);

        const pkg = await resp.json();
        renderPlaylistPackage(pkg);
    } catch (err) {
        console.error("Failed to load playlist for player", playerId, err);
        subtitle.textContent = `Failed to load playlist for player ${playerId}.`;
        body.innerHTML = `
            <div style="padding: 16px;">
                <span class="small">Error loading playlist package.</span>
            </div>
        `;
    } finally {
        if (refreshBtn) refreshBtn.disabled = false;
    }
}

function handlePlayerRowClick(player) {
    selectedPlayerId = player.id;

    const tbody = document.querySelector("#players-table tbody");
    const rows = Array.from(tbody.querySelectorAll("tr"));
    rows.forEach((row) => {
        if (parseInt(row.getAttribute("data-player-id"), 10) === player.id) {
            setSelectedRowHighlight(row);
        }
    });

    setPlaylistControlsEnabled(true);
    loadPlaylistsForSelector(null);
    fetchPlayerPlaylist(player.id);
}

// ---------------------------
// Render players
// ---------------------------
function renderPlayers(players) {
    const tbody = document.querySelector("#players-table tbody");
    tbody.innerHTML = "";

    let onlineCount = 0;

    players.forEach((p) => {
        const tr = document.createElement("tr");
        tr.classList.add("row-selectable");
        tr.setAttribute("data-player-id", p.id);
        if (p.is_online) onlineCount++;

        const tdId = document.createElement("td");
        tdId.textContent = p.id;
        tr.appendChild(tdId);

        const tdPlayer = document.createElement("td");
        tdPlayer.innerHTML = `
            <div>${p.name}</div>
            <div class="small">${p.device_id}</div>
        `;
        tr.appendChild(tdPlayer);

        const tdStatus = document.createElement("td");
        if (p.is_online) {
            tdStatus.innerHTML = `
                <span class="badge badge-online">
                    <span class="badge-dot"></span> Online
                </span>
            `;
        } else {
            tdStatus.innerHTML = `
                <span class="badge badge-offline">
                    <span class="badge-dot"></span> Offline
                </span>
            `;
        }
        tr.appendChild(tdStatus);

        const tdTemp = document.createElement("td");
        if (p.temperature_c !== null && p.temperature_c !== undefined) {
            const tempC = p.temperature_c;
            const tempClass = getTempClass(tempC);

            let displayTemp = tempC;
            let unit = "°C";

            if (p.uses_fahrenheit) {
                displayTemp = Math.round(tempC * 9 / 5 + 32);
                unit = "°F";
            }

            tdTemp.innerHTML =
                `<span class="${tempClass}">${displayTemp}${unit}</span>`;
        } else {
            tdTemp.innerHTML = `<span class="small">n/a</span>`;
        }
        tr.appendChild(tdTemp);

        const tdWeather = document.createElement("td");
        tdWeather.innerHTML = `<span class="small">loading…</span>`;
        tr.appendChild(tdWeather);

        const tdNet = document.createElement("td");
        if (p.network_type) {
            tdNet.innerHTML = `
                <span class="badge badge-net">${p.network_type}</span>
            `;
        } else {
            tdNet.innerHTML = `<span class="small">unknown</span>`;
        }
        tr.appendChild(tdNet);

        const tdLast = document.createElement("td");
        if (p.last_seen) {
            try {
                const dt = new Date(p.last_seen);
                const locale = navigator.language || "en-US";
                const formatted = dt.toLocaleString(locale, {
                    hour12: false,
                    year: "numeric",
                    month: "2-digit",
                    day: "2-digit",
                    hour: "2-digit",
                    minute: "2-digit",
                    second: "2-digit",
                    timeZone: userTimeZone
                });
                const [datePart, timePart] = formatted.split(",").map(s => s.trim());
                tdLast.innerHTML = `
                    <div class="small">
                        ${datePart}<br>${timePart} ${timeZoneShort}
                    </div>
                `;
            } catch (err) {
                console.warn("Failed to format last_seen, using raw.", err);
                tdLast.innerHTML = `<span class="small">${p.last_seen}</span>`;
            }
        } else {
            tdLast.innerHTML = `<span class="small">never</span>`;
        }
        tr.appendChild(tdLast);

        const tdLoc = document.createElement("td");
        const city = p.city || "Unknown";
        const arena = p.arena_name ? " – " + p.arena_name : "";
        if (p.city || p.arena_name) {
            tdLoc.innerHTML = `<div class="small">${city}${arena}</div>`;
        } else {
            tdLoc.innerHTML = `<span class="small">n/a</span>`;
        }
        tr.appendChild(tdLoc);

        tr.addEventListener("click", () => {
            handlePlayerRowClick(p);
        });

        if (selectedPlayerId !== null && p.id === selectedPlayerId) {
            setSelectedRowHighlight(tr);
        }

        tbody.appendChild(tr);
        fetchPlayerWeather(p, tdWeather);
    });

    const summary = document.getElementById("summary-text");
    summary.textContent = `Players online: ${onlineCount} / ${players.length}`;
}

// ---------------------------
// Refresh players from backend
// ---------------------------
async function refreshStatus() {
    const btn = document.getElementById("refresh-btn");

    showSkeletonRows();

    try {
        btn.disabled = true;
        btn.textContent = "Refreshing…";

        const resp = await fetch("/players/status");
        if (!resp.ok) throw new Error("HTTP " + resp.status);

        const data = await resp.json();
        renderPlayers(data);

        const now = new Date();
        document.getElementById("last-refresh-label").textContent =
            "Last refresh: " + formatLastRefresh(now);
    } catch (err) {
        console.error("Failed to refresh player status:", err);
        document.getElementById("summary-text").textContent =
            "Error loading player status";

        const tbody = document.querySelector("#players-table tbody");
        tbody.innerHTML = `
            <tr>
                <td colspan="8">
                    <span class="small">Error loading players.</span>
                </td>
            </tr>
        `;
    } finally {
        btn.disabled = false;
        btn.textContent = "Refresh now";
    }
}

// ---------------------------
// All playlists view (tab)
// ---------------------------
function renderPlaylists(playlists) {
    const tbody = document.querySelector("#playlists-table tbody");
    tbody.innerHTML = "";

    if (!playlists || playlists.length === 0) {
        const tr = document.createElement("tr");
        const td = document.createElement("td");
        td.colSpan = 7;
        td.innerHTML = `<span class="small">No playlists defined yet.</span>`;
        tr.appendChild(td);
        tbody.appendChild(tr);
        return;
    }

    playlists.forEach((pl) => {
        const tr = document.createElement("tr");

        const tdId = document.createElement("td");
        tdId.textContent = pl.id;
        tr.appendChild(tdId);

        const tdName = document.createElement("td");
        const desc = pl.description || "";
        tdName.innerHTML = `
            <div>${pl.name || "Untitled playlist"}</div>
            ${desc ? `<div class="small">${desc}</div>` : ""}
        `;
        tr.appendChild(tdName);

        const tdScope = document.createElement("td");
        const scope = pl.scope || "global";
        tdScope.innerHTML = `
            <span class="badge badge-pill-soft">${scope}</span>
        `;
        tr.appendChild(tdScope);

        const tdStatus = document.createElement("td");
        const active = (pl.is_active === undefined || pl.is_active === null)
            ? true
            : !!pl.is_active;
        tdStatus.innerHTML = active
            ? `<span class="badge badge-online"><span class="badge-dot"></span>Active</span>`
            : `<span class="badge badge-offline"><span class="badge-dot"></span>Disabled</span>`;
        tr.appendChild(tdStatus);

        const tdItems = document.createElement("td");
        const itemCount =
            typeof pl.item_count === "number"
                ? pl.item_count
                : (pl.items ? pl.items.length : 0);
        tdItems.textContent = itemCount;
        tr.appendChild(tdItems);

        const tdUpdated = document.createElement("td");
        const updated = pl.updated_at || pl.created_at || null;
        tdUpdated.innerHTML = updated
            ? `<span class="small">${updated}</span>`
            : `<span class="small">n/a</span>`;
        tr.appendChild(tdUpdated);

        const tdOwner = document.createElement("td");
        const ownerType = pl.owner_type || "n/a";
        const ownerLabel = pl.owner_name || "";
        tdOwner.innerHTML = ownerLabel
            ? `<div class="small">${ownerType} – ${ownerLabel}</div>`
            : `<span class="small">${ownerType}</span>`;
        tr.appendChild(tdOwner);

        tbody.appendChild(tr);
    });
}

async function refreshPlaylists() {
    const tbody = document.querySelector("#playlists-table tbody");
    const btn = document.getElementById("playlists-refresh-btn");

    try {
        if (btn) {
            btn.disabled = true;
            btn.textContent = "Loading…";
        }

        const resp = await fetch("/playlists/");
        if (!resp.ok) throw new Error("HTTP " + resp.status);

        const data = await resp.json();
        allPlaylistsCache = data;
        renderPlaylists(data);
        playlistsLoadedOnce = true;
    } catch (err) {
        console.error("Failed to load playlists:", err);
        tbody.innerHTML = `
            <tr>
                <td colspan="7">
                    <span class="small">Error loading playlists.</span>
                </td>
            </tr>
        `;
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.textContent = "Reload";
        }
    }
}

// ---------------------------
// View switching (sidebar + top tabs)
// ---------------------------
function showView(view) {
    const playersView = document.getElementById("players-view");
    const playerPlaylistView = document.getElementById("player-playlist-view");
    const playlistsView = document.getElementById("playlists-view");

    if (!playersView || !playerPlaylistView || !playlistsView) return;

    if (view === "players") {
        playersView.style.display = "";
        playerPlaylistView.style.display = "";
        playlistsView.style.display = "none";
    } else if (view === "playlists") {
        playersView.style.display = "none";
        playerPlaylistView.style.display = "none";
        playlistsView.style.display = "";
        if (!playlistsLoadedOnce) {
            refreshPlaylists();
        }
    }

    document.querySelectorAll(".nav-tab[data-view]").forEach((btn) => {
        if (btn.getAttribute("data-view") === view) {
            btn.classList.add("nav-tab-active");
        } else {
            btn.classList.remove("nav-tab-active");
        }
    });

    document.querySelectorAll(".top-tab[data-view]").forEach((btn) => {
        if (btn.getAttribute("data-view") === view) {
            btn.classList.add("top-tab-active");
        } else {
            btn.classList.remove("top-tab-active");
        }
    });
}

// ---------------------------
// THEME HANDLING
// ---------------------------
function applyTheme(theme) {
    const body = document.body;
    const btn = document.getElementById("theme-toggle-btn");
    if (!body || !btn) return;

    body.setAttribute("data-theme", theme);
    localStorage.setItem("arenaTheme", theme);

    btn.textContent = "Light / Dark";
}

function initTheme() {
    let theme = localStorage.getItem("arenaTheme");
    if (!theme) {
        const prefersDark = window.matchMedia &&
            window.matchMedia("(prefers-color-scheme: dark)").matches;
        theme = prefersDark ? "dark" : "light";
    }
    applyTheme(theme);

    if (window.matchMedia) {
        window.matchMedia("(prefers-color-scheme: dark)")
            .addEventListener("change", (e) => {
                const stored = localStorage.getItem("arenaTheme");
                if (stored) return;
                applyTheme(e.matches ? "dark" : "light");
            });
    }
}

// ---------------------------
// Event wiring / bootstrap
// ---------------------------
window.addEventListener("load", () => {
    initTheme();
    showView("players");
    setPlaylistControlsEnabled(false);

    // Buttons
    const refreshBtn = document.getElementById("refresh-btn");
    if (refreshBtn) {
        refreshBtn.addEventListener("click", refreshStatus);
    }

    const playlistsReloadBtn = document.getElementById("playlists-refresh-btn");
    if (playlistsReloadBtn) {
        playlistsReloadBtn.addEventListener("click", refreshPlaylists);
    }

    const playlistsNewBtn = document.getElementById("playlists-new-btn");
    if (playlistsNewBtn) {
        playlistsNewBtn.addEventListener("click", () => {
            alert("Playlist editor is not implemented yet. Layout only for now.");
        });
    }

    const playlistRefreshBtn = document.getElementById("playlist-refresh-btn");
    if (playlistRefreshBtn) {
        playlistRefreshBtn.addEventListener("click", () => {
            if (selectedPlayerId != null) {
                fetchPlayerPlaylist(selectedPlayerId);
            }
        });
    }

    const playlistAssignBtn = document.getElementById("playlist-assign-btn");
    if (playlistAssignBtn) {
        playlistAssignBtn.addEventListener("click", () => {
            if (selectedPlayerId == null) return;
            const select = document.getElementById("active-playlist-select");
            if (!select || !select.value) return;
            const pid = parseInt(select.value, 10);
            if (!pid) return;
            setActivePlaylistForPlayer(selectedPlayerId, pid);
        });
    }

    const playlistClearBtn = document.getElementById("playlist-clear-btn");
    if (playlistClearBtn) {
        playlistClearBtn.addEventListener("click", () => {
            if (selectedPlayerId == null) return;
            setActivePlaylistForPlayer(selectedPlayerId, null);
        });
    }

    document.querySelectorAll(".nav-tab[data-view]").forEach((btn) => {
        btn.addEventListener("click", () => {
            if (btn.disabled) return;
            const view = btn.getAttribute("data-view");
            if (!view) return;
            showView(view);
        });
    });

    document.querySelectorAll(".top-tab[data-view]").forEach((btn) => {
        btn.addEventListener("click", () => {
            const view = btn.getAttribute("data-view");
            if (!view) return;
            showView(view);
        });
    });

    const themeToggleBtn = document.getElementById("theme-toggle-btn");
    if (themeToggleBtn) {
        themeToggleBtn.addEventListener("click", () => {
            const cur = document.body.getAttribute("data-theme") || "light";
            applyTheme(cur === "light" ? "dark" : "light");
        });
    }

    // Header timezone label
    const headerLabel = document.getElementById("last-seen-header-label");
    if (headerLabel) {
        headerLabel.textContent = `(${timeZoneShort})`;
    }

    // Auto-refresh label (5 minutes)
    const autoRefreshLabel = document.getElementById("auto-refresh-label");
    if (autoRefreshLabel) {
        autoRefreshLabel.textContent = "Auto-refresh: every 5 minutes (players)";
    }

    // Initial load
    refreshStatus();

    // Auto-refresh every 5 minutes (300000 ms)
    setInterval(() => {
        const pv = document.getElementById("players-view");
        if (pv && pv.style.display === "none") return;
        refreshStatus();
    }, 300000);
});